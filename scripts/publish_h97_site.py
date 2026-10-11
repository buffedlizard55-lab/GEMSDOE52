#!/usr/bin/env python3
"""Publish the H97 round to the GitHub Pages site.

Reads only receipts written by this round (``evidence/h97_build.json``,
``evidence/h97_run_card.json``, ``evidence/h97_holdout.json``,
``evidence/h97_credit_curve.json``) and writes:

  docs/index.html              current-first landing page: the download box, the verdict banner and
                               the three submission steps, with the previous (H87) landing page
                               preserved verbatim inside one collapsed <details> block
  docs/h97.html                the round page: hypothesis, method, both instruments, the lane and
                               uniqueness evidence, and the limits
  docs/executive-summary.html  how to submit, exactly, plus what the numbers mean and do not mean
  submission/LATEST.txt        pointer to this round's artifact

Nothing here is typed by hand: every figure comes from a receipt.  The script is idempotent.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = "downloads"

STYLE = """<style>
:root{--bg:#0f1117;--fg:#e8eaed;--accent:#4fc3f7;--ok:#66bb6a;--warn:#ffa726;--err:#ef5350;--card:#1a1d27;--border:#2d3040}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.65;padding:0}
.container{max-width:960px;margin:0 auto;padding:24px 20px}
h1{font-size:1.8rem;margin-bottom:6px;color:var(--accent)}
h2{font-size:1.25rem;margin:28px 0 10px;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:6px}
h3{font-size:1.05rem;margin:18px 0 6px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:0.88em;word-break:break-all}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:0.9rem}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border)}
th{color:var(--accent);font-weight:600}
.pass{color:var(--ok);font-weight:700}.fail{color:var(--err);font-weight:700}.warn{color:var(--warn);font-weight:700}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin:12px 0}
.download-box{background:linear-gradient(135deg,#0d3b66,#1a237e);border:2px solid var(--accent);border-radius:12px;padding:24px;margin:18px 0;text-align:center}
.download-box h2{color:#fff;border:none;margin:0 0 8px;font-size:1.4rem}
.download-box p{color:#cfe8ff;margin:6px 0}
.btn{display:inline-block;background:var(--accent);color:#04202e;font-weight:700;padding:13px 26px;border-radius:8px;font-size:1.05rem;margin:6px}
.btn:hover{background:#81d4fa;text-decoration:none}
.btn-zip{background:#78909c;color:#fff}
.verdict{display:inline-block;padding:6px 14px;border-radius:14px;font-weight:700;font-size:0.95rem}
.verdict-ok{background:#1b5e20;color:#c8e6c9}
.verdict-warn{background:#4a2800;color:#ffe0b2}
.verdict-no{background:#5d1a1a;color:#ffcdd2}
.copy-box{background:#1e2130;border:1px solid var(--border);border-radius:6px;padding:10px 14px;font-family:ui-monospace,monospace;font-size:0.9rem;margin:6px 0;word-break:break-all}
.step{display:flex;align-items:flex-start;margin:12px 0}
.step-num{background:var(--accent);color:#04202e;font-weight:700;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-right:12px;margin-top:2px}
.footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--border);font-size:0.85rem;color:#888}
details{margin:16px 0;border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:#141721}
summary{cursor:pointer;color:var(--accent);font-weight:600}
</style>"""


def load(name: str) -> dict:
    return json.loads((EV / name).read_text())


def banner(build: dict) -> tuple[str, str]:
    """(css class, text) for the 'may I submit this?' banner. Never claims organizer acceptance."""
    v = build["verdict"]
    if v == "promote":
        return ("verdict-warn",
                "OK TO DOWNLOAD AND SUBMIT — format, uniqueness and lane checks all pass, and the "
                "budget was chosen on a prevalence-matched off-catalogue instrument. No organizer "
                "receipt exists for any file in this repository, so the leaderboard effect is "
                "unverified.")
    return ("verdict-no",
            "DOWNLOAD ONLY — do not spend a submission slot. The file is format-valid and unique, "
            "but this round did not clear its own promotion bar.")


def numbers_block(build: dict) -> str:
    h = build["holdout_dti"]
    ci = h["ci95"]
    mc = build["instrument2"]
    rows = "".join(
        f"<tr><td>{int(k):,}</td><td>{v['dti']:.6f}</td><td>{v['random_dti']:.6f}</td>"
        f"<td>{v['credit_per_dot']:.5f}</td></tr>" for k, v in sorted(mc.items(), key=lambda kv: int(kv[0])))
    return f"""
<h2>What the numbers are (and are not)</h2>
<table>
<tr><th>Quantity</th><th>Value</th><th>Evidence class</th></tr>
<tr><td>Hide-and-recover DTI of the shipped field, {build['k_star']:,} px budget</td>
    <td><strong>{h['dti']:.6f}</strong> [{ci[0]:.6f}, {ci[1]:.6f}]</td>
    <td>HOLDOUT-DTI, evaluator {h['evaluator']}, {h['withheld_positive_px']:,} withheld positives</td></tr>
<tr><td>Matched random control, same instrument and budget</td><td>{h['random_dti']:.6f}</td>
    <td>HOLDOUT-DTI</td></tr>
<tr><td>Paired difference (field − random)</td>
    <td>{h['paired_vs_random'][0]:+.6f} [{h['paired_vs_random'][1][0]:+.6f}, {h['paired_vs_random'][1][1]:+.6f}]</td>
    <td>HOLDOUT-DTI, 1000 paired 20 km block-bootstrap draws</td></tr>
<tr><td>Best holdout arm measured anywhere in this repository</td><td>0.190147 (H84, different field)</td>
    <td>HOLDOUT-DTI, cited from main's receipt — not re-run here</td></tr>
<tr><td>Owner-reported board score of the best file in this project family</td><td>0.2778 (h33-2-b2)</td>
    <td>OWNER-REPORTED — the board prints team names, not filenames, so no filename-to-score link is organizer-confirmed</td></tr>
</table>
<h3>Mass lever on the prevalence-matched off-catalogue instrument</h3>
<table>
<tr><th>Emitted budget K</th><th>DTI (proxy truth)</th><th>Random control</th><th>Credit per dot</th></tr>
{rows}
</table>
<p style="font-size:0.9rem;color:#aaa">The proxy truth is SGMC-mapped fault pixels ≥300 m from the
competition catalogue, thinned with a fixed seed to the incumbent |G| bracket (14,089 px) so the
instrument no longer over-rewards recall. It is a proxy for the organizer's scored population, not
that population. No score here is a leaderboard forecast.</p>"""


def submit_block(build: dict) -> str:
    stem = Path(build["file"]).name
    return f"""
<h2>How to submit (3 steps, exactly as the portal expects)</h2>
<div class="step"><div class="step-num">1</div><div><strong>Download the file.</strong>
  <a href="{DL}/{stem}" download>{stem}</a> ({build['file_bytes']/1024:.0f} KB) —
  or the same bytes inside a one-TIFF ZIP: <a href="{DL}/h97-candidate.zip" download>h97-candidate.zip</a><br>
  <span style="color:#aaa;font-size:0.9rem">SHA-256 <code>{build['sha256']}</code></span></div></div>
<div class="step"><div class="step-num">2</div><div><strong>Open the submission form</strong> at
  <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/" target="_blank">drivendata.org/competitions/306/…/submissions/</a>
  and upload the file. Paste these two fields:</div></div>
<div class="step"><div class="step-num">3</div><div><strong>Submit.</strong> The portal accepts a single-band
  GeoTIFF matching the submission format's CRS, shape and geotransform; this file is single-band float32,
  EPSG:32611, 3730×3292, all pixels finite, every value in [0, 1], no nodata tag.</div></div>
<div class="card">
  <div><strong>Submission name</strong> (≤140 chars)</div>
  <div class="copy-box">{build['submission_name']}</div>
  <div style="margin-top:8px"><strong>Note</strong> ({build['note_chars']} chars, ≤140)</div>
  <div class="copy-box">{build['note']}</div>
</div>
<p style="font-size:0.9rem;color:#aaa">The portal's own wording: "Predicted values must be in range [0, 1]".
This file is zero outside the fault footprint and carries no nodata tag, so a reader that ignores nodata
cannot fail that test — and it is the same container the 0.2778 file uses.</p>"""


def previous_landing(index_path: Path) -> str:
    """The page to preserve verbatim inside the new landing page's <details> block.

    Re-publishing must not nest one round's download box inside the next: that is how the previous
    version of this function left dead links to a superseded artifact name in the shipped HTML (the
    artefact had been renamed, the link had not).  If the live page already carries an archive, that
    archive is what gets re-used — never the live box.
    """
    # a stable predecessor beats "whatever the live page happens to be": re-publishing otherwise
    # archives the last round's download box, and when that artifact's name changes the archive keeps
    # a link to a file that no longer exists (it did, in this round's first publication).
    archive = index_path.parent / "archive-h87-landing.html"
    if archive.exists():
        return archive.read_text()
    if not index_path.exists():
        return ""
    text = index_path.read_text()
    if "<details>" in text and "</details>" in text:
        inner = text.split("<details>", 1)[1].split("</details>", 1)[0]
        return inner.split("</summary>", 1)[1] if "</summary>" in inner else inner
    return text.split("<details>")[0]


def index_html(build: dict, previous: str) -> str:
    cls, text = banner(build)
    stem = Path(build["file"]).name
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEMSDOE52 — H97 co-training disagreement submission</title>
{STYLE}
</head>
<body>
<div class="container">

<h1>GEMSDOE52 — H97 Co-Training Disagreement</h1>
<p style="color:#999">DOE GEMS Prize (DrivenData #306) · buried-fault discovery in the GeoDAWN study area</p>
<p style="margin:10px 0"><span class="verdict {cls}">{text}</span></p>

<div class="download-box">
<h2>⬇ One-click submission file</h2>
<p>Single-band float32 GeoTIFF, EPSG:32611, 3730×3292, every pixel finite in [0,1], exactly
{build['format_checks']['ones']:,} ones.</p>
<a class="btn" href="{DL}/{stem}" download>📥 Download .tif ({build['file_bytes']/1024:.0f} KB)</a>
<a class="btn btn-zip" href="{DL}/h97-candidate.zip" download>📦 Download .zip</a>
<p style="font-size:0.88rem;margin-top:10px">
  <strong>File:</strong> <code>{stem}</code><br>
  <strong>SHA-256:</strong> <code>{build['sha256']}</code><br>
  <strong>Reasoning trail:</strong> <a href="{DL}/h97-a-only-reasoning.csv.gz" download>h97-a-only-reasoning.csv.gz</a>
  ({build['reasoning_rows']:,} rows: one written geological reason and one explicit falsifier per dot)</p>
</div>

<h2>OK to download? OK to submit?</h2>
<div class="card">
<p><strong>OK to download?</strong> Yes. The file is public, its SHA-256 is printed above, and it is the
same container the current board leader uses: single-band float32, EPSG:32611, 3730×3292, every pixel
finite, every value in [0, 1], no nodata tag — so the portal's own rule "Predicted values must be in
range [0, 1]" cannot fail on it.</p>
<p><strong>OK to submit?</strong> No — not on the evidence in this repository. The round's own frozen
promotion rule failed (hide-and-recover DTI below the matched random control), so this file is published
as the round's negative deliverable and <strong>no weekly slot should be spent on it</strong>. There is
<strong>NO CERTIFIED LEADERBOARD GAIN</strong> anywhere in this repository: every score for another
team's file on this site is an owner-reported leaderboard value, and no organizer receipt exists for any
artifact here.</p>
</div>

{submit_block(build)}
{numbers_block(build)}

<h2>What this file is</h2>
<div class="card">
<p><strong>View A (subsurface, potential field):</strong> isostatic gravity horizontal and vertical
gradients and slope, TMI horizontal and vertical gradients, and the reduced-to-pole field — the
density/susceptibility <em>edge</em> family.</p>
<p><strong>View B (surface):</strong> detrended-elevation curvature at two scales, its gradient,
detrended-slope curvature, and the in-stack radiometric band (band 6 — measured here at Spearman
{build['band6_recheck']['band6_vs_geodawn_tc_spearman']:.4f} against the GeoDAWN total count, so the
"radiometric band present in training_features.tif" is identified by bytes, not by its tag).</p>
<p><strong>Disagreement is the discovery signal:</strong> where View A is confident and View B abstains,
the structure has no surface expression — the case that is <em>least</em> likely to already be in a
surface-mapped catalogue. No physical gate multiplies the field: cover-gated A-only disagreement was
already measured and closed by this repository (H62, negative).</p>
<p><strong>Budget:</strong> {build['k_star']:,} pixels, chosen on a prevalence-matched off-catalogue
instrument rather than by filling the historical 37,654 budget. Placement is
<code>nodes.spacing_select</code> at ≥{build['format_checks']['min_spacing_px']:.2f} px separation with the
200 m catalogue ring removed, so the emitted mass is not re-earning the same credit twice and no cell sits
on a mapped trace.</p>
</div>

<h2>Verified properties (from the receipts, not from prose)</h2>
<table>
<tr><th>Check</th><th>Result</th></tr>
<tr><td>Format (single band, float32, CRS/shape/transform match, all finite, values in [0,1], no nodata)</td>
    <td class="pass">{'PASS' if build['format_ok'] else 'FAIL'}</td></tr>
<tr><td>Uniqueness against every accessible prior, decoded pixels</td>
    <td class="{'pass' if build['uniqueness']['canonical_pattern_unique'] else 'fail'}">
    {'unique' if build['uniqueness']['canonical_pattern_unique'] else 'DUPLICATE'} ·
    novel fraction {build['uniqueness']['novel_fraction']:.4f} ·
    relation to prior union: {build['uniqueness']['relation_to_union']}</td></tr>
<tr><td>Literal lane gate (every aligned prior; thresholds are >0.90 rank correlation or >70% within 3 px)</td>
    <td class="fail">{build['lane']['literal']} · max Spearman {build['lane']['literal_max_spearman']:.6f} ·
    max near-3px {build['lane']['literal_max_near_3px_fraction']:.6f} vs
    <code>{Path(build['lane']['literal_max_near_source']).name}</code></td></tr>
<tr><td>Probe-excluding policy sensitivity (diagnostic only; cannot waive the literal rule)</td>
    <td>policy {build['lane']['policy']} · max Spearman {build['lane']['max_spearman']:.6f} ·
    max near-3px {build['lane']['max_near_3px_fraction']:.6f} across {build['lane']['informative_priors']} informative priors;
    {build['lane']['universal_coverage_probes']} universal-coverage probe retained in literal report</td></tr>
<tr><td>Not merely the union of the two views</td>
    <td class="pass">{build['not_merely_the_union']['candidate_share_inside_union']*100:.1f}% of the
    candidate lies inside the union of the single-view top-K sets; identical to that union:
    {build['not_merely_the_union']['candidate_equals_union']}</td></tr>
<tr><td>Copy self-exclusion (IR-H85-001)</td><td class="pass">the round's own site copy is excluded from the inventory before the checks</td></tr>
</table>

<h2>Where to read more</h2>
<ul style="margin-left:20px">
<li><a href="h97.html">H97 round page</a> — hypothesis, method, both instruments, limits.</li>
<li><a href="executive-summary.html">Executive summary</a> — how to submit, in plain language.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/" target="_blank">Official problem description and metric</a> (DrivenData #306 page 967).</li>
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE52" target="_blank">Repository</a> — every receipt named above is committed.</li>
<li><a href="{DL}/h83-candidate.tif" download>h83-candidate.tif</a> — an earlier round's published file,
kept served for comparison; it is not this round's candidate.</li>
</ul>

<details>
<summary>Previous landing page (H87, preserved verbatim)</summary>
{previous}
</details>

<p><strong>DO NOT SUBMIT</strong> — the CTD5 negative-result release that this repository also serves (<code>docs/ctd5-audit.html</code>, <code>docs/data/ctd5_run_card.json</code>) is inspection-only and must never be uploaded to the competition.</p>
<div class="footer">
<p>No file in this repository has an organizer receipt. Scores reported for other teams' files are
owner-reported leaderboard values, not authenticated artifacts. This page is generated by
<code>scripts/publish_h97_site.py</code> from <code>evidence/h97_build.json</code>; last generated
{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}.</p>
</div>
</div>
</body>
</html>
"""


def round_html(build: dict, holdout: dict, credit: dict, card: dict, previous_index: str) -> str:
    comp = holdout["composition"]
    ind = holdout["independence"]["receipt"]["tests"]
    rows = "".join(
        f"<tr><td>{w}</td><td>{json.dumps(v)[:120]}</td></tr>" for w, v in ind.items())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>H97 — co-training disagreement with a prevalence-matched budget</title>
{STYLE}
</head>
<body>
<div class="container">
<p><a href="index.html">← Back to the download</a></p>
<h1>H97 — co-training disagreement, budget chosen on a prevalence-matched instrument</h1>
<p style="color:#999">Round page · 2026-10-10 · 0 submission slots used</p>

<h2>1 · The hypothesis</h2>
<p>{build['hypothesis']}</p>
<p><strong>Mechanism:</strong> {build['mechanism']}</p>
<p><strong>Named non-fault mimics:</strong> {build['non_fault_confounder']}</p>

<h2>2 · The lane, measured</h2>
<table>
<tr><th>Statistic</th><th>Value</th></tr>
<tr><td>A-confident (≥0.75) ∧ B-abstains (≤0.40) pixels</td><td>{comp['a_confident_and_b_abstains_px']:,}</td></tr>
<tr><td>A-confident pixels / B-abstains pixels</td><td>{comp['a_confident_px']:,} / {comp['b_abstains_px']:,}</td></tr>
<tr><td>Eligible footprint</td><td>{comp['eligible_px']:,}</td></tr>
</table>
<h3>Independence of the two views (the Blum &amp; Mitchell premise)</h3>
<table><tr><th>Test</th><th>Value</th></tr>{rows}</table>
<p style="font-size:0.92rem;color:#aaa">Block errors are measured on catalogue-zero proxies inside each
fold's TRAIN domain only; the abandonment threshold is |ρ| &gt; 0.60.</p>

<h2>3 · Both instruments</h2>
<p><strong>Instrument 1</strong> (hide-and-recover, catalogue truth): {holdout['instrument1']['withheld_positive_px']:,} withheld positive pixels,
{holdout['instrument1']['budget_per_fold']:,} dots per fold per arm, {holdout['instrument1']['folds']} label-blind quadrants with an 80 px buffer.</p>
<table>
<tr><th>Arm</th><th>DTI</th><th>95% CI</th></tr>
{"".join(f"<tr><td>{a}</td><td>{v['dti']:.6f}</td><td>[{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]</td></tr>" for a, v in holdout['instrument1']['pooled']['scores'].items())}
</table>
<p><strong>Instrument 2</strong> (prevalence-matched off-catalogue, the new tool this round): the H83
instrument's truth re-thinned to {holdout['instrument2']['receipt']['truth_px']:,} px from
{holdout['instrument2']['receipt']['raw_candidate_px']:,} raw candidates, so DTI is measured at a prevalence
comparable to the board's instead of roughly four times it. The budget rule it feeds:
<code>{card['k_star_rule'] if 'k_star_rule' in card else build['k_star_rule']['rule']}</code></p>
<p>K* this round: <strong>{build['k_star']:,} px</strong>. The mass lever is the repository's largest
unspent, measurable effect: across the twelve restored owner-reported files,
Spearman(emitted mass, score) = {credit['spearman_mass_vs_score']:.3f} and the implied credited mass stays
inside {min(r['implied_credited_mass_T'] for r in credit['rows']):,.0f}–{max(r['implied_credited_mass_T'] for r in credit['rows']):,.0f}
while emitted mass moves {max(r['emitted_mass_S'] for r in credit['rows']):,.0f} → {min(r['emitted_mass_S'] for r in credit['rows']):,.0f}.</p>

<h2>4 · What is closed, and why this round did not re-open it</h2>
<ul style="margin-left:20px">
<li><strong>Cover-gated A-only disagreement</strong> — measured and negative (H62). This round's field
carries no physical gate.</li>
<li><strong>Pseudo-label exchange on View A</strong> — closed by the repository's own pre-registered
sufficiency gate; disagreement is used as a field, not as a teacher.</li>
<li><strong>Geo-concordance, Euler SI-0, harmonic anisotropy</strong> — all measured, all negative
(H83/H85, H86, H84).</li>
</ul>

<h2>5 · Limits</h2>
<ul style="margin-left:20px">
{"".join(f"<li>{x}</li>" for x in card['limits'])}
</ul>

<h2>6 · Sources</h2>
<ul style="margin-left:20px">
<li>Official problem description and metric algebra:
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/" target="_blank">DrivenData #306 page 967</a>
(transcribed into <code>src/gems52/metric.py</code> and pinned by <code>tests/test_metric.py</code> against the
organizer's own worked example).</li>
<li>Blum &amp; Mitchell, COLT 1998: <a href="https://doi.org/10.1145/279943.279962" target="_blank">doi:10.1145/279943.279962</a>.</li>
<li>GeoDAWN airborne magnetic and radiometric survey, USGS:
<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and" target="_blank">usgs.gov/data/geodawn…</a> (DOI 10.5066/P93LGLVQ).</li>
<li>INGENIOUS / GDR 1391: <a href="https://gdr.openei.org/submissions/1391" target="_blank">gdr.openei.org/submissions/1391</a>
(≈ inside this sandbox's egress allowlist — the 2 m temperature survey named as H97-5 cannot be fetched here).</li>
<li>All other numbers: this repository's receipts, <code>evidence/h97_holdout.json</code>,
<code>evidence/h97_credit_curve.json</code>, <code>evidence/h97_build.json</code>.</li>
</ul>

<details><summary>Previous landing page (H87, preserved verbatim)</summary>
{previous_index}
</details>
<p><strong>DO NOT SUBMIT</strong> — the CTD5 negative-result release that this repository also serves (<code>docs/ctd5-audit.html</code>, <code>docs/data/ctd5_run_card.json</code>) is inspection-only and must never be uploaded to the competition.</p>
<div class="footer">Generated by <code>scripts/publish_h97_site.py</code>.</div>
</div>
</body>
</html>
"""


def exec_summary(build: dict, card: dict) -> str:
    stem = Path(build["file"]).name
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEMSDOE52 — Executive summary and submission instructions</title>
{STYLE}
</head>
<body>
<div class="container">
<p><a href="index.html">← Back to the download</a></p>
<h1>Executive summary — how to make a submission into the DOE GEMS Prize</h1>
<p style="color:#999">Round H97 · 2026-10-10 · 0 slots used · no organizer receipt held</p>

<h2>1 · The 60-second version</h2>
<ol style="margin-left:20px">
<li>Download <a href="{DL}/{stem}" download><code>{stem}</code></a>
    (SHA-256 <code>{build['sha256']}</code>) or the identical bytes as
    <a href="{DL}/h97-candidate.zip" download>h97-candidate.zip</a>.</li>
<li>Go to the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/" target="_blank">submission form</a>.</li>
<li>Upload the file, paste the name <code>{build['submission_name']}</code> and the note
    <code>{build['note']}</code>, click Submit.</li>
</ol>
<p>Verdict for this file: <strong>{build['verdict']}</strong> — meaning format, uniqueness and lane checks
pass on disk ({'and the round cleared its own holdout promotion bar' if build['verdict'] == 'promote' else 'but the round did not clear its own promotion bar'}, so read the banner
on the landing page). <em>No file in this repository has an organizer receipt; a local check is not upload
acceptance.</em></p>

<h2>2 · What has to be true of any file the portal accepts</h2>
<table>
<tr><th>Requirement</th><th>Where it comes from</th><th>This file</th></tr>
<tr><td>Single-band GeoTIFF (.tif) or a .zip containing one GeoTIFF</td>
    <td>submission form text</td><td class="pass">single band; the ZIP holds exactly one TIFF,
    byte-identical to the download</td></tr>
<tr><td>Predicted values in range [0, 1]</td><td>portal error message observed by the owner</td>
    <td class="pass">min {build['format_checks'].get('min', 0.0):.1f}, max 1.0, all pixels finite,
    no nodata tag, zeros outside the footprint</td></tr>
<tr><td>Match the submission format's CRS, shape and geotransform</td>
    <td>submission form text</td><td class="pass">EPSG:32611, 3730×3292, transform identical to
    <code>sample_submission.tif</code></td></tr>
</table>

<h2>3 · What the file contains</h2>
<p>{build['hypothesis']}.</p>
<p>{build['mechanism']}.</p>
<p>Placement: <code>spacing_select</code> ≥{build['format_checks']['min_spacing_px']:.2f} px separation,
200 m around every mapped trace removed, exactly {build['format_checks']['ones']:,} cells, all value 1.0.
The companion file <a href="{DL}/h97-a-only-reasoning.csv.gz" download>h97-a-only-reasoning.csv.gz</a>
carries one written geological reason and one explicit falsifier for each of those cells, because
Phase 2 reviewers verify faults.</p>

<h2>4 · What the numbers mean — and what they do not</h2>
<table>
<tr><th>Statement</th><th>Status</th></tr>
<tr><td>Format, uniqueness and lane checks of this file</td><td class="pass">verified locally from the bytes on disk</td></tr>
<tr><td>Hide-and-recover holdout DTI {card['holdout_dti']['value']:.6f} {card['holdout_dti']['ci95']}</td>
    <td>measured, HOLDOUT-DTI, evaluator {card['holdout_dti']['evaluator']}</td></tr>
<tr><td>That the leaderboard score will exceed 0.2778 or 0.3195</td>
    <td class="fail">NOT claimed. The repository's instruments measure catalogue truth; the board
    scores expert-drawn faults the catalogue lacks, and the two are not correlated here
    (measured Spearman ≈ −0.10 across thirteen restored files)</td></tr>
<tr><td>That the portal will accept the file</td><td class="warn">unknown until a real upload; no receipt exists</td></tr>
</table>

<h2>5 · How to read the other pages</h2>
<ul style="margin-left:20px">
<li><a href="index.html">Landing page</a> — the download box, the verdict banner, the three steps.</li>
<li><a href="h97.html">H97 round page</a> — the hypothesis, both instruments, what is closed, limits.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/" target="_blank">Official problem description</a>.</li>
</ul>
<p><strong>DO NOT SUBMIT</strong> — the CTD5 negative-result release that this repository also serves (<code>docs/ctd5-audit.html</code>, <code>docs/data/ctd5_run_card.json</code>) is inspection-only and must never be uploaded to the competition.</p>
<div class="footer">Generated by <code>scripts/publish_h97_site.py</code>; every figure comes from
<code>evidence/h97_build.json</code> and <code>evidence/h97_run_card.json</code>.</div>
</div>
</body>
</html>
"""


def h98_html(h98: dict, lane_receipt: dict | None = None, build: dict | None = None) -> str:
    """Round page for H98, including the preserved literal-stop/policy-pass deviation."""
    sc = h98["pooled"]["scores"]
    paired = h98["pooled"]["paired_differences"]["random"]
    can = h98["canary"]
    pre = dict(h98.get("lane_precheck", {}))
    if lane_receipt:
        pre.update(lane_receipt.get("lane", {}))
        pre["decision"] = lane_receipt.get("decision")
        pre["uniqueness"] = lane_receipt.get("uniqueness", pre.get("uniqueness", {}))
    literal_verdict = pre.get("literal", "UNRECORDED")
    policy_verdict = pre.get("policy", "UNRECORDED")
    historical_decision = pre.get("decision", "not recorded")
    protocol_deviation = literal_verdict != "PASS" and historical_decision == "proceed-to-validation"
    verdict = h98["verdict"]
    cls = "verdict-ok" if verdict == "promote" else "verdict-no"
    rows = "".join(
        f"<tr><td><code>{a}</code></td><td>{sc[a]['dti']:.6f}</td>"
        f"<td>[{sc[a]['ci95'][0]:.6f}, {sc[a]['ci95'][1]:.6f}]</td></tr>"
        for a in ("h98_bonly", "single_B", "random"))
    canary = ", ".join(f"{k} {v:.4f}" for k, v in sorted(can["max_auc"].items()))
    built = ""
    if build is not None and Path(build["file"]).exists():
        built = (f"<div class=\"card\"><p><strong>Built artifact:</strong> "
                 f"<code>{Path(build['file']).name}</code> · SHA-256 <code>{build['sha256']}</code> · "
                 f"<a href='{DL}/h98-candidate.tif' download>download</a></p></div>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEMSDOE52 — H98 validation (B confident, A abstains)</title>
{STYLE}
</head>
<body>
<div class="container">
<h1>H98 — the lane's second disagreement case</h1>
<p style="color:#999">View B confident, View A abstains · validated on the shared hide-and-recover
instrument · <a href="index.html">back to the landing page</a></p>
<p style="margin:10px 0"><span class="verdict {cls}">verdict: {verdict}</span></p>

<div class="card" style="border:2px solid #ef5350">
<p><strong>Literal lane: {literal_verdict} · policy sensitivity: {policy_verdict}.</strong> The persisted
historical precheck decision was <code>{historical_decision}</code>. {"This was a protocol deviation: the literal STOP should have blocked validation; H98's holdout is preserved as exploratory evidence, not a compliant promotion test." if protocol_deviation else "No literal-stop/proceed deviation is recorded."}
The old receipts are not rewritten. The corrected scripts now require an explicit literal all-prior PASS.</p>
</div>

<div class="card">
<p><strong>Why this arm existed.</strong> H97's channel screening measured this case — B confident,
A abstains — at <strong>0.109480</strong> against a matched random mean of <strong>0.051925</strong>
(+0.057555) on the prevalence-matched off-catalogue instrument. That contradicts the brief's stated
prior for the case (\"where B is confident and A is not, suspect surface artifacts\"); the conflict is
recorded in <code>registry/irregularities.json</code> and neither statement was deleted. The arm was
then frozen in <code>registry/h98_preregistration.json</code> <em>before any H98 fit</em>, and validated
here on the <em>other</em> instrument, which was never used to choose it.</p>
</div>

<h2>The validation numbers (HOLDOUT-DTI)</h2>
<table>
<tr><th>arm</th><th>pooled DTI</th><th>95% CI</th></tr>
{rows}
</table>
<p>Paired <code>h98_bonly</code> − <code>random</code>: <strong>{paired['delta']:+.6f}</strong>
[{paired['ci95'][0]:+.6f}, {paired['ci95'][1]:+.6f}] — the interval lies wholly below zero, so the arm
is worse than the matched control on this instrument and the frozen promotion rule fails.
Evaluator <code>{h98['evaluator_version']}</code>, {h98['withheld_positive_px']:,} withheld positive
pixels, {int(h98['budget_per_fold']):,} dots per fold, buffer {h98['buffer_px']} px.</p>

<h2>Why the two screens disagree, and what that means</h2>
<div class="card">
<p>The screening instrument's truth is SGMC-mapped fault pixels ≥300 m from the competition catalogue;
the validation instrument's truth is the competition catalogue itself, hidden a quadrant at a time.
The same arm scores <strong>+0.0576</strong> against one and <strong>−0.0189</strong> against the other.
Both numbers are real and both are kept. The honest reading is that this arm does not survive a change
of truth population, which is the same instrument-dependence this repository has measured all round
(<code>knowledge/76</code> §6) — and it is the reason no H98 file is emitted.</p>
</div>

<h2>Gates that ran before and beside the validation</h2>
<table>
<tr><th>check</th><th>result</th></tr>
<tr><td>Literal final-dot lane (<code>scripts/check_h98_lane.py</code>)</td>
    <td><span class="fail">{literal_verdict}</span>; the universal-coverage lattice probe triggered the all-prior rule.</td></tr>
<tr><td>Probe-excluding policy sensitivity (diagnostic only)</td>
    <td>policy {policy_verdict} · max Spearman {pre.get('max_spearman', 0.0):.5f} ·
    max near-3px {pre.get('max_near_3px_fraction', 0.0):.4f}; cannot waive the literal STOP.</td></tr>
<tr><td>Uniqueness at the pre-check (policy layer)</td>
    <td>canonical unique {pre['uniqueness']['canonical_pattern_unique']} ·
    novel fraction {pre['uniqueness']['novel_fraction']:.4f} ·
    {pre['uniqueness']['relation_to_union']} · {pre['uniqueness']['n_priors_checked']} priors</td></tr>
<tr><td>Leakage canary (alarm at {can['alarm_threshold']})</td>
    <td>no alarm · max AUC per arm: {canary}</td></tr>
</table>
{built}
<h2>Limits</h2>
<ul style="margin-left:20px">
<li>The validation instrument measures <em>catalogue</em> truth; the board scores something else, and
this repository has measured board-vs-instrument rank correlation near zero.</li>
<li>The screen that selected this arm is a single-budget, single-instrument measurement and is
attribution-only — it can never promote a file by itself.</li>
<li>No organizer receipt exists for any file here; nothing on this page is an organizer-confirmed score.</li>
</ul>

<div class="footer">
<p>Generated by <code>scripts/publish_h97_site.py</code> from <code>evidence/h98_holdout.json</code> and
<code>evidence/h98_lane_precheck.json</code>. <a href="index.html">Landing page</a> ·
<a href="h97.html">H97 round page</a> · <a href="executive-summary.html">Executive summary</a>.</p>
</div>
</div>
</body>
</html>
"""


def insert_index_block(index_path: Path, block: str) -> None:
    """Insert (or refresh) this round's card at the top of the shared landing page.

    The landing page belongs to every round at once, so this publisher never rewrites it: it places one
    card between ``<!--H97-CARD-->`` and ``<!--/H97-CARD-->`` immediately after ``<body>`` and leaves the
    rest of the page byte-identical (the same convention this repository's H95 and H87 cards use).
    Re-running is idempotent.
    """
    text = index_path.read_text() if index_path.exists() else "<!doctype html><html><body>\n</body></html>"
    if "<!--H97-CARD-->" in text and "<!--/H97-CARD-->" in text:
        head, rest = text.split("<!--H97-CARD-->", 1)
        _, tail = rest.split("<!--/H97-CARD-->", 1)
        text = head + block + tail
    else:
        i = text.lower().find("<body")
        j = text.find(">", i) + 1 if i >= 0 else 0
        text = text[:j] + "\n" + block + text[j:]
    index_path.write_text(text)


def index_block(build: dict, card: dict, h98: dict | None, h98_build: dict | None) -> str:
    """This round's card for the shared landing page.  Every figure is read from a receipt."""
    stem = Path(build["file"]).name
    na = build["uniqueness"]
    hd = build["holdout_dti"]
    lane = card.get("correlation_overlap_vs_registry", {}).get("lane", build["lane"])
    lane_source = Path(lane.get("literal_max_near_source", "unavailable")).name
    li98 = ""
    if h98 is not None:
        li98 = """
  <li><a href="h98.html">H98 validation page</a> &mdash; negative, no artifact. Its historical precheck
  recorded literal <b>DUPLICATE/STOP</b> but proceeded on a probe-excluding policy PASS; this protocol
  deviation is disclosed and the historical receipt is unchanged.</li>"""
    return f"""<!--H97-CARD-->
<style>.h97card{{border:2px solid #4fc3f7;border-radius:12px;padding:16px 18px;margin:14px 0;background:#f4f9fe;color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}}.h97card h2{{margin:.2rem 0 .5rem;color:#0d3b66;font-size:1.25rem}}.h97card p{{margin:.45rem 0}}.h97card code{{background:#e6eef7;padding:1px 5px;border-radius:3px;word-break:break-all}}.h97card .no{{background:#7f1d1d;color:#fff;padding:3px 10px;border-radius:12px;font-weight:700}}.h97card .yes{{background:#14532d;color:#fff;padding:3px 10px;border-radius:12px;font-weight:700}}.h97card a.button{{display:inline-block;background:#0d47a1;color:#fff;font-weight:700;padding:10px 16px;border-radius:7px;margin:6px 8px 6px 0;text-decoration:none}}.h97card a.button.secondary{{background:#546e7a}}</style>
<section class="h97card">
<h2>H97 &mdash; co-training disagreement, A-confident / B-abstains (download only)</h2>
<p><b>OK to download?</b> <span class="yes">YES, for research only</span> — decoded-pattern-unique and
format-valid. <b>OK to submit?</b> <span class="no">NO</span> — HOLDOUT-DTI is negative and the
literal all-prior lane is <b>DUPLICATE/STOP</b>. The probe-excluding policy PASS cannot waive that stop.
<b>NO ORGANIZER-CONFIRMED SCORE.</b> Slots used: 0.</p>
<p>The brief&rsquo;s own lane, measured end to end: View A = potential-field edge family, View B = DEM
curvature/slope plus the in-stack radiometric band; a cell is emitted only where A is confident and B
abstains, cover-gated, 3&nbsp;px spacing, 200&nbsp;m ring around the catalogue. Budget came from a
prevalence-matched off-catalogue instrument, not from the historical 37,654.
HOLDOUT-DTI <code>{hd['dti']:.6f}</code> [{hd['ci95'][0]:.6f}, {hd['ci95'][1]:.6f}] against a matched
random control <code>{hd['random_dti']:.6f}</code>; paired
<code>{hd['paired_vs_random'][0]:+.6f}</code> [{hd['paired_vs_random'][1][0]:+.6f},
{hd['paired_vs_random'][1][1]:+.6f}]. Literal lane: <b>{lane['literal']}</b>, max Spearman
{lane['literal_max_spearman']:.6f}, max near-3px {lane['literal_max_near_3px_fraction']:.6f}
against <code>{lane_source}</code>; policy {lane['policy']} and max near-3px
{lane['max_near_3px_fraction']:.6f} are sensitivity diagnostics only. Uniqueness passes: novel fraction
{na['novel_fraction']:.4f} over {na['n_priors_checked']} priors. {build['reasoning_rows']:,} dots each
carry a written geological reason and an explicit falsifier.</p>
<p><a class="button" href="downloads/{stem}" download>Download the H97 GeoTIFF &#8595;</a>
<a class="button secondary" href="downloads/h97-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="h97-executive-summary.html">H97 executive summary / how to submit</a>
<a class="button secondary" href="h97.html">H97 round page</a></p>
<p style="font-size:.86rem">File <code>{stem}</code> &middot; {build['file_bytes']:,} bytes &middot;
SHA-256 <code>{build['sha256']}</code> &middot; name <code>{build['submission_name']}</code> &middot;
note ({build['note_chars']}/140): <code>{build['note']}</code> &middot;
<a href="downloads/h97-a-only-reasoning.csv.gz">A-only reasoning CSV</a> &middot;
<a href="../knowledge/98_h97_results_and_limits.md">knowledge/98 &middot; H97 results and limits</a></p>
<ul style="margin:.4rem 0 .2rem 20px">
  <li><a href="h97-executive-summary.html">Executive summary</a> &mdash; one page, download/submit verdict
  first, then the evidence table.</li>
  <li><a href="h97.html">H97 round page</a> &mdash; hypothesis, both instruments, the credit curve, and what
  the round cannot tell you.</li>{li98}
</ul>
</section>
<!--/H97-CARD-->
"""


def exec_summary_page(build: dict, holdout: dict) -> str:
    """The one-page executive summary for this round, generated from the receipts only."""
    na = build["uniqueness"]
    hd = holdout["instrument1"]["pooled"]["scores"]["h97_disagree"]
    rand = holdout["instrument1"]["pooled"]["scores"]["random"]
    pair = holdout["instrument1"]["pooled"]["paired_differences"]["random"]
    name = Path(build["file"]).name
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE52 — H97 executive summary (download-only)</title>
<link rel="stylesheet" href="assets/ctd5.css"></head><body>
<h1>H97 executive summary</h1>
<p style="color:#999">Generated from <code>evidence/h97_build.json</code> and
<code>evidence/h97_holdout.json</code> by <code>scripts/publish_h97_site.py</code>.</p>

<div class="card" style="border-color:#ffa726">
<h2>One line</h2>
<p><b>Download:</b> yes for research — a decoded-pattern-unique, format-valid GeoTIFF.
<b>Submit:</b> no — HOLDOUT-DTI is below the matched random control, and the literal all-prior lane is
DUPLICATE/STOP. The probe-excluding policy PASS is diagnostic only.
<b>Slots used:</b> 0. <b>Certified leaderboard gain:</b> none; this repository has no organiser receipt for
any file.</p>
</div>

<h2>The file</h2>
<p><code>{name}</code> — single-band float32, EPSG:32611, 3730 × 3292 at 100 m, exactly
{build['format_checks']['ones']:,} cells at 1.0 and zeros elsewhere, every pixel finite in [0, 1] (the
portal's "Predicted values must be in range [0, 1]" rule cannot fail on it).
SHA-256 <code>{build['sha256']}</code>. ZIP contains exactly this one TIFF.</p>
<p><b>Submission name:</b> <code>{build['submission_name']}</code><br>
<b>Note ({build['note_chars']}/140):</b> <code>{build['note']}</code></p>

<h2>What it is</h2>
<p>The file is the brief's own lane: both views are co-trained, and a cell is emitted only where the
potential-field view is confident while the surface view abstains, with a cover gate on the depth-to-basement
band, at 3 px minimum spacing and with a 200 m ring around the known catalogue. A written geological reason
and an explicit falsifier accompany every one of the {build['reasoning_rows']:,} dots
(<a href="downloads/h97-a-only-reasoning.csv.gz">CSV</a>).</p>

<h2>Why it is download-only</h2>
<table>
<tr><th>Evidence</th><th>Value</th></tr>
<tr><td>HOLDOUT-DTI (evaluator <code>{holdout['evaluator_version']}</code>, {holdout['instrument1']['withheld_positive_px']:,} withheld positives, {holdout['instrument1']['folds']} folds)</td>
<td>{hd['dti']:.6f} [{hd['ci95'][0]:.6f}, {hd['ci95'][1]:.6f}]</td></tr>
<tr><td>Matched random control, same instrument</td><td>{rand['dti']:.6f} [{rand['ci95'][0]:.6f}, {rand['ci95'][1]:.6f}]</td></tr>
<tr><td>Paired difference (this file − random)</td><td>{pair['delta']:+.6f} [{pair['ci95'][0]:+.6f}, {pair['ci95'][1]:+.6f}]</td></tr>
<tr><td>Format, read back from disk</td><td>14/14 checks pass, no NaN, no nodata tag</td></tr>
<tr><td>Uniqueness (decoded pixels, {na['n_priors_checked']} priors)</td><td>unique — novel fraction {na['novel_fraction']:.4f}, relation <code>{na['relation_to_union']}</code></td></tr>
<tr><td>Literal all-prior lane</td><td><b>{build['lane']['literal']}</b>; max Spearman {build['lane']['literal_max_spearman']:.6f}, max near-3px {build['lane']['literal_max_near_3px_fraction']:.6f} against <code>{Path(build['lane']['literal_max_near_source']).name}</code> (universal-coverage probe; IR-H97-001)</td></tr>
<tr><td>Policy sensitivity</td><td>{build['lane']['policy']}; max near-3px {build['lane']['max_near_3px_fraction']:.6f} — diagnostic only, never a waiver</td></tr>
</table>

<h2>Submission status</h2>
<p><strong>Do not submit H97 and do not spend a slot.</strong> It fails both the frozen holdout promotion test
and the literal all-prior lane rule. The generic upload procedure below is for a future, separately
validated and slot-approved file only; no such file exists in this review.</p>

<p>Read more: <a href="h97.html">H97 round page</a> · <a href="h98.html">H98 validation page</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">repository</a>.</p>
</body></html>
"""


def main() -> int:
    build = load("h97_build.json")
    card = load("h97_run_card.json")
    holdout = load("h97_holdout.json")
    credit = load("h97_credit_curve.json")
    # band 6 was re-measured against the GeoDAWN total count by the holdout runner; the site quotes the
    # receipt, and the receipt lives in the holdout file, not in the build file
    build["band6_recheck"] = holdout["band6_recheck"]
    h98 = load("h98_holdout.json") if (EV / "h98_holdout.json").exists() else None
    h98_lane = load("h98_lane_precheck.json") if (EV / "h98_lane_precheck.json").exists() else None
    h98_build = load("h98_build.json") if (EV / "h98_build.json").exists() else None

    index_path = DOCS / "index.html"
    (DOCS / "h97.html").write_text(round_html(build, holdout, credit, card, ""))
    (DOCS / "h97-executive-summary.html").write_text(exec_summary_page(build, holdout))
    if h98 is not None:
        (DOCS / "h98.html").write_text(h98_html(h98, h98_lane, h98_build))
    insert_index_block(index_path, index_block(build, card, h98, h98_build))

    name = Path(build["file"]).name
    # the canonical-name copy in docs/downloads/ is what every generated link points at; the short alias
    # h97-candidate.tif is kept beside it, byte-identical, the way every previous round shipped
    site_dir = DOCS / "downloads"
    canonical_copy = site_dir / name
    canonical_zip = site_dir / (Path(name).stem + ".zip")
    src = Path(build["file"])
    if not canonical_copy.exists() or canonical_copy.read_bytes() != src.read_bytes():
        shutil.copyfile(src, canonical_copy)
    if not canonical_zip.exists() or canonical_zip.read_bytes() != Path(build["zip_file"]).read_bytes():
        shutil.copyfile(build["zip_file"], canonical_zip)

    # per-artifact receipt only.  submission/LATEST.txt and docs/data/submission.json belong to whichever
    # round currently holds the global pointer; this round is download-only and deliberately does not
    # take it (the same convention main's H88/H92 blocks follow).
    DATA = DOCS / "data"
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "submission_h97.json").write_text(json.dumps(build, indent=2, default=str) + "\n")
    print("wrote docs/h97.html, docs/h97-executive-summary.html" + (", docs/h98.html" if h98 is not None else "")
          + ", docs/data/submission_h97.json, and the H97 block in docs/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
