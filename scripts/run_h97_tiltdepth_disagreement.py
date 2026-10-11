#!/usr/bin/env python3
"""H97: magnetic tilt-depth A-only disagreement against a strict surface DVA2/HVA view.

This experiment uses the shared FeatureStore, run_h84's verified unsupervised channel builder,
run_h61's fold/sample/learner hooks, gems52.spatial (including whole_pseudo_segments), the shared
hide-and-recover evaluator, node placement, lane gates, and submission writer. It does not fork the
metric or writer. The H84 B_DVA2 control is refit from the exact same folds and cache because it is
the strongest matched-mask historical result (0.1928290705 HOLDOUT-DTI, 53,186 positives).

Usage: .venv/bin/python scripts/run_h97_tiltdepth_disagreement.py [prior-check|channels|canary|fit|holdout|build|lane|write|card|all]
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata
from sklearn.metrics import roc_auc_score

import run_h61 as base
import run_h82 as h82
import run_h84 as h84
from gems52 import evaluate_holdout as evaluator
from gems52 import gates, nodes, spatial, submission_writer

PREREG = ROOT / "registry/h97_preregistration.json"
DOC = ROOT / "knowledge/97_hypotheses_H97_preregistered.md"
WORK = ROOT / "work/h97"
CHANNEL_WORK = WORK / "h84_channels"
CHANNEL_FEAT = CHANNEL_WORK / "features"
CHANNEL_EVID = CHANNEL_WORK / "evidence"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
EXPECTED_VALID = 4_593_171
EXPECTED_WITHHELD = 53_186
SEED = 61_052
K_FOLD = 9_400
K_TOTAL = 37_654
RING_PX = 2
CANARY_BAR = 0.90
INDEP_BAR = 0.60
A_SUFF_MEAN = 0.60
A_SUFF_FOLD = 0.55
PSEUDO_MIN_DIRECTION = 200


def log(*args):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *args, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(name, obj):
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h97_{name}.json"
    p.write_text(json.dumps(obj, indent=2, allow_nan=False, default=float) + "\n")
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    got = sha(DOC)
    if got != reg["hypothesis_sha256"] or DOC.stat().st_size != reg["hypothesis_bytes"]:
        raise SystemExit(f"H97 preregistration moved: {got}; refusing to fit")
    if reg.get("frozen_before_any_fit") is not True:
        raise SystemExit("H97 registry does not attest pre-fit freeze")
    prior = reg.get("frozen_prior_inventory", {})
    inv = ROOT / prior.get("path", "")
    if (not inv.exists() or sha(inv) != prior.get("sha256") or
            inv.stat().st_size != int(prior.get("bytes", -1))):
        raise SystemExit("frozen prior inventory moved or is missing; refusing H97 work")
    return reg


def verify_input_bytes():
    manifest = json.loads((ROOT / "registry/data_manifest.json").read_text())
    by_id = {f["id"]: f for f in manifest["files"]}
    verified = []
    for fid in ("training_features", "labels", "sample_submission", "ext_geodawn_rad_u8", "ext_geodawn_extensions_u8"):
        f = by_id[fid]
        path = ROOT / "data" / f["dest"]
        got = sha(path)
        n = path.stat().st_size
        if got != f["sha256"] or n != int(f["bytes"]):
            raise SystemExit(f"H97 input integrity STOP: {fid} sha/size mismatch ({got}, {n})")
        verified.append(dict(id=fid, path=str(path.relative_to(ROOT)), bytes=n, sha256=got, matches_manifest=True,
                             provenance=f.get("provenance", "")))
    rec = dict(stage="input_integrity", generated_utc=now(), manifest="registry/data_manifest.json",
               manifest_sha256=sha(ROOT / "registry/data_manifest.json"), all_verified=True,
               organizer_authenticated=False,
               transport_note="GeoDAWN extensions layer was restored after GitHub REST returned HTTP 403; a filtered clone of its manifest-pinned Git commit supplied the same blob, verified by byte count and SHA-256.",
               files=verified)
    dump("data_integrity", rec)
    return rec


def setup():
    reg = check_prereg()
    verify_input_bytes()
    _base_reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    truth_counts = [int(f["truth"].sum()) for f in folds]
    total = int(sum(truth_counts))
    if int(eligible.sum()) != EXPECTED_VALID or truth_counts != [27_309, 10_677, 6_813, 8_387] or total != EXPECTED_WITHHELD:
        raise SystemExit(f"mask mismatch; STOP before fit: valid={int(eligible.sum())}, fold_truth={truth_counts}, total={total}")
    if int(reg["mask"]["expected_withheld_positive_pixels"]) != total:
        raise SystemExit("registered mask count differs from actual mask")
    if set(va) & set(vb):
        raise SystemExit("View A / View B store columns overlap")
    if store.manifest.get("version", "").find("+external-geodawn-v1") < 0:
        raise SystemExit("shared external GeoDAWN feature extension absent")
    with rasterio.open(SAMPLE) as ref:
        shape, crs, transform = ref.shape, str(ref.crs), list(ref.transform)[:6]
    mask_hash = hashlib.sha256(np.ascontiguousarray(eligible).tobytes()).hexdigest()
    out = dict(stage="mask", generated_utc=now(), feature_store=str(store.directory),
               feature_store_version=store.manifest["version"], feature_manifest_sha256=sha(store.directory / "manifest.json"),
               input_features_sha256=store.manifest["inputs"]["features_sha256"],
               eligible_pixels=int(eligible.sum()), expected_eligible_pixels=EXPECTED_VALID,
               eligibility_mask_sha256=mask_hash, fold_splitter="gems52.spatial.folds label-blind-quadrants-v2",
               buffer_px=80, fold_truth_pixels=truth_counts, withheld_positive_pixels=total,
               expected_withheld_positive_pixels=EXPECTED_WITHHELD,
               shape=list(shape), crs=crs, transform=transform, view_A_count=len(va), view_B_count=len(vb),
               ring_px=ring_px, evaluator=evaluator.VERSION,
               status="PASS: exact H82/H84 eligible mask and whole-segment holdout count")
    dump("mask", out)
    log(f"mask PASS: valid={int(eligible.sum())}, withheld={total}, folds={truth_counts}, sha={mask_hash[:16]}…")
    return reg, store, cat, eligible, folds, va, vb, ring_px


def ensure_channels(store, eligible):
    """Use H84's shared, disk-audited channel builder in an H97-specific ignored work directory."""
    CHANNEL_WORK.mkdir(parents=True, exist_ok=True)
    CHANNEL_EVID.mkdir(parents=True, exist_ok=True)
    h84.WORK = CHANNEL_WORK
    h84.FEAT = CHANNEL_FEAT
    h84.EVID = CHANNEL_EVID
    h84.check_prereg()
    manifest_path = CHANNEL_FEAT / "manifest.json"
    if not manifest_path.exists():
        log("building H84's verified DVA2/HVA/COH channel bank into work/h97 (no historic H84 receipt overwritten)")
        h84.stage_channels()
    manifest = json.loads(manifest_path.read_text())
    if int(manifest.get("n_eligible", -1)) != int(eligible.sum()):
        raise SystemExit("H84 channel bank was built on a different eligible mask")
    bank = h82.Bank(CHANNEL_FEAT)
    needed = sorted(set(h84.DVA2 + h84.HVA + h84.COH))
    for name in needed:
        bank.col(name)  # byte-integrity check before canary/fit
    surface = surface_channel_names(needed)
    if (len(manifest["sha256"]) != 81 or len(h84.DVA2) != 50 or len(h84.HVA) != 25 or
            len(h84.COH) != 5 or len(surface) != 32):
        raise SystemExit(f"unexpected channel inventory: columns={len(manifest['sha256'])}, DVA2={len(h84.DVA2)}, "
                         f"HVA={len(h84.HVA)}, COH={len(h84.COH)}, surface={len(surface)}")
    out = dict(stage="channels", generated_utc=now(), channel_dir=str(CHANNEL_FEAT.relative_to(ROOT)),
               channel_manifest_sha256=sha(manifest_path), n_columns=len(manifest["sha256"]),
               n_eligible=int(manifest["n_eligible"]), channel_sha256=manifest["sha256"],
               H84_DVA2_control_channels=len(h84.DVA2), H97_strict_surface_channels=len(surface),
               strict_surface_channels=surface,
               view_separation=("H97 strict B receives only DVA2/HVA/COH from band 12 det_elev and band 19 det_elev_slope; "
                                "H84 B_DVA2 historical control receives all 50 DVA2 channels, including gravity/depth bands"),
               status="PASS: every requested channel hash-verified")
    dump("channels", out)
    return bank, surface


def channel_band(name):
    # Longest prefix first because det_elev_slope begins with det_elev.
    for band in sorted(h84.BANDS.values(), key=len, reverse=True):
        if name.startswith("DVA2_" + band + "_") or name.startswith("HVA_" + band + "_") or name.startswith("COH_" + band):
            return band
    return None


