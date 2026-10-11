#!/usr/bin/env python3
"""H97 -- co-training lane: the B-only disagreement stratum as a fall-line / cardinal artefact veto.

Preregistered in ``knowledge/97_hypotheses_H97_preregistered.md`` (frozen before any fit; SHA-256
pinned in ``registry/h97_preregistration.json``). This runner refuses to start if that file moved.

Shared tools are reused, never forked:
  * cached feature stack, label-blind folds, learners, ranks -> ``run_h61`` (setup, sample_for_fit,
    learner_for, to_grid, pct_rank);
  * DVA2 channel operator -> ``run_h84._compute_band`` (identical to H82's), mmap reads -> ``run_h82.Bank``;
  * fit helpers -> ``run_h84.gather_arm / predict_region``; stitching -> ``run_h82.stitch``;
  * scoring -> ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1); placement -> ``gems52.nodes``;
  * lane / uniqueness / format -> ``gems52.gates`` (via ``run_h84.stage_lane``, redirected);
  * packaging -> ``gems52.submission_writer``.

Stages: channels | orient | fit | independence | holdout | build | lane | write | card | all
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

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82                                                 # noqa: E402
import run_h84 as h84                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial                              # noqa: E402

PREREG = ROOT / "registry/h97_preregistration.json"
REG = json.loads(PREREG.read_text())
WORK = ROOT / "work/h97"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
SEED = base.SEED
K_FOLD = REG["emission"]["K_fold"]
K_TOTAL = REG["emission"]["K_total"]
RING_M = REG["emission"]["catalogue_ring_excluded_m"]
PREFIX = "gems52-h97-"
PRIMARY = REG["primary_arm"]
BEST = "B_DVA2"
OR = REG["orientation"]

DVA2 = h82.DVA2                                            # 50 channels, bands 12/19/13/15/18
SURF_NAMES = tuple(REG["surface_dva2_bands"].values())     # det_elev, det_elev_slope
DVA2S = sorted(n for n in DVA2 if any(n.startswith(f"DVA2_{nm}_") and
                                      n[len(f"DVA2_{nm}_"):].split("_")[0] in ("aniso", "logvar")
                                      for nm in SURF_NAMES))
ARM_CHANNELS = {"single_A": [], "single_B": [], "B_DVA2": DVA2, "B_DVA2s": DVA2S}
LEARNERS = tuple(REG["learner_arms"])

# redirect the shared modules' checkpoints to this round (run_h70.redirect precedent)
h82.WORK = WORK


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h97_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float, allow_nan=False) + "\n")
    return p


def check_prereg():
    if digest(ROOT / REG["hypothesis_document"]) != REG["hypothesis_sha256"]:
        raise SystemExit("H97 preregistered document changed after freezing; refusing to run")
    return REG


def _patch_h84():
    h84.WORK, h84.FEAT, h84.PREFIX, h84.K_TOTAL = WORK, FEAT, PREFIX, K_TOTAL
    h84.write = write
    h84.check_prereg = check_prereg


# ------------------------------------------------------------------------------------------- channels
def stage_channels():
    """DVA2 for the five H82 bands via the shared operator; only DVA2_* columns are kept."""
    from gems52.structural import save_array
    check_prereg()
    FEAT.mkdir(parents=True, exist_ok=True)
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    M, _cond = h84.harmonic_operator()
    sha, arr_sha, stats = {}, {}, {}
    t0 = time.time()

    def persist(name, grid):
        if not name.startswith("DVA2_"):
            return
        v = np.ascontiguousarray(np.asarray(grid, np.float32)[eligible])
        p = FEAT / (name + ".npy")
        for attempt in range(6):            # IR-H82/H84: re-read and require a bit-exact file
            save_array(p, v)
            if np.array_equal(np.load(p), v):
                break
            time.sleep(0.5)
        else:
            raise SystemExit(f"channel {name} could not be written bit-exactly")
        sha[name] = digest(p)
        arr_sha[name] = hashlib.sha256(v.tobytes()).hexdigest()

    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in h82.BANDS.items():
            h84._compute_band(ds, b, nm, eligible, M, persist, stats, t0)
    missing = sorted(set(DVA2) - set(sha))
    if missing:
        raise SystemExit(f"missing DVA2 channels: {missing}")
    # second audit pass after a pause (files that moved after write are recomputed by re-running)
    time.sleep(3.0)
    moved = [n for n in sha if digest(FEAT / (n + ".npy")) != sha[n]]
    if moved:
        raise SystemExit(f"IR-H84-003 class failure: {len(moved)} files moved after write: {moved[:5]}")
    man = dict(round="H97", created_utc=now(), operator="run_h84._compute_band (== run_h82 DVA2)",
               bands={str(k): v for k, v in h82.BANDS.items()}, lags_px=list(h82.LAGS), sigma_px=h82.SIGMA,
               dva2=DVA2, dva2_surface_only=DVA2S, sha256=sha, array_sha256=arr_sha,
               inputs_sha256=dict(store.manifest["inputs"]))
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    write("channels", dict(stage="channels", n=len(sha), dva2_surface_only=DVA2S, seconds=time.time() - t0,
                           file_sha256=sha, finished_utc=now()))
    log(f"channels: {len(sha)} DVA2 columns in {time.time()-t0:.0f}s")


# --------------------------------------------------------------------------------------------- orient
def orientation_fields(eligible):
    """FL (fall-line alignment of the Hessian feature axis), d_card (deg), defined mask, low-slope mask."""
    s = OR["sigma_px"]
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        z = ds.read(OR["band"]).astype(np.float64)
        slope = ds.read(OR["road_slope_band"]).astype(np.float64)
    ok = np.isfinite(z) & eligible
    mu, sd = float(z[ok].mean()), float(z[ok].std()) + 1e-12
    z = np.where(ok, (z - mu) / sd, 0.0)
    gx = ndi.gaussian_filter(z, s, order=(0, 1))
    gy = ndi.gaussian_filter(z, s, order=(1, 0))
    hxx = ndi.gaussian_filter(z, s, order=(0, 2))
    hyy = ndi.gaussian_filter(z, s, order=(2, 0))
    hxy = ndi.gaussian_filter(z, s, order=(1, 1))
    del z
    # eigen-decomposition of the symmetric 2x2 Hessian; principal angle of the larger-|lambda| axis
    tr2 = 0.5 * (hxx + hyy)
    rad = np.sqrt((0.5 * (hxx - hyy)) ** 2 + hxy ** 2)
    l1, l2 = tr2 + rad, tr2 - rad
    phi = 0.5 * np.arctan2(2.0 * hxy, hxx - hyy)        # eigenvector angle of l1 (image frame, x east, y south)
    phi_big = np.where(np.abs(l1) >= np.abs(l2), phi, phi + np.pi / 2.0)
    axis = phi_big + np.pi / 2.0                          # along-feature axis = smaller-|curvature| direction
    del tr2, rad, l1, l2, phi, phi_big, hxx, hyy, hxy
    gmag = np.hypot(gx, gy)
    gthr = float(np.quantile(gmag[eligible], OR["grad_defined_quantile"]))
    defined = eligible & (gmag > gthr)
    fl = np.abs(np.cos(axis) * gx + np.sin(axis) * gy) / np.maximum(gmag, 1e-12)
    fl = np.where(defined, np.clip(fl, 0.0, 1.0), 0.0)
    az = np.degrees(axis) % 180.0
    dcard = np.minimum.reduce([np.abs(az - 0.0), np.abs(az - 90.0), np.abs(az - 180.0)])
    sthr = float(np.quantile(slope[eligible & np.isfinite(slope)], OR["road_slope_max_quantile"]))
    lowslope = eligible & np.isfinite(slope) & (slope <= sthr)
    meta = dict(grad_threshold=gthr, slope_median=sthr, defined_fraction=float(defined[eligible].mean()),
                fl_ge_erosion_fraction=float((fl[eligible] >= OR["erosion_fl_min"]).mean()),
                dcard_le_road_fraction=float((dcard[eligible] <= OR["road_dcard_max_deg"]).mean()))
    return fl.astype(np.float32), dcard.astype(np.float32), defined, lowslope, meta


def stage_orient():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    fl, dcard, defined, lowslope, meta = orientation_fields(eligible)
    for n, a in (("FL", fl), ("DCARD", dcard), ("DEFINED", defined), ("LOWSLOPE", lowslope)):
        h82.save_verified(WORK / f"orient_{n}.npy", a)
    # sanity: the catalogue's own feature-axis geometry (descriptive; full public catalogue, no fold truth)
    cm = cat & eligible
    meta["catalogue_px"] = int(cm.sum())
    meta["catalogue_fl_ge_erosion_fraction"] = float((fl[cm] >= OR["erosion_fl_min"]).mean())
    meta["catalogue_mean_fl_defined"] = float(fl[cm & defined].mean())
    meta["eligible_mean_fl_defined"] = float(fl[eligible & defined].mean())
    write("orient", dict(stage="orient", **meta, finished_utc=now(),
                         note="descriptive only; thresholds were frozen before this ran"))
    log(json.dumps(meta, default=float))


def load_orient():
    return tuple(np.load(WORK / f"orient_{n}.npy") for n in ("FL", "DCARD", "DEFINED", "LOWSLOPE"))


# ------------------------------------------------------------------------------------------------ fit
def stage_fit():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    bank = h82.Bank(FEAT)
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    fl, dcard, defined, lowslope = load_orient()
    out = dict(stage="fit", started_utc=now(), arms=list(LEARNERS), seed=SEED, folds=[],
               canary_negatives="region cells > 5 px from catalogue, deterministic subsample of 400,000")
    for fold in folds:
        f = fold["fold"]
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_all = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        neg_g = np.sort(np.random.default_rng(SEED + 900 + f).choice(neg_all, min(400_000, len(neg_all)),
                                                                     replace=False))
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        allg = np.r_[pos_g, neg_g]
        rec = dict(fold=f, n_train_rows=int(len(rows)), n_pos=int(len(pos_g)), n_neg_canary=int(len(neg_g)),
                   auc={}, canary={}, seconds={})
        erow = store.inverse[allg]

        def auc_of(v):
            v = np.asarray(v, np.float64)
            if not np.isfinite(v).all():
                v = np.nan_to_num(v, nan=np.nanmedian(v))
            a = float(roc_auc_score(yy, v)) if np.ptp(v) > 0 else 0.5
            return max(a, 1 - a)
        for nm in list(va) + list(vb):
            rec["canary"][nm] = auc_of(store.gather(allg, [nm])[:, 0])
        for nm in DVA2:
            rec["canary"][nm] = auc_of(bank.col(nm)[erow])
        rec["canary"]["H97_FL"] = auc_of(fl.ravel()[allg])
        rec["canary"]["H97_DCARD"] = auc_of(dcard.ravel()[allg])
        worst = max(rec["canary"].items(), key=lambda kv: kv[1])
        rec["canary_max"], rec["canary_worst"] = worst[1], worst[0]
        rec["canary_alarm"] = bool(worst[1] >= REG["canary_alarm_auc"])
        log(f"fold {f}: canary max {worst[1]:.4f} ({worst[0]}) FL {rec['canary']['H97_FL']:.4f} "
            f"DCARD {rec['canary']['H97_DCARD']:.4f} alarm={rec['canary_alarm']}")
        for arm in LEARNERS:
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if not ck.exists():
                names_store = va if arm == "single_A" else vb
                m = base.learner_for("A" if arm == "single_A" else "B", SEED)
                m.fit(h84.gather_arm(store, bank, rows, names_store, ARM_CHANNELS[arm]), y)
                p = h84.predict_region(store, bank, m, names_store, ARM_CHANNELS[arm], region_rows)
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                h82.save_verified(ck, full)
                del m, p, full
            g = np.asarray(np.load(ck, mmap_mode="r"), np.float32)
            rec["auc"][arm] = float(roc_auc_score(yy, g[erow]))
            rec["seconds"][arm] = time.time() - t1
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g
        out["folds"].append(rec)
        write("fit", out)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_overall"] = max(r["canary_max"] for r in out["folds"])
    out["canary_alarm_auc_bar"] = REG["canary_alarm_auc"]
    sa = [r["auc"]["single_A"] for r in out["folds"]]
    out["sufficiency_view_A"] = dict(mean=float(np.mean(sa)), min_fold=float(np.min(sa)), per_fold=sa,
                                     gate_mean=0.60, gate_min_fold=0.55,
                                     passes=bool(np.mean(sa) >= 0.60 and np.min(sa) >= 0.55))
    out["finished_utc"] = now()
    write("fit", out)
    log(json.dumps({"canary_max": out["canary_max_overall"], "suff_A": out["sufficiency_view_A"]["mean"]}))


# --------------------------------------------------------------------------------------- independence
def stage_independence():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th_src = ROOT / REG["independence_thresholds_from"]
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="independence", started_utc=now(), thresholds_from=str(th_src.relative_to(ROOT)),
               thresholds_sha256=digest(th_src),
               thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"], min_blocks=20),
               pairs={}, caveat=("negatives are catalogue-zero proxies, not verified absence; weak error "
                                 "correlation is necessary for co-training, not proof of conditional independence"))
    for b_arm in ("B_DVA2s", "B_DVA2"):
        blocks_all, per_fold = [], []
        for fold in folds:
            f = fold["fold"]
            pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
            pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_{b_arm}_f{f}.npy"), eligible.shape)
            neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
            thr = (float(np.quantile(pa[neg], th["donor_rank_min"])), float(np.quantile(pb[neg], th["donor_rank_min"])))
            blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                                   neg, f, thr, side=th["block_side_px"], minimum=32)
            blocks_all += blocks
            per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), n_blocks=len(blocks)))
            del pa, pb
        res = spatial.independence(blocks_all, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
        out["pairs"][f"single_A_vs_{b_arm}"] = dict(per_fold=per_fold, result=res)
        log(f"independence A vs {b_arm}: " + json.dumps({k: v for k, v in res.items()
                                                         if not isinstance(v, (list, dict))}, default=float))
    out["finished_utc"] = now()
    write("independence", out)


# -------------------------------------------------------------------------------------------- arms
def arm_fields(rA, rB, rBs, fl, dcard, lowslope):
    """All H97 derived arms from rank fields (NaN = not allowed). Frozen rules, knowledge/97 sec.2."""
    sb = REG["strata"]["b_only"]
    erosion = fl >= OR["erosion_fl_min"]
    road = (dcard <= OR["road_dcard_max_deg"]) & lowslope
    off = REG["veto_offset"]

    def veto(rb, flag):
        b_only = (rb >= sb["B_rank_min"]) & (rA < sb["A_rank_max_exclusive"])
        return np.where(b_only & flag, rb + off, rb), b_only & flag
    out, flags = {}, {}
    out["H97_veto"], flags["H97_veto"] = veto(rB, erosion | road)
    out["H97_veto_fl"], flags["H97_veto_fl"] = veto(rB, erosion)
    out["H97_veto_card"], flags["H97_veto_card"] = veto(rB, road)
    out["H97_veto_s"], flags["H97_veto_s"] = veto(rBs, erosion | road)
    out["H97_scarp_soft"] = rB * (1.0 - REG["scarp_soft_weight"] * fl)
    c = REG["consensus"]
    out["H97_consensus"] = rB * (c["base"] + c["a_weight"] * rA)
    return out, flags, erosion, road


def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def stage_holdout():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    fl, dcard, defined, lowslope = load_orient()
    arms = tuple(REG["arms"])
    terms = {a: None for a in arms}
    out = dict(stage="holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD, min_px=3.0,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), folds=[], started_utc=now())
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        ranks = {}
        for arm in LEARNERS:
            g = base.to_grid(store.flat_idx, np.load(WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
            r = np.full(eligible.shape, np.nan, np.float32)
            r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
            ranks[arm] = r
            del g
        derived, flags, erosion, road = arm_fields(ranks["single_A"], ranks["B_DVA2"], ranks["B_DVA2s"],
                                                   fl, dcard, lowslope)
        tdist = ndi.distance_transform_edt(~fold["truth"])
        credit = np.clip(1.0 - tdist / 3.0, 0.0, None)        # per-dot diagnostic: 300 m triangle at 100 m px
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()), arms={})
        for arm in arms:
            fld = np.full(eligible.shape, -9.0, np.float32)
            if arm == "random":
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                src = ranks[arm] if arm in ranks else derived[arm]
                fld.ravel()[ai] = np.nan_to_num(src.ravel()[ai], nan=-9.0)
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()), mean_dot_credit=float(credit[em].mean()))
            if arm == BEST:      # stratified per-dot diagnostic of the control emission (not a score)
                b_only = (ranks["B_DVA2"] >= REG["strata"]["b_only"]["B_rank_min"]) & \
                         (ranks["single_A"] < REG["strata"]["b_only"]["A_rank_max_exclusive"])
                strata = dict(b_only_erosion=em & b_only & erosion, b_only_road=em & b_only & road & ~erosion,
                              b_only_clean=em & b_only & ~erosion & ~road, not_b_only=em & ~b_only)
                rec["control_dot_strata"] = {k: dict(n=int(v.sum()), mean_credit=float(credit[v].mean())
                                                     if v.any() else None) for k, v in strata.items()}
            if arm in flags:
                rec["arms"][arm]["vetoed_cells_in_allowed"] = int((flags[arm] & allowed).sum())
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())} credit/dot "
                f"{rec['arms'][arm]['mean_dot_credit']:.4f}")
            del fld, em
        out["folds"].append(rec)
        del ranks, derived, flags, tdist, credit
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    out["controls"] = {}
    for arm, target in REG["control_targets"].items():
        got = float(out["pooled"]["scores"][arm]["dti"])
        out["controls"][arm] = dict(committed=target, measured=got, abs_delta=abs(got - target),
                                    tolerance=REG["control_tolerance"],
                                    PASS=bool(abs(got - target) <= REG["control_tolerance"]))
    # each attribution arm's own paired comparison against the control B_DVA2
    out["vs_B_DVA2"] = {}
    for arm in arms:
        if arm in (BEST,):
            continue
        ps = evaluator.pooled_summary({arm: terms[arm], BEST: terms[BEST]}, draws=1000, seed=SEED, candidate=arm)
        out["vs_B_DVA2"][arm] = ps["paired_differences"][BEST]
    ps = evaluator.pooled_summary({"H97_veto_s": terms["H97_veto_s"], "B_DVA2s": terms["B_DVA2s"]},
                                  draws=1000, seed=SEED, candidate="H97_veto_s")
    out["H97_veto_s_vs_B_DVA2s"] = ps["paired_differences"]["B_DVA2s"]
    out["paired_differences_keyed_by"] = "comparison arm; each entry is candidate minus that arm"
    out["finished_utc"] = now()
    write("holdout", out)
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in arms}))
    log("controls: " + json.dumps(out["controls"], default=float))
    log("vs B_DVA2: " + json.dumps({k: [round(v["delta"], 6)] + [round(x, 6) for x in v["ci95"]]
                                    for k, v in out["vs_B_DVA2"].items()}, default=float))


# ----------------------------------------------------------------------------------------------- build
def stitched_fields(folds, eligible, flat):
    fA = h82.stitch("single_A", folds, eligible, flat)
    fB = h82.stitch("B_DVA2", folds, eligible, flat)
    fBs = h82.stitch("B_DVA2s", folds, eligible, flat)
    fb0 = h82.stitch("single_B", folds, eligible, flat)
    return fA, fB, fBs, fb0


def stage_build():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    fl, dcard, defined, lowslope = load_orient()
    fA, fB, fBs, fb0 = stitched_fields(folds, eligible, store.flat_idx)
    derived, flags, erosion, road = arm_fields(fA, fB, fBs, fl, dcard, lowslope)
    fP = derived[PRIMARY]
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fP) & (catd * 100.0 > RING_M)
    # surface for the lane gate: primary field mapped to [0,1] (vetoed cells sit at the bottom)
    lo = REG["veto_offset"]
    surf = np.where(eligible & np.isfinite(fP), (fP - lo) / (1.0 - lo), 0.0).astype(np.float32)
    h82.save_verified(WORK / "surface.npy", surf)
    for k, v in (("primary", fP), ("A", fA), ("B", fB), ("Bs", fBs), ("single_B", fb0)):
        h82.save_verified(WORK / f"field_{k}.npy", v)
    h82.save_verified(WORK / "pool.npy", pool)
    h82.save_verified(WORK / "veto_flag.npy", flags[PRIMARY] & pool)
    sa = REG["strata"]["a_only"]
    a_only = pool & np.isfinite(fA) & (fA >= sa["A_rank_min"]) & (fB >= sa["B_rank_band"][0]) & \
        (fB <= sa["B_rank_band"][1])
    a_cand = nodes.spacing_select(np.where(a_only, fA, -1.0).astype(np.float32), a_only, int(a_only.sum()),
                                  min_px=sa["spacing_px"])
    h82.save_verified(WORK / "a_only_candidates.npy", a_cand)
    sb = REG["strata"]["b_only"]
    b_only = pool & (fB >= sb["B_rank_min"]) & (fA < sb["A_rank_max_exclusive"])
    rec = dict(stage="build_fields", pool_px=int(pool.sum()), eligible_px=int(eligible.sum()),
               b_only_px=int(b_only.sum()), vetoed_px=int((flags[PRIMARY] & pool).sum()),
               vetoed_erosion_px=int((b_only & erosion).sum()), vetoed_road_px=int((b_only & road).sum()),
               b_only_erosion_fraction=float(erosion[b_only].mean()),
               b_only_road_fraction=float(road[b_only].mean()),
               null_erosion=1.0 / 3.0, null_road=1.0 / 18.0,
               a_only_px=int(a_only.sum()), a_only_candidates=int(a_cand.sum()), finished_utc=now())
    write("build_fields", rec)
    log(json.dumps(rec, default=float))


# ------------------------------------------------------------------------------------------------ lane
def stage_lane():
    _patch_h84()
    h84.stage_lane()          # surface lane -> quota placement -> dots lane, receipts to evidence/h97_lane.json


# ----------------------------------------------------------------------------------------------- write
A_BANDS, A_MECH = h84.A_BANDS, h84.A_MECH


def write_a_only_reasoning(cand, fA, fB, catd, eligible, fl, name):
    ys, xs = np.nonzero(cand)
    p = ROOT / "docs/downloads" / "h97-a-only-reasoning.csv"   # one copy only (name in the CSV rows' file name not needed)
    with rasterio.open(SAMPLE) as s:
        tr = s.transform
    z = {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in A_BANDS.items():
            a = ds.read(b).astype(np.float64)
            ok = np.isfinite(a) & eligible
            mu, sd = float(a[ok].mean()), float(a[ok].std()) + 1e-12
            z[nm] = (a[ys, xs] - mu) / sd
            del a, ok
    names = list(A_BANDS.values())
    Z = np.stack([np.abs(z[nm]) for nm in names])
    dom = [names[i] for i in Z.argmax(0)]
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "view_A_rank", "view_B_rank_B_DVA2",
                    "dist_to_mapped_catalogue_m", "surface_fall_line_alignment_FL", "dominant_view_A_band"] +
                   [f"z_{nm}" for nm in names] +
                   ["geological_reasoning", "named_non_fault_process_that_could_mimic_it", "falsifier",
                    "confidence_note", "evidence_class"])
        for i in range(len(ys)):
            mech, mimic = A_MECH[dom[i]]
            w.writerow([int(ys[i]), int(xs[i]), round(float(tr.c + (xs[i] + 0.5) * tr.a), 1),
                        round(float(tr.f + (ys[i] + 0.5) * tr.e), 1), round(float(fA[ys[i], xs[i]]), 5),
                        round(float(fB[ys[i], xs[i]]), 5), round(float(catd[ys[i], xs[i]] * 100.0), 1),
                        round(float(fl[ys[i], xs[i]]), 3), dom[i]] +
                       [round(float(z[nm][i]), 3) for nm in names] +
                       [f"A-only (buried-fault reading: A confident, surface view abstains). Dominant View-A band "
                        f"{dom[i]} at |z| = {float(Z[names.index(dom[i]), i]):.2f} "
                        f"({'strong, >= 2 sd' if Z[names.index(dom[i]), i] >= 2 else 'moderate, < 2 sd: weak evidence'}). "
                        f"Template reading if the anomaly is real: {mech}", mimic,
                        "a seismic-reflection, gravity or MT profile across the cell shows no basement offset, "
                        "or 1-m LiDAR / field mapping shows unfaulted Quaternary cover with no buried step",
                        "LOW: View A has failed sufficiency in every round incl. H97 (see run card); the A-only "
                        "stratum scored below random on the catalogue holdout (H93); reviewer lead only",
                        "model evidence for a Phase-2 reviewer target; NOT an organizer-confirmed fault"])
    return str(p.relative_to(ROOT)), int(len(ys))


def stage_write():
    check_prereg()
    from gems52 import submission_writer
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    ln = json.loads((EVID / "h97_lane.json").read_text())
    if "stopped" in ln:
        raise SystemExit("lane stopped before placement; no raster is written (duplicate logged)")
    dots = np.load(WORK / "dots.npy").astype(bool)
    pool = np.load(WORK / "pool.npy")
    fP, fA, fB, fb0 = (np.load(WORK / f"field_{k}.npy") for k in ("primary", "A", "B", "single_B"))
    fl = np.load(WORK / "orient_FL.npy")
    catd = ndi.distance_transform_edt(~cat)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h97-fallline-veto-dva2-{int(dots.sum())}px-{stamp}"
    note = ("H97 co-train veto: B-only dots on fall-line/cardinal axes demoted (Hessian), DVA2 surface field, "
            "3px, 200m ring; research")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}-zeros.tif"
    pred = dots.astype(np.float32)          # exactly {0,1}; 0.0 outside the footprint; no NaN anywhere
    rec = submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                             metadata=dict(round="H97", primary_arm=PRIMARY))
    fmt = gates.format_report(out, SAMPLE, footprint=eligible)
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nodata=a.nodata, nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   nan_inside_footprint=int(np.isnan(v[eligible]).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), ones_outside_footprint=int(((v == 1) & ~eligible).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"] and val["shape_match"]
                       and val["transform_match"] and val["bounds_match"] and val["range_ok"]
                       and val["ones_outside_footprint"] == 0 and fmt["ok"])
    # not-the-union at equal budget on the same pool
    sel = lambda f: nodes.spacing_select(np.where(pool, np.nan_to_num(f, nan=-1.0), -1.0).astype(np.float32),  # noqa
                                         pool, K_TOTAL, min_px=3.0)
    a_dots, b_dots, b0_dots = sel(fA), sel(fB), sel(fb0)
    u_dots = sel(np.maximum(np.nan_to_num(fA, nan=-1.0), np.nan_to_num(fB, nan=-1.0)))

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    nu = dict(dots_emitted=int(dots.sum()), dots_equal_union=bool(np.array_equal(dots, u_dots)),
              dots_subset_of_union=bool(not (dots & ~u_dots).any()),
              dots_equal_single_A=bool(np.array_equal(dots, a_dots)),
              dots_equal_B_DVA2=bool(np.array_equal(dots, b_dots)),
              jaccard_with_union=jac(dots, u_dots), jaccard_with_single_A=jac(dots, a_dots),
              jaccard_with_B_DVA2_unvetoed=jac(dots, b_dots), jaccard_with_single_B=jac(dots, b0_dots),
              dots_not_in_union=int((dots & ~u_dots).sum()),
              dots_not_in_unvetoed_B_DVA2=int((dots & ~b_dots).sum()))
    nu["not_union_pass"] = bool(not nu["dots_equal_union"] and not nu["dots_subset_of_union"]
                                and not nu["dots_equal_single_A"] and not nu["dots_equal_B_DVA2"])
    # uniqueness against every registry raster (full census + local + scored/reference)
    _patch_h84()
    full, meta = h84.full_registry()
    uq = gates.uniqueness_report(pred, full)
    cmp = {}
    for key, p in (("ref_h33_2_b2_owner_reported_0.2778", "data/reference/h33-2-b2-zeros.tif"),
                   ("h84_candidate", "docs/downloads/h84-candidate.tif"),
                   ("h95_candidate", "docs/downloads/h95-candidate.tif")):
        pp = ROOT / p
        if pp.exists():
            with rasterio.open(pp) as d:
                r = np.nan_to_num(d.read(1)) > 0
            near = ndi.binary_dilation(r, structure=gates._disk(3.0))
            cmp[key] = dict(shared_px=int((r & dots).sum()), prior_px=int(r.sum()),
                            near_3px_share_of_my_dots=float(near[dots].mean()), jaccard=jac(dots, r))
    a_cand = np.load(WORK / "a_only_candidates.npy").astype(bool)
    a_csv, n_a = write_a_only_reasoning(a_cand, fA, fB, catd, eligible, fl, name)
    veto = np.load(WORK / "veto_flag.npy").astype(bool)
    res = dict(stage="write", file=str(out.relative_to(ROOT)), bytes=out.stat().st_size, sha256=digest(out),
               name=name, note=note, note_chars=len(note), validator=val, format_report=fmt, writer_receipt=rec,
               not_the_union=nu, uniqueness=uq, registry_meta=meta, vs_named_priors=cmp,
               dots_on_vetoed_cells=int((dots & veto).sum()),
               catalogue=dict(min_dist_m=float((catd[dots] * 100).min()),
                              median_dist_m=float(np.median(catd[dots] * 100)),
                              within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100)),
               a_only_reasoning_csv=a_csv, a_only_rows=n_a, finished_utc=now())
    dl = ROOT / "docs/downloads"
    shutil.copy(out, dl / "h97-candidate.tif")
    with zipfile.ZipFile(dl / "h97-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, out.name)
    with zipfile.ZipFile(dl / "h97-candidate.zip") as z:
        assert z.namelist() == [out.name] and z.read(out.name) == out.read_bytes()
    res["download_staged"] = dict(tif="docs/downloads/h97-candidate.tif", zip="docs/downloads/h97-candidate.zip",
                                  tif_sha256=digest(dl / "h97-candidate.tif"),
                                  zip_sha256=digest(dl / "h97-candidate.zip"))
    write("build", res)
    log(json.dumps({k: res[k] for k in ("file", "bytes", "sha256", "name", "note")}, indent=1))
    log("validator: " + json.dumps(val, default=str))
    log("not_union: " + json.dumps(nu, default=float))
    log("uniqueness: " + json.dumps({k: uq[k] for k in uq if not isinstance(uq[k], (list, dict))}, default=str))


STAGES = dict(channels=stage_channels, orient=stage_orient, fit=stage_fit, independence=stage_independence,
              holdout=stage_holdout, build=stage_build, lane=stage_lane, write=stage_write)

if __name__ == "__main__":
    todo = sys.argv[1:] or ["all"]
    if todo == ["all"]:
        todo = list(STAGES)
    for s in todo:
        log(f"=== stage {s}")
        STAGES[s]()
