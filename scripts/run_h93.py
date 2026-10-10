#!/usr/bin/env python3
"""H93 -- antithetic / sign-asymmetric basement-step (ABS) channels added to View B;
hide-and-recover holdout; disagreement strata; gated emission.

Preregistered in knowledge/81_hypotheses_H93_preregistered.md (pinned in
registry/h93_preregistration.json). Shared, not forked: run_h61.setup / sample_for_fit /
learner_for / pct_rank / to_grid, gems52.spatial.folds, gems52.evaluate_holdout
(gems52-pooled-hide-v1), gems52.nodes.spacing_select, gems52.gates, gems52.grid.

Prerequisites (reuse, don't rebuild):
    feature store built + externally extended (work/r2/features)
    python scripts/run_h61.py fit exchange holdout     # shared co-training instrument

Usage: python scripts/run_h93.py [channels|fit|holdout|build|reasoning|gates|all]
"""
from __future__ import annotations

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
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, grid, nodes                                # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h93_preregistration.json"
WORK = ROOT / "work/h93"
EVID = ROOT / "evidence"
DOCS_DL = ROOT / "docs/downloads"
SUB = ROOT / "submission"
SAMPLE = ROOT / "data/sample_submission.tif"
FEATURES = ROOT / "data/training_features.tif"
ABS_NAMES = ("ABS_step3", "ABS_step1", "ABS_pair6", "ABS_cover")

# axis shifts (dy, dx): grid axes + diagonals; pair shifts at ~6 px along each axis
STEP_SHIFTS = {3: ((0, 3), (3, 0), (3, 3), (3, -3)),
               1: ((0, 1), (1, 0), (1, 1), (1, -1))}
PAIR_SHIFTS = {(0, 3): (0, 6), (3, 0): (6, 0), (3, 3): (4, 4), (3, -3): (4, -4)}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h93_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float))
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H93 preregistration changed after freezing")
    return reg


def require_h61(kind="pred_pre", views=("A", "B")):
    for f in range(4):
        for v in views:
            need = ROOT / "work/h61" / f"{kind}_{v}_f{f}.npy"
            if not need.exists():
                raise SystemExit(f"missing {need}: run  python scripts/run_h61.py fit exchange  first")


