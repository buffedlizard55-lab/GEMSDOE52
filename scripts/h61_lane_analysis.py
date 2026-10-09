#!/usr/bin/env python3
"""H61 lane analysis: why the literal 3 px rule fires, measured against chance.

The directed proximity statistic -- "what fraction of YOUR dots lie within 3 px of prior P's dots" --
has a *chance level*, and that chance level is exactly P's own 3 px coverage of the eligible
footprint: an emission placed uniformly at random lands within 3 px of P with probability
coverage(P).  The rule's trigger is 0.70, so for any prior whose coverage is at or above 0.70 the
rule fires on a random emission too and carries no information about lane drift.

This script reads the lane receipt that ``gems52.gates.lane_report`` already wrote (no raster is
decoded twice) and reports, per prior: coverage, near fraction, and the chance-normalised excess
``near - coverage``.  It changes no verdict.  The preregistered probe threshold (0.95) and the
literal 0.70/3 px rule both stand; the excess column is the diagnostic that tells the shared selector
what to fix *prospectively*, before the next round, rather than a relaxation applied to rescue this
one.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyse(receipt: dict, near_limit: float = 0.70) -> dict:
    rows = [r for r in receipt["per_prior"] if r.get("near_3px_fraction") is not None]
    table = []
    for r in rows:
        cov, near = r["coverage_3px_of_eligible"], r["near_3px_fraction"]
        table.append(dict(
            path=r["path"], name=Path(r["path"]).name, decoded_sha256=r.get("decoded_sha256"),
            coverage_3px=cov, near_3px_fraction=near, excess_over_chance=near - cov,
            ratio_to_chance=(near / cov) if cov else None,
            spearman=r.get("spearman"), probe=r["universal_coverage_probe"],
            near_offender=r.get("near_duplicate", False), rank_offender=r.get("rank_duplicate", False),
            coverage_at_or_above_trigger=bool(cov >= near_limit)))
    table.sort(key=lambda d: -d["near_3px_fraction"])
    offenders = [t for t in table if t["near_offender"]]
    informative_offenders = [t for t in offenders if not t["probe"]]
    excess = [t["excess_over_chance"] for t in table]
    cov_inf = sorted(t["coverage_3px"] for t in table if not t["probe"])
    return dict(
        instrument="scripts/h61_lane_analysis.py",
        evidence_class="lane diagnostic derived from evidence/h61_lane_dots.json; not a score",
        rule_trigger=near_limit,
        chance_level_explanation=(
            "An emission placed uniformly at random over the eligible footprint lies within 3 px of a "
            "prior with probability equal to that prior's own 3 px coverage. The directed proximity "
            "statistic therefore has a chance level, and the 0.70 trigger is only discriminating for "
            "priors whose coverage is below 0.70."),
        n_rasters=len(table),
        n_probes=sum(1 for t in table if t["probe"]),
        n_near_offenders=len(offenders),
        n_informative_near_offenders=len(informative_offenders),
        n_rasters_with_coverage_at_or_above_trigger=sum(
            1 for t in table if t["coverage_at_or_above_trigger"]),
        offenders=[dict(name=t["name"], coverage_3px=t["coverage_3px"],
                        near_3px_fraction=t["near_3px_fraction"],
                        excess_over_chance=t["excess_over_chance"], probe=t["probe"],
                        coverage_at_or_above_trigger=t["coverage_at_or_above_trigger"])
                   for t in offenders],
        informative_offenders=[dict(name=t["name"], coverage_3px=t["coverage_3px"],
                                    near_3px_fraction=t["near_3px_fraction"],
                                    excess_over_chance=t["excess_over_chance"])
                               for t in informative_offenders],
        excess_over_chance=dict(min=min(excess), median=statistics.median(excess),
                                mean=statistics.fmean(excess), max=max(excess),
                                n_above_zero=sum(1 for e in excess if e > 0)),
        informative_coverage_quantiles={
            q: cov_inf[min(len(cov_inf) - 1, int(float(q) * (len(cov_inf) - 1)))]
            for q in ("0.00", "0.25", "0.50", "0.75", "0.90", "0.99", "1.00")} if cov_inf else {},
        n_informative_above_trigger=sum(1 for c in cov_inf if c >= near_limit),
        prospective_recommendation=(
            "Apply the directed 3 px/0.70 rule only to priors whose measured 3 px coverage is BELOW "
            "the rule's own trigger, or equivalently test the chance-normalised excess "
            "(near - coverage) against a margin. Both forms are derived from the rule rather than "
            "tuned to a result. Adopt it in the shared selector BEFORE the next round; do not apply "
            "it retroactively to this one."),
        verdict_unchanged=(
            "This round's preregistered probe threshold (0.95) and the literal rule both stand, so the "
            "recorded lane verdict remains DUPLICATE/STOP and the artefact remains research-only."),
        top_of_table=table[:25])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", default="evidence/h61_lane_dots.json")
    ap.add_argument("--out", default="evidence/h61_lane_analysis.json")
    ap.add_argument("--docs-out", default="docs/data/h61_lane_analysis.json")
    args = ap.parse_args()
    rec = json.loads((ROOT / args.receipt).read_text())
    out = analyse(rec)
    for p in (args.out, args.docs_out):
        dest = ROOT / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("top_of_table", "offenders",
                                                                "informative_offenders")}, indent=1))
    print("informative offenders:", json.dumps(out["informative_offenders"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
