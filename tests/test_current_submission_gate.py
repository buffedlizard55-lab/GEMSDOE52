"""Current artifact and archive integrity checks; local gates are not upload approval."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio

from scripts import make_site_pages

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"
H57_NAME = "gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb.tif"
H57_SHA = "a153cda1aae9f77249154b31a06d85f286cd669d56961dded0f0d79547018d7d"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_h57_is_downloadable_but_not_slot_approved() -> None:
    sub = json.loads((DOCS / "data/submission.json").read_text())
    receipt = json.loads((DOCS / "data/h57_submission.json").read_text())
    holdout = json.loads((DOCS / "data/h57_holdout.json").read_text())
    page = (DOCS / "h57.html").read_text()

    assert (ROOT / "submission/LATEST.txt").read_text().strip() == H57_NAME
    assert sub["file"] == receipt["file"] == H57_NAME
    assert sub["sha256"] == receipt["sha256"] == H57_SHA
    assert sub["approved_for_weekly_slot"] is False
    assert receipt["approved_for_weekly_slot"] is False
    assert receipt["artifact_status"].startswith("RESEARCH ONLY")
    assert receipt["submission_slots_used"] == 0
    assert receipt["portal_upload_performed"] is False
    assert receipt["official_score"] is None
    assert receipt["format"]["ok"] is True
    assert receipt["uniqueness"]["canonical_pattern_unique"] is True
    assert receipt["uniqueness"]["support_novelty_gate_ok"] is False
    assert receipt["uniqueness"]["n_priors_checked"] == 567
    assert receipt["not_union"]["not_merely_union"] is True
    assert receipt["slot_gate"]["scientific_gate_pass"] is False
    assert receipt["slot_gate"]["approved_for_weekly_slot"] is False
    assert len(sub["submission_note"]) <= 200
    assert "do not submit" in page.lower()
    assert "0/4" in page

    canonical = DOWNLOADS / H57_NAME
    source = ROOT / "submission" / H57_NAME
    assert sha(canonical) == sha(source) == H57_SHA
    assert canonical.stat().st_size == sub["bytes"] == 185891
    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        mask = ds.dataset_mask() > 0
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert np.isfinite(data[mask]).all()
        assert float(data[mask].min()) == 0.0 and float(data[mask].max()) == 1.0
        assert np.isnan(data[~mask]).all()
        assert int(mask.sum()) == 5167373
        assert int(np.count_nonzero(data[mask])) == 37654

    canonical_zip = DOWNLOADS / (H57_NAME[:-4] + ".zip")
    with zipfile.ZipFile(canonical_zip) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [H57_NAME]
        assert archive.read(H57_NAME) == canonical.read_bytes()

    assert len(holdout["folds"]) == 4
    mean_h57 = sum(f["arms"]["h57_disagreement_cotrain"]["dti"] for f in holdout["folds"]) / 4
    mean_b = sum(f["arms"]["view_B_supervised"]["dti"] for f in holdout["folds"]) / 4
    assert abs(mean_h57 - 0.1106647575835852) < 1e-12
    assert abs(mean_b - 0.15130526541812087) < 1e-12
    assert receipt["slot_gate"]["positive_paired_folds"] == 0
    assert receipt["slot_gate"]["mean_lift_over_strongest_matched_baseline"] < 0


def test_h57_unreconciled_provenance_and_train_boundary_limits_are_explicit() -> None:
    provenance = json.loads((ROOT / "docs/data/h57_execution_provenance.json").read_text())
    review = provenance["post_execution_review"]
    runner = review["runner_source_reconciliation"]
    boundary = review["pseudo_component_boundary_review"]
    inputs = review["input_restore_review"]

    assert runner["runner_hashes_reconciled"] is False
    assert runner["historical_runner_snapshots_available"] is False
    assert len({runner["recorded_holdout_runner_sha256"],
                runner["recorded_artifact_build_runner_sha256"],
                runner["current_checkout_runner_sha256"]}) == 3
    assert runner["current_checkout_runner_sha256"] == sha(ROOT / "scripts/run_h57_real.py")
    assert runner["matching_or_reviewed_modules"]["src/gems52/h57.py"]["matches_recorded_holdout"] is True
    spatial = runner["matching_or_reviewed_modules"]["src/gems52/spatial.py"]
    assert spatial["current_checkout_sha256"] == sha(ROOT / "src/gems52/spatial.py")
    assert spatial["review_change"].startswith("Documentation-only")
    assert boundary["registered_training_domain_only"] is True
    assert "cannot detect" in boundary["unobserved_boundary"]
    assert inputs["pinned_input_directory_present"] is False
    assert inputs["current_repository_data_matches_pins"] is False

    page = (DOCS / "h57.html").read_text().lower()
    irregularities = (DOCS / "irregularities.html").read_text().lower()
    assert "execution provenance is not fully reconciled" in page
    assert "runner hashes differ" in page
    assert "no pseudo pixels entered the evaluation region" in page
    assert "runner provenance is unresolved" in irregularities
    assert "clean reproduction is not possible" in irregularities


def test_h56_is_a_historical_synthetic_demo_not_current() -> None:
    receipt = json.loads((DOCS / "data/submission_h56.json").read_text())
    page = (DOCS / "h56-cotrain.html").read_text().lower()
    assert receipt["synthetic"] is True
    assert receipt.get("approved_for_weekly_slot") is not True
    assert receipt["stem"].startswith("gems52-h56-cotrain-")
    assert (ROOT / "submission/LATEST.txt").read_text().strip() != receipt["stem"] + ".tif"
    assert "synthetic demo" in page
    assert "do not spend a weekly slot" in page


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


def test_h54_archive_publisher_cannot_move_above_or_replace_h57(monkeypatch, tmp_path) -> None:
    index = tmp_path / "index.html"
    index.write_text('<main><!--H57BAR-->current H57<!--/H57BAR--><!--H55BAR-->history<!--/H55BAR--></main>')
    archive = json.loads((DOCS / "data/h54_audit.json").read_text())
    bar = make_site_pages.download_bar(archive)

    assert make_site_pages.insert_bar(index, bar) is True
    result = index.read_text()
    assert result.index("<!--H57BAR-->") < result.index("<!--H54BAR-->")
    assert "historical only; not the current H57 artifact" in result
    assert "Do not submit this H54 archive" in result

    summary = tmp_path / "executive-summary.html"
    summary.write_text('<main><!--H57-EXEC-BAR-->current H57<!--/H57-EXEC-BAR--></main>')
    before = summary.read_text()
    assert make_site_pages.insert_bar(summary, bar) is False
    assert summary.read_text() == before