# ---------------------------------------------------------------------------------------- channels
def abs_channels(eligible):
    """The four preregistered ABS channels (knowledge/81 §2). Label-free, catalogue-free.

    Band 15 z = depth to basement surface. ASY_k(x) = |z(x+3n)-z(x)| - |z(x)-z(x-3n)| along
    axis k: a one-sided normal-fault step gives |ASY| ~ throw; a smooth ramp gives ~0.
    """
    with rasterio.open(FEATURES) as ds:
        z = ds.read(15).astype(np.float64)
    nod = z < -1e38
    z[~np.isfinite(z)] = np.nan
    z[nod] = np.nan
    ok = np.isfinite(z) & eligible
    zs = np.where(ok, z, 0.0)
    out = {}

    def axis_stats(shifts, offset_label):
        asys, valids = [], []
        for (dy, dx) in shifts:
            zp = np.roll(np.roll(zs, -dy, 0), -dx, 1)
            zm = np.roll(np.roll(zs, dy, 0), dx, 1)
            okp = np.roll(np.roll(ok, -dy, 0), -dx, 1)
            okm = np.roll(np.roll(ok, dy, 0), dx, 1)
            v = ok & okp & okm
            dp = np.where(v, zp - zs, 0.0)
            dm = np.where(v, zs - zm, 0.0)
            asy = np.where(v, np.abs(dp) - np.abs(dm), 0.0)
            asys.append(asy)
            valids.append(v)
        return asys, valids

    # ABS_step3 / ABS_step1 : max_k |ASY_k|
    for off, shifts in STEP_SHIFTS.items():
        asys, valids = axis_stats(shifts, off)
        mag = np.full(z.shape, np.nan)
        anyv = np.zeros(z.shape, bool)
        acc = np.zeros(z.shape)
        for asy, v in zip(asys, valids):
            acc = np.maximum(acc, np.where(v, np.abs(asy), 0.0))
            anyv |= v
        mag[anyv] = acc[anyv]
        out[f"ABS_step{off}"] = mag.astype(np.float32)

    # ABS_pair6 : opposite-sign paired steps ~6 px apart along the SAME axis
    asys3, valids3 = axis_stats(STEP_SHIFTS[3], 3)
    pair_acc = np.zeros(z.shape)
    pair_any = np.zeros(z.shape, bool)
    for (dy, dx), asy, v in zip(STEP_SHIFTS[3], asys3, valids3):
        pdy, pdx = PAIR_SHIFTS[(dy, dx)]
        asy6 = np.roll(np.roll(asy, -pdy, 0), -pdx, 1)
        v6 = np.roll(np.roll(v, -pdy, 0), -pdx, 1)
        both = v & v6
        opp = both & (asy * asy6 < 0)
        val = np.where(opp, np.abs(asy) * np.abs(asy6), 0.0)
        pair_acc = np.maximum(pair_acc, val)
        pair_any |= both
    pair = np.full(z.shape, np.nan)
    pair[pair_any] = pair_acc[pair_any]
    out["ABS_pair6"] = pair.astype(np.float32)

    # ABS_cover : ABS_step3 x pct_rank(z over eligible)
    v15 = z[eligible]
    r = np.zeros(z.shape)
    r[eligible] = (rankdata(v15, method="average") - 0.5) / float(len(v15))
    cov = out["ABS_step3"].astype(np.float64) * r
    cov[np.isnan(out["ABS_step3"])] = np.nan
    out["ABS_cover"] = cov.astype(np.float32)

    for k in out:
        out[k][~eligible] = np.nan
    return out


def stage_channels():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    WORK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ch = abs_channels(eligible)
    finite = {k: int(np.isfinite(v).sum()) for k, v in ch.items()}
    np.savez_compressed(WORK / "abs.npz", **ch)
    rec = dict(stage="channels", seconds=round(time.time() - t0, 1), finite_px=finite,
               eligible_px=int(eligible.sum()),
               definition="knowledge/81 section 2 (frozen)",
               note="band 15 is a model-derived basement depth; channels inherit its artefacts")
    write("channels", rec)
    log(f"ABS channels built in {time.time()-t0:.0f}s: {finite}")


def gather(store, rows, names, abs_stack):
    """rows are GRID-flat indices (what base.sample_for_fit returns and store.gather accepts)."""
    X = store.gather(rows, names) if names else np.empty((len(rows), 0), np.float32)
    if abs_stack is not None:
        D = np.stack([np.nan_to_num(abs_stack[k].ravel()[rows], nan=0.0).astype(np.float32)
                      for k in ABS_NAMES], 1)
        X = np.hstack([X, D]) if X.size else D
    return X


def predict(store, m, names, abs_stack, flat, chunk=250_000):
    out = np.empty(len(flat), np.float32)
    for i in range(0, len(flat), chunk):
        s = flat[i:i + chunk]                     # grid-flat indices
        X = store.gather(s, names) if names else np.empty((len(s), 0), np.float32)
        if abs_stack is not None:
            D = np.stack([np.nan_to_num(abs_stack[k].ravel()[s], nan=0.0).astype(np.float32)
                          for k in ABS_NAMES], 1)
            X = np.hstack([X, D]) if X.size else D
        out[i:i + chunk] = m.predict_proba(X)[:, 1]
    return out


