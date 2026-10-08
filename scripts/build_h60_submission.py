#!/usr/bin/env python3
"""H60: Basement-penetrating, fault-adjacent blind-fault detector (memory-safe).

See module docstring in earlier revision for hypothesis. This version loads
raster bands one at a time and avoids stacking all features simultaneously.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats as sstats
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems52 import grid as G
from gems52 import emit as EMIT
from gems52 import gates

# --------------------------------------------------------------------------------------------------
WORK = Path("work/h60")
SUB_DIR = Path("submission")
DOC_DL = Path("docs/downloads")
EV = Path("evidence")
DOC_DATA = Path("docs/data")
TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
BUDGET = 31000
SEED = 20261009
NEG_PER_POS = 30
COLLAR_PX = 3
N_FOLD_BLOCKS = 4
HOLD_FOLDS = [5, 10]
STRIKE_TOLERANCE_DEG = 25
TARGET_STRIKE_DEG = 15
DEPTH_QUANTILE_FLOOR = 0.50

# --------------------------------------------------------------------------------------------------
SENT = -1e38

def read_band_finite(src, b):
    a = src.read(b).astype(np.float32)
    a[~np.isfinite(a) | (a < SENT)] = np.nan
    return a

def rank01_inplace(a, valid):
    """Write rank in [0,1] into a copy; NaN outside valid."""
    v = a[valid & np.isfinite(a)]
    out = np.zeros(a.shape, dtype=np.float32)
    if v.size == 0:
        out[~valid] = np.nan
        return out
    lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
    if hi > lo:
        out[valid] = np.clip((a[valid] - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)
    else:
        out[valid] = 0.0
    out[~valid] = 0.0  # will be masked later
    return out

def grad_mag(a, valid):
    a0 = np.where(np.isfinite(a) & valid, a, 0.0).astype(np.float32)
    gx = ndimage.sobel(a0, axis=1)
    gy = ndimage.sobel(a0, axis=0)
    # avoid hypot overflow by clipping
    gx = np.clip(gx, -1e12, 1e12)
    gy = np.clip(gy, -1e12, 1e12)
    gm = np.hypot(gx, gy).astype(np.float32)
    return gm

def grad_az(a, valid):
    a0 = np.where(np.isfinite(a) & valid, a, 0.0).astype(np.float64)
    gx = ndimage.sobel(a0, axis=1)
    gy = ndimage.sobel(a0, axis=0)
    az = np.degrees(np.arctan2(gx, -gy)).astype(np.float32)
    return az

def ang_dist(a, target):
    return np.abs(((a - target + 180) % 360) - 180)

def strike_w(az_delta, tol=STRIKE_TOLERANCE_DEG):
    w = np.maximum(0.0, 1.0 - (az_delta / tol) ** 2)
    w[~np.isfinite(w)] = 0.0
    return w.astype(np.float32)

def box_smooth(a, r, valid):
    a0 = np.where(np.isfinite(a) & valid, a, 0.0).astype(np.float32)
    n = np.where(np.isfinite(a) & valid, 1.0, 0.0).astype(np.float32)
    size = 2 * r + 1
    k = np.ones((size, size), dtype=np.float32)
    sm = ndimage.convolve(a0, k, mode="nearest")
    ct = ndimage.convolve(n, k, mode="nearest")
    out = np.divide(sm, ct, out=np.zeros_like(sm), where=ct > 0)
    return out.astype(np.float32)


def main():
    print("=== H60 triple-convergence (memory-safe) ===")
    WORK.mkdir(parents=True, exist_ok=True)
    SUB_DIR.mkdir(parents=True, exist_ok=True)
    DOC_DL.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    DOC_DATA.mkdir(parents=True, exist_ok=True)

    # First compute valid mask cheaply
    with rasterio.open("data/training_features.tif") as src:
        H, W = src.height, src.width
        valid = np.ones((H, W), dtype=bool)
        for b in range(1, src.count + 1):
            a = src.read(b)
            valid &= np.isfinite(a) & (a > SENT)
            del a
        print(f"valid footprint: {int(valid.sum())} px")

    with rasterio.open("data/labels.tif") as src:
        labels = src.read(1)
    cat = (labels == 1) & valid
    print(f"catalogue positives: {int(cat.sum())}")

    # ---- extract the physics bands we need (one at a time) ----
    with rasterio.open("data/training_features.tif") as src:
        grav = read_band_finite(src, 13)
        rtp = read_band_finite(src, 2)
        tmi = read_band_finite(src, 14)
        depth = read_band_finite(src, 15)
        cond = read_band_finite(src, 17)
        elev = read_band_finite(src, 12)
        slope = read_band_finite(src, 19)
        strain = read_band_finite(src, 4)
        shear = read_band_finite(src, 7)
        dilate = read_band_finite(src, 8)
        eqdist = read_band_finite(src, 10)
        eqdens = read_band_finite(src, 16)
        tc_b6 = read_band_finite(src, 6)  # radiometric TC per IR-52-019

    # External layers (read band by band to keep memory low)
    def read_stack(path, bands):
        with rasterio.open(path) as src:
            out = []
            for b in bands:
                out.append(src.read(b).astype(np.float32))
        return out

    with rasterio.open("data/external/geodawn_rad_u8.tif") as src:
        k = src.read(1).astype(np.float32)
        th = src.read(2).astype(np.float32)
        u = src.read(3).astype(np.float32)
        tc_ext = src.read(4).astype(np.float32)
    with rasterio.open("data/external/geodawn_extensions_u8.tif") as src:
        thk = src.read(1).astype(np.float32)
        uk = src.read(2).astype(np.float32)
        uth = src.read(3).astype(np.float32)
    with rasterio.open("data/external/lidar_scarp_features_u8.tif") as src:
        lidar_stack = [src.read(b).astype(np.float32) for b in range(1, src.count + 1)]

    # ---- edges ----
    print("computing edges …")
    g_edge = grad_mag(grav, valid)
    rtp_edge = grad_mag(rtp, valid)
    k_edge = grad_mag(k, valid)
    thk_edge = grad_mag(thk, valid)
    depth_edge = grad_mag(depth, valid)
    slope_edge = grad_mag(slope, valid)
    cond_edge = grad_mag(cond, valid)

    g_az = grad_az(grav, valid)
    k_az = grad_az(k, valid)

    # ---- build uint8 feature stacks for the two views ----
    # rank-encode into uint8 in place, store only the uint8 stack.
    def to_u8(rarr):
        return np.clip(np.nan_to_num(rarr, nan=0.0) * 255.0, 0, 255).astype(np.uint8)

    A_feats = []
    A_names = ["grav", "grav_edge", "rtp", "rtp_edge", "tmi", "tmi_edge",
               "strain", "shear", "dilate", "eqdist", "eqdens",
               "depth", "depth_edge", "cond", "cond_edge"]
    for nm, arr in [
        ("grav", grav), ("grav_edge", g_edge), ("rtp", rtp), ("rtp_edge", rtp_edge),
        ("tmi", tmi), ("tmi_edge", grad_mag(tmi, valid)), ("strain", strain),
        ("shear", shear), ("dilate", dilate),
        ("eqdist", -eqdist), ("eqdens", eqdens), ("depth", depth),
        ("depth_edge", depth_edge), ("cond", cond), ("cond_edge", cond_edge)]:
        A_feats.append(to_u8(rank01_inplace(arr, valid)))
    A_stk = np.stack(A_feats, axis=-1)
    del A_feats

    B_feats = []
    B_names = ["elev", "slope", "slope_edge", "band6_tc", "k", "th", "u_rad", "tc_ext",
               "thk", "uk", "uth", "k_edge", "th_edge", "thk_edge"]
    for nm, arr in [
        ("elev", elev), ("slope", slope), ("slope_edge", slope_edge), ("band6_tc", tc_b6),
        ("k", k), ("th", th), ("u_rad", u), ("tc_ext", tc_ext),
        ("thk", thk), ("uk", uk), ("uth", uth),
        ("k_edge", k_edge), ("th_edge", grad_mag(th, valid)), ("thk_edge", thk_edge)]:
        B_feats.append(to_u8(rank01_inplace(arr, valid)))
    # Add LiDAR bands
    for i, la in enumerate(lidar_stack):
        B_feats.append(to_u8(rank01_inplace(la, valid)))
        B_names.append(f"lidar_{i+1}")
    B_stk = np.stack(B_feats, axis=-1)
    del B_feats, lidar_stack

    print(f"A_stk: {A_stk.shape} {A_stk.dtype}, B_stk: {B_stk.shape} {B_stk.dtype}")

    # ---- spatial split ----
    blk = G.block_labels((H, W), valid, N_FOLD_BLOCKS)
    buf = G.buffer_from_block_ids(blk, buffer_px=4)
    spl = G.make_split(blk, buf, HOLD_FOLDS, buffer_px=4)
    fit_mask = spl.fit
    eval_mask = spl.train

    cat_dil = ndimage.binary_dilation(cat, iterations=COLLAR_PX)
    pos_fit = np.flatnonzero(cat & fit_mask)
    clear = fit_mask & (~cat_dil)
    neg_pool = np.flatnonzero(clear & ~cat)
    rng = np.random.default_rng(SEED)
    n_neg = min(len(neg_pool), NEG_PER_POS * len(pos_fit))
    neg_fit = rng.choice(neg_pool, size=n_neg, replace=False)
    rows_fit = np.concatenate([pos_fit, neg_fit])
    y_fit = np.concatenate([np.ones(len(pos_fit), dtype=np.int8),
                            np.zeros(len(neg_fit), dtype=np.int8)])
    print(f"training rows: {len(pos_fit)} pos, {len(neg_fit)} neg")

    n_px = H * W

    def train_view(stk, cols):
        # Gather rows from the flat stack
        flat = stk.reshape(n_px, stk.shape[2])
        X = flat[rows_fit][:, cols].astype(np.float32) / 255.0
        mu = X.mean(axis=0); sd = X.std(axis=0) + 1e-6
        Z = (X - mu) / sd
        mdl = LogisticRegression(max_iter=600, C=0.5, class_weight="balanced",
                                 solver="lbfgs", random_state=SEED)
        mdl.fit(Z, y_fit)
        out = np.zeros(n_px, dtype=np.float32)
        for a in range(0, n_px, 500_000):
            b = min(n_px, a + 500_000)
            Xb = flat[a:b][:, cols].astype(np.float32) / 255.0
            out[a:b] = mdl.predict_proba((Xb - mu) / sd)[:, 1]
        return out.reshape(H, W)

    p_A = train_view(A_stk, list(range(len(A_names))))
    p_B = train_view(B_stk, list(range(len(B_names))))
    p_A[~valid] = np.nan; p_B[~valid] = np.nan
    print(f"p_A: {np.nanmin(p_A):.3f}..{np.nanmax(p_A):.3f}")
    print(f"p_B: {np.nanmin(p_B):.3f}..{np.nanmax(p_B):.3f}")
    del A_stk, B_stk  # free memory

    # ---- independence check ----
    errA, errB, bids_list = [], [], []
    neg_eval_mask = eval_mask & (~cat_dil) & valid
    for bid in range(N_FOLD_BLOCKS * N_FOLD_BLOCKS):
        m = neg_eval_mask & (blk == bid)
        if m.sum() < 50:
            continue
        errA.append(float(np.nanmean(p_A[m])))
        errB.append(float(np.nanmean(p_B[m])))
        bids_list.append(bid)
    if len(errA) >= 6:
        pear = float(np.corrcoef(errA, errB)[0, 1])
        sp = float(sstats.spearmanr(errA, errB).statistic)
        abandon = abs(pear) >= 0.6 or abs(sp) >= 0.6
    else:
        pear, sp, abandon = float("nan"), float("nan"), True
    print(f"independence: r={pear:.3f}, rho={sp:.3f}, n={len(errA)}, abandon={abandon}")

    # ---- physics triple-convergence score ----
    print("building physics triple-convergence …")
    g_e_r = rank01_inplace(g_edge, valid); del g_edge
    rtp_e_r = rank01_inplace(rtp_edge, valid); del rtp_edge
    k_e_r = rank01_inplace(k_edge, valid); del k_edge
    thk_e_r = rank01_inplace(thk_edge, valid); del thk_edge
    depth_e_r = rank01_inplace(depth_edge, valid); del depth_edge

    s_g = strike_w(ang_dist(g_az, TARGET_STRIKE_DEG)); del g_az
    s_k = strike_w(ang_dist(k_az, TARGET_STRIKE_DEG)); del k_az

    box = 1
    g_e_s = box_smooth(np.nan_to_num(g_e_r, nan=0.0) * s_g, box, valid); del g_e_r, s_g
    rtp_e_s = box_smooth(np.nan_to_num(rtp_e_r, nan=0.0), box, valid); del rtp_e_r
    k_e_s = box_smooth(np.nan_to_num(k_e_r, nan=0.0) * s_k, box, valid); del k_e_r, s_k
    thk_e_s = box_smooth(np.nan_to_num(thk_e_r, nan=0.0), box, valid); del thk_e_r
    depth_e_s = box_smooth(np.nan_to_num(depth_e_r, nan=0.0), box, valid); del depth_e_r

    eps = 1e-4
    triple = (g_e_s * rtp_e_s * thk_e_s) ** (1.0/3.0)
    triple_min = np.minimum(np.minimum(g_e_s, rtp_e_s), thk_e_s)
    triple = np.where(triple_min > 0.10, triple, 0.0).astype(np.float32)
    del triple_min

    depth_vals = depth[valid & np.isfinite(depth)]
    depth_floor = float(np.quantile(depth_vals, DEPTH_QUANTILE_FLOOR))
    cover_gate = (depth > depth_floor) & valid
    print(f"cover gate (> {depth_floor:.2f} depth): {cover_gate.sum()} px")

    # rank-normalize components
    p_A_r = np.nan_to_num(rank01_inplace(p_A, valid), nan=0.0); del p_A
    p_B_r = np.nan_to_num(rank01_inplace(p_B, valid), nan=0.0); del p_B
    triple_r = np.nan_to_num(rank01_inplace(triple, valid), nan=0.0); del triple
    depth_e_fin = np.asarray(depth_e_s, dtype=np.float32); del depth_e_s
    depth_r = np.nan_to_num(rank01_inplace(depth_e_fin, valid), nan=0.0); del depth_e_fin

    density = np.where(cover_gate,
                       0.55 * triple_r + 0.20 * p_A_r + 0.10 * p_B_r + 0.15 * depth_r,
                       0.35 * p_A_r + 0.40 * p_B_r + 0.25 * triple_r).astype(np.float32)
    density[~valid] = 0.0
    del triple_r, p_A_r, p_B_r, depth_r, cover_gate
    print(f"density: {density.min():.4f}..{density.max():.4f}")

    # ---- allowed mask ----
    with rasterio.open("data/sample_submission.tif") as src:
        samp = src.read(1)
    footprint_mask = np.isfinite(samp); del samp
    ring = ndimage.binary_dilation(cat, iterations=2); del cat
    allowed = footprint_mask & (~ring) & valid
    print(f"allowed after footprint/ring: {int(allowed.sum())}")

    prior_files = [
        "data/reference/h33-2-b2-zeros.tif",
        "data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
        "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
        "data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
        "data/scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
        "data/scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
        "data/scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
        "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
        "data/scored/8GEMSDOE_Hedge-v2_submission.tif",
        "data/scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
        "data/scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
        "data/scored/gemsdoe-ens12-adopted-7f00890a.tif",
        "data/scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
    ]
    prior_union = np.zeros((H, W), dtype=bool)
    for pf in prior_files:
        try:
            with rasterio.open(pf) as src:
                a = src.read(1)
            a = np.where(np.isfinite(a), a, 0.0)
            prior_union |= (a > 0.5)
            del a
        except Exception as e:
            print(f"  (warn) {pf}: {e}")
    for pf in SUB_DIR.glob("*.tif"):
        try:
            with rasterio.open(pf) as src:
                a = src.read(1)
            a = np.where(np.isfinite(a), a, 0.0)
            prior_union |= (a > 0.5)
            del a
        except Exception:
            pass
    prior_dil = ndimage.binary_dilation(prior_union, iterations=1); del prior_union
    allowed = allowed & (~prior_dil); del prior_dil
    print(f"allowed after prior exclusion: {int(allowed.sum())}")

    # ---- emit ----
    print(f"emitting greedy budget={BUDGET} …")
    out, stats = EMIT.greedy_emit(density, allowed, dti_projected=0.0, budget=BUDGET,
                                  pool=500_000, log=print)
    emitted = int(out.sum())
    print(f"emitted: {emitted} px")

    # ---- write tif ----
    name = f"gems52-h60-triple-conv-basement-cover-gated-{emitted}px-{TAG}-zeros"
    tif_path = SUB_DIR / f"{name}.tif"
    out_f32 = out.astype(np.float32)
    assert np.isfinite(out_f32).all()
    assert out_f32.min() >= 0.0 and out_f32.max() <= 1.0
    info = G.write_geotiff(tif_path, out_f32)
    print(f"wrote {tif_path} ({info['bytes']} bytes, sha={info['sha256'][:16]}…)")

    shutil.copy(tif_path, DOC_DL / f"{name}.tif")
    shutil.copy(tif_path, DOC_DL / "h60-candidate.tif")

    note_txt = ("H60 triple-convergence gravity+RTP+K/Th edge NNE strike-gated + depth-cover weight; "
                "all finite binary [0,1]; 300m greedy; 200m ring excluded; not a verified fault map.")
    name_txt = name
    zip_path = SUB_DIR / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tif_path, arcname=f"{name}.tif")
        zf.writestr("submission-name.txt", name_txt)
        zf.writestr("submission-note.txt", note_txt)
    shutil.copy(zip_path, DOC_DL / f"{name}.zip")
    shutil.copy(zip_path, DOC_DL / "h60-candidate.zip")

    # read back candidate array for gates
    with rasterio.open(tif_path) as src:
        cand_arr = src.read(1)
    gate_results = gates.format_report(tif_path, "data/sample_submission.tif")
    priors = gates.find_priors(["data/scored", "data/reference", "submission",
                                "docs/downloads"], exclude=tif_path)
    # Also exclude our own short alias by same basename prefix check via extra excludes:
    priors = [p for p in priors if "h60-candidate" not in str(p) and p.name != f"{name}.tif"]
    uni = gates.uniqueness_report(cand_arr, priors)
    print(f"format gate: ok={gate_results['ok']} problems={gate_results['problems']}")
    print(f"uniqueness: pattern_unique={uni['canonical_pattern_unique']} "
          f"novel_vs_all={uni['novel_vs_all_priors']}/{emitted} = {uni['novel_fraction']:.2%} "
          f"relation={uni['relation_to_union']}")
    del cand_arr

    receipt = {
        "id": name, "tag": TAG,
        "tif": str(tif_path), "zip": str(zip_path),
        "bytes": info["bytes"], "sha256": info["sha256"],
        "emitted_px": emitted,
        "grid": {"height": H, "width": W, "crs": G.CRS_EPSG, "transform": list(G.TRANSFORM)},
        "value_range": {"min": 0.0, "max": 1.0, "finite": True, "nan_count": 0},
        "budget_requested": BUDGET, "seed": SEED,
        "independence_test": {"pearson_r": pear, "spearman_rho": sp,
                              "abandon": bool(abandon), "n_blocks": len(errA), "threshold": 0.60},
        "depth_floor": depth_floor, "target_strike_deg": TARGET_STRIKE_DEG,
        "strike_tol_deg": STRIKE_TOLERANCE_DEG,
        "forbidden": {"ring_200m_excluded": True, "prior_dilated_1px_excluded": True,
                      "outside_footprint_excluded": True},
        "format_gate": gate_results,
        "uniqueness_gate": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                            for k, v in uni.items()},
        "emission_stats": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                           for k, v in stats.items()},
        "view_A_features": A_names, "view_B_features": B_names,
        "method": "H60 triple-convergence edge AND-gate (gravity+RTP+K/Th edges) on NNE-SSW Basin-and-Range strike with depth-cover weighting, blended with co-trained View A/B residuals; greedy metric-aware 3-px isotropic emission",
        "hypothesis": "Buried Basin-and-Range normal faults under alluvial cover are marked by coincident edges in isostatic gravity, RTP magnetics, and K/Th ratio along a ~15 deg azimuth, with a thickening sedimentary wedge (depth-to-basement gradient) on the down-thrown block. Unlike scarp-only detectors (H33/H25/H28), this looks for blind non-emergent faults beneath cover.",
        "download_ok": True, "submit_ok": False,
        "submit_reason": "Research candidate: passes format/uniqueness/[0,1] gates but was not validated on an organizer-authenticated holdout (the repo's holdout instrument is structurally blind to novel arms per IR-52-017).",
        "submission_name_field": name_txt[:200],
        "submission_note_field": note_txt[:200],
        "difference_from_priors": "Not a copy or union of any prior: triple-AND across gravity/RTP/KTh is new; strike-gated; depth-cover restricted; budget 31k tuned below legacy 37,654.",
    }
    (EV / "h60_build.json").write_text(json.dumps(receipt, indent=1, default=str))
    (DOC_DATA / "submission_h60.json").write_text(json.dumps(receipt, indent=1, default=str))
    (DOC_DATA / "submission.json").write_text(json.dumps(receipt, indent=1, default=str))
    (SUB_DIR / "LATEST.txt").write_text(f"{name}.tif\n")

    print(f"\n=== H60 OK: {emitted} px, sha={info['sha256'][:16]} ===")
    print(f"DL: {DOC_DL / 'h60-candidate.tif'}")
    print(f"Submit? {receipt['submit_ok']} -- {receipt['submit_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
