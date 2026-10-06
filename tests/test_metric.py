"""Verification of the official metric implementation (no truth assumed beyond the input)."""
import sys, math
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems52 import metric as M  # noqa: E402


def brute(pred, truth, radius=3.0):
    """Literal transcription of the published formulas: O(N^2), used as ground truth."""
    p = np.asarray(pred, float)
    g = np.asarray(truth).astype(bool)
    h, w = p.shape
    ys, xs = np.mgrid[0:h, 0:w]
    gt = np.stack([ys[g], xs[g]], axis=1)
    tp = 0.0
    for gy, gx in gt:
        best = 0.0
        for y in range(h):
            for x in range(w):
                d = math.hypot(y - gy, x - gx)
                if d <= radius:
                    best = max(best, p[y, x] * M.kernel(d))
        tp += best
    fp = 0.0
    for y in range(h):
        for x in range(w):
            if p[y, x] > 0:
                near = max((M.kernel(math.hypot(y - gy, x - gx)) for gy, gx in gt), default=0.0)
                fp += p[y, x] * (1.0 - near)
    fn = len(gt) - tp
    return tp, fp, fn


def test_published_example_arithmetic():
    """The problem description's own worked example: TP=3.00, FP=1.89, FN=2.00 -> 0.60."""
    assert M.dti(3.00, 1.89, 2.00) == pytest.approx(0.6026, abs=5e-4)
    assert round(M.dti(3.00, 1.89, 2.00), 2) == 0.60


def test_bruteforce_equivalence_random():
    rng = np.random.default_rng(0)
    for _ in range(8):
        pred = (rng.random((14, 14)) < 0.12) * rng.random((14, 14))
        truth = rng.random((14, 14)) < 0.10
        c = M.components(pred, truth)
        tp, fp, fn = brute(pred, truth)
        assert c["TP_w"] == pytest.approx(tp, abs=1e-9)
        assert c["FP_w"] == pytest.approx(fp, abs=1e-9)
        assert c["FN_w"] == pytest.approx(fn, abs=1e-9)


def test_algebra_identity():
    rng = np.random.default_rng(1)
    for _ in range(6):
        pred = (rng.random((16, 16)) < 0.2) * rng.random((16, 16))
        truth = rng.random((16, 16)) < 0.15
        c = M.components(pred, truth)
        assert c["FN_w"] == pytest.approx(c["K"] - c["TP_w"], abs=1e-9)
        assert c["FP_w"] == pytest.approx(c["S"] - c["M"], abs=1e-9)
        assert M.dti(c["TP_w"], c["FP_w"], c["FN_w"]) == pytest.approx(
            M.dti_algebra(c["TP_w"], c["S"], c["M"], c["K"]), abs=1e-12)


def test_marginal_emission_rule_exact_single_truth_pixel():
    """Exact check of ``dDTI > 0 <=> k > 0.2 DTI`` on an isolated truth pixel.

    With a single truth pixel and a single added pixel the improved credit is exactly
    ``k = kernel(d)`` and the added false-positive mass is ``1 - k``, so the rule is exact.
    """
    truth = np.zeros((25, 25), bool)
    truth[10, 10] = True
    for d in range(1, 6):
        pred = np.zeros((25, 25))
        # a starter emission that is *not* on the truth pixel, so dDTI is non-trivial
        pred[20, 20] = 1.0
        before = M.score(pred, truth)
        k = M.kernel(d)
        cand = pred.copy()
        cand[10, 10 + d] = 1.0
        after = M.score(cand, truth)
        assert (after > before) == (k > M.ALPHA * before), (d, k, before, after)


def test_far_mass_is_always_harmful():
    truth = np.zeros((21, 21), bool)
    truth[10, 3:18] = True
    pred = np.zeros((21, 21))
    pred[10, 5:15] = 1.0
    before = M.score(pred, truth)
    cand = pred.copy()
    cand[10, 20] = 1.0   # >= 3 px (300 m) from every truth pixel (truth ends at col 17)
    assert M.score(cand, truth) < before


def test_duplicate_mass_on_covered_truth_is_neutral_or_harmful():
    truth = np.zeros((21, 21), bool)
    truth[10, 3:18] = True
    pred = np.zeros((21, 21))
    pred[10, 3:18] = 1.0                          # exactly on the line
    base = M.score(pred, truth)
    assert base == pytest.approx(1.0, abs=1e-9)   # exact match scores 1.0
    dup = pred.copy()
    dup[11, 4:18] = 1.0                           # extra ribbon one pixel off
    assert M.score(dup, truth) < base


def test_credit_audit_off_by_one_ribbon():
    mask = np.zeros((15, 15), bool)
    mask[7, 2:13] = True
    a = M.credit_audit(mask)
    assert a.n_emitted == 11
    assert a.redundancy_fraction > 0.9            # a straight line is fully self-redundant
