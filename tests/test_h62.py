"""H62 regressions: the step-normalised View A must mean what the receipts say it means.

Four things are pinned here:

1. The matched step filter really is a step filter: it peaks on a synthetic step edge, is
   direction-insensitive in its magnitude column, and its persistence term rewards along-strike
   continuity while suppressing an isolated blob.
2. The H62 view definition is the preregistered one: step columns + template local-contrast
   channels + external deep TMI, and **no raw band values** (the property H61 measured as
   non-transferring).
3. The preregistration receipt binds to the frozen hypothesis document.
4. If the H62 artefact exists, it is portal-safe (single-band float32, all finite, values exactly
   {0,1}, grid identical to the pinned sample, single-TIFF ZIP), and its run card's verdict is
   consistent (download_ok always True; submit_ok only when the verdict is promote; note <= 140).
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from gems52 import gates, h62, structural

ROOT = Path(__file__).resolve().parents[1]


def test_step_columns_detect_a_synthetic_step_edge():
    """The matched step filter's measured contract, pinned on synthetic fields.

    Pinned properties (all measured, not assumed):
    * the detrend kills a uniform regional plane — a hillslope is not a break;
    * a real cross-strike step lights up the magnitude column far above the plane and noise floors;
    * both the signed and the magnitude columns are exactly invariant to flipping the field's
      sign — the normal's sign is fixed by the field's own gradient, so the columns are consistent
      whichever side of the structure is the downthrown one;
    * persistence at the centre of a long continuous edge recovers essentially the full |step|,
      while an isolated single-pixel break leaves only a small residual persistence;
    * the columns are finite inside the valid mask and exactly zero outside it.
    Honest limit, also pinned: the magnitude column fires on ANY localised contrast, including an
    isolated blob — it is a contrast detector, not a fault detector.
    """
    shape = (120, 160)
    valid = np.ones(shape, bool)
    yy, xx = np.mgrid[0:120, 0:160]
    rng = np.random.default_rng(11)
    base = (0.02 * xx + 0.01 * yy).astype(np.float32)          # regional plane
    field = base.copy()
    field[:, 90:] += 6.0                                       # long vertical step edge
    field += rng.normal(0, 0.05, shape).astype(np.float32)     # sensor noise
    cols = h62.step_columns(field, valid, "grav", offsets=(2,))
    assert set(cols) == {"A_step_grav_signed_2px", "A_step_grav_abs_2px",
                         "A_step_grav_persist_2px"}
    mag = cols["A_step_grav_abs_2px"]
    per = cols["A_step_grav_persist_2px"]
    edge = float(mag[55:65, 88:93].max())
    plane_floor = float(mag[80:110, 120:150].max())
    # the detrend removes the regional plane: the edge response dwarfs the plane background
    plane_only = h62.step_columns(base, valid, "grav", offsets=(2,))
    assert float(np.abs(plane_only["A_step_grav_signed_2px"][10:110, 10:150]).max()) < 1e-3
    assert edge > 50.0 * max(plane_floor, 1e-6)
    # noise alone does not produce the edge response
    noise_only = h62.step_columns(base + rng.normal(0, 0.05, shape).astype(np.float32),
                                  valid, "grav", offsets=(2,))
    assert edge > 5.0 * float(noise_only["A_step_grav_abs_2px"].max())
    # exact invariance of BOTH columns under a field sign flip (measured: max diff 0.0)
    flipped = h62.step_columns(-field, valid, "grav", offsets=(2,))
    np.testing.assert_allclose(flipped["A_step_grav_abs_2px"], mag, rtol=0, atol=1e-6)
    np.testing.assert_allclose(flipped["A_step_grav_signed_2px"],
                               cols["A_step_grav_signed_2px"], rtol=0, atol=1e-6)
    # persistence along a long continuous edge recovers essentially the full |step|...
    s_edge = abs(float(cols["A_step_grav_signed_2px"][60, 90]))
    assert s_edge > 0.1
    assert float(per[60, 90]) > 0.9 * s_edge
    # ...while an isolated single-pixel break leaves only a small residual persistence
    spike = base.copy()
    spike[60, 100] += 6.0
    c_spike = h62.step_columns(spike, valid, "grav", offsets=(2,))
    assert float(c_spike["A_step_grav_persist_2px"][60, 100]) < 0.1 * float(per[60, 90])
    # the magnitude column fires on an isolated blob too: a contrast detector, not a fault detector
    blob = base.copy()
    blob[40:45, 30:35] += 8.0
    c_blob = h62.step_columns(blob, valid, "grav", offsets=(2,))
    assert float(c_blob["A_step_grav_abs_2px"][40:45, 30:35].max()) > 0.1


def test_step_columns_are_finite_and_zero_outside_valid():
    shape = (60, 60)
    valid = np.zeros(shape, bool)
    valid[5:55, 5:55] = True
    rng = np.random.default_rng(7)
    field = rng.normal(size=shape).astype(np.float32)
    cols = h62.step_columns(field, valid, "rtp", offsets=(2, 4))
    for name, a in cols.items():
        assert a.shape == shape and a.dtype == np.float32
        assert np.isfinite(a[valid]).all(), name
        assert (a[~valid] == 0.0).all(), name


def test_view_A_h62_names_match_the_preregistration():
    """38 channels: 18 step + 17 template local-contrast + 3 external deep TMI; no raw bands."""
    manifest = {
        "view_A": ([f"raw_band_{i:02d}" for i in (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18)]
                   + ["A_gravity_grad_1", "A_gravity_grad_3", "A_gravity_grad_8",
                      "A_cover_grad_1", "A_cover_grad_3", "A_cover_grad_8",
                      "A_gravity_cover_signed_1", "A_gravity_cover_signed_3",
                      "A_gravity_cover_signed_8", "A_gravity_persistence_1_3",
                      "A_gravity_persistence_3_8", "A_cover_persistence_1_3",
                      "A_cover_persistence_3_8", "A_gravity_coherence", "A_cover_coherence",
                      "A_RTP_grad_1", "A_RTP_grad_3"]),
        "view_A_external": ["X_mag_TMI_up150_rank", "X_mag_TMI_up150_grad1",
                            "X_mag_TMI_up150_grad3"],
    }
    va = h62.view_A_h62_names(manifest)
    assert len(va) == 38, len(va)
    assert not any(n.startswith("raw_band_") for n in va)
    assert len(h62.step_feature_names()) == 18
    for name in h62.step_feature_names():
        assert name in va
    # a raw band sneaking into the view definition must be refused, not silently kept
    bad = dict(manifest)
    bad["view_A_external"] = ["X_mag_TMI_up150_rank", "raw_band_13"]
    with pytest.raises(ValueError):
        h62.view_A_h62_names(bad)


def test_register_columns_is_idempotent_and_updates_the_manifest(tmp_path):
    """A synthetic mini-store: register, re-register, and check the manifest contract."""
    shape = (40, 40)
    valid = np.zeros(shape, bool)
    valid[4:36, 4:36] = True
    flat_idx = np.flatnonzero(valid.ravel())
    store = tmp_path / "store"
    store.mkdir()
    structural.save_array(store / "valid.npy", valid)
    structural.save_array(store / "flat_idx.npy", flat_idx)
    rng = np.random.default_rng(3)
    base = rng.normal(size=flat_idx.size).astype(np.float32)
    structural.save_array(store / "A_gravity_grad_3.npy", base)
    manifest = dict(
        version="structural-core-v2-band6-B+external-geodawn-v1",
        template=dict(shape=list(shape), crs="EPSG:32611", transform=[100.0, 0.0, 0.0, 0.0, -100.0, 0.0]),
        feature_names=["A_gravity_grad_3"], feature_sha256={"A_gravity_grad_3": structural.digest(store / "A_gravity_grad_3.npy")},
        view_A=["raw_band_13", "A_gravity_grad_3"],
        view_A_external=["X_mag_TMI_up150_rank"],
        view_B_with_external=["raw_band_06", "raw_band_12", "raw_band_19"],
    )
    (store / "manifest.json").write_text(json.dumps(manifest))
    cols = {name: rng.normal(size=shape).astype(np.float32) for name in h62.step_feature_names()[:2]}
    s1 = h62.register_columns(store, cols, log=lambda *a, **k: None)
    assert sorted(s1["added"]) == sorted(cols)
    m1 = json.loads((store / "manifest.json").read_text())
    assert m1["version"].endswith("+h62-step-v1")
    assert m1["view_A_h62"]
    assert not any(n.startswith("raw_band_") for n in m1["view_A_h62"])
    # idempotent: a second run recomputes nothing
    s2 = h62.register_columns(store, cols, log=lambda *a, **k: None)
    assert s2["added"] == [] and sorted(s2["skipped"]) == sorted(cols)
    # a feature that would land in BOTH views must be refused: View B already owns a step name
    on_disk = json.loads((store / "manifest.json").read_text())
    on_disk["view_B_with_external"] = ["raw_band_06", "A_step_grav_abs_2px"]
    (store / "manifest.json").write_text(json.dumps(on_disk))
    with pytest.raises(ValueError, match="cross-view feature overlap"):
        h62.register_columns(store, {"A_step_rtp_abs_2px": rng.normal(size=shape).astype(np.float32)},
                             log=lambda *a, **k: None)


def test_h62_preregistration_binds_to_the_frozen_document():
    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert doc.exists(), "preregistered hypothesis document is missing"
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    assert reg["runner_refuses_if_hash_moves"] is True
    assert reg["frozen_before_any_fit"] is True
    assert reg["thresholds"]["sufficiency_screen_min_mean_oof_auc"] == 0.6


def test_h62_artefact_is_portal_safe_if_present():
    sample = ROOT / "data/sample_submission.tif"
    cands = sorted((ROOT / "submission").glob("gems52-h62-*.tif"))
    if not cands or not sample.exists():
        pytest.skip("H62 artefact or pinned sample not present in this checkout")
    path = cands[-1]
    rep = gates.format_report(path, sample, footprint=None)
    assert rep["ok"], rep["problems"]
    assert rep["nan_pixels"] == 0 and rep["infinity_pixels"] == 0
    assert rep["min"] >= 0.0 and rep["max"] <= 1.0
    assert rep["bands"] == 1 and rep["dtype"] == "float32"
    with rasterio.open(path) as src:
        a = src.read(1)
    assert set(np.unique(a)).issubset({0.0, 1.0})
    zip_path = path.with_suffix(".zip")
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as z:
            assert z.namelist() == [path.name]
            assert z.read(path.name) == path.read_bytes()


def test_h62_run_card_verdict_is_consistent_if_present():
    card_path = ROOT / "evidence/h62_run_card.json"
    if not card_path.exists():
        pytest.skip("H62 run card not built in this checkout")
    card = json.loads(card_path.read_text())
    assert card["verdict"] in ("promote", "negative")
    assert card["download_ok"] is True
    assert card["submit_ok"] == (card["verdict"] == "promote")
    assert card["slots_used"] == 0
    assert 1 <= len(card["submission_name"]) <= 140
    assert 1 <= len(card["note"]) <= 140
    assert card["validator"]["ok"] is True
    assert card["validator"]["nan_pixels"] == 0
    assert card["validator"]["grid_matches_sample"] is True
    assert card["not_the_union"]["cells_differing_from_union_max"] > 0
    # the holdout block must carry the labelling the protocol demands
    hd = card["holdout_dti"]
    assert hd["evidence_class"] == "HOLDOUT-DTI"
    assert hd["evaluator"] == "gems52-pooled-hide-v1"
    assert hd["withheld_positive_pixels"] > 0
    assert len(hd["ci95"]) == 2 and hd["ci95"][0] <= hd["candidate"] <= hd["ci95"][1]
