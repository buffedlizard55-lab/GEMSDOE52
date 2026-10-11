"""H75 is terminal: historical builders and publishers must be side-effect free under its stop."""
from __future__ import annotations

from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_h75_stop_blocks_legacy_builders_publishers_and_pointer_changes():
    docs = ROOT / "docs"
    submission = ROOT / "submission"
    protected = [
        docs / "index.html",
        docs / "executive-summary.html",
        docs / "downloads/index.html",
        docs / "h75-executive-summary.html",
        docs / "data/submission.json",
        docs / "data/feed.json",
        submission / "LATEST.txt",
        submission / "H60_LATEST.txt",
        submission / "H60C_LATEST.txt",
        submission / "H60D_LATEST.txt",
        submission / "H64_LATEST.txt",
        submission / "H66COVER_LATEST.txt",
        submission / "H71_LATEST.txt",
        ROOT / "index.html",
    ]
    before = {p: (p.exists(), p.read_bytes() if p.is_file() else None) for p in protected}
    assert "H75: DUPLICATE/STOP" in (docs / "index.html").read_text()
    assert "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in (
        docs / "h75-executive-summary.html"
    ).read_text()

    scripts = (
        "build_h60_submission.py",
        "build_h60d_submission.py",
        "publish_h60_site.py",
        "publish_h60c_site.py",
        "publish_site_h60d.py",
        "publish_h74_site.py",
        "publish_site_r3.py",
        "publish_ctd5.py",
        "publish_h58_site.py",
        "publish_h59_site.py",
        "publish_h61_site.py",
        "publish_h62_site.py",
        "publish_h63_site.py",
        "publish_h64_site.py",
        "publish_h66cover_site.py",
        "publish_h69_site.py",
        "publish_h71_site.py",
        "publish_site_h57.py",
        "publish_site_h59.py",
        "publish_site_r5.py",
    )
    for name in scripts:
        module = runpy.run_path(str(ROOT / "scripts" / name))
        assert module["main"]() in (0, None), name

    for name in ("h75_lane_place.py", "h75_write.py"):
        with pytest.raises(SystemExit, match="terminal DUPLICATE/STOP"):
            runpy.run_path(str(ROOT / "scripts" / name))

    after = {p: (p.exists(), p.read_bytes() if p.is_file() else None) for p in before}
    assert after == before
