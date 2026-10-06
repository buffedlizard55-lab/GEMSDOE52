"""Emission rules: the credit-bar rule and the exactness of the fast greedy cover."""
import numpy as np
import pytest

from gems52 import emission as E, holdout as H, metric as M


def _random_field(rng, shape):
    return np.clip(rng.normal(0.05, 0.2, shape), 0, 1).astype(np.float32)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_greedy_fast_matches_reference_exactly(seed):
    rng = np.random.default_rng(seed)
    shape = (int(rng.integers(40, 90)), int(rng.integers(40, 90)))
    f = _random_field(rng, shape)
    fp = np.ones(shape, bool)
    n = int(rng.integers(20, 200))
    b, _ = E.greedy_cover_fast(f, fp, n, headroom=2)
    a = E.greedy_cover(f, n, fp)
    assert (a == b).all()


def test_greedy_fast_matches_reference_with_stop_bar():
    rng = np.random.default_rng(7)
    f = _random_field(rng, (60, 70))
    fp = np.ones_like(f, bool)
    a = E.greedy_cover(f, 400, fp)
    b, tb = E.greedy_cover_fast(f, fp, 400, stop_bar=0.03)
    assert (a == b).all() and len(tb) <= 400


def test_greedy_cover_never_emits_more_than_budget_and_improves_credit():
    rng = np.random.default_rng(11)
    f = np.zeros((120, 120), np.float32)
    f[60, 20:100] = 0.9
    f += np.clip(rng.normal(0, 0.02, f.shape), 0, None).astype(np.float32)
    fp = np.ones_like(f, bool)
    m, trace = E.greedy_cover_fast(f, fp, 60)
    assert int(m.sum()) == 60
    marg = [t["marginal"] for t in trace]
    assert all(marg[i] >= marg[i + 1] - 1e-6 for i in range(len(marg) - 1)), "gains must be non-increasing"


def test_credit_bar_rule_on_a_fresh_field():
    """A single pixel on an empty prediction: it is the best cover of its nearest truth pixel
    with weight k, so the score rises iff k > 0 -- and never when k = 0."""
    truth = np.zeros((21, 21), bool)
    truth[10, 3:18] = True
    for row in range(5, 16):
        for col in range(0, 21):
            d = float(np.hypot(row - 10, max(0, 3 - col, col - 17)))
            cand = np.zeros((21, 21), np.float32)
            cand[row, col] = 1.0
            k = M.kernel(d)
            assert (M.score(cand, truth) > 0.0) == (k > 0.0), (row, col, d, k)


def test_credit_bar_is_the_exact_break_even_for_a_covering_pixel():
    """With a fully covered trace the marginal pixel's weight k decides: k > 0.2*DTI helps."""
    truth = np.zeros((21, 21), bool)
    truth[10, 3:18] = True
    # (a) a dotted trace: the score rises when a k=1 pixel is added, because 1 > 0.2*DTI
    pred = np.zeros((21, 21), np.float32)
    pred[10, 3:18:2] = 1.0
    before = M.score(pred, truth)
    assert 0.0 < before < 1.0
    cand = pred.copy()
    cand[10, 4] = 1.0
    assert M.score(cand, truth) > before
    # (b) a perfect trace is at the ceiling: extra mass at k=1 is exactly neutral
    perfect = np.zeros((21, 21), np.float32)
    perfect[10, 3:18] = 1.0
    assert M.score(perfect, truth) == pytest.approx(1.0, abs=1e-9)
    dup = perfect.copy()
    dup[10, 3] = 1.0
    assert M.score(dup, truth) == pytest.approx(1.0, abs=1e-9)


def test_redundant_mass_is_harmful_unless_it_covers_truth():
    """Mass that is already covered is pure FP cost: k=1 is neutral, k<1 is harmful."""
    truth = np.zeros((21, 21), bool)
    truth[10, 3:18] = True
    pred = np.zeros((21, 21), np.float32)
    pred[10, 3:18] = 1.0
    before = M.score(pred, truth)
    for row, col in [(10, 8), (10, 12), (11, 8), (13, 8)]:
        d = np.hypot(row - 10, 0)
        cand = pred.copy()
        cand[row, col] = 1.0
        if d == 0:
            assert M.score(cand, truth) == pytest.approx(before), "duplicate on the trace is neutral"
        else:
            assert M.score(cand, truth) < before, "duplicate off the trace is harmful"
