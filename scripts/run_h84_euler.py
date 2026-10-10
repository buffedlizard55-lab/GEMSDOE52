#!/usr/bin/env python3
"""H84-E (top-ranked untested idea): windowed Euler deconvolution on reduced-to-pole magnetics.

PRE-REGISTERED ARM (fixed before this run; not tuned on the holdout):
  * field T = band 2 (rtp, reduced-to-pole TMI); vertical derivative = band 9 (tmi_vg) as stored.
  * Euler's homogeneity equation with structural index SI = 0 (contact / step-like source, the
    geometry of a fault trace): (x-x0)Tx + (y-y0)Ty + (z-z0)Tz = 0, observation plane z = 0, so
    Tx*x0 + Ty*y0 + Tz*z0 = Tx*x + Ty*y.   Solved by least squares in 7-pixel (700 m) windows.
  * Accept a solution if its source lies inside its own window (|dx|,|dy| <= 700 m) and its depth
    z0 is in [50 m, 1500 m] and the 3x3 normal matrix is well conditioned.
  * Score = Gaussian (sigma 1.5 px) density of accepted solution locations. Emission = the H84
    protocol: spacing_select(score, allowed, K, min_px=3) with the same allowed rule and folds.

Catalogue use: NONE. Euler is label-free, so the same field is valid for every fold; the holdout
only decides what is allowed and what is scored. This is the cleanest possible leakage control.

Output: evidence/h84_euler_holdout.json (HOLDOUT-DTI, same evaluator and folds as H84).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rasterio  # noqa: E402

import run_h83_structural_concordance as H83  # noqa: E402  (footprint helper only)
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import nodes, spatial  # noqa: E402

RTP_BAND, TVG_BAND = 2, 9          # from the file's own band descriptions (checked this session)
WIN_R = 7                          # px; 700 m half-window
SEED = 84001                       # same as run_h84_holdout (random arm reproduces exactly)
K_FOLD = 9400
RING_PX = 2
BUFFER_PX = 80
DEPTH_MIN, DEPTH_MAX = 50.0, 1500.0
SIGMA_PX = 1.5
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
OUT = ROOT / "evidence/h84_euler_holdout.json"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def euler_score(valid):
    with rasterio.open(FEATURES) as s:
        T = np.where(valid, s.read(RTP_BAND).astype(np.float32), 0).astype(np.float32)
        Z = np.where(valid, s.read(TVG_BAND).astype(np.float32), 0).astype(np.float32)
    T[~np.isfinite(T)] = 0
    Z[~np.isfinite(Z)] = 0
    h, w = T.shape
    rows, cols = np.mgrid[0:h, 0:w].astype(np.float32)
    X = (cols * 100.0).astype(np.float32)
    Y = (rows * 100.0).astype(np.float32)
    Tx = (np.gradient(T, axis=1) / 100.0).astype(np.float32)
    Ty = (np.gradient(T, axis=0) / 100.0).astype(np.float32)
    Tz = Z
    rhs_pix = (Tx * X + Ty * Y).astype(np.float32)   # Tx*x + Ty*y  (z = 0 on observation plane)
    size = 2 * WIN_R + 1
    mean = lambda a: ndi.uniform_filter(a, size=size, mode="constant", cval=0.0)  # noqa: E731
    m = {k: mean(v) for k, v in {
        "xx": Tx * Tx, "xy": Tx * Ty, "xz": Tx * Tz, "yy": Ty * Ty, "yz": Ty * Tz, "zz": Tz * Tz,
        "xr": Tx * rhs_pix, "yr": Ty * rhs_pix, "zr": Tz * rhs_pix}.items()}
    del Tx, Ty, Tz, rhs_pix
    # solve per pixel in row chunks (3x3 batched) -> local solution (x0, y0, z0)
    sol = np.full((h, w, 3), np.nan, np.float32)
    for r0 in range(0, h, 256):
        sl = slice(r0, min(h, r0 + 256))
        M = np.stack([np.stack([m["xx"][sl], m["xy"][sl], m["xz"][sl]], -1),
                      np.stack([m["xy"][sl], m["yy"][sl], m["yz"][sl]], -1),
                      np.stack([m["xz"][sl], m["yz"][sl], m["zz"][sl]], -1)], -2).astype(np.float64)
        v = np.stack([m["xr"][sl], m["yr"][sl], m["zr"][sl]], -1).astype(np.float64)
        det = np.linalg.det(M)
        tr = np.trace(M, axis1=-2, axis2=-1)
        ok = (np.abs(det) > 1e-12 * np.maximum(tr, 1e-30) ** 3) & (tr > 0)
        Ms = np.where(ok[..., None, None], M, np.eye(3))
        u = np.linalg.solve(Ms, v[..., None])[..., 0]
        u[~ok] = np.nan
        sol[sl] = u.astype(np.float32)
    x0, y0, z0 = sol[..., 0], sol[..., 1], sol[..., 2]
    cx, cy = X, Y
    inwin = (np.abs(x0 - cx) <= WIN_R * 100) & (np.abs(y0 - cy) <= WIN_R * 100)
    good = inwin & (z0 >= DEPTH_MIN) & (z0 <= DEPTH_MAX) & valid & np.isfinite(z0)
    gi, gj = np.nonzero(good)
    pr = np.clip(np.rint(y0[gi, gj] / 100.0).astype(int), 0, h - 1)
    pc = np.clip(np.rint(x0[gi, gj] / 100.0).astype(int), 0, w - 1)
    acc = np.zeros((h, w), np.float32)
    np.add.at(acc, (pr, pc), 1.0)
    score = ndi.gaussian_filter(acc, SIGMA_PX).astype(np.float32)
    score[~valid] = 0
    stats = dict(windows=int(valid.sum()), accepted_solutions=int(good.sum()),
                 depth_median_m=float(np.median(z0[good])) if good.any() else None,
                 nonzero_score_px=int((score > 0).sum()))
    return score, stats


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
    with rasterio.open(LABELS) as ds:
        cat = ds.read(1) == 1
    valid = H83.footprint_all_bands(str(FEATURES)) & domain
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    log(f"eligible {int(valid.sum()):,}; folds {len(folds)}")
    score, stats = euler_score(valid)
    log(f"euler: {stats}")
    terms = {"euler_SI0": None, "random": None}
    per_fold = []
    auc = []
    for fold in folds:
        f = fold["fold"]
        vd = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & valid & ~fold["visible"] & (vd > RING_PX)
        em_e = nodes.spacing_select(score, allowed, K_FOLD, min_px=3.0).astype(np.float32)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)
        em_r = nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0).astype(np.float32)
        rec = dict(fold=f, arms={})
        for arm, em in (("euler_SI0", em_e), ("random", em_r)):
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=res["dti"], placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        truth_in = (fold["truth"] & fold["region"])[allowed]
        if truth_in.any() and (~truth_in).any():
            auc.append(float(roc_auc_score(truth_in.astype(int), score[allowed])))
        per_fold.append(rec)
    summ = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="euler_SI0")
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    out = dict(round="H84-E", stage="holdout", evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
               arm="euler_SI0 (pre-registered; structural index 0; 7px window; depth 50-1500 m; sigma 1.5px)",
               budget_per_fold=K_FOLD, withheld_positive_px=withheld, pooled=summ, per_fold=per_fold,
               canary_fold_auc=auc, canary_max_auc=max(auc) if auc else None,
               canary_alarm=bool(auc and max(auc) > 0.90), euler_stats=stats,
               inputs=dict(features_sha256=sha(FEATURES), labels_sha256=sha(LABELS)),
               elapsed_seconds=round(time.time() - t0, 1))
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a: round(summ["scores"][a]["dti"], 6) for a in summ["scores"]}))
    log("CI: " + json.dumps({a: summ["scores"][a]["ci95"] for a in summ["scores"]}))
    log("paired euler minus random: " + json.dumps(summ["paired_differences"], default=float))
    log(f"canary fold AUC {auc}; max {out['canary_max_auc']}")


if __name__ == "__main__":
    main()
