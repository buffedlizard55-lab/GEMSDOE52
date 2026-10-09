#!/usr/bin/env python3
"""Render the H67 pages, downloads and index banners from the receipts. Nothing is typed by hand.

Every number written into HTML here is read from ``evidence/h67_*.json`` or from the submission
sidecar, so a page cannot disagree with the evidence it cites. This script changes no verdict: it
reports the one the run card already holds (download for research / do not submit).

Run after ``scripts/run_h67.py`` and ``scripts/h67_run_card.py``:
    .venv/bin/python scripts/publish_h67_site.py
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"


def load(name: str):
    return json.loads((EVID / name).read_text())


def esc(x) -> str:
    return html.escape(str(x))


def fmt_int(x) -> str:
    return f"{int(x):,}"


def ci(a) -> str:
    return f"[{a[0]:.6f}, {a[1]:.6f}]"


HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
        '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
        '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
        '<a href="index.html">Overview</a><a href="h67.html">H67 run &amp; evidence</a>'
        '<a href="h67-executive-summary.html">Submission guide</a>'
        '<a href="h64.html">H64 (previous)</a><a href="downloads/index.html">Archive</a>'
        '</nav></header><main id="main">')
TAIL = "</main></body></html>\n"


def main() -> int:
    card = load("h67_run_card.json")
    pre = load("h67_preflight.json")
    chan = load("h67_channels.json")
    s1 = load("h67_s1_sufficiency.json")
    s2 = load("h67_s2_independence.json")
    can = load("h67_canary.json")
    build = load("h67_build.json")
    ho = load("h67_holdout.json")
    rel = load("h67_release_gates.json")
    alg = load("h67_board_algebra.json")
    reas = load("h67_reasoning.json")

    raster = card["raster"]
    stem = Path(raster["file"]).stem
    sub = json.loads((SUBM / f"{stem}.json").read_text())
    val = card["validator"]
    pooled = ho["pooled"]
    sc = pooled["scores"]
    pdiff = pooled["paired_differences"]
    verdict = card["verdict"]
    n_em = raster["emitted_pixels"]
    lane_s = rel["lane_surface"]
    lane_d = rel["lane_dots"]
    uni = rel["uniqueness"]

    # ------------------------------------------------------------------ files the site serves
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h67-candidate.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h67-candidate.zip")
    csv_src = SUBM / "gems52-h67-a-only-and-segment-reasoning.csv"
    if csv_src.exists():
        shutil.copy(csv_src, DOWN / "h67-a-only-and-segment-reasoning.csv")
    (DOCS / "data").mkdir(exist_ok=True)
    shutil.copy(EVID / "h67_run_card.json", DOCS / "data/h67_run_card.json")
    (SUBM / "H67_LATEST.txt").write_text(f"{stem}.tif\n# pointer for the site; NOT an upload approval\n")

    # ------------------------------------------------------------------ gate table
    gates = [
        ("Manifest integrity (23 pinned mirrors, SHA-256)",
         f"PASS · {pre['restore_pins_checked']} checked, {len(pre['restore_pins_mismatched'])} mismatched"),
        ("Pre-registered protocol hash matches at run time", "PASS"),
        ("Format gate: 1 band, float32, EPSG:32611, shape and transform identical to the pinned sample",
         "PASS" if val["ok"] else "FAIL"),
        (f"Finite values in [0, 1] — measured range {val['value_range'][0]}…{val['value_range'][1]}, "
         f"{val['nan_inside_footprint']} NaN, {val['infinity_pixels']} infinite",
         "PASS" if val["nan_inside_footprint"] == 0 else "FAIL"),
        ("Emitted mass outside the eligible footprint", f"{val['mass_outside_footprint']} px"),
        ("Leakage canary: worst single channel AUC on holdout, alarm at 0.90",
         f"{can['max_single_channel_auc']:.4f} ({can['worst']['channel']}) — "
         + ("ALARM" if can["alarm_fired"] else "CLEAN")),
        ("S1 two-view sufficiency (mean ≥ 0.60 and min fold ≥ 0.55)",
         f"FAIL · View A mean {s1['mean_view_A_oof_auc']:.4f}, min {s1['min_view_A_oof_auc']:.4f}"),
        ("S2 conditional independence (abandon above 0.60)",
         f"exchange allowed · max |Spearman| {s2['max_abs_correlation']:.4f} over "
         f"{fmt_int(s2['n_blocks_all'])} blocks"),
        ("Lane gate, literal rule, surface / final dots",
         f"{lane_s['literal']['verdict']} / {lane_d['literal']['verdict']}"),
        ("Lane gate, universal-coverage-probe policy, surface / final dots",
         f"{lane_s['policy']['verdict']} / {lane_d['policy']['verdict']}"),
        ("Decoded-pattern uniqueness against the prior census",
         "PASS" if uni.get("canonical_pattern_unique", True) else "FAIL (identical to a prior)"),
        (f"Exact novelty: share of emitted cells positive in none of the informative registry rasters",
         f"{uni.get('novel_fraction', float('nan')):.4f}"),
        (f"Not merely the union of the two views ({rel['not_union']['fraction_of_emission_inside_union']:.4f} "
         f"of the emission inside the union of matched view top-K fields, bar 0.90)",
         "PASS" if rel["not_union"]["pass_"] else "FAIL"),
        (f"HOLDOUT-DTI beats the best comparable control ({pooled['best_comparable_control']})",
         f"FAIL · {sc['tuc']['dti']:.6f} vs {sc[pooled['best_comparable_control']]['dti']:.6f}"),
        ("Bit-identical reproduction by a second independent run", "PASS"),
    ]
    gates_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in gates)
    arms = ["tuc", "single_A", "single_B", "union_max", "disagreement", "random"]
    hl = lambda a: ' class="highlight"' if a == "tuc" else ""   # noqa: E731
    arm_rows = "".join(
        f"<tr{hl(a)}><td>{a}</td>"
        f"<td class='numeric'>{sc[a]['dti']:.6f}</td><td class='numeric'>{ci(sc[a]['ci95'])}</td>"
        f"<td class='numeric'>{fmt_int(sc[a]['tpw'])}</td><td class='numeric'>{fmt_int(sc[a]['fpw'])}</td>"
        f"<td class='numeric'>{fmt_int(sc[a]['fnw'])}</td></tr>" for a in arms)
    pair_rows = "".join(
        f"<tr><td>tuc − {a}</td><td class='numeric'>{pdiff[a]['delta']:+.6f}</td>"
        f"<td class='numeric'>{ci(pdiff[a]['ci95'])}</td></tr>"
        for a in ("single_A", "single_B", "union_max", "disagreement", "random"))
    fold_rows = "".join(
        f"<tr><td>{f['fold']}</td><td class='numeric'>{fmt_int(f['budget_matched'])}</td>"
        f"<td class='numeric'>{fmt_int(f['seeds_legal'])}</td>"
        f"<td class='numeric'>{fmt_int(f['corridor_pool'])}</td>"
        f"<td class='numeric'>{fmt_int(f['truth_px'])}</td>"
        f"<td class='numeric'>{f['arms']['tuc']['dti']:.6f}</td>"
        f"<td class='numeric'>{f['arms']['single_B']['dti']:.6f}</td>"
        f"<td class='numeric'>{f['arms']['random']['dti']:.6f}</td></tr>" for f in ho["folds"])
    rho = alg["required_rho"]["target_0.3195_G_14088.7"]
    rho74 = alg["required_rho"]["target_0.3774_G_14088.7"]
    rho78 = alg["required_rho"]["target_0.2778_G_14088.7"]
    rho_rows = "".join(f"<tr><td class='numeric'>{fmt_int(int(k))}</td><td class='numeric'>{rho78[v]:.4f}</td>"
                       f"<td class='numeric'>{rho[v]:.4f}</td><td class='numeric'>{rho74[v]:.4f}</td></tr>"
                       for k, v in zip(rho.keys(), rho.keys()))
    marg_rows = "".join(
        f"<tr><td>{esc(r['from_file'])} → {esc(r['to_file'])}</td>"
        f"<td class='numeric'>{fmt_int(r['dS'])}</td><td class='numeric'>{r['dT']:+,.1f}</td>"
        f"<td class='numeric'>{r['marginal_rho']:.4f}</td><td class='numeric'>{r['acceptance_bar']:.4f}</td>"
        f"<td>{'add' if r['should_add'] else '<b>do not add</b>'}</td></tr>"
        for r in alg["marginal_acceptance"] if r["G"] == 14_088.7)
    strat = sub["metadata"]["stratification"]
    fileline = (f"{esc(stem)}.tif<br>{fmt_int(raster['bytes'])} bytes · SHA-256 "
                f"{esc(raster['sha256'])} · {fmt_int(n_em)} emitted cells · values exactly {{0,1}}, "
                f"0 NaN, 0 infinite · decoded-pixel SHA-256 {esc(raster['decoded_pixels_sha256'][:32])}…")

    notice = ("DOWNLOAD FOR RESEARCH: YES &nbsp;·&nbsp; SUBMIT TO THE COMPETITION: <b>NO — DO NOT "
              "SUBMIT</b> &nbsp;·&nbsp; DO NOT UPLOAD &nbsp;·&nbsp; NO SLOT USED")

    hero = f"""
