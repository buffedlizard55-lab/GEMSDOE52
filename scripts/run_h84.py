#!/usr/bin/env python3
"""H84 -- cover-conditioned co-training with surface-artefact demotion.

Lane (session brief, verbatim): co-training between a geophysical view (A: potential-field and
subsurface) and a surface view (B: DEM curvature/slope + radiometrics), with **disagreement as the
discovery signal**.  Where A is confident and B abstains the fault may be buried beneath cover;
where B is confident and A is silent, suspect a surface artefact.

Preregistered in ``knowledge/74_hypotheses_H84_preregistered.md`` and pinned by
``registry/h84_preregistration.json``.  This runner refuses to start if either hash has moved.

Shared tools are reused, never forked:
  run_h61.setup / sample_for_fit / learner_for / predict_flat / to_grid / pct_rank
  gems52.spatial.folds (label-blind quadrants) / negative_block_errors / independence /
      whole_pseudo_segments
  gems52.evaluate_holdout (gems52-pooled-hide-v1)   gems52.nodes.spacing_select
  gems52.gates (format/uniqueness/lane)             gems52.submission_writer

Stages (each checkpointed under work/h84 and evidence/h84_*.json):
    channels      cover / artefact / continuity conditioners + their empirical sign checks
    fit           leakage canary, then View A and View B per fold, predicted on the fold's region
    independence  the lane's mandated OOF negative-error correlation test
    exchange      one Blum-Mitchell donation round, B -> A only, kept only if 4/4 folds improve
    holdout       7 arms at a matched budget on hide-and-recover, pooled DTI + paired 95% CIs
    build         full-domain out-of-fold field, 200 m catalogue ring excluded, 88/12 placement
    lane          uniqueness + lane gates against the 526-raster census and the scored registry
    write         GeoTIFF (all-finite zeros), validator, not-the-union, A-only reasoning export
    card          one JSON run card assembled only from receipts on disk

Usage: python scripts/run_h84.py [channels|fit|independence|exchange|holdout|build|lane|write|card|all]
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
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer           # noqa: E402

PREREG = ROOT / "registry/h84_preregistration.json"
WORK = ROOT / "work/h84"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/downloads"
SAMPLE = ROOT / "data/sample_submission.tif"
PREFIX = "gems52-h84-"
REG = json.loads(PREREG.read_text())
TH = REG["thresholds"]
SEED = int(REG["seed"])
K_TOTAL = int(TH["budget_total_px"])
K_FOLD = int(TH["budget_per_fold_px"])
RING_M = float(TH["catalogue_exclusion_m"])
CONF, ABST = float(TH["confident_rank"]), float(TH["abstain_rank"])
ARMS = ("single_A", "single_B", "union_max", "B_art", "A_only_cover", "CCD", "random")
PRIMARY = "CCD"
RAD_GRAD = ("X_rad_K_grad3", "X_rad_Th_grad3", "X_rad_U_grad3",
            "X_rad_ThK_grad3", "X_rad_UK_grad3", "X_rad_UTh_grad3")


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h84_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


def save_verified(path: Path, v, tries: int = 6, pause: float = 0.4) -> str:
    """np.save + bit-exact read-back (H82 IR-H82-002: torn writes on this filesystem)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    want = np.ascontiguousarray(np.asarray(v))
    for attempt in range(1, tries + 1):
        np.save(path, want)
        try:
            back = np.asarray(np.load(path, mmap_mode="r"))
            same = back.shape == want.shape and back.dtype == want.dtype
            if same:
                # NaN is a legitimate value in these conditioner grids, so the comparison must
                # treat NaN as equal to NaN (np.array_equal defaults to NaN != NaN).
                same = (np.array_equal(back, want, equal_nan=True)
                        if np.issubdtype(want.dtype, np.floating) else np.array_equal(back, want))
            if same:
                return digest(path)
        except Exception:                                              # noqa: BLE001
            pass
        log(f"torn write on {path.name}; rewriting (attempt {attempt})")
        time.sleep(pause)
    raise RuntimeError(f"{path.name} would not persist bit-exactly")


def check_prereg() -> dict:
    if digest(ROOT / REG["hypothesis_document"]) != REG["hypothesis_sha256"]:
        raise SystemExit("H84 preregistration changed after freezing; re-pin registry/h84_preregistration.json")
    return REG


def setup():
    check_prereg()
    reg61, store, cat, eligible, folds, va, vb, _ring = base.setup()
    ring_px = RING_M / 100.0
    return store, cat, eligible, folds, va, vb, ring_px


def pct(v: np.ndarray) -> np.ndarray:
    return base.pct_rank(v)


