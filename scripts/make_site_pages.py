#!/usr/bin/env python3
"""Generate the H54 historical audit page without replacing current H75 status pages.

Why this script writes one page and edits two, instead of owning the site: PR #9 (the R2 round) added
`scripts/publish_site_r2.py`, which regenerates `index.html`, `executive-summary.html`,
`validation.html`, `forensics.html`, `method.html`, `hypotheses.html`, `sources.html`,
`irregularities.html`, `feed.html`, `h53.html`, `downloads/index.html` **and `README.md`**, and
`scripts/check_site.py` now enforces invariants of those generated pages (arm means rendered from the
current receipt; a failed-gate warning on the two top pages). An earlier version of this script wrote
`validation.html`, `feed.html`, `irregularities.html` and `sources.html` from its own templates, which
clobbered the R2 site and failed those checks. It does not do that any more.

The H54 archive page reads its dedicated `docs/data/h54_audit.json` receipt, never the current
submission pointer. It is explicitly historical and preserves no portal name/note fields. The shared
homepage is updated only if its legacy H56 anchor still exists; otherwise insertion safely skips.
"""
from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"
NAV = ('<a href="index.html">Overview</a><a href="executive-summary.html">Research status</a>'
       '<a href="h54.html">H54 historical audit</a><a href="h75-executive-summary.html">H75 stop status</a>'
       '<a href="validation.html">Validation</a>'
       '<a href="forensics.html">0.2778 evidence</a><a href="irregularities.html">Irregularities</a>'
       '<a href="sources.html">Sources</a>')


def esc(x) -> str:
    return html.escape(str(x))


def load(name: str) -> dict:
    p = EV / f"{name}.json"
    if not p.exists():
        return {"__missing__": str(p)}
    return json.loads(p.read_text())


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="Historical H54 research artifact; prior score inversions and zero-credit claims are withdrawn. Not for submission.">'
            f'<title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css">'
            f'</head><body><aside role="alert" style="padding:14px 22px;background:#fef2f2;color:#7f1d1d;border:2px solid #991b1b"><strong>H75: DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION.</strong> H75 is terminal; no override, waiver, or rerun is authorized. This H54 page is a historical archive, not submission approval. <a href="h75-executive-summary.html">H75 stop status</a>.</aside><a class="skip" href="#main">Skip to content</a>'
            f'<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{NAV}</nav></header>'
            f'<main id="main">{body}</main>'
            f'<footer>Competition 306 · every figure on this page is rendered from '
            f'<code>evidence/*.json</code> by <code>scripts/make_site_pages.py</code></footer>'
            f'</body></html>')


def download_bar(sub: dict) -> str:
    """Render the H54 research archive from its own receipt, without portal identifiers."""
    if not sub.get("exists"):
        return ('<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
            '<strong>H54 historical research archive</strong>'
            '<small>No H54 artifact is recorded in its audit receipt.</small>'
            '<small>NOT FOR SUBMISSION. No upload steps, override, name, or note are provided.</small>'
            '</div></div><!--/H54BAR-->')
    return (
        '<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
        '<strong>H54 historical research GeoTIFF — NOT FOR SUBMISSION</strong>'
        f'<small>{esc(sub.get("file"))} · {esc(sub.get("bytes"))} bytes · '
        f'SHA-256 <code>{esc((sub.get("sha256") or "")[:16])}…</code></small>'
        f'<small>Local format check: {esc(sub.get("format_ok"))}; global decoded-pattern uniqueness: '
        f'{esc(sub.get("global_decoded_pattern_uniqueness", "unknown"))}; weekly-slot approval: NO. '
        'Local format checks do not establish organizer acceptance.</small></div>'
        f'<a class="button" href="{esc(sub.get("download"))}" download>Download H54 research TIFF</a>'
        f'<a class="button secondary" href="{esc(sub.get("download_zip"))}" download>Research ZIP</a>'
        f'<a class="button secondary" href="h54.html">H54 evidence</a>'
        '</div><!--/H54BAR-->')


def insert_bar(path: pathlib.Path, bar: str) -> bool:
    """Update an existing H54 archive slot; otherwise refuse safely (never rewrite the current home page)."""
    if not path.exists():
        return False
    s = path.read_text()
    if "<!--H54BAR-->" in s and "<!--/H54BAR-->" in s:
        a = s.index("<!--H54BAR-->")
        b = s.index("<!--/H54BAR-->", a) + len("<!--/H54BAR-->")
        path.write_text(s[:a] + bar + s[b:])
        return True
    if path.name != "index.html":
        return False
    anchor = "<!--/H56BAR-->"
    if anchor not in s:
        return False
    index = s.index(anchor) + len(anchor)
    path.write_text(s[:index] + bar + s[index:])
    return True


