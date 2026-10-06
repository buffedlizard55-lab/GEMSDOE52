"""Round-4 (H33) hypotheses, the live-mirror instrument and the live-anchored slot gate.

Every test here is either a pure-maths check on the metric algebra or a check on the *logic* of the
gate.  The tests that need the competition rasters are skipped when `data/raw` is absent, so CI on a
clean checkout still runs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

def _read_band(path):
    import rasterio
    with rasterio.open(path) as ds:
        return ds.read(1).astype(np.float64)


RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


from gems52.hypotheses33 import (
    _hessian_ridge_response,
    _idw_surface,
    compute_h33_2_flank_sweep,
    missing_external_inputs,
    skeleton_endpoints_and_junctions,
)
from gems52.live_anchor import LIVE_LEDGER, invert_live_pair, lm_validity_report, removal_gain_bound

DATA = Path(__file__).resolve().parents[1] / "data" / "raw"
HAS_DATA = (DATA / "training_features.tif").exists()


# --------------------------------------------------------------------------------------------
# pure maths / logic
# --------------------------------------------------------------------------------------------

def test_idw_surface_is_local_and_bounded():
    """IDW with k = 2 always blends the second-nearest point, so the exact value at a node is the
    weighted mean -- not the node value.  What must hold is locality and boundedness."""
    pts = np.array([[10.0, 10.0], [50.0, 60.0]])
    vals = np.array([100.0, 200.0])
    s = _idw_surface(pts, vals, (80, 80), length_scale_px=10.0, k=2, sigma=0.0)
    assert s.shape == (80, 80)
    # at a node the surface is pulled towards the other node, but stays on the correct side
    assert 100.0 < s[10, 10] < 150.0
    assert 150.0 < s[50, 60] < 200.0
    # a single point with k = 1 reproduces its value exactly
    s1 = _idw_surface(pts[:1], vals[:1], (80, 80), length_scale_px=10.0, k=1, sigma=0.0)
    assert s1[10, 10] == pytest.approx(100.0)
    assert float(s1.min()) >= 0.0


def test_idw_surface_with_no_points_is_zero_not_crash():
    s = _idw_surface(np.zeros((0, 2)), np.zeros(0), (10, 10), sigma=0.0)
    assert s.shape == (10, 10) and float(np.abs(s).max()) == 0.0


def test_hessian_ridge_response_is_finite():
    """The Sato/Frangi response is not sign-definite on noise; it must be finite and it must
    actually respond to a synthetic ridge."""
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(0)
    a = gaussian_filter(rng.normal(size=(64, 64)), 2.0).astype(np.float32)
    r = _hessian_ridge_response(a, 2.0)
    assert np.isfinite(r).all()
    assert float(r.std()) > 0.0
    # a bright bar on a dark background must produce a positive ridge response on the bar
    bar = np.full((64, 64), -5.0, dtype=np.float32)
    bar[28:36, 5:59] = 5.0
    rb = _hessian_ridge_response(bar, 2.0)
    assert float(rb[31, 30]) > 0.0


def test_skeleton_endpoints_and_junctions():
    # a straight line: 2 endpoints, no junction
    line = np.zeros((11, 11), dtype=bool)
    line[5, 2:9] = True
    t, j = skeleton_endpoints_and_junctions(line)
    assert int(t.sum()) == 2
    assert int(j.sum()) == 0
    # a plus sign under the 8-neighbourhood rule: 4 endpoints and 5 pixels with >= 3 neighbours
    # (the centre plus the four arm pixels that touch the cross arm diagonally)
    f = np.zeros((11, 11), dtype=bool)
    f[5, 2:9] = True
    f[2:9, 5] = True
    t, j = skeleton_endpoints_and_junctions(f)
    assert int(t.sum()) == 4
    assert int(j.sum()) == 5


def test_flank_sweep_is_monotone_in_the_buffer():
    labels = np.zeros((40, 40), dtype=bool)
    labels[20, 20] = True
    base = np.zeros((40, 40), dtype=bool)
    base[20, 21] = True   # d = 1
    base[20, 22] = True   # d = 2
    base[20, 23] = True   # d = 3
    out = compute_h33_2_flank_sweep(base, labels, buffers=(1, 2, 3))
    assert int(out[1].sum()) == 2
    assert int(out[2].sum()) == 1
    assert int(out[3].sum()) == 0
    # nested by construction: every dot surviving B also survives B+1
    for b in (1, 2):
        assert bool((out[b + 1] & ~out[b]).sum() == 0)


def test_live_inversion_recovers_the_observed_pair():
    inv = invert_live_pair()
    assert inv.dti_hi == 0.2708 and inv.dti_lo == 0.2600
    assert inv.n_lo - inv.n_hi == 3891
    # S / D must reproduce both observed scores exactly
    d_lo = inv.d_hi + 0.2 * (inv.n_lo - inv.n_hi)
    assert inv.s_hi / inv.d_hi == pytest.approx(0.2708, abs=1e-12)
    assert inv.s_hi / d_lo == pytest.approx(0.2600, abs=1e-12)
    # mean credit per dot must be physically admissible (<= 1)
    assert 0.0 < inv.s_hi / inv.n_hi <= 1.0


def test_removal_gain_bound_is_zero_when_credit_cost_equals_the_budget():
    inv = invert_live_pair()
    # a removal of 0 dots has a zero budget, so any positive cost fails
    r = removal_gain_bound(inv, 0, 1.0)
    assert r["gain"] is False
    # a removal costing nothing always gains
    r2 = removal_gain_bound(inv, 1000, 0.0)
    assert r2["gain"] is True
    assert r2["safety_factor"] == float("inf")


def test_removal_gain_bound_rejects_an_over_expensive_removal():
    inv = invert_live_pair()
    budget = removal_gain_bound(inv, 2545, 1.0)["max_allowed_credit_loss"]
    assert removal_gain_bound(inv, 2545, budget * 0.5)["gain"] is True
    assert removal_gain_bound(inv, 2545, budget * 2.0)["gain"] is False


def test_lm_validity_report_flags_the_drift():
    rep = lm_validity_report({
        "H27-4-R1-SOLO": {"lm_mean": 0.263051, "emitted_pixels": 40199},
        "SAFE-MASS-PRUNED": {"lm_mean": 0.441279, "emitted_pixels": 7943},
    })
    row = next(r for r in rep["rows"] if r["candidate"] == "H27-4-R1-SOLO")
    # the live-minus-LM gap on the live-scored reference must be reported, not hidden
    assert row["live_minus_lm"] == pytest.approx(0.2708 - 0.263051)
    pruned = next(r for r in rep["rows"] if r["candidate"] == "SAFE-MASS-PRUNED")
    assert pruned["owner_reported_live_dti"] is None
    assert pruned["lm_calibrated_mean"] > 0.3262   # above the whole leaderboard: the drift finding


def test_live_ledger_dot_counts_match_the_owner_brief():
    assert LIVE_LEDGER["H27-4-R1-SOLO"]["dots"] == 40199
    assert LIVE_LEDGER["H27-4-R1-SOLO"]["dti"] == 0.2708
    assert LIVE_LEDGER["D2.8"]["dots"] == 44090
    assert LIVE_LEDGER["D2.8"]["dti"] == 0.2600


def test_missing_external_inputs_names_the_official_source():
    info = missing_external_inputs(Path("/nonexistent"))
    assert set(info) == {"2m_temperature_probes", "paleo_geothermal_features"}
    for v in info.values():
        assert v["url"].startswith("https://gdr.openei.org/files/1391/")
        assert v["published_bytes"] > 0
        assert v["hypothesis"].startswith("H33-")


# --------------------------------------------------------------------------------------------
# raster-dependent (skipped on a clean checkout)
# --------------------------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_DATA, reason="competition rasters not restored")
def test_gdr_thermal_prior_measured_on_the_real_tables():
    from gems52.hypotheses33 import compute_gdr_thermal_prior
    from gems52.holdout import read_binary
    import rasterio

    with rasterio.open(DATA / "sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    labels = read_binary(DATA / "labels.tif") & foot
    out = compute_gdr_thermal_prior(DATA, foot)
    st = {k: v for k, v in out.items() if not isinstance(v, (np.ndarray,))}
    # these are measured facts, not assertions about the model
    assert st["n_geothermometer_sites"] == 184
    assert st["n_sites_gt150"] == 53
    assert st["n_sites_gt150_far"] == 15
    assert st["n_sites_gt180"] == 22
    t = out["T_reservoir"]
    assert t.shape == foot.shape
    assert np.isfinite(t).all()
    assert float(t[foot].max()) > 150.0


@pytest.mark.skipif(not HAS_DATA, reason="competition rasters not restored")
def test_the_shipped_primary_is_portal_legal():
    """The one-click primary must be single-band float32, all finite, in [0, 1], no nodata."""
    import glob

    import rasterio

    cands = sorted(glob.glob("docs/downloads/gemsdoe32-h33-h33-2-b2-*-zeros.tif"))
    assert cands, "the H33-2-B2 primary download is missing"
    with rasterio.open(cands[0]) as ds:
        assert ds.count == 1
        assert ds.dtypes[0] == "float32"
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert ds.nodata is None
        a = ds.read(1)
    assert np.isfinite(a).all(), "the file carries NaN -- this is the portal rejection mechanism"
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    assert int((a > 0).sum()) == 37654
    # nothing within 200 m of the catalogue
    from scipy.ndimage import distance_transform_edt
    from gems52.holdout import read_binary
    labels = read_binary(DATA / "labels.tif")
    d = distance_transform_edt(~labels)
    assert int(((a > 0) & (d <= 2)).sum()) == 0


# ---------------------------------------------------------------------------------------------
# The load-bearing claim of the whole round, checked pixel-exactly from the published rasters.
# If this ever fails, the live-anchored inversion in src/gems52/live_anchor.py is built on sand.
# ---------------------------------------------------------------------------------------------
def _require_scored(*names: str):
    missing = [n for n in names if not (RAW / "scored" / n).exists()]
    if missing:
        pytest.skip(f"group artifacts not fetched in this checkout: {missing}")


def test_02708_is_exactly_d28_minus_its_3891_catalogue_adjacent_dots():
    _require_scored("gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
                    "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
    from scipy import ndimage
    d28 = _read_band(RAW / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif")
    best = _read_band(RAW / "scored/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
    cat = _read_band(RAW / "existing_faults.tif")
    dist = ndimage.distance_transform_edt(~(cat > 0))
    assert int((d28 > 0).sum()) == 44_090
    assert int((best > 0).sum()) == 40_199
    assert int(((d28 > 0) & (dist <= 1)).sum()) == 3_891
    # the 0.2708 file is exactly D2.8 with those dots deleted -- no other pixel changed
    keep = (d28 > 0) & (dist > 1)
    assert bool(np.array_equal(keep, best > 0))


def test_existing_faults_is_byte_identical_to_labels():
    _require_scored()
    if not (RAW / "labels.tif").exists():
        pytest.skip("labels.tif not present")
    assert (RAW / "existing_faults.tif").read_bytes() == (RAW / "labels.tif").read_bytes()


def test_flank_b2_removes_exactly_2545_dots_from_the_02708_base():
    """B = 1 is already applied to the base, so B = 2 must delete the dots at distance exactly 2."""
    _require_scored("gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
    from scipy import ndimage
    best = _read_band(RAW / "scored/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
    cat = _read_band(RAW / "existing_faults.tif")
    dist = ndimage.distance_transform_edt(~(cat > 0))
    assert int(((best > 0) & (dist <= 1)).sum()) == 0, "the 0.2708 base is not B=1-pruned"
    # `dist` is Euclidean, so the band (1, 2] also contains the diagonal neighbours at sqrt(2):
    # 1,344 dots sit at exactly 2 px and 1,201 in the open interval (1, 2).
    assert int(((best > 0) & (dist <= 2)).sum()) == 2_545
    assert int(((best > 0) & (dist > 2)).sum()) == 37_654
