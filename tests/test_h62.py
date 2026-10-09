"""Tests for the H62 round: frozen protocol, operator audit, gate logic.

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

REG = ROOT / "registry/h62_preregistration.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_protocol_hash_matches_registration():
    reg = json.loads(REG.read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]


def test_protocol_forbids_emission_and_upload():
    reg = json.loads(REG.read_text())
    assert "emission" in reg["stages_not_authorised"]
    assert "upload" in reg["stages_not_authorised"]
    assert reg["runner_refuses_if_hash_moves"] is True


def test_thresholds_are_the_preregistered_values():
    th = json.loads(REG.read_text())["thresholds"]
    assert th["canary_auc_alarm"] == 0.90
    assert th["premise_mean_oof_auc_min"] == 0.60
    assert th["premise_min_fold_auc_min"] == 0.55
    assert th["detrend_sigma_px"] == 15


def test_operator_audit_receipt_is_consistent():
    p = ROOT / "evidence/h62_operator_audit.json"
    if not p.exists():
        pytest.skip("operator audit receipt not produced yet")
    r = json.loads(p.read_text())
    ops = r["operators"]
    h60 = ops["h60_3_along_strike_second_difference"]["on_trace_mean"]
    x3 = ops["cross_strike_symmetric_difference_d3"]["on_trace_mean"]
    # The designed signal is a step across the trace; the H60-3 operator must be far weaker.
    assert h60 < 1e-3 * x3
    assert r["flag"] == "IR-H62-001"


def test_h60_operator_text_still_matches_source():
    import importlib.util
    spec = importlib.util.spec_from_file_location("h62_operator_audit", ROOT / "scripts/h62_operator_audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = mod.check_h60_source()           # raises SystemExit if the H60-3 operator text drifts
    assert src["operator_lines_found"]


def test_normal_is_perpendicular_to_strike():
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h62", ROOT / "scripts/run_h62.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for az in (15.0, 315.0):
        n0, n1 = mod.normal_rowcol(az)
        a = np.deg2rad(az)
        s_row, s_col = -np.cos(a), np.sin(a)     # unit strike in (row, col), row south
        assert abs(n0 * s_row + n1 * s_col) < 1e-12
        assert abs(np.hypot(n0, n1) - 1.0) < 1e-12


def test_fill_nearest_removes_zero_fill_boundary_step():
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h62", ROOT / "scripts/run_h62.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    arr = np.full((20, 20), 7.0, np.float32)
    valid = np.zeros((20, 20), bool)
    valid[:, 5:] = True
    arr[~valid] = 0.0                       # the store zero-fills off-footprint pixels
    filled = mod.fill_nearest(arr, valid)
    assert np.all(filled[valid] == 7.0)
    assert np.all(filled[:, :5] == 7.0)     # nearest valid value, not zero


def test_features_have_no_nan_inside_footprint_when_built():
    man_p = ROOT / "work/h62/feat/manifest.json"
    if not man_p.exists():
        pytest.skip("H62 feature cache not built in this checkout")
    man = json.loads(man_p.read_text())
    for name, st in man["stats"].items():
        assert st["nan_in_footprint"] == 0, name
        assert np.isfinite(st["min"]) and np.isfinite(st["max"]), name
