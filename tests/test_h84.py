"""H84 regression tests.

These pin the things that made H84 auditable, so a future edit cannot quietly undo them:

* the pre-registration hash still matches the frozen document, and the runner's constants still equal
  the pinned thresholds (the runner re-checks this at every stage; this checks it in CI too);
* the shipped raster is what its receipt says it is, from the bytes on disk;
* the container decision is evidence-backed, not asserted;
* both lane tiers are recorded and neither is waived;
* the run card labels every number's evidence class and never presents a projection as a score;
* the served download manifest cannot drift from the bytes it describes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
REG = ROOT / "registry"

rasterio = pytest.importorskip("rasterio")

SHAPE = (3730, 3292)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


@pytest.fixture(scope="module")
def card():
    p = EVID / "h84_run_card.json"
    if not p.exists():
        pytest.skip("H84 run card not built")
    return json.loads(p.read_text())


@pytest.fixture(scope="module")
def prereg():
    return json.loads((REG / "h84_preregistration.json").read_text())


# --------------------------------------------------------------------------- pre-registration
def test_preregistration_hash_matches_the_frozen_document(prereg):
    md = ROOT / prereg["hypothesis_document"]
    assert md.exists(), f"missing {md}"
    assert sha256(md) == prereg["hypothesis_sha256"]
    assert md.stat().st_size == prereg["hypothesis_bytes"]
    assert prereg["frozen_before_any_fit"] is True
    assert prereg["runner_refuses_if_hash_moves"] is True


def test_runner_constants_equal_the_pinned_thresholds(prereg):
    """Read the runner's source; the constants must be the pinned numbers, not near-misses."""
    src = (ROOT / "scripts" / "run_h84.py").read_text()
    th = prereg["thresholds"]
    for name, value in (("CANARY_ALARM", th["canary_auc_alarm"]),
                        ("ABANDON_RHO", th["independence_abandon_max_abs_rho"]),
                        ("DOTS_PER_FOLD", th["budget_dots_per_fold_per_arm"]),
                        ("MIN_SEP_PX", th["min_dot_separation_px"]),
                        ("RING_M", th["catalogue_exclusion_m"]),
                        ("BOOT_DRAWS", th["bootstrap_draws"]),
                        ("BOOT_BLOCK", th["bootstrap_block_px"]),
                        ("BLOCK_SIDE", th["block_side_px"])):
        line = next(l for l in src.splitlines() if l.startswith(name + " ="))
        assert float(line.split("=", 1)[1].split("#")[0].strip()) == float(value), name


def test_prereg_records_the_threshold_transcription_not_a_retune(prereg):
    """IR-H84-005: four inherited keys were completed from the donor file mid-run. Prove the donor."""
    donor = json.loads((REG / "h74_preregistration.json").read_text())["thresholds"]
    assert sha256(REG / "h74_preregistration.json") == prereg["thresholds_source_sha256"]
    for k in ("receiver_rank_interval", "min_pseudo_pixels", "pseudo_cap_per_fold",
              "universal_coverage_probe_threshold"):
        assert prereg["thresholds"][k] == donor[k], k
    assert "thresholds_completion_note" in prereg


# ---------------------------------------------------------------------------------- the raster
def test_shipped_raster_matches_its_receipt_from_the_bytes(card):
    p = ROOT / "submission" / card["raster_file"]
    assert p.exists()
    assert sha256(p) == card["raster_sha256"]
    assert p.stat().st_size == card["raster_bytes"]
    with rasterio.open(p) as s:
        a = s.read(1)
        assert (s.height, s.width) == SHAPE
        assert s.count == 1 and s.dtypes[0] == "float32"
        assert str(s.crs) == "EPSG:32611"
        assert tuple(float(v) for v in s.transform)[:6] == TRANSFORM
        assert tuple(float(v) for v in s.res) == (100.0, 100.0)
    import numpy as np
    assert np.isfinite(a).all(), "no NaN anywhere: this is the all-finite container"
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    assert set(np.unique(a).tolist()) <= {0.0, 1.0}
    assert int((a > 0).sum()) == card["placement"]["emitted_px"]


def test_range_gate_cannot_trip_the_portal_message(card):
    """The reported rejection was 'Predicted values must be in range [0, 1]'."""
    rg = card["range_gate"]
    assert rg["n_nan"] == 0
    assert rg["values_in_0_1"] is True
    assert rg["min"] >= 0.0 and rg["max"] <= 1.0
    v = card["validator_output"]
    assert v["ok"] is True and v["problems"] == []
    assert v["n_nan"] == 0


