"""Fast checks for the H88 round: protocol pin, verdict logic from the receipt, file validator, pages, register.

These read receipts and small files only. The raster checks read one 12 MB GeoTIFF with rasterio.
Run:  /home/user/gems-venv/bin/python -m pytest -q tests/test_h88.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DOCS = ROOT / "docs"


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- protocol pin ----------

def test_protocol_pin_matches_frozen_document():
    pin = _json(ROOT / "registry" / "h93_preregistration.json")
    assert pin["round"] == "H88"
    assert _sha(ROOT / pin["document"]) == pin["sha256"], "knowledge/80 was edited after the pin"
    assert pin["primary_arm"] == "P_strict_cotrain"
    assert pin["decision_bar_holdout_dti"] == pytest.approx(0.192829)
    assert pin["experiments_budget"] == 3 and pin["slots_budget"] == 0


def test_holdout_receipt_carries_the_pinned_protocol_hash():
    pin = _json(ROOT / "registry" / "h93_preregistration.json")
    holdout = _json(EV / "h93_holdout.json")
    assert holdout["protocol_sha256"] == pin["sha256"]
    assert holdout["evaluator_version"] == "gems52-pooled-hide-v1"


# ---------- verdict logic, recomputed from the receipt (not trusted from the label) ----------

def test_verdict_is_negative_from_receipt_numbers():
    holdout = _json(EV / "h93_holdout.json")
    s = holdout["scores"]
    bar = 0.192829
    beats_bar = s["P_strict_cotrain"]["dti"] >= bar
    paired_random_lower = holdout["paired_differences"]["random"]["ci95"][0]
    # The verdict is NEGATIVE unless P clears the bar AND beats random with a CI above zero.
    expected = "POSITIVE" if (beats_bar and paired_random_lower > 0) else "NEGATIVE"
    assert expected == "NEGATIVE"
    assert holdout["decision"]["verdict"] == "NEGATIVE"
    assert s["P_strict_cotrain"]["dti"] < s["random"]["dti"], "candidate should be below random on this instrument"


def test_run_card_decisions_are_consistent():
    card = _json(EV / "h93_run_card.json")
    assert card["verdict"] == "NEGATIVE"
    assert card["submit_decision"].startswith("NO")
    assert card["slots_used"] == 0
    assert card["experiments_used"] == 1
    assert card["holdout_dti"]["evidence_class"] == "HOLDOUT-DTI"
    assert card["holdout_dti"]["withheld_positive_px"] == 60894
    assert card["organiser_receipts"] == 0


def test_run_card_lane_gate_is_recorded_as_duplicate_stop():
    card = _json(EV / "h93_run_card.json")
    c = card["correlation_overlap_vs_registry"]
    assert c["surface_verdict"].startswith("PASS")
    assert c["dots_policy_verdict"] == "DUPLICATE/STOP"
    assert c["dots_policy_max_near_3px_fraction"] > 0.70
    assert c["max_decoded_jaccard"] < 0.5
    assert c["identical_to_any_prior"] == 0


def test_note_within_portal_limit():
    card = _json(EV / "h93_run_card.json")
    note = card["submission"]["note"]
    assert len(note) <= 140
    assert card["submission"]["note_chars"] == len(note)


# ---------- the file ----------

@pytest.fixture(scope="module")
def tif_path() -> Path:
    card = _json(EV / "h93_run_card.json")
    return ROOT / card["raster"]["file"]


def test_file_sha_matches_card_and_zip(tif_path):
    card = _json(EV / "h93_run_card.json")
    assert _sha(tif_path) == card["raster"]["sha256"]
    assert _sha(ROOT / card["raster"]["zip"]) == card["raster"]["zip_sha256"]


def test_raster_is_valid_submission_format(tif_path):
    rasterio = pytest.importorskip("rasterio")
    import numpy as np

    with rasterio.open(tif_path) as src:
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        assert src.crs.to_epsg() == 32611
        assert (src.height, src.width) == (3730, 3292)  # rows x cols, as in evidence/h93_validator.json
        arr = src.read(1)
    assert np.isfinite(arr).all()
    assert float(arr.min()) >= 0.0 and float(arr.max()) <= 1.0
    assert int((arr == 1.0).sum()) == 37654
    assert set(np.unique(arr).tolist()) <= {0.0, 1.0}


def test_validator_receipt_all_pass():
    v = _json(EV / "h93_validator.json")
    assert v["all_pass"] is True
    assert len(v["checks"]) == 12
    assert v["positives"] == 37654


# ---------- pages and register ----------

def test_front_page_states_download_yes_submit_no():
    text = (DOCS / "index.html").read_text()
    assert "OK to download? YES" in text
    assert "OK to submit" in text and "NO" in text
    assert "not slot-approved" in text
    assert "Do not upload" in text


def test_archived_h87_pages_are_marked_do_not_submit():
    for name in ("archive-h87-index.html", "archive-h87-executive-summary.html"):
        assert "DO NOT SUBMIT" in (DOCS / name).read_text(), name


def test_irregularity_register_has_h88_entries_with_required_keys():
    entries = _json(ROOT / "registry" / "irregularities.json")["entries"]
    by_id = {e["id"]: e for e in entries}
    required = {"id", "round", "severity", "status", "title", "what_it_is", "how_we_know", "handling"}
    for i in range(1, 9):
        key = f"IR-H93-{i:03d}"
        assert key in by_id, key
        assert required <= set(by_id[key]), key