def surface_channel_names(names):
    return sorted(n for n in names if channel_band(n) in {"det_elev", "det_elev_slope"})


def tilt_depth_from_angle(theta, eligible, *, cap_m=5_000.0, cell_m=100.0):
    """Rasterised nearest-contour approximation to half the +/-45-degree TDR contour spacing."""
    theta = np.asarray(theta, np.float32)
    eligible = np.asarray(eligible, bool)
    if theta.ndim != 2 or theta.shape != eligible.shape:
        raise ValueError("theta and eligible must be same-shaped 2-D arrays")
    if not np.isfinite(theta[eligible]).all():
        raise ValueError("theta is non-finite on eligible support")
    pos45 = eligible & (theta >= np.float32(np.pi / 4.0))
    neg45 = eligible & (theta <= np.float32(-np.pi / 4.0))
    if int(pos45.sum()) == 0 or int(neg45.sum()) == 0:
        raise ValueError("tilt-depth proxy needs both +/-45 degree contour sets")
    dpos = ndi.distance_transform_edt(~pos45)
    dneg = ndi.distance_transform_edt(~neg45)
    depth = np.minimum(0.5 * (dpos + dneg) * float(cell_m), float(cap_m)).astype(np.float32)
    central = eligible & (np.abs(theta) <= np.float32(np.pi / 4.0))
    depth[~central] = 0.0
    proximity = np.exp(-np.abs(theta) / np.float32(np.pi / 4.0)).astype(np.float32)
    proximity[~eligible] = 0.0
    depth[~eligible] = 0.0
    return depth, proximity, dict(positive_45_cells=int(pos45.sum()), negative_45_cells=int(neg45.sum()),
                                  central_band_cells=int(central.sum()))


def tilt_depth_features(store, eligible):
    """Registered rasterised nearest-contour tilt-depth proxy using cached band 3/9 only."""
    band_h = np.asarray(store.feature_grid("raw_band_03"), np.float32)
    band_v = np.asarray(store.feature_grid("raw_band_09"), np.float32)
    horizontal = np.abs(band_h)
    median_h = float(np.median(horizontal[eligible]))
    eps = max(1e-6, 0.01 * median_h)
    theta = np.arctan2(band_v, horizontal + eps).astype(np.float32)
    depth, zero_proximity, contour_counts = tilt_depth_from_angle(theta, eligible)
    if not np.isfinite(depth[eligible]).all() or not np.isfinite(zero_proximity[eligible]).all():
        raise SystemExit("non-finite tilt-depth channel")
    rec = dict(stage="tilt_depth", generated_utc=now(), source_features=["raw_band_03", "raw_band_09"],
               source_sha256={n: store.manifest["feature_sha256"][n] for n in ("raw_band_03", "raw_band_09")},
               formula="theta=atan2(band9,abs(band3)+0.01*median(abs(band3)[eligible])); depth_proxy=0.5*(distance_to_+45+distance_to_-45)*100m, capped at 5000m and set 0 outside |theta|<=45deg; proximity=exp(-abs(theta)/(pi/4))",
               epsilon=eps, median_horizontal_gradient=median_h, **contour_counts,
               depth_proxy_m=dict(p50=float(np.median(depth[eligible])), p95=float(np.quantile(depth[eligible], .95)),
                                  p99=float(np.quantile(depth[eligible], .99)), max=float(depth[eligible].max())),
               theta_range_rad=[float(theta[eligible].min()), float(theta[eligible].max())],
               contour_support_note=f"The raster contains {contour_counts['positive_45_cells']} +45-degree and {contour_counts['negative_45_cells']} -45-degree threshold cells; these counts are disclosed, not treated as connected contours.",
               caveat="A nearest-contour raster proxy, not a connected contour pairing or validated source-depth inversion.")
    dump("tilt_depth", rec)
    return {"tilt_depth_proxy_m": depth, "tilt_zero_proximity": zero_proximity}, theta


def gather_matrix(store, bank, flat_rows, store_names, channel_names=(), custom=None):
    flat_rows = np.asarray(flat_rows, np.int64)
    parts = []
    if store_names:
        parts.append(store.gather(flat_rows, store_names))
    if channel_names:
        idx = store.inverse[flat_rows]
        if (idx < 0).any():
            raise ValueError("requested channel row outside FeatureStore eligible footprint")
        parts.append(bank.gather(idx, channel_names))
    if custom:
        parts.append(np.column_stack([np.asarray(a, np.float32).ravel()[flat_rows] for a in custom.values()]))
    if not parts:
        return np.empty((len(flat_rows), 0), np.float32)
    out = np.ascontiguousarray(np.hstack(parts), dtype=np.float32)
    if not np.isfinite(out).all():
        raise ValueError("non-finite model feature matrix")
    return out


def learner_specs(va, vb, surface_channels, custom):
    return {
        "pre_A": ("A", va, (), custom),
        "pre_B": ("B", vb, surface_channels, None),
        "h84_B_DVA2": ("B", vb, h84.DVA2, None),
    }


def canary_feature_specs(va, vb, surface_channels, custom):
    specs = []
    specs.extend(("view_A", name, (name,), (), None) for name in va)
    specs.extend(("view_A", name, (), (), {name: custom[name]}) for name in custom)
    specs.extend(("strict_view_B", name, (name,), (), None) for name in vb)
    specs.extend(("strict_view_B", name, (), (name,), None) for name in surface_channels)
    # Every channel in the historical best comparator is screened too, even where it is mixed-view by content.
    specs.extend(("H84_B_DVA2_control", name, (), (name,), None) for name in h84.DVA2)
    return specs


def stage_canary():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    bank, surface_channels = ensure_channels(store, eligible)
    custom, _theta = tilt_depth_features(store, eligible)
    specs = canary_feature_specs(va, vb, surface_channels, custom)
    catd = ndi.distance_transform_edt(~cat)
    rng = np.random.default_rng(SEED + 970)
    out = dict(stage="canary", evidence_class="LEAKAGE-CANARY AUC (not HOLDOUT-DTI)",
               alarm_auc=CANARY_BAR, generated_utc=now(), folds=[])
    max_auc = 0.0
    alarms = []
    for fold in folds:
        f = int(fold["fold"])
        pos = np.flatnonzero((fold["truth"] & fold["region"] & eligible).ravel())
        neg = np.flatnonzero((fold["region"] & eligible & ~cat & (catd > 5)).ravel())
        if len(pos) < 100 or len(neg) < 100:
            raise SystemExit(f"fold {f}: canary has insufficient held-out positives/negatives")
        rr = np.random.default_rng(SEED + 970 + f)
        pos = rr.choice(pos, min(20_000, len(pos)), replace=False)
        neg = rr.choice(neg, min(40_000, len(neg)), replace=False)
        rows = np.concatenate((pos, neg))
        y = np.r_[np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)]
        per_feature = {}
        for view, name, names_store, names_ch, custom_one in specs:
            X = gather_matrix(store, bank, rows, names_store, names_ch, custom_one)
            values = X[:, 0]
            auc = float(roc_auc_score(y, values))
            di = max(auc, 1.0 - auc)
            key = f"{view}::{name}"
            per_feature[key] = dict(view=view, feature=name, auc=auc, direction_insensitive_auc=di)
            max_auc = max(max_auc, di)
            if di > CANARY_BAR:
                alarms.append(dict(fold=f, view=view, feature=name, auc=auc, direction_insensitive_auc=di))
        out["folds"].append(dict(fold=f, n_heldout_positive_sample=int(len(pos)),
                                 n_labeled_negative_sample=int(len(neg)), features=per_feature))
        fold_max = max(r["direction_insensitive_auc"] for r in per_feature.values())
        log(f"fold {f}: leakage canary max={fold_max:.4f}, features={len(per_feature)}")
    out.update(max_direction_insensitive_auc=max_auc, alarms=alarms, passed=not alarms,
               interpretation="AUC >0.90 is treated as leakage until disproven; no feature is silently dropped.",
               finished_utc=now())
    dump("canary", out)
    if alarms:
        log(f"canary STOP: {len(alarms)} feature/fold alarms")
    else:
        log(f"canary PASS: maximum direction-insensitive AUC={max_auc:.4f}")
    return out


def make_grid(store, values):
    return base.to_grid(store.flat_idx, values, store.valid.shape)


def predict_all(store, bank, model, store_names, channel_names=(), custom=None, chunk=200_000):
    flat = store.flat_idx
    out = np.empty(len(flat), np.float32)
    for start in range(0, len(flat), chunk):
        rows = flat[start:start + chunk]
        X = gather_matrix(store, bank, rows, store_names, channel_names, custom)
        out[start:start + len(rows)] = model.predict_proba(X)[:, 1].astype(np.float32)
    return make_grid(store, out)


def feature_bank_specs(va, vb, surface_channels, custom):
    return {
        "pre_A": ("A", va, (), custom),
        "pre_B": ("B", vb, surface_channels, None),
        "h84_B_DVA2": ("B", vb, h84.DVA2, None),
    }


