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


def test_h95_readme_states_both_verdicts_and_brief():
    # the top-of-README marker belongs to whichever round is newest (asserted in test_h99.py)
    text = (ROOT / "README.md").read_text()
    assert "<!--H95-README-->" in text and "<!--/H95-README-->" in text
    head = text[text.index("<!--H95-README-->"): text.index("<!--/H95-README-->")]
    assert "OK TO DOWNLOAD: YES" in head and "OK TO SUBMIT:" in head
    assert "docs/downloads/h95-candidate.tif" in head and SHA in head
    brief = (ROOT / "knowledge/94_current_user_brief_2026-10-10_H95.md").read_text()
    assert brief.strip()[:200] in head