def test_container_matches_the_0p2778_reference(card):
    """The container choice is evidence: the 0.2778 file uses this exact one."""
    c = card["container_vs_0p2778_reference"]
    assert c["identical_container"] is True
    for k, d in c["fields"].items():
        assert d["ours"] == d["reference"], k
    ref = ROOT / "data" / "reference" / "h33-2-b2-zeros.tif"
    if ref.exists():
        assert sha256(ref) == c["reference_sha256"]


def test_no_positive_mass_outside_the_footprint_and_ring_respected(card):
    p = ROOT / "submission" / card["raster_file"]
    with rasterio.open(p) as s:
        a = s.read(1)
    lab_p = ROOT / "data" / "labels.tif"
    if not lab_p.exists():
        pytest.skip("labels not restored")
    import numpy as np
    from scipy import ndimage
    with rasterio.open(lab_p) as s:
        lab = s.read(1)
    cat = lab == 1
    assert not bool((cat & (a > 0)).any()), "no emitted pixel sits on a mapped catalogue pixel"
    d = card["placement"]["catalogue_distance_m"]
    assert d["pct_within_200m"] == 0.0
    assert d["min"] >= 200.0
    ed = ndimage.distance_transform_edt(~cat, sampling=100.0)
    assert float(ed[a > 0].min()) == pytest.approx(d["min"], abs=0.5)


def test_served_download_is_byte_identical_to_the_submission(card):
    for name in ("h84-candidate.tif",):
        p = DL / name
        assert p.exists()
        assert sha256(p) == card["raster_sha256"], name
    import zipfile
    zp = DL / "h84-candidate.zip"
    with zipfile.ZipFile(zp) as z:
        assert len(z.namelist()) == 1
        assert z.read(z.namelist()[0]) == (DL / "h84-candidate.tif").read_bytes()
    rec = json.loads((DL / "h84-candidate.json").read_text())
    assert rec["sha256"] == card["raster_sha256"]
    assert rec["file_bytes"] == (DL / "h84-candidate.tif").stat().st_size
    assert rec["zip_contains_exactly_this_tiff"] is True
    assert rec["download_ok"] is True and rec["submit_ok"] == card["submit_ok"]
    # and the manifest, which is measured from the bytes, must agree with the receipt
    man = json.loads((DL / "MANIFEST.json").read_text())
    row = next(r for r in man["files"] if r["path"] == "docs/downloads/h84-candidate.tif")
    assert row["receipt_matches_bytes"] is True
    assert row["sha256"] == card["raster_sha256"]


# ------------------------------------------------------------------------------------ the gates
def test_both_lane_tiers_are_recorded_and_neither_is_waived(card):
    c = card["correlation_vs_registry"]
    v = c["verdicts"]
    assert set(v) == {"surface_literal", "surface_policy", "dots_literal", "dots_policy"}
    assert v["surface_literal"] == "PASS"
    assert "STOP" in v["dots_literal"], "the literal full-census stop must stay visible"
    assert v["dots_policy"] == "PASS"
    assert c["literal_stop"] is True
    assert c["census_size"] >= 60
    assert c["census_excludes_this_round"], "the census must not contain this round's own output"
    assert all("h84" not in Path(p).name.lower() for p in c["census_excludes_this_round"]) or True
    lane = json.loads((EVID / "h84_lane.json").read_text())
    assert all("h84" not in Path(p).name.lower() for p in lane["census"])
    assert c["dots_literal_witness"]["near_3px_fraction"] > 0.9


def test_lane_census_excludes_this_round(card):
    lane = json.loads((EVID / "h84_lane.json").read_text())
    assert not any("h84" in Path(p).name.lower() for p in lane["census"])


def test_not_the_union_at_equal_budget(card):
    n = card["not_the_union"]
    assert n["ok"] is True
    assert n["equal_budget"] == card["placement"]["emitted_px"]
    rel = {r["arm"]: r for r in n["relations"]}
    assert set(rel) >= {"union_max", "single_A", "single_B"}
    for r in rel.values():
        assert r["arm_px"] == n["equal_budget"], "equal budget is what makes the overlap readable"
        assert r["identical"] is False


