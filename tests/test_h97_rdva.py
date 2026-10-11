"""H97 current research artifact: bytes, frozen result, negative gates and public status."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STEM = "gems52-h97-rdva-cotrain-25400px-20261010-c6fbccd67b14-zeros"
FILE_SHA = "a6ca0f7b42ee722e1b04199557f84237ba186830a3b6860e38d3e4bf833722ad"
DECODED_SHA = "c6fbccd67b14db1b630a99bec1c2cf28a35bb620388378ac7f9551e822465d38"


def _load(name):
    return json.loads((ROOT / name).read_text())


def test_h97_frozen_registration_and_holdout_contract():
    reg_path = ROOT / "registry/h97_rdva_preregistration.json"
    reg = json.loads(reg_path.read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(reg_path.read_bytes()).hexdigest() == \
           "0631745794bfb6a582bfe2bc2f7d3f32ed9e066b1855469606d2ff89a8993db8"
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"] == \
           "f35c14e130af1ae00e6ed47a5a08a185125e81db8289ce30228ba7acfafc57e9"
    hold = _load("evidence/h97_rdva_holdout.json")
    assert hold["evidence_class"] == "HOLDOUT-DTI"
    assert hold["evaluator_version"] == "gems52-pooled-hide-v1"
    assert hold["withheld_positive_pixels"] == 53186
    assert hold["primary"] == "cotrain_B_RDVA"
    scores = hold["pooled"]["scores"]
    assert scores["cotrain_B_RDVA"]["dti"] == 0.18509042889108415
    assert scores["single_B_RDVA"]["dti"] == 0.18648202500601202
    paired = hold["pooled"]["paired_differences"]["single_B_RDVA"]
    assert paired["delta"] < 0 and paired["ci95"][0] < 0 < paired["ci95"][1]
    assert scores["cotrain_B_RDVA"]["dti"] < hold["bar_to_beat"] == 0.19282907051926573
    assert hold["promotion"]["pre_artifact_gate_pass"] is False
    assert hold["verdict"] == "negative"


def test_h97_canaries_independence_and_whole_segment_exchange():
    can = _load("evidence/h97_rdva_canary.json")
    assert can["any_alarm"] is False and can["max_auc"] < 0.90
    assert len(can["folds"]) == 4
    # 66 strict-A + 97 strict-B learner inputs, every one tested alone in every fold.
    assert all(len(f["per_feature"]) == 163 for f in can["folds"])
    assert all(not f["alarms"] for f in can["folds"])
    ex = _load("evidence/h97_rdva_exchange.json")
    assert ex["allowed_exchange"] is True
    assert ex["independence"]["result"]["max_abs_correlation"] < 0.60
    assert ex["one_round_only"] is True and ex["sample_weight"] == 0.25
    assert ex["total_pseudo_pixels"] == 15314
    a2b_px = b2a_px = a2b_segments = 0
    for fold in ex["folds"]:
        a2b = fold["directions"]["A->B"]
        b2a = fold["directions"]["B->A"]
        a2b_px += a2b["n_pixels"]; b2a_px += b2a["n_pixels"]
        a2b_segments += a2b["n_segments"]
        for direction in (a2b, b2a):
            assert sum(s["pixels"] for s in direction["segments"]) == direction["n_pixels"]
            assert all(s["pixels"] >= 5 for s in direction["segments"])
            assert direction["whole_segments_only"] is True
    assert (a2b_px, b2a_px, a2b_segments) == (7319, 7995, 578)
    # The primary is post-B only: B->A stays diagnostic and cannot enter the result arm.
    assert "post_A" not in _load("evidence/h97_rdva_holdout.json")["pooled"]["scores"]


def test_h97_tiff_and_zip_reverify_portal_range_fix():
    canonical = ROOT / "submission" / f"{STEM}.tif"
    published = DOCS / "downloads" / f"{STEM}.tif"
    alias = DOCS / "downloads/h97-rdva-candidate.tif"
    assert canonical.read_bytes() == published.read_bytes() == alias.read_bytes()
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == FILE_SHA
    with rasterio.open(canonical) as ds:
        a = ds.read(1)
        assert ds.count == 1 and ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert ds.shape == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert ds.nodata is None
    assert a.size == 12279160 and np.isfinite(a).all()
    assert set(np.unique(a).tolist()) == {0.0, 1.0}
    assert int(np.count_nonzero(a)) == 25400
    assert hashlib.sha256(a.astype("<f4", copy=False).tobytes()).hexdigest() == DECODED_SHA
    for zp in (ROOT / "submission" / f"{STEM}.zip", DOCS / "downloads/h97-rdva-candidate.zip"):
        with zipfile.ZipFile(zp) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".tif")]
            assert len(names) == 1 and z.read(names[0]) == canonical.read_bytes()
            assert z.testzip() is None


def test_h97_gates_distinguish_decoded_identity_from_near_dot_stop():
    card = _load("evidence/h97_rdva_run_card.json")
    assert card["verdict"] == "negative"
    assert card["download_ok"] is True
    assert card["submit_ok"] is False and card["approved_for_weekly_slot"] is False
    assert card["submission_slots_used"] == 0
    assert card["raster"]["sha256"] == FILE_SHA
    assert card["raster"]["decoded_sha256"] == DECODED_SHA
    assert card["full_validator_result"]["ok"] is True
    assert not card["full_validator_result"]["problems"]
    assert len(card["note"]) == card["note_chars"] <= 140
    uniq = card["uniqueness"]
    assert uniq["identical_to_a_prior"] is False
    assert uniq["distinct_from_every_comparable_prior"] is True
    assert uniq["n_priors_compared"] == 718
    assert uniq["audit_complete"] is False and len(uniq["incomparable_priors"]) == 1
    assert uniq["max_jaccard"] < 0.10
    assert uniq["distinct_by_decoded_values_or_shape"] is True
    file_identity = uniq["file_byte_identity"]
    assert file_identity["inventory_entries"] == 719
    assert file_identity["same_size_entries"] == 0
    assert file_identity["distinct_from_every_inventory_file"] is True
    lane = card["registry_correlation_overlap"]
    assert lane["surface_max_spearman"] < 0.90
    assert lane["surface_literal_verdict"] == "PASS"
    assert lane["final_dot_max_near_3px_fraction"] > 0.70
    assert lane["final_dot_literal_verdict"] == "DUPLICATE/STOP"
    assert card["literal_lane_stop"] is True
    ntu = card["not_the_union"]
    assert ntu["gate"] and not ntu["equals_equal_budget_union_field"]
    assert ntu["jaccard_union_field"] < 0.99 and ntu["dots_outside_union_field"] > 0


def test_h97_reasoning_is_complete_for_declared_scopes():
    card = _load("evidence/h97_rdva_run_card.json")
    reason = ROOT / card["reasoning"]["a_only_path"]
    segments = ROOT / card["reasoning"]["pseudo_segments_path"]
    with reason.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with segments.open(newline="", encoding="utf-8") as fh:
        segrows = list(csv.DictReader(fh))
    assert len(rows) == card["reasoning"]["a_only_rows"] == 2
    assert len(segrows) == card["reasoning"]["pseudo_A_to_B_segments"] == 578
    assert all(r["geological_reasoning"] and r["named_non_fault_mimics"] for r in rows)
    assert all("not an independently mapped" in r["verification_status"] for r in rows)
    assert all(r["direction"] == "A->B" and r["named_non_fault_mimics"] for r in segrows)


def test_h97_rdva_parallel_archive_download_but_never_slot_approved():
    archived = _load(f"docs/data/submission_{STEM}.json")
    current = _load("docs/data/submission.json")
    assert archived["file"] == f"{STEM}.tif"
    assert current["file"] != archived["file"], "parallel archive must not replace global current"
    assert (ROOT / "submission/LATEST.txt").read_text().strip() == current["file"]
    assert (ROOT / "docs/submission/LATEST.txt").read_text().strip() == current["file"]
    assert (ROOT / "submission/H97_RDVA_LATEST.txt").read_text().strip() == archived["file"]
    assert archived["download_ok"] is True and archived["submit_ok"] is False
    assert archived["approved_for_weekly_slot"] is False and archived["promoted"] is False
    assert archived["round"] == "H97-RDVA" and archived["original_frozen_round"] == "H97"
    for page in ("h97-rdva.html", "h97-rdva-executive-summary.html"):
        text = (DOCS / page).read_text(encoding="utf-8")
        assert "OK TO DOWNLOAD" in text.upper()
        assert "OK TO SUBMIT" in text.upper()
        assert "h97-rdva-candidate.tif" in text
        assert "DO NOT" in text.upper()
        assert "PARALLEL ARCHIVE" in text.upper()
    assert (DOCS / "index.html").read_text().count("<!--H97-RDVA-ARCHIVE-START-->") == 1


def test_h97_irregularities_and_public_receipts_are_current_and_portable():
    registry = _load("registry/irregularities.json")
    published = _load("docs/data/irregularities.json")
    assert published == registry
    ids = {e["id"] for e in registry["entries"]}
    assert {f"IR-H97-RDVA-{i:03d}" for i in range(1, 7)} <= ids
    for path in (
        "evidence/h97_rdva_run_card.json", "evidence/h97_rdva_lane_dots.json",
        "docs/data/h97_rdva_run_card.json", f"docs/data/submission_{STEM}.json",
    ):
        assert "/home/user/GEMSDOE52" not in (ROOT / path).read_text()


def test_h82_shared_verified_writer_is_atomic(tmp_path):
    # Regression for IR-H97-RDVA-001: no in-progress destination and no temporary files survive.
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_h82
    a = np.arange(10000, dtype=np.float32)
    p = tmp_path / "channel.npy"
    digest, attempts = run_h82.save_verified(p, a)
    assert attempts >= 1
    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest
    assert np.array_equal(np.load(p), a)
    assert not list(tmp_path.glob(".*.tmp-*.npy"))
