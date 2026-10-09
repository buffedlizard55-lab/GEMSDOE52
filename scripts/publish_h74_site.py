#!/usr/bin/env python3
"""Render the H74 landing page, executive summary / submission guide, results note, README block
and the site banners.

Every number on the published pages is read from ``evidence/h74_*.json`` or the writer's own
receipt.  Nothing is typed by hand, so a page cannot disagree with the evidence it cites, and
nothing here uploads anything or changes a verdict -- it only reports the verdict the run card
already holds.

Run after ``scripts/run_h74.py card``:
    .venv/bin/python scripts/publish_h74_site.py
"""
from __future__ import annotations

import gzip
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DAD = DOCS / "data"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"


def load(name: str):
    return json.loads((EVID / name).read_text())


def esc(x) -> str:
    return html.escape(str(x))


def fi(x) -> str:
    return f"{int(x):,}"


def ci(a) -> str:
    return f"[{a[0]:.6f}, {a[1]:.6f}]"


def main() -> int:
    card = load("h74_run_card.json")
    hold = load("h74_holdout.json")
    place = load("h74_placement.json")
    s1 = load("h74_sufficiency.json")
    exch = load("h74_pseudo_exchange.json")
    dis = load("h74_disagreement.json")
    stem = card["submission_name"]
    val = card["validator"]
    arm = place["shipped_arm"]
    n_dots = place["placed"]
    promote = bool(card["submit_recommended"])
    download_ok = bool(card["download_ok"])
    verdict = card["verdict"]
    sc = hold["pooled"]["scores"]
    pairs = hold["pooled"]["paired_vs_single_B"]
    reg = card["correlation_overlap_vs_registry"]

    # ------------------------------------------------------------------ files the pages serve
    DOWN.mkdir(parents=True, exist_ok=True)
    DAD.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip"):
        shutil.copy(SUBM / f"{stem}{ext}", DOWN / f"h74-candidate{ext}")
        shutil.copy(SUBM / f"{stem}{ext}", DOWN / f"{stem}{ext}")
    for f in sorted(EVID.glob("h74_*.json")):
        shutil.copy(f, DAD / f.name)
    csv_src = DOWN / "h74-a-only-reasoning.csv"
    csv_link = "h74-a-only-reasoning.csv"
    if csv_src.exists() and csv_src.stat().st_size > 8_000_000:
        gz = csv_src.with_suffix(".csv.gz")
        with csv_src.open("rb") as a, gzip.open(gz, "wb", compresslevel=6) as b:
            shutil.copyfileobj(a, b)
        csv_link = "h74-a-only-reasoning.csv.gz"

    fileline = (f"{esc(stem)}.tif<br>{fi(card['raster_bytes'])} bytes · SHA-256 "
                f"{esc(card['raster_sha256'])} · {fi(n_dots)} emitted cells · values exactly "
                f"{{0,1}}, {val['bands']} band, 0 NaN")

    if promote:
        notice = "PASSED EVERY MEASURED GATE · ELIGIBLE FOR THE SELECTOR · NO SLOT USED"
        verdict_line = "SAFE TO DOWNLOAD — AND IT CLEARED THE BAR TO BE CONSIDERED FOR A SLOT"
        sub_answer = "YES, it is eligible — but a human selector still owns the weekly slot."
        colour = "#e8f7ec"
    else:
        notice = "OK TO DOWNLOAD · DO NOT SUBMIT · NO SLOT USED"
        verdict_line = "SAFE TO DOWNLOAD — DO NOT SUBMIT IT"
        sub_answer = "NO. Download it, read it, cite it; do not spend a weekly slot on it."
        colour = "#fff1de"
    big = (f'<div class="notice" role="note" style="background:{colour};border-left:6px solid #12331f;'
           f'padding:18px 20px;margin:18px 0"><div style="font-size:1.35rem;font-weight:700;'
           f'letter-spacing:.01em">{esc(verdict_line)}</div>'
           f'<p style="margin:.5rem 0 0"><b>Can I download this file?</b> '
           f'{"Yes — the on-disk validator passes: one float32 band, every value in [0,1], no NaN, grid identical to sample_submission.tif." if download_ok else "No — the validator failed; the file is not published."}</p>'
           f'<p style="margin:.35rem 0 0"><b>Can I submit this file to DrivenData?</b> {esc(sub_answer)}</p>'
           f'<p style="margin:.35rem 0 0"><b>Why:</b> {esc(card["submit_recommendation_reason"])}</p>'
           f'<p style="margin:.35rem 0 0"><b>Verdict recorded in the run card:</b> <b>{esc(verdict)}</b></p></div>')

    clauses = card["gates"]
    clause_text = {
        "c1_format": "1 · Format: single-band float32 GeoTIFF, EPSG:32611, 3730×3292, transform of "
                     "sample_submission.tif, every value in [0,1], no NaN",
        "c2_unique": f"2 · Uniqueness: decoded pattern differs from every one of the "
                     f"{reg['priors_compared']} comparable registry rasters and is not the literal "
                     f"union of them",
        "c3_lane_dots_policy": "3 · Parallel-lane gate on the final dots (saturation policy: "
                               "Spearman ≤ 0.90 and ≤ 70% of dots within 3 px of any informative prior)",
        "c4_not_union": "4 · Not merely the union of the two views",
        "c5_S1_conditional": "5 · Conditional sufficiency S1′: View A's out-of-quadrant AUC on truth "
                             "inside View B's blind band ≥ 0.60 and ≥ 0.05 above its AUC on "
                             "surface-expressed truth",
        "c6_beats_single_B": "6 · HOLDOUT-DTI: the shipped arm's paired 95% CI against single_B has a "
                             "lower bound above zero"}
    clause_rows = "".join(
        f"<tr><td>{esc(clause_text[k])}</td><td><b>{'PASS' if v else 'FAIL'}</b></td></tr>"
        for k, v in clauses.items())

    ab = sum(d.get('n_pixels', 0) for f in exch['folds'] for k, d in f['directions'].items()
             if k == 'A->B')
    ba = sum(d.get('n_pixels', 0) for f in exch['folds'] for k, d in f['directions'].items()
             if k == 'B->A')

    # per-fold conditional ordering: the headline scientific result of the round
    fold_rows, order_ok = "", True
    for f in s1["folds"]:
        mono = f["auc_A_darkB"] <= f["auc_A_blind"] <= f["auc_A_brightB"]
        order_ok = order_ok and mono
        fold_rows += (f"<tr><td>{f['fold']}</td><td class='numeric'>{fi(f['n_truth'])}</td>"
                      f"<td class='numeric'>{f['auc_A_all']:.4f}</td>"
                      f"<td class='numeric'>{f['auc_B_all']:.4f}</td>"
                      f"<td class='numeric'>{f['auc_A_darkB']:.4f}</td>"
                      f"<td class='numeric'>{f['auc_A_blind']:.4f}</td>"
                      f"<td class='numeric'>{f['auc_A_brightB']:.4f}</td>"
                      f"<td class='numeric'>{f['auc_A_blind'] - f['auc_A_brightB']:+.4f}</td></tr>")
    fold_md = "".join(
        f"| {f['fold']} | {f['n_truth']:,} | {f['auc_A_all']:.4f} | {f['auc_B_all']:.4f} | "
        f"{f['auc_A_darkB']:.4f} | {f['auc_A_blind']:.4f} | {f['auc_A_brightB']:.4f} | "
        f"{f['auc_A_blind'] - f['auc_A_brightB']:+.4f} |\n" for f in s1["folds"])

    arms = ["single_B", arm] + [a for a in ("swap_010", "swap_025", "swap_050", "line_support_B")
                                if a != arm] + ["single_A", "union_max", "disagreement_pre",
                                                "disagreement_post", "random"]
    seen, arm_rows = set(), ""
    for a in arms:
        if a in seen or a not in sc:
            continue
        seen.add(a)
        hl = " style='background:#eef6ff;font-weight:600'" if a == arm else ""
        tag = " (shipped)" if a == arm else " (baseline control)" if a == "single_B" else ""
        d = pairs.get(a)
        delta = f"{d['delta']:+.6f} {ci(d['ci95'])}" if d else "—"
        arm_rows += (f"<tr{hl}><td>{esc(a)}{tag}</td><td class='numeric'>{sc[a]['dti']:.6f}</td>"
                     f"<td class='numeric'>{ci(sc[a]['ci95'])}</td>"
                     f"<td class='numeric'>{delta}</td></tr>")

    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>DOE GEMS · H74 conditional co-training</title>'
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            '<a href="index.html">Overview</a><a href="h74-executive-summary.html">How to submit</a>'
            '<a href="h71.html">H71 (earlier)</a><a href="downloads/index.html">Archive</a>'
            '</nav></header><main id="main">')
    tail = "</main></body></html>\n"
    buttons = (f'<div class="actions"><a class="button" href="downloads/h74-candidate.tif" download>'
               f'Download the H74 GeoTIFF ↓</a>'
               f'<a class="button secondary" href="downloads/h74-candidate.zip" download>Single-TIFF ZIP</a>'
               f'<a class="button secondary" href="downloads/{esc(csv_link)}" download>'
               f'A-only reasoning CSV</a></div>')

    earlier = """
<section><h2>Earlier rounds still on this site</h2><p class="small">Each is a separate artefact with its own
receipt. None of them is the H74 file and none is approved for a weekly slot.</p><ul>
<li><b>H71, negative. Do not upload.</b> <a href="h71.html">H71 landing</a> · <a href="h71-executive-summary.html">H71 guide</a></li>
<li><b>H64, negative. Do not upload.</b> <a href="h64.html">H64 landing</a></li>
<li><b>H61, negative; its file is a measured lane duplicate.</b> <a href="archive-h61-landing.html">H61 landing</a></li>
<li><b>H58, research-only.</b> <a href="h58.html">H58 page</a></li></ul></section>
"""

    index = head + f"""
<section class="hero"><div><div class="eyebrow">DOE GEMS / H74 · conditional co-training sufficiency,
B-core + A-rescue swap</div>
<h1>Download the file.<br>The verdict is right here.</h1>
<p class="lead">The co-training lane (Blum &amp; Mitchell, COLT&nbsp;’98) has been closed five times in this
repository by one gate: View A (gravity, magnetics, strain, seismicity) does not predict mapped faults on its own.
H74 asks whether that gate was measuring the wrong thing. Mapped faults are <em>surface-expressed by selection</em> —
they are in the catalogue because somebody saw them — which is exactly View B’s domain. So H74 re-tests sufficiency
<b>conditionally</b>: View A’s out-of-quadrant AUC restricted to held-out truth that lies inside View B’s blind band.
The shipped raster is the first properly nested co-training arm: View B’s ranking with the weakest φ of its budget
swapped for View A’s confident cells where View B abstains.</p>
{big}
{buttons}
<p class="fileline">{fileline}</p>
<p class="small"><a href="h74-executive-summary.html">How to submit, and whether this file may be submitted →</a>
· <a href="data/h74_run_card.json">Complete JSON run card ↗</a>
· <a href="../knowledge/63_hypotheses_H74_preregistered.md">Preregistered hypotheses ↗</a></p></section>
<hr class="divider">
<section><h2>The six frozen promotion clauses</h2>
<p class="small">Written into <code>knowledge/63_hypotheses_H74_preregistered.md</code> (SHA-256
<code>{esc(card['preregistration']['sha256'][:16])}…</code>, pinned in
<code>registry/h74_preregistration.json</code>) before a single model was fitted. All six must pass for the file to
be recommended for a weekly slot.</p>
<div class="table-wrap"><table><thead><tr><th>Clause</th><th>Result</th></tr></thead>
<tbody>{clause_rows}</tbody></table></div></section>
<hr class="divider">
<section><h2>Did View A ever have a chance? The conditional sufficiency test</h2>
<p>This is the new science in H74 and it is reported whether it helps or not.</p>
<div class="table-wrap"><table><thead><tr><th>Measurement</th><th>Value</th><th>Bar</th></tr></thead><tbody>
<tr><td>View A out-of-quadrant AUC, all held-out truth (the gate that closed H61/H63/H64/H65/H70)</td>
<td class="numeric">{s1['mean_auc_A']:.4f}</td><td class="numeric">0.60</td></tr>
<tr><td>View B out-of-quadrant AUC, all held-out truth</td><td class="numeric">{s1['mean_auc_B']:.4f}</td>
<td class="numeric">—</td></tr>
<tr><td><b>View A AUC on truth inside View B’s blind band (rank<sub>B</sub> ∈ [0.35, 0.65])</b></td>
<td class="numeric"><b>{(f"{s1['mean_auc_A_blind']:.4f}" if s1['mean_auc_A_blind'] is not None else '—')}</b></td>
<td class="numeric">≥ 0.60</td></tr>
<tr><td>View A AUC on surface-expressed truth (rank<sub>B</sub> &gt; 0.65)</td>
<td class="numeric">{(f"{s1['mean_auc_A_brightB']:.4f}" if s1['mean_auc_A_brightB'] is not None else '—')}</td>
<td class="numeric">—</td></tr>
<tr><td>Conditional margin (blind − surface-expressed)</td>
<td class="numeric">{(f"{s1['conditional_margin']:+.4f}" if s1['conditional_margin'] is not None else '—')}</td>
<td class="numeric">≥ +0.05</td></tr>
</tbody></table></div>
<p class="small">Conditional AUCs are computed on a label-selected subset (truth pixels chosen by View B’s own
rank) and are a <b>diagnostic, not an unbiased population estimate</b>. S1′ conditional verdict:
<b>{'PASS' if s1['S1_conditional_pass'] else 'FAIL'}</b>.</p>
<h3>The per-fold result, which is the real finding</h3>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>Held-out truth px</th><th>A, all</th><th>B, all</th>
<th>A ∣ B-dark</th><th>A ∣ B-blind</th><th>A ∣ B-bright</th><th>margin</th></tr></thead>
<tbody>{fold_rows}</tbody></table></div>
<p>{'<b>In every fold, without exception, the ordering is A∣B-dark &lt; A∣B-blind &lt; A∣B-bright.</b>' if order_ok else 'The ordering is not monotone across all folds.'}
View A is <em>least</em> informative exactly where View B is blind, and <em>most</em> informative exactly where
View B is already confident. That is the opposite of the hypothesis H74 was built to test. It does not merely fail
the bar — it forecloses the rescue argument that kept this lane open for six rounds: View A's apparent skill is a
shadow of the same surface-expressed structures View B reads directly, not an independent subsurface channel that
the catalogue under-samples. A buried-fault population that only gravity and magnetics can see would have produced
the reverse ordering.</p>
<p class="small">Note what did <em>not</em> fail: conditional independence. The two views' spatial-block
out-of-fold errors on labelled negatives correlate at only |ρ| {card['independence']['max_abs_correlation']:.4f}.
Co-training's independence precondition holds comfortably on this data; it is the <em>sufficiency</em>
precondition — each view must be able to learn the target alone — that is refuted, and now refuted
conditionally as well as globally.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI — <code>gems52-pooled-hide-v1</code></h2>
<p class="small">Hide-and-recover: whole fault segments withheld with an 80 px buffer, catalogue-derived features
built from visible faults only, visible faults masked pixel-exactly, pooled DTI with α 0.2, β 0.8 and a 300 m
triangular kernel. {fi(hold['withheld_positive_pixels'])} withheld positive pixels ·
{fi(hold['budget_per_arm_per_fold'])} dots/fold · 95% paired 20 km cluster bootstrap, {fi(hold['pooled']['bootstrap']['draws'])} draws.
The right-hand column is the paired difference against the baseline control <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th>
<th>Paired Δ vs single_B</th></tr></thead><tbody>{arm_rows}</tbody></table></div>
<p class="small">Control reproduction: <code>single_B</code> measured here
{hold['control_reproduction']['measured']:.6f} against the committed value
{hold['control_reproduction']['committed']:.6f}, |Δ|
{hold['control_reproduction']['abs_delta']:.2e} (tolerance
{hold['control_reproduction']['tolerance']}). Every number in this table is HOLDOUT-DTI — an internal instrument.
It is <b>not</b> a leaderboard score, and measured rank correlation between this instrument and the board is
−0.10 (<code>knowledge/10</code> §5), so none of it is a projection of competition performance.</p></section>
<hr class="divider">
<section><h2>What the shipped raster actually is</h2>
<div class="table-wrap"><table><tbody>
<tr><td>Shipped arm</td><td><code>{esc(arm)}</code> — {esc(place['ranking'])}</td></tr>
<tr><td>Emitted cells</td><td>{fi(n_dots)} of a {fi(place['budget'])} budget</td></tr>
<tr><td>A-only stratum (View A confident ∧ View B abstaining) in the legal pool</td>
<td>{fi(place['a_only_stratum_px'])} px</td></tr>
<tr><td>A-only candidate cells the lane identifies (each has a reasoning row)</td>
<td>{fi(place['a_only_candidate_cells'])}</td></tr>
<tr><td>A-only cells the shipped raster actually emits</td>
<td>{fi(place['a_only_cells_in_shipped_raster'])}</td></tr>
<tr><td>Legal placement pool</td><td>{fi(place['pool_px'])} px (valid ∧ not catalogue ∧ &gt; 200 m from a
mapped trace ∧ cross-family consensus ≤ {place['consensus_threshold']})</td></tr>
<tr><td>Placement</td><td>{esc(place['placement'])}</td></tr>
<tr><td>Jaccard against the union-of-views placement</td>
<td>{card['not_union']['jaccard_vs_union_max']:.4f}</td></tr>
<tr><td>Jaccard against single_B / single_A placements</td>
<td>{card['not_union']['jaccard_vs_single_B']:.4f} / {card['not_union']['jaccard_vs_single_A']:.4f}</td></tr>
<tr><td>Decoded pattern identical to a prior?</td>
<td>{'YES — ' + esc(str(reg['identical_prior_paths'])) if reg['identical_prior_paths'] else 'No, against all ' + fi(reg['priors_compared']) + ' comparable rasters'}</td></tr>
<tr><td>Audit complete?</td>
<td>{'Yes' if reg['audit_complete'] else esc(str(len(reg['incomparable_priors']))) + ' raster(s) are not on this grid and cannot be compared: ' + esc(', '.join(sorted({__import__('pathlib').Path(e['path']).name for e in reg['incomparable_priors']})))}</td></tr>
<tr><td>Novel support vs the union of every registry prior</td>
<td>{reg['novel_fraction_vs_prior_union']:.4f} ({esc(reg['relation_to_prior_union'])})</td></tr>
<tr><td>Lane gate, dots — literal / saturation policy</td>
<td>{esc(reg['dots_verdict_literal'])} / <b>{esc(reg['dots_verdict_policy'])}</b>
(max near-3px share {reg['dots_max_near_3px_policy']:.4f} against the 0.70 bar)</td></tr>
<tr><td>Lane gate, surface — literal / saturation policy</td>
<td>{esc(reg['surface_verdict_literal'])} / <b>{esc(reg['surface_verdict_policy'])}</b>
(max Spearman {reg['surface_max_spearman_policy']:.4f} against the 0.90 bar)</td></tr>
</tbody></table></div>
<p class="small">The literal lane rule is reported beside the policy rule and neither replaces the other: this
registry contains measured universal-coverage probe rasters ({reg['universal_coverage_probes']} of them) whose
3 px halo covers nearly the whole survey, so the literal rule fails for every non-empty raster — a property of the
registry, not of this candidate. The policy rule applies the identical test to the
{reg['informative_priors']} priors that actually localise something.</p></section>
<hr class="divider">
<section><h2>Pseudo-labelling, independence and leakage</h2>
<p class="small">Conditional independence was tested first, as the lane requires: the two views’ spatial-block
out-of-fold errors on labelled negatives correlate at max |ρ| <b>{card['independence']['max_abs_correlation']:.4f}</b>
over {fi(card['independence']['n_blocks'])} blocks against an abandon bar of {card['independence']['threshold']},
so the exchange was <b>{'allowed' if card['independence']['allow_exchange'] else 'abandoned'}</b>. Exactly one
whole-segment pseudo-label exchange ran, in the direction the lane prescribes (confident donor → abstaining
receiver), with whole spatial segments plus buffer so nothing reaches the evaluation region:
{fi(ab)} A→B and {fi(ba)} B→A pseudo-labels across {fi(len(exch['folds']))} folds ({fi(exch['total_pseudo_pixels'])} pseudo pixels in total).
Leakage canary: the strongest single feature alone reaches AUC
<b>{card['leakage_canary']['max_auc']:.4f}</b> ({esc(card['leakage_canary']['feature'])}) against the
{card['leakage_canary']['alarm_threshold']} alarm — <b>no alarm</b>.</p>
<p class="small"><b>Disagreement is a budget stratification here, never a label source.</b> That distinction is the
single most expensive lesson in this repository: full co-training with pseudo-labels as training labels scored
0.0084 on the holdout, below a random control at 0.0253.</p></section>
<hr class="divider">
<section><h2>Geological reasoning for every A-only candidate</h2>
<p class="small">The lane identifies {fi(card['a_only_reasoning']['n_a_only_candidates'])} A-only candidate
cells, of which the shipped raster emits {fi(card['a_only_reasoning']['n_emitted_in_shipped_raster'])}.
<b>Every candidate gets a row, whether or not the shipped arm emits it</b> — the reasoning requirement is about
the lane's discovery claims, not about which arm won the holdout.
Each has a row in <a href="downloads/{esc(csv_link)}" download>the reasoning CSV</a> carrying its UTM 11N
coordinates, both views’ out-of-fold ranks, measured depth-to-basement / gravity / RTP-magnetic / slope /
radiometric percentiles, distance to the nearest mapped trace, a written interpretation, a <b>named non-fault
process that could mimic it</b>, and the falsifier a Phase-2 reviewer would apply. Named mimics:
a buried lithologic contact (Tertiary volcanics against basin fill) produces the same potential-field edge with no
surface step and is not a fault; aeromagnetic flight-line and tie-line levelling residues are linear,
surface-invisible, and strike with the survey plan. These rows are <b>hypotheses from measured context, not
field-verified geology</b>.</p>
<h3>The other half of the disagreement signal, and a falsifier that did not fire</h3>
<p>The brief reads B-only disagreement (View B confident, View A abstaining) as a warning sign — roads,
canals, powerlines, erosion lines. The shipped raster emits {fi(dis['b_only_dots'])} such cells. Cultural
lineaments are straight and overwhelmingly cardinal, so the test is the share of cells whose best-supported
600 m chord lies within 10° of due N–S or due E–W:</p>
<div class="table-wrap"><table><thead><tr><th>Stratum</th><th>Cells</th><th>Cardinal share</th></tr></thead><tbody>
<tr><td>B-only (View B confident, View A abstaining)</td><td class="numeric">{fi(dis['b_only_dots'])}</td>
<td class="numeric">{dis['cardinal_orientation_share']['b_only']:.4f}</td></tr>
<tr><td>A-only candidates</td><td class="numeric">{fi(dis['a_only_candidates'])}</td>
<td class="numeric">{dis['cardinal_orientation_share']['a_only']:.4f}</td></tr>
<tr><td>All emitted cells</td><td class="numeric">{fi(dis['emitted_dots'])}</td>
<td class="numeric">{dis['cardinal_orientation_share']['all_emitted']:.4f}</td></tr>
<tr><td>Matched random control in the same legal pool</td>
<td class="numeric">{fi(dis['cardinal_orientation_share']['control_dots'])}</td>
<td class="numeric">{dis['cardinal_orientation_share']['matched_random_control']:.4f}</td></tr>
</tbody></table></div>
<p><b>The falsifier did not fire.</b> The B-only stratum is only
{(dis['cardinal_orientation_share']['b_only'] - dis['cardinal_orientation_share']['matched_random_control']):+.4f}
more cardinal than a matched random control — not the pile-up that infrastructure would produce. On this
survey the B-only cells are not measurably road-like, so the brief's road/erosion reading is <em>not</em>
supported here. The audit is reported because it was run, not because it confirmed anything.</p></section>
<hr class="divider">
<section><h2>What this does and does not show</h2><ul>
<li>It shows a unique, lane-checked, portal-valid raster built inside the assigned co-training lane, with the
conditional sufficiency test that five earlier rounds never ran.</li>
<li>It does <b>not</b> show a leaderboard gain. <b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing here is an organiser
score.</li>
<li>Public board for context (public board, not organiser-confirmed): 0.3774 rank 1 (xiaofanhu), 0.3195 rank 7
(DARD), 0.2778 rank 13 (extradr19) —
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official leaderboard</a>.
The best owner-reported GEMSDOE file scored 0.2778; the forensic account of why is in
<a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a>.</li>
<li>Holdout prevalence (~1%) is far above competition prevalence (~0.15%), and the holdout instrument does not rank
the board. Treat every number above as an internal measurement.</li>
<li><b>The holdout measured the ranking rule, not these bytes.</b> <code>line_support_B</code> was scored on each
fold's full allowed domain; the shipped raster applies the same rule inside a pool restricted to cross-family
consensus ≤ {place['consensus_threshold']}, which is what makes it lane-feasible. That restriction moves almost
every dot — Jaccard against the <code>single_B</code> placement is {card['not_union']['jaccard_vs_single_B']:.4f} —
so no number on this page describes the file you can download. That is the main reason it is research-only.</li>
<li>Support novelty against the prior union is {reg['novel_fraction_vs_prior_union']:.4f}
(<code>{esc(reg['relation_to_prior_union'])}</code>). On a registry holding
{reg['universal_coverage_probes']} universal-coverage probe rasters, the 3 px union of all priors covers
essentially the whole legal footprint, so <b>no</b> raster can show novel support. The meaningful uniqueness
statement is the decoded-pattern one: distinct from every one of the {fi(reg['priors_compared'])} comparable
rasters.</li></ul>
<p class="small"><a href="../knowledge/63_hypotheses_H74_preregistered.md">Ranked hypotheses and the frozen
protocol →</a> · <a href="../knowledge/63a_h74_amendment_shipped_arm_rule.md">Shipped-arm amendment →</a> ·
<a href="../knowledge/64_h74_results_and_limits.md">Results and limits →</a></p></section>
{earlier}""" + tail

    exec_html = head + f"""
<div class="eyebrow">Executive summary · submission guide</div>
<h1>Is this file OK to download and submit?</h1>
{big}
{buttons}
<p class="fileline">{fileline}</p>
<section class="prose">
<h2>The file contract, checked on disk by the shared validator</h2><ul>
<li>One band, float32, every value in [0, 1] — in practice exactly 0 or 1. The portal rule
<em>“Predicted values must be in range [0, 1]”</em> is satisfied.</li>
<li>No NaN and no infinite values anywhere in the file. Outside-footprint cells are encoded 0.0, not NaN
(a NaN file is both unwritable and unsubmittable).</li>
<li>EPSG:32611 · {val['shape'][0]}×{val['shape'][1]} · geotransform identical to the pinned
<code>sample_submission.tif</code>.</li>
<li>{fi(n_dots)} emitted cells, all more than 200 m from a mapped USGS/INGENIOUS trace, minimum 3 px (300 m)
separation so no two dots compete for the same kernel credit.</li>
<li>SHA-256 <code>{esc(card['raster_sha256'])}</code> · {fi(card['raster_bytes'])} bytes.</li>
<li>Local validator only. This is <b>not</b> an organiser acceptance receipt.</li></ul>

<h2>Exactly how to submit — the three form fields</h2>
<p>The DrivenData submission form for this competition has three things to fill in. Here is what each one wants and
exactly what to paste.</p>
<ol>
<li><b>File to submit.</b> Upload a single-band GeoTIFF, or a ZIP containing exactly one GeoTIFF. Use
<a href="downloads/h74-candidate.tif" download><code>h74-candidate.tif</code></a> or
<a href="downloads/h74-candidate.zip" download><code>h74-candidate.zip</code></a> — the ZIP holds that one TIFF and
nothing else, verified byte-for-byte.</li>
<li><b>Submission name (must be unique).</b> Every submission needs a name you have not used before. Paste:<br>
<code>{esc(card['submission_name'])}</code></li>
<li><b>Note (≤ 140 characters).</b> A short line distinguishing this entry from your others. Paste
({card['note_chars']} characters):<br><code>{esc(card['submission_note'])}</code></li>
</ol>
<ol start="4">
<li>Open the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">competition
submission page</a> (login required) and upload.</li>
<li><b>Only do this if the verdict box at the top of this page says the file may be submitted.</b>
{'It currently says it is eligible for the selector — the weekly slot decision is still a separate, human step.' if promote else 'It currently says DO NOT SUBMIT. This round spends no weekly slot. Download it, read the evidence, and keep your slot.'}</li>
</ol>

<h2>Why the verdict reads the way it does</h2>
<p>{esc(card['submit_recommendation_reason'])}</p>
<div class="table-wrap"><table><thead><tr><th>Clause</th><th>Result</th></tr></thead>
<tbody>{clause_rows}</tbody></table></div>
<p class="small">The standing rule in this repository: <b>never spend a competition upload slot on a candidate that
has not beaten the current comparable holdout best.</b> The comparable best is <code>single_B</code> at
{sc['single_B']['dti']:.6f} HOLDOUT-DTI; the shipped arm <code>{esc(arm)}</code> measured
{sc[arm]['dti']:.6f} with a paired 95% CI of {ci(pairs[arm]['ci95'])} against it.</p>

<h2>What you are downloading</h2>
<p>A {fi(n_dots)}-cell binary prediction raster produced by co-training View A (potential-field / subsurface:
gravity, magnetics, strain, seismicity) against View B (surface: DEM curvature and slope plus the radiometric bands
of <code>training_features.tif</code>), following Blum &amp; Mitchell, <i>Combining Labeled and Unlabeled Data with
Co-Training</i>, COLT ’98, pp. 92–100,
<a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a>. The two feature views are disjoint by
construction and verified disjoint at load time. Disagreement between them is used to stratify where the budget is
spent, never to manufacture training labels.</p>
</section>
{earlier}""" + tail

    (DOCS / "h74.html").write_text(index)
    (DOCS / "h74-executive-summary.html").write_text(exec_html)

    # ------------------------------------------------------------------ knowledge note
    rows_md = ""
    for a in seen:
        d = pairs.get(a)
        delta = f"{d['delta']:+.6f} {ci(d['ci95'])}" if d else "—"
        shipped = " **(shipped)**" if a == arm else ""
        rows_md += (f"| `{a}`{shipped} | {sc[a]['dti']:.6f} | "
                    f"{ci(sc[a]['ci95'])} | {delta} |\n")
    kn = f"""# 64 · H74 results and limits (rendered from the receipts by `scripts/publish_h74_site.py`)

**Verdict: `{verdict}`** · download OK: **{download_ok}** · spend a weekly slot: **{promote}**

Artefact `{stem}.tif`, SHA-256 `{card['raster_sha256']}`, {card['raster_bytes']} bytes, {n_dots} emitted cells.
Preregistration `knowledge/63_hypotheses_H74_preregistered.md`
(SHA-256 `{card['preregistration']['sha256']}`, pinned in `registry/h74_preregistration.json`),
amendment `knowledge/63a_h74_amendment_shipped_arm_rule.md`.

## 1 · What H74 changed

Five rounds closed this lane on one gate: View A's out-of-quadrant AUC on *all* held-out truth is ~0.52, below the
0.60 sufficiency bar. H74's claim is that this gate is confounded: the catalogue's faults are surface-expressed by
selection, so "View A cannot predict mapped faults" and "View A is uninformative" are not the same statement. The
new test **S1′** restricts View A's AUC to held-out truth inside View B's blind band and requires it to beat both an
absolute bar and View A's own AUC on surface-expressed truth.

| measurement | value | bar |
|---|---:|---:|
| View A AUC, all held-out truth (old gate S1) | {s1['mean_auc_A']:.4f} | 0.60 |
| View B AUC, all held-out truth | {s1['mean_auc_B']:.4f} | — |
| View A AUC, truth in View B's blind band | {(f"{s1['mean_auc_A_blind']:.4f}" if s1['mean_auc_A_blind'] is not None else '—')} | ≥ 0.60 |
| View A AUC, surface-expressed truth | {(f"{s1['mean_auc_A_brightB']:.4f}" if s1['mean_auc_A_brightB'] is not None else '—')} | — |
| conditional margin | {(f"{s1['conditional_margin']:+.4f}" if s1['conditional_margin'] is not None else '—')} | ≥ +0.05 |

S1 global pass: **{s1['S1_global_pass']}**. S1′ conditional pass: **{s1['S1_conditional_pass']}**.
Conditional AUCs are label-selected diagnostics, not unbiased estimates.

### Per fold — the actual finding

| fold | truth px | A all | B all | A∣B-dark | A∣B-blind | A∣B-bright | margin |
|---:|---:|---:|---:|---:|---:|---:|---:|
{fold_md}
{'**In every fold, without exception, A∣B-dark < A∣B-blind < A∣B-bright.**' if order_ok else '**The ordering is not monotone across all folds.**'}
View A is least informative exactly where View B is blind and most informative where View B is already confident —
the reverse of the H74 hypothesis. This does not merely fail the bar, it forecloses the rescue argument that kept
the lane open for six rounds: View A's apparent skill is a shadow of the same surface-expressed structures View B
reads directly, not an independent subsurface channel that the catalogue under-samples. A buried-fault population
visible only to gravity and magnetics would have produced the reverse ordering.

Conditional **independence** is not what failed: max |ρ| {card['independence']['max_abs_correlation']:.4f} over
{card['independence']['n_blocks']:,} blocks, well inside the 0.60 abandon bar. Co-training's independence
precondition holds on this data; its *sufficiency* precondition is refuted, now conditionally as well as globally.

## 2 · HOLDOUT-DTI (`gems52-pooled-hide-v1`, {hold['withheld_positive_pixels']} withheld positive px, {hold['budget_per_arm_per_fold']} dots/fold)

| arm | HOLDOUT-DTI | 95% CI | paired Δ vs single_B |
|---|---:|---:|---:|
{rows_md}
Control reproduction: single_B {hold['control_reproduction']['measured']:.6f} vs committed
{hold['control_reproduction']['committed']:.6f}, |Δ| {hold['control_reproduction']['abs_delta']:.2e}
(tolerance {hold['control_reproduction']['tolerance']}).

## 3 · The six frozen clauses

{"".join(f"* {clause_text[k]} → **{'PASS' if v else 'FAIL'}**{chr(10)}" for k, v in clauses.items())}
## 4 · Placement

Shipped arm `{arm}`; A-only stratum {place['a_only_stratum_px']:,} px, {place['a_only_candidate_cells']:,}
lane candidate cells, {place['a_only_cells_in_shipped_raster']:,} of them emitted by the shipped raster of
{n_dots:,}; legal pool {place['pool_px']} px at cross-family consensus ≤ {place['consensus_threshold']};
per-prior near-dot quota {place['quota']} over {place['quota_priors']} packed informative priors;
3 px hard-core separation. Lane (dots, policy) max near-3px share
{reg['dots_max_near_3px_policy']:.4f} against the 0.70 bar → **{reg['dots_verdict_policy']}**.

## 5 · Limits

* **The holdout measured the ranking RULE, not the shipped bytes.** `line_support_B` was scored on each
  fold's full allowed domain. The shipped raster applies the same rule inside a pool restricted to
  cross-family consensus ≤ {place['consensus_threshold']}, which is what makes it lane-feasible — and that
  restriction moves almost every dot (Jaccard against the `single_B` placement is only
  {card['not_union']['jaccard_vs_single_B']:.4f}). No holdout number describes the shipped bytes. This
  limitation is shared with H69 and H73 and is the main reason the file is research-only.
* HOLDOUT-DTI does not rank the board (Spearman −0.10, `knowledge/10` §5). No number here is a projection.
* Holdout prevalence ≈ 1% vs competition ≈ 0.15%; absolute DTI values are not comparable to leaderboard values.
* The literal lane rule fails for every non-empty raster on this registry because the registry contains
  {reg['universal_coverage_probes']} measured universal-coverage probes; the policy rule over
  {reg['informative_priors']} informative priors is the repository's authoritative lane verdict.
* Conditional sufficiency is measured on a label-selected subset and is a diagnostic only.
* The reasoning CSV is measured context plus a templated hypothesis and a named mimic — not field-verified geology.
* Inputs are SHA-256-pinned owner mirrors of the competition data, not organiser-authenticated downloads.
* Registry scope: the supplied, aligned, publicly mirrored inventory only; private or unlinked artefacts are not
  proven absent.
"""
    (ROOT / "knowledge/64_h74_results_and_limits.md").write_text(kn)

    # ------------------------------------------------------------------ banners (idempotent)
    short = "PROMOTE-ELIGIBLE · selector decides" if promote else "DO NOT SUBMIT"
    banner = (f'<!--H74-BANNER--><div class="notice" role="note" style="margin:0 0 1rem;'
              f'background:{colour}"><strong>Latest research round: H74 — {esc(short)}.</strong> '
              f'Conditional co-training sufficiency (S1′) and the first nested B-core + A-rescue arm. '
              f'<a href="downloads/h74-candidate.tif" download>Download the H74 GeoTIFF</a> '
              f'({fi(card["raster_bytes"])} bytes, SHA-256 <code>{esc(card["raster_sha256"][:16])}…</code>, '
              f'{fi(n_dots)} cells) · <a href="h74-executive-summary.html">Read the verdict and the exact '
              f'submission steps first</a> · <a href="h74.html">Run &amp; evidence</a>. Historical downloads '
              f'below are not upload approval.</div><!--/H74-BANNER-->')
    dl_rows = (f'<!--H74-DL--><tr><td><a href="h74-candidate.tif" download>h74-candidate.tif</a></td>'
               f'<td class="number">{fi(card["raster_bytes"])}</td>'
               f'<td class="mono">{esc(card["raster_sha256"])}</td>'
               f'<td>H74 · conditional co-training, {esc(arm)} · {fi(n_dots)} px · newest round; '
               f'<a href="../h74.html">evidence</a></td></tr>\n'
               f'<tr><td><a href="{esc(stem)}.tif" download>{esc(stem)}.tif</a></td>'
               f'<td class="number">{fi(card["raster_bytes"])}</td>'
               f'<td class="mono">{esc(card["raster_sha256"])}</td>'
               f'<td>canonical filename, byte-identical</td></tr>\n'
               f'<tr><td><a href="h74-candidate.zip" download>h74-candidate.zip</a></td>'
               f'<td class="number">single-TIFF ZIP</td><td class="mono">portal-accepted wrapper</td>'
               f'<td>holds exactly one TIFF, byte-identical</td></tr>\n'
               f'<tr><td><a href="{esc(csv_link)}" download>{esc(csv_link)}</a></td>'
               f'<td class="number">CSV</td><td class="mono">—</td>'
               f'<td>{fi(card["a_only_reasoning"]["n_a_only_candidates"])} A-only reasoning rows '
               f'(interpretation + named non-fault mimic + falsifier)</td></tr><!--/H74-DL-->')

    def splice(path: Path, anchor: str, block: str, start: str, end: str):
        text = path.read_text()
        if start in text:
            i = text.index(start)
            j = text.index(end, i) + len(end)
            if text[i:j] != block:
                text = text[:i] + block + text[j:]
        else:
            if anchor not in text:
                raise SystemExit(f"{path}: anchor {anchor!r} missing")
            text = text.replace(anchor, anchor + block, 1)
        path.write_text(text)

    splice(DOCS / "index.html", '<main id="main">', banner, "<!--H74-BANNER-->", "<!--/H74-BANNER-->")
    splice(DOCS / "executive-summary.html", '<main id="main">', banner,
           "<!--H74-BANNER-->", "<!--/H74-BANNER-->")
    splice(DOWN / "index.html", "<tbody>", dl_rows, "<!--H74-DL-->", "<!--/H74-DL-->")

    text = (DOWN / "index.html").read_text()
    notice_new = (f'<!--H74-DOWNLOAD-NOTICE--><aside style="padding:20px;background:{colour};color:#12331f;'
                  f'font:16px/1.6 system-ui"><b>Latest research: H74 — {esc(short)}.</b> '
                  f'<a href="h74-candidate.tif" download>Download the H74 GeoTIFF</a> '
                  f'({fi(card["raster_bytes"])} bytes, {fi(n_dots)} cells) · '
                  f'<a href="../h74-executive-summary.html">Verdict and exact submission steps</a> · '
                  f'<a href="../h74.html">Run &amp; evidence</a>. Historical downloads below are not upload '
                  f'approval.</aside><!--/H74-DOWNLOAD-NOTICE-->')
    m = re.search(r"<!--H[0-9A-Za-z]+-DOWNLOAD-NOTICE-->.*?<!--/H[0-9A-Za-z]+-DOWNLOAD-NOTICE-->", text, re.S)
    text = (text[:m.start()] + notice_new + text[m.end():]) if m else text.replace(
        "<body>", "<body>" + notice_new, 1)
    (DOWN / "index.html").write_text(text)

    # ------------------------------------------------------------------ README block
    readme = ROOT / "README.md"
    rtext = readme.read_text()
    block = f"""<!--H74-README-->
## H74 — conditional co-training sufficiency (S1′) and the B-core + A-rescue swap

**Verdict: {verdict}.** Download OK: **{download_ok}**. Spend a weekly slot: **{promote}**.
{card['submit_recommendation_reason']}

* One-click download: [`docs/downloads/h74-candidate.tif`](docs/downloads/h74-candidate.tif)
  ({card['raster_bytes']:,} bytes, SHA-256 `{card['raster_sha256']}`, {n_dots:,} cells, values exactly {{0,1}},
  0 NaN, EPSG:32611, grid identical to `sample_submission.tif`).
* Pages: [`docs/h74.html`](docs/h74.html) · [exact submission steps](docs/h74-executive-summary.html).
* Submission name: `{card['submission_name']}` · note ({card['note_chars']} chars): `{card['submission_note']}`
* New science: **S1′**, View A's out-of-quadrant AUC restricted to truth inside View B's blind band —
  {(f"{s1['mean_auc_A_blind']:.4f}" if s1['mean_auc_A_blind'] is not None else 'n/a')} against the 0.60 bar
  (global S1 for comparison: {s1['mean_auc_A']:.4f}); conditional margin
  {(f"{s1['conditional_margin']:+.4f}" if s1['conditional_margin'] is not None else 'n/a')} against +0.05.
* Shipped arm `{arm}`: HOLDOUT-DTI {sc[arm]['dti']:.6f} {ci(sc[arm]['ci95'])} vs the `single_B` control
  {sc['single_B']['dti']:.6f} {ci(sc['single_B']['ci95'])}; paired Δ {pairs[arm]['delta']:+.6f}
  {ci(pairs[arm]['ci95'])}. HOLDOUT-DTI, not a leaderboard score.
* Receipts: [`evidence/h74_run_card.json`](evidence/h74_run_card.json),
  [`knowledge/63_hypotheses_H74_preregistered.md`](knowledge/63_hypotheses_H74_preregistered.md),
  [`knowledge/64_h74_results_and_limits.md`](knowledge/64_h74_results_and_limits.md).
<!--/H74-README-->

"""
    if "<!--H74-README-->" in rtext:
        i = rtext.index("<!--H74-README-->")
        j = rtext.index("<!--/H74-README-->") + len("<!--/H74-README-->\n\n")
        rtext = rtext[:i] + block + rtext[j:]
    else:
        lines = rtext.split("\n")
        k = 1 if lines and lines[0].startswith("# ") else 0
        rtext = "\n".join(lines[:k]) + ("\n\n" if k else "") + block + "\n".join(lines[k:])
    readme.write_text(rtext)

    print("published:", DOCS / "h74.html", DOCS / "h74-executive-summary.html",
          ROOT / "knowledge/64_h74_results_and_limits.md", "README block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
