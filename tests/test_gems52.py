"""Comprehensive end-to-end verification tests for GEMSDOE32 (Passes 1, 2, and 3)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import rasterio

from gems52.metric import dti_binary, dti_bruteforce, dti_exact
from gems52.paths import ROOT, data_dir, docs_dir, downloads_dir, evidence_dir
from gems52.submission import audit_geotiff, sha256_file


def _require_inputs(*names):
    """Skip (never silently pass) when a gitignored competition input is absent.

    ``data/`` is gitignored by design, so a fresh clone and CI have no rasters until
    ``bash scripts/download_competition_data.sh`` has run.  A test that needs one must say so
    explicitly rather than fail the build or, worse, pass vacuously.  IR-32-CI-01.
    """
    import pytest
    d = data_dir()
    missing = [n for n in names if not (d / n).exists()]
    if missing:
        pytest.skip(f"competition input(s) absent from {d}: {', '.join(missing)} — run "
                    f"bash scripts/download_competition_data.sh first")


def test_dti_exact_matches_bruteforce():
    rng = np.random.default_rng(32)
    foot = np.ones((48, 48), dtype=bool)
    foot[:4, :] = False
    pred = (rng.random((48, 48)) < 0.04) & foot
    gt = (rng.random((48, 48)) < 0.03) & foot

    fast = dti_binary(pred, gt, foot)
    exact = dti_exact(np.where(foot, pred.astype(np.float32), np.nan), gt.astype(np.float32), foot)
    brute = dti_bruteforce(pred.astype(np.float32), gt.astype(np.float32))

    assert abs(fast["dti"] - brute["dti"]) < 1e-9
    assert abs(exact["dti"] - brute["dti"]) < 1e-9
    assert abs(fast["tp"] - brute["tp"]) < 1e-9
    assert abs(fast["fp"] - brute["fp"]) < 1e-9


def test_data_restore_and_sentinel_sanitization_manifests():
    _require_inputs("training_features.tif")
    restore = json.loads((ROOT / "data" / "restore_receipt.json").read_text())
    # 23 hash-pinned files (4 core + 7 external + 12 scored) per registry/data_manifest.json
    assert restore["verified_files_count"] == 23
    assert all(f["status"] == "present" for f in restore["files"])

    prep = json.loads((ROOT / "data" / "prepared_manifest.json").read_text())
    assert prep["grid"]["epsg"] == 32611
    assert prep["grid"]["height"] == 3730
    assert prep["grid"]["width"] == 3292
    assert prep["counts"]["footprint_valid_pixels"] == 5_167_373
    assert prep["counts"]["positive_catalogue_label_pixels"] == 60_988
    assert prep["counts"]["total_sentinel_band_pixels_inside_footprint"] == 58_171
    assert len(prep["bands"]) == 19


def test_d28_forensic_autopsy_verified():
    # GEMSDOE52 ships a re-derived forensic autopsy (see scripts/run_d28_autopsy.py equivalent)
    # that records the pixel-identical re-read of the three pinned reference artifacts.  We do
    # NOT pin the exact emitted-pixel count here -- the upstream LB scores (0.2600, 0.2477,
    # 0.1922) are owner-reported, not measured by us, so we only assert the structural shape.
    autopsy = json.loads((evidence_dir() / "d28_forensic_autopsy.json").read_text())
    assert len(autopsy["verified_reproductions_pixel_identical"]) == 3
    for rep in autopsy["verified_reproductions_pixel_identical"]:
        assert "leaderboard_dti" in rep
        assert "emitted_pixels" in rep
        assert rep["max_abs_diff_vs_ref"] == 0.0  # we re-read the bytes; they are identical

    chain = autopsy["ablation_chain_h19_5_to_d15_to_d28"]
    assert chain["H19-5-Dense-Backbone"]["emitted_pixels"] > 50_000
    assert chain["D1.5-Thinned-H19-5"]["emitted_pixels"] > 30_000
    assert chain["D2.8-Poisson300m-Ref"]["emitted_pixels"] > 30_000
    # the chain must be strictly nested: D1.5 subset of H19-5; D2.8 subset of H19-5
    assert chain["D1.5-Thinned-H19-5"]["strict_subset_of_h19_5"] is True
    assert chain["D2.8-Poisson300m-Ref"]["strict_subset_of_h19_5"] is True


def test_bo_surrogate_and_holdout_improvements():
    """GEMSDOE52 ships its own holdout-surrogate log under data/holdout_surrogate_log.json.

    This test asserts the *structural* properties of the log (presence of evaluations and
    diagnostics, plus the canonical ordering of the drift-corrected instrument over the
    catalogue-hidden proxy) without pinning specific candidate IDs from the GEMSDOE32
    predecessor repo -- GEMSDOE52's hypothesis family is different.
    """
    _require_inputs("training_features.tif")
    p = ROOT / "data" / "holdout_surrogate_log.json"
    if not p.exists():
        pytest.skip(f"{p} not present; run scripts/build_submission.py to generate it")
    log_json = json.loads(p.read_text())
    assert "evaluations" in log_json
    assert "diagnostics" in log_json
    assert len(log_json["evaluations"]) >= 1, "at least one evaluation must be logged"
    diag = log_json["diagnostics"]
    if "correlations" in diag:
        corr = diag["correlations"]
        # The drift-corrected instrument should always rank live scores better than the
        # raw catalogue proxy.  This is the structural property the predecessor repo
        # discovered and we inherit.
        assert corr.get("drift_corrected_spearman", 0) > corr.get("catalogue_hidden_spearman", 0)


def test_all_12_submission_geotiffs_pass_range_01_audit():
    _require_inputs("sample_submission.tif", "labels.tif")
    ddir = data_dir()
    with rasterio.open(ddir / "sample_submission.tif") as src:
        foot = np.isfinite(src.read(1))
    with rasterio.open(ddir / "labels.tif") as src:
        labels = np.isfinite(src.read(1)) & (src.read(1) > 0) & foot

    manifest_path = downloads_dir() / "submissions_manifest.json"
    if not manifest_path.exists():
        import pytest
        pytest.skip("docs/downloads/submissions_manifest.json is absent: the parallel session's 12 "
                    "submission GeoTIFFs are gitignored and are not shipped in this checkout, so "
                    "this audit cannot run here. It is not a silent pass -- see IR-32-CI-01.")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["validator_range_fix_verified"] is True
    assert manifest.get("portal_illegal") == [], "the audit found a portal-illegal artifact"
    # scripts/audit_shipped.py rebuilds this manifest from the files actually on disk, so it lists
    # every artifact the repository ships (27 as of the H33 round), not only the six the pipeline's
    # own step 6 wrote.
    subs = manifest["submissions"]
    assert len(subs) >= 6, f"expected at least the 6 pipeline artifacts, got {len(subs)}"

    seen_filenames = set()
    for sub in subs:
        fname = sub["file"]
        assert fname not in seen_filenames, f"{fname} appears twice in the manifest"
        seen_filenames.add(fname)
        tif_path = downloads_dir() / fname
        assert tif_path.exists(), f"manifest lists a file that is not on disk: {fname}"
        assert sha256_file(tif_path) == sub["sha256"], f"digest mismatch for {fname}"
        # Mode is inferred from what the file actually writes outside the footprint -- never from
        # the filename and never from the nodata tag, because
        # `gems52-h19-5-smoothmaxcov-44090-zeros.tif` carried `nodata = NaN` on an all-finite
        # raster (IR-34-NODATA-01), so the tag is not trustworthy.
        with rasterio.open(tif_path) as ds:
            _arr, _nd = ds.read(1), ds.nodata
        _out = _arr[~foot]
        if bool(np.isnan(_out).all()):
            mode = "nan"
        elif bool(np.all(_out == 0.0)):
            mode = "zeros"
        else:                       # neither convention: fail loudly rather than guess
            raise AssertionError(
                f"{fname} writes {np.unique(_out)[:4]} outside the footprint; it follows neither "
                "the zeros nor the NaN convention")
        # IR-34-NODATA-01: a nodata tag that contradicts the file's own content is portal risk.
        if _nd is not None and np.isnan(_nd) and not np.isnan(_arr).any():
            raise AssertionError(
                f"{fname} carries nodata=NaN but contains no NaN; that tag/content mismatch is the "
                "configuration the DrivenData validator could reject (IR-34-NODATA-01)")
        audit = audit_geotiff(tif_path, foot, labels, mode=mode)
        assert audit["all_checks_passed"] is True, \
            f"{fname} failed the 12-point validator: {audit.get('failed_checks')}"


def test_docs_and_readme_integrity():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    index_html = (docs_dir() / "index.html").read_text(encoding="utf-8")
    exec_html = (docs_dir() / "executive-summary.html").read_text(encoding="utf-8")

    # Core values must appear on every public-facing page
    for text in (readme, index_html):
        assert "Maximize P(Win)" in text
        assert "Own the Outcome" in text

    # The README must reference the DrivenData submission validator error string so a human
    # reviewer immediately knows we addressed the "Predicted values must be in range [0, 1]"
    # problem in src/gems52/submission.py.
    assert "Predicted values must be in range [0, 1]" in readme

    # The site must headline the GEMSDOE52 submission TIF (a stable substring)
    assert "gemsdoe52-cotrain-a-b-disagreement-v2-flank3" in index_html
    assert "gemsdoe52-cotrain-a-b-disagreement-v2-flank3" in exec_html

    # Check every local href/src in docs/index.html and docs/executive-summary.html resolves
    for page_name, content in (("index.html", index_html), ("executive-summary.html", exec_html)):
        refs = re.findall(r'(?:href|src)="([^"#]+)"', content)
        for ref in refs:
            if ref.startswith(("http://", "https://", "mailto:", "javascript:")):
                continue
            target = (docs_dir() / ref).resolve()
            assert target.exists(), f"Broken local reference {ref} in docs/{page_name} -> {target}"
