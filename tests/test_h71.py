"""Tests for the H71 round: frozen protocol, candidate-field construction, gate logic.

These tests need no competition raster. The feature-store checks skip cleanly when work/ is absent.
"""
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

REG = ROOT / "registry/h71_preregistration.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_protocol_hash_matches_registration():
    reg = json.loads(REG.read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]


def test_protocol_is_a_submission_round_with_a_spend_no_slot_verdict():
    reg = json.loads(REG.read_text())
    assert reg["runner_refuses_if_hash_moves"] is True
    assert "spends no weekly slot" in reg["verdict_rule"]
    assert reg["budget"]["max_experiments"] == 3


def test_thresholds_are_the_preregistered_values():
    th = json.loads(REG.read_text())["thresholds"]
    assert th["canary_auc_alarm"] == 0.90
    assert th["independence_abandon_max_abs_rho"] == 0.60
    assert th["donor_rank_min"] == 0.95
    assert th["receiver_rank_interval"] == [0.35, 0.65]
    assert th["buffer_px"] == 80
    assert th["budget_dots_per_fold_per_arm"] == 9400
    assert th["min_dot_separation_px"] == 3.0
    assert th["catalogue_exclusion_m"] == 200.0
    assert th["lane_near_dot_fraction"] == 0.70
    assert th["lane_rank_correlation"] == 0.90
    assert th["quiet_zone_radius_px"] == 3.0
    # the control reproduction bar is the amended H61 tolerance
    assert th["single_B_h61_control_holdout_dti"] == 0.174517
    assert th["single_B_control_abs_tolerance"] == 0.001


