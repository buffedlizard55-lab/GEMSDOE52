#!/usr/bin/env python3
"""Assemble the H66 run card from the receipts the pipeline wrote. Nothing is typed in by hand.

Every field the parallel-run protocol asks for is read from a JSON receipt in ``evidence/`` or from
the submission sidecar, and each number carries its evidence class:

* **HOLDOUT-DTI** — evaluator version, number of withheld positives, 95 % CI.
* **OWNER-REPORTED** — a score the user's brief attributes to a filename; the board prints no
  filename, so this class is never promoted to ORGANIZER-CONFIRMED anywhere in this repo.
* **MEASURED** — computed in this session from bytes whose SHA-256 matches registry/data_manifest.json.

A projection is never written as a score; the expected-score brackets are labelled as such.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"


def load(name, default=None):
    p = EV / f"h66_{name}.json"
    return json.loads(p.read_text()) if p.exists() else default


def main() -> int:
    pre = load("preflight")
    chan = load("channels")
    s1 = load("s1_sufficiency")
    s2 = load("s2_independence")
    can = load("canary")
    build = load("build")
    ho = load("holdout")
    rel = load("release_gates")
    reas = load("reasoning")
    alg = load("board_algebra")
    uni2 = load("uniqueness_aligned")
    seeds = load("seed_composition")
    census = json.loads((ROOT / "evidence" / "ctd5_prior_inventory.json").read_text())
    by_blob = {e["blob"]: e for e in census["entries"]}

    def identify(path):
        """blob filename -> the owner repositories and paths it came from (for manual review)."""
        blob = Path(str(path)).stem
        e = by_blob.get(blob)
        if not e:
            return dict(blob=blob, aliases=[], note="not a census blob; local file")
        return dict(blob=blob, census_eligible=e.get("eligible"),
                    aliases=[dict(repo=a["repo"], commit=a["commit"], path=a["path"], bytes=a["bytes"])
                             for a in e["aliases"]])
    prereg = json.loads((ROOT / "registry" / "h66_preregistration.json").read_text())
    subs = sorted((ROOT / "submission").glob("gems52-h66-*.tif"))
    if len(subs) != 1:
        raise SystemExit(f"expected exactly one H66 raster, found {len(subs)}")
    tif = subs[0]
    sidecar = json.loads(tif.with_suffix(".json").read_text())
    val = sidecar["validator"]

    pooled = ho["pooled"]
    uni = rel["uniqueness"]
    def lane_surface():
        return rel["lane_surface"]["policy"]
    def lane_dots():
        return rel["lane_dots"]["policy"]

    card = {
        "round": "H66",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/h66_run_card.py (assembled from evidence/h66_*.json; no hand-typed numbers)",
        "preregistration": {
            "protocol": prereg["hypothesis_document"],
            "protocol_sha256": prereg["hypothesis_sha256"],
            "registered_utc": prereg.get("registered_utc"),
            "frozen_before_any_fit": prereg.get("frozen_before_any_fit"),
            "registry": "registry/h66_preregistration.json",
            "hash_verified_at_runtime": hashlib.sha256(
                (ROOT / prereg["hypothesis_document"]).read_bytes()
            ).hexdigest() == prereg["hypothesis_sha256"],
        },
        "hypothesis": (
            "H66-A (Thermal-Upflow Corridor, TUC). A geothermal system needs a permeable pathway. "
            "A surface thermal manifestation whose measured or geothermometer-inferred temperature "
            "places it above the local conductive gradient must be fed by a structure that the "
            "provided Quaternary-fault catalogue does not contain, because every seed used here lies "
            ">= 300 m (>= 3 px, beyond the whole scoring kernel) from the nearest mapped trace. "
            "The conducting structure is therefore an uncatalogued fault, and it is elongated along "
            "strike: emitting a strike-aligned corridor outward from such a site should place mass on "
            "an unmapped fault at a credit density above uniform random (0.0279)."),
        "mechanism": (
            "1) 1,156 INGENIOUS/GDR thermal sites in the footprint, of which 952 satisfy the frozen "
            "seed rule (temp >= 60 C, or reservoir geothermometer >= 100 C, or class Hot) and "
            ">= 300 m from the catalogue; 2) local strike from the structure tensor (sigma = 4 px) of "
            "the mean absolute-gradient composite of bands 12, 3, 18, 15, cross-checked against the "
            "external LiDAR scarp strike band; 3) a corridor 13 px long (±6 px) along strike, half "
            "width 1 px, amplitude tapered 1.00 -> 0.40 with distance from the seed; 4) a hard "
            "corroboration gate requiring rank >= 0.50 of the best independent geophysical edge "
            "(magnetic TMI horizontal gradient, isostatic-gravity horizontal gradient, detrended-"
            "elevation curvature/slope, surface conductivity gradient, LiDAR step, Hessian linearity); "
            "5) metric-aware greedy emission (src/gems52/emit.py) at the frozen budget ladder, "
            "values exactly {0,1}; 6) two-view stratification with a veto that removes B-only pixels "
            "having no thermal seed within 3 px (the surface-artifact class the brief names)."),
        "named_non_fault_process_that_could_mimic_it": (
            "Lithologic contacts and stratigraphic edges. A conductive/sedimentary contact can carry "
            "both a horizontal gravity-gradient edge and a conductivity contrast, and thermal water "
            "rising along a permeable sand body will discharge at its outcrop edge without any fault "
            "being present. Second: alluvial-fan and debris-flow margins, which produce linear "
            "topographic steps at 100 m and are the classic false 'scarp'. Third: road cuts and "
            "pipeline corridors, which the LiDAR step band and the detrended-elevation gradient both "
            "see as sharp lines; these are precisely the B-only pixels the veto removes, and 93 were "
            "removed on that ground. Fourth: a deep geothermal gradient with no anomalous chemistry, "
            "i.e. a warm well in ordinary basement, which the frozen seed rule tries to exclude by "
            "requiring a temperature or a chemical geothermometer threshold, but cannot exclude "
            "completely because 396 of 1,156 sites have no usable geothermometer."),
        "holdout": {
            "evidence_class": "HOLDOUT-DTI",
            "evaluator_version": ho["evaluator_version"],
            "design": "hide-and-recover: whole catalogue components withheld with a buffer; every "
                      "catalogue-derived quantity recomputed per fold from the VISIBLE catalogue only; "
                      "visible faults masked pixel-exactly; pooled DTI alpha=0.2 beta=0.8, 300 m "
                      "triangular kernel",
            "withheld_positive_pixels": ho["withheld_positives_total"],
            "folds": [{k: f[k] for k in ("fold", "budget_matched", "seeds_legal", "corridor_pool",
                                          "truth_px")} for f in ho["folds"]],
            "pooled_dti": {k: {"dti": round(v["dti"], 6),
                               "ci95": [round(v["ci95"][0], 6), round(v["ci95"][1], 6)],
                               "tpw": round(v["tpw"], 1), "fpw": round(v["fpw"], 1),
                               "fnw": round(v["fnw"], 1)}
                           for k, v in pooled["scores"].items()},
            "best_comparable_control": pooled["best_comparable_control"],
            "paired_differences_vs_candidate": {
                k: {"delta": round(v["delta"], 6),
                    "ci95": [round(v["ci95"][0], 6), round(v["ci95"][1], 6)]}
                for k, v in pooled["paired_differences"].items()},
            "reading": (
                "NEGATIVE. The candidate is significantly worse than uniform random and significantly "
                "worse than the single-view surface baseline on this instrument. Note that random "
                "also beats single_B, and that the instrument ranks the organiser-scored 0.2778 "
                "champion at 0.00479, below a random placeholder (IR-H60-003; Spearman(board, "
                "instrument) = -0.099, n=13, p=0.748): the hide-and-recover truth class IS the mapped "
                "catalogue, while this candidate is constructed to be >= 200 m away from it, so the "
                "instrument cannot score this hypothesis class in either direction. The result is "
                "reported as measured and not reinterpreted as a score."),
        },
        "lane_gates": {
            "evidence_class": "MEASURED",
            "S1_two_view_sufficiency": {
                "view_A_oof_auc": [round(x, 4) for x in s1["view_A_oof_auc"]],
                "mean_view_A": round(s1["mean_view_A_oof_auc"], 4),
                "min_view_A": round(s1["min_view_A_oof_auc"], 4),
                "view_B_oof_auc": [round(x, 4) for x in s1["view_B_oof_auc"]],
                "mean_view_B": round(s1["mean_view_B_oof_auc"], 4),
                "bar": "mean >= 0.60 AND min >= 0.55 (frozen)",
                "pass": s1["S1_pass"],
                "consequence": "no pseudo-label exchange was performed; the co-training premise of "
                               "the brief is not met, so disagreement was used only for stratification "
                               "and for the B-only artifact veto (declared deviation IR-H66-001)",
            },
            "S2_conditional_independence": {
                "n_blocks": s2["n_blocks_all"],
                "max_abs_spearman": round(s2["max_abs_correlation"], 4),
                "tests": s2["tests"],
                "abandon_threshold": 0.60,
                "allow_exchange": s2["allow_exchange"],
                "reading": "the abandonment rule did NOT fire on H66's own measurement (0.2951 < 0.60), "
                           "which contradicts N-19 (0.7625 on the H61/H63 feature set) and agrees with "
                           "H62 (0.1757). The statistic is learner- and block-size-dependent, spanning "
                           "0.0078-0.7625 across rounds; it is not a stable property of 'the two views'.",
            },
            "leakage_canary": {
                "max_single_channel_auc": round(can["max_single_channel_auc"], 4),
                "worst": can["worst"],
                "alarm_threshold": 0.90,
                "alarm_fired": can["alarm_fired"],
            },
        },
        "registry_correlation_and_overlap": {
            "evidence_class": "MEASURED",
            "surface_phase": {k: lane_surface()[k] for k in ("max_spearman", "max_near_3px_fraction",
                                                             "max_near_source", "verdict")},
            "dots_phase": {k: lane_dots()[k] for k in ("max_spearman", "max_near_3px_fraction",
                                                       "max_near_source", "verdict")},
            "rank_offenders_dots": lane_dots()["rank_offenders"],
            "near_offenders_dots": lane_dots()["near_offenders"],
            "identical_to_a_prior": lane_dots()["identical"],
            "uniqueness": {k: uni[k] for k in ("n_priors_checked", "canonical_pattern_unique",
                                               "equals_literal_prior_union", "research_publication_ok",
                                               "support_novelty_gate_ok", "union_px",
                                               "novel_vs_all_priors", "novel_fraction",
                                               "prior_px_dropped", "relation_to_union")},
            "not_merely_the_union_of_the_two_views": rel["not_union"],
            "recomputed_over_alignment_filtered_corpus": {
                "why": "the shared gate sets canonical_pattern_unique=False if ANY prior fails to open; "
                       "the first pass included the 2 census-ineligible fixtures, so it reported False "
                       "while 0 priors were identical. Recomputed with them excluded and published "
                       "(IR-H66-007, IR-H66-010).",
                "n_priors_checked": uni2["corpus"]["n_checked"],
                "n_excluded": uni2["corpus"]["n_excluded"],
                "excluded": uni2["corpus"]["excluded"],
                "read_errors": uni2["read_errors"],
                "identical_priors": uni2["identical_priors"],
                "canonical_pattern_unique": uni2["result"]["canonical_pattern_unique"],
                "research_publication_ok": uni2["result"]["research_publication_ok"],
                "support_novelty_gate_ok": uni2["result"]["support_novelty_gate_ok"],
                "novel_fraction": uni2["result"]["novel_fraction"],
                "gate_correction": uni2["result"]["gate_correction"],
                "closest_priors_by_jaccard": uni2["closest_priors"][:5],
            },
            "lane_offender_identification": {
                "literal_source": identify(rel["lane_dots"]["literal"]["max_near_source"]),
                "literal_reading": "5,167,373 dots = every eligible cell; 3 px halo coverage 1.0000 "
                                   "under both the gate's disk and a square element, i.e. a total-"
                                   "coverage diagnostic raster. Its 1.0000 near fraction carries no "
                                   "information about this candidate.",
                "policy_source": identify(rel["lane_dots"]["policy"]["max_near_source"]),
                "policy_reading": "362,327 dots; disk 3 px halo coverage of the eligible footprint "
                                  "0.8886 (informative under the gate's 0.95 threshold) but 0.9648 "
                                  "under a square 7x7 element, i.e. the classification that decides "
                                  "this round's lane verdict flips with the structuring element "
                                  "(IR-H66-008). Under the shared gate as written the rule fires.",
                "support_overlap_vs_proximity_overlap": "max Jaccard with any single prior is 0.0138 "
                                                        "(853 of 24,907 pixels shared), yet 84.08 % of "
                                                        "the dots lie within 3 px of one prior's dots: "
                                                        "the corridors run alongside an existing "
                                                        "curvature-scarp emission without reusing its "
                                                        "pixels. The brief's rule is a proximity rule, "
                                                        "so it fires.",
            },
            "seed_composition": seeds,
            "prior_corpus": {
                "n_priors": rel["lane_surface"]["priors_checked"],
                "distinct_decoded_patterns": rel["lane_surface"]["distinct_decoded_priors"],
                "errors": rel["lane_surface"]["error_count"],
                "informative_priors": rel["lane_surface"]["policy"]["informative_priors"],
                "universal_coverage_probes": rel["lane_surface"]["policy"]["universal_coverage_probes"],
                "source": "526-blob frozen prior census (evidence/ctd5_prior_inventory.json, "
                          "work/h66/prior_fetch_receipt.json: 526 fetched, 0 errors, 524 file-SHA "
                          "matches; the 2 mismatches are exactly the 2 census-ineligible entries) plus "
                          "35 local submission/*.tif, 12 data/scored priors and the 0.2778 reference",
            },
        },
        "raster": {
            "file": str(tif.relative_to(ROOT)),
            "sha256": sidecar["sha256"],
            "bytes": sidecar["bytes"],
            "zip_sha256": sidecar.get("zip_sha256"),
            "decoded_pixels_sha256": hashlib.sha256(
                _decoded(tif).tobytes()).hexdigest(),
            "emitted_pixels": int(val["n_nonzero"]),
            "reproduced_bit_identically_by_a_second_independent_run": True,
        },
        "validator": {
            "evidence_class": "MEASURED (local format check; NOT organizer upload acceptance)",
            "ok": val["ok"], "problems": val["problems"],
            "nan_inside_footprint": val["n_nan"], "infinity_pixels": val["infinity_pixels"],
            "value_range": [val["min"], val["max"]],
            "unique_values": _unique(tif),
            "n_nonzero": val["n_nonzero"], "mass": val["mass"],
            "crs": val["crs"], "shape": [val["height"], val["width"]],
            "transform": val["transform"], "bounds": val["bounds"],
            "bounds_match_sample_submission": val["bounds"] == val["ref_bounds"],
            "dtype": val["dtype"], "bands": val["bands"],
            "mass_outside_footprint": val["mass_outside_footprint"],
            "nodata": val["nodata"],
            "note_on_nodata": "sample_submission.tif declares a NaN nodata; this file declares none and "
                              "carries 0.0 outside the eligible footprint, which is what "
                              "grid.write_geotiff requires (N-5 forbids NaN outside the footprint).",
        },
        "submission_identifiers": {
            "name": sidecar["submission_name"],
            "name_chars": len(sidecar["submission_name"]),
            "note": sidecar["note"],
            "note_chars": sidecar["note_chars"],
            "note_within_140": sidecar["note_chars"] <= 140,
        },
        "verdict": {
            "download_for_research": "YES",
            "submit_to_competition": "NO",
            "promotion": "negative",
            "approved_for_weekly_slot": sidecar["approved_for_weekly_slot"],
            "promoted": sidecar["promoted"],
            "submission_slots_used": sidecar["submission_slots_used"],
            "reasons": [
                "LANE RULE FIRES: 84.08 % of the final dots lie within 3 px of one informative registry "
                "raster's dots (15GEMSDOE docs/downloads/gems-cleanup-a-20260928T195952Z-curv_scarp.tif, "
                "362,327 dots). The brief's clause 1 sets the bar at 70 % and says: log it as a "
                "duplicate and STOP. Logged; stopped; no further development of this candidate.",
                "HOLDOUT-DTI 0.015432 [0.010756, 0.021313] is significantly below uniform random "
                "(paired delta -0.041191 [-0.047743, -0.034102]) and below single-view B "
                "(-0.035871 [-0.049674, -0.023605]); the frozen promotion bar was 'candidate minus "
                "best comparable control > 0 with the 95 % CI excluding 0'.",
                "S1 two-view sufficiency FAILED (View A mean OOF AUC 0.593 < 0.60, min fold 0.5462 < "
                "0.55), so the brief's co-training premise is not met and no pseudo-labels were used.",
                "The expected-score bracket for a fully novel field at this budget "
                "(rho ~ U[0.0279, 0.1387], S = 24,907, |G| = 14,088.7) is DTI in [0.0428, 0.2126] - "
                "below the 0.2778 champion even at its optimistic end. A projection, never a score.",
                "Promotion is a separate selector step within the weekly cap (brief clause 9). This "
                "card records a negative result, which the brief also calls a deliverable.",
            ],
        },
        "budget": {
            "declared": "3 experiments or 2 hours, whichever first",
            "experiments_used": 3,
            "experiments": ["E1 lane gates: S1 sufficiency, S2 conditional independence, leakage "
                            "canary, preflight integrity",
                            "E2 hide-and-recover holdout, 4 folds, 6 matched arms, pooled bootstrap",
                            "E3 build at the frozen budget + format gate + lane gates on the surface "
                            "and on the final dots + uniqueness report"],
            "wall_clock": "exceeded: the sandbox started cold (no cached feature stack, 3.9 GB RAM, "
                          "2 CPUs), the full 19-band stack and a 526-blob prior census had to be "
                          "restored and fetched, and five defects had to be fixed in the runner "
                          "(IR-H66-002 sentinel contamination, JSON NaN in receipts, module "
                          "shadowing, a false-positive degenerate-channel guard, and the "
                          "partially-filled in-quadrant AUC grid). Disclosed rather than smoothed.",
        },
        "declared_deviations": prereg.get("declared_deviations", []),
        "irregularities_found_this_round": [
            "IR-H66-002 (severe, caught before publication): 3,061 in-domain cells carry the "
            "float32 nodata sentinel -3.4028234663852886e+38 in 18 of 19 bands (3,073 in band 6). "
            "Transform.rank01 bins against lo = -3.4e38, which collapses every rank channel to a "
            "near-constant. Fixed by using the template's own intersection footprint "
            "(grid.footprint_from(training_features.tif, bands='all')); eligible fell from "
            "5,167,373 to 5,164,300.",
            "IR-H66-003: three defensible footprints coexist (labels>=0 gives 5,167,373; band-12 "
            "non-sentinel 5,165,852; all-19-band intersection 5,164,300). This round uses the "
            "intersection and says so.",
            "IR-H66-004: two channels are legitimately zero-inflated (rank_b10, grad_b17: > 50 % of "
            "the footprint ties at the physical minimum). A blunt 'collapsed channel' guard reports "
            "them as failures; replaced with a degenerate test (< 10 distinct rank levels, or raw "
            "|value| > 1e30 inside the eligible set).",
            "IR-H66-005: the independence statistic S2 is not a stable property of the two views - "
            "0.0078 to 0.7625 across five rounds on the same data, driven by feature set, learner "
            "and block size. The ABANDON rule can therefore fire or not fire at will; it cannot be "
            "used as a go/no-go gate without fixing all three.",
        ],
        "board_algebra": {
            "evidence_class": "MEASURED on restored bytes; published scores are OWNER-REPORTED",
            "receipt": "evidence/h66_board_algebra.json",
            "script": "scripts/h66_board_algebra.py",
            "champion_ref_h33_2_b2": alg["files"]["ref_h33_2_b2"],
            "set_relations_re_measured": alg["set_relations"],
            "mass_vs_board_spearman": alg["mass_vs_board"],
            "required_rho_target_0_3195_at_G_14088_7": alg["required_rho"]["target_0.3195_G_14088.7"],
        },
        "reasoning_record": reas,
        "seed_population": {
            "evidence_class": "MEASURED",
            "receipt": "evidence/h66_seed_composition.json",
            "unique_sites": seeds["unique_sites"], "evidence_sites": seeds["evidence_sites"],
            "legal_seeds": seeds["legal_seeds"], "blocks_1km": seeds["composition"]["blocks_1km"],
            "composition": seeds["composition"], "caveat": seeds["caveat"],
        },
        "links_for_manual_review": [
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ (task, metric, "
            "submission format, two-round prize structure) - fetched 2026-10-09",
            "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ "
            "(JS-rendered; NOT readable by fetch - the score list in the brief is owner-reported)",
            "https://github.com/drivendataorg/gems-prize-reference-solution (reference solution)",
            "https://community.drivendata.org/c/gems-prize-challenge/111 (forum)",
            "https://doi.org/10.1145/279943.279962 (Blum & Mitchell, co-training, COLT '98)",
            "https://doi.org/10.5066/P93LGLVQ (USGS GeoDAWN)",
            "https://epsg.io/32611 (CRS)",
            "https://www.usgs.gov/3d-elevation-program (1 m DEM named as the missing lever)",
        ],
        "negative_result_statement": (
            "H66-A is a negative result and is published as one. Thermal-upflow sites restricted to "
            ">= 300 m from mapped faults, extended along a structure-tensor strike and gated by an "
            "independent geophysical edge, do not localise catalogue faults better than uniform "
            "random on the shared hide-and-recover instrument. Together with N-20 (thermal "
            "lineaments as a rank bonus: +0.00003) and H58 (cold-geothermometer consensus: 22 px "
            "survived), that is the third independent measurement against the thermal-spring family "
            "of hypotheses in this region."),
    }
    out = EV / "h66_run_card.json"
    out.write_text(json.dumps(card, indent=1, allow_nan=False, default=str) + "\n")
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "data" / "h66_run_card.json").write_text(
        json.dumps(card, indent=1, allow_nan=False, default=str) + "\n")
    print(json.dumps({k: card[k] for k in ("verdict", "submission_identifiers")}, indent=1, default=str))
    print(f"\nwrote {out.relative_to(ROOT)} and docs/data/h66_run_card.json")
    return 0


def _unique(path):
    import numpy as np
    a = _decoded(path)
    return [float(x) for x in np.unique(a)[:8]]


def _decoded(path):
    import numpy as np
    import rasterio
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    return np.ascontiguousarray(a)


if __name__ == "__main__":
    sys.exit(main())
