"""H62 unit and receipt tests.

The pure-function tests need no rasters and run in CI.  The artifact test reads the shipped
GeoTIFF only if it is present on disk (the CI workflow restores the small pinned inputs only), so
it can never fail a clean checkout for lack of data.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import h62  # noqa: E402


# --------------------------------------------------------------------------- the two-view fields
def test_concordance_surface_is_the_minimum_not_the_union():
    pa = np.array([[0.9, 0.1], [0.7, 0.4]], np.float32)
    pb = np.array([[0.2, 0.8], [0.7, 0.4]], np.float32)
    out = h62.concordance_surface(pa, pb)
    assert np.allclose(out, [[0.2, 0.1], [0.7, 0.4]], atol=1e-6)
    assert not np.allclose(out, np.maximum(pa, pb))       # never the union


def test_concordant_cell_requires_both_views_confident():
    pa = np.array([[0.9, 0.9], [0.5, 0.9]], np.float32)
    pb = np.array([[0.9, 0.5], [0.9, 0.9]], np.float32)
    allowed = np.ones((2, 2), bool)
    cell = h62.concordant_cell(pa, pb, allowed, 0.6)
    assert cell.tolist() == [[True, False], [False, True]]
    # and the cell is a subset of the union's confident set, never a superset
    assert (cell & ~(np.maximum(pa, pb) >= 0.6)).sum() == 0


def test_independent_thinning_uses_each_view_alone_and_reports_the_null():
    shape = (40, 40)
    rng = np.random.default_rng(7)
    pa = np.zeros(shape, np.float32)
    pb = np.zeros(shape, np.float32)
    # two identical confident blobs: the thinnings must coincide exactly, so the lift over the
    # independence null is large (n/k), not ~1
    pa[10:30, 10:30] = 0.9
    pb[10:30, 10:30] = 0.9
    allowed = np.ones(shape, bool)

    def select(score, allowed_mask, k):
        # a plain 3 px lattice thinning, no dependence on the other view
        out = np.zeros(shape, bool)
        ys, xs = np.nonzero(np.where(allowed_mask, score, 0.0) >= 0.6)
        taken = 0
        blocked = np.zeros(shape, bool)
        for y, x in zip(ys, xs):
            if blocked[y, x]:
                continue
            out[y, x] = True
            taken += 1
            if taken >= k:
                break
            blocked[max(0, y - 3):y + 4, max(0, x - 3):x + 4] = True
        return out

    th = h62.independent_thinning(pa, pb, allowed, 0.6, 200, select)
    assert th["n_thin_a"] == th["n_thin_b"] > 0
    assert th["n_corroborated"] == th["n_thin_a"]        # identical fields corroborate fully
    assert th["corroboration_lift"] > 1.0
    assert np.array_equal(th["corroborated"], th["thin_a"] & th["thin_b"])


def test_corroboration_null_scales_as_k_squared_over_n():
    """The structural limit filed as IR-H62-002: two independent thinnings intersect in k^2/n."""
    n, k = 4_861_502, 30_000
    assert 180 < k * k / n < 190


# --------------------------------------------------------------------------- cover-conditioned A-only
def test_cover_conditioned_disagreement_uses_a_pool_quantile():
    shape = (10, 10)
    pa = np.full(shape, 0.9, np.float32)
    pb = np.full(shape, 0.1, np.float32)
    depth = np.zeros(shape, np.float32)
    depth[:, :5] = 100.0
    depth[:, 5:] = 900.0
    allowed = np.ones(shape, bool)
    out, thr = h62.cover_conditioned_disagreement(pa, pb, depth, allowed, 0.6, 0.4, 0.70)
    assert thr == pytest.approx(900.0)                     # the 70th percentile of the pool
    assert out[:, :5].sum() == 0                           # thin cover: the cell is not licensed
    assert out[:, 5:].sum() > 0                            # thick cover: buried-fault candidate


# --------------------------------------------------------------------------- instrument 2
def test_revealed_colocation_matches_a_hand_computation():
    grid = np.zeros((20, 20), bool)
    grid[5, 5] = True                       # one core pixel
    dots = np.zeros((20, 20), bool)
    dots[5, 5] = True                       # on it
    dots[6, 6] = True                       # sqrt(2) away, inside r = 3
    dots[15, 15] = True                     # far away
    pool = np.ones((20, 20), bool)
    r = h62.revealed_colocation(dots, grid, pool)
    assert r["n_dots"] == 3
    assert r["colocated"] == 2
    assert r["fraction"] == pytest.approx(2 / 3)
    # scipy's binary_dilation default structure is the 4-connected cross, so three iterations
    # give the 25-cell L1 diamond, not the 29-cell Euclidean disc (IR-H62-004).
    assert r["random_baseline"] == pytest.approx(25 / 400)
    assert r["lift"] > 1.0


def test_implied_credit_density_is_a_bracket_within_the_measured_bounds():
    d = h62.implied_credit_density(0.30)
    assert 0.0279 <= d["rho_lo"] <= d["rho_hi"] <= 0.184


# --------------------------------------------------------------------------- the budget rule
def test_budget_argmax_is_independent_of_field_scale():
    """c cancels: only the decay exponent gamma moves S*."""
    pts = [(8000, 0.40), (12000, 0.36), (17000, 0.33), (25000, 0.29), (38000, 0.22)]
    a = h62.budget_from_gamma(pts, clamp=(0, 10**9))
    b = h62.budget_from_gamma([(s, 10.0 * f) for s, f in pts], clamp=(0, 10**9))
    assert a["budget_px"] == b["budget_px"]
    assert a["ok"] is True


def test_budget_rule_falls_back_when_the_fit_is_impossible():
    assert h62.budget_from_gamma([(8000, 0.4)])["budget_px"] == h62.BUDGET_FALLBACK
    # a non-decaying field has gamma > 1 and the formula does not apply
    bad = h62.budget_from_gamma([(8000, 0.1), (12000, 0.2), (17000, 0.4)])
    assert bad["budget_px"] == h62.BUDGET_FALLBACK


# --------------------------------------------------------------------------- the |G| bracket
def test_g_bracket_is_the_measured_interval_and_the_legacy_point_sits_outside_it():
    """IR-H62-005: |G| is identified only as an interval; 14,088.7 px is a non-binding bound."""
    lo, hi = h62.G_BRACKET_PX
    assert 5_949.0 < lo < 5_950.0      # T <= |G| on calib_8GEMSDOE_Hedge-v2 (166,519 px @ 0.1563)
    assert 12_512.0 < hi < 12_513.0    # monotone credit on d15 (60,069 @ 0.2477) subset gems27
    assert h62.G_ANCHOR_PX > hi        # the legacy point is OUTSIDE the identified interval


def test_budget_argmax_is_linear_in_g():
    pts = [(8000, 0.39375), (12000, 0.36258), (17000, 0.33135), (25000, 0.28568), (38000, 0.22468)]
    lo = h62.budget_from_gamma(pts, g_anchor=h62.G_BRACKET_PX[0])
    hi = h62.budget_from_gamma(pts, g_anchor=h62.G_BRACKET_PX[1])
    lo, hi = h62.G_BRACKET_PX
    b_lo = h62.budget_from_gamma(pts, g_anchor=lo)
    b_hi = h62.budget_from_gamma(pts, g_anchor=hi)
    assert b_lo["ok"] and b_hi["ok"]
    assert b_hi["s_star_unclamped"] / b_lo["s_star_unclamped"] == pytest.approx(hi / lo, rel=1e-9)
    # the whole bracket is reported, not one contested point
    assert [round(r["g_px"], 1) for r in b_hi["g_sensitivity"]] == [5949.3, 12512.1, 14088.7]


# --------------------------------------------------------------------------- reasoning rows
def test_cell_of_partitions_the_confidence_table():
    assert h62.cell_of(0.9, 0.9, 0.6, 0.4) == "concordant"
    assert h62.cell_of(0.9, 0.1, 0.6, 0.4) == "A-only (buried candidate)"
    assert h62.cell_of(0.1, 0.9, 0.6, 0.4) == "B-only (surface-only; artefact-suspect)"
    assert h62.cell_of(0.5, 0.5, 0.6, 0.4) == "neither"


def test_a_only_note_names_the_non_fault_alternative_and_never_claims_a_fault():
    thin = h62.a_only_note(50.0, 600.0)
    thick = h62.a_only_note(900.0, 600.0)
    assert "lithologic contact" in thin and "gravity gradient" in thin
    assert "buried-structure candidate" in thick
    row = h62.reasoning_row(row=1, col=2, easting=3.0, northing=4.0, pa=0.9, pb=0.1,
                            depth_m=900.0, cell="A-only (buried candidate)",
                            corroborated=False, notes=thick)
    assert row["status"].startswith("HYPOTHESIS FOR PHASE-2 REVIEW")
    assert "verified fault" not in row["status"].replace("not a verified fault", "")


# --------------------------------------------------------------------------- receipts and artifact
def _evidence(name: str):
    p = ROOT / "evidence" / name
    return json.loads(p.read_text()) if p.exists() else None


def test_h62_preregistration_is_intact():
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_document_sha256"]
    for key, pinned in reg["evaluator_version"].items():
        if not key.endswith("_py_sha256"):
            continue
        mod = ROOT / "src" / "gems52" / (key[: -len("_py_sha256")] + ".py")
        assert hashlib.sha256(mod.read_bytes()).hexdigest() == pinned


def test_h62_round_facts_are_recorded_and_consistent():
    cot, val = _evidence("h62_cotrain.json"), _evidence("h62_validation.json")
    if cot is None or val is None:
        pytest.skip("H62 receipts not present in this checkout")
    pre = _evidence("h62_preflight_integrity.json")
    if pre is not None:
        assert pre["pinned_all_ok"] is True
        assert pre["pinned_files_verified"] == 23
    assert cot["leakage_canary"]["worst_auc"] <= 0.90
    assert cot["independence"]["max_abs_correlation"] < 0.60
    # the disagreement signal measured below its matched random control on instrument 2
    for row in val["instrument2_revealed"]["per_field"]:
        if row["field"] in ("dis_contrast", "dis_product", "cover_A_only"):
            assert row["f_25000"]["lift"] < 1.0
    # the shipped concordance beats both single views and the union on the registered instrument
    arms = val["instrument1_holdout"]["arms"]
    assert arms["conc_soft|25000"]["pooled_dti"] > arms["clf_union|25000"]["pooled_dti"]
    assert arms["conc_soft|25000"]["pooled_dti"] > arms["view_B|25000"]["pooled_dti"]


def test_h62_shipped_artifact_if_present():
    build = _evidence("h62_build.json")
    if build is None:
        pytest.skip("H62 build receipt not present in this checkout")
    stem = f"gems52-h62-{build['winner']}-arm{build['budget_px']}px"
    tif = ROOT / "submission" / (stem + ".tif")
    if not tif.exists():
        pytest.skip("H62 GeoTIFF not restored in this checkout")
    receipt = json.loads((ROOT / "submission" / (stem + ".json")).read_text())
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == receipt["sha256"]
    assert receipt["validator"]["ok"] is True
    assert receipt["validator"]["n_nan"] == 0
    assert receipt["validator"]["min"] >= 0.0 and receipt["validator"]["max"] <= 1.0
    assert build["ring_rule_ok"] is True
    assert build["not_merely_union"]["outside_union_fraction"] >= 0.30
    assert build["winner"] not in ("view_B", "clf_union")   # the union disqualifier, H62-3
    card = _evidence("h62_run_card.json")
    assert card["raster_sha256"] == receipt["sha256"]
    assert len(card["submission_note"]) <= 140
    assert len(card["submission_name"]) <= 140
    ro = card["correlation_overlap_vs_registry"]
    # the strict gate counts every registry raster (H60-6 withdrawn by the H60D recheck), so it
    # stops on the spacing-5 lattice; the coverage-aware repair is published beside it, never
    # instead of it.
    assert ro["lane_drift_detected"] is True
    assert ro["lane_dots_max_within_3px_frac_gate"] == ro["lane_dots_max_within_3px_frac_raw"]
    assert ro["lane_drift_is_registry_saturation"] is True
    assert ro["repaired_gate"]["policy_verdict"] == "PASS"
    assert ro["repaired_gate"]["n_universal_coverage_probes"] >= 1
    assert ro["pattern_unique"] is True
    assert card["verdict"] == "negative"
    assert "DO NOT SUBMIT" in card["promotion_scope"]
    # the artifact survived the strict gate's stop, so it must not be presented as submittable
    assert receipt["submission_slots_used"] == 0
    assert receipt["promoted"] is False
