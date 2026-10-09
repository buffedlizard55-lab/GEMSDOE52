"""Small synthetic contract tests for the H74S adapter; no fit or experiment is run here."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from run_h72 import build_a_only_surface, not_union_report  # noqa: E402
from run_h74s import _normalized_exit_code  # noqa: E402
from gems52 import nodes  # noqa: E402


def _synthetic_views(shape=(80, 80)):
    n = int(np.prod(shape))
    # Increasing A ranks make a deterministic high-confidence tail.
    a = np.arange(n, dtype=np.float32).reshape(shape)
    flat = a.ravel()
    n_hi = int(np.ceil(0.05 * n))
    hi_idx = np.argsort(flat)[-n_hi:]
    # The highest 40% of that A tail are deliberately B-abstaining; the top 60% are not.
    n_abstain = int(0.40 * n_hi)
    abstain_idx = hi_idx[:n_abstain]
    middle = np.arange(int(0.40 * n), int(0.40 * n) + len(abstain_idx), dtype=np.float32)
    remaining = np.setdiff1d(np.arange(n, dtype=np.float32), middle, assume_unique=False)
    b = np.empty(n, np.float32)
    b[abstain_idx] = middle
    other_idx = np.setdiff1d(np.arange(n), abstain_idx, assume_unique=False)
    b[other_idx] = remaining
    return {"A": a, "B": b.reshape(shape)}


def test_negative_run_card_is_a_successful_cli_result():
    assert _normalized_exit_code({"verdict": "negative"}) == 0
    assert _normalized_exit_code(0) == 0
    assert _normalized_exit_code(None) == 0
    assert _normalized_exit_code(2) == 2


def test_a_only_surface_is_strictly_high_a_and_abstaining_b():
    allowed = np.ones((80, 80), bool)
    views = _synthetic_views(allowed.shape)
    candidate = build_a_only_surface(views, allowed, 0.95, (0.35, 0.65))
    assert candidate["stratum_pixels"] > 0
    assert np.all(candidate["rank_A"][candidate["stratum"]] >= 0.95)
    assert np.all((candidate["rank_B"][candidate["stratum"]] >= 0.35)
                  & (candidate["rank_B"][candidate["stratum"]] <= 0.65))
    assert np.all(candidate["surface"][~candidate["stratum"]] == 0)
    assert np.isfinite(candidate["surface"]).all()
    assert candidate["surface"].min() >= 0 and candidate["surface"].max() <= 1


def test_a_only_candidate_is_not_the_views_or_their_max_union():
    allowed = np.ones((80, 80), bool)
    views = _synthetic_views(allowed.shape)
    candidate = build_a_only_surface(views, allowed, 0.95, (0.35, 0.65))
    # Remove the very highest-A 60% from the synthetic abstention stratum so the fixed A-only
    # placement cannot accidentally be the top-k single-view placement.
    ra = candidate["rank_A"]
    rb = candidate["rank_B"].copy()
    stratum_idx = np.flatnonzero(candidate["stratum"])
    stratum_idx = stratum_idx[np.argsort(ra.ravel()[stratum_idx])]
    rb.ravel()[stratum_idx[-max(1, len(stratum_idx) // 2):]] = 0.99
    lo, hi = 0.35, 0.65
    strict = allowed & (ra >= 0.95) & (rb >= lo) & (rb <= hi)
    candidate = dict(rank_A=ra, rank_B=rb, stratum=strict)
    k = 16
    emission = nodes.spacing_select(np.where(strict, ra, -np.inf).astype(np.float32),
                                    strict, k, min_px=3.0)
    report = not_union_report(
        emission, candidate, views, allowed,
        {"thresholds": {
            "final_output_dots_total": k,
            "minimum_dot_separation_px": 3.0,
        }})
    assert int(emission.sum()) == k
    assert report["every_dot_in_strict_a_only_stratum"]
    assert not report["equals_union_max"]
    assert report["cells_different_from_union"] > 0
    assert report["not_union_pass"]
