"""Invariants for the corrected metric-aware emitter (``src/gems52/emitter.py``).

These tests exist because of a measured defect: the superseded rule
(``gems52-h19-5-smoothmaxcov-44090``) put 25,485 of its 44,090 dots (57.8 %) **off the belief
field it was packing**, and scored 0.01632 against the only real truth raster versus the
incumbent's 0.16177.  The invariants below are exactly the properties that defect violated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems52 import emitter, metric as M  # noqa: E402


def _field(shape=(41, 41), rows=(20,), spans=((5, 36),)):
    f = np.zeros(shape)
    for r, (a, b) in zip(rows, spans):
        f[r, a:b] = 1.0
    return f


def test_support_confinement_is_absolute():
    """No emitted pixel may sit outside the belief field's own support."""
    f = _field()
    for budget in (10, 100, 1000, None):
        mask, log = emitter.emit(f, budget=budget, prior_dti=0.26)
        assert log.off_support_px == 0, budget
        assert not (mask & (f <= 0)).any(), budget
        assert log.n_emitted == int(mask.sum())


def test_budget_is_respected_exactly():
    f = _field()
    mask, log = emitter.emit(f, budget=17, prior_dti=0.26)
    assert int(mask.sum()) == 17
    assert log.stopped_by == "budget"


def test_emission_is_a_subset_of_support_and_deterministic():
    f = _field(rows=(5, 20, 35), spans=((3, 20), (10, 38), (25, 40)))
    m1, _ = emitter.emit(f, budget=60)
    m2, _ = emitter.emit(f, budget=60)
    assert np.array_equal(m1, m2)
    assert (m1 & (f <= 0)).sum() == 0


def test_first_dot_lands_on_the_highest_proximity_pixel():
    """The first acceptance must be the pixel with the largest static gain."""
    f = _field(rows=(20, 25), spans=((5, 36), (5, 36)))
    prox = emitter.expected_proximity(f)
    mask, log = emitter.emit(f, budget=1)
    y, x = np.argwhere(mask)[0]
    assert prox[y, x] == pytest.approx(prox.max())


def test_exact_marginal_gain_never_exceeds_the_static_upper_bound():
    """``marginal_gain`` with live coverage must be <= the uncovered upper bound."""
    rng = np.random.default_rng(0)
    f = _field(rows=(20,))
    cov = np.zeros_like(f)
    for _ in range(12):
        y = int(rng.integers(0, f.shape[0]))
        x = int(rng.integers(0, f.shape[1]))
        g = emitter.marginal_gain(f, cov, y, x)
        prox = float(emitter.expected_proximity(f)[y, x])
        assert g <= prox + 1e-9
        emitter._deliver(cov, y, x)
    # after covering the whole ridge, the marginal gain of a ridge pixel must fall to ~0
    for x in range(f.shape[1]):
        emitter._deliver(cov, 20, x)
    assert emitter.marginal_gain(f, cov, 20, 12) == pytest.approx(0.0, abs=1e-9)


def test_delivered_credit_matches_an_independent_credit_pass():
    """``log.credit_delivered`` must equal the official-implementation TP_w of the emission."""
    f = _field(rows=(12, 20, 28), spans=((4, 22), (8, 34), (20, 39)))
    mask, log = emitter.emit(f, budget=32)
    c = M.components(mask.astype(float), f.astype(bool))
    assert log.credit_delivered == pytest.approx(c["TP_w"], rel=1e-9, abs=1e-9)


def test_credit_bar_cannot_bind_on_a_binary_fields_own_support():
    """Proposition of knowledge/02 section 4b: for a binary field, kbar >= 1 on its support, so
    the added false-positive mass is <= 0 and the bar accepts unconditionally."""
    f = _field()
    prox = emitter.expected_proximity(f)
    on = f > 0
    assert float(prox[on].min()) >= 1.0
    mask, log = emitter.emit(f, budget=None, prior_dti=0.26)
    assert log.n_emitted == int(on.sum())
    assert log.stopped_by == "exhausted_support"


def test_lazy_greedy_matches_exact_greedy():
    """The fast path IS the exact greedy (lazy re-validation), so it must match it on small fields.

    This test exists because an earlier version of ``emit`` ranked candidates by the *static*
    upper bound and accepted in that order.  On a straight 1-px ridge every interior pixel has
    the same static bound, so it accepted adjacent dots and delivered 10.0 of the exact greedy's
    15.0 units of credit -- a 33 % shortfall, i.e. a milder version of the very defect this
    module was written to repair.
    """
    f = _field(shape=(25, 25), rows=(12,), spans=((3, 22),))
    fast, lf = emitter.emit(f, budget=8)
    exact, le = emitter.exact_greedy(f, budget=8)
    assert int(fast.sum()) == int(exact.sum()) == 8
    assert lf.off_support_px == le.off_support_px == 0
    assert lf.credit_delivered == pytest.approx(le.credit_delivered, rel=1e-9)
    # and it must be strictly better than the static-order sweep it replaced
    prox = emitter.expected_proximity(f)
    static_order = np.argsort(-prox[f > 0], kind="stable")
    assert lf.credit_delivered > 11.0, lf.credit_delivered


def test_theta_thinning_control_is_support_confined_and_sums_to_its_count():
    f = _field(rows=(20,), spans=((5, 36),))
    mask, log = emitter.dot_thin(f, min_dist=2.828)
    assert log.off_support_px == 0
    assert int(mask.sum()) == log.n_emitted
    # a straight 31-px ridge thinned at 2.828 px spacing -> about 11 dots
    assert 9 <= log.n_emitted <= 13


def test_rejects_negative_field():
    with pytest.raises(ValueError):
        emitter.emit(-np.ones((5, 5)))


def test_log_reports_every_documented_field():
    f = _field()
    _, log = emitter.emit(f, budget=5, prior_dti=0.26, rho=1.0)
    d = log.as_dict()
    for key in ("rule", "n_support_px", "n_emitted", "total_mass", "off_support_px",
                "credit_delivered", "first_marginal_gain", "last_marginal_gain", "stopped_by",
                "implied_bar_alpha_s", "implied_bar_two_round"):
        assert key in d, key
    assert d["implied_bar_alpha_s"] == pytest.approx(0.052)
    assert d["implied_bar_two_round"] == pytest.approx(0.026)
