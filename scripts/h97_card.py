#!/usr/bin/env python3
"""Assemble the single H97 JSON run card from receipts on disk only (no recomputation, no typed numbers)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
REG = json.loads((ROOT / "registry/h97_preregistration.json").read_text())


def load(n):
    return json.loads((EV / f"h97_{n}.json").read_text())


def main():
    fit, ind, ho, bf, ln, bu, orient = (load(n) for n in
                                        ("fit", "independence", "holdout", "build_fields", "lane", "build", "orient"))
    sc = ho["pooled"]["scores"]
    pdB = ho["pooled"]["paired_differences"]["B_DVA2"]
    P = REG["primary_arm"]
    tif = ROOT / bu["file"]
    sha = hashlib.sha256(tif.read_bytes()).hexdigest()
    assert sha == bu["sha256"], "raster bytes moved after the write stage"
    lit_s = ln["full_surface"]["literal"]
    lit_d, pol_d = ln["full_dots"]["literal"], ln["full_dots"]["policy"]
    uq = bu["uniqueness"]
    gates = dict(
        controls_reproduce=all(v["PASS"] for v in ho["controls"].values()),
        leakage_canary=not fit["canary_alarm_any"],
        independence_not_abandoned=all(p["result"]["allow_exchange"] for p in ind["pairs"].values()),
        holdout_bar=bool(sc[P]["dti"] > REG["holdout_bar"]),
        holdout_paired_vs_B_DVA2=bool(pdB["ci95"][0] > 0),
        lane_surface_literal=not str(lit_s["verdict"]).upper().startswith("DUPLICATE"),
        lane_dots=not (str(lit_d["verdict"]).upper().startswith("DUPLICATE")
                       and str(pol_d["verdict"]).upper().startswith("DUPLICATE")),
        uniqueness=bool(uq["distinct_from_every_comparable_prior"] and not uq["equals_literal_prior_union"]),
        format=bool(bu["validator"]["PASS"]),
        not_the_union=bool(bu["not_the_union"]["not_union_pass"]))
    promote = all(gates.values())
    failed = [k for k, v in gates.items() if not v]
    S = lambda a: dict(label="HOLDOUT-DTI", evaluator=ho["evaluator"],  # noqa: E731
                       withheld_positive_px=sc[a]["withheld_positive_pixels"], dti=sc[a]["dti"], ci95=sc[a]["ci95"])
    card = dict(
        round="H97", generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        preregistration=dict(document=REG["hypothesis_document"], sha256=REG["hypothesis_sha256"],
                             frozen_utc=REG["preregistered_utc"]),
        hypothesis=("In the co-training lane, cells where the surface view (B) is confident and the geophysical "
                    "view (A) is not are the brief's surface-artefact suspects. Where such a cell's linear feature "
                    "runs down the fall line (gully/rill/drainage) or exactly N-S/E-W on a low-slope floor "
                    "(section-line road), demoting it and refilling the budget with the next-ranked cells raises "
                    "credit per dot."),
        mechanism=("Hessian (sigma 2 px) of detrended elevation (band 12): the along-feature axis is the "
                   "smaller-|curvature| eigenvector; FL = |cos| of its angle to the downslope gradient. Fault "
                   "scarps run across slope (Wallace 1977, doi:10.1130/0016-7606(1977)88<1267:PAAOYF>2.0.CO;2); "
                   "drainage runs down it. B-only = r_B >= 0.95 and r_A < 0.65 (B = B_DVA2 OOF, A = single_A OOF)."),
        named_non_fault_mimics=["drainage lines, gullies and erosion rills (fall-line aligned)",
                                "section-line roads and fences (cardinal, low slope)",
                                "for the vetoed side: fault-controlled drainage and N-S range-front faults are real "
                                "faults that the veto would wrongly demote"],
        independence=dict((k, dict(max_abs_rho=v["result"]["max_abs_correlation"], n_blocks=v["result"]["n_blocks"],
                                   abandon_at=ind["thresholds"]["abandon_max_abs_rho"]))
                          for k, v in ind["pairs"].items()),
        view_A_sufficiency=fit["sufficiency_view_A"],
        leakage_canary=dict(max_auc=fit["canary_max_overall"], bar=fit["canary_alarm_auc_bar"],
                            fall_line_alone=[r["canary"]["H97_FL"] for r in fit["folds"]],
                            dcard_alone=[r["canary"]["H97_DCARD"] for r in fit["folds"]]),
        holdout={a: S(a) for a in REG["arms"]},
        primary_minus_B_DVA2=dict(label="HOLDOUT-DTI paired", delta=pdB["delta"], ci95=pdB["ci95"]),
        attribution_minus_B_DVA2={k: dict(delta=v["delta"], ci95=v["ci95"]) for k, v in ho["vs_B_DVA2"].items()},
        control_reproduction=ho["controls"],
        control_dot_strata_per_fold=[r["control_dot_strata"] for r in ho["folds"]],
        build_fields=bf, orientation_descriptives=orient,
        lane=dict(surface_literal=dict(verdict=lit_s["verdict"], max_spearman=lit_s["max_spearman"]),
                  dots_literal=dict(verdict=lit_d["verdict"], max_near_3px=lit_d["max_near_3px_fraction"],
                                    worst=lit_d["max_near_source"]),
                  dots_policy=dict(verdict=pol_d["verdict"],
                                   max_near_3px=pol_d["max_near_3px_fraction"],
                                   worst=pol_d["max_near_source"],
                                   probes_excluded=pol_d["universal_coverage_probes"]),
                  placement=ln.get("emitted_placement"), n_registry=ln.get("n_full")),
        uniqueness={k: v for k, v in uq.items() if not isinstance(v, (list, dict))},
        not_the_union=bu["not_the_union"],
        raster=dict(file=bu["file"], bytes=bu["bytes"], sha256=sha, download=bu["download_staged"]),
        validator=bu["validator"],
        submission=dict(name=bu["name"], note=bu["note"], note_chars=bu["note_chars"]),
        a_only_reasoning=dict(csv=bu["a_only_reasoning_csv"], rows=bu["a_only_rows"]),
        gates=gates, failed_gates=failed,
        verdict="promote" if promote else "negative",
        ok_to_download=bool(bu["validator"]["PASS"]),
        ok_to_submit=bool(promote),
        submission_slots_used=0,
        experiments_used="3 of 3")
    (EV / "h97_run_card.json").write_text(json.dumps(card, indent=1, default=float, allow_nan=False) + "\n")
    print(json.dumps(dict(verdict=card["verdict"], failed=failed, sha256=sha), indent=1))


if __name__ == "__main__":
    main()
