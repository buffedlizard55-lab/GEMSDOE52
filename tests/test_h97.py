"""H97/H98 (frozen as H88/H89, then H92/H93) — the co-training texture-disagreement round.

Every assertion reads a receipt or a published file at test time; nothing here
restates a number that is not already in ``evidence/`` or ``registry/``.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARD = json.loads((ROOT / "evidence/h97_run_card.json").read_text())
CARD98 = json.loads((ROOT / "evidence/h98_run_card.json").read_text())
HOLDOUT = json.loads((ROOT / "evidence/h97_holdout.json").read_text())
HOLDOUT98 = json.loads((ROOT / "evidence/h98_holdout.json").read_text())
BUILD = json.loads((ROOT / "evidence/h97_build.json").read_text())
SHA = CARD["raster"]["sha256"]
TIFF = ROOT / "docs/downloads/h97-candidate.tif"


def test_newest_round_owns_the_top_of_the_readme():
    text = (ROOT / "README.md").read_text()
    assert text.startswith("<!--H97-README-->")
    head = text[: text.index("<!--/H97-README-->")]
    assert "OK TO DOWNLOAD: YES" in head and "OK TO SUBMIT: NO" in head
    assert "docs/downloads/h97-candidate.tif" in head and SHA in head
    assert "knowledge/100_h97_h98_results.md" in head


def test_download_is_the_canonical_file_and_the_card_sha():
    published = TIFF.read_bytes()
    submission = (ROOT / "submission" / CARD["raster"]["file"]).read_bytes()
    canonical = (ROOT / "docs/downloads" / CARD["raster"]["file"]).read_bytes()
    assert published == submission == canonical
    assert hashlib.sha256(published).hexdigest() == SHA == BUILD["sha256"]
    assert len(published) == CARD["raster"]["bytes"] == BUILD["format_checks"]["bytes"]


def test_zip_holds_exactly_one_byte_identical_geotiff():
    with zipfile.ZipFile(ROOT / "docs/downloads/h97-candidate.zip") as z:
        names = z.namelist()
        assert len(names) == 1 and names[0].endswith(".tif")
        assert hashlib.sha256(z.read(names[0])).hexdigest() == SHA


def test_raster_is_the_portal_container_the_validator_reported():
    import numpy as np
    import rasterio
    with rasterio.open(TIFF) as d:
        v = d.read(1)
        assert d.count == 1 and d.dtypes[0] == "float32"
        assert str(d.crs) == "EPSG:32611" and v.shape == (3730, 3292)
        assert d.nodata is None
    assert np.isfinite(v).all()                     # 0 NaN, 0 inf -> the portal's [0,1] check passes
    assert float(v.min()) >= 0.0 and float(v.max()) <= 1.0
    assert int((v > 0).sum()) == CARD["raster"]["placed"] == BUILD["placed"]
    fc = BUILD["format_checks"]
    assert fc["nan_pixels"] == 0 and fc["infinity_pixels"] == 0 and fc["mass_outside_footprint"] == 0
    assert fc["bounds"] == fc["ref_bounds"] and fc["problems"] == [] and fc["ok"] is True


def test_both_preregistration_pins_verify():
    for reg_path, doc_path in [("registry/h97_preregistration.json", "knowledge/97_hypotheses_H97_preregistered.md"),
                               ("registry/h98_preregistration.json", "knowledge/98_hypotheses_H98_preregistered.md")]:
        reg = json.loads((ROOT / reg_path).read_text())
        assert reg["hypothesis_document"] == doc_path
        actual = hashlib.sha256((ROOT / doc_path).read_bytes()).hexdigest()
        assert actual == reg["hypothesis_sha256"]
        # results must never be appended to a pinned preregistration document
        body = (ROOT / doc_path).read_text()
        assert "Filled in after the run" in body or "\u00a74" in body


def test_holdout_receipts_back_every_number_in_the_cards():
    for card, receipt in ((CARD, HOLDOUT), (CARD98, HOLDOUT98)):
        h = card["holdout"]
        assert h["instrument"] == "gems52-pooled-hide-v1"
        assert h["withheld_positive_px"] == 53186          # 53,186 — never 60,894 (IR-H97-006)
        scores = receipt["pooled"]["scores"]
        primary = receipt["primary"]
        assert h["primary_dti"] == pytest.approx(scores[primary]["dti"])
        assert h["primary_ci95"] == pytest.approx(scores[primary]["ci95"])
        assert h["random_dti"] == pytest.approx(scores["random"]["dti"])
        assert h["random_ci95"] == pytest.approx(scores["random"]["ci95"])
        assert scores[primary]["withheld_positive_pixels"] == h["withheld_positive_px"]
        paired = receipt["pooled"]["paired_differences"]["random"]
        assert h["paired_primary_minus_random"]["delta"] == pytest.approx(paired["delta"])
        assert h["paired_primary_minus_random"]["ci95"] == pytest.approx(paired["ci95"])
        # every arm's CI must lie below the random control's point estimate
        assert paired["ci95"][1] < 0
        # the preregistered primary must be strictly below its own random control
        assert h["primary_dti"] < h["random_dti"]


def test_verdict_is_the_frozen_rule_not_an_opinion():
    assert "NEGATIVE" in CARD["verdict"]
    assert "NEGATIVE" in CARD98["verdict"]
    bar = json.loads((ROOT / "registry/h97_preregistration.json").read_text())["thresholds"]
    assert bar["bootstrap_draws"] == 1000
    assert CARD["raster"]["placed"] <= CARD["raster"]["budget"]
    for field in ("hypothesis", "mechanism", "named_non_fault_mimic", "verdict", "verdict_reason",
                  "submission_name", "submission_note"):
        assert CARD.get(field), f"run card must carry {field}"


def test_submission_identifiers_respect_the_portal_limits():
    note, name = CARD["submission_note"], CARD["submission_name"]
    assert len(note) <= 140 and len(name) <= 140
    assert name == "h97-cotrain-atexture-disagreement-37654px"
    assert BUILD["submission_name"] == name and BUILD["submission_note"] == note
    assert BUILD["submission_note_chars"] == len(note) == 74
    # the artifact must not be claimed as approved anywhere sticky
    assert BUILD["verdict"] == "DOWNLOAD YES, SUBMIT NO"
    assert json.loads((ROOT / "docs/data/feed.json").read_text())["submission"] \
        != CARD["raster"]["file"]


def test_a_only_reasoning_dossier_is_complete_and_hash_pinned():
    import csv
    path = ROOT / "docs/downloads/h97-candidate-a-only-reasoning.csv"
    assert path.read_bytes()[:1] != b"" and hashlib.sha256(path.read_bytes()).hexdigest() \
        == BUILD["a_only_reasoning"]["sha256"]
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == CARD["raster"]["placed"] == BUILD["a_only_reasoning"]["rows"]
    a_only = [r for r in rows if r["class"].startswith("A")]
    assert len(a_only) == BUILD["a_only_reasoning"]["a_only_dots"] == 34187
    assert all(r["geological_reasoning"].strip() for r in rows)


def test_not_the_union_of_the_two_views():
    u = BUILD["not_the_union"]
    assert u["disagreement_dots"] == 37654 and u["dots_also_in_consensus"] == 0
    assert abs(u["spearman_field_vs_unionmax"]) < 0.5      # a max(A,B) rescaling would be ~1.0


def test_uniqueness_and_lane_gates_are_reported_not_waived():
    uniq = BUILD["uniqueness"]
    assert uniq["identical_to_a_prior"] is False and uniq["n_priors_checked"] >= 146
    assert uniq["support_novelty_gate_ok"] is True
    assert uniq["novel_fraction"] >= 0.20 and uniq["equals_literal_prior_union"] is False
    lane = BUILD["lane"]
    assert lane["max_spearman"] < lane["rank_threshold"]          # the brief's 0.90 rank bar passes
    assert lane["duplicate"] is True                              # the literal dot rule fires...
    assert CARD["registry"]["lane_near_3px_max_excluding_probes"] < 0.70   # ...only on the probe raster
    assert "not waived" in CARD["registry"]["note"] or "no lane retuning" in lane["rule"]


def test_identifier_rename_history_is_recorded_and_auditable():
    diff = (ROOT / "evidence/h97_identifier_rename.diff").read_text()
    assert diff.count("-") and ("h88" in diff or "H88" in diff)
    for reg_path in ("registry/h97_preregistration.json", "registry/h98_preregistration.json"):
        reg = json.loads((ROOT / reg_path).read_text())
        hist = reg["identifier_rename"]
        assert [h["to"] for h in hist["history"]] == ["H92 / H93", "H97 / H98"]
        assert hist["evidence_diff"] == "evidence/h97_identifier_rename.diff"
        assert hist["irregularity"] == "IR-H97-008"
        assert hist["history"][1]["document_sha256_after"] == reg["hypothesis_sha256"]
    ent = [e for e in json.loads((ROOT / "registry/irregularities.json").read_text())["entries"]
           if e["id"] == "IR-H97-008"]
    assert len(ent) == 1 and "identifier collision" in ent[0]["title"].lower()


def test_feed_emits_the_newest_round_from_the_shared_tool():
    """scripts/refresh_feed.py must derive newest_round itself, so a scheduled refresh keeps it."""
    src = (ROOT / "scripts/refresh_feed.py").read_text()
    assert "newest_round=newest_round()" in src and "def newest_round()" in src
    assert "never advertise bytes we cannot verify" in src


def test_site_pages_carry_the_verdict_and_one_click_downloads():
    for rel in ("docs/index.html", "docs/executive-summary.html", "docs/downloads/index.html"):
        page = (ROOT / rel).read_text()
        assert "<!--H97-CARD-->" in page or "<!--H97-DL-->" in page, rel
        assert "SUBMIT: NO" in page or "OK TO SUBMIT: NO" in page or "SUBMIT NO" in page, rel
        assert "h97-candidate.tif" in page, rel
    feed = json.loads((ROOT / "docs/data/feed.json").read_text())["newest_round"]
    assert feed["sha256"] == SHA and feed["hash_verified"] is True
    assert str(feed["round"]).startswith("H97") and feed["paired_vs_random"] < 0