# --------------------------------------------------------------------------------- stage: channels
def stage_channels():
    """Cover, continuity input, radiometric-edge and valley conditioners, from the cached stack."""
    store, cat, eligible, folds, va, vb, ring_px = setup()
    WORK.mkdir(parents=True, exist_ok=True)
    flat = store.flat_idx
    shape = eligible.shape

    def grid(name):
        return base.to_grid(flat, store.gather(flat, [name])[:, 0], shape)

    cover_raw = grid("raw_band_15")                      # depth to basement = cover thickness (m)
    curv_plus = grid("B_curvature_plus_3")               # most positive principal curvature
    curv_minus = grid("B_curvature_minus_3")
    det_elev = grid("raw_band_12")

    cover_rank = np.full(shape, np.nan, np.float32)
    cover_rank.ravel()[flat] = pct(cover_raw.ravel()[flat])
    valley = np.full(shape, np.nan, np.float32)
    valley.ravel()[flat] = (pct(curv_plus.ravel()[flat]) * pct((-det_elev).ravel()[flat])).astype(np.float32)

    rad = np.zeros(len(flat), np.float32)
    for nm in RAD_GRAD:
        rad = np.maximum(rad, pct(store.gather(flat, [nm])[:, 0]))
    rad_edge = np.full(shape, np.nan, np.float32)
    rad_edge.ravel()[flat] = rad
    artifact = np.full(shape, np.nan, np.float32)
    artifact.ravel()[flat] = np.clip(0.5 * (1.0 - rad) + 0.5 * valley.ravel()[flat], 0.0, 1.0)

    # Empirical sign checks -- the preregistration asserts a convention; these measure it.
    top_plus = curv_plus.ravel()[flat] >= np.quantile(curv_plus.ravel()[flat], 0.99)
    top_minus = curv_minus.ravel()[flat] <= np.quantile(curv_minus.ravel()[flat], 0.01)
    de = det_elev.ravel()[flat]
    checks = dict(
        convention="B_curvature_plus_3 large positive is expected at concave-up valley bottoms",
        mean_detrended_elev_top1pct_curv_plus_m=float(de[top_plus].mean()),
        mean_detrended_elev_top1pct_curv_minus_m=float(de[top_minus].mean()),
        mean_detrended_elev_all_m=float(de.mean()),
        valley_convention_consistent=bool(de[top_plus].mean() < de[top_minus].mean()),
        cover_m=dict(min=float(np.nanmin(cover_raw[eligible])), median=float(np.nanmedian(cover_raw[eligible])),
                     p90=float(np.nanquantile(cover_raw[eligible], 0.90)), max=float(np.nanmax(cover_raw[eligible]))),
        cover_median_threshold_m=float(np.nanmedian(cover_raw[eligible])),
        artifact=dict(mean=float(np.nanmean(artifact[eligible])), p05=float(np.nanquantile(artifact[eligible], 0.05)),
                      p95=float(np.nanquantile(artifact[eligible], 0.95))),
        radiometric_channels=list(RAD_GRAD))
    for nm, arr in (("cover_rank", cover_rank), ("artifact", artifact), ("rad_edge", rad_edge),
                    ("valley", valley), ("cover_raw", cover_raw)):
        save_verified(WORK / f"{nm}.npy", np.where(eligible, arr, np.nan).astype(np.float32))
    out = dict(stage="channels", started_utc=now(), eligible_px=int(eligible.sum()),
               store_version=store.manifest["version"], checks=checks,
               formula=("artifact = 0.5*(1-rad_edge) + 0.5*valley ; "
                        "valley = pct(B_curvature_plus_3)*pct(-raw_band_12) ; "
                        "rad_edge = max over six X_rad_*_grad3 percentile ranks"))
    write("channels", out)
    log("channels: " + json.dumps(checks, default=float)[:400])


# -------------------------------------------------------------------------------------- stage: fit
def region_rows(fold, eligible):
    return np.flatnonzero((fold["region"] & eligible).ravel())


def stage_fit():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    rng = np.random.default_rng(SEED)
    out = dict(stage="fit", started_utc=now(), seed=SEED, n_A=len(va), n_B=len(vb),
               view_A_features=va, view_B_features=vb, folds=[], canary=[])
    alarm = False
    cmax = 0.0
    for fold in folds:
        f = fold["fold"]
        rows, y, w = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + f))
        rec = dict(fold=f, n_train=int(len(rows)), n_pos=int(y.sum()),
                   region_px=int(fold["region"].sum()), truth_px=int(fold["truth"].sum()))
        rr = region_rows(fold, eligible)
        truth_flat = fold["truth"].ravel()[rr]
        # leakage canary: every learner channel alone, on the held-out region.  Stratified
        # subsample (all held-out positives + 200k negatives) so the canary costs seconds, not
        # minutes; the standard error of an AUC on 2e5 negatives is ~1e-3, far below the 0.90 bar.
        pos_i = np.flatnonzero(truth_flat)
        neg_i = np.flatnonzero(~truth_flat.astype(bool))
        rsub = np.random.default_rng(SEED + 900 + f)
        if len(neg_i) > 200_000:
            neg_i = rsub.choice(neg_i, 200_000, replace=False)
        sub = np.concatenate([pos_i, neg_i])
        ysub = truth_flat[sub].astype(np.int8)
        worst = ("", 0.0)
        for nm in list(va) + list(vb):
            v = store.gather(rr[sub], [nm])[:, 0]
            good = np.isfinite(v)
            a = roc_auc_score(ysub[good], v[good])
            a = max(a, 1.0 - a)                       # direction-insensitive
            if a > worst[1]:
                worst = (nm, float(a))
            del v
        out["canary"].append(dict(fold=f, max_channel=worst[0], max_auc=worst[1],
                                  n_pos=int(len(pos_i)), n_neg=int(len(neg_i)),
                                  sampling="all held-out positives + <=200k random negatives",
                                  alarm=bool(worst[1] > TH["canary_auc_alarm"])))
        alarm |= worst[1] > TH["canary_auc_alarm"]
        cmax = max(cmax, worst[1])
        log(f"fold {f}: canary max {worst[1]:.4f} ({worst[0]})")
        for view, names in (("A", va), ("B", vb)):
            t0 = time.time()
            model = base.learner_for(view, seed=SEED + f)
            X = store.gather(rows, names)
            model.fit(X, y, sample_weight=w)
            tf = time.time() - t0
            del X
            t0 = time.time()
            p = base.predict_flat(store, model, names, rr)
            save_verified(WORK / f"pred_single_{view}_f{f}.npy", p)
            save_verified(WORK / f"rows_f{f}.npy", rr)
            good = np.isfinite(p)
            auc = float(roc_auc_score(truth_flat[good], p[good]))
            rec[f"view_{view}"] = dict(fit_seconds=round(tf, 1), predict_seconds=round(time.time() - t0, 1),
                                       heldout_region_auc=auc, n_region_pos=int(truth_flat.sum()),
                                       n_region_neg=int((~truth_flat.astype(bool)).sum()))
            log(f"fold {f} view {view}: region AUC {auc:.4f} (fit {tf:.1f}s)")
            del p
        out["folds"].append(rec)
    out.update(canary_alarm_any=bool(alarm), canary_max_auc=cmax,
               mean_auc_A=float(np.mean([r["view_A"]["heldout_region_auc"] for r in out["folds"]])),
               mean_auc_B=float(np.mean([r["view_B"]["heldout_region_auc"] for r in out["folds"]])))
    write("fit", out)
    log(f"fit done: mean AUC A {out['mean_auc_A']:.4f} B {out['mean_auc_B']:.4f} canary {cmax:.4f}")