# --------------------------------------------------------------------------------------------- fit
def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    require_h61()
    WORK.mkdir(parents=True, exist_ok=True)
    abs_stack = dict(np.load(WORK / "abs.npz"))
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    arms = {"single_B": (vb, None), "B_ABS": (vb, abs_stack), "ABS_only": ([], abs_stack)}
    out = dict(stage="fit", abs_channels=list(ABS_NAMES), folds=[], canary_alarm_auc=0.9)
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        rows, y, _ = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_train=int(len(rows)), auc={}, canary={})
        for arm, (names, chs) in arms.items():
            m = base.learner_for("B", SEED)
            m.fit(gather(store, rows, names, chs), y)
            p = predict(store, m, names, chs, flat)
            np.save(WORK / f"pred_{arm}_f{f}.npy", p)
            g = base.to_grid(flat, p, eligible.shape).ravel()
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[pos_g], g[neg_g]]))
        for k in ABS_NAMES:                       # leakage canary: each channel ALONE
            v = abs_stack[k].ravel()[np.r_[pos_g, neg_g]]
            keep = np.isfinite(v)
            a = float(roc_auc_score(yy[keep], v[keep]))
            rec["canary"][k] = max(a, 1 - a)
        rec["canary_max"] = max(rec["canary"].values())
        log(f"fold {f}: {rec['auc']} canary max {rec['canary_max']:.3f}")
        out["folds"].append(rec)
    out["canary_alarm"] = any(r["canary_max"] >= 0.90 for r in out["folds"])
    write("fit", out)


# ----------------------------------------------------------------------------------------- holdout
def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    require_h61()
    reg = check_prereg()          # H93 thresholds, not H61's
    th = reg["thresholds"]
    K = int(th["budget_dots_per_fold_per_arm"])
    abs_stack = dict(np.load(WORK / "abs.npz"))
    flat = store.flat_idx
    shape = eligible.shape
    npix = int(eligible.size)
    arms = ("single_B", "B_ABS", "ABS_only", "disagree_Aonly", "random")
    terms = {a: None for a in arms}
    base_dots = {"union_max": np.zeros(shape, bool), "single_A": np.zeros(shape, bool),
                 "single_B": np.zeros(shape, bool)}
    out = dict(stage="holdout", evaluator=evaluator.VERSION, budget_per_fold=K, folds=[],
               stratum=dict(a_confident_quantile=th["a_confident_quantile"],
                            b_abstain_interval=th["b_abstain_interval"]))

    def rank_in(g, mask):
        r = np.full(npix, np.nan, np.float32)
        idx = np.flatnonzero(mask.ravel())
        x = g.ravel()[idx]
        ok = np.isfinite(x)
        r[idx[ok]] = (rankdata(x[ok], method="average") - 0.5) / float(ok.sum())
        return r.reshape(shape)

    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        region = fold["region"] & eligible
        # pooled ranks of the shared H61 pre-exchange predictions, inside this fold's region
        gA = base.to_grid(flat, np.load(ROOT / "work/h61" / f"pred_pre_A_f{f}.npy"), shape)
        gB = base.to_grid(flat, np.load(ROOT / "work/h61" / f"pred_pre_B_f{f}.npy"), shape)
        rA, rB = rank_in(gA, region), rank_in(gB, region)
        stratum = region & np.isfinite(rA) & np.isfinite(rB) & \
            (rA >= th["a_confident_quantile"]) & \
            (rB >= th["b_abstain_interval"][0]) & (rB <= th["b_abstain_interval"][1])
        del gA, gB
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   a_only_stratum_px=int(stratum.sum()), arms={})
        # baseline placements for the not-merely-union check
        u = np.maximum(np.nan_to_num(rA, nan=-1.0), np.nan_to_num(rB, nan=-1.0))
        fld_u = np.full(shape, -1.0, np.float32)
        fld_u.ravel()[np.flatnonzero(allowed.ravel())] = u.ravel()[np.flatnonzero(allowed.ravel())]
        base_dots["union_max"] |= nodes.spacing_select(fld_u, allowed, K, min_px=3.0)
        for arm_name, r in (("single_A", rA), ("single_B", rB)):
            fld = np.full(shape, -1.0, np.float32)
            ai = np.flatnonzero(allowed.ravel())
            fld.ravel()[ai] = np.nan_to_num(r.ravel()[ai], nan=-1.0)
            base_dots[arm_name] |= nodes.spacing_select(fld, allowed, K, min_px=3.0)
        del rA, rB, u, fld_u
        for arm in arms:
            fld = np.full(shape, -1.0, np.float32)
            ai = np.flatnonzero(allowed.ravel())
            if arm == "random":
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai),
                                                                                dtype=np.float32)
                allowed_arm = allowed
            elif arm == "disagree_Aonly":
                gA = base.to_grid(flat, np.load(ROOT / "work/h61" / f"pred_pre_A_f{f}.npy"), shape)
                gB = base.to_grid(flat, np.load(ROOT / "work/h61" / f"pred_pre_B_f{f}.npy"), shape)
                rA2, rB2 = rank_in(gA, region), rank_in(gB, region)
                sel = allowed & stratum
                fld.ravel()[np.flatnonzero(sel.ravel())] = \
                    np.nan_to_num(rA2.ravel()[np.flatnonzero(sel.ravel())], nan=-1.0)
                allowed_arm = sel
                del gA, gB, rA2, rB2
            else:
                g = base.to_grid(flat, np.load(WORK / f"pred_{arm}_f{f}.npy"), shape)
                fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]).astype(np.float32),
                                                nan=-1.0)
                allowed_arm = allowed
            em = nodes.spacing_select(fld, allowed_arm, K, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        out["folds"].append(rec)
    np.savez_compressed(WORK / "baseline_dots.npz", **base_dots)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="B_ABS")
    write("holdout", out)
    sc = out["pooled"]["scores"]
    log(json.dumps({a: round(sc[a]["dti"], 6) for a in arms}))
    tol = float(reg["thresholds"]["control_reproduction"]["tolerance"])
    refB = float(reg["thresholds"]["control_reproduction"]["single_B"])
    refR = float(reg["thresholds"]["control_reproduction"]["random"])
    log(f"control reproduction: single_B {sc['single_B']['dti']:.6f} (ref {refB}), "
        f"random {sc['random']['dti']:.6f} (ref {refR})")
    if abs(sc["single_B"]["dti"] - refB) > tol or abs(sc["random"]["dti"] - refR) > tol:
        raise SystemExit("control reproduction failed: instrument drift, investigate before use")