def test_runner_refuses_if_preregistration_moves(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h71", ROOT / "scripts/run_h71.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    reg = json.loads(REG.read_text())
    assert mod.check_prereg()["round"] == "H71"
    # a moved document must be refused
    bad = json.loads(REG.read_text())
    bad["hypothesis_sha256"] = "0" * 64
    p = tmp_path / "h71_preregistration.json"
    p.write_text(json.dumps(bad))
    old = mod.REG_PATH
    mod.REG_PATH = p
    try:
        with pytest.raises(SystemExit):
            mod.check_prereg()
    finally:
        mod.REG_PATH = old
    assert reg["hypothesis_sha256"] == _sha(ROOT / reg["hypothesis_document"])


def test_candidate_field_is_finite_only_on_the_a_only_stratum():
    """The H71 emission field: rankA on the strict A-only stratum, -inf elsewhere."""
    rng = np.random.default_rng(0)
    shape = (64, 48)
    rankA = rng.random(shape, dtype=np.float32)
    rankB = rng.random(shape, dtype=np.float32)
    allowed = np.ones(shape, bool)
    lo, hi, dmin = 0.35, 0.65, 0.95
    stratum = (rankA >= dmin) & (rankB >= lo) & (rankB <= hi) & allowed
    field = np.where(stratum, rankA, -np.inf).astype(np.float32)
    finite = np.isfinite(field)
    # finiteness is exactly the stratum
    assert np.array_equal(finite, stratum)
    # every finite value is the view-A rank of that cell
    assert np.allclose(field[stratum], rankA[stratum])
    # placement can only ever take stratum cells
    from gems52 import nodes
    em = nodes.spacing_select(field, allowed, 10_000, min_px=3.0)
    assert np.all(em <= stratum)
    assert 0 < int(em.sum()) <= int(stratum.sum())


def test_quiet_domain_excludes_every_informative_prior_halo():
    """A dot in the quiet domain is >3px from every informative prior's positive pixel, so the
    directed near-dot fraction of the emission against every informative prior is 0 by construction."""
    from scipy import ndimage as ndi
    from gems52 import gates
    shape = (200, 180)
    allowed = np.zeros(shape, bool)
    allowed[10:190, 10:170] = True
    rng = np.random.default_rng(1)
    prior_sup = np.zeros(shape, bool)
    prior_sup[40:60, 40:60] = rng.random((20, 20)) < 0.5
    prior_sup[120:140, 100:130] = rng.random((20, 30)) < 0.5
    assert prior_sup.any()
    # informative prior (coverage far below the probe threshold)
    cov = gates.registry_coverage(prior_sup, allowed, gates.NEAR_RADIUS_PX)
    assert cov < gates.PROBE_COVERAGE
    quiet = allowed & ~ndi.binary_dilation(prior_sup, structure=gates._disk(gates.NEAR_RADIUS_PX))
    # no quiet cell lies within the lane's 3px disk of a prior positive pixel
    halo = ndi.binary_dilation(prior_sup, structure=gates._disk(3.0))
    assert not (quiet & halo).any()
    # and the lane's own directed statistic would read 0 for any emission inside quiet
    yy, xx = np.nonzero(quiet)
    if len(yy):
        proposal = prior_sup
        near = np.zeros(len(yy), bool)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dy * dy + dx * dx > 9:
                    continue
                y, x = yy + dy, xx + dx
                ok = (y >= 0) & (y < shape[0]) & (x >= 0) & (x < shape[1])
                near[ok] |= proposal[y[ok], x[ok]]
        assert not near.any()


def test_grid_rank_covers_exactly_the_allowed_domain():
    """Regression: the control-arm fields must be finite over the whole allowed domain (a reshape
    slip once produced a short array and crashed the holdout)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h71", ROOT / "scripts/run_h71.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shape = (40, 30)
    rng = np.random.default_rng(2)
    # strictly increasing values: no ties, so the tie-aware rank is exactly (i+0.5)/n
    flat_vals = (np.arange(int(np.prod(shape))) * (1.0 + 1e-6)
                 + rng.random(int(np.prod(shape))) * 1e-9).astype(np.float32)
    allowed = np.zeros(shape, bool)
    allowed[5:35, 4:26] = True
    idx = np.flatnonzero(allowed.ravel())
    g = mod._grid_rank(flat_vals, idx, shape)
    assert g.shape == shape
    assert np.isfinite(g[allowed]).all()
    assert np.all(~np.isfinite(g[~allowed]))
    # ranks are a permutation of (0..n-1)/(n) percentiles over the allowed domain
    r = np.sort(g[allowed])
    n = r.size
    assert np.allclose(r, (np.arange(n) + 0.5) / n, atol=1e-5)


def test_holdout_receipt_is_consistent_when_present():
    p = ROOT / "evidence/h71_holdout.json"
    if not p.exists():
        pytest.skip("holdout receipt not produced yet")
    h = json.loads(p.read_text())
    assert h["stage"] == "holdout"
    assert h["candidate_arm"] == "a_only"
    mp = h["matched_pooled"]
    assert mp["evaluator_version"] == "gems52-pooled-hide-v1"
    assert mp["scores"]["a_only"]["withheld_positive_pixels"] == h["withheld_positive_pixels"]
    # every matched arm filled the same per-fold budget
    assert all(f["matched_arms"][a]["filled"]
               for f in h["folds"] for a in ("a_only", "single_A", "single_B", "union_max", "random"))
    assert h["matched_budget_per_fold"] == min(h["a_only_fill_per_fold"].values())
    # the control reproduction bar
    assert h["control_check"]["pass_"] is True


def test_build_receipts_are_consistent_when_present():
    b = ROOT / "evidence/h71_build.json"
    u = ROOT / "evidence/h71_uniqueness.json"
    if not (b.exists() and u.exists()):
        pytest.skip("build receipts not produced yet")
    build, uniq = json.loads(b.read_text()), json.loads(u.read_text())
    assert build["budget"] > 0
    assert build["lane_dots_policy_max_near"] is not None
    mode = build.get("placement_rule") or {}
    if mode.get("cap") is not None:
        # lane-capped mode guarantees the built file satisfies the lane's own <= 0.70 rule
        assert build["lane_dots_policy_max_near"] <= 0.70 + 1e-12
    else:
        # fallback mode: the lane verdict is reported verbatim, whatever it measures
        assert mode.get("rule", "").startswith("fallback")
    assert build["not_union"]["emitted_cells_that_are_strict_a_only"] == build["budget"]
    assert build["validator"]["ok"] is True
    assert uniq["tier1_all_priors"]["canonical_pattern_unique"] is True
    assert (uniq["tier2_informative_priors"]["novel_fraction"] or 0.0) >= 0.2


def test_run_card_verdict_rule_when_present():
    p = ROOT / "evidence/h71_run_card.json"
    if not p.exists():
        pytest.skip("run card not produced yet")
    card = json.loads(p.read_text())
    assert card["round"] == "H71"
    assert card["submission_slots_used"] == 0
    assert card["experiments_used"].startswith("3 of 3")
    assert len(card["note"]) == card["note_chars"] <= 140
    promote = card["verdict_promote"]
    reg = card["correlation_overlap_vs_registry"]
    uniq_ok = bool(reg["uniqueness_tier1"]["canonical_pattern_unique"]
                   and (reg["uniqueness_tier2"]["novel_fraction"] or 0.0) >= 0.2
                   and not reg["uniqueness_tier1"]["equals_literal_prior_union"]
                   and not reg["uniqueness_tier2"]["equals_literal_prior_union"])
    gates_ok = (card["validator"]["ok"] and uniq_ok
                and reg["lane_dots_policy"] == "PASS"
                and reg["lane_surface_policy"] == "PASS"
                and card["not_the_union"]["not_union_pass"]
                and card["holdout_dti"]["paired_candidate_minus_single_B"]["ci95"][0] > 0)
    assert promote == gates_ok
    if not promote:
        assert card["verdict"].startswith("NEGATIVE")
        assert "DOWNLOAD YES" in card["verdict"]


def test_submission_writer_rejects_out_of_range_and_nan(tmp_path):
    """The portal error 'Predicted values must be in range [0, 1]' must be unreachable."""
    from gems52 import submission_writer
    sample = ROOT / "data/sample_submission.tif"
    if not sample.exists():
        pytest.skip("sample_submission.tif not restored")
    import rasterio
    with rasterio.open(sample) as ds:
        footprint = np.isfinite(ds.read(1))
    good = np.zeros(footprint.shape, np.float32)
    r = submission_writer.write_submission(tmp_path / "ok.tif", good, sample, footprint,
                                           note="n", name="n")
    assert r["validator"]["ok"]
    bad = good.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        submission_writer.write_submission(tmp_path / "nan.tif", bad, sample, footprint,
                                           note="n", name="n")
    bad2 = good.copy()
    bad2[0, 0] = 1.5
    with pytest.raises(ValueError):
        submission_writer.write_submission(tmp_path / "range.tif", bad2, sample, footprint,
                                           note="n", name="n")
