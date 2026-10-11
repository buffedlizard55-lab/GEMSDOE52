import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = json.loads((ROOT / "evidence/h95_run_card.json").read_text())
SHA = CARD["raster"]["sha256"]


def test_h95_download_matches_submission_and_card():
    a = (ROOT / "docs/downloads/h95-candidate.tif").read_bytes()
    b = (ROOT / CARD["raster"]["path"]).read_bytes()
    assert a == b and hashlib.sha256(a).hexdigest() == SHA
    assert CARD["submission"]["note_chars"] == len(CARD["submission"]["note"]) <= 140


def test_h95_zip_single_geotiff():
    with zipfile.ZipFile(ROOT / "docs/downloads/h95-candidate.zip") as z:
        names = z.namelist()
        assert len(names) == 1 and names[0].endswith(".tif")
        assert hashlib.sha256(z.read(names[0])).hexdigest() == SHA


def test_h95_values_in_unit_interval_and_grid():
    import numpy as np
    import rasterio
    with rasterio.open(ROOT / "docs/downloads/h95-candidate.tif") as d:
        v = d.read(1)
        assert d.count == 1 and str(d.crs) == "EPSG:32611" and v.shape == (3730, 3292) and d.dtypes[0] == "float32"
    assert np.isfinite(v).all() and set(np.unique(v).tolist()) == {0.0, 1.0}


def test_h95_verdict_follows_frozen_rule():
    reg = json.loads((ROOT / "registry/h95_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    gates = CARD["gates"]
    assert CARD["verdict"]["submit_ok"] == all(g["pass"] for g in gates.values())
    e2 = json.loads((ROOT / "evidence/h95_e2_lane_holdout.json").read_text())
    p = e2["promotion"]
    expect = p["primary_dti"] > reg["promotion"]["holdout_bar"] and p["paired_vs_single_B"]["ci95"][0] > 0
    assert gates["holdout_promotion"]["pass"] == expect == p["promote"]
    assert e2["control_reproduction"]["ok"]


def test_readme_carries_current_verdicts_brief_and_the_h95_archive():
    """H95 stopped being the incumbent when H97 shipped; its block stays in the README as an archive
    (the same convention as the H89/H87/H83/H82 blocks below it), the current block keeps the
    download/submit verdicts explicit, and the standing brief stays verbatim."""
    text = (ROOT / "README.md").read_text()
    assert text.startswith("<!--H97-README-->"), "the newest block must sit at the top of the README"
    current = text[: text.index("<!--/H97-README-->")]
    assert "OK TO DOWNLOAD: YES" in current and "OK TO SUBMIT:" in current
    assert "docs/downloads/h97-candidate.tif" in current
    h95 = text[text.index("<!--H95-README-->"): text.index("<!--/H95-README-->")]
    assert "OK TO DOWNLOAD: YES" in h95 and "OK TO SUBMIT:" in h95
    assert "docs/downloads/h95-candidate.tif" in h95 and SHA in h95
    brief = (ROOT / "knowledge/94_current_user_brief_2026-10-10_H95.md").read_text()
    assert brief.strip()[:200] in text
