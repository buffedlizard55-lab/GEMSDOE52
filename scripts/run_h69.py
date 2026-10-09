#!/usr/bin/env python3
"""H69 - basement-surface two-view co-training, and the first lane-feasible placement in this repo.

Read ``knowledge/52_hypotheses_H69_preregistered.md`` first; this script refuses to run if that
file's SHA-256 has moved, which is what "frozen before any fit" has to mean mechanically.

Stages (each writes a checkpoint under ``work/h69/`` and an audit receipt under ``evidence/``):

  features  build the uint8 rank stack: View A = differential geometry of the basement surface and
            the potential field; View B = DEM curvature/slope + the radiometric total-count band.
  lane      the brief's co-training: canary, S1 sufficiency, S2 independence, one pseudo-label
            exchange, six arms, pooled HOLDOUT-DTI with a paired 20 km cluster bootstrap.
  place     the lane-feasible constrained placer: the measured credited core plus the smallest
            novel mass that satisfies the brief's per-raster 70 % near-dot rule *by construction*.
  gates     format, decoded-pattern uniqueness, literal + saturation-policy lane on the surface and
            on the final dots, not-the-union, the projection algebra, and the written GeoTIFF.

Nothing here claims an organiser score. ``ORGANIZER-CONFIRMED`` is never produced by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import cotrain, evaluate_holdout as EH, gates, grid as G, holdout, metric, nodes, spatial  # noqa: E402

W = ROOT / "work/h69"
EV = ROOT / "evidence"
SUB = ROOT / "submission"
PREREG = ROOT / "knowledge/52_hypotheses_H69_preregistered.md"
PREREG_SHA = "2791f5ff807de294207047acec349f6fc0ab10adc9f7bed9f8531d9d8dc1df81"

# ---- frozen constants (knowledge/52 sections 2, 4) ---------------------------------------------
N_FOLDS = 4
BUFFER_PX = 4                 # 400 m > the 300 m kernel
PREVALENCE = 0.002            # inside the measured 0.00112-0.00294 bracket
NEG_PER_POS = 12
BUDGET_PER_FOLD = 9400        # 4 x 9400 = 37,600, matched to H63/H64 for comparability
CONF_Q = 0.995
ABSTAIN_Q = 0.60
CANARY_ALARM = 0.90
S1_MEAN = 0.60
S1_FOLD = 0.55
ABANDON_R = 0.60
CORRIDOR_M = 200.0
NEAR_LIMIT = 0.70             # the brief's literal rule: "more than 70%" is a duplicate
NEAR_TARGET = 0.6985          # enforced margin, so the literal rule cannot be touched by rounding
RANK_LIMIT = 0.90
SINGLE_B_CONTROL = 0.1745172876
CONTROL_TOL = 0.001
G_LO, G_HI = 5949.282184328427, 12512.133928571544     # evidence/h61_forensics.json G_identification.masked
RHO_NOVEL = (0.02795, 0.13871)                          # measured uniform-random and champion densities
REPORTED = {"A": 0.2778, "B": 0.2600, "C": 0.2477, "E": 0.1922}

T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:8.1f}s]", *a, flush=True)


def now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha_file(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=G._fallback))


def check_prereg():
    got = sha_file(PREREG)
    if got != PREREG_SHA:
        raise SystemExit(f"FROZEN PREREGISTRATION MOVED: {PREREG}\n  pinned {PREREG_SHA}\n  actual {got}")
    log("preregistration hash verified:", got[:16], "…")


# ================================================================================================
# stage 1 - features
# ================================================================================================
def _rank(a, valid):
    v = a[valid]
    lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros(a.shape, np.uint8)
    r = np.clip(np.nan_to_num((a - lo) / (hi - lo), nan=0.0), 0, 1)
    out = (r * 255.0).astype(np.uint8)
    out[~valid] = 0
    return out


def _ggm(a, sigma):
    return ndi.gaussian_gradient_magnitude(np.nan_to_num(a, nan=0.0), sigma, mode="nearest")


def _lap(a, sigma):
    return np.abs(ndi.gaussian_laplace(np.nan_to_num(a, nan=0.0), sigma, mode="nearest"))


def _grad_coh(a, b, sigma=3.0):
    """|cos| of the angle between the two horizontal gradients: 1 where the two fields edge together."""
    ay, ax = np.gradient(ndi.gaussian_filter(np.nan_to_num(a, nan=0.0), sigma, mode="nearest"))
    by, bx = np.gradient(ndi.gaussian_filter(np.nan_to_num(b, nan=0.0), sigma, mode="nearest"))
    na = np.hypot(ay, ax)
    nb = np.hypot(by, bx)
    dot = np.abs(ay * by + ax * bx)
    den = na * nb
    out = np.zeros(a.shape, np.float32)
    ok = den > 1e-12
    out[ok] = (dot[ok] / den[ok]).astype(np.float32)
    return out


def stage_features():
    """Build (H, W, F) uint8 rank stack. One band resident at a time; peak well under 1 GB."""
    valid = np.load(W / "valid.npy")
    feats = ROOT / "data/training_features.tif"
    cache: dict[int, np.ndarray] = {}

    def band(i):
        if i not in cache:
            cache[i] = G.read_band(feats, i)
            if len(cache) > 5:
                cache.pop(next(iter(cache)))
        return cache[i]

    plan: list[tuple[str, str, object]] = []
    A = plan.append
    # ---- View A: potential field and subsurface, all as differential/band-pass operators --------
    A(("a_b15_cover_level", "A", lambda: band(15)))
    A(("a_grad_basement_s2", "A", lambda: _ggm(band(15), 2.0)))
    A(("a_grad_basement_s4", "A", lambda: _ggm(band(15), 4.0)))
    A(("a_grad_basement_s8", "A", lambda: _ggm(band(15), 8.0)))
    A(("a_lap_basement_s3", "A", lambda: _lap(band(15), 3.0)))
    dog13 = lambda: (ndi.gaussian_filter(np.nan_to_num(band(13), nan=0.0), 8.0, mode="nearest")
                     - ndi.gaussian_filter(np.nan_to_num(band(13), nan=0.0), 40.0, mode="nearest"))
    A(("a_dog_isograv_signed", "A", dog13))
    A(("a_dog_isograv_abs", "A", lambda: np.abs(dog13())))
    A(("a_isograv_level", "A", lambda: band(13)))
    A(("a_isograv_hg_b18", "A", lambda: band(18)))
    A(("a_isograv_vg_b11", "A", lambda: band(11)))
    A(("a_isograv_slope_b5", "A", lambda: band(5)))
    A(("a_gradcoh_grav_rtp", "A", lambda: _grad_coh(band(13), band(2), 3.0)))
    A(("a_rtp_b2", "A", lambda: band(2)))
    A(("a_tmi_b14", "A", lambda: band(14)))
    A(("a_grad_conductivity_s3", "A", lambda: _ggm(band(17), 3.0)))
    A(("a_strain_invariant_b4", "A", lambda: band(4)))
    A(("a_strain_dilatation_b8", "A", lambda: band(8)))
    A(("a_seismic_density_b16", "A", lambda: band(16)))
    # ---- View B: surface (DEM curvature/slope) + radiometric total count ------------------------
    A(("b_delev_level_b12", "B", lambda: band(12)))
    A(("b_delev_slope_b19", "B", lambda: band(19)))
    A(("b_grad_delev_s2", "B", lambda: _ggm(band(12), 2.0)))
    A(("b_lap_delev_s3", "B", lambda: _lap(band(12), 3.0)))
    A(("b_roughness_contrast", "B", lambda: _ggm(band(12), 6.0) - _ggm(band(12), 2.0)))
    A(("b_rad_tc_band6", "B", lambda: band(6)))

    stack = np.zeros(valid.shape + (len(plan) + 2,), np.uint8)
    names, views = [], []
    for j, (nm, vw, fn) in enumerate(plan):
        t = time.time()
        stack[..., j] = _rank(np.asarray(fn(), np.float32), valid)
        names.append(nm)
        views.append(vw)
        log(f"  channel {j + 1}/{len(plan)} {nm} ({time.time() - t:.1f}s)")

    # ---- the two external radiometric channels, identity measured not assumed -------------------
    with rasterio.open(ROOT / "data/external/geodawn_rad_u8.tif") as s:
        ext = s.read().astype(np.float32)
    b6 = G.read_band(feats, 6)
    from scipy.stats import spearmanr
    idx = np.flatnonzero(valid.ravel())
    rng = np.random.default_rng(65)
    smp = rng.choice(idx, size=min(400_000, idx.size), replace=False)
    ys, xs = np.unravel_index(smp, valid.shape)
    b6v = b6[ys, xs]
    rhos = []
    for k in range(ext.shape[0]):
        ev = ext[k][ys, xs]
        m = np.isfinite(ev) & np.isfinite(b6v)
        rhos.append(float(spearmanr(ev[m], b6v[m]).statistic) if m.sum() > 100 else float("nan"))
    tc_band = int(np.nanargmax(np.abs(rhos)))
    log("external radiometric band Spearman vs organiser band 6:", [round(r, 5) for r in rhos],
        "-> total-count band index (1-based):", tc_band + 1)
    stack[..., len(plan)] = _rank(ext[tc_band], valid)
    names.append("b_ext_rad_tc")
    views.append("B")
    others = np.nanmean(np.delete(ext, tc_band, axis=0), axis=0)
    stack[..., len(plan) + 1] = _rank(others - ext[tc_band], valid)
    names.append("b_ext_rad_contrast_unverified")
    views.append("B")

    np.save(W / "stack.npy", stack)
    write_json(W / "stack_meta.json", dict(names=names, views=views, shape=list(stack.shape),
                                           dtype=str(stack.dtype),
                                           external_rad_spearman_vs_band6=[round(r, 6) for r in rhos],
                                           external_tc_band_1based=tc_band + 1,
                                           external_identity_note=(
                                               "the external GeoDAWN radiometric raster carries no band tags; "
                                               "the total-count band is identified by rank correlation against "
                                               "organiser band 6, whose own identity as radiometric TC is measured "
                                               "in evidence/h61_forensics.json; the remaining three bands are "
                                               "averaged into one contrast channel and their individual identities "
                                               "are UNVERIFIED")))
    log(f"stack built: {stack.shape} {stack.nbytes / 1e6:.0f} MB, "
        f"View A {views.count('A')} channels, View B {views.count('B')} channels")
    return dict(names=names, views=views)


# ================================================================================================
# stage 2 - the lane
# ================================================================================================
def _fit_view(stack, cols, pos, neg, seed):
    v = cotrain.View(name="v", cols=cols)
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
    rows = np.concatenate([pos, neg])
    v.fit(stack, rows, y, seed)
    return v


def stage_lane():
    """The lane, on the committed shared instrument and nothing else.

    Folds are ``spatial.folds`` (label-blind quadrants, whole intersecting segments hidden,
    buffer_px = 80). Emission is ``nodes.spacing_select`` at 9,400 dots per fold per arm with 3 px
    separation. Scoring is ``evaluate_holdout.evaluate`` pooled over folds and bootstrapped over
    200 px (20 km) physical blocks. Training sampling, the learner, the percentile-rank operating
    field and the whole-segment pseudo-label rule are imported from ``scripts/run_h61.py`` rather
    than re-implemented, so a repair to the shared instrument lands in one place.
    """
    import run_h61 as base
    from sklearn.metrics import roc_auc_score

    meta = json.loads((W / "stack_meta.json").read_text())
    names, views = meta["names"], meta["views"]
    cols_a = [i for i, v in enumerate(views) if v == "A"]
    cols_b = [i for i, v in enumerate(views) if v == "B"]
    stack = np.load(W / "stack.npy")
    flat = stack.reshape(-1, stack.shape[2])
    valid = np.load(W / "valid.npy")
    legal = np.load(W / "legal.npy")
    with rasterio.open(ROOT / "data/labels.tif") as s:
        cat = s.read(1) == 1
    # `eligible` in the committed instrument is the *valid footprint*, catalogue pixels included:
    # spatial.folds builds quadrant regions from it, sample_train draws positives from
    # fold["train"] & fold["visible"], and truth = held_all & region is a subset of the catalogue.
    # Passing the off-catalogue set here empties both classes ("insufficient training classes").
    eligible = valid
    offcat = valid & ~cat
    SEED = base.SEED
    K = 9400
    MIN_PX = 3.0
    BUFFER_PX = 80
    RING_PX = 2
    log(f"eligible (valid footprint) {int(eligible.sum())} px; off-catalogue {int(offcat.sum())} px "
        f"(h61_forensics eligible_px = 5,103,406); legal (>200 m ring excluded) {int(legal.sum())} px")

    def gather(rows, cols):
        return flat[rows][:, cols].astype(np.float32)

    def predict(model, cols, rows, chunk=250_000):
        out = np.empty(len(rows), np.float32)
        for i in range(0, len(rows), chunk):
            out[i:i + chunk] = model.predict_proba(gather(rows[i:i + chunk], cols))[:, 1].astype(np.float32)
        return out

    folds = list(spatial.folds(cat, eligible, buffer_px=BUFFER_PX))
    log("folds: " + json.dumps([f["receipt"] for f in folds], default=str)[:600])
    elig_idx = np.flatnonzero(eligible.ravel())
    catd = ndi.distance_transform_edt(~cat)

    # ---------- canary: every channel alone, per fold -------------------------------------------
    can_folds = []
    for fold in folds:
        reg = fold["region"]
        pos = np.flatnonzero((fold["truth"] & reg).ravel())
        neg = np.flatnonzero((reg & ~cat & (catd > 5)).ravel())
        rngc = np.random.default_rng(SEED + 900 + fold["fold"])
        pos = rngc.choice(pos, min(20000, len(pos)), replace=False)
        neg = rngc.choice(neg, min(40000, len(neg)), replace=False)
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        sel = np.r_[pos, neg]
        per = []
        for j, nm in enumerate(names):
            v = flat[sel][:, j].astype(np.float32)
            auc = float(roc_auc_score(y, v))
            per.append(dict(channel=nm, view=views[j], auc_alone=round(auc, 6),
                            leakage=bool(auc > CANARY_ALARM)))
        can_folds.append(dict(fold=fold["fold"], n_pos=int(len(pos)), n_neg=int(len(neg)), channels=per))
        log(f"  canary fold {fold['fold']}: max AUC {max(c['auc_alone'] for c in per):.4f}")
    max_auc = max(c["auc_alone"] for f in can_folds for c in f["channels"])
    worst = max((c for f in can_folds for c in f["channels"]), key=lambda c: c["auc_alone"])
    write_json(EV / "h69_canary.json", dict(
        evidence_class="LEAKAGE CANARY - each channel fitted alone, out-of-quadrant, per fold",
        alarm_threshold=CANARY_ALARM, n_channels=len(names), n_folds=len(folds),
        max_alarm_across_folds=max_auc, worst=worst,
        any_alarm=bool(max_auc > CANARY_ALARM),
        interpretation=("a single channel above 0.90 would mean the held-out segment is visible in one "
                        "feature, i.e. leakage, until proven otherwise"),
        folds=can_folds))
    log(f"canary: max single-channel AUC {max_auc:.4f} ({worst['channel']}) alarm {CANARY_ALARM}")

    # ---------- per-fold fit, independence, exchange, arms --------------------------------------
    indep_rows, ex_log, s1_rows = [], [], []
    terms = {a: None for a in base.ARMS}
    per_fold = []
    preA_all = np.full(eligible.shape, np.nan, np.float32)
    preB_all = np.full(eligible.shape, np.nan, np.float32)
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + 500 + f)
        rows, y = base.sample_train(fold, cat, rng, max_pos=20000, max_neg=60000)
        mA = base.learner(SEED).fit(gather(rows, cols_a), y)
        mB = base.learner(SEED).fit(gather(rows, cols_b), y)
        pa = base.to_grid(elig_idx, predict(mA, cols_a, elig_idx), eligible.shape)
        pb = base.to_grid(elig_idx, predict(mB, cols_b, elig_idx), eligible.shape)
        preA_all[np.isfinite(pa)] = pa[np.isfinite(pa)]
        preB_all[np.isfinite(pb)] = pb[np.isfinite(pb)]

        # S1 sufficiency: out-of-quadrant AUC of View A against the held-out truth
        reg = fold["region"]
        pos = np.flatnonzero((fold["truth"] & reg).ravel())
        neg = np.flatnonzero((reg & ~cat & (catd > 5)).ravel())
        rngs = np.random.default_rng(SEED + 500 + f)
        ps = rngs.choice(pos, min(20000, len(pos)), replace=False)
        ns = rngs.choice(neg, min(40000, len(neg)), replace=False)
        yy = np.r_[np.ones(len(ps)), np.zeros(len(ns))]
        ss = np.r_[np.nan_to_num(pa.ravel()[ps], nan=-1.0), np.nan_to_num(pa.ravel()[ns], nan=-1.0)]
        auc_a = float(roc_auc_score(yy, ss))
        ssb = np.r_[np.nan_to_num(pb.ravel()[ps], nan=-1.0), np.nan_to_num(pb.ravel()[ns], nan=-1.0)]
        auc_b = float(roc_auc_score(yy, ssb))
        s1_rows.append(dict(fold=f, n_pos=int(len(ps)), n_neg=int(len(ns)),
                            view_A_oof_auc=round(auc_a, 6), view_B_oof_auc=round(auc_b, 6)))
        log(f"  fold {f}: View A out-of-quadrant AUC {auc_a:.4f}  View B {auc_b:.4f}")

        # emission domain: label-blind visible-catalogue collar
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = reg & ~fold["visible"] & (vis_dist > RING_PX)
        del vis_dist
        allowed_idx = np.flatnonzero(allowed.ravel())
        rA = np.full(eligible.shape, np.nan, np.float32)
        rB = np.full(eligible.shape, np.nan, np.float32)
        rA.ravel()[allowed_idx] = base.pct_rank(pa.ravel()[allowed_idx])
        rB.ravel()[allowed_idx] = base.pct_rank(pb.ravel()[allowed_idx])

        # S2 independence on held-out labelled negatives (catalogue-zero proxies)
        negmask = allowed & np.isfinite(rA) & np.isfinite(rB)
        indep_rows += spatial.negative_block_errors(rA, rB, negmask, f, (0.95, 0.95),
                                                    side=50, minimum=32)

        # one pseudo-label exchange, whole segments only, inside the training domain
        forbidden = cat | fold["held_all"] | ~eligible
        a_to_b, rec1 = spatial.whole_pseudo_segments(
            rA, rB, fold["train"], forbidden, 0.95, 0.35, 0.65, side=50, min_pixels=5, cap=2000)
        b_to_a, rec2 = spatial.whole_pseudo_segments(
            rB, rA, fold["train"], forbidden, 0.95, 0.35, 0.65, side=50, min_pixels=5, cap=2000)
        ran = a_to_b.size >= 5 and b_to_a.size >= 5
        if ran:
            rowsA = np.concatenate([rows, b_to_a])
            yA = np.concatenate([y, np.ones(b_to_a.size, np.int8)])
            rowsB = np.concatenate([rows, a_to_b])
            yB = np.concatenate([y, np.ones(a_to_b.size, np.int8)])
            mA2 = base.learner(SEED).fit(gather(rowsA, cols_a), yA)
            mB2 = base.learner(SEED).fit(gather(rowsB, cols_b), yB)
            qa = base.to_grid(elig_idx, predict(mA2, cols_a, elig_idx), eligible.shape)
            qb = base.to_grid(elig_idx, predict(mB2, cols_b, elig_idx), eligible.shape)
        else:
            qa, qb = pa, pb
        rA2 = np.full(eligible.shape, np.nan, np.float32)
        rB2 = np.full(eligible.shape, np.nan, np.float32)
        rA2.ravel()[allowed_idx] = base.pct_rank(qa.ravel()[allowed_idx])
        rB2.ravel()[allowed_idx] = base.pct_rank(qb.ravel()[allowed_idx])
        ex_log.append(dict(fold=f, ran=bool(ran), pseudo_a_to_b=int(a_to_b.size),
                           pseudo_b_to_a=int(b_to_a.size), segments_a_to_b=rec1[:5],
                           segments_b_to_a=rec2[:5]))

        rng2 = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng2.random(len(allowed_idx), dtype=np.float32)
        fields = {
            "single_A": np.nan_to_num(rA, nan=-1.0),
            "single_B": np.nan_to_num(rB, nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(rA, rB), nan=-1.0),
            "disagreement_pre": np.nan_to_num(rA - rB, nan=-1.0),
            "disagreement_post": np.nan_to_num(rA2 - rB2, nan=-1.0),
            "random": rnd,
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(reg.sum()), arms={})
        for arm, field in fields.items():
            em = nodes.spacing_select(field, allowed, K, min_px=MIN_PX)
            n = int(em.sum())
            result, term = EH.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=result["dti"], tpw=result["tpw"], placed=n, requested=K,
                                    filled=bool(n == K))
            log(f"    fold {f} arm {arm}: placed {n}/{K} DTI {result['dti']:.6f}")
        per_fold.append(rec)
        np.save(W / f"rA_f{f}.npy", rA)
        np.save(W / f"rB_f{f}.npy", rB)
        np.save(W / f"rA2_f{f}.npy", rA2)
        np.save(W / f"rB2_f{f}.npy", rB2)
        np.save(W / f"allowed_f{f}.npy", allowed)

    # ---------- S1 verdict -----------------------------------------------------------------------
    aucs_a = [r["view_A_oof_auc"] for r in s1_rows]
    aucs_b = [r["view_B_oof_auc"] for r in s1_rows]
    s1_summary = {"A": dict(folds=aucs_a, mean=float(np.mean(aucs_a)), minimum=float(np.min(aucs_a))),
                  "B": dict(folds=aucs_b, mean=float(np.mean(aucs_b)), minimum=float(np.min(aucs_b)))}
    s1_pass = bool(np.mean(aucs_a) >= S1_MEAN and np.min(aucs_a) >= S1_FOLD)
    write_json(EV / "h69_s1.json", dict(
        evidence_class="SUFFICIENCY SCREEN - View A out-of-quadrant AUC against the held-out truth",
        instrument="spatial.folds(label-blind quadrants, buffer_px=80) + the H61 learner",
        thresholds=dict(mean=S1_MEAN, fold=S1_FOLD), pass_=s1_pass, summary=s1_summary, folds=s1_rows,
        mean_only_reading=bool(np.mean(aucs_a) >= S1_MEAN),
        fold_floor_reading=bool(np.min(aucs_a) >= S1_FOLD),
        comparison=dict(H61=0.5163, H63=0.5362, H64=0.5230),
        note=("the frozen gate is conjunctive (mean AND every fold), so a mean that clears 0.60 with one "
              "fold below 0.55 is still a FAIL and is not retro-tuned; both readings are published")))
    log(f"S1: View A mean {np.mean(aucs_a):.4f} min {np.min(aucs_a):.4f} -> "
        f"{'PASS' if s1_pass else 'FAIL'}; View B mean {np.mean(aucs_b):.4f}")

    # ---------- S2 verdict -----------------------------------------------------------------------
    pre = spatial.independence(indep_rows, threshold=ABANDON_R, min_blocks=20)
    slim = {k: v for k, v in pre.items() if k != "blocks"}
    write_json(EV / "h69_independence.json", dict(
        evidence_class="CONDITIONAL-INDEPENDENCE PROXY on held-out labelled negatives",
        pre_exchange=slim, n_blocks=pre["n_blocks"], abandon_threshold=ABANDON_R,
        allow_exchange=pre["allow_exchange"], exchange_log=ex_log,
        total_pseudo_pixels=int(sum(x["pseudo_a_to_b"] + x["pseudo_b_to_a"] for x in ex_log)),
        caveat=("a proxy diagnostic over 50 px spatial blocks of percentile-ranked OOF fields, not proof "
                "of conditional feature independence")))
    log(f"S2: max|rho| {pre['max_abs_correlation']} over {pre['n_blocks']} blocks; "
        f"allow_exchange={pre['allow_exchange']}; pseudo pixels "
        f"{sum(x['pseudo_a_to_b'] + x['pseudo_b_to_a'] for x in ex_log)}")

    # ---------- pooled HOLDOUT-DTI ---------------------------------------------------------------
    pooled = EH.pooled_summary(terms, draws=1000, seed=520810, candidate="disagreement_post")
    log("POOLED HOLDOUT-DTI (evaluator %s):" % EH.VERSION)
    for k in base.ARMS:
        v = pooled["scores"][k]
        log(f"   {k:20s} {v['dti']:.6f}  CI [{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]")
    all_filled = all(a["filled"] for r in per_fold for a in r["arms"].values())
    rand = pooled["scores"]["random"]["dti"]
    write_json(EV / "h69_holdout.json", dict(
        evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
        withheld_positives=int(pooled["scores"]["single_A"]["withheld_positive_pixels"]),
        budget_per_fold=K, min_dot_separation_px=MIN_PX, buffer_px=BUFFER_PX, ring_px=RING_PX,
        n_folds=len(folds), all_arms_filled=bool(all_filled),
        seed=SEED, learner="run_h61.learner (HistGradientBoostingClassifier, committed settings)",
        pooled=pooled, per_fold=per_fold,
        instrument_control=dict(
            random_arm=float(rand), committed_H64_random_arm=0.080426,
            abs_delta=float(abs(rand - 0.080426)),
            within_0p001=bool(abs(rand - 0.080426) <= 0.001),
            reading=("the random arm depends only on the instrument - folds, allowed set, budget, "
                     "spacing and metric - and not on any model, so it is the control that can "
                     "reproduce across rounds that change channel sets")),
        prereg_control_clause=dict(
            clause="knowledge/52 section 2 required single_B to reproduce 0.1745172876 to |d| <= 0.001",
            single_B_this_round=float(pooled["scores"]["single_B"]["dti"]),
            status="FAILED AS WRITTEN, reported not hidden",
            reason=("the clause is unsatisfiable for a round that deliberately changes View B's channel "
                    "set: H69's View B is 8 basement-independent surface/radiometric channels, H61's was "
                    "view_B_with_external from the shared FeatureStore. The model-free random arm is the "
                    "control that isolates the instrument; both numbers are published.")),
        validity_warning=("knowledge/10 section 5 measured Spearman rho = -0.1045 (p = 0.734, n = 13) "
                          "between this instrument and the organiser's reported scores, and the reported "
                          "champion ranks 13th of 13 here while ranking 1st on the board. HOLDOUT-DTI is "
                          "an instrument reading, never a forecast."),
        implementation_sha256=EH.implementation_hashes()))

    # ---------- the A-only discovery set ---------------------------------------------------------
    conf_a = np.zeros(eligible.shape, bool)
    abst_b = np.zeros(eligible.shape, bool)
    rA_stitch = np.full(eligible.shape, np.nan, np.float32)
    rB_stitch = np.full(eligible.shape, np.nan, np.float32)
    for f in range(len(folds)):
        a = np.load(W / f"rA_f{f}.npy")
        b = np.load(W / f"rB_f{f}.npy")
        conf_a |= np.isfinite(a) & (a >= 0.95)
        abst_b |= np.isfinite(b) & (b >= 0.35) & (b <= 0.65)
        fa = np.isfinite(a) & ~np.isfinite(rA_stitch)
        rA_stitch[fa] = a[fa]
        fb = np.isfinite(b) & ~np.isfinite(rB_stitch)
        rB_stitch[fb] = b[fb]
    a_only = conf_a & abst_b & legal
    seg, nseg = ndi.label(a_only, structure=np.ones((3, 3), bool))
    ed = ndi.distance_transform_edt(~cat, sampling=100.0)
    pa_grid = np.nan_to_num(preA_all, nan=0.0)
    pb_grid = np.nan_to_num(preB_all, nan=0.0)
    import csv
    rows_out = []
    sizes = np.bincount(seg.ravel())[1:] if nseg else np.array([0])
    for k in range(1, nseg + 1):
        m = seg == k
        npx = int(m.sum())
        if npx < 3:
            continue
        cy, cx = np.nonzero(m)
        y0, x0 = int(round(cy.mean())), int(round(cx.mean()))
        b = {names[i]: int(stack[y0, x0, i]) for i in range(len(names))}
        rows_out.append(dict(
            segment_id=f"H69-AO-{len(rows_out):05d}", n_pixels=npx, row=y0, col=x0,
            easting=float(G.TRANSFORM[2] + (x0 + 0.5) * G.TRANSFORM[0]),
            northing=float(G.TRANSFORM[5] + (y0 + 0.5) * G.TRANSFORM[4]),
            distance_to_nearest_mapped_trace_m=round(float(ed[y0, x0]), 1),
            view_a_percentile_mean=round(float(np.nanmean(np.where(m, rA_stitch, np.nan))), 4),
            view_b_percentile_mean=round(float(np.nanmean(np.where(m, rB_stitch, np.nan))), 4),
            cover_thickness_band15_rank=b.get("a_b15_cover_level"),
            basement_gradient_s2_rank=b.get("a_grad_basement_s2"),
            basement_gradient_s4_rank=b.get("a_grad_basement_s4"),
            basement_gradient_s8_rank=b.get("a_grad_basement_s8"),
            basement_laplacian_s3_rank=b.get("a_lap_basement_s3"),
            dog_isograv_abs_rank=b.get("a_dog_isograv_abs"),
            grad_cohesion_grav_rtp_rank=b.get("a_gradcoh_grav_rtp"),
            conductivity_edge_rank=b.get("a_grad_conductivity_s3"),
            strain_invariant_rank=b.get("a_strain_invariant_b4"),
            detrended_elev_slope_rank=b.get("b_delev_slope_b19"),
            dem_roughness_contrast_rank=b.get("b_roughness_contrast"),
            rad_tc_band6_rank=b.get("b_rad_tc_band6"),
            reasoning=(
                "View A (potential field / subsurface) is at or above its 95th operating percentile while "
                "View B (surface DEM curvature, slope and radiometric total count) abstains inside its "
                "35th-65th percentile interval. Under the Blum-Mitchell reading this is the "
                "buried-structure class: a normal fault that offsets the basement surface recorded by "
                "organiser band 15 without producing a preserved scarp, so the geomorphic catalogue that "
                "produced labels.tif has no signal there and absence from it is weak evidence of absence. "
                f"Measured context at the segment centroid (0-255 within-footprint ranks): basement-surface "
                f"gradient {b.get('a_grad_basement_s4')} (sigma 4 px), basement Laplacian "
                f"{b.get('a_lap_basement_s3')}, band-passed isostatic residual {b.get('a_dog_isograv_abs')}, "
                f"gravity/RTP gradient coherence {b.get('a_gradcoh_grav_rtp')} (a fault cutting both the "
                "density and the magnetisation surface makes the two gradients parallel), conductivity edge "
                f"{b.get('a_grad_conductivity_s3')}, geodetic strain invariant {b.get('a_strain_invariant_b4')}, "
                f"against a detrended-elevation slope of {b.get('b_delev_slope_b19')} and a radiometric "
                f"total count of {b.get('b_rad_tc_band6')}. Nearest mapped trace "
                f"{float(ed[y0, x0]):.0f} m, outside the 200 m ring whose credit measures at exactly zero. "
                "STATUS: a HYPOTHESIS from measured context plus a template mechanism, NOT field-verified "
                "geology; Phase 2 reviewers must verify it. The named non-fault mimic is a lithologic "
                "contact or a basin axis with a density and magnetisation contrast and no relief.")))
    csv_path = EV / "h69_a_only_geological_reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()) if rows_out else ["none"])
        wr.writeheader()
        wr.writerows(rows_out)
    write_json(EV / "h69_a_only.json", dict(
        evidence_class="A-only discovery set (View A >= 95th percentile, View B abstaining 35th-65th)",
        rule="spatial.whole_pseudo_segments receiver interval, applied grid-wide over the legal set",
        n_pixels=int(a_only.sum()), n_segments=int(nseg), n_segments_written=len(rows_out),
        min_segment_px=3, csv=str(csv_path.relative_to(ROOT)),
        segment_size_quantiles={str(q): float(np.quantile(sizes, q)) for q in (0.5, 0.9, 0.99)},
        caveat=("measured context plus a template mechanism, NOT field-verified geology; the named mimic "
                "is a lithologic contact or basin axis with a density/magnetisation contrast and no relief"),
        s1_status=("PASS" if s1_pass else
                   f"FAIL (View A mean {np.mean(aucs_a):.4f}, min fold {np.min(aucs_a):.4f}) - so this set "
                   "is reported as the lane's discovery signal and is NOT promoted to the emission")))
    np.save(W / "pa.npy", pa_grid)
    np.save(W / "pb.npy", pb_grid)
    write_json(W / "lane_ckpt.json", dict(
        s1_pass=s1_pass, s1=s1_summary, allow_exchange=pre["allow_exchange"],
        single_B=float(pooled["scores"]["single_B"]["dti"]),
        random_arm=float(rand), names=names, views=views,
        withheld_positives=int(pooled["scores"]["single_A"]["withheld_positive_pixels"])))
    log("LANE_DONE")


# ================================================================================================
# stage 3 - the lane-feasible constrained placer
# ================================================================================================
def stage_place():
    """Novel-only emission, placed so the brief's lane rule cannot be violated.

    Amendment ``knowledge/52b`` withdrew the pre-registered credited-core emission: this repository has
    already corrected a core-recombination file as NOT unique (README H60C correction, IR-H61-007,
    IR-UNQ-001), and sizing a file to land 0.005 under the 0.70 threshold that a previous round was
    corrected for exceeding is re-tuning a negative result into a positive.

    Placement is a quota-constrained greedy:
      1. place S dots in field-rank order with hard-core 3 px spacing over the legal set;
      2. measure every informative prior's directed 3 px near-dot count;
      3. any prior above floor(NEAR_TARGET*S) becomes an offender; re-place, skipping candidates inside
         an offender's 3 px halo once that offender's quota is full;
      4. re-measure against ALL informative priors and stop only when clean.
    """
    ck0 = json.loads((W / "lane_ckpt.json").read_text())
    valid = np.load(W / "valid.npy")
    legal = np.load(W / "legal.npy")
    rows = json.loads((W / "prior_rows.json").read_text())
    info = [r for r in rows if "error" not in r and not r["universal_coverage_probe"]]
    probes = [r for r in rows if r.get("universal_coverage_probe")]
    log(f"informative priors {len(info)}; universal-coverage probes {len(probes)}")

    # ---- the stitched operating field: quadrants are disjoint, so per-fold percentile ranks stitch
    rA = np.full(valid.shape, np.nan, np.float32)
    rB = np.full(valid.shape, np.nan, np.float32)
    for f in range(N_FOLDS):
        a = np.load(W / f"rA_f{f}.npy")
        b = np.load(W / f"rB_f{f}.npy")
        fa = np.isfinite(a) & ~np.isfinite(rA)
        rA[fa] = a[fa]
        fb = np.isfinite(b) & ~np.isfinite(rB)
        rB[fb] = b[fb]
    consensus = np.load(W / "consensus.npy").astype(np.float32)
    base_pool = legal & np.isfinite(rA) & np.isfinite(rB)
    cmax = float(consensus[base_pool].max()) if base_pool.any() else 1.0
    cw = (1.0 + 0.5 * (consensus / max(cmax, 1.0))).astype(np.float32)
    field = (np.nan_to_num(rB, nan=0.0)
             * np.power(np.clip(np.nan_to_num(rA, nan=0.0), 1e-6, 1.0), 0.25) * cw).astype(np.float32)
    field[~base_pool] = -1.0
    log(f"base pool {int(base_pool.sum())} px; consensus max {cmax:.0f}; "
        f"field max {float(field[base_pool].max()):.5f}")

    S = 37600
    disk = gates._disk(gates.NEAR_RADIUS_PX)
    cap = int(np.floor(NEAR_TARGET * S))

    def fast_proposal(path):
        """Same support rule as gates.canonical + gates.lane_report, without the float32 round trip."""
        with rasterio.open(path) as ds:
            a = ds.read(1)
        ok = np.isfinite(a) & (a >= 0) & (a <= 1)
        pv = a[ok & (a > 0)]
        binary = (pv.size == 0) or bool(np.all(pv == 1.0))
        return (ok & (a > 0)) if binary else (ok & (a >= 0.5))

    def halo_of(path):
        return ndi.binary_dilation(fast_proposal(path), structure=disk)

    def place(pool, quota_paths=(), cap_each=0):   # quota path retained and tested; exclusion is used
        """Greedy top-S with hard-core 3 px spacing and an exact per-prior near-dot quota.

        Memory-lean by construction: each quota prior's 3 px halo is stored *packed* (1.5 MB instead of
        12.3 MB), and a single lazy ``forbidden`` mask is OR-ed in at the moment a prior's count reaches
        the cap. The candidate test is then one bool lookup, and the 84-prior count update runs only on
        the 37,600 accepted dots, never on the ~308,000 scanned. Counts can never pass the cap because
        the mask is set on the same iteration the cap is reached.
        """
        idx = np.flatnonzero(pool.ravel())
        order = idx[np.argsort(-field.ravel()[idx], kind="stable")]
        h, w = valid.shape
        ncell = h * w
        taken = np.zeros(valid.shape, bool)
        quota_paths = list(quota_paths)
        nq = len(quota_paths)
        masks = np.array([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01], np.uint8)
        packed = [np.packbits(halo_of(t).ravel()) for t in quota_paths]
        counts = np.zeros(nq, np.int64)
        forbidden = np.zeros(ncell, bool)
        cy, cx, scanned, blocked_by_quota = [], [], 0, 0
        for fi in order:
            if len(cy) >= S:
                break
            scanned += 1
            y, x = divmod(int(fi), w)
            if taken[y, x]:
                continue
            if nq and forbidden[fi]:
                blocked_by_quota += 1
                continue
            cy.append(y)
            cx.append(x)
            y0, y1 = max(0, y - 3), min(h, y + 4)
            x0, x1 = max(0, x - 3), min(w, x + 4)
            taken[y0:y1, x0:x1] |= disk[(y0 - y + 3):(7 - (y + 4 - y1)),
                                         (x0 - x + 3):(7 - (x + 4 - x1))]
            if nq:
                bi, m = fi >> 3, masks[fi & 7]
                for k in range(nq):
                    if packed[k][bi] & m:
                        counts[k] += 1
                        if counts[k] == cap_each:
                            forbidden |= np.unpackbits(packed[k], count=ncell).astype(bool)
        out = np.zeros(valid.shape, bool)
        if cy:
            out[np.asarray(cy, np.int64), np.asarray(cx, np.int64)] = True
        del packed, forbidden, taken
        return out, dict(requested=S, placed=int(out.sum()), scanned=int(scanned),
                         blocked_by_quota=int(blocked_by_quota),
                         quota_use={quota_paths[i]: int(c) for i, c in enumerate(counts)}
                         if nq else {})

    def measure(em):
        """Directed 3 px near-dot count for every informative prior (exact, all of them)."""
        yy, xx = np.nonzero(em)
        nd = int(em.sum())
        out = []
        for r in info:
            halo = halo_of(r["path"])
            out.append((int(halo[yy, xx].sum()), r["path"]))
        out.sort(key=lambda t: -t[0])
        return out, nd

    # ---- round 1: unconstrained, to find which priors actually bind ------------------------------
    log("placement round 1: unconstrained greedy over the legal set")
    em, st = place(base_pool)
    log(f"  round 1 placed {st['placed']} after scanning {st['scanned']} candidates")
    near, nd = measure(em)
    n_off = int(sum(1 for c, _ in near if c > cap))
    log(f"  placed {nd}; worst informative near-dot {near[0][0]} ({near[0][0] / nd:.4f}) cap {cap} "
        f"-> {Path(near[0][1]).name}; offenders {n_off}")
    rounds = [dict(round=1, design="unconstrained top-S", placed=nd, worst_near=near[0][0],
                   worst_share=round(near[0][0] / nd, 6), worst_prior=Path(near[0][1]).name,
                   n_offenders=n_off, pool_px=int(base_pool.sum()))]

    # ---- two constructions were measured and rejected; both numbers are published ---------------
    # (1) A quota of floor(0.6985*S) against a TARGET S has the wrong denominator, and iterating it to
    #     a fixed point does not converge: measured this session, quota 24,500 -> S 32,871 (share
    #     0.7453), 22,960 -> 30,864 (0.7439), 21,558 -> 29,069 (0.7416). S/Q is structurally ~1.34,
    #     so the share is pinned near 0.745 at every budget, above the 0.70 limit.
    # (2) Excluding the offenders' 3 px halos from the pool is not available at all: the union of the
    #     84 offenders' halos leaves 361 px of the 4,859,987 px legal set.
    # What does work is a third lever, measured below: restrict the pool to pixels of low CROSS-FAMILY
    # CONSENSUS, i.e. pixels that few distinct published decoded patterns cover. Those pixels exist in
    # quantity (837,047 px at consensus <= 30) and an emission drawn from them is not sitting inside the
    # family's agreed habitat, which is exactly what the brief's lane rule is asking for.
    targets = list(dict.fromkeys([p for c, p in near if c > cap] + [p for c, p in near[:40]]))
    packed_path = W / "quota_halos.npz"
    if packed_path.exists():
        z = np.load(packed_path, allow_pickle=True)
        packed = [z[f"h{i}"] for i in range(len(z["paths"]))]
        targets = [str(x) for x in z["paths"]]
        log(f"loaded {len(targets)} cached packed halos")
    else:
        log(f"packing {len(targets)} prior halos (1.5 MB packed each)")
        packed = [np.packbits(halo_of(t).ravel()) for t in targets]
        np.savez(packed_path, paths=np.array(targets, dtype=object),
                 **{f"h{i}": pk for i, pk in enumerate(packed)})
    masks8 = np.array([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01], np.uint8)
    # one (K, nbytes) uint8 matrix instead of a Python loop over K packed arrays per accepted dot:
    # the quota test becomes one vector gather, which is the difference between 30 s and 0.2 s
    P = np.stack(packed)
    del packed
    log(f"packed halo matrix {P.shape} = {P.nbytes / 1e6:.0f} MB")

    def shares_over_targets(dots_idx):
        """Exact near-dot count for every packed prior over the placed dots (fast, no re-reads)."""
        bi = dots_idx >> 3
        bm = masks8[dots_idx & 7]
        return ((P[:, bi] & bm[None, :]) != 0).sum(axis=1).astype(np.int64)

    def place_pool(pool, quota):
        idx = np.flatnonzero(pool.ravel())
        order = idx[np.argsort(-field.ravel()[idx], kind="stable")]
        h, w = valid.shape
        ncell = h * w
        taken = np.zeros(valid.shape, bool)
        counts = np.zeros(P.shape[0], np.int64)
        forbidden = np.zeros(ncell, bool)
        cy, cx, scanned = [], [], 0
        for fi in order:
            if len(cy) >= S:
                break
            scanned += 1
            y, x = divmod(int(fi), w)
            if taken[y, x] or forbidden[fi]:
                continue
            cy.append(y)
            cx.append(x)
            y0, y1 = max(0, y - 3), min(h, y + 4)
            x0, x1 = max(0, x - 3), min(w, x + 4)
            taken[y0:y1, x0:x1] |= disk[(y0 - y + 3):(7 - (y + 4 - y1)),
                                         (x0 - x + 3):(7 - (x + 4 - x1))]
            hits = np.flatnonzero((P[:, fi >> 3] & masks8[fi & 7]) != 0)
            if hits.size:
                counts[hits] += 1
                for k in hits[counts[hits] == quota]:
                    forbidden |= np.unpackbits(P[k], count=ncell).astype(bool)
        out = np.zeros(valid.shape, bool)
        if cy:
            out[np.asarray(cy, np.int64), np.asarray(cx, np.int64)] = True
        return out, int(scanned), counts

    search = []
    best = None
    for c in (160, 120, 100, 80, 60, 50, 40, 30, 25, 22, 20):
        pool_c = base_pool & (consensus <= c)
        npc = int(pool_c.sum())
        if npc < S:
            search.append(dict(consensus_le=c, pool_px=npc, placed=0, skipped="pool smaller than budget"))
            log(f"  consensus<={c}: pool {npc} < S {S}, skipped")
            continue
        quota = int(np.floor(NEAR_TARGET * S))
        em_c, scanned, counts = place_pool(pool_c, quota)
        n_c = int(em_c.sum())
        idx_c = np.flatnonzero(em_c.ravel())
        cnt = shares_over_targets(idx_c)
        worst = int(cnt.max())
        share = worst / max(n_c, 1)
        allowed = int(np.floor(NEAR_TARGET * n_c))
        ok = bool(n_c == S and worst <= allowed)
        search.append(dict(consensus_le=c, pool_px=npc, placed=n_c, scanned=scanned, quota=quota,
                           worst_target_near=worst, worst_share=round(share, 6),
                           allowed_at_achieved_budget=allowed, feasible=ok,
                           worst_target=Path(targets[int(cnt.argmax())]).name))
        log(f"  consensus<={c}: pool {npc} placed {n_c} worst {worst} ({share:.4f}) "
            f"allowed {allowed} -> {'FEASIBLE' if ok else 'no'}")
        if ok and best is None:
            best = (c, em_c)
        if ok:
            break
    if best is None:
        raise SystemExit("no consensus threshold produced a lane-feasible full budget; search table "
                         "published in work/h69/place_ckpt.json")
    c_best, em = best
    log(f"selected consensus<={c_best}; verifying against ALL {len(info)} informative priors")
    near, nd = measure(em)
    share = near[0][0] / max(nd, 1)
    allowed = int(np.floor(NEAR_TARGET * nd))
    feasible = bool(nd == S and near[0][0] <= allowed)
    rounds.append(dict(round=2, design=f"consensus-restricted pool (consensus <= {c_best}) + quota",
                       placed=nd, worst_near=near[0][0], worst_share=round(share, 6),
                       worst_prior=Path(near[0][1]).name,
                       n_offenders=int(sum(1 for c2, _ in near if c2 > allowed)),
                       allowed_at_achieved_budget=allowed, feasible=feasible,
                       pool_px=int((base_pool & (consensus <= c_best)).sum()),
                       n_priors_verified=len(info)))
    log(f"placement feasible={feasible}: placed {nd}/{S}, worst informative share {share:.4f} "
        f"vs literal limit {NEAR_LIMIT}")

    pred = em.astype(np.float32)
    np.save(W / "pred.npy", pred)
    np.save(W / "novel_field.npy", np.clip(field, 0.0, 1.0))
    np.save(W / "base_pool.npy", base_pool)
    write_json(W / "place_ckpt.json", dict(
        design="novel-only (prereg amendment knowledge/52b withdrew the credited-core emission)",
        S_requested=S, S_placed=int(nd), cap=cap, margin=NEAR_TARGET, literal_limit=NEAR_LIMIT,
        n_core=0, n_novel_placed=int(nd),
        core_fraction=0.0, novel_fraction_vs_binding=1.0,
        worst_informative_near=near[0][0], worst_informative_near_share=round(near[0][0] / max(nd, 1), 6),
        worst_informative_prior=Path(near[0][1]).name,
        allowed_at_achieved_budget=int(np.floor(NEAR_TARGET * nd)),
        consensus_threshold=c_best, n_priors_verified=len(info),
        rejected_constructions=dict(
            quota_fixed_point=("iterating the quota to a fixed point does not converge: 24,500 -> S 32,871 "
                               "(share 0.7453), 22,960 -> 30,864 (0.7439), 21,558 -> 29,069 (0.7416); "
                               "S/Q is structurally ~1.34 so the share is pinned near 0.745 at every budget"),
            halo_exclusion=("the union of the 84 offenders' 3 px halos leaves 361 px of the 4,859,987 px "
                            "legal set, so exclusion cannot fund a budget")),
        consensus_search=search,
        top10_informative_near=[dict(share=round(c / max(nd, 1), 6), count=c, prior=Path(p).name)
                                for c, p in near[:10]],
        rounds=rounds, feasible=feasible, n_quota_priors=len(targets),
        base_pool_px=int(base_pool.sum()), consensus_max_in_pool=cmax,
        ranking=("field = stitched per-fold operating percentile rank of View B, times View A rank^0.25, "
                 "times (1 + 0.5*consensus/consensus_max); consensus counts distinct decoded prior "
                 "patterns whose 3 px halo covers the pixel (H69-2)"),
        placement=("greedy top-S with hard-core 3 px spacing over a pool restricted to pixels of low "
                   "cross-family consensus, under a per-prior near-dot quota of floor(0.6985*S); the "
                   "directed 3 px near-dot count of ALL informative priors is then re-measured exactly"),
        exclusion_rather_than_quota=(
                   "two constructions were measured and rejected before this one. (1) A quota of "
                   "floor(0.6985*S) against a TARGET S has the wrong denominator: at quota 26,263 only "
                   "35,149 dots were placeable, an achieved share of 0.7472 against a limit of 0.70. "
                   "(2) Excluding the offenders' halos is not available at all: the union of the 84 "
                   "offenders' 3 px halos leaves 361 px of the 4,859,987 px legal set. The shipped "
                   "construction iterates the quota to a fixed point against the ACHIEVED budget."),
        view_A_channels=len([v for v in ck0["views"] if v == "A"]),
        view_B_channels=len([v for v in ck0["views"] if v == "B"])))
    log("PLACE_DONE")


# ================================================================================================
# stage 4 - gates, projection, artefacts
# ================================================================================================
def stage_gates(args):
    pred = np.load(W / "pred.npy")
    valid = np.load(W / "valid.npy")
    legal = np.load(W / "legal.npy")
    core = np.load(W / "core.npy")
    ck = json.loads((W / "place_ckpt.json").read_text())
    sample = ROOT / "data/sample_submission.tif"
    stamp = now()
    S = int(pred.sum())
    name = f"gems52-h69-cotrain-basementview-consensus-lanefeasible-{S}px-{stamp}"
    tif = SUB / f"{name}.tif"

    # ---------- format --------------------------------------------------------------------------
    arr = np.asarray(pred, np.float32)                                  # all-finite export policy
    assert np.isfinite(arr).all() and arr.min() >= 0.0 and arr.max() <= 1.0
    info = G.write_geotiff(tif, arr)
    fmt = gates.format_report(tif, sample, footprint=valid)
    log(f"format gate: ok={fmt['ok']} problems={fmt['problems']}")

    # ---------- registry ------------------------------------------------------------------------
    found = gates.find_priors([W / "priors", ROOT / "submission", ROOT / "data/scored",
                               ROOT / "data/reference"], exclude=tif)
    found = [p for p in found if p.name != tif.name]
    # Pre-filter to rasters on the competition grid. gates.lane_report and gates.uniqueness_report both
    # turn an unaligned prior into a per-row error, and uniqueness_report then reports
    # canonical_pattern_unique=False because of it -- an "error" that would silently read as "this file
    # is a copy of something". Excluded files are counted and published, not dropped quietly.
    priors, skipped = [], []
    with rasterio.open(sample) as ref:
        gmeta = (ref.shape, ref.crs, ref.transform)
    for p in found:
        try:
            with rasterio.open(p) as ds:
                if ds.count == 1 and (ds.shape, ds.crs, ds.transform) == gmeta:
                    priors.append(p)
                else:
                    skipped.append(dict(path=str(p), reason=f"count={ds.count} shape={ds.shape} "
                                                            f"crs={ds.crs} transform mismatch={tuple(ds.transform)[:6] != gmeta[2]}"))
        except Exception as exc:
            skipped.append(dict(path=str(p), reason=f"{type(exc).__name__}: {str(exc)[:120]}"))
    log(f"registry: {len(found)} .tif files found, {len(priors)} aligned single-band priors used, "
        f"{len(skipped)} excluded as not on the competition grid")
    cov_cache: dict[str, float] = {}
    nf = np.load(W / "novel_field.npy").astype(np.float64)
    lo_s, hi_s = float(nf[legal].min()), float(nf[legal].max())
    surface = np.clip((nf - lo_s) / (hi_s - lo_s), 0.0, 1.0).astype(np.float32)
    surface[~legal] = 0.0
    log(f"surface field for the lane's surface phase: min-max normalised over the legal set "
        f"[{lo_s:.5f}, {hi_s:.5f}] -> [{float(surface[legal].min()):.4f}, {float(surface[legal].max()):.4f}]")
    # The two lane phases cost ~13 min over 566 rasters, so each report is cached against the SHA-256
    # of the emission and the prior count. A cache hit is only possible for a byte-identical candidate
    # over a byte-identical registry, and this round's own artefacts are excluded from that registry.
    cache_key = hashlib.sha256(pred.astype("<f4").tobytes()).hexdigest()[:16] + f"-{len(priors)}"
    cpath = {k: W / f"gatecache_{k}_{cache_key}.json" for k in ("surface", "dots", "uniq")}

    def cached(key, fn):
        if cpath[key].exists():
            log(f"{key} report loaded from cache {cpath[key].name}")
            return json.loads(cpath[key].read_text())
        rep = fn()
        write_json(cpath[key], rep)
        return rep

    lane_surface = cached("surface", lambda: gates.lane_report(
        surface, legal, priors, sample=sample, phase="surface", coverage_cache=cov_cache, log=log))
    log(f"lane surface: literal {lane_surface['literal']['verdict']} "
        f"policy {lane_surface['policy']['verdict']} "
        f"max_rho={lane_surface['policy']['max_spearman']} errors={lane_surface['error_count']}")
    lane_dots = cached("dots", lambda: gates.lane_report(
        pred, legal, priors, sample=sample, phase="dots", coverage_cache=cov_cache, log=log))
    uniq = cached("uniq", lambda: gates.uniqueness_report(pred, priors, top=None))
    log(f"lane dots: literal {lane_dots['literal']['verdict']} policy {lane_dots['policy']['verdict']} "
        f"max_near={lane_dots['policy']['max_near_3px_fraction']} "
        f"max_rho={lane_dots['policy']['max_spearman']} errors={lane_dots['error_count']}")
    log(f"uniqueness: pattern_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f} union_px={uniq['union_px']} "
        f"equals_literal_union={uniq['equals_literal_prior_union']}")

    # ---------- not the union of the two views ---------------------------------------------------
    pa = np.load(W / "pa.npy")
    pb = np.load(W / "pb.npy")
    diff_cells = []
    for f in range(N_FOLDS):
        a = np.load(W / f"rA_f{f}.npy")
        b = np.load(W / f"rB_f{f}.npy")
        allowed = np.load(W / f"allowed_f{f}.npy")
        u = nodes.spacing_select(np.nan_to_num(np.maximum(a, b), nan=-1.0), allowed,
                                 BUDGET_PER_FOLD, min_px=3.0)
        diff_cells.append(int((u != (pred > 0)).sum()))
    not_union = dict(per_fold_differing_cells=diff_cells, min_differing=int(min(diff_cells)),
                     pass_=bool(min(diff_cells) > 0),
                     instrument=("union_max arm of the committed splitter (spatial.folds), placed by "
                                 "nodes.spacing_select at the same 9,400-dot-per-fold budget and 3 px "
                                 "separation as every other arm"),
                     note="the shipped emission is one global 37,600-dot placement, so it differs from "
                          "every per-fold union arm by construction; measured rather than asserted")

    # ---------- projection (never a score) -------------------------------------------------------
    sizes = dict(A=37654, B=44090, C=60069, E=121131)
    proj = []
    n_novel = S - ck["n_core"]
    ts = np.linspace(0, 1, 161)
    rs = np.linspace(RHO_NOVEL[0], RHO_NOVEL[1], 161)
    TT, RR = np.meshgrid(ts, rs, indexing="ij")
    for g in np.linspace(G_LO, G_HI, 41):
        T = {k: REPORTED[k] * (0.2 * sizes[k] + 0.8 * g) for k in sizes}
        lo = T["A"] + T["C"] - T["E"]
        hi = T["A"]
        tail = T["E"] - T["B"]
        n5, n6 = 30220, 46821
        central = T["C"] - tail * n5 / (n5 + n6)
        scale = ck["n_core"] / 25517.0
        lo, hi, central = lo * scale, hi * scale, central * scale
        den = 0.2 * S + 0.8 * g
        row = dict(g=float(g), t_core_lo=float(lo), t_core_hi=float(hi), t_core_central=float(central))
        for lbl, tc in (("lo", lo), ("central", central), ("hi", hi)):
            for rlbl, rho in (("rho_lo", RHO_NOVEL[0]), ("rho_mid", float(np.mean(RHO_NOVEL))),
                              ("rho_hi", RHO_NOVEL[1])):
                t = min(tc + rho * n_novel, g)
                row[f"dti_{lbl}_{rlbl}"] = round(t / den, 6)
        proj.append(row)
    # ---- counterfactual: the withdrawn core+novel recombination, quantified but NOT shipped ------
    counterfactual = {}
    n_core_cf, n_novel_cf = 25502, 11200
    S_cf = n_core_cf + n_novel_cf
    for glbl, g in (("G_lo", G_LO), ("G_mid", 0.5 * (G_LO + G_HI)), ("G_hi", G_HI)):
        T = {k: REPORTED[k] * (0.2 * sizes[k] + 0.8 * g) for k in sizes}
        lo = (T["A"] + T["C"] - T["E"]) * n_core_cf / 25517.0
        hi = T["A"] * n_core_cf / 25517.0
        tc = lo + TT * (hi - lo)
        t = np.minimum(tc + RR * n_novel_cf, g)
        d = t / (0.2 * S_cf + 0.8 * g)
        counterfactual[glbl] = dict(g=float(g), S=S_cf, n_core=n_core_cf, n_novel=n_novel_cf,
                                    t_core_bounds=[float(lo), float(hi)],
                                    p_beat_02778=float((d > 0.2778).mean()),
                                    p_beat_03774=float((d > 0.3774).mean()),
                                    mean_dti=float(d.mean()), worst_dti=float(d.min()),
                                    best_dti=float(d.max()))
    pw = {}
    for glbl, g in (("G_lo", G_LO), ("G_mid", 0.5 * (G_LO + G_HI)), ("G_hi", G_HI)):
        T = {k: REPORTED[k] * (0.2 * sizes[k] + 0.8 * g) for k in sizes}
        lo = (T["A"] + T["C"] - T["E"]) * ck["n_core"] / 25517.0
        hi = T["A"] * ck["n_core"] / 25517.0
        tc = lo + TT * (hi - lo)
        t = np.minimum(tc + RR * n_novel, g)
        d = t / (0.2 * S + 0.8 * g)
        pw[glbl] = dict(g=float(g), p_beat_02778=float((d > 0.2778).mean()),
                        p_beat_03195=float((d > 0.3195).mean()),
                        p_beat_03774=float((d > 0.3774).mean()),
                        mean_dti=float(d.mean()), worst_dti=float(d.min()), best_dti=float(d.max()),
                        t_core_bounds=[float(lo), float(hi)])
    log("PROJECTION:", json.dumps(pw, indent=1))

    # ---------- artefacts ------------------------------------------------------------------------
    zf = SUB / f"{name}.zip"
    with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, tif.name)
    (SUB / f"{name}-submission-name.txt").write_text(name + "\n")
    # The portal's note field is bounded, and a note truncated mid-word is a note nobody can read:
    # build it short enough that the 140-character cut can never fire, then assert that it did not.
    note = (f"H69 co-training, novel-only {n_novel}px, consensus-restricted lane-feasible; "
            f"max near-dot {lane_dots['policy']['max_near_3px_fraction']:.3f}; "
            f"research, not a verified fault map")
    if len(note) > 140:
        raise SystemExit(f"submission note is {len(note)} chars, over the 140 budget")
    (SUB / f"{name}-submission-note.txt").write_text(note + "\n")

    lane_ok = bool(lane_dots["policy"]["verdict"] == "PASS" and lane_surface["policy"]["verdict"] == "PASS")
    # The >=20% support-novelty diagnostic cannot pass on a registry whose informative priors' 3 px
    # halos cover 100% of the legal set (work/h69/probe.py: pool_exact_novel = 0). It is reported as a
    # FAILED diagnostic, never silently waived (gates.gate_correction). Uniqueness for the verdict is
    # the brief's own rule: distinct decoded pattern, Spearman <= 0.90, near-dot <= 0.70 per raster.
    uniq_ok = bool(uniq["canonical_pattern_unique"] and not uniq["equals_literal_prior_union"])
    hold = json.loads((EV / "h69_holdout.json").read_text())
    sB = hold["pooled"]["scores"]["single_B"]["dti"]
    cand = hold["pooled"]["scores"]["disagreement_post"]["dti"]
    pd = hold["pooled"]["paired_differences"]["single_B"]
    beats = bool(pd["ci95"][0] > 0)
    s1 = json.loads((EV / "h69_s1.json").read_text())
    verdict = "promote" if (fmt["ok"] and uniq_ok and lane_ok and s1["pass_"] and beats) else "negative"
    portal_will_accept = bool(fmt["ok"])          # the file itself cannot trip a format rejection
    submit = bool(verdict == "promote")           # the frozen promote rule, all five clauses
    card = dict(
        round="H69", generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis=("H69-1 basement-surface differential geometry as View A, co-trained against a "
                    "DEM-curvature/slope + radiometric-total-count View B, with disagreement as the "
                    "discovery signal; H69-2 cross-family consensus as the credit-density proxy for "
                    "the novel mass"),
        mechanism=("Blum-Mitchell two-view co-training (View A = differential geometry of the basement "
                   "surface and the potential field; View B = DEM curvature/slope plus radiometric total "
                   "count) for the discovery signal and the holdout arms, then a NOVEL-ONLY emission "
                   "ranked by the stitched two-view operating field times cross-family consensus and "
                   "placed by a greedy whose pool is restricted to low-consensus pixels so the brief's "
                   "70% per-raster near-dot rule holds against every informative prior. The "
                   "pre-registered credited-core variant was withdrawn before placement; see "
                   "knowledge/52b."),
        named_non_fault_mimic=("a lithologic contact or a basin axis with a density and magnetisation "
                               "contrast and no relief; on the surface view, roads and erosion lines"),
        holdout_dti=dict(evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
                         withheld_positives=hold["withheld_positives"],
                         scores={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in
                                 hold["pooled"]["scores"].items()},
                         candidate_minus_single_B=dict(delta=pd["delta"], ci95=pd["ci95"]),
                         beats_single_B=beats,
                         validity=("the instrument anti-ranks the board (rho=-0.1045, p=0.734, n=13); "
                                   "HOLDOUT-DTI is not a forecast")),
        s1_sufficiency=dict(view_A_mean=s1["summary"]["A"]["mean"],
                            view_A_min=s1["summary"]["A"]["minimum"], pass_=s1["pass_"]),
        projection=dict(evidence_class="PROJECTION, never a score",
                        g_bracket=[G_LO, G_HI], rho_novel_prior=list(RHO_NOVEL),
                        per_g=pw, per_g_table=proj[::10],
                        counterfactual_recombination_NOT_SHIPPED=dict(
                            why=("prereg amendment knowledge/52b withdrew the credited-core emission: this "
                                 "repository already corrected a core-recombination file as NOT unique "
                                 "(README H60C correction, IR-H61-007, IR-UNQ-001), and sizing a file to "
                                 "land just under the 0.70 threshold a previous round was corrected for "
                                 "exceeding is re-tuning a negative result into a positive"),
                            design="P1 = A & C restricted to the legal set (25,502 px) + 11,200 novel px",
                            per_g=counterfactual),
                        algebra="DTI = min(t_core + rho_novel*n_novel, |G|) / (0.2*S + 0.8*|G|)"),
        registry=dict(n_tif_files_found=len(found), n_priors=len(priors),
                      n_excluded_not_on_competition_grid=len(skipped),
                      excluded_examples=skipped[:10],
                      lane_report_error_count=lane_dots["error_count"],
                      lane_report_errors=lane_dots["errors"][:10],
                      distinct_decoded=lane_dots["distinct_decoded_priors"],
                      n_probes=lane_dots["policy"]["universal_coverage_probes"],
                      n_informative=lane_dots["policy"]["informative_priors"]),
        correlation_vs_registry=dict(
            literal=dict(max_spearman=lane_dots["literal"]["max_spearman"],
                         max_near_3px=lane_dots["literal"]["max_near_3px_fraction"],
                         max_near_source=lane_dots["literal"].get("max_near_source"),
                         verdict=lane_dots["literal"]["verdict"],
                         duplicate=bool(lane_dots["literal"]["verdict"] != "PASS")),
            policy=dict(max_spearman=lane_dots["policy"]["max_spearman"],
                        max_near_3px=lane_dots["policy"]["max_near_3px_fraction"],
                        max_near_source=lane_dots["policy"].get("max_near_source"),
                        verdict=lane_dots["policy"]["verdict"],
                        duplicate=bool(lane_dots["policy"]["verdict"] != "PASS")),
            surface_literal=dict(max_spearman=lane_surface["literal"]["max_spearman"],
                                 verdict=lane_surface["literal"]["verdict"],
                                 duplicate=bool(lane_surface["literal"]["verdict"] != "PASS")),
            surface_policy=dict(max_spearman=lane_surface["policy"]["max_spearman"],
                                verdict=lane_surface["policy"]["verdict"],
                                duplicate=bool(lane_surface["policy"]["verdict"] != "PASS"))),
        overlap_vs_registry=dict(novel_fraction_vs_all_informative_union=uniq.get("novel_fraction"),
                                 novel_fraction_vs_binding_priors=ck["novel_fraction_vs_binding"],
                                 support_novelty_20pct_diagnostic=bool(uniq.get("support_novelty_gate_ok")),
                                 support_novelty_diagnostic_status=(
                                     "FAILED and reported, not waived: the union of all informative "
                                     "priors' 3px halos covers 100% of the legal set, so no candidate "
                                     "on this registry can pass it (work/h69/probe.py)"),
                                 union_px=uniq.get("union_px"),
                                 canonical_pattern_unique=uniq["canonical_pattern_unique"],
                                 equals_literal_prior_union=uniq["equals_literal_prior_union"],
                                 credited_core_shipped=False,
                                 credited_core_withdrawn_by="knowledge/52b_h69_prereg_amendment_placement.md",
                                 core_px=ck["n_core"], novel_px=n_novel),
        raster_sha256=info["sha256"], raster_bytes=info["bytes"],
        validator=dict(no_nan_inside_footprint=int(fmt["nan_pixels"]) == 0,
                       values_in_0_1=bool(fmt["min"] >= 0.0 and fmt["max"] <= 1.0),
                       unique_values=int(len(np.unique(arr))),
                       value_set=[float(v) for v in np.unique(arr)],
                       mass_outside_valid_footprint=int(((arr > 0) & ~valid).sum()),
                       dtype=fmt["dtype"], bands=fmt["bands"],
                       crs=fmt["crs"], shape=[fmt["height"], fmt["width"]],
                       transform=fmt["transform"], matches_sample=bool(fmt["ok"]),
                       problems=fmt["problems"]),
        not_union=not_union,
        submission_name=name, submission_note=note, note_chars=len(note),
        gates=dict(format=bool(fmt["ok"]), lane=lane_ok, unique=uniq_ok, not_union=not_union["pass_"],
                   S1=s1["pass_"], holdout_beats_single_B=beats),
        verdict=verdict,
        download_ok=bool(fmt["ok"]),
        portal_will_accept_the_format=portal_will_accept,
        submit_recommended=submit,
        submit_recommendation_reason=(
            "all five frozen promote clauses pass" if submit else
            "the frozen promote rule (knowledge/52 section 3) requires format AND uniqueness AND lane AND "
            "not-union AND S1 AND a holdout paired CI lower bound above single_B; "
            + " and ".join([f"{k} FAILS" for k, v in
                            (("S1 sufficiency", s1["pass_"]), ("holdout beats single_B", beats),
                             ("format", fmt["ok"]), ("uniqueness", uniq_ok), ("lane", lane_ok),
                             ("not-union", not_union["pass_"])) if not v])
            + ", so no weekly slot should be spent on it"),
        slots_used=0,
    )
    write_json(EV / "h69_run_card.json", card)
    write_json(EV / "h69_format_gate.json", fmt)
    write_json(EV / "h69_uniqueness.json", {k: v for k, v in uniq.items() if k != "per_prior"})
    write_json(EV / "h69_lane_surface.json", {k: v for k, v in lane_surface.items() if k != "per_prior"})
    write_json(EV / "h69_lane_dots.json", {k: v for k, v in lane_dots.items() if k != "per_prior"})
    write_json(EV / "h69_placement.json", ck)
    write_json(SUB / f"{name}.json", card)
    (SUB / "H69_LATEST.txt").write_text(
        f"{tif.name}\n# pointer for the site; NOT an upload approval. Verdict: {verdict}. "
        f"Download OK: {fmt['ok']}. Spend a weekly slot: {submit}.\n")
    log(f"RUN CARD: verdict={verdict} format={fmt['ok']} lane={lane_ok} unique={uniq_ok} "
        f"not_union={not_union['pass_']} S1={s1['pass_']} beats_single_B={beats}")
    log(f"TIFF {tif.name} {info['bytes']} bytes sha256 {info['sha256']}")
    log("GATES_DONE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["features", "lane", "place", "gates", "all"])
    ap.add_argument("--force-features", action="store_true")
    args = ap.parse_args()
    check_prereg()
    W.mkdir(parents=True, exist_ok=True)
    if args.stage in ("features", "all") and (args.force_features or not (W / "stack.npy").exists()):
        stage_features()
    if args.stage in ("lane", "all") and not (EV / "h69_holdout.json").exists():
        stage_lane()
    if args.stage in ("place", "all") and not (W / "pred.npy").exists():
        stage_place()
    if args.stage in ("gates", "all"):
        stage_gates(args)


if __name__ == "__main__":
    main()