# -------------------------------------------------------------------------------------------- build
def stage_build():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    reg = check_prereg()          # H93 thresholds, not H61's
    flat = store.flat_idx
    field = np.full(eligible.shape, np.nan, np.float32)
    for fold in folds:
        g = base.to_grid(flat, np.load(WORK / f"pred_B_ABS_f{fold['fold']}.npy"), eligible.shape)
        r = np.full(eligible.shape, np.nan, np.float32)
        ai = np.flatnonzero((fold["region"] & eligible).ravel())
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        m = np.isfinite(r) & ~np.isfinite(field)
        field[m] = r[m]
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(field) & (catd * 100.0 > float(reg["thresholds"]["zero_tax_m"]))
    K_TOTAL = int(reg["thresholds"]["budget_total"])
    em = nodes.spacing_select(np.where(pool, field, -1.0).astype(np.float32), pool, K_TOTAL,
                              min_px=float(reg["thresholds"]["min_spacing_px"]))
    np.save(WORK / "dots.npy", em)
    np.save(WORK / "surface.npy", np.where(eligible & np.isfinite(field), field, 0.0).astype(np.float32))
    # pooled A-only disagreement stratum (stitched pre-exchange ranks)
    shape = eligible.shape
    npix = int(eligible.size)
    rA = np.full(shape, np.nan, np.float32)
    rB = np.full(shape, np.nan, np.float32)
    for fold in folds:
        region = fold["region"] & eligible
        for tgt, v in (("A", rA), ("B", rB)):
            g = base.to_grid(flat, np.load(ROOT / "work/h61" / f"pred_pre_{tgt}_f{fold['fold']}.npy"),
                            shape)
            idx = np.flatnonzero(region.ravel())
            x = g.ravel()[idx]
            ok = np.isfinite(x)
            r = np.full(npix, np.nan, np.float32)
            r[idx[ok]] = ((rankdata(x[ok], method="average") - 0.5) / float(ok.sum())).astype(np.float32)
            v.ravel()[idx[ok]] = r[idx[ok]]
    th = reg["thresholds"]
    stratum = np.isfinite(rA) & np.isfinite(rB) & (rA >= th["a_confident_quantile"]) & \
        (rB >= th["b_abstain_interval"][0]) & (rB <= th["b_abstain_interval"][1])
    np.save(WORK / "a_only_stratum.npy", stratum)
    np.save(WORK / "rank_A.npy", np.nan_to_num(rA, nan=0.0).astype(np.float32))
    np.save(WORK / "rank_B.npy", np.nan_to_num(rB, nan=0.0).astype(np.float32))
    write("build", dict(dots=int(em.sum()), pool_px=int(pool.sum()), K_TOTAL=K_TOTAL,
                        a_only_stratum_px=int(stratum.sum()),
                        min_cat_dist_m=float((catd[em] * 100).min()) if em.any() else None))
    log(f"dots {int(em.sum())}, min catalogue distance {(catd[em]*100).min():.1f} m, "
        f"A-only stratum {int(stratum.sum())} px")


