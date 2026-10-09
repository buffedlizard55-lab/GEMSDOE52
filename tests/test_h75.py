import hashlib, json, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SHA = "b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16"

def test_h75_download_matches_submission_and_card():
    a = (ROOT / "docs/downloads/h75-candidate.tif").read_bytes()
    b = (ROOT / "submission/gems52-h75-dva-variogram-anisotropy-B-37654px-20261009.tif").read_bytes()
    assert a == b and hashlib.sha256(a).hexdigest() == SHA
    card = json.loads((ROOT / "evidence/h75_run_card.json").read_text())
    assert card["raster_sha256"] == SHA and len(card["note"]) <= 140 and card["validator"]["PASS"]
    assert card["paired_B_DVA_minus_single_B"]["ci95"][0] > 0
    assert card["lane"]["dots_verdict"] == "DUPLICATE/STOP"   # the failure must stay visible

def test_h75_zip_single_geotiff():
    with zipfile.ZipFile(ROOT / "docs/downloads/h75-candidate.zip") as z:
        names = z.namelist()
        assert len(names) == 1 and names[0].endswith(".tif")
        assert hashlib.sha256(z.read(names[0])).hexdigest() == SHA

def test_h75_values_in_unit_interval():
    import numpy as np, rasterio
    with rasterio.open(ROOT / "docs/downloads/h75-candidate.tif") as d:
        v = d.read(1)
        assert d.count == 1 and str(d.crs) == "EPSG:32611" and v.shape == (3730, 3292)
    assert np.isfinite(v).all() and set(np.unique(v).tolist()) == {0.0, 1.0}
