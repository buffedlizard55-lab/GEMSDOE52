"""Regression guards for the H83 pre-fit stop and its public-facing evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_feed_module():
    spec = importlib.util.spec_from_file_location("h83_refresh_feed", ROOT / "scripts" / "refresh_feed.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _json(path: str):
    return json.loads((ROOT / path).read_text())


def test_h83_run_card_is_explicitly_not_run_and_has_no_promotable_file():
    card = _json("evidence/h83_preflight_run_card.json")
    assert card["round"] == "H83-preflight"
    assert card["generated_utc"] == "2026-10-10T20:00:42Z"
    assert card["updated_utc"] >= card["generated_utc"]
    assert card["verdict"] == "negative"
    assert card["experiments_used"] == 0
    assert card["submission_slots_used"] == 0
    assert card["candidate_holdout_dti"]["label"] == "HOLDOUT-DTI"
    assert card["candidate_holdout_dti"]["evaluator"] is None
    assert card["candidate_holdout_dti"]["withheld_positive_count"] is None
    assert card["candidate_holdout_dti"]["dti"] is None
    assert card["candidate_holdout_dti"]["ci95"] is None
    assert card["raster"]["file"] is None and card["raster"]["sha256"] is None
    assert card["validator"]["status"].startswith("NOT RUN")
    assert card["submission_name"] is None and card["submission_note"] is None
    assert card["registry_correlation_overlap"]["surface_rank_correlation"] is None
    assert card["registry_correlation_overlap"]["final_dot_near_3px_share"] is None
    observations = card["source_observations"]
    assert observations["owner_mirror_restore_attempted"] is True
    assert observations["h83_model_inputs_restored"] is False
    assert observations["validation_only_template_restore"]["file"] == "data/sample_submission.tif"
    assert "NOT organizer-authenticated" in observations["validation_only_template_restore"]["provenance"]
    assert observations["validation_only_label_restore"]["file"] == "data/labels.tif"
    assert "not used for an H83 fit or holdout" in observations["validation_only_label_restore"]["purpose"]


def test_h83_board_snapshot_is_team_level_and_not_a_file_receipt():
    snapshot = _json("registry/leaderboard_snapshot_2026-10-10.json")
    assert snapshot["rows_captured"] == 50
    assert len(snapshot["rows"]) == 50
    assert snapshot["observed_date_utc"] == "2026-10-10"
    assert snapshot["observed_at_utc"] is None
    assert snapshot["score_class"].startswith("PUBLIC-BOARD")
    assert snapshot["owner_reported_file_claim"]["file_score_link_confirmed_by_board"] is False
    rows = {row["rank"]: row for row in snapshot["rows"]}
    assert (rows[1]["team"], rows[1]["score"]) == ("xiaofanhu", 0.3774)
    assert (rows[8]["team"], rows[8]["score"]) == ("DARD", 0.3195)
    assert (rows[22]["team"], rows[22]["score"]) == ("extradr19", 0.2778)


def test_site_feed_separates_h83_preflight_from_last_h82_archive():
    feed = _load_feed_module()
    preflight = feed.latest_preflight()
    research = feed.research_status()
    assert preflight["round"] == "H83-preflight"
    assert preflight["candidate_tiff_exists"] is False
    assert preflight["candidate_file"] is None
    assert preflight["submission_slots_used"] == 0
    assert preflight["landing_page"] == "h83-preflight.html"
    assert research["round"] == "H82"
    assert research["approved_for_weekly_slot"] is False
    assert research["submit_ok"] is False
    assert research["hash_verified"] is True
    assert research["download"] == "downloads/h82-candidate.tif"

    published = _json("docs/data/feed.json")
    assert published["latest_preflight"] == preflight
    assert published["latest_research"]["round"] == "H82"
    assert published["latest_research"]["hash_verified"] is True
    assert "not an organizer submission-page receipt" in published["submission_pointer_scope"]
    assert "did not modify the legacy global marker" in published["submission_pointer_note"]
    download_count, download_scope = feed.published_download_count()
    assert published["downloads"] == download_count
    assert published["downloads_scope"] == download_scope
    copied_card = (ROOT / "docs/data/h83_preflight_run_card.json").read_bytes()
    source_card = (ROOT / "evidence/h83_preflight_run_card.json").read_bytes()
    assert copied_card == source_card


def test_h83_page_and_readme_lead_with_current_negative_status():
    page = (ROOT / "docs/h83-preflight.html").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "H83 status: NEGATIVE" in page
    assert "PUBLIC-BOARD" in page
    assert "This is not a geothermal-vent mapping task" in page
    assert "fault-prediction raster is not a geothermal-vent map" in readme
    assert "data/h83_preflight_run_card.json" in page
    assert "no H83 holdout-DTI" in page
    assert "Current direction — H83 preflight" in readme
    assert "H82 completed run archive" in readme
    assert "Maximize P(Win)" in readme and "Own the Outcome" in readme


def test_dated_board_observation_is_not_misreported_as_exact_age():
    js = (ROOT / "docs/site.js").read_text()
    # The site may calculate a 24-hour warning only for a timestamp with a time and zone;
    # an ISO date alone is not silently interpreted as midnight UTC.
    assert "typeof observed==='string'&&/T.*(?:Z|[+-]\\d{2}:\\d{2})$/" in js
    assert _json("docs/data/leaderboard.json")["observed_at_utc"] is None
