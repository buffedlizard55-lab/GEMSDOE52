#!/usr/bin/env python3
"""H66 — Thermal-Upflow Corridor (TUC): lane gates, holdout, build, release gates.

One script, one lane, no private fork of any shared instrument.  Everything scored here delegates
to the template's own modules: ``gems52.metric`` (official DTI), ``gems52.holdout`` (folds, visible
masking), ``gems52.evaluate_holdout`` (pooled hide-and-recover evaluator
``gems52-pooled-hide-v1``), ``gems52.spatial`` (label-blind quadrant folds + the fail-closed
negative-error independence diagnostic), ``gems52.emit`` (coverage greedy), ``gems52.gates``
(format + lane uniqueness) and ``gems52.submission_writer`` (fail-closed packaging).

Frozen protocol: ``knowledge/43_hypotheses_H66_preregistered.md``; this script refuses to run if its
SHA-256 has moved since ``registry/h66_preregistration.json`` was written.

Evidence classes are never mixed:
  HOLDOUT-DTI        shared evaluator, hide-and-recover, with a 95 % paired cluster CI.
  PREMISE-AUC        out-of-quadrant AUC of a fitted view; a diagnostic, not a score.
  ORGANIZER-CONFIRMED  only a number copied from a submission-page receipt.  None exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import emit, evaluate_holdout as EH, gates, grid, holdout, metric, spatial, submission_writer  # noqa: E402
from gems52 import transform as T  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work" / "h66"
EVID = ROOT / "evidence"
SUB = ROOT / "submission"
PROTO = ROOT / "knowledge" / "43_hypotheses_H66_preregistered.md"
SEED = 660660
ZERO_TAX_M = 200.0          # R-zero-tax (knowledge/10 §2)
SEED_EXCLUSION_M = 300.0    # a seed must be beyond the whole DTI kernel from any mapped fault
BUFFER_PX = 80              # identical to H61/H63/H64 so PREMISE-AUC stays comparable
S1_MEAN_MIN, S1_FOLD_MIN = 0.60, 0.55
ABANDON_R = 0.60
CANARY_ALARM = 0.90
BUDGETS = (8_000, 15_000, 25_000, 37_654)
CORR_GATE = 0.50
TAPER = {0: 1.00, 1: 0.95, 2: 0.88, 3: 0.80, 4: 0.68, 5: 0.52, 6: 0.40}
HALF_LEN = 6
HALF_WIDTH = 1

# View A: potential field / subsurface, exactly the lane's definition.  Band 6 is NOT here: it is the
# GeoDAWN aeroradiometric total-count grid (N-18, Spearman +1.0000 against the USGS TC grid), so it
# is filed in View B.
VIEW_A_BANDS = (13, 18, 5, 11, 2, 3, 9, 14, 4, 7, 8, 16, 10, 15, 17)
VIEW_B_BANDS = (12, 19, 6)


def log(*a):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _clean(o):
    """JSON cannot carry NaN/inf; replace with None rather than silently writing a number."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def write_receipt(name, obj):
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h66_{name}.json"
    p.write_text(json.dumps(_clean(obj), indent=1, allow_nan=False) + "\n")
    log(f"receipt -> {p.relative_to(ROOT)}")
    return p


def check_prereg():
    reg_path = ROOT / "registry" / "h66_preregistration.json"
    reg = json.loads(reg_path.read_text())
    got = sha(PROTO)
    if got != reg["hypothesis_sha256"]:
        raise SystemExit(f"H66 protocol changed after registration ({got[:12]} != "
                         f"{reg['hypothesis_sha256'][:12]}); refusing to run")
    return reg


