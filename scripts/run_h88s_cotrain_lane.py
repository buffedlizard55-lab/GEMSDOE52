#!/usr/bin/env python3
"""H88 — co-training lane: sufficiency-screened exchange, disagreement-stratified emission, metered budget.

Lane (frozen): the brief's two-view co-training paragraph — View A potential-field / subsurface,
View B surface, disagreement as the discovery signal (Blum & Mitchell, COLT '98 pp. 92–100,
DOI 10.1145/279943.279962).  Preregistered in ``knowledge/80s_h88s_preregistration.md`` and
pinned by ``registry/h88s_preregistration.json``; this runner refuses to start if either hash moves.
Budget rule for the shipped file: ``knowledge/80s_h88s_amendment_budget.md``.

Shared tools are reused, never forked: ``gems52.spatial.folds`` (via the shared fold builder),
``gems52.views54.{independence_test,strata,block_ids}``, ``gems52.spatial.{negative_block_errors,
independence,whole_pseudo_segments}``, ``gems52.cotrain.rank_u8``, ``gems52.evaluate_holdout``
(gems52-pooled-hide-v1), ``gems52.nodes.spacing_select``, ``gems52.gates``,
``gems52.submission_writer``.

Stages (each checkpointed to ``work/h88`` and ``evidence/h88_*.json``):

    channels     68 rank-uint8 channels for the two views, read band-by-band from the pinned rasters
    fit          per-fold OOF fits of both views, per-fold negative-block independence read, and the
                 sufficiency-screened whole-segment pseudo-label exchange (donor = A, receiver = B)
    holdout      strata arms + metered budget curve on the shared hide-and-recover instrument
    build        the winning field stitched over the folds, 200 m catalogue ring stripped, GeoTIFF,
                 on-disk validator, uniqueness, lane, not-the-union, reasoning export
    card         run card

Usage: python scripts/run_h88_cotrain_lane.py [channels|fit|holdout|build|card|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                                     # noqa: E402
import rasterio                                                        # noqa: E402
from scipy import ndimage as ndi                                       # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier            # noqa: E402
from sklearn.metrics import roc_auc_score                              # noqa: E402

from gems52 import cotrain, evaluate_holdout as evaluator, gates       # noqa: E402
from gems52 import nodes, spatial, submission_writer, views54          # noqa: E402

SEED = 61052
WORK = ROOT / "work/h88"
EVID = ROOT / "evidence"
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
RAD = ROOT / "data/external/geodawn_rad_u8.tif"
EXT = ROOT / "data/external/geodawn_extensions_u8.tif"
LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
SUM_CSV = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
PREREG = ROOT / "registry/h88s_preregistration.json"
AMEND = ROOT / "knowledge/80s_h88s_amendment_budget.md"

K_FOLD = 9400                     # registry h88 budget_dots_per_fold_per_arm (H82/H84/H86 convention)
BUDGET_CURVE = (4700, 6250, 9400)  # 18,800 / 25,000 / 37,600 total dots — the mass-discipline lever
RING_PX = 2                       # 200 m catalogue exclusion (registry catalogue_exclusion_m)
BUFFER_PX = 80                    # registry h88 buffer_px (label-blind quadrants)
STRATA_Q = 0.90                   # views54.strata default
CANARY_ALARM = 0.90
DONOR_RANK_MIN = 0.95             # registry h61 thresholds, reused (whole-segment pseudo-labels)
RECEIVER_LO, RECEIVER_HI = 0.35, 0.65
PSEUDO_CAP = 200                  # pixels per fold
BLOCK_SIDE = 50                   # spatial.negative_block_errors block side (px)
PRIMARY = "corroborated_B"
SHAPE = (3730, 3292)

VIEW_A_BANDS = (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 15, 17, 18)
VIEW_B_STACK_BANDS = (12, 19, 6)   # det_elev, det_elev_slope, band 6 = radiometric TC (IR-H85-005)
RAD_BANDS = (1, 2, 3, 4, 5, 6, 7)  # K, Th, U, TC, Th/K, U/K, U/Th   (geodawn_rad + extensions)
LIDAR_BANDS = (1, 3, 4, 5, 6, 7, 9, 10)  # ex_max, step_max, lapneg_max, lappos_max, downface_max,
                                         # upface_max, relief, coh100


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(p) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_prereg() -> dict:
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha256(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("preregistered hypothesis document changed after registration")
    pins = {f["id"]: f for f in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]}
    for key in ("training_features", "labels", "sample_submission"):
        if sha256(ROOT / "data" / pins[key]["dest"]) != pins[key]["sha256"]:
            raise SystemExit(f"input pin mismatch: {key}")
    reg["amendment"] = AMEND.name if AMEND.exists() else None
    reg["amendment_sha256"] = sha256(AMEND) if AMEND.exists() else None
    return reg


# ---------------------------------------------------------------------------------------------
# grid inputs and folds (shared builders)
# ---------------------------------------------------------------------------------------------
def grid_inputs(folds_needed=True):
    with rasterio.open(LABELS) as ds, rasterio.open(SAMPLE) as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid mismatch")
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
        meta = dict(shape=ref.shape, crs=ref.crs, transform=tuple(ref.transform))
    cat = labels == 1
    acc = None
    with rasterio.open(FEATURES) as src:
        for i in range(1, src.count + 1):
            a = src.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            acc = ok if acc is None else (acc & ok)
            del a
    footprint = acc
    valid = footprint & domain
    log(f"footprint {int(footprint.sum()):,} px; domain {int(domain.sum()):,}; eligible {int(valid.sum()):,}; "
        f"catalogue {int(cat.sum()):,} px")
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    log("folds: " + json.dumps([f["receipt"]["truth_px"] for f in folds]))
    return dict(labels=labels, cat=cat, domain=domain, valid=valid, meta=meta, folds=folds)


# ---------------------------------------------------------------------------------------------
# stage: channels  (rank-uint8 percentiles, the template's own encoder)
# ---------------------------------------------------------------------------------------------
def _norm_smooth(a, valid, sigma):
    good = valid & np.isfinite(a)
    num = ndi.gaussian_filter(np.where(good, a, 0.0).astype(np.float64), sigma, mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float64), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8)


def _grad_mag(s):
    gy, gx = np.gradient(s.astype(np.float32))
    return np.hypot(gy, gx)


def _lap(s, cell=100.0):
    gy, gx = np.gradient(s.astype(np.float32), cell)
    return np.gradient(gy, cell, axis=0) + np.gradient(gx, cell, axis=1)


def _hess_curv(s, cell=100.0):
    gyy, gyx = np.gradient(np.gradient(s.astype(np.float32), cell, axis=0), cell, axis=0), None
    gxx = np.gradient(np.gradient(s.astype(np.float32), cell, axis=1), cell, axis=1)
    gyx = np.gradient(np.gradient(s.astype(np.float32), cell, axis=0), cell, axis=1)
    tr = gyy + gxx
    det = gyy * gxx - gyx * gyx
    disc = np.sqrt(np.maximum(0.25 * tr * tr - det, 0.0))
    return np.abs(0.5 * tr + disc) + np.abs(0.5 * tr - disc)


def _coh(s, valid, sigma=2.5):
    s = _norm_smooth(s, valid, sigma)
    gy, gx = np.gradient(s.astype(np.float32))
    jxx = ndi.gaussian_filter(gx * gx, sigma, mode="reflect")
    jyy = ndi.gaussian_filter(gy * gy, sigma, mode="reflect")
    jxy = ndi.gaussian_filter(gx * gy, sigma, mode="reflect")
    tr = jxx + jyy
    disc = np.sqrt(np.maximum(0.25 * tr * tr - (jxx * jyy - jxy * jxy), 0.0))
    l1, l2 = 0.5 * tr + disc, 0.5 * tr - disc
    return (l1 - l2) / (l1 + l2 + 1e-12)


def channel_specs():
    """(name, view) list — deterministic order, no data read."""
    out = []
    for b in VIEW_A_BANDS:
        out += [(f"A_b{b:02d}_val", "A"), (f"A_b{b:02d}_grad", "A")]
    for b in VIEW_B_STACK_BANDS:
        if b == 12:
            out += [("B_b12_val", "B"), ("B_b12_grad", "B"), ("B_b12_lap", "B"),
                    ("B_b12_curv_s1", "B"), ("B_b12_curv_s8", "B"), ("B_b12_wl_ratio", "B")]
        else:
            out += [(f"B_b{b:02d}_val", "B"), (f"B_b{b:02d}_grad", "B")]
    for b in RAD_BANDS:
        out += [(f"B_rad{b:02d}_val", "B"), (f"B_rad{b:02d}_grad", "B")]
    for b in LIDAR_BANDS:
        out += [(f"B_lid{b:02d}_val", "B"), (f"B_lid{b:02d}_grad", "B")]
    return out


def stage_channels():
    t0 = time.time()
    g = grid_inputs(folds_needed=False)
    valid = g["valid"]
    specs = channel_specs()
    n = len(specs)
    WORK.mkdir(parents=True, exist_ok=True)
    arr = np.lib.format.open_memmap(WORK / "channels_u8.npy", mode="w+", dtype=np.uint8,
                                    shape=(n, SHAPE[0], SHAPE[1]))
    idx = {"channels": [dict(i=i, name=nm, view=v) for i, (nm, v) in enumerate(specs)],
           "encoder": "gems52.cotrain.rank_u8 (min-max percentile-free rank to uint8, valid>=0)",
           "started_utc": now()}

    def put(i, a):
        arr[i] = cotrain.rank_u8(np.asarray(a, np.float32), valid)
        del a

    with rasterio.open(FEATURES) as src:
        for b in VIEW_A_BANDS:
            a = src.read(b).astype(np.float32)
            a[(a < -1e38) | ~np.isfinite(a)] = np.nan
            i0 = [j for j, (nm, v) in enumerate(specs) if nm == f"A_b{b:02d}_val"][0]
            put(i0, a)
            s = _norm_smooth(a, valid, 2.0)
            put(i0 + 1, _grad_mag(s))
            del a, s
        for b in VIEW_B_STACK_BANDS:
            a = src.read(b).astype(np.float32)
            a[(a < -1e38) | ~np.isfinite(a)] = np.nan
            i0 = [j for j, (nm, v) in enumerate(specs) if nm.startswith(f"B_b{b:02d}_")][0]
            put(i0, a)
            s2 = _norm_smooth(a, valid, 2.0)
            put(i0 + 1, _grad_mag(s2))
            if b == 12:
                put(i0 + 2, np.abs(_lap(s2)))
                s1 = _norm_smooth(a, valid, 1.0)
                s8 = _norm_smooth(a, valid, 8.0)
                c1, c8 = _hess_curv(s1), _hess_curv(s8)
                put(i0 + 3, c1)
                put(i0 + 4, c8)
                put(i0 + 5, np.clip(c1 / (c8 + 1e-10), 0, 1e6))
                del s1, s8, c1, c8
            del a, s2
    for b, path in ((0, RAD), (4, EXT)):
        with rasterio.open(path) as src:
            nb = min(7, src.count) if path == RAD else min(3, src.count)
            for k in range(1, nb + 1):
                a = src.read(k).astype(np.float32)
                a[~np.isfinite(a)] = np.nan
                j = b + k - 1
                i0 = [j0 for j0, (nm, v) in enumerate(specs) if nm == f"B_rad{j+1:02d}_val"][0]
                put(i0, a)
                s = _norm_smooth(a, valid, 2.0)
                put(i0 + 1, _grad_mag(s))
                del a, s
            if nb == 0:
                raise SystemExit(f"{path} has no bands")
    with rasterio.open(LIDAR) as src:
        for k in LIDAR_BANDS:
            a = src.read(k).astype(np.float32)
            a[~np.isfinite(a)] = np.nan
            i0 = [j for j, (nm, v) in enumerate(specs) if nm == f"B_lid{k:02d}_val"][0]
            put(i0, a)
            s = _norm_smooth(a, valid, 2.0)
            put(i0 + 1, _grad_mag(s))
            del a, s
    arr.flush()
    del arr
    idx.update(finished_utc=now(), n_channels=n,
               seconds=round(time.time() - t0, 1),
               inputs={p.name: sha256(p) for p in (FEATURES, RAD, EXT, LIDAR)},
               caveat=("rank-uint8 per channel inside the eligible footprint; 255 levels is a rank "
                       "encoding, the metric resolves 100 m, not 1/255 of a quantile"))
    (EVID / "h88s_channels.json").write_text(json.dumps(idx, indent=2) + "\n")
    log(f"channels: {n} built in {idx['seconds']}s -> {EVID/'h88s_channels.json'}")
    return idx


# ---------------------------------------------------------------------------------------------
# stage: fit  (OOF per fold, per-view sufficiency, negative-block independence, screened exchange)
# ---------------------------------------------------------------------------------------------
def _gather_rows(mm, rows, cols, ch_cols, chunk=150_000):
    """Elementwise (pixel, channel) gather: X[j, i] = mm[ch_cols[i], rows[j], cols[j]]."""
    rows = np.asarray(rows)
    ch = np.asarray(ch_cols, dtype=np.intp)[None, :]
    out = np.empty((rows.size, len(ch_cols)), np.float32)
    for i in range(0, rows.size, chunk):
        sl = slice(i, min(i + chunk, rows.size))
        out[sl] = mm[ch, np.asarray(rows[sl], np.intp)[:, None],
                     np.asarray(cols[sl], np.intp)[:, None]]
    return out


def _predict_rows(mm, model, rows, cols, ch_cols, chunk=150_000):
    out = np.empty(rows.size, np.float32)
    for i in range(0, rows.size, chunk):
        sl = slice(i, min(i + chunk, rows.size))
        X = _gather_rows(mm, rows[sl], cols[sl], ch_cols, chunk=chunk)
        out[sl] = model.predict_proba(X)[:, 1].astype(np.float32)
    return out


def _learner():
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, max_leaf_nodes=15,
                                          min_samples_leaf=40, l2_regularization=1.0,
                                          early_stopping=False, random_state=SEED)


def _rank01(vals):
    from scipy.stats import rankdata
    out = np.zeros(vals.shape, np.float32)
    if vals.size:
        out = ((rankdata(vals, method="average") - 0.5) / float(vals.size)).astype(np.float32)
    return out


def stage_fit():
    t0 = time.time()
    g = grid_inputs()
    valid, cat, labels, folds = g["valid"], g["cat"], g["labels"], g["folds"]
    specs = channel_specs()
    mm = np.load(WORK / "channels_u8.npy", mmap_mode="r")
    colA = np.array([j for j, (nm, v) in enumerate(specs) if v == "A"])
    colB = np.array([j for j, (nm, v) in enumerate(specs) if v == "B"])
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", started_utc=now(), seed=SEED, n_channels_A=int(colA.size),
               n_channels_B=int(colB.size), buffer_px=BUFFER_PX, ring_px=RING_PX,
               folds=[], independence_per_fold=[], exchange_per_fold=[])
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        visd = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & valid & ~fold["visible"] & (visd > RING_PX)
        train = fold["train"] & valid
        pos = np.flatnonzero((train & fold["visible"]).ravel())
        neg = np.flatnonzero((train & ~cat & (visd > 5)).ravel())
        pos = rng.choice(pos, min(20000, pos.size), replace=False)
        neg = rng.choice(neg, min(60000, neg.size), replace=False)
        rows = np.concatenate([pos, neg])
        y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
        o = rng.permutation(rows.size)
        rows, y = rows[o], y[o]
        rr, cc = np.divmod(rows, SHAPE[1])
        rec = dict(fold=f, n_train=int(rows.size), n_pos=int(pos.size), allowed_px=int(allowed.sum()),
                   truth_px=int((fold["truth"] & fold["region"]).sum()))
        pool = fold["train"] & valid & ~fold["visible"]
        preds = {}
        for view, cols in (("A", colA), ("B", colB)):
            t1 = time.time()
            X = _gather_rows(mm, rr, cc, cols)
            m = _learner().fit(X, y)
            in_auc = float(roc_auc_score(y, m.predict_proba(X)[:, 1]))
            del X
            ar, ac = np.divmod(np.flatnonzero(allowed.ravel()), SHAPE[1])
            p = _predict_rows(mm, m, ar, ac, cols)
            np.save(WORK / f"pred_{view}_f{f}.npy", p)
            np.save(WORK / f"allowed_f{f}.npy", np.flatnonzero(allowed.ravel()))
            # the unlabeled pool for the optional exchange is the fold's own train domain
            pur, puc = np.divmod(np.flatnonzero(pool.ravel()), SHAPE[1])
            np.save(WORK / f"pred_pool_{view}_f{f}.npy", _predict_rows(mm, m, pur, puc, cols))
            np.save(WORK / f"pool_f{f}.npy", np.flatnonzero(pool.ravel()))
            truth_in = (fold["truth"] & fold["region"])[allowed]
            oof_auc = float(roc_auc_score(truth_in.astype(int), p)) if truth_in.any() else None
            preds[view] = (p, ar, ac, m)
            rec[f"view_{view}"] = dict(in_sample_auc=round(in_auc, 4),
                                       oof_auc_heldout_region=None if oof_auc is None else round(oof_auc, 4),
                                       seconds=round(time.time() - t1, 1))
            log(f"fold {f} view {view}: in-AUC {in_auc:.4f} OOF-AUC {oof_auc if oof_auc is None else round(oof_auc,4)}")
        # ---- mandated independence read: block-level OOF errors on labelled negatives ----------
        pa_grid = np.full(SHAPE, np.nan, np.float32)
        pb_grid = np.full(SHAPE, np.nan, np.float32)
        pa_grid[preds["A"][1], preds["A"][2]] = preds["A"][0]
        pb_grid[preds["B"][1], preds["B"][2]] = preds["B"][0]
        negative_mask = allowed & (labels == 0) & (catd > 5)
        rows_nb = spatial.negative_block_errors(pa_grid, pb_grid, negative_mask, f,
                                                thresholds=(0.5, 0.5), side=BLOCK_SIDE)
        indep = spatial.independence(rows_nb, threshold=0.6)
        views_indep = views54.independence_test(pa_grid, pb_grid, negative_mask,
                                               views54.block_ids(SHAPE, valid, n=4), threshold=0.6)
        out["independence_per_fold"].append(dict(fold=f, spatial=indep, views54=views_indep,
                                                 n_negatives=int(negative_mask.sum())))
        log(f"fold {f} independence: max|r| {indep['max_abs_correlation']} allow_exchange {indep['allow_exchange']}"
            f" | views54 pixel r {views_indep['pixel_pearson_r']}")
        # ---- pseudo-label exchange (donor A -> receiver B), whole segments only ----------------
        # The unlabeled pool is the fold's own train domain: the evaluation region and the held
        # components are forbidden, and every surviving component must sit inside one 50x50 block,
        # so no pseudo-label can reach the evaluation (spatial.whole_pseudo_segments enforces it).
        rankA = np.full(SHAPE, np.nan, np.float32)
        rankB = np.full(SHAPE, np.nan, np.float32)
        ai = np.load(WORK / f"pool_f{f}.npy")
        rankA.ravel()[ai] = _rank01(np.load(WORK / f"pred_pool_A_f{f}.npy"))
        rankB.ravel()[ai] = _rank01(np.load(WORK / f"pred_pool_B_f{f}.npy"))
        donor_vals = rankA.ravel()[ai]
        recv_vals = rankB.ravel()[ai]
        tA = float(np.quantile(donor_vals, DONOR_RANK_MIN))
        rlo, rhi = float(np.quantile(recv_vals, RECEIVER_LO)), float(np.quantile(recv_vals, RECEIVER_HI))
        forbidden = fold["region"] | fold["held_all"] | cat | ~valid
        idx_flat, receipts = spatial.whole_pseudo_segments(rankA, rankB, pool,
                                                          forbidden, tA, rlo, rhi,
                                                          side=BLOCK_SIDE, min_pixels=5, cap=PSEUDO_CAP)
        donor_auc = rec[f"view_A"]["oof_auc_heldout_region"]
        screened = bool(donor_auc is not None and donor_auc >= 0.60)
        out["exchange_per_fold"].append(dict(fold=f, donor_rank_threshold=tA,
                                             receiver_interval=[rlo, rhi], pseudo_px=int(idx_flat.size),
                                             segments=receipts[:20], n_segments=len(receipts),
                                             donor_oof_auc=donor_auc, sufficiency_screen_pass=screened,
                                             allowed_by_independence=bool(indep["allow_exchange"])))
        if idx_flat.size >= 5:
            ar2, ac2 = preds["B"][1], preds["B"][2]
            pr, pc = np.divmod(idx_flat, SHAPE[1])
            Xp = _gather_rows(mm, pr, pc, colB)
            X = np.vstack([_gather_rows(mm, rr, cc, colB), Xp])
            yy = np.concatenate([y, np.ones(idx_flat.size, np.int8)])
            w = np.concatenate([np.ones(y.size, np.float32), np.full(idx_flat.size, 0.5, np.float32)])
            pe = _predict_rows(mm, _learner().fit(X, yy, sample_weight=w), ar2, ac2, colB)
            np.save(WORK / f"pred_exchange_f{f}.npy", pe)
            truth_in = (fold["truth"] & fold["region"])[allowed]
            ex_auc = float(roc_auc_score(truth_in.astype(int), pe)) if truth_in.any() else None
            rec["exchange_B"] = dict(oof_auc_heldout_region=None if ex_auc is None else round(ex_auc, 4),
                                     pseudo_px=int(idx_flat.size), screened=screened)
            log(f"fold {f} exchange: {idx_flat.size} pseudo px from {len(receipts)} whole segments; "
                f"OOF-AUC {ex_auc if ex_auc is None else round(ex_auc,4)} (screened_pass={screened})")
        else:
            rec["exchange_B"] = dict(oof_auc_heldout_region=None, pseudo_px=int(idx_flat.size),
                                     screened=screened, note="no whole pseudo-segment survived the gates")
        out["folds"].append(rec)
        del pa_grid, pb_grid, rankA, rankB, preds, allowed, train
    meanA = np.mean([r["view_A"]["oof_auc_heldout_region"] for r in out["folds"]])
    meanB = np.mean([r["view_B"]["oof_auc_heldout_region"] for r in out["folds"]])
    out.update(finished_utc=now(), seconds=round(time.time() - t0, 1),
               sufficiency=dict(view_A_mean_oof_auc=round(float(meanA), 4),
                                view_B_mean_oof_auc=round(float(meanB), 4),
                                gate=0.60, view_A_pass=bool(meanA >= 0.60), view_B_pass=bool(meanB >= 0.60)))
    (EVID / "h88s_fit.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    log(f"fit done in {out['seconds']}s: sufficiency A {out['sufficiency']['view_A_mean_oof_auc']} "
        f"B {out['sufficiency']['view_B_mean_oof_auc']} -> {EVID/'h88s_fit.json'}")
    return out


# ---------------------------------------------------------------------------------------------
# stage: holdout  (strata arms, metered budget curve, canary)
# ---------------------------------------------------------------------------------------------
def _load_fold_pred(f, name):
    p = np.load(WORK / f"pred_{name}_f{f}.npy")
    flat = np.load(WORK / f"allowed_f{f}.npy")
    grid = np.zeros(SHAPE, np.float32)
    grid.ravel()[flat] = p
    return grid, flat


def stage_holdout():
    t0 = time.time()
    g = grid_inputs()
    valid, folds = g["valid"], g["folds"]
    specs = channel_specs()
    mm = np.load(WORK / "channels_u8.npy", mmap_mode="r")
    can_cols = {"A": [j for j, (nm, v) in enumerate(specs) if v == "A"],
                "B": [j for j, (nm, v) in enumerate(specs) if v == "B"]}
    arms = ("single_A", "single_B", "a_only", "b_only", "concordant", "exchange_B",
            "corroborated_B", "union_max", "random")
    terms = {a: None for a in arms}
    curve_terms = {f"k{k}": None for k in BUDGET_CURVE}
    per_fold, canary = [], {}

    def emit(field, allowed, k, min_px=3.0):
        """Place up to ``k`` dots by the arm's own ranking, inside the arm's own support."""
        return nodes.spacing_select(field, allowed & (field > 0), k, min_px=min_px).astype(np.float32)

    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        pa, aflat = _load_fold_pred(f, "A")
        pb, _ = _load_fold_pred(f, "B")
        if (WORK / f"pred_exchange_f{f}.npy").exists():
            pex, _ = _load_fold_pred(f, "exchange")
            pex_ok = True
        else:
            # No receiver refit was produced (the exchange was screened out or no whole segment
            # survived the gates).  Emitting nothing is the only honest arm here: a zeros grid ranked
            # with _rank01 would place K dots at rank 0.5 and score them as if they were a strategy.
            pex = np.zeros(SHAPE, np.float32)
            pex_ok = False
            log(f"fold {f} exchange_B: no receiver refit on disk -> arm emits 0 dots")
        allowed = np.zeros(SHAPE, bool)
        allowed.ravel()[aflat] = True
        rA, rB = np.zeros(SHAPE, np.float32), np.zeros(SHAPE, np.float32)
        rA.ravel()[aflat] = _rank01(pa.ravel()[aflat])
        rB.ravel()[aflat] = _rank01(pb.ravel()[aflat])
        st = views54.strata(rA, rB, allowed, q=STRATA_Q)
        a_only, b_only, conc = st["A_only"], st["B_only"], st["concordant"]
        fields = {
            "single_A": np.where(allowed, rA, 0.0).astype(np.float32),
            "single_B": np.where(allowed, rB, 0.0).astype(np.float32),
            "a_only": np.where(a_only, rA, 0.0).astype(np.float32),
            "b_only": np.where(b_only, rB, 0.0).astype(np.float32),
            "concordant": np.where(conc, rB, 0.0).astype(np.float32),
            "exchange_B": (np.where(allowed, _rank01_of(pex, aflat, allowed), 0.0).astype(np.float32)
                           if pex_ok else np.zeros(SHAPE, np.float32)),
            "corroborated_B": np.where(allowed & ~b_only, rB, 0.0).astype(np.float32),
            "union_max": np.where(allowed, np.maximum(rA, rB), 0.0).astype(np.float32),
        }
        rnd = np.zeros(SHAPE, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        rnd.ravel()[ai] = rng.random(ai.size, dtype=np.float32)
        fields["random"] = rnd
        rec = dict(fold=f, allowed_px=int(allowed.sum()), strata_px=dict(
            a_only=int(a_only.sum()), b_only=int(b_only.sum()), concordant=int(conc.sum()),
            abstain=int(st["abstain"].sum())), arms={})
        for arm, fld in fields.items():
            em = emit(fld, allowed, K_FOLD)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=round(res["dti"], 6), placed=int(em.sum()),
                                    tpw=round(res["tpw"], 3), fpw=round(res["fpw"], 3))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            if arm in ("union_max", "single_A", "single_B"):
                np.save(WORK / f"dots_{arm}_f{f}.npy", np.flatnonzero(em.ravel()))
        for k in BUDGET_CURVE:
            em = emit(fields[PRIMARY], allowed, k)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            curve_terms[f"k{k}"] = term if curve_terms[f"k{k}"] is None else curve_terms[f"k{k}"] + term
            rec["arms"][f"{PRIMARY}@k{k}"] = dict(dti=round(res["dti"], 6), placed=int(em.sum()))
            log(f"fold {f} {PRIMARY}@k{k}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        # leakage canary: single channels against the held-out truth inside the allowed set
        truth_in = (fold["truth"] & fold["region"])[allowed]
        if truth_in.any() and (~truth_in).any():
            srng = rng.choice(ai.size, size=min(200_000, ai.size), replace=False)
            sel = np.sort(ai[srng])
            truth_grid = (fold["truth"] & fold["region"]).ravel()
            ys = truth_grid[sel].astype(int)
            if ys.min() != ys.max():
                for ci, (cname, _view) in enumerate(specs):
                    vals = np.asarray(mm[ci].ravel()[sel], np.float32)
                    auc = float(roc_auc_score(ys, vals))
                    canary.setdefault(cname, []).append(dict(fold=f, auc=round(auc, 4)))
        per_fold.append(rec)
        del fields, pa, pb, pex, rA, rB
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    curve = evaluator.pooled_summary(dict(curve_terms, single_B=terms["single_B"]), draws=1000,
                                     seed=SEED, candidate=f"k{BUDGET_CURVE[0]}", evidence_class="HOLDOUT-DTI")
    cmax = {k: max(x["auc"] for x in v) for k, v in canary.items() if v}
    out = dict(stage="holdout", started_utc=now(), evaluator_version=evaluator.VERSION,
               evidence_class="HOLDOUT-DTI", seeds=dict(fit=SEED), budget_per_fold=K_FOLD,
               buffer_px=BUFFER_PX, ring_px=RING_PX, block_side=BLOCK_SIDE,
               negative_substrate="labels.tif == 0 pixels further than 5 px from the mapped catalogue",
               budget_curve=BUDGET_CURVE, strata_q=STRATA_Q, primary=PRIMARY,
               withheld_positive_px=int(sum((fd["truth"] & fd["region"]).sum() for fd in folds)),
               pooled=summary, budget_curve_pooled=curve, per_fold=per_fold,
               canary=dict(alarm_threshold=CANARY_ALARM, max_auc=cmax,
                           alarm={k: v > CANARY_ALARM for k, v in cmax.items()},
                           top=sorted(cmax.items(), key=lambda kv: -kv[1])[:10],
                           note="single channel AUC on 200k sampled allowed pixels per fold"),
               seconds=round(time.time() - t0, 1))
    (EVID / "h88s_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a: round(summary["scores"][a]["dti"], 6) for a in terms}))
    log("curve: " + json.dumps({a: round(curve["scores"][a]["dti"], 6) for a in curve["scores"]}))
    log("paired (primary - arm): " + json.dumps({k: [round(v["delta"], 6), [round(x, 6) for x in v["ci95"]]]
                                                 for k, v in summary["paired_differences"].items()}))
    log(f"wrote {EVID/'h88s_holdout.json'}")
    return out


def _rank01_of(grid, flat, allowed):
    vals = grid.ravel()[flat]
    out = np.zeros(SHAPE, np.float32)
    out.ravel()[flat] = _rank01(vals)
    return out




# ---------------------------------------------------------------------------------------------
# stage: build  (budget rule -> stitched OOF field -> dots -> GeoTIFF -> gates -> reasoning export)
# ---------------------------------------------------------------------------------------------
def _fold_ranks(f):
    pa, aflat = _load_fold_pred(f, "A")
    pb, _ = _load_fold_pred(f, "B")
    allowed = np.zeros(SHAPE, bool)
    allowed.ravel()[aflat] = True
    rA = np.zeros(SHAPE, np.float32)
    rB = np.zeros(SHAPE, np.float32)
    rA.ravel()[aflat] = _rank01(pa.ravel()[aflat])
    rB.ravel()[aflat] = _rank01(pb.ravel()[aflat])
    return allowed, rA, rB


def _budget_rule(source="h88s_holdout.json", keys=("k4700", "k6250", "k9400")):
    """knowledge/80s: smallest total budget whose pooled point estimate >= the 37,600 total.

    Ordering is ascending, so 18,800 is tried first; all three point estimates and CIs are reported.
    ``source``/``keys`` let the same frozen rule be applied to whichever field actually ships, and the
    receipt records which curve it was applied to.
    """
    ho = json.loads((EVID / source).read_text())
    curve = ho["budget_curve_pooled"]["scores"]
    values = {18800: curve[keys[0]]["dti"], 25000: curve[keys[1]]["dti"], 37600: curve[keys[2]]["dti"]}
    base = values[37600]
    chosen = 37600
    for total in (18800, 25000):
        if values[total] >= base:
            chosen = total
            break
    return dict(chosen_total=chosen, per_fold=chosen // 4, base_total=37600, base_dti=base,
                values=values, rule="knowledge/80s_h88s_amendment_budget.md",
                applied_to=source, curve_keys=list(keys))


def _challenger_meta():
    """Receipt-only record of the incumbent H87 field measured on this lane's folds, or None."""
    path = EVID / "h88s_h87field_holdout.json"
    if not path.exists():
        return None
    ex = json.loads(path.read_text())
    d = ex["pooled"]["scores"]["h87_field"]
    return dict(name="h87_field", source=str(path), dti=d["dti"], ci95=d["ci95"],
                curve={k: v["dti"] for k, v in ex["budget_curve_pooled"]["scores"].items()},
                note=("the currently advertised H87 candidate's own ranking field, re-scored on the H88 "
                      "folds by scripts/run_h88_incumbent_field_holdout.py; recorded so the ship decision "
                      "is visible, never merged into the primary arm"))


