"""H59 unit tests: view spec, fields, decision rule, OOF folds, gates, reasoning rows."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import h59  # noqa: E402


def test_view_spec_matches_registration() -> None:
    """View A carries the brief's strain/seismicity bands (7/8/10); band 6 stays in View B."""
    a_bands = sorted(b for _, b, _ in h59.VIEW_A_BANDS)
    assert a_bands == sorted([1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18])
    b_bands = sorted(b for _, b, n in h59.VIEW_B_BANDS
                     if "training_features" in str(_))
    assert b_bands == [6, 12, 19]
    assert "A_geod_shearrate" in h59.VIEW_A_LAYERS
    assert "A_deq" in h59.VIEW_A_LAYERS
    assert "B_rad_tc" in h59.VIEW_B_LAYERS          # band 6 is measured radiometric TC (IR-52-019)
    assert len(h59.VIEW_A_LAYERS) * 3 == 48
    assert len(h59.VIEW_B_LAYERS) * 3 == 36


def test_field_product_and_veto() -> None:
    pa = np.array([[0.9, 0.2], [0.5, np.nan]], np.float32)
    pb = np.array([[0.1, 0.8], [0.7, 0.3]], np.float32)
    prod = h59.field_product(pa, pb)
    assert prod[0, 0] == pytest.approx(0.09)
    assert prod[1, 1] == 0.0                          # NaN -> 0, never NaN in a field
    union = np.maximum(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0))
    b_only = np.zeros((2, 2), bool)
    b_only[1, 0] = True
    field, veto = h59.field_veto_b(union, b_only)
    assert veto[1, 0] is np.bool_(False)
    assert field[1, 0] == 0.0                         # vetoed stratum carries no rank
    assert field[0, 0] == pytest.approx(0.9)


def test_spacing_stats_and_support_novelty() -> None:
    em = np.zeros((20, 20), bool)
    em[5, 5] = em[5, 9] = em[10, 5] = True
    s = h59.spacing_stats(em)
    assert s["n"] == 3
    assert s["min_nn_px"] == pytest.approx(4.0)       # (5,5)-(5,9) is 4 px; (5,5)-(10,5) is 5
    prior = np.zeros((20, 20), bool)
    prior[5, 5] = True
    nov = h59.support_novelty(em, [("p1", prior)], reference=("ref", prior))
    assert nov["emission_novel_px"] == 2
    assert nov["emission_novel_fraction"] == pytest.approx(2 / 3)
    assert nov["overlap_with_reference_px"] == 1


def test_not_the_union_checks() -> None:
    shape = (40, 40)
    rng = np.random.default_rng(0)
    pa = rng.random(shape).astype(np.float32)
    pb = rng.random(shape).astype(np.float32)
    pool = np.ones(shape, bool)
    em_union = h59.iso_select_exact(np.maximum(pa, pb), pool, 20)
    checks = h59.not_the_union_checks(em_union, pa, pb, pool, budget=20)
    # the union-field emission legitimately equals its own field's emission (reported, not gated)
    assert checks["equals_union_field"] is True
    assert checks["equals_set_union"] is False        # a max-ranking is not the set union
    assert checks["equals_view_a"] is False
    assert checks["equals_view_b"] is False
    em_a = h59.iso_select_exact(pa, pool, 20)
    checks_a = h59.not_the_union_checks(em_a, pa, pb, pool, budget=20)
    assert checks_a["equals_view_a"] is True          # a field's own emission is caught


def test_utmxy_uses_pinned_transform() -> None:
    east, north = h59._utmxy(np.array([0]), np.array([0]))
    assert east[0] == pytest.approx(243350.0 + 50.0)
    assert north[0] == pytest.approx(4508550.0 - 50.0)


def test_iso_select_exact_reaches_budget_and_keeps_spacing() -> None:
    """The exact greedy reaches any budget the pool can carry -- the NMS-5 prefilter of
    h57.iso_select capped a smooth field at 27,905/37,654 (the H59 emitter amendment)."""
    rng = np.random.default_rng(7)
    # a smooth single-peak field: the worst case for local-maximum prefilters
    yy, xx = np.mgrid[0:120, 0:120]
    field = np.exp(-(((yy - 60) ** 2 + (xx - 60) ** 2) / 800.0)).astype(np.float32)
    pool = np.ones(field.shape, bool)
    nodes = h59.iso_select_exact(field, pool, 400)
    assert int(nodes.sum()) == 400                      # full budget on a smooth field
    s = h59.spacing_stats(nodes)
    assert s["min_nn_px"] >= 3.0                        # inclusive 3 px rule holds everywhere
    # greedy order property: the field maximum is always taken
    assert nodes[60, 60]
    # a tiny k and a zero budget behave
    assert int(h59.iso_select_exact(field, pool, 0).sum()) == 0
    assert int(h59.iso_select_exact(field, ~pool, 5).sum()) == 0


# --------------------------------------------------------------------------------------------
# decision rule
# --------------------------------------------------------------------------------------------
def _summary_from_rows(rows):
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_h59
    return run_h59.summarize(rows)


def _mkrow(mode, fold, arm, dti):
    return dict(mode=mode, fold=fold, budget_label="primary", arm=arm, dti=dti,
                support_shortfall=0, emitted=37654, requested_budget=37654,
                global_budget=37654, legal_pixels=1, field_support_pixels=1, tpw=0, fpw=0,
                fnw=0, n_truth=10)


