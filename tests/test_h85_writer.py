"""H85: the zero-outside container option of the shared portal-exact writer.

Regression guard for IR-H85-004: the container must be finite and inside [0, 1] everywhere,
keep the organiser template's CRS/shape/transform, and pass the shared format gate.
Skipped when the restored competition template is absent (data/ is not in git).
"""
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_submission.tif"


@pytest.mark.skipif(not SAMPLE.exists(), reason="competition template not restored under data/")
def test_zero_outside_container_is_finite_and_in_range(tmp_path):
    import rasterio
    from gems52 import gates, grid

    with rasterio.open(SAMPLE) as s:
        smp = s.read(1)
    footprint = np.isfinite(smp) & (smp > -1e38)
    inside = np.zeros(grid.SHAPE, np.float32)
    rng = np.random.default_rng(0)
    idx = np.flatnonzero(footprint.ravel())
    inside.ravel()[rng.choice(idx, 500, replace=False)] = 1.0
    out = tmp_path / "zero_outside.tif"
    rec = grid.write_geotiff_portal_exact(out, inside, footprint, SAMPLE, outside="zero")
    assert rec["portal_exact"] is True
    with rasterio.open(out) as src:
        arr = src.read(1)
        assert src.nodata is None
        assert src.count == 1 and src.dtypes[0] == "float32"
        assert str(src.crs) == "EPSG:32611"
        assert (src.height, src.width) == grid.SHAPE
    assert np.isfinite(arr).all()
    assert arr.min() >= 0.0 and arr.max() <= 1.0
    assert int((arr > 0).sum()) == 500
    report = gates.format_report(out, SAMPLE)
    assert report["ok"], report.get("problems")


def test_default_writer_still_uses_nan_outside_signature():
    import inspect
    from gems52 import grid

    sig = inspect.signature(grid.write_geotiff_portal_exact)
    assert sig.parameters["outside"].default == "nan"