def fit_one(store, bank, rows, y, view, names_store, names_ch, custom, seed):
    model = base.learner_for(view, seed)
    X = gather_matrix(store, bank, rows, names_store, names_ch, custom)
    model.fit(X, y)
    del X
    return model


def add_pseudo_rows(rows, y, pseudo_flat):
    pseudo_flat = np.asarray(pseudo_flat, np.int64)
    if not len(pseudo_flat):
        return rows, y
    # The model sample is <=80k and the selected cap is <=2k; a set removes conflicting sampled negatives.
    pseudo_set = set(int(x) for x in pseudo_flat.tolist())
    keep = np.fromiter((int(r) not in pseudo_set for r in rows), count=len(rows), dtype=bool)
    return np.r_[rows[keep], pseudo_flat], np.r_[y[keep], np.ones(len(pseudo_flat), np.int8)]


def stage_fit():
    check_prereg()
    canary_path = EVID / "h97_canary.json"
    if not canary_path.exists():
        raise SystemExit("run canary first")
    canary = json.loads(canary_path.read_text())
    if not canary.get("passed"):
        raise SystemExit("H97 leakage canary failed; no fit permitted")
    _reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    bank, surface_channels = ensure_channels(store, eligible)
    custom, _theta = tilt_depth_features(store, eligible)
    catd = ndi.distance_transform_edt(~cat)
    feature_specs = feature_bank_specs(va, vb, surface_channels, custom)
    out = dict(stage="fit", generated_utc=now(), seed=SEED, feature_names={
                   "pre_A": {"store": va, "custom": list(custom)},
                   "pre_B_strict": {"store": vb, "h84_channels": surface_channels},
                   "H84_B_DVA2_control": {"store": vb, "h84_channels": h84.DVA2}},
               n_A=len(va) + len(custom), n_B_strict=len(vb) + len(surface_channels),
               n_H84_control=len(vb) + len(h84.DVA2), folds=[],
               evaluator=evaluator.VERSION, withheld_positive_pixels=EXPECTED_WITHHELD)
    blocks_all = []
    suff_A, suff_B = [], []
    for fold in folds:
        f = int(fold["fold"])
        t0 = time.time()
        rng = np.random.default_rng(SEED + f)
        train_rows, train_y, train_w = base.sample_for_fit(fold, cat, rng)
        if train_w is not None:
            raise SystemExit("H97 expects the shared default unit-weight learner hook")
        rec = dict(fold=f, n_train_rows=int(len(train_rows)), n_train_positive=int(train_y.sum()),
                   n_train_negative=int(len(train_y) - train_y.sum()), fits={}, metrics={})
        predictions = {}
        for arm, (view, names_store, names_ch, arm_custom) in feature_specs.items():
            t1 = time.time()
            model = fit_one(store, bank, train_rows, train_y, view, names_store, names_ch, arm_custom, SEED)
            pred_grid = predict_all(store, bank, model, names_store, names_ch, arm_custom)
            pred_path = WORK / f"pred_{arm}_f{f}.npy"
            pred_path.parent.mkdir(parents=True, exist_ok=True)
            h82.save_verified(pred_path, pred_grid)
            predictions[arm] = pred_grid
            rec["fits"][arm] = dict(seconds=float(time.time() - t1), model="run_h61.learner_for",
                                     seed=SEED, n_features=(len(names_store) + len(names_ch) + (len(arm_custom) if arm_custom else 0)),
                                     prediction_file=str(pred_path.relative_to(ROOT)),
                                     prediction_file_sha256=sha(pred_path))
            del model
            log(f"fold {f} {arm}: fitted and predicted {int(eligible.sum())} eligible pixels in {rec['fits'][arm]['seconds']:.1f}s")

        pa, pb = predictions["pre_A"], predictions["pre_B"]
        region = fold["region"] & eligible
        pos = np.flatnonzero((fold["truth"] & region).ravel())
        neg = np.flatnonzero((region & ~cat & (catd > 5)).ravel())
        y_oof = np.r_[np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)]
        sA = float(roc_auc_score(y_oof, np.r_[pa.ravel()[pos], pa.ravel()[neg]]))
        sB = float(roc_auc_score(y_oof, np.r_[pb.ravel()[pos], pb.ravel()[neg]]))
        suff_A.append(sA)
        suff_B.append(sB)
        rec["metrics"].update(out_of_quadrant_auc_A=sA, out_of_quadrant_auc_B=sB,
                              n_oof_positive=int(len(pos)), n_oof_negative=int(len(neg)))
        neg_mask = region & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        ta = float(np.quantile(pa[neg_mask], .95))
        tb = float(np.quantile(pb[neg_mask], .95))
        error_blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                                     neg_mask, f, (ta, tb), side=50, minimum=32)
        blocks_all.extend(error_blocks)
        rec["metrics"].update(negative_block_thresholds=[ta, tb], n_negative_error_blocks=len(error_blocks),
                              n_oof_labeled_negatives=int(neg_mask.sum()))

        # Conditional, whole-segment, bidirectional exchange. No held-out labels appear in these masks.
        train_domain = fold["train"] & eligible
        visible = fold["visible"]
        visible_dist = ndi.distance_transform_edt(~visible)
        pseudo_train = train_domain & ~visible & (visible_dist > 5)
        pseudo_neg = pseudo_train & ~cat
        exchange_gate = dict(canary_pass=bool(canary["passed"]),
                             independence_measured=None, independence_pass=None,
                             view_A_mean_sufficiency=None, view_A_min_fold_sufficiency=None,
                             pseudo_min_per_direction=PSEUDO_MIN_DIRECTION)
        # Independence/sufficiency are pooled after the four OOF folds. Per-fold candidates are
        # held for a second pass below; no pseudo-label is accepted until both pooled gates are known.
        rec["pseudo_candidates"] = dict(preliminary_train_negatives=int(pseudo_neg.sum()),
                                        candidate_scope="fold.train & eligible & not fold.visible & >500m from visible catalogue; hidden truth is not consulted",
                                        diagnostic_helper="gems52.spatial.whole_pseudo_segments (conditional call after pooled OOF gates)")
        out["folds"].append(rec)
        del predictions, train_rows, train_y, train_w, pa, pb
        log(f"fold {f}: OOF AUC A={sA:.4f} B={sB:.4f}; error blocks={len(error_blocks)}; {time.time()-t0:.1f}s")

    independence = spatial.independence(blocks_all, threshold=INDEP_BAR, min_blocks=20)
    mean_A, min_A = float(np.mean(suff_A)), float(np.min(suff_A))
    sufficiency = dict(mean=mean_A, min_fold=min_A, per_fold=suff_A,
                       gate_mean=A_SUFF_MEAN, gate_min_fold=A_SUFF_FOLD,
                       passes=bool(mean_A >= A_SUFF_MEAN and min_A >= A_SUFF_FOLD))
    out["independence"] = independence
    out["sufficiency_view_A"] = sufficiency
    out["sufficiency_view_B"] = dict(mean=float(np.mean(suff_B)), min_fold=float(np.min(suff_B)), per_fold=suff_B)
    exchange_allowed = bool(canary["passed"] and independence["allow_exchange"] and sufficiency["passes"])
    out["conditional_exchange_gate"] = dict(canary_pass=bool(canary["passed"]),
                                            independence_measured=bool(independence["measured"]),
                                            independence_allow_exchange=bool(independence["allow_exchange"]),
                                            view_A_sufficiency_pass=sufficiency["passes"],
                                            exchange_allowed_before_segment_counts=exchange_allowed)
    if exchange_allowed:
        log("conditional exchange gates passed; selecting whole pseudo-segments for both directions")
        # Make a second pass over folds. The stage is deterministic and reuses the verified pre-model
        # probability maps; it does not refit the pre-exchange models.
        for fold, rec in zip(folds, out["folds"]):
            f = int(fold["fold"])
            pa = np.asarray(np.load(WORK / f"pred_pre_A_f{f}.npy", mmap_mode="r"), np.float32)
            pb = np.asarray(np.load(WORK / f"pred_pre_B_f{f}.npy", mmap_mode="r"), np.float32)
            visible_dist = ndi.distance_transform_edt(~fold["visible"])
            train_domain = fold["train"] & eligible
            pseudo_train = train_domain & ~fold["visible"] & (visible_dist > 5)
            forbidden = ~train_domain | fold["visible"] | (visible_dist <= 5)
            neg = pseudo_train & ~cat
            if int(neg.sum()) < 100:
                rec["pseudo_exchange"] = dict(accepted=False, reason="too few training negative proxies")
                continue
            # Confidence/abstention thresholds are fold-local and derived only from training negatives.
            a_hi = float(np.quantile(pa[neg], .95))
            b_lo, b_hi = [float(x) for x in np.quantile(pb[neg], [.35, .65])]
            b_donor_hi = float(np.quantile(pb[neg], .95))
            a_lo, a_hi_receiver = [float(x) for x in np.quantile(pa[neg], [.35, .65])]
            a_to_b, a_receipts = spatial.whole_pseudo_segments(
                pa, pb, pseudo_train, forbidden, a_hi, b_lo, b_hi,
                side=50, min_pixels=5, cap=2000)
            b_to_a, b_receipts = spatial.whole_pseudo_segments(
                pb, pa, pseudo_train, forbidden, b_donor_hi, a_lo, a_hi_receiver,
                side=50, min_pixels=5, cap=2000)
            accepted = len(a_to_b) >= PSEUDO_MIN_DIRECTION and len(b_to_a) >= PSEUDO_MIN_DIRECTION
            rec["pseudo_exchange"] = dict(accepted=accepted, min_pixels_per_direction=PSEUDO_MIN_DIRECTION,
                A_to_B_pixels=int(len(a_to_b)), B_to_A_pixels=int(len(b_to_a)),
                A_to_B_components=a_receipts, B_to_A_components=b_receipts,
                thresholds=dict(A_donor_q95=a_hi, B_receiver_q35_q65=[b_lo, b_hi],
                                B_donor_q95=b_donor_hi, A_receiver_q35_q65=[a_lo, a_hi_receiver]),
                helper="gems52.spatial.whole_pseudo_segments", block_side_px=50, component_min_px=5,
                cap_per_direction=2000, training_domain_buffer_px=80, visible_catalogue_exclusion_px=5,
                hidden_labels_used=False)
            if accepted:
                # Remove any sampled catalogue-zero negative that becomes a pseudo-positive before append.
                train_rng = np.random.default_rng(SEED + f)
                rows, y, w = base.sample_for_fit(fold, cat, train_rng)
                if w is not None:
                    raise SystemExit("unexpected sample weights during conditional exchange")
                rows_A, y_A = add_pseudo_rows(rows, y, b_to_a)  # B donates to A
                rows_B, y_B = add_pseudo_rows(rows, y, a_to_b)  # A donates to B
                for arm, view, names_store, names_ch, custom_map, rr, yy, seed in (
                        ("post_A", "A", va, (), custom, rows_A, y_A, SEED + 1000 + f),
                        ("post_B", "B", vb, surface_channels, None, rows_B, y_B, SEED + 1000 + f)):
                    model = fit_one(store, bank, rr, yy, view, names_store, names_ch, custom_map, seed)
                    pred_grid = predict_all(store, bank, model, names_store, names_ch, custom_map)
                    path = WORK / f"pred_{arm}_f{f}.npy"
                    h82.save_verified(path, pred_grid)
                    rec.setdefault("post_fits", {})[arm] = dict(seed=seed, n_train=int(len(rr)), n_pseudo=int(len(rr)-len(rows)),
                                                                  file=str(path.relative_to(ROOT)), sha256=sha(path))
                    del model, pred_grid
            del pa, pb
        all_accepted = all(bool(r.get("pseudo_exchange", {}).get("accepted")) for r in out["folds"])
        out["conditional_exchange_gate"]["exchange_allowed_after_segment_counts"] = all_accepted
        if not all_accepted:
            out["conditional_exchange_gate"]["reason"] = "at least one fold/direction fell below 200; whole exchange not treated as a promotion arm"
            # If one fold cannot support both directions, use the pre-exchange models in every fold.
            for fold in folds:
                f = int(fold["fold"])
                for arm in ("post_A", "post_B"):
                    path = WORK / f"pred_{arm}_f{f}.npy"
                    path.unlink(missing_ok=True)
    else:
        out["conditional_exchange_gate"]["reason"] = (
            "exchange abandoned: canary, spatial-block independence and View-A sufficiency are all required")

    # If no full, all-fold exchange passed, post predictions are exact aliases of the pre predictions.
    exchange_used = bool(out["conditional_exchange_gate"].get("exchange_allowed_after_segment_counts", exchange_allowed))
    if not exchange_used:
        for fold in folds:
            f = int(fold["fold"])
            for src, dst in (("pre_A", "post_A"), ("pre_B", "post_B")):
                srcp, dstp = WORK / f"pred_{src}_f{f}.npy", WORK / f"pred_{dst}_f{f}.npy"
                if not dstp.exists():
                    shutil.copyfile(srcp, dstp)
    out["pseudo_label_training_used"] = exchange_used
    out["finished_utc"] = now()
    dump("fit", out)
    dump("independence", dict(stage="independence", generated_utc=now(), instrument="gems52.spatial.independence",
         block_side_px=50, minimum_negatives_per_block=32, min_blocks=20, max_abs_rho_stop=INDEP_BAR,
         negative_class="held-out catalogue-zero proxies, not verified fault absence", result=independence))
    dump("sufficiency", dict(stage="view_A_sufficiency", generated_utc=now(), result=sufficiency,
         note="OOF AUC tests the mapped catalogue population; it does not prove off-catalogue fault sufficiency."))
    log(json.dumps({"canary_max": canary["max_direction_insensitive_auc"], "view_A_sufficiency": sufficiency,
                    "independence_max_abs_correlation": independence.get("max_abs_correlation"),
                    "independence_allow_exchange": independence.get("allow_exchange"),
                    "pseudo_label_training_used": exchange_used}, default=float))
    return out


