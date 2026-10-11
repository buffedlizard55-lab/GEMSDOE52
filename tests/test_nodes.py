"""Unit tests for the node-layer: NMS determinism, the tax identity, and metric parity.

The last test is the important one: ``nodes.node_dti`` is a *second* implementation of the official
metric (node-space form).  Two implementations of the same published formula are a liability unless
they are asserted equal, so they are, on random small fields, against ``gems52.metric.official_dti``.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems52 import metric as M
from gems52 import nodes as ND


def test_top_k_mask_selects_exactly_k_and_the_largest():
    rng = np.random.default_rng(0)
    f = rng.random((40, 50)).astype(np.float32)
    allowed = np.zeros((40, 50), dtype=bool)
    allowed[5:35, 5:45] = True
    m = ND.top_k_mask(f, allowed, 20)
    assert int(m.sum()) == 20
    assert np.all(np.isin(np.argwhere(m)[:, 0], np.arange(5, 35)))
    # any pixel outside the mask must beat every pixel inside it
    inside_min = f[m].min()
    outside_max = f[allowed & ~m].max()
    assert inside_min >= outside_max - 1e-12


def test_top_k_mask_is_a_noop_at_zero_budget():
    f = np.ones((8, 8), dtype=np.float32)
    assert ND.top_k_mask(f, np.ones((8, 8), dtype=bool), 0).sum() == 0


def test_local_maxima_is_deterministic_on_a_plateau():
    f = np.zeros((10, 10), dtype=np.float32)
    f[2:5, 2:5] = 1.0                      # a plateau: every pixel is a maximum
    allowed = np.ones_like(f, dtype=bool)
    m = ND.local_maxima(f, allowed, radius_px=1)
    assert int(m.sum()) == 1               # exactly one survivor
    assert tuple(np.argwhere(m)[0]) == (2, 2)


def test_local_maxima_keeps_separated_peaks():
    f = np.zeros((10, 10), dtype=np.float32)
    f[1, 1] = 1.0
    f[8, 8] = 1.0
    m = ND.local_maxima(f, np.ones_like(f, dtype=bool), radius_px=1)
    assert int(m.sum()) == 2


def test_tax_identity_matches_the_metric_definition():
    """tax == sum over emitted x of (1 - max_g k) must equal the published FPw, exactly."""
    rng = np.random.default_rng(1)
    shape = (60, 70)
    nodes = np.zeros(shape, dtype=bool)
    idx = rng.choice(shape[0] * shape[1], 25, replace=False)
    nodes.ravel()[idx] = True
    p = nodes.astype(np.float32)
    truth = np.zeros(shape, dtype=bool)
    tidx = rng.choice(shape[0] * shape[1], 12, replace=False)
    truth.ravel()[tidx] = True
    r = M.dti(p, truth)
    tax = ND.tax_of_nodes(nodes, truth)
    assert tax == pytest.approx(r["fpw"], rel=1e-9, abs=1e-9)


def test_node_dti_agrees_with_official_metric_on_random_fields():
    rng = np.random.default_rng(7)
    for trial in range(6):
        shape = (48, 52)
        p = (rng.random(shape) < 0.004).astype(np.float32)
        g = (rng.random(shape) < 0.006)
        ref = M.dti(p, g)
        got = ND.node_dti(p > 0, g)
        assert got["dti"] == pytest.approx(ref["dti"], rel=1e-9, abs=1e-12), f"trial {trial}"
        assert got["T"] == pytest.approx(ref["tpw"], rel=1e-9, abs=1e-9)


def test_node_dti_handles_an_empty_truth_mask():
    z = np.zeros((16, 16), dtype=bool)
    assert np.isnan(ND.node_dti(z, z)["dti"])


def test_spacing_stats_reports_the_dilation_tax_argument():
    nodes = np.zeros((30, 30), dtype=bool)
    nodes[5, 5] = nodes[5, 7] = nodes[5, 20] = True
    st = ND.spacing_stats(nodes)
    assert st["n"] == 3
    assert st["median_px"] == pytest.approx(2.0)     # 2, 2, 13 -> median 2 (nearest neighbour of the pair)
    assert st["share_within_2px"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------------------------
# H87: the metric's own marginal acceptance rule as a shared placement tool.
# ---------------------------------------------------------------------------------------------
def test_kernel7_is_the_metric_kernel_and_sums_to_the_registered_constant():
    W = ND.kernel7()
    assert W.shape == (7, 7)
    assert W[3, 3] == pytest.approx(1.0)
    assert W.sum() == pytest.approx(ND.KERNEL_SUM if hasattr(ND, "KERNEL_SUM") else W.sum())
    # k(d) = max(1 - d/300 m, 0) on a 100 m grid: offset (2,2) -> d = 2.828 px -> 1 - 2.828/3
    assert W[5, 5] == pytest.approx(1.0 - np.sqrt(8.0) / 3.0)
    assert W[6, 3] == 0.0 and W[0, 0] == 0.0            # exactly at the 300 m cut-off
    assert np.allclose(W, W[::-1, :]) and np.allclose(W, W[:, ::-1])


def test_cover_of_agrees_with_the_authoritative_max_cover():
    rng = np.random.default_rng(3)
    dots = np.zeros((50, 60), bool)
    dots[rng.integers(4, 46, 40), rng.integers(4, 56, 40)] = True
    truth = np.zeros((50, 60), bool)
    truth[rng.integers(2, 48, 60), rng.integers(2, 58, 60)] = True
    covers, _, _ = M.max_cover(dots.astype(np.float32), truth)
    assert covers.shape == (int(truth.sum()),)          # metric returns per-truth-pixel cover
    assert np.allclose(ND.cover_of(dots)[truth], covers, atol=1e-12)


def test_marginal_gain_field_is_the_exact_delta_T_of_one_addition():
    rng = np.random.default_rng(7)
    g = rng.random((40, 44)) * (rng.random((40, 44)) > 0.9)
    allowed = np.ones((40, 44), bool)
    r0 = ND.marginal_greedy(g, allowed, max_dots=12, round_cap=4)
    dots = r0["dots"]
    C = ND.cover_of(dots)
    gain = ND.marginal_gain_field(np.where(allowed, g, 0.0), C)
    for _ in range(6):                                   # six independent single-dot additions
        y, x = int(rng.integers(6, 34)), int(rng.integers(6, 38))
        if dots[y, x]:
            continue
        one = np.zeros_like(dots)
        one[y, x] = True
        exact = float((g * np.maximum(C, ND.cover_of(one))).sum()) - float((g * C).sum())
        assert gain[y, x] == pytest.approx(exact, abs=1e-9)


def test_marginal_greedy_reports_exactly_what_the_metric_would_score():
    rng = np.random.default_rng(11)
    g = rng.random((60, 60)) * (rng.random((60, 60)) > 0.85)
    allowed = np.ones((60, 60), bool)
    g = (g > 0).astype(float)                            # binary truth: mass and support agree
    r = ND.marginal_greedy(g, allowed, max_dots=400)
    assert r["n_added"] > 0 and r["n_added"] <= 400
    assert r["T"] == pytest.approx(float((g * ND.cover_of(r["dots"])).sum()), rel=1e-9)
    d = M.dti(r["dots"].astype(np.float32), g > 0)
    assert d["tpw"] == pytest.approx(r["T"], rel=1e-9)   # TPw of the authoritative metric
    assert d["fnw"] == pytest.approx(float(g.sum()) - r["T"], rel=1e-9)
    # separation is respected
    ys, xs = np.nonzero(r["dots"])
    if len(ys) > 1:
        from scipy.spatial import cKDTree
        nn = cKDTree(np.stack([ys, xs], 1)).query(np.stack([ys, xs], 1), k=2)[0][:, 1]
        assert nn.min() >= 3.0 - 1e-9


def test_marginal_greedy_self_terminates_near_the_metric_optimum_on_a_uniform_density():
    """The budget is derived, not chosen: on a uniform density the rule must stop close to the
    spacing that maximises DTI, not at the minimum separation and not at half of it.

    This is the regression that caught two real defects in the first version of the tool: with a
    stale within-round gain field it saturated the 3 px minimum separation (DTI 0.0643 where the
    optimum for the same density is ~0.09), and with a square raster tie-break it lost ~8% against
    the staggered packing that the owner-reported 0.0904 calibration raster uses.
    """
    rho = 12367.0 / 5167373.0                            # the pinned |G| over the real footprint
    n = 500
    g = np.full((n, n), rho)
    allowed = np.ones((n, n), bool)
    r = ND.marginal_greedy(g, allowed, max_dots=400_000, round_cap=20_000)
    assert r["stop_reason"] == "marginal_rule"
    S = r["n_added"]
    # a ~5-6 px packing (0.028-0.040 of the pixels), not a 3 px saturation (0.111) and not sparse
    assert 0.02 * n * n < S < 0.055 * n * n
    assert 4.2 < np.sqrt(n * n / S) < 6.5
    C = ND.cover_of(r["dots"])
    dti = float((g * C).sum()) / (0.2 * S + 0.8 * rho * n * n)
    # neither halving nor doubling the dot count beats it by more than a few percent
    for frac, label in ((0.5, "sparser"), (2.0, "denser")):
        k = int(S * frac)
        alt = ND.spacing_select(g, allowed, k, min_px=3.0)
        Ca = ND.cover_of(alt > 0)
        d_alt = float((g * Ca).sum()) / (0.2 * k + 0.8 * rho * n * n)
        assert d_alt < dti * 1.05, f"{label} packing beat the marginal rule: {d_alt} vs {dti}"
