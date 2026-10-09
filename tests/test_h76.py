"""H76 regression tests.

Most of these exist because something broke during the round and the fix has to stay fixed:

* ``save_verified`` — the first channel build produced 8 files of 79 with one 4 KiB page of zeros after
  the .npy header (IR-H76-002). Persistence must re-read what it wrote.
* ``Bank.vsa`` — band names contain underscores (``det_elev``, ``iso_grav_anom_hg``), so a plain
  ``split("_")`` raised ``ValueError`` on every VSA channel.
* ``arm_channels("single_B")`` — the control arm must carry the View B store columns. Written once with
  an empty feature list, it could not reproduce the committed 0.174517 control at all.
* ``az.axial_resultant`` returns ``(mean, R, n)`` — the third value is a weighted pixel count, not a
  circular standard deviation. It was passed through ``np.degrees()`` once and published as an SD.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
REG = ROOT / "registry"
FEAT = ROOT / "work/h76/features"
sys.path.insert(0, str(ROOT / "scripts"))

CARD = EVID / "h76_run_card.json"


def _card():
    if not CARD.exists():
        pytest.skip("H76 run card not built yet (run scripts/run_h76.py card)")
    return json.loads(CARD.read_text())


# ---------------------------------------------------------------------------------- preregistration
def test_preregistration_pin_matches_the_hypothesis_document():
    reg = json.loads((REG / "h76_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert doc.exists(), reg["hypothesis_document"]
    got = hashlib.sha256(doc.read_bytes()).hexdigest()
    assert got == reg["hypothesis_sha256"], (
        "the frozen hypothesis document changed after pinning; re-pin before any further claim "
        "(IR-H75-002: appending an amendment silently changes the hash)")


def test_preregistration_declares_the_scored_registry_a_loosening():
    reg = json.loads((REG / "h76_preregistration.json").read_text())
    blob = json.dumps(reg).lower()
    assert "duplicate" in blob and "stop" in blob, "the literal DUPLICATE/STOP rule must stay in the pin"


def test_scored_registry_is_sha_verified_and_never_organizer_confirmed():
    d = json.loads((REG / "h76_scored_registry.json").read_text())
    assert d["all_sha_match"] is True
    assert d["n_files"] == len(d["files"]) >= 10
    assert "LOOSENING" in d["declared_effect"] and "never waives a literal DUPLICATE/STOP" in d["declared_effect"]
    for key, e in d["files"].items():
        assert e["exists"] and e["sha_matches_pin"], key
        assert e["score_class"].startswith("OWNER-REPORTED"), key
        assert "NOT ORGANIZER-CONFIRMED" in e["score_class"], key
        assert isinstance(e["owner_reported_public_board_score"], float), key
    scores = [e["owner_reported_public_board_score"] for e in d["files"].values()]
    assert max(scores) == pytest.approx(0.2778), "the owner's best reported file must stay in the registry"


# ---------------------------------------------------------------------------------- persistence
def test_save_verified_rewrites_a_torn_write(tmp_path, monkeypatch):
    import run_h76 as R

    real_save = np.save
    state = {"calls": 0}

    def torn_save(path, arr, *a, **k):
        """Write correctly, then zero one page after the 128-byte header — exactly IR-H76-002."""
        real_save(path, arr, *a, **k)
        state["calls"] += 1
        if state["calls"] == 1:
            with open(path, "r+b") as fh:
                fh.seek(128)
                fh.write(b"\x00" * 3968)

    monkeypatch.setattr(R.np, "save", torn_save)
    want = np.arange(5000, dtype=np.float32)
    sha, attempts = R.save_verified(tmp_path / "chan.npy", want, pause=0.0)
    assert attempts == 2, "a torn first write must be detected and rewritten"
    assert np.array_equal(np.load(tmp_path / "chan.npy"), want)
    assert sha == hashlib.sha256((tmp_path / "chan.npy").read_bytes()).hexdigest()


def test_save_verified_does_not_call_itself():
    """The regex that routed every np.save through save_verified also rewrote the call inside
    save_verified, producing 993-deep recursion. Guard the source, not just the behaviour."""
    src = (ROOT / "scripts/run_h76.py").read_text()
    body = src.split("def save_verified(", 1)[1].split("\ndef ", 1)[0]
    assert "save_verified(path" not in body, "save_verified must call plain np.save"
    assert "np.save(path, want)" in body


def test_save_verified_accepts_nan_and_bool_columns(tmp_path):
    import run_h76 as R
    a = np.array([0.0, np.nan, 1.0, np.nan], np.float32)
    sha, att = R.save_verified(tmp_path / "nan.npy", a)
    assert att == 1 and np.array_equal(np.load(tmp_path / "nan.npy"), a, equal_nan=True)
    b = np.array([True, False, True])
    sha2, att2 = R.save_verified(tmp_path / "deg.npy", b)
    assert att2 == 1 and np.load(tmp_path / "deg.npy").dtype == np.bool_


# ---------------------------------------------------------------------------------- channel bank
@pytest.mark.skipif(not (FEAT / "manifest.json").exists(), reason="channel bank not built on this machine")
def test_every_channel_file_matches_its_manifest_digest():
    man = json.loads((FEAT / "manifest.json").read_text())
    bad = [k for k, v in man["sha256"].items()
           if hashlib.sha256((FEAT / f"{k}.npy").read_bytes()).hexdigest() != v]
    assert not bad, f"channel byte-integrity failure: {bad}"


@pytest.mark.skipif(not (FEAT / "manifest.json").exists(), reason="channel bank not built on this machine")
def test_bank_vsa_parses_band_names_that_contain_underscores():
    import run_h76 as R
    bank = R.Bank(FEAT)
    rows = np.arange(0, bank.manifest["n_eligible"], 9973)
    for nm in R.VSA:
        v = bank.gather(rows, [nm], fold=0)[:, 0]
        assert v.shape == (len(rows),)
        assert np.isfinite(v).all()
        assert v.min() >= -1.0 - 1e-6 and v.max() <= 1.0 + 1e-6, nm
    # the frozen convention: cos2 is evaluated everywhere and is 0 only where the tensor is degenerate
    reg = bank.gather(rows, ["VSA_det_elev_cos2reg_l2"], fold=0)[:, 0]
    assert (reg != 0).all(), "a regional-strike channel has no degenerate-tensor escape hatch"


@pytest.mark.skipif(not (FEAT / "manifest.json").exists(), reason="channel bank not built on this machine")
def test_channel_inventory_matches_the_frozen_design():
    import run_h76 as R
    assert len(R.DVA2) == 50 and len(R.VSA) == 10 and len(R.H75C) == 12
    assert len(set(R.DVA2) & set(R.H75C)) == 0
    man = json.loads((FEAT / "manifest.json").read_text())
    assert set(R.DVA2 + R.VSA) == set(man["learner_channels"]["dva2"] + man["learner_channels"]["vsa"])
    assert "XVSA_visible_tensor_mag" not in json.dumps(man), (
        "amendment 67a demoted it to a diagnostic before any fit; it must never reappear as a learner channel")


def test_arm_channels_single_B_carries_the_view_B_store_columns():
    """The control arm must be able to reproduce 0.174517; an empty feature matrix cannot."""
    import run_h76 as R
    R.base_vb_cache.update(vb=["X_dem_slope", "X_rad_tc"], va=["X_mag_TMI_up150"])
    assert R.arm_channels("single_B") == (["X_dem_slope", "X_rad_tc"], [])
    assert R.arm_channels("single_A") == (["X_mag_TMI_up150"], [])
    assert R.arm_channels(R.PRIMARY)[1] == R.DVA2 + R.VSA
    assert R.arm_channels("B_DVA")[1] == R.H75C


def test_axial_resultant_third_value_is_a_count_not_a_standard_deviation():
    from gems52 import azimuth as az
    a = np.radians(np.array([10.0, 12.0, 8.0, 11.0]))
    mean, R_, n = az.axial_resultant(a)
    assert n == pytest.approx(4.0), "the third return is the weighted pixel count"
    assert 0.0 <= R_ <= 1.0 and np.degrees(mean) < 180.0
    # Mardia-Jupp axial circular SD, the quantity the strike receipt must carry
    sd = np.degrees(np.sqrt(-2.0 * np.log(R_)))
    assert 0.0 < sd < 90.0
    dispersed = np.radians(np.array([0.0, 45.0, 90.0, 135.0]))
    _, R2, _ = az.axial_resultant(dispersed)
    assert R2 < 0.05, "a uniform axial sample must have a near-zero resultant, hence an undefined SD"


# ---------------------------------------------------------------------------------- receipts
def test_run_card_has_every_field_the_brief_demands():
    c = _card()
    for k in ("hypothesis", "mechanism", "mimic", "holdout", "lane", "raster", "validator",
              "verdict", "verdict_promote", "registry_correlation_overlap", "not_the_union",
              "placement", "canary", "reasoning_csv"):
        assert k in c, f"run card is missing the brief-required field {k!r}"
    assert c["hypothesis"] and c["mechanism"] and c["mimic"]
    assert c["raster"]["sha256"] and len(c["raster"]["sha256"]) == 64
    assert len(c["raster"]["note"]) <= 140 and c["raster"]["note_chars"] == len(c["raster"]["note"])
    assert len(c["raster"]["name"]) <= 140
    assert c["validator"]["PASS"] is True
    assert "registry_correlation_overlap" in c and "not_the_union" in c
    ho = c["holdout"]
    assert ho["label"] == "HOLDOUT-DTI" and ho["evaluator"] and ho["withheld_positive_pixels"] > 0
    for arm, s in ho["scores"].items():
        assert s["label"] == "HOLDOUT-DTI", arm
        assert len(s["ci95"]) == 2 and s["ci95"][0] <= s["dti"] <= s["ci95"][1], arm
    assert "never_a_board_forecast" in ho


def test_run_card_verdict_follows_the_frozen_promotion_rule():
    c = _card()
    r = c["verdict_reasons"]
    expected = bool(r["holdout_primary_beats_single_B"] and r["controls_reproduce"]
                    and r["lane_literal_full_census_not_duplicate"] and r["format_validator_pass"]
                    and r["not_the_union_pass"])
    assert c["verdict_promote"] is expected, (
        "promotion must be the frozen conjunction, never a post-hoc pick; attribution arms are excluded")
    if r["holdout_primary_beats_single_B"]:
        assert r["paired_ci_lower_bound"] > 0, "the frozen rule needs a paired CI lower bound above zero"
    else:
        assert r["paired_ci_lower_bound"] <= 0 or not r["controls_reproduce"] \
            or not r["lane_literal_full_census_not_duplicate"]


def test_run_card_labels_every_score_class_it_quotes():
    c = _card()
    import re
    blob = json.dumps(c)
    # Every mention of ORGANIZER-CONFIRMED must be a negation ("NOT ORGANIZER-CONFIRMED", "never
    # ORGANIZER-CONFIRMED"). This runner has no DrivenData credentials, so it cannot confirm anything
    # with the organiser, and an unqualified claim would be a hallucination.
    bare = [m for m in re.finditer(r"ORGANIZER-CONFIRMED", blob)]
    assert bare, "the card should state the score classes explicitly"
    for m in bare:
        ctx = blob[max(0, m.start() - 40):m.start()].lower()
        assert "not " in ctx or "never " in ctx, (
            f"unqualified ORGANIZER-CONFIRMED claim: ...{blob[max(0, m.start()-60):m.end()+20]}...")
    assert "OWNER-REPORTED" in blob, "registry scores must stay owner-reported"
    assert "HOLDOUT-DTI" in blob
    reg = c["registry_correlation_overlap"]["scored_only_registry"]
    assert reg["score_label"] == "OWNER-REPORTED (never ORGANIZER-CONFIRMED)"


def test_download_matches_the_submission_bytes_and_the_card():
    c = _card()
    served = ROOT / "docs/downloads/h76-candidate.tif"
    if not served.exists():
        pytest.skip("site not published yet (run scripts/publish_h76_site.py)")
    b = served.read_bytes()
    assert hashlib.sha256(b).hexdigest() == c["raster"]["sha256"]
    assert b == (ROOT / c["raster"]["file"]).read_bytes()
    with zipfile.ZipFile(ROOT / "docs/downloads/h76-candidate.zip") as z:
        assert len(z.namelist()) == 1 and z.namelist()[0].endswith(".tif")
        assert hashlib.sha256(z.read(z.namelist()[0])).hexdigest() == c["raster"]["sha256"]


def test_served_raster_is_single_band_float32_in_the_unit_interval():
    c = _card()
    served = ROOT / "docs/downloads/h76-candidate.tif"
    if not served.exists():
        pytest.skip("site not published yet")
    import rasterio
    with rasterio.open(served) as d, rasterio.open(ROOT / "data/sample_submission.tif") as s:
        v = d.read(1)
        assert d.count == 1 and d.dtypes[0] == "float32"
        assert d.crs == s.crs and str(d.crs) == "EPSG:32611"
        assert d.shape == s.shape and d.transform == s.transform and d.bounds == s.bounds
    assert np.isfinite(v).all(), "the organiser rejects NaN inside the footprint only by range; be strict"
    assert float(v.min()) >= 0.0 and float(v.max()) <= 1.0
    assert int((v == 1).sum()) == c["raster"]["emitted_cells"]


# ---------------------------------------------------------------------------------- browser validator
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_validator_parses():
    js = ROOT / "docs/assets/tifcheck.js"
    r = subprocess.run([NODE, "--check", str(js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_validator_reproduces_rasterio_pixel_counts(tmp_path):
    """The JS decoder is pinned against two files whose statistics were measured with rasterio.

    h75-candidate.tif: tiled, DEFLATE, horizontal-differencing predictor -> 12,241,506 zeros and
    37,654 ones. sample_submission.tif: 1-row strips, LZW -> 5,167,373 finite pixels of which
    60,988 are 1.0, and 7,111,787 NaN. Byte-wise predictor differencing or the wrong LZW width rule
    reproduces neither, which is how both bugs were found.
    """
    harness = tmp_path / "h.cjs"
    harness.write_text("""