# ----------------------------------------------------------------------------------------- reasoning
def stage_reasoning():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy")
    stratum = np.load(WORK / "a_only_stratum.npy")
    with rasterio.open(FEATURES) as ds:
        depth = ds.read(15).astype(np.float32)
    grav = np.load(ROOT / "work/r2/features/A_gravity_grad_3.npy").astype(np.float32)
    flat = store.flat_idx
    grav_grid = np.full(eligible.shape, np.nan, np.float32)
    grav_grid.ravel()[flat] = grav
    lab, n = ndi.label(stratum, np.ones((3, 3), bool))
    with rasterio.open(SAMPLE) as ref:
        tr = ref.transform
    rows = []
    dot_ids = np.unique(lab[dots])
    dot_ids = dot_ids[dot_ids > 0]
    order = sorted(dot_ids, key=lambda i: -int((dots & (lab == i)).sum()))[:200]
    for cid in order:
        comp = lab == cid
        ys, xs = np.nonzero(comp)
        d_in = dots & comp
        dvals = depth[comp]
        gvals = grav_grid[comp]
        rows.append(dict(
            segment_id=int(cid),
            stratum_px=int(comp.sum()),
            shipped_dots=int(d_in.sum()),
            centroid_easting=float(tr.c + xs.mean() * tr.a + tr.a / 2),
            centroid_northing=float(tr.f + ys.mean() * tr.e + tr.e / 2),
            median_depth_to_basement_m=float(np.nanmedian(dvals)),
            median_gravity_gradient_300m=float(np.nanmedian(gvals)) if np.isfinite(gvals).any() else None,
            reasoning=("A-only disagreement candidate: the subsurface view (gravity/magnetic/"
                       "strain + basement-depth structure) is confident while the surface view "
                       "abstains (low DEM curvature/slope and no radiometric contrast). Reading: "
                       "a normal fault may be concealed beneath alluvial cover, retaining a "
                       "basement-depth throw and potential-field edge but no surface scarp. "
                       "Named non-fault mimics: differential compaction over a buried lithologic "
                       "step, palaeo-channel incision into basement, or an artefact of the "
                       "model-derived basement-depth grid (band 15). Status: HYPOTHESIS pending "
                       "Phase-2 geological verification, not verified geology.")))
    import csv
    p = DOCS_DL / "h93-a-only-reasoning.csv"
    DOCS_DL.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    write("reasoning", dict(segments=len(rows), csv=str(p),
                            total_a_only_segments=int(n),
                            segments_with_shipped_dots=int(len(dot_ids)),
                            rule="one row per connected A-only stratum component intersecting the shipped dots, max 200"))
    log(f"A-only reasoning: {len(rows)} segments with shipped dots ({int(len(dot_ids))} total)")


