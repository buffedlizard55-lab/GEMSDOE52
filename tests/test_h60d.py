"""Tests for the H60D lane module: disagreement fields, pooled DTI, leakage canary,
lane drift gate and the run card.  All synthetic; no competition data needed."""
from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from gems52 import h60d


# --------------------------------------------------------------------------------------------
# disagreement fields
# --------------------------------------------------------------------------------------------
def test_dis_product_is_large_only_where_A_confident_and_B_abstains():
    pa = np.zeros((4, 4), np.float32)
    pb = np.zeros((4, 4), np.float32)
    pa[0, 0] = 1.0          # A confident
    pb[1, 1] = 1.0          # B confident elsewhere
    d = h60d.dis_product(pa, pb)
    assert d[0, 0] == pytest.approx(1.0)     # A confident, B abstains -> maximum
    assert d[1, 1] == pytest.approx(0.0)     # B confident -> product zero
    assert d.min() >= 0.0 and d.max() <= 1.0


def test_dis_product_is_not_the_union():
    rng = np.random.default_rng(1)
    pa = rng.random((50, 50), dtype=np.float32)
    pb = rng.random((50, 50), dtype=np.float32)
    union = np.maximum(pa, pb)
    d = h60d.dis_product(pa, pb)
    # the product is large where the union is small: negatively related, not equal
    assert not np.allclose(d, union)
    assert float(np.corrcoef(d.ravel(), union.ravel())[0, 1]) < 0.9


def test_dis_contrast_and_b_product():
    pa = np.array([[1.0, 0.0]], np.float32)
    pb = np.array([[0.0, 1.0]], np.float32)
    assert h60d.dis_contrast(pa, pb)[0, 0] == pytest.approx(1.0)
    assert h60d.dis_contrast(pa, pb)[0, 1] == pytest.approx(0.0)
    assert h60d.dis_b_product(pa, pb)[0, 1] == pytest.approx(1.0)
    assert h60d.dis_b_product(pa, pb)[0, 0] == pytest.approx(0.0)


# --------------------------------------------------------------------------------------------
# pooled DTI and CI
# --------------------------------------------------------------------------------------------
def test_pooled_dti_pools_components_not_ratios():
    # two folds; the pooled DTI must equal the DTI of the summed components
    folds = [dict(tpw=10.0, fpw=5.0, fnw=90.0, n_truth=100),
             dict(tpw=20.0, fpw=5.0, fnw=80.0, n_truth=100)]
    pl = h60d.pooled_dti(folds)
    expected = 30.0 / (30.0 + 0.2 * 10.0 + 0.8 * 170.0)
    assert pl["dti"] == pytest.approx(expected)
    assert pl["n_truth"] == 200
    # pooling ratios would give a different (wrong) number
    wrong = float(np.mean([10.0 / (10.0 + 0.2 * 5.0 + 0.8 * 90.0),
                           20.0 / (20.0 + 0.2 * 5.0 + 0.8 * 80.0)]))
    assert pl["dti"] != pytest.approx(wrong)


def test_bootstrap_ci_brackets_the_mean():
    ci = h60d.bootstrap_ci([0.10, 0.20, 0.15, 0.12], n_boot=2000, seed=7)
    assert ci["ci_lo"] <= ci["mean"] <= ci["ci_hi"]
    assert ci["n"] == 4
    empty = h60d.bootstrap_ci([])
    assert empty["ci_lo"] is None


# --------------------------------------------------------------------------------------------
# leakage canary
# --------------------------------------------------------------------------------------------
def _truth_region():
    truth = np.zeros((20, 20), bool)
    truth[5:8, 5:8] = True
    return truth, np.ones((20, 20), bool)


def test_layer_auc_canary_perfect_anti_and_tied():
    truth, region = _truth_region()
    perfect = np.zeros((20, 20), np.float32)
    perfect[truth] = 1.0
    assert h60d.layer_auc_canary(perfect, truth, region) == pytest.approx(1.0)
    anti = np.zeros((20, 20), np.float32)
    anti[~truth] = 1.0
    assert h60d.layer_auc_canary(anti, truth, region) == pytest.approx(0.0)
    tied = np.ones((20, 20), np.float32)
    assert h60d.layer_auc_canary(tied, truth, region) == pytest.approx(0.5)