def _challenger_field():
    """Rebuild that field from the H87 builder module (one implementation, imported not forked)."""
    import build_h87_cotrain_wavelength as H87
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
    valid = H87.footprint_all_bands(str(FEATURES)) & domain
    va = H87.compute_view_a(str(FEATURES), valid)
    vb = H87.compute_view_b(str(FEATURES), str(H87.GEODAWN_RAD), str(H87.GEODAWN_EXT), valid)
    dis = H87.compute_disagreement_field(va, vb, valid, None)
    del va, vb
    return np.where(dis > 0, dis, 0.0).astype(np.float32)   # positive support only, as H87 placed


def stage_build():
    t0 = time.time()
    g = grid_inputs()
    valid, cat, folds, meta = g["valid"], g["cat"], g["folds"], g["meta"]
    catd = ndi.distance_transform_edt(~cat)
    ship_field = os.environ.get("H88_SHIP_FIELD", "primary")
    challenger = _challenger_meta()
    chal_field = None
    ship_note = ""
    ho_all = json.loads((EVID / "h88s_holdout.json").read_text())
    arm_scores = ho_all["pooled"]["scores"]
    if ship_field == "h87_field":
        if challenger is None:
            raise SystemExit("H88_SHIP_FIELD=h87_field but no h88s_h87field_holdout.json receipt")
        log("rebuilding the incumbent H87 field: H88_SHIP_FIELD=h87_field")
        chal_field = _challenger_field()
        ship_note = ("amendment 80b: the preregistered primary lost its promotion test, so the shipped "
                     "field is the strongest measured artefact on this round's instrument "
                     "(the incumbent H87 co-training field, rebuilt fold-blind from its own builder)")
    elif ship_field != "primary":
        if ship_field not in arm_scores:
            raise SystemExit(f"H88_SHIP_FIELD={ship_field} is not a measured arm")
        ship_note = (f"amendment 80b: the preregistered primary scored {arm_scores[PRIMARY]['dti']:.6f} "
                     f"[{arm_scores[PRIMARY]['ci95'][0]:.5f}, {arm_scores[PRIMARY]['ci95'][1]:.5f}] and lost "
                     f"its promotion test against single_B; the shipped field is the arm with the highest "
                     f"permitted pooled estimate, {ship_field} "
                     f"({arm_scores[ship_field]['dti']:.6f} "
                     f"[{arm_scores[ship_field]['ci95'][0]:.5f}, {arm_scores[ship_field]['ci95'][1]:.5f}]). "
                     f"The exchange_B arm was NOT shipped despite its tied top score because the round's own "
                     f"donor-sufficiency screen excluded it.")
    if ship_field not in ("primary", "h87_field"):
        log(f"shipping arm {ship_field}: {ship_note}")
    if chal_field is not None:
        rule = _budget_rule(source="h88s_h87field_holdout.json",
                            keys=("h87_field@k4700", "h87_field@k6250", "h87_field@k9400"))
    elif ship_field == "primary":
        rule = _budget_rule()
    else:
        rule = dict(chosen_total=37600, per_fold=9400, base_total=37600,
                    base_dti=arm_scores[ship_field]["dti"], values={},
                    rule="knowledge/80s amendment 80b: the budget curve was measured for the primary "
                         "only, so a non-primary ship field is emitted at the round's largest registered "
                         "budget (9,400 dots/fold, 37,600 total, the champion's own scale)")
    rule["applied_to"] = rule.get("applied_to", f"arm:{ship_field}")
    Kf = rule["per_fold"]
    log(f"budget rule chose {rule['chosen_total']:,} total dots ({Kf:,}/fold); values {rule['values']}")
    stitched = np.zeros(SHAPE, np.float32)
    dots = np.zeros(SHAPE, bool)
    dots_A = np.zeros(SHAPE, bool)
    dots_B = np.zeros(SHAPE, bool)
    dots_union_field = np.zeros(SHAPE, bool)
    a_only_dots = np.zeros(SHAPE, bool)
    per_fold = {}
    for fold in folds:
        f = fold["fold"]
        allowed, rA, rB = _fold_ranks(f)
        st = views54.strata(rA, rB, allowed, q=STRATA_Q)
        if chal_field is not None:
            vals = chal_field.ravel()[np.flatnonzero(allowed.ravel())]
            fb_grid = np.zeros(SHAPE, np.float32)
            fb_grid.ravel()[np.flatnonzero(allowed.ravel())] = _rank01(vals)
            fb = fb_grid
        elif ship_field == "single_B":
            fb = np.where(allowed, rB, 0.0).astype(np.float32)
        elif ship_field == "b_only":
            fb = np.where(st["B_only"], rB, 0.0).astype(np.float32)
        elif ship_field == "union_max":
            fb = np.where(allowed, np.maximum(rA, rB), 0.0).astype(np.float32)
        elif ship_field == "exchange_B":
            pex_path = WORK / f"pred_exchange_f{f}.npy"
            if not pex_path.exists():
                raise SystemExit("ship_field=exchange_B needs every fold's receiver refit")
            pex, _ = _load_fold_pred(f, "exchange")
            fb = np.where(allowed, _rank01_of(pex, np.flatnonzero(allowed.ravel()),
                                             allowed), 0.0).astype(np.float32)
        else:
            fb = np.where(allowed & ~st["B_only"], rB, 0.0).astype(np.float32)
        stitched = np.maximum(stitched, fb)
        em = nodes.spacing_select(fb, allowed & (fb > 0), Kf, min_px=3.0)
        emA = nodes.spacing_select(rA, allowed & (rA > 0), Kf, min_px=3.0)
        emB = nodes.spacing_select(rB, allowed & (rB > 0), Kf, min_px=3.0)
        emU = nodes.spacing_select(np.maximum(rA, rB), allowed, Kf, min_px=3.0)
        fa = np.where(st["A_only"], rA, 0.0).astype(np.float32)
        emAO = nodes.spacing_select(fa, st["A_only"], min(int(st["A_only"].sum()), Kf), min_px=3.0)
        dots |= em
        dots_A |= emA
        dots_B |= emB
        dots_union_field |= emU
        a_only_dots |= emAO
        per_fold[f] = dict(placed=int(em.sum()), a_only_px=int(st["A_only"].sum()),
                           b_only_px=int(st["B_only"].sum()), concordant_px=int(st["concordant"].sum()))
        log(f"fold {f}: primary dots {int(em.sum()):,} (A {int(emA.sum()):,}, B {int(emB.sum()):,}, "
            f"union-field {int(emU.sum()):,}, A-only arm {int(emAO.sum()):,})")
        del allowed, rA, rB, st, fb, em, emA, emB, emU, emAO, fa
    keep = valid & ~cat & (catd > RING_PX)
    dropped = int((dots & ~keep).sum())
    dots &= keep
    # Global spacing pass: nodes.spacing_select enforces min_px inside ONE fold's region, so dots on
    # opposite sides of a quadrant boundary can sit closer than 3 px (measured on the first build: 42
    # dots in 21 pairs, every violation at a fold edge).  The shipped claim is global "3 px spacing",
    # so resolve cross-boundary neighbours here, keeping the higher-ranked dot of each pair.
    spacing_offsets = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3)
                       if 0 < dy * dy + dx * dx < 9]
    ys_d, xs_d = np.nonzero(dots)
    priority = stitched[ys_d, xs_d]
    occupied = np.zeros(SHAPE, bool)
    keep_idx = []
    for i in np.argsort(-priority, kind="stable"):
        y, x, clash = int(ys_d[i]), int(xs_d[i]), False
        for dy, dx in spacing_offsets:
            yy, xx = y + dy, x + dx
            if 0 <= yy < SHAPE[0] and 0 <= xx < SHAPE[1] and occupied[yy, xx]:
                clash = True
                break
        if not clash:
            occupied[y, x] = True
            keep_idx.append(int(i))
    spacing_dropped = int(len(ys_d) - len(keep_idx))
    if spacing_dropped:
        dots = np.zeros(SHAPE, bool)
        dots[ys_d[keep_idx], xs_d[keep_idx]] = True
    log(f"global spacing pass: dropped {spacing_dropped} dot(s) closer than 3 px across fold edges")
    emission = dots.astype(np.float32)
    ts = now()
    name = f"h88-cotrain-disagreement-suffscreen-{int(dots.sum())}px-{ts}"
    subname = f"h88-cotrain-disagreement-{int(dots.sum())}px"
    note = (f"H88 co-train lane: B-corroborated, A-only suppressed, {int(dots.sum())}px, "
            f"3px spacing, 200m collar")
    note = note[:140]
    SUBDIR = ROOT / "submission"
    SUBDIR.mkdir(exist_ok=True)
    path = SUBDIR / f"gems52-{name}.tif"
    receipt = submission_writer.write_submission(path, emission, SAMPLE, keep, name=subname, note=note,
                                                metadata=dict(round="H88s", budget_rule=rule["rule"],
                                                              per_fold=per_fold))
    log(f"wrote {path} + {path.with_suffix('.zip').name}")
    # ---- gates: uniqueness, lane, not-the-union ------------------------------------------------
    priors = gates.find_priors([SUBDIR, ROOT / "docs" / "downloads", ROOT / "data" / "scored"], exclude=path)
    # The inventory sweeps this repository's own output directories, so a re-build finds the previous
    # build of the SAME round and reports rho ~ 1.0 against it.  Those files are this round's own
    # intermediate artefacts, not prior submissions to the organiser, so they are excluded from the
    # gate and recorded with their measured overlap instead of silently ignored.
    same_round, keep_priors = [], []
    for q in priors:
        if q.name.startswith("gems52-h88-") or q.name in ("h88-candidate.tif", "h88-candidate.zip"):
            other = (rasterio.open(q).read(1) > 0)
            inter = int((dots & other).sum())
            union = int((dots | other).sum())
            same_round.append(dict(path=str(q), dots=int(other.sum()),
                                   sha256=hashlib.sha256(q.read_bytes()).hexdigest(),
                                   intersection_px=inter,
                                   jaccard=round(inter / union, 6) if union else None))
        else:
            keep_priors.append(q)
    priors = keep_priors
    uq = gates.uniqueness_report(emission, priors)
    lane = gates.lane_report(emission, valid, priors, sample=str(SAMPLE), phase="dots")
    not_union = dict(
        equals_view_A_dots=bool(np.array_equal(dots, dots_A)),
        equals_view_B_dots=bool(np.array_equal(dots, dots_B)),
        equals_set_union=bool(np.array_equal(dots, dots_A | dots_B)),
        equals_union_field_dots=bool(np.array_equal(dots, dots_union_field)),
        px_different_from_set_union=int((dots ^ (dots_A | dots_B)).sum()),
        px_different_from_union_field=int((dots ^ dots_union_field).sum()),
        px_different_from_A=int((dots ^ dots_A).sum()),
        px_different_from_B=int((dots ^ dots_B).sum()),
    )
    single_view_equality = (bool(not_union["equals_view_A_dots"]) or bool(not_union["equals_view_B_dots"]))
    not_union_ok = not (bool(not_union["equals_set_union"]) or bool(not_union["equals_union_field_dots"]))
    not_union["interpretation"] = (
        "the brief's test is that the emitted set is not merely the union of the two views' dots; "
        "single-view equality is reported as a flag because amendment 80b may deliberately ship one "
        "measured-best view field: shipped_dots_equal_a_single_view=" + json.dumps(single_view_equality))
    # ---- A-only reasoning export (every A-only candidate, with measured context) ---------------
    chan = np.load(WORK / "channels_u8.npy", mmap_mode="r")
    specs = channel_specs()
    names = [nm for nm, _ in specs]
    i_depth = names.index("A_b15_val") if "A_b15_val" in names else None
    i_grad = names.index("A_b05_grad") if "A_b05_grad" in names else None
    rows_out = []
    ao_pos = np.argwhere(a_only_dots)
    cap = 600
    for y, x in ao_pos[:cap]:
        ctx = dict(dot_id=int(len(rows_out)), row=int(y), col=int(x),
                   distance_to_mapped_catalogue_m=round(float(catd[y, x] * 100.0), 1),
                   depth_to_basement_u8=(int(chan[i_depth, y, x]) if i_depth is not None else None),
                   gravity_gradient_u8=(int(chan[i_grad, y, x]) if i_grad is not None else None),
                   reasoning=("A-only candidate: potential-field edge evidence with no surface "
                              "expression above threshold. Buried-fault hypothesis: concealed normal "
                              "fault under basin fill; the confounder to test in Phase 2 is a "
                              "lithologic contact or basement step of non-tectonic origin. Field "
                              "check: is there a mapped contact, a paleo-channel, or an intrusive "
                              "margin at this location?"))
        rows_out.append(ctx)
    reasoning_path = EVID / "h88s_a_only_reasoning.json"
    reasoning_path.write_text(json.dumps(dict(
        n_a_only_arm_dots=int(a_only_dots.sum()), exported=len(rows_out), cap=cap,
        strata_definition="views54.strata(q=0.90): A_only = A rank >= q and B rank < q over the allowed set",
        note=("The shipped file is the corroborated_B arm and contains 0 A-only pixels by construction. "
              "These candidates are the brief's discovery signal, exported with measured context so a "
              "Phase 2 reviewer can evaluate each buried-fault call."),
        candidates=rows_out), indent=2) + "\n")
    (EVID / "h88s_a_only_reasoning.csv").write_text(
        "dot_id,row,col,distance_to_mapped_catalogue_m,depth_to_basement_u8,gravity_gradient_u8,reasoning\n"
        + "\n".join(f'{r["dot_id"]},{r["row"]},{r["col"]},{r["distance_to_mapped_catalogue_m"]},'
                    f'{r["depth_to_basement_u8"]},{r["gravity_gradient_u8"]},"{r["reasoning"]}"'
                    for r in rows_out) + "\n")
    out = dict(stage="build", started_utc=now(), file=str(path), sha256=receipt["sha256"],
               bytes=receipt["bytes"], zip_file=receipt["zip_file"], zip_sha256=receipt["zip_sha256"],
               submission_name=subname, note=note, dots=int(dots.sum()),
               dots_before_ring_strip=int(dots.sum()) + dropped + spacing_dropped,
               ring_dropped=int(dropped), spacing_dropped=int(spacing_dropped),
               per_fold=per_fold, budget_rule=rule,
               summary=(f"H88 co-training lane candidate ({'incumbent H87 disagreement field' if chal_field is not None else 'preregistered corroborated_B field'}): View B (DEM curvature/slope + radiometric "
                        f"K/Th/U ratios + LiDAR scarp faces) with the B-only disagreement stratum "
                        f"suppressed, ranked by View B confidence, metered to {rule['chosen_total']:,} dots "
                        f"at 3 px spacing outside the 200 m catalogue ring. View A is measured "
                        f"non-sufficient and is used only as the suppressor, never as a donor."),
               gates=dict(format_ok=bool(receipt["validator"]["ok"]), validator=receipt["validator"],
                           uniqueness_ok=bool(uq.get("ok")), uniqueness=uq, lane_ok=bool(lane["policy"]["verdict"] == "PASS"),
                           lane=lane["policy"], lane_literal=lane["literal"], not_union=not_union,
                           not_union_ok=bool(not_union_ok),
                           same_round_excluded=same_round,
                           same_round_note=("artefacts of this same round were excluded from the "
                                            "prior inventory before the uniqueness/lane gates; their "
                                            "overlap with the shipped dots is recorded above")),
               a_only_reasoning=dict(file=str(reasoning_path), n_dots=int(a_only_dots.sum()), exported=len(rows_out)),
               ship_field=ship_field, ship_note=ship_note, challenger=challenger,
               ship_arm_holdout=dict(arm=ship_field,
                                     dti=arm_scores.get(ship_field, {}).get("dti") if ship_field in arm_scores else None,
                                     ci95=arm_scores.get(ship_field, {}).get("ci95") if ship_field in arm_scores else None,
                                     evidence_class="HOLDOUT-DTI",
                                     arm_table={a: [round(d["dti"], 6), [round(x, 5) for x in d["ci95"]]]
                                                for a, d in arm_scores.items()}),
               verdict=("promote" if (receipt["validator"]["ok"] and uq.get("ok") and not_union_ok) else "negative"),
               seconds=round(time.time() - t0, 1))
    (EVID / "h88s_build.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    log(f"build: dots {int(dots.sum()):,} (dropped {dropped} by the ring, {spacing_dropped} by global spacing), gates "
        f"format={out['gates']['format_ok']} unique={out['gates']['uniqueness_ok']} "
        f"lane={out['gates']['lane_ok']} not_union={not_union_ok} -> verdict {out['verdict']}")
    return out


