"""H62 tests — buried structural corridors (co-training lane).

Gate-contract tests only; they run on synthetic arrays and do not need the pinned data.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def h62():
    return _load("run_h62_mod", "scripts/run_h62.py")


def test_preregistration_frozen(h62):
    import hashlib
    p = ROOT / "registry/h62_preregistration.json"
    assert p.exists()
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha == h62.PREREG_SHA
    d = json.loads(p.read_text())
    assert d["frozen_before_any_fit"] is True
    assert len(d["hypotheses"]) == 5
    assert d["hypotheses"][0]["id"] == "H62-1"
    for h in d["hypotheses"]:
        for k in ("id", "layers", "physical_signature", "why_off_catalogue",
                  "new_vs_repo", "mimic_non_fault", "rank"):
            assert k in h, f"hypothesis {h.get('id')} missing {k}"


def test_line_elements_cover_four_azimuths(h62):
    ses = h62._line_elements()
    assert len(ses) == len(h62.LINE_HALF_WIDTHS) * 4
    for se in ses:
        n = se.shape[0]
        assert se.shape[0] == se.shape[1] and n % 2 == 1
        # each element is a straight line of exactly n cells in an n x n box
        assert se.sum() == n


def test_corridor_mask_gates(h62):
    rng = np.random.default_rng(0)
    shape = (60, 60)
    d = np.zeros(shape, np.float32)
    depth = np.full(shape, 300.0)          # cover OK everywhere
    edge = np.zeros(shape, np.float32)
    permitted = np.ones(shape, bool)
    # a horizontal disagreement ridge with strong edge: 25 px long, crosses the gates
    d[30, 10:35] = 0.5
    edge[30, 10:35] = 2.0                  # above P75 of mostly-zero edge
    mask, info = h62.h62_corridor_mask(d, permitted, depth, edge, log=lambda *a: None)
    assert mask.any(), "persisted corridor should survive the gates"
    assert not mask[5, 5]
    # cover gate: same ridge under shallow cover must die
    depth_s = np.full(shape, 50.0)
    mask2, _ = h62.h62_corridor_mask(d, permitted, depth_s, edge, log=lambda *a: None)
    assert not mask2.any()
    # persistence gate: an isolated blob must die
    d2 = np.zeros(shape, np.float32)
    d2[20:23, 20:23] = 0.5
    mask3, _ = h62.h62_corridor_mask(d2, permitted, depth, edge, log=lambda *a: None)
    assert not mask3.any()


def test_note_and_name_limits_from_build_script():
    src = (ROOT / "scripts/build_h62_submission.py").read_text()
    assert 'assert len(name) <= 200' in src
    assert 'assert len(note) <= 140' in src
    # the registered note literal must satisfy the run-card 140-char rule
    import re
    m = re.search(r'note = \((.*?)\)\n    assert', src, re.S)
    assert m
    parts = re.findall(r'"([^"]*)"', m.group(1))
    note = "".join(parts)
    assert len(note) <= 140, f"note is {len(note)} chars"


def test_raster_contract_is_all_finite_binary():
    # the shipped H62 raster (if built) must be all-finite {0,1} — the portal rejects NaN
    # with "Predicted values must be in range [0, 1]".
    import rasterio
    cands = sorted((ROOT / "submission").glob("gems52-h62-*.tif"))
    if not cands:
        pytest.skip("artifact not built yet")
    with rasterio.open(cands[-1]) as src:
        a = src.read(1)
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        assert str(src.crs) == "EPSG:32611"
        assert a.shape == (3730, 3292)
        assert np.isfinite(a).all()
        assert a.min() >= 0.0 and a.max() <= 1.0
        assert set(np.unique(a)).issubset({0.0, 1.0})