# --------------------------------------------------------------------------- inputs
def preflight():
    """Restore receipt + manifest pins re-checked, grid identity, footprint, catalogue geometry."""
    rec = json.loads((DATA / "restore_receipt.json").read_text())
    man = json.loads((ROOT / "registry" / "data_manifest.json").read_text())
    pins = {f["id"]: f for f in man["files"]}
    checked = []
    for r in rec["files"]:
        p = ROOT / r["dest"]
        if not p.exists():
            continue
        f = pins.get(r["id"])
        if not f:
            continue
        d, n = sha(p), p.stat().st_size
        checked.append(dict(id=r["id"], dest=r["dest"], bytes=n, sha256=d, pin_sha256=f["sha256"],
                            pin_bytes=f["bytes"], matches=bool(d == f["sha256"] and n == f["bytes"])))
    bad = [c["id"] for c in checked if not c["matches"]]
    with rasterio.open(DATA / "sample_submission.tif") as ds:
        sample = ds.read(1)
        grid_meta = dict(shape=[ds.height, ds.width], crs=str(ds.crs), transform=list(ds.transform),
                    dtype=str(ds.dtypes[0]),
                    nodata=(None if ds.nodata is None or not np.isfinite(float(ds.nodata))
                            else float(ds.nodata)),
                    nodata_declared_is_nan=bool(ds.nodata is not None and not np.isfinite(float(ds.nodata))))
    with rasterio.open(DATA / "labels.tif") as ds:
        lab_raw = ds.read(1)
        lab_tr = list(ds.transform)
        lab_crs = str(ds.crs)
    cat = lab_raw > 0
    inside = lab_raw >= 0                       # -1 is the organiser's outside-domain code
    with rasterio.open(DATA / "training_features.tif") as ds:
        tf_tr = list(ds.transform)
    # IR-H66-002: the domain carries 3,061 in-domain nodata-sentinel cells (-3.4028234663852886e+38)
    # in 18 of the 19 bands and 3,073 in band 6.  Including them in `eligible` makes
    # transform.rank01 bin against lo = -3.4e38, collapsing every rank channel to a near-constant and
    # silently destroying the fit.  The template's own sentinel-aware intersection footprint is used
    # instead (gems52.grid.footprint_from(..., 'all')), which is what features.build also does.
    feat_ok = grid.footprint_from(DATA / "training_features.tif", bands="all")
    n_sentinel_in_domain = int((inside & ~feat_ok).sum())
    eligible = inside & feat_ok
    d_cat = ndi.distance_transform_edt(~cat, sampling=metric.PIXEL_M).astype(np.float32)
    out = dict(stage="preflight", started_utc=now(), grid=grid_meta,
               labels_transform_matches_sample=bool(lab_tr == grid_meta["transform"]),
               labels_crs_matches_sample=bool(lab_crs == grid_meta["crs"]),
               features_transform_matches_sample=bool(tf_tr == grid_meta["transform"]),
               restore_pins_checked=len(checked), restore_pins_mismatched=bad,
               cells_total=int(cat.size), cells_outside_domain=int((~inside).sum()),
               cells_domain=int(inside.sum()), cells_feature_finite=int(feat_ok.sum()),
               eligible=int(eligible.sum()),
               in_domain_nodata_sentinel_cells=n_sentinel_in_domain,
               sentinel_policy="gems52.grid.footprint_from(bands='all'): in-domain cells carrying the "
                               "-3.4028234663852886e+38 nodata sentinel in any band are excluded from "
                               "eligible, so transform.rank01 can never bin against the sentinel (IR-H66-002)",
               catalogue_px=int(cat.sum()),
               sample_submission_ones=int((sample > 0).sum()),
               sample_equals_catalogue=bool(int((sample > 0).sum()) == int(cat.sum())),
               legal_zero_tax=int((eligible & (d_cat >= ZERO_TAX_M)).sum()),
               champion_reference=None, finished_utc=now())
    ref = DATA / "reference" / "h33-2-b2-zeros.tif"
    if ref.exists():
        with rasterio.open(ref) as ds:
            r = ds.read(1) > 0
        out["champion_reference"] = dict(file=ref.name, sha256=sha(ref), emitted=int(r.sum()),
                                         min_dist_to_catalogue_m=float(d_cat[r].min()),
                                         median_dist_to_catalogue_m=float(np.median(d_cat[r])),
                                         frac_within_zero_tax=float((d_cat[r] < ZERO_TAX_M).mean()),
                                         emitted_inside_eligible=int((r & eligible).sum()))
    write_receipt("preflight", out)
    return dict(sample=sample, grid=grid_meta, cat=cat, eligible=eligible, d_cat=d_cat, pf=out)


def load_bands():
    """Sentinel-aware reads: the competition nodata becomes NaN (gems52.grid.read_band), and the
    LiDAR product's own `valid` band masks its 0-nodata cells."""
    need = sorted(set(VIEW_A_BANDS) | set(VIEW_B_BANDS))
    out = {}
    for b in need:
        out[b] = grid.read_band(DATA / "training_features.tif", b)
    with rasterio.open(DATA / "external" / "lidar_scarp_features_u8.tif") as ds:
        names = list(ds.descriptions)
        arr = ds.read().astype(np.float32)
        lv = arr[names.index("valid")] > 0 if "valid" in names else np.ones(arr.shape[1:], bool)
        for i, nm in enumerate(names):
            a = arr[i]
            a[~lv] = np.nan
            out[f"lidar_{nm}"] = a
    out["_lidar_valid_cells"] = int(lv.sum())
    return out


CH_SRC_BAND = {"grad_b12": 12, "grad_b13": 13, "grad_b15": 15, "grad_b17": 17, "grad_b18": 18,
               "grad_b3": 3, "elev": 12, "slope": 19, "rad_tc": 6, "hess_line": 12, "range5": 12}