def rank_on_mask(values, mask):
    out = np.full(mask.shape, -1.0, np.float32)
    v = np.asarray(values, np.float32)[mask]
    if not len(v):
        return out
    out[mask] = ((rankdata(v, method="average") - 0.5) / len(v)).astype(np.float32)
    return out


def compose_disagreement(rA, rB, mask):
    """Frozen H97 rank blend; a bounded A-only boost, never max(A,B) union."""
    rA, rB, mask = np.asarray(rA, np.float32), np.asarray(rB, np.float32), np.asarray(mask, bool)
    if rA.shape != rB.shape or rA.shape != mask.shape:
        raise ValueError("rank fields and allowed mask must match")
    aonly = mask & (rA >= 0.95) & (rB >= 0.35) & (rB <= 0.65)
    boost = np.where(aonly, np.clip((rA - 0.95) / 0.05, 0.0, 1.0), 0.0).astype(np.float32)
    field = np.full(mask.shape, -1.0, np.float32)
    field[mask] = 0.80 * np.clip(rB[mask], 0.0, 1.0) + 0.20 * boost[mask]
    return field, aonly


def allowed_holdout(fold, valid, ring_px):
    visible_dist = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (visible_dist > ring_px)


def place_arm(field, allowed, k=K_FOLD):
    f = np.where(allowed, np.nan_to_num(field, nan=-1.0, neginf=-1.0, posinf=-1.0), -1.0).astype(np.float32)
    return nodes.spacing_select(f, allowed, k, min_px=3.0)


