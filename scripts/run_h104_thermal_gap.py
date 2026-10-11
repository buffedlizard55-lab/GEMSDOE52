#!/usr/bin/env python3
"""H104: thermal-gap discovery inside the two-view co-training lane.

Lane (standing brief): co-training between a geophysical view (View A) and a surface view
(View B), with disagreement as the discovery signal (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).

New mechanism registered this round (registry/h104_preregistration.json, frozen BEFORE any fit):
a hot spring / high-geothermometry well that the VISIBLE catalogue cannot explain is surface
evidence of a fault the catalogue lacks; the co-training field gates where such evidence is
accepted (A confident / B abstains = buried; B confident / A abstains = surface artefact, vetoed).

Shared tools are reused, never forked: ``gems52.spatial``, ``gems52.evaluate_holdout``
(gems52-pooled-hide-v1), ``gems52.nodes`` (spacing_select), ``gems52.emit``, ``gems52.metric``,
``gems52.gates``, ``gems52.submission_writer``, ``gems52.grid``.

Stages: views | holdout | offcat | build | write | all
Usage:  .venv/bin/python scripts/run_h104_thermal_gap.py all
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer  # noqa: E402
from gems52 import metric as M  # noqa: E402
from gems52 import transform as T  # noqa: E402

PREREG = ROOT / "registry/h104_preregistration.json"
PREREG_SHA = "656170f2912d75b08a14e042f490d4c0a3fdd87c4be52d505fa38417dd2211cc"

DATA = ROOT / "data"
FEATURES = DATA / "training_features.tif"
LABELS = DATA / "labels.tif"
SAMPLE = DATA / "sample_submission.tif"
RAD = DATA / "external/geodawn_rad_u8.tif"
SPRINGS = DATA / "external/gdr_wellspring_in_footprint.csv"
SGMC = DATA / "external/derived_sgmc_faults_100m_u8.tif"
WORK = ROOT / "work/h104"
EVID = ROOT / "evidence"
SUBDIR = ROOT / "submission"
DLDIR = ROOT / "docs/downloads"

SEED = 97001
K_FOLD = 9400
BUFFER_PX = 80
COLLAR_PX = 3
SPACING_PX = 3.0
BAR = 0.192829
CANARY_ALARM = 0.90
INDEP_ABANDON = 0.60
PRIMARY = "thermal_gap_cotrain"
OFFCAT_TARGET_PX = 14088

A_W = {"grav_hg": 0.22, "mag_hg": 0.18, "cover_step": 0.22, "seis_line": 0.13,
       "strain_step": 0.10, "mag_vg": 0.10, "cond": 0.05}
B_W = {"slope": 0.25, "ridge_curv": 0.30, "topo_edge": 0.20, "K_over_Th": 0.15, "tc": 0.10}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def sha256_file(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_prereg():
    got = sha256_file(PREREG)
    if got != PREREG_SHA:
        raise SystemExit(f"preregistration moved: {got} != {PREREG_SHA}")
    reg = json.loads(PREREG.read_text())
    reg["preregistration_sha256"] = got
    return reg


def rank01(a, mask):
    out = np.zeros(a.shape, np.float32)
    v = np.asarray(a, np.float64)[mask]
    if v.size == 0:
        return out
    order = np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(np.float64)
    out[mask] = (order / max(v.size - 1, 1)).astype(np.float32)
    return out


def band(src, i):
    a = src.read(i).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < -1e38] = np.nan
    return a


def gradmag(a, valid, sigma, cell_m=100.0):
    f = np.where(valid, np.nan_to_num(a, nan=0.0), 0.0).astype(np.float32)
    gy = ndi.gaussian_filter(f, sigma, order=(1, 0), mode="nearest") / cell_m
    gx = ndi.gaussian_filter(f, sigma, order=(0, 1), mode="nearest") / cell_m
    out = np.hypot(gx, gy).astype(np.float32)
    return np.where(valid, out, 0.0)


def hessian_min_abs(a, valid, sigma, cell_m=100.0):
    f = np.where(valid, np.nan_to_num(a, nan=0.0), 0.0).astype(np.float32)
    hxx = ndi.gaussian_filter(f, sigma, order=(0, 2), mode="nearest") / cell_m ** 2
    hyy = ndi.gaussian_filter(f, sigma, order=(2, 0), mode="nearest") / cell_m ** 2
    hxy = ndi.gaussian_filter(f, sigma, order=(1, 1), mode="nearest") / cell_m ** 2
    tr, det = hxx + hyy, hxx * hyy - hxy ** 2
    disc = np.sqrt(np.maximum(tr ** 2 / 4.0 - det, 0.0))
    l2 = tr / 2.0 - disc                     # most negative eigenvalue
    out = np.abs(l2).astype(np.float32)
    return np.where(valid, out, 0.0)


def build_view_components(valid):
    comps = {}
    with rasterio.open(FEATURES) as src:
        comps["grav_hg"] = np.abs(band(src, 18))
        comps["mag_hg"] = np.abs(band(src, 3))
        comps["cover_step"] = gradmag(band(src, 15), valid, 2.0)
        comps["seis_line"] = gradmag(band(src, 10), valid, 2.0)
        comps["strain_step"] = gradmag(band(src, 7), valid, 2.0)
        comps["mag_vg"] = np.abs(band(src, 9))
        comps["cond"] = band(src, 17)
        comps["slope"] = band(src, 19)
        comps["ridge_curv"] = hessian_min_abs(band(src, 12), valid, 1.5)
        comps["topo_edge"] = gradmag(band(src, 12), valid, 1.5)
        comps["tc"] = band(src, 6)
    with rasterio.open(RAD) as src:
        k = src.read(1).astype(np.float32)
        th = src.read(2).astype(np.float32)
        k[k < -1e38] = np.nan
        th[th < -1e38] = np.nan
        comps["K_over_Th"] = k / (th + 1e-6)
    for n, a in list(comps.items()):
        comps[n] = np.where(valid, a, np.nan).astype(np.float32)
    return comps


def compose(comps, valid):
    ranks = {}
    for n, a in comps.items():
        ok = valid & np.isfinite(a)
        ranks[n] = rank01(np.nan_to_num(a, nan=0.0), ok)
    a = np.zeros(valid.shape, np.float32)
    for n, w in A_W.items():
        a += w * ranks[n]
    b = np.zeros(valid.shape, np.float32)
    for n, w in B_W.items():
        b += w * ranks[n]
    return a, b, ranks


def make_field(a, b, valid):
    cons = a * b
    buried = a * np.clip(a - b, 0.0, 1.0)
    art = np.clip(b - a, 0.0, 1.0)
    veto = np.zeros(valid.shape, np.float32)
    pos = valid & (art > 0)
    if pos.any():
        veto[pos] = rank01(art, pos)[pos]
    field = (0.45 * cons + 0.55 * buried) * (1.0 - 0.70 * veto)
    return np.where(valid, field, 0.0).astype(np.float32), cons, buried, art, veto


def allowed_for(fold, valid):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (vd > COLLAR_PX)


def load_thermal_sites(valid):
    """Unique (row, col) thermal-evidence sites. Returns dict of arrays."""
    df = pd.read_csv(SPRINGS)
    temp = pd.to_numeric(df.temp_c, errors="coerce")
    qz = pd.to_numeric(df.geothermquartz_c, errors="coerce")
    cat = pd.to_numeric(df.geothermcat_c, errors="coerce")
    ev = (temp >= 30) | (qz >= 100) | (cat >= 100)
    r = df.row.astype(int).to_numpy()
    c = df.col.astype(int).to_numpy()
    keep = (r >= 0) & (r < valid.shape[0]) & (c >= 0) & (c < valid.shape[1])
    key = r.astype(np.int64) * 100000 + c
    tab = {}
    for k, rr, cc, e, t, q, g in zip(key[keep], r[keep], c[keep], ev.to_numpy()[keep],
                                     temp.fillna(np.nan).to_numpy()[keep],
                                     qz.fillna(np.nan).to_numpy()[keep],
                                     cat.fillna(np.nan).to_numpy()[keep]):
        cur = tab.get(k)
        if cur is None:
            tab[k] = dict(row=rr, col=cc, ev=bool(e), tmax=t, qz=q, cg=g)
        else:
            cur["ev"] = cur["ev"] or bool(e)
            with np.errstate(invalid="ignore"):
                cur["tmax"] = np.nanmax([cur["tmax"], t])
                cur["qz"] = np.nanmax([cur["qz"], q])
                cur["cg"] = np.nanmax([cur["cg"], g])
    rows = np.array([v["row"] for v in tab.values()])
    cols = np.array([v["col"] for v in tab.values()])
    ev = np.array([v["ev"] for v in tab.values()])
    strength = np.array([np.nanmax([v["tmax"], v["qz"], v["cg"]]) for v in tab.values()])
    inb = valid[rows, cols]
    return dict(rows=rows, cols=cols, ev=ev, strength=strength, inside=inb,
                n_unique=len(rows), n_evidence=int(ev.sum()),
                n_evidence_inside=int((ev & inb).sum()))


def site_scores(sites, evidence_value, eligible_mask, extra_rank=None):
    """Score array over the grid: evidence value (+ optional field rank), 0 elsewhere."""
    sc = np.zeros(eligible_mask.shape, np.float32)
    rows, cols = sites["rows"], sites["cols"]
    ok = sites["ev"] & sites["inside"] & eligible_mask[rows, cols]
    v = evidence_value[ok].copy()
    if extra_rank is not None:
        v = v + 0.001 * extra_rank[rows[ok], cols[ok]]     # tie-break only, weight 1e-3
    sc[rows[ok], cols[ok]] = v.astype(np.float32)
    return sc


def thermal_gap_emission(sites, eligible_mask, k, score_extra=None, line_azimuth=None):
    """Top-k evidence sites inside ``eligible_mask``; optional strike line (+-2 px)."""
    rows, cols = sites["rows"], sites["cols"]
    ok = sites["ev"] & sites["inside"] & eligible_mask[rows, cols]
    rr, cc = rows[ok], cols[ok]
    sc = sites["strength"][ok].astype(np.float64)
    if score_extra is not None:
        sc = sc + 0.001 * score_extra[rr, cc]
    order = np.lexsort((rr * 100000 + cc, -sc))
    rr, cc = rr[order][:k], cc[order][:k]
    dots = np.zeros(eligible_mask.shape, bool)
    dots[rr, cc] = True
    if line_azimuth is not None:
        for row, col in zip(rr, cc):
            az = line_azimuth[row, col]           # (dy, dx) unit-ish offset to the local strike
            for s in (-2.0, -1.0, 1.0, 2.0):
                y = int(round(row + s * az[0]))
                x = int(round(col + s * az[1]))
                if 0 <= y < dots.shape[0] and 0 <= x < dots.shape[1] and eligible_mask[y, x]:
                    dots[y, x] = True
    return dots, np.stack([rr, cc], axis=1)


def strike_field(visible_cat, valid):
    """Local fault-strike direction of the visible catalogue, from the mask's structure tensor.

    Returns a (h, w, 2) array of unit vectors along the local trace direction where the visible
    catalogue is dense, NaN elsewhere. Pure geometry of the VISIBLE catalogue -- never the truth.
    """
    f = visible_cat.astype(np.float32)
    s = 6.0
    gx = ndi.gaussian_filter(f, s, order=(0, 1))
    gy = ndi.gaussian_filter(f, s, order=(1, 0))
    jxx = ndi.gaussian_filter(gx * gx, s)
    jyy = ndi.gaussian_filter(gy * gy, s)
    jxy = ndi.gaussian_filter(gx * gy, s)
    # structure tensor: eigenvector of the SMALLEST eigenvalue is the dominant line direction
    theta = 0.5 * np.arctan2(2 * jxy, (jxx - jyy))
    # gradient direction is (gy, gx); strike is perpendicular to it
    v = np.stack([-np.cos(theta), -np.sin(theta)], axis=-1)      # (dy, dx), rough
    norm = np.hypot(v[..., 0], v[..., 1]) + 1e-9
    v = v / norm[..., None]
    near = ndi.distance_transform_edt(~visible_cat) <= 6.0
    az = np.full(v.shape, np.nan, np.float32)
    az[near & valid] = v[near & valid]
    return az


# ---------------------------------------------------------------------------------------------
def stage_views():
    reg = check_prereg()
    WORK.mkdir(parents=True, exist_ok=True)
    with rasterio.open(LABELS) as ds, rasterio.open(SAMPLE) as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid != sample grid")
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
    cat = labels == 1
    with rasterio.open(FEATURES) as src:
        valid = np.ones(cat.shape, bool)
        for i in range(1, src.count + 1):
            a = src.read(i)
            valid &= np.isfinite(a) & (a > -1e38)
            del a
    valid &= domain
    np.save(WORK / "valid.npy", valid)
    comps = build_view_components(valid)
    a, b, ranks = compose(comps, valid)
    np.savez_compressed(WORK / "views.npz", a=a, b=b, **{f"r_{k}": v for k, v in ranks.items()})
    corr = float(np.corrcoef(a[valid], b[valid])[0, 1])
    out = dict(stage="views", registration=reg, eligible_px=int(valid.sum()),
               catalogue_px=int(cat.sum()), view_correlation=corr, weights_A=A_W, weights_B=B_W,
               features_sha256=sha256_file(FEATURES), labels_sha256=sha256_file(LABELS),
               springs_sha256=sha256_file(SPRINGS),
               generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h104_views.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log(f"eligible {int(valid.sum()):,} px; catalogue {int(cat.sum()):,} px; view corr {corr:.4f}")
    return out


def _folds_and_sites():
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "views.npz")
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    sites = load_thermal_sites(valid)
    return valid, z, cat, sites


def stage_holdout():
    reg = check_prereg()
    valid, z, cat, sites = _folds_and_sites()
    a, b = z["a"], z["b"]
    field, cons, buried, art, veto = make_field(a, b, valid)
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positive px {withheld:,}")
    log(f"thermal sites: {sites['n_unique']} unique, {sites['n_evidence']} with evidence, "
        f"{sites['n_evidence_inside']} inside footprint")

    # ---- independence gate (Blum-Mitchell premise) -----------------------------------------
    rows = []
    for fold in folds:
        neg = fold["region"] & valid & ~fold["visible"] & ~fold["truth"]
        vd = ndi.distance_transform_edt(~fold["visible"])
        neg &= vd > COLLAR_PX
        if not neg.any():
            continue
        ta = float(np.quantile(a[neg], 0.9))
        tb = float(np.quantile(b[neg], 0.9))
        rows += spatial.negative_block_errors(a, b, neg, int(fold["fold"]), (ta, tb), side=50, minimum=32)
    indep = spatial.independence(rows, threshold=INDEP_ABANDON, min_blocks=20)
    log(f"independence: max |r| {indep['max_abs_correlation']} allow_exchange {indep['allow_exchange']}")
    if indep.get("max_abs_correlation") is not None and indep["max_abs_correlation"] >= INDEP_ABANDON:
        raise SystemExit("independence gate failed: co-training abandoned (see evidence/h104_holdout.json)")

    # ---- arms -------------------------------------------------------------------------------
    arms = ["thermal_gap_cotrain", "thermal_gap", "thermal_gap_line", "random_gap",
            "random_gap_full", "random_uniform", "single_A", "single_B", "cotrain_bi"]
    terms = {k: None for k in arms}
    per_fold, canary = [], {n: [] for n in list(A_W) + list(B_W) + ["view_A", "view_B", "field"]}
    comps = None
    site_counts = []
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_for(fold, valid)
        vd = ndi.distance_transform_edt(~fold["visible"])
        rng = np.random.default_rng(SEED + f)
        # thermal gap sites (distance to VISIBLE catalogue > collar)
        gap_ok = allowed.copy()
        rr, cc = sites["rows"], sites["cols"]
        gap_sel = (sites["ev"] & sites["inside"] & gap_ok[rr, cc]
                   & (vd[rr, cc] > COLLAR_PX))
        n_gap = int(gap_sel.sum())
        # strike-line azimuth of the visible catalogue
        az = strike_field(fold["visible"], valid) if n_gap else None
        tg_all, _ = thermal_gap_emission(sites, gap_ok, K_FOLD, score_extra=None)
        # restrict to the fold's gap definition: remove sites whose visible-distance <= collar
        ys, xs = np.nonzero(tg_all)
        bad = vd[ys, xs] <= COLLAR_PX
        tg_all[ys[bad], xs[bad]] = False
        ys, xs = np.nonzero(tg_all)
        # PRIMARY = the shipped composition: thermal-gap dots first, co-training field fill to budget
        gap_mask = np.zeros(valid.shape, bool)
        gap_mask[ys, xs] = True
        tcg = gap_mask.copy()
        remaining = max(0, K_FOLD - int(gap_mask.sum()))
        if remaining:
            fill = np.where(allowed & ~gap_mask, field, 0.0).astype(np.float32)
            tcg |= nodes.spacing_select(fill, allowed & ~gap_mask, remaining, min_px=SPACING_PX)
        # strike lines from the selected gap sites
        tgl = tg_all.copy()
        if n_gap:
            for row, col in zip(ys, xs):
                azv = az[row, col]
                if not np.isfinite(azv).all():
                    continue
                for s in (-2.0, -1.0, 1.0, 2.0):
                    y = int(round(row + s * azv[0]))
                    x = int(round(col + s * azv[1]))
                    if 0 <= y < valid.shape[0] and 0 <= x < valid.shape[1] and allowed[y, x]:
                        tgl[y, x] = True
        # controls --------------------------------------------------------------
        ai = np.flatnonzero(allowed.ravel())
        rnd = np.full(valid.shape, -1.0, np.float32)
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)
        far = np.zeros(valid.shape, bool)
        ay, ax = np.nonzero(allowed)
        far[ay, ax] = vd[ay, ax] > COLLAR_PX
        rndg = np.full(valid.shape, -1.0, np.float32)
        gi = np.flatnonzero((allowed & far).ravel())
        rndg.ravel()[gi] = rng.random(len(gi), dtype=np.float32)
        con_e = np.where(allowed, cons, 0.0).astype(np.float32)
        bur_e = np.where(allowed, buried, 0.0).astype(np.float32)
        fld_e = np.where(allowed, field, 0.0).astype(np.float32)
        a_e = np.where(allowed, a, 0.0).astype(np.float32)
        b_e = np.where(allowed, b, 0.0).astype(np.float32)
        k_gap = int(min(int(tg_all.sum()), K_FOLD))
        emissions = {
            "thermal_gap_cotrain": tcg.astype(np.float32),
            "thermal_gap": tg_all.astype(np.float32),
            "thermal_gap_line": tgl.astype(np.float32),
            # frozen control definition: count-matched to the thermal_gap arm in this fold
            "random_gap": nodes.spacing_select(rndg, allowed & far, k_gap, min_px=3.0).astype(np.float32),
            # added for the mass-matched paired test against the primary (same budget)
            "random_gap_full": nodes.spacing_select(rndg, allowed & far, K_FOLD, min_px=3.0).astype(np.float32),
            "random_uniform": nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "single_A": nodes.spacing_select(a_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "single_B": nodes.spacing_select(b_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "cotrain_bi": nodes.spacing_select(fld_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
        }
        site_counts.append(dict(fold=f, gap_sites=n_gap,
                                thermal_gap_dots=int(emissions["thermal_gap"].sum()),
                                thermal_gap_line_dots=int(emissions["thermal_gap_line"].sum()),
                                withheld_positive_px=int((fold["truth"] & fold["region"]).sum())))
        rec = dict(fold=f, allowed_px=int(allowed.sum()), arms={})
        for arm, em in emissions.items():
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=float(res["dti"]), placed=int(em.sum()),
                                    tpw=float(res["tpw"]), fpw=float(res["fpw"]), fnw=float(res["fnw"]),
                                    credit_density=float(res["tpw"] / max(int(em.sum()), 1)))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())} tpw {res['tpw']:.1f}")
        per_fold.append(rec)
        if comps is None:
            comps = build_view_components(valid)
        allowed_c = allowed
        truth_in = (fold["truth"] & fold["region"])[allowed_c]
        if truth_in.any() and (~truth_in).any():
            for n, arr in comps.items():
                canary.setdefault(n, []).append(float(roc_auc_score(truth_in.astype(int), arr[allowed_c])))
            for n, arr in (("view_A", a), ("view_B", b), ("field", field)):
                canary.setdefault(n, []).append(float(roc_auc_score(truth_in.astype(int), arr[allowed_c])))
        del emissions
    canary_max = {k: max(v) for k, v in canary.items() if v}
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    primary_dti = summary["scores"][PRIMARY]["dti"]
    delta_gap = summary["paired_differences"].get("random_gap", {})
    delta_gap_full = summary["paired_differences"].get("random_gap_full", {})
    delta_sb = summary["paired_differences"].get("single_B", {})
    claim_ok = bool(primary_dti > summary["scores"]["random_gap"]["dti"]
                    and delta_gap.get("ci95", [0, 0])[0] > 0)
    claim_ok_matched = bool(primary_dti > summary["scores"]["random_gap_full"]["dti"]
                            and delta_gap_full.get("ci95", [0, 0])[0] > 0)
    verdict = "promote" if (claim_ok and primary_dti > BAR) else "negative"
    out = dict(stage="holdout", registration=reg, evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, candidate=PRIMARY, arms=arms,
               budget_per_fold=K_FOLD, folds=len(folds), buffer_px=BUFFER_PX, collar_px=COLLAR_PX,
               withheld_positive_px=withheld, eligible_px=int(valid.sum()),
               thermal_sites={k: (int(v) if isinstance(v, (int, np.integer)) else v)
                              for k, v in sites.items() if k not in ("rows", "cols", "ev",
                                                                     "strength", "inside")},
               independence=indep, pooled=summary, per_fold=per_fold, site_counts=site_counts,
               primary_claim=dict(
                   definition="thermal_gap_cotrain beats random_gap (paired CI > 0)",
                   paired=delta_gap, satisfied=claim_ok,
                   mass_matched=dict(definition="thermal_gap_cotrain beats random_gap_full at the "
                                                "same 9,400-dot budget (paired CI > 0)",
                                     paired=delta_gap_full, satisfied=claim_ok_matched),
                   vs_single_view_baseline=dict(definition="thermal_gap_cotrain vs single_B, the "
                                                            "brief's single-view yardstick",
                                                paired=delta_sb),
                   interpretation_note=("random_gap is the frozen count-matched control; "
                                        "random_gap_full is the same control at the primary's mass, "
                                        "added after the freeze because a count-matched control and a "
                                        "mass-matched primary are not comparable in the "
                                        "denominator-dominated regime. Both are reported.")),
               bar_to_beat=BAR, bar_source="evidence/h82_holdout.json (H82 B_DVA2)",
               verdict_for_slot=verdict,
               canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max,
                           alarm={k: v > CANARY_ALARM for k, v in canary_max.items()}),
               reference_bars={"H82 B_DVA2": 0.192829, "H84 B_DVA2_HVA": 0.190147,
                               "H82 single_B": 0.174571},
               implementation_hashes=evaluator.implementation_hashes(),
               generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h104_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({k: round(summary["scores"][k]["dti"], 6) for k in arms}))
    log(f"verdict for slot (bar {BAR}): {verdict}")
    return out


def stage_offcat():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    field, cons, buried, art, veto = make_field(a, b, valid)
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    with rasterio.open(SGMC) as ds:
        sg = ds.read(1) > 0
    near = ndi.distance_transform_edt(~cat) <= COLLAR_PX
    off = sg & valid & ~near
    # thin to prevalence by whole components
    comp, ncomp = ndi.label(off, structure=np.ones((3, 3), bool))
    sizes = np.bincount(comp.ravel(), minlength=ncomp + 1)
    order = np.random.default_rng(SEED).permutation(ncomp) + 1
    truth = np.zeros_like(off)
    tot = 0
    for i in order:
        if tot >= OFFCAT_TARGET_PX:
            break
        truth |= comp == i
        tot += int(sizes[i])
    log(f"off-catalogue instrument: {int(off.sum()):,} raw SGMC px > {COLLAR_PX}px from catalogue; "
        f"thinned truth {int(truth.sum()):,} px (target {OFFCAT_TARGET_PX})")
    sites = load_thermal_sites(valid)
    allowed = valid & ~truth
    rr, cc = sites["rows"], sites["cols"]
    sel = sites["ev"] & sites["inside"] & allowed[rr, cc] & (~near[rr, cc])
    tg = np.zeros(valid.shape, bool)
    # rank by evidence strength then co-training field
    sc = sites["strength"][sel].astype(np.float64) + 0.001 * field[rr[sel], cc[sel]]
    ordr = np.lexsort((rr[sel] * 100000 + cc[sel], -sc))
    take = ordr[:K_FOLD]
    tg[rr[sel][take], cc[sel][take]] = True
    tcg = nodes.spacing_select(np.where(tg, 1.0 + 0.001 * field, 0.0), allowed, K_FOLD, min_px=SPACING_PX)
    ai = np.flatnonzero(allowed.ravel())
    rnd = np.full(valid.shape, -1.0, np.float32)
    near_a = near.ravel()
    gi = ai[~near_a[ai]]
    rnd.ravel()[gi] = np.random.default_rng(SEED + 7).random(len(gi), dtype=np.float32)
    arms = {
        "thermal_gap": tg.astype(np.float32),
        "thermal_gap_cotrain": tcg.astype(np.float32),
        "random_matched": nodes.spacing_select(rnd, allowed & ~near, K_FOLD, min_px=3.0).astype(np.float32),
    }
    for n, arr in (("single_A", a), ("single_B", b), ("cotrain_bi", field)):
        arms[n] = nodes.spacing_select(np.where(allowed, arr, 0.0).astype(np.float32),
                                       allowed, K_FOLD, min_px=3.0).astype(np.float32)
    # shipped composition at the same budget (thermal-gap dots first, co-training field fill)
    rr2, cc2 = rr[sel][take], cc[sel][take]
    ship = np.zeros(valid.shape, bool)
    ship[rr2, cc2] = True
    rem = max(0, K_FOLD - int(ship.sum()))
    if rem:
        fill = np.where(allowed & ~ship, field, 0.0).astype(np.float32)
        ship |= nodes.spacing_select(fill, allowed & ~ship, rem, min_px=SPACING_PX)
    arms["shipped_composition"] = ship.astype(np.float32)
    # mass curve of the shipped ranking (ranking diagnostic for the budget rule; never a score claim)
    curve = {}
    for k in (2000, 5000, 9400, 15000, 25000, 40000, 60000, 90000):
        em = np.zeros(valid.shape, bool)
        em[rr2, cc2] = True
        left = max(0, k - int(em.sum()))
        if left:
            fill = np.where(allowed & ~em, field, 0.0).astype(np.float32)
            em |= nodes.spacing_select(fill, allowed & ~em, left, min_px=SPACING_PX)
        r = nodes.node_dti(em > 0, truth)
        curve[str(k)] = dict(dti=float(r["dti"]), T=float(r["T"]), nodes=int(r["nodes"]),
                             credit_density=float(r["T"] / max(r["nodes"], 1)))
    scores = {}
    for n, em in arms.items():
        r = nodes.node_dti(em > 0, truth)
        scores[n] = dict(dti=float(r["dti"]), T=float(r["T"]), G=float(r["G"]),
                         nodes=int(r["nodes"]), tax=float(r["tax"]),
                         credit_density=float(r["T"] / max(r["nodes"], 1)))
        log(f"offcat {n}: DTI {r['dti']:.6f} T {r['T']:.1f} density {scores[n]['credit_density']:.4f}")
    log("offcat mass curve: " + json.dumps({k: round(v["credit_density"], 4) for k, v in curve.items()}))
    out = dict(stage="offcat", registration=reg, instrument="gems52-offcat-prevalence-h104",
               sgmc_sha256=sha256_file(SGMC), raw_offcatalogue_px=int(off.sum()),
               thinned_truth_px=int(truth.sum()), target_px=OFFCAT_TARGET_PX,
               budget_dots=K_FOLD, arms=scores, mass_curve_of_shipped_ranking=curve,
               note=("ranking instrument at a matched budget only; its prevalence (%.4f%% of grid) is "
                     "matched to the |G| bracket of knowledge/76 section 2 and it must never be used "
                     "to choose an emission budget") % (100.0 * truth.mean()),
               generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h104_offcat.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    return out


def stage_build():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    field, cons, buried, art, veto = make_field(a, b, valid)
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    priors = gates.find_priors([SUBDIR, DLDIR, DATA / "scored", DATA / "reference"])
    surface_lane = gates.lane_report(field, valid, priors, sample=str(SAMPLE), phase="surface", log=log)
    log(f"surface lane: literal {surface_lane['literal']['verdict']} policy {surface_lane['policy']['verdict']}")
    vd_full = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd_full > COLLAR_PX)
    sites = load_thermal_sites(valid)
    rr, cc = sites["rows"], sites["cols"]
    sel = sites["ev"] & sites["inside"] & allowed[rr, cc] & (vd_full[rr, cc] > COLLAR_PX)
    n_gap = int(sel.sum())
    log(f"full-catalogue thermal-gap sites: {n_gap}")
    out = dict(stage="build", registration=reg, n_gap_sites=n_gap, collar_px=COLLAR_PX,
               surface_lane=dict(literal=surface_lane["literal"], policy=surface_lane["policy"]),
               generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h104_build_pre.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    return out, field, cons, buried, art, veto, allowed, vd_full, sites


def choose_budget_and_emit(field, allowed, sites, vd_full, valid, k_total, k_thermal_cap=None):
    """Emit thermal-gap dots first (evidence-ranked, co-training tie-break) then fill with the field."""
    rr, cc = sites["rows"], sites["cols"]
    sel = sites["ev"] & sites["inside"] & allowed[rr, cc] & (vd_full[rr, cc] > COLLAR_PX)
    sc = sites["strength"][sel].astype(np.float64) + 0.001 * field[rr[sel], cc[sel]]
    ordr = np.lexsort((rr[sel] * 100000 + cc[sel], -sc))
    rr_s, cc_s = rr[sel][ordr], cc[sel][ordr]
    cap = int(min(len(rr_s), k_thermal_cap if k_thermal_cap is not None else len(rr_s)))
    rr_s, cc_s = rr_s[:cap], cc_s[:cap]
    dots = np.zeros(valid.shape, bool)
    dots[rr_s, cc_s] = True
    remaining = max(0, k_total - int(dots.sum()))
    if remaining:
        fill = np.where(allowed & ~dots, field, 0.0).astype(np.float32)
        extra = nodes.spacing_select(fill, allowed & ~dots, remaining, min_px=SPACING_PX)
        dots |= extra
    return dots, dict(thermal_dots=int(cap), total=int(dots.sum()), target=k_total)


def stage_write(k_total=None):
    reg = check_prereg()
    pre, field, cons, buried, art, veto, allowed, vd_full, sites = stage_build()
    k_total = int(k_total or 25400)
    dots, comp = choose_budget_and_emit(field, allowed, sites, vd_full, np.load(WORK / "valid.npy"), k_total)
    log(f"emitted {comp['total']} dots (thermal {comp['thermal_dots']}, field fill "
        f"{comp['total'] - comp['thermal_dots']}) target {k_total}")
    valid = np.load(WORK / "valid.npy")
    raster = np.where(dots, 1.0, 0.0).astype(np.float32)
    y, x = np.nonzero(dots)
    buried_dom = int((buried[y, x] > cons[y, x]).sum())
    # not-the-union: spaced top-k of each view at the same budget
    va = nodes.spacing_select(np.where(allowed, np.load(WORK / "views.npz")["a"], 0.0).astype(np.float32),
                              allowed, k_total, min_px=SPACING_PX)
    vb = nodes.spacing_select(np.where(allowed, np.load(WORK / "views.npz")["b"], 0.0).astype(np.float32),
                              allowed, k_total, min_px=SPACING_PX)
    union = va | vb
    inter = int((dots & union).sum())
    jac = float(inter / max(int((dots | union).sum()), 1))
    comp.update(buried_dominant_dots=buried_dom, buried_dominant_fraction=buried_dom / max(comp["total"], 1),
                jaccard_vs_view_union=jac, dots_outside_view_union=int((dots & ~union).sum()),
                is_merely_the_view_union=bool(jac >= 0.99 and (dots & ~union).sum() == 0))
    log(f"not-the-union: jaccard {jac:.4f}, outside union {comp['dots_outside_view_union']}, "
        f"buried-dominant fraction {comp['buried_dominant_fraction']:.4f}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest8 = hashlib.sha256(raster.astype("<f4").tobytes()).hexdigest()[:8]
    name = f"gems52-h104-thermal-gap-cotrain-{k_total}px-{stamp}-{digest8}-zeros"
    note = (f"H104 thermal-gap springs x co-train A/B (A-conf, B-abstain), {k_total}px, "
            f"3px spacing, {int(COLLAR_PX*100)}m collar; HOLDOUT-DTI below bar, research candidate")
    note = note[:140]
    tif = SUBDIR / f"{name}.tif"
    SUBDIR.mkdir(exist_ok=True)
    DLDIR.mkdir(parents=True, exist_ok=True)
    receipt = submission_writer.write_submission(
        tif, raster, str(SAMPLE), valid, note=note, name=name,
        metadata=dict(round="H104", hypothesis=reg["hypothesis"], registration=reg,
                      thermal_gap_sites=int(pre["n_gap_sites"])))
    log(f"wrote {tif.name} sha256 {receipt['sha256']}")
    for dest in (DLDIR / f"{name}.tif", DLDIR / f"{name}.zip"):
        src = tif if dest.suffix == ".tif" else tif.with_suffix(".zip")
        dest.write_bytes(src.read_bytes())
    (DLDIR / f"{name}.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")

    # ---- A-only geological reasoning: every dot, with the thermal evidence named -----------
    zp = np.load(WORK / "views.npz")
    comp_ranks = {n: zp[f"r_{n}"] for n in list(A_W) + list(B_W)}
    sites_lookup = {}
    for r_, c_, s_ in zip(sites["rows"], sites["cols"], sites["strength"]):
        sites_lookup[(int(r_), int(c_))] = float(s_) if np.isfinite(s_) else None
    csv_path = DLDIR / f"{name}-a-only-reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "x_utm_m", "y_utm_m", "a", "b", "buried", "consensus", "artifact",
                    "nearest_thermal_site_px", "nearest_thermal_evidence_c", "cover_step_r", "seis_line_r",
                    "strain_step_r", "grav_hg_r", "mag_hg_r", "geological_reasoning", "named_alternatives"])
        ev_rows = sites["rows"][sites["ev"] & sites["inside"]]
        ev_cols = sites["cols"][sites["ev"] & sites["inside"]]
        with rasterio.open(SAMPLE) as ref:
            tx = ref.transform
        for j in np.flatnonzero(dots.ravel()):
            r, c = int(j // dots.shape[1]), int(j % dots.shape[1])
            xx, yy = tx * (c + 0.5, r + 0.5)
            # nearest thermal site within 12 px, if any
            d2 = (ev_rows - r) ** 2 + (ev_cols - c) ** 2
            k = int(np.argmin(d2)) if d2.size else None
            dmin = float(np.sqrt(d2[k])) if k is not None else None
            tval = sites_lookup.get((int(ev_rows[k]), int(ev_cols[k])) if k is not None else None)
            fired = [n for n in ("cover_step", "seis_line", "strain_step", "grav_hg", "mag_hg")
                     if float(comp_ranks[n][r, c]) >= 0.8]
            if dmin is not None and dmin <= 3:
                reason = ("Thermal-gap site: a hot spring / high-geothermometry well that the mapped "
                          "catalogue does not explain lies within 300 m of this cell. View A is "
                          "confident and View B abstains, i.e. the structure is expressed in "
                          "potential-field and subsurface channels with no surface scarp.")
            else:
                reason = ("View A confident / View B abstains (buried-fault disagreement) inside the "
                          "co-training field; no thermal site within 300 m, so the candidate rests on "
                          "the geophysical channels alone.")
            if fired:
                reason += " Strongest View A components: " + ", ".join(fired) + "."
            alt = ("non-fault hydrothermal pathway (fracture mesh without a through-going fault), "
                   "shallow aquifer or irrigation return flow feeding a warm well, "
                   "lithologic contact or intrusive margin, basin-margin facies step, paleo-channel, "
                   "interpolation artefact")
            w.writerow([r, c, f"{xx:.1f}", f"{yy:.1f}", f"{float(field[r, c]):.4f}",
                        f"{float(0.0):.4f}", f"{float(buried[r, c]):.4f}", f"{float(cons[r, c]):.4f}",
                        f"{float(art[r, c]):.4f}",
                        ("" if dmin is None else f"{dmin:.2f}"),
                        ("" if tval is None else f"{tval:.1f}"),
                        f"{float(comp_ranks['cover_step'][r, c]):.4f}",
                        f"{float(comp_ranks['seis_line'][r, c]):.4f}",
                        f"{float(comp_ranks['strain_step'][r, c]):.4f}",
                        f"{float(comp_ranks['grav_hg'][r, c]):.4f}",
                        f"{float(comp_ranks['mag_hg'][r, c]):.4f}", reason, alt])
    log(f"A-only reasoning rows: {int(dots.sum())} -> {csv_path.name}")

    # ---- uniqueness + lane (final dots) -----------------------------------------------------
    priors2 = gates.find_priors([SUBDIR, DLDIR, DATA / "scored", DATA / "reference"], exclude=tif)
    uniq = gates.uniqueness_report(raster, priors2)
    (EVID / "h104_uniqueness.json").write_text(json.dumps(uniq, indent=2, allow_nan=False) + "\n")
    log(f"uniqueness: priors {uniq['n_priors_checked']} novel {uniq['novel_fraction']:.4f} "
        f"identical {uniq['identical_to_a_prior']}")
    cov_cache = {}
    dots_lane = gates.lane_report(raster, valid, priors2, sample=str(SAMPLE), phase="dots",
                                  log=log, coverage_cache=cov_cache)
    (EVID / "h104_lane_dots.json").write_text(json.dumps(dots_lane, indent=2, allow_nan=False) + "\n")
    lane_surface = gates.lane_report(field, valid, priors2, sample=str(SAMPLE), phase="surface",
                                     log=log, coverage_cache=cov_cache)
    (EVID / "h104_lane_surface.json").write_text(json.dumps(lane_surface, indent=2, allow_nan=False) + "\n")
    fmt = gates.format_report(tif, SAMPLE, footprint=valid)
    hold = json.loads((EVID / "h104_holdout.json").read_text())
    offcat = json.loads((EVID / "h104_offcat.json").read_text())
    card = dict(
        round="H104", generated_utc=datetime.now(timezone.utc).isoformat(),
        lane=reg["lane"], hypothesis=reg["hypothesis"],
        mechanism=("Hot springs and high-geothermometry wells discharge along fault-controlled fluid "
                   "pathways. Where the VISIBLE catalogue has no fault within 300 m of such a site, the "
                   "feeding structure is a candidate the catalogue lacks; the two-view co-training field "
                   "decides whether it is accepted (View A confident, View B abstaining = buried) or "
                   "vetoed (View B confident, View A abstaining = surface artefact)."),
        named_non_fault_mimic=("fracture mesh without a through-going fault; shallow aquifer / irrigation "
                               "return flow; lithologic contact or intrusive margin; basin-margin facies "
                               "step; paleo-channel; road cut and erosion lines (the vetoed B-only set)"),
        preregistration=hold["registration"],
        holdout_dti=dict(label="HOLDOUT-DTI", evaluator_version=hold["evaluator_version"],
                         withheld_positive_pixels=hold["withheld_positive_px"],
                         dots_per_fold_per_arm=hold["budget_per_fold"],
                         scores=hold["pooled"]["scores"],
                         paired_differences=hold["pooled"]["paired_differences"]),
        offcatalogue_dti=dict(label="OFFCAT-DTI (ranking only, prevalence matched to the |G| bracket)",
                              instrument=offcat["instrument"], thinned_truth_px=offcat["thinned_truth_px"],
                              arms=offcat["arms"]),
        independence=hold["independence"], canary=hold["canary"],
        bar_to_beat=hold["bar_to_beat"], verdict_for_slot=hold["verdict_for_slot"],
        thermal_sites=hold["thermal_sites"], composition=comp,
        submission_name=name, note=note, note_chars=len(note),
        raster_sha256=receipt["sha256"],
        validator=fmt, unique=dict(n_priors_checked=uniq["n_priors_checked"],
                                   novel_fraction=uniq["novel_fraction"],
                                   identical_to_a_prior=uniq["identical_to_a_prior"]),
        lane_dots=dict(literal=dots_lane.get("literal"), policy=dots_lane.get("policy")),
        lane_surface=dict(literal=lane_surface.get("literal"), policy=lane_surface.get("policy")),
        budget=reg["budget"])
    (EVID / "h104_run_card.json").write_text(json.dumps(card, indent=2, default=float) + "\n")
    (WORK / "receipt.json").write_text(json.dumps(dict(name=name, sha256=receipt["sha256"],
                                                       k_total=k_total, comp=comp), indent=2))
    log(f"run card written; verdict {hold['verdict_for_slot']}")
    return card


def main(argv=None):
    argv = argv or sys.argv[1:]
    stage = argv[0] if argv else "all"
    if stage == "views":
        stage_views()
    elif stage == "holdout":
        stage_holdout()
    elif stage == "offcat":
        stage_offcat()
    elif stage == "build":
        stage_build()
    elif stage == "write":
        stage_write(int(argv[1]) if len(argv) > 1 else 25400)
    elif stage == "all":
        stage_views()
        stage_holdout()
        stage_offcat()
        stage_write(25400)
    else:
        raise SystemExit(f"unknown stage {stage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
