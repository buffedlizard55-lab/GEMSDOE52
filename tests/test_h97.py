"""H97 invariants: orientation geometry, frozen arm rules, and receipt <-> file consistency."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
CARD_P = ROOT / "evidence/h97_run_card.json"


def _h97():
    pytest.importorskip("rasterio")
    import run_h97
    return run_h97


def test_preregistration_hash_frozen():
    reg = json.loads((ROOT / "registry/h97_preregistration.json").read_text())
    doc = (ROOT / reg["hypothesis_document"]).read_bytes()
    assert hashlib.sha256(doc).hexdigest() == reg["hypothesis_sha256"]
    assert reg["primary_arm"] == "H97_veto" and reg["budget"]["submission_slots_allowed"] == 0


def _orient_on(z, monkeypatch, h):
    """Run the shipped orientation code on a synthetic DEM by faking the raster read."""
    class DS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, b):
            return z if b == h.OR["band"] else np.full(z.shape, 1.0)
    monkeypatch.setattr(h.rasterio, "open", lambda *a, **k: DS())
    return h.orientation_fields(np.ones(z.shape, bool))


def test_gully_running_downslope_is_fall_line(monkeypatch):
    h = _h97()
    yy, xx = np.mgrid[0:80, 0:80].astype(float)
    # plane dipping toward +y (south) with a gully (valley) running along y at x = 40
    # (steep plane so the along-valley gradient is "defined"; probe 1 px off the thalweg, where the wall
    # gradient adds in quadrature and the cell clears the 25th-percentile gradient threshold)
    z = -2.0 * yy - 3.0 * np.exp(-((xx - 40) ** 2) / (2 * 3.0 ** 2))
    fl, dcard, defined, low, _ = _orient_on(z, monkeypatch, h)
    assert defined[40, 41]
    assert fl[40, 41] > 0.95                       # feature axis parallel to the gradient
    assert dcard[40, 41] < 1.0                     # valley runs N-S: cardinal


def test_scarp_across_slope_is_not_fall_line(monkeypatch):
    h = _h97()
    yy, xx = np.mgrid[0:80, 0:80].astype(float)
    # plane dipping toward +y with a step (scarp) whose crest runs along x (across slope) at y = 40
    z = -0.5 * yy - 4.0 / (1 + np.exp(-(yy - 40) / 1.5))
    fl, dcard, defined, low, _ = _orient_on(z, monkeypatch, h)
    assert fl[38, 40] < 0.10                       # crest perpendicular to the gradient
    assert dcard[38, 40] < 1.0                     # crest runs E-W: cardinal


def test_arm_rules_demote_only_flagged_b_only_cells():
    h = _h97()
    rB = np.array([0.99, 0.99, 0.99, 0.50])
    rA = np.array([0.10, 0.90, 0.10, 0.10])
    fl = np.array([0.95, 0.95, 0.10, 0.95])
    dcard = np.full(4, 30.0)
    low = np.ones(4, bool)
    out, flags, erosion, road = h.arm_fields(rA, rB, rB, fl, dcard, low)
    assert flags["H97_veto"].tolist() == [True, False, False, False]   # A-supported and clean cells untouched
    assert out["H97_veto"][0] < -0.9 and out["H97_veto"][1] == pytest.approx(0.99)
    assert out["H97_veto"][3] == pytest.approx(0.50)                   # not B-confident -> not B-only


@pytest.mark.skipif(not CARD_P.exists(), reason="run card not generated")
def test_card_matches_shipped_bytes_and_verdict():
    card = json.loads(CARD_P.read_text())
    tif = ROOT / card["raster"]["file"]
    dl = ROOT / "docs/downloads/h97-candidate.tif"
    for p in (tif, dl):
        assert hashlib.sha256(p.read_bytes()).hexdigest() == card["raster"]["sha256"]
    assert card["validator"]["PASS"] and card["validator"]["nan"] == 0
    assert card["validator"]["values"] == [0.0, 1.0]
    assert len(card["submission"]["note"]) <= 140 and len(card["submission"]["name"]) <= 140
    assert card["verdict"] == ("promote" if all(card["gates"].values()) else "negative")
    assert card["ok_to_submit"] is all(card["gates"].values())
    assert card["submission_slots_used"] == 0


@pytest.mark.skipif(not CARD_P.exists(), reason="run card not generated")
def test_readme_and_site_lead_with_h97_verdict():
    card = json.loads(CARD_P.read_text())
    head = (ROOT / "README.md").read_text()
    assert head.startswith("<!--H97-README-->")
    block = head[: head.index("<!--/H97-README-->")]
    assert "OK TO DOWNLOAD: YES" in block and "OK TO SUBMIT: NO" in block or card["ok_to_submit"]
    assert card["raster"]["sha256"] in block and "docs/downloads/h97-candidate.tif" in block
    idx = (ROOT / "docs/index.html").read_text()
    assert idx.index("<!--H97-CARD-->") < idx.index("<!--H95-CARD-->")
    for page in ("docs/h97.html", "docs/h97-executive-summary.html"):
        t = (ROOT / page).read_text()
        assert "downloads/h97-candidate.tif" in t and "OK TO SUBMIT" in t
