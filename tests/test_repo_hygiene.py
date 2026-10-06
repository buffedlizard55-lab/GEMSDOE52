"""Repository-hygiene tests.

These exist because of a real, blocking defect: ``README.md`` and ``.gitignore`` were **merged to
``main`` with unresolved conflict markers** (``<<<<<<< HEAD`` at README line 1, ``>>>>>>> origin/main``
at line 570).  The repository's own front page was unreadable and the ``.gitignore`` rules that
re-include the downloadable GeoTIFFs sat inside the conflicted region.  See IR-32-MERGE-01.

Each test below pins one property that would have caught it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKER = re.compile(rb"^(<{7} |={7}$|>{7} )", re.MULTILINE)

# text-ish files that must never contain a conflict marker
SUFFIXES = {".md", ".py", ".html", ".json", ".yml", ".yaml", ".css", ".txt", ".sh", ".cfg", ".toml"}
SKIP_DIRS = {".git", "data", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


def _tracked_text_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    for rel in out.stdout.splitlines():
        p = ROOT / rel
        if not p.is_file() or p.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p, rel


def test_no_conflict_markers_anywhere_in_tracked_files():
    offenders = []
    for p, rel in _tracked_text_files():
        try:
            if MARKER.search(p.read_bytes()):
                offenders.append(rel)
        except OSError:
            continue
    assert not offenders, f"unresolved merge-conflict markers in: {offenders}"


def test_gitignore_does_not_contain_conflict_markers():
    gi = (ROOT / ".gitignore").read_bytes()
    assert b"<<<<<<<" not in gi and b">>>>>>>" not in gi


def test_the_downloadable_artifact_is_trackable():
    """A bare ``downloads/`` ignore pattern would exclude ``docs/downloads/`` and silently make
    every deliverable untrackable -- git cannot re-include a file whose parent directory is
    excluded.  The pattern must be anchored to the repository root.

    This test asserts (a) at least one submission-style ``*-zeros.tif`` exists under
    ``docs/downloads/``, and (b) git does not ignore that file.  It does NOT pin a single
    hard-coded filename -- that approach was abandoned because every session may produce a
    new timestamped filename; what matters is that *whatever* the download is, git can track it.
    """
    d = ROOT / "docs" / "downloads"
    tifs = sorted(d.glob("*-zeros.tif")) if d.exists() else []
    assert tifs, "no *-zeros.tif under docs/downloads/ -- run scripts/build_submission.py first"
    target = tifs[-1].relative_to(ROOT).as_posix()  # latest by mtime
    rc = subprocess.run(["git", "check-ignore", "-q", "--", target], cwd=ROOT)
    assert rc.returncode == 1, f"{target} is git-ignored and would not be published"


def test_raw_data_is_ignored():
    rc = subprocess.run(["git", "check-ignore", "-q", "--", "data/raw/labels.tif"], cwd=ROOT)
    assert rc.returncode == 0, "raw competition data must never be committed"


@pytest.mark.parametrize("rel", [
    "README.md",
    "knowledge/02_the_ceiling_and_the_instrument.md",
    "docs/research/hypotheses-round2.md",
])
def test_required_documents_exist_and_are_non_trivial(rel):
    p = ROOT / rel
    assert p.exists(), rel
    assert p.stat().st_size > 500, f"{rel} looks empty"


def test_readme_leads_with_the_download():
    """The brief requires the one-click file to be obvious at the very beginning of the site."""
    text = (ROOT / "README.md").read_text()
    head = text[:6000]
    assert "ONE-CLICK" in head.upper()
    assert "docs/downloads/" in head
