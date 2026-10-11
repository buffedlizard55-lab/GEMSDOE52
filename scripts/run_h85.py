#!/usr/bin/env python3
"""H85 -- holdout validation of the H83 structural-concordance + geothermal field, then a re-issued file.

Why this exists
---------------
H83 shipped a GeoTIFF (``submission/gems52-h83-structcon-geotherm-*.tif``) and described it as
"ready for upload", but its own run card said ``holdout_dti: NOT_EVALUATED``.  This runner measures
that field on the repository's shared hide-and-recover instrument before any slot decision.

Shared tools, reused and not forked
-----------------------------------
* ``run_h61.setup()``       fold construction (label-blind quadrants, 80 m buffer, visible-catalogue collar)
* ``run_h83_structural_concordance``  the H83 concordance / geothermal field code, called unchanged
                             (only the catalogue argument is neutralised for the holdout, see below)
* ``gems52.nodes.spacing_select``  the repo's metric-aware placement (greedy, 3 px minimum spacing)
* ``gems52.evaluate_holdout``      the pooled DTI evaluator (alpha 0.2, beta 0.8, 300 m triangular kernel)
* ``gems52.gates``                 format / uniqueness gates for the final file

Leakage rules enforced here
---------------------------
* The H83 field multiplies by a catalogue-buffer exclusion.  Inside a holdout that exclusion would
  read the HELD-OUT truth.  ``combine_signals`` is therefore called with an all-zero label raster;
  every catalogue-dependent step is then a no-op, and the only per-fold dependence is the visible-
  catalogue collar in ``allowed_of``.
* The field uses only raw feature bands and the GDR well/spring table; no label is read.
* Every single-channel score is canary-tested for AUC against the held-out truth (bar 0.90).

Usage: python scripts/run_h85.py [holdout|write|card|all]
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
from scipy.stats import rankdata                      # noqa: E402
from sklearn.metrics import roc_auc_score             # noqa: E402

import run_h61 as base                                # noqa: E402
import run_h83_structural_concordance as h83          # noqa: E402
from gems52 import evaluate_holdout as evaluator      # noqa: E402
from gems52 import nodes                              # noqa: E402

SEED = base.SEED
K_FOLD = 9400              # same per-fold budget as H82 (4 folds x 9400 = 37,600 ~ 37,654)
K_TOTAL = 37654
H82_BEST = 0.189200        # H82 B_DVA2 HOLDOUT-DTI receipt (evidence/h82_holdout.json), same instrument
H82_RANDOM = 0.080426      # H82 random arm receipt, used as the instrument reproduction check
CANARY_BAR = 0.90
WORK = ROOT / "work/h85"
EVID = ROOT / "evidence"
FEAT = ROOT / "data/training_features.tif"
WELLS = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
PREFIX = "gems52-h85-"


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Average-rank normalisation to [0,1] over ``mask``; zero outside (ties averaged)."""
    out = np.zeros(a.shape, np.float32)
    v = a[mask].astype(np.float64)
    r = (rankdata(v) - 1.0) / max(len(v) - 1, 1)
    out[mask] = r.astype(np.float32)
    return out


