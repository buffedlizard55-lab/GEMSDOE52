"""The published site is a rendering of the repository, never a hand-typed page.

The two properties that matter operationally are checked here by *re-reading the written bytes*:

* the root pages (which GitHub Pages actually serves -- the repository's Pages source is ``main:/``,
  i.e. the repository root, not ``docs/``) must link at files that exist on disk, so the one-click
  download can never be a dead button (IR-34-ROOT-01);
* the download the site headlines must be the download the registry declares primary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"


def _require_inputs(*names: str):
    missing = [n for n in names if not (SITE / n).exists()]
    if missing:
        pytest.skip(f"site not built in this checkout: {missing}")


def test_root_pages_link_to_the_primary():
    _require_inputs("index.html", "downloads")
    sub = json.loads((ROOT / "registry" / "submission_build.json").read_text())
    primary = sub["file"]["path"]
    assert (ROOT / primary).is_file(), f"registry primary {primary} is not on disk"

    root_pages = sorted(ROOT.glob("*.html"))
    assert root_pages, "no root .html pages found"
    for page in root_pages:
        html = page.read_text()
        # every local href/src on the page must resolve to a real file
        for rel in re.findall(r'(?:href|src)="([^"#]+?)"', html):
            if rel.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            target = (page.parent / rel).resolve()
            assert target.is_file(), f"{page.name} links at missing file: {rel}"
        # and the page must offer the primary download, correctly prefixed
        assert "docs/downloads/" in html or page.name == "index.html" and True
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert hrefs, f"{page.name} offers no download at all"
        assert any(Path(h).name == Path(primary).name for h in hrefs), \
            f"{page.name} does not headline the registry primary {Path(primary).name}"


def test_docs_pages_link_to_the_primary():
    _require_inputs("index.html")
    sub = json.loads((ROOT / "registry" / "submission_build.json").read_text())
    primary = Path(sub["file"]["path"]).name
    for page in sorted(SITE.glob("*.html")):
        html = page.read_text()
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert hrefs, f"{page.name} offers no download at all"
        assert any(Path(h).name == primary for h in hrefs), \
            f"{page.name} does not headline the registry primary {primary}"


def test_submission_note_fits_the_portal_budget():
    sub = json.loads((ROOT / "registry" / "submission_build.json").read_text())
    # DrivenData's Note field is capped at 200 characters (GEMSDOE28 measured 192/200 for its own).
    assert len(sub["note"]) <= 200, f"note is {len(sub['note'])} chars; portal caps it at 200"
    assert sub["name"] and sub["file"]["sha256"]


def test_registry_and_site_agree_on_the_hypothesis_count():
    _require_inputs("hypotheses.html")
    hyp = json.loads((ROOT / "registry" / "hypotheses.json").read_text())
    ids = [h["id"] for h in hyp["hypotheses"]]
    assert len(ids) == len(set(ids)), "duplicate hypothesis id in the registry"
    html = (SITE / "hypotheses.html").read_text()
    for h in hyp["hypotheses"]:
        assert h["id"] in html, f"{h['id']} is registered but not rendered on the hypotheses page"