# ----------------------------------------------------------------------------- stage: independence
def load_pred(view, fold, eligible):
    f = fold["fold"]
    rr = np.load(WORK / f"rows_f{f}.npy")
    p = np.load(WORK / f"pred_single_{view}_f{f}.npy")
    return base.to_grid(rr, p, eligible.shape)


def stage_independence():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    rows, per_fold = [], []
    for fold in folds:
        f = fold["fold"]
        pa, pb = load_pred("A", fold, eligible), load_pred("B", fold, eligible)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        thr = (float(np.quantile(pa[neg], th["donor_rank_min"])), float(np.quantile(pb[neg], th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        rows += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr), n_blocks=len(blocks)))
        log(f"fold {f}: {len(blocks)} independence blocks over {int(neg.sum())} proxy negatives")
        del pa, pb, neg
    res = spatial.independence(rows, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    out = dict(stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
               thresholds_inherited_from=str(src.relative_to(ROOT)), thresholds_inherited_sha256=digest(src),
               thresholds=dict(block_side_px=th["block_side_px"], donor_rank_min=th["donor_rank_min"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"], min_blocks=20,
                               negative_ring_px=4),
               per_fold=per_fold,
               result={k: v for k, v in res.items() if k != "blocks"},
               n_blocks=len(rows),
               caveat=("proxy negatives are catalogue-zero pixels, which is not verified fault absence; "
                       "a weak error correlation is not proof of conditional feature independence"))
    write("independence", out)
    log("independence: max|rho| %s allow_exchange %s over %d blocks"
        % (res["max_abs_correlation"], res["allow_exchange"], len(rows)))


# --------------------------------------------------------------------------------- stage: exchange
def stage_exchange():
    """One Blum-Mitchell donation round, B -> A only, inside the fold's buffered training domain."""
    store, cat, eligible, folds, va, vb, ring_px = setup()
    ind = json.loads((EVID / "h84_independence.json").read_text())
    allow = bool(ind["result"]["allow_exchange"])
    out = dict(stage="exchange", started_utc=now(), allow_exchange=allow, folds=[],
               rule=f"keep the refit View A only if out-of-quadrant AUC improves in "
                    f"{TH['donation_fold_improvement_required']}/4 folds")
    if not allow:
        out["skipped"] = "independence instrument disallowed exchange"
        write("exchange", out)
        return
    fit = json.loads((EVID / "h84_fit.json").read_text())
    improved = 0
    for fold in folds:
        f = fold["fold"]
        # IR-H84-001: the fit stage predicts on each fold's evaluation region only, so the
        # checkpointed grids are NaN across the buffered TRAINING domain -- which is precisely
        # where a pseudo-label is allowed to come from.  The donor/receiver fields for the
        # donation step are therefore re-derived on the training domain here, from models refit
        # bit-identically (same seed, same sample, deterministic learner) to the fit stage.
        tr_rows = np.flatnonzero((fold["train"] & eligible).ravel())
        rows0, y0, w0 = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + f))
        pa = np.full(eligible.shape, np.nan, np.float32)
        pb = np.full(eligible.shape, np.nan, np.float32)
        for view, names, dest in (("A", va, pa), ("B", vb, pb)):
            m = base.learner_for(view, seed=SEED + f)
            m.fit(store.gather(rows0, names), y0, sample_weight=w0)
            dest.ravel()[tr_rows] = base.predict_flat(store, m, names, tr_rows)
            del m
        # donor/receiver fields over the training domain; only that domain may donate
        fin = np.isfinite(pa) & np.isfinite(pb)
        qa, qb = pa[fin], pb[fin]
        donor_thr = float(np.quantile(qb, CONF))
        recv_lo, recv_hi = float(np.nanmin(qa)), float(np.quantile(qa, ABST))
        forbidden = cat | ~eligible
        idx, receipts = spatial.whole_pseudo_segments(
            np.nan_to_num(pb, nan=-1.0), np.nan_to_num(pa, nan=-1.0), fold["train"], forbidden,
            donor_thr, recv_lo, recv_hi, side=50, min_pixels=5, cap=2000)
        rows, y, w = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + f))
        rec = dict(fold=f, donated_px=int(len(idx)), donated_components=len(receipts),
                   donor_threshold=donor_thr, receiver_band=[recv_lo, recv_hi])
        if len(idx):
            rows2 = np.concatenate([rows, idx])
            y2 = np.concatenate([y, np.ones(len(idx), np.int8)])
            w2 = np.concatenate([np.ones(len(rows), np.float64), np.full(len(idx), 0.5)])
        else:
            rows2, y2, w2 = rows, y, None
        model = base.learner_for("A", seed=SEED + 100 + f)
        model.fit(store.gather(rows2, va), y2, sample_weight=w2)
        rr = np.load(WORK / f"rows_f{f}.npy")
        p = base.predict_flat(store, model, va, rr)
        save_verified(WORK / f"pred_post_A_f{f}.npy", p)
        truth_flat = fold["truth"].ravel()[rr]
        good = np.isfinite(p)
        auc_post = float(roc_auc_score(truth_flat[good], p[good]))
        auc_pre = float(fit["folds"][f]["view_A"]["heldout_region_auc"])
        rec.update(auc_pre=auc_pre, auc_post=auc_post, improved=bool(auc_post > auc_pre))
        improved += int(auc_post > auc_pre)
        log(f"fold {f}: donation {len(idx)} px -> A AUC {auc_pre:.4f} -> {auc_post:.4f}")
        out["folds"].append(rec)
        del pa, pb, p
    out.update(folds_improved=improved,
               keep_post_exchange=bool(improved >= int(TH["donation_fold_improvement_required"])),
               decision=("post-exchange View A adopted" if improved >= int(TH["donation_fold_improvement_required"])
                         else "pre-exchange View A retained (frozen rule: improvement required in 4/4 folds)"))
    write("exchange", out)
    log("exchange: " + out["decision"])


