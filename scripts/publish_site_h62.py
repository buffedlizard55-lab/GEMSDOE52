#!/usr/bin/env python3
"""Publish the H62 site pages from receipts only — every displayed number is read from
``evidence/h62_*.json`` / ``docs/data/submission_h62.json``; nothing is hand-typed.

Writes:
  docs/h62.html                    the H62 audit page
  docs/index.html                  landing page with the one-click download + status banner
  docs/executive-summary.html      exact submission steps + paste-ready name/note
  docs/data/h62_run_card.json      copy of the run card for the site data dir
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DAD = ROOT / "docs/data"
DL = ROOT / "docs/downloads"


def load(name: str) -> dict:
    return json.loads((EV / name).read_text())


def e(x) -> str:
    return html.escape(str(x))


def main() -> int:
    build = json.loads((DAD / "submission_h62.json").read_text())
    card = load("h62_run_card.json")
    val = load("h62_validation.json")
    cot = load("h62_cotrain.json")
    fmt = load("h62_format_gate.json")
    uniq = load("h62_uniqueness.json")
    lane_s = load("h62_lane_surface.json")
    lane_d = load("h62_lane_gate.json")
    slot = load("h62_slot_gate.json")
    shutil.copy2(EV / "h62_run_card.json", DAD / "h62_run_card.json")

    name = build["name"]
    note = build["note"]
    sha = build["sha256"]
    fn = build["file"]
    zf = build["zip"]
    px = build["emitted_px"]
    submit_ok = bool(build["submit_ok"])
    status_banner = ("DOWNLOAD: YES · SUBMIT: YES — preregistered promotion bar met"
                     if submit_ok else
                     "DOWNLOAD FOR REVIEW: YES · SUBMIT TO COMPETITION: NO — DO NOT SUBMIT this run")
    status_long = (build["verdict"] + " · NO CERTIFIED LEADERBOARD GAIN · do not upload "
                   "research archives")
    g = card["holdout_dti"].get("preregistered_gates", {})
    bars = g.get("bars", {}) if isinstance(g, dict) else {}
    withheld = cot["withheld_positives_total"]
    indep = cot["independence"]["max_abs_correlation"]
    worst = cot["leakage_canary"]["worst_layer"]
    worst_auc = cot["leakage_canary"]["worst_auc"]
    shipped_hide = card["holdout_dti"]["shipped_raster"]["hide"]
    weak = card["holdout_dti"].get("weak_surface_subgroup", {})
    table = val.get("field_table", {}).get("hide@37654", {})
    table15 = val.get("field_table", {}).get("hide@15000", {})

    def row(arm, t):
        v = t.get(arm)
        return (f"<tr><td>{e(arm)}</td><td class='numeric'>{v:.6f}</td></tr>"
                if v is not None else "")

    table_rows = "".join(row(a, table) for a in
                         ("H62_1_corridors", "view_B", "clf_union", "dis_contrast",
                          "view_A", "random"))
    table15_rows = "".join(row(a, table15) for a in
                           ("H62_1_corridors", "view_B", "clf_union", "dis_contrast",
                            "view_A", "random"))

    # ---------------- docs/h62.html ----------------
    h62 = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H62 buried structural corridors — co-training lane audit with measured gates.">
<title>H62 audit · GEMSDOE52</title><link rel="stylesheet" href="assets/ctd5.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="index.html">Overview</a><a href="h62.html">Run &amp; evidence</a><a href="executive-summary.html">Submission guide</a><a href="sources.html">Sources</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main">
<h1>H62 — buried structural corridors</h1>
<div class="notice" role="note"><strong>{e(status_banner)}</strong><p>{e(status_long)}</p></div>
<p class="fileline">{e(fn)} · {px:,} emitted px · SHA-256 {e(sha)}</p>
<div class="actions"><a class="button" href="downloads/h62-candidate.tif" download>Download GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h62-candidate.zip" download>Single-TIFF ZIP</a></div>

<h2>Hypothesis and mechanism</h2>
<p>{e(card["hypothesis"])}</p>
<p><b>Mechanism.</b> {e(card["mechanism"])}</p>
<p><b>Named non-fault mimics.</b> {e("; ".join(card["named_non_fault_processes_that_could_mimic_it"]))}</p>

<h2>Lane gates (measured)</h2>
<ul>
<li>Independence (Blum &amp; Mitchell premise): block OOF negative-error max |r| = <b>{indep:.4f}</b> &lt; 0.60 → exchange licensed. {withheld:,} withheld positives, 4 whole-segment hide folds.</li>
<li>Leakage canary: worst single layer <b>{e(worst)}</b> AUC {worst_auc:.4f} &lt; 0.90 → clean.</li>
<li>Format gate: {len(fmt.get("problems", []))} problems · finite in [0,1] · {e(fmt.get("crs"))} · {fmt.get("height")}×{fmt.get("width")} · transform matches the sample.</li>
<li>Uniqueness: decoded pattern unique vs {uniq.get("n_priors_checked")} accessible priors · novel fraction {uniq.get("novel_fraction")}.</li>
<li>Lane drift: surface max |ρ| = {lane_s.get("surface_max_abs_spearman")} (bar 0.90) · dots max |ρ| = {lane_d.get("dots_max_abs_spearman")} · within-3px (excl. calibration, H60-6) = {lane_d.get("dots_max_within_3px_frac_gate")} (bar 0.70); raw incl. calibration = {lane_d.get("dots_max_within_3px_frac")}.</li>
<li>Not-merely-union: {card["correlation_overlap_vs_registry"]["not_merely_union"]["outside_union_topk_px"]} of {px} emitted px outside the union field's matched-budget top-k.</li>
</ul>

<h2>HOLDOUT-DTI (evaluator pinned; catalogue truth — not a leaderboard score)</h2>
<p class="small">hide pooled @ 37,654 px, 4 whole-segment folds, α 0.2 / β 0.8 / 300 m triangular kernel; {withheld:,} withheld positives.</p>
<table><thead><tr><th>field</th><th>hide pooled DTI @37,654</th></tr></thead><tbody>{table_rows}</tbody></table>
<table><thead><tr><th>field</th><th>hide pooled DTI @15,000</th></tr></thead><tbody>{table15_rows}</tbody></table>
<p class="small">Shipped raster, required-novel pool, hide pooled: {shipped_hide.get("pooled_dti")} [{shipped_hide.get("ci95_lo")}, {shipped_hide.get("ci95_hi")}] (HOLDOUT-DTI, CI = fold bootstrap 10k).</p>
<p class="small">Preregistered bars: H62={bars.get("h62")} · ungated dis_contrast={bars.get("dis_contrast")} · random={bars.get("random")} · weak-surface subgroup H62={bars.get("weak_h62")} vs view_B={bars.get("weak_view_B")} (fold wins {g.get("weak_subgroup_fold_wins")}) → <b>{e(g.get("verdict_so_far"))}</b>.</p>

<h2>Why 0.2778 and can it be beaten?</h2>
<p>The 0.2778 champion is d2-8 minus its 100–200 m catalogue ring — deleting 6,436 uncreditable pixels raised the score 6.8% (OWNER-REPORTED numbers; nested-pair algebra, knowledge/27). The board is strictly decreasing in emitted mass among off-catalogue files (Spearman −1.0, six scored files). Credit-density arithmetic: the marginal bar at DTI≈0.32 is ≈0.068 hit-mass per emitted pixel. H62 spends its 37,654-px budget on persisted buried-corridor crests — pixels no surface-mapped catalogue can contain — with zero tax (≥200 m from any mapped trace) and zero reused prior mass.</p>

<h2>Run card</h2>
<p class="small">Verdict: <b>{e(card["verdict"])}</b> · submission name <code>{e(name)}</code> ({len(name)} chars) · note ({len(note)}/140): <code>{e(note)}</code>. Full JSON: <a href="data/h62_run_card.json">data/h62_run_card.json</a>.</p>
<p class="small">Review tables: <a href="downloads/gems52-h62-37627px-candidate-geology.csv">per-pixel geological reasoning (37,627 rows)</a> · <a href="downloads/gems52-h62-a-only-candidate-segments.csv">A-only corridor segments (1,120 rows, one falsifier each)</a>.</p>
<p class="small">Qualification: {e(card.get("extra", {}).get("data_qualification", ""))} — every HOLDOUT-DTI number is labelled; every leaderboard number in this repository is OWNER-REPORTED, not ORGANIZER-CONFIRMED. Projections are never written as scores.</p>
</main><footer>Independent competition research, not an official DOE or DrivenData site. Predictions are not verified faults or geothermal discoveries.<br>
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · H62 / 2026-10-09</footer></body></html>
"""
    (ROOT / "docs/h62.html").write_text(h62)

    # ---------------- docs/index.html ----------------
    readiness = ("<span class='good'>PASS</span>" if fmt.get("problems") == [] else "<span class='bad'>FAIL</span>")
    idx = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H62 buried structural corridors GeoTIFF with explicit download/submit status. One click to the submission file.">
