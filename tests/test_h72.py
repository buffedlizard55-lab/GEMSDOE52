"""H72 preregistration and pure two-view surface tests; no model fit required."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))


def test_h72_preregistration_and_budget_amendment_hashes_are_frozen():
    reg = json.loads((ROOT / "registry/h72_preregistration.json").read_text())
    hypothesis = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(hypothesis.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    amendment = next(a for a in reg["amendments"] if a["document"] == "knowledge/59a_h72_budget_amendment.md")
    p = ROOT / amendment["document"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == amendment["sha256"]
    assert p.stat().st_size == amendment["bytes"]
    assert reg["frozen_before_any_fit"] is True
    assert reg["view_A_features"] == ["raw_band_04", "raw_band_07", "raw_band_08"]
    assert reg["thresholds"]["matched_budget_dots_per_fold_per_arm"] == 1264
    assert reg["thresholds"]["final_output_dots_total"] == 5056
    assert reg["budget"]["max_experiments"] == 3
    assert reg["budget"]["max_wall_clock_hours"] == 2


def test_h72_a_only_surface_is_strict_and_normalized():
    import run_h72

    shape = (100, 100)
    allowed = np.ones(shape, bool)
    # A is ordered by flat index. B is an independent permutation so the A top tail intersects B's middle.
    a = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    b = np.random.default_rng(72).permutation(np.prod(shape)).astype(np.float32).reshape(shape)
    result = run_h72.build_a_only_surface(
        {"A": a, "B": b}, allowed, 0.95, (0.35, 0.65))
    ra, rb = result["rank_A"], result["rank_B"]
    expected = allowed & (ra >= 0.95) & (rb >= 0.35) & (rb <= 0.65)
    assert np.array_equal(result["stratum"], expected)
    assert result["stratum_pixels"] == int(expected.sum())
    assert expected.any()
    surface = result["surface"]
    assert np.isfinite(surface).all()
    assert float(surface.min()) >= 0.0
    assert float(surface.max()) <= 1.0
    assert np.all(surface[~expected] == 0.0)
    assert np.all(surface[expected] > 0.0)


def test_h72_domain_rank_is_nan_outside_domain():
    import run_h72

    values = np.arange(12, dtype=np.float32).reshape(3, 4)
    domain = np.zeros((3, 4), bool)
    domain[1:, 1:3] = True
    ranked = run_h72._rank_on_domain(values, domain)
    assert np.isfinite(ranked[domain]).all()
    assert np.isnan(ranked[~domain]).all()
    assert set(np.round(ranked[domain], 6)) == {0.125, 0.375, 0.625, 0.875}


def test_h72_final_candidate_is_declared_research_only_and_not_slot_approved():
    import run_h72

    reg = json.loads((ROOT / "registry/h72_preregistration.json").read_text())
    state = {"experiments_completed": 0, "monotonic_start": 0.0}
    card = run_h72.make_run_card(reg, state, stop_reason="test stop")
    assert card["eligibility"]["downloadable"] is False
    assert card["eligibility"]["portal_format_valid"] is None
    assert card["eligibility"]["portal_format_status"] == "NOT ASSESSED — no H72 TIFF exists"
    assert card["eligibility"]["organizer_confirmed"] is False
    assert card["eligibility"]["approved_for_competition_submission"] is False
    assert card["submission_slots_used"] == 0
    assert card["selector_decision_made"] is False
    assert card["verdict"] == "negative; no selector/slot decision and no submission made"
