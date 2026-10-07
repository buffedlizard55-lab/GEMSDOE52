from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

from gems52 import cotrain as legacy_cotrain, features as legacy_features, spatial
from gems55 import h57, radlayers, reasoning
from scripts.run_h57 import _score_field

ROOT = Path(__file__).resolve().parents[1]


def test_core_band_dictionary_covers_all_19_bands_including_shear_band_7():
    assert set(legacy_features.BANDS) == set(range(1, 20))
    assert legacy_features.BANDS[7] == "geod_shearrate"
    # The alias is retained only for the historical builder; it is not a corrected View-A input.
    assert legacy_features.BANDS[6] == "mag_tilt_curvature"


def test_h57_uses_corrected_and_disjoint_radiometric_views():
    assert len(radlayers.VIEW_A) == 16
    assert len(radlayers.VIEW_B) == 20
    assert not set(radlayers.VIEW_A) & set(radlayers.VIEW_B)
    assert "A_mag_tilt_abs" not in radlayers.VIEW_A
    assert "R_tc_rank" in radlayers.VIEW_B
    assert {"R_thk_step900", "R_uk_step900", "L_step_max", "L_cover"} <= set(radlayers.VIEW_B)


def test_h57_stack_rank_u8_is_linear_minmax_not_ecdf():
    values = np.array([[10.0, 12.0, 20.0], [30.0, 40.0, 50.0]], np.float32)
    valid = np.ones_like(values, bool)
    actual = legacy_cotrain.rank_u8(values, valid)
    expected = (((values - values.min()) / (values.max() - values.min())) * 255).astype(np.uint8)
    assert np.array_equal(actual, expected)
    assert actual[0, 1] == 12  # linear truncation, not rank/ECDF mapping


def test_h57_registration_and_prefit_lock_are_hash_consistent():
    registration_path = ROOT / "registry/h57_preregistration.json"
    hypothesis_path = ROOT / "knowledge/17_hypotheses_H57_preregistered.md"
    lock_path = ROOT / "evidence/h57_prefit_lock.json"
    registration = json.loads(registration_path.read_text())
    lock = json.loads(lock_path.read_text())
    reg_hash = hashlib.sha256(registration_path.read_bytes()).hexdigest()
    hyp_hash = hashlib.sha256(hypothesis_path.read_bytes()).hexdigest()
    assert registration["hypothesis_sha256"] == hyp_hash
    assert lock["registration_sha256"] == reg_hash
    assert lock["hypothesis_sha256"] == hyp_hash
    assert lock["model_fit_started"] is False
    assert lock["spatial_holdout_scored"] is False
    assert lock["input_pins_match"] is True
    assert registration["fold_protocol"]["buffer_px"] == 80
    assert registration["pseudo_label_exchange"]["minimum_accepted_segments_per_direction_per_fold"] == 1
    assert registration["placement"]["dti_projected"] == 0.0
    assert "400000" in registration["placement"]["pool_rule"]
    assert "A_mag_tilt_abs" not in registration["views"]["view_A"]
    assert "R_tc_rank" in registration["views"]["view_B"]
    assert "TO_BE_FILLED" not in registration_path.read_text()


def test_h57_registered_hist_gradient_boosting_configuration_fits_on_cpu():
    from gems55.h57 import fit_model

    rng = np.random.default_rng(57)
    stack = rng.integers(0, 256, size=(20, 20, 3), dtype=np.uint8)
    rows = np.arange(200, dtype=np.int64)
    y = np.tile(np.array([0, 1], np.int8), 100)
    learner = json.loads((ROOT / "registry/h57_preregistration.json").read_text())["learner"]
    model = fit_model(stack, rows, y, [0, 1, 2], learner, seed=520208,
                      pseudo_positive=np.array([250, 251], np.int64), pseudo_weight=0.25)
    assert model.n_features_in_ == 3
    assert model.predict_proba(stack.reshape(-1, 3)[[0, 1]]).shape == (2, 2)


def test_training_rows_are_deterministic_and_respect_catalogue_collar():
    catalogue = np.zeros((40, 50), bool)
    catalogue[20, 20:27] = True
    valid = np.ones_like(catalogue)
    train = np.ones_like(catalogue)
    rows1, y1, receipt1 = h57.training_rows(catalogue, valid, train, 100, seed=12, collar_px=3)
    rows2, y2, receipt2 = h57.training_rows(catalogue, valid, train, 100, seed=12, collar_px=3)
    assert np.array_equal(rows1, rows2)
    assert np.array_equal(y1, y2)
    assert receipt1 == receipt2
    assert int(y1.sum()) == int(catalogue.sum())
    positive = rows1[y1 == 1]
    negative = rows1[y1 == 0]
    assert set(positive) == set(np.flatnonzero(catalogue.ravel()))
    forbidden = ndi.binary_dilation(catalogue, structure=spatial.disk(3)).ravel()
    assert not forbidden[negative].any()
    assert receipt1["n_negative"] == 100


