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
H56_NAME = "gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif"
H56_SHA = "c391ae7a5d0d4b25c69f219110d808dffbe08fa0148c0241984eca9590edc4e6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_h56_is_a_synthetic_demo_not_slot_approved() -> None:
    sub = json.loads((DOCS / "data/submission.json").read_text())
    receipt = json.loads((DOCS / "data/submission_h56.json").read_text())
    page = (DOCS / "h56-cotrain.html").read_text()

    assert (ROOT / "submission/LATEST.txt").read_text().strip() == H56_NAME
    assert sub["file"] == H56_NAME
    assert sub["sha256"] == receipt["sha256"] == H56_SHA
    assert sub["approved_for_weekly_slot"] is False
    assert sub["synthetic"] is True
    assert sub["artifact_status"].startswith("RESEARCH ONLY — SYNTHETIC")
    assert sub["submission_slots_used"] == 0
    assert sub["slot_gate"]["approved_for_weekly_slot"] is False
    assert "synthetic" in receipt["holdout"]["note"].lower()
    assert receipt["format_gate"]["ok"] is True
    assert receipt["format_gate"]["mass_outside_footprint"] == 0
    assert "0 on catalogue" in receipt["provenance_note"]
    assert receipt["uniqueness"]["canonical_pattern_unique"] is True
    assert receipt["uniqueness"]["research_publication_ok"] is True
    assert receipt["not_union"]["is_literal_union"] is False
    assert receipt["not_union"]["is_merely_union"] is False
    assert len(sub["submission_note"]) <= 200
    assert "synthetic demo" in page.lower()
    assert "do not spend a weekly slot" in page.lower()
    assert "do not upload until you rerun on real data" in page.lower()

    canonical = DOWNLOADS / H56_NAME
    source = ROOT / "submission" / H56_NAME
    assert sha(canonical) == sha(source) == H56_SHA
    assert canonical.stat().st_size == sub["bytes"] == 141106
    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert np.isfinite(data).all()
        assert set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == 37654
        with rasterio.open(ROOT / "data/sample_submission.tif") as template:
            footprint = np.isfinite(template.read(1))
        assert int(footprint.sum()) == receipt["format_gate"]["valid_px"]
        assert np.all(data[~footprint] == 0)

    canonical_zip = DOWNLOADS / (H56_NAME[:-4] + ".zip")
    with zipfile.ZipFile(canonical_zip) as archive:
        assert archive.testzip() is None
        tiffs = [name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))]
        assert len(tiffs) == 1 and archive.read(tiffs[0]) == canonical.read_bytes()
        assert "SUBMISSION_NOTE.txt" in archive.namelist()
        assert "evidence.json" in archive.namelist()
        assert sub["submission_note"] in archive.read("SUBMISSION_NOTE.txt").decode()

    # This old alias remains tied to the separately archived H56 core-continuation artifact; it is
    # not the current H56 co-training TIFF and must not be presented as the current download.
    historical_name = "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif"
    historical = DOWNLOADS / historical_name
    short = DOWNLOADS / "h56-candidate.tif"
    assert short.read_bytes() == historical.read_bytes()
    assert short.read_bytes() != canonical.read_bytes()
    old_page = (DOCS / "h56.html").read_text()
    assert "HISTORICAL H56 CORE-CONTINUATION ARCHIVE" in old_page
    assert "h56-cotrain.html" in old_page


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


def test_h54_archive_publisher_cannot_move_above_or_replace_h56(monkeypatch, tmp_path) -> None:
    index = tmp_path / "index.html"
    index.write_text('<main><!--H56BAR-->current H56<!--/H56BAR--><!--H55BAR-->history<!--/H55BAR--></main>')
    archive = json.loads((DOCS / "data/h54_audit.json").read_text())
    bar = make_site_pages.download_bar(archive)

    assert make_site_pages.insert_bar(index, bar) is True
    result = index.read_text()
    assert result.index("<!--H56BAR-->") < result.index("<!--H54BAR-->")
    assert "historical only; not the current H56 artifact" in result
    assert "Do not submit this H54 archive" in result

    summary = tmp_path / "executive-summary.html"
    summary.write_text('<main><!--H56-EXEC-BAR-->current H56<!--/H56-EXEC-BAR--></main>')
    before = summary.read_text()
    assert make_site_pages.insert_bar(summary, bar) is False
    assert summary.read_text() == before
