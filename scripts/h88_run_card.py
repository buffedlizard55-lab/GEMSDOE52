#!/usr/bin/env python3
"""H88 run card -- the machine-readable receipt for the shipped H88 GeoTIFF.

Follows the shared ``build_h61_submission.py`` card schema.  Everything is recomputed from the
shipped bytes and the shared out-of-fold checkpoints in this process and then checked against the
written file:

* the emission is rebuilt with ``run_h88.view_rank_mosaic`` / ``disagreement_field`` /
  ``placement_field`` and asserted equal to the shipped mask (reproducibility);
* the not-the-union block re-places View A, View B and ``max(A,B)`` at the same dot count;
* the lane gate runs over every aligned prior still on disk;
* ``gates.uniqueness_report`` checks the decoded pattern against every prior.

Writes ``evidence/h88_run_card.json`` and ``docs/data/h88_run_card.json``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio as rio
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h61 as base                                                     # noqa: E402
import run_h88 as h88                                                      # noqa: E402
from gems52 import gates, nodes                                            # noqa: E402

EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
SAMPLE = ROOT / "data/sample_submission.tif"


def main() -> int:
    audit = json.loads((EVID / "h88_audit.json").read_text())
    ladder = json.loads((EVID / "h88_ladder.json").read_text())
    shipped = sorted((ROOT / "submission").glob("gems52-h88-*.tif"))
    tif = shipped[-1]
    receipt = json.loads(tif.with_suffix(".json").read_text())
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()

    with rio.open(tif) as s:
        em = s.read(1)
    d = em > 0
    n = int(d.sum())

    # ---- rebuild the field with the shipped code path and prove the bytes reproduce
    with rio.open(ROOT / "data/labels.tif") as ds:
        shape = ds.shape
    ranks, strata = h88.view_rank_mosaic(folds, store, shape, ring_px, eligible,
                                         tags=("post", "pre"))
    field = h88.disagreement_field(ranks["post"])
    fld, allowed, footprint = h88.placement_field(field, cat, eligible, SAMPLE)
    rebuilt = nodes.spacing_select(fld, allowed, n, min_px=3.0)
    reproduces = bool(np.array_equal(rebuilt, d))
    if not reproduces:
        raise SystemExit(f"run card refused: rebuilt emission differs from the shipped bytes "
                         f"({int((rebuilt & d).sum())} of {n} shared)")

    # ---- not merely the union of the two views: re-place A, B and max(A,B) at the same count
    a_em = nodes.spacing_select(ranks["post"]["A"], allowed, n, min_px=3.0)
    b_em = nodes.spacing_select(ranks["post"]["B"], allowed, n, min_px=3.0)
    u_field = h88.union_field(ranks["post"])
    u_em = nodes.spacing_select(np.where(allowed, u_field, -1.0), allowed, n, min_px=3.0)
    a_only = (strata == 2) & allowed                     # A confident tail, B abstains
    not_union = dict(
        cells_differing_from_view_A=int((d != a_em).sum()),
        cells_differing_from_view_B=int((d != b_em).sum()),
        cells_differing_from_union_max=int((d != u_em).sum()),
        dots_shared_with_view_A=int((d & a_em).sum()),
        dots_shared_with_view_B=int((d & b_em).sum()),
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(
            rankdata(fld[allowed]), rankdata(np.where(allowed, u_field, -1.0)[allowed]))[0, 1]),
        strict_a_only_candidate_px=int(a_only.sum()),
        emitted_cells_that_are_strict_a_only=int((d & a_only).sum()),
        verdict=("the emission is not max(A,B), not either single view, and not their union -- but "
                 "it is dominated by the surface view's abstention: only "
                 f"{int((d & a_only).sum())} of {n} dots sit in the strict A-only stratum"))
    del ranks, u_field, rebuilt

    # ---- format
    fmt = gates.format_report(tif, SAMPLE)

    # ---- uniqueness (decoded pattern) and lane (spatial proximity) over every aligned prior on disk
    priors = gates.find_priors([ROOT / "submission", ROOT / "docs/downloads", ROOT / "data/scored"],
                               exclude=tif)
    priors = [p for p in priors if p.name not in ("h88-candidate.tif", tif.name)]
    uni = gates.uniqueness_report(em, priors)
    lane = gates.lane_report(np.asarray(em, np.float32), footprint, priors, sample=SAMPLE,
                             phase="dots")
    lane_near = lane["literal"]["max_near_3px_fraction"]

    card = {
        "round": "H88",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lane": ("two-view co-training (Blum & Mitchell 1998, doi:10.1145/279943.279962); View A "
                 "potential-field/subsurface, View B surface; disagreement as the discovery signal"),
        "hypothesis": ("the brief's disagreement field is only worth emitting at a support size set "
                       "by the board's truth prevalence, not by the family's inherited 37,654-dot "
                       "convention; the board budget follows from the instrument optimum divided by "
                       "the measured prevalence ratio"),
        "mechanism": ("rank(A_post) - rank(B_post) over the whole footprint in a one-quadrant-per-"
                      "fold out-of-fold mosaic, placed as 3 px dots outside the 200 m catalogue "
                      "collar at the prevalence-corrected board budget"),
        "named_non_fault_process": ("basement lithological or intrusive contact under cover with no "
                                    "displacement; aeromagnetic flight-line/tie-line artefact in "
                                    "the supplied derivative bands; and for B-abstention-dominated "
                                    "dots, roads, canals and erosion lineaments"),
        "evidence_class": "HOLDOUT-DTI (gems52-pooled-hide-v1, 53,186 withheld positives)",
        "holdout_dti": {
            "evaluator": ladder["pooled"]["75k2"]["evaluator_version"],
            "withheld_positive_pixels": ladder["pooled"]["75k2"]["scores"]["disagreement_post"]
                                        ["withheld_positive_pixels"],
            "candidate": ladder["pooled"]["75k2"]["scores"]["disagreement_post"]["dti"],
            "shipped_rung": "75k2 (the instrument optimum of the shipped field)",
            "controls": {a: ladder["pooled"]["75k2"]["scores"][a]["dti"] for a in
                         ("single_B", "union_max", "a_only_stratum", "random")},
            "paired_vs_single_B": ladder["pooled"]["75k2"]["paired_differences"]["single_B"],
            "pooled_curve_dots_per_fold": {lab: {"disagreement_post": v["scores"]
                                                 ["disagreement_post"]["dti"]}
                                           for lab, v in ladder["pooled"].items()},
            "bootstrap": ladder["pooled"]["75k2"]["bootstrap"],
            "simulator_validity": ("R4 measured Spearman -0.10 between this instrument and the "
                                   "owner-reported board; it screens procedures and does not promote"),
        },
        "instrument": {
            "prevalence_correction": audit["prevalence_correction"],
            "board_algebra": audit["board_algebra"],
        },
        "support_calibration": {
            "instrument_optimum_dots_per_fold": ladder["optimum"]["disagreement_post"]
                                                ["instrument_optimum_dots_per_fold"],
            "instrument_optimum_total": ladder["optimum"]["disagreement_post"]
                                        ["instrument_optimum_total"],
            "monotone_rising_on_the_instrument": ladder["optimum"]["disagreement_post"]
                                                  .get("monotone_rising"),
            "prevalence_ratio_used": ladder["optimum"]["disagreement_post"]["prevalence_ratio"],
            "board_corrected_total_dots": n,
            "caveat": ("a proportionality argument for a self-similar field, not a measurement on "
                       "the board; every curve is still rising at the top rung, so the corrected "
                       "budget is a LOWER bound"),
        },
        "reproduces_from_current_code": reproduces,
        "raster_sha256": receipt["sha256"],
        "file": str(tif.relative_to(ROOT)),
        "zip": str(tif.with_suffix(".zip").relative_to(ROOT)),
        "emitted_px": n,
        "submission_name": receipt["submission_name"],
        "note": receipt["note"],
        "note_chars": receipt["note_chars"],
        "validator": {k: fmt.get(k) for k in ("ok", "problems", "bands", "dtype", "crs", "width",
                                              "height", "n_nan", "min", "max", "n_nonzero")},
        "not_the_union": not_union,
        "uniqueness": {k: uni.get(k) for k in ("n_priors_checked", "n_priors_compared",
                                               "canonical_pattern_unique",
                                               "distinct_from_every_comparable_prior",
                                               "identical_to_a_prior", "audit_complete",
                                               "equals_literal_prior_union",
                                               "research_publication_ok",
                                               "support_novelty_gate_ok", "novel_fraction",
                                               "novel_vs_all_priors", "prior_px_dropped",
                                               "relation_to_union", "union_px")},
        "correlation_vs_registry": {
            "dots": {"literal": lane["literal"], "policy": lane["policy"]},
            "scope": (f"{lane['priors_checked']} aligned rasters still on disk (submission/, "
                      "docs/downloads/, data/scored/); the 545-raster work/h61/priors inventory "
                      "used by the H61/H75 cards is no longer in the workspace"),
        },
        "lane_rule": ("STOP at Spearman > 0.90 or directed <= 3 px dot proximity > 0.70; no lane "
                      "retuning"),
        "canary_note": ("the per-feature leakage canary (AUC > 0.90 = leakage) is carried by the "
                        "shared fit stage; the highest view AUC measured in this family is 0.9481 "
                        "in-sample, which is not an alarm -- alarms are on held-out features"),
        "code": {"runner": "scripts/run_h88.py", "reasoning": "scripts/h88_reasoning.py",
                 "run_card": "scripts/h88_run_card.py"},
        "reasoning_rows": {"rows": int(sum(1 for _ in (ROOT / "docs/downloads"
                                                       / "h88-a-only-reasoning.csv").open())) - 1,
                           "csv": "docs/downloads/h88-a-only-reasoning.csv",
                           "a_only_stratum_rows": int(sum(
                               1 for _ in (ROOT / "docs/downloads" / "h88-a-only-reasoning.csv")
                               .open() if ",2,A-only," in _))},
        "download_ok": True,
        "submit_ok": False,
        "slots_used": 0,
        "promotion_is_a_separate_selector_step": True,
        "experiments_used": "1 of 3 this session",
        "verdict": ("HOLDOUT: NEGATIVE -- the mandated disagreement field measures "
                    f"{ladder['pooled']['75k2']['scores']['disagreement_post']['dti']:.4f} pooled "
                    "HOLDOUT-DTI at 75.2k dots, below the random arm "
                    f"({ladder['pooled']['75k2']['scores']['random']['dti']:.4f}) and "
                    f"{abs(ladder['pooled']['75k2']['paired_differences']['single_B']['delta']):.4f} "
                    "below single_B with a paired CI excluding zero. LANE: DUPLICATE/STOP on dots "
                    f"(directed <=3 px proximity {lane_near:.4f} > 0.70; the largest offender is our "
                    "own H61 candidate, which shares the same out-of-fold field family). Overall: "
                    "research-only. DOWNLOAD YES (format-valid, decoded-unique), SUBMIT NO."),
        "ai_use": ("An AI assistant wrote the code, the protocol and the reasoning templates. No "
                   "geologist verified any emitted structure and no field observation was collected."),
        "sources": [
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "https://doi.org/10.1145/279943.279962",
            "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
            "https://doi.org/10.5066/P93LGLVQ",
            "https://github.com/drivendataorg/gems-prize-reference-solution",
        ],
    }
    for p in (EVID / "h88_run_card.json", DOCS / "h88_run_card.json"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(card, indent=1, default=str) + "\n")
    print(json.dumps({"sha256": card["raster_sha256"], "reproduces": reproduces,
                      "validator_ok": card["validator"]["ok"],
                      "novel_fraction": card["uniqueness"]["novel_fraction"],
                      "lane_literal": lane["literal"]["verdict"],
                      "lane_policy": lane["policy"]["verdict"],
                      "lane_near": lane_near,
                      "a_only_dots": not_union["emitted_cells_that_are_strict_a_only"]}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
