"""H66cover regression tests: pre-registration integrity, the frozen H66-A field rule, the conjunctive
verdict rule, and consistency of the published card with its receipts.  Receipt-dependent tests
skip if the receipts are not on disk (a clean clone without ``work/``/``data/`` still runs the rest)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_preregistration_hash_matches_document():
    reg = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]
    assert reg["frozen_before_any_fit"] is True
    assert reg["runner_refuses_if_hash_moves"] is True


def test_amendments_hash_match_documents():
    reg = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())
    assert reg.get("amendments"), "the budget-cap amendment must be recorded"
    for am in reg["amendments"]:
        assert _sha(ROOT / am["document"]) == am["sha256"]


def test_h61_shared_stages_are_not_forked():
    """H66cover reuses the H61 stages; the runner must not override the learner or the stage functions."""
    import run_h61 as base
    import run_h66cover as r
    assert r.base is base
    assert not hasattr(r, "learner_for"), "H66cover must not override the shared learner hook"
    for view in ("A", "B"):
        assert base.learner_for(view, 7).get_params() == base.learner(7).get_params()


def test_h66a_field_is_gated_and_cover_weighted():
    """The frozen field: (rankA - rankB) * cover_norm inside the A-only gate, -1 elsewhere."""
    import run_h66cover as r
    th = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())["thresholds"]
    shape = (4, 5)
    allowed_idx = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.int64)   # 8 of 20 cells allowed
    rank_a = np.array([0.99, 0.90, 0.50, 0.96, 0.99, 0.40, 0.97, 0.99])
    rank_b = np.array([0.50, 0.50, 0.50, 0.10, 0.80, 0.50, 0.60, 0.34])
    cover = np.array([1.0, 3.0, 1.0, 7.0, 1.0, 1.0, 15.0, 1.0], dtype=np.float32)
    field = r.h66a_field(rank_a, rank_b, cover, allowed_idx, shape, th).ravel()
    # gate: rankA >= 0.95 and 0.35 <= rankB <= 0.65 -> cells 0, 6 (0.99/0.50, 0.97/0.60) only
    gated = np.zeros(20, bool)
    gated[allowed_idx[[0, 6]]] = True
    assert np.array_equal(field > -1.0, gated), "field support must be exactly the A-only gate"
    # cover weight: log1p min-max over the allowed rows; cell 6 (cover 15) must outweigh cell 0
    assert field[6] > field[0] > 0, "thicker cover must raise the field inside the gate"
    # disagreement sign: (rankA - rankB) is positive inside the gate by construction
    assert field[0] > 0 and field[6] > 0


def test_h66a_field_rejects_out_of_gate_emission():
    import run_h66cover as r
    th = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())["thresholds"]
    shape = (2, 2)
    allowed_idx = np.array([0, 1, 2, 3], dtype=np.int64)
    rank_a = np.array([0.99, 0.99, 0.10, 0.99])
    rank_b = np.array([0.50, 0.90, 0.50, 0.50])   # cell 1 is B-confident, not abstaining
    cover = np.ones(4, dtype=np.float32)
    field = r.h66a_field(rank_a, rank_b, cover, allowed_idx, shape, th).ravel()
    assert field[1] == -1.0 and field[2] == -1.0
    assert field[0] > -1.0 and field[3] > -1.0


def test_thresholds_restate_h61_unchanged():
    h61 = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    h66 = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())["thresholds"]
    assert h66 == h61, "H66cover restates no threshold; it reuses the H61 frozen values"


def test_verdict_rule_is_conjunctive():
    reg = json.loads((ROOT / "registry/h66cover_preregistration.json").read_text())
    rule = reg["verdict_rule"]
    for token in ("format", "lane", "unique", "not-union", "single_B", "95% CI"):
        assert token in rule


@pytest.mark.skipif(not (ROOT / "evidence/h66cover_run_card.json").exists(),
                    reason="H66cover receipts not on disk in this clone")
def test_card_matches_receipts_and_file():
    card = json.loads((ROOT / "evidence/h66cover_run_card.json").read_text())
    stem = card["raster"]["file"][:-4]
    sub = json.loads((ROOT / "submission" / f"{stem}.json").read_text())
    assert sub["sha256"] == card["raster"]["sha256"]
    assert sub["submission_name"] == card["submission_name"]
    assert sub["note"] == card["note"]
    assert len(card["note"]) <= 140 and len(card["submission_name"]) <= 140
    hold = json.loads((ROOT / "evidence/h66cover_holdout.json").read_text())
    assert card["holdout_dti"]["candidate"] == hold["pooled"]["scores"]["h66a_cover_gated_a_only"]["dti"]
    assert card["holdout_dti"]["withheld_positive_pixels"] == \
        hold["pooled"]["scores"]["h66a_cover_gated_a_only"]["withheld_positive_pixels"]
    # the verdict must agree with the measured paired difference
    paired = card["holdout_dti"]["paired_h66a_minus_single_B"]
    beats = paired["delta"] > 0 and paired["ci95"][0] > 0
    assert card["promote"] == (beats and card["validator"]["ok"]
                               and card["not_the_union"]["not_union_pass"])


@pytest.mark.skipif(not (ROOT / "evidence/h66cover_run_card.json").exists(),
                    reason="H66cover receipts not on disk in this clone")
def test_published_raster_is_in_unit_interval_and_binary():
    import rasterio
    card = json.loads((ROOT / "evidence/h66cover_run_card.json").read_text())
    stem = card["raster"]["file"][:-4]
    for name in (f"submission/{stem}.tif", "docs/downloads/h66cover-candidate.tif"):
        with rasterio.open(ROOT / name) as ds:
            a = ds.read(1)
            assert ds.count == 1 and ds.dtypes == ("float32",)
            assert ds.crs.to_epsg() == 32611
            assert (ds.height, ds.width) == (3730, 3292)
            assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
            assert np.isfinite(a).all()
            assert set(np.unique(a).tolist()) == {0.0, 1.0}
            assert int(np.count_nonzero(a)) == card["counts"]["placed"]


def test_namespacing_leaves_main_h66_files_untouched():
    """IR-H66-015: this round's files carry the h66cover prefix; the parallel session's H66
    (PR #56) owns the bare h66-* names, so this round must not reference them as its own."""
    runner = (ROOT / "scripts/run_h66cover.py").read_text()
    publisher = (ROOT / "scripts/publish_h66cover_site.py").read_text()
    for src in (runner, publisher):
        assert "registry/h66_preregistration.json" not in src
        assert "evidence/h66_" not in src
        assert '"h66-candidate' not in src and "'h66-candidate" not in src
        assert "docs/h66.html" not in src and "docs/h66-executive-summary.html" not in src
