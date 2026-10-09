"""H62 regression tests: pre-registration integrity, the shared learner hook, the frozen verdict rule,
and consistency of the published card with its receipts.  Receipt-dependent tests skip if the
receipts are not on disk (a clean clone without ``work/``/``data/`` still runs the rest)."""
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
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]
    assert reg["frozen_before_any_fit"] is True
    assert reg["runner_refuses_if_hash_moves"] is True


def test_amendments_hash_match_documents():
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    assert reg.get("amendments"), "the control-tolerance amendment must be recorded"
    for am in reg["amendments"]:
        assert _sha(ROOT / am["document"]) == am["sha256"]


def test_h61_default_learner_is_unchanged():
    """The shared hook must return the H61 learner for both views by default (H61 unchanged)."""
    import run_h61 as base
    for view in ("A", "B"):
        assert base.learner_for(view, 7).get_params() == base.learner(7).get_params()


def test_view_a_learner_is_the_single_preregistered_change():
    import run_h62 as r
    pa = r.view_a_learner(5).get_params()
    pb = r.base.learner(5).get_params()
    assert (pa["max_iter"], pa["max_leaf_nodes"], pa["min_samples_leaf"], pa["l2_regularization"]) == (
        120, 7, 400, 5.0)
    assert (pa["learning_rate"]) == 0.05
    # View B keeps the H61 learner exactly
    assert r.learner_for("B", 5).get_params() == pb


def test_verdict_rule_is_conjunctive():
    import run_h62 as r
    ok = dict(fmt_ok=True, lane_ok=True, uniq_ok=True, not_union_ok=True, s1=True, holdout_ok=True)
    assert r.verdict_text(**ok).startswith("ELIGIBLE FOR SELECTOR, NOT PROMOTED")
    for k in ok:
        bad = dict(ok, **{k: False})
        assert r.verdict_text(**bad).startswith("NEGATIVE"), k


def test_control_tolerance_is_declared_and_small():
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    tol = reg["thresholds"]["single_B_control_abs_tolerance"]
    assert 0 < tol <= 0.001
    assert abs(reg["thresholds"]["single_B_h61_control_holdout_dti"] - 0.174517) < 1e-9


def test_sufficiency_gate_thresholds_as_preregistered():
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    th = reg["thresholds"]
    assert th["S1_sufficiency_mean_oof_auc_min"] == 0.60
    assert th["S1_sufficiency_min_fold_oof_auc"] == 0.55
    assert th["S2_independence_abandon_max_abs_rho"] == 0.6


@pytest.mark.skipif(not (ROOT / "evidence/h62_run_card.json").exists(), reason="H62 build not on disk")
def test_card_matches_receipts_and_file():
    card = json.loads((ROOT / "evidence/h62_run_card.json").read_text())
    suf = json.loads((ROOT / "evidence/h62_sufficiency.json").read_text())
    hold = json.loads((ROOT / "evidence/h62_holdout.json").read_text())
    assert card["sufficiency_S1"]["S1_pass"] == suf["S1_pass"]
    assert card["holdout_dti"]["scores"]["single_B"]["dti"] == hold["pooled"]["scores"]["single_B"]["dti"]
    tif = ROOT / "docs/downloads/h62-candidate.tif"
    assert _sha(tif) == card["raster"]["sha256"]
    assert len(card["submission_name"]) <= 140 and len(card["note"]) <= 140
    # the frozen rule: a failed S1 cannot be eligible
    if not suf["S1_pass"]:
        assert card["verdict"].startswith("NEGATIVE")
        assert card["exchange"]["skipped"] is True


@pytest.mark.skipif(not (ROOT / "docs/downloads/h62-candidate.tif").exists(), reason="H62 raster not on disk")
def test_published_raster_is_in_unit_interval_and_binary():
    import rasterio
    with rasterio.open(ROOT / "docs/downloads/h62-candidate.tif") as ds:
        a = ds.read(1)
        assert ds.count == 1 and ds.crs.to_epsg() == 32611
        assert np.isfinite(a).all()
        assert a.min() >= 0.0 and a.max() <= 1.0
        assert set(np.unique(a)).issubset({0.0, 1.0})
        ref_t = None
        if (ROOT / "data/sample_submission.tif").exists():
            with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
                ref_t = (ref.shape, ref.crs, ref.transform)
        if ref_t is not None:
            assert (ds.shape, ds.crs, ds.transform) == ref_t