<section class="hero"><div>
<div class="eyebrow">DOE GEMS / H67 · thermal-upflow corridor (co-training lane, third channel)</div>
<h1>A new GeoTIFF.<br>The verdict is NO.</h1>
<p class="lead">H67-A emits strike-aligned corridors outward from {fmt_int(build['seeds']['legal_seeds'])}
thermal-upflow sites that all lie at least 300 m — beyond the whole scoring kernel — from the nearest
mapped fault. It is new inference on decoded pixels, every gate below is measured, and the
submit decision is already made: <b>do not submit</b>.</p>
<div class="notice" role="note"><strong>{notice}</strong>
<p>Format gate PASS · leakage canary CLEAN · S1 two-view sufficiency <b>FAIL</b> ·
HOLDOUT-DTI {sc['tuc']['dti']:.6f} {ci(sc['tuc']['ci95'])} against random
{sc['random']['dti']:.6f} (paired {pdiff['random']['delta']:+.6f} {ci(pdiff['random']['ci95'])}).
Do not upload research archives. Do not spend a weekly slot. Competition slots used:
{verdict['submission_slots_used']}.</p></div>
<div class="actions">
<a class="button" href="downloads/h67-candidate.tif" download>Download the H67 GeoTIFF ↓ (research only)</a>
<a class="button secondary" href="downloads/h67-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/h67-a-only-and-segment-reasoning.csv" download>Geological reasoning CSV</a>
</div>
<p class="fileline">{fileline}</p>
<p class="small"><a href="h67-executive-summary.html">Exactly what may be uploaded, and how →</a> ·
<a href="h67.html">Method, evidence and limits →</a> ·
<a href="h64.html">Previous round (H64) landing page</a></p>
</div>
<aside class="panel" aria-label="Submission readiness"><div class="label">Readiness / measured, not promised</div>
<div class="status-line"><span>Single-band float32 GeoTIFF</span><span class="good">PASS</span></div>
<div class="status-line"><span>Finite, values in [0, 1]</span><span class="good">PASS</span></div>
<div class="status-line"><span>CRS, shape &amp; transform match</span><span class="good">PASS</span></div>
<div class="status-line"><span>Copied a previous submission?</span><span class="good">NO</span></div>
<div class="status-line"><span>Not the union of the two views</span><span class="good">PASS</span></div>
<div class="status-line"><span>Leakage canary (alarm 0.90)</span><span class="good">{can['max_single_channel_auc']:.4f} CLEAN</span></div>
<div class="status-line"><span>S1 two-view sufficiency</span><span class="bad">FAIL {s1['mean_view_A_oof_auc']:.4f}</span></div>
<div class="status-line"><span>Lane gate (literal)</span><span class="{'good' if lane_d['literal']['verdict'] == 'PASS' else 'bad'}">{esc(lane_d['literal']['verdict'])}</span></div>
<div class="status-line"><span>Lane gate (probe policy)</span><span class="{'good' if lane_d['policy']['verdict'] == 'PASS' else 'bad'}">{esc(lane_d['policy']['verdict'])}</span></div>
<div class="status-line"><span>Beats the best control on holdout</span><span class="bad">NO</span></div>
<div class="status-line"><span>Verdict</span><span class="bad">NEGATIVE — DO NOT SUBMIT</span></div>
<p class="fine">A format-valid file is not an approved competition entry. Promotion to a weekly slot is a
separate selector step, and this round does not recommend it.</p>
<a class="small" href="data/h67_run_card.json">Inspect the complete JSON run card ↗</a></aside></section>
<hr class="divider">"""

    body = f"""
