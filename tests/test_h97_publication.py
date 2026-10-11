from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_h97_run_card_fail_closed_after_both_promotion_and_lane_stops():
    card = json.loads((ROOT / "evidence/h97_run_card.json").read_text())
    assert card["round"] == "H97"
    assert card["verdict"] == "negative"
    assert card["gates_pass"] is False
    assert card["submission"]["ok_to_download"] is False
    assert card["submission"]["ok_to_submit"] is False
    assert card["submission"]["submission_slots_used"] == 0
    assert card["submission"]["promoted"] is False
    assert card["raster"]["file"] is None
    assert "no TIFF written" in card["status"]
    assert card["registry"]["dots_literal"] == "DUPLICATE/STOP"
    assert card["holdout_gate"]["HOLDOUT_GATE_PASS"] is False
    assert card["three_review_passes_complete"] is True
    assert card["review_record_file"] == "evidence/h97_review_passes.json"
    assert len(card["three_review_passes"]) == 3
    assert all(p["status"] == "complete" for p in card["three_review_passes"])


def test_h97_every_score_is_labeled_with_matched_holdout_metadata():
    hold = json.loads((ROOT / "evidence/h97_holdout.json").read_text())
    assert hold["pooled"]["evaluator_version"] == "gems52-pooled-hide-v1"
    for result in hold["pooled"]["scores"].values():
        assert result["evidence_class"] == "HOLDOUT-DTI"
        assert result["withheld_positive_pixels"] == 53_186
        assert len(result["ci95"]) == 2
    assert hold["H84_control_reproduction"]["PASS"] is True
    assert hold["promotion_gate"]["HOLDOUT_GATE_PASS"] is False


def test_h97_publication_says_no_tiff_and_preserves_h33_attribution_caveat():
    readme = (ROOT / "README.md").read_text()
    current = readme[: readme.index("<!--/H97-CURRENT-->")]
    site = (ROOT / "docs/index.html").read_text()
    page = (ROOT / "docs/h97.html").read_text()
    knowledge = (ROOT / "knowledge/98_h97_results_and_limits.md").read_text()
    for text in (current, site, page, knowledge):
        assert "H33" in text and "0.2747" in text
        assert "attribution" in text.lower() or "attributed" in text.lower()
    assert "OK TO DOWNLOAD: NO" in current
    assert "OK TO SUBMIT: NO" in current
    assert "no h97 competition geotiff was written" in current.lower()
    assert "DUPLICATE/STOP" in page


def test_h97_no_candidate_tiff_or_a_only_reasoning_rows_exist():
    assert not list((ROOT / "submission").glob("*h97*.tif"))
    assert not list((ROOT / "docs/downloads").glob("*h97*.tif"))
    csv_bytes = (ROOT / "docs/downloads/h97-a-only-reasoning.csv").read_bytes()
    assert b"\r" not in csv_bytes
    rows = [line for line in csv_bytes.decode("utf-8").splitlines() if line.strip()]
    assert len(rows) == 1  # header only; the emitted A-only candidate set is empty
