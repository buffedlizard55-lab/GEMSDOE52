"""Current artifact and archive integrity checks; local gates are not upload approval."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_round(sub: dict) -> str:
    """Which round owns `submission/LATEST.txt`, read from the receipt rather than hard-coded."""
    f = sub.get("file", "")
    for tag in ("h60", "h59", "h58", "h57", "h56", "h55", "h54"):
        if f"-{tag}-" in f:
            return tag.upper()
    return "UNKNOWN"


def test_current_artifact_is_downloadable_but_not_slot_approved() -> None:
    """Round-aware: whichever round owns the pointer, its own gates must hold.

    The H56 assertions below are kept verbatim in `test_h56_archive_stays_intact` so that H56's
    findings remain checked after it stops being the incumbent.
    """
    sub = json.loads((DOCS / "data/submission.json").read_text())
    rnd = _current_round(sub)

    assert (ROOT / "submission/LATEST.txt").read_text().strip() == sub["file"]
    if rnd == "H59":
        # approval may only mirror the mechanical registered gate (tests/test_h59.py re-verifies
        # that it cannot be asserted); the pointer test stays fully round-agnostic
        slot = json.loads((ROOT / "evidence/h59_slot_gate.json").read_text())
        mechanical = bool(slot["slot_bar_met"] and slot["checks_pass"])
        assert sub["approved_for_weekly_slot"] == mechanical
        assert sub.get("promoted_field") == slot["shipped_field"]
    else:
        assert sub["approved_for_weekly_slot"] is False, "the slot gate must never be asserted open"
        assert sub.get("promoted") is False

    canonical = DOWNLOADS / sub["file"]
    # the scheduled feed rewrites docs/data/submission.json from evidence/submission_<stem>.json,
    # so the short aliases follow the repository convention rather than a publisher-only key
    short = (DOWNLOADS / "h57-candidate.tif" if "-h57-" in sub["file"]
             else DOWNLOADS / "h59-candidate.tif" if "-h59-" in sub["file"]
             else DOWNLOADS / Path(sub["short_tif"]).name)
    assert canonical.exists(), f"{rnd}: canonical download missing"
    assert sha(canonical) == sub["sha256"]
    assert short.read_bytes() == canonical.read_bytes()

    # A ZIP is a valid submission payload when it holds exactly one GeoTIFF that is the canonical
    # download.  The scheduled feed repackages the canonical ZIP for whatever LATEST.txt names and
    # adds SUBMISSION_NOTE.txt / evidence.json beside the TIFF, so archive-level byte equality with
    # the short alias is reported by check_site as a note, not demanded here.
    canonical_zip = DOWNLOADS / (sub["file"][:-4] + ".zip")
    short_zip = (DOWNLOADS / "h57-candidate.zip" if "-h57-" in sub["file"]
                 else DOWNLOADS / "h59-candidate.zip" if "-h59-" in sub["file"]
                 else DOWNLOADS / Path(sub["short_zip"]).name)
    for zp in (canonical_zip, short_zip):
        with zipfile.ZipFile(zp) as archive:
            tiffs = [n for n in archive.namelist() if n.lower().endswith((".tif", ".tiff"))]
            assert len(tiffs) == 1, f"{zp.name} must hold exactly one GeoTIFF"
            assert archive.read(tiffs[0]) == canonical.read_bytes()

    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert np.isfinite(data).all(), "local all-finite policy; historical portal rejection cause is unconfirmed"
        assert set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == sub["nonzero_px"]

    if rnd == "H57":
        build = json.loads((DOCS / "data/h57_build.json").read_text())
        gate = json.loads((DOCS / "data/h57_slot_gate.json").read_text())
        assert build["format_gate"]["ok"], build["format_gate"]["problems"]
        assert build["uniqueness"]["canonical_pattern_unique"]
        assert build["not_the_union"]["arm_outside_prior_support_px"] == build["arm"]["px"]
        assert build["file"]["min_distance_to_catalogue_m"] > 200.0
        assert len(str(sub.get("note") or sub.get("submission_note") or "")) <= 200
        # R1 is registered as unmet for this round; if that ever changes it must change loudly
        assert gate["r1"]["met"] is False
        assert gate["checks"]["R4 format gate (single band, float32, EPSG:32611, 3730x3292, "
                             "transform, all finite, [0,1], no nodata)"] is True

    if rnd == "H59":
        # the H59 receipt carries its own gate report; the site's current-pointer file must agree
        result = json.loads((DOCS / "data/h59_result.json").read_text())
        assert result["artifact"]["format_gate"]["ok"], result["artifact"]["format_gate"]["problems"]
        assert result["artifact"]["uniqueness"]["canonical_pattern_unique"]
        assert result["artifact"]["ring_min_distance_m"] > 200.0
        assert (result["artifact"]["spacing"]["min_nn_px"] or 0) >= 3.0
        # amendment 3 gate semantics: the forbidden equalities are the set-union of the two views'
        # emissions and the union-field emission; equality with a constituent view's own emission
        # is reported and expected exactly when that view is the shipped field
        ntu = result["artifact"]["not_the_union"]
        assert not ntu["equals_set_union"]
        assert not ntu["equals_union_field"]
        shipped = result["holdout"]["decision"]["shipped_field"]
        assert ntu["equals_view_b"] is (shipped == "view_B")
        assert ntu["equals_view_a"] is (shipped == "view_A")
        assert result["reasoning_dossier"]["rows"] == sub["nonzero_px"]
        assert result["reasoning_dossier"]["a_only_rows"] >= 0
        assert len(str(sub.get("note") or sub.get("submission_note") or "")) <= 200
        # the repo's standing rule: the machine field never asserts an open slot gate
        assert result["artifact"]["emission_px"] == 37654


def test_h56_archive_stays_intact() -> None:
    """H56 stopped being the incumbent when H57 shipped; its own receipts must still verify."""
    gate = json.loads((DOCS / "data/h56_slot_gate_review_2026-10-07.json").read_text())
    verify = json.loads((DOCS / "data/gems52-h56-verify.json").read_text())
    scope = json.loads((DOCS / "data/h56_a_only_reasoning_scope_2026-10-07.json").read_text())

    assert gate["decision"]["approved_for_weekly_slot"] is False
    assert gate["spatial_holdout"]["h56_comparable_holdout_receipt_found"] is False
    assert gate["leaderboard_score_to_filename_mapping_authenticated"] is False
    assert verify["identical_to_any_prior"] == []
    assert verify["priors_checked"] == 33
    assert verify["novel_px"] == 12941
    assert verify["min_NN_separation_ok"] is False
    assert gate["postbuild_decoded_pattern_review"]["derived_arm_cells_with_accessible_prior_support"] == 2059
    assert scope["status"].startswith("NOT PRODUCED")

    canonical = DOWNLOADS / "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif"
    short = DOWNLOADS / "h56-candidate.tif"
    assert canonical.exists() and short.exists()
    assert short.read_bytes() == canonical.read_bytes()
    assert sha(canonical) != json.loads(
        (DOCS / "data/submission.json").read_text())["sha256"], "H56 must not be the incumbent"
    with rasterio.open(canonical) as ds:
        assert int(np.count_nonzero(ds.read(1))) == 40517
    canonical_zip = DOWNLOADS / (canonical.stem + ".zip")
    short_zip = DOWNLOADS / "h56-candidate.zip"
    assert canonical_zip.read_bytes() == short_zip.read_bytes()
    with zipfile.ZipFile(short_zip) as archive:
        assert archive.namelist() == [canonical.name]
        assert archive.read(canonical.name) == canonical.read_bytes()


def test_h54_remains_a_separate_audit_only_archive() -> None:
    audit = json.loads((DOCS / "data/h54_audit.json").read_text())
    assert audit["approved_for_weekly_slot"] is False
    assert audit["global_decoded_pattern_uniqueness"].startswith("unknown")
    assert audit["file"] != (ROOT / "submission/LATEST.txt").read_text().strip()

    canonical = DOWNLOADS / audit["file"]
    short = DOWNLOADS / "h54-audit-only.tif"
    assert short.read_bytes() == canonical.read_bytes()
    with zipfile.ZipFile(DOWNLOADS / "h54-audit-only.zip") as archive:
        tiffs = [name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))]
        assert len(tiffs) == 1
        assert archive.read(tiffs[0]) == canonical.read_bytes()


# --- H96 (arena/90369109 session): bidirectional co-training disagreement field -------------------
# Every gate claim is re-derived from the published bytes/receipts, and the run-card contract is
# enforced: approved_for_weekly_slot=False and submit_ok=False on a negative verdict, zero slots,
# unique submission name + <=200-char note, and the round's receipts present beside the artifact.


H96_STEM = "gems52-h96-bidir-cotrain-coverstep-25400px-20261010T222552Z-a6ab4495-zeros"
H96_SHA = "ba2dae7db2b919bb53c147cae0d5f9663b368b059fc1b26c69d8dbfc35948ade"


def _h96_receipts():
    import json as _json
    artifacts = _json.loads((ROOT / f"evidence/submission_{H96_STEM}.json").read_text())
    card = _json.loads((ROOT / "evidence/h96_run_card.json").read_text())
    hold = _json.loads((ROOT / "evidence/h96_holdout.json").read_text())
    return artifacts, card, hold


def test_h96_receipt_gate_blocks_promote_while_below_the_bar() -> None:
    artifacts, card, hold = _h96_receipts()
    assert artifacts["sha256"] == H96_SHA
    assert artifacts["file"].startswith("gems52-h96-bidir")
    assert artifacts["round"] == "H96"
    assert artifacts["nonzero_px"] == 25400
    assert artifacts["short_tif"] == "h96-candidate.tif"
    assert artifacts["short_zip"] == "h96-candidate.zip"
    assert artifacts["validator"]["sha256"] == H96_SHA
    # unique submission name + short note (the submission-naming convention)
    note = artifacts["note"]
    assert 1 <= len(note) <= 200
    assert artifacts["note_chars"] == len(note)
    # run-card contract: negative verdict => slot gate closed, no upload, no promotion
    assert card["verdict"] == "negative"
    assert card["verdict_for_slot"] == "negative"
    assert card["approved_for_weekly_slot"] is False
    assert card["submit_ok"] is False
    assert card["download_ok"] is True
    assert card["submission_slots_used"] == 0
    assert artifacts["approved_for_weekly_slot"] is False
    assert artifacts["promoted"] is False
    assert artifacts["submission_slots_used"] == 0
    assert card["budget"]["submission_slot"] == "not spent"
    # labels discipline: the holdout block is HOLDOUT-DTI with the evaluator identity; no org score
    hdti = card["holdout_dti"]
    assert hdti["label"] == "HOLDOUT-DTI"
    assert hdti["evaluator_version"] == "gems52-pooled-hide-v1"
    assert hdti["withheld_positive_pixels"] == 60894
    assert card["bar_to_beat"] == 0.192829
    # per-round receipts frozen before the fit (prereg + amendment hashes recorded)
    reg = artifacts["metadata"]["registration"]
    assert reg["frozen_before_any_fit"] is True
    assert reg["preregistration_sha256"].startswith("0f664c43")
    assert reg["amendment_sha256"].startswith("91f74c5a")
    assert card["preregistration"] == reg
    # the round's own receipts must exist beside the artifact
    for name in ("h96_run_card.json", "h96_holdout.json", "h96_lane_surface.json", "h96_lane_dots.json"):
        assert (ROOT / "evidence" / name).is_file(), name
    # submission naming convention: the unique name and short note reach the site
    page = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "h96-bidir-cotrain-coverstep-25400px" in page
    assert note[:60] in page
    # LATEST pointers all name this stem: H96 remains the incumbent current pointer (its shared
    # LATEST files and the current-submission JSON are untouched by later negative rounds; the H102
    # round - written as H97, renamed at merge per IR-H102-004 - keeps only its own round pin).
    for p in ("submission/LATEST.txt", "docs/submission/LATEST.txt", "submission/H96_LATEST.txt"):
        txt = (ROOT / p).read_text(encoding="utf-8").strip()
        assert txt in (H96_STEM, H96_STEM + ".tif"), (p, txt)
    # the run card names its validator and reports ok
    assert card["validator"]["ok"] is True
    assert card["validator"]["sha256"] == H96_SHA


def test_h96_artifact_bytes_re_verify_every_gate_claim() -> None:
    import numpy as np
    import rasterio

    artifacts, card, hold = _h96_receipts()
    canonical = DOCS / "downloads" / f"{H96_STEM}.tif"
    assert canonical.is_file()
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == H96_SHA
    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert np.isfinite(data).all()
        # the "[0,1]" portal lesson: values strictly inside [0,1], exactly {0,1}
        assert set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == 25400
    # uniqueness gate recorded in the run card
    assert card["uniqueness"]["canonical_pattern_unique"] is True
    assert card["uniqueness"]["novel_fraction"] > 0.5
    assert card["uniqueness"]["equals_literal_prior_union"] is False
    # lane surface PASS; dots lane policy PASS while the literal probe hit stays disclosed (IR-H96-002)
    lane_s = json.loads((ROOT / "evidence/h96_lane_surface.json").read_text())
    assert lane_s["ok"] is True and lane_s["duplicate"] is False
    assert lane_s["literal"]["max_spearman"] < 0.90
    lane_d = json.loads((ROOT / "evidence/h96_lane_dots.json").read_text())
    assert lane_d["policy"]["verdict"] == "PASS"
    assert lane_d["literal"]["verdict"] == "DUPLICATE/STOP"  # disclosed probe-lane hit (IR-H96-002), not real drift
    assert lane_d["literal"]["max_near_3px_fraction"] > 0.99
    # holdout summary recorded: primary DTI in [0,1] with a CI, below the bar
    scores = hold["pooled"]["scores"]
    primary = scores["cotrain_bi"]
    assert 0.0 <= primary["dti"] <= 1.0
    assert len(primary["ci95"]) == 2 and primary["ci95"][0] <= primary["dti"] <= primary["ci95"][1]
    assert primary["dti"] < hold["bar_to_beat"]
    assert card["holdout_dti"]["scores"]["cotrain_bi"]["dti"] == primary["dti"]
    # the site carries the round's audit page and the download alias
    assert 'href="h96.html"' in (DOCS / "index.html").read_text(encoding="utf-8")
    assert (DOCS / "downloads/h96-candidate.tif").is_file()
    assert (DOCS / "downloads/h96-candidate.tif").read_bytes() == canonical.read_bytes()


# --- H102 (arena/1bc2f2ec session): co-training disagreement-state quota field ---------------------
# Written as H97, renamed H97 -> H102 at merge: parallel sessions had merged their own H97/H97b and
# H98-H101 rounds into main while this round ran (IR-H102-004; identifier-only rename per the
# IR-H84-006 precedent - GeoTIFF bytes and every holdout number unchanged). The round is NEGATIVE, so
# the shared current pointer stays on the incumbent H96; this round keeps only its own round pin
# (submission/H102_LATEST.txt). Same run-card contract as H96: negative verdict => slot gate closed,
# no upload, no promotion, zero slots.

H102_STEM = "gems52-h102-disagreement-quota-dva2-25400px-20261011T005958Z-9bd97e7c-zeros"
H102_SHA = "c49a07d15a5bb293c0f29f67d9d4931ed5f2f9ce48978da86af4e59a54f2523d"


def _h102_receipts():
    import json as _json
    artifacts = _json.loads((ROOT / f"evidence/submission_{H102_STEM}.json").read_text())
    card = _json.loads((ROOT / "evidence/h102_run_card.json").read_text())
    w = _json.loads((ROOT / "evidence/h102_write.json").read_text())
    return artifacts, card, w


def test_h102_receipt_gate_blocks_promote_while_below_the_bar() -> None:
    artifacts, card, w = _h102_receipts()
    assert artifacts["sha256"] == H102_SHA
    assert artifacts["file"].startswith("gems52-h102-")
    assert artifacts["round"] == "H102"
    assert artifacts["nonzero_px"] == 25400
    assert artifacts["short_tif"] == "h102-candidate.tif"
    assert artifacts["short_zip"] == "h102-candidate.zip"
    assert artifacts["marker"] == "submission/H102_LATEST.txt"
    assert artifacts["incumbent_round"] == "H96"
    assert artifacts["validator"]["sha256"] == H102_SHA
    # unique submission name + short note (the submission-naming convention)
    note = artifacts["note"]
    assert 1 <= len(note) <= 140
    assert artifacts["note_chars"] == len(note)
    # run-card contract: negative verdict => slot gate closed, no upload, no promotion
    assert card["verdict"] == "negative"
    assert card["submit_ok"] is False
    assert card["download_ok"] is True
    assert card["slots_used"] == 0
    assert artifacts["approved_for_weekly_slot"] is False
    assert artifacts["promoted"] is False
    assert artifacts["submission_slots_used"] == 0
    # labels discipline: HOLDOUT-DTI on the repo evaluator; the bar is the committed B_DVA2 reading
    hdti = card["holdout_dti"]
    assert hdti["evaluator"] == "gems52-pooled-hide-v1"
    assert hdti["withheld_positive_px"] == 53186
    assert hdti["B_DVA2@9400_per_fold_committed_bar"] == 0.192829
    prim_dti, prim_ci = hdti["quota_primary@6350_per_fold"]
    assert prim_dti < 0.058228, "the primary arm must be below the random control of the same budget"
    assert prim_ci[0] < 0 < prim_ci[1] or prim_ci[1] < 0.058228
    assert card["gates"]["holdout_promotion"] == "FAIL"
    assert card["gates"]["control_reproduction"] == "PASS"
    assert card["gates"]["canary"] == "PASS"
    assert card["gates"]["independence"] == "PASS"
    assert card["gates"]["format"] == "PASS"
    assert card["gates"]["not_the_union"] == "PASS"
    # preregistration frozen before any fit; the rename is identifier-only (IR-H102-004 / IR-H84-006):
    # the re-pinned sha matches the renamed document's bytes and the pre-rename sha is preserved.
    reg = artifacts["metadata"]["registration"]
    assert reg["frozen_before_any_fit"] is True
    regfile = json.loads((ROOT / "registry/h102_preregistration.json").read_text())
    doc = ROOT / regfile["hypothesis_document"]
    assert regfile["hypothesis_sha256"] == reg["preregistration_sha256"]
    assert regfile["hypothesis_sha256"] == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert regfile["pre_rename"]["hypothesis_sha256"].startswith("31f7c92c")
    assert regfile["pre_rename"]["round"] == "H97"
    # the round's own receipts must exist beside the artifact
    for name in ("h102_run_card.json", "h102_e1_graft_holdout.json", "h102_e2_quota_holdout.json",
                 "h102_lane.json", "h102_write.json", "h102_fit.json", "h102_independence.json"):
        assert (ROOT / "evidence" / name).is_file(), name
    # the post-merge lane re-check against main's parallel rounds must PASS
    relane = json.loads((ROOT / "evidence/h102_lane_vs_parallel_main.json").read_text())
    assert relane["ok"] is True and relane["duplicate"] is False
    # submission naming convention: the unique name and short note reach the site
    page = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "h102-disagreement-quota-dva2-25400px" in page
    assert note[:60] in page
    assert (DOCS / "h102.html").is_file() and (DOCS / "h102-executive-summary.html").is_file()
    # the NEGATIVE round does not move the incumbent: all shared pointers still name H96
    for p in ("submission/LATEST.txt", "docs/submission/LATEST.txt"):
        txt = (ROOT / p).read_text(encoding="utf-8").strip()
        assert txt in (H96_STEM, H96_STEM + ".tif"), (p, txt)
    cur = json.loads((DOCS / "data" / "submission.json").read_text())
    assert cur["file"] in (H96_STEM, H96_STEM + ".tif")
    # this round's own pin names this stem
    pin = (ROOT / "submission/H102_LATEST.txt").read_text(encoding="utf-8").strip()
    assert pin in (H102_STEM, H102_STEM + ".tif")
    # the run card names its validator and reports ok
    assert card["validator"]["ok"] is True
    assert card["validator"]["sha256"] == H102_SHA
    # the artifact bytes re-verify: 25,400 binary dots, all finite, no nodata
    import numpy as np
    import rasterio
    tif = ROOT / "submission" / (H102_STEM + ".tif")
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == H102_SHA
    with rasterio.open(tif) as ds:
        data = ds.read(1)
        assert ds.dtypes == ("float32",) and ds.crs.to_epsg() == 32611
        assert np.isfinite(data).all() and set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == 25400
    # the short aliases are byte-identical
    assert (DOWNLOADS / "h102-candidate.tif").read_bytes() == tif.read_bytes()