def test_layer_auc_canary_matches_sklearn_on_random_data():
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(3)
    truth, region = _truth_region()
    score = rng.random((20, 20), dtype=np.float32)
    got = h60d.layer_auc_canary(score, truth, region)
    want = roc_auc_score(truth[region], score[region])
    assert got == pytest.approx(want, abs=1e-9)


def test_canary_report_flags_leakage_and_streams_layers():
    truth, region = _truth_region()
    perfect = np.zeros((20, 20), np.float32)
    perfect[truth] = 1.0
    clean = np.zeros((20, 20), np.float32)
    clean[0, 0] = 1.0

    def layer_iter():
        yield "perfect", perfect
        yield "clean", clean

    rep = h60d.canary_report(layer_iter(), [dict(truth=truth, region=region)])
    assert rep["leakage_detected"] is True
    assert rep["worst_layer"] == "perfect"
    assert rep["worst_auc"] == pytest.approx(1.0)
    assert rep["n_layers"] == 2

    rep2 = h60d.canary_report(iter([("clean", clean)]), [dict(truth=truth, region=region)])
    assert rep2["leakage_detected"] is False


# --------------------------------------------------------------------------------------------
# lane drift gate
# --------------------------------------------------------------------------------------------
def _write_tif(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=from_origin(243350, 4508550, 100, 100)) as d:
        d.write(arr.astype("float32"), 1)


def test_lane_gate_flags_identical_surface_and_dots(tmp_path):
    surface = np.zeros((30, 30), np.float32)
    surface[10, 10] = 1.0
    prior = np.zeros((30, 30), np.float32)
    prior[10, 10] = 1.0
    p = tmp_path / "prior.tif"
    _write_tif(p, prior)
    dots = np.zeros((30, 30), bool)
    dots[10, 10] = True
    rep = h60d.lane_drift_report(surface, dots, [p], np.ones((30, 30), bool))
    assert rep["lane_drift_detected"] is True
    assert rep["surface_max_abs_spearman"] == pytest.approx(1.0)
    assert rep["dots_max_within_3px_frac"] == pytest.approx(1.0)
    assert "DUPLICATE LANE" in rep["verdict"]


def test_lane_gate_passes_a_distant_raster(tmp_path):
    surface = np.zeros((30, 30), np.float32)
    surface[10, 10] = 1.0
    prior = np.zeros((30, 30), np.float32)
    prior[25, 25] = 1.0
    p = tmp_path / "prior.tif"
    _write_tif(p, prior)
    dots = np.zeros((30, 30), bool)
    dots[2, 2] = True
    rep = h60d.lane_drift_report(surface, dots, [p], np.ones((30, 30), bool))
    assert rep["lane_drift_detected"] is False
    assert rep["dots_max_within_3px_frac"] == pytest.approx(0.0)
    assert rep["surface_check_passed"] is True
    assert rep["dots_check_passed"] is True


def test_lane_gate_dot_proximity_threshold(tmp_path):
    # 8 of 10 dots within 3 px of one prior's dots = 0.80 > 0.70 -> drift
    rng = np.random.default_rng(5)
    prior = np.zeros((60, 60), np.float32)
    prior[10:20, 10:20] = 1.0
    p = tmp_path / "prior.tif"
    _write_tif(p, prior)
    dots = np.zeros((60, 60), bool)
    yy, xx = np.nonzero(prior)
    take = rng.choice(yy.size, 8, replace=False)
    dots[yy[take], xx[take]] = True          # 8 dots exactly on prior dots
    dots[40, 40] = True
    dots[45, 45] = True                      # 2 far away
    surface = rng.random((60, 60), dtype=np.float32)
    rep = h60d.lane_drift_report(surface, dots, [p], np.ones((60, 60), bool))
    assert rep["dots_max_within_3px_frac"] == pytest.approx(0.8)
    assert rep["lane_drift_detected"] is True


def test_lane_gate_surface_only_when_no_dots(tmp_path):
    surface = np.zeros((30, 30), np.float32)
    surface[10, 10] = 1.0
    prior = np.zeros((30, 30), np.float32)
    prior[10, 10] = 1.0
    p = tmp_path / "prior.tif"
    _write_tif(p, prior)
    rep = h60d.lane_drift_report(surface, None, [p], np.ones((30, 30), bool))
    assert rep["lane_drift_detected"] is True          # surface check alone can flag drift
    assert rep["dots_check_passed"] is None


