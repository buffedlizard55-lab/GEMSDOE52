#!/usr/bin/env python3
"""Publish H60C's research-download-only status page from pinned audit receipts.

This script deliberately does not rewrite docs/h60c.html (the reviewed historical audit),
docs/index.html, or docs/executive-summary.html (the current CTD5 STOP page). It emits no
portal instructions, submission name, or note: H60C fails the final-dot uniqueness gate.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SUB = ROOT / "submission"
BUILD_PATH = "docs/data/h60c_build.json"
AUDIT_PATH = "evidence/uniqueness_audit_h60c_20261008.json"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def load(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        raise SystemExit(f"missing receipt {rel}; refusing to publish a placeholder status")
    return json.loads(path.read_text())


def status_record(build: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """Return a non-submission status receipt with no copyable portal identifiers."""
    fmt = build["format"]
    surface = audit["phases"]["surface"]
    dots = audit["phases"]["dots"]
    h33_rows = [row for row in audit["top_overlaps"]
                if row["path"] == "data/reference/h33-2-b2-zeros.tif"]
    if not h33_rows:
        raise SystemExit("uniqueness receipt lacks the H33 support row")
    h33 = h33_rows[0]

    rank_limit = float(surface["rank_threshold"])
    dot_limit = float(dots["near_threshold"])
    max_spearman = float(surface["max_spearman"])
    max_near = float(dots["max_near_3px_fraction"])
    rank_failed = max_spearman > rank_limit
    dot_failed = max_near > dot_limit
    audit_failed = bool(surface.get("error_count", 0) or dots.get("error_count", 0))
    gate_pass = not (rank_failed or dot_failed or audit_failed)

    # This page is intentionally a no-submit status. A future inventory update must not
    # silently turn this historic file into an upload candidate; the review is prospective.
    submission_ok = False
    return {
        "round": "H60C",
        "status": "RESEARCH DOWNLOAD ONLY — DO NOT SUBMIT",
        "download_ok_for_research": True,
        "submission_ok": submission_ok,
        "organizer_confirmed": False,
        "artifact": {
            "filename": build["file"],
            "sha256": build["sha256"],
            "bytes": int(build["bytes"]),
            "emitted_pixels": int(build["emitted_px"]),
            "source_receipt": BUILD_PATH,
        },
        "local_format_check": {
            "passed": bool(fmt["ok"]),
            "validation_class": fmt["validation_class"],
            "problems": list(fmt["problems"]),
            "caveat": "A local template/range pass is not organizer acceptance.",
        },
        "uniqueness_diagnostic": {
            "evidence_class": audit["evidence_class"],
            "inventory_scope": dots["scope"],
            "decoded_pattern_distinct_in_checked_inventory": bool(
                build["uniqueness"]["canonical_pattern_unique"]),
            "max_spearman": max_spearman,
            "spearman_limit": rank_limit,
            "max_final_dot_fraction_within_3px": max_near,
            "near_3px_limit": dot_limit,
            "rank_gate_failed": rank_failed,
            "final_dot_gate_failed": dot_failed,
            "gate_pass": gate_pass,
            "duplicate_stop": not gate_pass,
            "support_overlap_pixels": int(audit["candidate_px_inside_any_prior_support"]),
            "candidate_pixels": int(audit["candidate_nonzero"]),
            "share_inside_any_prior_support": float(
                audit["share_of_candidate_px_inside_any_prior_support"]),
            "h33_intersection_pixels": int(h33["intersection"]),
            "share_inside_h33_support": float(h33["share_of_candidate_in_prior"]),
            "receipt": AUDIT_PATH,
        },
        "holdout_status": (
            "The archived fold-mean hide-and-recover values are not comparable HOLDOUT-DTI; "
            "no organizer-confirmed score is claimed for this artifact."
        ),
        "no_slot_authorized": True,
    }


def nav(active: str) -> str:
    items = [
        ("index.html", "Overview"),
        ("executive-summary.html", "CTD5 status"),
        ("h60c.html", "H60C audit"),
        ("h60c-submission-status.html", "H60C download status"),
        ("hypotheses.html", "Hypotheses"),
        ("irregularities.html", "Limitations"),
        ("sources.html", "Sources"),
        ("downloads/index.html", "Downloads"),
    ]
    links = "".join(
        f'<a href="{url}"{" aria-current=page" if url == active else ""}>{label}</a>'
        for url, label in items
    )
    return (
        '<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>'
        f"{links}</nav></header>"
    )


def head(title: str, description: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="description" content="{esc(description)}">'
        f"<title>{esc(title)}</title>"
        '<link rel="stylesheet" href="style.css">'
        '<script src="site.js" defer></script></head><body>'
        '<a class="skip" href="#main">Skip to status</a>'
    )


def foot() -> str:
    return (
        '<footer>DOE GEMS competition 306 · Reproducible local research · '
        'Predictions are hypotheses for Phase-2 review, not verified faults or geothermal '
        'discoveries. <a href="irregularities.html">Limitations</a> · '
        '<a href="sources.html">Sources</a> · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a>'
        '</footer></body></html>'
    )


def render_status_page(build: dict[str, Any], audit: dict[str, Any]) -> str:
    """Render the H60C status page; intentionally contains no upload workflow or identifiers."""
    status = status_record(build, audit)
    artifact = status["artifact"]
    fmt = status["local_format_check"]
    unique = status["uniqueness_diagnostic"]
    size = build["format"]
    pct_any = 100 * unique["share_inside_any_prior_support"]
    pct_h33 = 100 * unique["share_inside_h33_support"]
    pct_near = 100 * unique["max_final_dot_fraction_within_3px"]
    pct_dot_limit = 100 * unique["near_3px_limit"]
    pct_rank = unique["max_spearman"]
    status_json = "data/h60c_submission.json"

    parts = [
        head(
            "H60C research archive status — do not submit · GEMSDOE52",
            "H60C is available for local research download only. Its final-dot uniqueness gate "
            "fails; do not submit it or spend a competition slot.",
        ),
        nav("h60c-submission-status.html"),
        '<main id="main"><div class="eyebrow">H60C · archived research artifact · status is not upload approval</div>',
        '<h1>Research download only.<br><strong>Do not submit H60C.</strong></h1>',
        '<div class="status" role="alert"><strong>DOWNLOAD FOR LOCAL RESEARCH: YES · '
        'SUBMIT TO COMPETITION: NO</strong><p>This is a format-checked research archive, not a '
        'unique submission candidate. The final-dot proximity rule fires against a registered '
        'spacing-five raster. No competition slot was used for this archive, and this page grants no selector approval.</p></div>',
        '<section class="download-bar" aria-label="H60C research download">',
        f'<div><strong>{esc(artifact["filename"])}</strong>',
        f'<small>{artifact["bytes"]:,} bytes · SHA-256 <code>{esc(artifact["sha256"])}</code></small>',
        f'<small>Local template/range check: {"PASS" if fmt["passed"] else "FAIL"} · '
        f'{esc(size["bands"])} band(s) · {esc(size["dtype"])} · {esc(size["crs"])} · '
        f'{size["width"]} × {size["height"]} · finite values in [0,1]</small></div>',
        '<a class="button" href="downloads/h60c-candidate.tif" download>'
        '↓ Download research TIFF — DO NOT SUBMIT</a>',
        '<a class="button" href="downloads/h60c-candidate.zip" download>'
        '↓ Download research ZIP — DO NOT SUBMIT</a>',
        '<a class="button secondary" href="h60c.html">Read the H60C research audit →</a>',
        '</section>',
        '<h2>Decision at a glance</h2>',
        '<div class="table-wrap"><table><thead><tr><th>question</th><th>status</th></tr></thead><tbody>',
        '<tr><td>OK to download for local research?</td><td><b>YES.</b> Downloading is not a competition upload.</td></tr>',
        '<tr><td>OK to submit this raster or spend a slot?</td><td><b>NO — DO NOT SUBMIT.</b> The final-dot gate fails; no selector approval is recorded.</td></tr>',
        f'<tr><td>Local file-format checks?</td><td><b>{"PASS" if fmt["passed"] else "FAIL"} locally.</b> '
        'This is not an organizer portal acceptance or organizer validation receipt.</td></tr>',
        '<tr><td>Decoded full-array pattern distinct in the supplied inventory?</td><td><b>YES, with scope limits.</b> '
        'That alone does not establish a unique submission.</td></tr>',
        f'<tr><td>Maximum rank correlation vs. checked registry rasters?</td><td>{pct_rank:.6f} '
        f'(limit {unique["spearman_limit"]:.2f}; this rank gate does not fire).</td></tr>',
        f'<tr><td>Final dots within 3 px of the spacing-five prior?</td><td><b>{pct_near:.4f}%</b> '
        f'(stop limit &gt; {pct_dot_limit:.0f}%); gate fails.</td></tr>',
        f'<tr><td>Candidate cells inside any prior support?</td><td>{unique["support_overlap_pixels"]:,} / '
        f'{unique["candidate_pixels"]:,} ({pct_any:.4f}%).</td></tr>',
        f'<tr><td>Candidate cells inside <code>h33-2-b2</code> support?</td><td>{unique["h33_intersection_pixels"]:,} '
        f'({pct_h33:.4f}%).</td></tr>',
        '<tr><td>Comparable candidate-specific HOLDOUT-DTI with 95% CI?</td><td>No. Archived fold means are not '
        'comparable HOLDOUT-DTI; they are not organizer scores.</td></tr>',
        '<tr><td>Organizer-confirmed score or submission receipt?</td><td>No. Do not infer one.</td></tr>',
        '</tbody></table></div>',
        '<div class="status"><strong>How to read the uniqueness result.</strong> '
        f'The full decoded array is distinct in the checked inventory and maximum Spearman is below '
        f'{unique["spearman_limit"]:.2f}, but {pct_near:.4f}% of final dots are within 3 px of the '
        f'spacing-five raster, above the &gt;{pct_dot_limit:.0f}% stop threshold. The raster also reuses '
        'a large prior-supported core. A new filename, ZIP, or byte encoding would not make its '
        'predicted pattern unique.</div>',
        '<h2>Evidence and scope</h2>',
        '<p>The local audit covered the supplied aligned inventory only; it cannot prove absence of private '
        'or unlinked submissions. Support overlap is a spatial diagnostic, not a score. Score labels and '
        'file-to-score mappings elsewhere on the historical H60C audit are owner-reported, not '
        'organizer-confirmed. No organizer score is claimed here.</p>',
        '<ul>',
        f'<li><a href="{esc(status_json)}">H60C status receipt</a> (machine-readable; no portal name or note).</li>',
        '<li><a href="../evidence/uniqueness_audit_h60c_20261008.json">H60C uniqueness audit</a> (diagnostic, not a score).</li>',
        '<li><a href="data/h60c_build.json">H60C build and local format receipt</a>.</li>',
        '<li><a href="../registry/irregularities.json">Irregularity registry</a>, including IR-UNQ-001 and IR-UNQ-006.</li>',
        '<li><a href="h60c.html">Historical H60C analysis and its attribution caveats</a>.</li>',
        '<li>The separate <a href="executive-summary.html">CTD5 status</a> remains DO NOT SUBMIT; this page does not change it.</li>',
        '</ul>',
        '<p><b>No portal steps, submission name, or portal note are provided.</b> Keep this artifact in the '
        'research archive; do not select, rename, or upload it as a candidate.</p>',
        '</main>',
        foot(),
    ]
    return "\n".join(parts)


def main() -> int:
    build = load(BUILD_PATH)
    audit = load(AUDIT_PATH)
    status = status_record(build, audit)
    page = render_status_page(build, audit)
    (DOCS / "h60c-submission-status.html").write_text(page + "\n")
    (DOCS / "data" / "h60c_submission.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n"
    )

    artifact = status["artifact"]
    unique = status["uniqueness_diagnostic"]
    (SUB / "H60C_LATEST.txt").write_text(
        "RESEARCH DOWNLOAD ONLY — DO NOT SUBMIT\n"
        f"file: {artifact['filename']}\n"
        f"sha256: {artifact['sha256']}\n"
        f"bytes: {artifact['bytes']}\n"
        f"final_dot_gate: FAIL ({unique['max_final_dot_fraction_within_3px']:.6f} > "
        f"{unique['near_3px_limit']:.2f})\n"
        "submission_ok: false\n"
        "organizer_confirmed: false\n"
    )
    print("wrote H60C research-only status page and no-submit receipt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
