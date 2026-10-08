import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems52 import h57, spatial
from scripts.run_h57_real import _component_reasoning_csv


def _write_raster(path: Path, values, *, crs="EPSG:32611", transform=Affine(100, 0, 243350, 0, -100, 4508550), nodata=None, descriptions=None):
    values = np.asarray(values)
    count = 1 if values.ndim == 2 else values.shape[0]
    data = values[None] if values.ndim == 2 else values
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[2], height=data.shape[1],
                       count=count, dtype=data.dtype, crs=crs, transform=transform,
                       nodata=nodata) as dst:
        dst.write(data)
        if descriptions:
            for i, description in enumerate(descriptions, 1):
                dst.set_band_description(i, description)
    return path


def _tiny_data(tmp_path):
    shape = (24, 24)
    template = np.ones(shape, np.float32)
    template[0, 0] = np.nan
    labels = np.zeros(shape, np.int8)
    labels[0, 0] = -1
    labels[4, 4] = 1
    labels[10, 10] = 1
    labels[19, 19] = 1
    features = np.empty((19, *shape), np.float32)
    yy, xx = np.indices(shape)
    for band in range(19):
        features[band] = (band + 1) * 0.1 + yy * 0.01 + xx * 0.02
    features[5, 4, 4] = np.nan  # sample-valid label with no band-6 support
    features[:, 0, 0] = np.nan
    _write_raster(tmp_path / "training_features.tif", features, nodata=np.nan,
                  descriptions=[f"band_{i}" for i in range(1, 20)])
    _write_raster(tmp_path / "labels.tif", labels, nodata=-1)
    _write_raster(tmp_path / "sample_submission.tif", template, nodata=np.nan)
    return tmp_path


def test_h57_corrected_view_assignment_and_no_nan_outside_sample(tmp_path):
    assert 6 not in h57.VIEW_A_BANDS and 6 in h57.VIEW_B_BANDS
    assert 17 in h57.VIEW_A_BANDS and 12 in h57.VIEW_B_BANDS
    data = _tiny_data(tmp_path)
    manifest = h57.build_feature_cache(data / "training_features.tif", data / "labels.tif",
                                       data / "sample_submission.tif", tmp_path / "cache",
                                       preregistration_sha256="test-registration", log=lambda _: None)
    assert manifest["template_footprint_px"] == 24 * 24 - 1
    assert manifest["eligible_feature_footprint_px"] == 24 * 24 - 2
    assert manifest["catalogue_px"] == 2  # unsupported band-6 positive remains export-eligible, not modelled
    store = h57.FeatureStore(tmp_path / "cache")
    assert store.A.shape[0] == 28
    assert store.B.shape[0] == 12
    assert not store.valid[4, 4]
    assert not store.catalogue[4, 4]
    assert store.template_valid[4, 4]
    assert np.isfinite(store.A[:, store.valid].T).all()
    assert np.isfinite(store.B[:, store.valid].T).all()
    assert np.all(store.A[:, ~store.valid] == 0)
    assert np.all(store.B[:, ~store.valid] == 0)
    rows = np.array([10 * 24 + 10, 19 * 24 + 19])
    assert store.gather(rows, "A").shape == (2, 28)
    assert store.gather(rows, "B").shape == (2, 12)
    again = h57.build_feature_cache(data / "training_features.tif", data / "labels.tif",
                                    data / "sample_submission.tif", tmp_path / "cache",
                                    preregistration_sha256="test-registration", log=lambda _: None)
    assert again["builder_sha256"] == manifest["builder_sha256"]


def test_normalized_gaussian_does_not_blend_invalid_cells():
    values = np.zeros((11, 11), np.float32)
    values[5, 5] = 1.0
    values[5, 6] = 1000.0
    valid = np.ones_like(values, bool)
    valid[5, 6] = False
    smooth = h57.normalized_gaussian(values, valid, 1.0)
    assert np.isfinite(smooth[valid]).all()
    assert np.max(smooth[valid]) <= 1.0
    assert smooth[5, 5] < 1.0
    edge = h57.edge_magnitude(values, valid, 1.0)
    assert np.isfinite(edge[valid]).all()
    assert edge[5, 6] == 0


def test_empirical_rank_is_tie_aware_and_uses_the_reference_distribution():
    score = np.array([1, 2, 2, 3, np.nan], np.float32)
    rank, n = h57.empirical_rank(score, np.array([1, 2, 2, 4], np.float32))
    assert n.tolist() == [4]
    assert rank[:4].tolist() == pytest.approx([0.125, 0.5, 0.5, 0.75])
    assert rank[4] == 0