def stage_holdout():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    fit = json.loads((EVID / "h97_fit.json").read_text())
    bank, surface_channels = ensure_channels(store, eligible)
    terms = {name: None for name in ("h97_aligned_disagreement", "single_A_pre", "single_B_pre_strict",
                                     "single_A_post", "single_B_post_strict", "union_max_pre",
                                     "a_only_disagreement", "h84_B_DVA2_control", "random")}
    out = dict(stage="holdout", evidence_class="HOLDOUT-DTI", evaluator=evaluator.VERSION,
               metric=dict(alpha=0.2, beta=0.8, triangular_kernel_m=300),
               withheld_positive_pixels=EXPECTED_WITHHELD, budget_per_fold=K_FOLD,
               minimum_spacing_px=3.0, visible_catalogue_mask="exact; via shared evaluator and allowed mask",
               implementation_hashes=evaluator.implementation_hashes(), folds=[], generated_utc=now())
    catd = ndi.distance_transform_edt(~cat)
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_holdout(fold, eligible, ring_px)
        if not allowed.any():
            raise SystemExit(f"fold {f}: empty holdout allowed mask")
        pred = {arm: np.asarray(np.load(WORK / f"pred_{arm}_f{f}.npy", mmap_mode="r"), np.float32)
                for arm in ("pre_A", "pre_B", "post_A", "post_B", "h84_B_DVA2")}
        rA_pre = rank_on_mask(pred["pre_A"], allowed)
        rB_pre = rank_on_mask(pred["pre_B"], allowed)
        rA_post = rank_on_mask(pred["post_A"], allowed)
        rB_post = rank_on_mask(pred["post_B"], allowed)
        rInc = rank_on_mask(pred["h84_B_DVA2"], allowed)
        candidate, aonly = compose_disagreement(rA_post, rB_post, allowed)
        union = np.where(allowed, np.maximum(rA_pre, rB_pre), -1.0).astype(np.float32)
        a_only_field = np.where(aonly, rA_post, -1.0).astype(np.float32)
        fields = dict(h97_aligned_disagreement=candidate,
                      single_A_pre=np.where(allowed, rA_pre, -1.0),
                      single_B_pre_strict=np.where(allowed, rB_pre, -1.0),
                      single_A_post=np.where(allowed, rA_post, -1.0),
                      single_B_post_strict=np.where(allowed, rB_post, -1.0),
                      union_max_pre=union, a_only_disagreement=a_only_field,
                      h84_B_DVA2_control=np.where(allowed, rInc, -1.0))
        fields["random"] = np.full(eligible.shape, -1.0, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        fields["random"].ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
        fold_rec = dict(fold=f, allowed_pixels=int(allowed.sum()), a_only_stratum_pixels=int(aonly.sum()), arms={})
        for arm, field in fields.items():
            arm_allowed = aonly if arm == "a_only_disagreement" else allowed
            emitted = place_arm(field, arm_allowed)
            result, term = evaluator.evaluate(emitted.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            fold_rec["arms"][arm] = dict(result, evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
                                         placed=int(emitted.sum()), allowed_pixels=int(arm_allowed.sum()))
            log(f"fold {f} {arm}: HOLDOUT-DTI={result['dti']:.6f}, placed={int(emitted.sum())}")
        out["folds"].append(fold_rec)
        del pred
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED,
                                       candidate="h97_aligned_disagreement", evidence_class="HOLDOUT-DTI")
    out["pooled"] = summary
    score = summary["scores"]["h97_aligned_disagreement"]["dti"]
    inc = summary["scores"]["h84_B_DVA2_control"]["dti"]
    diff = summary["paired_differences"]["h84_B_DVA2_control"]
    hist = json.loads((EVID / "h84_holdout.json").read_text())
    h84_hist = float(hist["pooled"]["scores"]["B_DVA2"]["dti"])
    out["H84_control_reproduction"] = dict(evidence_class="HOLDOUT-DTI", evaluator=evaluator.VERSION,
        withheld_positive_pixels=EXPECTED_WITHHELD, historical_H84_B_DVA2=h84_hist,
        refit_H84_B_DVA2_same_H97_mask=inc, abs_delta=abs(inc-h84_hist), tolerance=0.001,
        PASS=bool(abs(inc-h84_hist) <= 0.001), historical_H84_ci95=hist["pooled"]["scores"]["B_DVA2"]["ci95"],
        refit_ci95=summary["scores"]["h84_B_DVA2_control"]["ci95"],
        note="The refit control is the same-run comparator; H84's recorded score remains historical, not organizer-confirmed.")
    out["promotion_gate"] = dict(candidate_score=score, historical_bar=0.19282907051926573,
        refit_control=inc, candidate_minus_refit_delta=diff["delta"], paired_ci95=diff["ci95"],
        exceeds_historical_bar=bool(score > 0.19282907051926573),
        paired_lower_ci_above_zero=bool(diff["ci95"][0] > 0),
        control_reproduces=out["H84_control_reproduction"]["PASS"],
        HOLDOUT_GATE_PASS=bool(score > 0.19282907051926573 and diff["ci95"][0] > 0 and out["H84_control_reproduction"]["PASS"]))
    out["finished_utc"] = now()
    dump("holdout", out)
    log("H97 holdout primary vs matched controls: " + json.dumps({
        k: {"dti": v["dti"], "ci95": v["ci95"]} for k, v in summary["scores"].items()}, default=float))
    log("H84 same-run control: " + json.dumps(out["H84_control_reproduction"], default=float))
    log("H97 promotion gate: " + json.dumps(out["promotion_gate"], default=float))
    return out


def stitch_prediction(arm, folds, eligible):
    grid = np.full(eligible.shape, np.nan, np.float32)
    covered = np.zeros(eligible.shape, bool)
    for fold in folds:
        pred = np.asarray(np.load(WORK / f"pred_{arm}_f{int(fold['fold'])}.npy", mmap_mode="r"), np.float32)
        region = fold["region"] & eligible
        if np.any(covered & region):
            raise SystemExit("fold regions overlap; cannot build an out-of-fold surface")
        grid[region] = pred[region]
        covered |= region
    if not np.array_equal(covered, eligible) or not np.isfinite(grid[eligible]).all():
        raise SystemExit(f"stitched OOF surface does not cover the eligible mask for {arm}: {int(covered.sum())}/{int(eligible.sum())}")
    return grid


def spearman_exact(a, b, mask):
    x, y = np.asarray(a, np.float32)[mask], np.asarray(b, np.float32)[mask]
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    rx = rankdata(x, method="average").astype(np.float64)
    ry = rankdata(y, method="average").astype(np.float64)
    rx -= rx.mean(); ry -= ry.mean()
    return float(np.dot(rx, ry) / np.sqrt(np.dot(rx, rx) * np.dot(ry, ry)))


def jaccard(a, b):
    union = int((a | b).sum())
    return float((a & b).sum() / max(union, 1))


def not_union_metrics(candidate, union, single_a, single_b, surface, union_field, eligible):
    """Keep the registered union comparison distinct from single-view equality diagnostics."""
    candidate = np.asarray(candidate, dtype=bool)
    union = np.asarray(union, dtype=bool)
    single_a = np.asarray(single_a, dtype=bool)
    single_b = np.asarray(single_b, dtype=bool)
    subset_union = bool((candidate & ~union).sum() == 0)
    equal_union = bool(np.array_equal(candidate, union))
    equal_single_a = bool(np.array_equal(candidate, single_a))
    equal_single_b = bool(np.array_equal(candidate, single_b))
    return dict(
        dots=int(candidate.sum()), union_dots=int(union.sum()),
        shared_with_union=int((candidate & union).sum()),
        jaccard_with_union=jaccard(candidate, union),
        subset_of_union=subset_union, equal_union=equal_union,
        equal_single_A=equal_single_a, equal_single_B=equal_single_b,
        jaccard_with_single_A=jaccard(candidate, single_a),
        jaccard_with_single_B=jaccard(candidate, single_b),
        spearman_candidate_vs_union_field=spearman_exact(
            surface, np.where(eligible, union_field, 0.0), eligible),
        # Preregistered criterion: a non-equal, non-subset placement is not simply
        # the union. Equality with a single-view placement is reported separately.
        not_union_pass=bool(not equal_union and not subset_union),
        distinct_from_both_single_view_placements=bool(not equal_single_a and not equal_single_b),
        not_union_definition="candidate placement is not identical to and not a subset of union-max placement",
    )


def git_blob_sha1(path):
    path = Path(path)
    n = path.stat().st_size
    h = hashlib.sha1()
    h.update(f"blob {n}\0".encode())
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_prior_inventory():
    """Fail closed unless every frozen source blob and every eligible raster is verified."""
    reg = check_prereg()
    pin = reg["frozen_prior_inventory"]
    inv_path = ROOT / pin["path"]
    inventory = json.loads(inv_path.read_text())
    receipt_path = ROOT / "work/h61/prior_fetch_receipt.json"
    if not receipt_path.exists():
        raise SystemExit("verified full prior census missing; restore and verify before any lane check")
    receipt = json.loads(receipt_path.read_text())
    entries = inventory["entries"]
    eligible_entries = [e for e in entries if e.get("eligible")]
    source_repositories = len({a["repo"] for e in entries for a in e["aliases"]})
    if (source_repositories != pin["source_repositories"] or
            len(entries) != pin["blob_entries"] or len(eligible_entries) != pin["eligible_aligned_rasters"] or
            receipt.get("inventory") != pin["path"] or receipt.get("n_entries") != len(entries) or
            receipt.get("n_errors") != 0 or len(receipt.get("files", {})) != len(entries)):
        raise SystemExit("incomplete or error-bearing prior inventory receipt; refusing registry lane pass")
    rows = receipt["files"]
    git_receipt_path = ROOT / "work/ctd5/git_restore_receipt.json"
    git_receipt = None
    if git_receipt_path.exists():
        git_receipt = json.loads(git_receipt_path.read_text())
        if (git_receipt.get("entries") != len(entries) or git_receipt.get("failures") or
                int(git_receipt.get("restored", 0)) + int(git_receipt.get("verified_cached", 0)) != len(entries)):
            raise SystemExit("Git transport restore receipt is incomplete; refusing registry lane pass")
    eligible_checked = 0
    for e in entries:
        blob = e["blob"]
        state = rows.get(blob)
        if not state or state.get("status", "").startswith("error"):
            raise SystemExit(f"frozen prior blob {blob} is absent or errored in the restore receipt")
        path = ROOT / state["dest"]
        if not path.exists() or path.stat().st_size != int(e["aliases"][0]["bytes"]):
            raise SystemExit(f"frozen prior blob {blob} is missing or has the wrong byte count")
        if git_blob_sha1(path) != blob:
            raise SystemExit(f"frozen prior blob {blob} failed current Git-blob SHA-1 verification")
        if e.get("eligible"):
            if sha(path) != e["sha256"]:
                raise SystemExit(f"eligible prior blob {blob} failed current census SHA-256 verification")
            if (state.get("file_sha_matches_census") is not True or
                    state.get("shape_matches_census") is not True or
                    state.get("crs_matches_census") is not True or
                    list(state.get("decoded_shape", [])) != list(e.get("shape", [])) or
                    state.get("decoded_crs") != e.get("crs")):
                raise SystemExit(f"eligible prior blob {blob} lacks matching decoded shape/CRS/hash receipt")
            eligible_checked += 1
    result = dict(stage="prior_inventory_restore", generated_utc=now(),
        inventory=pin["path"], inventory_sha256=sha(inv_path), inventory_bytes=inv_path.stat().st_size,
        frozen_blob_entries=len(entries), eligible_aligned_rasters=len(eligible_entries),
        source_repositories=pin["source_repositories"], git_blob_sha1_verified=len(entries),
        eligible_file_sha256_verified=eligible_checked, census_shape_and_crs_verified=eligible_checked,
        receipt=str(receipt_path.relative_to(ROOT)), receipt_entries=receipt["n_entries"],
        receipt_errors=receipt["n_errors"], receipt_file_sha_matches=receipt["n_census_sha_is_file_sha"],
        receipt_decoded_sha_matches=receipt["n_census_sha_is_decoded_sha"],
        census_sha_column=receipt.get("sha_column_reading"),
        git_transport_receipt=str(git_receipt_path.relative_to(ROOT)) if git_receipt else None,
        git_transport=git_receipt.get("transport") if git_receipt else "shared prior fetcher receipt; transport not independently recorded",
        complete=True, organizer_authenticated=False,
        scope="The frozen supplied owner-repository census only; inaccessible private/release/unlinked artifacts are not proven absent.")
    dump("prior_restore", result)
    return result


def stage_prior_check():
    result = verify_prior_inventory()
    log("frozen prior inventory PASS: " + json.dumps(result, default=float))
    return result


def registry_paths():
    restore = verify_prior_inventory()
    paths, meta = h84.full_registry()
    if (meta.get("census_entries") != restore["frozen_blob_entries"] or
            meta.get("census_errors") != 0 or
            meta.get("census_present") != restore["eligible_aligned_rasters"]):
        raise SystemExit(f"incomplete registry coverage ({meta}); refusing lane verdict")
    # Include the public download mirror; shared lane_report deduplicates identical decoded rasters.
    dd = ROOT / "docs/downloads"
    downloads = sorted(dd.glob("*.tif")) if dd.exists() else []
    seen = {p.resolve() for p in paths}
    for p in downloads:
        if p.resolve() not in seen:
            paths.append(p); seen.add(p.resolve())
    meta.update(prior_restore=restore, docs_downloads_added=len(downloads), n_total_paths=len(paths))
    return paths, meta


def stage_build():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    fit = json.loads((EVID / "h97_fit.json").read_text())
    hold = json.loads((EVID / "h97_holdout.json").read_text())
    postA = stitch_prediction("post_A", folds, eligible)
    postB = stitch_prediction("post_B", folds, eligible)
    preA = stitch_prediction("pre_A", folds, eligible)
    preB = stitch_prediction("pre_B", folds, eligible)
    incumbent = stitch_prediction("h84_B_DVA2", folds, eligible)
    catd = ndi.distance_transform_edt(~cat)
    with rasterio.open(SAMPLE) as ref:
        sample_domain = np.isfinite(ref.read(1)) & (ref.read(1) > -1e38)
        transform = ref.transform
    pool = eligible & sample_domain & ~cat & (catd > RING_PX)
    if int(pool.sum()) <= K_TOTAL:
        raise SystemExit("emission pool too small")
    rA, rB = rank_on_mask(postA, pool), rank_on_mask(postB, pool)
    rInc = rank_on_mask(incumbent, pool)
    pooled_field, aonly = compose_disagreement(rA, rB, pool)
    surface = np.where(eligible, np.maximum(pooled_field, 0.0), 0.0).astype(np.float32)
    if not np.isfinite(surface).all() or surface.min() < 0 or surface.max() > 1:
        raise SystemExit("full surface field is not finite in [0,1]")
    h82.save_verified(WORK / "full_surface.npy", surface)
    h82.save_verified(WORK / "pool.npy", pool)
    h82.save_verified(WORK / "a_only.npy", aonly)
    # The cross-fitted surface gate is run before any dot placement.
    paths, pmeta = registry_paths()
    log(f"surface lane preflight: {len(paths)} aligned/registered raster paths; registry={pmeta}")
    surface_lane = gates.lane_report(surface, eligible, paths, sample=SAMPLE, phase="surface", log=log)
    dump("lane_surface", surface_lane)
    rec = dict(stage="build", generated_utc=now(), pool_pixels=int(pool.sum()),
               eligible_pixels=int(eligible.sum()), a_only_stratum_pixels=int(aonly.sum()),
               surface_candidate_decoded_sha256=surface_lane.get("candidate_decoded_sha256"),
               full_registry=pmeta, surface_lane_literal=surface_lane["literal"]["verdict"],
               surface_lane_policy=surface_lane["policy"]["verdict"],
               surface_max_spearman=surface_lane["literal"]["max_spearman"],
               surface_duplicate_paths=surface_lane["literal"].get("rank_offenders", []),
               surface_registry_errors=surface_lane.get("error_count"),
               h84_historical_control=hold["H84_control_reproduction"],
               no_dot_placement_before_surface_check=True)
    surface_stop = (surface_lane.get("error_count", 1) > 0 or
                    surface_lane["literal"]["verdict"] != "PASS" or
                    (surface_lane["literal"]["max_spearman"] is not None and
                     surface_lane["literal"]["max_spearman"] > 0.90))
    if surface_stop:
        rec["stopped"] = ("surface registry incomplete/error-bearing; stop before placement" if surface_lane.get("error_count", 1) > 0
                           else "surface uniqueness gate is DUPLICATE/STOP; stop before placement")
        dump("build", rec)
        log(rec["stopped"])
        return rec
    # Placement only after the surface correlation gate.
    score = np.where(pool, surface, -1.0).astype(np.float32)
    dots = nodes.spacing_select(score, pool, K_TOTAL, min_px=3.0, log=log)
    if int(dots.sum()) != K_TOTAL:
        rec["placement_shortfall"] = dict(requested=K_TOTAL, placed=int(dots.sum()))
    h82.save_verified(WORK / "final_dots.npy", dots.astype(np.float32))
    dots_lane = gates.lane_report(dots.astype(np.float32), eligible, paths, sample=SAMPLE, phase="dots", log=log)
    uniqueness = gates.uniqueness_report(dots.astype(np.float32), paths)
    # Equal-budget top-k controls over the same eligible, 200 m collar and spacing.
    a_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(rA, nan=-1.0), -1.0).astype(np.float32), pool, K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(rB, nan=-1.0), -1.0).astype(np.float32), pool, K_TOTAL, min_px=3.0)
    union_field = np.where(pool, np.maximum(np.nan_to_num(rA, nan=-1.0), np.nan_to_num(rB, nan=-1.0)), -1.0)
    union_dots = nodes.spacing_select(union_field.astype(np.float32), pool, K_TOTAL, min_px=3.0)
    not_union = not_union_metrics(
        dots, union_dots, a_dots, b_dots, surface,
        np.maximum(rA, rB), eligible)
    rec.update(dots=int(dots.sum()),
        dots_lane_literal=dots_lane["literal"]["verdict"],
        dots_lane_policy=dots_lane["policy"]["verdict"],
        dots_registry_errors=dots_lane.get("error_count"),
        dots_max_near_3px_fraction=dots_lane["literal"]["max_near_3px_fraction"],
        dots_near_offenders=dots_lane["literal"].get("near_offenders", []),
        uniqueness=dict(audit_complete=uniqueness["audit_complete"],
            distinct_from_every_comparable_prior=uniqueness["distinct_from_every_comparable_prior"],
            identical_to_a_prior=uniqueness["identical_to_a_prior"],
            n_priors_checked=uniqueness["n_priors_checked"], n_priors_compared=uniqueness["n_priors_compared"],
            novel_fraction=uniqueness["novel_fraction"], equals_literal_prior_union=uniqueness["equals_literal_prior_union"],
            support_novelty_gate_ok=uniqueness["support_novelty_gate_ok"]),
        not_the_union=not_union,
        stop_duplicate=bool(dots_lane["literal"]["verdict"].upper().startswith("DUPLICATE") or
                            dots_lane.get("error_count", 1) > 0 or not uniqueness["audit_complete"] or
                            not uniqueness["distinct_from_every_comparable_prior"]),
        registry_full=pmeta)
    dump("lane_dots", dots_lane)
    dump("uniqueness", uniqueness)
    dump("build", rec)
    log("dots lane: " + json.dumps({"literal": rec["dots_lane_literal"], "policy": rec["dots_lane_policy"],
                                   "near": rec["dots_max_near_3px_fraction"], "not_union": not_union}, default=float))
    return rec


