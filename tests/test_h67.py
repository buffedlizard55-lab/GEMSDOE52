"""Regression tests for the H67 round.

Each test names the defect it would have caught. H67 hit six of them in one session, and five were
caught only because a receipt disagreed with a number that looked plausible; those are the assertions
below. Everything here reads receipts and pinned bytes, so the suite stays fast and deterministic.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid                                  # noqa: E402
from gems52.metric import ALPHA, BETA, R_M    # noqa: E402

EV = ROOT / "evidence"
SUB = ROOT / "submission"
DATA = ROOT / "data"


def load(name):
    return json.loads((EV / f"h67_{name}.json").read_text())


def raster():
    tifs = sorted(SUB.glob("gems52-h67-*.tif"))
    assert len(tifs) == 1, f"expected exactly one H67 raster, found {len(tifs)}"
    return tifs[0]


def card():
    return load("run_card")


# --------------------------------------------------------------------- pre-registration
def test_protocol_hash_is_frozen_and_still_matches():
    """Would have caught: editing the pre-registered protocol after registering its hash.

    run_h67.py verifies this at startup and refuses to run; the test makes the refusal permanent.
    """
    reg = json.loads((ROOT / "registry" / "h67_preregistration.json").read_text())
    proto = ROOT / reg["hypothesis_document"]
    assert proto.exists()
    assert hashlib.sha256(proto.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    assert card()["preregistration"]["hash_verified_at_runtime"] is True


# --------------------------------------------------------------------- IR-H67-002
def test_in_domain_nodata_sentinels_exist_and_are_excluded_from_eligible():
    """Would have caught IR-H67-002: rank channels binned against -3.4e38.

    The defect was invisible on disk - the file is format-valid and the channels look finite - and it
    would have published a garbage-but-valid submission. Two independent halves are pinned: the
    sentinels really are inside the organiser's domain, and `eligible` really is smaller than the
    domain because of them.
    """
    # CI restores only sample_submission + labels (scripts/restore_data.py --only): the 419 MB
    # feature raster is not present there, and every assertion below is defined on it.  Skip, not
    # fail, when the full data placement has not been run (shared-tool guard, IR-H65B-001 session).
    if not (DATA / "training_features.tif").exists():
        import pytest
        pytest.skip("training_features.tif not restored in this environment")
    pre = load("preflight")
    assert pre["cells_domain"] > pre["eligible"] > 0
    assert pre["in_domain_nodata_sentinel_cells"] > 0
    assert "footprint_from" in pre["sentinel_policy"]
    with rasterio.open(DATA / "labels.tif") as ds:
        in_domain = ds.read(1) >= 0
    with rasterio.open(DATA / "training_features.tif") as ds:
        b12 = ds.read(12)
    assert int((in_domain & (b12 < grid.SENTINEL_LIMIT)).sum()) > 0
    assert int((~in_domain).sum()) == pre["cells_outside_domain"]


def test_no_channel_is_degenerate_and_the_zero_inflated_ones_are_named():
    """Would have caught IR-H67-004: a blunt 'collapsed channel' guard failing legitimate layers.

    `rank_b10` and `grad_b17` have more than half the footprint tied at the physical minimum. That is
    a property of the data, not a bug, and the guard must say so instead of failing.
    """
    chan = load("channels")
    assert chan["degenerate_channels"] == []
    assert set(chan["zero_inflated_channels"]) <= {"grad_b17", "rank_b10"}
    assert chan["zero_inflated_channels"], "expected at least the two known zero-inflated channels"


# --------------------------------------------------------------------- canary and gates
def test_leakage_canary_is_clean_and_below_the_alarm():
    can = load("canary")
    assert can["alarm_fired"] is False
    assert can["max_single_channel_auc"] < 0.90
    assert can["worst"]["channel"]


def test_s1_sufficiency_failed_and_no_pseudo_labels_were_used():
    """Would have caught: a run that quietly exchanges pseudo-labels after S1 failed.

    S1 is the premise of the whole lane. The bar is frozen in the pre-registration, and the deviation
    (thermal seeds as a third channel; disagreement used for stratification and veto only) is declared,
    not discovered after the fact.
    """
    s1 = load("s1_sufficiency")
    assert s1["S1_pass"] is False
    assert s1["mean_view_A_oof_auc"] < 0.60 or s1["min_view_A_oof_auc"] < 0.55
    assert len(s1["view_A_oof_auc"]) == len(s1["view_B_oof_auc"]) == 4
    reg = json.loads((ROOT / "registry" / "h67_preregistration.json").read_text())
    assert any(str(d).startswith("IR-H67-001") for d in reg["declared_deviations"])


def test_s2_is_recorded_with_its_block_count_and_not_only_its_verdict():
    """Would have caught IR-H67-005: reporting a single independence number without its sample.

    Across five rounds this statistic spans 0.0078-0.7625 on the same data, so the block count and both
    tests have to travel with it or it means nothing.
    """
    s2 = load("s2_independence")
    assert s2["n_blocks_all"] > 100
    assert s2["max_abs_correlation"] <= 1.0
    assert set(s2["tests"]) == {"negative_mean_squared_error", "negative_false_positive_rate"}


# --------------------------------------------------------------------- holdout
def test_holdout_is_labelled_and_the_candidate_is_significantly_below_random():
    """The frozen promotion bar, evaluated by the test rather than by a human reading a table."""
    ho = load("holdout")
    assert ho["evaluator_version"] == "gems52-pooled-hide-v1"
    assert ho["withheld_positives_total"] > 0
    p = ho["pooled"]
    assert p["scores"]["tuc"]["dti"] < p["scores"]["random"]["dti"]
    d = p["paired_differences"]["random"]
    assert d["ci95"][1] < 0, "paired CI must exclude zero for the negative to be a negative"
    d2 = p["paired_differences"]["single_B"]
    assert d2["ci95"][1] < 0


def test_holdout_folds_are_budget_matched_inside_each_fold():
    ho = load("holdout")
    assert len(ho["folds"]) == 4
    for f in ho["folds"]:
        assert f["budget_matched"] > 0
        assert f["budget_matched"] <= f["corridor_pool"]
        assert f["truth_px"] > 0


# --------------------------------------------------------------------- the raster itself
@pytest.mark.skipif(not (DATA / "sample_submission.tif").is_file(), reason="competition template not restored")
def test_raster_on_disk_matches_its_receipt():
    """Would have caught IR-H65-007 ('Predicted values must be in range [0, 1]') before upload."""
    c = card()
    r = raster()
    val = c["validator"]
    assert val["ok"] is True and val["problems"] == []
    assert hashlib.sha256(r.read_bytes()).hexdigest() == c["raster"]["sha256"]
    assert r.stat().st_size == c["raster"]["bytes"]
    with rasterio.open(r) as ds, rasterio.open(DATA / "sample_submission.tif") as ref:
        a = ds.read(1)
        assert ds.count == 1 and ds.dtypes[0] == "float32"
        assert ds.crs == ref.crs and ds.shape == ref.shape
        assert list(ds.transform)[:6] == list(ref.transform)[:6]
        assert list(ds.bounds) == list(ref.bounds)
    assert np.isfinite(a).all()
    assert set(np.unique(a).tolist()) <= {0.0, 1.0}
    assert int((a > 0).sum()) == c["raster"]["emitted_pixels"] == val["n_nonzero"]
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    assert val["nan_inside_footprint"] == 0 and val["infinity_pixels"] == 0
    assert val["mass_outside_footprint"] == 0


@pytest.mark.skipif(not (DATA / "labels.tif").is_file(), reason="competition labels not restored")
def test_emitted_mass_is_entirely_inside_the_eligible_footprint_and_off_catalogue():
    """N-5 forbids NaN outside the footprint; the lane forbids the 200 m catalogue ring."""
    pre, build = load("preflight"), load("build")
    r = raster()
    with rasterio.open(r) as ds:
        a = ds.read(1) > 0
    with rasterio.open(DATA / "labels.tif") as ds:
        cat = ds.read(1) > 0
    assert int((a & cat).sum()) == 0
    assert build["min_dist_to_catalogue_m"] >= 200.0
    assert a.sum() == build["emitted"]
    assert build["emitted"] <= build["corridor_pool"]


def test_build_is_a_bit_identical_fixed_point():
    """Would have caught: a build whose pixels depend on something not in the receipt.

    Two independent runs of the pipeline produced the same decoded pixels; the card records the decoded
    hash and this test re-derives it from the file on disk.
    """
    c = card()
    assert c["raster"]["reproduced_bit_identically_by_a_second_independent_run"] is True
    with rasterio.open(raster()) as ds:
        a = ds.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    assert hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest() == c["raster"]["decoded_pixels_sha256"]


def test_submission_identifiers_are_within_limits_and_not_promoted():
    c = card()
    ids, v = c["submission_identifiers"], c["verdict"]
    assert ids["note_within_140"] and ids["note_chars"] <= 140
    assert ids["name_chars"] <= 140
    assert v["submit_to_competition"] == "NO"
    assert v["download_for_research"] == "YES"
    assert v["approved_for_weekly_slot"] is False and v["promoted"] is False
    assert v["submission_slots_used"] == 0


def test_lane_gate_reports_both_verdicts_side_by_side():
    """35 registry rasters are universal-coverage probes: their literal verdict is DUPLICATE for ANY
    non-empty raster, so publishing only the literal verdict would be a false alarm and publishing
    only the policy verdict would be a silent waiver."""
    c = card()
    reg = c["registry_correlation_and_overlap"]
    for phase in ("surface_phase", "dots_phase"):
        assert reg[phase]["verdict"] in ("PASS", "DUPLICATE/STOP")
        assert reg[phase]["max_spearman"] is None or -1.0 <= reg[phase]["max_spearman"] <= 1.0
    assert reg["prior_corpus"]["universal_coverage_probes"] > 0
    assert reg["prior_corpus"]["n_priors"] > 100


# --------------------------------------------------------------------- board algebra
@pytest.mark.skipif(not (DATA / "reference/h33-2-b2-zeros.tif").exists(), reason="reference not restored")
def test_the_02778_explanation_reproduces_from_the_bytes():
    """Would have caught: quoting knowledge/27 instead of measuring it.

    The whole 'why 0.2778' answer is one set relation plus one distance range, and both are cheap.
    """
    alg = load("board_algebra")
    rel = alg["set_relations"]["d2_8__minus__ref_h33_2_b2"]
    assert alg["set_relations"]["ref_h33_2_b2__minus__d2_8"]["subset"] is True
    assert rel["px"] == 6436
    assert rel["dist_min_m"] == 100.0 and rel["dist_max_m"] == 200.0
    assert alg["files"]["ref_h33_2_b2"]["frac_within_200m"] == 0.0
    assert alg["mass_vs_board"]["spearman"] == -1.0


def test_required_credit_density_is_the_metric_inverted():
    """The projection formula, checked against itself rather than against a quoted table."""
    S, G = 37_654, 14_088.7
    rho = 0.1387
    dti = rho * S / (ALPHA * S + BETA * G)
    assert abs(dti - 0.2778) < 5e-4
    req = 0.3195 * (ALPHA + BETA * G / S)
    assert abs(req - 0.1595) < 5e-4
    alg = load("board_algebra")
    assert abs(alg["required_rho"]["target_0.3195_G_14088.7"]["37654"] - req) < 1e-3
    assert R_M == 300.0


def test_marginal_rule_rejects_every_step_past_the_champion():
    alg = load("board_algebra")
    steps = [r for r in alg["marginal_acceptance"] if r["G"] == 14_088.7]
    assert len(steps) == 4
    assert all(not r["should_add"] for r in steps)


# --------------------------------------------------------------------- reasoning record
def test_every_emitted_pixel_carries_a_written_interpretation_and_a_falsifier():
    """The brief requires geological reasoning for every A-only candidate; Phase-2 reviewers verify faults."""
    reas = load("reasoning")
    assert reas["rows"] == card()["raster"]["emitted_pixels"]
    assert reas["a_only_rows"] >= 0
    import csv
    path = SUB / "gems52-h67-a-only-and-segment-reasoning.csv"
    assert path.exists()
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == reas["rows"]
    assert all(r["interpretation"].strip() and r["falsifier"].strip() for r in rows)
    a_only = [r for r in rows if r["stratum"] == "A_only"]
    assert len(a_only) == reas["strata"].get("A_only", 0)
    assert all(float(r["dist_to_catalogue_m"]) >= 200.0 for r in rows)
