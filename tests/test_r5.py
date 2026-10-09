"""R5 regression tests: the bugs that were found by running, and the rules that were frozen.

Each test here exists because something went wrong or because a number is load-bearing:

  * ``fold[rows]`` on a 2-D grid selects whole rows -- ~4 GB here, an OOM kill, no traceback
    (IR-R5-002).
  * ``component_folds`` divided a length-(n+1) centroid sum by a length-n size vector and died with a
    broadcast error two stages downstream of the real mistake.
  * ``place_dots`` cut its candidate list to the budget, which caps every emission at about
    budget/7 because a ranked field is spatially clustered.
  * ``S* = 4|G|beta/(1-beta)`` is the frozen budget rule; if the algebra behind it is wrong the
    emission size is wrong and nothing downstream notices.
  * The organiser's format clauses are the difference between a submission and the portal's
    "Predicted values must be in range [0, 1]" rejection.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems52 import grid as GRID
from gems52_r5 import cotrain_r5 as C
from gems52_r5 import localize as Z

G_PX = 14088.7
BETA = 0.2284
C_FIELD = 471.6


# -------------------------------------------------------------------------------- IR-R5-002
def test_fold_lookup_must_be_paired_indexing():
    """The two-character bug: one index array on a 2-D grid selects whole rows."""
    fold = np.zeros((40, 30), np.int16)
    fold[10:20, 20:26] = 1                                 # a narrow strip: the sampled columns miss it
    fold[30:, 20:] = 3
    rows = np.array([0, 15, 31, 39])
    cols = np.array([0, 5, 25, 29])

    paired = fold[rows, cols]
    assert paired.shape == (rows.size,)
    assert list(paired) == [0, 0, 3, 3]

    whole_rows = fold[rows]
    assert whole_rows.shape == (rows.size, fold.shape[1])          # the trap: 2-D, not per-pixel
    assert whole_rows.nbytes > paired.nbytes * 5
    # and the fold test built from it is wrong: row 15 does contain fold 1, but the *sampled pixel*
    # (15, 5) does not, so the whole-row form marks a training pixel as held out
    assert bool((whole_rows == 1).any(axis=1)[1]) is True
    assert bool((paired == 1)[1]) is False


def test_fit_oof_uses_paired_indexing_on_the_sample():
    """Guard the call site itself: fit_oof must never index the grid with one array."""
    import inspect
    src = inspect.getsource(C.fit_oof)
    assert "fold[rows, cols]" in src
    code = "\n".join(l.split("#")[0] for l in src.splitlines())   # comments explain the trap; code must not contain it
    assert "fold[rows]" not in code and "fold[cols]" not in code


# -------------------------------------------------------------------------------- component_folds
def test_component_folds_partitions_every_component_exactly_once():
    """The [1:] slice must come after dividing by sizes, never before.

    bincount over component ids is indexed 1..n with slot 0 unused, so the centroid sums have length
    n+1 while the size vector has length n.  Slicing first divides component i+1's centroid by
    component i's size and then fails to broadcast -- which is how it presented, two stages away from
    the mistake.
    """
    rng = np.random.default_rng(7)
    valid = np.zeros((60, 80), bool)
    valid[5:55, 5:75] = True
    cat = np.zeros_like(valid)
    n_comp = 30
    for i in range(n_comp):
        r = int(rng.integers(6, 50))
        c = int(rng.integers(6, 70))
        cat[r:r + 3, c:c + 2] = True                    # 6-px blobs, may overlap
    cat &= valid

    fold = Z.component_folds(cat, valid, n_folds=4)
    assert fold.shape == cat.shape and fold.dtype == np.int16
    assert (fold[cat & valid] >= 0).all(), "every catalogue pixel must land in a fold"
    assert (fold[~cat] == -1).all(), "non-catalogue pixels carry no fold id"
    assert set(np.unique(fold[cat])) <= {0, 1, 2, 3}
    # a component is never split across folds -- that is the whole point of assigning components
    from scipy import ndimage
    comp, n_comp = ndimage.label(cat & valid, structure=np.ones((3, 3), bool))
    assert n_comp > 1
    for cid in range(1, n_comp + 1):
        ids = np.unique(fold[comp == cid])
        assert ids.size == 1, f"component {cid} was split across folds {ids}"
    # and the deal is balanced by pixels, not by component count
    per_fold = np.array([int((cat & (fold == k)).sum()) for k in range(4)])
    assert per_fold.sum() == int(cat.sum())
    assert per_fold.min() > 0
    assert per_fold.max() / max(per_fold.min(), 1) < 2.0
    # determinism: the same seed gives the same deal
    assert np.array_equal(fold, Z.component_folds(cat, valid, n_folds=4))


def test_fold_masks_geometry_and_truth_survival():
    rng = np.random.default_rng(11)
    valid = np.ones((50, 60), bool)
    cat = np.zeros_like(valid)
    cat[10:12, 10:40] = True
    cat[30:32, 5:50] = True
    fold = np.zeros((50, 60), np.int16)
    fold[:, 30:] = 1
    m = Z.fold_masks(cat, valid, fold, k=0, buffer_px=2)
    for key in ("hidden", "visible", "legal", "train_exclusion", "hidden_px", "legal_px",
                "truth_survival_in_legal"):
        assert key in m
    assert m["hidden"].shape == valid.shape
    assert not (m["hidden"] & m["visible"]).any(), "hidden and visible must be disjoint"
    assert m["legal"].dtype == bool
    assert 0.0 <= m["truth_survival_in_legal"] <= 1.0
    # fold 0 hides the left half, so the trace that lives entirely on the left must mostly survive
    assert m["hidden"][10:12, 10:30].all()


# -------------------------------------------------------------------------------- place_dots
def test_place_dots_reaches_the_budget_on_a_clustered_field():
    """Cutting the candidate list to the budget caps output at ~budget/7; scan_cap must not."""
    rng = np.random.default_rng(3)
    h = w = 200
    allowed = np.ones((h, w), bool)
    score = rng.random((h, w)).astype(np.float32)
    # a clustered field: hot blobs, exactly the shape a real detector's rank field has
    for _ in range(40):
        r, c = int(rng.integers(10, h - 10)), int(rng.integers(10, w - 10))
        score[max(0, r - 4):r + 5, max(0, c - 4):c + 5] += 3.0

    budget = 500
    dots = Z.place_dots(score, allowed, budget, min_sep_px=3.0, prefilter=True, scan_cap=100_000)
    got, want, seen = Z.place_dots.last_shortfall
    assert got == want == budget, f"placed {got} of {want} while scanning {seen}"
    assert int(dots.sum()) == budget
    ys, xs = np.nonzero(dots)
    # the 3 px exclusion really holds
    d = np.hypot(ys[:, None] - ys[None, :], xs[:, None] - xs[None, :])
    np.fill_diagonal(d, np.inf)
    assert d.min() >= 3.0


def test_place_dots_reports_a_real_shortfall_instead_of_padding():
    allowed = np.zeros((60, 60), bool)
    allowed[10:14, 10:14] = True                        # 16 px of room, 3 px exclusion -> ~2 dots
    score = np.ones((60, 60), np.float32)
    dots = Z.place_dots(score, allowed, 100, min_sep_px=3.0, prefilter=False, scan_cap=10_000)
    got, want, seen = Z.place_dots.last_shortfall
    assert want == 100 and got < want
    assert int(dots.sum()) == got
    assert (dots & ~allowed).sum() == 0, "no dot may fall outside the allowed set"


# -------------------------------------------------------------------------------- budget rule
def test_budget_star_is_the_stationary_point_of_the_dti_curve():
    """S* = 4|G|beta/(1-beta): the amplitude cancels, so it can be frozen before any candidate exists."""
    s_star = int(round(4.0 * G_PX * BETA / (1.0 - BETA)))
    assert s_star == 16681

    def dti(s, c=C_FIELD, g=G_PX, beta=BETA):
        return min(c * s ** beta, g) / (0.2 * s + 0.8 * g)

    grid = np.arange(2_000, 60_000, 250)
    best = grid[int(np.argmax([dti(float(s)) for s in grid]))]
    assert abs(best - s_star) <= 500, f"numeric optimum {best} disagrees with the closed form {s_star}"
    # sensitivity quoted in knowledge/27 §4
    assert int(round(4.0 * G_PX * 0.15 / 0.85)) == 9945
    assert int(round(4.0 * G_PX * 0.30 / 0.70)) == 24152
    # and it scales linearly in |G|, which is the whole of the final-round argument
    assert abs(int(round(4.0 * (2 * G_PX) * BETA / (1.0 - BETA))) - 2 * s_star) <= 1  # rounding only


def test_marginal_credit_bar_is_alpha_times_dti():
    """Adding mass helps iff its marginal credit rate exceeds alpha*DTI -- so random mass always hurts.

    d/dS [T/(alpha S + beta|G|)] > 0  <=>  dT/dS > alpha*DTI, which is exactly ``metric.credit_bar``.
    """
    from gems52 import metric as M
    for dti_value in (0.05, 0.2778, 0.3195, 0.3774):
        assert M.credit_bar(dti_value) == pytest.approx(M.ALPHA * dti_value, rel=1e-12)

    # the derivative, checked numerically rather than trusted algebraically
    s, t = 40_000.0, 5_305.0
    dti = t / (M.ALPHA * s + M.BETA * G_PX)
    for d in (1.0, 10.0, 100.0):
        gain = (t + M.credit_bar(dti) * d) / (M.ALPHA * (s + d) + M.BETA * G_PX) - dti
        assert abs(gain) < 1e-6, "at the bar the score is stationary"
        loss = (t + 0.5 * M.credit_bar(dti) * d) / (M.ALPHA * (s + d) + M.BETA * G_PX) - dti
        assert loss < 0, "below the bar, more mass lowers DTI"
    # uniform random over the legal footprint earns ~0.024 per pixel, below the bar at every live DTI
    rho_random = G_PX * 8.14 / 4_861_502
    assert rho_random < M.credit_bar(0.2778) < M.credit_bar(0.3195) < M.credit_bar(0.3774)


def test_win_probability_is_monotone_in_the_target_and_matches_the_closed_form():
    import importlib.util
    spec = importlib.util.spec_from_file_location("r5novel", "scripts/run_r5_novel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    s = 16_681
    t1 = C_FIELD * s ** BETA
    lo, hi = mod.KAPPA
    prev = None
    for target in (0.2778, 0.3195, 0.3774):
        r = mod.win_probability(s, target)
        need = target * (0.2 * s + 0.8 * G_PX)
        assert r["credit_needed"] == pytest.approx(need)
        assert r["kappa_needed"] == pytest.approx(need / t1)
        assert r["p_win"] == pytest.approx(float(np.clip((hi - need / t1) / (hi - lo), 0.0, 1.0)))
        if prev is not None:
            assert r["p_win"] < prev, "a harder target must be less likely"
        prev = r["p_win"]
    assert mod.budget_star() == 16681


# -------------------------------------------------------------------------------- format clauses
def test_write_geotiff_refuses_the_portal_rejection_before_it_can_happen():
    arr = np.zeros(GRID.SHAPE, np.float32)
    arr[100, 100] = 1.0
    with pytest.raises(ValueError):
        GRID.write_geotiff("/tmp/should_not_exist_nan.tif", arr * np.nan)
    arr[0, 0] = np.nan
    with pytest.raises(ValueError):
        GRID.write_geotiff("/tmp/should_not_exist_nan.tif", arr)
    arr[0, 0] = 1.5
    with pytest.raises(ValueError):
        GRID.write_geotiff("/tmp/should_not_exist_range.tif", arr)
    import pathlib
    assert not pathlib.Path("/tmp/should_not_exist_nan.tif").exists()
    assert not pathlib.Path("/tmp/should_not_exist_range.tif").exists()


def test_official_submission_clauses_are_pinned():
    """The four clauses the organiser publishes (knowledge/25 §4), as constants that cannot drift."""
    assert GRID.CRS_EPSG == "EPSG:32611"
    assert GRID.CELL_M == 100.0
    assert GRID.SHAPE == (3730, 3292)
    assert tuple(float(v) for v in GRID.TRANSFORM) == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def test_shipped_r5_artifact_satisfies_every_clause(tmp_path):
    """End-to-end on the real receipt, skipped when the restored bytes are not present."""
    import json
    from pathlib import Path
    rec = Path("docs/data/submission_r5.json")
    tif = Path("submission") / (json.loads(rec.read_text())["stem"] + ".tif") if rec.is_file() else None
    if tif is None or not tif.is_file() or not Path("data/sample_submission.tif").is_file():
        pytest.skip("R5 artifact or competition fixture not restored in this checkout")
    info = GRID.read_geotiff(tif)
    ref = GRID.read_geotiff(Path("data/sample_submission.tif"))
    rec_j = json.loads(rec.read_text())
    assert info["bands"] == 1 and info["dtype"] == "float32"
    assert info["crs"] == ref["crs"] == "EPSG:32611"
    assert tuple(info["transform"]) == tuple(ref["transform"])
    assert (info["height"], info["width"]) == (ref["height"], ref["width"]) == GRID.SHAPE
    assert info["finite_pixels"] == info["height"] * info["width"], "every cell must be finite"
    assert info["min"] >= 0.0 and info["max"] <= 1.0
    assert info["unique_values"] == 2
    assert info["positive_pixels"] == rec_j["nonzero_px"]
    assert info["sha256"] == rec_j["sha256"]
    assert len(rec_j["note"]) <= 200


# -------------------------------------------------------------------------------- co-training
def test_pseudo_labels_reports_the_empty_set_as_a_measurement():
    """Independent random views: the component reading must come back empty and say why."""
    rng = np.random.default_rng(5)
    shape = (200, 200)
    legal = np.ones(shape, bool)
    legal[:5, :] = False
    a = rng.random(shape).astype(np.float64)
    b = rng.random(shape).astype(np.float64)
    a[~legal] = np.nan
    b[~legal] = np.nan
    bid = np.zeros(shape, np.int32)
    bid[:, :100] = 0
    bid[:, 100:] = 1

    comp = C.pseudo_labels(a, b, legal, np.zeros(shape, np.int16), np.zeros(shape, bool),
                           unit="component", bid=bid, min_px=9)
    assert comp["a_to_b"]["px"] == 0
    assert comp["a_to_b"]["raw_px"] > 0, "the raw cut is not empty; the component filter is what empties it"
    # for independent views the raw count must sit near the independence expectation
    assert comp["a_to_b"]["ratio_to_independence"] == pytest.approx(1.0, abs=0.35)
    assert comp["expected_px_under_independence"] > 0

    blk = C.pseudo_labels(a, b, legal, np.zeros(shape, np.int16), np.zeros(shape, bool),
                          unit="block", bid=bid, min_px=9)
    assert blk["a_to_b"]["px"] >= 0
    with pytest.raises(ValueError):
        C.pseudo_labels(a, b, legal, np.zeros(shape, np.int16), np.zeros(shape, bool), unit="block")


def test_independence_verdict_respects_the_abandonment_threshold():
    rng = np.random.default_rng(2)
    shape = (180, 180)
    valid = np.ones(shape, bool)
    pos = np.zeros(shape, bool)
    bid = np.zeros(shape, np.int32)
    for i in range(6):
        for j in range(6):
            bid[i * 30:(i + 1) * 30, j * 30:(j + 1) * 30] = i * 6 + j
            pos[i * 30 + 3:i * 30 + 6, j * 30 + 3:j * 30 + 6] = True   # both classes in every block
    neg = valid & ~pos
    # independence() needs >= min_blocks blocks with >= min_px labelled negatives each; 36 blocks of
    # 900 px with 9 positives satisfies it, and the 4x4 version did not (it returned
    # "insufficient_blocks", which is the correct answer for too few blocks, not a bug)
    indep = C.independence(rng.random(shape), rng.random(shape), pos, neg, bid)
    assert indep["verdict"] == "independent" and indep["independent"] is True
    assert indep["max_abs"] < C.ABANDON_R

    shared = rng.random(shape)
    assert indep["n_blocks"] >= 20
    coupled = C.independence(shared, shared + 0.01 * rng.random(shape), pos, neg, bid)
    assert coupled["n_blocks"] == indep["n_blocks"]


def test_rank_within_masks_and_never_writes_into_its_input():
    rng = np.random.default_rng(1)
    a = rng.random((40, 40)).astype(np.float32)
    a[~np.eye(40, dtype=bool)] = np.nan
    mask = np.zeros((40, 40), bool)
    mask[5:35, 5:35] = True
    before = a.copy()
    out = C.rank_within(a, mask)
    assert np.array_equal(a, before, equal_nan=True), "rank_within must not touch the field it ranks"
    assert (out[mask & np.isfinite(a)] >= 0).all()
    assert (out[~mask] == -1.0).all()
