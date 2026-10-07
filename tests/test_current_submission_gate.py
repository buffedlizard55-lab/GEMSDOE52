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


def test_h56_is_downloadable_but_not_slot_approved() -> None:
    sub = json.loads((DOCS / "data/submission.json").read_text())
    gate = json.loads((DOCS / "data/h56_slot_gate_review_2026-10-07.json").read_text())
    verify = json.loads((DOCS / "data/gems52-h56-verify.json").read_text())
    scope = json.loads((DOCS / "data/h56_a_only_reasoning_scope_2026-10-07.json").read_text())

    assert (ROOT / "submission/LATEST.txt").read_text().strip() == sub["file"]
    assert sub["approved_for_weekly_slot"] is False
    assert gate["decision"]["approved_for_weekly_slot"] is False
    assert gate["spatial_holdout"]["h56_comparable_holdout_receipt_found"] is False
    assert gate["leaderboard_score_to_filename_mapping_authenticated"] is False
    assert verify["identical_to_any_prior"] == []
    assert verify["priors_checked"] == 33
    assert verify["novel_px"] == 12941
    assert verify["min_NN_separation_ok"] is False
    assert gate["postbuild_decoded_pattern_review"]["derived_arm_cells_with_accessible_prior_support"] == 2059
    assert scope["status"].startswith("NOT PRODUCED")

    canonical = DOWNLOADS / sub["file"]
    short = DOWNLOADS / "h56-candidate.tif"
    assert sha(canonical) == sub["sha256"]
    assert short.read_bytes() == canonical.read_bytes()
    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert np.isfinite(data).all()
        assert set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == 40517

    canonical_zip = DOWNLOADS / (sub["file"][:-4] + ".zip")
    short_zip = DOWNLOADS / "h56-candidate.zip"
    assert canonical_zip.read_bytes() == short_zip.read_bytes()
    with zipfile.ZipFile(short_zip) as archive:
        assert archive.namelist() == [sub["file"]]
        assert archive.read(sub["file"]) == canonical.read_bytes()


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