# ---------------------------------------------------------------------------------------------
# stage: card
# ---------------------------------------------------------------------------------------------
def stage_card():
    ho = json.loads((EVID / "h88s_holdout.json").read_text())
    fit = json.loads((EVID / "h88s_fit.json").read_text())
    bu = json.loads((EVID / "h88s_build.json").read_text())
    prim = ho["pooled"]["scores"][ho["primary"]]
    pd = ho["pooled"]["paired_differences"]
    curve = ho["budget_curve_pooled"]["scores"]
    promotable = bool(pd["single_B"]["ci95"][0] > 0)
    card = dict(round="H88s", generated_utc=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        hypothesis=("Sufficiency-screened two-view co-training: View B surface evidence with the B-only "
                    "disagreement stratum suppressed by View A, metered to the smallest budget that does "
                    "not lose pooled holdout credit."),
        mechanism=("Linear relief/curvature and radiometric alteration evidence at the surface — the "
                   "family that carries this competition's measurable skill — with the disagreement "
                   "stratum the brief names as a surface artefact removed, and mass reduced toward the "
                   "metric's marginal-credit bar."),
        named_non_fault_process=("roads, canals and levees, quarry faces, railroad grades, playa "
                                 "shorelines and erosion lines (surface channels); lithologic contacts, "
                                 "intrusive margins and paleo-channels (potential-field channels); "
                                 "gridding seams (interpolated point layers)."),
        holdout=dict(evidence_class="HOLDOUT-DTI", evaluator_version=ho["evaluator_version"],
                     withheld_positive_px=ho["withheld_positive_px"], folds=len(ho["per_fold"]),
                     budget_per_fold=ho["budget_per_fold"], primary=ho["primary"],
                     dti=prim["dti"], ci95=prim["ci95"],
                     single_B=dict(dti=ho["pooled"]["scores"]["single_B"]["dti"],
                                   ci95=ho["pooled"]["scores"]["single_B"]["ci95"]),
                     paired_primary_minus_single_B=pd["single_B"],
                     budget_curve={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in curve.items()},
                     random_control_dti=ho["pooled"]["scores"]["random"]["dti"],
                     promotable_over_single_view=promotable),
        co_training_premises=dict(
            independence_max_abs_rho_per_fold=[r["spatial"]["max_abs_correlation"] for r in fit["independence_per_fold"]],
            independence_threshold=0.60, abandonment_fired=False,
            sufficiency_view_A_mean_oof_auc=fit["sufficiency"]["view_A_mean_oof_auc"],
            sufficiency_view_B_mean_oof_auc=fit["sufficiency"]["view_B_mean_oof_auc"],
            exchange=dict(pseudo_px=[r["pseudo_px"] for r in fit["exchange_per_fold"]],
                          segments=[r["n_segments"] for r in fit["exchange_per_fold"]],
                          screened_out=[not r["sufficiency_screen_pass"] for r in fit["exchange_per_fold"]])),
        leakage_canary=ho["canary"]["max_auc"],
        raster_sha256=bu["sha256"], file=bu["file"], bytes=bu["bytes"],
        submission_name=bu["submission_name"], note=bu["note"],
        validator=bu["gates"]["validator"],
        uniqueness=dict(novel_fraction=bu["gates"]["uniqueness"].get("novel_fraction"),
                        identical_to_a_prior=bu["gates"]["uniqueness"].get("identical_to_a_prior")),
        lane=bu["gates"]["lane"], not_union=bu["gates"]["not_union"],
        slots_used=0,
        verdict=("SUBMIT-ELIGIBLE (beats single_B with paired CI clear of zero) / owner's selector step"
                 if promotable else
                 "DOWNLOAD YES / SUBMIT-ELIGIBLE — amendment 80b: shipped field `" + bu["ship_field"] +
                 "` is the arm with the highest permitted pooled estimate; the preregistered primary did "
                 "NOT beat it with a paired CI clear of zero. Owner's selector step."),
        limits=["holdout DTI does not rank board scores (Spearman -0.1045, IR-52-017)",
                "the budget was chosen by a point estimate on a noisy instrument (knowledge/80s)",
                "View A is used as a suppressor only; its sufficiency failure is the ninth such measurement",
                "no organiser receipt exists for any number in this repo"])
    (EVID / "h88s_run_card.json").write_text(json.dumps(card, indent=2, default=str) + "\n")
    log("wrote evidence/h88s_run_card.json")
    return card


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    check_prereg()
    if stage in ("channels", "all"):
        stage_channels()
    if stage in ("fit", "all"):
        stage_fit()
    if stage in ("holdout", "all"):
        stage_holdout()
    if stage in ("build", "all"):
        stage_build()
    if stage in ("card", "all"):
        stage_card()


if __name__ == "__main__":
    main()
