#!/usr/bin/env python3
"""Publish an explicitly research-only H55 record and one-click links from audited receipts."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def publish() -> None:
    receipt = json.loads((EV / "submission_h55.json").read_text())
    holdout = json.loads((EV / "h55_profile_holdout.json").read_text())
    name = receipt["file"]
    if not name.startswith("gems52-h55-profile-") or not name.endswith("-research.tif"):
        raise ValueError("H55 receipt points to an unexpected TIFF")
    tif = DOCS / "downloads" / name
    if not tif.is_file() or receipt["sha256"] != __import__("hashlib").sha256(tif.read_bytes()).hexdigest():
        raise ValueError("H55 published TIFF is absent or differs from audited receipt")
    # Research-only download archives contain exactly the TIFF, never portal identifiers or notes.
    archive_path = tif.with_suffix('.zip')
    valid_archive = False
    if archive_path.exists():
        try:
            with zipfile.ZipFile(archive_path) as archive:
                valid_archive = (archive.namelist() == [name]
                                 and archive.read(name) == tif.read_bytes()
                                 and archive.testzip() is None)
        except (OSError, KeyError, zipfile.BadZipFile):
            valid_archive = False
    if not valid_archive:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(tif, arcname=name)
    gate = receipt["validation"]
    scores = [f["arms"] for f in holdout["folds"]]
    primary = [r["structural_contrast_h55"]["dti"] for r in scores]
    surface = [r["view_B_h55"]["dti"] for r in scores]
    base_surface = [r["view_B"]["dti"] for r in scores]
    uniqueness = receipt["uniqueness"]
    summary = {
        "file": name,
        "sha256": receipt["sha256"],
        "bytes": receipt["bytes"],
        "format_ok": receipt["format"]["ok"],
        "format": {k: receipt["format"][k] for k in ("bands", "dtype", "crs", "width", "height", "transform", "min", "max", "nan_pixels", "n_nonzero")},
        "research_only": True,
        "weekly_slot_approved": False,
        "holdout": {
            "folds": len(primary),
            "baseline_surface_dti": base_surface,
            "surface_plus_profile_dti": surface,
            "structural_profile_dti": primary,
            "mean_profile_dti": sum(primary) / len(primary),
            "mean_best_comparable_baseline_dti": holdout["means"][gate["best_comparable_baseline"]],
            "best_comparable_baseline": gate["best_comparable_baseline"],
            "mean_lift": gate["mean_dti_lift"],
            "positive_folds": gate["positive_folds"],
            "approved_for_slot": gate["approved_for_slot"],
            "reason": gate["reason"],
        },
        "uniqueness": {k: uniqueness[k] for k in ("n_priors_checked", "canonical_pattern_unique", "equals_literal_prior_union", "research_publication_ok", "support_novelty_gate_ok", "novel_vs_all_priors", "novel_fraction", "prior_px_dropped", "relation_to_union", "scope")},
        "view_comparison": receipt["view_comparison"],
        "a_only_emitted_pixels_with_reasoning": receipt["a_only_reasoning"]["rows"],
        "official_score": None,
        "organizer_upload_acceptance": None,
    }
    (DOCS / "data/h55_profile.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (DOCS / "data/h55_profile_holdout.json").write_text(json.dumps(holdout, indent=2, allow_nan=False) + "\n")

    current_index = DOCS / "index.html"
    current_h75 = DOCS / "h75-executive-summary.html"
    h75_is_current = (current_index.is_file() and current_h75.is_file()
                      and "H75: DUPLICATE/STOP" in current_index.read_text(errors="replace")
                      and "NOT FOR SUBMISSION" in current_h75.read_text(errors="replace"))
    if not h75_is_current:
        index = DOCS / "index.html"
        text = index.read_text()
        card = f'''<section class="card" id="h55-profile-followup"><h2>H55-PROFILE follow-up — research only, not promoted</h2><p>The five-scale paired-normal DEM profile candidate is a separate experiment. Its frozen spatial holdout failed the required mean-lift gate (+0.002300 vs +0.005); it does not replace the main H55 download or <code>submission/LATEST.txt</code>.</p><p><a class="button" href="downloads/{name}" download>Download H55-PROFILE research TIFF</a> <a href="downloads/{name[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="h55-profile.html">Full follow-up audit</a></p></section>'''
        marker_start, marker_end = "<!--H55PROFILE-->", "<!--/H55PROFILE-->"
        if marker_start in text and marker_end in text:
            i, j = text.index(marker_start), text.index(marker_end) + len(marker_end)
            text = text[:i] + marker_start + card + marker_end + text[j:]
        elif "<!--/H55BAR-->" in text:
            i = text.index("<!--/H55BAR-->") + len("<!--/H55BAR-->")
            text = text[:i] + marker_start + card + marker_end + text[i:]
        else:
            text = text.replace('<main id="main">', '<main id="main">' + marker_start + card + marker_end, 1)
        index.write_text(text)

    detail = f'''<div class="eyebrow">H55 · historical pre-registered surface-profile experiment</div>
<h1>Historical research file, not a contest recommendation.</h1>
<div class="notice bad" role="alert"><strong>RESEARCH ONLY · NOT FOR SUBMISSION.</strong> The local catalogue-proxy comparison failed its promotion gate. No organizer score or portal acceptance is known, no owner override is authorized, and no weekly slot was used.</div>
<p><a class="button" href="downloads/{name}" download>↓ Download H55 research TIFF</a> <a class="button" href="downloads/{name[:-4]}.zip" download>↓ Download research ZIP</a></p>
<div class="card"><h2>Historical artifact facts</h2><p>File: <code>{name}</code></p><p>SHA-256: <code>{receipt['sha256']}</code></p><p><strong>Research-only; not approved for submission.</strong> No portal name or note is provided.</p></div>
<h2>Pass/fail decision — catalogue-proxy evaluation</h2>
<p><strong>Historical CATALOGUE-PROXY DTI (not shared HOLDOUT-DTI, not a leaderboard score):</strong> H55 structural-profile mean {sum(primary)/len(primary):.6f} versus local <code>{gate['best_comparable_baseline']}</code> baseline {holdout['means'][gate['best_comparable_baseline']]:.6f}; paired mean difference {gate['mean_dti_lift']:+.6f}; positive folds {gate['positive_folds']}/4. The preregistered +0.005 mean-lift bar failed, so no slot was approved. This was a spatial-quadrant, whole-original-component hide-and-recover proxy with an 80-pixel training buffer. No pooled shared-evaluator 95% CI was computed for this older experiment; see the dated fold receipt. These proxy values do not measure organizer truth or predict a competition score.</p>
<div class="table-wrap"><table><thead><tr><th>Spatial fold</th><th>Surface baseline</th><th>Surface + profile features</th><th>Structural baseline</th><th>Structural + profile (primary)</th></tr></thead><tbody>{''.join(f'<tr><td>{i}</td><td>{s0:.6f}</td><td>{s1:.6f}</td><td>{r["structural_contrast"]["dti"]:.6f}</td><td>{p:.6f}</td></tr>' for i,(s0,s1,r,p) in enumerate(zip(base_surface,surface,scores,primary)))}<tr><td><strong>Mean</strong></td><td><strong>{sum(base_surface)/4:.6f}</strong></td><td><strong>{sum(surface)/4:.6f}</strong></td><td><strong>{holdout['means']['structural_contrast']:.6f}</strong></td><td><strong>{sum(primary)/4:.6f}</strong></td></tr></tbody></table></div>
<h2>What the new transform tests</h2><p>Band 12 detrended elevation is smoothed and its local gradient defines a normal. The code samples bilateral elevations at 100, 200, 300, 400 and 600 m, subtracts a local first-order plane, records signed step, paired flank contrast/asymmetry, and tangent persistence. It is deliberately compared with both the original surface-only model and the structural baseline at equal emitted budgets. It does not prove a fault; roads, gullies, lithologic contacts and DEM artifacts remain plausible alternatives.</p><p><strong>Scope:</strong> H55 is a supervised structural-contrast model, not co-training. The repository separately tested view-error correlation on held-out catalogue-zero proxy negatives and ran a buffered one-round exchange experiment; that separate experiment did not promote over the surface-only baseline and its pseudo-labels are not used here. Weak error correlation is not proof that the theorem's stronger view assumptions hold.</p>
<h2>Output and uniqueness audit</h2><p>Single-band float32 GeoTIFF, 3292 × 3730, EPSG:32611, exact sample transform, all raw values finite in [0,1], {receipt['format']['n_nonzero']:,} positive cells, internal footprint mask, no positive mass outside the valid support. Local checks are not an organizer's upload-acceptance guarantee.</p><p>Decoded-pattern uniqueness passed against <strong>{uniqueness['n_priors_checked']} accessible aligned TIFF priors</strong>: {uniqueness['novel_fraction']:.1%} of emitted support was absent from their binary / ≥0.5 support union, and {uniqueness['prior_px_dropped']:,} pixels in that union were omitted. The model output is not the union of View A and View B ({receipt['view_comparison']['not_merely_union']}). This is a bounded repository inventory: assets inaccessible from this checkout, private competition submissions and every historical website file have not all been exhaustively authenticated or compared. It cannot support an absolute global-uniqueness claim.</p>
<p><strong>A-only emitted pixels with individual geological reasoning:</strong> {receipt['a_only_reasoning']['rows']:,}. <a href="downloads/{name[:-4]}-candidates.csv">Download per-pixel reasoning CSV</a> · <a href="downloads/{name[:-4]}-audit.json">Full TIFF and uniqueness receipt</a> · <a href="data/h55_profile.json">Compact machine-readable summary</a> · <a href="data/h55_profile_holdout.json">Holdout fold evidence</a>.</p>
<h2>0.2778 evidence: no causal explanation established</h2><p>The saved 2026-10-09 20:18 UTC public-board observation places the team-level 0.2778 row at rank 17 (top 0.3774; 0.3195 at rank 7). The board has no TIFF hash or organizer receipt, so the file association remains owner-reported. Local bytes show the H33-labelled 37,654-cell bitmap is a strict subset of a separate 44,090-cell bitmap associated by its owner with 0.2600: 6,436 cells removed and none added, all 100–200 m from the known-fault mask. This local relationship does not identify hidden-truth credit or explain any score change. Official staff confirms only new-fault truth is scored and that new-fault pixels may occur within 300 m of known traces, so the removed cells are not automatically zero-credit. Earlier |G| and credit calculations are conditional scenarios, not measurements or a causal explanation.</p>
<h2>Registered hypotheses and next tests</h2><p>The full pre-registration lists four candidates, layer names, mechanisms, repo-level novelty and cost. H55-PROFILE is the only one implemented in this turn; H55-JUNCTION and H55-STRAIN use supplied bands but remain untested. H55-SEISMIC requires official USGS ComCat event bytes: a sandbox request to the official FDSN endpoint failed TLS before receiving a response. It is deferred, not treated as viable or used in this TIFF.</p><p><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/12_hypotheses_H55_preregistered.md">Full ranked hypotheses and protocol</a> · <a href="data/h55_profile_holdout.json">Raw holdout receipt</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official scoring definition</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official leaderboard</a> · <a href="https://earthquake.usgs.gov/fdsnws/event/1/">USGS ComCat FDSN</a> · <a href="https://gdr.openei.org/submissions/1391">DOE GDR INGENIOUS</a> · <a href="https://www.usgs.gov/the-national-map-data-delivery/gis-data-download">USGS 3DEP download</a>.</p>'''
    page = DOCS / "h55-profile.html"
    nav = '<a href="index.html">Overview</a><a href="executive-summary.html">Research status</a><a href="validation.html">Validation</a><a href="h55-profile.html">H55-PROFILE follow-up</a><a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a>'
    page.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="H55 paired-normal profile: historical research GeoTIFF, failed local promotion gate, and auditable limits."><title>H55 historical research artifact · GEMSDOE52</title><link rel="stylesheet" href="style.css"></head><body><aside role="alert" style="padding:14px 22px;background:#fef2f2;color:#7f1d1d;border:2px solid #991b1b"><strong>H75: DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION.</strong> This is a historical H55 archive. <a href="h75-executive-summary.html">H75 stop status</a>.</aside><a class="skip" href="#main">Skip to evidence</a><header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{nav}</nav></header><main id="main">{detail}</main><footer>Fault-map research proposal, not a verified fault or geothermal vent. <a href="irregularities.html">Limitations &amp; review</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a></footer></body></html>''')

    if not h75_is_current:
        downloads = DOCS / "downloads/index.html"
        existing = downloads.read_text() if downloads.exists() else ""
        latest = (ROOT / "submission/LATEST.txt").read_text().strip()
        incumbent = f'<p id="main-h55-download"><strong>Main H55 candidate (unchanged):</strong> <a href="{latest}" download>Download incumbent TIFF</a> · <a href="{latest[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="../h55.html">incumbent evidence</a></p>'
        h55_link = f'<p id="h55-profile-downloads"><strong>H55-PROFILE follow-up — research only, NOT promoted:</strong> <a href="{name}" download>Download TIFF</a> · <a href="{name[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="{name[:-4]}-audit.json">audit</a> · <a href="{name[:-4]}-candidates.csv">A-only reasoning CSV</a> · <a href="../h55-profile.html">experiment page</a></p>'
        for marker, paragraph in (("main-h55-download", incumbent), ("h55-profile-downloads", h55_link)):
            pattern = rf'<p[^>]*id="{marker}"[^>]*>.*?</p>'
            if re.search(pattern, existing, flags=re.S):
                existing = re.sub(pattern, lambda _: paragraph, existing, flags=re.S)
            else:
                existing = existing.replace("<h1>Research downloads</h1>", "<h1>Research downloads</h1>" + paragraph, 1)
        main_match = re.search(r'<p[^>]*id="main-h55-download"[^>]*>.*?</p>', existing, flags=re.S)
        profile_match = re.search(r'<p[^>]*id="h55-profile-downloads"[^>]*>.*?</p>', existing, flags=re.S)
        if main_match and profile_match:
            existing = re.sub(r'<p[^>]*id="(?:main-h55-download|h55-profile-downloads)"[^>]*>.*?</p>', "", existing, flags=re.S)
            existing = existing.replace("<h1>Research downloads</h1>", "<h1>Research downloads</h1>" + main_match.group(0) + profile_match.group(0), 1)
        downloads.write_text(existing)

    else:
        print("H75 status is current; H55-PROFILE publisher skipped the shared downloads index")

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    readme_block = f'''<!--H55PROFILEREADME-->
## H55-PROFILE follow-up — generated, but not promoted

**[Download the H55-PROFILE research TIFF](docs/downloads/{name})** · [single-TIFF ZIP](docs/downloads/{name[:-4]}.zip) · [experiment page](docs/h55-profile.html). This follow-up does **not** replace the main H55 candidate or change `submission/LATEST.txt`.

- Artifact facts: `{name}`, SHA-256 `{receipt['sha256']}`. No portal name or note is provided.
- Local format/range/geometry and decoded-pattern checks were assessed against {uniqueness['n_priors_checked']} accessible aligned priors. Bounded audit only; not proof against private/unlinked site assets.
- **RESEARCH ONLY · NOT FOR SUBMISSION:** catalogue-proxy mean difference {gate['mean_dti_lift']:+.6f}, {gate['positive_folds']}/4 folds positive; pre-registered +0.005 lift threshold failed. No official score/upload acceptance and no weekly slot used. The main H55 file and `submission/LATEST.txt` remain unchanged.
- Inputs were SHA-pinned owner mirrors, not organizer-authenticated. No external raster or ComCat data entered this model.
- [Preregistered hypotheses](knowledge/12_hypotheses_H55_preregistered.md) · [holdout](evidence/h55_profile_holdout.json) · [TIFF/uniqueness receipt](evidence/submission_h55.json) · [3-pass review](evidence/h55_review_receipt.json).

**Next-session start:** read this README and the full current task prompt below; the H55 candidate failed its promotion gate. A download link is not approval to spend a contest slot.
<!--/H55PROFILEREADME-->'''
    if "<!--H55PROFILEREADME-->" in readme and "<!--/H55PROFILEREADME-->" in readme:
        readme = re.sub(r"<!--H55PROFILEREADME-->.*?<!--/H55PROFILEREADME-->",
                        lambda _: readme_block, readme, count=1, flags=re.S)
    elif "## Historical H54 candidate" in readme:
        readme = readme.replace("## Historical H54 candidate", readme_block + "\n\n## Historical H54 candidate", 1)
    else:
        readme = readme.replace("# GEMSDOE52", "# GEMSDOE52\n\n" + readme_block, 1)
    readme_path.write_text(readme)


def main() -> None:
    publish()
    print("Published H55-PROFILE follow-up page and byte-checked research download; incumbent preserved")


if __name__ == "__main__":
    main()