def test_decide_field_picks_eligible_winner_and_excludes_diagnostics() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_h59
    rows = []
    for mode in ("hide", "block"):
        for fold in range(4):
            rows.append(_mkrow(mode, fold, "random", 0.001))
            rows.append(_mkrow(mode, fold, "view_A", 0.004))
            rows.append(_mkrow(mode, fold, "view_B", 0.005))
            rows.append(_mkrow(mode, fold, "union", 0.006))
            rows.append(_mkrow(mode, fold, "product", 0.0055))
            rows.append(_mkrow(mode, fold, "vetoB", 0.0044))
            rows.append(_mkrow(mode, fold, "basestep", 0.002))
            rows.append(_mkrow(mode, fold, "seismicity", 0.002))
            # a diagnostic arm that wins everything must still never ship
            rows.append(_mkrow(mode, fold, "a_only_stratum", 0.009))
    summary = run_h59.summarize(rows)
    decision = run_h59.decide_field(summary, independence_ok=True)
    assert decision["shipped_field"] == "union"
    assert "a_only_stratum" not in decision["eligible_fields"]
    # union beats the best single view (0.005) by 0.001 < 0.003 -> not strongly
    assert decision["beats_single_view_strongly"] is False


def test_decide_field_independence_fallback_is_single_view() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_h59
    rows = []
    for mode in ("hide", "block"):
        for fold in range(4):
            rows.append(_mkrow(mode, fold, "random", 0.001))
            rows.append(_mkrow(mode, fold, "view_A", 0.004))
            rows.append(_mkrow(mode, fold, "view_B", 0.005))
            rows.append(_mkrow(mode, fold, "union", 0.009))
    summary = run_h59.summarize(rows)
    decision = run_h59.decide_field(summary, independence_ok=False)
    assert decision["shipped_field"] == "view_B"      # abandoned -> best single view only
    assert decision["independence_abandoned"] is True


# --------------------------------------------------------------------------------------------
# OOF folds
# --------------------------------------------------------------------------------------------
def test_oof_folds_whole_components_and_no_wraparound_border() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_h59
    h, w = 40, 40
    valid = np.ones((h, w), bool)
    cat = np.zeros((h, w), bool)
    # one component crossing the vertical midline: must stay whole in one fold
    cat[10:12, 18:22] = True
    folds = run_h59.oof_folds(cat, valid, buffer_px=2)
    assert len(folds) == 4
    for f in folds:
        assert not (f["fit"] & f["region"]).any()
        assert not (f["fit"] & f["held_comp"]).any()
        assert int(f["held_comp"].sum()) in (0, 8)    # the whole component belongs to one fold
    total_held = sum(int(f["held_comp"].sum()) for f in folds)
    assert total_held == 8
    # no wraparound: fold 0 (top-left quadrant) fits on the opposite (right) edge, and a
    # roll-based border would have carved the last columns out of its fit set via a phantom border
    f0 = folds[0]
    assert not f0["region"][0, 0] is None
    assert f0["region"][0, 0] and f0["region"][h // 2 - 1, w // 2 - 1]
    assert f0["fit"][0, -1], "phantom wraparound border removed the true grid edge from fit"
    assert f0["fit"][-1, 0], "phantom wraparound border removed the true grid edge from fit"
    assert not f0["fit"][0, 0]          # own quadrant is never fit


class _FakeLayers:
    """Minimal Layers stand-in: three named uint8 layers on a small grid."""

    def __init__(self, grids: dict):
        import numpy as _np
        self._grids = {k: _np.asarray(v, _np.uint8) for k, v in grids.items()}

    def index(self, names):
        keys = list(self._grids)
        missing = [n for n in names if n not in keys]
        if missing:
            raise KeyError(missing)
        return np.array([keys.index(n) for n in names], np.int64)

    @property
    def mm(self):
        return np.stack(list(self._grids.values()))


def test_reasoning_rows_writes_a_only_geology(tmp_path) -> None:
    h, w = 12, 12
    valid = np.ones((h, w), bool)
    cat = np.zeros((h, w), bool)
    cat[6, 6] = True
    pa = np.full((h, w), 0.2, np.float32)
    pb = np.full((h, w), 0.1, np.float32)
    emission = np.zeros((h, w), bool)
    emission[2, 2] = True        # A-only (pa high, pb low)
    emission[2, 8] = True        # B-only
    emission[8, 2] = True        # concordant
    emission[8, 8] = True        # neither
    pa[2, 2], pb[2, 2] = 0.9, 0.1
    pa[2, 8], pb[2, 8] = 0.1, 0.9
    pa[8, 2], pb[8, 2] = 0.9, 0.9
    strata = h57_disagreement(pa, pb, np.ones((h, w), bool))
    layers = _FakeLayers({
        "A_depth_to_base_val": np.full((h, w), 200),
        "A_cond_surf_val": np.full((h, w), 100),
        "B_det_elev_val": np.full((h, w), 128),
        "B_det_elev_slope_val": np.full((h, w), 60),
        "A_grav_anom_grad": np.full((h, w), 90),
        "A_tmi_hg_grad": np.full((h, w), 80),
        "B_lidar_step_max_val": np.full((h, w), 30),
    })
    out = tmp_path / "reasoning.csv"
    receipt = h59.reasoning_rows(emission, pa, pb, strata, layers, valid, cat, out)
    assert receipt["rows"] == 4
    assert receipt["a_only_rows"] == 1
    lines = out.read_text().splitlines()
    assert len(lines) == 5                          # header + 4 rows
    a_only_row = next(ln for ln in lines if ",A_only," in ln)
    assert "not a verified fault" in a_only_row
    assert "Falsified" in a_only_row or "falsified" in a_only_row.lower()


def h57_disagreement(pa, pb, allowed):
    from gems52 import h57
    return h57.disagreement(pa, pb, allowed, q_conf=0.60, q_abstain=0.40)