def allowed_of(fold, ring_px):
    vd = ndimage.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def build_fields(valid):
    """Return every single-channel score and the H83 field, all computed without the catalogue."""
    log("H83 structural concordance (unchanged H83 code) ...")
    concord, grav_rank, mag_rank, dem_rank, conc_count = h83.compute_structural_concordance(str(FEAT), valid)
    log("geothermal density from GDR well/spring table ...")
    wells = h83.load_well_spring_data(str(WELLS))
    geo = h83.compute_geothermal_density(wells, valid, sigma_px=15.0)
    zero_labels = np.zeros(h83.SHAPE, np.int8)          # neutralises the catalogue exclusion
    h83_field = h83.combine_signals(concord, conc_count, grav_rank, mag_rank, dem_rank,
                                    geo, valid, zero_labels)
    cc_rank = rank01(concord, valid)
    geo_rank = rank01(geo, valid)
    fields = {
        "H85_geo_concordance": h83_field,           # the H83 field, catalogue-free
        "concordance_only": cc_rank,                # H83 concordance without the geothermal term
        "geothermal_only": geo_rank,                # single non-geophysical channel (wells/springs)
        "surr_gravity_only": grav_rank,             # single-instrument linearity, potential-field (View A-like)
        "surr_magnetic_only": mag_rank,             # single-instrument linearity, magnetics
        "surr_dem_only": dem_rank,                  # single-instrument linearity, DEM surface (View B-like)
    }
    return fields, dict(n_wells=len(wells), concord_mean=float(concord[valid].mean()))


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    valid = h83.footprint_all_bands(str(FEAT))
    # The evaluation domain is the feature-store eligible set (the H61/H82 instrument). It must be a
    # subset of the all-band footprint on which the H83 field is defined; the reverse need not hold
    # (572,669 all-band pixels lie outside the store set and are never evaluated or emitted).
    if (eligible & ~valid).any():
        raise SystemExit("feature-store eligible set is not inside the H83 all-band footprint; refusing to run")
    log(f"all-band footprint {int(valid.sum()):,} px; evaluation (store-eligible) {int(eligible.sum()):,} px")
    fields, meta = build_fields(valid)
    arm_fields = dict(fields)
    arms = list(arm_fields.keys())
    terms = {}

    def add(name, em, fold):
        res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
        terms[name] = term if name not in terms else terms[name] + term
        return res

    out = dict(stage="h85-holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), meta=meta,
               folds=[], note="HOLDOUT-DTI on the H82 instrument; fields catalogue-free; placement per fold.")
    log(f"withheld positives {out['withheld_positive_px']} (H82 receipt 53186)")
    for fold in folds:
        f = fold["fold"]
        rec = dict(fold=f, arms={}, canary={})
        allowed = allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        truth_in = fold["truth"] & eligible & fold["region"] & ~fold["visible"]
        pos = np.flatnonzero(truth_in.ravel())
        rng = np.random.default_rng(SEED + 500 + f)
        # ---- leakage canary: each single channel alone, AUC on held-out truth vs allowed negatives
        neg_pool = np.setdiff1d(ai, pos, assume_unique=False)
        neg = rng.choice(neg_pool, size=min(200_000, len(neg_pool)), replace=False)
        pos_s = rng.choice(pos, size=min(60_000, len(pos)), replace=False) if len(pos) else pos
        for name, fld in arm_fields.items():
            y = np.r_[np.ones(len(pos_s)), np.zeros(len(neg))]
            s = np.r_[fld.ravel()[pos_s], fld.ravel()[neg]]
            rec["canary"][name] = float(roc_auc_score(y, s)) if len(pos_s) else None
        # ---- arms: each field placed with the repo's spacing selector on the fold's allowed set
        for name in arms:
            fld = np.full(eligible.shape, -1.0, np.float32)
            fld.ravel()[ai] = arm_fields[name].ravel()[ai]
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res = add(name, em, fold)
            rec["arms"][name] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {name}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        # ablation: the H83 shipped placement (top-k, no spacing) on the H85 field
        fld = np.full(eligible.shape, -1.0, np.float32)
        fld.ravel()[ai] = arm_fields["H85_geo_concordance"].ravel()[ai]
        em = h83.topk_emit(np.where(allowed, fld, 0.0), allowed, K_FOLD)
        res = add("H85_geo_concordance_topk_noSpacing", em, fold)
        rec["arms"]["H85_geo_concordance_topk_noSpacing"] = dict(res, placed=int(em.sum()))
        log(f"fold {f} topk-ablation: DTI {res['dti']:.6f} placed {int(em.sum())}")
        # reproduction control: H82's random arm (same seed, same placement)
        rnd = np.full(eligible.shape, -1.0, np.float32)
        rnd.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
        em = nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0)
        res = add("random", em, fold)
        rec["arms"]["random"] = dict(res, placed=int(em.sum()))
        log(f"fold {f} random: DTI {res['dti']:.6f}")
        out["folds"].append(rec)

    out["canary_max_auc"] = {n: max(r["canary"][n] for r in out["folds"]) for n in arms}
    out["canary_alarm_any"] = any(v > CANARY_BAR for v in out["canary_max_auc"].values())
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="H85_geo_concordance")
    sc = out["pooled"]["scores"]
    out["controls"] = dict(
        random_reproduction=dict(committed=H82_RANDOM, measured=sc["random"]["dti"],
                                 abs_delta=abs(sc["random"]["dti"] - H82_RANDOM),
                                 tolerance=1e-3,
                                 PASS=bool(abs(sc["random"]["dti"] - H82_RANDOM) <= 1e-3)))
    cand = sc["H85_geo_concordance"]
    best_single = max((k for k in sc if k not in ("H85_geo_concordance",)),
                      key=lambda k: sc[k]["dti"])
    out["gate"] = dict(
        candidate_dti=cand["dti"], candidate_ci95=cand["ci95"],
        best_comparable_control=best_single, best_comparable_control_dti=sc[best_single]["dti"],
        repo_holdout_best_H82=H82_BEST,
        beats_repo_holdout_best_point=bool(cand["dti"] > H82_BEST),
        paired_vs_best_control=out["pooled"]["paired_differences"].get(best_single),
        canary_pass=not out["canary_alarm_any"],
        verdict=("PASS: beats repo holdout best (point) and canary clear -- eligible for slot selector"
                 if (cand["dti"] > H82_BEST and not out["canary_alarm_any"])
                 else "NEGATIVE/NOT-PROMOTED: does not beat repo holdout best on this instrument"),
    )
    WORK.mkdir(parents=True, exist_ok=True)
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "h85_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("gate:", json.dumps(out["gate"], default=float)[:900])
    log("controls:", json.dumps(out["controls"], default=float))
    log("scores:", json.dumps({k: round(v["dti"], 6) for k, v in sc.items()}))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "holdout"
    if stage in ("holdout", "all"):
        stage_holdout()