const fs=require('fs');
const api=require(process.argv[2]);
(async()=>{
  const out={};
  for(const f of process.argv.slice(3)){
    const buf=fs.readFileSync(f);
    const ab=buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength);
    const r=await api.checkFile({name:f.split('/').pop(),size:buf.length,arrayBuffer:async()=>ab});
    out[f.split('/').pop()]={zero:r.stats.zero,one:r.stats.one,nan:r.stats.nan,finite:r.stats.finite,
                             ok:r.ok,passed:r.passed,total:r.total};
  }
  console.log(JSON.stringify(out));
})();
""")
    args = [NODE, str(harness), str(ROOT / "docs/assets/tifcheck.js"),
            str(ROOT / "docs/downloads/h75-candidate.tif")]
    sample = ROOT / "data/sample_submission.tif"
    if sample.exists():
        args.append(str(sample))
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    h = got["h75-candidate.tif"]
    assert (h["zero"], h["one"], h["nan"]) == (12241506, 37654, 0), h
    assert h["ok"] is True and h["passed"] == h["total"]
    if "sample_submission.tif" in got:
        s = got["sample_submission.tif"]
        assert (s["nan"], s["finite"], s["one"]) == (7111787, 5167373, 60988), s


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_validator_rejects_a_out_of_range_file(tmp_path):
    """The user's actual rejection was 'Predicted values must be in range [0, 1]'; the checker must
    reproduce that verdict on a file that would trigger it, and stay silent on a good one."""
    import rasterio
    src = ROOT / "docs/downloads/h75-candidate.tif"
    if not src.exists():
        pytest.skip("no candidate raster to corrupt")
    with rasterio.open(src) as d:
        prof = d.profile.copy()
        a = d.read(1)
    bad = tmp_path / "bad_range.tif"
    prof.update(count=1, dtype="float32")
    with rasterio.open(bad, "w", **prof) as o:
        o.write((a * 2.0).astype("float32"), 1)
    harness = tmp_path / "h2.cjs"
    harness.write_text("""
