#!/usr/bin/env python3
"""Run the preregistered H57 real-raster experiment; never contacts the portal.

Example:
  PYTHONPATH=src ./.venv/bin/python scripts/run_h57_real.py \
    --data-dir /tmp/gems52-restored-core --stage all

The input directory must contain SHA-pinned training_features.tif, labels.tif, and
sample_submission.tif. The resulting download is a research artifact unless the
spatial gate, format/novelty gates, and independent confirmation all pass. This
runner never uploads or spends a competition submission slot.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import zipfile

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

from gems52 import emit, gates, h57, metric, spatial

PREREG_PATH = ROOT / "registry/h57_preregistration.json"
WORK = ROOT / "work/h57"
EVIDENCE = ROOT / "evidence"
FEATURES = WORK / "features"
BUFFER_PX = 80
BUDGET = 37_654
NEGATIVE_COLLAR_PX = 3
LEARNER = dict(max_iter=120, max_leaf_nodes=15, learning_rate=0.08,
               l2_regularization=2.0, min_samples_leaf=80,
               early_stopping=False, class_weight="balanced")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {message}", flush=True)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: str | Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(obj), indent=2, allow_nan=False) + "\n")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _input_paths(data_dir: Path) -> dict[str, Path]:
    return {"training_features.tif": data_dir / "training_features.tif",
            "labels.tif": data_dir / "labels.tif",
            "sample_submission.tif": data_dir / "sample_submission.tif"}


def verify_input_pins(data_dir: Path, prereg: dict) -> dict:
    expected = prereg["input_files"]
    actual = {}
    for name, path in _input_paths(data_dir).items():
        if not path.is_file():
            raise FileNotFoundError(f"missing H57 input: {path}")
        row = dict(bytes=path.stat().st_size, sha256=h57.sha256_file(path))
        expected_row = expected[name]
        if row["bytes"] != expected_row["bytes"] or row["sha256"] != expected_row["sha256"]:
            raise ValueError(f"H57 input does not match its frozen integrity pin: {name} {row}")
        actual[name] = row
    return actual


def _indices_digest(rows: np.ndarray) -> str:
    return digest_bytes(np.asarray(rows, dtype="<i8").tobytes())


def _model_signature(store: h57.FeatureStore, view: str, rows: np.ndarray,
                     y: np.ndarray, seed: int, pseudo: np.ndarray | None,
                     prereg_sha: str) -> str:
    payload = dict(
        preregistration_sha256=prereg_sha,
        builder_sha256=h57.sha256_file(Path(h57.__file__)),
        runner_sha256=h57.sha256_file(Path(__file__)),
        feature_manifest_sha256=h57.sha256_file(store.directory / "manifest.json"),
        view=view, rows_sha256=_indices_digest(rows),
        y_sha256=digest_bytes(np.asarray(y, dtype=np.int8).tobytes()),
        pseudo_sha256=_indices_digest(pseudo) if pseudo is not None else None,
        seed=int(seed), learner=LEARNER,
        sklearn=__import__("sklearn").__version__)
    return digest_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def fit_cached(store: h57.FeatureStore, view: str, rows: np.ndarray, y: np.ndarray,
               seed: int, folder: Path, prereg_sha: str,
               pseudo: np.ndarray | None = None):
    folder.mkdir(parents=True, exist_ok=True)
    model_path = folder / f"view_{view}_{'cotrain' if pseudo is not None else 'base'}.joblib"
    receipt_path = model_path.with_suffix(".json")
    signature = _model_signature(store, view, rows, y, seed, pseudo, prereg_sha)
    if model_path.is_file() and receipt_path.is_file():
        try:
            if json.loads(receipt_path.read_text()).get("signature") == signature:
                log(f"cache hit: {model_path.relative_to(ROOT)}")
                return joblib.load(model_path)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    model = h57.fit_classifier(store, view, rows, y, seed, pseudo_rows=pseudo,
                               pseudo_weight=0.25, learner_config=LEARNER)
    joblib.dump(model, model_path, compress=3)
    write_json(receipt_path, dict(signature=signature, view=view, seed=int(seed),
                                  training_rows=int(len(rows)), pseudo_rows=int(0 if pseudo is None else len(pseudo)),
                                  model_sha256=h57.sha256_file(model_path)))
    return model


def _training_reference(prediction: np.ndarray, train: np.ndarray,
                        unlabeled_pool: np.ndarray) -> np.ndarray:
    mask = np.asarray(train, bool) & np.asarray(unlabeled_pool, bool) & np.isfinite(prediction)
    return np.asarray(prediction[mask], dtype=np.float32)


def select_pseudo_for_fold(store: h57.FeatureStore, model_a, model_b,
                           train: np.ndarray, catalogue: np.ndarray,
                           near_catalogue: np.ndarray, fold_dir: Path,
                           minimum: int = 200, cap: int = 2000) -> dict:
    """Measure both allowed exchanges in the train domain without touching the eval region."""
    p_a = h57.predict_domain(store, model_a, "A", train)
    p_b = h57.predict_domain(store, model_b, "B", train)
    unlabeled = train & store.valid & ~catalogue & ~near_catalogue
    ref_a, ref_b = p_a[unlabeled], p_b[unlabeled]
    if not len(ref_a) or not len(ref_b):
        return dict(eligible=False, reason="no finite unlabeled training reference", pseudo_a_to_b=[], pseudo_b_to_a=[])
    qa = np.quantile(ref_a, [0.4, 0.8, 0.99])
    qb = np.quantile(ref_b, [0.4, 0.8, 0.99])
    forbidden = ~train | near_catalogue | ~store.valid
    ids_a, receipts_a = spatial.whole_pseudo_segments(
        p_a, p_b, train, forbidden, float(qa[2]), float(qb[0]), float(qb[1]),
        side=50, min_pixels=5, cap=cap)
    ids_b, receipts_b = spatial.whole_pseudo_segments(
        p_b, p_a, train, forbidden, float(qb[2]), float(qa[0]), float(qa[1]),
        side=50, min_pixels=5, cap=cap)
    fold_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(fold_dir / "pseudo_rows.npz", a_to_b=ids_a, b_to_a=ids_b)
    passes = len(ids_a) >= minimum and len(ids_b) >= minimum
    return dict(eligible=bool(passes),
                reason="both directions met the registered minimum" if passes else "one or both directions below 200 whole-segment pixels",
                thresholds=dict(A_confident=float(qa[2]), B_confident=float(qb[2]),
                               A_abstain=[float(qa[0]), float(qa[1])],
                               B_abstain=[float(qb[0]), float(qb[1])]),
                pseudo_A_confident_B_abstains=int(len(ids_a)),
                pseudo_B_confident_A_abstains=int(len(ids_b)),
                whole_components_A_to_B=receipts_a, whole_components_B_to_A=receipts_b,
                pseudo_index_sha256_A_to_B=_indices_digest(ids_a),
                pseudo_index_sha256_B_to_A=_indices_digest(ids_b),
                pseudo_rows_file=str(fold_dir / "pseudo_rows.npz"))


def _fold_prediction_cache(store: h57.FeatureStore, fold: dict, fold_dir: Path,
                           model_a, model_b, signature: str) -> tuple[np.ndarray, np.ndarray]:
    path = fold_dir / "base_region_scores.npz"
    receipt = fold_dir / "base_region_scores.json"
    if path.is_file() and receipt.is_file():
        try:
            if json.loads(receipt.read_text()).get("signature") == signature:
                with np.load(path) as z:
                    return z["ids"], z["p_a"], z["p_b"]
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    region = fold["region"] & store.valid
    ids = np.flatnonzero(region.ravel())
    p_a = h57.predict_domain(store, model_a, "A", region).ravel()[ids]
    p_b = h57.predict_domain(store, model_b, "B", region).ravel()[ids]
    if not (np.isfinite(p_a).all() and np.isfinite(p_b).all()):
        raise ValueError("OOF predictions must cover every eligible evaluation pixel")
    np.savez_compressed(path, ids=ids, p_a=p_a.astype(np.float32), p_b=p_b.astype(np.float32))
    write_json(receipt, dict(signature=signature, fold=int(fold["fold"]),
                             region_pixels=int(len(ids)), prediction_sha256_A=digest_bytes(p_a.astype('<f4').tobytes()),
                             prediction_sha256_B=digest_bytes(p_b.astype('<f4').tobytes())))
    return ids, p_a, p_b


def _full_prediction_map(shape: tuple[int, int], ids: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.full(int(np.prod(shape)), np.nan, dtype=np.float32)
    out[np.asarray(ids, dtype=np.int64)] = np.asarray(values, dtype=np.float32)
    return out.reshape(shape)


def _emit_score(density: np.ndarray, fold: dict, valid: np.ndarray,
                budget_global: int = BUDGET) -> tuple[np.ndarray, dict]:
    region = fold["region"] & valid
    visible = fold["visible"] & valid
    allowed = region & ~visible
    budget = int(round(budget_global * int(region.sum()) / max(int(valid.sum()), 1)))
    prediction, placement = emit.greedy_emit(
        np.asarray(density, np.float32), allowed, dti_projected=0.0, budget=budget,
        pool=400_000, hard_max=budget, log=lambda _message: None)
    prediction[~region | visible] = 0.0
    truth = fold["truth"] & region & valid
    result = metric.dti(prediction, truth)
    result.update(emitted=int((prediction > 0).sum()), fold_budget=budget,
                  truth_pixels=int(truth.sum()), eval_pixels=int(region.sum()), placement=placement)
    return prediction, result


def _release_memory() -> None:
    """Release large NumPy work buffers between full-grid folds where libc permits."""
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def _score_holdout_fold(store: h57.FeatureStore, prereg: dict, prereg_sha: str,
                        fold: dict, pseudo_report: dict, holdout_exchange: bool,
                        independence: dict, valid: np.ndarray, catalogue: np.ndarray,
                        near_catalogue: np.ndarray) -> dict:
    """Score one fold in a short-lived frame so full-resolution maps are promptly freed."""
    fi = int(fold["fold"])
    folder = WORK / f"fold_{fi}"
    with np.load(folder / "training_rows.npz") as z:
        rows, y = z["rows"], z["y"]
    seed = int(prereg["holdout_protocol"]["seed"]) + fi
    model_a = fit_cached(store, "A", rows, y, seed, folder, prereg_sha)
    model_b = fit_cached(store, "B", rows, y, seed, folder, prereg_sha)
    score_path = folder / "base_region_scores.npz"
    with np.load(score_path) as z:
        ids, pa_region, pb_region = z["ids"], z["p_a"], z["p_b"]
    p_a_base = _full_prediction_map(store.shape, ids, pa_region)
    p_b_base = _full_prediction_map(store.shape, ids, pb_region)
    train_a = h57.predict_domain(store, model_a, "A", fold["train"])
    train_b = h57.predict_domain(store, model_b, "B", fold["train"])
    train_unlabeled = fold["train"] & valid & ~catalogue & ~near_catalogue
    reference_a_base = _training_reference(train_a, fold["train"], train_unlabeled)
    reference_b_base = _training_reference(train_b, fold["train"], train_unlabeled)
    domain = fold["region"] & valid
    base_fields, base_meta = h57.disagreement_field(
        p_a_base, p_b_base, reference_a_base, reference_b_base, domain)
    # The helper also returns a full 12M-cell strata raster for final explanation; do not serialize it per fold.
    base_meta.pop("strata", None)
    arms = {"view_A_supervised": base_fields["view_A"],
            "view_B_supervised": base_fields["view_B"],
            "matched_max_union": base_fields["matched_max_union"]}
    candidate_arm = "h57_disagreement_cotrain" if holdout_exchange else "view_B_fallback"
    candidate_meta = {"branch": "co-training" if holdout_exchange else "predeclared View-B fallback",
                      "base_field": base_meta}
    if holdout_exchange:
        with np.load(folder / "pseudo_rows.npz") as z:
            pseudo_a_to_b, pseudo_b_to_a = z["a_to_b"], z["b_to_a"]
        model_a_cotrain = fit_cached(store, "A", rows, y, seed, folder, prereg_sha,
                                     pseudo=pseudo_b_to_a)
        model_b_cotrain = fit_cached(store, "B", rows, y, seed, folder, prereg_sha,
                                     pseudo=pseudo_a_to_b)
        p_a_cotrain = h57.predict_domain(store, model_a_cotrain, "A", domain)
        p_b_cotrain = h57.predict_domain(store, model_b_cotrain, "B", domain)
        train_a_cotrain = h57.predict_domain(store, model_a_cotrain, "A", fold["train"])
        train_b_cotrain = h57.predict_domain(store, model_b_cotrain, "B", fold["train"])
        ref_a_cotrain = _training_reference(train_a_cotrain, fold["train"], train_unlabeled)
        ref_b_cotrain = _training_reference(train_b_cotrain, fold["train"], train_unlabeled)
        cotrain_fields, cotrain_meta = h57.disagreement_field(
            p_a_cotrain, p_b_cotrain, ref_a_cotrain, ref_b_cotrain, domain)
        # Retain summary counts/thresholds only; the full strata raster is not evidence JSON.
        cotrain_meta.pop("strata", None)
        arms[candidate_arm] = cotrain_fields["h57_disagreement"]
        candidate_meta.update(cotrain=cotrain_meta,
                              pseudo_A_confident_B_abstains=int(len(pseudo_a_to_b)),
                              pseudo_B_confident_A_abstains=int(len(pseudo_b_to_a)))
        del cotrain_fields, p_a_cotrain, p_b_cotrain, train_a_cotrain, train_b_cotrain
        del model_a_cotrain, model_b_cotrain, pseudo_a_to_b, pseudo_b_to_a
    else:
        arms["view_B_fallback"] = arms["view_B_supervised"]
        candidate_meta["reason"] = independence["reason"] if not independence["allow_exchange"] else \
            "one or more folds failed the registered whole-segment exchange minimum"

    del base_fields, p_a_base, p_b_base, train_a, train_b, reference_a_base, reference_b_base
    scores, emissions = {}, {}
    for name, density in arms.items():
        if name == "view_B_fallback":
            continue
        emitted, score = _emit_score(density, fold, valid)
        scores[name] = score
        emissions[name] = emitted > 0
        del emitted
    scores["view_B_fallback"] = scores["view_B_supervised"]
    emissions["view_B_fallback"] = emissions["view_B_supervised"]
    if candidate_arm == "view_B_fallback":
        candidate_score = scores["view_B_supervised"]
    else:
        candidate_score = scores[candidate_arm]
    max_union = emissions["matched_max_union"]
    candidate_mask = emissions[candidate_arm]
    union_equal_by_arm = {name: bool(np.array_equal(mask, max_union))
                          for name, mask in emissions.items()}
    not_union = dict(equal=bool(np.array_equal(candidate_mask, max_union)),
                     intersection=int((candidate_mask & max_union).sum()),
                     candidate_pixels=int(candidate_mask.sum()), union_pixels=int(max_union.sum()),
                     candidate_only=int((candidate_mask & ~max_union).sum()),
                     union_only=int((max_union & ~candidate_mask).sum()))
    candidate_meta["matched_max_union"] = not_union
    result = dict(fold=fi, receipt=fold["receipt"], candidate_arm=candidate_arm,
                  candidate=candidate_score, arms=scores, candidate_not_union=not_union,
                  union_equal_by_arm=union_equal_by_arm, exchange=pseudo_report,
                  placement_budget_rule="37,654 * eligible region / eligible footprint",
                  candidate_metadata=candidate_meta)
    log(f"  fold {fi}: A={scores['view_A_supervised']['dti']:.6f}, "
        f"B={scores['view_B_supervised']['dti']:.6f}, "
        f"union={scores['matched_max_union']['dti']:.6f}, "
        f"candidate({candidate_arm})={candidate_score['dti']:.6f}")
    return result


def run_holdout(store: h57.FeatureStore, prereg: dict, prereg_sha: str) -> dict:
    """Run the four whole-component, 80-pixel spatial holdout and fail-closed exchange gate."""
    valid = np.asarray(store.valid, bool)
    catalogue = np.asarray(store.catalogue, bool)
    folds = list(spatial.folds(catalogue, valid, buffer_px=BUFFER_PX))
    if len(folds) != 4:
        raise AssertionError(f"expected 4 folds, got {len(folds)}")
    # Drop bulky fold-construction scratch maps not needed after component assignment.
    for fold in folds:
        for key in ("components", "quadrant", "held_all"):
            fold.pop(key, None)
    distance = ndi.distance_transform_edt(~catalogue)
    near_catalogue = distance <= NEGATIVE_COLLAR_PX
    del distance
    negative_rows, training_receipts = [], []
    log(f"H57 holdout: {len(folds)} whole-component spatial folds; 80 px buffer; {int(valid.sum()):,} eligible cells")

    # Base supervised models and OOF region scores: save predictions, not model/data arrays, in RAM.
    for fold in folds:
        fi = int(fold["fold"])
        folder = WORK / f"fold_{fi}"
        folder.mkdir(parents=True, exist_ok=True)
        rows, y, sample = h57.sample_training_rows(
            catalogue, valid, fold["train"], seed=int(prereg["holdout_protocol"]["seed"]) + fi,
            positive_cap=int(prereg["learner"]["training_positive_cap_per_fold"]),
            negative_cap=int(prereg["learner"]["training_negative_cap_per_fold"]),
            collar_px=NEGATIVE_COLLAR_PX)
        np.savez_compressed(folder / "training_rows.npz", rows=rows, y=y)
        seed = int(prereg["holdout_protocol"]["seed"]) + fi
        base_a = fit_cached(store, "A", rows, y, seed, folder, prereg_sha)
        base_b = fit_cached(store, "B", rows, y, seed, folder, prereg_sha)
        pred_signature = digest_bytes((
            _model_signature(store, "A", rows, y, seed, None, prereg_sha)
            + _model_signature(store, "B", rows, y, seed, None, prereg_sha)
            + digest_bytes(np.packbits(fold["region"]).tobytes())
        ).encode())
        ids, pa_region, pb_region = _fold_prediction_cache(store, fold, folder, base_a, base_b, pred_signature)
        pa_map = _full_prediction_map(store.shape, ids, pa_region)
        pb_map = _full_prediction_map(store.shape, ids, pb_region)
        negative_eval = fold["region"] & valid & ~near_catalogue
        block_rows = spatial.negative_block_errors(pa_map, pb_map, negative_eval, fi,
                                                   (0.5, 0.5), side=50, minimum=32)
        negative_rows.extend(block_rows)
        training_receipts.append(dict(
            **fold["receipt"], **sample,
            training_rows=int(len(rows)), training_index_sha256=_indices_digest(rows),
            training_negative_pool="catalogue-zero proxy; not verified absence",
            evaluation_out_of_fold_scores=int(np.isfinite(pa_region).sum()),
            negative_error_blocks=int(len(block_rows)),
            model_A_sha256=h57.sha256_file(folder / "view_A_base.joblib"),
            model_B_sha256=h57.sha256_file(folder / "view_B_base.joblib")))
        log(f"  fold {fi}: held={fold['receipt']['truth_px']:,}, train={fold['receipt']['training_domain_px']:,}, "
            f"OOF negatives blocks={len(block_rows)}")
        del base_a, base_b, rows, y, ids, pa_region, pb_region, pa_map, pb_map, negative_eval, block_rows
        _release_memory()

    independence = spatial.independence(
        negative_rows,
        threshold=float(prereg["co_training_gate"]["maximum_absolute_correlation"]),
        min_blocks=int(prereg["co_training_gate"]["minimum_usable_blocks"]))
    independence["measurement"] = "OOF per-view negative proxy errors by 50x50-pixel block; FPR threshold 0.5"
    independence["input_data_authentication"] = "owner-maintained mirror, SHA-pinned; not organizer-authenticated"
    independence["minimum_proxy_negatives_per_block"] = int(prereg["co_training_gate"]["minimum_proxy_negatives_per_block"])
    independence["correlation_gate_checks"] = ["Pearson", "tie-aware Spearman", "blockwise negative MSE", "blockwise FPR at 0.5"]
    independence["warning"] = "No verified geological-absence labels are supplied; this is only a catalogue-zero proxy diagnostic, not proof of co-training's conditional-independence assumptions."
    write_json(EVIDENCE / "h57_independence.json", independence)
    log(f"  proxy-error gate allow_exchange={independence['allow_exchange']} "
        f"max_abs_r={independence['max_abs_correlation']}; {independence['reason']}")

    pseudo_folds = []
    holdout_exchange = bool(independence["allow_exchange"])
    if holdout_exchange:
        for fold in folds:
            fi = int(fold["fold"])
            folder = WORK / f"fold_{fi}"
            with np.load(folder / "training_rows.npz") as z:
                rows, y = z["rows"], z["y"]
            seed = int(prereg["holdout_protocol"]["seed"]) + fi
            model_a = fit_cached(store, "A", rows, y, seed, folder, prereg_sha)
            model_b = fit_cached(store, "B", rows, y, seed, folder, prereg_sha)
            report = select_pseudo_for_fold(store, model_a, model_b, fold["train"],
                                            catalogue, near_catalogue, folder,
                                            minimum=200, cap=2000)
            report["fold"] = fi
            pseudo_folds.append(report)
            log(f"  fold {fi}: whole pseudo A→B={report.get('pseudo_A_confident_B_abstains', 0)}, "
                f"B→A={report.get('pseudo_B_confident_A_abstains', 0)}")
            del rows, y, model_a, model_b, report
            _release_memory()
        holdout_exchange = all(r.get("eligible", False) for r in pseudo_folds) and len(pseudo_folds) == 4
    else:
        pseudo_folds = [dict(fold=int(fold["fold"]), eligible=False,
                             reason="independence/proxy-error gate failed closed; exchange not measured")
                        for fold in folds]

    candidate_arm = "h57_disagreement_cotrain" if holdout_exchange else "view_B_fallback"
    fold_rows = []
    for fold, pseudo_report in zip(folds, pseudo_folds):
        fold_rows.append(_score_holdout_fold(store, prereg, prereg_sha, fold,
                                             pseudo_report, holdout_exchange,
                                             independence, valid, catalogue,
                                             near_catalogue))
        _release_memory()

    return dict(generated_utc=now(), preregistration_sha256=prereg_sha,
                protocol="four contiguous quadrants; original whole 8-connected mapped components; 80-pixel Euclidean buffer; metric-support neighborhood retained",
                feature_manifest_sha256=h57.sha256_file(FEATURES / "manifest.json"),
                feature_support_px=h57.MAX_SUPPORT_PX, external_data_used=False,
                negative_class="catalogue-zero proxy, not verified geological absence",
                candidate_arm_provisional=candidate_arm,
                independence=independence,
                pseudo_exchange_by_fold=pseudo_folds,
                training_receipts=training_receipts,
                arms={"view_A_supervised": "matched single-view baseline",
                      "view_B_supervised": "matched single-view baseline",
                      "matched_max_union": "same-budget maximum of supervised view ranks",
                      "h57_disagreement_cotrain": "predeclared disagreement-density field after one gated pseudo-exchange",
                      "view_B_fallback": "predeclared branch if exchange is abandoned"},
                folds=fold_rows,
                no_public_score_forecast=True,
                official_score=None,
                organizer_inputs_authenticated=False,
                submission_slots_used=0,
                caveats=[
                    "The competition feature/label rasters were restored from owner-maintained mirrors with matching SHA pins; organizer portal bytes were not authenticated.",
                    "A catalogue-zero cell is not a verified geological absence; blockwise errors and DTI are proxy holdout diagnostics.",
                    "Original raster connectivity is only a segment proxy, not an authenticated geological fault identifier.",
                    "Band 6's radiometric TC-like assignment is strongly corroborated against an owner mirror but is not named by the official USGS band mapping.",
                    "The metric-aware max-coverage greedy is a surrogate, not expected DTI or a public-score forecast.",
                    "No competition portal was contacted; no submission or weekly slot was used."])

def complete_holdout_gate(report: dict, selected_arm: str,
                          historical_floor: float,
                          artifact_receipt: dict | None = None) -> dict:
    folds = report["folds"]
    names = ("view_A_supervised", "view_B_supervised", "matched_max_union")
    means = {name: float(np.mean([fold["arms"][name]["dti"] for fold in folds])) for name in names}
    best = max(names, key=lambda name: means[name])
    candidate_scores = [float(fold["arms"][selected_arm]["dti"]) for fold in folds]
    candidate_mean = float(np.mean(candidate_scores))
    paired = [candidate_scores[i] - float(fold["arms"][best]["dti"]) for i, fold in enumerate(folds)]
    lift = candidate_mean - means[best]
    wins = int(sum(x > 0 for x in paired))
    historical_wins = None
    historical_folds = []
    try:
        prior = json.loads((EVIDENCE / "h55_profile_holdout.json").read_text())
        historical_name = "structural_contrast_h55"
        historical_folds = [float(fold["arms"][historical_name]["dti"]) for fold in prior["folds"]]
        historical_mean = float(prior["means"][historical_name])
        historical_wins = int(sum(candidate_scores[i] > historical_folds[i] for i in range(min(4, len(historical_folds)))))
        historical_sha = h57.sha256_file(EVIDENCE / "h55_profile_holdout.json")
    except (OSError, ValueError, KeyError, TypeError):
        historical_mean, historical_sha = None, None
    floor = historical_floor if historical_mean is None else float(historical_mean)
    any_union_equal = any(bool(fold.get("union_equal_by_arm", {}).get(
        selected_arm, fold["candidate_not_union"]["equal"])) for fold in folds)
    checks = dict(
        candidate_mean_dti=candidate_mean,
        matched_baseline_means=means,
        strongest_matched_baseline=best,
        mean_lift_over_strongest_matched_baseline=float(lift),
        paired_fold_lifts=paired,
        positive_paired_folds=wins,
        total_folds=len(folds),
        meets_mean_lift=bool(lift >= 0.005),
        meets_positive_fold_count=bool(wins >= 3),
        historical_internal_holdout_mean=float(floor) if floor is not None else None,
        historical_reference_sha256=historical_sha,
        candidate_beats_historical_internal_mean=bool(floor is not None and candidate_mean > floor),
        candidate_beats_historical_per_fold=int(historical_wins or 0),
        candidate_is_distinct_from_matched_max_union=not any_union_equal,
        scientific_gate_pass=bool(lift >= 0.005 and wins >= 3 and floor is not None
                                  and candidate_mean > floor and not any_union_equal),
        independent_confirmation_received=False,
        organizer_input_bytes_authenticated=False,
        portal_format_acceptance_tested=False,
        portal_upload_authorized=False,
        automatic_upload=False,
        submission_slots_used=0,
        approved_for_weekly_slot=False)
    reasons = []
    if not checks["meets_mean_lift"]:
        reasons.append("mean DTI lift over strongest matched baseline < 0.005")
    if not checks["meets_positive_fold_count"]:
        reasons.append("fewer than 3/4 paired folds improved")
    if floor is None or not checks["candidate_beats_historical_internal_mean"]:
        reasons.append("did not exceed the historical internal holdout reference floor")
    if any_union_equal:
        reasons.append("candidate equals the matched max-union in at least one outer fold")
    if not checks["scientific_gate_pass"]:
        reasons.append("spatial promotion gate failed; do not spend a weekly slot")
    if not checks["independent_confirmation_received"]:
        reasons.append("independent confirmation and organizer-format acceptance have not been obtained")
    if not checks["organizer_input_bytes_authenticated"]:
        reasons.append("model inputs are owner-mirrored, not organizer-authenticated")
    checks["reason"] = "; ".join(reasons) if reasons else "local research gate passed; human portal submission remains unauthorized"
    checks["candidate_artifact"] = artifact_receipt.get("file") if artifact_receipt else None
    return checks


def scan_aligned_priors(template_path: Path, inventory_path: Path, *,
                         exclude_candidate: Path | None = None) -> tuple[list[Path], dict]:
    public_prior_dir = Path(os.environ.get("GEMS52_H57_PUBLIC_PRIORS_DIR", "/tmp/gems52-competitor-priors"))
    roots = [ROOT / "submission", ROOT / "docs/downloads", ROOT / "data/reference",
             ROOT / "data/scored", ROOT / "data/review/priors", ROOT / "data/review/competitors",
             public_prior_dir]
    # Exclude both the candidate itself and staged copies by basename. Do not pass the inventory
    # JSON path here: doing so would leave the just-built submission inside its own prior scan.
    discovered = gates.find_priors(roots, exclude=exclude_candidate)
    public_manifest_path = EVIDENCE / "h57_public_repo_priors.json"
    public_sources = {}
    if public_manifest_path.is_file():
        try:
            public_manifest = json.loads(public_manifest_path.read_text())
            public_sources = {Path(row["fetched_path"]).resolve(): row
                              for row in public_manifest.get("files", [])
                              if row.get("fetched_path") and not row.get("error")}
        except (OSError, ValueError, KeyError, TypeError):
            public_manifest = {}
    else:
        public_manifest = {}
    aligned, skipped = [], []
    with rasterio.open(template_path) as template:
        for path in discovered:
            try:
                with rasterio.open(path) as prior:
                    if (prior.count == 1 and prior.shape == template.shape
                            and prior.crs == template.crs and prior.transform == template.transform
                            and prior.bounds == template.bounds):
                        aligned.append(path)
                    else:
                        skipped.append(dict(path=str(path), reason="not an aligned single-band prediction on the template grid"))
            except Exception as exc:  # malformed/unsupported local file is disclosed, not silently called checked
                skipped.append(dict(path=str(path), reason=f"{type(exc).__name__}: {str(exc)[:180]}"))
    aligned_rows = []
    unique_by_sha = {}
    aliases_by_sha = {}
    unique_paths = []
    for path in aligned:
        sha = h57.sha256_file(path)
        row = dict(path=str(path), bytes=path.stat().st_size, sha256=sha)
        source = public_sources.get(path.resolve())
        if source:
            row.update(source_repository=source.get("repository"), source_path=source.get("path"),
                       source_url=source.get("source_url"), source_tree_sha=source.get("tree_sha"),
                       source_blob_sha=source.get("blob_sha"), source_file_sha256=source.get("sha256"))
        else:
            row["source_url"] = None
            row["source_kind"] = "local repository submission/archive"
        aligned_rows.append(row)
        if sha in unique_by_sha:
            aliases_by_sha.setdefault(sha, [unique_by_sha[sha]])
            aliases_by_sha[sha].append(row)
        else:
            unique_by_sha[sha] = row
            unique_paths.append(path)
    duplicate_groups = [dict(sha256=sha, representative=rows[0]["path"],
                             exact_byte_aliases=[r["path"] for r in rows[1:]],
                             source_urls=[r.get("source_url") for r in rows if r.get("source_url")])
                        for sha, rows in aliases_by_sha.items()]
    inventory = dict(generated_utc=now(), roots=[str(x) for x in roots],
                     discovered_tif_count=len(discovered), aligned_prior_path_count=len(aligned),
                     aligned_unique_byte_contents=len(unique_paths),
                     exact_byte_duplicate_paths_collapsed=sum(len(r["exact_byte_aliases"]) for r in duplicate_groups),
                     aligned_files=aligned_rows, exact_byte_duplicate_groups=duplicate_groups, skipped=skipped,
                     public_sibling_repo_prior_manifest=(str(public_manifest_path) if public_manifest_path.is_file() else None),
                     public_repo_tiff_paths=int(public_manifest.get("candidate_tiff_paths", 0)),
                     public_repo_downloaded_tiff_paths=int(public_manifest.get("downloaded_tiff_paths", 0)),
                     public_repo_fetch_errors=int(public_manifest.get("fetch_errors", 0)),
                     public_repo_tree_truncations=int(public_manifest.get("recursive_tree_truncations", 0)),
                     scope="All locally aligned TIFF paths plus publicly committed TIFF assets fetched from the listed sibling GEMS repositories; exact-byte duplicates are represented once in decoded comparison and all aliases are enumerated. Inaccessible/private/unlinked/uncommitted assets are not checked.")
    write_json(inventory_path, inventory)
    return unique_paths, inventory


def _component_reasoning_csv(path: Path, store: h57.FeatureStore, strata_map: np.ndarray,
                             emitted: np.ndarray, p_a: np.ndarray, p_b: np.ndarray,
                             raw_path: Path) -> dict:
    """Describe all A-only and B-only disagreement components, selected or not.

    The A-only rows are geological hypotheses, not confirmed faults. B-only rows
    are flagged as possible surface/radiometric artifacts, not automatically
    discarded or labelled as artifacts.
    """
    width = store.shape[1]
    context_bands = (2, 6, 12, 13, 14, 15, 17, 19)
    all_components = []
    masks = {"A-only": strata_map == 2, "B-only": strata_map == 3}
    for view_name, candidate in masks.items():
        labels, _ = ndi.label(candidate, structure=np.ones((3, 3), dtype=bool))
        objects = ndi.find_objects(labels)
        for component, sl in enumerate(objects, 1):
            if sl is None:
                continue
            yy, xx = np.nonzero(labels[sl] == component)
            yy, xx = yy + sl[0].start, xx + sl[1].start
            flat = yy.astype(np.int64) * width + xx
            all_components.append(dict(view=view_name, component_id=component, flat=flat))

    candidate_ids = np.flatnonzero(((strata_map == 2) | (strata_map == 3)).ravel())
    features_a = store.gather(candidate_ids, "A")
    features_b = store.gather(candidate_ids, "B")
    names_a, names_b = store.names("A"), store.names("B")
    edge_indices = {
        "A-only": (features_a, names_a, [i for i, n in enumerate(names_a) if "_edge_sigma" in n]),
        "B-only": (features_b, names_b, [i for i, n in enumerate(names_b) if "_edge_sigma" in n]),
    }

    context_means, context_z = {}, {}
    with rasterio.open(raw_path) as source:
        transform = source.transform
        valid_flat = np.asarray(store.valid, bool).ravel()
        for band in context_bands:
            values = source.read(band).astype(np.float32).ravel()
            values[~np.isfinite(values) | (values < -1e30)] = np.nan
            sampled = values[valid_flat]
            global_mean, global_std = float(np.nanmean(sampled)), float(np.nanstd(sampled))
            for item in all_components:
                component = (item["view"], item["component_id"])
                mean = float(np.nanmean(values[item["flat"]]))
                context_means.setdefault(component, {})[band] = mean
                context_z.setdefault(component, {})[band] = ((mean - global_mean) / global_std
                                                             if global_std > 0 else 0.0)
            del sampled, values

    distance_m = ndi.distance_transform_edt(~np.asarray(store.catalogue, bool)).astype(np.float32) * 100.0
    p_a_flat, p_b_flat, emitted_flat = p_a.ravel(), p_b.ravel(), np.asarray(emitted, bool).ravel()
    fieldnames = ["candidate_rank", "view_stratum", "component_id", "candidate_pixels", "selected_emitted_pixels",
                  "centroid_easting_m", "centroid_northing_m", "mean_view_A_score", "mean_view_B_score",
                  "mean_nearest_catalogue_distance_m", "elongation", "axis_degrees_from_easting",
                  "band02_rtp_mean", "band02_rtp_global_z", "band06_tc_like_mean", "band06_tc_like_global_z",
                  "band12_elevation_mean", "band12_elevation_global_z", "band13_gravity_mean", "band13_gravity_global_z",
                  "band14_tmi_mean", "band14_tmi_global_z", "band15_basement_depth_mean", "band15_basement_depth_global_z",
                  "band17_conductivity_mean", "band17_conductivity_global_z", "band19_slope_mean", "band19_slope_global_z",
                  "top_local_gradient_channels", "gradient_values_are_not_model_attributions",
                  "geological_interpretation", "competing_explanations", "status"]
    rows_by_view = {"A-only": [], "B-only": []}
    candidate_position = {(item["view"], item["component_id"]): np.searchsorted(candidate_ids, item["flat"])
                          for item in all_components}
    for item in all_components:
        view_name, component, flat = item["view"], item["component_id"], item["flat"]
        y, x = np.divmod(flat, width)
        xx = transform.a * (x + 0.5) + transform.b * (y + 0.5) + transform.c
        yy = transform.d * (x + 0.5) + transform.e * (y + 0.5) + transform.f
        if len(x) > 1:
            xy = np.column_stack((xx, yy))
            covariance = np.cov(xy, rowvar=False)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            elongation = float(np.sqrt(max(eigenvalues[-1], 0.0) / max(eigenvalues[0], 1e-9)))
            axis = float(np.degrees(np.arctan2(eigenvectors[1, -1], eigenvectors[0, -1])) % 180.0)
        else:
            elongation, axis = 1.0, None
        features, names, edge_ids = edge_indices[view_name]
        positions = candidate_position[(view_name, component)]
        means = features[positions].mean(axis=0) if len(positions) else np.zeros(len(names))
        top_edges = sorted(edge_ids, key=lambda i: (-float(means[i]), names[i]))[:3]
        top_text = "; ".join(f"{names[i]}={means[i]:.6g}" for i in top_edges)
        z = context_z[(view_name, component)]
        anomaly_bands = (2, 13, 14, 17) if view_name == "A-only" else (6, 12, 19)
        anomalies = [f"band {band} z={z[band]:+.2f}" for band in anomaly_bands if abs(z[band]) >= 1.0]
        anomaly_text = "; ".join(anomalies) if anomalies else "no >=1 SD raw-view context band"
        if view_name == "A-only":
            geology = ("A-only rank rule (A >= training-domain q99; B in q40–q80); context: " + anomaly_text +
                       ". Compatible with a covered fault/splay or subtle geophysical structure only if local gradients and independent mapping corroborate it; context z-scores are not fault probabilities.")
            alternatives = ("Lithologic contact or intrusion; gravity/magnetic processing edge; strain/seismic background; conductivity inversion boundary; chance high rank; incomplete catalogue; unrelated radiometric or DEM transition.")
            status = "unverified geological hypothesis; independent review required before Phase-2 claim"
        else:
            geology = ("B-only rank rule (B >= training-domain q99; A in q40–q80); context: " + anomaly_text +
                       ". A DEM/radiometric-only edge may be a road, erosion scarp, drainage/levee, or land-cover contact; it is a possible artifact, not presumed to be one.")
            alternatives = ("Genuine fault missed by View A; surface road/erosion/drainage; lithologic or land-cover contact; radiometric processing edge; incomplete catalogue.")
            status = "artifact-sensitive diagnostic; not automatically suppressed or declared false"
        rows_by_view[view_name].append(dict(
            component_id=component, candidate_pixels=int(len(flat)),
            selected_emitted_pixels=int(emitted_flat[flat].sum()),
            centroid_easting_m=float(np.mean(xx)), centroid_northing_m=float(np.mean(yy)),
            mean_view_A_score=float(np.nanmean(p_a_flat[flat])),
            mean_view_B_score=float(np.nanmean(p_b_flat[flat])),
            mean_nearest_catalogue_distance_m=float(np.mean(distance_m.ravel()[flat])),
            elongation=elongation, axis_degrees_from_easting=axis,
            band02_rtp_mean=context_means[(view_name, component)][2], band02_rtp_global_z=z[2],
            band06_tc_like_mean=context_means[(view_name, component)][6], band06_tc_like_global_z=z[6],
            band12_elevation_mean=context_means[(view_name, component)][12], band12_elevation_global_z=z[12],
            band13_gravity_mean=context_means[(view_name, component)][13], band13_gravity_global_z=z[13],
            band14_tmi_mean=context_means[(view_name, component)][14], band14_tmi_global_z=z[14],
            band15_basement_depth_mean=context_means[(view_name, component)][15], band15_basement_depth_global_z=z[15],
            band17_conductivity_mean=context_means[(view_name, component)][17], band17_conductivity_global_z=z[17],
            band19_slope_mean=context_means[(view_name, component)][19], band19_slope_global_z=z[19],
            top_local_gradient_channels=top_text,
            gradient_values_are_not_model_attributions="true",
            geological_interpretation=geology, competing_explanations=alternatives, status=status))

    paths = {"A-only": path, "B-only": path.with_name(path.stem.replace("a-only-reasoning", "b-only-diagnostic") + path.suffix)}
    for view_name, rows in rows_by_view.items():
        score_key = "mean_view_A_score" if view_name == "A-only" else "mean_view_B_score"
        rows.sort(key=lambda row: (-row[score_key], -row["candidate_pixels"], row["component_id"]))
        for rank, row in enumerate(rows, 1):
            row.update(candidate_rank=rank, view_stratum=view_name)
        target = paths[view_name]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return dict(a_only_path=str(paths["A-only"]), b_only_path=str(paths["B-only"]),
                a_only_candidate_pixels=int((strata_map == 2).sum()),
                a_only_candidate_components=len(rows_by_view["A-only"]),
                a_only_selected_emitted_px=int(((strata_map == 2) & emitted).sum()),
                b_only_candidate_pixels=int((strata_map == 3).sum()),
                b_only_candidate_components=len(rows_by_view["B-only"]),
                b_only_selected_emitted_px=int(((strata_map == 3) & emitted).sum()),
                explanation_unit="every 8-connected component in the full disagreement-candidate field, including zero-emission candidates; A-only and B-only files are separate",
                geology_is_confirmed=False,
                b_only_interpretation="possible surface artifact only; no component is called an artifact without independent evidence")


def _format_report(path: Path, template_path: Path, template_valid: np.ndarray) -> dict:
    problems = []
    with rasterio.open(path) as src, rasterio.open(template_path) as template:
        a = src.read(1)
        valid = np.asarray(template_valid, bool)
        if src.count != 1: problems.append("band count is not 1")
        if src.dtypes[0] != "float32": problems.append("dtype is not float32")
        if src.shape != template.shape: problems.append("shape differs from template")
        if src.crs != template.crs: problems.append("CRS differs from template")
        if src.transform != template.transform: problems.append("transform differs from template")
        if not np.array_equal(src.dataset_mask() > 0, valid): problems.append("internal validity mask differs from template")
        if not np.isfinite(a[valid]).all(): problems.append("NaN/infinity inside template validity mask")
        elif (a[valid] < 0).any() or (a[valid] > 1).any(): problems.append("in-footprint values outside [0,1]")
        if not np.isnan(a[~valid]).all(): problems.append("outside-template values are not all NaN/nodata")
        report = dict(path=str(path), bytes=path.stat().st_size, sha256=h57.sha256_file(path),
                      single_band=src.count == 1, dtype=src.dtypes[0], crs=str(src.crs),
                      shape=list(src.shape), transform=list(src.transform)[:6], bounds=list(src.bounds),
                      nodata=str(src.nodata), template_valid_px=int(valid.sum()),
                      in_footprint_min=float(np.min(a[valid])) if valid.any() else None,
                      in_footprint_max=float(np.max(a[valid])) if valid.any() else None,
                      in_footprint_nonzero=int((a[valid] > 0).sum()),
                      outside_footprint_nan=int(np.isnan(a[~valid]).sum()),
                      outside_footprint_finite=int(np.isfinite(a[~valid]).sum()),
                      exact_internal_mask=bool(np.array_equal(src.dataset_mask() > 0, valid)),
                      problems=problems, ok=not problems,
                      validation_class="local rasterio read-back against the owner-mirrored sample template; not organizer portal acceptance")
    return report


def _same_grid_prior_mask(prediction: np.ndarray, allowed: np.ndarray) -> tuple[np.ndarray, dict]:
    output, stats = emit.greedy_emit(np.asarray(prediction, np.float32), allowed,
                                     dti_projected=0.0, budget=BUDGET,
                                     pool=400_000, hard_max=BUDGET, log=lambda _message: None)
    return output > 0, stats


def build_candidate(data_dir: Path, store: h57.FeatureStore, prereg: dict,
                    prereg_sha: str, holdout: dict) -> dict:
    """Refit on all eligible training cells, emit fresh predictions, and audit on-disk bytes."""
    raw_path = data_dir / "training_features.tif"
    template_path = data_dir / "sample_submission.tif"
    valid = np.asarray(store.valid, bool)
    template_valid = np.asarray(store.template_valid, bool)
    catalogue = np.asarray(store.catalogue, bool)
    near_catalogue = ndi.distance_transform_edt(~catalogue) <= NEGATIVE_COLLAR_PX
    rows, y, sample = h57.sample_training_rows(
        catalogue, valid, valid, seed=int(prereg["holdout_protocol"]["seed"]) + 100,
        positive_cap=int(prereg["learner"]["training_positive_cap_per_fold"]),
        negative_cap=int(prereg["learner"]["training_negative_cap_per_fold"]),
        collar_px=NEGATIVE_COLLAR_PX)
    folder = WORK / "full_fit"
    model_a = fit_cached(store, "A", rows, y, int(prereg["holdout_protocol"]["seed"]) + 100,
                         folder, prereg_sha)
    model_b = fit_cached(store, "B", rows, y, int(prereg["holdout_protocol"]["seed"]) + 100,
                         folder, prereg_sha)
    allow_from_holdout = bool(holdout["independence"]["allow_exchange"]
                              and len(holdout["pseudo_exchange_by_fold"]) == 4
                              and all(row.get("eligible", False) for row in holdout["pseudo_exchange_by_fold"]))
    full_pseudo = None
    final_exchange = False
    if allow_from_holdout:
        full_pseudo = select_pseudo_for_fold(store, model_a, model_b, valid, catalogue,
                                             near_catalogue, folder, minimum=200, cap=2000)
        final_exchange = bool(full_pseudo.get("eligible"))
    if final_exchange:
        with np.load(folder / "pseudo_rows.npz") as z:
            pseudo_a_to_b = z["a_to_b"].astype(np.int64)
            pseudo_b_to_a = z["b_to_a"].astype(np.int64)
        model_a_final = fit_cached(store, "A", rows, y, int(prereg["holdout_protocol"]["seed"]) + 100,
                                   folder, prereg_sha, pseudo=pseudo_b_to_a)
        model_b_final = fit_cached(store, "B", rows, y, int(prereg["holdout_protocol"]["seed"]) + 100,
                                   folder, prereg_sha, pseudo=pseudo_a_to_b)
        candidate_arm = "h57_disagreement_cotrain"
    else:
        model_a_final, model_b_final = model_a, model_b
        candidate_arm = "view_B_fallback"
    log(f"H57 full refit branch: {candidate_arm}; full pseudo exchange eligible={final_exchange}")

    p_a = h57.predict_domain(store, model_a_final, "A", valid)
    p_b = h57.predict_domain(store, model_b_final, "B", valid)
    unlabeled = valid & ~catalogue & ~near_catalogue
    ref_a, ref_b = p_a[unlabeled], p_b[unlabeled]
    domain = valid & ~catalogue
    fields, strata_report = h57.disagreement_field(p_a, p_b, ref_a, ref_b, domain)
    if candidate_arm == "h57_disagreement_cotrain":
        density = fields["h57_disagreement"]
        strata_map = strata_report["strata"]
    else:
        # The frozen fallback is B-only, not a post-hoc union or an unreported blend.
        density = fields["view_B"]
        strata_map = strata_report["strata"]
    allowed = valid & ~catalogue
    prediction, placement = emit.greedy_emit(
        density, allowed, dti_projected=0.0, budget=BUDGET, pool=400_000,
        hard_max=BUDGET, log=lambda _message: None)
    prediction[~valid] = 0.0
    if int((prediction > 0).sum()) != BUDGET:
        raise ValueError(f"metric-aware emitter produced {int((prediction > 0).sum())}, not the registered {BUDGET} pixels")
    if int((prediction[catalogue] > 0).sum()) != 0:
        raise AssertionError("candidate emitted on a mapped catalogue pixel")

    decoded_sha = digest_bytes(prediction.astype("<f4").tobytes())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    method = "cotrain-disagreement" if candidate_arm == "h57_disagreement_cotrain" else "viewB-fallback"
    stem = f"gems52-h57-{method}-{BUDGET}px-{timestamp}-{decoded_sha[:10]}"
    tif_name = stem + ".tif"
    out_path = ROOT / "submission" / tif_name
    download_path = ROOT / "docs/downloads" / tif_name
    zip_path = ROOT / "docs/downloads" / (stem + ".zip")
    outside_nan = h57.export_mask(prediction, template_valid)
    status = "RESEARCH ONLY — DO NOT SUBMIT; no portal upload authorized"
    write_report = h57.write_submission_tiff(out_path, outside_nan, template_path,
                                            template_valid, status=status)
    format_report = _format_report(out_path, template_path, template_valid)
    if not format_report["ok"] or not write_report["on_disk_readback_exact"]:
        raise ValueError(f"H57 GeoTIFF format/read-back gate failed: {format_report['problems']}")

    # Audit all locally accessible aligned single-band priors. Competition inputs are excluded by
    # gates.find_priors; inaccessible sibling pages/files remain explicitly outside this scope.
    prior_paths, inventory = scan_aligned_priors(
        template_path, EVIDENCE / "h57_prior_inventory.json", exclude_candidate=out_path)
    canonical = prediction.astype(np.float32, copy=True)
    uniqueness = gates.uniqueness_report(canonical, prior_paths, top=None)
    uniqueness.update(inventory_aligned_unique_byte_contents=len(prior_paths),
                      inventory_aligned_path_count=inventory["aligned_prior_path_count"],
                      exact_byte_duplicate_paths_collapsed=inventory["exact_byte_duplicate_paths_collapsed"],
                      all_accessible_scope=inventory["scope"])
    # The two names below intentionally separate byte/pattern distinction from a stricter support-
    # novelty proportion that can be saturated by a dense exploratory prior.
    uniqueness["support_novelty_requirement"] = "20% is reported as a separate hard diagnostic; not waived for a submission gate"
    uniqueness["local_candidate_is_pattern_unique"] = bool(uniqueness["canonical_pattern_unique"])
    if not uniqueness["canonical_pattern_unique"]:
        log("WARNING: H57 pattern is not distinguishable from every aligned accessible prior; do not submit")

    # Same-budget A, B and max-union outputs are independently placed on the exact final allowed set.
    view_a_mask, view_a_placement = _same_grid_prior_mask(fields["view_A"], allowed)
    view_b_mask, view_b_placement = _same_grid_prior_mask(fields["view_B"], allowed)
    max_union_mask, max_union_placement = _same_grid_prior_mask(fields["matched_max_union"], allowed)
    literal_view_union = view_a_mask | view_b_mask
    final_mask = prediction > 0
    not_union = dict(
        exact_equal_view_A=bool(np.array_equal(final_mask, view_a_mask)),
        exact_equal_view_B=bool(np.array_equal(final_mask, view_b_mask)),
        exact_equal_matched_max_union=bool(np.array_equal(final_mask, max_union_mask)),
        exact_equal_literal_union=bool(np.array_equal(final_mask, literal_view_union)),
        candidate_pixels=int(final_mask.sum()),
        view_A_pixels=int(view_a_mask.sum()), view_B_pixels=int(view_b_mask.sum()),
        matched_max_union_pixels=int(max_union_mask.sum()), literal_view_union_pixels=int(literal_view_union.sum()),
        intersection_with_matched_max_union=int((final_mask & max_union_mask).sum()),
        novel_vs_matched_max_union=int((final_mask & ~max_union_mask).sum()),
        matched_max_union_dropped=int((max_union_mask & ~final_mask).sum()),
        candidate_only_vs_literal_union=int((final_mask & ~literal_view_union).sum()),
        literal_union_only=int((literal_view_union & ~final_mask).sum()),
        placement=dict(view_A=view_a_placement, view_B=view_b_placement, max_union=max_union_placement),
        not_merely_union=bool(not np.array_equal(final_mask, max_union_mask)
                              and not np.array_equal(final_mask, literal_view_union)))

    a_only_reasoning = _component_reasoning_csv(
        ROOT / "docs/downloads" / (stem + "-a-only-reasoning.csv"), store, strata_map,
        final_mask, p_a, p_b, raw_path)
    shutil.copy2(out_path, download_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(download_path, arcname=tif_name)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != [tif_name] or archive.read(tif_name) != download_path.read_bytes():
            raise ValueError("single-TIFF ZIP failed member/read-back verification")

    submission_name = f"GEMSDOE52-H57-{method}-{BUDGET}px"
    baseline_names = ("view_A_supervised", "view_B_supervised", "matched_max_union")
    baseline_means = {arm: float(np.mean([fold["arms"][arm]["dti"] for fold in holdout["folds"]]))
                      for arm in baseline_names}
    strongest_arm = max(baseline_names, key=lambda arm: baseline_means[arm])
    provisional_mean = float(np.mean([fold["arms"][candidate_arm]["dti"] for fold in holdout["folds"]]))
    lift_summary = provisional_mean - baseline_means[strongest_arm]
    positive_folds = sum(holdout["folds"][i]["arms"][candidate_arm]["dti"]
                         > holdout["folds"][i]["arms"][strongest_arm]["dti"]
                         for i in range(len(holdout["folds"])))
    final_method = "co-training" if candidate_arm == "h57_disagreement_cotrain" else "View-B fallback"
    short_note = (f"H57 {final_method} | {BUDGET:,} metric-placed px | local gate FAIL "
                  f"({lift_summary:+.4f} DTI vs best; {positive_folds}/4) | research only; DO NOT upload.")
    if len(short_note) > 200:
        raise AssertionError("submission note exceeds 200 characters")
    slot_gate = complete_holdout_gate(holdout, candidate_arm,
                                      float(prereg["promotion_gate"]["must_exceed_historical_internal_holdout_floor"]))
    slot_gate["artifact_local_gates"] = dict(format_pass=bool(format_report["ok"]),
                                              exact_pattern_unique=bool(uniqueness["canonical_pattern_unique"]),
                                              support_novelty_pass=bool(uniqueness["support_novelty_gate_ok"]),
                                              not_merely_union=bool(not_union["not_merely_union"]))
    slot_gate["artifact_local_gate_pass"] = bool(
        format_report["ok"] and uniqueness["canonical_pattern_unique"]
        and uniqueness["support_novelty_gate_ok"] and not_union["not_merely_union"])
    slot_gate["all_local_promotion_gates_pass"] = bool(
        slot_gate["scientific_gate_pass"] and slot_gate["artifact_local_gate_pass"])
    # This runner is research-only by design. Even a future local gate pass cannot stand in for an
    # independent confirmation, authenticated organizer inputs, explicit portal authorization, or
    # a successful portal-format check.
    slot_gate["approved_for_weekly_slot"] = False
    slot_gate["reason"] += "; no portal slot is authorized in this session"
    receipt = dict(
        generated_utc=now(), file=tif_name, stem=stem, submission_name=submission_name,
        submission_note=short_note, submission_note_chars=len(short_note),
        status=status, artifact_status=status, approved_for_weekly_slot=False,
        candidate_arm=candidate_arm, decoded_pattern_sha256=decoded_sha,
        sha256=write_report["sha256"], bytes=write_report["bytes"],
        input_provenance="SHA-pinned owner-maintained mirrors; not organizer-authenticated",
        input_sha256=holdout.get("input_sha256"),
        preregistration_sha256=prereg_sha,
        feature_manifest_sha256=h57.sha256_file(FEATURES / "manifest.json"),
        source_sha256=dict(runner=h57.sha256_file(Path(__file__)), module=h57.sha256_file(Path(h57.__file__)),
                           spatial=h57.sha256_file(ROOT / "src/gems52/spatial.py")),
        model="H57 supervised HistGradientBoosting plus one whole-segment pseudo-exchange only when the preregistered spatial proxy-error gate permits; otherwise explicit View-B-only fallback",
        exchange=dict(holdout_gate=holdout["independence"], holdout_pseudo_folds=holdout["pseudo_exchange_by_fold"],
                      full_data_exchange=full_pseudo, final_exchange_used=final_exchange),
        training=sample,
        normalization="binary {0,1} output on eligible in-footprint cells; all other in-footprint cells 0; NaN only outside the sample-template mask",
        placement=placement, format=format_report, write_readback=write_report,
        uniqueness=uniqueness, prior_inventory=inventory,
        not_union=not_union, a_only_reasoning=a_only_reasoning,
        slot_gate=slot_gate, scientific_holdout_gate=slot_gate["scientific_gate_pass"],
        submission_slots_used=0, portal_upload_performed=False, official_score=None,
        public_score_forecast=None, official_problem_url="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
        software=dict(python=platform.python_version(), numpy=np.__version__, rasterio=rasterio.__version__,
                      sklearn=__import__("sklearn").__version__))

    # Publish local evidence and exactly one TIFF member in the ZIP. The audit TIFF is a fresh model
    # emission; prior artifacts were consulted only after fitting for decoded-pattern comparison.
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_path, download_path)
    write_json(EVIDENCE / f"submission_{stem}.json", receipt)
    write_json(EVIDENCE / "h57_submission.json", receipt)
    write_json(EVIDENCE / "h57_candidate_local_gates.json", dict(
        format=format_report, write_readback=write_report, uniqueness=uniqueness,
        not_union=not_union, slot_gate=slot_gate))
    write_json(ROOT / "docs/downloads" / (stem + "-audit.json"), receipt)
    (ROOT / "submission/LATEST.txt").write_text(tif_name + "\n")
    (ROOT / "submission/H57_RESEARCH_LATEST.txt").write_text(tif_name + "\n")
    return receipt


def refresh_candidate_audit(candidate_path: Path, template_path: Path) -> dict:
    """Re-run raster-format and decoded-prior checks on an already generated H57 artifact.

    This is intentionally inference-free. It supports reproducible correction of an audit-path bug
    without refitting or changing a single prediction pixel.
    """
    candidate_path = candidate_path.resolve()
    stem = candidate_path.stem
    receipt_path = ROOT / "docs/downloads" / f"{stem}-audit.json"
    if not candidate_path.is_file() or not receipt_path.is_file():
        raise FileNotFoundError(f"candidate or audit receipt missing: {candidate_path}, {receipt_path}")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("file") != candidate_path.name:
        raise ValueError("candidate path does not match the artifact receipt")
    with rasterio.open(template_path) as template:
        template_valid = template.dataset_mask() > 0
    format_report = _format_report(candidate_path, template_path, template_valid)
    if not format_report["ok"]:
        raise ValueError(f"candidate format check failed: {format_report['problems']}")
    with rasterio.open(candidate_path) as dataset:
        candidate = dataset.read(1)
    canonical = gates.canonical(candidate)
    prior_paths, inventory = scan_aligned_priors(
        template_path, EVIDENCE / "h57_prior_inventory.json", exclude_candidate=candidate_path)
    uniqueness = gates.uniqueness_report(canonical, prior_paths, top=None)
    uniqueness.update(inventory_aligned_unique_byte_contents=len(prior_paths),
                      inventory_aligned_path_count=inventory["aligned_prior_path_count"],
                      exact_byte_duplicate_paths_collapsed=inventory["exact_byte_duplicate_paths_collapsed"],
                      all_accessible_scope=inventory["scope"],
                      support_novelty_requirement=(
                          "20% is reported as a separate hard diagnostic; not waived for a submission gate"),
                      local_candidate_is_pattern_unique=bool(uniqueness["canonical_pattern_unique"]))
    receipt["format"] = format_report
    receipt["uniqueness"] = uniqueness
    receipt["prior_inventory"] = inventory
    receipt["posthoc_audit"] = dict(
        generated_utc=now(), inference_rerun=False,
        reason="Corrected prior scan to exclude this exact artifact and staged aliases by basename; pixels and model unchanged.",
        candidate_sha256=format_report["sha256"])
    slot_gate = receipt["slot_gate"]
    local_gates = dict(format_pass=bool(format_report["ok"]),
                       exact_pattern_unique=bool(uniqueness["canonical_pattern_unique"]),
                       support_novelty_pass=bool(uniqueness["support_novelty_gate_ok"]),
                       not_merely_union=bool(receipt["not_union"]["not_merely_union"]))
    slot_gate["artifact_local_gates"] = local_gates
    slot_gate["artifact_local_gate_pass"] = bool(all(local_gates.values()))
    slot_gate["all_local_promotion_gates_pass"] = bool(
        slot_gate["scientific_gate_pass"] and slot_gate["artifact_local_gate_pass"])
    slot_gate["approved_for_weekly_slot"] = False
    receipt["slot_gate"] = slot_gate
    receipt["artifact_status"] = receipt.get("status", "RESEARCH ONLY — DO NOT SUBMIT")
    receipt["approved_for_weekly_slot"] = False
    receipt["scientific_holdout_gate"] = bool(slot_gate["scientific_gate_pass"])
    receipt["submission_slots_used"] = 0
    receipt["portal_upload_performed"] = False
    receipt["official_score"] = None
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    write_json(EVIDENCE / "h57_submission.json", receipt)
    write_json(EVIDENCE / f"submission_{stem}.json", receipt)
    write_json(EVIDENCE / "h57_candidate_local_gates.json", dict(
        format=format_report, uniqueness=uniqueness, not_union=receipt["not_union"], slot_gate=slot_gate))
    write_json(receipt_path, receipt)
    write_json(ROOT / "docs/data/h57_submission.json", receipt)
    for holdout_path in (EVIDENCE / "h57_holdout.json", ROOT / "docs/data/h57_holdout.json"):
        if holdout_path.is_file():
            holdout_receipt = json.loads(holdout_path.read_text())
            holdout_receipt["candidate_exact_pattern_unique"] = bool(uniqueness["canonical_pattern_unique"])
            holdout_receipt["candidate_support_novelty_pass"] = bool(uniqueness["support_novelty_gate_ok"])
            holdout_receipt["candidate_not_merely_union"] = bool(receipt["not_union"]["not_merely_union"])
            holdout_receipt["slot_gate"] = slot_gate
            write_json(holdout_path, holdout_receipt)
    return receipt


def run(data_dir: Path, stage: str) -> dict:
    prereg = json.loads(PREREG_PATH.read_text())
    prereg_sha = h57.sha256_file(PREREG_PATH)
    input_hashes = verify_input_pins(data_dir, prereg)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if stage in ("prepare", "all"):
        manifest = h57.build_feature_cache(
            data_dir / "training_features.tif", data_dir / "labels.tif",
            data_dir / "sample_submission.tif", FEATURES,
            preregistration_sha256=prereg_sha, log=log)
        write_json(EVIDENCE / "h57_features.json", manifest)
    else:
        if not (FEATURES / "manifest.json").is_file():
            raise FileNotFoundError("H57 feature cache missing; run --stage prepare first")
    store = h57.FeatureStore(FEATURES)
    if stage == "prepare":
        return {"features": manifest}
    if stage in ("validate", "all"):
        report = run_holdout(store, prereg, prereg_sha)
        report["input_sha256"] = input_hashes
        write_json(EVIDENCE / "h57_holdout_provisional.json", report)
        if stage == "validate":
            return report
    else:
        provisional = EVIDENCE / "h57_holdout_provisional.json"
        if not provisional.exists():
            raise FileNotFoundError("H57 holdout receipt missing; run --stage validate first")
        report = json.loads(provisional.read_text())
        if report.get("preregistration_sha256") != prereg_sha:
            raise ValueError("H57 holdout receipt does not match the frozen registration")
        report["input_sha256"] = input_hashes
    if stage in ("build", "all"):
        receipt = build_candidate(data_dir, store, prereg, prereg_sha, report)
        report["candidate_artifact"] = receipt["file"]
        report["selected_candidate_arm"] = receipt["candidate_arm"]
        report["candidate_format_pass"] = receipt["format"]["ok"]
        report["candidate_exact_pattern_unique"] = receipt["uniqueness"]["canonical_pattern_unique"]
        report["candidate_support_novelty_pass"] = receipt["uniqueness"]["support_novelty_gate_ok"]
        report["candidate_not_merely_union"] = receipt["not_union"]["not_merely_union"]
        report["slot_gate"] = receipt["slot_gate"]
        report["portal_upload_performed"] = False
        report["submission_slots_used"] = 0
        report["official_score"] = None
        write_json(EVIDENCE / "h57_holdout.json", report)
        write_json(ROOT / "docs/data/h57_holdout.json", report)
        write_json(ROOT / "docs/data/h57_submission.json", receipt)
        write_json(ROOT / "docs/data/h57_preregistration.json", prereg)
        return dict(holdout=report, submission=receipt)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.environ.get("GEMS52_DATA_DIR", "/tmp/gems52-restored-core"),
                        help="directory holding the three SHA-pinned core competition rasters")
    parser.add_argument("--stage", choices=("prepare", "validate", "build", "audit", "all"), default="all")
    parser.add_argument("--artifact", help="H57 candidate TIFF to recheck with --stage audit; no inference is rerun")
    args = parser.parse_args()
    if args.stage == "audit":
        if not args.artifact:
            parser.error("--artifact is required with --stage audit")
        receipt = refresh_candidate_audit(Path(args.artifact), Path(args.data_dir) / "sample_submission.tif")
        print(f"RECHECKED {receipt['file']}: exact_pattern_unique={receipt['uniqueness']['canonical_pattern_unique']}, "
              f"support_novelty_pass={receipt['uniqueness']['support_novelty_gate_ok']}, "
              f"weekly_slot_approved={receipt['slot_gate']['approved_for_weekly_slot']}")
        return 0
    result = run(Path(args.data_dir), args.stage)
    if args.stage == "validate":
        print(json.dumps(_json_safe(result["independence"]), indent=2))
        print("H57 spatial holdout run complete; no portal action occurred.")
    else:
        submission = result.get("submission") if "submission" in result else None
        if submission:
            print(f"WROTE {submission['file']} ({submission['bytes']} bytes)")
            print(f"STATUS: {submission['status']}")
            print(f"DOWNLOAD: docs/downloads/{submission['file']}")
            print(f"ZIP: docs/downloads/{Path(submission['file']).stem}.zip")
            print(f"UPLOAD APPROVAL: {submission['slot_gate']['approved_for_weekly_slot']}")
        else:
            print("H57 preparation complete; no prediction file generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