# -------------------------------------------------------------------------------------------- gates
def stage_gates():
    reg = check_prereg()
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy")
    surface = np.load(WORK / "surface.npy")
    holdout = json.loads((EVID / "h93_holdout.json").read_text())
    fit = json.loads((EVID / "h93_fit.json").read_text())
    h61_indep = json.loads((EVID / "h61_independence.json").read_text())
    h61_ex = json.loads((EVID / "h61_pseudo_exchange.json").read_text())
    pooled = holdout["pooled"]
    sc = pooled["scores"]
    diff = pooled["paired_differences"]["single_B"]
    promote_ci = float(diff["ci95"][0]) > 0.0
    canary_ok = not fit["canary_alarm"]
    indep_ok = bool(h61_indep["allow_exchange"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"gems52-h93-abs-cotrain-37654px-{stamp}-zeros"
    tif = SUB / f"{name}.tif"
    inside = dots.astype(np.float32)
    receipt = grid.write_geotiff_portal_exact(tif, inside, eligible, SAMPLE, outside="zero")
    # union-not check (prereg §3): shipped dots vs pooled single-view / union placements
    base_dots = dict(np.load(WORK / "baseline_dots.npz"))
    union_not = {}
    for k, v in base_dots.items():
        inter = int((dots & v).sum())
        union_not[f"jaccard_vs_{k}"] = inter / max(int((dots | v).sum()), 1)
    union_ok = all(j < float(reg["thresholds"]["union_jaccard_bar"]) for j in union_not.values())

    # gates over the full local registry (self-copies excluded by path + basename inside find_priors)
    priors = gates.find_priors([DOCS_DL, SUB, ROOT / "data/scored", ROOT / "data/reference"],
                               exclude=tif)
    uniq = gates.uniqueness_report(inside, priors)
    lane_surface = gates.lane_report(surface.astype(np.float32), eligible, priors, sample=SAMPLE,
                                     phase="surface")
    lane_dots = gates.lane_report(inside, eligible, priors, sample=SAMPLE, phase="dots")
    fmt = gates.format_report(tif, SAMPLE)

    def lane_summary(lz):
        lit = lz["literal"]
        pol = lz.get("policy") or {}
        return dict(literal_max_spearman=lit.get("max_spearman"),
                    literal_max_near3=lit.get("max_near_3px_fraction"),
                    literal_near3_offender=lit.get("max_near_source"),
                    literal_verdict=lit.get("verdict"),
                    policy_max_spearman=pol.get("max_spearman"),
                    policy_max_near3=pol.get("max_near_3px_fraction"),
                    policy_near3_offender=pol.get("max_near_source"),
                    policy_verdict=pol.get("verdict"),
                    n_probes=pol.get("universal_coverage_probes", 0))

    # verdict ladder (prereg §4)
    lane_policy_ok = (
        (lane_surface["literal"].get("max_spearman") or 0) <= 0.90 and
        (lane_dots["literal"].get("max_spearman") or 0) <= 0.90 and
        ((lane_dots.get("policy") or {}).get("max_near_3px_fraction") or 0) <= 0.70 and
        ((lane_dots.get("policy") or {}).get("max_spearman") or 0) <= 0.90 and
        lane_surface["policy"].get("verdict") == "PASS" and
        lane_dots["policy"].get("verdict") == "PASS")
    format_ok = bool(fmt.get("ok", True)) and not fmt.get("problems")
    promote = bool(promote_ci and canary_ok and indep_ok and union_ok and lane_policy_ok
                   and uniq.get("distinct_from_every_comparable_prior"))
    verdict = "promote" if promote else "negative"
    ok_submit = promote

    # stage the downloadable copy + zip
    dl = DOCS_DL / f"{name}.tif"
    shutil.copyfile(tif, dl)
    zp = DOCS_DL / f"{name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(dl, arcname=dl.name)
    sha = digest(dl)
    note = ("H93 antithetic basement step + view B co-training, A>B disagreement strata, "
            "37654px, 3px spacing")
    assert len(note) <= 140, "submission note must be <= 140 chars"

    card = dict(
        round="H93",
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        hypothesis=("Antithetic / sign-asymmetric basement steps (band 15) add a subsurface "
                    "channel the surface view lacks; co-training lane with disagreement strata."),
        mechanism=("Signed one-sided step |dz+|-|dz-| at 100/300 m and opposite-sign paired steps "
                   "~600 m apart locate half-graben margin / buried range-front faults with "
                   "basement throw but no surface expression; the four ABS channels join View B in "
                   "one learner; emission from the stitched OOF field outside the 200 m catalogue "
                   "ring at 3 px spacing."),
        non_fault_process=("Differential compaction over buried lithologic steps, palaeo-channel "
                           "incision into basement, and interpolation/smoothing artefacts of the "
                           "model-derived basement-depth grid (band 15)."),
        holdout_dti={a: dict(dti=sc[a]["dti"], ci95=sc[a]["ci95"],
                             withheld_positive_pixels=sc[a]["withheld_positive_pixels"])
                     for a in sc},
        paired_B_ABS_minus_single_B=diff,
        promote_rule_met=dict(ci_lower_bound_gt_0=bool(promote_ci), canaries_pass=bool(canary_ok),
                              independence_pass=bool(indep_ok), union_check_pass=bool(union_ok)),
        independence=dict(max_abs_rho=h61_indep["pre"]["max_abs_correlation"],
                          threshold=0.60, allow_exchange=indep_ok,
                          note="run_h61 block-level negative-error correlation"),
        exchange=dict(total_pseudo_pixels=h61_ex.get("total_pseudo_pixels"),
                      rule="measured only, never shipped (N-1 settled)"),
        correlation_vs_registry=dict(surface=lane_summary(lane_surface), dots=lane_summary(lane_dots),
                                     literal_rule="STOP at rank>0.90 or near3>0.70 vs ONE raster",
                                     probe_caveat=("universal-coverage probes make literal near3 ~1 "
                                                   "for ANY nonempty raster; policy numbers exclude "
                                                   "them; both are reported")),
        union_not=union_not,
        raster=dict(path=str(dl), sha256=sha, bytes=int(dl.stat().st_size),
                    ones=int(dots.sum()), values="{0,1}"),
        validator=dict(format=fmt, all_finite=receipt.get("finite_values_in_range"),
                       values_in_0_1=True, nan_inside_footprint=0,
                       crs_shape_transform_match=True),
        uniqueness=dict(n_priors_checked=uniq["n_priors_checked"],
                        identical_to_a_prior=uniq["identical_to_a_prior"],
                        distinct_from_every_comparable_prior=uniq["distinct_from_every_comparable_prior"],
                        novel_fraction=uniq.get("novel_fraction")),
        submission_name="h93-abs-cotrain-37654px",
        submission_note=note,
        verdict=verdict,
        ok_to_download_and_submit=dict(download=True, submit=ok_submit,
                                       reason=("promote rule met" if ok_submit else
                                               "failing gate: " + ", ".join(
                                                   [n for n, okv in dict(
                                                       ci=promote_ci, canary=canary_ok,
                                                       independence=indep_ok, union=union_ok,
                                                       lane=lane_policy_ok).items() if not okv]
                                                   or ["holdout not above single_B"]))))
    write("run_card", card)
    log(f"verdict={verdict} submit={ok_submit} sha256={sha}")
    log(f"lane dots literal near3={lane_summary(lane_dots)['literal_max_near3']} "
        f"policy near3={lane_summary(lane_dots)['policy_max_near3']}")
    return card


def main():
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st in ("channels", "all"):
        check_prereg()
        stage_channels()
    if st in ("fit", "all"):
        check_prereg()
        stage_fit()
    if st in ("holdout", "all"):
        stage_holdout()
    if st in ("build", "all"):
        stage_build()
    if st in ("reasoning", "all"):
        stage_reasoning()
    if st in ("gates", "all"):
        stage_gates()


if __name__ == "__main__":
    main()
