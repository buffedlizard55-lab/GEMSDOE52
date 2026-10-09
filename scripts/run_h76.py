#!/usr/bin/env python3
"""H76-E2: rank new off-catalogue detector fields on the SHARED hide-and-recover holdout.

Reuses the template instruments -- run_h61.setup() (feature store, label-blind quadrant folds,
200 m visible-catalogue ring), gems52.nodes.spacing_select (metric-motivated placement) and
gems52.evaluate_holdout (pooled DTI + paired block bootstrap).  No private fork of any of them.

Every field below is an unsupervised function of the raster columns only.  No label, no fold truth
and no fold geometry enters any field, so there is nothing to leak.  The controls (`single_B`,
`random`) are the template's own, so the numbers are directly comparable to the committed H61/H71
control value.

Memory note: the sandbox has 3.9 GB.  Every intermediate is float32, ranking is done only over the
4.59 M-pixel eligible footprint, and each band is released before the next is read.
"""
from __future__ import annotations
import gc, json, sys, time
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import run_h61 as base                                             # noqa: E402
from gems52 import nodes, evaluate_holdout as evaluator             # noqa: E402

EVID = ROOT / "evidence"; WORK = ROOT / "work/h76"
EVID.mkdir(exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
SEED = 520810
K = 9400           # the committed control budget -> comparable to single_B = 0.174571
MIN_PX = 3.0
BUDGET_NOTE = "9,400 dots per fold per arm, the committed H61/H71 control budget"
FEATURES = ROOT / "data/training_features.tif"


def log(*a):
    print(*a, flush=True)


def read_band(path, index, eligible):
    """One band as float32, NaN outside the eligible footprint. Nothing else retained."""
    with rasterio.open(path) as ds:
        raw = ds.read(index).astype(np.float32)
        nod = ds.nodata
    if nod is not None:
        raw[np.isclose(raw, np.float32(nod))] = np.nan
    raw[~eligible] = np.nan
    return raw


def rank_grid(v, eligible):
    """Percentile rank in [0,1] over the eligible footprint only; float32 out."""
    idx = np.flatnonzero(eligible.ravel())
    x = np.asarray(v, np.float32).ravel()[idx]
    out = np.zeros(v.size, np.float32)
    good = np.isfinite(x)
    if good.sum() > 1:
        out[idx[good]] = (rankdata(x[good]) / float(good.sum())).astype(np.float32)
    return out.reshape(v.shape)


def grad_mag(grid):
    """|grad| of a float32 grid, NaN filled with its own median first. float32 out."""
    g = np.array(grid, np.float32, copy=True)
    g[~np.isfinite(g)] = np.float32(np.nanmedian(g)) if np.isfinite(g).any() else 0.0
    a = np.gradient(g, axis=0); b = np.gradient(g, axis=1)
    out = np.hypot(a, b, dtype=np.float32)
    del a, b, g
    return out


def hessian_abs_lmin(grid):
    """|most-negative Hessian eigenvalue| = maximum principal curvature. float32 throughout."""
    g = np.array(grid, np.float32, copy=True)
    med = np.nanmedian(g) if np.isfinite(g).any() else np.float32(0.0)
    g[~np.isfinite(g)] = np.float32(med)
    gy = np.gradient(g, axis=0)
    gx = np.gradient(g, axis=1)
    gyy = np.gradient(gy, axis=0)
    gxy = np.gradient(gy, axis=1)
    gxx = np.gradient(gx, axis=1)
    del gy, gx
    tr = gyy + gxx
    det = gyy * gxx - gxy * gxy
    disc = np.maximum(tr * tr - np.float32(4.0) * det, np.float32(0.0))
    lmin = np.float32(0.5) * (tr - np.sqrt(disc, dtype=np.float32))
    out = np.abs(lmin, dtype=np.float32)
    del gyy, gxy, gxx, tr, det, disc, lmin, g
    return out


def main() -> int:
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    shape = eligible.shape
    npix = int(eligible.size)
    log(f"H76-E2: {len(folds)} label-blind folds, eligible {int(eligible.sum())} px, "
        f"ring {ring_px} px, budget {K} dots/arm/fold")
    for f in folds:
        need = ROOT / "work/h61" / f"pred_pre_B_f{f['fold']}.npy"
        if not need.exists():
            raise SystemExit(f"missing {need}: run  python scripts/run_h61.py fit  first")

    # ---- H76-A: basement-surface curvature, gated to THIN sedimentary cover (band 15)
    b15 = read_band(FEATURES, 15, eligible)
    med15 = float(np.nanmedian(b15))
    curv15 = hessian_abs_lmin(b15)
    thin = np.zeros(shape, np.float32)
    thin[np.isfinite(b15) & (b15 <= np.float32(med15))] = 1.0
    m15 = grad_mag(b15)                       # kept: band-15 slope for H76-C and H76-D
    A = rank_grid(curv15, eligible) * (np.float32(0.35) + np.float32(0.65) * thin)
    del curv15, thin; gc.collect()
    log(f"  built H76-A (basement curvature x thin cover; median cover {med15:.1f})")

    # ---- H76-B: dilatation strain-partition boundary -- |grad| of band 8, not its magnitude
    b08 = read_band(FEATURES, 8, eligible)
    B = rank_grid(grad_mag(b08), eligible)
    del b08; gc.collect()
    log("  built H76-B (geodetic dilatation gradient)")

    # ---- H76-C: conductivity-gradient x basement-step coincidence
    b17 = read_band(FEATURES, 17, eligible)
    C = rank_grid(grad_mag(b17), eligible) * rank_grid(m15, eligible)
    del b17; gc.collect()
    log("  built H76-C (conductivity gradient x basement step)")

    # ---- H76-D: antithetic margin -- basement step gated to the basin floor (band 12 low)
    b12 = read_band(FEATURES, 12, eligible)
    floor = rank_grid(-b12, eligible)
    del b12; gc.collect()
    D = rank_grid(m15, eligible) * (np.float32(0.30) + np.float32(0.70) * floor)
    del m15, floor; gc.collect()
    log("  built H76-D (basement step x basin floor)")

    # ---- H76-E: LiDAR scarp x radiometric-K discordance
    lid = read_band(ROOT / "data/external/lidar_scarp_features_u8.tif", 1, eligible)
    rl = rank_grid(np.nan_to_num(lid, nan=0.0), eligible)
    del lid
    kb = read_band(ROOT / "data/external/geodawn_rad_u8.tif", 1, eligible)
    E = np.float32(0.5) * rl + np.float32(0.5) * rank_grid(grad_mag(kb), eligible)
    del rl, kb; gc.collect()
    log("  built H76-E (LiDAR scarp + radiometric K gradient)")

    # ---- H76-F: equal-weight percentile-rank fusion of the four new structural fields
    F = ((rank_grid(A, eligible) + rank_grid(B, eligible) +
          rank_grid(C, eligible) + rank_grid(D, eligible)) * np.float32(0.25))
    log("  built H76-F (rank fusion of A-D)")

    NEW = {"h76_A_basement_curv_thincover": A, "h76_B_dilatation_gradient": B,
           "h76_C_cond_basement_coincidence": C, "h76_D_antithetic_margin": D,
           "h76_E_lidar_rad_discordance": E, "h76_F_rank_fusion": F}
    del A, B, C, D, E, F; gc.collect()

    out = dict(stage="holdout", budget_per_arm_per_fold=K, min_separation_px=MIN_PX,
               budget_note=BUDGET_NOTE, arms=list(NEW) + ["single_B", "random"], folds=[])
    terms = {a: None for a in out["arms"]}
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        allowed_idx = np.flatnonzero(allowed.ravel())
        preB = np.zeros(npix, np.float32)
        preB[flat] = np.load(ROOT / "work/h61" / f"pred_pre_B_f{f}.npy").astype(np.float32)
        x = preB.ravel()[allowed_idx]
        rB = np.zeros(npix, np.float32)
        rB[allowed_idx] = (rankdata(x) / float(len(x))).astype(np.float32)
        del preB, x
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(npix, np.float32)
        rnd[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        fields = {k: v.ravel() for k, v in NEW.items()}
        fields["single_B"] = rB
        fields["random"] = rnd
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()), arms={})
        for arm, field in fields.items():
            t0 = time.time()
            em = nodes.spacing_select(field.reshape(shape), allowed, K, min_px=MIN_PX)
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=result["dti"], tpw=result["tpw"], emitted=result["emitted"])
            log(f"  fold {f} {arm:32s} emitted {result['emitted']}/{K} "
                f"DTI {result['dti']:.6f} ({time.time()-t0:.0f}s)")
            del em
        del fields, rB, rnd, allowed_idx; gc.collect()
        out["folds"].append(rec)

    summ = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="h76_F_rank_fusion")
    out["pooled"] = json.loads(json.dumps(summ, default=str))
    log("\n=== POOLED HOLDOUT-DTI (evaluator %s, %d folds, %s) ==="
        % (evaluator.VERSION, len(folds), BUDGET_NOTE))
    for arm, row in sorted(summ["scores"].items(), key=lambda kv: -kv[1]["dti"]):
        log(f"  {arm:32s} DTI {row['dti']:.6f}  95% CI [{row['ci95'][0]:.6f}, {row['ci95'][1]:.6f}]"
            f"  withheld_pos_px={row['withheld_positive_pixels']}")
    log("\n  paired deltas vs candidate 'h76_F_rank_fusion':")
    for arm, row in summ["paired_differences"].items():
        log(f"    {arm:32s} delta {row['delta']:+.6f}  95% CI [{row['ci95'][0]:+.6f}, {row['ci95'][1]:+.6f}]")
    (EVID / "h76_holdout.json").write_text(json.dumps(out, indent=1, default=str))
    log(f"\nwrote {EVID/'h76_holdout.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