def channels(bands, eligible):
    """Declared channel set, as empirical-CDF ranks inside the footprint (float16 to fit in RAM).

    Only ranks are kept: every downstream consumer (design matrix, edge-energy composite,
    corroboration, stratification, canary) is a monotone function of the channel, and 3 GB of RAM
    does not hold both the raw and the ranked copies of 27 full-grid channels.
    """
    rk = {}

    def bands_of(nm):
        if nm in CH_SRC_BAND:
            return bands.get(CH_SRC_BAND[nm])
        if nm.startswith("rank_b"):
            return bands.get(int(nm[6:]))
        if nm.startswith("lidar_"):
            return bands.get(nm)
        return bands.get(nm)

    def put(nm, a):
        rk[nm] = T.rank01(T.fill_outside(np.asarray(a, np.float32), eligible), eligible)\
            .astype(np.float16)

    for b in (12, 13, 15, 17, 18, 3):
        put(f"grad_b{b}", T.gradient_magnitude(bands[b], eligible))
    put("elev", bands[12])
    put("slope", bands[19])
    put("rad_tc", bands[6])
    put("hess_line", T.hessian_line(bands[12], eligible, 300.0))
    b12f = T.fill_outside(bands[12], eligible)
    put("range5", ndi.maximum_filter(b12f, size=5) - ndi.minimum_filter(b12f, size=5))
    for b in VIEW_A_BANDS:
        put(f"rank_b{b}", bands[b])
    for nm in ("step_max", "upface_max", "downface_max", "relief", "coh100", "ex_max"):
        k = f"lidar_{nm}"
        if k in bands:
            put(nm, bands[k])
    # ---- integrity of the ranking, checked rather than assumed ----------------------------------
    # A channel is *degenerate* if the nodata sentinel survived into it (which would put lo at
    # -3.4e38 and collapse every real value into one bin, IR-H66-002) or if it carries fewer than
    # 10 distinct rank levels.  A channel whose minimum rank is ~0.5 is NOT degenerate: it is
    # zero-inflated (more than half the footprint ties at the physical minimum, e.g. band 10
    # distance-to-earthquake and the conductivity gradient), which is a property of the layer and is
    # reported, not failed.
    sanity, degenerate, zero_inflated = {}, [], []
    for k, v in rk.items():
        vv = v[eligible].astype(np.float32)
        lo, hi, mean = float(vv.min()), float(vv.max()), float(vv.mean())
        nlev = int(np.unique(np.round(vv, 4)).size)
        sanity[k] = dict(rank_min=lo, rank_max=hi, rank_mean=mean, distinct_levels_1e4=nlev,
                         raw_abs_max=float(np.nanmax(np.abs(np.asarray(bands_of(k), np.float64)[eligible])))
                         if bands_of(k) is not None else None)
        if nlev < 10 or (sanity[k]["raw_abs_max"] is not None and sanity[k]["raw_abs_max"] > 1e30):
            degenerate.append(k)
        if hi - lo < 0.5:
            zero_inflated.append(k)
        del vv
    return rk, dict(n_channels=len(rk), storage="float16 empirical-CDF rank inside the footprint",
                    rank_summary=sanity, degenerate_channels=degenerate,
                    zero_inflated_channels=zero_inflated,
                    zero_inflated_note="minimum rank ~0.5 because >50% of the footprint ties at the "
                                       "physical minimum; a layer property, not a sentinel collapse",
                    lidar_valid_cells=bands.get("_lidar_valid_cells"))


A_RANK_KEYS = ("grad_b13", "grad_b18", "grad_b3", "grad_b15", "hess_line",
               "rank_b5", "rank_b11", "rank_b2", "rank_b9", "rank_b14", "rank_b4", "rank_b7",
               "rank_b8", "rank_b16", "rank_b10", "rank_b17")
B_RANK_KEYS = ("slope", "elev", "rad_tc", "range5", "step_max", "upface_max", "downface_max",
               "relief", "coh100", "ex_max", "grad_b12")


def design_at(rk, keys, idx):
    """Design matrix on the requested flat indices only; never a full-grid stack (RAM)."""
    ks = [k for k in keys if k in rk]
    X = np.empty((len(idx), len(ks)), np.float32)
    for j, k in enumerate(ks):
        X[:, j] = np.nan_to_num(rk[k].ravel()[idx], nan=0.0).astype(np.float32)
    return X, ks


