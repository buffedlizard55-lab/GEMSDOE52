from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_h97_tiltdepth_disagreement as h97  # noqa: E402


def test_h97_preregistration_hash_is_frozen_before_fit():
    reg = h97.check_prereg()
    assert reg["frozen_before_any_fit"] is True
    assert reg["primary_hypothesis"] == "H97-A"
    assert reg["mask"]["expected_withheld_positive_pixels"] == 53_186


def test_strict_surface_channel_filter_excludes_geophysical_bands():
    names = sorted(set(h97.h84.DVA2 + h97.h84.HVA + h97.h84.COH))
    selected = h97.surface_channel_names(names)
    assert len(h97.h84.DVA2) == 50
    assert len(selected) == 32
    assert {h97.channel_band(n) for n in selected} == {"det_elev", "det_elev_slope"}
    assert all(n not in selected for n in names if h97.channel_band(n) in {"iso_grav_anom", "depth_to_base_surf", "iso_grav_anom_hg"})


def test_tilt_depth_proxy_uses_half_plus_minus_45_contour_spacing():
    theta_x = np.linspace(-np.pi / 2, np.pi / 2, 17, dtype=np.float32)
    theta = np.broadcast_to(theta_x, (9, 17)).copy()
    eligible = np.ones(theta.shape, dtype=bool)
    depth, proximity, counts = h97.tilt_depth_from_angle(theta, eligible)
    # +/-45 degree threshold columns are four 100 m cells either side of zero.
    assert depth[4, 8] == pytest.approx(400.0)
    assert depth[4, 15] == 0.0  # outside the registered +/-45 degree contour band
    assert proximity[4, 8] == pytest.approx(1.0)
    assert counts["positive_45_cells"] > 0 and counts["negative_45_cells"] > 0
    assert np.isfinite(depth).all() and np.isfinite(proximity).all()


def test_disagreement_formula_is_bounded_and_only_boosts_a_only():
    r_a = np.array([[0.98, 0.99, 0.99], [0.99, 0.99, 0.99]], dtype=np.float32)
    r_b = np.array([[0.50, 0.90, 0.20], [0.50, 0.50, 0.50]], dtype=np.float32)
    mask = np.array([[True, True, True], [False, True, True]], dtype=bool)
    score, a_only = h97.compose_disagreement(r_a, r_b, mask)
    assert a_only.tolist() == [[True, False, False], [False, True, True]]
    assert score[0, 0] == pytest.approx(0.8 * 0.5 + 0.2 * 0.6)
    assert score[0, 1] == pytest.approx(0.8 * 0.9)
    assert score[0, 2] == pytest.approx(0.8 * 0.2)
    assert score[1, 0] == -1.0
    assert np.all((score[mask] >= 0.0) & (score[mask] <= 1.0))


def test_pseudo_rows_remove_conflicting_sampled_negatives_before_positive_append():
    rows = np.array([1, 2, 3], dtype=np.int64)
    y = np.array([0, 0, 1], dtype=np.int8)
    fit_rows, fit_y = h97.add_pseudo_rows(rows, y, np.array([2, 4], dtype=np.int64))
    assert fit_rows.tolist() == [1, 3, 2, 4]
    assert fit_y.tolist() == [0, 1, 1, 1]


def test_git_blob_sha1_uses_the_git_object_header(tmp_path):
    import hashlib

    p = tmp_path / "blob.bin"
    p.write_bytes(b"test")
    assert h97.git_blob_sha1(p) == hashlib.sha1(b"blob 4\x00test").hexdigest()


def test_no_artifact_receipt_normalizes_without_missing_note_chars():
    fields = h97.submission_card_fields({
        "artifact_written": False, "file": None, "validator": {"PASS": False},
        "download_ok": False, "submit_ok": False,
    })
    assert fields == {
        "name": None, "note": None, "note_chars": None,
        "ok_to_download": False, "ok_to_submit": False,
        "submission_slots_used": 0, "promoted": False,
    }


def test_registered_not_union_gate_is_separate_from_single_view_identity():
    candidate_b = np.array([[1, 0, 1, 0]], dtype=bool)
    other_a = np.array([[0, 1, 0, 0]], dtype=bool)
    union = np.array([[0, 1, 0, 1]], dtype=bool)
    metrics = h97.not_union_metrics(
        candidate_b, union, other_a, candidate_b,
        np.array([[0.9, 0.1, 0.8, 0.2]], dtype=np.float32),
        np.array([[0.9, 0.8, 0.8, 0.7]], dtype=np.float32),
        np.ones((1, 4), dtype=bool),
    )
    assert metrics["not_union_pass"] is True
    assert metrics["equal_single_B"] is True
    assert metrics["distinct_from_both_single_view_placements"] is False
    assert "not identical to and not a subset" in metrics["not_union_definition"]
    same_as_union = h97.not_union_metrics(
        candidate_b, candidate_b, other_a, candidate_b,
        np.array([[0.9, 0.1, 0.8, 0.2]], dtype=np.float32),
        np.array([[0.9, 0.8, 0.8, 0.7]], dtype=np.float32),
        np.ones((1, 4), dtype=bool),
    )
    assert same_as_union["not_union_pass"] is False


def test_prior_registry_refuses_incomplete_coverage(tmp_path, monkeypatch):
    import hashlib
    import json

    root = tmp_path
    evidence = root / "evidence"
    (root / "work/h61").mkdir(parents=True)
    evidence.mkdir()
    doc = evidence / "hypothesis.md"
    doc.write_text("frozen")
    inv = evidence / "ctd5_prior_inventory.json"
    inv.write_text(json.dumps({"entries": []}))
    prereg = root / "h97_preregistration.json"
    prereg.write_text(json.dumps({
        "frozen_before_any_fit": True,
        "hypothesis_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
        "hypothesis_bytes": doc.stat().st_size,
        "frozen_prior_inventory": {"path": "evidence/ctd5_prior_inventory.json",
            "sha256": hashlib.sha256(inv.read_bytes()).hexdigest(), "bytes": inv.stat().st_size,
            "blob_entries": 526, "eligible_aligned_rasters": 524, "source_repositories": 50},
    }))
    (root / "work/h61/prior_fetch_receipt.json").write_text(json.dumps({
        "inventory": "evidence/ctd5_prior_inventory.json", "n_entries": 0, "n_errors": 0, "files": {}
    }))
    monkeypatch.setattr(h97, "ROOT", root)
    monkeypatch.setattr(h97, "DOC", doc)
    monkeypatch.setattr(h97, "PREREG", prereg)
    monkeypatch.setattr(h97, "EVID", evidence)
    with pytest.raises(SystemExit, match="incomplete or error-bearing prior inventory"):
        h97.verify_prior_inventory()