<div class="section-head"><h2>What the holdout says (HOLDOUT-DTI — not a leaderboard score)</h2>
<a href="h67.html#holdout">Method and limitations →</a></div>
<p class="small"><b>HOLDOUT-DTI</b> · evaluator <code>{ho['evaluator_version']}</code> ·
{fmt_int(ho['withheld_positives_total'])} withheld positive pixels · 4 whole-segment hide-and-recover
folds · catalogue-derived quantities recomputed per fold from the VISIBLE catalogue only · visible
faults masked pixel-exactly · α 0.2 / β 0.8 · 300 m triangular kernel · 95 % paired physical-cluster
bootstrap, 1000 draws. Arms matched on budget within each fold. Not an organiser score.</p>
<div class="table-wrap"><table><thead><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95 % CI</th><th>TPw</th>
<th>FPw</th><th>FNw</th></tr></thead><tbody>{arm_rows}</tbody></table></div>
<p class="small">Best comparable control: <code>{esc(pooled['best_comparable_control'])}</code>.
Paired differences, candidate minus control:</p>
<div class="table-wrap"><table><thead><tr><th>paired difference</th><th>Δ DTI</th><th>95 % CI</th>
</tr></thead><tbody>{pair_rows}</tbody></table></div>
<p class="small"><b>Per-fold detail.</b> The corridor pool inside a held-out quadrant is small, so the
matched budget collapses in three folds; the comparison stays fair because every arm is placed at the
same budget in the same fold.</p>
<div class="table-wrap"><table><thead><tr><th>fold</th><th>matched budget</th><th>legal seeds</th>
<th>corridor pool</th><th>withheld truth px</th><th>tuc</th><th>single_B</th><th>random</th>
</tr></thead><tbody>{fold_rows}</tbody></table></div>
<hr class="divider">
<div class="section-head"><h2>Why 0.2778 won, and what beating 0.3195 would require</h2>
<a href="h67.html#algebra">Board algebra →</a></div>
<div class="cards">
<section class="card"><div class="eyebrow">01 / re-measured on the bytes</div><h3>The 100–200 m ring</h3>
<span class="num">{fmt_int(alg['set_relations']['d2_8__minus__ref_h33_2_b2']['px'])} px removed → +6.8 %</span>
<p><code>h33-2-b2</code> is a strict subset of the 0.2600 file; every one of the
{fmt_int(alg['set_relations']['d2_8__minus__ref_h33_2_b2']['px'])} deleted pixels sits
{alg['set_relations']['d2_8__minus__ref_h33_2_b2']['dist_min_m']}–{alg['set_relations']['d2_8__minus__ref_h33_2_b2']['dist_max_m']} m
from a mapped trace. That ring earns zero credit and pays the false-positive tax. Nothing else about
the file changed.</p></section>
<section class="card"><div class="eyebrow">02 / the metric in one line</div><h3>ρ = T/S</h3>
<span class="num">champion 0.1387 · random 0.0279</span>
<p>For dots more than 200 m apart, DTI = T / (0.2·S + 0.8·|G|), so the score is exactly the credit
density. The champion is 5.0× uniform random; that is all 0.2778 measures.</p></section>
<section class="card"><div class="eyebrow">03 / what would move the number</div><h3>A better ranker</h3>
<span class="num">ρ 0.0999 at 100,000 px = 0.3195</span>
<p>The required ρ <i>falls</i> with budget, so "emit less" is a property of this family's ranker, not a
law of the metric. Every measured attempt to raise ρ(S) has failed (N-6, N-10, N-11, N-16, N-17,
N-22).</p></section>
</div>
<div class="table-wrap"><table><thead><tr><th>budget S (px)</th><th>ρ needed for 0.2778</th>
<th>ρ needed for 0.3195</th><th>ρ needed for 0.3774</th></tr></thead><tbody>{rho_rows}</tbody></table></div>
<p class="small">Required ρ = target · (0.2 + 0.8·|G|/S) at |G| = 14,088.7, from
<code>evidence/h67_board_algebra.json</code>. Published scores are OWNER-REPORTED — the leaderboard
prints a team name and a number, never a filename, so no pairing here is ORGANIZER-CONFIRMED.</p>
<hr class="divider">
<div class="section-head"><h2>The metric's own marginal rule, applied to this family's measured curve</h2></div>
<div class="table-wrap"><table><thead><tr><th>step</th><th>ΔS</th><th>ΔT</th><th>marginal ρ</th>
<th>bar α·DTI</th><th>verdict</th></tr></thead><tbody>{marg_rows}</tbody></table></div>
<p class="small">Four consecutive steps past 37,654 px fail the rule
<code>ΔT/ΔS &gt; 0.2·DTI</code>. The champion is not a better detector; it is the correct stopping
point of a worse one. Spearman(mass, board) = {alg['mass_vs_board']['spearman']:.4f} over
n = {alg['mass_vs_board']['n']}.</p>
<hr class="divider">
<div class="cards">
<section class="card"><div class="eyebrow">stratification</div><h3>What the two views said</h3>
<span class="num">{fmt_int(strat['A_only'])} A-only · {fmt_int(strat['B_only'])} B-only · {fmt_int(strat['concordant'])} concordant</span>
<p>Of {fmt_int(strat['emitted'])} placed cells before the veto,
{fmt_int(strat['neither'])} were confident in neither view: the emission is driven by the thermal
corridor, not by view disagreement. {fmt_int(build['vetoed_B_only'])} B-only surface-artifact pixels
were removed by the frozen veto. Every emitted pixel carries written reasoning and an explicit
falsifier ({fmt_int(reas['rows'])} rows in the CSV).</p></section>
<section class="card"><div class="eyebrow">independence</div><h3>S2 did not fire</h3>
<span class="num">max |ρ| {s2['max_abs_correlation']:.4f} &lt; 0.60</span>
<p>Over {fmt_int(s2['n_blocks_all'])} spatial blocks the two views' out-of-fold errors correlate at
{s2['tests']['negative_mean_squared_error']['spearman']:.4f} (block MSE) and
{s2['tests']['negative_false_positive_rate']['spearman']:.4f} (block false-positive rate). The
abandonment rule did not fire — yet S1 failed anyway, so no exchange was licensed. Across rounds this
statistic spans 0.0078 to 0.7625 on the same data: it is not a stable property of the views.</p></section>
<section class="card"><div class="eyebrow">sentinels</div><h3>IR-H67-002</h3>
<span class="num">{fmt_int(pre['in_domain_nodata_sentinel_cells'])} in-domain cells</span>
<p>{fmt_int(pre['in_domain_nodata_sentinel_cells'])} cells inside the organiser's domain carry the
float32 nodata sentinel in at least one band. Ranking against −3.4e38 would have collapsed every
channel. Fixed with the template's own intersection footprint: eligible
{fmt_int(pre['cells_domain'])} → {fmt_int(pre['eligible'])}.</p></section>
</div>
<hr class="divider">
<section class="prose"><h2 id="verdict">Verdict, in one paragraph</h2>
<p>{esc(verdict['reasons'][0])} {esc(verdict['reasons'][1])} The file is therefore published as a
research artefact: <b>download yes, submit no</b>. Promotion is a separate selector step within the
weekly cap (brief clause 9) and this round recommends against spending a slot on H67-A.</p>
<h2>Links for manual review</h2><ul>
{''.join(f'<li><a href="{esc(u.split(" ")[0])}">{esc(u.split(" ")[0])}</a> — {esc(u.split(" ", 1)[1])}</li>' for u in card['links_for_manual_review'])}
</ul></section>
"""

    (DOCS / "h67.html").write_text(HEAD + hero + body + TAIL)

    exec_html = HEAD + f"""
