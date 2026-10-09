"""H77: the portal-exact writer contract and the shipped artefact.

These tests exist because the brief reported a portal rejection --
"Predicted values must be in range [0, 1]" -- and the structural cause was a container profile this
repository had never matched to the organiser's own template (IR-H77-004).  They pin the writer's
behaviour and re-read the shipped file from disk, so neither can regress silently.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from gems52 import grid

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_submission.tif"
BUILD = ROOT / "evidence" / "h77_build.json"


def _template_profile():
    with rasterio.open(SAMPLE) as ds:
        p = ds.profile
        return dict(crs=str(ds.crs), h=ds.height, w=ds.width,
                    transform=tuple(float(v) for v in ds.transform),
                    nodata=ds.nodata, compress=p.get("compress"),
                    tiled=bool(p.get("tiled", False)), dtype=ds.dtypes[0])


@pytest.mark.skipif(not SAMPLE.exists(), reason="competition data not restored")
def test_portal_exact_writer_matches_the_organiser_template_container(tmp_path):
    t = _template_profile()
    inside = np.zeros(grid.SHAPE, np.float32)
    fp = np.zeros(grid.SHAPE, bool)
    fp[100:400, 100:400] = True
    inside[150, 150] = 1.0
    out = tmp_path / "portal_exact.tif"
    info = grid.write_geotiff_portal_exact(out, inside, fp, SAMPLE)
    with rasterio.open(out) as ds:
        a = ds.read(1)
        p = ds.profile
        assert ds.count == 1 and ds.dtypes[0] == t["dtype"] == "float32"
        assert str(ds.crs) == t["crs"] == "EPSG:32611"
        assert (ds.height, ds.width) == (t["h"], t["w"]) == grid.SHAPE
        assert tuple(float(v) for v in ds.transform) == t["transform"]
        assert ds.nodata is not None and np.isnan(ds.nodata), "nodata must be declared as NaN"
        assert p.get("compress") == t["compress"], "compression must match the template"
        assert bool(p.get("tiled", False)) == t["tiled"], "strip/tile layout must match the template"
    fin = np.isfinite(a)
    assert not np.any(~fin & fp), "no non-finite pixel inside the footprint"
    assert np.all(np.isnan(a[~fp])), "everything outside the footprint is NaN"
    assert info["portal_exact"] is True
    assert info["positive_pixels"] == 1


@pytest.mark.skipif(not SAMPLE.exists(), reason="competition data not restored")
def test_portal_exact_writer_is_fail_closed(tmp_path):
    fp = np.zeros(grid.SHAPE, bool)
    fp[10:20, 10:20] = True
    good = np.zeros(grid.SHAPE, np.float32)

    over = good.copy(); over[11, 11] = 1.5
    with pytest.raises(ValueError, match="out of range"):
        grid.write_geotiff_portal_exact(tmp_path / "a.tif", over, fp, SAMPLE)

    neg = good.copy(); neg[11, 11] = -0.25
    with pytest.raises(ValueError, match="out of range"):
        grid.write_geotiff_portal_exact(tmp_path / "b.tif", neg, fp, SAMPLE)

    leak = good.copy(); leak[3000, 3000] = 1.0        # outside the footprint
    with pytest.raises(ValueError, match="outside the footprint"):
        grid.write_geotiff_portal_exact(tmp_path / "c.tif", leak, fp, SAMPLE)

    withnan = good.copy(); withnan[12, 12] = np.nan
    with pytest.raises(ValueError, match="NaN/inf"):
        grid.write_geotiff_portal_exact(tmp_path / "d.tif", withnan, fp, SAMPLE)

    with pytest.raises(TypeError, match="float32"):
        grid.write_geotiff_portal_exact(tmp_path / "e.tif", np.zeros(grid.SHAPE, np.float64), fp, SAMPLE)


def test_shipped_h77_artefact_passes_every_portal_rule():
    """Re-read the published file: this is the file the site tells the user to upload."""
    card = json.loads(BUILD.read_text())
    for rel in (Path("submission") / card["file"], Path("docs/downloads/h77-candidate.tif")):
        path = ROOT / rel
        assert path.exists(), f"missing published artefact {rel}"
        with rasterio.open(path) as ds:
            a = ds.read(1)
            assert ds.count == 1 and ds.dtypes[0] == "float32"
            assert str(ds.crs) == "EPSG:32611"
            assert (ds.height, ds.width) == grid.SHAPE
            assert tuple(float(v) for v in ds.transform)[:6] == tuple(grid.TRANSFORM)
            assert ds.nodata is not None and np.isnan(ds.nodata)
        fin = np.isfinite(a)
        assert np.unique(a[fin]).tolist() == [0.0, 1.0], "values must be exactly binary"
        assert int(((a < 0) | (a > 1))[fin].sum()) == 0
        assert int((a > 0).sum()) == card["emitted_px"] == 37654

    import hashlib
    a = (ROOT / "submission" / card["file"]).read_bytes()
    b = (ROOT / "docs/downloads/h77-candidate.tif").read_bytes()
    assert hashlib.sha256(a).hexdigest() == card["sha256"]
    assert hashlib.sha256(b).hexdigest() == card["sha256"], "the download copy must be the same bytes"
    assert card["submit_ok"] is False, "the round does not approve a weekly slot"
    assert card["download_ok"] is True
    assert len(card["note"]) <= 140 and len(card["submission_name"]) <= 140


def test_shipped_h77_artefact_is_lane_feasible_and_unique():
    card = json.loads(BUILD.read_text())
    assert card["uniqueness"]["canonical_pattern_unique"] is True
    assert card["uniqueness"]["equals_literal_prior_union"] is False
    assert card["uniqueness"]["novel_fraction"] > 0.9
    assert card["lane_dots"]["policy"] == "PASS"
    assert card["lane_dots"]["literal"] == "PASS"
    assert card["lane_dots"]["max_near_3px_fraction"] < 0.70
    assert card["lane_dots"]["max_spearman"] < 0.90
    assert card["footprint"]["min_dot_distance_to_catalogue_m"] >= 200.0


def test_every_new_h77_arm_is_reported_as_losing_to_the_control():
    """The negative result is the deliverable; it must not be quietly dropped or re-spun."""
    hold = json.loads((ROOT / "evidence" / "h77_holdout.json").read_text())
    scores = hold["pooled"]["scores"]
    control = scores["single_B"]["dti"]
    assert abs(control - 0.174571) < 1e-5, "the control must reproduce its committed value"
    new = [k for k in scores if k.startswith("h77_")]
    assert len(new) == 6
    for arm in new:
        assert scores[arm]["dti"] < control, f"{arm} must stay below the control"
    assert scores["h77_D_antithetic_margin"]["dti"] < scores["random"]["dti"]
