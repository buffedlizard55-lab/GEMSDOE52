#!/usr/bin/env python3
"""H62 -- physically specified View A (cross-strike, regionally detrended basement and gravity offsets).

Frozen protocol: knowledge/41_hypotheses_H65_preregistered.md (SHA-256 in registry/h65_preregistration.json). The file keeps its original H62 label; see knowledge/41a.
This runner refuses to start if either hash has moved.

Stages (E2 of the preregistered budget; E3 is conditional and is NOT implemented here):
    features  build the eight H62-A layers once, on the shared feature-store footprint
    canary    raw and fitted single-feature leakage canary on every fold's held-out sample
    premise   fit H62-A on each label-blind fold, measure out-of-quadrant AUC, apply the premise gate

Reuse, not forks: folds, sampler, learner and held-out definition come from scripts/run_h61.py
(stage setup), the feature footprint from gems52.structural.FeatureStore, and the H61 controls are
read from the stored receipt evidence/h61_fit_checkpoint.json without refitting.

Nothing here writes a raster, touches submission/, or uploads anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h61 as h61                                              # noqa: E402  (shared fold/sampler/learner)
from gems52 import structural                                      # noqa: E402

WORK = ROOT / "work/h62"
FEAT = WORK / "feat"
EVID = ROOT / "evidence"
REG = ROOT / "registry/h65_preregistration.json"
SEED = h61.SEED
SIGMA_PX = 15.0
OFFSETS_PX = (3, 6)
STRIKES = {"nne": 15.0, "nw": 315.0}
BANDS = (15, 13)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_registration() -> dict:
    reg = json.loads(REG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha256(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H62 hypothesis document changed after registration; refusing to run")
    if reg.get("stages_not_authorised") is None or "emission" not in reg["stages_not_authorised"]:
        raise SystemExit("registration does not forbid emission; refusing to run")
    return reg


def feature_names() -> list[str]:
    return [f"H62_b{b:02d}_{tag}_d{d}" for b in BANDS for tag in STRIKES for d in OFFSETS_PX]


def normal_rowcol(az_deg: float) -> tuple[float, float]:
    """Unit normal to a strike of compass azimuth az, in (row, col) with row increasing south.

    Strike (north, east) = (cos a, sin a); normal (north, east) = (-sin a, cos a);
    row = -north, so the normal in (row, col) is (sin a, cos a).
    """
    a = np.deg2rad(az_deg)
    return float(np.sin(a)), float(np.cos(a))


def fill_nearest(arr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Replace off-footprint values by the nearest footprint value.

    Without this, the zero fill outside the footprint would create artificial steps along the
    survey boundary and the symmetric difference would respond to the boundary, not the basement.
    """
    idx = ndi.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    return arr[tuple(idx)]


def build_features(store) -> dict:
    FEAT.mkdir(parents=True, exist_ok=True)
    valid = store.valid.astype(bool)
    w = valid.astype(np.float32)
    w_s = {}
    man = dict(stage="features", generated_utc=now(), sigma_px=SIGMA_PX, offsets_px=list(OFFSETS_PX),
               strikes_deg=STRIKES, bands=list(BANDS), footprint_px=int(valid.sum()),
               operator="O = | D - G_sigma(D) |, D = | z(p + d n) - z(p - d n) |, n = unit normal to strike, "
                        "G_sigma = normalised Gaussian over the footprint",
               files={}, stats={})
    for b in BANDS:
        raw = store.feature_grid(f"raw_band_{b:02d}").astype(np.float32)
        z = fill_nearest(raw, valid).astype(np.float32)
        for tag, az in STRIKES.items():
            n0, n1 = normal_rowcol(az)
            for d in OFFSETS_PX:
                p = ndi.shift(z, (-n0 * d, -n1 * d), order=1, mode="nearest")
                m = ndi.shift(z, (n0 * d, n1 * d), order=1, mode="nearest")
                D = np.abs(p - m).astype(np.float32)
                del p, m
                if (b, SIGMA_PX) not in w_s:
                    w_s[(b, SIGMA_PX)] = ndi.gaussian_filter(w, SIGMA_PX)
                G = ndi.gaussian_filter(D * w, SIGMA_PX) / np.maximum(w_s[(b, SIGMA_PX)], 1e-6)
                O = np.where(valid, np.abs(D - G), 0.0).astype(np.float32)
                name = f"H62_b{b:02d}_{tag}_d{d}"
                path = FEAT / f"{name}.npy"
                np.save(path, O)
                vals = O[valid]
                man["files"][name] = dict(path=str(path.relative_to(ROOT)), sha256=sha256(path))
                man["stats"][name] = dict(finite_in_footprint=int(np.isfinite(vals).sum()),
                                          nan_in_footprint=int((~np.isfinite(vals)).sum()),
                                          min=float(vals.min()), p50=float(np.median(vals)),
                                          p99=float(np.quantile(vals, 0.99)), max=float(vals.max()))
                log(f"[features] {name}: p50 {man['stats'][name]['p50']:.4g} "
                    f"p99 {man['stats'][name]['p99']:.4g} nan {man['stats'][name]['nan_in_footprint']}")
                del D, G, O, vals
        del z
        del raw
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    return man