# ---------------------------------------------------------------------------------- stage: holdout
def allowed_of(fold, eligible, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & eligible & ~fold["visible"] & (vd > ring_px)


def fold_fields(fold, eligible, ring_px, post_A: bool):
    """Per-fold rank fields and the pre-registered disagreement masks over the allowed set."""
    f = fold["fold"]
    rr = np.load(WORK / f"rows_f{f}.npy")
    pa_name = f"pred_post_A_f{f}.npy" if post_A and (WORK / f"pred_post_A_f{f}.npy").exists() else f"pred_single_A_f{f}.npy"
    pa = np.load(WORK / pa_name)
    pb = np.load(WORK / f"pred_single_B_f{f}.npy")
    allowed = allowed_of(fold, eligible, ring_px)
    ai = np.flatnonzero(allowed.ravel())
    ga = base.to_grid(rr, pa, eligible.shape)
    gb = base.to_grid(rr, pb, eligible.shape)
    rA = np.full(eligible.shape, -1.0, np.float32)
    rB = np.full(eligible.shape, -1.0, np.float32)
    rA.ravel()[ai] = np.nan_to_num(pct(ga.ravel()[ai]), nan=-1.0)
    rB.ravel()[ai] = np.nan_to_num(pct(gb.ravel()[ai]), nan=-1.0)
    del ga, gb
    cover = np.load(WORK / "cover_rank.npy")
    artifact = np.load(WORK / "artifact.npy")
    A_conf, A_abst = (rA >= CONF) & allowed, (rA < ABST) & allowed
    B_conf, B_abst = (rB >= CONF) & allowed, (rB < ABST) & allowed
    m32 = A_conf.astype(np.float32)
    neigh = ndi.uniform_filter(m32, 5, mode="constant", cval=0.0) * 25.0 - m32   # 24 neighbours, centre excluded
    cont = neigh >= float(TH["continuity_neighbours_5x5_min"]) - 1e-6
    disc = A_conf & B_abst & (np.nan_to_num(cover, nan=0.0) >= TH["cover_rank_min"]) & cont
    B_art = np.where(allowed, rB - float(TH["artifact_demotion_weight"]) * np.nan_to_num(artifact, nan=0.0)
                     * (B_conf & A_abst), -1.0).astype(np.float32)
    return dict(allowed=allowed, rA=rA, rB=rB, B_art=B_art, disc=disc,
                union=np.where(allowed, np.maximum(rA, rB), -1.0).astype(np.float32))


def place_ccd(ff, k_total, seed=0):
    """88 % artefact-demoted B dots, then 12 % reserved cover-gated A-only discovery dots."""
    share = float(TH["discovery_budget_share"])
    k2 = int(round(k_total * share))
    k1 = k_total - k2
    d1 = nodes.spacing_select(ff["B_art"], ff["allowed"], k1, min_px=TH["min_separation_px"])
    halo = ndi.binary_dilation(d1, structure=np.ones((7, 7), bool))
    pool2 = ff["allowed"] & ff["disc"] & ~halo
    fld2 = np.where(pool2, ff["rA"], -1.0).astype(np.float32)
    d2 = nodes.spacing_select(fld2, pool2, k2, min_px=TH["min_separation_px"])
    return d1 | d2, dict(requested_b=k1, placed_b=int(d1.sum()), requested_discovery=k2,
                         placed_discovery=int(d2.sum()), discovery_pool_px=int(pool2.sum()),
                         shortfall_discovery=int(k2 - d2.sum()))


def stage_holdout():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    ex = json.loads((EVID / "h84_exchange.json").read_text()) if (EVID / "h84_exchange.json").exists() else {}
    post_A = bool(ex.get("keep_post_exchange", False))
    terms = {a: None for a in ARMS}
    out = dict(stage="holdout", started_utc=now(), evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               post_exchange_A_used=post_A, implementation_hashes=evaluator.implementation_hashes(),
               withheld_positive_px=int(sum(int(f["truth"].sum()) for f in folds)), folds=[])
    for fold in folds:
        f = fold["fold"]
        ff = fold_fields(fold, eligible, ring_px, post_A)
        rec = dict(fold=f, allowed_px=int(ff["allowed"].sum()), truth_px=int(fold["truth"].sum()),
                   discovery_pool_px=int((ff["disc"] & ff["allowed"]).sum()), arms={})
        for arm in ARMS:
            if arm == "random":
                ai = np.flatnonzero(ff["allowed"].ravel())
                fld = np.full(eligible.shape, -1.0, np.float32)
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
                em = nodes.spacing_select(fld, ff["allowed"], K_FOLD, min_px=TH["min_separation_px"])
                info = {}
            elif arm == "CCD":
                em, info = place_ccd(ff, K_FOLD)
            elif arm == "A_only_cover":
                pool = ff["allowed"] & ff["disc"]
                em = nodes.spacing_select(np.where(pool, ff["rA"], -1.0).astype(np.float32), pool,
                                          K_FOLD, min_px=TH["min_separation_px"])
                info = dict(pool_px=int(pool.sum()))
            else:
                fld = {"single_A": ff["rA"], "single_B": ff["rB"], "union_max": ff["union"],
                       "B_art": ff["B_art"]}[arm]
                em = nodes.spacing_select(fld, ff["allowed"], K_FOLD, min_px=TH["min_separation_px"])
                info = {}
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()), filled=bool(int(em.sum()) == K_FOLD), **info)
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del em
        out["folds"].append(rec)
        del ff
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    pd = out["pooled"]["paired_differences"]
    out["paired_differences_keyed_by"] = "comparison arm; each entry is candidate minus that arm"
    out["primary_paired"] = {f"{PRIMARY}_minus_{k}": v for k, v in pd.items()}
    sb = out["pooled"]["scores"]["single_B"]["dti"]
    cc = out["pooled"]["scores"][PRIMARY]["dti"]
    delta = pd["single_B"]
    out["promotion_test"] = dict(
        rule=("non-inferiority to single_B: point estimate >= single_B - %.3f AND paired 95%% CI lower "
              "bound > %.3f (frozen, knowledge/74 sec.4.4)" % (TH["noninferiority_margin_dti"],
                                                               TH["noninferiority_ci_lower_bound"])),
        single_B=sb, primary=cc, delta=delta["delta"], delta_ci95=delta["ci95"],
        point_ok=bool(cc >= sb - TH["noninferiority_margin_dti"]),
        ci_ok=bool(delta["ci95"][0] > TH["noninferiority_ci_lower_bound"]),
        superiority=bool(delta["ci95"][0] > 0.0))
    out["promotion_test"]["noninferior"] = bool(out["promotion_test"]["point_ok"] and out["promotion_test"]["ci_ok"])
    write("holdout", out)
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in ARMS}))
    log("promotion test: " + json.dumps(out["promotion_test"], default=float))


