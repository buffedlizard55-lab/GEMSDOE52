#!/usr/bin/env python3
"""H97 -- the H96 disagreement formula grafted onto the strongest measured surface learner (H84 B_DVA2_HVA).

Pre-registered in ``knowledge/97_hypotheses_H97_preregistered.md`` (frozen before the graft is scored; SHA-256 pinned in
``registry/h97_preregistration.json``).  This runner refuses to start if that document's hash has moved.

Nothing here forks a shared tool:
  * fits            -> ``run_h84.stage_fit`` (the frozen H84 learners).  H97 fits NO new learner.  Its only inputs are the
                       per-fold predictions of H84 arms ``single_A`` and ``B_DVA2_HVA`` in ``work/h84``.
  * folds / masks   -> ``run_h61.setup`` / ``run_h84.allowed_of`` (gems52.spatial.folds, label-blind, 80 px buffer).
  * scoring         -> ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1), 9,400 dots per fold per arm, 3 px spacing.
  * stitching       -> ``run_h82.stitch`` (per-fold percentile rank, the H73/H75 convention).
  * lane            -> ``run_h84.stage_lane`` logic with ``run_h73.place_lane`` quota placement, ``gems52.gates``.
  * writing         -> ``gems52.submission_writer.write_submission`` (exactly {0,1}, 0.0 outside footprint, no NaN).

Stages:  holdout | build | lane | write | card | all
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
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402

import run_h61 as base                                               # noqa: E402
import run_h82 as h82                                                # noqa: E402
import run_h84 as h84                                                # noqa: E402
import run_h73 as h73                                                # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, nodes, submission_writer                   # noqa: E402

DOC = ROOT / "knowledge/97_hypotheses_H97_preregistered.md"
PREREG = ROOT / "registry/h97_preregistration.json"
WORK = ROOT / "work/h97"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
SEED = h84.SEED
K_FOLD = 9400
K_TOTAL = 37654
RING_M = 200.0
BAR = 0.190147          # committed H84 B_DVA2_HVA HOLDOUT-DTI (evidence/h84_holdout.json)
CONTROL_TOL = 1e-3
W_CONS, W_BURIED, W_VETO = 0.45, 0.55, 0.70          # copied from H96 (registry/h96_preregistration.json)
ARMS = ("B_DVA2_HVA", "single_A", "graft_primary", "consensus_only", "random")
PRIMARY = "graft_primary"
PREFIX = "gems52-h97-"
PRIOR_RECEIPT = ROOT / "work/h61/prior_fetch_receipt.json"

h82.WORK = h84.WORK  # run_h84 already did this; kept explicit so stitching reads the H84 arms


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_prereg():
    reg = json.loads(PREREG.read_text())
    got = sha256_file(DOC)
    if got != reg["document_sha256"]:
        raise SystemExit(f"H97 document hash moved: {got} != {reg['document_sha256']}; refusing to run")
    return dict(document_sha256=got, frozen_utc=reg["frozen_utc"], frozen_before_any_fit=True)


def write(name, obj):
    """H97 receipts only.  Never writes an H84 receipt (run_h84.write would overwrite the shared file)."""
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h97_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


def rank01(a, mask):
    """0..1 rank inside mask (ties broken by flat index), 0 outside.  Same definition as run_h96_cotrain_bidir.rank01."""
    out = np.zeros(a.shape, np.float32)
    v = a[mask]
    if v.size == 0:
        return out
    out[mask] = np.argsort(np.argsort(v)).astype(np.float32) / max(v.size - 1, 1)
    return out


def graft(a, b, mask):
    """H97 formula.  a, b are per-pixel percentile ranks in [0,1] (NaN-free inside mask).

    consensus = a*b ; buried = a*clip(a-b,0,1) (A confident, B abstains) ;
    veto = rank01(clip(b-a,0,1)) (B confident, A abstains) ; field = (0.45*consensus + 0.55*buried)*(1-0.70*veto)
    """
    a = np.where(mask, a, 0.0).astype(np.float32)
    b = np.where(mask, b, 0.0).astype(np.float32)
    consensus = a * b
    buried = a * np.clip(a - b, 0.0, 1.0)
    veto = rank01(np.clip(b - a, 0.0, 1.0), mask)
    field = (W_CONS * consensus + W_BURIED * buried) * (1.0 - W_VETO * veto)
    return np.where(mask, field, -1.0).astype(np.float32)


def require_h84_arms(folds):
    missing = [str(h84.WORK / f"pred_{arm}_f{f['fold']}.npy") for f in folds for arm in ("single_A", "B_DVA2_HVA")
               if not (h84.WORK / f"pred_{arm}_f{f['fold']}.npy").exists()]
    if missing:
        raise SystemExit("H84 arm predictions missing; run `python scripts/run_h84.py channels` then "
                         f"`python scripts/run_h84.py fit` first: {missing[:3]} ...")


# ----------------------------------------------------------------------------------------------- stage: holdout
def stage_holdout():
    pre = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    require_h84_arms(folds)
    WORK.mkdir(parents=True, exist_ok=True)
    terms = {a: None for a in ARMS}
    out = dict(stage="holdout", prereg=pre, evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), folds=[], started_utc=now())
    for fold in folds:
        f = fold["fold"]
        allowed = h84.allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        gA = base.to_grid(store.flat_idx, np.load(h84.WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        gB = base.to_grid(store.flat_idx, np.load(h84.WORK / f"pred_B_DVA2_HVA_f{f}.npy"), eligible.shape)
        a_r = np.nan_to_num(base.pct_rank(gA.ravel()[ai]), nan=0.0)
        b_r = np.nan_to_num(base.pct_rank(gB.ravel()[ai]), nan=0.0)
        a_full = np.zeros(eligible.shape, np.float32)
        b_full = np.zeros(eligible.shape, np.float32)
        a_full.ravel()[ai] = a_r
        b_full.ravel()[ai] = b_r
        allowed_f = allowed.astype(bool)
        fields = {
            "B_DVA2_HVA": np.full(eligible.shape, -1.0, np.float32),
            "single_A": np.full(eligible.shape, -1.0, np.float32),
            "graft_primary": graft(a_full, b_full, allowed_f),
            "consensus_only": np.where(allowed_f, a_full * b_full, -1.0).astype(np.float32),
        }
        fields["B_DVA2_HVA"].ravel()[ai] = np.nan_to_num(base.pct_rank(gB.ravel()[ai]), nan=-1.0)
        fields["single_A"].ravel()[ai] = np.nan_to_num(base.pct_rank(gA.ravel()[ai]), nan=-1.0)
        rec = dict(fold=f, n_allowed=int(len(ai)), arms={})
        for arm in ARMS:
            if arm == "random":
                fld = np.full(eligible.shape, -1.0, np.float32)
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                fld = fields[arm]
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del fld, em
        out["folds"].append(rec)
        del gA, gB, a_full, b_full, fields
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    got = float(out["pooled"]["scores"]["B_DVA2_HVA"]["dti"])
    out["control"] = dict(arm="B_DVA2_HVA", committed=BAR, measured=got, abs_delta=abs(got - BAR),
                          tolerance=CONTROL_TOL, PASS=bool(abs(got - BAR) <= CONTROL_TOL))
    out["finished_utc"] = now()
    write("holdout", out)
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in ARMS}))
    log("control: " + json.dumps(out["control"], default=float))
    log("primary paired: " + json.dumps({k: [round(v["delta"], 6)] + [round(x, 6) for x in v["ci95"]]
                                          for k, v in out["pooled"]["paired_differences"].items()}, default=float))


# ----------------------------------------------------------------------------------------------- stage: build
def stage_build():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    require_h84_arms(folds)
    WORK.mkdir(parents=True, exist_ok=True)
    flat = store.flat_idx
    fA = h82.stitch("single_A", folds, eligible, flat)
    fB = h82.stitch("B_DVA2_HVA", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fA) & np.isfinite(fB) & (catd * 100.0 > RING_M)
    a = np.where(pool, np.nan_to_num(fA, nan=0.0), 0.0)
    b = np.where(pool, np.nan_to_num(fB, nan=0.0), 0.0)
    # Emission rank domain: the emission pool (stitched fold ranks), a disclosed choice; the holdout ranks inside each
    # fold's allowed mask.  The preregistration fixes the formula, not the rank domain (IR-H97-002).
    surf = graft(a, b, pool)
    # [0,1] surface with 0.0 outside the pool (the lane gate requires a normalized finite field; H84 convention)
    surf = np.where(pool, surf, 0.0).astype(np.float32)
    assert np.isfinite(surf).all() and surf.min() >= 0.0 and surf.max() <= 1.0 + 1e-6
    np.save(WORK / "surface.npy", surf)
    np.save(WORK / "pool.npy", pool)
    np.save(WORK / "field_A.npy", fA)
    np.save(WORK / "field_B.npy", fB)
    rec = dict(stage="build", pool_px=int(pool.sum()), eligible_px=int(eligible.sum()), ring_excluded_m=RING_M,
               rank_domain="stitched per-fold percentile ranks over the emission pool (disclosed; IR-H97-002)",
               surface_nonneg_px=int((surf >= 0).sum()), started_utc=now())
    write("build", rec)
    log(json.dumps(rec, default=float))


# ----------------------------------------------------------------------------------------------- stage: lane
def stage_lane():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    h73.H73 = json.loads((ROOT / "registry/h73_preregistration.json").read_text())
    surf = np.load(WORK / "surface.npy")
    pool = np.load(WORK / "pool.npy")
    full, meta = h84.full_registry()
    restr, scored = h82.restricted_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full), n_restricted=len(restr),
               doctrine=("both registries reported verbatim; a restricted-registry PASS never waives a literal "
                         "full-census DUPLICATE/STOP (AGENTS.md, knowledge/62 IR-H73-011)"))
    log(f"lane: full census {len(full)} rasters, scored-only {len(restr)} rasters")
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface", log=log)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface")
    write("lane", out)
    if out["full_surface"]["literal"]["verdict"].upper().startswith("DUPLICATE"):
        out["stopped"] = "surface literal DUPLICATE -> logged as duplicate, stopped before placement"
        write("lane", out)
        log(out["stopped"])
        return
    sups, suprows = h82.restricted_supports(restr, eligible)
    out["restricted_supports"] = suprows
    fld = np.where(pool, surf, -1.0).astype(np.float32)
    lane_dots, lrec = h73.place_lane(fld, pool, K_TOTAL, sups, eligible.shape, limit=0.70, rounds=8)
    out["quota_placement"] = lrec
    if int(lane_dots.sum()) == K_TOTAL:
        dots, out["emitted_placement"] = lane_dots, "quota (run_h73.place_lane, scored-only supports)"
    else:
        dots = nodes.spacing_select(fld, pool, K_TOTAL, min_px=3.0)
        out["emitted_placement"] = f"fallback spacing_select (quota short-filled at {int(lane_dots.sum())})"
    np.save(WORK / "dots.npy", dots)
    out["dots"] = int(dots.sum())
    df = dots.astype(np.float32)
    out["full_dots"] = gates.lane_report(df, eligible, full, sample=SAMPLE, phase="dots", log=log)
    out["restricted_dots"] = gates.lane_report(df, eligible, restr, sample=SAMPLE, phase="dots")
    out["uniqueness_full"] = gates.uniqueness_report(df, full)
    out["finished_utc"] = now()
    write("lane", out)
    for k in ("full_surface", "restricted_surface", "full_dots", "restricted_dots"):
        r = out[k]
        log(f"{k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, max near "
            f"{r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']}")


# ----------------------------------------------------------------------------------------------- stage: write
def _spearman_sub(a, b, eligible, step=7):
    from scipy.stats import spearmanr
    m = eligible.copy()
    m.ravel()[np.arange(m.size) % step != 0] = False
    return float(spearmanr(a[m], b[m]).correlation)


def stage_write():
    started = now()
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    ln = json.loads((EVID / "h97_lane.json").read_text())
    if "stopped" in ln:
        raise SystemExit("lane stopped before placement; no raster is written (duplicate logged)")
    dots = np.load(WORK / "dots.npy").astype(bool)
    pool = np.load(WORK / "pool.npy")
    surf = np.load(WORK / "surface.npy")
    fA, fB = np.load(WORK / "field_A.npy"), np.load(WORK / "field_B.npy")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h97-graft-B_DVA2_HVA-{int(dots.sum())}px-{stamp}"
    note = ("H97: H96 disagreement formula grafted on H84 B_DVA2_HVA (A=single_A); 3px spacing; 200m ring cut; "
            "binary dots; HOLDOUT-DTI gate in run card")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    # remove earlier outputs of this same H97 candidate family (each run stamps a new name), so no stale
    # copy of the candidate remains in submission/ to be compared with it (IR-H97-007)
    fam = f"gems52-h97-graft-B_DVA2_HVA-{int(dots.sum())}px-*"
    for stale in list((ROOT / "submission").glob(fam + ".*")):
        if stale != out and stale.name != out.with_suffix(".zip").name:
            stale.unlink()
    for stale in list((ROOT / "submission").glob(fam + ".zip")):
        if stale != out.with_suffix(".zip"):
            stale.unlink()
    for stale in list((ROOT / "docs" / "downloads").glob(f"gems52-h97-graft-B_DVA2_HVA-{int(dots.sum())}px-*-a-only-reasoning.csv")):
        if not stale.name.startswith(f"gems52-{name}"):
            stale.unlink()
    pred = dots.astype(np.float32)
    submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                       metadata=dict(round="H97", primary_arm=PRIMARY))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nodata=a.nodata, nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   nan_inside_footprint=int(np.isnan(v[eligible]).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()),
                   ones_outside_footprint=int(((v == 1) & ~eligible).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"] and val["shape_match"]
                       and val["transform_match"] and val["bounds_match"] and val["range_ok"]
                       and val["ones_outside_footprint"] == 0)
    val["sha256"] = sha256_file(out)
    val["bytes"] = out.stat().st_size
    # not-the-union: equal-budget comparators on the same pool
    def ds(field):
        return nodes.spacing_select(np.where(pool, np.nan_to_num(field, nan=-1.0), -1.0).astype(np.float32),
                                    pool, K_TOTAL, min_px=3.0)
    a_dots, b_dots = ds(fA), ds(fB)
    u_dots = ds(np.where(pool, np.maximum(np.nan_to_num(fA, nan=-1.0), np.nan_to_num(fB, nan=-1.0)), -1.0))

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    nu = dict(dots_emitted=int(dots.sum()), union_max_dots=int(u_dots.sum()),
              dots_equal_union=bool(np.array_equal(dots, u_dots)),
              dots_subset_of_union=bool(not (dots & ~u_dots).any()),
              dots_equal_single_A=bool(np.array_equal(dots, a_dots)),
              dots_equal_B_DVA2_HVA=bool(np.array_equal(dots, b_dots)),
              jaccard_with_union=jac(dots, u_dots), jaccard_with_single_A=jac(dots, a_dots),
              jaccard_with_B_DVA2_HVA=jac(dots, b_dots),
              spearman_surface_vs_unionmax=_spearman_sub(np.nan_to_num(surf, nan=0.0),
                                                         np.nan_to_num(np.where(pool, np.maximum(
                                                             np.nan_to_num(fA, nan=-1.0),
                                                             np.nan_to_num(fB, nan=-1.0)), -1.0), nan=0.0),
                                                         eligible))
    nu["not_union_pass"] = bool(not nu["dots_equal_union"] and not nu["dots_subset_of_union"]
                                and not nu["dots_equal_single_A"] and not nu["dots_equal_B_DVA2_HVA"])
    # uniqueness, decoded, against the full census
    full, meta = h84.full_registry()
    # the candidate itself was written to submission/ above; it must not be compared with its own copy
    full = [p for p in full if Path(str(p)).resolve() != out.resolve()]
    uq = gates.uniqueness_report(dots.astype(np.float32), full)
    uq["excluded_own_path"] = str(out.relative_to(ROOT))
    # zip with exactly one TIFF
    zp = out.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out, arcname=out.name)
    # A-only reasoning for every A-only dot (A rank > B rank); reuses the H84 writer, fed with the true View-B rank
    catd = ndi.distance_transform_edt(~cat)
    cand = dots & (np.nan_to_num(fA, nan=-1.0) > np.nan_to_num(fB, nan=-1.0))
    h84_name = name
    rpath, nrows = h84.write_a_only_reasoning(store, cand, np.nan_to_num(fA, nan=0.0),
                                              np.nan_to_num(fB, nan=0.0), catd, eligible, h84_name)
    rec = dict(stage="write", name=name, note=note, note_chars=len(note), name_chars=len(name),
               file=str(out.relative_to(ROOT)), zip=str(zp.relative_to(ROOT)), validator=val,
               not_the_union=nu, uniqueness=uq, a_only_reasoning=dict(path=rpath, rows=nrows,
                                                                     dots_total=int(dots.sum())),
               started_utc=started, finished_utc=now())
    write("write", rec)
    log(json.dumps(dict(validator_PASS=val["PASS"], sha256=val["sha256"], ones=val["ones"],
                        not_union=nu["not_union_pass"], a_only_rows=nrows), default=float))


# ----------------------------------------------------------------------------------------------- stage: card
def stage_card():
    """One JSON run card, assembled only from receipts on disk.  The verdict is computed from the frozen rule."""
    pre = check_prereg()
    ho = json.loads((EVID / "h97_holdout.json").read_text())
    ln = json.loads((EVID / "h97_lane.json").read_text())
    wr = json.loads((EVID / "h97_write.json").read_text())
    dg = json.loads((EVID / "h97_posthoc_diagnostic.json").read_text())
    h84_ho = json.loads((ROOT / "evidence/h84_holdout.json").read_text())
    h84_fit = json.loads((EVID / "h97_repro_h84_fit.json").read_text())
    pool = ho["pooled"]
    sc = pool["scores"]
    pd_ = pool["paired_differences"]
    g_vs_b = pd_["B_DVA2_HVA"]
    g_vs_c = pd_["consensus_only"]
    canary_max = float(h84_fit["canary_max_learner_overall"])
    dots_lit = ln["full_dots"]["literal"]
    surf_lit = ln["full_surface"]["literal"]
    val = wr["validator"]
    uq = wr["uniqueness"]
    checks = {
        "control_reproduction": bool(ho["control"]["PASS"]),
        "holdout_bar": bool(sc[PRIMARY]["dti"] > BAR),
        "paired_vs_B_DVA2_HVA_ci_lower_gt0": bool(g_vs_b["ci95"][0] > 0),
        "paired_vs_consensus_only_ci_lower_gt0": bool(g_vs_c["ci95"][0] > 0),
        "leakage_canary_below_0.90": bool(canary_max < 0.90),
        "surface_lane_literal_pass": not str(surf_lit["verdict"]).upper().startswith("DUPLICATE"),
        "dot_lane_literal_pass": not str(dots_lit["verdict"]).upper().startswith("DUPLICATE"),
        "validator_pass": bool(val["PASS"]),
        # decoded-pattern uniqueness over every census prior (not the support-novelty diagnostic, which is
        # recorded separately below as a failed gate, not silently waived)
        "uniqueness_pass": bool(uq.get("canonical_pattern_unique") and not uq.get("identical_to_a_prior"))
                           if isinstance(uq, dict) else False,
        "support_novelty_ge_20pct": bool(uq.get("support_novelty_gate_ok")) if isinstance(uq, dict) else False,
    }
    promote = all(checks.values())
    card = dict(
        round="H97", lane_definition="co-training: geophysical view A vs surface view B, disagreement as discovery signal",
        hypothesis=("H96 disagreement formula, grafted onto the strongest measured surface learner (H84 B_DVA2_HVA, "
                    "HOLDOUT-DTI 0.190147), adds discovery signal beyond agreement and beyond the control."),
        mechanism=("View A (single_A) confident and View B abstaining = buried-fault candidate (basement step under "
                   "cover); View B confident and A abstaining = surface-artefact suspect, vetoed."),
        named_non_fault_mimic=("lithologic contacts and intrusive margins; basin-margin facies steps; paleo-channels; "
                               "road cuts; erosion lines and drainage incision; induced-seismicity clusters"),
        holdout=dict(evaluator=ho["evaluator"], label="HOLDOUT-DTI", withheld_positive_px=ho["withheld_positive_px"],
                     budget_per_fold=K_FOLD, graft_primary=dict(dti=sc[PRIMARY]["dti"], ci95=sc[PRIMARY]["ci95"]),
                     arms={a: dict(dti=sc[a]["dti"], ci95=sc[a]["ci95"]) for a in ARMS},
                     paired_graft_minus_B_DVA2_HVA=dict(delta=g_vs_b["delta"], ci95=g_vs_b["ci95"]),
                     paired_graft_minus_consensus_only=dict(delta=g_vs_c["delta"], ci95=g_vs_c["ci95"]),
                     bar=BAR, bar_source="evidence/h84_holdout.json pooled.scores.B_DVA2_HVA"),
        h84_committed_reference=dict(B_DVA2_HVA=h84_ho["pooled"]["scores"]["B_DVA2_HVA"]["dti"]),
        posthoc_diagnostic=dict(file="evidence/h97_posthoc_diagnostic.json", post_hoc=True,
                                pooled={a: dg["pooled"][a]["dti"] for a in dg["pooled"]}),
        canary=dict(max_single_feature_auc=canary_max, alarm_bar=0.90),
        lane=dict(surface_literal=surf_lit, dots_literal=dots_lit,
                  surface_policy=ln["full_surface"]["policy"]["verdict"],
                  dots_policy=ln["full_dots"]["policy"]["verdict"],
                  registry_full_census=ln["n_full"], registry_scored_only=ln["n_restricted"]),
        raster=dict(file=wr["file"], zip=wr["zip"], sha256=val["sha256"], bytes=val["bytes"],
                    validator=val, not_the_union=wr["not_the_union"], uniqueness=uq),
        a_only_reasoning=wr["a_only_reasoning"],
        submission_name=wr["name"], submission_note=wr["note"], submission_note_chars=wr["note_chars"],
        checks=checks, verdict=("promote" if promote else "negative"),
        download_ok=bool(val["PASS"]), submit_ok=bool(promote),
        slots_used=0, experiments_used=2,
        experiments_note=("1 = the preregistered graft (frozen); 2 = post-hoc decomposition, labelled as such, "
                          "not promotable"),
        preregistration=pre,
        irregularities=["IR-H97-001", "IR-H97-002", "IR-H97-003", "IR-H97-004"],
        generated_utc=now(),
    )
    p = write("run_card", card)
    log(json.dumps(dict(verdict=card["verdict"], checks=checks), default=float))
    return p


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("holdout", "all"):
        stage_holdout()
    if stage in ("build", "all"):
        stage_build()
    if stage in ("lane", "all"):
        stage_lane()
    if stage in ("write", "all"):
        stage_write()
    if stage in ("card", "all"):
        stage_card()