def test_disagreement_field_is_finite_and_has_explicit_a_only_b_only_strata():
    pa = np.array([[0.99, 0.99, 0.50, 0.50]], np.float32)
    pb = np.array([[0.50, 0.99, 0.99, 0.50]], np.float32)
    domain = np.ones_like(pa, bool)
    ref = np.linspace(0, 1, 101, dtype=np.float32)
    fields, report = h57.disagreement_field(pa, pb, ref, ref, domain)
    assert report["strata"].shape == pa.shape
    assert report["stratum_counts"]["A_only"] >= 1
    assert report["stratum_counts"]["B_only"] >= 1
    assert fields["h57_disagreement"].shape == pa.shape
    assert np.isfinite(fields["h57_disagreement"]).all()
    assert (fields["h57_disagreement"] >= 0).all()


def test_whole_pseudo_segments_are_ranked_without_splitting_to_meet_cap():
    donor = np.zeros((60, 60), np.float32)
    receiver = np.full_like(donor, 0.5)
    donor[1, 1:7] = 0.99
    donor[10, 10:16] = 0.95
    donor[20, 20:25] = 0.90
    train = np.ones_like(donor, bool)
    ids, receipts = spatial.whole_pseudo_segments(donor, receiver, train, np.zeros_like(train),
                                                  0.85, 0.4, 0.8, side=50,
                                                  min_pixels=5, cap=11)
    assert len(ids) == 11
    assert [row["pixels"] for row in receipts] == [6, 5]
    assert [row["mean_donor"] for row in receipts] == pytest.approx([0.99, 0.90])
    assert set(ids.tolist()) == set(np.r_[60 + np.arange(1, 7), 20 * 60 + np.arange(20, 25)].tolist())


def test_h57_geotiff_preserves_sample_nans_and_rejects_internal_nans(tmp_path):
    data = _tiny_data(tmp_path)
    with rasterio.open(data / "sample_submission.tif") as template:
        valid = np.isfinite(template.read(1)) & (template.dataset_mask() > 0)
    out = np.zeros(valid.shape, np.float32)
    out[10, 10] = 1
    out[~valid] = np.nan
    path = tmp_path / "prediction.tif"
    receipt = h57.write_submission_tiff(path, out, data / "sample_submission.tif", valid,
                                       status="research only")
    assert receipt["on_disk_readback_exact"]
    with rasterio.open(path) as src:
        assert src.count == 1 and src.dtypes[0] == "float32"
        assert src.crs.to_epsg() == 32611
        assert np.isnan(src.read(1)[0, 0])
        assert src.read(1)[10, 10] == 1
    out[1, 1] = np.nan
    with pytest.raises(ValueError, match="in-footprint"):
        h57.write_submission_tiff(tmp_path / "invalid.tif", out,
                                 data / "sample_submission.tif", valid,
                                 status="bad")


def test_every_a_and_b_only_component_is_reported_even_if_not_emitted(tmp_path):
    data = _tiny_data(tmp_path)
    h57.build_feature_cache(data / "training_features.tif", data / "labels.tif",
                            data / "sample_submission.tif", tmp_path / "cache",
                            preregistration_sha256="test-registration", log=lambda _: None)
    store = h57.FeatureStore(tmp_path / "cache")
    strata = np.zeros(store.shape, np.uint8)
    strata[2, 2:4] = 2
    strata[5, 5] = 2  # disconnected A-only component; no emitted pixels
    strata[8, 8:10] = 3
    p_a = np.full(store.shape, 0.5, np.float32)
    p_b = np.full(store.shape, 0.5, np.float32)
    emitted = np.zeros(store.shape, bool)
    emitted[2, 2] = True
    output_path = tmp_path / "candidate-a-only-reasoning.csv"
    report = _component_reasoning_csv(output_path, store, strata, emitted, p_a, p_b,
                                      data / "training_features.tif")
    assert report["a_only_candidate_components"] == 2
    assert report["a_only_selected_emitted_px"] == 1
    assert report["b_only_candidate_components"] == 1
    with output_path.open(newline="", encoding="utf-8") as stream:
        import csv
        a_rows = list(csv.DictReader(stream))
    with Path(report["b_only_path"]).open(newline="", encoding="utf-8") as stream:
        import csv
        b_rows = list(csv.DictReader(stream))
    assert len(a_rows) == 2
    assert any(row["selected_emitted_pixels"] == "0" for row in a_rows)
    assert len(b_rows) == 1
    assert "possible artifact" in b_rows[0]["geological_interpretation"]