const fs=require('fs');const api=require(process.argv[2]);
(async()=>{const f=process.argv[3];const buf=fs.readFileSync(f);
 const ab=buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength);
 const r=await api.checkFile({name:'x.tif',size:buf.length,arrayBuffer:async()=>ab});
 const rng=r.checks.find(c=>c.id==='range');
 console.log(JSON.stringify({ok:r.ok,range_pass:rng.pass}));})();
""")
    r = subprocess.run([NODE, str(harness), str(ROOT / "docs/assets/tifcheck.js"), str(bad)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got["ok"] is False and got["range_pass"] is False


# ---------------------------------------------------------------------------------- site
def test_site_pages_exist_and_link_only_to_real_files():
    for rel in ("docs/index.html", "docs/h76.html", "docs/h76-executive-summary.html",
                "docs/h76-hypotheses.html", "docs/h76-sources.html", "docs/validator.html",
                "index.html"):
        p = ROOT / rel
        if not p.exists():
            pytest.skip(f"{rel} not published yet")
        text = p.read_text()
        base = p.parent
        import re
        for m in re.finditer(r'(?:href|src)="([^"#:]+)"', text):
            t = m.group(1)
            if t.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            assert (base / t).resolve().exists(), f"{rel} links to a missing file: {t}"


def test_validator_page_states_the_privacy_position_and_the_rule_source():
    p = ROOT / "docs/validator.html"
    if not p.exists():
        pytest.skip("validator page not published yet")
    t = p.read_text()
    assert "in your browser" in t and "Nothing is uploaded" in t
    assert "competitions/306/competition-doe-gems/page/967" in t
    assert "Predicted values must be in range [0, 1]" in t
    assert "assets/tifcheck.js" in t


def test_index_puts_the_verdict_before_the_download_button():
    p = ROOT / "docs/index.html"
    if not p.exists():
        pytest.skip("site not published yet")
    t = p.read_text()
    button = 'href="downloads/h76-candidate.tif"'
    if "OK to download?" not in t or button not in t:
        pytest.skip("docs/index.html is still a previous round's page; run scripts/publish_h76_site.py")
    assert t.index("OK to download?") < t.index(button), (
        "the brief requires it to be obvious whether the file may be downloaded and submitted; "
        "the verdict must precede the button")
    c = _card()
    assert ("OK TO SUBMIT" in t) or ("research artefact only" in t.lower()) or c["submit_ok"]