def write_a_only_reasoning(store, dots, aonly, postA, postB, theta, depth, transform, catd, ring_px):
    csv_path = ROOT / "docs/downloads" / "h97-a-only-reasoning.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    ys, xs = np.nonzero(dots.astype(bool) & aonly)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["row", "col", "easting_m", "northing_m", "A_probability", "B_probability",
                         "tilt_angle_deg", "tilt_depth_proxy_m", "distance_to_catalogue_m",
                         "geological_reasoning", "named_non_fault_mimics", "falsifier", "evidence_class"])
        for y, x in zip(ys, xs):
            writer.writerow([int(y), int(x), round(float(transform.c + (x + .5) * transform.a), 1),
                round(float(transform.f + (y + .5) * transform.e), 1),
                round(float(postA[y, x]), 6), round(float(postB[y, x]), 6),
                round(float(np.degrees(theta[y, x])), 3), round(float(depth[y, x]), 1),
                round(float(catd[y, x] * 100.0), 1),
                "A-only geophysical/depth confidence while the surface view abstains: possible buried continuation of a magnetic contact or basement step beneath cover; reviewer lead only.",
                "Lithologic or intrusive contact, basin-fill facies boundary, alluvial-fan margin, a radiometric soil/vegetation/thickness contrast, flight-line processing artifact, road/section line, or drainage edge.",
                "Reject if field/geophysical transect shows no coherent displaced contact, the feature follows a road/drainage/flight line, or high-resolution mapping finds intact unfaulted cover.",
                "model evidence for Phase-2 geological review; not a confirmed fault"])
    return str(csv_path.relative_to(ROOT)), int(len(ys))


