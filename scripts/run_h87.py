#!/usr/bin/env python3
"""H87: strictly separated-view directional-variogram co-training test.

The runner reuses the integrity-checked structural feature store plus the shared spatial folds,
metric evaluator, placement, GeoTIFF writer, uniqueness gate, and lane gate. The only added inputs
are label-free A-view variogram columns, registered into that same cached FeatureStore. The runner
refuses any moved pre-registration or changed input bytes.

The method fails closed: A/B pseudo-label exchange is attempted only if both views pass OOF
sufficiency, single-channel leakage canaries are clean, and the prescribed spatial-block negative
error correlations are defined, have >=20 blocks, and remain below |rho|=0.60. A failed gate is a
negative result, not a reason to retune.

Usage:
  .venv/bin/python scripts/run_h87.py all
  .venv/bin/python scripts/run_h87.py cache
  .venv/bin/python scripts/run_h87.py fit
  .venv/bin/python scripts/run_h87.py independence
  .venv/bin/python scripts/run_h87.py holdout
  .venv/bin/python scripts/run_h87.py write

No DrivenData upload slot is used. A generated TIFF is explicitly research-only unless every
pre-registered holdout and file gate passes; this session does not upload or select a slot.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                     # noqa: E402
import rasterio                                                        # noqa: E402
from scipy import ndimage as ndi                                       # noqa: E402
from scipy.stats import rankdata                                       # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier           # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h82 as h82                                                  # noqa: E402 (reuse its tested DVA kernel)
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

PREREG = ROOT / "registry/h87_preregistration.json"
HYPOTHESES = ROOT / "knowledge/80_h87_hypotheses_preregistered.md"
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
STORE_DIR = ROOT / "work/r2/features"
WORK = ROOT / "work/h87"
EVIDENCE = ROOT / "evidence"
DOC_DATA = ROOT / "docs/data"
DOWNLOADS = ROOT / "docs/downloads"
SEED = 87052
BUFFER_PX = 80
NEGATIVE_COLLAR_PX = 5
RING_PX = 2
CANARY_AUC = 0.90
SUFFICIENCY_AUC = 0.60
INDEPENDENCE_RHO = 0.60
BLOCK_PX = 50
MIN_NEGATIVES_PER_BLOCK = 32
MIN_BLOCKS = 20
DONOR_RANK = 0.95
RECEIVER_RANK = (0.35, 0.65)
PSEUDO_MIN_PIXELS = 5
PSEUDO_CAP = 2000
PSEUDO_BLOCK_PX = 50
K_FOLD = 9400
K_TOTAL = 37654
MIN_SPACING_PX = 3.0
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_BLOCK_PX = 200
DVA_LAGS = (1, 2, 3, 4, 6)
DVA_BANDS = ((2, "rtp"), (13, "iso_grav_anom"), (15, "depth_to_base_surf"),
             (17, "conductivity_surface"), (7, "geodetic_shear"), (16, "earthquake_intensity"))
DVA_DIRECTIONS = tuple(tuple(map(int, z)) for z in h82.FAN)
DVA_SIGMA = float(h82.SIGMA)
PRIMARY_NAME = "a_only"
SUBMISSION_NOTE = (
    "H87 geophysical DVA vs surface/radiometric abstention; 3px spaced; research only; no slot used"
)


def log(*args, **kwargs):
    # Structural builder's shared callback includes flush=True; it is already flushed here.
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *args, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False, default=float) + "\n")


def publish_receipt(name: str, data: dict) -> None:
    write_json(EVIDENCE / f"h87_{name}.json", data)
    write_json(DOC_DATA / f"h87_{name}.json", data)


def verify_prereg() -> dict:
    reg = json.loads(PREREG.read_text())
    if sha256(HYPOTHESES) != reg["hypothesis_sha256"]:
        raise SystemExit("H87 frozen hypothesis hash differs from registry; stop before any fit")
    if HYPOTHESES.stat().st_size != reg["hypothesis_bytes"]:
        raise SystemExit("H87 frozen hypothesis byte count differs from registry")
    if reg.get("frozen_before_any_fit") is not True:
        raise SystemExit("H87 registry does not certify pre-fit registration")
    return reg


def verify_inputs() -> dict:
    manifest = json.loads((ROOT / "registry/data_manifest.json").read_text())
    pins = {f["id"]: f for f in manifest["files"]}
    receipt = {}
    for key, path in (("training_features", FEATURES), ("labels", LABELS),
                      ("sample_submission", SAMPLE)):
        if not path.exists():
            raise SystemExit(f"missing {path}; restore hash-pinned inputs with scripts/restore_data.py")
        pin = pins[key]
        n, digest = path.stat().st_size, sha256(path)
        good = n == pin["bytes"] and digest == pin["sha256"]
        receipt[key] = dict(path=str(path.relative_to(ROOT)), bytes=n, sha256=digest,
                            expected_bytes=pin["bytes"], expected_sha256=pin["sha256"],
                            matches_integrity_pin=good,
                            provenance="owner-mirrored bytes; integrity-pinned, not organizer-authenticated")
        if not good:
            raise SystemExit(f"input integrity pin failed for {key}; refusing to continue")
    return receipt


def expected_dva_names() -> list[str]:
    return [f"H87_DVA_{name}_{kind}_l{lag}"
            for _band, name in DVA_BANDS for lag in DVA_LAGS for kind in ("aniso", "logvar")]


def register_dva_column(store_dir: Path, name: str, values: np.ndarray,
                        flat_idx: np.ndarray) -> tuple[str, bool]:
    """Write a compact, verified feature column into the shared structural FeatureStore."""
    dest = store_dir / f"{name}.npy"
    column = np.asarray(values, dtype=np.float32).ravel()
    if column.size != flat_idx.size or not np.isfinite(column).all():
        raise ValueError(f"bad H87 column shape or non-finite values: {name}")
    manifest_path = store_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    hashes = manifest.setdefault("feature_sha256", {})
    names = manifest.setdefault("feature_names", [])
    if dest.exists() and name in hashes and structural.digest(dest) == hashes[name]:
        # Re-use only if the actual values are the registered column as well.
        saved = np.load(dest, mmap_mode="r", allow_pickle=False)
        if saved.shape == column.shape and np.array_equal(saved, column):
            return hashes[name], False
    structural.save_array(dest, column)
    digest = structural.digest(dest)
    hashes[name] = digest
    if name not in names:
        names.append(name)
    manifest["feature_sha256"] = hashes
    manifest["feature_names"] = names
    write_json(manifest_path, manifest)
    return digest, True


def build_dva_cache(reg: dict) -> dict:
    """Build/reuse the shared stack, then register H87's A-only DVA columns once."""
    expected = expected_dva_names()
    t0 = time.time()
    if not (STORE_DIR / "manifest.json").exists():
        log("building the missing shared structural feature cache once (no labels enter this stage)")
        structural.build(features=str(FEATURES), sample=str(SAMPLE), dest=str(STORE_DIR),
                         log=log, include_optional_profiles=False)
    manifest_path = STORE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    input_pins = reg["views"]
    feature_sha = json.loads((ROOT / "registry/data_manifest.json").read_text())
    wanted_sha = {x["id"]: x["sha256"] for x in feature_sha["files"]}
    if manifest.get("inputs", {}).get("features_sha256") != wanted_sha["training_features"]:
        raise SystemExit("stale structural cache: training_features SHA does not match registered mirror")
    if manifest.get("inputs", {}).get("sample_sha256") != wanted_sha["sample_submission"]:
        raise SystemExit("stale structural cache: sample_submission SHA does not match registered mirror")
    base_b = list(manifest.get("view_B", []))
    if not base_b:
        raise SystemExit("shared structural cache has no base view_B features")
    if set(base_b) & set(expected):
        raise SystemExit("H87 feature names overlap the base surface view")
    valid = np.load(STORE_DIR / "valid.npy", allow_pickle=False)
    flat_idx = np.load(STORE_DIR / "flat_idx.npy", allow_pickle=False)
    if not np.array_equal(flat_idx, np.flatnonzero(valid.ravel())):
        raise SystemExit("shared feature-store index mapping is invalid")
    hashes = dict(manifest.get("feature_sha256", {}))
    complete = all((STORE_DIR / f"{n}.npy").exists() and n in hashes
                   and structural.digest(STORE_DIR / f"{n}.npy") == hashes[n] for n in expected)
    added = []
    if not (complete and manifest.get("h87_view_A")):
        log(f"building {len(expected)} label-free H87 directional-variogram A columns")
        with rasterio.open(FEATURES) as src:
            if src.count != 19 or src.shape != valid.shape:
                raise SystemExit("training feature raster does not match the shared feature cache")
            for band, tag in DVA_BANDS:
                raw = src.read(band).astype(np.float64)
                ok = valid & np.isfinite(raw) & (raw > -1e38)
                if not ok.any() or not np.isfinite(raw[ok]).all():
                    raise SystemExit(f"band {band} has no finite eligible values")
                mu = float(raw[ok].mean(dtype=np.float64))
                sd = float(raw[ok].std(dtype=np.float64))
                if not np.isfinite(sd) or sd <= 0:
                    raise SystemExit(f"band {band} has constant/non-finite eligible values")
                z = np.where(ok, (raw - mu) / sd, 0.0)
                weights = ndi.gaussian_filter(ok.astype(np.float64), DVA_SIGMA) + 1e-9
                del raw
                log(f"band {band} ({tag}): standardized label-free on {int(ok.sum()):,} cached pixels")
                for lag in DVA_LAGS:
                    mx, mn, mean = h82._gamma_stats(z, ok, weights, lag, DVA_DIRECTIONS, None)
                    anisotropy = (mx - mn) / (mx + mn + 1e-9)
                    log_variance = np.log10(mean + 1e-9)
                    for kind, grid in (("aniso", anisotropy), ("logvar", log_variance)):
                        name = f"H87_DVA_{tag}_{kind}_l{lag}"
                        compact = np.asarray(grid, np.float32).ravel()[flat_idx]
                        digest, was_added = register_dva_column(STORE_DIR, name, compact, flat_idx)
                        if was_added:
                            added.append(name)
                        hashes[name] = digest
                        del compact, grid
                    del mx, mn, mean, anisotropy, log_variance
                del z, ok, weights
        # A single manifest update records the disjoint views and provenance of the extension.
        manifest = json.loads(manifest_path.read_text())
        hashes = dict(manifest.get("feature_sha256", {}))
        manifest["version"] = manifest.get("version", "structural-core")
        if "+h87-dva-a-v1" not in manifest["version"]:
            manifest["version"] += "+h87-dva-a-v1"
        manifest["h87_view_A"] = expected
        manifest["h87_view_B"] = base_b
        manifest["feature_names"] = list(dict.fromkeys(manifest.get("feature_names", []) + expected))
        manifest["feature_sha256"] = hashes
        manifest["h87_dva"] = dict(
            bands=[dict(band=b, tag=t) for b, t in DVA_BANDS], directions=[list(d) for d in DVA_DIRECTIONS],
            lags_px=list(DVA_LAGS), smoothing_sigma_px=DVA_SIGMA,
            formula_anisotropy="(max directional semivariance - min)/(max + min + 1e-9)",
            formula_logvar="log10(mean directional semivariance + 1e-9)",
            standardization="mean/std over label-free cached eligible footprint per band",
            source_kernel="run_h82._gamma_stats, reused without copying; eight-direction H82 implementation",
            view_A_raw_bands_used=False,
            view_B_raw_bands=[6, 12, 19],
            band6_identity="provisional byte-based radiometric total-count identity; source-tag discrepancy remains open",
            support_px=int(manifest.get("support_px", structural.SUPPORT_PX)),
            external_data_used=False,
        )
        if set(manifest["h87_view_A"]) & set(manifest["h87_view_B"]):
            raise SystemExit("H87 view feature sets overlap")
        write_json(manifest_path, manifest)
    # Validate every extension column from disk before any fit.
    manifest = json.loads(manifest_path.read_text())
    for name in expected:
        path = STORE_DIR / f"{name}.npy"
        if name not in manifest.get("feature_sha256", {}) or structural.digest(path) != manifest["feature_sha256"][name]:
            raise SystemExit(f"H87 cached feature failed SHA re-read: {name}")
        a = np.load(path, mmap_mode="r", allow_pickle=False)
        if a.shape != flat_idx.shape or not np.isfinite(a).all():
            raise SystemExit(f"H87 cached feature failed shape/finite re-read: {name}")
    out = dict(stage="cache", generated_utc=now(), shared_feature_store=str(STORE_DIR.relative_to(ROOT)),
               base_feature_version=manifest.get("version"), eligible_pixels=int(valid.sum()),
               view_A_features=expected, view_B_features=base_b, newly_written_columns=added,
               n_A=len(expected), n_B=len(base_b), view_overlap=sorted(set(expected) & set(base_b)),
               input_sha256=manifest.get("inputs"), feature_sha256={n: manifest["feature_sha256"][n] for n in expected},
               integrity_verified=True, external_data_used=False,
               implementation_note="reused H82 _gamma_stats and shared structural FeatureStore; no evaluator/writer fork",
               elapsed_seconds=round(time.time() - t0, 1))
    publish_receipt("cache", out)
    return out