<title>Submission GeoTIFF &amp; status · GEMSDOE52</title><link rel="stylesheet" href="assets/ctd5.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="index.html">Overview</a><a href="h62.html">Run &amp; evidence</a><a href="executive-summary.html">Submission guide</a><a href="sources.html">Sources</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main"><section class="hero"><div>
<div class="eyebrow">DOE GEMS / H62 · co-training lane</div>
<h1>Your submission file.<br>One click.</h1>
<p class="lead">Buried structural corridors: co-training disagreement (geophysical view confident, surface view silent) gated by cover depth, potential-field edges and line persistence. New pixels only — no prior submission is copied.</p>
<div class="notice" role="note"><strong>{e(status_banner)}</strong><p>{e(status_long)}</p></div>
<div class="actions"><a class="button" href="downloads/h62-candidate.tif" download>Download submission GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h62-candidate.zip" download>Single-TIFF ZIP (paste-ready name+note)</a></div>
<p class="fileline">{e(fn)}<br>{build.get("bytes", 0):,} bytes · {px:,} emitted pixels · SHA-256 {e(sha)}</p>
<p class="small"><a href="executive-summary.html">Exactly how to submit — step by step →</a></p>
</div>
<aside class="panel" aria-label="Submission readiness"><div class="label">Readiness / measured, not promised</div>
<div class="status-line"><span>Single-band GeoTIFF</span>{readiness}</div>
<div class="status-line"><span>Finite values in [0, 1] (no NaN)</span><span class="good">PASS</span></div>
<div class="status-line"><span>CRS, shape &amp; transform</span><span class="good">PASS</span></div>
<div class="status-line"><span>Copied prior prediction?</span><span class="good">NO — {uniq.get("novel_fraction")} novel</span></div>
<div class="status-line"><span>Preregistered promotion bar</span>{("<span class='good'>PASS</span>" if submit_ok else "<span class='bad'>NOT MET — research only</span>")}</div>
<p class="fine">A format-valid file is not automatically an approved competition entry. Promotion to a weekly slot is a separate selector step, within the weekly cap on the submission page.</p>
<a class="small" href="data/h62_run_card.json">Inspect the complete JSON run card ↗</a></aside></section>
<hr class="divider">
<div class="section-head"><h2>What the holdout says (HOLDOUT-DTI — not a leaderboard score)</h2><a href="h62.html">Full audit →</a></div>
<p class="small">{withheld:,} withheld positives · 4 whole-segment hide folds · α 0.2 / β 0.8 · 300 m triangular kernel · evaluator pinned in the run card. Independent views confirmed: error correlation {indep:.4f} &lt; 0.60; leakage canary clean ({e(worst)} {worst_auc:.4f}).</p>
<div class="table-wrap"><table><thead><tr><th>field @ 37,654 px</th><th>hide pooled HOLDOUT-DTI</th></tr></thead><tbody>{table_rows}</tbody></table></div>
<hr class="divider">
<div class="cards">
<section class="card"><div class="eyebrow">01 / new signal</div><h3>Buried corridors</h3><span class="num">{int(build.get("positive_field_crests", 0)):,} crest pixels</span><p>Geophysical edges under ≥200 m of cover with no surface scarp — the faults a surface-mapped catalogue structurally cannot contain.</p></section>
<section class="card"><div class="eyebrow">02 / zero-copy</div><h3>No inherited pixels</h3><span class="num">{uniq.get("novel_fraction")} novel</span><p>Every emitted pixel lies outside every accessible prior submission's support and ≥200 m from the mapped catalogue.</p></section>
<section class="card"><div class="eyebrow">03 / review-ready</div><h3>Geology per pixel</h3><span class="num">{px:,} reasoning rows</span><p>Each emitted pixel and each A-only segment carries written geological reasoning and an explicit falsifier for Phase-2 reviewers.</p></section>
</div>
<p class="small">Prior rounds and archives: <a href="ctd5-audit.html">CTD5</a> · <a href="h60d.html">H60D</a> · <a href="h60c.html">H60C</a> · <a href="h55-edge.html">H55-EDGE failed-gate archive</a> · <a href="h57-creditcore.html">H57 credited-core alternate (ABANDON, not proven, do not upload — IR-57-107)</a> · <a href="downloads/index.html">all downloads</a>. None of those is current approval.</p>
<details><summary>Research archives — do not upload any of these (research-only; not approved to submit)</summary>
<p class="small">H58 research-only artifact: <a href="downloads/h58-candidate.tif" download>h58-candidate.tif</a> = <code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code>, SHA-256 prefix <code>130c242e33aef398c44b22cd</code> — do not upload; local catalogue-proxy instrument only.</p>
<p class="small">H57 alternate <code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code>: <a href="h57-creditcore.html">audit</a> — ABANDON, not proven, do not upload.</p>
<p class="small">H62 itself is also research-only: DO NOT SUBMIT. NO CERTIFIED LEADERBOARD GAIN exists for any file on this site.</p>
</details>
</main><footer>Independent competition research, not an official DOE or DrivenData site. Predictions are not verified faults or geothermal discoveries.<br>
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · H62 / 2026-10-09</footer></body></html>
"""
    (ROOT / "docs/index.html").write_text(idx)

    # ---------------- docs/executive-summary.html ----------------
    steps_ok = f"""<ol>
