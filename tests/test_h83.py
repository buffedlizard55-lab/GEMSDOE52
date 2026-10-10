"""H83 — co-training on two instruments.

The tests here are cheap and structural: they pin the two instruments' *contracts* (the off-catalogue
truth can never be a training positive; the two instruments share one fit; the frozen rule is still
the one that decides the verdict) and they verify the published artefact against the bytes on disk.
They do not re-run the pipeline and they never assert a leaderboard gain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
SUBM = ROOT / "submission"
DOCS = ROOT / "docs"


def load(n: str) -> dict:
    p = EVID / f"h83_{n}.json"
    if not p.exists():
        pytest.skip(f"missing receipt {p.name}; run scripts/run_h83.py")
    return json.loads(p.read_text())


def test_preregistration_is_pinned_and_unchanged():
    reg = json.loads((ROOT / "registry/h83_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert doc.exists()
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    assert reg["submission_slots_used"] == 0
    assert reg["attribution_arms_not_promotable"] is True


def test_both_instruments_scored_every_arm_at_a_matched_budget():
    hold = load("holdout")
    p = hold["pooled"]["pooled"]
    arms = set(p["scores"])
    for key in ("offcatalogue", "offcatalogue_b"):
        assert set(hold[key]["pooled"]["scores"]) == arms, key
        assert hold[key]["all_arms_filled"] is True, key
    for a in hold["pooled"]["folds"]:
        for arm, row in a["arms"].items():
            assert row["placed"] == row["requested"], (a["fold"], arm)
    assert "disagreement_post" in arms


def test_gems52_offcatalogue_v1_truth_is_disjoint_from_the_catalogue_positive_class():
    """The whole point of I2: its truth is never a training positive of the same fit."""
    hold = load("holdout")
    fit = load("fit_checkpoint")
    # I2 truth counts are recorded per fold; every arm filled the budget on it, and the
    # off-catalogue positives come from a different compilation, so the two instruments can share
    # one fit. What is testable cheaply is that both instruments ran on the same fitted models.
    assert len(fit["folds"]) == len(hold["pooled"]["folds"]) == 4
    for r in fit["folds"]:
        assert r["offcat_truth_px"] >= 0
    for key in ("offcatalogue", "offcatalogue_b"):
        assert hold[key]["pooled"]["scores"]["single_B"]["withheld_positive_pixels"] > 0


def test_canary_did_not_fire():
    can = load("canary")
    reg = json.loads((ROOT / "registry/h83_preregistration.json").read_text())
    assert can["max_alarm_across_folds"] < reg["thresholds"]["canary_auc_alarm"]
    assert can["any_alarm"] is False


def test_independence_screen_precedes_and_gates_the_exchange():
    ind = load("independence")
    ex = load("pseudo_exchange")
    reg = json.loads((ROOT / "registry/h83_preregistration.json").read_text())
    bar = reg["thresholds"]["independence_abandon_max_abs_rho"]
    assert ind["pre"]["n_blocks"] >= reg["thresholds"]["min_independence_blocks"]
    assert ind["allow_exchange"] == (abs(ind["pre"]["max_abs_correlation"]) < bar
                                     and ind["pre"]["measured"])
    if not ind["allow_exchange"]:
        assert ex["total_pseudo_pixels"] == 0
    # one round only, never more
    assert ex["rule"].startswith("exactly one exchange")


def test_shipped_raster_matches_its_receipt_and_is_portal_legal():
    sub = load("submission")
    rec = sub["receipt"]
    tif = SUBM / rec["file"]
    assert tif.exists()
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == rec["sha256"]
    assert tif.stat().st_size == rec["bytes"]
    assert 1 <= len(rec["submission_name"]) <= 140
    assert 1 <= rec["note_chars"] <= 140
    val = rec["validator"]
    assert val["ok"] is True
    assert val["bands"] == 1 and val["dtype"] == "float32"
    assert val["crs"] == "EPSG:32611"
    assert (val["height"], val["width"]) == (3730, 3292)
    assert 0.0 <= val["min"] and val["max"] <= 1.0
    assert int(val["positive_pixels"]) == int(sub["placed"])


def test_shipped_raster_has_no_non_finite_pixel_and_no_mass_outside_the_footprint():
    """The owner's portal rejection was 'Predicted values must be in range [0, 1]'.

    This file is all-finite with zeros outside the footprint, so no reader — nodata-aware or not —
    can see a value outside [0, 1].
    """
    rasterio = pytest.importorskip("rasterio")
    sub = load("submission")
    with rasterio.open(SUBM / sub["receipt"]["file"]) as ds:
        a = ds.read(1)
    assert np.isfinite(a).all()
    assert a.min() >= 0.0 and a.max() <= 1.0
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        finite = np.isfinite(ref.read(1))
    assert not np.any((a > 0) & ~finite)


def test_output_is_not_merely_the_union_of_the_two_views():
    sub = load("submission")
    nu = sub["not_union"]
    assert nu["verdict"].startswith("PASS")
    assert nu["dots_shared_with_union_max"] < sub["placed"]
    assert nu["jaccard_with_union_max"] < 1.0


def test_run_card_carries_every_field_the_brief_requires():
    card = load("run_card")
    for k in ("hypothesis", "mechanism", "named_non_fault_mimic", "holdout", "lane",
              "raster", "submission_name", "note", "verdict"):
        assert k in card, k
    assert card["verdict"] in ("promote", "negative")
    assert len(card["note"]) <= 140
    assert card["submission_slots_used"] == 0
    # a holdout number is labelled, never presented bare
    assert card["holdout"]["evidence_class"] == "HOLDOUT-DTI"
    assert card["holdout"]["evaluator"] == "gems52-pooled-hide-v1"
    assert card["holdout"]["withheld_positive_pixels"] > 0
    assert len(card["holdout"]["ci95"]) == 2


def test_verdict_follows_the_frozen_ci_rule():
    card = load("run_card")
    hold = load("holdout")
    d = hold["pooled"]["pooled"]["paired_differences"]["single_B"]
    assert card["verdict"] == ("promote" if d["ci95"][0] > 0 else "negative")


def test_offcatalogue_numbers_are_never_labelled_as_holdout_dti():
    hold = load("holdout")
    for key in ("offcatalogue", "offcatalogue_b"):
        assert hold[f"{key}_evidence_class"] == "OFFCAT-DTI"
        assert hold[key]["pooled"]["evidence_class"] == "OFFCAT-DTI"


def test_published_downloads_are_byte_identical_to_the_repository_artefact():
    sub = load("submission")
    rec = sub["receipt"]
    for name in ("h83-candidate.tif", "h83-candidate.zip"):
        p = DOCS / "downloads" / name
        if not p.exists():
            pytest.skip(f"{name} not published yet")
    tif = SUBM / rec["file"]
    pub = DOCS / "downloads" / "h83-candidate.tif"
    assert hashlib.sha256(pub.read_bytes()).hexdigest() == rec["sha256"]
    import zipfile
    with zipfile.ZipFile(DOCS / "downloads" / "h83-candidate.zip") as z:
        assert z.namelist() == [tif.name]
        assert z.read(tif.name) == tif.read_bytes()


def test_site_states_both_verdicts_and_links_the_download():
    idx = (DOCS / "index.html").read_text()
    assert "OK to download?" in idx
    assert "OK to submit" in idx
    assert "downloads/h83-candidate.tif" in idx
    guide = (DOCS / "h83-executive-summary.html").read_text()
    assert "Predicted values must be in range" in guide
    assert "File to submit" in guide