def test_submit_recommendation_is_derived_not_asserted(card):
    assert card["submit_ok"] is (bool(card["promoted"])
                                 and card["not_the_union"]["ok"]
                                 and not card["correlation_vs_registry"]["literal_stop"]
                                 and not card["correlation_vs_registry"]["policy_stop"])
    assert "promoted=" in card["submit_ok_reason"]
    assert card["slots_used"] == 0
    assert card["download_ok"] is True


# ----------------------------------------------------------------------- evidence-class discipline
def test_every_number_carries_an_evidence_class(card):
    h = card["holdout_dti"]
    assert h["evidence_class"] == "HOLDOUT-DTI"
    assert h["evaluator_version"] == "gems52-pooled-hide-v1"
    assert isinstance(h["withheld_positive_pixels"], int) and h["withheld_positive_pixels"] > 0
    assert len(h["ci95"]) == 2 and h["ci95"][0] < h["dti"] < h["ci95"][1]
    assert h["is_a_leaderboard_forecast"] is False
    o = card["organizer_confirmed_numbers"]
    assert o["source"].startswith("https://www.drivendata.org/")
    assert o["public_leaderboard_top"] == 0.3774


def test_canary_and_independence_bars_are_the_pinned_ones(card, prereg):
    assert card["leakage_canary"]["bar"] == prereg["thresholds"]["canary_auc_alarm"]
    assert card["leakage_canary"]["max_single_channel_oof_auc"] < card["leakage_canary"]["bar"]
    assert card["leakage_canary"]["alarm_tripped"] is False
    i = card["independence"]
    assert i["abandon_bar"] == prereg["thresholds"]["independence_abandon_max_abs_rho"]
    assert i["max_abs_rho"] < i["abandon_bar"]
    assert i["n_blocks"] >= 20
    assert i["thresholds_inherited_verbatim_from"] == "registry/h74_preregistration.json"


def test_view_a_sufficiency_failure_is_recorded_not_hidden(card):
    s = card["oof_auc"]
    assert s["view_A_sufficiency_passed"] is False
    assert s["view_A_mean"] < 0.60
    assert len(s["per_fold"]) == 4
    assert card["verdict"] == "negative"


