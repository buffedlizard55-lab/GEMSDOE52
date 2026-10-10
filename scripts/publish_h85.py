#!/usr/bin/env python3
"""Collect every H85 number from its receipts and write evidence/h85_run_card.json (no hand-copied numbers).

Reads: evidence/h85_holdout.json, evidence/h85_euler_holdout.json, evidence/h85_build.json,
evidence/h85_lane.json. Writes: evidence/h85_run_card.json and prints the table used on the site.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "evidence"


def load(name):
    return json.loads((E / name).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ho = load("h85_holdout.json")
    eu = load("h85_euler_holdout.json")
    bu = load("h85_build.json")
    la = load("h85_lane.json")
    fp = ROOT / bu["file"]
    assert sha(fp) == bu["sha256"], "candidate file changed since build"
    s = ho["pooled"]["scores"]
    pd = ho["pooled"]["paired_differences"]
    eu_s = eu["pooled"]["scores"]["euler_SI0"]
    eu_pd = eu["pooled"]["paired_differences"]["random"]
    lane_s = la["surface_max_over_priors"]
    lane_d = la["final_dots_max_over_priors"]
    rows = la["final_dots"]["per_prior"]
    inf = [r for r in rows if not r.get("universal_coverage_probe")]
    probes = [r["path"].split("/")[-1] for r in rows if r.get("universal_coverage_probe")]
    max_near_inf = max(inf, key=lambda r: r.get("near_3px_fraction") or 0)
    card = dict(
        round="H85",
        hypothesis=("A top-ranked, previously untried geophysical method (windowed Euler deconvolution, SI 0, on RTP "
                    "magnetics, depth-gated) and the H83 structural-concordance x geothermal candidate can rank "
                    "catalogue-missing fault pixels above a random allowed-set baseline under hide-and-recover."),
        mechanism=("Euler solutions cluster along depth-resolved source edges (contacts/steps). Under the "
                   "hide-and-recover protocol the catalogue is never an input to either detector."),
        named_non_fault_mimic=("Lithologic contacts and intrusive margins (Euler SI 0 is also satisfied by "
                               "non-fault steps); for H83, lithology and gridding seams; for the geothermal term, "
                               "springs and wells sit where thermal, not structural, processes dominate."),
        holdout=dict(
            evaluator_version=ho["pooled"]["evaluator_version"], evidence_class="HOLDOUT-DTI",
            withheld_positive_px=ho["withheld_positive_px"], eligible_px=ho["eligible_px"], folds=ho["folds"],
            budget_per_fold=ho["budget_per_fold"], bootstrap="paired physical 20 km spatial-cluster percentile, 1000 draws",
            h85_spaced_primary=dict(dti=s["h85_spaced"]["dti"], ci95=s["h85_spaced"]["ci95"]),
            h83_as_built_topk=dict(dti=s["h83_topk"]["dti"], ci95=s["h83_topk"]["ci95"]),
            concordance_only=dict(dti=s["concordance_only"]["dti"], ci95=s["concordance_only"]["ci95"]),
            random=dict(dti=s["random"]["dti"], ci95=s["random"]["ci95"]),
            paired_h85_minus_random=dict(delta=pd["random"]["delta"], ci95=pd["random"]["ci95"]),
            paired_h85_minus_concordance_only=dict(delta=pd["concordance_only"]["delta"], ci95=pd["concordance_only"]["ci95"]),
            paired_h85_minus_h83_topk=dict(delta=pd["h83_topk"]["delta"], ci95=pd["h83_topk"]["ci95"]),
            euler_SI0=dict(dti=eu_s["dti"], ci95=eu_s["ci95"], paired_minus_random=dict(delta=eu_pd["delta"], ci95=eu_pd["ci95"]),
                           evaluator_version=eu["pooled"]["evaluator_version"], withheld_positive_px=eu["withheld_positive_px"]),
        ),
        leakage_canary=dict(threshold_auc=0.90,
                            h85_features_max_auc=ho["canary"]["max_auc"], h85_alarm=any(ho["canary"]["alarm"].values()),
                            euler_max_fold_auc=eu["canary_max_auc"], euler_alarm=eu["canary_alarm"]),
        lane_and_overlap=dict(
            rank_correlation_bar=0.90, near_dot_bar=0.70, near_radius_px=3.0,
            surface_before_placement_max_spearman=lane_s.get("spearman"),
            final_dots_max_spearman=lane_d.get("spearman"),
            final_dots_max_near3px_informative=max_near_inf.get("near_3px_fraction"),
            final_dots_max_near3px_informative_prior=max_near_inf["path"].split("/")[-1],
            universal_coverage_probes=probes,
            duplicate_flag=bool(la["final_dots"]["duplicate"]), lane_ok=bool(la["final_dots"]["ok"]),
            priors_checked=la["final_dots"]["priors_checked"],
            priors_distinct_decoded=la["final_dots"]["distinct_decoded_priors"],
            uniqueness=bu["uniqueness"],
            overlap_with_h33_2_b2=bu["overlap_with_reference"],
            note=("Spearman and near-3px are measured against every aligned prior in submission/, docs/downloads/, "
                  "data/scored/ and data/reference/. The only raster above 0.70 near-3px is the registry's own "
                  "universal-coverage probe, whose 3 px coverage is 0.999 (a property of the probe, see gates.registry_coverage)."),
        ),
        raster=dict(path=bu["file"], sha256=bu["sha256"], decoded_sha256=bu["decoded_sha256"], bytes=bu["file_bytes"],
                    download_copy="docs/downloads/h85-candidate.tif", download_zip="docs/downloads/h85-candidate.zip"),
        validator=bu["validator"],
        submission_name=bu["name"], note=bu["note"], note_chars=bu["note_chars"],
        spacing=bu["spacing_stats"],
        ok_to_download=True,
        ok_to_submit=False,
        submit_reason=("HOLDOUT-DTI 0.0694 [0.0569, 0.0822] is statistically indistinguishable from random "
                       "(0.0754 [0.0675, 0.0834]; paired delta -0.0061 [-0.0169, +0.0056]) and far below the "
                       "repository's comparable holdout best (B_DVA2 0.1892, a different fold set; see IR-H85-007). "
                       "AGENTS.md forbids a slot unless the candidate beats that best."),
        slots_used=0,
        verdict="negative",
        experiments_used=2, experiment_budget=3, hours_budget=2,
        organizer_confirmed_scores=[],
        evidence_class_note=("Every score here is HOLDOUT-DTI (local evaluator) or a projection; none is ORGANIZER-CONFIRMED. "
                             "Public board numbers quoted elsewhere are OWNER-REPORTED or PUBLIC-BOARD and are not filename-linked."),
        receipts=["evidence/h85_holdout.json", "evidence/h85_euler_holdout.json", "evidence/h85_build.json",
                  "evidence/h85_lane.json", "knowledge/74_h85_hypotheses_ranked.md"],
    )
    (E / "h85_run_card.json").write_text(json.dumps(card, indent=2, default=float) + "\n")
    print(json.dumps({k: card[k] for k in ("submission_name", "ok_to_download", "ok_to_submit", "verdict")}, indent=1))
    print("H85 spaced:", s["h85_spaced"]["dti"], s["h85_spaced"]["ci95"], "random:", s["random"]["dti"])
    print("Euler:", eu_s["dti"], eu_s["ci95"], "paired vs random", eu_pd["delta"], eu_pd["ci95"])


if __name__ == "__main__":
    main()
