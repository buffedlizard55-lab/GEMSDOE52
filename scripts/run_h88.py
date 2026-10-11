#!/usr/bin/env python3
"""H88 -- basement-step coherence on cover thickness (band 15), pre-registered in knowledge/80.

Why this exists
---------------
The repo has used band 15 (``depth_to_base_surf``, sedimentary cover thickness) only as a covariate.
A buried, basin-bounding normal fault offsets the basement top, so an oriented, coherent step in
cover thickness is a candidate signal for a fault with no surface trace. H88 tests that one layer on
the shared hide-and-recover instrument before any slot decision.

Shared tools, reused and not forked
-----------------------------------
* ``run_h61.setup()``        fold construction (label-blind quadrants, 80 m buffer, visible collar)
* ``run_h85.allowed_of``      allowed set = region minus visible minus 200 m visible-catalogue collar
* ``run_h85.rank01``          rank normalisation to [0, 1] over the footprint
* ``gems52.nodes.spacing_select``  metric-aware 3 px placement (the same selector as H82/H85)
* ``gems52.evaluate_holdout`` pooled DTI evaluator (alpha 0.2, beta 0.8, 300 m triangular kernel)
* ``run_h85.gate_candidate``  shared uniqueness + lane gate (moved out of H85 unchanged)
* ``gems52.grid.write_geotiff_portal_exact`` the organiser-template container

Leakage rules
-------------
* The field reads only band 15 of ``training_features.tif``. No label, no catalogue, no held-out truth.
* Each arm is canary-tested by single-channel AUC against the held-out truth (bar 0.90).

Usage: python scripts/run_h88.py [holdout|write|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                    # noqa: E402
from scipy import ndimage                             # noqa: E402
from sklearn.metrics import roc_auc_score             # noqa: E402

import run_h61 as base                                # noqa: E402
import run_h83_structural_concordance as h83          # noqa: E402
import run_h85 as h85                                 # noqa: E402  (allowed_of, rank01, gate_candidate)
from gems52 import evaluate_holdout as evaluator      # noqa: E402
from gems52 import nodes                              # noqa: E402

SEED = base.SEED
K_FOLD = 9400              # per-fold budget, as H82 / H85
K_TOTAL = 37654
H82_BEST = 0.189200        # H82 B_DVA2 receipt on this instrument: the bar in knowledge/80 section 5
H82_RANDOM = 0.080426      # H82 random arm receipt (instrument reproduction check)
CANARY_BAR = 0.90
BAND_INDEX = 15            # 1-based band in training_features.tif
BAND_TAG = "depth_to_base_surf"
SIGMA_SMOOTH_PX = 2.0      # 200 m
SIGMA_TENSOR_PX = 4.0      # 400 m
WORK = ROOT / "work/h88"
EVID = ROOT / "evidence"
FEAT = ROOT / "data/training_features.tif"
PREFIX = "gems52-h88-"
CANDIDATE = "H88_step"


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def step_fields(valid: np.ndarray):
    """Return the H88 arms on the full grid. Only band 15 is read; no label is touched."""
    import rasterio
    with rasterio.open(FEAT) as s:
        assert str(s.descriptions[BAND_INDEX - 1]).startswith(BAND_TAG), s.descriptions[BAND_INDEX - 1]
        d = s.read(BAND_INDEX).astype(np.float64)
    bad = ~np.isfinite(d) | (d <= -1e30)
    inside = valid & ~bad
    n_bad_inside = int((valid & bad).sum())
    fill = float(np.median(d[inside]))
    d = np.where(inside, d, fill)                      # fill only inside the footprint, avoids edge spikes
    ds = ndimage.gaussian_filter(d, SIGMA_SMOOTH_PX, mode="nearest")
    gy, gx = np.gradient(ds)                           # depth units per pixel
    g = np.hypot(gx, gy)
    jxx = ndimage.gaussian_filter(gx * gx, SIGMA_TENSOR_PX, mode="nearest")
    jyy = ndimage.gaussian_filter(gy * gy, SIGMA_TENSOR_PX, mode="nearest")
    jxy = ndimage.gaussian_filter(gx * gy, SIGMA_TENSOR_PX, mode="nearest")
    tr = jxx + jyy
    disc = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2)
    coh = np.where(tr > 1e-12, disc / np.maximum(tr, 1e-12), 0.0)   # in [0, 1]
    step = g * coh
    arms = {
        CANDIDATE: h85.rank01(step, valid),
        "H88_gradient_only": h85.rank01(g, valid),
        "raw_depth_to_base": h85.rank01(d, valid),
    }
    stats = dict(band=BAND_INDEX, tag=BAND_TAG, n_nonfinite_or_nodata_inside_footprint=n_bad_inside,
                 fill_value_m_units_as_stored=fill,
                 band_min=float(d[valid].min()), band_max=float(d[valid].max()),
                 band_median=float(np.median(d[valid])),
                 coherence_mean_inside=float(coh[valid].mean()),
                 gradient_p50=float(np.percentile(g[valid], 50)), gradient_p99=float(np.percentile(g[valid], 99)))
    return arms, stats


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    valid = h83.footprint_all_bands(str(FEAT))
    if (eligible & ~valid).any():
        raise SystemExit("feature-store eligible set is not inside the all-band footprint; refusing to run")
    log(f"footprint {int(valid.sum()):,} px; evaluation (store-eligible) {int(eligible.sum()):,} px")
    arm_fields, stats = step_fields(valid)
    log("band-15 stats:", json.dumps(stats))
    arms = list(arm_fields)
    terms = {}

    def add(name, em, fold):
        res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
        terms[name] = term if name not in terms else terms[name] + term
        return res

    out = dict(stage="h88-holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), band15_stats=stats,
               folds=[], note="HOLDOUT-DTI on the H82 instrument; H88 field uses band 15 only; placement per fold.",
               preregistration="knowledge/80_h88_preregistered.md")
    log(f"withheld positives {out['withheld_positive_px']} (H82 receipt 53186)")
    for fold in folds:
        f = fold["fold"]
        rec = dict(fold=f, arms={}, canary={})
        allowed = h85.allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        truth_in = fold["truth"] & eligible & fold["region"] & ~fold["visible"]
        pos = np.flatnonzero(truth_in.ravel())
        rng = np.random.default_rng(SEED + 500 + f)
        neg_pool = np.setdiff1d(ai, pos, assume_unique=False)
        neg = rng.choice(neg_pool, size=min(200_000, len(neg_pool)), replace=False)
        pos_s = rng.choice(pos, size=min(60_000, len(pos)), replace=False) if len(pos) else pos
        for name, fld in arm_fields.items():                       # leakage canary, per arm
            y = np.r_[np.ones(len(pos_s)), np.zeros(len(neg))]
            s = np.r_[fld.ravel()[pos_s], fld.ravel()[neg]]
            rec["canary"][name] = float(roc_auc_score(y, s)) if len(pos_s) else None
        for name in arms:                                          # the arms, placed with the repo selector
            fld = np.full(eligible.shape, -1.0, np.float32)
            fld.ravel()[ai] = arm_fields[name].ravel()[ai]
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res = add(name, em, fold)
            rec["arms"][name] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {name}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        # placement ablation on the candidate: top-k without spacing (the H83 failure mode, IR-H85-001 area)
        fld = np.full(eligible.shape, -1.0, np.float32)
        fld.ravel()[ai] = arm_fields[CANDIDATE].ravel()[ai]
        order = np.argsort(-fld.ravel()[ai])[:K_FOLD]
        em = np.zeros(eligible.shape, bool); em.ravel()[ai[order]] = True
        res = add(CANDIDATE + "_topk_noSpacing", em, fold)
        rec["arms"][CANDIDATE + "_topk_noSpacing"] = dict(res, placed=int(em.sum()))
        log(f"fold {f} topk-ablation: DTI {res['dti']:.6f}")
        rnd = np.full(eligible.shape, -1.0, np.float32)            # reproduction control (H82 random arm)
        rnd.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
        em = nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0)
        res = add("random", em, fold)
        rec["arms"]["random"] = dict(res, placed=int(em.sum()))
        log(f"fold {f} random: DTI {res['dti']:.6f}")
        out["folds"].append(rec)

    all_names = list(terms)
    out["canary_max_auc"] = {n: max(r["canary"][n] for r in out["folds"]) for n in arms}
    out["canary_alarm_any"] = any(v > CANARY_BAR for v in out["canary_max_auc"].values())
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=CANDIDATE)
    sc = out["pooled"]["scores"]
    out["controls"] = dict(
        random_reproduction=dict(committed=H82_RANDOM, measured=sc["random"]["dti"],
                                 abs_delta=abs(sc["random"]["dti"] - H82_RANDOM), tolerance=1e-3,
                                 PASS=bool(abs(sc["random"]["dti"] - H82_RANDOM) <= 1e-3)))
    cand = sc[CANDIDATE]
    paired_rand = out["pooled"]["paired_differences"]["random"]
    point_pass = cand["dti"] > H82_BEST
    lower_pass = paired_rand["ci95"][0] > 0
    canary_pass = not out["canary_alarm_any"]
    out["gate"] = dict(
        candidate_dti=cand["dti"], candidate_ci95=cand["ci95"],
        repo_holdout_best_H82=H82_BEST,
        beats_repo_holdout_best_point=bool(point_pass),
        paired_vs_random=paired_rand,
        paired_lower_bound_above_zero=bool(lower_pass),
        canary_pass=bool(canary_pass),
        all_arms=sorted(all_names),
        verdict=("PASS: beats H82 point bar, paired CI vs random above 0, canary clear -- eligible for slot selector (owner decides)"
                 if (point_pass and lower_pass and canary_pass)
                 else "NEGATIVE/NOT-PROMOTED: fails the pre-registered rule (knowledge/80 section 5)"),
    )
    WORK.mkdir(parents=True, exist_ok=True)
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "h88_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("gate:", json.dumps(out["gate"], default=float)[:1200])
    log("controls:", json.dumps(out["controls"], default=float))
    log("scores:", json.dumps({k: round(v["dti"], 6) for k, v in sc.items()}))


def stage_write():
    """Write the H88 candidate (after the holdout), with the shared gate. Download-only unless the gate passes."""
    import rasterio
    from gems52 import gates
    from gems52 import grid as GR

    sample = ROOT / "data/sample_submission.tif"
    with rasterio.open(sample) as s:
        smp = s.read(1)
    footprint = np.isfinite(smp) & (smp > -1e38)
    with rasterio.open(ROOT / "data/labels.tif") as s:
        cat = s.read(1) == 1
    valid = h83.footprint_all_bands(str(FEAT))
    arm_fields, stats = step_fields(valid)
    score = np.where(footprint & valid, arm_fields[CANDIDATE], 0.0).astype(np.float32)   # already in [0, 1]
    assert float(score.max()) <= 1.0 + 1e-6 and float(score.min()) >= 0.0
    dcat_px = ndimage.distance_transform_edt(~cat)
    allowed = footprint & valid & (dcat_px > 2.0) & ~cat           # 200 m = 2 px collar, Euclidean
    score_m = np.where(allowed, score, -1.0).astype(np.float32)
    em = nodes.spacing_select(score_m, allowed, K_TOTAL, min_px=3.0).astype(np.float32)
    n = int(em.sum())
    log(f"placed {n} of {K_TOTAL} dots; allowed {int(allowed.sum()):,} px")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"h88-basement-step-cat200-{K_TOTAL}px-20261010"
    out = ROOT / "submission" / f"gems52-h88-basement-step-{K_TOTAL}px-20261010.tif"
    GR.write_geotiff_portal_exact(out, em, footprint, sample, outside="zero")
    fmt = gates.format_report(out, sample)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    log(f"wrote {out.name} sha256 {sha[:16]} format ok={fmt['ok']} problems={fmt.get('problems')}")

    own = {"h88-candidate.tif", "h88-candidate.zip", out.name}
    g = h85.gate_candidate(out, em, footprint, allowed, score, sample, own)
    uni, lane_surface, lane_dots, probe_check, lane_literal = (
        g["uni"], g["lane_surface"], g["lane_dots"], g["probe_check"], g["lane_literal"])
    hold = json.loads((EVID / "h88_holdout.json").read_text())
    hs = hold["pooled"]["scores"][CANDIDATE]
    cards = dict(
        hypothesis=("H88: a coherent, sustained step in depth-to-basement (band 15, cover thickness) marks a "
                    "basin-bounding buried fault without a surface trace."),
        mechanism=("gradient magnitude of the Gaussian-smoothed cover-thickness field times the structure-tensor "
                   "coherence of its gradient field (line-like steps), placed with 3 px spacing outside the 200 m "
                   "catalogue collar."),
        non_fault_process=("basin-margin alluvial fans and bounding fronts; basement facies boundaries; "
                           "paleo-channel incisions in cover; DEM-to-basement interpolation seams."),
        holdout=dict(evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
                     dti=hs["dti"], ci95=hs["ci95"], withheld_positive_pixels=hs["withheld_positive_pixels"],
                     random_control_dti=hold["pooled"]["scores"]["random"]["dti"],
                     paired_vs_random=hold["pooled"]["paired_differences"]["random"],
                     verdict=hold["gate"]["verdict"],
                     note="from evidence/h88_holdout.json; the file's placement is the H88_step arm"),
        raster_sha256=sha, file=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
        submission_name=name,
        note="H88 basement-step coherence (band 15 cover); 3px spaced; 200m ring out; binary; see holdout",
        validator=dict(format_ok=bool(fmt["ok"]), problems=fmt.get("problems"), bands=fmt.get("bands"),
                       dtype=fmt.get("dtype"), crs=fmt.get("crs"), shape=[fmt.get("height"), fmt.get("width")],
                       nan_inside_footprint=int(fmt.get("n_nan", -1)), min=fmt.get("min"), max=fmt.get("max"),
                       positives=int(fmt.get("n_nonzero", -1))),
        uniqueness=dict(n_priors_checked=len(g["priors"]), ok=bool(uni.get("ok")),
                        novel_fraction=uni.get("novel_fraction"),
                        canonical_pattern_unique=uni.get("canonical_pattern_unique"),
                        identical_to_a_prior=uni.get("identical_to_a_prior"),
                        max_jaccard_vs_priors=max((r.get("jaccard", 0) for r in uni.get("per_prior", [])),
                                                  default=None)),
        lane=lane_literal,
        band15=stats,
        dots=n, slots_used=0,
        verdict=(f"DOWNLOAD YES (format-valid, decoded-unique) / SUBMIT {'YES' if hold['gate']['beats_repo_holdout_best_point'] and hold['gate']['paired_lower_bound_above_zero'] and hold['gate']['canary_pass'] else 'NO'}: "
                 f"{hold['gate']['verdict']}"),
        generated_utc=ts,
    )
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "h88_run_card.json").write_text(json.dumps(cards, indent=2, default=str) + "\n")
    (EVID / "h88_gates_raw.json").write_text(json.dumps(dict(uniqueness=uni, lane_surface=lane_surface,
                                                             lane_dots=lane_dots, probe_check=probe_check,
                                                             format=fmt), indent=2, default=str) + "\n")
    log("run card -> evidence/h88_run_card.json")
    log(json.dumps({k: cards[k] for k in ("submission_name", "raster_sha256", "uniqueness", "lane")}, default=str)[:1500])
    return out


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "holdout"
    if stage in ("holdout", "all"):
        stage_holdout()
    if stage in ("write", "all"):
        stage_write()
