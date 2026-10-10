"""H84 harmonic variogram operator: exact recovery, isotropy null, and rotation equivariance."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    pytest.importorskip("rasterio")
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("run_h84", ROOT / "scripts" / "run_h84.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_exact_recovery_on_the_h82_fan():
    m = _load()
    ph = np.radians(np.asarray(m.PHI_DEG))
    a, b, c = 2.0, 0.6, -0.3
    g = a + b * np.cos(2 * ph) + c * np.sin(2 * ph)
    A, B, C, amp = m.harmonic_stats(g)
    assert np.allclose([A, B, C], [a, b, c], atol=1e-12)
    assert np.isclose(amp, np.hypot(b, c) / a)


def test_isotropic_field_has_zero_amplitude_and_operator_is_well_conditioned():
    m = _load()
    A, B, C, amp = m.harmonic_stats(np.full(8, 3.7))
    assert np.isclose(A, 3.7) and abs(B) < 1e-12 and abs(C) < 1e-12 and amp < 1e-12
    _, cond = m.harmonic_operator()
    assert cond < 10.0


def test_quadratic_form_identity_gives_ellipse_eccentricity():
    """gamma = h^T B h for a 2x2 SPD B -> amplitude equals (l1-l2)/(l1+l2)."""
    m = _load()
    rot = np.radians(23.0)
    R = np.array([[np.cos(rot), -np.sin(rot)], [np.sin(rot), np.cos(rot)]])
    Bm = R @ np.diag([3.0, 1.0]) @ R.T
    ph = np.radians(np.asarray(m.PHI_DEG))
    u = np.stack([np.cos(ph), np.sin(ph)], 1)
    g = np.einsum("ni,ij,nj->n", u, Bm, u)
    *_, amp = m.harmonic_stats(g)
    assert np.isclose(amp, (3.0 - 1.0) / (3.0 + 1.0))


def test_vectorised_grid_matches_pointwise():
    m = _load()
    rng = np.random.default_rng(0)
    G = rng.random((8, 5, 6)) + 0.1
    A, B, C, amp = m.harmonic_stats(G)
    for i in range(5):
        for j in range(6):
            a2, b2, c2, amp2 = m.harmonic_stats(G[:, i, j])
            assert np.isclose(A[i, j], a2) and np.isclose(amp[i, j], amp2)
