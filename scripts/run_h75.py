#!/usr/bin/env python3
"""H75 -- directional variogram anisotropy (DVA) added to View B; hide-and-recover holdout; emission.

Preregistered in knowledge/65_hypotheses_H75_preregistered.md (pinned in registry/h75_preregistration.json).
Shared, not forked: run_h61.setup / sample_for_fit / learner_for / pct_rank / to_grid, gems52.evaluate_holdout,
gems52.nodes.spacing_select, gems52.gates, gems52.submission_writer, build_h61_submission.prior_paths.

Usage: python scripts/run_h75.py [fit|holdout|build|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import nodes                                             # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h75_preregistration.json"
WORK = ROOT / "work/h75"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
K_FOLD = int(os.environ.get("H75_K_FOLD", 9400))
K_TOTAL = int(os.environ.get("H75_K_TOTAL", 37654))
DVA_BANDS = {12: "det_elev", 19: "det_elev_slope", 13: "iso_grav_anom"}
LAGS = (2, 4)
SIGMA = 3.0


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h75_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float))
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H75 preregistration changed after freezing")
    return reg


# ------------------------------------------------------------------------------------------- DVA
def dva_channels(eligible):
    """12 channels: per band x lag -> anisotropy and log mean semivariance (label-free)."""
    out = {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in DVA_BANDS.items():
            z = ds.read(b).astype(np.float64)
            ok = np.isfinite(z) & eligible
            mu, sd = z[ok].mean(), z[ok].std() + 1e-12
            z = np.where(ok, (z - mu) / sd, 0.0)
            w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
            for h in LAGS:
                gam = []
                for dy, dx in ((0, h), (h, h), (h, 0), (h, -h)):
                    zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
                    oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
                    d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
                    g = ndi.gaussian_filter(d2, SIGMA) / w
                    gam.append(g)
                gam = np.stack(gam)
                mx, mn = gam.max(0), gam.min(0)
                out[f"DVA_{nm}_aniso_l{h}"] = ((mx - mn) / (mx + mn + 1e-9)).astype(np.float32)
                out[f"DVA_{nm}_logvar_l{h}"] = np.log10(gam.mean(0) + 1e-9).astype(np.float32)
    for k in out:
        out[k][~eligible] = np.nan
    return out


def gather(store, rows, names, dva):
    X = store.gather(rows, names) if names else np.empty((len(rows), 0), np.float32)
    if dva:
        D = np.stack([dva[k].ravel()[rows] for k in sorted(dva)], 1)
        X = np.hstack([X, np.nan_to_num(D, nan=0.0)])
    return X


def predict(store, m, names, dva, rows, chunk=250_000):
    out = np.empty(len(rows), np.float32)
    for i in range(0, len(rows), chunk):
        s = rows[i:i + chunk]
        out[i:i + chunk] = m.predict_proba(gather(store, s, names, dva))[:, 1]
    return out


# ------------------------------------------------------------------------------------------- stages
def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    WORK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    dva = dva_channels(eligible)
    np.savez_compressed(WORK / "dva.npz", **dva)
    log(f"DVA channels built in {time.time()-t0:.0f}s: {sorted(dva)}")
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    arms = {"single_B": (vb, None), "B_DVA": (vb, dva), "DVA_only": ([], dva)}
    out = dict(stage="fit", dva_channels=sorted(dva), folds=[])
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        rows, y, _ = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, auc={}, canary={})
        for arm, (names, d) in arms.items():
            m = base.learner_for("B", SEED)
            m.fit(gather(store, rows, names, d), y)
            p = predict(store, m, names, d, flat)
            np.save(WORK / f"pred_{arm}_f{f}.npy", p)
            g = base.to_grid(flat, p, eligible.shape).ravel()
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[pos_g], g[neg_g]]))
        for k in sorted(dva):
            v = dva[k].ravel()[np.r_[pos_g, neg_g]]
            ok = np.isfinite(v)
            a = float(roc_auc_score(yy[ok], v[ok]))
            rec["canary"][k] = max(a, 1 - a)
        rec["canary_max"] = max(rec["canary"].values())
        log(f"fold {f}: {rec['auc']} canary max {rec['canary_max']:.3f}")
        out["folds"].append(rec)
    out["canary_alarm"] = any(r["canary_max"] >= 0.90 for r in out["folds"])
    write("fit", out)


def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    arms = ("single_B", "B_DVA", "DVA_only", "random")
    terms = {a: None for a in arms}
    out = dict(stage="holdout", evaluator="gems52-pooled-hide-v1", budget_per_fold=K_FOLD, folds=[])
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        rec = dict(fold=f, arms={})
        for arm in arms:
            fld = np.full(eligible.shape, -1.0, np.float32)
            if arm == "random":
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                g = base.to_grid(flat, np.load(WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
                fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f}")
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="B_DVA")
    write("holdout", out)
    log(json.dumps({a: out["pooled"]["scores"][a]["dti"] for a in arms}))


def stage_build():
    """Full-domain B_DVA field: refit on all visible catalogue, rank, 200 m ring excluded, binary dots."""
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dva = dict(np.load(WORK / "dva.npz"))
    flat = store.flat_idx
    # stitch: each pixel takes the prediction of the fold whose region contains it (same as H73)
    field = np.full(eligible.shape, np.nan, np.float32)
    for fold in folds:
        g = base.to_grid(flat, np.load(WORK / f"pred_B_DVA_f{fold['fold']}.npy"), eligible.shape)
        r = np.full(eligible.shape, np.nan, np.float32)
        ai = np.flatnonzero((fold["region"] & eligible).ravel())
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        m = np.isfinite(r) & ~np.isfinite(field)
        field[m] = r[m]
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(field) & (catd * 100.0 > 200.0)
    em = nodes.spacing_select(np.where(pool, field, -1.0).astype(np.float32), pool, K_TOTAL, min_px=3.0)
    np.save(WORK / "dots.npy", em)
    np.save(WORK / "surface.npy", np.where(eligible & np.isfinite(field), field, 0.0).astype(np.float32))
    write("build_placement", dict(dots=int(em.sum()), pool_px=int(pool.sum()),
                                  min_cat_dist_m=float((catd[em] * 100).min())))
    log(f"dots {int(em.sum())}, min catalogue distance {(catd[em]*100).min():.1f} m")


def main():
    check_prereg()
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("fit", stage_fit), ("holdout", stage_holdout), ("build", stage_build)):
        if st in (name, "all"):
            fn()


if __name__ == "__main__":
    main()
