"""H73 placement and preregistration tests (fast, synthetic grids; no competition data needed).

They pin the two properties the lane construction depends on: hard-core spacing (d >= 3 px) and
that a per-prior quota can never be exceeded (amendment 61a). They also pin the preregistration
hashes, so a silent edit to the frozen hypothesis or its amendment fails the suite.
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

run_h73 = pytest.importorskip("run_h73")


def test_place_quota_spacing_and_cap():
    rng = np.random.default_rng(3)
    field = rng.random((60, 70)).astype(np.float32)
    pool = np.ones(field.shape, bool)
    # a "prior" whose 3 px halo covers a 20x20 block; its quota is 10 dots
    support = np.zeros(field.shape, bool)
    support[20:40, 20:40] = True
    from scipy import ndimage as ndi
    halo = ndi.binary_dilation(support, structure=run_h73.gates._disk(3.0))
    quota = [(np.packbits(halo.ravel()), 10)]
    dots, n = run_h73.place_quota(field, pool, 200, quota)
    assert n == int(dots.sum())
    assert run_h73.min_separation_ok(dots)
    assert int((dots & halo).sum()) <= 10           # the cap is hard, never exceeded
    assert int(dots.sum()) == 200                    # plenty of room, so the fill completes


def test_place_quota_reaches_cap_exactly_when_it_binds():
    field = np.zeros((40, 40), np.float32)
    field[10:30, 10:30] = 1.0                        # every top-ranked dot sits inside the quota block
    pool = np.ones(field.shape, bool)
    support = np.zeros(field.shape, bool)
    support[10:30, 10:30] = True
    from scipy import ndimage as ndi
    halo = ndi.binary_dilation(support, structure=run_h73.gates._disk(3.0))
    dots, _ = run_h73.place_quota(field, pool, 30, [(np.packbits(halo.ravel()), 5)])
    assert int((dots & halo).sum()) == 5             # binds exactly at the cap, then the halo is forbidden


def test_place_lane_reports_failure_honestly_when_infeasible():
    field = np.random.default_rng(0).random((30, 30)).astype(np.float32)
    pool = np.ones(field.shape, bool)
    # the only informative prior covers the whole grid: no placement can satisfy 0.70, so ok must be False
    sup = np.argwhere(np.ones(field.shape, bool)).astype(np.int32)
    dots, rec = run_h73.place_lane(field, pool, 40, [sup], field.shape, limit=0.70, rounds=3)
    assert rec["ok"] is False


def test_preregistration_pins_match_frozen_documents():
    reg = json.loads((ROOT / "registry/h73_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    for am in reg.get("amendments", []):
        assert hashlib.sha256((ROOT / am["document"]).read_bytes()).hexdigest() == am["sha256"]
    assert reg["thresholds"]["lane_near_dot_fraction"] == 0.70
    assert reg["thresholds"]["lane_rank_correlation"] == 0.90
    assert reg["thresholds"]["consensus_T_grid"] == [200, 150, 100, 80, 60, 40]


def test_support_rule_matches_gate_convention():
    binary = np.array([[0.0, 1.0], [1.0, 0.0]], np.float32)
    cont = np.array([[0.2, 0.7], [0.5, 0.0]], np.float32)
    sb, is_b = run_h73.support_of(binary)
    sc, is_c = run_h73.support_of(cont)
    assert is_b and not is_c
    assert sb.tolist() == [[False, True], [True, False]]
    assert sc.tolist() == [[False, True], [True, False]]   # >= 0.5 for continuous priors