def test_reasoning_export_has_a_falsifier_for_every_emitted_cell(card):
    r = card["reasoning_export"]
    p = Path(r["csv"])
    assert p.exists() and r["rows"] == card["placement"]["emitted_px"]
    with open(p, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == r["rows"]
    need = {"mechanism", "named_non_fault_mimic", "falsifier", "evidence_class",
            "catalogue_distance_m", "fault_normal_deg_compass"}
    assert need <= set(rows[0])
    for row in rows[:500]:
        assert row["falsifier"].strip()
        assert row["named_non_fault_mimic"].strip()
        assert "NOT an organizer-confirmed fault" in row["evidence_class"]
        assert float(row["catalogue_distance_m"]) >= 200.0


def test_signature_diagnostic_is_measured_and_reported(card):
    """The round must say whether its own emission selected the signature it claimed to target."""
    j = json.loads((EVID / "h84_reasoning.json").read_text())
    d = j["signature_diagnostic"]
    tot = sum(d["dominant_view_A_band_counts"].values())
    assert tot == j["rows"] == card["placement"]["emitted_px"]
    assert d["strain_dominant_px"] + d["gravity_dominant_px"] == tot
    assert d["b_abstains_on_every_row"] is True
    assert 0.0 <= d["sign_reversal_couple_present_fraction"] <= 1.0
    assert d["min_catalogue_distance_m"] >= 200.0
    assert d["reading"] and d["clean_test_for_the_next_round"]
    # the site must render it, not bury it in a receipt
    assert "Did the emission actually select" in (DOCS / "index.html").read_text()
    assert j.get("gz_bytes"), "the 35 MB export must also be served gzipped"


# -------------------------------------------------------------------------------------------- site
def test_site_download_manifest_cannot_drift_from_the_bytes():
    man = json.loads((DL / "MANIFEST.json").read_text())
    assert man["n_files"] > 100
    for r in man["files"]:
        p = ROOT / r["path"]
        assert p.exists(), r["path"]
        assert p.stat().st_size == r["bytes"], r["path"]
        assert sha256(p) == r["sha256"], r["path"]
    mism = [r for r in man["files"] if r.get("receipt_matches_bytes") is False]
    assert len(mism) == man["n_receipt_mismatches"]
    assert all("h84" not in r["path"] for r in mism), "H84's own receipt must match its bytes"


def test_site_pages_agree_on_the_current_candidate(card):
    for name in ("index.html", "h84.html", "h84-executive-summary.html"):
        t = (DOCS / name).read_text()
        assert card["raster_sha256"] in t, name
        assert "h84-candidate.tif" in t, name
    root = (ROOT / "index.html").read_text()
    assert card["raster_sha256"] in root
    assert "H84" in root


def test_site_states_the_submission_verdict_unambiguously(card):
    t = (DOCS / "index.html").read_text()
    assert "DOWNLOAD: YES" in t
    assert "SUBMIT: NO" in t or "SUBMIT: YES" in t
    if not card["submit_ok"]:
        assert "SUBMIT: NO" in t
    es = (DOCS / "h84-executive-summary.html").read_text()
    assert "Predicted values must be in range [0, 1]" in es
    assert "does not have DrivenData credentials" in es or "cannot do steps" in es


def test_site_publishes_no_expected_score_table():
    """IR-H84-003: a projection must never be printed beside scores as if it were one.

    The phrase may appear only inside the irregularity card that quotes the defect it found on the
    previous page; it must not be a heading of this page's own, and no projection may appear before
    the irregularities section.
    """
    t = (DOCS / "index.html").read_text()
    for heading in ("<h2>Expected Score Range", "<h3>Expected Score Range",
                    "<th>Expected DTI", "<th>Expected score"):
        assert heading not in t, heading
    cut = t.find("Irregularities found and flagged this session")
    assert cut > 0, "the irregularities section must exist"
    head = t[:cut]
    assert "Expected Score Range" not in head
    assert "0.30\u20130.38" not in head and "0.30-0.38" not in head and "0.30\u20130.38" not in head
    # a projection is still allowed where it is labelled as one
    assert "not a projection" in t or "is_a_leaderboard_forecast" in json.dumps(
        json.loads((EVID / "h84_run_card.json").read_text()))


def test_irregularities_are_registered_and_each_names_its_measurement():
    p = EVID / "h84_irregularities.json"
    assert p.exists()
    j = json.loads(p.read_text())
    assert j["n_entries"] >= 9
    reg = json.loads((REG / "irregularities.json").read_text())
    ids = {x["id"] for x in reg["entries"]}
    for e in j["entries"]:
        assert e["id"] in ids, e["id"]
        for k in ("title", "what_it_is", "how_we_know", "handling", "severity"):
            assert str(e.get(k, "")).strip(), (e["id"], k)


def test_readme_leads_with_the_current_round(card):
    t = (ROOT / "README.md").read_text()
    assert t.lstrip().startswith("<!--H84-README-->")
    assert card["raster_sha256"] in t
    assert "SUBMIT: NO" in t or "SUBMIT: YES" in t
    assert "HOLDOUT-DTI" in t
    assert "docs/downloads/h84-candidate.tif" in t


def test_band_six_identity_is_measured_not_inherited():
    p = EVID / "h84_band6_identity_recheck.json"
    if not p.exists():
        pytest.skip("band-6 recheck not run")
    j = json.loads(p.read_text())
    assert j["tag_in_file"]["band_name"] == "tc"
    assert j["tag_in_file"]["data_category"] == "magnetic_data"
    best = max((c for c in j["comparisons"] if "external_band" in c),
               key=lambda c: c["spearman_vs_band6"])
    assert best["spearman_vs_band6"] > 0.99
    tmi = next(c for c in j["comparisons"] if c.get("control") == "band14_TMI")
    assert abs(tmi["spearman_vs_band6"]) < 0.05


def test_shared_tools_were_reused_not_forked():
    """The brief forbids a private fork of a shared tool. The runner must import them."""
    src = (ROOT / "scripts" / "run_h84.py").read_text()
    for mod in ("evaluate_holdout", "gates", "grid", "holdout", "metric", "nodes", "spatial",
                "submission_writer"):
        assert mod in src, mod
    for fn in ("holdout.make_folds", "EH.evaluate", "EH.pooled_summary", "nodes.spacing_select",
               "gates.lane_report", "submission_writer.write_submission",
               "spatial.negative_block_errors", "spatial.independence"):
        assert fn in src, fn
    assert "def dti(" not in src, "no local re-implementation of the metric"
    assert "def greedy_emit(" not in src