def setup() -> tuple[dict, structural.FeatureStore, np.ndarray, np.ndarray, list[dict], list[str], list[str], dict]:
    reg = verify_prereg()
    inputs = verify_inputs()
    build = build_dva_cache(reg)
    store = structural.FeatureStore(STORE_DIR)
    names_a = list(store.manifest.get("h87_view_A", []))
    names_b = list(store.manifest.get("h87_view_B", []))
    if not names_a or not names_b or set(names_a) & set(names_b):
        raise SystemExit("H87 strict view split missing or overlapping")
    if any(n.startswith("raw_band_") for n in names_a):
        raise SystemExit("raw band leaked into H87 view A")
    if not all(n.startswith("H87_DVA_") for n in names_a):
        raise SystemExit("unregistered feature entered H87 view A")
    with rasterio.open(LABELS) as ds, rasterio.open(SAMPLE) as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("label grid differs from sample submission")
        labels = ds.read(1)
        sample_values = ref.read(1)
        sample_domain = np.isfinite(sample_values) & (sample_values > -1e38)
        sample_meta = dict(shape=list(ref.shape), crs=str(ref.crs), epsg=ref.crs.to_epsg(),
                           transform=list(ref.transform)[:6], resolution=list(ref.res))
    cat = labels == 1
    labelled_zero = labels == 0
    eligible = store.valid & sample_domain & (labels >= 0)
    if cat.shape != eligible.shape or not cat.any():
        raise SystemExit("label mask or eligible footprint is empty/misaligned")
    folds = list(spatial.folds(cat, eligible, buffer_px=BUFFER_PX))
    held = sum(int((f["truth"] & f["region"]).sum()) for f in folds)
    if held <= 0 or any(f["receipt"]["shared_train_truth_components"] != 0 for f in folds):
        raise SystemExit("invalid whole-segment holdout geometry")
    ctx = dict(inputs=inputs, cache=build, sample_meta=sample_meta,
               sample_domain=sample_domain, labelled_zero=labelled_zero,
               withheld_positive_pixels=held, eligible_pixels=int(eligible.sum()),
               catalogue_pixels=int(cat.sum()),
               splitter="gems52.spatial.folds / label-blind-quadrants-v2",
               buffer_px=BUFFER_PX,
               label_note="integrity-pinned catalogue labels; a catalogue-zero proxy is not verified fault absence")
    log(f"setup: eligible {int(eligible.sum()):,}; catalogue {int(cat.sum()):,}; withheld {held:,}; A={len(names_a)} B={len(names_b)}")
    return reg, store, cat, eligible, folds, names_a, names_b, ctx