def stage_write():
    check_prereg()
    build_path = EVID / "h97_build.json"
    if not build_path.exists():
        raise SystemExit("run the matched holdout and full-registry build gates before write")
    build = json.loads(build_path.read_text())
    if build.get("stopped"):
        rec = dict(stage="write", generated_utc=now(), artifact_written=False, file=None, bytes=None,
            sha256=None, name=None, note=None, note_chars=None,
            validator={"PASS": False, "reason": "surface gate stopped before placement"},
            download_files=[], download_ok=False, submit_ok=False,
            submit_status="NO — surface uniqueness/inventory gate stopped before placement; no slot selected",
            stop_reason=build["stopped"], lane=dict(surface=build.get("surface_lane_literal"),
                surface_max_spearman=build.get("surface_max_spearman"), dots="not run"),
            evidence_class="no submission raster was written")
        dump("write", rec)
        log("H97 write stopped: " + rec["stop_reason"])
        return rec

    _reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    dots_path, aonly_path = WORK / "final_dots.npy", WORK / "a_only.npy"
    if not dots_path.exists() or not aonly_path.exists():
        raise SystemExit("build stopped before final placement; no GeoTIFF will be written")
    dots = np.asarray(np.load(dots_path, mmap_mode="r"), np.float32)
    aonly = np.asarray(np.load(aonly_path, mmap_mode="r"), bool)
    postA = stitch_prediction("post_A", folds, eligible)
    postB = stitch_prediction("post_B", folds, eligible)
    custom, theta = tilt_depth_features(store, eligible)
    depth = custom["tilt_depth_proxy_m"]
    catd = ndi.distance_transform_edt(~cat)
    with rasterio.open(SAMPLE) as ref:
        transform = ref.transform
    a_csv, a_rows = write_a_only_reasoning(store, dots, aonly, postA, postB, theta, depth,
                                            transform, catd, ring_px)

    lane_safe = bool(build.get("surface_lane_literal") == "PASS" and
        build.get("dots_lane_literal") == "PASS" and build.get("dots") == K_TOTAL and
        not build.get("placement_shortfall") and not build.get("stop_duplicate", True) and
        build.get("dots_registry_errors", 1) == 0 and
        build.get("uniqueness", {}).get("audit_complete", False) and
        build.get("uniqueness", {}).get("distinct_from_every_comparable_prior", False) and
        build.get("not_the_union", {}).get("not_union_pass", False))
    if not lane_safe:
        reasons = []
        if build.get("surface_lane_literal") != "PASS": reasons.append("surface registry gate not PASS")
        if build.get("dots_lane_literal") != "PASS": reasons.append("final-dot literal lane gate not PASS")
        if build.get("dots_registry_errors", 1): reasons.append("final-dot registry coverage/audit incomplete")
        if build.get("dots") != K_TOTAL or build.get("placement_shortfall"):
            reasons.append("full 37,654-dot placement was not achieved")
        if build.get("stop_duplicate", True): reasons.append("duplicate or indistinguishable raster detected")
        if not build.get("uniqueness", {}).get("distinct_from_every_comparable_prior", False): reasons.append("decoded-pattern uniqueness not established")
        if not build.get("not_the_union", {}).get("not_union_pass", False): reasons.append("not-the-union gate failed")
        if not build.get("not_the_union", {}).get("distinct_from_both_single_view_placements", False):
            reasons.append("final placement matches a single-view placement; no incremental disagreement contribution")
        rec = dict(stage="write", generated_utc=now(), artifact_written=False, file=None, bytes=None,
            sha256=None, name=None, note=None, note_chars=None,
            validator={"PASS": False, "reason": "; ".join(reasons)},
            A_only_reasoning_csv=a_csv, A_only_reasoning_rows=a_rows,
            download_files=[], download_ok=False, submit_ok=False,
            submit_status="NO — literal lane/uniqueness gate blocked release; no slot selected or spent",
            stop_reason="; ".join(reasons), lane=dict(surface=build.get("surface_lane_literal"),
                surface_max_spearman=build.get("surface_max_spearman"), dots=build.get("dots_lane_literal"),
                dots_max_near_3px_fraction=build.get("dots_max_near_3px_fraction"),
                dots_duplicate=build.get("stop_duplicate"), dots_registry_errors=build.get("dots_registry_errors")),
            uniqueness=build.get("uniqueness"), not_the_union=build.get("not_the_union"),
            evidence_class="no download/submission raster written because the strict registered gates did not pass")
        dump("write", rec)
        log("H97 write blocked: " + rec["stop_reason"])
        return rec

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = f"h97-tiltdepth-disagreement-37654px-{stamp}"
    note = "H97 tilt-depth A-only disagreement with strict surface DVA2/HVA; 200m collar, 3px spacing; research only"
    if len(name) > 140 or len(note) > 140:
        raise SystemExit("portal name/note length exceeds 140 characters")
    out_path = ROOT / "submission" / f"gems52-{name}-zeros.tif"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pred = np.nan_to_num(dots, nan=0.0).astype(np.float32)
    fit = json.loads((EVID / "h97_fit.json").read_text())
    receipt = submission_writer.write_submission(out_path, pred, SAMPLE, eligible, note=note, name=name,
         metadata=dict(round="H97", primary="H97-A", pseudo_label_training_used=fit["pseudo_label_training_used"],
                       holdout_evidence="evidence/h97_holdout.json"))
    with rasterio.open(out_path) as ds, rasterio.open(SAMPLE) as ref:
        a = ds.read(1)
        validator = dict(count=ds.count, dtype=ds.dtypes[0], crs=str(ds.crs), shape=list(ds.shape),
            transform=list(ds.transform)[:6], sample_crs=str(ref.crs), sample_shape=list(ref.shape),
            sample_transform=list(ref.transform)[:6], crs_match=ds.crs == ref.crs,
            shape_match=ds.shape == ref.shape, transform_match=ds.transform == ref.transform,
            bounds_match=ds.bounds == ref.bounds, nodata=ds.nodata, nan=int(np.isnan(a).sum()),
            infinite=int(np.isinf(a).sum()), nan_inside_footprint=int(np.isnan(a[eligible]).sum()),
            min=float(a.min()), max=float(a.max()), positive_pixels=int((a > 0).sum()),
            expected_positive_pixels=K_TOTAL,
            positive_outside_footprint=int(((a > 0) & ~eligible).sum()),
            values=sorted(np.unique(a).tolist())[:10])
    validator["PASS"] = bool(validator["count"] == 1 and validator["dtype"] == "float32" and
        validator["crs_match"] and validator["shape_match"] and validator["transform_match"] and
        validator["bounds_match"] and validator["nan"] == 0 and validator["infinite"] == 0 and
        validator["nan_inside_footprint"] == 0 and validator["min"] >= 0 and validator["max"] <= 1 and
        validator["positive_pixels"] == K_TOTAL and validator["positive_outside_footprint"] == 0)
    dl = ROOT / "docs/downloads"
    dl.mkdir(parents=True, exist_ok=True)
    tiff_dl = dl / f"h97-candidate-{stamp}.tif"
    zip_dl = dl / f"h97-candidate-{stamp}.zip"
    receipt_dl = dl / f"h97-candidate-{stamp}-receipt.json"
    shutil.copy2(out_path, tiff_dl)
    shutil.copy2(out_path.with_suffix(".zip"), zip_dl)
    shutil.copy2(out_path.with_suffix(".json"), receipt_dl)
    file_sha = sha(out_path)
    hold = json.loads((EVID / "h97_holdout.json").read_text())
    receipt_rec = dict(stage="write", generated_utc=now(), artifact_written=True,
        file=str(out_path.relative_to(ROOT)), bytes=out_path.stat().st_size, sha256=file_sha,
        name=name, note=note, note_chars=len(note), writer_receipt=receipt, validator=validator,
        A_only_reasoning_csv=a_csv, A_only_reasoning_rows=a_rows,
        download_files=[str(tiff_dl.relative_to(ROOT)), str(zip_dl.relative_to(ROOT)), str(receipt_dl.relative_to(ROOT))],
        download_ok=bool(validator["PASS"]), submit_ok=False,
        submit_status="NO — slot selection is separate and no organizer submission/receipt has occurred",
        holdout_gate=hold["promotion_gate"], canary_pass=json.loads((EVID / "h97_canary.json").read_text())["passed"],
        lane=dict(surface_literal=build["surface_lane_literal"], surface_max_spearman=build["surface_max_spearman"],
                  dots_literal=build["dots_lane_literal"], dots_max_near_3px_fraction=build["dots_max_near_3px_fraction"],
                  dots_duplicate=build["stop_duplicate"], registry_errors=build["dots_registry_errors"]),
        uniqueness=build["uniqueness"], not_the_union=build["not_the_union"],
        evidence_class="unique decoded-format candidate for research/audit only; no ORGANIZER-CONFIRMED score")
    dump("write", receipt_rec)
    log(f"GeoTIFF written: {out_path.relative_to(ROOT)} sha256={file_sha} validator={validator['PASS']} download={receipt_rec['download_ok']} submit=NO")
    return receipt_rec