def load_features(names: list[str]) -> dict:
    out = {}
    man = json.loads((FEAT / "manifest.json").read_text())
    for n in names:
        path = ROOT / man["files"][n]["path"]
        if sha256(path) != man["files"][n]["sha256"]:
            raise SystemExit(f"H62 feature byte-integrity failure: {n}")
        out[n] = np.load(path, mmap_mode="r")
    return out


def stage_features() -> dict:
    store = structural.FeatureStore(ROOT / h61.STORE)
    man = build_features(store)
    log(f"features written: {len(man['files'])} layers")
    return man


def stage_canary() -> dict:
    _h61, store, cat, eligible, folds, va, vb, ring_px = h61.setup()
    reg = check_registration()                       # H62 thresholds, not H61's
    names = feature_names()
    F = load_features(names)
    th = reg["thresholds"]
    rng = np.random.default_rng(SEED)
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="canary", started_utc=now(), alarm_auc=th["canary_auc_alarm"],
               evidence_class="HOLDOUT-DTI diagnostic AUC (not a DTI score)", folds=[])
    for fold in folds:
        region = fold["region"]
        pos = np.flatnonzero((fold["truth"] & region).ravel())
        neg = np.flatnonzero((region & ~cat & (catd > 5)).ravel())
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        rows = np.concatenate([pos, neg])
        y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
        per = {}
        for n in names:
            x = np.asarray(F[n].ravel()[rows], np.float64)
            auc = float(roc_auc_score(y, x))
            per[n] = dict(auc=auc, direction_insensitive=max(auc, 1 - auc))
        ranked = sorted(per.items(), key=lambda kv: -kv[1]["direction_insensitive"])
        tr_rows, tr_y = h61.sample_train(fold, cat, np.random.default_rng(SEED + 900 + fold["fold"]))
        fitted = {}
        for n, _ in ranked[:5]:
            m = h61.learner(SEED + 1)
            m.fit(np.asarray(F[n].ravel()[tr_rows], np.float32)[:, None], tr_y)
            fitted[n] = float(roc_auc_score(y, m.predict_proba(
                np.asarray(F[n].ravel()[rows], np.float32)[:, None])[:, 1]))
        alarms = [n for n, r in per.items() if r["direction_insensitive"] > th["canary_auc_alarm"]]
        out["folds"].append(dict(fold=fold["fold"], n_pos=int(len(pos)), n_neg=int(len(neg)),
                                 max_direction_insensitive_auc=ranked[0][1]["direction_insensitive"],
                                 top5=[(n, r["direction_insensitive"]) for n, r in ranked[:5]],
                                 fitted_top5_heldout=fitted, alarms=alarms, per_feature=per))
        log(f"fold {fold['fold']} canary max AUC {ranked[0][1]['direction_insensitive']:.4f} "
            f"({ranked[0][0]}) alarms={alarms}")
    out.update(finished_utc=now(),
               any_alarm=bool(any(r["alarms"] for r in out["folds"])),
               dropped_features=sorted({n for r in out["folds"] for n in r["alarms"]}),
               max_raw_auc_any_feature=max(r["max_direction_insensitive_auc"] for r in out["folds"]),
               max_fitted_top5_heldout_auc=max(max(r["fitted_top5_heldout"].values()) for r in out["folds"]),
               interpretation="AUC above the alarm means leakage until proven otherwise; catalogue-zero "
                              "negatives are proxies, not verified fault absence.")
    write("canary", out)
    return out


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h65_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    return p