# ------------------------------------------------------------------------------------ stage: build
def stitch_fields(folds, eligible, ring_px, post_A):
    """Out-of-fold rank fields over the whole domain: each pixel scored by the model that did not see it."""
    shape = eligible.shape
    acc = {k: np.full(shape, np.nan, np.float32) for k in ("rA", "rB", "B_art", "union")}
    disc = np.zeros(shape, bool)
    cover_px = {}
    for fold in folds:
        ff = fold_fields(fold, eligible, ring_px, post_A)
        m = ff["allowed"] & ~np.isfinite(acc["rA"])
        for k in acc:
            acc[k][m] = ff[k][m]
        disc |= ff["disc"] & m
        cover_px[fold["fold"]] = int((ff["disc"] & m).sum())
        del ff
    return acc, disc, cover_px


def stage_build():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    ex = json.loads((EVID / "h84_exchange.json").read_text()) if (EVID / "h84_exchange.json").exists() else {}
    post_A = bool(ex.get("keep_post_exchange", False))
    acc, disc, cover_px = stitch_fields(folds, eligible, ring_px, post_A)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(acc["B_art"]) & (catd * 100.0 > RING_M)
    ff = dict(allowed=pool, rA=np.where(pool, np.nan_to_num(acc["rA"], nan=-1.0), -1.0).astype(np.float32),
              rB=np.where(pool, np.nan_to_num(acc["rB"], nan=-1.0), -1.0).astype(np.float32),
              B_art=np.where(pool, np.nan_to_num(acc["B_art"], nan=-1.0), -1.0).astype(np.float32),
              disc=disc & pool,
              union=np.where(pool, np.nan_to_num(acc["union"], nan=-1.0), -1.0).astype(np.float32))
    dots, info = place_ccd(ff, K_TOTAL)
    union_dots = nodes.spacing_select(ff["union"], pool, K_TOTAL, min_px=TH["min_separation_px"])
    a_dots = nodes.spacing_select(ff["rA"], pool, K_TOTAL, min_px=TH["min_separation_px"])
    b_dots = nodes.spacing_select(ff["rB"], pool, K_TOTAL, min_px=TH["min_separation_px"])
    discovery = dots & ff["disc"]
    save_verified(WORK / "dots.npy", dots)
    save_verified(WORK / "discovery_dots.npy", discovery)
    save_verified(WORK / "union_dots.npy", union_dots)
    save_verified(WORK / "a_dots.npy", a_dots)
    save_verified(WORK / "b_dots.npy", b_dots)
    # a [0,1] surface for the lane's rank-correlation phase
    surf = np.where(pool, np.clip(np.nan_to_num(acc["B_art"], nan=0.0), 0.0, 1.0), 0.0).astype(np.float32)
    save_verified(WORK / "surface.npy", surf)
    for k in ("rA", "rB", "B_art"):
        save_verified(WORK / f"field_{k}.npy", acc[k])
    sp = nodes.spacing_stats(dots)
    rec = dict(stage="build", started_utc=now(), placement=info, dots=int(dots.sum()),
               discovery_dots=int(discovery.sum()), pool_px=int(pool.sum()),
               eligible_px=int(eligible.sum()), post_exchange_A_used=post_A,
               discovery_pool_px=int(ff["disc"].sum()), discovery_pool_by_fold=cover_px,
               ring_excluded_m=RING_M, min_cat_dist_m=float((catd[dots] * 100).min()),
               median_cat_dist_m=float(np.median(catd[dots] * 100)),
               within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100),
               spacing=sp, union_dots=int(union_dots.sum()), a_dots=int(a_dots.sum()), b_dots=int(b_dots.sum()))
    write("build", rec)
    log("build: " + json.dumps({k: rec[k] for k in ("dots", "discovery_dots", "min_cat_dist_m",
                                                    "median_cat_dist_m", "within_300m_pct")}, default=float))