# --------------------------------------------------------------------------- lane gates S1 / S2 / canary
def fit_views(rk, cat, eligible, folds):
    """OOF out-of-quadrant probability grids for View A and View B (declared learner: logistic)."""
    shape = eligible.shape
    n = int(shape[0]) * int(shape[1])
    oof = {v: np.full(n, np.nan, np.float32) for v in ("A", "B")}
    per_fold = []
    for fold in folds:
        f = fold["fold"]
        region, train = fold["region"], fold["train"]
        catd = ndi.distance_transform_edt(~fold["visible"])
        pos = np.flatnonzero((train & cat).ravel())
        neg = np.flatnonzero((train & ~cat & (catd > 5)).ravel())
        rng = np.random.default_rng(SEED + f)
        pos = rng.choice(pos, min(30_000, len(pos)), replace=False)
        neg = rng.choice(neg, min(90_000, len(neg)), replace=False)
        sel = np.r_[pos, neg]
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        rec = dict(fold=f, n_train_pos=int(len(pos)), n_train_neg=int(len(neg)),
                   receipt=fold["receipt"], aucs={})
        for v, keys in (("A", A_RANK_KEYS), ("B", B_RANK_KEYS)):
            Xs, ks = design_at(rk, keys, sel)
            clf = LogisticRegression(max_iter=800, C=1.0, solver="lbfgs")
            clf.fit(Xs, y)
            del Xs
            ridx = np.flatnonzero(region.ravel())
            oof[v][ridx] = clf.predict_proba(design_at(rk, ks, ridx)[0])[:, 1].astype(np.float32)
            tpos = np.flatnonzero((fold["truth"] & region).ravel())
            tneg = np.flatnonzero((region & ~cat & (catd > 5)).ravel())
            r2 = rng.choice(tpos, min(20_000, len(tpos)), replace=False) if len(tpos) else tpos
            n2 = rng.choice(tneg, min(40_000, len(tneg)), replace=False) if len(tneg) else tneg
            yy = np.r_[np.ones(len(r2)), np.zeros(len(n2))]
            ss = np.r_[oof[v][r2], oof[v][n2]]
            auc = float(roc_auc_score(yy, ss))
            ipos, ineg = pos[:20_000], neg[:20_000]
            pi = clf.predict_proba(design_at(rk, ks, np.r_[ipos, ineg])[0])[:, 1]
            ai = float(roc_auc_score(np.r_[np.ones(len(ipos)), np.zeros(len(ineg))], pi))
            rec["aucs"][v] = dict(oof_auc=auc, in_quadrant_auc=ai, channels=ks)
            log(f"fold {f} view {v}: OOF AUC {auc:.4f}  in-quadrant {ai:.4f}")
        per_fold.append(rec)
    return {v: oof[v].reshape(shape) for v in ("A", "B")}, per_fold


def stage_lane_gates(rk, cat, eligible, folds, d_cat):
    oof, per_fold = fit_views(rk, cat, eligible, folds)
    aucs = {v: [r["aucs"][v]["oof_auc"] for r in per_fold] for v in ("A", "B")}
    s1 = dict(stage="S1_sufficiency", evidence_class="PREMISE-AUC (out-of-quadrant), not a DTI score",
              learner="LogisticRegression(max_iter=800, C=1.0, lbfgs) on rank channels",
              splitter="label-blind-quadrants-v2 (gems52.spatial.folds, buffer_px=80)",
              folds=per_fold, view_A_oof_auc=aucs["A"], view_B_oof_auc=aucs["B"],
              mean_view_A_oof_auc=float(np.mean(aucs["A"])), min_view_A_oof_auc=float(np.min(aucs["A"])),
              mean_view_B_oof_auc=float(np.mean(aucs["B"])), min_view_B_oof_auc=float(np.min(aucs["B"])),
              thresholds=dict(mean_min=S1_MEAN_MIN, fold_min=S1_FOLD_MIN),
              reference_stored=dict(H61_view_A=0.5163, H63_view_A=0.5362, H64_view_A=0.5230,
                                    H61_view_B=0.6843, H63_view_B=0.6862),
              finished_utc=now())
    s1["S1_pass"] = bool(s1["mean_view_A_oof_auc"] >= S1_MEAN_MIN
                         and s1["min_view_A_oof_auc"] >= S1_FOLD_MIN)
    write_receipt("s1_sufficiency", s1)

    # ---- S2 independence: OOF errors on held-out catalogue-zero proxies, per 50 px block ----------
    rows = []
    thr = {}
    for v in ("A", "B"):
        vals = oof[v][eligible & ~cat]
        thr[v] = float(np.quantile(vals[np.isfinite(vals)], 1.0 - 25_000 / max(1, vals.size)))
    for fold in folds:
        catd = ndi.distance_transform_edt(~fold["visible"])
        negmask = fold["region"] & ~cat & (catd > 5) & np.isfinite(oof["A"]) & np.isfinite(oof["B"])
        rows += spatial.negative_block_errors(oof["A"], oof["B"], negmask, fold["fold"],
                                              (thr["A"], thr["B"]), side=50, minimum=32)
    s2 = spatial.independence(rows, threshold=ABANDON_R, min_blocks=20)
    s2.update(stage="S2_independence", thresholds=dict(fixed_budget_quantile=thr, abandon_r=ABANDON_R),
              negative_class="held-out catalogue-zero proxies >=5 px from any visible trace",
              finished_utc=now())
    s2["blocks"] = rows[:400]                      # cap the receipt; the statistic uses all rows
    s2["n_blocks_all"] = len(rows)
    write_receipt("s2_independence", s2)

    # ---- canary: every channel alone on the held-out quadrant ------------------------------------
    can = dict(stage="canary", alarm=CANARY_ALARM, channels=[], finished_utc=now())
    for fold in folds:
        catd = ndi.distance_transform_edt(~fold["visible"])
        pos = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        rng = np.random.default_rng(SEED + 77 + fold["fold"])
        pos = rng.choice(pos, min(8_000, len(pos)), replace=False)
        neg = rng.choice(neg, min(16_000, len(neg)), replace=False)
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        for nm, arr in rk.items():
            flat = arr.ravel()
            s = np.r_[flat[pos], flat[neg]]
            if np.ptp(s) <= 0:
                continue
            a = float(roc_auc_score(y, s))
            can["channels"].append(dict(fold=fold["fold"], channel=nm, auc=max(a, 1 - a),
                                        signed_auc=a))
    mx = max(c["auc"] for c in can["channels"])
    worst = max(can["channels"], key=lambda c: c["auc"])
    can.update(max_single_channel_auc=mx, worst=worst, alarm_fired=bool(mx >= CANARY_ALARM))
    can["channels"] = sorted(can["channels"], key=lambda c: -c["auc"])[:40]
    write_receipt("canary", can)
    return oof, s1, s2, can