def test_primary_field_uses_frozen_disagreement_replacements_and_nan_domain():
    pa = np.array([[0.99, 0.50, 0.98, 0.20], [0.50, 0.99, 0.95, 0.30]], np.float32)
    pb = np.array([[0.50, 0.99, 0.98, 0.30], [0.50, 0.50, 0.20, 0.30]], np.float32)
    depth = np.array([[0.25, 0.50, 0.90, 0.10], [0.60, 0.30, 0.30, 0.30]], np.float32)
    domain = np.ones_like(pa, bool)
    domain[1, 3] = False
    thresholds = {
        "A": {"q40": 0.40, "q80": 0.80, "q99": 0.95},
        "B": {"q40": 0.40, "q80": 0.80, "q99": 0.95},
    }
    field, strata, counts = h57.compose_primary_field(pa, pb, thresholds, depth, domain)
    assert strata[0, 0] == 2  # A-only
    assert field[0, 0] == np.float32(0.99 * (0.35 + 0.40 * 0.25))
    assert strata[0, 1] == 3  # B-only
    assert field[0, 1] == np.float32(0.25 * 0.99)
    assert strata[0, 2] == 1  # concordant
    assert field[0, 2] == np.float32(0.98)
    assert np.isnan(field[1, 3])
    assert counts["a_only_pixels"] == 2
    assert counts["b_only_pixels"] == 1
    assert counts["concordant_pixels"] == 1


def test_independence_gate_fails_closed_on_correlated_block_errors():
    rows_by_fold = {}
    for fold in range(4):
        rows = []
        for i in range(24):
            x = float(i)
            rows.append(dict(fold=fold, n_negatives=50, mse_A=x, mse_B=x,
                             fpr_A=x / 100.0, fpr_B=x / 100.0))
        rows_by_fold[fold] = rows
    result = h57.independence_gate(rows_by_fold, threshold=0.6, minimum_blocks=20)
    assert result["status"] == "DISABLE_EXCHANGE"
    assert result["allow_exchange"] is False
    assert len(result["failures"]) == 5  # four outer folds plus pooled


def test_independence_gate_fails_closed_on_missing_blocks():
    rows_by_fold = {fold: [] for fold in range(4)}
    result = h57.independence_gate(rows_by_fold, threshold=0.6, minimum_blocks=20)
    assert result["allow_exchange"] is False
    assert "insufficient" in result["failures"][0]


def test_h57_reasoning_reports_lidar_coverage_and_safe_optional_thermal():
    shape = (9, 9)
    emitted = np.zeros(shape, bool)
    emitted[4, 4] = True
    valid = np.ones(shape, bool)
    catalogue = np.zeros(shape, bool)
    stratum = emitted.copy()
    layers = {
        "L_cover": np.ones(shape, np.float32),
        "L_step_max__rank": np.full(shape, 0.8, np.float32),
        "A_depth_base_rank__rank": np.full(shape, 0.7, np.float32),
        "A_grav_step__rank": np.full(shape, 0.75, np.float32),
        "Th_coherence": None,
    }
    payload = reasoning.build(
        emitted, stratum, layers, valid, np.full(shape, 1200.0, np.float32), catalogue,
        prob_a=np.full(shape, 0.91, np.float32),
        prob_b=np.full(shape, 0.21, np.float32),
    )
    assert payload["n_components"] == 1
    record = payload["candidates"][0]
    assert record["lidar_coverage"]["mean"] == 1.0
    assert record["lidar_scarp_rank"]["p50"] == 0.8
    assert record["view_a_score"]["mean"] == 0.91
    assert record["view_b_score"]["mean"] == 0.21
    assert any("Within the measured LiDAR area" in line and "scarp-step response" in line
               for line in record["interpretation"])
    assert payload["layers_missing"] == ["Th_coherence"]
    assert "nearest_thermal_feature" not in record


def test_h57_reasoning_rejects_probability_grid_shape_mismatch():
    shape = (3, 3)
    mask = np.zeros(shape, bool)
    with np.testing.assert_raises_regex(ValueError, "prob_a must match"):
        reasoning.build(mask, mask, {}, np.ones(shape, bool), np.zeros(shape), mask,
                        prob_a=np.zeros((2, 2), np.float32))


def test_h57_holdout_scores_unmodelled_truth_as_false_negative():
    shape = (30, 30)
    valid = np.ones(shape, bool)
    valid[0, 0] = False
    region = valid.copy()
    held_all = np.zeros(shape, bool)
    held_all[15, 15] = True
    held_all[0, 0] = True  # outside the model footprint: must remain FN, not disappear
    fold = dict(region=region, visible=np.zeros(shape, bool),
                truth=held_all & valid, held_all=held_all)
    result = _score_field(np.ones(shape, np.float32), fold, valid,
                          global_budget=2, pool_cap=100)
    assert result["n_truth"] == 2
    assert result["per_fold_budget"] == 2