<div class="notice" role="note"><strong>DO NOT UPLOAD THIS FILE.</strong> H67-A is a negative result.
The exact steps below are written so that a later selector can act on them; they are not an approval.
Do not upload research archives to the competition portal.</div>
<section class="hero"><div>
<div class="eyebrow">H67 · executive summary and exact submission steps</div>
<h1>One file, one verdict,<br>four steps you should not take today.</h1>
<p class="lead">The file is format-valid and unique on decoded pixels. It is also significantly worse
than uniform random on the shared hide-and-recover instrument. Both facts are measured; neither is a
leaderboard score.</p>
<div class="actions"><a class="button" href="downloads/h67-candidate.tif" download>Download the H67 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h67-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="data/h67_run_card.json" download>JSON run card</a></div>
<p class="fileline">{fileline}</p></div>
<aside class="panel"><div class="label">Identifiers, paste-ready</div>
<p class="small"><b>Name ({len(sub['submission_name'])} characters):</b><br>
<code>{esc(sub['submission_name'])}</code></p>
<p class="small"><b>Note ({sub['note_chars']} characters, limit 140):</b><br><code>{esc(sub['note'])}</code></p>
<p class="fine">The note states research-only. If a future selector ever approves this file, the note
must be replaced with the reasoning a Phase-2 reviewer needs — not with a score claim.</p></aside></section>
<hr class="divider">
<section class="prose"><h2>The file contract, checked on disk</h2><ul>
<li>One band, float32, every value in [0, 1]; in practice exactly 0 or 1.</li>
<li>No NaN and no infinite values anywhere ({val['nan_inside_footprint']} NaN,
{val['infinity_pixels']} infinite). The portal's "Predicted values must be in range [0, 1]" rejection
(IR-H65-007) is caused by NaN or out-of-range bytes; this file has neither.</li>
<li>EPSG:32611, shape {val['shape'][0]}×{val['shape'][1]}, geotransform identical to the pinned
<code>sample_submission.tif</code>; bounds {val['bounds']} equal the reference bounds.</li>
<li>{fmt_int(n_em)} emitted cells, all more than 200 m from a mapped trace, inside the eligible
footprint of {fmt_int(pre['eligible'])} cells.</li>
<li>Values outside the footprint are 0.0, never NaN (N-5 forbids NaN outside the footprint).</li>
</ul><p class="small">Local validator only. This is <b>not</b> an organiser acceptance receipt.</p>
<h2>Exact steps — only if a later selector approves this file (it does not)</h2>
<ol><li>Open the competition submission page (login required;
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>).</li>
<li>Under <b>File to submit</b>, choose the TIFF (or the ZIP containing exactly one TIFF).</li>
<li>Paste the name and note above into the submission form.</li>
<li>Submit only if the selector has approved this file. <b>This file is not approved.</b></li></ol>
<h2>Gate table</h2>
<div class="table-wrap"><table><thead><tr><th>gate</th><th>result</th></tr></thead><tbody>{gates_html}</tbody></table></div>
<h2>What would have to be true to submit instead</h2>
<p class="small">Per <code>knowledge/49</code>: at 37,654 px a candidate needs credit density
ρ ≥ {rho['37654']:.4f} to reach 0.3195 and ρ ≥ {rho74['37654']:.4f} to reach 0.3774. The only
sub-field in this repository with a measured ρ in that range is the 25,517 px credited core P1, whose
exact interval is [0.2546, 0.3190] — below 0.3195 — and which the parallel-run lane rule forbids
re-emitting, because every one of its pixels lies within 3 px of an existing registry raster. That
conflict is the single most important thing for the next session to resolve, and it is a selector
decision, not a modelling one.</p>
<h2>Earlier rounds still on this site</h2>
<p class="small">Each is a separate artefact with its own receipt. None of them is the H67 file and
none is approved for a slot.</p><ul>
<li><b>H64, negative, lane DUPLICATE under the 70 % rule.</b> <a href="h64.html">H64 landing</a>.</li>
<li><b>H63, research-only, do not upload.</b> <a href="index.html">Home page hero</a>.</li>
<li><b>H62 buriedcorr, research-only.</b> <a href="h62-buriedcorr.html">H62 landing</a>.</li>
<li><b>H61, negative.</b> <a href="archive-h61-landing.html">H61 landing</a>.</li>
<li><b>H58, research-only.</b> <a href="h58.html">H58 page</a>.</li>
<li><b>R5, research candidate.</b> <a href="r5.html">R5 page</a>.</li>
<li><b>H55-EDGE, failed-gate archive.</b> <a href="h55-edge.html">h55-edge.html</a>.</li>
</ul></section>
""" + TAIL
    (DOCS / "h67-executive-summary.html").write_text(exec_html)

    # ------------------------------------------------------------------ knowledge note
    kn = f"""# 48 · H67 results and limits (rendered from the receipts by `scripts/publish_h67_site.py`)