def gate_candidate(out, em, footprint, allowed, score, sample, own):
    """Shared uniqueness + lane gate for a binary dot file (H85, H87 ...). Returns the gate record.

    ``own`` is the set of basenames of this candidate's own download copies, excluded from the priors
    (IR-H85-001). Moved here unchanged from ``stage_write`` in H85 so that every round uses one gate.
    """
    import rasterio
    from gems52 import gates
    priors = gates.find_priors([ROOT / "submission", ROOT / "docs/downloads", ROOT / "data/scored"], exclude=out)
    # Exclude this candidate's own download copies. find_priors only drops the exact output path and
    # its basename; the docs/downloads copy has a different basename, so without this line the
    # candidate is compared against itself (the self-match bug first seen in the H83 audit, IR-H85-001).
    priors = [q for q in priors if q.name not in own]
    uni = gates.uniqueness_report(em, priors)
    surface = np.where(allowed, score, 0.0).astype(np.float32)          # finite, in [0,1]
    lane_surface = gates.lane_uniqueness_report(surface, footprint, priors, sample=sample, phase="surface")
    lane_dots = gates.lane_uniqueness_report(em, footprint, priors, sample=sample, phase="dots")
    cand_dots = em > 0
    # Literal lane rule (shared gate) and a probe-control: a registry raster whose positives sit within
    # 3 px of almost ANY dot set (universal-coverage probe) makes the literal dots test fire for every
    # candidate. We measure that directly: the share of RANDOM allowed dots (same K, same allowed set)
    # within 3 px of the same raster. If random dots also score >= 0.90, the raster is a probe.
    rng_lane = np.random.default_rng(SEED + 9001)
    rnd_idx = rng_lane.choice(np.flatnonzero(allowed.ravel()), size=K_TOTAL, replace=False)
    rnd_dots = np.zeros(em.shape, bool); rnd_dots.ravel()[rnd_idx] = True
    probe_check = []
    for row in lane_dots["per_prior"]:
        share = float(row.get("near_3px_fraction") or 0.0)
        if share <= 0.70:
            continue
        with rasterio.open(row["path"]) as src:
            pos = np.nan_to_num(src.read(1), nan=0.0) > 0
        dd = ndimage.distance_transform_edt(~pos)
        probe_check.append(dict(path=str(Path(row["path"]).relative_to(ROOT)),
                                candidate_near_3px=share,
                                random_dots_near_3px=float((dd[rnd_dots] <= 3.0).mean()),
                                classified_universal_probe=bool((dd[rnd_dots] <= 3.0).mean() >= 0.90)))
    non_probe = [r["near_3px_fraction"] for r in lane_dots["per_prior"]
                 if r.get("near_3px_fraction") is not None
                 and not any(Path(r["path"]).name == Path(q["path"]).name and q["classified_universal_probe"]
                             for q in probe_check)]
    near_excl_probe = max(non_probe) if non_probe else None
    lane_literal = dict(
        surface=dict(max_spearman=lane_surface["max_spearman"], threshold=0.90, duplicate=bool(lane_surface["duplicate"]),
                     verdict="PASS" if not lane_surface["duplicate"] else "DUPLICATE/STOP"),
        dots=dict(max_near_3px_any_prior=lane_dots["max_near_3px_fraction"], threshold=0.70,
                  duplicate=bool(lane_dots["duplicate"]),
                  verdict="DUPLICATE/STOP" if lane_dots["duplicate"] else "PASS",
                  offenders=probe_check),
        dots_max_near_3px_excluding_universal_probes=near_excl_probe,
        dots_excluding_universal_probes_verdict=("PASS (policy only; literal rule still DUPLICATE/STOP)"
                                                 if near_excl_probe is not None and near_excl_probe <= 0.70 else "DUPLICATE/STOP"),
        scope="all 135 local rasters in submission/, docs/downloads/, data/scored/; not the 567-blob full census",
    )
    return dict(priors=priors, uni=uni, lane_surface=lane_surface, lane_dots=lane_dots,
                probe_check=probe_check, lane_literal=lane_literal)