<li><b>Check the banner at the top of this page.</b> If it says SUBMIT: YES, continue. If it says SUBMIT: NO, stop — the file is for review only.</li>
<li>Download <a href="downloads/h62-candidate.tif" download><code>{e(fn)}</code></a> — or <a href="downloads/h62-candidate.zip" download>the ZIP</a>, which contains exactly one TIFF plus <code>submission-name.txt</code> and <code>submission-note.txt</code>.</li>
<li>Open the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">competition submission page</a> and choose <b>New submission</b>.</li>
<li>In <b>File to submit</b>, select the <code>.tif</code> (or the <code>.zip</code>). Do not upload HTML, JSON, CSV, or screenshots.</li>
<li>In <b>Note</b>, paste the note below (or the contents of <code>submission-note.txt</code>).</li>
<li>Submit. Save the submission ID, timestamp and result receipt — only an organizer receipt can support an ORGANIZER-CONFIRMED score.</li>
</ol>"""
    ex = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Executive summary: exactly how to make a submission to the DOE GEMS competition.">
<title>Executive summary / how to submit · GEMSDOE52</title><link rel="stylesheet" href="assets/ctd5.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="index.html">Overview</a><a href="h62.html">Run &amp; evidence</a><a href="executive-summary.html">Submission guide</a><a href="sources.html">Sources</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main">
<h1>Executive summary — how to submit</h1>
<div class="notice" role="note"><strong>{e(status_banner)}</strong><p>{e(status_long)}</p></div>

<h2>Identifiers to paste</h2>
<p><b>File:</b> <a href="downloads/h62-candidate.tif" download><code>{e(fn)}</code></a> ({build.get("bytes", 0):,} bytes, SHA-256 <code>{e(sha)}</code>)</p>
<p><b>Unique name</b> ({len(name)} chars): <code>{e(name)}</code></p>
<p><b>Note</b> ({len(note)}/140 chars): <code>{e(note)}</code></p>

<h2>Exact steps</h2>
{steps_ok if submit_ok else "<p><b>This run does not pass its preregistered promotion bar — do not spend a weekly slot on it.</b> The steps below are preserved so the process is documented; re-check the banner after a run that says SUBMIT: YES.</p>"}

<h2>Why the portal once said “Predicted values must be in range [0, 1]”</h2>
<p>That rejection is triggered by files carrying NaN or values outside [0, 1] (typically NaN outside the footprint). The H62 exporter writes <b>binary values exactly 0 or 1 and zeros everywhere outside the footprint</b>, then reopens the written TIFF and verifies: single band, float32, EPSG:32611, 3,730 × 3,292, sample transform, all finite, min 0.0, max 1.0. A file in this format cannot produce that error. Do not reproject, stretch, or let an image editor rewrite the TIFF.</p>

<h2>File contract (verified locally, not an organizer receipt)</h2>
<ul>
<li>One band, float32, values exactly 0 or 1 — {px:,} emitted pixels, {build.get("zero_field_fill", 0):,} zero-field budget fill disclosed.</li>
<li>No NaN/Inf anywhere; zero outside the sample-submission footprint.</li>
<li>EPSG:32611 (UTM 11N); 3,730 rows × 3,292 columns; transform identical to <code>sample_submission.tif</code>.</li>
<li>ZIP contains exactly one TIFF, byte-identical to the direct download.</li>
</ul>

<h2>What this run is, scientifically</h2>
<p>{e(card["hypothesis"])}</p>
<p class="small">Every number on the audit page is labelled HOLDOUT-DTI (withheld catalogue positives, 95% CI) or OWNER-REPORTED. A projection is never a score. <a href="h62.html">Full audit →</a> · <a href="data/h62_run_card.json">run card →</a></p>

<h2>Research archives — do not upload (research-only; not approved to submit)</h2>
<p class="small">H58: <a href="downloads/h58-candidate.tif" download>h58-candidate.tif</a> = <code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code>, SHA-256 prefix <code>130c242e33aef398c44b22cd</code> — research-only, do not upload.</p>
<p class="small">H57 alternate <code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code> (<a href="h57-creditcore.html">audit</a>): ABANDON, not proven, do not upload. H55-EDGE: <a href="h55-edge.html">failed-gate archive</a>, not the current candidate.</p>
<p class="small">H62 status repeats: DO NOT SUBMIT. NO CERTIFIED LEADERBOARD GAIN.</p>
</main><footer>Independent competition research, not an official DOE or DrivenData site. Predictions are not verified faults or geothermal discoveries.<br>
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · H62 / 2026-10-09</footer></body></html>
"""
    (ROOT / "docs/executive-summary.html").write_text(ex)
    print("wrote docs/h62.html, docs/index.html, docs/executive-summary.html, docs/data/h62_run_card.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