def submission_card_fields(write_receipt):
    """Normalize successful and no-artifact receipts to one stable run-card schema."""
    return dict(name=write_receipt.get("name"), note=write_receipt.get("note"),
        note_chars=write_receipt.get("note_chars"),
        ok_to_download=bool(write_receipt.get("download_ok", False)),
        ok_to_submit=bool(write_receipt.get("submit_ok", False)),
        submission_slots_used=0, promoted=False)


def stage_card():
    check_prereg()
    mask = json.loads((EVID / "h97_mask.json").read_text())
    canary = json.loads((EVID / "h97_canary.json").read_text())
    fit = json.loads((EVID / "h97_fit.json").read_text())
    hold = json.loads((EVID / "h97_holdout.json").read_text())
    build = json.loads((EVID / "h97_build.json").read_text())
    wr = json.loads((EVID / "h97_write.json").read_text())
    tilt = json.loads((EVID / "h97_tilt_depth.json").read_text())
    review_path = EVID / "h97_review_passes.json"
    review_record = json.loads(review_path.read_text()) if review_path.exists() else {"passes": []}
    control = hold["H84_control_reproduction"]
    promotion = hold["promotion_gate"]
    pseudo_ok = bool(fit["pseudo_label_training_used"])
    gates_pass = bool(promotion["HOLDOUT_GATE_PASS"] and canary["passed"] and
        fit["independence"].get("allow_exchange", False) and fit["sufficiency_view_A"]["passes"] and
        build.get("surface_lane_literal", "").upper() == "PASS" and
        build.get("dots_lane_literal", "").upper() == "PASS" and
        build.get("uniqueness", {}).get("distinct_from_every_comparable_prior", False) and
        build.get("not_the_union", {}).get("not_union_pass", False) and wr["validator"]["PASS"])
    card = dict(round="H97", generated_utc=now(), preregistration=dict(file=str(PREREG.relative_to(ROOT)),
        sha256=sha(PREREG), hypothesis_document=str(DOC.relative_to(ROOT)),
        hypothesis_sha256=sha(DOC), frozen_before_any_fit=True),
        hypothesis="H97-A magnetic tilt-depth proxy as a geophysical View-A teacher; strict surface DVA2/HVA/radiometric View B; bounded A-only disagreement boost.",
        mechanism="The tilt-angle zero contour approximates a magnetic contact; half the ±45° contour separation estimates source-top depth under the ideal vertical-contact model. A map-space nearest-contour proxy is used, then A-only high confidence can add a fixed 20% score term only where B is between its 35th and 65th percentile.",
        named_non_fault_mimics=["intrusive/lithologic contact", "basin-fill facies boundary", "alluvial-fan margin", "radiometric soil/vegetation/thickness contrast", "airborne flight-line artifact", "road or drainage line"],
        method_reference="Salem et al. (2007), DOI 10.1190/1.2821934; DOI corrected from the prior H92 note's 10.1190/1.2431639.",
        eligible_pixels=mask["eligible_pixels"], withheld_positive_pixels=mask["withheld_positive_pixels"],
        tilt_depth_diagnostic=dict(
            positive_45_cells=tilt["positive_45_cells"], negative_45_cells=tilt["negative_45_cells"],
            central_band_cells=tilt["central_band_cells"], depth_proxy_m=tilt["depth_proxy_m"],
            contour_support_note=tilt["contour_support_note"]),
        holdout=hold["pooled"], H84_control_reproduction=control,
        holdout_gate=promotion, leakage_canary=dict(max_auc=canary["max_direction_insensitive_auc"], passed=canary["passed"], alarms=len(canary["alarms"])),
        independence=dict(max_abs_correlation=fit["independence"].get("max_abs_correlation"),
                          allow_exchange=fit["independence"].get("allow_exchange"),
                          n_blocks=fit["independence"].get("n_blocks")),
        view_A_sufficiency=fit["sufficiency_view_A"], pseudo_label_training_used=pseudo_ok,
        registry=dict(
            census_entries=build.get("full_registry", {}).get("census_entries"),
            census_present=build.get("full_registry", {}).get("census_present"),
            eligible_aligned_rasters=build.get("full_registry", {}).get("census_present"),
            local_artifacts=build.get("full_registry", {}).get("local_artifacts"),
            docs_downloads_added=build.get("full_registry", {}).get("docs_downloads_added"),
            total_paths=build.get("full_registry", {}).get("n_total_paths"),
            restore_errors=build.get("full_registry", {}).get("census_errors"),
            surface_literal=build.get("surface_lane_literal"),
            surface_max_spearman=build.get("surface_max_spearman"),
            dots_literal=build.get("dots_lane_literal"),
            dots_policy=build.get("dots_lane_policy"),
            dots_max_near_3px_fraction=build.get("dots_max_near_3px_fraction"),
            dots_registry_errors=build.get("dots_registry_errors"),
            stop_duplicate=build.get("stop_duplicate"),
            uniqueness=build.get("uniqueness"), not_the_union=build.get("not_the_union")),
        review_passes=review_record.get("passes", []),
        raster=dict(file=wr["file"], bytes=wr["bytes"], sha256=wr["sha256"], validator=wr["validator"]),
        submission=submission_card_fields(wr),
        verdict="negative" if not gates_pass else "eligible_for_selector_not_promoted",
        gates_pass=gates_pass,
        board_status=dict(organizer_confirmed_score=None, no_board_receipt_for_H97=True,
                          benchmark_0_3195_beaten=False, benchmark_0_3774_beaten=False,
                          statement="HOLDOUT-DTI does not demonstrate beating any public leaderboard score; no organizer result exists."),
        three_review_passes=review_record.get("passes", []),
        three_review_passes_complete=bool(review_record.get("complete", False)),
        review_record_file=str(review_path.relative_to(ROOT)) if review_path.exists() else None,
        status=("research-only; download YES for audit, submit NO; no slot selected or spent" if wr.get("download_ok") else
                "no TIFF written; download NO, submit NO; no slot selected or spent"))
    dump("run_card", card)
    log("H97 run card: " + json.dumps({"verdict": card["verdict"], "gates_pass": card["gates_pass"],
                                     "holdout_gate": promotion, "raster": card["raster"]}, default=float))
    return card


def run_all():
    stage_prior_check()
    _reg, store, _cat, eligible, _folds, _va, _vb, _ring = setup()
    ensure_channels(store, eligible)
    stage_canary()
    stage_fit()
    stage_holdout()
    stage_build()
    stage_write()
    stage_card()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stage = argv[0] if argv else "all"
    if stage == "prior-check":
        stage_prior_check()
    elif stage == "channels":
        _reg, store, _cat, eligible, _folds, _va, _vb, _ring = setup()
        ensure_channels(store, eligible)
    elif stage == "canary":
        stage_canary()
    elif stage == "fit":
        stage_fit()
    elif stage == "holdout":
        stage_holdout()
    elif stage == "build":
        stage_build()
    elif stage == "lane":
        stage_build()
    elif stage == "write":
        stage_write()
    elif stage == "card":
        stage_card()
    elif stage == "all":
        run_all()
    else:
        raise SystemExit("stage must be prior-check|channels|canary|fit|holdout|build|lane|write|card|all")


if __name__ == "__main__":
    main()