# --------------------------------------------------------------------------- TUC emission
def read_sites():
    df = pd.read_csv(DATA / "external" / "gdr_wellspring_in_footprint.csv")
    best = df.groupby(["row", "col"]).agg(
        temp=("temp_c", "max"), q=("geothermquartz_c", "max"), ch=("geothermchalc_c", "max"),
        cat_t=("geothermcat_c", "max"), dist_csv=("dist_known_fault_px", "min"),
        hot=("thermalclass", lambda s: int((s.astype(str).str.strip().str.lower() == "hot").any())),
        warm=("thermalclass", lambda s: int((s.astype(str).str.strip().str.lower() == "warm").any())),
        n_layers=("layer", "nunique"),
        names=("name", lambda s: "; ".join(sorted({str(x) for x in s})[:3]))).reset_index()
    best["res_T"] = best[["q", "ch", "cat_t"]].max(axis=1)
    return best


def seed_table(sites, eligible, d_cat):
    r, c = sites.row.values, sites.col.values
    ok = (r >= 0) & (r < eligible.shape[0]) & (c >= 0) & (c < eligible.shape[1])
    s = sites[ok].copy()
    r, c = s.row.values, s.col.values
    s["in_eligible"] = eligible[r, c]
    s["d_cat_m"] = d_cat[r, c]
    ev = (s.temp >= 60) | (s.res_T >= 100) | (s.hot == 1)
    s["evidence"] = ev
    w = np.select(
        [(s.res_T >= 150) | (s.temp >= 100), (s.res_T >= 120) | (s.temp >= 80),
         (s.res_T >= 100) | (s.temp >= 60)], [1.0, 0.7, 0.45], default=0.30)
    s["w"] = np.where(ev, w, 0.0)
    s["legal_seed"] = ev & s.in_eligible & (s.d_cat_m >= SEED_EXCLUSION_M)
    return s


def strike_field(rk, eligible):
    """Local structural strike + coherence from the structure tensor of a multi-channel edge energy."""
    E = np.mean([rk[k] for k in ("grad_b12", "grad_b3", "grad_b18", "grad_b15") if k in rk], axis=0)
    E = np.nan_to_num(E, nan=0.0).astype(np.float64)
    sig = 4.0
    gy, gx = np.gradient(ndi.gaussian_filter(E, sig))
    Jxx = ndi.gaussian_filter(gx * gx, sig)
    Jyy = ndi.gaussian_filter(gy * gy, sig)
    Jxy = ndi.gaussian_filter(gx * gy, sig)
    theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)          # direction of the *line*, not the gradient
    tr = Jxx + Jyy
    coh = np.sqrt(np.maximum((Jxx - Jyy) ** 2 + 4 * Jxy ** 2, 0)) / np.maximum(tr, 1e-12)
    return E.astype(np.float32), theta.astype(np.float32), coh.astype(np.float32)


def corroboration(rk, eligible):
    keys = [k for k in ("grad_b3", "grad_b18", "grad_b15", "grad_b17", "step_max", "hess_line")
            if k in rk]
    C = np.max([rk[k] for k in keys], axis=0)
    return np.nan_to_num(C, nan=0.0).astype(np.float32), keys


