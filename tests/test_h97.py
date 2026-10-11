"""H97 / H97b guards: frozen preregistration hashes, the written bytes, and the verdict's honesty.

These tests never assert that a submission is slot-approved (no round may assert that) and never
assert a leaderboard score.  They assert that what the round claims on disk is what the receipts
say, and that the two frozen documents have not moved under the runner.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("reg_name", ["h97_preregistration.json", "h97b_preregistration.json"])
def test_preregistration_hash_is_frozen(reg_name: str) -> None:
    reg = json.loads((ROOT / "registry" / reg_name).read_text())
    doc = ROOT / (reg["hypothesis_document"] if "hypothesis_document" in reg
                  else reg["amendment_document"])
    assert _sha(doc) == (reg.get("hypothesis_sha256") or reg["amendment_sha256"])
    assert reg["hypothesis_bytes"] if "hypothesis_bytes" in reg else True


def test_primary_artifact_is_all_finite_binary_and_matches_the_validator() -> None:
    wr = json.loads((EVID / "h97_write.json").read_text())
    tif = ROOT / wr["tif"]
    assert _sha(tif) == wr["sha256"]
    fm = wr["validator"]
    assert fm["ok"], fm["problems"]
    assert fm["bands"] == 1 and fm["dtype"] == "float32"
    assert fm["crs"] == "EPSG:32611" and (fm["height"], fm["width"]) == (3730, 3292)
    assert fm["nodata"] is None, "the portal range rejection is a nodata/NaN trap; use the all-finite container"
    assert fm["nan_pixels"] == 0 and fm["infinity_pixels"] == 0
    assert 0.0 <= fm["min"] and fm["max"] <= 1.0
    with rasterio.open(tif) as src:
        a = src.read(1)
    vals = np.unique(a)
    assert np.all(np.isin(vals, [0.0, 1.0])), f"values must be exactly {{0,1}}, saw {vals[:5]}"
    assert int((a > 0).sum()) == fm["n_nonzero"]
    assert len(wr["note"]) <= 140 and wr["note_chars"] == len(wr["note"])


def test_lane_gate_is_reported_for_the_primary_and_the_reason_is_recorded() -> None:
    lane = json.loads((EVID / "h97_lane_dots.json").read_text())
    card = json.loads((EVID / "h97_run_card.json").read_text())
    if lane["policy"]["verdict"] != "PASS":
        # a duplicate must be labelled a duplicate; the card may not claim uniqueness
        assert "lane_dots" in card["failed_gates"]
        ir = json.loads((ROOT / "registry" / "irregularities.json").read_text())
        assert any(e["id"] == "IR-H97-003" for e in ir["entries"])
    assert card["submit_ok"] is False, "H97 primary failed a gate; submit approval must not be asserted"


def test_h97b_artifact_is_the_lane_distinct_one_and_is_written_cleanly() -> None:
    wr = json.loads((EVID / "h97b_write.json").read_text())
    tif = ROOT / wr["tif"]
    assert _sha(tif) == wr["sha256"]
    fm = wr["validator"]
    assert fm["ok"] and fm["nodata"] is None and fm["nan_pixels"] == 0
    assert wr["uniqueness"]["identical_to_a_prior"] is False
    assert wr["uniqueness"]["audit_complete"] is True
    card = json.loads((EVID / "h97b_run_card.json").read_text())
    assert card["verdict"] in ("promote", "negative")
    assert card["submit_ok"] == (card["verdict"] == "promote")
    assert card["slots_used"] == 0
    # the download the site links exists and is byte-identical to the receipt
    alias = DOCS / "downloads" / "h97b-candidate.tif"
    assert alias.exists() and _sha(alias) == wr["sha256"]


def test_instrument_finding_is_recorded_with_its_confound_control() -> None:
    inst = json.loads((EVID / "h97_instrument.json").read_text())
    assert inst["spearman_board_vs_holdout"]["n"] == 13
    assert inst["spearman_board_vs_holdout"]["spearman"] < 0.5, "the falsifier was hit; rewrite the claim"
    assert abs(inst["partial_board_vs_holdout_given_log_mass"]["spearman"]) < 0.5
    assert inst["spearman_board_vs_mass"]["spearman"] < -0.5
    board = [r["board_score"] for r in inst["rows"]]
    assert max(board) == 0.2778 and min(board) == 0.0107


def test_irregularity_ids_resolve() -> None:
    ir = json.loads((ROOT / "registry" / "irregularities.json").read_text())
    ids = {e["id"] for e in ir["entries"]}
    for i in range(1, 8):
        assert f"IR-H97-{i:03d}" in ids
