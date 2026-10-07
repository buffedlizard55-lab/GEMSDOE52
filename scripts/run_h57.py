#!/usr/bin/env python3
"""H57: registered real-data, corrected-view spatial holdout and research artifact builder.

Stages are deliberately ordered:
  prepare  audit inputs, build label-free features and the corrected A/B uint8 stack;
  holdout  run four whole-component 80-pixel folds, OOF independence, matched controls, then
           (only if permitted) precheck every pseudo-label fold before fitting any round-1 model;
  build    only after a completed holdout, fit on the full labelled domain and emit the registered
           primary (or the explicitly named B-only fallback), then independently gate the TIFF.

No portal upload, public-score forecast, prior-raster feature, or prior-raster pixel reuse occurs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

# Set before numerical libraries are imported.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import numpy as np
import rasterio
from scipy import ndimage as ndi
import sklearn

from gems52 import cotrain, emit, gates, metric, spatial
from gems52 import features as core_features
from gems52 import grid
from gems55 import h57 as H57
from gems55 import radlayers, reasoning

REG_PATH = ROOT / "registry/h57_preregistration.json"
HYP_PATH = ROOT / "knowledge/17_hypotheses_H57_preregistered.md"
LOCK_PATH = ROOT / "evidence/h57_prefit_lock.json"
FEATURES_PATH = ROOT / "data/training_features.tif"
LABELS_PATH = ROOT / "data/labels.tif"
SAMPLE_PATH = ROOT / "data/sample_submission.tif"
WORK = ROOT / "work/h57"
DERIVED = WORK / "derived"
STACK_PATH = WORK / "stack.npy"
EVIDENCE = ROOT / "evidence"
SUBMISSION = ROOT / "submission"
DOWNLOADS = ROOT / "docs/downloads"

SOURCE_PATHS = (
    "scripts/run_h57.py",
    "scripts/prepare_data.py",
    "src/gems55/h57.py",
    "src/gems52/features.py",
    "src/gems52/transform.py",
    "src/gems52/spatial.py",
    "src/gems52/cotrain.py",
    "src/gems52/emit.py",
    "src/gems52/metric.py",
    "src/gems52/gates.py",
    "src/gems52/grid.py",
    "src/gems55/radlayers.py",
    "src/gems55/reasoning.py",
)
INPUT_PATHS = {
    "training_features.tif": ROOT / "data/training_features.tif",
    "labels.tif": ROOT / "data/labels.tif",
    "sample_submission.tif": ROOT / "data/sample_submission.tif",
    "geodawn_rad_u8.tif": ROOT / "data/external/geodawn_rad_u8.tif",
    "geodawn_extensions_u8.tif": ROOT / "data/external/geodawn_extensions_u8.tif",
    "lidar_scarp_features_u8.tif": ROOT / "data/external/lidar_scarp_features_u8.tif",
}
CONTROL_NAMES = (
    "view_A",
    "view_B_corrected",
    "early_fusion",
    "max_AB_union_control",
    "round0_disagreement_no_exchange",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def digest(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot JSON-encode {type(value).__name__}")


def write_json(path: str | Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False, default=_json_default) + "\n")
    tmp.replace(path)


def _canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                  allow_nan=False, default=_json_default).encode()).hexdigest()


def software_versions() -> dict:
    import numpy
    import rasterio as rio
    import scipy
    return dict(python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
                sklearn=sklearn.__version__, rasterio=rio.__version__)


def _git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _input_readback(registration: dict) -> dict:
    reports = {}
    for name, path in INPUT_PATHS.items():
        pin = registration["inputs"][name]
        if not path.is_file():
            raise RuntimeError(f"required pinned input missing: {path}")
        report = dict(path=str(path.relative_to(ROOT)), sha256=digest(path), bytes=path.stat().st_size)
        if report["sha256"] != pin["sha256"] or report["bytes"] != pin["bytes"]:
            raise RuntimeError(f"H57 input pin mismatch for {name}; no model fit started")
        reports[name] = report
    identity = registration["inputs"]["band6_identity_evidence"]
    identity_path = ROOT / identity["path"]
    if digest(identity_path) != identity["sha256"]:
        raise RuntimeError("band-6 identity evidence changed after preregistration")
    return reports


def preflight() -> dict:
    """Fail closed on branch, lock, input, registration or previous-run inconsistencies."""
    if not REG_PATH.is_file() or not HYP_PATH.is_file() or not LOCK_PATH.is_file():
        raise RuntimeError("H57 registration, hypothesis document or pre-fit lock is missing")
    registration = json.loads(REG_PATH.read_text())
    lock = json.loads(LOCK_PATH.read_text())
    reg_sha, hyp_sha, lock_sha = digest(REG_PATH), digest(HYP_PATH), digest(LOCK_PATH)
    if registration.get("hypothesis_sha256") != hyp_sha:
        raise RuntimeError("registered hypothesis-document hash mismatch; no model fit started")
    if lock.get("status") != "PREFIT_LOCKED" or lock.get("model_fit_started") is not False:
        raise RuntimeError("H57 pre-fit lock is not in its frozen state")
    if (lock.get("registration_sha256") != reg_sha or lock.get("hypothesis_sha256") != hyp_sha
            or lock.get("base_commit") != registration.get("base_commit")
            or lock.get("working_branch") != registration.get("working_branch")
            or lock.get("input_pins_match") is not True
            or lock.get("registration_hash_matches_hypothesis") is not True):
        raise RuntimeError("prefit lock hashes/base/branch/input-pins do not match the frozen H57 registration")
    if registration.get("no_competition_slot_spend") is not True or registration.get("no_public_score_forecast") is not True:
        raise RuntimeError("H57 safety constraints must remain frozen: no portal upload or public-score forecast")
    if "TO_BE_FILLED" in REG_PATH.read_text() or "TO_BE_FILLED" in HYP_PATH.read_text():
        raise RuntimeError("unfilled registration placeholder")
    branch = _git_value("branch", "--show-current")
    head = _git_value("rev-parse", "HEAD")
    if branch != registration["working_branch"]:
        raise RuntimeError(f"wrong working branch {branch!r}; H57 is fixed to {registration['working_branch']!r}")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", registration["base_commit"], "HEAD"],
                              cwd=ROOT, check=False)
    if ancestor.returncode != 0:
        raise RuntimeError("registered H57 base commit is not an ancestor of HEAD")
    inputs = _input_readback(registration)
    for name, report in inputs.items():
        locked = lock["input_readback"].get(name, {})
        if locked.get("sha256") != report["sha256"] or locked.get("bytes") != report["bytes"]:
            raise RuntimeError(f"input {name} differs from the pre-fit lock")
    source_hashes = {name: digest(ROOT / name) for name in SOURCE_PATHS}
    locked_sources = lock.get("source_sha256")
    if locked_sources is not None and locked_sources != source_hashes:
        raise RuntimeError("H57 implementation source differs from the pre-fit code-review lock")
    fingerprint = dict(registration_sha256=reg_sha, hypothesis_sha256=hyp_sha,
                       prefit_lock_sha256=lock_sha, input_sha256={k: v["sha256"] for k, v in inputs.items()},
                       band6_identity_sha256=digest(ROOT / registration["inputs"]["band6_identity_evidence"]["path"]),
                       source_sha256=source_hashes, software=software_versions())
    return dict(registration=registration, registration_sha256=reg_sha, hypothesis_sha256=hyp_sha,
                prefit_lock_sha256=lock_sha, branch=branch, head=head, inputs=inputs,
                source_sha256=source_hashes, source_fingerprint=fingerprint,
                source_signature=_canonical_hash(fingerprint))


def full_signature(ctx: dict, stack_sha256: str) -> str:
    return _canonical_hash(dict(ctx["source_fingerprint"], stack_sha256=stack_sha256))


def write_run_integrity(ctx: dict, status: str, feature_receipt: dict | None = None,
                        details: dict | None = None) -> dict:
    fit_started = status in {"MODEL_FIT_STARTED", "HOLDOUT_COMPLETE", "ARTIFACT_BUILT"}
    holdout_scored = status in {"HOLDOUT_COMPLETE", "ARTIFACT_BUILT"}
    previous = EVIDENCE / "h57_run_integrity.json"
    prior = json.loads(previous.read_text()) if previous.exists() else {}
    record = dict(
        updated_utc=utc_now(), status=status,
        base_commit=ctx["registration"]["base_commit"], branch=ctx["branch"], head_at_update=_git_value("rev-parse", "HEAD"),
        registration_sha256=ctx["registration_sha256"], hypothesis_sha256=ctx["hypothesis_sha256"],
        prefit_lock_sha256=ctx["prefit_lock_sha256"], source_signature=ctx["source_signature"],
        run_signature=(feature_receipt or {}).get("run_signature"),
        input_sha256={k: v["sha256"] for k, v in ctx["inputs"].items()},
        source_sha256=ctx["source_sha256"], software=software_versions(),
        model_fit_started=bool(prior.get("model_fit_started") or fit_started),
        spatial_holdout_scored=bool(prior.get("spatial_holdout_scored") or holdout_scored),
        portal_upload_performed=False, submission_slots_used=0,
        feature_manifest_sha256=(feature_receipt or {}).get("manifest_sha256"),
        details=details or {},
    )
    write_json(WORK / "run_integrity.json", record)
    write_json(previous, record)
    return record


def build_feature_store(ctx: dict) -> dict:
    """Build the input-derived feature store and corrected View A/B stack."""
    WORK.mkdir(parents=True, exist_ok=True)
    names = list(radlayers.VIEW_A) + list(radlayers.VIEW_B)
    registered = ctx["registration"]["views"]
    if (list(radlayers.VIEW_A) != registered["view_A"]
            or list(radlayers.VIEW_B) != registered["view_B"]):
        raise RuntimeError("runtime view channels differ from the frozen H57 registration")
    if len(names) != len(set(names)):
        raise RuntimeError("corrected H57 feature lists contain duplicate channel names")
    if "A_mag_tilt_abs" in radlayers.VIEW_A or "R_tc_rank" not in radlayers.VIEW_B:
        raise RuntimeError("corrected band-6 routing invariant failed")
    missing = [name for name in names if not (DERIVED / f"{name}.npy").is_file()]
    existing_receipt = WORK / "feature_store_receipt.json"
    if existing_receipt.is_file() and STACK_PATH.is_file() and not missing:
        old = json.loads(existing_receipt.read_text())
        old_manifest_hash = old.get("manifest_sha256")
        unhashed_old = {k: v for k, v in old.items() if k != "manifest_sha256"}
        if old_manifest_hash != _canonical_hash(unhashed_old):
            raise RuntimeError("cached H57 feature receipt failed its canonical integrity hash")
        if old.get("source_signature") == ctx["source_signature"] and old.get("channel_names") == names:
            if digest(STACK_PATH) != old.get("stack_sha256"):
                raise RuntimeError("cached H57 stack hash mismatch; refusing to fit")
            if digest(DERIVED / "manifest.json") != old.get("derived_manifest_sha256"):
                raise RuntimeError("cached H57 derived-layer manifest hash mismatch; refusing to fit")
            return old

    os.chdir(ROOT)
    prepare = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_data.py")],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    if prepare.stdout:
        print(prepare.stdout, end="")
    if prepare.stderr:
        print(prepare.stderr, file=sys.stderr, end="")
    if prepare.returncode != 0:
        raise RuntimeError("scripts/prepare_data.py failed; no model fit started")

    log("building core label-free layers")
    core_report = core_features.build(work_dir=str(WORK), features_path=str(FEATURES_PATH), log=log)
    log("building corrected radiometric and LiDAR View-B layers")
    external_report = radlayers.build(work_dir=str(WORK), log=log)
    valid = np.load(DERIVED / "valid_footprint.npy", mmap_mode="r")[:].astype(bool)
    missing = [name for name in names if not (DERIVED / f"{name}.npy").is_file()]
    if missing:
        raise RuntimeError(f"feature builder did not produce registered layers: {missing}")
    log(f"building corrected stack with {len(radlayers.VIEW_A)} A / {len(radlayers.VIEW_B)} B channels")
    stack = cotrain.build_stack_from_dir(DERIVED, names, valid)
    if stack.shape != valid.shape + (len(names),) or stack.dtype != np.uint8:
        raise RuntimeError(f"unexpected H57 stack shape/dtype: {stack.shape}, {stack.dtype}")
    np.save(STACK_PATH, stack)
    del stack
    stack_sha = digest(STACK_PATH)
    derived_manifest_path = DERIVED / "manifest.json"
    receipt = dict(
        generated_utc=utc_now(), experiment=ctx["registration"]["experiment"],
        source_signature=ctx["source_signature"], registration_sha256=ctx["registration_sha256"],
        hypothesis_sha256=ctx["hypothesis_sha256"], input_sha256={k: v["sha256"] for k, v in ctx["inputs"].items()},
        shape=list(valid.shape), eligible_pixels=int(valid.sum()), n_channels=len(names),
        view_A=list(radlayers.VIEW_A), view_B=list(radlayers.VIEW_B), channel_names=names,
        band6_routing="radiometric total count in View B; legacy A_mag_tilt_abs is excluded",
        stack_encoding=ctx["registration"]["feature_construction"]["stack_encoding"],
        stack_file=str(STACK_PATH.relative_to(ROOT)), stack_bytes=STACK_PATH.stat().st_size,
        stack_sha256=stack_sha, derived_manifest_sha256=digest(derived_manifest_path),
        core_layer_count=len(core_report.get("layers", {})), external_layer_count=len(external_report),
        core_manifest_layers=sorted(core_report.get("layers", {})), external_layers=sorted(external_report),
        valid_mask_path=str((DERIVED / "valid_footprint.npy").relative_to(ROOT)),
        source_sha256=ctx["source_sha256"], software=software_versions(),
    )
    receipt["run_signature"] = full_signature(ctx, stack_sha)
    receipt["manifest_sha256"] = _canonical_hash(receipt)
    write_json(existing_receipt, receipt)
    write_json(EVIDENCE / "h57_feature_manifest.json", receipt)
    return receipt


def load_data(feature_receipt: dict):
    valid = np.load(DERIVED / "valid_footprint.npy", mmap_mode="r")[:].astype(bool)
    with rasterio.open(LABELS_PATH) as src:
        if src.count != 1 or src.shape != valid.shape:
            raise RuntimeError("labels grid no longer matches the H57 eligible domain")
        catalogue = src.read(1) == 1
    depth_rank = np.load(DERIVED / "A_depth_base_rank__rank.npy", mmap_mode="r")[:].astype(np.float32)
    stack = np.load(STACK_PATH, mmap_mode="r")
    if stack.shape != valid.shape + (feature_receipt["n_channels"],):
        raise RuntimeError("H57 stack changed after feature manifest was written")
    return catalogue, valid, depth_rank, stack


def validate_fold(fold: dict, buffer_px: int) -> dict:
    receipt = fold["receipt"]
    if receipt["shared_train_truth_components"] != 0:
        raise RuntimeError(f"fold {fold['fold']} shares a train/truth component")
    if (fold["train"] & fold["region"]).any() or (fold["train"] & fold["held_all"]).any():
        raise RuntimeError(f"fold {fold['fold']} has train/evaluation overlap")
    nearest = receipt["nearest_training_to_region_px"]
    if nearest is None or nearest + 1e-9 < buffer_px:
        raise RuntimeError(f"fold {fold['fold']} fails the {buffer_px}-pixel feature buffer")
    if not (fold["truth"] <= fold["region"]).all():
        raise RuntimeError(f"fold {fold['fold']} truth escaped its evaluation region")
    return receipt


def _model_signature(ctx: dict, feature_receipt: dict, model_name: str, channel_names: list[str],
                     columns: list[int], rows: np.ndarray, y: np.ndarray, seed: int,
                     pseudo: np.ndarray | None, learner: dict) -> str:
    pseudo = np.asarray(pseudo if pseudo is not None else [], dtype=np.int64)
    payload = dict(run_signature=feature_receipt["run_signature"], model_name=model_name,
                   channel_names=channel_names, columns=columns, seed=int(seed), learner=learner,
                   rows_sha256=hashlib.sha256(np.asarray(rows, dtype="<i8").tobytes()).hexdigest(),
                   labels_sha256=hashlib.sha256(np.asarray(y, dtype=np.int8).tobytes()).hexdigest(),
                   pseudo_sha256=hashlib.sha256(np.sort(pseudo).astype("<i8").tobytes()).hexdigest(),
                   pseudo_weight=ctx["registration"]["pseudo_label_exchange"]["pseudo_sample_weight"])
    return _canonical_hash(payload)


def _model_paths(model_name: str) -> tuple[Path, Path]:
    path = WORK / "models" / f"{model_name}.joblib"
    return path, path.with_suffix(".meta.json")


def model_cache_matches(model_name: str, signature: str) -> bool:
    path, meta_path = _model_paths(model_name)
    if not path.is_file() or not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text())
        return meta.get("signature") == signature and meta.get("model_sha256") == digest(path)
    except (OSError, ValueError):
        return False


def fit_or_load_model(ctx: dict, feature_receipt: dict, stack: np.ndarray, rows: np.ndarray,
                      y: np.ndarray, names: list[str], columns: list[int], seed: int,
                      model_name: str, pseudo: np.ndarray | None = None):
    learner = ctx["registration"]["learner"]
    signature = _model_signature(ctx, feature_receipt, model_name, names, columns, rows, y,
                                  seed, pseudo, learner)
    path, meta_path = _model_paths(model_name)
    if model_cache_matches(model_name, signature):
        return joblib.load(path), signature, True
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"fitting {model_name}: {len(rows)} catalogue rows + {len(pseudo) if pseudo is not None else 0} pseudo rows, {len(columns)} channels")
    model = H57.fit_model(stack, rows, y, columns, learner, seed, pseudo_positive=pseudo,
                          pseudo_weight=ctx["registration"]["pseudo_label_exchange"]["pseudo_sample_weight"])
    tmp = path.with_suffix(path.suffix + ".partial")
    joblib.dump(model, tmp, compress=3)
    tmp.replace(path)
    write_json(meta_path, dict(signature=signature, model_name=model_name, seed=int(seed),
                               learner=learner, model_sha256=digest(path),
                               pseudo_pixels=int(len(pseudo) if pseudo is not None else 0),
                               generated_utc=utc_now()))
    return model, signature, False


def _row_hash(rows: np.ndarray, y: np.ndarray) -> str:
    return _canonical_hash(dict(rows=hashlib.sha256(np.asarray(rows, dtype="<i8").tobytes()).hexdigest(),
                                labels=hashlib.sha256(np.asarray(y, dtype=np.int8).tobytes()).hexdigest()))


def _fold_cache_signature(feature_receipt: dict, fold: dict, training: dict, seed: int) -> str:
    return _canonical_hash(dict(run_signature=feature_receipt["run_signature"], fold=fold["receipt"],
                                training_sample=training, seed=int(seed), channel_names=radlayers.VIEW_A + radlayers.VIEW_B))


def _score_field(field: np.ndarray, fold: dict, valid: np.ndarray, global_budget: int,
                 pool_cap: int) -> dict:
    region = fold["region"] & valid
    allowed = region & ~fold["visible"]
    budget = int(round(global_budget * int(region.sum()) / max(int(valid.sum()), 1)))
    pool = min(pool_cap, max(budget * 16, 10_000))
    density = np.zeros(valid.shape, np.float32)
    vals = np.nan_to_num(np.asarray(field, np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    density[allowed] = np.clip(vals[allowed], 0.0, 1.0)
    prediction, placement = emit.greedy_emit(density, allowed, 0.0, budget, pool=pool, log=lambda *_: None)
    # Keep held-component labels outside the all-band feature footprint as false negatives. The
    # model cannot place there, but excluding them from the metric would make the holdout easier.
    truth = fold["held_all"]
    score = metric.dti(prediction, truth)
    score.update(emitted=int((prediction > 0).sum()), per_fold_budget=budget,
                 allowed_pixels=int(allowed.sum()), placement_pool=pool, placement=placement)
    return score


def _score_random(fold: dict, valid: np.ndarray, global_budget: int, seed: int) -> dict:
    region = fold["region"] & valid
    allowed = region & ~fold["visible"]
    budget = int(round(global_budget * int(region.sum()) / max(int(valid.sum()), 1)))
    indices = np.flatnonzero(allowed.ravel())
    count = min(budget, int(indices.size))
    rng = np.random.default_rng(seed)
    chosen = rng.choice(indices, size=count, replace=False) if count else np.empty(0, np.int64)
    prediction = np.zeros(valid.size, np.float32)
    prediction[chosen] = 1.0
    prediction = prediction.reshape(valid.shape)
    score = metric.dti(prediction, fold["held_all"])
    score.update(emitted=count, per_fold_budget=budget, allowed_pixels=int(allowed.sum()),
                 random_seed=int(seed), placement="uniform without-replacement matched control")
    return score


def _fold_model_signatures(ctx, feature_receipt, rows, y, fi):
    names_a, names_b = list(radlayers.VIEW_A), list(radlayers.VIEW_B)
    names_all = names_a + names_b
    cols_a = list(range(len(names_a)))
    cols_b = list(range(len(names_a), len(names_all)))
    cols_all = list(range(len(names_all)))
    seed = int(ctx["registration"]["seed"]) + int(fi)
    sigs = {}
    for name, names, columns in (("A0", names_a, cols_a), ("B0", names_b, cols_b),
                                 ("AB0", names_all, cols_all)):
        model_name = f"fold{fi}_{name}"
        sigs[name] = _model_signature(ctx, feature_receipt, model_name, names, columns,
                                      rows, y, seed, None, ctx["registration"]["learner"])
    return names_a, names_b, names_all, cols_a, cols_b, cols_all, seed, sigs


def _read_cached_round0(path: Path, signature: str, model_names: list[str], signatures: dict) -> dict | None:
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if record.get("cache_signature") != signature:
        return None
    if not all(model_cache_matches(name, signatures[key]) for key, name in zip(("A0", "B0", "AB0"), model_names)):
        return None
    return record


def run_round0_fold(ctx: dict, feature_receipt: dict, stack: np.ndarray, catalogue: np.ndarray,
                    valid: np.ndarray, depth_rank: np.ndarray, catalogue_collar: np.ndarray,
                    fold: dict) -> dict:
    registration = ctx["registration"]
    fi = int(fold["fold"])
    buffer_px = int(registration["fold_protocol"]["buffer_px"])
    validate_fold(fold, buffer_px)
    rows, y, training = H57.training_rows(
        catalogue, valid, fold["train"],
        max_negatives=int(registration["fold_protocol"]["max_sampled_negatives_per_fold"]),
        seed=int(registration["seed"]) + fi,
        collar_px=int(registration["fold_protocol"]["negative_collar_px"]),
    )
    names_a, names_b, names_all, cols_a, cols_b, cols_all, seed, signatures = _fold_model_signatures(
        ctx, feature_receipt, rows, y, fi)
    fold_path = WORK / "folds" / f"fold{fi}_round0.json"
    cache_signature = _fold_cache_signature(feature_receipt, fold, training, seed)
    cached = _read_cached_round0(fold_path, cache_signature,
                                 [f"fold{fi}_A0", f"fold{fi}_B0", f"fold{fi}_AB0"], signatures)
    if cached is not None:
        log(f"fold {fi}: reusing complete round-0 predictions/scores and model caches")
        return cached

    model_a, _, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_a, cols_a,
                                      seed, f"fold{fi}_A0")
    model_b, _, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_b, cols_b,
                                      seed, f"fold{fi}_B0")
    model_ab, _, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_all, cols_all,
                                       seed, f"fold{fi}_AB0")
    prediction_domain = fold["train"] | fold["region"]
    pa = H57.predict_grid(stack, model_a, cols_a, prediction_domain)
    pb = H57.predict_grid(stack, model_b, cols_b, prediction_domain)
    pab = H57.predict_grid(stack, model_ab, cols_all, prediction_domain)
    train_unlabelled = fold["train"] & valid & ~catalogue
    qa = H57.training_thresholds(pa, train_unlabelled)
    qb = H57.training_thresholds(pb, train_unlabelled)
    thresholds = {"A": qa, "B": qb}
    negative = fold["region"] & valid & ~catalogue_collar
    gate_cfg = registration["independence_gate"]
    block_rows = spatial.negative_block_errors(
        pa, pb, negative, fi, (qa["q99"], qb["q99"]),
        side=int(registration["pseudo_label_exchange"]["block_side_px"]),
        minimum=int(gate_cfg["minimum_finite_negatives_per_50x50_block"]),
    )
    round0_field, strata0, strata_counts = H57.compose_primary_field(
        pa, pb, thresholds, depth_rank, fold["region"] & valid)
    max_ab = np.fmax(pa, pb).astype(np.float32)
    budget = int(registration["primary_budget_global_pixels"])
    pool_cap = int(registration["placement"]["pool_cap"])
    fields = {
        "view_A": pa,
        "view_B_corrected": pb,
        "early_fusion": pab,
        "max_AB_union_control": max_ab,
        "round0_disagreement_no_exchange": round0_field,
    }
    scores = {}
    for arm, field in fields.items():
        log(f"fold {fi}: placing round-0 control {arm}")
        scores[arm] = _score_field(field, fold, valid, budget, pool_cap)
        log(f"fold {fi}: {arm} DTI={scores[arm]['dti']:.6f} emitted={scores[arm]['emitted']}")
    scores["matched_random"] = _score_random(
        fold, valid, budget, int(registration["seed"]) + 100_000 + fi)
    record = dict(
        fold=fi, receipt=fold["receipt"], training_sample=training,
        training_rows_sha256=_row_hash(rows, y), thresholds=thresholds,
        round0_strata=strata_counts, negative_error_blocks=block_rows,
        scores=scores, cache_signature=cache_signature,
        exact_training_rows_shared_by_all_controls=True,
        model_seed=seed, feature_channels={"A": names_a, "B": names_b},
    )
    write_json(fold_path, record)
    del pa, pb, pab, max_ab, round0_field, fields, model_a, model_b, model_ab
    return record


def _load_model_for_fold(ctx: dict, feature_receipt: dict, stack: np.ndarray,
                         catalogue: np.ndarray, valid: np.ndarray, fold: dict,
                         model_letter: str):
    fi = int(fold["fold"])
    rows, y, _ = H57.training_rows(
        catalogue, valid, fold["train"],
        max_negatives=int(ctx["registration"]["fold_protocol"]["max_sampled_negatives_per_fold"]),
        seed=int(ctx["registration"]["seed"]) + fi,
        collar_px=int(ctx["registration"]["fold_protocol"]["negative_collar_px"]),
    )
    names_a, names_b = list(radlayers.VIEW_A), list(radlayers.VIEW_B)
    names = names_a if model_letter == "A" else names_b
    cols = list(range(len(names_a))) if model_letter == "A" else list(range(len(names_a), len(names_a) + len(names_b)))
    model_name = f"fold{fi}_{model_letter}0"
    model, _, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names, cols,
                                    int(ctx["registration"]["seed"]) + fi, model_name)
    return model, rows, y, names, cols


def precheck_exchange(ctx: dict, feature_receipt: dict, stack: np.ndarray,
                      catalogue: np.ndarray, valid: np.ndarray,
                      rows_by_fold: dict[int, dict]) -> dict:
    """Generate no round-1 fit until OOF independence and all four bilateral segment checks pass."""
    registration = ctx["registration"]
    out_path = EVIDENCE / "h57_pseudo_exchange.json"
    gate = json.loads((EVIDENCE / "h57_independence.json").read_text())
    if (gate.get("registration_sha256") != ctx["registration_sha256"]
            or gate.get("run_signature") != feature_receipt["run_signature"]):
        raise RuntimeError("OOF independence receipt does not match the current frozen H57 run")
    if not gate["allow_exchange"]:
        report = dict(generated_utc=utc_now(), status="DISABLED_INDEPENDENCE_GATE",
                      enabled=False, used_in_primary=False,
                      reason="OOF block-error independence failed closed; no pseudo labels were generated and no round-1 model was fit",
                      independence_sha256=digest(EVIDENCE / "h57_independence.json"), folds=[])
        write_json(out_path, report)
        return report

    from scipy import ndimage
    forbidden_base = ndimage.binary_dilation(
        catalogue, structure=spatial.disk(int(registration["fold_protocol"]["negative_collar_px"])))
    pseudo_dir = WORK / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    fold_reports, availability_failures = [], []
    for fold in spatial.folds(catalogue, valid, int(registration["fold_protocol"]["buffer_px"])):
        fi = int(fold["fold"])
        validate_fold(fold, int(registration["fold_protocol"]["buffer_px"]))
        model_a, rows, y, _, cols_a = _load_model_for_fold(ctx, feature_receipt, stack,
                                                           catalogue, valid, fold, "A")
        model_b, _, _, _, cols_b = _load_model_for_fold(ctx, feature_receipt, stack,
                                                        catalogue, valid, fold, "B")
        pa = H57.predict_grid(stack, model_a, cols_a, fold["train"])
        pb = H57.predict_grid(stack, model_b, cols_b, fold["train"])
        thresholds = rows_by_fold[fi]["thresholds"]
        train_unlabelled = fold["train"] & valid & ~catalogue
        qa_check = H57.training_thresholds(pa, train_unlabelled)
        qb_check = H57.training_thresholds(pb, train_unlabelled)
        for view, stored, recomputed in (("A", thresholds["A"], qa_check), ("B", thresholds["B"], qb_check)):
            for key in ("q40", "q80", "q99"):
                if not np.isclose(stored[key], recomputed[key], rtol=0, atol=1e-8):
                    raise RuntimeError(f"fold {fi} {view} threshold changed before pseudo-label exchange")
        forbidden = forbidden_base.copy()
        forbidden.ravel()[rows] = True
        exchange = registration["pseudo_label_exchange"]
        side = int(exchange["block_side_px"])
        min_pixels = int(exchange["minimum_segment_pixels"])
        cap = int(exchange["max_pseudo_pixels_per_donor_per_fold"])
        to_b, seg_a = spatial.whole_pseudo_segments(
            pa, pb, fold["train"], forbidden, thresholds["A"]["q99"],
            thresholds["B"]["q40"], thresholds["B"]["q80"], side=side,
            min_pixels=min_pixels, cap=cap)
        to_a, seg_b = spatial.whole_pseudo_segments(
            pb, pa, fold["train"], forbidden, thresholds["B"]["q99"],
            thresholds["A"]["q40"], thresholds["A"]["q80"], side=side,
            min_pixels=min_pixels, cap=cap)
        if (len(seg_a) < 1) or (len(seg_b) < 1):
            availability_failures.append(dict(fold=fi, A_to_B_segments=len(seg_a), B_to_A_segments=len(seg_b)))
        if to_a.size and (not fold["train"].ravel()[to_a].all() or fold["region"].ravel()[to_a].any()
                          or forbidden.ravel()[to_a].any()):
            raise RuntimeError(f"fold {fi} A-target pseudo rows violate registered forbidden masks")
        if to_b.size and (not fold["train"].ravel()[to_b].all() or fold["region"].ravel()[to_b].any()
                          or forbidden.ravel()[to_b].any()):
            raise RuntimeError(f"fold {fi} B-target pseudo rows violate registered forbidden masks")
        cache_path = pseudo_dir / f"fold{fi}.npz"
        tmp = pseudo_dir / f"fold{fi}.partial.npz"
        np.savez_compressed(tmp, pseudo_to_a=to_a, pseudo_to_b=to_b)
        tmp.replace(cache_path)
        fold_reports.append(dict(
            fold=fi,
            A_donor_to_B=dict(pixels=int(to_b.size), segments=seg_a,
                              pixel_index_sha256=hashlib.sha256(np.sort(to_b).astype("<i8").tobytes()).hexdigest(),
                              evaluation_pixels=int(fold["region"].ravel()[to_b].sum())),
            B_donor_to_A=dict(pixels=int(to_a.size), segments=seg_b,
                              pixel_index_sha256=hashlib.sha256(np.sort(to_a).astype("<i8").tobytes()).hexdigest(),
                              evaluation_pixels=int(fold["region"].ravel()[to_a].sum())),
            all_rows_train_only=bool(fold["train"].ravel()[to_a].all() and fold["train"].ravel()[to_b].all()),
            zero_evaluation_rows=bool(not fold["region"].ravel()[to_a].any() and not fold["region"].ravel()[to_b].any()),
            forbidden_hash_excluded=True,
            pseudo_file=str(cache_path.relative_to(ROOT)),
        ))
        del pa, pb, model_a, model_b

    enabled = not availability_failures and len(fold_reports) == int(registration["fold_protocol"]["folds"])
    report = dict(
        generated_utc=utc_now(), status="READY_FOR_ROUND1" if enabled else "DISABLED_NO_BILATERAL_SEGMENTS",
        enabled=bool(enabled), used_in_primary=False, precheck_completed_before_any_round1_fit=True,
        independence_sha256=digest(EVIDENCE / "h57_independence.json"),
        minimum_accepted_segments_per_direction_per_fold=1,
        failures=availability_failures, folds=fold_reports,
        reason=("all four folds have accepted whole components in both directions; round 1 may proceed"
                if enabled else "at least one fold lacks a whole eligible segment in one donor direction; disable exchange globally and use B-only fallback"),
    )
    write_json(out_path, report)
    return report


def run_round1_fold(ctx: dict, feature_receipt: dict, stack: np.ndarray,
                    catalogue: np.ndarray, valid: np.ndarray, depth_rank: np.ndarray,
                    fold: dict, round0_record: dict) -> dict:
    fi = int(fold["fold"])
    pseudo_path = WORK / "pseudo" / f"fold{fi}.npz"
    if not pseudo_path.is_file():
        raise RuntimeError(f"fold {fi} pseudo precheck cache missing; no round-1 fit")
    pseudo = np.load(pseudo_path)
    pseudo_to_a = pseudo["pseudo_to_a"].astype(np.int64)
    pseudo_to_b = pseudo["pseudo_to_b"].astype(np.int64)
    rows, y, training = H57.training_rows(
        catalogue, valid, fold["train"],
        max_negatives=int(ctx["registration"]["fold_protocol"]["max_sampled_negatives_per_fold"]),
        seed=int(ctx["registration"]["seed"]) + fi,
        collar_px=int(ctx["registration"]["fold_protocol"]["negative_collar_px"]),
    )
    names_a, names_b = list(radlayers.VIEW_A), list(radlayers.VIEW_B)
    cols_a = list(range(len(names_a)))
    cols_b = list(range(len(names_a), len(names_a) + len(names_b)))
    seed = int(ctx["registration"]["seed"]) + fi
    model_a, sig_a, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_a, cols_a,
                                          seed, f"fold{fi}_A1", pseudo=pseudo_to_a)
    model_b, sig_b, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_b, cols_b,
                                          seed, f"fold{fi}_B1", pseudo=pseudo_to_b)
    pa = H57.predict_grid(stack, model_a, cols_a, fold["region"])
    pb = H57.predict_grid(stack, model_b, cols_b, fold["region"])
    field, strata, counts = H57.compose_primary_field(
        pa, pb, round0_record["thresholds"], depth_rank, fold["region"] & valid)
    score = _score_field(field, fold, valid,
                         int(ctx["registration"]["primary_budget_global_pixels"]),
                         int(ctx["registration"]["placement"]["pool_cap"]))
    record = dict(fold=fi, arm="cotrain_disagreement_aonly", score=score,
                  strata=counts, thresholds_reused_from_round0=True,
                  pseudo_to_a_pixels=int(pseudo_to_a.size), pseudo_to_b_pixels=int(pseudo_to_b.size),
                  model_signatures={"A1": sig_a, "B1": sig_b},
                  training_rows_sha256=_row_hash(rows, y),
                  same_base_rows_seed_and_learner=True)
    write_json(WORK / "folds" / f"fold{fi}_round1.json", record)
    del pa, pb, field, model_a, model_b, pseudo
    return record


def run_holdout(ctx: dict, feature_receipt: dict) -> dict:
    existing_path = EVIDENCE / "h57_holdout.json"
    run_sig = feature_receipt["run_signature"]
    if existing_path.is_file():
        old = json.loads(existing_path.read_text())
        if (old.get("registration_sha256") == ctx["registration_sha256"]
                and old.get("run_signature") == run_sig
                and old.get("status") == "COMPLETED_RESEARCH_HOLDOUT"):
            log("matching completed H57 holdout exists; reusing it without refit")
            return old
        raise RuntimeError("an H57 holdout receipt exists with different registration/code/input signature")

    registration = ctx["registration"]
    catalogue, valid, depth_rank, stack = load_data(feature_receipt)
    collar = ndi.binary_dilation(catalogue, structure=spatial.disk(int(registration["fold_protocol"]["negative_collar_px"])))
    fold_receipts = []
    for fold in spatial.folds(catalogue, valid, int(registration["fold_protocol"]["buffer_px"])):
        fold_receipts.append(validate_fold(fold, int(registration["fold_protocol"]["buffer_px"])))
        del fold
    if len(fold_receipts) != int(registration["fold_protocol"]["folds"]):
        raise RuntimeError("spatial fold count differs from preregistration; no model fit started")
    write_run_integrity(ctx, "MODEL_FIT_STARTED", feature_receipt,
                        dict(stage="outer spatial holdout", fold_leakage_receipts=fold_receipts))
    log(f"H57 round-0 fits start: {len(fold_receipts)} folds, buffer={registration['fold_protocol']['buffer_px']} px")
    fold_records = {}
    for fold in spatial.folds(catalogue, valid, int(registration["fold_protocol"]["buffer_px"])):
        fi = int(fold["fold"])
        fold_records[fi] = run_round0_fold(ctx, feature_receipt, stack, catalogue, valid,
                                           depth_rank, collar, fold)
        del fold

    rows_by_fold = {fi: record["negative_error_blocks"] for fi, record in fold_records.items()}
    indep_cfg = registration["independence_gate"]
    independence = H57.independence_gate(
        rows_by_fold, threshold=float(indep_cfg["max_abs_correlation"]),
        minimum_blocks=int(indep_cfg["minimum_non_degenerate_blocks"]),
    )
    independence.update(generated_utc=utc_now(), registration_sha256=ctx["registration_sha256"],
                        run_signature=run_sig, oof_source="round-0 supervised predictions in held-out regions only",
                        negative_class="held-out catalogue-zero proxies, not verified fault absence",
                        fpr_threshold="round-0 training-unlabelled q99 for each view")
    write_json(EVIDENCE / "h57_independence.json", independence)
    pseudo = precheck_exchange(ctx, feature_receipt, stack, catalogue, valid, fold_records)

    primary_records = {}
    if pseudo["enabled"]:
        log("OOF independence and bilateral pseudo-component gates pass; fitting one registered exchange round")
        for fold in spatial.folds(catalogue, valid, int(registration["fold_protocol"]["buffer_px"])):
            fi = int(fold["fold"])
            primary_records[fi] = run_round1_fold(ctx, feature_receipt, stack, catalogue,
                                                  valid, depth_rank, fold, fold_records[fi])
            del fold
        pseudo["used_in_primary"] = True
        pseudo["round1_model_fits"] = 8
        pseudo["round1_model_fit_utc"] = utc_now()
        write_json(EVIDENCE / "h57_pseudo_exchange.json", pseudo)
    else:
        log("co-training disabled; registered research comparison is B-only, not co-training")

    control_means = {
        name: float(np.mean([fold_records[fi]["scores"][name]["dti"] for fi in sorted(fold_records)]))
        for name in CONTROL_NAMES
    }
    random_mean = float(np.mean([fold_records[fi]["scores"]["matched_random"]["dti"]
                                 for fi in sorted(fold_records)]))
    if pseudo["enabled"]:
        primary_name = "cotrain_disagreement_aonly"
        primary_mean = float(np.mean([primary_records[fi]["score"]["dti"] for fi in sorted(primary_records)]))
        best_control = max(CONTROL_NAMES, key=lambda name: control_means[name])
        paired = [primary_records[fi]["score"]["dti"] - fold_records[fi]["scores"][best_control]["dti"]
                  for fi in sorted(fold_records)]
        mean_lift = float(np.mean(paired))
        historical = float(registration["primary_comparator"]["historical_best_comparable"]["mean_dti"])
        historical_lift = primary_mean - historical
        positive = sum(value > 0 for value in paired)
        gates_cfg = registration["slot_gate"]
        scientific_pass = bool(
            independence["allow_exchange"]
            and mean_lift >= float(gates_cfg["minimum_mean_lift_vs_strongest_same_run_control"])
            and historical_lift >= float(gates_cfg["minimum_mean_lift_vs_historical_best"])
            and positive >= int(gates_cfg["minimum_positive_paired_outer_folds"])
        )
        scientific_reason = ("all registered holdout thresholds pass" if scientific_pass else
                             "one or more registered mean-lift / paired-fold thresholds failed")
        primary_folds = {
            fi: dict(score=primary_records[fi]["score"], paired_lift_vs_fixed_best_control=paired[i],
                     primary_strata=primary_records[fi]["strata"])
            for i, fi in enumerate(sorted(fold_records))
        }
    else:
        primary_name = "view_B_corrected_fallback"
        primary_mean = control_means["view_B_corrected"]
        best_control = max(CONTROL_NAMES, key=lambda name: control_means[name])
        paired = []
        mean_lift = None
        historical = float(registration["primary_comparator"]["historical_best_comparable"]["mean_dti"])
        historical_lift = primary_mean - historical
        positive = 0
        scientific_pass = False
        scientific_reason = ("co-training primary was not fit or scored because the registered exchange gate failed; "
                             "B-only is a research fallback, not a promoted primary")
        primary_folds = {}

    fold_output = []
    for fi in sorted(fold_records):
        fold_output.append(dict(
            fold=fi, receipt=fold_records[fi]["receipt"],
            training_sample=fold_records[fi]["training_sample"],
            training_rows_sha256=fold_records[fi]["training_rows_sha256"],
            thresholds=fold_records[fi]["thresholds"],
            round0_strata=fold_records[fi]["round0_strata"],
            scores=fold_records[fi]["scores"],
            primary=(primary_folds.get(fi) if pseudo["enabled"] else None),
            paired_lift_vs_fixed_best_control=(primary_folds.get(fi, {}).get("paired_lift_vs_fixed_best_control")
                                               if pseudo["enabled"] else None),
        ))
    holdout = dict(
        generated_utc=utc_now(), status="COMPLETED_RESEARCH_HOLDOUT",
        experiment=registration["experiment"], registration_sha256=ctx["registration_sha256"],
        hypothesis_sha256=ctx["hypothesis_sha256"], prefit_lock_sha256=ctx["prefit_lock_sha256"],
        run_signature=run_sig, feature_manifest_sha256=feature_receipt["manifest_sha256"],
        input_sha256={k: v["sha256"] for k, v in ctx["inputs"].items()},
        model_fit=True, holdout_run=True, portal_upload_performed=False, submission_slots_used=0,
        protocol=dict(folds=int(registration["fold_protocol"]["folds"]),
                      buffer_px=int(registration["fold_protocol"]["buffer_px"]),
                      feature_support_px=int(registration["feature_construction"]["max_spatial_support_px"]),
                      feature_channels_A=len(radlayers.VIEW_A), feature_channels_B=len(radlayers.VIEW_B),
                      eligible_pixels=int(valid.sum()), primary_budget_global_pixels=int(registration["primary_budget_global_pixels"]),
                      negative_class=registration["fold_protocol"]["negative_class"],
                      all_fold_leakage_receipts=fold_receipts),
        controls=dict(means=control_means, matched_random_mean=random_mean,
                      strongest_control=best_control, strongest_control_mean=control_means[best_control]),
        exchange=dict(enabled=bool(pseudo["enabled"]), independence_status=independence["status"],
                      reason=pseudo["reason"], bilateral_pseudo_gate=bool(pseudo["enabled"])),
        primary=dict(arm=primary_name, mean_dti=primary_mean,
                     measured_as_co_training=bool(pseudo["enabled"]),
                     fold_scores={str(fi): primary_folds[fi] for fi in primary_folds}),
        comparisons=dict(mean_lift_vs_fixed_strongest_same_run_control=mean_lift,
                         fixed_strongest_same_run_control=best_control,
                         paired_outer_folds_positive=int(positive), paired_outer_folds_total=4,
                         historical_best_comparable_mean_dti=historical,
                         mean_lift_vs_historical_best=historical_lift,
                         historical_reference=registration["primary_comparator"]["historical_best_comparable"]),
        slot_gate=dict(scientific_holdout_pass=bool(scientific_pass), approved_for_weekly_slot=False,
                       approval_pending_format_uniqueness_reasoning=bool(scientific_pass),
                       minimum_mean_lift_same_run=float(registration["slot_gate"]["minimum_mean_lift_vs_strongest_same_run_control"]),
                       minimum_mean_lift_historical=float(registration["slot_gate"]["minimum_mean_lift_vs_historical_best"]),
                       minimum_positive_folds=int(registration["slot_gate"]["minimum_positive_paired_outer_folds"]),
                       reason=scientific_reason),
        independence_file="evidence/h57_independence.json", pseudo_exchange_file="evidence/h57_pseudo_exchange.json",
        folds=fold_output,
        no_public_score_forecast=True, organizer_score_mapping_authenticated=False,
        organizer_input_bytes_authenticated=False,
        caveats=[
            "Input rasters are SHA/size-pinned owner mirrors, not organizer-authenticated downloads.",
            "Catalogue-zero cells are proxy negatives, not verified geological absence.",
            "Original 8-connected label components are spatial proxies, not authenticated fault segments.",
            "A passing catalogue-recovery holdout is not validation on the organizer's hidden new-fault truth.",
            "H55's 0.1970318 historical comparator is a local comparable holdout, not a public score or organizer truth.",
            "No leaderboard-score forecast, portal upload, or submission-slot use is recorded.",
        ],
    )
    write_json(existing_path, holdout)
    write_run_integrity(ctx, "HOLDOUT_COMPLETE", feature_receipt,
                        dict(holdout_path=str(existing_path.relative_to(ROOT)),
                             holdout_sha256=digest(existing_path), scientific_gate=scientific_pass,
                             primary_arm=primary_name))
    log(f"H57 holdout complete: arm={primary_name} mean={primary_mean:.6f}, "
        f"same-run lift={mean_lift if mean_lift is not None else 'N/A'}, "
        f"historical lift={historical_lift:+.6f}, scientific gate={scientific_pass}")
    return holdout


def _deployment_training(ctx: dict, feature_receipt: dict, stack: np.ndarray,
                         catalogue: np.ndarray, valid: np.ndarray):
    registration = ctx["registration"]
    rows, y, training = H57.training_rows(
        catalogue, valid, valid,
        max_negatives=int(registration["fold_protocol"]["max_sampled_negatives_per_fold"]),
        seed=int(registration["seed"]),
        collar_px=int(registration["fold_protocol"]["negative_collar_px"]),
    )
    names_a, names_b = list(radlayers.VIEW_A), list(radlayers.VIEW_B)
    cols_a = list(range(len(names_a)))
    cols_b = list(range(len(names_a), len(names_a) + len(names_b)))
    model_a = model_b = None
    if json.loads((EVIDENCE / "h57_holdout.json").read_text())["exchange"]["enabled"]:
        model_a, sig_a, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_a, cols_a,
                                              int(registration["seed"]), "deploy_A0")
    model_b, sig_b, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_b, cols_b,
                                          int(registration["seed"]), "deploy_B0")
    p_b0 = H57.predict_grid(stack, model_b, cols_b, valid)
    if model_a is None:
        return dict(arm="view_B_corrected_fallback", field=p_b0, p_a=None, p_b=p_b0,
                    thresholds=None, strata=None, training=training,
                    model_signatures={"B0": sig_b}, exchange=None,
                    active=False, reason="holdout disabled co-training; fit corrected View B only")

    p_a0 = H57.predict_grid(stack, model_a, cols_a, valid)
    unlabelled = valid & ~catalogue
    thresholds = {"A": H57.training_thresholds(p_a0, unlabelled),
                  "B": H57.training_thresholds(p_b0, unlabelled)}
    forbidden = ndi.binary_dilation(catalogue, structure=spatial.disk(int(registration["fold_protocol"]["negative_collar_px"])))
    forbidden.ravel()[rows] = True
    exchange_cfg = registration["pseudo_label_exchange"]
    to_b, seg_a = spatial.whole_pseudo_segments(
        p_a0, p_b0, valid, forbidden, thresholds["A"]["q99"],
        thresholds["B"]["q40"], thresholds["B"]["q80"],
        side=int(exchange_cfg["block_side_px"]), min_pixels=int(exchange_cfg["minimum_segment_pixels"]),
        cap=int(exchange_cfg["max_pseudo_pixels_per_donor_per_fold"]))
    to_a, seg_b = spatial.whole_pseudo_segments(
        p_b0, p_a0, valid, forbidden, thresholds["B"]["q99"],
        thresholds["A"]["q40"], thresholds["A"]["q80"],
        side=int(exchange_cfg["block_side_px"]), min_pixels=int(exchange_cfg["minimum_segment_pixels"]),
        cap=int(exchange_cfg["max_pseudo_pixels_per_donor_per_fold"]))
    if not len(seg_a) or not len(seg_b):
        return dict(arm="view_B_corrected_fallback", field=p_b0, p_a=p_a0, p_b=p_b0,
                    thresholds=thresholds, strata=None, training=training,
                    model_signatures={"A0": sig_a, "B0": sig_b},
                    exchange=dict(enabled=False, reason="deployment fit has no eligible whole segments in both directions",
                                  A_to_B_segments=len(seg_a), B_to_A_segments=len(seg_b)),
                    active=False, reason="full-data bilateral exchange precheck failed; use B-only fallback")
    model_a1, sig_a1, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_a, cols_a,
                                            int(registration["seed"]), "deploy_A1", pseudo=to_a)
    model_b1, sig_b1, _ = fit_or_load_model(ctx, feature_receipt, stack, rows, y, names_b, cols_b,
                                            int(registration["seed"]), "deploy_B1", pseudo=to_b)
    p_a1 = H57.predict_grid(stack, model_a1, cols_a, valid)
    p_b1 = H57.predict_grid(stack, model_b1, cols_b, valid)
    depth_rank = np.load(DERIVED / "A_depth_base_rank__rank.npy", mmap_mode="r")[:].astype(np.float32)
    field, strata, strata_counts = H57.compose_primary_field(p_a1, p_b1, thresholds, depth_rank, valid)
    return dict(arm="cotrain_disagreement_aonly", field=field, p_a=p_a1, p_b=p_b1,
                p_a0=p_a0, p_b0=p_b0, thresholds=thresholds, strata=strata,
                strata_counts=strata_counts, training=training,
                model_signatures={"A0": sig_a, "B0": sig_b, "A1": sig_a1, "B1": sig_b1},
                exchange=dict(enabled=True, A_to_B_segments=len(seg_a), A_to_B_pixels=int(to_b.size),
                              B_to_A_segments=len(seg_b), B_to_A_pixels=int(to_a.size),
                              A_to_B_components=seg_a, B_to_A_components=seg_b,
                              pseudo_to_a_sha256=hashlib.sha256(np.sort(to_a).astype("<i8").tobytes()).hexdigest(),
                              pseudo_to_b_sha256=hashlib.sha256(np.sort(to_b).astype("<i8").tobytes()).hexdigest()),
                active=True, reason="round-1 whole-component exchange applied after the OOF gate")


def _emission(field: np.ndarray, allowed: np.ndarray, budget: int, pool_cap: int) -> tuple[np.ndarray, dict]:
    pool = min(pool_cap, max(int(budget) * 16, 10_000))
    density = np.zeros(allowed.shape, np.float32)
    values = np.nan_to_num(np.asarray(field, np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    density[allowed] = np.clip(values[allowed], 0.0, 1.0)
    emitted, stats = emit.greedy_emit(density, allowed, 0.0, int(budget), pool=pool, log=lambda *_: None)
    return emitted, stats


def _reasoning_csv(payload: dict, path: Path) -> dict:
    import csv

    rows = []
    for candidate in payload.get("candidates", []):
        def stat(name, field="mean"):
            value = candidate.get(name) or {}
            return value.get(field) if isinstance(value, dict) else None
        rows.append(dict(
            candidate_id=f"H57-A-{candidate['component']:05d}", row=candidate.get("row"),
            col=candidate.get("col"), utm_easting=candidate.get("utm_easting"),
            utm_northing=candidate.get("utm_northing"), latitude=candidate.get("lat"),
            longitude=candidate.get("lon"), neighborhood_pixels=candidate.get("n_px"),
            emitted_A_only_pixels=candidate.get("n_emitted_px"),
            distance_to_catalogue_m=candidate.get("distance_to_nearest_catalogue_m"),
            strike_degrees=candidate.get("strike_deg"), elongation=candidate.get("elongation"),
            view_A_score_mean=stat("view_a_score"), view_B_score_mean=stat("view_b_score"),
            basement_depth_rank_mean=stat("depth_to_basement_rank"),
            gravity_step_rank_median=stat("gravity_step_rank", "p50"),
            TC_step_rank_median=stat("tc_step_rank", "p50"),
            ThK_step_rank_median=stat("thk_step_rank", "p50"),
            UK_step_rank_median=stat("uk_step_rank", "p50"),
            LiDAR_coverage_fraction=stat("lidar_coverage"),
            LiDAR_scarp_rank_median=stat("lidar_scarp_rank", "p50"),
            interpretation=" ".join(candidate.get("interpretation") or []),
            alternatives="; ".join(candidate.get("alternative_explanations") or []),
            verification_status=candidate.get("verification_status"),
        ))
    headers = list(rows[0]) if rows else [
        "candidate_id", "row", "col", "utm_easting", "utm_northing", "latitude", "longitude",
        "neighborhood_pixels", "emitted_A_only_pixels", "distance_to_catalogue_m", "strike_degrees",
        "elongation", "view_A_score_mean", "view_B_score_mean", "basement_depth_rank_mean",
        "gravity_step_rank_median", "TC_step_rank_median", "ThK_step_rank_median", "UK_step_rank_median",
        "LiDAR_coverage_fraction", "LiDAR_scarp_rank_median", "interpretation", "alternatives", "verification_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return dict(path=str(path.relative_to(ROOT)), rows=len(rows), sha256=digest(path),
                candidate_groups=len(payload.get("candidates", [])),
                emitted_a_only_pixels=payload.get("n_px", 0))


def build_artifact(ctx: dict, feature_receipt: dict, holdout: dict) -> dict:
    registration = ctx["registration"]
    if holdout.get("registration_sha256") != ctx["registration_sha256"]:
        raise RuntimeError("holdout was produced under a different H57 registration")
    if holdout.get("run_signature") != feature_receipt.get("run_signature"):
        raise RuntimeError("holdout code/input/feature signature differs from deployment")
    if holdout.get("status") != "COMPLETED_RESEARCH_HOLDOUT":
        raise RuntimeError("no completed H57 spatial holdout; do not build a candidate")
    # Idempotent exact-run guard.
    for receipt_path in sorted(EVIDENCE.glob("submission_gems52-h57-*.json")):
        prior_receipt = json.loads(receipt_path.read_text())
        if (prior_receipt.get("run_signature") == feature_receipt["run_signature"]
                and prior_receipt.get("registration_sha256") == ctx["registration_sha256"]):
            artifact_path = ROOT / prior_receipt.get("path", "")
            if (not artifact_path.is_file()
                    or digest(artifact_path) != prior_receipt.get("sha256")):
                raise RuntimeError("matching H57 receipt exists but its canonical TIFF is missing or altered")
            download = prior_receipt.get("download")
            if download:
                download_path = ROOT / download
                if not download_path.is_file() or digest(download_path) != prior_receipt.get("sha256"):
                    raise RuntimeError("matching H57 download copy is missing or differs from its receipt")
            zip_download = prior_receipt.get("zip_download")
            if zip_download:
                zip_download_path = ROOT / zip_download
                if (not zip_download_path.is_file()
                        or digest(zip_download_path) != prior_receipt.get("zip_sha256")):
                    raise RuntimeError("matching H57 ZIP download is missing or differs from its receipt")
            log(f"matching H57 artifact receipt already exists: {receipt_path.name}; verified and reusing")
            return prior_receipt

    catalogue, valid, depth_rank, stack = load_data(feature_receipt)
    write_run_integrity(ctx, "MODEL_FIT_STARTED", feature_receipt,
                        dict(stage="full-data artifact fit after completed holdout"))
    deployed = _deployment_training(ctx, feature_receipt, stack, catalogue, valid)
    allowed = valid & ~catalogue
    global_budget = int(registration["primary_budget_global_pixels"])
    pool_cap = int(registration["placement"]["pool_cap"])
    prediction, placement = _emission(deployed["field"], allowed, global_budget, pool_cap)
    emitted_mask = prediction > 0
    if not emitted_mask.any():
        raise RuntimeError("registered emitter produced an empty candidate")
    if (emitted_mask & ~valid).any() or (emitted_mask & catalogue).any():
        raise RuntimeError("candidate contains pixels outside the eligible or visible-catalogue mask")
    decoded_sha = hashlib.sha256(prediction.astype("<f4").tobytes()).hexdigest()
    arm_slug = "cotrain-disagreement-aonly" if deployed["active"] else "view-b-corrected-fallback"
    name_receipt_path = WORK / "artifact_name.json"
    name_receipt = json.loads(name_receipt_path.read_text()) if name_receipt_path.is_file() else {}
    if (name_receipt.get("run_signature") == feature_receipt["run_signature"]
            and name_receipt.get("registration_sha256") == ctx["registration_sha256"]):
        stamp = name_receipt["stamp"]
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        write_json(name_receipt_path, dict(run_signature=feature_receipt["run_signature"],
                                           registration_sha256=ctx["registration_sha256"], stamp=stamp))
    stem = f"gems52-h57-{arm_slug}-{int(emitted_mask.sum())}px-{stamp}-{decoded_sha[:12]}-research"
    out = SUBMISSION / f"{stem}.tif"
    zip_path = SUBMISSION / f"{stem}.zip"
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    write_receipt = grid.write_geotiff(out, prediction.astype(np.float32, copy=False))
    with rasterio.open(out) as src:
        decoded = src.read(1)
    written_decoded_sha = hashlib.sha256(decoded.astype("<f4").tobytes()).hexdigest()
    if written_decoded_sha != decoded_sha or not np.array_equal(decoded, prediction):
        raise RuntimeError("written TIFF pixels do not exactly match the in-memory emission")
    format_report = gates.format_report(out, SAMPLE_PATH, footprint=valid)

    roots = [ROOT / "data", ROOT / "submission", ROOT / "docs"]
    prior_paths = gates.find_priors(roots, exclude=out)
    uniqueness = gates.uniqueness_report(prediction, prior_paths)
    prior_unique = bool(uniqueness["canonical_pattern_unique"])
    prior_union_distinct = not bool(uniqueness["equals_literal_prior_union"])
    same_run_union_report = dict(applicable=False, reason="fallback arm has no co-training two-view emission")
    if deployed["active"]:
        # Compare against standalone emissions from the exact round-1 A/B views that formed the
        # candidate, rather than the round-0 supervised controls.
        em_a, stats_a = _emission(deployed["p_a"], allowed, global_budget, pool_cap)
        em_b, stats_b = _emission(deployed["p_b"], allowed, global_budget, pool_cap)
        union = (em_a > 0) | (em_b > 0)
        same_run_union_report = dict(
            applicable=True, source="standalone emissions from the fitted round-1 View-A and View-B models",
            view_A_emitted=int((em_a > 0).sum()), view_B_emitted=int((em_b > 0).sum()),
            union_emitted=int(union.sum()), candidate_emitted=int(emitted_mask.sum()),
            candidate_equals_literal_AB_emission_union=bool(np.array_equal(emitted_mask, union)),
            candidate_intersection_with_union=int((emitted_mask & union).sum()),
            candidate_outside_AB_union=int((emitted_mask & ~union).sum()),
            union_pixels_not_in_candidate=int((union & ~emitted_mask).sum()),
            view_A_placement=stats_a, view_B_placement=stats_b,
            gate_pass=not bool(np.array_equal(emitted_mask, union)),
        )
    else:
        same_run_union_report["gate_pass"] = True

    reasoning_json = None
    reasoning_csv = None
    if deployed["active"]:
        layers = {}
        layer_names = (
            "A_depth_base_rank__rank", "A_grav_step__rank", "A_mag_step__rank",
            "A_strain_inv_rank__rank", "R_tc_step900__rank", "R_thk_step900__rank",
            "R_uk_step900__rank", "B_scarp_p900__rank", "L_step_max__rank", "L_cover",
        )
        for name in layer_names:
            p = DERIVED / f"{name}.npy"
            if p.exists():
                layers[name] = np.load(p, mmap_mode="r")
        layers.setdefault("Th_coherence", None)
        distance_to_catalogue = ndi.distance_transform_edt(~catalogue).astype(np.float32) * 100.0
        with rasterio.open(SAMPLE_PATH) as src:
            transform = src.transform
        reasoning_payload = reasoning.build(
            emitted_mask, deployed["strata"] == 2, layers, valid, distance_to_catalogue,
            catalogue, transform=transform, group_px=3, log=log,
            prob_a=deployed["p_a"], prob_b=deployed["p_b"],
        )
        alternatives = [
            "Lithologic boundary or basin-fill/bedrock contact rather than a fault.",
            "Gravity or basement-depth inversion/model dependence rather than independent structure.",
            "Radiometric survey or resampling seam rather than a geological contact.",
            "Road cut, channel, terrace riser or other non-tectonic surface lineament.",
            "LiDAR coverage edge, tile boundary or uneven acquisition rather than scarp absence/presence.",
        ]
        for candidate in reasoning_payload["candidates"]:
            candidate["candidate_id"] = f"H57-A-{candidate['component']:05d}"
            candidate["alternative_explanations"] = alternatives
            candidate["verification_status"] = (
                "MODEL HYPOTHESIS ONLY — not a verified fault, geothermal system or resource; "
                "field and expert confirmation required.")
        a_only_emitted = int((emitted_mask & (deployed["strata"] == 2) & valid & ~catalogue).sum())
        reasoning_complete = (reasoning_payload["n_px"] == a_only_emitted
                              and all(row.get("interpretation") and row.get("alternative_explanations")
                                      and row.get("verification_status")
                                      for row in reasoning_payload["candidates"]))
        reasoning_payload.update(
            generated_utc=utc_now(), candidate_file=out.name,
            expected_emitted_a_only_pixels=a_only_emitted,
            complete=bool(reasoning_complete),
            scope="Every emitted pixel in the registered A-only stratum is grouped at 300 m for review; component groups are not verified geological faults.",
            alternatives="Lithologic contact; basement/depth inversion dependence; radiometric survey seam; road/channel/terrace scarp; LiDAR coverage/tile boundary.",
            verification_status="MODEL HYPOTHESIS ONLY — field and expert confirmation required.",
        )
        reasoning_json_path = EVIDENCE / f"h57_reasoning_{stamp}.json"
        write_json(reasoning_json_path, reasoning_payload)
        reasoning_csv_path = EVIDENCE / f"h57_a_only_reasoning_{stamp}.csv"
        reasoning_csv = _reasoning_csv(reasoning_payload, reasoning_csv_path)
        reasoning_json = dict(path=str(reasoning_json_path.relative_to(ROOT)),
                              sha256=digest(reasoning_json_path), groups=reasoning_payload["n_components"],
                              emitted_a_only_pixels=a_only_emitted, complete=bool(reasoning_complete),
                              layers_present=reasoning_payload["layers_present"],
                              layers_missing=reasoning_payload["layers_missing"])
    else:
        reasoning_complete = False

    science = holdout["slot_gate"]
    local_gates = dict(
        scientific_holdout=bool(science["scientific_holdout_pass"]),
        canonical_decoded_pattern_unique=prior_unique,
        not_literal_prior_union=bool(prior_union_distinct),
        not_literal_same_run_AB_union=bool(same_run_union_report.get("applicable")
                                            and same_run_union_report.get("gate_pass")),
        format=bool(format_report["ok"]),
        a_only_reasoning=(bool(reasoning_complete) if deployed["active"] else False),
    )
    approved = bool(deployed["active"] and all(local_gates.values()))
    unique_id = f"GEMSDOE52-H57-{arm_slug}-{decoded_sha[:10]}"
    submission_name = unique_id
    if deployed["active"]:
        note = (f"H57 corrected A/B; band 6 is radiometric TC. 80px holdout lift "
                f"{holdout['comparisons']['mean_lift_vs_fixed_strongest_same_run_control']:+.4f}, "
                f"{holdout['comparisons']['paired_outer_folds_positive']}/4 folds; "
                + ("local gates pass; no public score claim." if approved else "research only; not approved for upload."))
    else:
        note = "H57 corrected View-B single-view fallback; co-training disabled by frozen OOF gates; research only; not approved for upload."
    note = note[:200]
    if len(submission_name) > 200:
        raise RuntimeError("portal submission name exceeds 200 characters")

    safe_to_download = bool(format_report["ok"] and prior_unique)
    import shutil
    # Keep an on-disk ZIP for audit convenience, but expose it as a simple download only after
    # local format/range and decoded-pattern uniqueness checks both pass.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(out, arcname=out.name)
    zip_sha256 = digest(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None or archive.namelist() != [out.name]:
            raise RuntimeError("candidate ZIP must contain exactly one TIFF with a valid CRC")
        if hashlib.sha256(archive.read(out.name)).hexdigest() != digest(out):
            raise RuntimeError("candidate ZIP TIFF payload differs from the canonical TIFF")
    if safe_to_download:
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, DOWNLOADS / out.name)
        shutil.copy2(zip_path, DOWNLOADS / zip_path.name)
        if digest(DOWNLOADS / out.name) != write_receipt["sha256"]:
            raise RuntimeError("published TIFF copy differs from the verified submission bytes")
        if digest(DOWNLOADS / zip_path.name) != zip_sha256:
            raise RuntimeError("published ZIP copy differs from its source bytes")
        with zipfile.ZipFile(DOWNLOADS / zip_path.name) as archive:
            members = archive.namelist()
            if archive.testzip() is not None or members != [out.name]:
                raise RuntimeError("published ZIP must contain exactly the single candidate TIFF with a valid CRC")
            if hashlib.sha256(archive.read(out.name)).hexdigest() != digest(out):
                raise RuntimeError("published ZIP TIFF payload differs from the canonical TIFF")
    receipt_path = EVIDENCE / f"submission_{stem}.json"
    receipt = dict(
        generated_utc=utc_now(), status="COMPLETED_RESEARCH_ARTIFACT",
        experiment=registration["experiment"], file=out.name, zip=zip_path.name,
        zip_sha256=zip_sha256, zip_bytes=int(zip_path.stat().st_size),
        path=str(out.relative_to(ROOT)), download=(f"docs/downloads/{out.name}" if safe_to_download else None),
        zip_download=(f"docs/downloads/{zip_path.name}" if safe_to_download else None),
        sha256=write_receipt["sha256"], decoded_pixels_sha256=decoded_sha,
        bytes=int(out.stat().st_size), emitted_pixels=int(emitted_mask.sum()),
        dtype="float32", bands=1, shape=list(prediction.shape), crs="EPSG:32611",
        transform=list(grid.TRANSFORM), values=[0.0, 1.0], nan_pixels=0,
        candidate_arm=deployed["arm"], candidate_arm_is_cotrain=bool(deployed["active"]),
        competition_unique_identifier=unique_id, submission_name=submission_name,
        submission_note=note, submission_note_chars=len(note), submission_name_chars=len(submission_name),
        safe_to_download_for_research=safe_to_download,
        approved_for_weekly_slot=approved,
        approved_to_submit=approved,
        status_for_user=("APPROVED FOR SUBMISSION after registered local gates" if approved else
                         "RESEARCH ONLY — NOT APPROVED TO SUBMIT"),
        slots_used=0, portal_upload_performed=False,
        registration_sha256=ctx["registration_sha256"], hypothesis_sha256=ctx["hypothesis_sha256"],
        prefit_lock_sha256=ctx["prefit_lock_sha256"], run_signature=feature_receipt["run_signature"],
        holdout_file="evidence/h57_holdout.json", holdout_sha256=digest(EVIDENCE / "h57_holdout.json"),
        holdout_summary=dict(primary=holdout["primary"], comparisons=holdout["comparisons"],
                             exchange=holdout["exchange"], slot_gate=holdout["slot_gate"]),
        deployment=dict(training=deployed["training"], model_signatures=deployed["model_signatures"],
                        thresholds=deployed.get("thresholds"), exchange=deployed.get("exchange"),
                        placement=placement, emitted_on_catalogue=int((emitted_mask & catalogue).sum()),
                        emitted_outside_valid=int((emitted_mask & ~valid).sum())),
        format_gate=format_report,
        uniqueness=dict(**uniqueness, canonical_decoded_pattern_unique=prior_unique,
                        not_literal_prior_union=prior_union_distinct,
                        support_novelty_fraction_is_diagnostic_only=True,
                        scope_roots=[str(p.relative_to(ROOT)) for p in roots]),
        same_run_AB_union=same_run_union_report,
        reasoning_json=reasoning_json, reasoning_csv=reasoning_csv,
        local_gates=local_gates,
        provenance=dict(input_sha256={k: v["sha256"] for k, v in ctx["inputs"].items()},
                        feature_manifest_sha256=feature_receipt["manifest_sha256"],
                        model_source_sha256=ctx["source_sha256"],
                        owner_mirror_not_organizer_authenticated=True),
        no_public_score_forecast=True,
        score_attribution_authenticated=False,
        caveats=[
            "Safe to download means local file integrity/grid/range passed; it does not mean the file is a good model or organizer-accepted.",
            "Owner-mirror hashes are not organizer authentication; auxiliary rasters are derivatives, not raw USGS downloads.",
            "Catalogue-zero validation proxies are not verified fault absence; connected components are raster proxies, not fault IDs.",
            "The 80-pixel holdout is catalogue recovery, not validation against organizer-hidden new faults.",
            "The public leaderboard is participant-level; no file-to-score attribution or score forecast is claimed.",
            "A local approval, if true, is not an upload or portal acceptance receipt.",
        ],
    )
    write_json(receipt_path, receipt)
    # Never redirect the competitive LATEST marker to a failed-gate artifact.
    if approved:
        (SUBMISSION / "LATEST.txt").write_text(out.name + "\n")
    write_run_integrity(ctx, "ARTIFACT_BUILT", feature_receipt,
                        dict(artifact_file=out.name, artifact_sha256=write_receipt["sha256"],
                             approved_for_weekly_slot=approved, holdout_sha256=digest(EVIDENCE / "h57_holdout.json")))
    log(f"H57 artifact {out.name}: format={format_report['ok']}, decoded_unique={prior_unique}, "
        f"slot_approved={approved}, slots_used=0")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("prepare", "holdout", "build", "all"), default="all")
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        ctx = preflight()
        if args.stage in ("prepare", "holdout", "all"):
            feature_receipt = build_feature_store(ctx)
            write_run_integrity(ctx, "FEATURES_READY", feature_receipt,
                                dict(eligible_pixels=feature_receipt["eligible_pixels"],
                                     stack_sha256=feature_receipt["stack_sha256"]))
        else:
            feature_receipt_path = WORK / "feature_store_receipt.json"
            if not feature_receipt_path.is_file():
                raise RuntimeError("H57 feature store is missing; run --stage prepare first")
            feature_receipt = json.loads(feature_receipt_path.read_text())
            if feature_receipt.get("source_signature") != ctx["source_signature"]:
                raise RuntimeError("H57 feature store source signature changed")
            if digest(STACK_PATH) != feature_receipt.get("stack_sha256"):
                raise RuntimeError("H57 stack hash differs from its feature-store receipt")
        if args.stage in ("holdout", "all"):
            holdout = run_holdout(ctx, feature_receipt)
        elif args.stage == "build":
            holdout_path = EVIDENCE / "h57_holdout.json"
            if not holdout_path.is_file():
                raise RuntimeError("candidate build is blocked until the registered spatial holdout completes")
            holdout = json.loads(holdout_path.read_text())
        else:
            holdout = None
        if args.stage in ("build", "all"):
            if holdout is None:
                raise RuntimeError("no completed holdout is available")
            build_artifact(ctx, feature_receipt, holdout)
    except Exception as error:
        log(f"STOP: {type(error).__name__}: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