def corridor_pool(seeds, theta, coh, C, legal, taper=TAPER, half_len=HALF_LEN, half_w=HALF_WIDTH):
    """Strike-aligned ribbons around each legal seed, weighted by evidence, taper and corroboration."""
    h, w = legal.shape
    F = np.zeros((h, w), np.float32)
    src = np.zeros((h, w), np.int16)          # how many seeds reach this cell
    s = seeds[seeds.legal_seed]
    rows, cols = s.row.values, s.col.values
    ws = s.w.values.astype(np.float64)
    for t in range(-half_len, half_len + 1):
        tp = taper[abs(t)]
        for q in range(-half_w, half_w + 1):
            dy = t * np.sin(theta[rows, cols]) + q * np.cos(theta[rows, cols])
            dx = t * np.cos(theta[rows, cols]) - q * np.sin(theta[rows, cols])
            yy = np.rint(rows + dy).astype(np.int64)
            xx = np.rint(cols + dx).astype(np.int64)
            m = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
            yy, xx = yy[m], xx[m]
            val = ws[m] * tp * (0.5 + C[yy, xx])
            keep = legal[yy, xx] & (C[yy, xx] >= CORR_GATE)
            yy, xx, val = yy[keep], xx[keep], val[keep]
            np.maximum.at(F, (yy, xx), val)
            np.add.at(src, (yy, xx), 1)
    return F, src


def build_emission(F, legal, budget, dti_projected=0.0):
    allowed = legal & (F > 0)
    pool = int(allowed.sum())
    if pool == 0 or budget == 0:
        return np.zeros(legal.shape, np.float32), dict(pool=pool, emitted=0, budget=budget)
    p, info = emit.greedy_emit(F, allowed, dti_projected=dti_projected, budget=min(budget, pool))
    info.update(pool=pool, budget=int(budget))
    return p.astype(np.float32), info


# --------------------------------------------------------------------------- holdout
def stage_holdout(rk, oof, cat, eligible, sites, theta_coh_C, budget):
    E_theta, coh, C = theta_coh_C
    folds = list(spatial.folds(cat, eligible, buffer_px=BUFFER_PX))
    terms = {}
    per_fold = []
    rng = np.random.default_rng(SEED + 9)
    for fold in folds:
        f = fold["fold"]
        vis = fold["visible"] & eligible
        d_vis = ndi.distance_transform_edt(~vis, sampling=metric.PIXEL_M)   # VISIBLE catalogue only
        legal_f = eligible & (d_vis >= ZERO_TAX_M) & ~vis & fold["region"]
        seeds_f = seed_table(sites, eligible, d_vis)
        F, src = corridor_pool(seeds_f, E_theta, coh, C, legal_f)
        cand, info = build_emission(F, legal_f, budget)
        cand = holdout.mask_visible(cand, vis)
        k = int((cand > 0).sum())
        arms = {"tuc": cand}
        pA = np.nan_to_num(oof["A"], nan=0.0)
        pB = np.nan_to_num(oof["B"], nan=0.0)
        for nm, field in (("single_A", pA), ("single_B", pB), ("union_max", np.maximum(pA, pB)),
                          ("disagreement", np.clip(pA * (1.0 - pB), 0, 1))):
            arms[nm] = holdout.emit_topk(field, legal_f, k)
        rr = np.zeros(legal_f.shape, bool)
        idx = np.flatnonzero(legal_f.ravel())
        pick = rng.choice(idx, min(k, len(idx)), replace=False)
        rr.ravel()[pick] = True
        arms["random"] = rr.astype(np.float32)
        row = dict(fold=f, budget_matched=k, seeds_legal=int(seeds_f.legal_seed.sum()),
                   corridor_pool=info.get("pool"), truth_px=int((fold["truth"] & fold["region"]).sum()),
                   arms={})
        for nm, p in arms.items():
            res, tt = EH.evaluate(p, fold, eligible)
            terms.setdefault(nm, []).append(tt)
            row["arms"][nm] = dict(dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"], fnw=res["fnw"],
                                   emitted=res["emitted"])
        per_fold.append(row)
        log(f"holdout fold {f}: matched budget {k}, tuc DTI {row['arms']['tuc']['dti']:.5f}, "
            f"single_B {row['arms']['single_B']['dti']:.5f}, random {row['arms']['random']['dti']:.5f}")
    # pooled_summary wants ONE (n_blocks, 4) array per arm: contributions from the same physical
    # 20 km block are merged across folds BEFORE resampling (evaluate_holdout docstring).
    merged = {k: np.sum(np.asarray(v, float), axis=0) for k, v in terms.items()}
    pooled = EH.pooled_summary(merged, draws=1000, seed=SEED, candidate="tuc")
    out = dict(stage="holdout", evidence_class="HOLDOUT-DTI",
               evaluator_version=EH.VERSION, implementation_hashes=EH.implementation_hashes(),
               buffer_px=BUFFER_PX, splitter="label-blind-quadrants-v2",
               catalogue_features_recomputed_from="visible catalogue only (per fold)",
               visible_masking="gems52.holdout.mask_visible (pixel-exact)",
               withheld_positives_total=int(sum(r["truth_px"] for r in per_fold)),
               budget=budget, folds=per_fold, pooled=pooled, finished_utc=now())
    write_receipt("holdout", out)
    return out