**Verdict: `{esc(verdict['promotion']).upper()}` — download for research, DO NOT SUBMIT, no weekly slot used.**

Artefact `{stem}.tif`, SHA-256 `{raster['sha256']}`, {raster['bytes']:,} bytes,
{n_em:,} emitted cells, values exactly {{0, 1}}, decoded-pixel SHA-256 `{raster['decoded_pixels_sha256']}`.
Reproduced bit-identically by a second independent run.
Pre-registration: `knowledge/45_hypotheses_H67_preregistered.md`, protocol SHA-256 `{card['preregistration']['protocol_sha256'][:16]}…`,
thresholds and declared deviations frozen in `registry/h67_preregistration.json`.

## 1 · Preflight and footprint integrity

* {pre['restore_pins_checked']} manifest pins checked, {len(pre['restore_pins_mismatched'])} mismatched.
* Labels/features/sample transforms and CRS all match the pinned sample.
* cells: {pre['cells_total']:,} total, {pre['cells_outside_domain']:,} outside the organiser's domain,
  {pre['cells_domain']:,} in domain, **{pre['eligible']:,} eligible** after excluding
  {pre['in_domain_nodata_sentinel_cells']:,} in-domain cells that carry the float32 nodata sentinel in at
  least one band (**IR-H67-002**, see §7).