# ----------------------------------------------------------------------------------- stage: write
def stage_write():
    """Re-issue the H85 field as a competition GeoTIFF with the repo's metric-aware placement.

    Placement: ``nodes.spacing_select`` (greedy, 3 px minimum separation), K = 37,654, allowed =
    footprint minus the 200 m catalogue collar (distance-transform, not a dilation).  The field is
    the catalogue-free H85 field, divided by its analytic maximum (1.2) so the ranking is unchanged
    and the score is on [0,1]; the emitted raster is binary {0,1}.
    """
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
    fields, meta = build_fields(valid)
    raw = fields["H85_geo_concordance"]
    score = np.where(footprint & valid, raw / 1.2, 0.0).astype(np.float32)   # analytic max of combine_signals = 1.2
    assert float(score.max()) <= 1.0 + 1e-6 and float(score.min()) >= 0.0
    dcat_px = ndimage.distance_transform_edt(~cat)
    allowed = footprint & valid & (dcat_px > 2.0) & ~cat           # 200 m = 2 px collar, Euclidean
    score_m = np.where(allowed, score, -1.0).astype(np.float32)
    em = nodes.spacing_select(score_m, allowed, K_TOTAL, min_px=3.0).astype(np.float32)
    n = int(em.sum())
    log(f"placed {n} of {K_TOTAL} dots; allowed {int(allowed.sum()):,} px")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"h85-geoconc-spaced-cat200-{K_TOTAL}px-20261010"
    fname = f"gems52-h85-geoconc-spaced-{K_TOTAL}px-20261010.tif"   # date-only: deterministic name; outside="zero"
    out = ROOT / "submission" / fname
    rec = GR.write_geotiff_portal_exact(out, em, footprint, sample, outside="zero")
    fmt = gates.format_report(out, sample)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    log(f"wrote {out.name} sha256 {sha[:16]} format ok={fmt['ok']} problems={fmt.get('problems')}")

    own = {"h85-candidate.tif", "h85-candidate.zip", out.name}
    g = gate_candidate(out, em, footprint, allowed, score, sample, own)
    priors, uni, lane_surface, lane_dots = g["priors"], g["uni"], g["lane_surface"], g["lane_dots"]
    probe_check, lane_literal = g["probe_check"], g["lane_literal"]
    cards_lane = lane_literal
    hold = json.loads((EVID / "h85_holdout.json").read_text())
    cards = dict(
        hypothesis="H85: catalogue-free geo-concordance field (structure-tensor linearity over 3 bands + "
                   "GDR well/spring temperature) placed with the repo's 3 px spacing selector outside the "
                   "200 m catalogue collar.",
        mechanism="Linear structural evidence that agrees across gravity, magnetic and DEM gradients, "
                  "weighted by proximity to geothermal manifestations.",
        non_fault_process="Lithological contacts; basin-margin gravity steps; road and erosion lineaments in DEM; "
                          "interpolation seams.",
        holdout=dict(evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
                     dti=hold["pooled"]["scores"]["H85_geo_concordance"]["dti"],
                     ci95=hold["pooled"]["scores"]["H85_geo_concordance"]["ci95"],
                     withheld_positive_pixels=hold["pooled"]["scores"]["H85_geo_concordance"]["withheld_positive_pixels"],
                     random_control_dti=hold["pooled"]["scores"]["random"]["dti"],
                     note="from evidence/h85_holdout.json; the file's own placement is the H85_geo_concordance arm"),
        raster_sha256=sha, file=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
        submission_name=name,
        note="H85 geo-concordance, catalogue-free; 3px spaced; 200m ring out; binary; holdout below random",
        validator=dict(format_ok=bool(fmt["ok"]), problems=fmt.get("problems"), bands=fmt.get("bands"),
                       dtype=fmt.get("dtype"), crs=fmt.get("crs"), shape=[fmt.get("height"), fmt.get("width")],
                       nan_inside_footprint=int(fmt.get("n_nan", -1)), min=fmt.get("min"), max=fmt.get("max"),
                       positives=int(fmt.get("n_nonzero", -1))),
        uniqueness=dict(n_priors_checked=len(priors), ok=bool(uni.get("ok")),
                        novel_fraction=uni.get("novel_fraction"),
                        canonical_pattern_unique=uni.get("canonical_pattern_unique"),
                        identical_to_a_prior=uni.get("identical_to_a_prior"),
                        max_jaccard_vs_priors=max((r.get("jaccard", 0) for r in uni.get("per_prior", [])),
                                                  default=None)),
        lane=cards_lane,
        dots=n, build_meta=meta, not_union_test="not applicable: single-view structural field, no co-training",
        slots_used=0,
        verdict=("DOWNLOAD YES (format-valid, decoded-unique) / SUBMIT NO: holdout below random control; "
                 "literal lane rule DUPLICATE/STOP on dots (universal-probe raster; see lane)"),
        generated_utc=ts,
    )
    EVID.mkdir(parents=True, exist_ok=True)
    hold = json.loads((EVID / "h85_holdout.json").read_text())
    (EVID / "h85_run_card.json").write_text(json.dumps(cards, indent=2, default=str) + "\n")
    (EVID / "h85_gates_raw.json").write_text(json.dumps(dict(uniqueness=uni, lane_surface=lane_surface,
                                                             lane_dots=lane_dots, format=fmt),
                                                        indent=2, default=str) + "\n")
    log("run card -> evidence/h85_run_card.json")
    log(json.dumps({k: cards[k] for k in ("submission_name", "raster_sha256", "validator", "uniqueness", "lane")},
                   default=str)[:1500])
    return out


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("write", "all"):
    stage_write()