# --------------------------------------------------------------------------------------------
# run card
# --------------------------------------------------------------------------------------------
def test_run_card_labels_and_structure():
    card = h60d.run_card(
        hypothesis="h", mechanism="m", mimic_processes=["roads"],
        holdout=dict(pooled_dti=0.001, label="HOLDOUT-DTI ..."),
        registry_overlap=dict(lane_gate_dots={}),
        raster_sha256="abc123", validator=dict(no_nan_inside_footprint=True),
        submission_name="n", submission_note="note" * 10,
        verdict="negative")
    assert card["verdict"] == "negative"
    assert card["submission_note_chars"] == len("note" * 10)
    assert "HOLDOUT-DTI" in card["number_labels"]
    assert set(card["evaluator_version"]) == {"metric.py", "holdout.py", "h57.py", "h60d.py",
                                              "emit.py"}
    # every evaluator pin is a real sha256 of the module on disk
    import hashlib
    from pathlib import Path
    for mod, digest in card["evaluator_version"].items():
        p = Path(__file__).resolve().parents[1] / "src/gems52" / mod
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest


# --------------------------------------------------------------------------------------------
# H60-6: calibration rasters are excluded from the 3-px proximity component only
# --------------------------------------------------------------------------------------------
def test_calibration_basenames_reads_the_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": [
        {"id": "calib_lattice", "path": "inputs/calibration/lattice.tif",
         "dest": "scored/lattice.tif"},
        {"id": "other", "path": "inputs/x.tif", "dest": "scored/discovery.tif"},
    ]}))
    assert h60d.calibration_basenames(manifest) == {"lattice.tif"}
    assert h60d.calibration_basenames(tmp_path / "missing.json") == set()


def test_lane_gate_proximity_excludes_calibration_but_spearman_still_applies(tmp_path):
    # a dense "calibration lattice" prior: every dot of the run is within 3 px of it
    # (raw proximity 1.0 > 0.70), but the run is NOT a duplicate: rank correlation ~ 0
    rng = np.random.default_rng(11)
    prior = np.zeros((60, 60), np.float32)
    prior[::2, ::2] = 1.0                      # dense regular lattice
    cal = tmp_path / "lattice.tif"
    _write_tif(cal, prior)
    dots = np.zeros((60, 60), bool)
    dots[1, 1] = dots[3, 3] = dots[5, 5] = dots[7, 7] = True
    surface = rng.random((60, 60), dtype=np.float32)
    rep = h60d.lane_drift_report(surface, dots, [cal], np.ones((60, 60), bool),
                                calibration={"lattice.tif"})
    assert rep["dots_max_within_3px_frac"] == pytest.approx(1.0)      # raw, reported
    assert rep["dots_max_within_3px_frac_gate"] == pytest.approx(0.0)   # excluded from gate
    assert rep["calibration_rasters_excluded_from_proximity"] == ["lattice.tif"]
    assert rep["lane_drift_detected"] is False                          # proximity only
    assert rep["dots_check_passed"] is True
    # the Spearman components still apply to a calibration raster: an identical surface
    # must flag drift even when the raster is calibration
    rep2 = h60d.lane_drift_report(prior, dots, [cal], np.ones((60, 60), bool),
                                 calibration={"lattice.tif"})
    assert rep2["surface_max_abs_spearman"] == pytest.approx(1.0)
    assert rep2["lane_drift_detected"] is True


def test_lane_gate_proximity_still_flags_a_discovery_prior(tmp_path):
    # the same dense prior NOT classified as calibration must still trip the gate
    prior = np.zeros((60, 60), np.float32)
    prior[::2, ::2] = 1.0
    p = tmp_path / "discovery.tif"
    _write_tif(p, prior)
    dots = np.zeros((60, 60), bool)
    dots[1, 1] = dots[3, 3] = dots[5, 5] = dots[7, 7] = True
    surface = np.random.default_rng(3).random((60, 60), dtype=np.float32)
    rep = h60d.lane_drift_report(surface, dots, [p], np.ones((60, 60), bool),
                                calibration={"lattice.tif"})
    assert rep["dots_max_within_3px_frac_gate"] == pytest.approx(1.0)
    assert rep["lane_drift_detected"] is True