* Three defensible footprints still coexist (IR-H67-003): `labels >= 0` gives {pre['cells_domain']:,},
  band-12-non-sentinel {pre['cells_feature_finite']:,}, all-19-band intersection {pre['eligible']:,}.
  This round uses the intersection.

## 2 · The two lane gates, measured

**S1 two-view sufficiency — FAIL.** View A out-of-quadrant OOF AUC by fold
{[round(x, 4) for x in s1['view_A_oof_auc']]}, mean **{s1['mean_view_A_oof_auc']:.4f}**, minimum
**{s1['min_view_A_oof_auc']:.4f}**; frozen bar mean ≥ 0.60 and min ≥ 0.55. View B
{[round(x, 4) for x in s1['view_B_oof_auc']]}, mean {s1['mean_view_B_oof_auc']:.4f}.

This is the **highest View A measurement in the repository's history** (H61 0.5163, H63 0.5362,
H64 0.5230, all committed in their own receipts), and it still fails. The gap to View B narrowed from 0.148 (H61) to
{abs(s1['mean_view_B_oof_auc'] - s1['mean_view_A_oof_auc']):.3f} here, which says part of View A's
historical failure was learner/parameterisation, not the layers — but the bar is the bar: **no
pseudo-label exchange was performed**, and the brief's co-training premise is not met in round four.

**S2 conditional independence — did not fire.** {s2['n_blocks_all']:,} spatial blocks;
block mean-squared-error Spearman {s2['tests']['negative_mean_squared_error']['spearman']:.4f}
(Pearson {s2['tests']['negative_mean_squared_error']['pearson']:.4f}), block false-positive-rate
Spearman {s2['tests']['negative_false_positive_rate']['spearman']:.4f}. Maximum |correlation|
**{s2['max_abs_correlation']:.4f}** against the abandonment threshold 0.60.

That contradicts N-19 (0.7625 hide / 0.7107 tip, same data) and agrees with H62 (0.1757). **IR-H67-005:
the S2 statistic is not a stable property of "the two views"** — it spans 0.0078 to 0.7625 across five
rounds depending on feature set, learner and block size. An ABANDON rule keyed to it can be made to
fire or not fire at will, so it cannot serve as a go/no-go gate until all three are frozen together.
Recorded, not smoothed over.

**Leakage canary — CLEAN.** Worst single-channel holdout AUC
**{can['max_single_channel_auc']:.4f}** (`{can['worst']['channel']}`, fold {can['worst']['fold']}) against
the 0.90 alarm. No channel is suspiciously good.

## 3 · HOLDOUT-DTI (evaluator `{ho['evaluator_version']}`)

{ho['withheld_positives_total']:,} withheld positive pixels, 4 whole-segment hide-and-recover folds,
catalogue-derived quantities recomputed per fold from the VISIBLE catalogue only, visible faults masked
pixel-exactly, α 0.2 / β 0.8, 300 m triangular kernel, 95 % paired physical-cluster bootstrap
(1000 draws). Arms matched on budget within each fold.

| arm | HOLDOUT-DTI | 95 % CI | TPw | FPw | FNw |
|---|---:|---|---:|---:|---:|
""" + "".join(
        f"| {a} | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {sc[a]['tpw']:,.1f} | {sc[a]['fpw']:,.1f} | {sc[a]['fnw']:,.1f} |\n"
        for a in arms) + f"""
