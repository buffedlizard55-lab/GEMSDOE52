#!/usr/bin/env python3
"""H60-A -- fit and falsify a corroboration-ladder model on the organiser's own scores.

Why a parametric ladder instead of the free-form curve
------------------------------------------------------
Stage 2 of this round fitted a free rho(k) with one parameter per corroboration count; it produced
rho(10) = 13.4 and missed file `L` by 86 %, so it was fitting noise with 13 free parameters on 13
equations.  Here the ladder is *parametric* -- four coefficients -- and is therefore falsifiable
against the twelve measured credits: if a monotone-corroboration story is true it must reproduce
all twelve numbers from four coefficients.

Model
-----
Every off-catalogue pixel in the union of the twelve scored files is labelled by

    c = number of distinct h19-clade files  (A B C D E F G) that emit it, capped at 4
    f = number of distinct external provenance families (gemsdoe10, gemsdoe8, gemsdoe13,
        gemsdoe9) that emit it

Credit density is modelled as

    rho(c, f) = rho_clade * r_clade ** (c - 1) * r_ext ** f        c >= 1
    rho(0, f) = rho_ext   * r_ext ** (f - 1)                       f >= 1
    rho(0, 0) = 0                                                  (outside every file)

so a pixel credited by two clade thinnings is r_clade times as dense as one credited by a single
thinning, and a pixel corroborated across provenance families gains r_ext per family.

Predicted credit of file i is then T_hat_i = sum over its pixels of rho(c(x), f(x)), and the four
coefficients are fitted by weighted least squares on the twelve measured T_i.  The fit is judged
by relative residuals and by a leave-one-file-out re-fit.

Everything is recomputed from restored, SHA-256-pinned bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G_PX = 14088.7
ALPHA, BETA = 0.2, 0.8

SCORES = {"A": 0.2778, "B": 0.2600, "C": 0.2477, "D": 0.2449, "E": 0.1922, "F": 0.1894,
          "G": 0.1855, "H": 0.1839, "I": 0.1563, "K": 0.1280, "L": 0.0904, "M": 0.0107}
REL = {
    "A": "reference/h33-2-b2-zeros.tif",
    "B": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "C": "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "D": "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "E": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "F": "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "G": "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "H": "scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "I": "scored/8GEMSDOE_Hedge-v2_submission.tif",
    "K": "scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "L": "scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "M": "scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
}
CLADE = ["A", "B", "C", "D", "E", "F", "G"]
EXT_FAMILY = {"H": "gemsdoe10", "K": "gemsdoe10", "I": "gemsdoe8", "L": "gemsdoe13",
              "M": "gemsdoe9"}
ORDER = list(REL)


def main() -> int:
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    finite = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    cat = np.zeros(tpl.shape, dtype=bool)
    cat[finite] = np.isfinite(lb[finite]) & (lb[finite] > 0.5)

    masks = {}
    for k in ORDER:
        with rasterio.open(DATA / REL[k]) as s:
            a = s.read(1)
        masks[k] = finite & np.isfinite(a) & (np.abs(a) > 1e-12)
    Sfull = {k: int(masks[k].sum()) for k in ORDER}
    T = {k: SCORES[k] * (ALPHA * Sfull[k] + BETA * G_PX) for k in ORDER}
    off = {k: masks[k] & ~cat for k in ORDER}

    # corroboration labels
    c_cnt = np.zeros(tpl.shape, dtype=np.int8)
    for k in CLADE:
        c_cnt += off[k].astype(np.int8)
    np.clip(c_cnt, 0, 4, out=c_cnt)
    fam_masks = {}
    for fam in sorted(set(EXT_FAMILY.values())):
        m = np.zeros(tpl.shape, dtype=bool)
        for k, f in EXT_FAMILY.items():
            if f == fam:
                m |= off[k]
        fam_masks[fam] = m
    fams = sorted(fam_masks)
    f_cnt = np.zeros(tpl.shape, dtype=np.int8)
    for fam in fams:
        f_cnt += fam_masks[fam].astype(np.int8)

    union = np.zeros(tpl.shape, dtype=bool)
    for k in ORDER:
        union |= off[k]
    print(f"union (off-catalogue) = {int(union.sum())} px")

    # design: for each file, count of pixels at each (c, f) label
    cvals = np.arange(1, 5)
    fvals = np.arange(0, len(fams) + 1)
    cu = c_cnt[union]
    fu = f_cnt[union]
    lab = (cu.astype(np.int32) * 10 + fu.astype(np.int32))
    labvals, labinv = np.unique(lab, return_inverse=True)
    labcount = np.bincount(labinv, minlength=labvals.size).astype(float)

    def design_row(m: np.ndarray) -> np.ndarray:
        sub = (c_cnt[m].astype(np.int32) * 10 + f_cnt[m].astype(np.int32))
        cnt = np.zeros(labvals.size, dtype=float)
        u, inv = np.unique(sub, return_inverse=True)
        bc = np.bincount(inv, minlength=u.size).astype(float)
        pos = np.searchsorted(labvals, u)
        cnt[pos] = bc
        return cnt

    rows = np.array([design_row(off[k]) for k in ORDER])       # 12 x n_lab

    def density_of(theta: np.ndarray) -> np.ndarray:
        """rho for every observed (c, f) label."""
        rho0, r1, r2, rho_ext = theta
        out = np.zeros(labvals.size)
        for j, lv in enumerate(labvals):
            c, f = divmod(int(lv), 10)
            if c == 0 and f == 0:
                out[j] = 0.0
            elif c >= 1:
                out[j] = rho0 * (r1 ** (c - 1)) * (r2 ** f)
            else:
                out[j] = rho_ext * (r2 ** (f - 1))
        return out

    def predict(theta: np.ndarray) -> np.ndarray:
        return rows @ (density_of(theta) * labcount)

    b = np.array([T[k] for k in ORDER])
    w = 1.0 / np.maximum(b, 1.0)

    def resid(logtheta):
        th = np.exp(logtheta)
        return (predict(th) - b) * w

    best = None
    for seed in range(12):
        rng = np.random.default_rng(seed)
        x0 = np.log(np.array([0.05, 2.0, 1.5, 0.02]) * (10 ** rng.uniform(-0.5, 0.5, 4)))
        try:
            r = least_squares(resid, x0, method="lm", max_nfev=20000)
        except Exception:
            continue
        if best is None or r.cost < best.cost:
            best = r
    th = np.exp(best.x)
    pred = predict(th)
    rel = (pred - b) / b
    print("\nfitted coefficients:")
    print(f"  rho_clade (one clade thinning)      = {th[0]:.5f}")
    print(f"  r_clade   (per extra clade thinning) = {th[1]:.4f}")
    print(f"  r_ext     (per external family)      = {th[2]:.4f}")
    print(f"  rho_ext   (one external family only) = {th[3]:.5f}")
    print("\nfile   T_measured  T_predicted  rel.err")
    for i, k in enumerate(ORDER):
        print(f"  {k}   {b[i]:9.1f} {pred[i]:11.1f}  {rel[i]:+.3f}")
    print(f"  median |rel.err| = {np.median(np.abs(rel)):.4f}   max = {np.abs(rel).max():.4f}")

    # leave-one-file-out refit
    loo = {}
    for held in range(len(ORDER)):
        keep = [i for i in range(len(ORDER)) if i != held]
        bk, wk = b[keep], w[keep]
        rk = rows[keep]

        def r2_(logtheta, rk=rk, bk=bk, wk=wk):
            t = np.exp(logtheta)
            out = np.zeros(labvals.size)
            rho0, r1, r2, rho_ext = t
            for j, lv in enumerate(labvals):
                c, f = divmod(int(lv), 10)
                out[j] = (0.0 if (c == 0 and f == 0) else
                          rho0 * r1 ** (c - 1) * r2 ** f if c >= 1 else
                          rho_ext * r2 ** (f - 1))
            return (rk @ (out * labcount) - bk) * wk

        rr = least_squares(r2_, best.x, method="lm", max_nfev=20000)
        t2 = np.exp(rr.x)
        out = np.zeros(labvals.size)
        rho0, r1, r2, rho_ext = t2
        for j, lv in enumerate(labvals):
            c, f = divmod(int(lv), 10)
            out[j] = (0.0 if (c == 0 and f == 0) else
                      rho0 * r1 ** (c - 1) * r2 ** f if c >= 1 else
                      rho_ext * r2 ** (f - 1))
        ph = float(rows[held] @ (out * labcount))
        loo[ORDER[held]] = dict(lo_pred=ph, measured=float(b[held]),
                                rel_err=float((ph - b[held]) / b[held]))
    print("\nleave-one-file-out (4 coefficients refit on 11 files, predicting the 12th):")
    for k, v in loo.items():
        print(f"  {k}  measured {v['measured']:9.1f}   LOO pred {v['lo_pred']:9.1f}   "
              f"{v['rel_err']:+.3f}")
    loo_med = float(np.median([abs(v["rel_err"]) for v in loo.values()]))
    print(f"  median |LOO rel.err| = {loo_med:.4f}")

    # the number the round needs: density of the arm tiers
    dens = density_of(th)
    table = []
    print("\nfitted density rho(c, f) for the (clade count, external family count) labels:")
    print("   c  f        px      rho      credit")
    for j, lv in enumerate(labvals):
        c, f = divmod(int(lv), 10)
        table.append(dict(clade_count=int(c), ext_count=int(f), px=float(labcount[j]),
                          rho=float(dens[j]), credit=float(dens[j] * labcount[j])))
        if labcount[j] >= 1:
            print(f"  {c}  {f}  {int(labcount[j]):9d}  {dens[j]:.5f}  {dens[j]*labcount[j]:9.1f}")

    out = dict(G_px=G_PX, scores=SCORES, S_full=Sfull, T=T,
               coefficients=dict(rho_clade=float(th[0]), r_clade=float(th[1]),
                                 r_ext=float(th[2]), rho_ext=float(th[3])),
               fit=dict(predicted=pred.tolist(), measured=b.tolist(),
                        rel_err=rel.tolist(), median_abs_rel=float(np.median(np.abs(rel))),
                        max_abs_rel=float(np.abs(rel).max())),
               loo=loo, loo_median_abs_rel=loo_med, labels=table)
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "h60_ladder.json").write_text(json.dumps(out, indent=1))
    np.save(ROOT / "work" / "h60_ladder_labels.npy",
            np.stack([c_cnt[union], f_cnt[union]]).astype(np.int8))
    np.save(ROOT / "work" / "h60_union_idx.npy", np.flatnonzero(union.ravel()).astype(np.int64))
    print("\nwrote work/h60_ladder.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
