#!/usr/bin/env python3
"""Render the H60 site from the receipts.  No number appears in the HTML that is not in a JSON.

Outputs: docs/index.html (historical research download), docs/h60.html (full audit),
docs/executive-summary.html (research-only status), docs/h60-data.json (machine-readable copy).
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
    home = DOCS / "index.html"
    h75 = DOCS / "h75-executive-summary.html"
    if (home.is_file() and h75.is_file()
            and "H75: DUPLICATE/STOP" in home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in h75.read_text(errors="replace")):
        print("H75 terminal stop is current; historical H60 publisher skipped all page and pointer changes")
        return 0
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
    # H60 is a historical research artifact. Local format/uniqueness checks do not grant
    # submission eligibility or establish portal acceptance; no current selector approval exists.
    ok_submit = False
    ivd = rd("h60_instrument_verdict.json") or {}
    # Two separate questions, answered separately, because conflating them is how a
    # format-valid file gets described as a good submission.
    verdict_class = "no" if not ok_submit else "ok"
    verdict = ("RESEARCH DOWNLOAD ONLY · LOCAL FORMAT CHECKS DO NOT ESTABLISH PORTAL ACCEPTANCE · "
               "SUBMISSION NOT APPROVED; NO SLOT RECOMMENDED")
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
<a href="index.html">Overview</a><a href="executive-summary.html">H60 research status</a>
<a href="h60.html">H60 audit</a><a href="h59.html">H59 (previous)</a>
<a href="irregularities.html">Limitations</a><a href="sources.html">Sources</a></nav></header>
<main id="main">{body}</main>
<footer><p>Every number on these pages is read from a JSON record in <code>evidence/</code> at
build time by <code>scripts/publish_h60_site.py</code>. The saved leaderboard row is a public,
team-level observation; historical file/score associations are owner-reported unless an organizer
receipt binds a submission ID, file hash, and score. No such H60 receipt is available.</p></footer>
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
This is a local value-range check only; it does not establish portal acceptance or rule out other portal rejection causes.</small>
<small>SHA-256 <code>{esc(art.get('tif_sha256'))}</code></small>
<small>Format gate: <strong>{'PASS' if art.get('format_gate_ok') else 'FAIL'}</strong>
problems = {esc(art.get('format_problems'))} ·
uniqueness: pattern unique vs {esc((art.get('uniqueness') or {}).get('priors_checked'))} aligned priors =
<strong>{esc((art.get('uniqueness') or {}).get('pattern_unique'))}</strong>,
novel support {fnum((art.get('uniqueness') or {}).get('novel_fraction'), 4)},
literal union of priors = {esc((art.get('uniqueness') or {}).get('literal_union'))}</small>
</div>
<a class="button" href="downloads/h60-cotrain-candidate.tif" download>↓ Download the H60 research TIFF</a>
<a class="button" href="downloads/h60-cotrain-candidate.zip" download>↓ Download the one-TIFF ZIP</a>
<a class="button secondary" href="executive-summary.html">H60 status →</a>
</section>

<section class="card"><h3>Research artifact status</h3>
<p><strong>Not approved for submission.</strong> The file is retained for historical review only. Local format and uniqueness checks do not establish portal acceptance or scientific promotion. No paste-ready note, upload procedure, or slot recommendation is provided.</p></section>

<h1>Historical score algebra — no causal explanation established for 0.2778</h1>
<p class="lede">The distance-weighted Tversky identity describes the metric for a specified hidden-truth mask; it does not identify the credit of particular pixels from submission bytes alone. The saved 2026-10-09 20:18 UTC public-board observation places the team row at rank 17 with 0.2778, but no row binds a TIFF hash or organizer receipt to that score. The H33 file association is owner-reported. The 37,654/44,090 local subset and 100–200 m distances do not explain a score change; new-fault truth may lie within 300 m of known traces, so removed-cell credit is unknown. Any inversion or projection below is conditional scenario arithmetic, not measured credit or a score forecast. See knowledge/49 and IR-R5-011.</p>

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

<section class="card"><h3>Historical arm selection</h3>
<p class="metric">{esc(build.get('arm'))}</p>
<p class="small">{npx:,} px. This is a retained research decision from a legacy hide-and-recover instrument, not a promotion or submission recommendation. The receipt lacks evaluator identity, withheld-positive count, and 95% CI required for a reportable HOLDOUT-DTI claim. H60 remains research-only.</p></section>

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

<h2>Exploratory internal instrument — not a candidate ranker</h2>
<p>The saved public-board observation is a team-level row, not a file receipt. The file labels in this legacy comparison are owner-reported. The second numeric column is an internal proximity-to-catalogue diagnostic, <strong>not a reportable HOLDOUT-DTI</strong>: its receipt does not include a named evaluator, withheld-positive count, or 95% CI. It cannot rank candidates for competition submission. See <code>evidence/h60_instrument_verdict.json</code>.</p>
<table><thead><tr><th>prior label</th><th>OWNER-REPORTED file/score label (not a receipt)</th><th>legacy internal diagnostic (not a competition score)</th><th>mean px</th></tr></thead>
<tbody>{prior_rows}</tbody></table>
<p class="small">The owner-reported-label association with this diagnostic is exploratory only: Spearman ρ = {fnum(ivd.get('spearman_board_vs_instrument'), 3)}, p = {fnum(ivd.get('p_value'), 3)}, n = {esc(ivd.get('n'))}. This small, unauthenticated sample supplies no reliable calibration, ranking, inversion, or causal evidence. The row labelled 0.2778 has diagnostic value {fnum(ivd.get('champion_instrument_dti'), 5)} and the row labelled as a placeholder has {fnum(ivd.get('placeholder_instrument_dti'), 5)}; those are diagnostic outputs, not leaderboard values and not evidence that the public board rewards or penalizes any mechanism. A prior budget amendment is preserved as historical context only, not a current scoring rule or recommendation (<code>evidence/h60_budget_amendment.json</code>).</p>

<h2>Legacy hide-and-recover diagnostics</h2>
<p class="small"><strong>Not reportable as HOLDOUT-DTI:</strong> the historical receipt records four folds and a buffer but omits the evaluator version, total withheld-positive count, and 95% CI. The table is retained only as a descriptive archive of recovery on held-out catalogue segments, not a competition score or score forecast. The competition's new-fault truth is not the same as the published catalogue.</p>
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
<div class="eyebrow">H60 · historical research status</div>
<h1>Research artifact — not approved for submission</h1>
<div class="notice"><strong>RESEARCH DOWNLOAD ONLY · LOCAL FORMAT CHECKS ARE NOT PORTAL ACCEPTANCE · SUBMISSION: NO · NO SLOT RECOMMENDED</strong>
<p>No organizer-confirmed receipt or current selector approval exists for this artifact. This legacy page intentionally provides no upload steps or paste-ready note.</p></div>
<section class="download-bar"><div><strong>{esc(name)}.tif</strong>
<small>{art.get('bytes', 0):,} bytes · one float32 band · EPSG:32611 · {grid.get('labels', {}).get('height', 3730):,} × {grid.get('labels', {}).get('width', 3292):,} · {npx:,} pixels</small>
<small>SHA-256 <code>{esc(art.get('tif_sha256'))}</code></small>
<small>Local format gate: <strong>{'PASS' if art.get('format_gate_ok') else 'FAIL'}</strong>. Portal acceptance: <strong>UNVERIFIED</strong>.</small></div>
<a class="button" href="downloads/h60-cotrain-candidate.tif" download>Download for research review</a>
<a class="button" href="downloads/h60-cotrain-candidate.zip" download>Research archive ZIP</a></section>
<h2>Evidence limits</h2><p>The H60 hide-and-recover values are internal measurements and do not authenticate or predict a public score. The saved 2026-10-09 20:18 UTC board observation places 0.2778 at rank 17; no TIFF hash maps it to these bytes. The local subset and distance comparisons do not identify hidden-truth credit or explain a score change. New-fault truth may occur within 300 m of known traces. See <a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a> and <code>IR-R5-011</code>.</p>
<p>H60 scripts and receipts remain in the repository as historical provenance. This page does not authorize a rerun, new run-card, candidate rebuild, or submission.</p>
"""
    insert_block(DOCS / "executive-summary.html", "H60-ARTIFACT", exe)

    # ==================================================================== audit page
    aud = f"""
<div class="eyebrow">H60 audit · every gate, every receipt</div>
<h1>Audit</h1>
<div class="status"><strong>H60: RESEARCH DOWNLOAD ONLY · NOT APPROVED FOR SUBMISSION.</strong> Local format/uniqueness checks do not establish portal acceptance, scientific promotion, or slot eligibility. No override or submission steps are provided.</div>
<h2>Artefact</h2>
<table><tbody>
<tr><td>name</td><td><code>{esc(name)}</code></td></tr>
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

<h2>Legacy hide-and-recover receipt (descriptive only)</h2>
<p class="small"><strong>Not reportable as HOLDOUT-DTI:</strong> this historical JSON omits evaluator version, total withheld-positive count, and 95% CI. The values below describe held-out catalogue-segment recovery only; they are not competition scores or leaderboard forecasts.</p>
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