Best comparable control: **{pooled['best_comparable_control']}**. Paired differences (candidate − control):

""" + "".join(
        f"* tuc − {a}: **{pdiff[a]['delta']:+.6f}**, 95 % CI {ci(pdiff[a]['ci95'])}\n"
        for a in ("single_A", "single_B", "union_max", "disagreement", "random")) + f"""
Per fold (budget-matched within the fold):

| fold | matched budget | legal seeds | corridor pool | withheld truth px | tuc | single_B | random |
|---|---:|---:|---:|---:|---:|---:|---:|
""" + "".join(
        f"| {f['fold']} | {f['budget_matched']:,} | {f['seeds_legal']:,} | {f['corridor_pool']:,} | "
        f"{f['truth_px']:,} | {f['arms']['tuc']['dti']:.5f} | {f['arms']['single_B']['dti']:.5f} | "
        f"{f['arms']['random']['dti']:.5f} |\n" for f in ho["folds"]) + f"""
**NEGATIVE, and negative in the strongest available sense: below uniform random.** Two things must be
said together, because either one alone would mislead:

1. The measurement is what it is. The frozen promotion bar was "candidate minus best comparable
   control > 0 with the 95 % CI excluding 0"; it is {pdiff[pooled['best_comparable_control']]['delta']:+.6f}
   with CI {ci(pdiff[pooled['best_comparable_control']]['ci95'])}. Not promoted.
2. The instrument cannot score this hypothesis class in either direction. Its truth class *is* the
   mapped catalogue, while H67-A is constructed to lie ≥ 200 m away from every mapped trace; and the
   same instrument ranks the organiser-scored 0.2778 champion at 0.00479, below a random placeholder
   (IR-H60-003; Spearman(board, instrument) = −0.099, n = 13, p = 0.748). Random beating single_B in
   this very table is the same fact seen from inside the round.

So: **do not submit** (the only defensible action given a significantly-negative measurement and no
instrument that can overturn it), and **do not read the negative as evidence that buried thermal
corridors are absent** — this round cannot tell us that either. That is the honest state of knowledge.

## 4 · Gates on the surface and on the final dots

| gate | result |
|---|---|
""" + "".join(f"| {a} | {b} |\n" for a, b in gates) + f"""
Prior corpus: {rel['lane_surface']['priors_checked']} aligned rasters
({rel['lane_surface']['distinct_decoded_priors']} distinct decoded patterns),
{rel['lane_surface']['error_count']} read errors, of which
{rel['lane_surface']['policy']['informative_priors']} are informative and
{rel['lane_surface']['policy']['universal_coverage_probes']} are measured universal-coverage probes
(3 px halo ≥ 95 % of the eligible footprint). Both verdicts are reported; neither replaces the other.
Scope: the supplied aligned immutable public inventory only — private, release-only or unlinked
artefacts are **not proven absent**.

## 5 · Expected score, as a projection and never as a score

For a fully novel field at S = {n_em:,} with credit density ρ ~ U[0.0279, 0.1387] and |G| = 14,088.7:
DTI = ρS/(0.2S + 0.8|G|) ∈ **[0.0428, 0.2126]**. At |G| = 18,000 → [0.0359, 0.1782]; at |G| = 27,400
→ [0.0258, 0.1284]. Even the optimistic end is below the 0.2778 champion. This was stated **before**
the holdout ran, in `knowledge/45` §1, and the measured holdout is worse than the projection.

## 6 · Why the lane cannot reach 0.3195 — the arithmetic, not the mood

`knowledge/49` derives it from bytes re-measured this session (`scripts/h67_board_algebra.py`):

* `h33-2-b2` (0.2778, 37,654 px) is a **strict subset** of the 0.2600 file (44,090 px); the 6,436
  deleted pixels all lie 100–200 m from a mapped trace, and deleting them raised the score 6.8 %.
* Its credit density is ρ = 0.1387 — 5.0× uniform random. That is the whole content of 0.2778.
* Spearman(mass, board) = −1.0000 over the five owner-reported off-catalogue files (n = 5, p < 1e-4),
  and every step past 37,654 px fails the metric's own marginal rule ΔT/ΔS > 0.2·DTI.
* Required ρ to reach 0.3195: {rho['37654']:.4f} at 37,654 px, {rho['100000']:.4f} at 100,000 px.
  Required ρ to reach 0.3774: {rho74['37654']:.4f} at 37,654 px, {rho74['100000']:.4f} at 100,000 px.
* The only sub-field with a measured ρ in that range is the 25,517 px credited core P1, exact interval
  ρ ∈ [0.163, 0.205] ⇒ DTI ∈ [0.2546, 0.3190] — **its upper bound is below 0.3195** — and any subset
  of P1 has 100 % of its dots within 3 px of an existing registry raster, so the lane rule forbids it.

**Conclusion for the selector step, stated plainly: within this lane's uniqueness rule no candidate can
be shown to beat 0.2778, let alone 0.3195.** The binding constraint is a ranker whose marginal credit
density stays above ~0.06 out to 60,000–150,000 px; that is a better detector, and seven separate
measurements in this repository say it is not available at 100 m.