# ------------------------------------------------------------------------------------- stage: lane
def census_paths():
    from build_h61_submission import prior_paths
    full, meta = prior_paths(WORK / "prior_fetch_receipt.json", ("submission",))
    full = [p for p in full if p.exists() and PREFIX not in p.name]
    return full, meta


def scored_registry():
    paths = sorted((ROOT / "data/scored").glob("*.tif")) + sorted((ROOT / "data/reference").glob("*.tif"))
    return [p for p in paths if p.exists()], json.loads((ROOT / "registry/h82_scored_registry.json").read_text())


def stage_lane():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    dots = np.load(WORK / "dots.npy").astype(np.float32)
    surf = np.load(WORK / "surface.npy")
    full, meta = census_paths()
    restr, scored = scored_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full), n_restricted=len(restr),
               scored_registry_rule=scored["membership_rule"],
               doctrine=("both registries are reported verbatim; a restricted-registry PASS never waives a "
                         "literal full-census DUPLICATE/STOP"))
    log(f"lane: full census {len(full)} rasters, scored-only {len(restr)}")
    cache: dict = {}
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface",
                                            log=log, coverage_cache=cache)
    out["full_dots"] = gates.lane_report(dots, eligible, full, sample=SAMPLE, phase="dots",
                                         log=log, coverage_cache=cache)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface",
                                                  coverage_cache=cache)
    out["restricted_dots"] = gates.lane_report(dots, eligible, restr, sample=SAMPLE, phase="dots",
                                               coverage_cache=cache)
    out["uniqueness_full"] = {k: v for k, v in gates.uniqueness_report(dots, full).items() if k != "per_prior"}
    for k in ("full_surface", "full_dots", "restricted_surface", "restricted_dots"):
        r = out[k]
        out[k] = {kk: vv for kk, vv in r.items() if kk != "per_prior"}
        log(f"{k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, "
            f"near {r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']} "
            f"(near {r['policy']['max_near_3px_fraction']}, informative {r['policy']['informative_priors']})")
    write("lane", out)


# ------------------------------------------------------------------------------------ stage: write
def write_reasoning(store, dots, discovery, catd, eligible, name):
    """Per-candidate reviewer record for every A-only discovery dot (Phase 2 requirement)."""
    ys, xs = np.nonzero(discovery)
    flat = (ys * eligible.shape[1] + xs).astype(np.int64)
    cols = {nm: store.gather(flat, [nm])[:, 0] for nm in
            ("raw_band_15", "raw_band_18", "raw_band_02", "raw_band_12", "raw_band_19", "raw_band_13")}
    rad = np.load(WORK / "rad_edge.npy")
    cover_rank = np.load(WORK / "cover_rank.npy")
    rA, rB = np.load(WORK / "field_rA.npy"), np.load(WORK / "field_rB.npy")
    with rasterio.open(SAMPLE) as ref:
        T = ref.transform
    path = DOCS / "h84-a-only-reasoning.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh, lineterminator="\r\n")
        wtr.writerow(["row", "col", "utm11n_easting_m", "utm11n_northing_m", "rank_view_A", "rank_view_B",
                      "depth_to_basement_m", "isostatic_gravity_hgrad", "rtp_magnetics_nT",
                      "isostatic_gravity_anomaly_mGal", "detrended_elev_m", "detrended_slope",
                      "radiometric_edge_rank", "cover_rank", "distance_to_catalogue_m",
                      "geological_reasoning", "named_non_fault_mimic", "falsifier"])
        for i in range(len(ys)):
            y, x = int(ys[i]), int(xs[i])
            e, n = T * (x + 0.5, y + 0.5)
            wtr.writerow([y, x, round(float(e), 1), round(float(n), 1),
                          round(float(rA[y, x]), 4), round(float(rB[y, x]), 4),
                          round(float(cols["raw_band_15"][i]), 1), round(float(cols["raw_band_18"][i]), 4),
                          round(float(cols["raw_band_02"][i]), 2), round(float(cols["raw_band_13"][i]), 3),
                          round(float(cols["raw_band_12"][i]), 1), round(float(cols["raw_band_19"][i]), 3),
                          round(float(rad[y, x]), 4), round(float(cover_rank[y, x]), 4),
                          round(float(catd[y, x] * 100.0), 1),
                          ("Continuous potential-field edge (gravity horizontal gradient and/or RTP step) "
                           "under %d m of modelled sedimentary cover, with no surface expression: View B "
                           "abstains at rank %.2f. Interpreted as a basement-cutting normal fault whose "
                           "hanging-wall basin has been filled, so no scarp survives at the 100 m cell."
                           % (round(float(cols["raw_band_15"][i])), float(rB[y, x]))),
                          "buried lithological contact or basin-margin palaeochannel (same edge, no offset)",
                          ("falsified if a depth-slice of the airborne magnetics or a seismic/gravity "
                           "forward model shows a conformable contact with no vertical offset of the "
                           "basement surface across the edge")])
    return dict(path=str(path.relative_to(ROOT)), rows=int(len(ys)), sha256=digest(path),
                encoding="utf-8", line_terminator="CRLF (RFC 4180)")