# --------------------------------------------------------------------------- build + gates
def stratify(emitted, rk, eligible):
    A = np.mean([rk[k] for k in A_RANK_KEYS if k in rk], axis=0)
    B = np.mean([rk[k] for k in B_RANK_KEYS if k in rk], axis=0)
    e = emitted > 0
    conc = e & (A >= 0.7) & (B >= 0.7)
    aonly = e & (A >= 0.7) & (B < 0.5)
    bonly = e & (B >= 0.7) & (A < 0.5)
    neither = e & ~conc & ~aonly & ~bonly
    return dict(A=A, B=B, counts=dict(emitted=int(e.sum()), concordant=int(conc.sum()),
                                      A_only=int(aonly.sum()), B_only=int(bonly.sum()),
                                      neither=int(neither.sum())),
                masks=dict(concordant=conc, A_only=aonly, B_only=bonly, neither=neither))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all")
    ap.add_argument("--budget", type=int, default=0, help="0 = largest the gated pool supports, <=37654")
    ap.add_argument("--name", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)

    t0 = time.time()
    reg = check_prereg()
    log("protocol hash verified:", reg["hypothesis_sha256"][:16])
    WORK.mkdir(parents=True, exist_ok=True)

    pf = preflight()
    cat, eligible, d_cat = pf["cat"], pf["eligible"], pf["d_cat"]
    bands = load_bands()
    rk, chsan = channels(bands, eligible)
    del bands
    if chsan["degenerate_channels"]:
        raise SystemExit(f"degenerate rank channels (sentinel survived or <10 levels): "
                         f"{chsan['degenerate_channels']}")
    log(f"zero-inflated (legitimately, not sentinels): {chsan['zero_inflated_channels']}")
    write_receipt("channels", chsan)
    log(f"channels {len(rk)}; eligible {int(eligible.sum())}; no collapsed rank channels")

    folds = list(spatial.folds(cat, eligible, buffer_px=BUFFER_PX))
    oof, s1, s2, can = stage_lane_gates(rk, cat, eligible, folds, d_cat)
    log(f"S1 pass={s1['S1_pass']} (mean A {s1['mean_view_A_oof_auc']:.4f}); "
        f"S2 max|r|={s2['max_abs_correlation']} measured={s2['measured']} allow={s2['allow_exchange']}; "
        f"canary max={can['max_single_channel_auc']:.4f}")

    E, theta, coh = strike_field(rk, eligible)
    C, ckeys = corroboration(rk, eligible)
    sites = read_sites()
    legal = eligible & (d_cat >= ZERO_TAX_M) & ~cat
    seeds = seed_table(sites, eligible, d_cat)
    F, src = corridor_pool(seeds, theta, coh, C, legal)
    pool = int((legal & (F > 0)).sum())
    log(f"seeds legal {int(seeds.legal_seed.sum())}; corridor pool {pool} px (legal {int(legal.sum())})")

    supported = [b for b in BUDGETS if b <= pool]
    budget = int(min(args.budget or (max(supported) if supported else pool), 37_654, pool))
    curve = []
    for b in supported or [min(pool, 8_000)]:
        p, info = build_emission(F, legal, int(b))
        curve.append(dict(budget=int(b), emitted=int((p > 0).sum()), info=info))
        log(f"budget ladder {b}: emitted {int((p>0).sum())}")
    emitted, info = build_emission(F, legal, budget)
    st = stratify(emitted, rk, eligible)
    # lane rule: B-only with no seed within 3 px is a suspected surface artefact -> veto
    seedmask = np.zeros(emitted.shape, bool)
    s = seeds[seeds.legal_seed]
    seedmask[s.row.values, s.col.values] = True
    near_seed = ndi.binary_dilation(seedmask, iterations=3)
    veto = st["masks"]["B_only"] & ~near_seed
    if veto.any():
        emitted = emitted.copy()
        emitted[veto] = 0.0
    log(f"B-only artefact veto removed {int(veto.sum())} px; emitted {int((emitted>0).sum())}")

    build = dict(stage="build", budget=budget, emitted=int((emitted > 0).sum()),
                 corridor_pool=pool, seeds=dict(total_sites=int(len(sites)),
                                                evidence_sites=int(seeds.evidence.sum()),
                                                legal_seeds=int(seeds.legal_seed.sum()),
                                                blocks_1km=int(len(set(zip((s[s.legal_seed].row // 10).astype(int),
                                                                           (s[s.legal_seed].col // 10).astype(int)))))),
                 corroboration_channels=ckeys, corr_gate=CORR_GATE, taper=TAPER,
                 half_len=HALF_LEN, half_width=HALF_WIDTH, budget_ladder=curve,
                 stratification=st["counts"], vetoed_B_only=int(veto.sum()),
                 strike=dict(sigma_px=4.0, source="structure tensor of the 4-channel edge-energy rank"),
                 min_dist_to_catalogue_m=float(d_cat[emitted > 0].min()) if (emitted > 0).any() else None,
                 median_dist_to_catalogue_m=float(np.median(d_cat[emitted > 0])) if (emitted > 0).any() else None,
                 values=sorted({float(v) for v in np.unique(emitted)}),
                 seconds=round(time.time() - t0, 1), finished_utc=now())
    write_receipt("build", build)

    ho = stage_holdout(rk, oof, cat, eligible, sites, (theta, coh, C), budget)

    # ---- release gates ---------------------------------------------------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = args.name or f"gems52-h66-thermal-upflow-corridor-{build['emitted']}px-{stamp}"
    note = args.note or ("H66 thermal-upflow corridor; strike-aligned; geophysically corroborated; "
                         "off-catalogue >=200 m; research-only")
    note = note[:140]
    outp = SUB / f"{name}.tif"
    # write_submission takes the sample *path* (it delegates to gates.format_report, which opens it)
    receipt = submission_writer.write_submission(outp, emitted, DATA / "sample_submission.tif", eligible,
                                                 note=note, name=name,
                                                 metadata=dict(round="H66", protocol=PROTO.name,
                                                               protocol_sha256=reg["hypothesis_sha256"],
                                                               budget=budget, stratification=st["counts"]))
    log("wrote", outp.name, receipt["sha256"][:16], f"{receipt['bytes']} bytes")

    priors = sorted(str(p) for p in (WORK / "priors").glob("*.tif")) if (WORK / "priors").exists() else []
    prior_fetch = ROOT / "work" / "h66" / "prior_fetch_receipt.json"
    priors = [p for p in priors]
    priors += sorted(str(p) for p in (DATA / "scored").glob("*.tif"))
    priors += sorted(str(p) for p in (DATA / "reference").glob("*.tif"))
    # exclude this round's own earlier builds: an identical decoded pattern in the prior list would
    # be reported as "identical to a prior" and would hide the real comparison
    priors += sorted(str(p) for p in SUB.glob("*.tif")
                     if p != outp and not p.name.startswith("gems52-h66-"))
    lane_s = gates.lane_report(emitted, eligible, priors, sample=str(DATA / "sample_submission.tif"),
                               phase="surface")
    lane_d = gates.lane_report(emitted, eligible, priors, sample=str(DATA / "sample_submission.tif"),
                               phase="dots")
    uniq = gates.uniqueness_report(emitted, priors)
    fmt = gates.format_report(outp, str(DATA / "sample_submission.tif"), footprint=eligible)
    # not merely the union of the two views
    pA = holdout.emit_topk(np.nan_to_num(oof["A"], nan=0.0), legal, build["emitted"])
    pB = holdout.emit_topk(np.nan_to_num(oof["B"], nan=0.0), legal, build["emitted"])
    uni = (pA > 0) | (pB > 0)
    inter = int(((emitted > 0) & uni).sum())
    not_union = dict(union_px=int(uni.sum()), emitted_px=int((emitted > 0).sum()),
                     intersection=inter,
                     fraction_of_emission_inside_union=inter / max(1, int((emitted > 0).sum())),
                     pass_=bool(inter / max(1, int((emitted > 0).sum())) < 0.90))
    release = dict(stage="release", file=receipt["file"], sha256=receipt["sha256"],
                   bytes=receipt["bytes"], submission_name=name, note=note,
                   format=fmt, uniqueness=uniq, not_union=not_union,
                   lane_surface=dict(literal=lane_s["literal"], policy={k: v for k, v in lane_s["policy"].items()
                                      if k != "probe_paths"}, priors_checked=lane_s["priors_checked"],
                                      distinct_decoded_priors=lane_s["distinct_decoded_priors"],
                                      error_count=lane_s["error_count"]),
                   lane_dots=dict(literal={k: v for k, v in lane_d["literal"].items()},
                                  policy={k: v for k, v in lane_d["policy"].items() if k != "probe_paths"},
                                  priors_checked=lane_d["priors_checked"],
                                  error_count=lane_d["error_count"]),
                   holdout_pooled={k: v for k, v in ho["pooled"].items() if k in ("scores", "paired_differences")},
                   seconds=round(time.time() - t0, 1), finished_utc=now())
    write_receipt("release_gates", release)
    log("DONE", json.dumps({k: release[k] for k in ("file", "sha256", "bytes")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
