"""Regression tests for timestamp-based R5 prior-set reconstruction.

R5 predates several parallel rounds.  In particular H75's TIFF filename carries a UTC date but no
clock time; failing to parse YYYYMMDD kept its pixels in R5's prior set and falsely changed the
historical novelty receipt.  A same-day date-only token remains conservative/ambiguous.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import runpy
import zipfile


_SITE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/check_site.py"))
_artifact_stamp = _SITE["_artifact_stamp"]
_is_later_than_build = _SITE["_is_later_than_build"]


def test_date_only_artifact_on_later_utc_day_is_excluded_from_r5_priors(tmp_path):
    artifact = tmp_path / "gems52-h75-dva-20261009.tif"
    artifact.touch()
    built = datetime(2026, 10, 8, 23, 51, 56)

    stamp, precise = _artifact_stamp(artifact)
    assert stamp == datetime(2026, 10, 9, 0, 0)
    assert precise is False
    assert _is_later_than_build(artifact, built) is True


def test_same_day_date_only_artifact_is_kept_as_conservative_prior(tmp_path):
    artifact = tmp_path / "parallel-round-20261008.tif"
    artifact.touch()
    built = datetime(2026, 10, 8, 23, 51, 56)

    assert _is_later_than_build(artifact, built) is False


def test_precise_timestamp_uses_time_of_day_not_just_date(tmp_path):
    artifact = tmp_path / "parallel-round-20261008T235200Z.tif"
    artifact.touch()
    built = datetime(2026, 10, 8, 23, 51, 56)

    stamp, precise = _artifact_stamp(artifact)
    assert stamp == datetime(2026, 10, 8, 23, 52)
    assert precise is True
    assert _is_later_than_build(artifact, built) is True


def test_r5_uses_emission_time_not_later_submission_wrapper_time(tmp_path):
    from json import dumps

    data_dir = tmp_path / "docs" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "r5_novel_emission.json").write_text(
        dumps({"generated_utc": "2026-10-08T23:40:33Z"}), encoding="utf-8"
    )
    (data_dir / "submission_r5.json").write_text(
        dumps({"generated_utc": "2026-10-08T23:51:56Z"}), encoding="utf-8"
    )

    stamp, precise = _SITE["_r5_build_stamp"](data_dir)
    assert stamp == datetime(2026, 10, 8, 23, 40, 33)
    assert precise is True


def test_every_public_download_zip_is_a_single_tiff_without_sidecars():
    downloads = Path(__file__).resolve().parents[1] / "docs" / "downloads"
    archives = sorted(downloads.glob("*.zip"))
    assert archives, "expected public research archives"
    for path in archives:
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            assert len(members) == 1, f"{path.name} has non-TIFF sidecars: {members}"
            assert members[0].lower().endswith((".tif", ".tiff")), path.name
            tiff = downloads / members[0]
            if tiff.is_file():
                assert archive.read(members[0]) == tiff.read_bytes(), path.name
            assert archive.testzip() is None, path.name