def stage_write():
    store, cat, eligible, folds, va, vb, ring_px = setup()
    dots = np.load(WORK / "dots.npy")
    discovery = np.load(WORK / "discovery_dots.npy")
    union_dots = np.load(WORK / "union_dots.npy")
    a_dots, b_dots = np.load(WORK / "a_dots.npy"), np.load(WORK / "b_dots.npy")
    hold = json.loads((EVID / "h84_holdout.json").read_text())
    pred = dots.astype(np.float32)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h84-coverco-disagree-{int(dots.sum())}px-{stamp}"
    note = ("H84 cover-conditioned co-training: artefact-demoted View B + 12% reserved A-only "
            "sub-cover dots; 200m catalogue ring excluded; binary")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    rec = submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                             metadata=dict(round="H84", primary_arm=PRIMARY,
                                                           preregistration=str(PREREG.relative_to(ROOT))))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(bands=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=str(a.crs) == str(s.crs), shape_match=a.shape == s.shape,
                   transform_match=tuple(a.transform)[:6] == tuple(s.transform)[:6],
                   bounds_match=tuple(round(x, 6) for x in a.bounds) == tuple(round(x, 6) for x in s.bounds),
                   nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   unique_values=sorted(float(x) for x in np.unique(v[np.isfinite(v)])[:10]),
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()),
                   nan_inside_footprint=int((np.isnan(v) & eligible).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["bands"] == 1 and val["dtype"] == "float32" and val["crs_match"] and val["shape_match"]
                       and val["transform_match"] and val["bounds_match"] and val["range_ok"]
                       and val["unique_values"] == [0.0, 1.0])
    val["rule_source"] = ("official submission format: single-band float32 GeoTIFF, EPSG:32611, 100 m, same "
                          "bounds/shape/geotransform as the submission format, values in [0,1] -- "
                          "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/")

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    not_union = dict(
        dots=int(dots.sum()), discovery_dots=int(discovery.sum()),
        equal_union=bool(np.array_equal(dots, union_dots)),
        subset_of_union=bool(int((dots & ~union_dots).sum()) == 0),
        equal_single_A=bool(np.array_equal(dots, a_dots)), equal_single_B=bool(np.array_equal(dots, b_dots)),
        shared_with_union=int((dots & union_dots).sum()), jaccard_union=jac(dots, union_dots),
        shared_with_A=int((dots & a_dots).sum()), jaccard_A=jac(dots, a_dots),
        shared_with_B=int((dots & b_dots).sum()), jaccard_B=jac(dots, b_dots))
    not_union["PASS"] = bool(not not_union["equal_union"] and not not_union["subset_of_union"]
                             and not not_union["equal_single_A"] and not not_union["equal_single_B"])
    catd = ndi.distance_transform_edt(~cat)
    cmp = {}
    for key, p in (("ref_h33_2_b2_owner_reported_0.2778", "data/reference/h33-2-b2-zeros.tif"),
                   ("h83_same_repo_previous_round", "docs/downloads/h83-candidate.tif"),
                   ("h82_same_repo_previous_round", "docs/downloads/h82-candidate.tif")):
        pp = ROOT / p
        if not pp.exists():
            continue
        with rasterio.open(pp) as d:
            r = np.nan_to_num(d.read(1)) > 0
        near = ndi.binary_dilation(r, structure=np.ones((7, 7), bool))
        cmp[key] = dict(prior_px=int(r.sum()), shared_px=int((r & dots).sum()),
                        near_3px_share_of_my_dots=float(near[dots].mean()), jaccard=jac(dots, r))
    reasoning = write_reasoning(store, dots, discovery, catd, eligible, name)
    res = dict(stage="write", started_utc=now(), file=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
               sha256=digest(out), submission_name=name, note=note, note_chars=len(note),
               validator=val, writer_receipt=rec, not_the_union=not_union, vs_named_priors=cmp,
               catalogue=dict(min_dist_m=float((catd[dots] * 100).min()),
                              median_dist_m=float(np.median(catd[dots] * 100)),
                              within_200m_px=int((catd[dots] * 100 <= 200).sum()),
                              within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100)),
               reasoning_csv=reasoning,
               holdout_promotion_test=hold["promotion_test"])
    DOCS.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, DOCS / "h84-candidate.tif")
    with zipfile.ZipFile(DOCS / "h84-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, out.name)
    with zipfile.ZipFile(DOCS / "h84-candidate.zip") as z:
        assert z.namelist() == [out.name] and z.read(out.name) == out.read_bytes()
    res["download_staged"] = dict(tif="docs/downloads/h84-candidate.tif", zip="docs/downloads/h84-candidate.zip",
                                  tif_sha256=digest(DOCS / "h84-candidate.tif"),
                                  zip_sha256=digest(DOCS / "h84-candidate.zip"))
    write("write", res)
    log("validator PASS=%s ones=%d nan=%d; not-the-union PASS=%s" %
        (val["PASS"], val["ones"], val["nan"], not_union["PASS"]))
    log(f"file {res['file']} sha256 {res['sha256'][:16]}... {res['bytes']} bytes")


# ------------------------------------------------------------------------------------- stage: card
def stage_card():
    ch = json.loads((EVID / "h84_channels.json").read_text())
    fit = json.loads((EVID / "h84_fit.json").read_text())
    ind = json.loads((EVID / "h84_independence.json").read_text())
    exg = json.loads((EVID / "h84_exchange.json").read_text())
    hold = json.loads((EVID / "h84_holdout.json").read_text())
    build = json.loads((EVID / "h84_build.json").read_text())
    lane = json.loads((EVID / "h84_lane.json").read_text())
    wr = json.loads((EVID / "h84_write.json").read_text())
    pt = hold["promotion_test"]
    gates_pass = dict(
        format=bool(wr["validator"]["PASS"]),
        uniqueness_not_identical=bool(not lane["uniqueness_full"].get("identical_to_any", False)),
        lane_surface_rank=bool((lane["full_surface"]["literal"]["max_spearman"] or 0) <= TH["lane_rank_limit"]),
        lane_dots_policy=bool(lane["full_dots"]["policy"]["verdict"] == "PASS"),
        not_the_union=bool(wr["not_the_union"]["PASS"]),
        holdout_noninferior=bool(pt["noninferior"]))
    submit_ok = all(gates_pass.values())
    verdict = "promote" if submit_ok else "negative"
    xs = {}
    xp = EVID / "h84_lane_excess.json"
    if xp.exists():
        x = json.loads(xp.read_text())
        xs = {k: v for k, v in x.items() if k != "per_prior"}
    card = dict(
        round="H84", generated_utc=now(), preregistration=str(PREREG.relative_to(ROOT)),
        preregistration_sha256=REG["hypothesis_sha256"],
        hypothesis=("Faults missing from the USGS/INGENIOUS catalogue are preferentially buried: a "
                    "continuous potential-field edge under above-median sedimentary cover where the surface "
                    "view abstains is a fault candidate, and a surface-confident pixel without a radiometric "
                    "edge is a non-tectonic lineament."),
        mechanism=("Two-view co-training (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962). View A = "
                   "potential-field/subsurface channels, View B = DEM + radiometric channels. One B->A "
                   "donation round on whole confident-disagreement segments inside the buffered training "
                   "domain. Emission = 88% artefact-demoted View B + 12% reserved cover-gated A-only "
                   "discovery dots, 3 px spacing, 200 m catalogue ring excluded, binary {0,1}."),
        named_non_fault_process=("buried lithological contact or basin-margin palaeochannel for the A-only "
                                 "dots; drainage incision or graded road for the demoted B-only pixels"),
        holdout=dict(evaluator=hold["evaluator"], withheld_positive_pixels=hold["withheld_positive_px"],
                     budget_per_fold=hold["budget_per_fold"],
                     scores={a: dict(dti=hold["pooled"]["scores"][a]["dti"],
                                     ci95=hold["pooled"]["scores"][a]["ci95"]) for a in ARMS},
                     primary_minus_single_B=dict(delta=pt["delta"], ci95=pt["delta_ci95"]),
                     evidence_class="HOLDOUT-DTI (not a leaderboard score and not a projection)"),
        leakage_canary=dict(max_single_channel_auc=fit["canary_max_auc"], bar=TH["canary_auc_alarm"],
                            alarm=fit["canary_alarm_any"]),
        view_independence=dict(max_abs_rho=ind["result"]["max_abs_correlation"],
                               bar=ind["thresholds"]["abandon_max_abs_rho"],
                               blocks=ind["n_blocks"], allow_exchange=ind["result"]["allow_exchange"]),
        donation=dict(folds_improved=exg.get("folds_improved"), decision=exg.get("decision"),
                      donated_px=[f["donated_px"] for f in exg.get("folds", [])]),
        correlation_overlap_vs_registry=dict(
            census_rasters=lane["n_full"], scored_rasters=lane["n_restricted"],
            surface_max_spearman_literal=lane["full_surface"]["literal"]["max_spearman"],
            dots_max_near_3px_literal=lane["full_dots"]["literal"]["max_near_3px_fraction"],
            dots_literal_verdict=lane["full_dots"]["literal"]["verdict"],
            dots_policy_verdict=lane["full_dots"]["policy"]["verdict"],
            dots_max_near_3px_policy=lane["full_dots"]["policy"]["max_near_3px_fraction"],
            identical_to_any_prior=lane["uniqueness_full"].get("identical_to_any")),
        raster_sha256=wr["sha256"], raster_bytes=wr["bytes"], raster_file=wr["file"],
        validator=wr["validator"], not_the_union=wr["not_the_union"],
        placement=dict(build["placement"], dots=build["dots"], discovery_dots=build["discovery_dots"],
                       min_cat_dist_m=build["min_cat_dist_m"], median_cat_dist_m=build["median_cat_dist_m"],
                       within_300m_pct=build["within_300m_pct"], spacing=build["spacing"]),
        channels_sign_check=ch["checks"],
        submission_name=wr["submission_name"], submission_note=wr["note"], note_chars=wr["note_chars"],
        gates=gates_pass, verdict=verdict,
        lane_excess_chance_corrected=xs,
        download="YES" if gates_pass["format"] else "NO",
        portal_format_valid=bool(wr["validator"]["PASS"]),
        auto_promoted_by_frozen_rule=bool(submit_ok),
        failed_gates=[k for k, v in gates_pass.items() if not v],
        submit=("YES" if submit_ok else
                "NO - not auto-promoted: " + ", ".join(k for k, v in gates_pass.items() if not v)),
        slots_used=0, experiments_used=3, experiments_budget=REG["experiments_budget"],
        caveats=[
            "HOLDOUT-DTI is measured on withheld CATALOGUE segments; the competition scores faults the "
            "catalogue lacks. Spearman(holdout, public board) measured at -0.10 in this repository.",
            "Prior scores quoted anywhere in this repository are OWNER-REPORTED filename attributions, "
            "never ORGANIZER-CONFIRMED.",
            "Local format validation is not organiser upload acceptance.",
            "Competition rasters are integrity-pinned mirrors, not organizer-authenticated downloads."])
    (EVID / "h84_run_card.json").write_text(json.dumps(card, indent=1, default=float) + "\n")
    print(json.dumps(card, indent=1, default=float))
    return card


STAGES = dict(channels=stage_channels, fit=stage_fit, independence=stage_independence,
              exchange=stage_exchange, holdout=stage_holdout, build=stage_build, lane=stage_lane,
              write=stage_write, card=stage_card)


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    order = list(STAGES) if what == "all" else [w for w in what.split(",")]
    for w in order:
        if w not in STAGES:
            raise SystemExit(f"unknown stage {w}; choose from {', '.join(STAGES)} or all")
    t0 = time.time()
    for w in order:
        log(f"=== stage {w} ===")
        STAGES[w]()
    log(f"done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
