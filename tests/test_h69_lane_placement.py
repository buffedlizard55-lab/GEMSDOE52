"""Guards for the H69 round: the frozen preregistration, the withdrawal amendment, and the two
defects this round actually hit.

Both defects are recorded here because both were *silent* when they happened:

1. A quota cap of ``floor(0.6985 * S)`` is computed against a **target** budget. When the greedy cannot
   reach that target the achieved share rises above the literal limit -- measured in this round at
   26,263 / 35,149 = 0.7472 against a limit of 0.70. The shipped construction excludes offenders'
   halos from the pool instead, which has no denominator.
2. The committed instrument's ``eligible`` mask is the **valid footprint including catalogue pixels**.
   Passing the off-catalogue set empties both training classes (``spatial.folds`` builds
   ``truth = held_all & region`` from the catalogue), which surfaces as "insufficient training
   classes" and, on a screen that only computes an AUC, as a silently wrong sufficiency number.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_frozen_preregistration_hash_matches_the_pinned_document():
    reg = json.loads((ROOT / "registry/h69_preregistration.json").read_text())
    doc = ROOT / reg["preregistration_file"]
    assert doc.exists(), f"preregistration document missing: {doc}"
    assert sha(doc) == reg["preregistration_sha256"]
    runner = (ROOT / "scripts/run_h69.py").read_text()
    assert reg["preregistration_sha256"] in runner, (
        "scripts/run_h69.py must pin the same hash it is registered with, or it cannot refuse to run "
        "when the frozen document moves")


def test_amendment_withdrawing_the_credited_core_is_registered():
    reg = json.loads((ROOT / "registry/h69_preregistration.json").read_text())
    amd = ROOT / reg["amendment_file"]
    assert amd.exists()
    assert sha(amd) == reg["amendment_sha256"]
    text = amd.read_text()
    for needle in ("withdrawn", "IR-UNQ-001", "IR-H61-007", "novel-only",
                   "re-tune a negative result into a positive"):
        assert needle in text, f"amendment must state {needle!r}"


def test_preregistration_document_itself_was_never_edited():
    """The pinned document keeps its original hash; the change lives in a separate amendment."""
    reg = json.loads((ROOT / "registry/h69_preregistration.json").read_text())
    text = (ROOT / reg["preregistration_file"]).read_text()
    assert "credited core" in text, "the original preregistration still records what it pre-registered"
    assert "WITHDRAWN" not in text, (
        "the withdrawal must be an amendment, not an edit to the frozen document")


@pytest.mark.parametrize("name", ["h69_run_card.json", "h69_holdout.json", "h69_s1.json",
                                  "h69_independence.json", "h69_canary.json", "h69_format_gate.json",
                                  "h69_uniqueness.json", "h69_lane_dots.json", "h69_lane_surface.json",
                                  "h69_placement.json", "h69_a_only.json"])
def test_receipt_exists(name):
    assert (ROOT / "evidence" / name).exists(), f"missing receipt evidence/{name}"


def test_run_card_is_portal_safe_and_lane_clean_and_not_promoted():
    card = json.loads((ROOT / "evidence/h69_run_card.json").read_text())
    val = card["validator"]
    assert val["bands"] == 1 and val["dtype"] == "float32"
    assert val["crs"] == "EPSG:32611"
    assert val["shape"] == [3730, 3292]
    assert tuple(val["transform"]) == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
    assert val["no_nan_inside_footprint"] and val["values_in_0_1"]
    assert card["gates"]["format"], "the format gate must pass before anything is served"
    assert card["slots_used"] == 0
    pol = card["correlation_vs_registry"]["policy"]
    assert pol["max_near_3px"] <= 0.70, pol
    assert pol["max_spearman"] <= 0.90, pol
    assert card["overlap_vs_registry"]["canonical_pattern_unique"]
    # the withdrawal is real: no inherited core mass in the shipped file
    assert card["overlap_vs_registry"]["core_px"] == 0


def test_placement_receipt_records_the_exclusion_construction_not_the_quota():
    pl = json.loads((ROOT / "evidence/h69_placement.json").read_text())
    assert pl["n_core"] == 0
    assert pl["feasible"], "the file only ships if the re-measurement against every informative prior is clean"
    assert pl["S_placed"] >= 0.9 * pl["S_requested"], "a large budget shortfall must be reported, not shipped silently"
    assert pl["worst_informative_near_share"] <= 0.70
    assert "exclusion_rather_than_quota" in pl
    # the cap's denominator must be the achieved S, not the target S
    assert pl["worst_informative_near"] <= int(pl["margin"] * pl["S_placed"])


def test_instrument_uses_the_valid_footprint_as_eligible():
    """Defect 2: an off-catalogue `eligible` empties both training classes."""
    hold = json.loads((ROOT / "evidence/h69_holdout.json").read_text())
    assert hold["withheld_positives"] > 0
    assert hold["all_arms_filled"], "every arm must fill its budget or the comparison is invalid"
    assert hold["evaluator_version"] == "gems52-pooled-hide-v1"


def test_holdout_numbers_are_labelled_and_the_control_failure_is_disclosed():
    hold = json.loads((ROOT / "evidence/h69_holdout.json").read_text())
    assert hold["evidence_class"] == "HOLDOUT-DTI"
    assert "forecast" in hold["validity_warning"]
    assert hold["prereg_control_clause"]["status"].startswith("FAILED AS WRITTEN")
    assert "instrument_control" in hold and "random_arm" in hold["instrument_control"]


def test_zero_pseudo_labels_is_recorded_not_hidden():
    ind = json.loads((ROOT / "evidence/h69_independence.json").read_text())
    assert ind["total_pseudo_pixels"] == 0
    assert all(not x["ran"] for x in ind["exchange_log"])
    hold = json.loads((ROOT / "evidence/h69_holdout.json").read_text())
    sc = hold["pooled"]["scores"]
    assert sc["disagreement_post"]["dti"] == sc["disagreement_pre"]["dti"]


def test_no_organizer_confirmed_label_anywhere_in_the_round_receipts():
    for name in ("h69_run_card.json", "h69_holdout.json", "h69_s1.json", "h69_lane_dots.json"):
        text = (ROOT / "evidence" / name).read_text()
        assert "ORGANIZER-CONFIRMED\"" not in text.replace("NOT ORGANIZER-CONFIRMED", ""), name