def sample_train(fold: dict, cat: np.ndarray, labelled_zero: np.ndarray,
                 rng: np.random.Generator, max_pos: int = 20000,
                 max_neg: int = 60000) -> tuple[np.ndarray, np.ndarray]:
    pos = np.flatnonzero((fold["train"] & fold["visible"]).ravel())
    visible_distance = ndi.distance_transform_edt(~fold["visible"])
    neg = np.flatnonzero((fold["train"] & labelled_zero &
                          (visible_distance > NEGATIVE_COLLAR_PX)).ravel())
    del visible_distance
    if len(pos) < 100 or len(neg) < 100:
        raise SystemExit("insufficient fold-local training positives or negatives")
    pos = rng.choice(pos, min(max_pos, len(pos)), replace=False)
    neg = rng.choice(neg, min(max_neg, len(neg)), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    return rows[order], y[order]


def canary_sample(fold: dict, labelled_zero: np.ndarray,
                  rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    pos = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
    visible_distance = ndi.distance_transform_edt(~fold["visible"])
    neg = np.flatnonzero((fold["region"] & labelled_zero &
                          (visible_distance > NEGATIVE_COLLAR_PX)).ravel())
    del visible_distance
    if len(pos) < 20 or len(neg) < 20:
        raise SystemExit(f"fold {fold['fold']} cannot supply a valid leakage-canary sample")
    pos = rng.choice(pos, min(20000, len(pos)), replace=False)
    neg = rng.choice(neg, min(40000, len(neg)), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    return rows, y


def learner(seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, max_leaf_nodes=15,
        min_samples_leaf=40, l2_regularization=1.0, early_stopping=False, random_state=seed)


def predict_flat(store: structural.FeatureStore, model, names: list[str], rows: np.ndarray,
                 chunk: int = 200000) -> np.ndarray:
    out = np.empty(len(rows), dtype=np.float32)
    for i in range(0, len(rows), chunk):
        sel = rows[i:i + chunk]
        X = store.gather(sel, names)
        out[i:i + chunk] = model.predict_proba(X)[:, 1].astype(np.float32)
    return out


def to_grid(flat_idx: np.ndarray, values: np.ndarray, shape: tuple[int, int], fill=np.nan) -> np.ndarray:
    grid = np.full(int(np.prod(shape)), fill, dtype=np.float32)
    grid[flat_idx] = np.asarray(values, dtype=np.float32)
    return grid.reshape(shape)


def rank_on_mask(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        raise ValueError("cannot rank an empty mask")
    out = np.zeros(values.shape, dtype=np.float32)
    v = np.asarray(values[mask], dtype=np.float64)
    if not np.isfinite(v).all():
        raise ValueError("rank values must be finite on the permitted mask")
    out[mask] = ((rankdata(v, method="average") - 0.5) / max(len(v), 1)).astype(np.float32)
    return out


def save_prediction(path: Path, values: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    structural.save_array(path, np.asarray(values, np.float32))
    return structural.digest(path)


def stage_canary() -> tuple[dict, dict]:
    reg, store, cat, eligible, folds, names_a, names_b, ctx = setup()
    all_names = names_a + names_b
    out = dict(stage="canary", evidence_class="HOLDOUT-DTI diagnostic AUC (not a DTI score)",
               alarm_direction_insensitive_auc=CANARY_AUC, input_provenance=ctx["inputs"], folds=[])
    alarms = []
    for fold in folds:
        f = int(fold["fold"])
        rows, y = canary_sample(fold, ctx["labelled_zero"],
                                np.random.default_rng(SEED + 1000 + f))
        per_feature = {}
        for name in all_names:
            x = store.gather(rows, [name])[:, 0]
            auc = float(roc_auc_score(y, x))
            direction_insensitive = max(auc, 1.0 - auc)
            rec = dict(raw_auc=auc, direction_insensitive_auc=direction_insensitive,
                       view="A" if name in names_a else "B")
            per_feature[name] = rec
            if direction_insensitive > CANARY_AUC:
                alarms.append(dict(fold=f, feature=name, **rec))
        fold_out = dict(fold=f, sample_rows=len(rows), positive_sample=int(y.sum()),
                        negative_sample=int((y == 0).sum()), per_feature=per_feature,
                        max_direction_insensitive_auc=max(v["direction_insensitive_auc"] for v in per_feature.values()))
        out["folds"].append(fold_out)
        log(f"canary fold {f}: max single-feature AUC={fold_out['max_direction_insensitive_auc']:.4f}")
    out["alarms"] = alarms
    out["alarm"] = bool(alarms)
    out["verdict"] = "STOP: AUC > 0.90 is leakage until proven otherwise" if alarms else "PASS: no single feature exceeded 0.90"
    out["maximum_auc"] = max(x["max_direction_insensitive_auc"] for x in out["folds"])
    out["evaluator_version_for_fold_sampling"] = evaluator.VERSION
    publish_receipt("canary", out)
    if out["alarm"]:
        raise SystemExit("H87 canary alarm; no model fit was run")
    return out, dict(reg=reg, store=store, cat=cat, eligible=eligible,
                     labelled_zero=ctx["labelled_zero"], folds=folds,
                     names_a=names_a, names_b=names_b, ctx=ctx)


def stage_fit(context: dict | None = None) -> tuple[dict, dict]:
    if context is None:
        canary, context = stage_canary()
    else:
        canary = json.loads((EVIDENCE / "h87_canary.json").read_text())
        if canary.get("alarm"):
            raise SystemExit("stored H87 canary alarm; refusing to fit")
    store, cat, eligible, folds = (context[k] for k in ("store", "cat", "eligible", "folds"))
    names_a, names_b = context["names_a"], context["names_b"]
    flat_idx = store.flat_idx
    out = dict(stage="fit", evidence_class="HOLDOUT-DTI diagnostic AUC (not a DTI score)",
        started_utc=now(), evaluator_version=evaluator.VERSION, fold_geometry=[f["receipt"] for f in folds],
        canary_max_auc=canary["maximum_auc"], training_sample=dict(max_positive=20000, max_negative=60000,
            negative_collar_px=NEGATIVE_COLLAR_PX), folds=[])
    for fold in folds:
        f = int(fold["fold"])
        rows, y = sample_train(fold, cat, context["labelled_zero"], np.random.default_rng(SEED + f))
        train_info = dict(rows=len(rows), positive=int(y.sum()), negative=int((y == 0).sum()))
        fold_rec = dict(fold=f, training=train_info, views={})
        for view, names in (("A", names_a), ("B", names_b)):
            t_fit = time.time()
            X = store.gather(rows, names)
            model = learner(SEED + f)
            model.fit(X, y)
            in_auc = float(roc_auc_score(y, model.predict_proba(X)[:, 1]))
            del X
            prediction = predict_flat(store, model, names, flat_idx)
            # Predictions for the held-out region only determine sufficiency; the full vector is
            # retained so a permitted exchange can select pseudo segments wholly inside fold['train'].
            grid = to_grid(flat_idx, prediction, eligible.shape)
            canary_rows, canary_y = canary_sample(fold, context["labelled_zero"],
                np.random.default_rng(SEED + 1000 + f))
            oof_auc = float(roc_auc_score(canary_y, grid.ravel()[canary_rows]))
            pred_path = WORK / f"pred_pre_{view}_f{f}.npy"
            pred_hash = save_prediction(pred_path, prediction)
            fold_rec["views"][view] = dict(train_seconds=round(time.time() - t_fit, 1),
                in_sample_auc=in_auc, region_oof_auc=oof_auc, prediction_file=str(pred_path.relative_to(ROOT)),
                prediction_sha256=pred_hash, n_region_positive=int(canary_y.sum()),
                n_region_negative=int((canary_y == 0).sum()), features=len(names))
            del grid, model, prediction
            log(f"fit fold {f} view {view}: OOF diagnostic AUC={oof_auc:.4f}; n={len(names)} features")
        out["folds"].append(fold_rec)
        del rows, y
    auc_a = [r["views"]["A"]["region_oof_auc"] for r in out["folds"]]
    auc_b = [r["views"]["B"]["region_oof_auc"] for r in out["folds"]]
    out["sufficiency"] = dict(evidence_class="HOLDOUT-DTI diagnostic AUC (not a DTI score)",
        threshold=SUFFICIENCY_AUC, view_A_mean=float(np.mean(auc_a)), view_A_per_fold=auc_a,
        view_B_mean=float(np.mean(auc_b)), view_B_per_fold=auc_b,
        view_A_pass=bool(np.mean(auc_a) >= SUFFICIENCY_AUC),
        view_B_pass=bool(np.mean(auc_b) >= SUFFICIENCY_AUC),
        both_pass=bool(np.mean(auc_a) >= SUFFICIENCY_AUC and np.mean(auc_b) >= SUFFICIENCY_AUC),
        interpretation="diagnostic screening rule, not a DTI score and not proof of theoretical sufficiency")
    out["evaluator_hashes"] = evaluator.implementation_hashes()
    out["finished_utc"] = now()
    publish_receipt("fit", out)
    context["fit_receipt"] = out
    return out, context


def stage_independence(context: dict | None = None) -> tuple[dict, dict]:
    if context is None:
        fit = json.loads((EVIDENCE / "h87_fit.json").read_text())
        _, context = stage_canary()
        context["fit_receipt"] = fit
    fit = context.get("fit_receipt") or json.loads((EVIDENCE / "h87_fit.json").read_text())
    store, cat, eligible, folds = (context[k] for k in ("store", "cat", "eligible", "folds"))
    rows, per_fold = [], []
    for fold in folds:
        f = int(fold["fold"])
        pa_flat = np.load(WORK / f"pred_pre_A_f{f}.npy", mmap_mode="r", allow_pickle=False)
        pb_flat = np.load(WORK / f"pred_pre_B_f{f}.npy", mmap_mode="r", allow_pickle=False)
        pa = to_grid(store.flat_idx, pa_flat, eligible.shape)
        pb = to_grid(store.flat_idx, pb_flat, eligible.shape)
        visible_distance = ndi.distance_transform_edt(~fold["visible"])
        negative = (fold["region"] & context["labelled_zero"] &
                    (visible_distance > NEGATIVE_COLLAR_PX) & np.isfinite(pa) & np.isfinite(pb))
        del visible_distance
        qa, qb = pa[negative], pb[negative]
        thresholds = (float(np.quantile(qa, DONOR_RANK)), float(np.quantile(qb, DONOR_RANK)))
        blocks = spatial.negative_block_errors(pa, pb, negative, f, thresholds,
            side=BLOCK_PX, minimum=MIN_NEGATIVES_PER_BLOCK)
        rows.extend(blocks)
        per_fold.append(dict(fold=f, negative_proxy_pixels=int(negative.sum()),
            block_count=len(blocks), thresholds=list(thresholds),
            negative_class="held-out catalogue-zero proxies, not verified absence"))
        log(f"independence fold {f}: {len(blocks)} blocks from {int(negative.sum()):,} proxy negatives")
        del pa, pb
    indep = spatial.independence(rows, threshold=INDEPENDENCE_RHO, min_blocks=MIN_BLOCKS)
    suff = fit["sufficiency"]
    exchange_allowed = bool(indep["allow_exchange"] and suff["both_pass"])
    out = dict(stage="independence", started_utc=now(), evaluator_version=evaluator.VERSION,
        per_fold=per_fold, block_side_px=BLOCK_PX, minimum_negatives_per_block=MIN_NEGATIVES_PER_BLOCK,
        independent_error_test=indep, sufficiency= suff,
        exchange_allowed=exchange_allowed,
        exchange_gate_reason=("both views pass the frozen sufficiency threshold and independence is measured below threshold"
            if exchange_allowed else "exchange disabled: " + "; ".join(x for x, bad in (
                ("independence undefined/strong/too few blocks", not indep["allow_exchange"]),
                ("one or both views fail the sufficiency screen", not suff["both_pass"])) if bad)),
        negative_class="held-out catalogue-zero proxy, not verified fault absence",
        interpretation="OOF error correlation is a diagnostic; weak correlation does not establish conditional independence")
    publish_receipt("independence", out)
    context["independence_receipt"] = out
    return out, context


def rank_grid_on_train(pred_grid: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    out = np.full(pred_grid.shape, np.nan, dtype=np.float32)
    vals = np.asarray(pred_grid[train_mask], np.float64)
    if len(vals) == 0 or not np.isfinite(vals).all():
        raise ValueError("no finite training-domain predictions for pseudo-label ranking")
    out[train_mask] = ((rankdata(vals, method="average") - 0.5) / len(vals)).astype(np.float32)
    return out


def stage_exchange(context: dict | None = None) -> tuple[dict, dict]:
    if context is None:
        _, context = stage_canary()
    indep = context.get("independence_receipt") or json.loads((EVIDENCE / "h87_independence.json").read_text())
    if not indep.get("exchange_allowed"):
        out = dict(stage="exchange", started_utc=now(), ran=False,
                   reason=indep["exchange_gate_reason"], pseudo_pixels=0, folds=[],
                   interpretation="fail-closed; no pseudo-labels were created")
        publish_receipt("exchange", out)
        context["exchange_receipt"] = out
        return out, context
    store, cat, eligible, folds = (context[k] for k in ("store", "cat", "eligible", "folds"))
    names_a, names_b = context["names_a"], context["names_b"]
    out = dict(stage="exchange", started_utc=now(), ran=True, round_count=1,
        donor_rank_min=DONOR_RANK, receiver_rank_interval=list(RECEIVER_RANK),
        block_side_px=PSEUDO_BLOCK_PX, min_segment_pixels=PSEUDO_MIN_PIXELS,
        per_direction_cap_per_fold=PSEUDO_CAP, folds=[], total_pseudo_pixels=0,
        no_evaluation_or_buffer_overlap=True)
    post_by_fold = {}
    for fold in folds:
        f = int(fold["fold"])
        rows, y = sample_train(fold, cat, context["labelled_zero"], np.random.default_rng(SEED + f))
        used = np.zeros(eligible.shape, dtype=bool)
        used.ravel()[rows] = True
        pa_flat = np.load(WORK / f"pred_pre_A_f{f}.npy", mmap_mode="r", allow_pickle=False)
        pb_flat = np.load(WORK / f"pred_pre_B_f{f}.npy", mmap_mode="r", allow_pickle=False)
        pa = to_grid(store.flat_idx, pa_flat, eligible.shape)
        pb = to_grid(store.flat_idx, pb_flat, eligible.shape)
        rank_a = rank_grid_on_train(pa, fold["train"])
        rank_b = rank_grid_on_train(pb, fold["train"])
        visible_distance = ndi.distance_transform_edt(~fold["visible"])
        forbidden = (fold["region"] | fold["held_all"] | (visible_distance <= 4) | used)
        del visible_distance
        exchange = {}
        # donor A -> receiver B and donor B -> receiver A. These are the only admitted pseudo-label cells.
        for donor, receiver, donor_grid, receiver_grid in (
                ("A", "B", rank_a, rank_b), ("B", "A", rank_b, rank_a)):
            idx, segments = spatial.whole_pseudo_segments(donor_grid, receiver_grid,
                fold["train"], forbidden, DONOR_RANK, RECEIVER_RANK[0], RECEIVER_RANK[1],
                side=PSEUDO_BLOCK_PX, min_pixels=PSEUDO_MIN_PIXELS, cap=PSEUDO_CAP)
            if np.intersect1d(idx, rows).size or len(idx) > PSEUDO_CAP:
                raise AssertionError("pseudo labels overlap sampled labels or exceed their cap")
            exchange[f"{donor}_to_{receiver}"] = dict(pixel_count=int(len(idx)), segment_count=len(segments),
                segments=segments, flat_indices=idx.tolist())
        rec = dict(fold=f, directions=exchange)
        post = {}
        for view, names, pseudo_key in (("A", names_a, "B_to_A"), ("B", names_b, "A_to_B")):
            pseudo = np.asarray(exchange[pseudo_key]["flat_indices"], dtype=np.int64)
            if len(pseudo):
                x_train = store.gather(rows, names)
                x_pseudo = store.gather(pseudo, names)
                y_full = np.r_[y, np.ones(len(pseudo), np.int8)]
                X = np.concatenate((x_train, x_pseudo), axis=0)
            else:
                X = store.gather(rows, names)
                y_full = y
            model = learner(SEED + 100 + f)
            model.fit(X, y_full)
            pred = predict_flat(store, model, names, store.flat_idx)
            post[view] = pred
            rec.setdefault("post_fit", {})[view] = dict(training_rows=int(len(y_full)),
                pseudo_positive_pixels=int(len(pseudo)), pseudo_segments=exchange[pseudo_key]["segment_count"])
        out["total_pseudo_pixels"] += sum(x["pixel_count"] for x in exchange.values())
        out["folds"].append(rec)
        post_by_fold[f] = post
        del pa, pb, rank_a, rank_b, rows, y
        log(f"exchange fold {f}: A->B {exchange['A_to_B']['pixel_count']} px; B->A {exchange['B_to_A']['pixel_count']} px")
    for f, post in post_by_fold.items():
        for view, pred in post.items():
            save_prediction(WORK / f"pred_post_{view}_f{f}.npy", pred)
    publish_receipt("exchange", out)
    context["exchange_receipt"] = out
    return out, context


def allowed_fold(fold: dict, valid: np.ndarray) -> np.ndarray:
    visible_distance = ndi.distance_transform_edt(~fold["visible"])
    allowed = fold["region"] & valid & ~fold["visible"] & (visible_distance > RING_PX)
    return allowed


def make_emissions(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                   fold: int) -> tuple[dict[str, np.ndarray], dict]:
    rank_a = rank_on_mask(pa, allowed)
    rank_b = rank_on_mask(pb, allowed)
    a_only = allowed & (rank_a >= DONOR_RANK) & (rank_b >= RECEIVER_RANK[0]) & (rank_b <= RECEIVER_RANK[1])
    b_only = allowed & (rank_b >= DONOR_RANK) & (rank_a >= RECEIVER_RANK[0]) & (rank_a <= RECEIVER_RANK[1])
    score_a_only = np.where(a_only, rank_a * (1.0 - rank_b), 0.0).astype(np.float32)
    score_a = np.where(allowed, rank_a, 0.0).astype(np.float32)
    score_b = np.where(allowed, rank_b, 0.0).astype(np.float32)
    score_union = np.where(allowed, np.maximum(rank_a, rank_b), 0.0).astype(np.float32)
    rng = np.random.default_rng(SEED + 5000 + fold)
    score_random = np.zeros(allowed.shape, dtype=np.float32)
    score_random[allowed] = rng.random(int(allowed.sum()), dtype=np.float32)
    arms = {
        "a_only": (score_a_only, a_only),
        "single_A": (score_a, allowed),
        "single_B": (score_b, allowed),
        "union_max": (score_union, allowed),
        "random": (score_random, allowed),
    }
    meta = dict(allowed_pixels=int(allowed.sum()), a_only_pool=int(a_only.sum()),
        b_only_pool=int(b_only.sum()), concordant=int((allowed & (rank_a >= DONOR_RANK) & (rank_b >= DONOR_RANK)).sum()),
        abstain=int((allowed & (rank_a < DONOR_RANK) & (rank_b < DONOR_RANK)).sum()),
        confidence=dict(donor_rank_min=DONOR_RANK, receiver_interval=list(RECEIVER_RANK)))
    return {k: nodes.spacing_select(score, mask, K_FOLD, min_px=MIN_SPACING_PX).astype(np.float32)
            for k, (score, mask) in arms.items()}, meta


def stage_holdout(context: dict | None = None) -> tuple[dict, dict]:
    if context is None:
        _, context = stage_canary()
    fit = context.get("fit_receipt") or json.loads((EVIDENCE / "h87_fit.json").read_text())
    independence_receipt = context.get("independence_receipt") or json.loads((EVIDENCE / "h87_independence.json").read_text())
    exchange_receipt = context.get("exchange_receipt")
    if exchange_receipt is None:
        p = EVIDENCE / "h87_exchange.json"
        exchange_receipt = json.loads(p.read_text()) if p.exists() else {"ran": False}
    store, cat, eligible, folds = (context[k] for k in ("store", "cat", "eligible", "folds"))
    use_post = bool(exchange_receipt.get("ran"))
    arm_terms: dict[str, np.ndarray] = {}
    per_fold = []
    primary = "a_only"
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_fold(fold, eligible)
        rec = dict(fold=f, withheld_positive_pixels=int((fold["truth"] & fold["region"]).sum()),
                   arms={}, strata_by_prediction={}, all_arms_filled=True)
        # Always compare the pre-exchange model. If (and only if) both frozen gates opened,
        # additionally compare the one-round exchanged model as the primary against the same-fold
        # pre-exchange and single-view controls.
        prediction_sets = ["pre", "post"] if use_post else ["pre"]
        for suffix in prediction_sets:
            pa_flat = np.load(WORK / f"pred_{suffix}_A_f{f}.npy", mmap_mode="r", allow_pickle=False)
            pb_flat = np.load(WORK / f"pred_{suffix}_B_f{f}.npy", mmap_mode="r", allow_pickle=False)
            pa = to_grid(store.flat_idx, pa_flat, eligible.shape)
            pb = to_grid(store.flat_idx, pb_flat, eligible.shape)
            emissions, strata = make_emissions(pa, pb, allowed, f)
            rec["strata_by_prediction"][suffix] = strata
            for arm, emission in emissions.items():
                if suffix == "post" and arm == "random":
                    # Same seeded random baseline is already recorded for pre; no duplicate arm.
                    continue
                key = (arm if not use_post and suffix == "pre" else
                       "a_only" if suffix == "post" and arm == "a_only" else
                       f"{arm}_{suffix}")
                if int(emission.sum()) != K_FOLD:
                    rec["all_arms_filled"] = False
                result, terms = evaluator.evaluate(emission, fold, eligible,
                    block_side=BOOTSTRAP_BLOCK_PX)
                if key not in arm_terms:
                    arm_terms[key] = terms.copy()
                else:
                    arm_terms[key] += terms
                rec["arms"][key] = dict(evidence_class="HOLDOUT-DTI",
                    evaluator_version=evaluator.VERSION, dti=float(result["dti"]), ci95=None,
                    placed=int(emission.sum()), target_budget=K_FOLD,
                    budget_filled=int(emission.sum()) == K_FOLD,
                    withheld_positive_pixels=int(result["n_truth"]), tpw=float(result["tpw"]),
                    fpw=float(result["fpw"]), fnw=float(result["fnw"]))
            del pa, pb
        per_fold.append(rec)
        log(f"holdout fold {f}: A-only primary placed {rec['arms']['a_only']['placed']}/{K_FOLD}; "
            f"single_B control HOLDOUT-DTI {rec['arms'].get('single_B_pre', rec['arms'].get('single_B'))['dti']:.5f}")
    summary = evaluator.pooled_summary(arm_terms, draws=BOOTSTRAP_DRAWS,
                                       seed=SEED + 6, candidate=primary)
    all_arms_filled = all(x["all_arms_filled"] for x in per_fold)
    summary["best_control_by_point_estimate"] = summary.get("best_comparable_control")
    summary["budget_comparable"] = all_arms_filled
    summary["paired_differences_valid_for_fixed_budget_gate"] = all_arms_filled
    if not all_arms_filled:
        summary["best_comparable_control"] = None
        summary["invalid_comparison_reason"] = (
            "At least one arm failed to fill the preregistered 9,400-per-fold budget after spacing; "
            "DTI and bootstrap outputs are descriptive for their actual emissions, not a valid matched-budget ranking.")
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    out = dict(round="H87", stage="holdout", evidence_class="HOLDOUT-DTI",
        evaluator_version=evaluator.VERSION, alpha=0.2, beta=0.8, triangular_radius_m=300.0,
        folds=4, buffer_px=BUFFER_PX, budget_per_fold=K_FOLD,
        withheld_positive_pixels=withheld, eligible_pixels=int(eligible.sum()),
        output_arm=primary, predictions="post-exchange" if use_post else "pre-exchange; exchange gate closed",
        independence=independence_receipt["independent_error_test"],
        sufficiency=fit["sufficiency"], exchange=exchange_receipt,
        pooled=summary, per_fold=per_fold,
        all_arms_filled=all(x["all_arms_filled"] for x in per_fold),
        interpretation="Holdout-DTI is conditional on this catalogue, these folds and fixed budget; it is not an organizer score or leaderboard projection.",
        evaluator_hashes=evaluator.implementation_hashes(), generated_utc=now())
    publish_receipt("holdout", out)
    context["holdout_receipt"] = out
    return out, context


def full_fit_and_predict(store: structural.FeatureStore, cat: np.ndarray, labelled_zero: np.ndarray,
                         eligible: np.ndarray, names_a: list[str], names_b: list[str],
                         do_exchange: bool = False) -> tuple[np.ndarray, np.ndarray, dict]:
    rows_pos = np.flatnonzero((cat & eligible).ravel())
    cat_distance = ndi.distance_transform_edt(~cat)
    rows_neg = np.flatnonzero((eligible & labelled_zero &
                               (cat_distance > NEGATIVE_COLLAR_PX)).ravel())
    rng = np.random.default_rng(SEED + 9000)
    if len(rows_pos) < 100 or len(rows_neg) < 100:
        raise SystemExit("full-data supervised model lacks labelled examples")
    rows_pos = rng.choice(rows_pos, min(20000, len(rows_pos)), replace=False)
    rows_neg = rng.choice(rows_neg, min(60000, len(rows_neg)), replace=False)
    rows = np.r_[rows_pos, rows_neg]
    y = np.r_[np.ones(len(rows_pos), np.int8), np.zeros(len(rows_neg), np.int8)]
    order = rng.permutation(len(rows))
    rows, y = rows[order], y[order]
    predictions, models = {}, {}
    training = dict(rows=len(rows), positive=int(y.sum()), negative=int((y == 0).sum()),
                    negative_collar_px=NEGATIVE_COLLAR_PX, full_data_exchange_requested=bool(do_exchange))
    for view, names in (("A", names_a), ("B", names_b)):
        model = learner(SEED + 9000)
        model.fit(store.gather(rows, names), y)
        predictions[view] = predict_flat(store, model, names, store.flat_idx)
        models[view] = model
        training[f"view_{view}_feature_count"] = len(names)
    if do_exchange:
        pa = to_grid(store.flat_idx, predictions["A"], eligible.shape)
        pb = to_grid(store.flat_idx, predictions["B"], eligible.shape)
        rank_a = rank_grid_on_train(pa, eligible)
        rank_b = rank_grid_on_train(pb, eligible)
        used = np.zeros(eligible.shape, dtype=bool)
        used.ravel()[rows] = True
        visible_distance = ndi.distance_transform_edt(~cat)
        forbidden = (visible_distance <= 4) | used
        del visible_distance
        exchange = {}
        for donor, receiver, donor_grid, receiver_grid in (
                ("A", "B", rank_a, rank_b), ("B", "A", rank_b, rank_a)):
            idx, segments = spatial.whole_pseudo_segments(donor_grid, receiver_grid,
                eligible, forbidden, DONOR_RANK, RECEIVER_RANK[0], RECEIVER_RANK[1],
                side=PSEUDO_BLOCK_PX, min_pixels=PSEUDO_MIN_PIXELS, cap=PSEUDO_CAP)
            if np.intersect1d(idx, rows).size or len(idx) > PSEUDO_CAP:
                raise AssertionError("full-data pseudo segments overlap supervised samples or exceed the cap")
            exchange[f"{donor}_to_{receiver}"] = dict(pixel_count=int(len(idx)),
                segment_count=len(segments), segments=segments, indices=idx.tolist())
        for view, names, pseudo_key in (("A", names_a, "B_to_A"), ("B", names_b, "A_to_B")):
            pseudo_rows = np.asarray(exchange[pseudo_key]["indices"], dtype=np.int64)
            donor, receiver = ("B", "A") if view == "A" else ("A", "B")
            if len(pseudo_rows):
                X = np.concatenate((store.gather(rows, names),
                                    store.gather(pseudo_rows, names)), axis=0)
                y_full = np.r_[y, np.ones(len(pseudo_rows), np.int8)]
                model = learner(SEED + 9100)
                model.fit(X, y_full)
                models[view] = model
                predictions[view] = predict_flat(store, model, names, store.flat_idx)
            training.setdefault("full_exchange", {})[f"{donor}_to_{receiver}"] = dict(
                pseudo_pixels=int(len(pseudo_rows)),
                pseudo_segments=exchange[pseudo_key]["segment_count"])
        training["full_exchange"]["rounds"] = 1
        training["full_exchange"]["policy"] = "only after both OOF sufficiency and block-error gates; whole 50x50px segments, one round"
        del pa, pb, rank_a, rank_b
    return predictions["A"], predictions["B"], training


def write_reasoning_csv(path: Path, coords: np.ndarray, rank_a: np.ndarray,
                        rank_b: np.ndarray, score: np.ndarray, store: structural.FeatureStore,
                        names_a: list[str], names_b: list[str]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = coords[:, 0].astype(np.int64) * store.valid.shape[1] + coords[:, 1].astype(np.int64)
    # Keep the evidence table compact but let reviewers inspect the mechanism's named channels.
    selected_names = ([n for n in names_a if n.endswith(("_aniso_l2", "_aniso_l4"))] +
                      list(names_b))
    a_features = store.gather(flat, selected_names) if len(flat) else np.empty((0, len(selected_names)), np.float32)
    band_values = {}
    with rasterio.open(FEATURES) as src:
        for band, tag in DVA_BANDS:
            grid = src.read(band)
            band_values[f"band_{band}_{tag}"] = grid[coords[:, 0], coords[:, 1]].astype(float) if len(coords) else np.empty(0)
            del grid
    band_review = {
        "rtp": ("band 2 RTP magnetics", "A DVA anisotropy is strongest in reduced-to-pole magnetics; a magnetic-susceptibility contrast can mark a buried lineament, but is not diagnostic of a fault.", "magnetized lithologic contact, RTP processing seam, or survey/gridding boundary"),
        "iso_grav_anom": ("band 13 isostatic gravity", "A DVA anisotropy is strongest in isostatic gravity; a density contrast may follow a basin margin or subsurface structure, but is not a fault-specific signal.", "basin-fill/lithologic density contrast, terrain correction, or gravity interpolation seam"),
        "depth_to_base_surf": ("band 15 modelled basement depth", "A DVA anisotropy is strongest in modelled basement depth; a cover-thickness edge may be structurally controlled, but inherits the source model's smoothing and dependencies.", "basin geometry, inversion/model boundary, or interpolation seam; basement depth is not independent fault evidence"),
        "conductivity_surface": ("band 17 surface conductivity", "A DVA anisotropy is strongest in the in-stack conductivity surface; a conductive boundary can be compatible with a fluid pathway, but cannot identify fluids or a fault by itself.", "clay-rich or saline basin fill, lithologic conductivity contrast, or EM inversion seam"),
        "geodetic_shear": ("band 7 geodetic shear", "A DVA anisotropy is strongest in geodetic shear; the broad deformation field may align with a structure, but its spatial support is not direct 100 m fault mapping.", "regional strain interpolation, station geometry, or geodetic smoothing"),
        "earthquake_intensity": ("band 16 earthquake intensity/density", "A DVA anisotropy is strongest in the gridded earthquake-intensity field; event clustering may relate to structure, but density is not a mapped fault trace.", "event-catalogue coverage, smoothing/azimuth parameters, or a non-tectonic event cluster"),
    }
    band_tags = [tag for _band, tag in DVA_BANDS]
    feature_col = {name: i for i, name in enumerate(selected_names)}
    headers = ["row", "col", "easting_m", "northing_m", "view_A_rank", "view_B_rank",
        "a_only_score", "dominant_A_band", "dominant_A_two_scale_anisotropy_mean",
        "geological_reason", "evidence_class", "interpretation", "named_non_fault_mimic",
        "specific_non_fault_mimic", "falsifier"]
    headers += [f"value_{n}" for n in selected_names]
    headers += list(band_values)
    transform = rasterio.open(SAMPLE).transform
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for i, (row, col) in enumerate(coords):
            x, y = rasterio.transform.xy(transform, int(row), int(col), offset="center")
            strength_by_tag = {}
            for tag in band_tags:
                l2 = float(a_features[i, feature_col[f"H87_DVA_{tag}_aniso_l2"]])
                l4 = float(a_features[i, feature_col[f"H87_DVA_{tag}_aniso_l4"]])
                strength_by_tag[tag] = (l2 + l4) / 2.0
            dominant_tag = max(strength_by_tag, key=strength_by_tag.get)
            dominant_band, physical_reason, specific_mimic = band_review[dominant_tag]
            view_a_rank = float(rank_a[row, col])
            view_b_rank = float(rank_b[row, col])
            record = dict(row=int(row), col=int(col), easting_m=round(float(x), 3), northing_m=round(float(y), 3),
                view_A_rank=view_a_rank, view_B_rank=view_b_rank, a_only_score=float(score[row, col]),
                dominant_A_band=dominant_band,
                dominant_A_two_scale_anisotropy_mean=float(strength_by_tag[dominant_tag]),
                geological_reason=(f"{physical_reason} This is a relative per-cell channel ranking, not calibrated significance; "
                    f"View-A rank={view_a_rank:.3f}, View-B rank={view_b_rank:.3f} (in the registered abstention interval)"),
                evidence_class="MODEL_SCREENING_NOT_VERIFIED_FAULT_OR_VENT",
                interpretation=(f"Candidate-specific leading A channel: {dominant_band}. {physical_reason} "
                    "View B abstains, which is not independent confirmation."),
                named_non_fault_mimic=specific_mimic,
                specific_non_fault_mimic=specific_mimic,
                falsifier=("Reject a fault interpretation if independent mapping/profile finds no displaced marker or persistent subsurface edge, "
                    "or if the lineament follows the named lithologic, source-model, survey, or interpolation boundary."))
            for j, name in enumerate(selected_names):
                record[f"value_{name}"] = float(a_features[i, j])
            for name, values in band_values.items():
                record[name] = float(values[i])
            writer.writerow(record)
    return dict(path=str(path.relative_to(ROOT)), rows=int(len(coords)),
                sha256=sha256(path), bytes=path.stat().st_size,
                all_rows_have_reasoning=True, evidence_class="candidate review targets; not verified faults",
                view_B_feature_count=int(len(names_b)), view_B_features_included=list(names_b),
                dominant_A_band_rule=("For each emitted cell, identify the A channel with the greatest arithmetic mean of its normalized DVA anisotropy at lags 2 and 4; a comparative review aid, not calibrated significance."),
                candidate_specific_fields=["dominant_A_band", "dominant_A_two_scale_anisotropy_mean",
                    "geological_reason", "specific_non_fault_mimic", "falsifier"])


def slim_lane(report: dict) -> dict:
    keep = {}
    for key, value in report.items():
        if isinstance(value, (str, bool, int, float)) or value is None:
            keep[key] = value
    for key in ("literal", "policy", "rule", "scope", "instrument", "phase", "evidence_class"):
        if key in report:
            keep[key] = report[key]
    keep["per_prior"] = report.get("per_prior", [])
    return keep


def self_copy_filter(priors: list[Path], candidate: Path) -> list[Path]:
    digest = sha256(candidate) if candidate.exists() else None
    out = []
    for p in priors:
        if candidate.exists() and p.resolve() == candidate.resolve():
            continue
        if p.name == candidate.name:
            continue
        if digest and p.is_file() and sha256(p) == digest:
            continue
        out.append(p)
    return out


def stage_write(context: dict | None = None) -> tuple[dict, dict]:
    if context is None:
        _, context = stage_canary()
    holdout = context.get("holdout_receipt") or json.loads((EVIDENCE / "h87_holdout.json").read_text())
    fit = context.get("fit_receipt") or json.loads((EVIDENCE / "h87_fit.json").read_text())
    store, cat, eligible = context["store"], context["cat"], context["eligible"]
    names_a, names_b = context["names_a"], context["names_b"]
    sample_meta = context["ctx"]["sample_meta"]
    # Full-fit is for the final research TIFF only; all holdout evidence above is fold-isolated.
    exchange_enabled = bool(context.get("exchange_receipt", {}).get("ran"))
    pa_flat, pb_flat, training = full_fit_and_predict(store, cat, context["labelled_zero"],
        eligible, names_a, names_b, do_exchange=exchange_enabled)
    pa = to_grid(store.flat_idx, pa_flat, eligible.shape)
    pb = to_grid(store.flat_idx, pb_flat, eligible.shape)
    cat_distance = ndi.distance_transform_edt(~cat)
    allowed = eligible & ~cat & (cat_distance > RING_PX)
    rank_a = rank_on_mask(pa, allowed)
    rank_b = rank_on_mask(pb, allowed)
    a_only = allowed & (rank_a >= DONOR_RANK) & (rank_b >= RECEIVER_RANK[0]) & (rank_b <= RECEIVER_RANK[1])
    b_only = allowed & (rank_b >= DONOR_RANK) & (rank_a >= RECEIVER_RANK[0]) & (rank_a <= RECEIVER_RANK[1])
    surface = np.where(a_only, rank_a * (1.0 - rank_b), 0.0).astype(np.float32)
    surface[~eligible] = 0.0

    roots = [ROOT / "submission", DOWNLOADS, ROOT / "data/scored", ROOT / "data/reference"]
    prior_paths = gates.find_priors(roots)
    prior_paths = [p for p in prior_paths if "h87-candidate" not in p.name]
    lane_surface = gates.lane_report(surface, eligible, prior_paths, sample=str(SAMPLE), phase="surface")
    surface_literal = lane_surface.get("literal", {})
    surf_spearman = surface_literal.get("max_spearman")
    surface_stop = bool((surf_spearman is not None and float(surf_spearman) > 0.90) or
                        surface_literal.get("verdict") == "DUPLICATE/STOP" or
                        int(lane_surface.get("error_count", 0)) > 0)
    if surface_stop:
        # Literal protocol says stop before placement; do not silently waive it.
        out = dict(round="H87", stage="write", generated_utc=now(),
            hypothesis=HYPOTHESES.name, hypothesis_sha256=sha256(HYPOTHESES),
            mechanism="strict A-only geophysical DVA predictions where surface View B abstains",
            named_non_fault_process="basin/lithologic contacts, inversion or interpolation seams, conductive clays/saline basin fill",
            holdout_dti=dict(evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
                withheld_positive_pixels=holdout["withheld_positive_pixels"],
                primary=holdout["pooled"]["scores"].get("a_only")),
            correlation_overlap_vs_registry=dict(surface_before_placement=slim_lane(lane_surface)),
            raster_sha256=None, validator=None, submission_name="h87-dva-aonly-37654px-20261010",
            note=SUBMISSION_NOTE, download_ok=False, submit_ok=False, slots_used=0,
            stop_before_placement=True,
            reason="surface rank-correlation/lane audit exceeded the literal gate or had an incomparable prior; DUPLICATE/STOP",
            verdict="negative", verdict_reason="Fail-closed lane stop; no placement, GeoTIFF or weekly slot.")
        publish_receipt("lane", dict(round="H87", generated_utc=now(),
            surface_before_placement=lane_surface, final_dots=None,
            literal_surface=dict(pass_gate=False, max_spearman=surf_spearman,
                verdict=surface_literal.get("verdict")),
            literal_final=None, scope="129 accessible local prior rasters; not proof against unlinked/private submissions"))
        publish_receipt("build", out)
        write_json(EVIDENCE / "h87_run_card.json", out)
        write_json(DOC_DATA / "h87_run_card.json", out)
        return out, context

    dots = nodes.spacing_select(surface, a_only, K_TOTAL, min_px=MIN_SPACING_PX).astype(np.float32)
    n_dots = int(dots.sum())
    if n_dots == 0:
        raise SystemExit("H87 A-only candidate pool produced zero placed pixels; no TIFF written")
    stamp = "20261010"
    file_name = f"gems52-h87-dva-aonly-{n_dots}px-{stamp}.tif"
    path = ROOT / "submission" / file_name
    name = f"h87-dva-aonly-{n_dots}px-20261010"
    note = SUBMISSION_NOTE
    if len(name) > 140 or len(note) > 140:
        raise SystemExit("H87 submission name or note exceeds 140 characters")
    metadata = dict(round="H87", hypothesis=HYPOTHESES.name,
        hypothesis_sha256=sha256(HYPOTHESES), method="strict two-view DVA disagreement; A-only, B abstains",
        view_A_bands=[b for b, _ in DVA_BANDS], view_B_bands=[6, 12, 19],
        pseudo_exchange_performed=bool(context.get("exchange_receipt", {}).get("ran")),
        holdout_reference="evidence/h87_holdout.json", no_organizer_upload=True,
        data_provenance="integrity-pinned owner mirror, not organizer-authenticated")
    receipt = submission_writer.write_submission(path, dots, SAMPLE, eligible,
        note=note, name=name, metadata=metadata)

    # Publish the exact same bytes as a direct, obvious download. Copies are removed from the
    # comparison inventory by decoded/file SHA; a filename alone is never treated as novelty.
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    download_tif = DOWNLOADS / "h87-candidate.tif"
    download_zip = DOWNLOADS / "h87-candidate.zip"
    shutil.copyfile(path, download_tif)
    shutil.copyfile(path.with_suffix(".zip"), download_zip)
    if sha256(download_tif) != sha256(path):
        raise IOError("download copy bytes differ from source submission TIFF")
    with rasterio.open(path) as src:
        raster = src.read(1)
        raster_meta = dict(count=src.count, dtype=src.dtypes[0], shape=list(src.shape),
            crs=str(src.crs), transform=list(src.transform)[:6], nodata=src.nodata,
            all_finite=bool(np.isfinite(raster).all()), min=float(raster.min()), max=float(raster.max()),
            positive_pixels=int((raster > 0).sum()), binary=bool(np.isin(raster, [0.0, 1.0]).all()))
    report = gates.format_report(path, SAMPLE, footprint=eligible)
    sample_domain = context["ctx"]["sample_domain"]
    report["no_nan_inside_sample_footprint"] = bool(np.isfinite(raster[sample_domain]).all())
    report["shape_crs_transform_match"] = bool(
        tuple(raster_meta["shape"]) == tuple(sample_meta["shape"]) and
        raster_meta["crs"] == sample_meta["crs"] and
        np.allclose(raster_meta["transform"], sample_meta["transform"], rtol=0, atol=1e-9))
    report["outside_sample_domain_zero"] = bool((raster[~sample_domain] == 0).all())
    report["all_finite_in_0_1"] = bool(raster_meta["all_finite"] and 0.0 <= raster_meta["min"] <= raster_meta["max"] <= 1.0)
    report["ok"] = bool(report.get("ok") and report["no_nan_inside_sample_footprint"] and
                        report["shape_crs_transform_match"] and report["outside_sample_domain_zero"] and
                        report["all_finite_in_0_1"])
    if not report["ok"]:
        raise SystemExit(f"H87 on-disk validator failed: {report.get('problems')}")

    final_priors = gates.find_priors(roots, exclude=path)
    final_priors = self_copy_filter(final_priors, path)
    uniq = gates.uniqueness_report(dots, final_priors)
    lane_dots = gates.lane_report(dots, eligible, final_priors, sample=str(SAMPLE), phase="dots")
    lane_literal = lane_dots.get("literal", {})
    # The current registry includes measured universal-coverage probes. Per the user's literal
    # lane rule, report (and do not waive) every >0.90 rank or >0.70 directed near-dot result.
    literal_spearman = lane_literal.get("max_spearman")
    literal_near = lane_literal.get("max_near_3px_fraction")
    lane_literal_duplicate = bool(lane_literal.get("verdict") == "DUPLICATE/STOP" or
        (literal_spearman is not None and float(literal_spearman) > 0.90) or
        (literal_near is not None and float(literal_near) > 0.70) or
        int(lane_dots.get("error_count", 0)) > 0)
    lane_receipt = dict(round="H87", generated_utc=now(), evidence_class="uniqueness/lane diagnostic, not a score",
        surface_before_placement=lane_surface, final_dots=lane_dots,
        literal_surface=dict(pass_gate=not surface_stop,
            max_spearman=surface_literal.get("max_spearman"),
            max_near_3px_fraction=surface_literal.get("max_near_3px_fraction"),
            verdict=surface_literal.get("verdict")),
        literal_final=dict(pass_gate=not lane_literal_duplicate,
            max_spearman=literal_spearman, max_near_3px_fraction=literal_near,
            max_near_source=lane_literal.get("max_near_source"), verdict=lane_literal.get("verdict")),
        scope="129 accessible local prior rasters; not proof against unlinked/private submissions")
    publish_receipt("lane", lane_receipt)

    # Equal-budget placement ablation: not just the union of the two view ranks.
    same_k = n_dots
    dot_a = nodes.spacing_select(np.where(allowed, rank_a, 0.0).astype(np.float32),
                                 allowed, same_k, min_px=MIN_SPACING_PX)
    dot_b = nodes.spacing_select(np.where(allowed, rank_b, 0.0).astype(np.float32),
                                 allowed, same_k, min_px=MIN_SPACING_PX)
    dot_union_max = nodes.spacing_select(np.where(allowed, np.maximum(rank_a, rank_b), 0.0).astype(np.float32),
                                         allowed, same_k, min_px=MIN_SPACING_PX)
    dot_union_support = dot_a | dot_b
    def overlap(mask):
        inter = int((dots.astype(bool) & mask.astype(bool)).sum())
        union = int((dots.astype(bool) | mask.astype(bool)).sum())
        return dict(intersection=inter, jaccard=inter / max(union, 1),
                    differing_cells=int(np.count_nonzero(dots != mask)),
                    identical=bool(np.array_equal(dots, mask)),
                    subset=bool((dots.astype(bool) & ~mask.astype(bool)).sum() == 0))
    not_union = dict(candidate_positive_pixels=n_dots,
        vs_single_A=overlap(dot_a), vs_single_B=overlap(dot_b),
        vs_equal_budget_union_max=overlap(dot_union_max),
        vs_union_of_separately_placed_A_and_B=overlap(dot_union_support),
        candidate_is_union_of_views=bool(np.array_equal(dots.astype(bool), dot_union_max.astype(bool)) or
                                         np.array_equal(dots.astype(bool), dot_union_support.astype(bool))),
        equal_budget=int(same_k), method="shared nodes.spacing_select, 3 px spacing")

    coords = np.argwhere(dots > 0)
    reasoning = write_reasoning_csv(DOWNLOADS / "h87-a-only-reasoning.csv.gz",
        coords, rank_a, rank_b, surface, store, names_a, names_b)
    # Mirror the review table beside the submission for reproducibility.
    shutil.copyfile(DOWNLOADS / "h87-a-only-reasoning.csv.gz",
                    ROOT / "submission" / "gems52-h87-a-only-reasoning.csv.gz")

    holdout_scores = holdout["pooled"]["scores"]
    dti_primary = holdout_scores["a_only"]
    control_name = holdout["pooled"].get("best_comparable_control")
    point_control_name = holdout["pooled"].get("best_control_by_point_estimate")
    paired = holdout["pooled"]["paired_differences"].get(control_name) if control_name else None
    beats_comparable = bool(paired and paired["ci95"][0] > 0.0 and holdout["all_arms_filled"])
    integrity_unique = bool(uniq.get("research_publication_ok") and uniq.get("audit_complete") and
                            uniq.get("n_priors_compared", 0) > 0)
    lane_pass = not lane_literal_duplicate
    download_ok = bool(report["ok"] and integrity_unique)
    # Selection/promotion is explicitly a separate weekly-selector step. This run never promotes,
    # approves upload, or spends a slot, even if its experiment gates happen to pass.
    eligible_for_selector = bool(download_ok and lane_pass and
        not_union["candidate_is_union_of_views"] is False and beats_comparable and
        fit["sufficiency"]["both_pass"] and context.get("independence_receipt", {}).get("exchange_allowed"))
    submit_ok = False
    status = "negative"
    sha = sha256(path)
    card = dict(round="H87", generated_utc=now(), hypothesis=HYPOTHESES.name,
        hypothesis_sha256=sha256(HYPOTHESES),
        mechanism="A-view directional variogram anisotropy of magnetic, gravity, basement-depth, conductivity, shear and seismic-intensity bands; emit only A-confident / B-abstaining candidates",
        named_non_fault_process="basin/lithologic contacts, inversion or interpolation seams, conductive clays/saline basin fill; DEM roads and erosion lines can mimic B-only candidates",
        holdout_dti=dict(evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
            withheld_positive_pixels=holdout["withheld_positive_pixels"], ci95=dti_primary["ci95"],
            dti=dti_primary["dti"], alpha=0.2, beta=0.8, triangular_radius_m=300.0,
            comparison_valid=bool(holdout["all_arms_filled"]),
            invalid_reason=holdout["pooled"].get("invalid_comparison_reason"),
            paired_vs_best_same_fold_control=paired, best_comparable_control=control_name,
            highest_point_estimate_control_not_comparable=point_control_name,
            all_arms_filled=holdout["all_arms_filled"], result_file="evidence/h87_holdout.json"),
        view_gates=dict(canary_max_direction_insensitive_auc=json.loads((EVIDENCE / "h87_canary.json").read_text())["maximum_auc"],
            canary_alarm=False, sufficiency=fit["sufficiency"],
            negative_error_correlation=context["independence_receipt"]["independent_error_test"]["max_abs_correlation"],
            negative_error_blocks=context["independence_receipt"]["independent_error_test"]["n_blocks"],
            exchange_performed=bool(context.get("exchange_receipt", {}).get("ran")),
            exchange_reason=context["independence_receipt"]["exchange_gate_reason"]),
        correlation_overlap_vs_registry=dict(surface_before_placement=slim_lane(lane_surface),
            final_dots=slim_lane(lane_dots), literal_lane_duplicate=lane_literal_duplicate,
            uniqueness=uniq),
        raster_sha256=sha, decoded_pixel_sha256=uniq.get("candidate_decoded_sha256"),
        file=str(path.relative_to(ROOT)), download_tif=str(download_tif.relative_to(ROOT)),
        download_zip=str(download_zip.relative_to(ROOT)), file_bytes=path.stat().st_size,
        validator=dict(format_report=report, decoded_metadata=raster_meta,
                       no_nan_inside_footprint=report["no_nan_inside_sample_footprint"],
                       values_in_0_1=report["all_finite_in_0_1"],
                       crs_shape_transform_match=report["shape_crs_transform_match"]),
        not_union=not_union, a_only_reasoning=reasoning,
        submission_name=name, note=note, note_chars=len(note), training_sample=training,
        final_strata=dict(allowed_pixels=int(allowed.sum()), a_only_pixels=int(a_only.sum()),
                          b_only_pixels=int(b_only.sum()), emitted_pixels=n_dots),
        decision=dict(download="YES" if download_ok else "NO", submit="NO",
            reason=("Download is approved for inspection only after local format and decoded-uniqueness checks. "
                    "Do not submit: View A fails the preregistered sufficiency screen, the A-only arm underfilled its matched budget, "
                    "and no weekly selector or organizer receipt exists.")),
        download_ok=download_ok, submit_ok=submit_ok, eligible_for_separate_selector=eligible_for_selector,
        slots_used=0, weekly_slot_promotion="not performed; separate selector step required",
        organizer_confirmed_scores=[], verdict=status,
        verdict_reason=("Negative: View A mean OOF AUC is below the registered 0.60 sufficiency screen, pseudo-label exchange was closed, "
            "A-only holdout placement underfilled the fixed budget so its paired DTI comparison is invalid, and no weekly slot was selected. "
            "The TIFF is safe to download/inspect but is not approved for submission."),
        data_provenance="integrity-pinned owner mirror; not organizer-authenticated",
        implementation_hashes=evaluator.implementation_hashes(),
        experiments_used=2 + int(bool(context.get("exchange_receipt", {}).get("ran"))),
        experiment_budget=3, hours_budget=2,
        official_sources=[
            "https://doi.org/10.1145/279943.279962",
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "https://www.osti.gov/biblio/1724082",
            "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and"],
        local_manual_review=["knowledge/80_h87_hypotheses_preregistered.md",
            "evidence/h87_canary.json", "evidence/h87_fit.json", "evidence/h87_independence.json",
            "evidence/h87_exchange.json", "evidence/h87_holdout.json", "evidence/h87_lane.json",
            reasoning["path"]])
    receipt.update(dict(download_copy=str(download_tif.relative_to(ROOT)),
        download_copy_sha256=sha256(download_tif), ok_to_download=download_ok,
        ok_to_submit=submit_ok, slots_used=0, verdict=status,
        holdout_dti=dti_primary, note_chars=len(note)))
    write_json(path.with_suffix(".json"), receipt)
    write_json(EVIDENCE / "h87_build.json", card)
    write_json(DOC_DATA / "h87_build.json", card)
    write_json(EVIDENCE / "h87_run_card.json", card)
    write_json(DOC_DATA / "h87_run_card.json", card)
    (ROOT / "submission/H87_LATEST.txt").write_text(str(path.relative_to(ROOT)) + "\n")
    (ROOT / "docs/submission/H87_LATEST.txt").write_text(str(download_tif.relative_to(ROOT)) + "\n")
    context["build_card"] = card
    log(f"written {path.relative_to(ROOT)} sha256={sha[:16]}… validator={report['ok']} "
        f"unique={integrity_unique} lane_literal_duplicate={lane_literal_duplicate} submit_ok={submit_ok}")
    return card, context


def run_all() -> dict:
    started = now()
    t0 = time.time()
    verify_prereg()
    verify_inputs()
    canary, ctx = stage_canary()
    cache = ctx["ctx"]["cache"]
    fit, ctx = stage_fit(ctx)
    ctx["fit_receipt"] = fit
    independence, ctx = stage_independence(ctx)
    exchange, ctx = stage_exchange(ctx)
    holdout, ctx = stage_holdout(ctx)
    card, ctx = stage_write(ctx)
    summary = dict(round="H87", started_utc=started, finished_utc=now(),
        elapsed_seconds=round(time.time() - t0, 1), cache=cache, canary=canary,
        fit=fit, independence=independence, exchange=exchange, holdout=holdout,
        build=card, verdict=card.get("verdict", "negative"), slots_used=0)
    publish_receipt("session", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("all", "cache", "fit", "independence", "holdout", "write"), nargs="?", default="all")
    args = ap.parse_args()
    if args.stage == "all":
        out = run_all()
    elif args.stage == "cache":
        verify_prereg(); verify_inputs(); out = build_dva_cache(json.loads(PREREG.read_text()))
    elif args.stage == "fit":
        _, ctx = stage_canary(); fit, _ctx = stage_fit(ctx); out = fit
    elif args.stage == "independence":
        _, ctx = stage_canary(); fit = json.loads((EVIDENCE / "h87_fit.json").read_text())
        ctx["fit_receipt"] = fit; out, _ctx = stage_independence(ctx)
    elif args.stage == "holdout":
        _, ctx = stage_canary(); ctx["fit_receipt"] = json.loads((EVIDENCE / "h87_fit.json").read_text())
        ctx["independence_receipt"] = json.loads((EVIDENCE / "h87_independence.json").read_text())
        ex = json.loads((EVIDENCE / "h87_exchange.json").read_text()) if (EVIDENCE / "h87_exchange.json").exists() else {"ran": False}
        ctx["exchange_receipt"] = ex; out, _ctx = stage_holdout(ctx)
    else:  # write
        _, ctx = stage_canary(); ctx["fit_receipt"] = json.loads((EVIDENCE / "h87_fit.json").read_text())
        ctx["independence_receipt"] = json.loads((EVIDENCE / "h87_independence.json").read_text())
        ctx["exchange_receipt"] = json.loads((EVIDENCE / "h87_exchange.json").read_text())
        ctx["holdout_receipt"] = json.loads((EVIDENCE / "h87_holdout.json").read_text())
        out, _ctx = stage_write(ctx)
    print(json.dumps(out, indent=2, default=float)[:12000])


if __name__ == "__main__":
    main()
