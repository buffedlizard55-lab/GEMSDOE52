#!/usr/bin/env python3
"""H88: bidirectional co-training disagreement (View A geophysical, View B surface).

Lane (the session's assigned method paragraph, standing brief): co-training between a
geophysical view and a surface view, with disagreement as the discovery signal
(Blum & Mitchell, COLT '98, pp. 92-100, doi:10.1145/279943.279962).

Frozen BEFORE any fit in registry/h88_preregistration.json (sha256
0f664c43f166264864c3815d31a9230f5b95b257a426d4670a8b5ed7c78f7094) plus the pre-fit veto
amendment registry/h88_amendment_veto.json (sha256
91f74c5a5e4c730e826b91ae0731bf58883779af6753238e839e1c6ae8a84785).  This runner refuses to
start if either hash has moved.

Shared tools are reused, never forked: ``gems52.spatial`` (whole-component folds,
negative_block_errors, independence, whole_pseudo_segments), ``gems52.evaluate_holdout``
(gems52-pooled-hide-v1), ``gems52.nodes.spacing_select``, ``gems52.gates``,
``gems52.submission_writer``.

Stages (each checkpointed to work/h88 and evidence/h88_*.json):
    views     View A / View B composites from restored bytes (catalogue-free fields)
    holdout   independence gate + leakage canaries + 6 arms x 4 folds + mass-lever budget curve
    build     full-catalogue field, S=25,400 mass-lever dots, 3 px spacing, 200 m collar
    write     GeoTIFF via submission_writer, uniqueness, lane (surface + dots), not-the-union,
              A-only geological reasoning CSV, run card

Usage: .venv/bin/python scripts/run_h88_cotrain_bidir.py [views|holdout|build|write|all]
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rasterio  # noqa: E402
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer  # noqa: E402

PREREG = ROOT / "registry/h88_preregistration.json"
AMEND = ROOT / "registry/h88_amendment_veto.json"
PREREG_SHA = "0f664c43f166264864c3815d31a9230f5b95b257a426d4670a8b5ed7c78f7094"
AMEND_SHA = "91f74c5a5e4c730e826b91ae0731bf58883779af6753238e839e1c6ae8a84785"

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
RAD = ROOT / "data/external/geodawn_rad_u8.tif"
WORK = ROOT / "work/h88"
EVID = ROOT / "evidence"
SUBDIR = ROOT / "submission"
DLDIR = ROOT / "docs/downloads"

SEED = 88001
K_FOLD = 9400            # matched budget of every comparable receipt
K_FOLD_MASS = 6350       # mass-lever arm: 4 x 6,350 = 25,400
S_SHIP = 25400           # shipped mass (knowledge/76 section 3)
RING_PX = 2              # 200 m / 100 m cells
BUFFER_PX = 80           # spatial.folds buffer (registry/h61 thresholds)
CANARY_ALARM = 0.90
INDEP_ABANDON = 0.60
PRIMARY = "cotrain_bi"
BAR = 0.192829           # HOLDOUT-DTI bar to beat for promotion (H82 B_DVA2, evidence/h82_holdout.json)

# component weights (frozen in the registration; views are rank-01-normalised first)
A_W = {"grav_hg": 0.22, "mag_hg": 0.18, "cover_step": 0.22, "seis_line": 0.13,
       "strain_step": 0.10, "mag_vg": 0.10, "cond": 0.05}
B_W = {"slope": 0.25, "ridge_curv": 0.30, "topo_edge": 0.20, "K_over_Th": 0.15, "tc": 0.10}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_prereg():
    got_p = sha256_file(PREREG)
    got_a = sha256_file(AMEND)
    if got_p != PREREG_SHA or got_a != AMEND_SHA:
        raise SystemExit(f"pre-registration hash moved: {got_p} / {got_a}; refusing to run")
    return {"preregistration_sha256": got_p, "amendment_sha256": got_a,
            "frozen_before_any_fit": True}


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """0..1 rank inside mask (ties broken by flat index), 0 outside."""
    out = np.zeros(a.shape, np.float32)
    v = a[mask]
    if v.size == 0:
        return out
    out[mask] = np.argsort(np.argsort(v)).astype(np.float32) / max(v.size - 1, 1)
    return out


def clean(band: np.ndarray) -> np.ndarray:
    b = np.asarray(band, np.float32).copy()
    b[~np.isfinite(b)] = 0.0
    b[b < -1e38] = 0.0
    return b


def smooth_normalized(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    good = valid & np.isfinite(a)
    num = ndi.gaussian_filter(np.where(good, a, 0.0).astype(np.float64), sigma,
                              mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float64), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8).astype(np.float32)


def gradmag(a: np.ndarray, valid: np.ndarray, sigma: float, cell_m: float = 100.0) -> np.ndarray:
    s = smooth_normalized(a, valid, sigma)
    gy, gx = np.gradient(s, cell_m)
    return np.sqrt(gx * gx + gy * gy).astype(np.float32)


def hessian_min_abs(a: np.ndarray, valid: np.ndarray, sigma: float, cell_m: float = 100.0):
    s = smooth_normalized(a, valid, sigma)
    gyy = np.gradient(np.gradient(s, cell_m, axis=0), cell_m, axis=0)
    gxx = np.gradient(np.gradient(s, cell_m, axis=1), cell_m, axis=1)
    gyx = np.gradient(np.gradient(s, cell_m, axis=0), cell_m, axis=1)
    trace, det = gyy + gxx, gyy * gxx - gyx * gyx
    disc = np.sqrt(np.maximum(0.25 * trace * trace - det, 0.0))
    lam_min = 0.5 * trace - disc
    return np.abs(lam_min).astype(np.float32)


def band(src, i):
    return clean(src.read(i))


def build_views(valid: np.ndarray, want: dict | None = None):
    """Catalogue-free View A / View B composites, plus the component ranks (for canaries/reasoning)."""
    comps = {}
    with rasterio.open(FEATURES) as src:
        # View A
        comps["grav_hg"] = np.abs(band(src, 18))
        comps["mag_hg"] = np.abs(band(src, 3))
        log("A: gravity/magnetic horizontal gradients done")
        b15 = band(src, 15)
        comps["cover_step"] = gradmag(b15, valid, 2.0)
        del b15
        log("A: cover-thickness step (band 15 gradient, sigma=2 px) done")
        b10 = band(src, 10)
        comps["seis_line"] = gradmag(b10, valid, 2.0)
        del b10
        log("A: seismicity lineation (band 10 gradient) done")
        b7 = band(src, 7)
        comps["strain_step"] = gradmag(b7, valid, 2.0)
        del b7
        log("A: strain step (band 7 gradient) done")
        comps["mag_vg"] = np.abs(band(src, 9))
        comps["cond"] = band(src, 17)
        # View B
        comps["slope"] = band(src, 19)
        b12 = band(src, 12)
        comps["ridge_curv"] = hessian_min_abs(b12, valid, 1.5)
        comps["topo_edge"] = gradmag(b12, valid, 1.5)
        del b12
        log("B: ridge curvature + topographic edge done")
        comps["tc"] = band(src, 6)   # radiometric total count by bytes (IR-52-019)
    # K/Th from GeoDAWN radiometrics (manifest: rad_u8 band 1 = K, band 2 = Th)
    with rasterio.open(RAD) as src:
        k = src.read(1).astype(np.float32) / 255.0
        th = src.read(2).astype(np.float32) / 255.0
    k[~np.isfinite(k)] = 0.0
    th[~np.isfinite(th)] = 0.0
    comps["K_over_Th"] = k / (th + 1e-3)
    log("B: K/Th ratio done")

    if want:  # canary stage may request single components only
        return {n: comps[n] for n in want}

    a = np.zeros(valid.shape, np.float32)
    for n, w in A_W.items():
        a += np.float32(w) * rank01(comps[n], valid)
        del comps[n]
    log("View A composite done")
    b = np.zeros(valid.shape, np.float32)
    for n, w in B_W.items():
        b += np.float32(w) * rank01(comps[n], valid)
        del comps[n]
    log("View B composite done")
    return rank01(a, valid), rank01(b, valid)


def make_field(a: np.ndarray, b: np.ndarray, valid: np.ndarray):
    """Bidirectional disagreement field (amended veto on positive support only)."""
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
    return fold["region"] & valid & ~fold["visible"] & (vd > RING_PX)


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
            arr = src.read(i)
            valid &= np.isfinite(arr) & (arr > -1e38)
            del arr
    valid &= domain
    np.save(WORK / "valid.npy", valid)
    log(f"eligible {int(valid.sum()):,} px; catalogue {int(cat.sum()):,} px")
    a, b = build_views(valid)
    np.savez_compressed(WORK / "views.npz", a=a, b=b)
    corr = float(np.corrcoef(a[valid], b[valid])[0, 1])
    out = dict(stage="views", registration=reg, eligible_px=int(valid.sum()),
               catalogue_px=int(cat.sum()), view_correlation=float(corr),
               weights_A=A_W, weights_B=B_W,
               features_sha256=sha256_file(FEATURES), labels_sha256=sha256_file(LABELS),
               rad_sha256=sha256_file(RAD), generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h88_views.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log(f"view correlation {corr:.4f} (diagnostic; the independence gate uses OOF negative errors)")
    return out


def stage_holdout():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    field, cons, buried, art, veto = make_field(a, b, valid)
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positive px {withheld:,}")

    # ---- independence gate: spatial-block OOF errors on labelled negatives ----------------
    rows = []
    for fold in folds:
        neg = fold["region"] & valid & ~fold["visible"] & ~fold["truth"]
        vd = ndi.distance_transform_edt(~fold["visible"])
        neg &= vd > RING_PX
        if not neg.any():
            continue
        ta = float(np.quantile(a[neg], 0.9))
        tb = float(np.quantile(b[neg], 0.9))
        rows += spatial.negative_block_errors(a, b, neg, int(fold["fold"]), (ta, tb),
                                              side=50, minimum=32)
    indep = spatial.independence(rows, threshold=INDEP_ABANDON, min_blocks=20)
    log(f"independence: max |r| {indep['max_abs_correlation']}, allow_exchange {indep['allow_exchange']}, "
        f"reason: {indep['reason']}")
    if indep.get("max_abs_correlation") is not None and indep["max_abs_correlation"] >= INDEP_ABANDON:
        out = dict(stage="holdout", registration=reg, independence=indep,
                   verdict="ABANDONED: view errors strongly correlated; co-training abandoned per the brief",
                   generated_utc=datetime.now(timezone.utc).isoformat())
        (EVID / "h88_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
        raise SystemExit("independence gate failed: co-training abandoned (see evidence/h88_holdout.json)")

    # ---- pseudo-label diagnostic (whole segments, buffered): count only, no exchange -------
    forbidden = cat.copy()
    vd_all = ndi.distance_transform_edt(~cat)
    train = valid & ~cat & (vd_all > RING_PX)
    _idx, receipts = spatial.whole_pseudo_segments(
        a, b, train, forbidden, donor_threshold=0.90, receiver_lo=0.20, receiver_hi=0.60,
        side=50, min_pixels=5, cap=2000)
    n_segs, n_seg_px = len(receipts), int(_idx.size)
    log(f"whole-segment A-confident/B-abstain pseudo-label candidates (diagnostic only): "
        f"{n_segs} segments, {n_seg_px} px")

    # ---- arms x folds at matched budget + mass-lever budget curve --------------------------
    arms = ("cotrain_bi", "consensus_only", "buried_only", "single_A", "single_B", "random")
    terms = {a_: None for a_ in arms}
    terms_mass = {a_: None for a_ in ("cotrain_bi", "single_B", "random")}
    per_fold, canary = [], {n: [] for n in list(A_W) + list(B_W) + ["view_A", "view_B", "field"]}
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_for(fold, valid)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)
        cons_e = np.where(allowed, cons, 0.0).astype(np.float32)
        bur_e = np.where(allowed, buried, 0.0).astype(np.float32)
        fld_e = np.where(allowed, field, 0.0).astype(np.float32)
        a_e = np.where(allowed, a, 0.0).astype(np.float32)
        b_e = np.where(allowed, b, 0.0).astype(np.float32)
        emissions = {
            "cotrain_bi": nodes.spacing_select(fld_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "consensus_only": nodes.spacing_select(cons_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "buried_only": nodes.spacing_select(bur_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "single_A": nodes.spacing_select(a_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "single_B": nodes.spacing_select(b_e, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "random": nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0).astype(np.float32),
        }
        emissions_mass = {
            "cotrain_bi": nodes.spacing_select(fld_e, allowed, K_FOLD_MASS, min_px=3.0).astype(np.float32),
            "single_B": nodes.spacing_select(b_e, allowed, K_FOLD_MASS, min_px=3.0).astype(np.float32),
            "random": nodes.spacing_select(rnd, allowed, K_FOLD_MASS, min_px=3.0).astype(np.float32),
        }
        rec = dict(fold=f, withheld_positive_px=int((fold["truth"] & fold["region"]).sum()),
                   allowed_px=int(allowed.sum()), arms={}, mass_arms={})
        for arm, em in emissions.items():
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=float(res["dti"]), placed=int(em.sum()),
                                    tpw=float(res["tpw"]), fpw=float(res["fpw"]), fnw=float(res["fnw"]))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        for arm, em in emissions_mass.items():
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms_mass[arm] = term if terms_mass[arm] is None else terms_mass[arm] + term
            rec["mass_arms"][arm] = dict(dti=float(res["dti"]), placed=int(em.sum()))
            log(f"fold {f} mass-lever {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        per_fold.append(rec)
        del emissions, emissions_mass, rnd

    # ---- canaries: each component alone against held-out truth inside the allowed set ------
    canary_rows = {}
    comps = build_view_components(valid)
    for fold in folds:
        allowed = allowed_for(fold, valid)
        truth_in = (fold["truth"] & fold["region"])[allowed]
        if not (truth_in.any() and (~truth_in).any()):
            continue
        f = int(fold["fold"])
        for n, arr in comps.items():
            auc = float(roc_auc_score(truth_in.astype(int), arr[allowed]))
            canary_rows.setdefault(n, []).append(dict(fold=f, auc=auc))
        for n, arr in (("view_A", a), ("view_B", b), ("field", field)):
            auc = float(roc_auc_score(truth_in.astype(int), arr[allowed]))
            canary_rows.setdefault(n, []).append(dict(fold=f, auc=auc))
    canary_max = {k: max(x["auc"] for x in v) for k, v in canary_rows.items()}
    canary_alarm = {k: v > CANARY_ALARM for k, v in canary_max.items()}

    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    summary_mass = evaluator.pooled_summary(terms_mass, draws=1000, seed=SEED, candidate=PRIMARY)
    primary_dti = summary["scores"][PRIMARY]["dti"]
    verdict = "promote" if primary_dti > BAR else "negative"
    out = dict(
        stage="holdout", registration=reg, evidence_class="HOLDOUT-DTI",
        evaluator_version=evaluator.VERSION, candidate=PRIMARY,
        budget_per_fold=K_FOLD, mass_lever_budget_per_fold=K_FOLD_MASS,
        folds=len(folds), buffer_px=BUFFER_PX, ring_px=RING_PX,
        withheld_positive_px=withheld, eligible_px=int(valid.sum()),
        independence=indep, pseudo_label_diagnostic=dict(
            whole_segments=n_segs, whole_segment_px=n_seg_px, used_for_training=False,
            note="iterative pseudo-label exchange is a closed negative (N-1, knowledge/03); count only"),
        pooled=summary, pooled_mass_lever=summary_mass,
        bar_to_beat=BAR, bar_source="evidence/h82_holdout.json (H82 B_DVA2 HOLDOUT-DTI 0.192829)",
        verdict_for_slot=verdict,
        per_fold=per_fold,
        canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max, alarm=canary_alarm,
                    per_channel=canary_rows),
        reference_not_rerun={
            "H82 B_DVA2 (best comparable holdout)": dict(dti=0.192829, ci95=[0.170790, 0.213691],
                                                         source="evidence/h82_holdout.json"),
            "H84 main primary B_DVA2_HVA": dict(dti=0.190147, ci95=[0.168893, 0.211154],
                                                source="evidence/h84_run_card.json"),
            "H82 single_B": dict(dti=0.174571, ci95=[0.152313, 0.196302],
                                 source="evidence/h82_holdout.json")},
        implementation_hashes=evaluator.implementation_hashes(),
        generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h88_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a_: round(summary["scores"][a_]["dti"], 6) for a_ in arms}))
    log("CI: " + json.dumps({a_: summary["scores"][a_]["ci95"] for a_ in arms}))
    log(f"verdict for slot (bar {BAR}): {verdict}")
    return out


def build_view_components(valid: np.ndarray):
    """Single components for leakage canaries and A-only reasoning."""
    comps = {}
    with rasterio.open(FEATURES) as src:
        comps["grav_hg"] = np.abs(band(src, 18))
        comps["mag_hg"] = np.abs(band(src, 3))
        b15 = band(src, 15)
        comps["cover_step"] = gradmag(b15, valid, 2.0)
        del b15
        b10 = band(src, 10)
        comps["seis_line"] = gradmag(b10, valid, 2.0)
        del b10
        b7 = band(src, 7)
        comps["strain_step"] = gradmag(b7, valid, 2.0)
        del b7
        comps["mag_vg"] = np.abs(band(src, 9))
        comps["cond"] = band(src, 17)
        comps["slope"] = band(src, 19)
        b12 = band(src, 12)
        comps["ridge_curv"] = hessian_min_abs(b12, valid, 1.5)
        comps["topo_edge"] = gradmag(b12, valid, 1.5)
        del b12
        comps["tc"] = band(src, 6)
    with rasterio.open(RAD) as src:
        k = src.read(1).astype(np.float32) / 255.0
        th = src.read(2).astype(np.float32) / 255.0
    comps["K_over_Th"] = k / (th + 1e-3)
    return comps


def stage_build():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    field, cons, buried, art, veto = make_field(a, b, valid)
    # lane drift check on the SURFACE (pre-placement field)
    priors = gates.find_priors([SUBDIR, DLDIR, ROOT / "data/scored", ROOT / "data/reference"])
    log(f"registry priors found: {len(priors)}")
    surface_lane = gates.lane_report(field, valid, priors, sample=str(SAMPLE), phase="surface",
                                     log=log)
    log(f"surface lane: literal spearman max {surface_lane['literal']['max_spearman']}, "
        f"literal {surface_lane['literal']['verdict']}, policy {surface_lane['policy']['verdict']}")
    if surface_lane["policy"]["verdict"] != "PASS":
        raise SystemExit("lane drift on the surface (informative priors): DUPLICATE/STOP — "
                         f"policy rank offenders {surface_lane['policy']['rank_offenders']}, "
                         f"near offenders {surface_lane['policy']['near_offenders']}")
    # full-catalogue allowed set: not on catalogue, 200 m collar from the FULL catalogue
    vd = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd > RING_PX)
    log(f"allowed {int(allowed.sum()):,} px (collar {RING_PX} px around full catalogue)")
    dots = nodes.spacing_select(np.where(allowed, field, 0.0).astype(np.float32),
                                allowed, S_SHIP, min_px=3.0)
    n = int(dots.sum())
    log(f"placed {n} dots (target {S_SHIP})")
    if n != S_SHIP:
        log("WARNING: placed != target; the run card will record both")
    raster = np.where(dots, 1.0, 0.0).astype(np.float32)
    np.savez_compressed(WORK / "ship.npz", raster=raster, field=field,
                        consensus=cons, buried=buried, artifact=art, veto=veto, a=a, b=b)
    # composition of the emitted dots (not-the-union evidence)
    y, x = np.nonzero(dots)
    buried_dom = int((buried[y, x] > cons[y, x]).sum())
    comp = dict(emitted=n, target=S_SHIP,
                buried_dominant_dots=buried_dom, consensus_dominant_dots=n - buried_dom,
                buried_dominant_fraction=buried_dom / max(n, 1))
    # Jaccard vs the union of the two views' spaced top-k supports at the same K
    ua = nodes.spacing_select(a, allowed, S_SHIP, min_px=3.0)
    ub = nodes.spacing_select(b, allowed, S_SHIP, min_px=3.0)
    union = ua | ub
    inter = int((dots & union).sum())
    comp["jaccard_vs_viewA_viewB_spaced_topk_union"] = float(inter / max(int((dots | union).sum()), 1))
    comp["intersection_with_view_union"] = inter
    comp["dots_outside_view_union"] = int((dots & ~union).sum())
    comp["is_merely_the_view_union"] = bool(comp["jaccard_vs_viewA_viewB_spaced_topk_union"] >= 0.99
                                            and comp["dots_outside_view_union"] == 0)
    log(f"not-the-union: jaccard vs view union {comp['jaccard_vs_viewA_viewB_spaced_topk_union']:.4f}, "
        f"dots outside union {comp['dots_outside_view_union']}, "
        f"buried-dominant fraction {comp['buried_dominant_fraction']:.4f}")
    out = dict(stage="build", registration=reg, composition=comp,
               allowed_px=int(allowed.sum()), catalogue_px=int(cat.sum()),
               collar_px=RING_PX, spacing_px=3.0,
               surface_lane=dict(literal=surface_lane["literal"], policy=surface_lane["policy"]),
               generated_utc=datetime.now(timezone.utc).isoformat())
    (EVID / "h88_build.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    return out


def stage_write():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    z = np.load(WORK / "ship.npz")
    raster, field = z["raster"], z["field"]
    cons, buried, art, veto = z["consensus"], z["buried"], z["artifact"], z["veto"]
    a, b = z["a"], z["b"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest8 = hashlib.sha256(raster.astype("<f4").tobytes()).hexdigest()[:8]
    name = f"gems52-h88-bidir-cotrain-coverstep-25400px-{stamp}-{digest8}-zeros"
    note = ("H88 bidir co-train A/B disagreement, cover-step ViewA, 25400px mass lever, 3px, "
            "200m collar; HOLDOUT-DTI below bar, research candidate")
    assert len(note) <= 140, len(note)
    tif = SUBDIR / f"{name}.tif"
    SUBDIR.mkdir(exist_ok=True)
    DLDIR.mkdir(parents=True, exist_ok=True)
    receipt = submission_writer.write_submission(
        tif, raster, str(SAMPLE), valid, note=note, name=name,
        metadata=dict(round="H88", hypothesis="bidirectional co-training disagreement; "
                      "A-confident/B-abstain = buried fault, B-confident/A-abstain = artifact veto",
                      evidence_class="HOLDOUT-DTI", registration=reg))
    log(f"wrote {tif} sha256 {receipt['sha256']}")
    # stage download copies
    for dest in (DLDIR / f"{name}.tif", DLDIR / f"{name}.zip"):
        src = tif if dest.suffix == ".tif" else tif.with_suffix(".zip")
        dest.write_bytes(src.read_bytes())
    (DLDIR / f"{name}.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")

    # ---- A-only geological reasoning (every buried-dominant dot) ---------------------------
    with rasterio.open(SAMPLE) as ref:
        T = ref.transform
    comps = build_view_components(valid)
    comp_rank = {n: rank01(arr, valid) for n, arr in comps.items()}
    del comps
    y, x = np.nonzero(raster > 0)
    b_dom = buried[y, x] > cons[y, x]
    import csv
    csv_path = DLDIR / f"{name}-a-only-reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "x_utm_m", "y_utm_m", "a", "b", "buried", "consensus", "artifact",
                    "cover_step_r", "seis_line_r", "strain_step_r", "grav_hg_r", "mag_hg_r",
                    "geological_reasoning", "named_alternatives"])
        for j in np.flatnonzero(b_dom):
            r, c = int(y[j]), int(x[j])
            xx, yy = T * (c + 0.5, r + 0.5)
            cs = float(comp_rank["cover_step"][r, c])
            sl = float(comp_rank["seis_line"][r, c])
            st = float(comp_rank["strain_step"][r, c])
            gh = float(comp_rank["grav_hg"][r, c])
            mh = float(comp_rank["mag_hg"][r, c])
            fired = [n for n, v in (("cover-thickness step", cs), ("seismicity lineation", sl),
                                    ("strain step", st), ("gravity edge", gh), ("magnetic edge", mh))
                     if v >= 0.8]
            reason = ("View A confident and View B abstains (buried-fault disagreement). "
                      + ("Strongest signatures: " + ", ".join(fired) + ". " if fired else
                         "Subsurface composite is high but no single component is extreme. ")
                      + "A sustained step in cover thickness across this cell is the expected "
                        "expression of a buried normal fault offsetting the basement with no "
                        "surface scarp; coincident potential-field edges support a structural "
                        "rather than stratigraphic origin.")
            alt = ("lithologic contact; intrusive margin; basin-margin facies step; paleo-channel; "
                   "aftershock/induced seismicity cluster; interpolation artefact")
            w.writerow([r, c, f"{xx:.1f}", f"{yy:.1f}",
                        f"{float(a[r, c]):.4f}", f"{float(b[r, c]):.4f}",
                        f"{float(buried[r, c]):.4f}", f"{float(cons[r, c]):.4f}",
                        f"{float(art[r, c]):.4f}", f"{cs:.4f}", f"{sl:.4f}", f"{st:.4f}",
                        f"{gh:.4f}", f"{mh:.4f}", reason, alt])
    log(f"A-only reasoning rows: {int(b_dom.sum())} -> {csv_path.name}")

    # ---- uniqueness + lane (final dots) ---------------------------------------------------
    priors = gates.find_priors([SUBDIR, DLDIR, ROOT / "data/scored", ROOT / "data/reference"],
                               exclude=tif)
    uniq = gates.uniqueness_report(raster, priors)
    (EVID / "h88_uniqueness.json").write_text(json.dumps(uniq, indent=2, allow_nan=False) + "\n")
    log(f"uniqueness: priors {uniq['n_priors_checked']}, novel fraction "
        f"{uniq['novel_fraction']:.4f}, pattern unique {uniq['canonical_pattern_unique']}, "
        f"identical to a prior {uniq['identical_to_a_prior']}")
    cov_cache = {}
    dots_lane = gates.lane_report(raster, valid, priors, sample=str(SAMPLE), phase="dots",
                                  log=log, coverage_cache=cov_cache)
    (EVID / "h88_lane_dots.json").write_text(json.dumps(dots_lane, indent=2, allow_nan=False) + "\n")
    surface_lane = gates.lane_report(field, valid, priors, sample=str(SAMPLE), phase="surface",
                                     log=log, coverage_cache=cov_cache)
    (EVID / "h88_lane_surface.json").write_text(json.dumps(surface_lane, indent=2, allow_nan=False) + "\n")
    log("lane dots verdict: " + json.dumps(dots_lane.get("verdict", dots_lane.get("summary")))[:300])

    hold = json.loads((EVID / "h88_holdout.json").read_text())
    build = json.loads((EVID / "h88_build.json").read_text())
    fmt = gates.format_report(tif, SAMPLE, footprint=valid)
    card = dict(
        round="H88", generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis=hold.get("registration", {}).get("preregistration_sha256") and
        ("Bidirectional co-training disagreement: a sustained cover-thickness step and "
         "strain/seismicity lineation coincident with potential-field edges where the surface view "
         "abstains marks buried faults the surface-trace catalogue lacks; the reverse disagreement "
         "marks surface artifacts and is vetoed."),
        mechanism=("Concealed normal faults offset the basement beneath alluvial cover: the cover "
                   "thickness steps (band 15 gradient), shear strain steps (band 7 gradient) and "
                   "seismicity lineations (band 10 gradient) register in View A while DEM curvature "
                   "and slope (View B) see no scarp. View-B-confident/View-A-abstain cells are "
                   "vetoed as road/erosion suspects (Blum & Mitchell 1998 two-view disagreement)."),
        named_non_fault_mimic=("lithologic contacts and intrusive margins (potential-field edges "
                               "without fault offset); basin-margin facies steps (cover steps "
                               "without faulting); paleo-channels; aftershock clusters; road cuts "
                               "and erosion lines (the vetoed B-only population)"),
        preregistration=hold["registration"],
        independence=hold["independence"],
        pseudo_label_diagnostic=hold["pseudo_label_diagnostic"],
        holdout_dti=dict(label="HOLDOUT-DTI", evaluator_version=hold["evaluator_version"],
                         withheld_positive_pixels=hold["withheld_positive_px"],
                         dots_per_fold_per_arm=hold["budget_per_fold"],
                         scores=hold["pooled"]["scores"],
                         paired_vs_single_view=hold["pooled"]["paired_differences"],
                         mass_lever_curve=hold["pooled_mass_lever"]["scores"],
                         ci="95% paired 20 km spatial-cluster bootstrap, 1000 draws"),
        bar_to_beat=hold["bar_to_beat"], verdict_for_slot=hold["verdict_for_slot"],
        canary=hold["canary"],
        correlation_vs_registry=dict(
            surface=dict(max_spearman=surface_lane["literal"]["max_spearman"],
                         literal_verdict=surface_lane["literal"]["verdict"],
                         policy_verdict=surface_lane["policy"]["verdict"]),
            dots=dict(max_spearman=dots_lane["literal"]["max_spearman"],
                      max_near_3px=dots_lane["literal"]["max_near_3px_fraction"],
                      max_near_source=dots_lane["literal"]["max_near_source"],
                      literal_verdict=dots_lane["literal"]["verdict"],
                      policy_verdict=dots_lane["policy"]["verdict"])),
        uniqueness=dict(n_priors_checked=uniq["n_priors_checked"],
                        novel_fraction=uniq["novel_fraction"],
                        canonical_pattern_unique=uniq["canonical_pattern_unique"],
                        identical_to_a_prior=uniq["identical_to_a_prior"],
                        equals_literal_prior_union=uniq["equals_literal_prior_union"]),
        not_union=build["composition"],
        validator=fmt,
        raster_file=tif.name, raster_sha256=fmt["sha256"],
        zip_file=tif.with_suffix(".zip").name,
        submission_name=name, note=note, note_chars=len(note),
        download_ok=True,
        submit_ok=False,
        approved_for_weekly_slot=False, submission_slots_used=0,
        verdict=hold["verdict_for_slot"],
        budget=dict(experiments=3, hours="<=2", submission_slot="not spent"),
        evidence_class_note=("Every number is HOLDOUT-DTI (gems52-pooled-hide-v1) or measured "
                            "from bytes; no ORGANIZER-CONFIRMED receipt exists for any file in "
                            "this family; a projection is never written as a score."),
        a_only_reasoning_file=csv_path.name, a_only_rows=int(b_dom.sum()))
    (EVID / "h88_run_card.json").write_text(json.dumps(card, indent=2, allow_nan=False, default=float) + "\n")
    log(f"run card written; verdict {card['verdict']}; submit_ok {card['submit_ok']}")
    return card


def main():
    t0 = time.time()
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("views", "all"):
        stage_views()
    if stage in ("holdout", "all"):
        stage_holdout()
    if stage in ("build", "all"):
        stage_build()
    if stage in ("write", "all"):
        stage_write()
    log(f"done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