def stage_premise() -> dict:
    _h61, store, cat, eligible, folds, va, vb, ring_px = h61.setup()
    reg = check_registration()                       # H62 thresholds, not H61's
    names = feature_names()
    F = load_features(names)
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    inv = store.inverse
    out = dict(stage="premise", started_utc=now(), view_A_features=names, n_A=len(names),
               seed=SEED, learner="run_h61.learner", folds=[])
    X_all = np.empty((len(flat), len(names)), np.float32)
    for j, n in enumerate(names):
        X_all[:, j] = np.asarray(F[n].ravel()[flat], np.float32)
    if not np.isfinite(X_all).all():
        raise SystemExit("non-finite H62 features inside the eligible footprint")
    for fold in folds:
        rng = np.random.default_rng(SEED + fold["fold"])
        rows, y = h61.sample_train(fold, cat, rng)
        X = np.stack([np.asarray(F[n].ravel()[rows], np.float32) for n in names], 1)
        m = h61.learner(SEED)
        t0 = time.time()
        m.fit(X, y)
        in_auc = float(roc_auc_score(y, m.predict_proba(X)[:, 1]))
        del X
        pred = np.empty(len(flat), np.float32)
        for i in range(0, len(flat), 250_000):
            pred[i:i + 250_000] = m.predict_proba(X_all[i:i + 250_000])[:, 1].astype(np.float32)
        pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
        neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())]
        yy = np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))]
        oof = float(roc_auc_score(yy, np.r_[pred[pos_idx], pred[neg_idx]]))
        out["folds"].append(dict(fold=fold["fold"], n_train=int(len(rows)), n_pos_train=int(y.sum()),
                                 in_sample_auc=in_auc, heldout_region_auc=oof,
                                 n_region_pos=int(len(pos_idx)), n_region_neg=int(len(neg_idx)),
                                 fit_seconds=round(time.time() - t0, 1)))
        np.save(WORK / f"pred_h62A_f{fold['fold']}.npy", pred)
        log(f"fold {fold['fold']}: in-AUC {in_auc:.4f} OOF-region-AUC {oof:.4f}")
    aucs = [f["heldout_region_auc"] for f in out["folds"]]
    h61_fit = json.loads((EVID / "h61_fit_checkpoint.json").read_text())
    control = {
        "source": "evidence/h61_fit_checkpoint.json (stored H61 receipt, not refitted)",
        "view_A_oof_by_fold": [f["view_A"]["heldout_region_auc"] for f in h61_fit["folds"]],
        "view_B_oof_by_fold": [f["view_B"]["heldout_region_auc"] for f in h61_fit["folds"]],
    }
    control["view_A_mean"] = float(np.mean(control["view_A_oof_by_fold"]))
    control["view_B_mean"] = float(np.mean(control["view_B_oof_by_fold"]))
    th = reg["thresholds"]
    mean_auc, min_auc = float(np.mean(aucs)), float(np.min(aucs))
    passed = bool(mean_auc >= th["premise_mean_oof_auc_min"] and min_auc >= th["premise_min_fold_auc_min"])
    out.update(finished_utc=now(), h62_A_mean_oof_auc=mean_auc, h62_A_min_fold_oof_auc=min_auc,
               h61_control=control,
               gate=dict(mean_threshold=th["premise_mean_oof_auc_min"], min_fold_threshold=th["premise_min_fold_auc_min"],
                         premise_passed=passed),
               verdict="PREMISE PASS -> E3 holdout comparison authorised (not run)" if passed
               else "NEGATIVE -> H62-A does not carry out-of-quadrant information; no holdout arm, "
                    "no emission, no slot",
               caveat="Premise AUC only. It does not measure detection of faults, fault truth, "
                      "or any competition score. Catalogue-zero is not verified fault absence.")
    write("premise", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["features", "canary", "premise", "all"])
    args = ap.parse_args()
    reg = check_registration()
    stages = ["features", "canary", "premise"] if args.stage == "all" else [args.stage]
    for s in stages:
        t0 = time.time()
        log(f"=== H62 stage {s} ===")
        {"features": stage_features, "canary": stage_canary, "premise": stage_premise}[s]()
        log(f"--- stage {s} done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
