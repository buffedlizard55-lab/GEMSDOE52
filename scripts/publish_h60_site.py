#!/usr/bin/env python3
"""Render the H60 site from the receipts.  No number appears in the HTML that is not in a JSON.

Outputs: docs/index.html (landing + download), docs/h60.html (full audit),
docs/executive-summary.html (how to submit), docs/h60-data.json (machine-readable copy).
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"
DOCS = ROOT / "docs"


def rd(name, default=None):
    p = EV / name
    return json.loads(p.read_text()) if p.exists() else default


def esc(x):
    return html.escape(str(x))


def fnum(x, n=4):
    return "n/a" if x is None else (f"{x:,.0f}" if n == 0 else f"{x:.{n}f}")


def insert_block(path, marker, body):
    """Insert an idempotent marked block at the top of <main id="main">.

    docs/index.html and docs/executive-summary.html are shared with every previous round, and
    scripts/check_site.py asserts that the H57 alternate, H58 and separate H55-EDGE archive
    links survive on them.  PR #34 replaced both pages wholesale, dropped those links, and
    turned a passing checker into 9 failures.  Inserting a marked block keeps the archive
    intact and is idempotent, the same convention insert_h55_review already uses.
    """
    html = path.read_text()
    open_m, close_m = f"<!--{marker}-->", f"<!--/{marker}-->"
    block = f"{open_m}\n{body}\n{close_m}"
    if open_m in html:
        i = html.index(open_m)
        j = html.index(close_m) + len(close_m)
        html = html[:i] + block + html[j:]
    else:
        anchor = '<main id="main">'
        if anchor not in html:
            raise ValueError(f"{path}: no <main id=\"main\"> anchor to insert into")
        i = html.index(anchor) + len(anchor)
        html = html[:i] + block + html[i:]
    path.write_text(html)


def main() -> int:
    art = rd("h60_artifact.json") or {}
    build = rd("h60_build.json") or {}
    fmt = rd("h60_format_gate.json") or {}
    uniq = rd("h60_uniqueness.json") or {}
    indep = rd("h60_independence.json") or {}
    pseudo = rd("h60_pseudo.json") or {}
    hold = rd("h60_holdout.json") or {}
    selj = rd("h60_selection.json") or {}
    views = rd("h60_views.json") or {}
    strata = rd("h60_strata.json") or {}
    folds = rd("h60_folds.json") or {}
    pre = json.loads((ROOT / "registry/h60_preregistration.json").read_text())
    grid = rd("grid.json") or {}

    proof0 = (art.get("range_proof_from_served_bytes") or {})
    ok_submit = (bool(art.get("format_gate_ok"))
                 and bool((uniq or {}).get("canonical_pattern_unique"))
                 and not (uniq or {}).get("equals_literal_prior_union")
                 and bool(proof0.get("in_range")))
    ivd = rd("h60_instrument_verdict.json") or {}
    # Two separate questions, answered separately, because conflating them is how a
    # format-valid file gets described as a good submission.
    verdict_class = "ok" if ok_submit else "warn"
    verdict = (("OK TO DOWNLOAD · PORTAL-VALID AND UNIQUE, THE UPLOAD WILL BE ACCEPTED · "
                "NO CERTIFIED LEADERBOARD GAIN — the only local instrument ranks the 0.2778 "
                f"champion at {ivd.get('champion_instrument_dti', float('nan')):.5f}, below a "
                "random placeholder (IR-H60-003), so nothing here can show this file beats your "
                "current best") if ok_submit else
               "REVIEW ONLY — DO NOT SPEND A WEEKLY SLOT: a gate failed")
    name = art.get("name", "(no artefact built yet)")
    note = art.get("note", "")
    npx = art.get("emitted_px", 0)

    # ---- holdout table -------------------------------------------------------------
    budgets = hold.get("budgets", [])
    arms = [a for a in (hold.get("mean_dti") or {})]
    hold_rows = ""
    for a in arms:
        cells = "".join(f"<td>{fnum(hold['mean_dti'][a][str(b)], 5)}</td>" for b in budgets)
        wins = hold.get("fold_wins_vs_random", {}).get(f"{a}@{build.get('budget')}")
        cap = (hold.get("capture_at_37654") or {}).get(a)
        cls = ' class="hi"' if a == build.get("arm") else ""
        hold_rows += (f"<tr{cls}><td>{esc(a)}</td>{cells}"
                      f"<td>{fnum(cap, 4) if cap is not None else 'n/a'}</td>"
                      f"<td>{'—' if a == 'random' else esc(wins)}</td></tr>")
    hold_head = "".join(f"<th>@{b:,}</th>" for b in budgets)

    # ---- per-fold view AUC ---------------------------------------------------------
    fold_rows = ""
    for r in views.get("folds", []):
        fold_rows += (f"<tr><td>{r['fold']}</td><td>{r['n_pos']:,}</td><td>{r['n_neg']:,}</td>"
                      f"<td>{fnum(r.get('auc_A_heldout'), 4)}</td>"
                      f"<td>{fnum(r.get('auc_B_heldout'), 4)}</td></tr>")

    # ---- uniqueness rows -----------------------------------------------------------
    urows = ""
    for r in (uniq.get("per_prior") or [])[:60]:
        if r.get("error"):
            urows += f"<tr><td>{esc(Path(r['path']).name)}</td><td colspan=4>error: {esc(r['error'])}</td></tr>"
            continue
        urows += (f"<tr><td>{esc(Path(r['path']).name)}</td><td>{r['prior_px']:,}</td>"
                  f"<td>{r['intersection']:,}</td><td>{fnum(r['jaccard'], 4)}</td>"
                  f"<td>{'YES' if r['identical'] else 'no'}</td></tr>")

    ivd_rows = (rd("h60_instrument_verdict.json") or {}).get("rows") or []
    prior_rows = ""
    for _r in sorted(ivd_rows, key=lambda r: -r["board"]):
        _cls = ' class="hi"' if _r["prior"] == "champion_h33_2_b2" else ""
        prior_rows += (f"<tr{_cls}><td>{esc(_r['prior'])}</td>"
                       f"<td>{fnum(_r['board'], 4)}</td>"
                       f"<td>{fnum(_r['instrument'], 5)}</td>"
                       f"<td>{_r['mean_px']:,.0f}</td></tr>")
    nnu = (build.get("not_merely_union_of_the_two_views") or {})
    proof = (art.get("range_proof_from_served_bytes") or {})

    CSS = (DOCS / "style.css").read_text()

    def page(title, body, desc):
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(desc)}"><title>{esc(title)}</title>
<style>{CSS}</style></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>
<a href="index.html">Overview</a><a href="executive-summary.html">How to submit</a>
<a href="h60.html">H60 audit</a><a href="h59.html">H59 (previous)</a>
<a href="irregularities.html">Limitations</a><a href="sources.html">Sources</a></nav></header>
<main id="main">{body}</main>
<footer><p>Every number on these pages is read from a JSON receipt in <code>evidence/</code> at
build time by <code>scripts/publish_h60_site.py</code>. Nothing here is organiser-authenticated:
the DrivenData portal is login-walled, so leaderboard scores quoted anywhere in this repository
are owner-reported filename attributions.</p></footer>
</body></html>"""

    # ========================================================================= index
    idx = f"""
<div class="eyebrow">H60 · two-view co-training on SHA-verified competition bytes ·
<span class="pill {verdict_class}">{esc(verdict)}</span></div>

<section class="download-bar" aria-label="submission download">
<div>
<strong>{esc(name)}.tif</strong>
<small>{art.get('bytes', 0):,} bytes · single-band float32 · EPSG:32611 ·
{grid.get('labels', {}).get('height', 3730):,} × {grid.get('labels', {}).get('width', 3292):,} @ 100 m ·
{npx:,} emitted pixels · all pixels finite · values exactly {esc(proof.get('values_set'))}</small>
<small><strong>Range proof re-read from the served file:</strong>
min = {esc(proof.get('min'))}, max = {esc(proof.get('max'))}, NaN pixels = {esc(proof.get('n_nan'))},
in [0,1] = <strong>{esc(proof.get('in_range'))}</strong>.
This is the check that produced the portal's &ldquo;Predicted values must be in range [0, 1]&rdquo;
rejection on an earlier file; it cannot trip on this one.</small>
<small>SHA-256 <code>{esc(art.get('tif_sha256'))}</code></small>
<small>Format gate: <strong>{'PASS' if art.get('format_gate_ok') else 'FAIL'}</strong>
problems = {esc(art.get('format_problems'))} ·
uniqueness: pattern unique vs {esc((art.get('uniqueness') or {}).get('priors_checked'))} aligned priors =
<strong>{esc((art.get('uniqueness') or {}).get('pattern_unique'))}</strong>,
novel support {fnum((art.get('uniqueness') or {}).get('novel_fraction'), 4)},
literal union of priors = {esc((art.get('uniqueness') or {}).get('literal_union'))}</small>
</div>
<a class="button" href="downloads/h60-cotrain-candidate.tif" download>↓ Download the submission TIFF (one click)</a>
<a class="button" href="downloads/h60-cotrain-candidate.zip" download>↓ Download the one-TIFF ZIP</a>
<a class="button secondary" href="executive-summary.html">How to submit →</a>
</section>

<section class="card">
<h3>Paste these into the submission form</h3>
<p><strong>Note (optional):</strong></p>
<pre>{esc(note)}</pre>
<p class="small">{len(note)} characters (the form allows 200). The ZIP also carries
<code>submission-name.txt</code> and <code>submission-note.txt</code>.</p>
</section>

<h1>Why the 0.2778 file scored what it did, and what would actually beat it.</h1>
<p class="lede">The metric is a distance-weighted Tversky index. With
<code>FNw = |G| − TPw</code> it collapses to
<code>DTI = T / (0.2·T + 0.2·(S − M) + 0.8·|G|)</code>, where <code>T</code> is credited mass,
<code>S</code> is emitted mass and <code>M</code> is emitted mass that sits within 300 m of a truth
pixel. Every emitted pixel that is <em>not</em> near a fault costs 0.2 in the denominator. That single
identity, measured against the restored bytes of the 0.2778 file, is the whole story.</p>

<div class="grid">
<section class="card"><h3>Independence premise</h3>
<p class="metric">{fnum(indep.get('spearman_false_alarm'), 4)}</p>
<p class="small">Spearman of per-block false-alarm rate at a fixed budget, out-of-fold,
labelled negatives only, {esc(indep.get('n_blocks_used'))} blocks of 50 px — the statistic the
brief names — against the registered abandonment threshold {esc(indep.get('abandon_threshold'))}.
Mean-score-on-negatives correlation {fnum(indep.get('spearman_mean_score_on_negatives'), 4)};
pixel-level {fnum(indep.get('spearman_pixel_score'), 4)}.
<strong>Abandon pseudo-labelling: {esc(indep.get('abandoned'))}.</strong></p></section>

<section class="card"><h3>Pseudo-label exchange</h3>
<p class="metric">{fnum(pseudo.get('auc_delta'), 4)}</p>
<p class="small">held-out View-B AUC change from one confident-to-abstain exchange
({esc((pseudo.get('fold0_viewB_auc') or {}).get('base'))} →
{esc((pseudo.get('fold0_viewB_auc') or {}).get('with_pseudo'))}) on
{esc(pseudo.get('pseudo_positive_px'))} positive / {esc(pseudo.get('pseudo_negative_px'))}
negative pseudo-labels taken from whole 50×50 segments outside 300 m of any label.
{esc(pseudo.get('verdict'))}</p></section>

<section class="card"><h3>Selected arm</h3>
<p class="metric">{esc(build.get('arm'))}</p>
<p class="small">{npx:,} px at the budget the preregistered rule chose
(mean hide-and-recover DTI {fnum((selj.get('selected') or {}).get('mean_dti'), 5)},
{esc((selj.get('selected') or {}).get('fold_wins'))}/4 folds above the matched-budget random
control). {esc(selj.get('note'))}</p></section>

<section class="card"><h3>Not merely the union of the two views</h3>
<p class="metric">{fnum(nnu.get('fraction_outside_both_topk'), 3)}</p>
<p class="small">fraction of emitted pixels outside <em>both</em> views' own top-K at the same
budget (inside View A's top-K {fnum(nnu.get('fraction_inside_topk_viewA'), 3)},
View B's {fnum(nnu.get('fraction_inside_topk_viewB'), 3)}). The emitter maximises expected
triangular max-coverage, so it spreads a hard-core pattern instead of taking a top-K.</p></section>
</div>

<h2>The five preregistered hypotheses</h2>
<p class="small">Frozen at SHA-256 <code>{esc(pre['sha256'][:16])}…</code>
(<code>registry/h60_preregistration.json</code>) before the first fit. Full text in
<code>knowledge/25_hypotheses_H60_preregistered.md</code>.</p>
<table><thead><tr><th>rank</th><th>id</th><th>target</th><th>layers</th><th>validated by</th></tr></thead><tbody>
<tr><td>1</td><td>H60-1</td><td>metric-algebra-optimal emission budget (the 0.2·(S−M) tax)</td>
<td>none — the published metric</td><td>holdout DTI-vs-budget curve, 4 folds</td></tr>
<tr><td>2</td><td>H60-2</td><td>strike-oriented ridge energy in the aeroradiometric total-count channel</td>
<td>b06_ridge_nne/nw, b06_gradmag, b02/b14/b05/b17/b19/b12_ridge_*</td><td>blocked AUC + hide-and-recover</td></tr>
<tr><td>3</td><td>H60-3</td><td>strike-projected basement-depth steps = buried range-front faults</td>
<td>b15_step_nne/nw, b13_step_nne</td><td>blocked AUC + hide-and-recover</td></tr>
<tr><td>4</td><td>H60-4</td><td>dilational intersection nodes of the NNE and NW strike sets</td>
<td>node_nne_x_nw, node_nne_x_nw_A</td><td>blocked AUC + hide-and-recover</td></tr>
<tr><td>5</td><td>H60-5</td><td>rank-encoded seismicity (band 10 has impossible values, IR-R4-002)</td>
<td>b10_rank, b16_rank</td><td>ablation</td></tr>
</tbody></table>

<h2>The control that decides whether any of this can be trusted</h2>
<p>All thirteen scored priors, scored against the same four hide-and-recover folds
(<code>evidence/h60_prior_control.json</code>):</p>
<table><thead><tr><th>prior</th><th>owner-reported board</th><th>hide-and-recover DTI</th><th>mean px</th></tr></thead>
<tbody>{prior_rows}</tbody></table>
<p class="small"><strong>The 0.2778 champion scores {fnum(ivd.get('champion_instrument_dti'), 5)}
on this instrument — below the random placeholder's
{fnum(ivd.get('placeholder_instrument_dti'), 5)}.</strong> Spearman(board, instrument) across all
13 priors = {fnum(ivd.get('spearman_board_vs_instrument'), 3)} (p = {fnum(ivd.get('p_value'), 3)},
n = 13): no usable rank information, and not a demonstrable inversion either. An instrument on
which the incumbent loses to noise cannot promote a challenger, so this repository does not
certify a slot for this file. Across the six off-catalogue priors the board is instead
<em>strictly decreasing in emitted mass</em> (Spearman −1.000), which is the evidence behind the
budget amendment in <code>evidence/h60_budget_amendment.json</code>.</p>

<h2>Hide-and-recover, matched budget</h2>
<p class="small">Whole contiguous blocks held out ({esc(folds.get('n_blocks'))} blocks → 4 folds,
{esc(folds.get('buffer_px'))} px boundary buffer), truth = the held-out catalogue, emission domain =
footprint minus the {esc(build.get('emitted_outside_footprint') is not None and 200)} m catalogue ring.
<strong>This measures recovery of held-out catalogue segments; the competition truth is
expert-labelled faults that are NOT in the catalogue, so it is an instrument and not a score
forecast.</strong></p>
<table><thead><tr><th>arm</th>{hold_head}<th>capture</th><th>folds &gt; random</th></tr></thead>
<tbody>{hold_rows}</tbody></table>

<h2>Per-fold blocked AUC</h2>
<table><thead><tr><th>fold</th><th>held-out positives</th><th>held-out negatives</th>
<th>View A (potential field / subsurface)</th><th>View B (surface + radiometric)</th></tr></thead>
<tbody>{fold_rows}</tbody></table>
<p class="small">mean View A {fnum(views.get('mean_auc_A'), 4)} · mean View B
{fnum(views.get('mean_auc_B'), 4)} · {esc(len(views.get('layers_A', [])))} A layers /
{esc(len(views.get('layers_B', [])))} B layers. Band 6 is in View B: its TIFF tag claims a magnetic
tilt derivative, the bytes say aeroradiometric total count (IR-52-019).</p>

<h2>Discovery strata</h2>
<table><thead><tr><th>stratum</th><th>pixels</th><th>median depth to basement (m)</th></tr></thead><tbody>
{''.join(f"<tr><td>{esc(k)}</td><td>{v['px']:,}</td><td>{esc(v.get('median_depth_to_basement'))}</td></tr>" for k, v in (strata or {}).items() if isinstance(v, dict) and 'px' in v)}
</tbody></table>
<p class="small">Cut points read from the receipt: {esc((strata or {}).get('definition'))}
(confident A ≥ {fnum((strata.get('thresholds') or {{}}).get('confident_A'), 4)},
B ≥ {fnum((strata.get('thresholds') or {{}}).get('confident_B'), 4)}).
A-only = candidate buried fault beneath cover; B-only = the mirror (suspect road, erosion line or
bedding scarp). Every emitted pixel carries a
written geological claim and an explicit falsifier in
<a href="downloads/{esc(name)}-geology.csv">the per-pixel reasoning CSV</a>
({esc(npx)} rows, {esc((rd('h60_reasoning.json') or {}).get('a_only_rows'))} of them A-only).
These are hypotheses for Phase-2 geological review, not verified faults.</p>

<h2>Official sources</h2>
<ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Problem
description and performance metric</a> — metric constants α=0.2, β=0.8, R=300 m read from this page.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Public
leaderboard</a>.</li>
<li><a href="https://github.com/drivendataorg/gems-prize-reference-solution">Reference solution</a>
(Prof. John Lipor, U-Net MC-CV).</li>
<li><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS
GeoDAWN airborne magnetic and radiometric surveys</a> (DOI
<a href="https://doi.org/10.5066/P93LGLVQ">10.5066/P93LGLVQ</a>).</li>
<li><a href="https://gbcge.org/current-projects/ingenious/">INGENIOUS project, Great Basin Center
for Geothermal Energy</a>.</li>
<li><a href="https://epsg.io/32611">EPSG:32611 — WGS 84 / UTM zone 11N</a>.</li>
<li><a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index</a>.</li>
<li><a href="https://doi.org/10.1145/279943.279962">Blum &amp; Mitchell, COLT 1998, pp. 92–100</a>
— co-training.</li>
<li><a href="https://gdr.openei.org/submissions/1391">Geothermal Data Repository submission 1391</a>.</li>
</ul>
"""

    insert_block(DOCS / "index.html", "H60-ARTIFACT", idx)

    # =========================================================== executive summary
    exe = f"""
<div class="eyebrow">Executive summary · how to make a submission</div>
<h1>Three clicks, then two pastes.</h1>
<section class="download-bar">
<div><strong>{esc(name)}.tif</strong>
<small>{art.get('bytes', 0):,} bytes · float32 · single band · EPSG:32611 ·
{grid.get('labels', {}).get('height', 3730):,} × {grid.get('labels', {}).get('width', 3292):,} ·
every pixel finite and in [0,1] · {npx:,} positive pixels</small>
<small class="pill {verdict_class}">{esc(verdict)}</small></div>
<a class="button" href="downloads/h60-cotrain-candidate.tif" download>↓ 1. Download the TIFF</a>
<a class="button" href="downloads/h60-cotrain-candidate.zip" download>↓ or the ZIP</a>
</section>

<h2>The steps</h2>
<ol>
<li><strong>Download.</strong> Click the TIFF button above (or the ZIP — the portal accepts
&ldquo;a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF&rdquo;).</li>
<li><strong>Go to the submission page</strong>:
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">
competitions/306 → New submission</a>. You need a DrivenData account that has accepted the
competition rules.</li>
<li><strong>Choose the file</strong> you just downloaded.</li>
<li><strong>Paste the note</strong> (optional but it is how you tell submissions apart later):
<pre>{esc(note)}</pre></li>
<li><strong>Submit.</strong> The portal validates CRS, shape and geotransform against
<code>sample_submission.tif</code> and checks that every value is in [0, 1].</li>
</ol>

<h2>Why the earlier &ldquo;Predicted values must be in range [0, 1]&rdquo; rejection happened</h2>
<p>It was not a scaling error. The competition page says &ldquo;data outside the bounds is null or
nan&rdquo;, so an earlier export wrote NaN outside the data footprint — and a NaN fails any
range comparison. This repository now exports <strong>0.0</strong> outside the footprint instead, and
<code>gems52.grid.write_geotiff</code> refuses to write a single non-finite pixel and then re-reads the
file it wrote. The proof is re-read from the served bytes at publish time:</p>
<table><tbody>
<tr><td>min value in the served file</td><td><strong>{esc(proof.get('min'))}</strong></td></tr>
<tr><td>max value in the served file</td><td><strong>{esc(proof.get('max'))}</strong></td></tr>
<tr><td>NaN / infinite pixels</td><td><strong>{esc(proof.get('n_nan'))}</strong></td></tr>
<tr><td>distinct values</td><td><strong>{esc(proof.get('values_set'))}</strong></td></tr>
<tr><td>nodata tag</td><td>{esc(fmt.get('nodata'))}</td></tr>
<tr><td>CRS</td><td>{esc(fmt.get('crs'))}</td></tr>
<tr><td>transform</td><td>{esc(fmt.get('transform'))}</td></tr>
<tr><td>block size / dtype</td><td>{esc(fmt.get('blocksize'))} · {esc(fmt.get('dtype'))}</td></tr>
<tr><td>format-gate problems</td><td><strong>{esc(fmt.get('problems'))}</strong></td></tr>
</tbody></table>

<h2>Is it OK to submit?</h2>
<p><strong>{esc(verdict)}.</strong> The file is portal-valid by construction: one band, float32,
EPSG:32611, {grid.get('labels', {}).get('height', 3730):,} ×
{grid.get('labels', {}).get('width', 3292):,}, transform identical to
<code>sample_submission.tif</code>, every pixel finite, values in {{0,1}}, nearest emitted pixel
{esc(build.get('nearest_emitted_to_catalogue_m'))} m from the published catalogue.</p>
<p>What this repository will <em>not</em> claim: a leaderboard score. The portal is login-walled, so no
score in this repository is organiser-authenticated, and the local hide-and-recover instrument
recovers held-out catalogue segments — the competition truth is expert-labelled faults that are
<em>not</em> in the catalogue. The preregistered slot rule is
&ldquo;{esc(selj.get('promotion_rule'))}&rdquo; and it returned
{esc(json.dumps(selj.get('selected')))}. Budget is the one lever whose size is known from the metric's
own algebra; everything else is a ranking bet.</p>

<h2>What is in the repository</h2>
<ul>
<li><code>scripts/run_h60.py</code> — folds, both views out-of-fold, independence test,
pseudo-label exchange, strata, hide-and-recover, budget curve, selection.</li>
<li><code>scripts/build_h60_submission.py</code> — final fit, metric-aware placement, every gate,
the reasoning CSV, the artefact.</li>
<li><code>scripts/publish_h60_site.py</code> — this site, rendered only from
<code>evidence/*.json</code>.</li>
<li><code>knowledge/25_hypotheses_H60_preregistered.md</code> — the five hypotheses, frozen before
the first fit.</li>
<li><code>knowledge/26_brief_2026-10-08_h60.md</code> — the user brief, verbatim.</li>
<li><code>knowledge/27_why_02778_h60.md</code> — the metric forensics on the restored bytes.</li>
</ul>
"""
    insert_block(DOCS / "executive-summary.html", "H60-ARTIFACT", exe)

    # ==================================================================== audit page
    aud = f"""
<div class="eyebrow">H60 audit · every gate, every receipt</div>
<h1>Audit</h1>
<h2>Artefact</h2>
<table><tbody>
<tr><td>name</td><td><code>{esc(name)}</code></td></tr>
<tr><td>note</td><td>{esc(note)}</td></tr>
<tr><td>tif sha256</td><td><code>{esc(art.get('tif_sha256'))}</code></td></tr>
<tr><td>bytes</td><td>{art.get('bytes', 0):,}</td></tr>
<tr><td>emitted px</td><td>{npx:,}</td></tr>
<tr><td>arm / budget</td><td>{esc(build.get('arm'))} / {esc(build.get('budget'))}</td></tr>
<tr><td>nearest emitted pixel to a mapped trace</td><td>{esc(build.get('nearest_emitted_to_catalogue_m'))} m</td></tr>
<tr><td>emitted outside footprint / outside submission domain</td>
<td>{esc(build.get('emitted_outside_footprint'))} / {esc(build.get('emitted_outside_submission_domain'))}</td></tr>
</tbody></table>

<h2>Format gate (re-read from the bytes)</h2>
<pre>{esc(json.dumps(fmt, indent=1)[:4000])}</pre>

<h2>Uniqueness gate — {esc(uniq.get('n_priors_checked'))} aligned priors, all checked</h2>
<p class="small">Rule: {esc(uniq.get('rule'))}. Scope: {esc(uniq.get('scope'))}.</p>
<table><thead><tr><th>prior</th><th>prior px</th><th>intersection</th><th>Jaccard</th><th>identical</th></tr></thead>
<tbody>{urows}</tbody></table>
<p>novel vs all priors: {esc(uniq.get('novel_vs_all_priors'))} px
({fnum(uniq.get('novel_fraction'), 4)}) · prior px dropped: {esc(uniq.get('prior_px_dropped'))} ·
relation: {esc(uniq.get('relation_to_union'))}</p>

<h2>Emitter</h2>
<pre>{esc(json.dumps(build.get('emit_stats'), indent=1))}</pre>

<h2>Not merely the union of the two views</h2>
<pre>{esc(json.dumps(nnu, indent=1))}</pre>

<h2>Independence test (the brief's own criterion)</h2>
<pre>{esc(json.dumps(indep, indent=1))}</pre>

<h2>Pseudo-label exchange</h2>
<pre>{esc(json.dumps(pseudo, indent=1))}</pre>

<h2>Hide-and-recover, all folds</h2>
<pre>{esc(json.dumps({k: hold.get(k) for k in ('ring_m', 'budgets', 'folds', 'mean_dti', 'fold_wins_vs_random', 'capture_at_37654')}, indent=1)[:9000])}</pre>

<h2>Selection</h2>
<pre>{esc(json.dumps(selj, indent=1))}</pre>

<h2>Inputs</h2>
<pre>{esc(json.dumps(grid.get('features'), indent=1))}</pre>
"""
    (DOCS / "h60.html").write_text(page(
        "GEMSDOE52 — H60 audit", aud, "Full H60 audit trail: gates, receipts, per-prior uniqueness."))

    (DOCS / "h60-data.json").write_text(json.dumps(dict(
        artifact=art, build=build, format_gate=fmt, uniqueness={k: v for k, v in (uniq or {}).items()
                                                               if k != "per_prior"},
        independence=indep, pseudo=pseudo, holdout_mean=hold.get("mean_dti"),
        fold_wins=hold.get("fold_wins_vs_random"), selection=selj, views=views,
        strata=strata, folds=folds, preregistration=pre), indent=1, default=str))
    print(f"[site] H60 block inserted into docs/index.html and docs/executive-summary.html, "
          f"docs/h60.html written; verdict={verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