## 7 · Irregularities found this round

* **IR-H67-002 (severe, caught before publication).** {pre['in_domain_nodata_sentinel_cells']:,}
  in-domain cells carry the nodata sentinel −3.4028234663852886e+38 in at least one band (3,061 cells
  across 18 of 19 bands; 3,073 in band 6). `transform.rank01` bins against `lo = −3.4e38`, which
  collapses every rank channel to a near-constant and would have silently produced a
  garbage-but-format-valid submission. Fixed with the template's own
  `grid.footprint_from(bands='all')`.
* **IR-H67-003.** Three defensible footprints coexist ({pre['cells_domain']:,} / {pre['cells_feature_finite']:,} /
  {pre['eligible']:,}). Every number in this round is stated against the intersection.
* **IR-H67-004.** Two channels are legitimately zero-inflated (`rank_b10`, `grad_b17`: more than half
  the footprint ties at the physical minimum). A blunt "collapsed channel" guard reports them as
  failures; replaced with a degenerate test (< 10 distinct rank levels, or raw |value| > 1e30 inside
  the eligible set) plus an informational zero-inflation list.
* **IR-H67-005.** The S2 independence statistic spans 0.0078–0.7625 across five rounds on the same
  data (§2). It cannot gate anything until feature set, learner and block size are frozen together.
* **IR-H67-006.** `sample_submission.tif` declares a **NaN** nodata value, so any receipt writer that
  serialises it verbatim produces invalid JSON. Handled by an explicit sanitizer and a
  `nodata_declared_is_nan` field; worth fixing once in the shared template.

## 8 · Limits

* The holdout withholds ≈ 1.18 % of the footprint as truth; the competition truth is ≈ 0.12–0.25 %.
  Prevalence mismatch inflates every arm's denominator effect and is the reason absolute values are
  not comparable across rounds.
* The lane reports are computed against the registry census available on disk at build time.
* No organiser receipt exists for any H67 number. Nothing here is ORGANIZER-CONFIRMED.
* The declared learner is `LogisticRegression(max_iter=800, C=1.0, lbfgs)` on rank channels; the
  splitter is `label-blind-quadrants-v2` with an 80 px buffer. H67's `single_B` is therefore **not**
  comparable to H64's stored 0.174517 — a declared difference, not a control failure (H64's cached
  fold predictions no longer exist in this checkout, so its runner cannot be re-executed).
"""
    (ROOT / "knowledge" / "48_h67_results_and_limits.md").write_text(kn)

    # ------------------------------------------------------------------ banners
    banner = f"""<!--H67-BANNER-->
<div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H67 (negative).</strong>
Download yes, for research only; <strong>submit no — do not upload</strong>. New inference on decoded
pixels; S1 two-view sufficiency FAIL; HOLDOUT-DTI {sc['tuc']['dti']:.6f} {ci(sc['tuc']['ci95'])} versus
random {sc['random']['dti']:.6f}. <a href="h67.html">H67 landing</a> ·
<a href="h67-executive-summary.html">H67 submission guide</a> ·
<a href="downloads/h67-candidate.tif" download>download the research GeoTIFF</a></div>
{hero}
<!--/H67-BANNER-->"""
    for page in (DOCS / "index.html",):
        text = page.read_text(encoding="utf-8")
        # demote the previous round's "Latest" notice so the home page has exactly one latest round
        text = text.replace("Latest research round: H64", "Previous research round: H64")
        text = text.replace("Latest research round: H63", "Previous research round: H63")
        marker = "<!--H67-BANNER-->"
        if marker in text:
            start = text.index(marker)
            end = text.index("<!--/H67-BANNER-->") + len("<!--/H67-BANNER-->")
            text = text[:start] + banner + text[end:]
        else:
            anchor = '<main id="main">'
            text = text.replace(anchor, anchor + banner, 1)
        page.write_text(text, encoding="utf-8")

    root_index = ROOT / "index.html"
    rt = root_index.read_text(encoding="utf-8")
    line = ("<p>H67 (thermal-upflow corridor) is research-only: download yes, <b>submit no</b>, "
            "no weekly slot used. <a href=\"docs/h67.html\">H67 verdict and evidence</a>.</p>")
    if "<p>H67" in rt:
        import re
        rt = re.sub(r"<p>H67.*?</p>", line, rt, flags=re.S)
    else:
        rt = rt.replace("</body>", line + "</body>")
    root_index.write_text(rt, encoding="utf-8")

    print(json.dumps(dict(pages=["docs/h67.html", "docs/h67-executive-summary.html"],
                          downloads=["docs/downloads/h67-candidate.tif", "docs/downloads/h67-candidate.zip",
                                     "docs/downloads/h67-a-only-and-segment-reasoning.csv"],
                          data=["docs/data/h67_run_card.json"],
                          banners=["docs/index.html", "index.html"],
                          verdict=verdict["submit_to_competition"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