def table(head, rows) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(
        f'<td class="num">{esc(c)}</td>' if isinstance(c, (int, float)) else f"<td>{esc(c)}</td>"
        for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def h54_body() -> str:
    """Historical H54 page; superseded score inversion is not a current measurement."""
    sub = json.loads((DOCS / "data/h54_audit.json").read_text())
    name = esc(sub.get("file", "gems52-h54-revealed-core-strike-continuation-50517px-r1.tif"))
    sha = esc(sub.get("sha256", ""))
    nbytes = esc(sub.get("bytes", "unknown"))
    pixels = esc(sub.get("emitted_pixels", sub.get("pixels", sub.get("format", {}).get("n_nonzero", "unknown"))))
    status = ('<div class="notice bad" role="alert"><strong>H54 IS A HISTORICAL RESEARCH ARTIFACT — NOT FOR SUBMISSION.</strong>'
              '<p>The previous revealed-preference inversion and its asserted zero-credit 200 m corridor are withdrawn. '
              'They relied on owner-reported score/file associations and assumptions that do not identify hidden-truth credit. '
              'This archive gives no upload procedure, portal name/note, owner override, or slot recommendation.</p></div>')
    local = ('<h2>What can still be stated</h2><ul>'
             '<li>A local historical raster and its byte-level properties can be preserved for audit; local format validity is not portal acceptance or submission eligibility.</li>'
             '<li>The local H33-labelled 37,654-cell bitmap is a strict subset of a separate owner-reported 44,090-cell bitmap: 6,436 removed, none added. This does not authenticate either score association or explain a score change.</li>'
             '<li>The removed cells are 100–200 m from the local known-fault mask, but that distance is not a credit measurement. Official staff says the known mask is pixel-exact, only new-fault truth is scored, and new-fault truth may lie within 300 m of known traces.</li>'
             '<li>Historical |G| estimates, atom-credit tables, and score projections are conditional scenario arithmetic, not HOLDOUT-DTI, public-board measurements, or organizer-confirmed scores.</li>'
             '</ul>')
    return (f'<div class="eyebrow">H54 · historical audit · superseded analysis</div>'
            f'<h1>H54: preserve the artifact, withdraw the causal story.</h1>{status}'
            f'<section class="download-bar"><div><strong>{name}</strong>'
            f'<small>{nbytes} bytes · {pixels} emitted cells · SHA-256 <code>{sha}</code></small>'
            '<small>Research download only. The local format receipt does not establish eligibility.</small></div>'
            f'<a class="button" href="downloads/h54-audit-only.tif" download>Download H54 research TIFF</a>'
            f'<a class="button secondary" href="downloads/h54-audit-only.zip" download>Research ZIP</a></section>'
            f'{local}<h2>Corrected score evidence</h2>'
            '<p>The saved public-board observation at 2026-10-09 20:18 UTC places extradr19 at 0.2778/rank 17 and the top row at 0.3774. It is a team-level observation, not a TIFF-hash receipt. The H33 file association remains owner-reported; no organizer-confirmed receipt binds a file hash to 0.2778.</p>'
            '<p>See <a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a>, '
            '<a href="forensics.html">the 0.2778 evidence review</a>, and '
            '<a href="../registry/irregularities.json">IR-52-003</a> for provenance and limits.</p>'
            '<p><a href="data/h54_audit.json">Dedicated H54 archive audit (published record)</a> · '
            '<a href="data/submission_gems52-h54-revealed-core-strike-continuation-50517px-r1.json">H54 artifact receipt</a> · '
            '<a href="data/h54_artifact_review_2026-10-07.json">H54 artifact review</a> · '
            '<a href="../evidence/revealed_submission_audit.json">Broader historical revealed-submission analysis (superseded for causal interpretation)</a></p>')


def main() -> int:
    (DOCS / "h54.html").write_text(page("H54 revealed preference", h54_body()))
    print("wrote docs/h54.html")
    sub = json.loads((DOCS / "data/h54_audit.json").read_text())
    bar = download_bar(sub)
    ok = insert_bar(DOCS / "index.html", bar)
    print(("updated" if ok else "SKIPPED safely") + " the H54 audit bar in docs/index.html")
    print("left docs/executive-summary.html (current status hub) untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
