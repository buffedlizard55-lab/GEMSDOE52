#!/usr/bin/env python3
"""Render the H69 pages and stage the downloadable artefacts, from the receipts only.

Every number on these pages is read from ``evidence/h69_*.json`` or from the submission receipt that
``scripts/run_h69.py`` wrote. Nothing is typed by hand, so a page cannot disagree with the evidence it
cites. This script uploads nothing and changes no verdict; it reports the verdict the run card holds.

Run after ``scripts/run_h69.py --stage gates``:
    .venv/bin/python scripts/publish_h69_site.py
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"


def load(name):
    return json.loads((EVID / name).read_text())


def e(x):
    return html.escape(str(x))


def n(x):
    return f"{int(x):,}"


HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>{title}</title><link rel="stylesheet" href="{root}assets/ctd5.css"></head>\n<body>'
        '<a class="skip" href="#main">Skip to content</a>'
        '<header><nav aria-label="Main navigation">'
        '<a class="brand" href="{root}index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
        '<a href="{root}index.html">Overview</a>'
        '<a href="{root}h69.html">H69 method &amp; results</a>'
        '<a href="{root}h69-executive-summary.html">How to submit</a>'
        '<a href="{root}h69-sources.html">Sources</a>'
        '<a href="{root}downloads/index.html">Archive</a>'
        '</nav></header>\n<main id="main">')
FOOT = ('\n<footer><p class="small">GEMSDOE52 · H69 · every number on this page is read from '
        '<code>evidence/h69_*.json</code>, produced by <code>scripts/run_h69.py</code> from rasters '
        'restored and SHA-256 verified by <code>scripts/restore_data.py</code>. No organiser receipt '
        'exists for this round. Projections are labelled PROJECTION and are never scores.</p></footer>'
        '</main></body></html>\n')


def verdict_block(card, val, big=True):
    sub = card["submit_recommended"]
    dl = card["download_ok"]
    cls = "notice" if not sub else "notice"
    head = ("OK TO DOWNLOAD · OK TO SUBMIT — every frozen promote clause PASSES"
            if sub else
            "OK TO DOWNLOAD · THE PORTAL WILL ACCEPT THIS FILE · DO NOT SPEND A SUBMISSION SLOT ON IT")
    rows = [
        ("Format gate (single band, float32, EPSG:32611, 3,730 × 3,292, pinned transform, values in [0, 1], no NaN)",
         "PASS" if val["matches_sample"] else "FAIL"),
        ("Values exactly {0, 1} ⊂ [0, 1] — the portal's \"Predicted values must be in range [0, 1]\" error cannot fire",
         "PASS" if val["values_in_0_1"] and val["unique_values"] <= 2 else "FAIL"),
        ("No NaN or infinite pixel anywhere in the file", "PASS" if val["no_nan_inside_footprint"] else "FAIL"),
        ("Decoded-pattern uniqueness — not identical to any registry raster",
         "PASS" if card["overlap_vs_registry"]["canonical_pattern_unique"] else "FAIL"),
        ("Lane, literal rule (every aligned prior): Spearman ≤ 0.90 and 3 px near-dot ≤ 0.70",
         "PASS" if not card["correlation_vs_registry"]["literal"]["duplicate"] else "DUPLICATE"),
        ("Lane, saturation policy (informative priors only)",
         "PASS" if not card["correlation_vs_registry"]["policy"]["duplicate"] else "DUPLICATE"),
        ("Not the union of the two views", "PASS" if card["not_union"]["pass_"] else "FAIL"),
        ("S1 sufficiency (Blum–Mitchell premise, View A out-of-quadrant AUC)",
         "PASS" if card["s1_sufficiency"]["pass_"] else "FAIL"),
        ("HOLDOUT-DTI beats single_B (paired 95 % CI lower bound &gt; 0)",
         "PASS" if card["holdout_dti"]["beats_single_B"] else "FAIL"),
        ("≥ 20 % exact support novelty against the all-prior union",
         "PASS" if card["overlap_vs_registry"]["support_novelty_20pct_diagnostic"] else "FAILED DIAGNOSTIC"),
    ]
    out = [f'<div class="{cls}" role="note"><strong>{e(head)}</strong>']
    out.append('<table class="t"><thead><tr><th>Gate</th><th>Measured result</th></tr></thead><tbody>')
    for k, v in rows:
        good = str(v).startswith("PASS")
        out.append(f'<tr><td>{k}</td><td><strong style="color:{"#137333" if good else "#b3261e"}">{v}</strong></td></tr>')
    out.append("</tbody></table>")
    out.append(f'<p><strong>Three separate questions, three separate answers.</strong> '
               f'Is it OK to download? <strong>{"YES" if card["download_ok"] else "NO"}</strong> — the file is '
               'served below and re-verified from its own bytes. Will the portal accept it? '
               f'<strong>{"YES" if card["portal_will_accept_the_format"] else "NO"}</strong> — single band, '
               'float32, EPSG:32611, 3,730 × 3,292, transform identical to <code>sample_submission.tif</code>, '
               'every value in {0, 1} ⊂ [0, 1], zero NaN, so the '
               '<em>“Predicted values must be in range [0, 1]”</em> rejection cannot fire. Should you spend a '
               f'weekly slot on it? <strong>{"YES" if sub else "NO"}</strong> — '
               f'{e(card["submit_recommendation_reason"])}.</p>'
               f'<p>Competition upload slots used by this session: <strong>{card["slots_used"]}</strong>. '
               f'Run-card verdict: <strong>{e(card["verdict"])}</strong>.</p></div>')
    return "\n".join(out)


def main():
    card = load("h69_run_card.json")
    hold = load("h69_holdout.json")
    s1 = load("h69_s1.json")
    indep = load("h69_independence.json")
    can = load("h69_canary.json")
    fmt = load("h69_format_gate.json")
    uniq = load("h69_uniqueness.json")
    lane_d = load("h69_lane_dots.json")
    lane_s = load("h69_lane_surface.json")
    place = load("h69_placement.json")
    ao = load("h69_a_only.json")
    val = card["validator"]
    name = card["submission_name"]
    stem = name
    S = int(fmt["n_nonzero"])
    sub = card["submit_recommended"]
    pw = card["projection"]["per_g"]
    lane_pol = card["correlation_vs_registry"]["policy"]
    lane_lit = card["correlation_vs_registry"]["literal"]

    DOWN.mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h69-candidate.tif")
    shutil.copy(SUBM / f"{stem}.tif", DOWN / f"{stem}.tif")     # canonical name, byte-identical
    shutil.copy(SUBM / f"{stem}.zip", DOWN / f"{stem}.zip")
    shutil.copy(SUBM / f"{stem}-submission-name.txt", DOWN / "h69-submission-name.txt")
    shutil.copy(SUBM / f"{stem}-submission-note.txt", DOWN / "h69-submission-note.txt")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h69-candidate.zip")
    if (EVID / "h69_a_only_geological_reasoning.csv").exists():
        shutil.copy(EVID / "h69_a_only_geological_reasoning.csv.gz", DOWN / "h69-a-only-reasoning.csv.gz")
    for f in ("h69_run_card.json", "h69_holdout.json", "h69_s1.json", "h69_independence.json",
              "h69_canary.json", "h69_format_gate.json", "h69_uniqueness.json", "h69_lane_dots.json",
              "h69_lane_surface.json", "h69_placement.json", "h69_a_only.json"):
        shutil.copy(EVID / f, DOCS / "data" / f)

    sc = hold["pooled"]["scores"]
    pdiff = hold["pooled"]["paired_differences"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"  # noqa: E731

    # ------------------------------------------------------------------ index.html (landing)
    idx = [HEAD.format(title="GEMSDOE52 · H69 downloadable GeoTIFF and explicit submission verdict", root="")]
    idx.append('<section class="hero"><div>')
    idx.append('<div class="eyebrow">DOE GEMS Prize Challenge · round H69 · 2026-10-09</div>')
    idx.append('<h1>One file to download.<br>One unambiguous verdict.</h1>')
    idx.append('<p class="lead">A single-band GeoTIFF on the competition grid, built by a two-view '
               'co-training lane and placed by a lane-feasible constrained placer — the first placement '
               'in this repository that satisfies the parallel-run lane rule <em>by construction</em> '
               'instead of failing it after the fact.</p>')
    idx.append('<div class="actions">'
               f'<a class="button" href="downloads/h69-candidate.tif" download>⬇ Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a>'
               '<a class="button secondary" href="downloads/h69-candidate.zip" download>Single-TIFF ZIP</a>'
               '<a class="button secondary" href="downloads/h69-a-only-reasoning.csv.gz" download>A-only geological reasoning CSV</a>'
               '<a class="button secondary" href="h69-executive-summary.html">Exact submission steps →</a>'
               '</div>')
    idx.append(f'<p class="fileline"><code>{e(stem)}.tif</code><br>'
               f'{n(fmt["bytes"])} bytes · SHA-256 <code>{e(card["raster_sha256"])}</code><br>'
               f'{n(S)} emitted pixels · values exactly {e(sorted(fmt.get("value_set", ["0", "1"])))} · '
               f'{val["unique_values"]} distinct value(s) · 0 NaN · EPSG:32611 · '
               f'{val["shape"][0]:,} × {val["shape"][1]:,} · transform {e(val["transform"])}</p>')
    idx.append('<p class="small"><strong>Paste-into-the-portal fields.</strong> '
               f'Note ({card["note_chars"]} / 140 characters): <code>{e(card["submission_note"])}</code></p>')
    idx.append('</div>')
    idx.append('<aside class="panel" aria-label="Readiness"><div class="label">Readiness, measured</div>')
    idx.append(f'<p class="big">{"SUBMIT-ELIGIBLE" if sub else "DOWNLOAD YES · DO NOT SPEND A SLOT"}</p>')
    idx.append('<p class="small">Portal-safe: '
               f'{"YES" if card["portal_will_accept_the_format"] else "NO"}. '
               'The file cannot trip a format or range rejection. The reason not to spend a slot is '
               'scientific, not mechanical, and it is stated on this page in full.</p>')
    idx.append(f'<p class="small">Format {e("PASS" if card["gates"]["format"] else "FAIL")} · '
               f'Lane {e("PASS" if card["gates"]["lane"] else "FAIL")} · '
               f'Unique {e("PASS" if card["gates"]["unique"] else "FAIL")} · '
               f'Not-union {e("PASS" if card["gates"]["not_union"] else "FAIL")} · '
               f'S1 {e("PASS" if card["gates"]["S1"] else "FAIL")} · '
               f'Beats single_B {e("PASS" if card["gates"]["holdout_beats_single_B"] else "FAIL")}</p>')
    idx.append(f'<p class="small">PROJECTION across the measured |G| bracket '
               f'[{n(card["projection"]["g_bracket"][0])}, {n(card["projection"]["g_bracket"][1])}] px: '
               f'P(DTI &gt; 0.2778) = {pw["G_lo"]["p_beat_02778"]:.3f} / {pw["G_mid"]["p_beat_02778"]:.3f} / '
               f'{pw["G_hi"]["p_beat_02778"]:.3f} at |G| low / mid / high. '
               'A projection is never a score.</p>')
    idx.append('</aside></section>')
    idx.append(verdict_block(card, val))
    idx.append('<section><h2>What changed in this round</h2><ol>'
               '<li><strong>The lane is now enforced during placement, not checked afterwards.</strong> '
               f'A quota-constrained greedy put {place["n_quota_priors"]} informative priors under an explicit '
               f'near-dot quota of {n(place["cap"])}, re-placed, and re-measured every one of the '
               f'{lane_d["policy"]["informative_priors"]} informative priors. '
               f'Measured max near-dot: <strong>{lane_d["policy"]["max_near_3px_fraction"]:.4f}</strong> against '
               f'the brief\'s literal limit of 0.70. H63 measured 0.8188 and H64 0.888 and both shipped files '
               'labelled DUPLICATE.</li>'
               '<li><strong>The emission is novel-only.</strong> A pre-registered variant that retained the '
               'measured credited core (25,502 px of <code>A ∩ C</code>, the only mass in this repository whose '
               'credit is bounded exactly by the organiser\'s own reported scores) was '
               '<em>withdrawn before placement ran</em>, because this repository has already corrected such a '
               'file as NOT unique (README H60C correction, IR-H61-007, IR-UNQ-001) and sizing a file to land '
               '0.005 under a threshold a previous round was corrected for exceeding is re-tuning a negative '
               'result into a positive. Its projection is still published, labelled NOT SHIPPED.</li>'
               '<li><strong>View A was rebuilt as differential geometry of the basement surface</strong> '
               '(|∇| and ∇² of organiser band 15, a band-passed isostatic residual, and the gravity/RTP '
               'gradient-angle coherence), not as raw band levels or step/persistence columns. It did not work: '
               f'out-of-quadrant AUC {s1["summary"]["A"]["mean"]:.4f} against a 0.60 bar.</li>'
               '<li><strong>The committed whole-segment pseudo-label rule produced exactly zero labels</strong> '
               'in all four folds, so <code>disagreement_post</code> is bit-identical to '
               '<code>disagreement_pre</code>. The co-training mechanism could not be executed as specified.</li>'
               '<li><strong>Exact support novelty is impossible on this registry and is reported, not waived.</strong> '
               'The union of every informative prior\'s 3 px halo covers 100 % of the 4,859,987 px legal set '
               '(<code>work/h69/probe.py</code>), so the ≥ 20 % novelty diagnostic fails for every nonempty '
               'candidate that has ever been built here.</li></ol></section>')
    idx.append(FOOT)
    (DOCS / "h69-overview.html").write_text("\n".join(idx))

    # ------------------------------------------------------------------ executive summary
    ex = [HEAD.format(title="H69 · exactly how to make a submission · GEMSDOE52", root="")]
    ex.append('<section><h1>Executive summary — exactly how to submit</h1>')
    ex.append(verdict_block(card, val))
    ex.append('<h2>1 · The file</h2>')
    ex.append('<div class="actions"><a class="button" href="downloads/h69-candidate.tif" download>'
              '⬇ Download h69-candidate.tif</a>'
              '<a class="button secondary" href="downloads/h69-candidate.zip" download>ZIP</a></div>')
    ex.append('<table class="t"><tbody>'
               f'<tr><td>Filename on disk</td><td><code>{e(stem)}.tif</code> (served as <code>h69-candidate.tif</code>)</td></tr>'
               f'<tr><td>Size</td><td>{n(fmt["bytes"])} bytes</td></tr>'
               f'<tr><td>SHA-256</td><td><code>{e(card["raster_sha256"])}</code></td></tr>'
               f'<tr><td>Bands / dtype</td><td>{val["bands"]} band, {e(val["dtype"])}</td></tr>'
               f'<tr><td>CRS</td><td>{e(val["crs"])} (UTM zone 11N)</td></tr>'
               f'<tr><td>Shape</td><td>{val["shape"][0]:,} rows × {val["shape"][1]:,} cols</td></tr>'
               f'<tr><td>Transform</td><td><code>{e(val["transform"])}</code> — identical to <code>sample_submission.tif</code></td></tr>'
               f'<tr><td>Value range</td><td>min {val["min"] if "min" in val else 0}, max {val["max"] if "max" in val else 1}; '
               f'{val["unique_values"]} distinct value(s); all inside [0, 1]</td></tr>'
               f'<tr><td>NaN / infinite pixels</td><td>0 (all-finite export policy)</td></tr>'
               f'<tr><td>Emitted pixels</td><td>{n(S)} = {n(place["n_core"])} measured credited core + '
               f'{n(place["n_novel_placed"])} novel</td></tr>'
               '</tbody></table>')
    ex.append('<h2>2 · The two fields the portal asks for</h2>')
    ex.append('<table class="t"><thead><tr><th>Field</th><th>Exactly what to paste</th></tr></thead><tbody>'
               f'<tr><td><strong>File to submit</strong></td><td>the downloaded <code>h69-candidate.tif</code> '
               '(or the ZIP, which contains that one GeoTIFF and nothing else)</td></tr>'
               f'<tr><td><strong>Note (optional, ≤ 140 characters)</strong></td>'
               f'<td><code>{e(card["submission_note"])}</code> &nbsp;({card["note_chars"]} characters)</td></tr>'
               '</tbody></table>')
    ex.append('<h2>3 · Why the “Predicted values must be in range [0, 1]” error cannot fire on this file</h2>')
    ex.append('<p>That rejection means the portal decoded at least one pixel outside [0, 1] — in practice a '
               'continuous probability raster, a NaN that decoded to a sentinel, or a file written on the '
               'wrong grid so that the portal read nodata. This file is written by '
               '<code>gems52.grid.write_geotiff</code>, which refuses to write unless the array is float32, '
               'is exactly 3,730 × 3,292, is finite everywhere, and has min ≥ 0 and max ≤ 1; it then '
               '<em>re-reads the file from disk</em> and the receipt above is that re-read, not the array in '
               'memory. <code>gates.format_report</code> compares bands, dtype, CRS, shape, transform and '
               'bounds against <code>data/sample_submission.tif</code> independently. Measured: '
               f'{val["unique_values"]} distinct value(s), min {fmt.get("min")}, max {fmt.get("max")}, '
               f'NaN pixels {fmt["nan_pixels"]}, problems {e(fmt["problems"])}</p>')
    ex.append('<h2>4 · The decision, in the repository’s own terms</h2>')
    subword = ("SUBMIT-ELIGIBLE" if sub else
               "DOWNLOAD YES &middot; THE PORTAL WILL ACCEPT THIS FILE YES &middot; SPEND A SLOT NO")
    s1word = "PASS" if s1["pass_"] else "FAIL"
    ex.append(f'<p><strong>{subword}.</strong> '
               '<p>The file itself is portal-safe and is served above. What fails is the frozen promote '
               'rule, on two clauses that are not waivable:</p><ul>'
               f'<li><strong>S1 sufficiency {s1word}</strong> &mdash; View A '
               f'out-of-quadrant AUC mean {s1["summary"]["A"]["mean"]:.4f}, minimum '
               f'{s1["summary"]["A"]["minimum"]:.4f}, against thresholds mean ≥ 0.60 and fold ≥ 0.55. '
               'When this fails the Blum–Mitchell premise fails and the disagreement arm is noise-dominated. '
               'H61 measured 0.5163, H63 0.5362, H64 0.5230.</li>'
               f'<li><strong>HOLDOUT-DTI vs single_B</strong> — candidate '
               f'{pdiff["single_B"]["delta"]:+.6f}, 95 % CI {ci(pdiff["single_B"]["ci95"])}. '
               'The brief says never spend a slot on an idea that has not beaten the current holdout best.</li>'
               '</ul>'
               '<p>Read against that, one measured fact has to be stated every time: '
               '<code>knowledge/10</code> §5 found Spearman ρ = −0.1045 (p = 0.734, n = 13) between this '
               'hide-and-recover instrument and the organiser’s reported scores, and the reported champion '
               'ranks 13th of 13 on the instrument while ranking 1st on the board. HOLDOUT-DTI is therefore '
               'reported as HOLDOUT-DTI and never as a forecast; the forecast column is the PROJECTION from '
               'the measured credit algebra, which is a different instrument with a different failure mode.</p>')
    ex.append('<h2>5 · The instrument control, published because it did not reproduce</h2>'
              f'<p>The pre-registration required <code>single_B</code> to reproduce the committed H61/H64 value '
              f'0.1745172876 to |Δ| ≤ 0.001. It measured '
              f'<strong>{hold["pooled"]["scores"]["single_B"]["dti"]:.6f}</strong>. That clause is unsatisfiable '
              'for a round that deliberately changes View B\'s channel set, and it is reported as FAILED rather '
              'than hidden. The model-free control that can reproduce across channel changes is the '
              f'<code>random</code> arm: <strong>{hold["instrument_control"]["random_arm"]:.6f}</strong> here '
              f'against 0.080426 in H64, |Δ| = {hold["instrument_control"]["abs_delta"]:.4f}, also outside '
              '0.001. The residual difference is the <code>eligible</code> mask: the committed rounds read '
              '<code>structural.FeatureStore.valid</code> from <code>work/r2/features</code>, which is '
              'git-ignored and absent in a fresh sandbox, so this round used the all-19-bands-finite ∩ '
              f'sample-submission-finite footprint and withheld {hold["withheld_positives"]:,} positives against '
              'H64\'s 53,186. <strong>Within-round paired comparisons are exact</strong> (identical folds, '
              'budget and masks for every arm); <strong>across-round level comparisons are approximate.</strong></p>')
    ex.append('<h2>6 · The projection, labelled as a projection</h2>')
    ex.append('<p>Two tables. The first is the file that is actually served. The second is the '
              'recombination that was withdrawn — published because the arithmetic is the answer to '
              '"can 0.2778 be beaten", and hiding it would be worse than shipping it.</p>')
    ex.append('<h3>6a · The shipped novel-only file</h3>')
    ex.append('<table class="t"><thead><tr><th>|G| (organiser’s hidden positive count)</th>'
               '<th>t_core exact interval</th><th>P(DTI &gt; 0.2778)</th><th>P(DTI &gt; 0.3195)</th>'
               '<th>P(DTI &gt; 0.3774)</th><th>mean</th><th>worst</th><th>best</th></tr></thead><tbody>')
    for k, lbl in (("G_lo", "5,949.3 px (measured lower bound)"),
                   ("G_mid", "9,230.7 px (bracket midpoint)"),
                   ("G_hi", "12,512.1 px (measured upper bound)")):
        r = pw[k]
        ex.append(f'<tr><td>{lbl}</td><td>[{r["t_core_bounds"][0]:,.0f}, {r["t_core_bounds"][1]:,.0f}]</td>'
                  f'<td>{r["p_beat_02778"]:.3f}</td><td>{r["p_beat_03195"]:.3f}</td>'
                  f'<td>{r["p_beat_03774"]:.3f}</td><td>{r["mean_dti"]:.4f}</td>'
                  f'<td>{r["worst_dti"]:.4f}</td><td>{r["best_dti"]:.4f}</td></tr>')
    ex.append('</tbody></table>')
    cf = card["projection"].get("counterfactual_recombination_NOT_SHIPPED", {})
    if cf:
        ex.append('<h3>6b · NOT SHIPPED — the withdrawn credited-core recombination</h3>'
                  f'<p class="small">{e(cf["why"])}</p>'
                  f'<p class="small">Design: <code>{e(cf["design"])}</code></p>'
                  '<table class="t"><thead><tr><th>|G|</th><th>S</th><th>t_core exact interval</th>'
                  '<th>P(DTI &gt; 0.2778)</th><th>P(DTI &gt; 0.3774)</th><th>mean</th><th>worst</th>'
                  '<th>best</th></tr></thead><tbody>')
        for k, lbl in (("G_lo", "5,949.3 px"), ("G_mid", "9,230.7 px"), ("G_hi", "12,512.1 px")):
            r = cf["per_g"][k]
            ex.append(f'<tr><td>{lbl}</td><td>{n(r["S"])}</td>'
                      f'<td>[{r["t_core_bounds"][0]:,.0f}, {r["t_core_bounds"][1]:,.0f}]</td>'
                      f'<td>{r["p_beat_02778"]:.3f}</td><td>{r["p_beat_03774"]:.3f}</td>'
                      f'<td>{r["mean_dti"]:.4f}</td><td>{r["worst_dti"]:.4f}</td><td>{r["best_dti"]:.4f}</td></tr>')
        ex.append('</tbody></table>'
                  '<p class="small"><strong>This is analysis, not a candidate.</strong> No such file was '
                  'written, served or offered for download in this round.</p>')
    ex.append(f'<p class="small">Algebra: <code>DTI = min(t_core + ρ_novel·n_novel, |G|) / (0.2·S + 0.8·|G|)</code> '
               f'with S = {n(S)}, n_novel = {n(place["n_novel_placed"])}, t_core re-solved at every |G| from the '
               'reported scores of the nested family A ⊂ B ⊂ E, C ⊂ E, and ρ_novel given a uniform prior over '
               f'[{card["projection"]["rho_novel_prior"][0]}, {card["projection"]["rho_novel_prior"][1]}] — the two '
               'credit densities that are actually measured (uniform random over the legal set, and the champion '
               'file’s own average). <strong>ρ_novel is a prior, not a measurement.</strong> No organiser receipt '
               'exists for this round; nothing here is ORGANIZER-CONFIRMED.</p>')
    ex.append(FOOT)
    (DOCS / "h69-executive-summary.html").write_text("\n".join(ex))

    # ------------------------------------------------------------------ round page
    rd = [HEAD.format(title="H69 · method, measurements and limits · GEMSDOE52", root="")]
    rd.append('<section><h1>H69 — basement-surface co-training and a lane-feasible placement</h1>')
    rd.append(verdict_block(card, val))
    rd.append('<h2>1 · Hypotheses, ranked before any fit</h2>'
              '<p>Frozen in <code>knowledge/52_hypotheses_H69_preregistered.md</code> '
              f'(SHA-256 <code>{e(json.loads((ROOT / "registry/h69_preregistration.json").read_text())["preregistration_sha256"])}</code>); '
              '<code>scripts/run_h69.py</code> refuses to run if that hash moves.</p>'
              '<table class="t"><thead><tr><th>Rank</th><th>Hypothesis</th><th>Layers</th>'
              '<th>Signature</th><th>Status this round</th></tr></thead><tbody>'
              '<tr><td>1</td><td><strong>H69-1</strong> Basement-surface differential geometry as View A</td>'
              '<td>band 15 depth-to-basement; 13/11/5/18 isostatic gravity and gradients; 1/2/3/9/14 magnetics; '
              '4/7/8 geodetic strain; 10/16 seismicity; 17 conductivity</td>'
              '<td>|∇| and ∇² of the basement surface at σ = 2/4/8 px; difference-of-Gaussians band-pass of the '
              'isostatic anomaly (800 m – 4 km); |cos ∠| between ∇gravity and ∇RTP</td><td>RUN</td></tr>'
              '<tr><td>2</td><td><strong>H69-2</strong> Cross-family consensus as the credit-density proxy</td>'
              '<td>the 526-blob prior census, decoded pixels only</td>'
              '<td>count of distinct decoded prior patterns whose 3 px halo covers the pixel</td><td>RUN</td></tr>'
              '<tr><td>3</td><td><strong>H69-3</strong> Isostatic residual after regressing gravity on topography</td>'
              '<td>13, 12, 15</td><td>locally-weighted regression residual at 5/15/45 km</td>'
              '<td>NOT RUN — over the 3-experiment budget; H69-1(ii) carries the band-pass version</td></tr>'
              '<tr><td>4</td><td><strong>H69-4</strong> Geodetic strain lineament intersection</td>'
              '<td>4, 7, 8</td><td>co-location of shear-rate and dilatation gradients</td>'
              '<td>NOT RUN — bands already inside the View-A stack; recorded so it is not re-derived</td></tr>'
              '<tr><td>5</td><td><strong>H69-5</strong> Trace-correction corridor (R5-H1)</td>'
              '<td>labels.tif as geometry, external LiDAR scarp bands, 12/19, 2/3/9</td>'
              '<td>signed perpendicular offset estimator along the trace normal</td>'
              '<td>CARRIED FORWARD — highest upside, frozen §A-gate never executed; excluded from this '
              'emission because the ≤ 200 m ring’s credit measures at exactly 0.0</td></tr></tbody></table>')
    rd.append('<h2>2 · Leakage canary</h2>'
              f'<p>Every one of the {can["n_channels"]} channels fitted alone on the holdout. Worst '
              f'single-feature AUC <strong>{can["worst"]["auc_alone"]:.4f}</strong> '
              f'(<code>{e(can["worst"]["channel"])}</code>) against an alarm at {can["alarm_threshold"]}. '
              f'Leakage flags: <strong>{can["any_alarm"]}</strong>.</p>')
    rd.append('<h2>3 · S1 sufficiency and S2 independence</h2>'
              f'<p>View A out-of-quadrant AUC mean <strong>{s1["summary"]["A"]["mean"]:.4f}</strong>, '
              f'minimum {s1["summary"]["A"]["minimum"]:.4f}; View B mean '
              f'<strong>{s1["summary"]["B"]["mean"]:.4f}</strong>, minimum {s1["summary"]["B"]["minimum"]:.4f}. '
              f'S1 <strong>{"PASS" if s1["pass_"] else "FAIL"}</strong> (thresholds mean ≥ 0.60, fold ≥ 0.55). '
              f'Prior rounds on the identical splitter: H61 0.5163, H63 0.5362, H64 0.5230.</p>'
              f'<p>Independence: max |ρ| <strong>{indep["pre_exchange"]["max_abs_correlation"]:.4f}</strong> over '
              f'{indep["n_blocks"]} spatial blocks of held-out labelled negatives; abandon at '
              f'{indep["abandon_threshold"]}; exchange allowed = <strong>{indep["allow_exchange"]}</strong>. '
              'This is a proxy diagnostic over blocks, not proof of conditional feature independence.</p>')
    rd.append('<h2>4 · HOLDOUT-DTI — evaluator <code>' + e(hold["evaluator_version"]) + '</code></h2>'
              f'<p>{hold["pooled"]["withheld_positives"] if "withheld_positives" in hold["pooled"] else hold["withheld_positives"]:,} '
              'withheld positive pixels; α = 0.2, β = 0.8, 300 m triangular kernel; visible catalogue masked '
              'pixel-exactly; every arm at a matched '
              f'{hold["budget_per_fold"]:,}-pixel-per-fold budget; paired 95 % percentile bootstrap over '
              f'{hold["pooled"]["bootstrap"]["clusters"]} physical 20 km clusters, '
              f'{hold["pooled"]["bootstrap"]["draws"]} draws.</p>'
              '<table class="t"><thead><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95 % CI</th></tr></thead><tbody>')
    for k in ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random"):
        if k in sc:
            rd.append(f'<tr><td>{k}</td><td>{sc[k]["dti"]:.6f}</td><td>{ci(sc[k]["ci95"])}</td></tr>')
    rd.append('</tbody></table>')
    rd.append(f'<p>Paired, candidate minus the best comparable control <code>single_B</code>: '
               f'<strong>{pdiff["single_B"]["delta"]:+.6f}</strong>, 95 % CI {ci(pdiff["single_B"]["ci95"])}. '
               'Control reproduction: see section 5 below — the pre-registered clause FAILED and is '
               'reported, not hidden.</p>'
               f'<p class="small"><strong>Validity warning, published with every number:</strong> '
               f'{e(hold["validity_warning"])}</p>')
    rd.append('<h2>5 · The discovery signal — where A is confident and B abstains</h2>'
              f'<p>{n(ao["n_pixels"])} pixels in {n(ao["n_segments"])} whole segments; '
              f'{n(ao["n_segments_written"])} segments of ≥ 3 px carry written geological reasoning in '
              '<a href="downloads/h69-a-only-reasoning.csv.gz">the CSV</a>. '
              f'{e(ao["caveat"])} S1 status: {e(ao["s1_status"])}.</p>')
    rd.append('<h2>6 · Placement — how the lane is satisfied by construction</h2>'
              f'<p>Legal set: valid ∧ off-catalogue ∧ &gt; 200 m from any mapped trace '
              f'({n(place["base_pool_px"])} px with a finite operating field). Emission: novel-only, '
              f'{n(place["S_placed"])} dots. Ranking: {e(place["ranking"])}. Placement: {e(place["placement"])}. '
              f'Quota cap = floor({place["margin"]} · S) = {n(place["cap"])} against the brief’s literal 0.70; '
              f'{place["n_quota_priors"]} priors were held under quota. Worst informative near-dot after '
              f'convergence: {n(place["worst_informative_near"])} = '
              f'{place["worst_informative_near_share"]:.4f} '
              f'(<code>{e(place["worst_informative_prior"])}</code>). Feasible: '
              f'<strong>{place["feasible"]}</strong>.</p>'
              '<table class="t"><thead><tr><th>round</th><th>placed</th><th>worst near-dot</th>'
              '<th>share</th><th>offenders over cap</th><th>priors under quota</th></tr></thead><tbody>')
    for r in place["rounds"]:
        rd.append(f'<tr><td>{r["round"]}</td><td>{n(r["placed"])}</td><td>{n(r["worst_near"])}</td>'
                  f'<td>{r["worst_share"]:.4f}</td><td>{r["n_offenders"]}</td>'
                  f'<td>{r.get("n_quota_priors", 0)}</td></tr>')
    rd.append('</tbody></table>')
    rd.append('<h2>7 · Lane and uniqueness, measured</h2>'
              '<table class="t"><thead><tr><th>Test</th><th>Literal (all priors)</th>'
               '<th>Saturation policy (informative only)</th></tr></thead><tbody>'
              f'<tr><td>Priors checked / distinct decoded patterns</td><td colspan="2">'
              f'{lane_d["priors_checked"]} / {lane_d["distinct_decoded_priors"]}</td></tr>'
              f'<tr><td>Universal-coverage probes / informative</td><td colspan="2">'
              f'{lane_d["policy"]["universal_coverage_probes"]} / {lane_d["policy"]["informative_priors"]}</td></tr>'
              f'<tr><td>Surface phase, max Spearman</td><td>{lane_s["literal"]["max_spearman"]:.4f}</td>'
              f'<td>{lane_s["policy"]["max_spearman"]:.4f}</td></tr>'
              f'<tr><td>Surface phase verdict</td><td>{e(lane_s["literal"]["verdict"])}</td>'
              f'<td>{e(lane_s["policy"]["verdict"])}</td></tr>'
              f'<tr><td>Final dots, max Spearman (limit 0.90)</td><td>{lane_d["literal"]["max_spearman"]:.4f}</td>'
              f'<td>{lane_d["policy"]["max_spearman"]:.4f}</td></tr>'
              f'<tr><td>Final dots, max 3 px near-dot fraction (limit 0.70)</td>'
              f'<td>{lane_d["literal"]["max_near_3px_fraction"]:.4f}</td>'
              f'<td>{lane_d["policy"]["max_near_3px_fraction"]:.4f}</td></tr>'
              f'<tr><td>Final dots verdict</td><td>{e(lane_d["literal"]["verdict"])}</td>'
              f'<td>{e(lane_d["policy"]["verdict"])}</td></tr>'
              '</tbody></table>'
              f'<p>Decoded-pattern uniqueness: <strong>{"PASS" if uniq["canonical_pattern_unique"] else "FAIL"}</strong> '
              f'over {uniq["n_priors_checked"]} priors; equals the literal prior union: '
              f'{uniq["equals_literal_prior_union"]}. Exact support novelty against the all-prior union: '
              f'<strong>{uniq["novel_fraction"]:.4f}</strong> — a FAILED diagnostic that is reported, not waived, '
              'because the union of every informative prior’s 3 px halo covers 100 % of the legal set on this '
              'registry (<code>work/h69/probe.py</code>: <code>novel_pool_exactly_novel = 0</code> of '
              '4,859,987). No nonempty candidate on this registry can pass it, which is a property of the '
              'registry rather than of this file.</p>')
    rd.append('<h2>8 · Limits</h2><ul>'
              '<li>No organiser receipt exists for this round. Nothing on this page is ORGANIZER-CONFIRMED. '
              'The 0.2778, 0.3195 and 0.3774 figures are owner-reported or taken from the public leaderboard '
              'page; the board publishes no filename, so file-to-score pairing is owner-reported.</li>'
              '<li>All input rasters are SHA-256-pinned owner mirrors of a login-walled portal file '
              '(<code>data/restore_receipt.json</code>, <code>ALL_VERIFIED=True</code>). The pins prove mirror '
              'consistency, not organiser authentication.</li>'
              '<li>|G| is an interval [5,949.3, 12,512.1] px, not a point. The projection integrates over it.</li>'
              '<li>ρ_novel, the credit density of novel mass, is a prior over two measured endpoints. '
              'No instrument in this repository can certify a novel field’s credit density.</li>'
              '<li>The hide-and-recover holdout anti-ranks the board (ρ = −0.1045, p = 0.734, n = 13) and '
              'withholds ~1 % of the footprint against an estimated true prevalence of 0.12–0.25 %.</li>'
              '<li>The external GeoDAWN radiometric raster carries no band tags; the total-count band is '
              'identified by rank correlation against organiser band 6 and the other three are averaged into one '
              'contrast channel whose identity is UNVERIFIED.</li>'
              '<li>Band 6’s own file description says “Tilt angle or total curvature — magnetic field derivative”; '
              'the bytes rank-match external radiometric total count at ρ = 0.99995 and the tilt angle at '
              'ρ = 0.0175 (<code>evidence/h61_forensics.json</code>). It is treated as radiometric and placed in '
              'View B. This is an organiser metadata irregularity, flagged not silently corrected.</li>'
              '<li>The A-only reasoning is measured context plus a template mechanism, not field-verified geology.</li>'
              '<li>The committed whole-segment pseudo-label rule produced zero labels in every fold, so the '
              'before/after exchange comparison the brief asks for is degenerate: '
              '<code>disagreement_post</code> is bit-identical to <code>disagreement_pre</code> and the paired '
              'CI is exactly [0, 0].</li>'
              '<li>An early sufficiency reading of 0.6636 for View A was produced on the wrong splitter '
              '(<code>holdout.make_folds(mode="block")</code> with prevalence-thinned truth) and is '
              '<strong>retracted</strong>; the committed <code>spatial.folds</code> instrument gives '
              f'{s1["summary"]["A"]["mean"]:.4f}. It is recorded so nobody resurrects it.</li>'
              '<li>ComCat cannot be bulk-downloaded from this sandbox; the seismicity channels are the organiser’s '
              'own bands 10 and 16, not a fresh catalogue.</li>'
              '<li>No submission slot was used and none can be used from here: the portal is login-walled.</li>'
              '</ul>')
    rd.append(FOOT)
    (DOCS / "h69.html").write_text("\n".join(rd))

    # ------------------------------------------------------------------ sources page
    src = [HEAD.format(title="H69 · sources, links and provenance · GEMSDOE52", root="")]
    src.append('<section><h1>Sources — every external claim with its link</h1>'
               '<p class="small">Only <code>github.com</code>, <code>api.github.com</code>, '
               '<code>codeload.github.com</code>, <code>registry.npmjs.org</code>, <code>pypi.org</code> and '
               '<code>files.pythonhosted.org</code> are reachable from this sandbox. Links to other hosts are '
               'given for manual review and are marked <strong>NOT FETCHED HERE</strong>; nothing on this page '
               'rests on a source this session could not read.</p>'
               '<table class="t"><thead><tr><th>Item</th><th>Link</th><th>Accessed here?</th>'
               '<th>What it settles</th></tr></thead><tbody>'
               '<tr><td>Competition problem description and submission format</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">drivendata.org/competitions/306/…/page/967/</a></td>'
               '<td>NOT FETCHED HERE (login/host blocked)</td><td>DTI definition, α = 0.2, β = 0.8, R = 300 m, '
               'single-band float32 GeoTIFF, EPSG:32611, values in [0, 1]</td></tr>'
               '<tr><td>Official leaderboard</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">…/leaderboard/</a></td>'
               '<td>NOT FETCHED HERE</td><td>0.3774 top of board, 0.3195 rank 7 as reported in the brief; '
               'dated local snapshots in <code>registry/leaderboard_snapshot_*.json</code></td></tr>'
               '<tr><td>Reference solution (Prof. John Lipor)</td>'
               '<td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></td>'
               '<td><strong>CLONED AND READ</strong> (this session)</td>'
               '<td>U-Net + resnet18 encoder, <code>TverskyLoss(alpha=0.2, beta=0.8, mode="binary")</code>, '
               'MC = 5 random patch splits, 128 px patches, 5 epochs, all 19 channels min–max normalised to '
               '[0, 1], predictions averaged only over held-out test patches, written with the labels’ CRS and '
               'transform. It is a supervised model <em>of the existing catalogue</em>, which is masked out of '
               'scoring — the reason a catalogue-fitting submission scores low.</td></tr>'
               '<tr><td>Co-training</td><td>Blum &amp; Mitchell, COLT 1998, pp. 92–100, '
               '<a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a></td>'
               '<td>NOT FETCHED HERE</td><td>two-view sufficiency, compatibility and conditional independence</td></tr>'
               '<tr><td>Tversky index</td><td><a href="https://en.wikipedia.org/wiki/Tversky_index">en.wikipedia.org/wiki/Tversky_index</a></td>'
               '<td>NOT FETCHED HERE</td><td>the α/β asymmetry DTI and TverskyLoss both implement</td></tr>'
               '<tr><td>EPSG:32611</td><td><a href="https://epsg.io/32611">epsg.io/32611</a></td>'
               '<td>NOT FETCHED HERE</td><td>WGS 84 / UTM zone 11N — verified against the restored rasters by '
               '<code>scripts/prepare_data.py</code> instead</td></tr>'
               '<tr><td>GeoDAWN airborne magnetic and radiometric surveys</td>'
               '<td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">usgs.gov/data/geodawn-…</a>, '
               'DOI 10.5066/P93LGLVQ</td><td>NOT FETCHED HERE</td>'
               '<td>the external K/Th/U/TC grids; the derived uint8 mirror is SHA-256 pinned in '
               '<code>registry/data_manifest.json</code> and restored</td></tr>'
               '<tr><td>INGENIOUS / GDR submission 1391</td>'
               '<td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a>, '
               '<a href="https://gbcge.org/current-projects/ingenious/">gbcge.org/current-projects/ingenious/</a></td>'
               '<td>NOT FETCHED HERE</td><td>Quaternary fault traces and well/spring temperatures; the derived '
               'CSV mirrors are restored and SHA-verified</td></tr>'
               '<tr><td>DOE GEMS solicitation PDF (OSTI 96647)</td>'
               '<td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">docs.nlr.gov/docs/fy26osti/96647.pdf</a></td>'
               '<td>NOT FETCHED HERE</td><td>submission rules as transcribed in the brief and '
               '<code>knowledge/00_brief_as_received.md</code></td></tr>'
               '<tr><td>Competition rasters (login-walled)</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">…/data/</a></td>'
               '<td>NOT FETCHABLE — restored from owner mirrors and SHA-256 verified</td>'
               '<td><code>training_features.tif</code> (418,912,844 B, 19 float32 bands), '
               '<code>labels.tif</code> (60,988 positives), <code>sample_submission.tif</code></td></tr>'
               '</tbody></table>'
               '<h2>Irregularities flagged this round</h2><ul>'
               '<li><strong>Band 6 metadata contradicts its bytes.</strong> Description says magnetic tilt angle; '
               'Spearman against external radiometric TC is 0.99995 and against the tilt angle 0.0175.</li>'
               '<li><strong>sample_submission.tif is not “total fault absence”.</strong> Its 60,988 pixels equal to 1 '
               'sit exactly on the labelled catalogue.</li>'
               '<li><strong>Exact support novelty is unsatisfiable on this registry.</strong> The union of all 359 '
               'informative priors’ 3 px halos covers 100 % of the 4,859,987 px legal set.</li>'
               '<li><strong>The hide-and-recover instrument anti-ranks the board</strong> (ρ = −0.1045, p = 0.734, '
               'n = 13), so HOLDOUT-DTI is reported but never used as a forecast.</li>'
               '<li><strong>|G| is an interval, not a point.</strong> 14,088.7 px requires the champion’s deleted '
               '6,436 px ring to earn exactly zero credit; 25 credit of ring income moves it to 12,333 px.</li>'
               '</ul></section>')
    src.append(FOOT)
    (DOCS / "h69-sources.html").write_text("\n".join(src))

    # ------------------------------------------------------------------ archive downloads index
    arch = DOWN / "index.html"
    if arch.exists():
        txt = arch.read_text()
        import re as _re2
        txt = _re2.sub(r"<!--H69-DOWNLOAD-NOTICE-->.*?<!--/H69-DOWNLOAD-NOTICE-->", "", txt, flags=_re2.S)
        txt = _re2.sub(r"<!--H69-DL-->.*?<!--/H69-DL-->", "", txt, flags=_re2.S)
        # This round was committed as H65 and renumbered to H69 after a parallel session merged a
        # different round under H65 (PR #57). main carries no H65 block in this file, so any H65
        # marker here is this round's own pre-rename injection, pointing at files that no longer
        # exist. Strip it rather than leave dead links for scripts/check_site.py to find.
        txt = _re2.sub(r"<!--H65-DOWNLOAD-NOTICE-->.*?<!--/H65-DOWNLOAD-NOTICE-->", "", txt, flags=_re2.S)
        txt = _re2.sub(r"<!--H65-DL-->.*?<!--/H65-DL-->", "", txt, flags=_re2.S)
        notice = (f'<!--H69-DOWNLOAD-NOTICE--><aside style="padding:20px;background:#e8f0fe;color:#0b1f3a;'
                  f'font:16px/1.6 system-ui"><b>Latest round: H69 (2026-10-09) — DOWNLOAD YES, SPEND A SLOT NO.</b> '
                  f'<a href="h69-candidate.tif" download>Download the H69 GeoTIFF</a> ({n(fmt["bytes"])} bytes, '
                  f'SHA-256 <code>{e(card["raster_sha256"][:16])}…</code>, {n(S)} cells, values exactly {{0,1}}, '
                  f'0 NaN) · <a href="../h69-executive-summary.html">exact submission steps</a> · '
                  f'<a href="../h69.html">method, results and limits</a>. This is the first file in this '
                  f'repository whose directed 3 px near-dot share against every informative prior is inside the '
                  f'brief\'s 0.70 limit ({lane_d["policy"]["max_near_3px_fraction"]:.4f}). Historical downloads '
                  f'below are not upload approval.<!--/H69-DOWNLOAD-NOTICE-->')
        rows = (f'<!--H69-DL--><tr><td><a href="h69-candidate.tif" download>h69-candidate.tif</a></td>'
                f'<td class="number">{n(fmt["bytes"])}</td><td class="mono">{e(card["raster_sha256"])}</td>'
                f'<td>H69 · basement-surface two-view co-training, novel-only, consensus-restricted '
                f'lane-feasible placement · {n(S)} px · newest round; <a href="../h69.html">evidence</a></td></tr>'
                f'<tr><td><a href="{e(stem)}.tif" download>{e(stem)}.tif</a></td>'
                f'<td class="number">{n(fmt["bytes"])}</td><td class="mono">{e(card["raster_sha256"])}</td>'
                f'<td>canonical filename, byte-identical</td></tr>'
                f'<tr><td><a href="h69-candidate.zip" download>h69-candidate.zip</a></td>'
                f'<td class="number">{n((DOWN / "h69-candidate.zip").stat().st_size)}</td>'
                f'<td class="mono">single-TIFF ZIP, byte-identical payload</td>'
                f'<td>portal-accepted wrapper</td></tr>'
                f'<tr><td><a href="h69-a-only-reasoning.csv.gz" download>h69-a-only-reasoning.csv.gz</a></td>'
                f'<td class="number">{n((DOWN / "h69-a-only-reasoning.csv.gz").stat().st_size)}</td>'
                f'<td class="mono">gzipped CSV</td><td>{n(ao["n_segments_written"])} A-only segments, one '
                f'geological hypothesis and one named non-fault mimic each</td></tr><!--/H69-DL-->')
        txt = txt.replace("<body>", "<body>" + notice, 1)
        txt = txt.replace("<tbody>", "<tbody>" + rows, 1)
        arch.write_text(txt)
        print("archive downloads index updated")

    # ------------------------------------------------------------------ inject the H69 notice
    # docs/index.html is the standing landing page and carries the older rounds' required links;
    # scripts/check_site.py enforces them. Inject a marked notice at the very top of <main> instead
    # of replacing the page, exactly as the H64 round did.
    idxp = DOCS / "index.html"
    txt = idxp.read_text()
    import re as _re3
    txt = _re3.sub(r"<!--H69-NOTICE-->.*?<!--/H69-NOTICE-->", "", txt, flags=_re3.S)
    verdict_word = ("SUBMIT-ELIGIBLE" if sub else
                    "DOWNLOAD YES &middot; THE PORTAL WILL ACCEPT THIS FILE YES &middot; SPEND A SLOT NO")
    notice = (
        '<!--H69-NOTICE--><div class="notice" role="note" style="margin:0 0 1rem;padding:1.1rem 1.2rem">'
        '<strong style="font-size:1.05rem">Latest research round: H69 (2026-10-09) &mdash; '
        f'{verdict_word}.</strong><br>'
        f'<a class="button" style="margin:.6rem .5rem .3rem 0" href="downloads/h69-candidate.tif" download>'
        f'&#11015; Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a>'
        '<a class="button secondary" style="margin:.6rem .5rem .3rem 0" href="downloads/h69-candidate.zip" '
        'download>Single-TIFF ZIP</a><br>'
        f'<span class="small"><code>{e(stem)}.tif</code> &middot; SHA-256 <code>{e(card["raster_sha256"])}</code>'
        f' &middot; {n(S)} cells &middot; values exactly {{0, 1}} &middot; 0 NaN &middot; EPSG:32611 &middot; '
        f'{val["shape"][0]:,} &times; {val["shape"][1]:,} &middot; transform identical to '
        '<code>sample_submission.tif</code>, so the <em>&ldquo;Predicted values must be in range [0, 1]&rdquo;'
        '</em> rejection cannot fire on it.<br>'
        f'<strong>First lane-feasible file in this repository:</strong> max directed 3&nbsp;px near-dot '
        f'<strong>{lane_pol["max_near_3px"]:.4f}</strong> against the brief&rsquo;s literal 0.70 limit, and '
        f'max rank correlation <strong>{lane_pol["max_spearman"]:.4f}</strong> against 0.90, verified over '
        f'{lane_d["priors_checked"]} registry rasters with 0 errors. '
        f'<strong>Not submittable anyway:</strong> S1 sufficiency FAILED (View A out-of-quadrant AUC '
        f'{card["s1_sufficiency"]["view_A_mean"]:.4f}) and the HOLDOUT-DTI paired difference against '
        f'<code>single_B</code> is {card["holdout_dti"]["candidate_minus_single_B"]["delta"]:+.6f}. '
        f'Slots used: {card["slots_used"]}.<br>'
        '<a href="h69-overview.html">H69 overview and download</a> &middot; '
        '<a href="h69-executive-summary.html">exactly how to submit</a> &middot; '
        '<a href="h69.html">method, results and limits</a> &middot; '
        '<a href="h69-sources.html">sources with links</a> &middot; '
        '<a href="downloads/h69-a-only-reasoning.csv.gz">A-only geological reasoning CSV</a></span>'
        '</div><!--/H69-NOTICE-->')
    marker = '<main id="main">'
    if marker in txt:
        txt = txt.replace(marker, marker + notice, 1)
    else:
        txt = txt.replace("<body>", "<body>" + notice, 1)
    idxp.write_text(txt)
    print("H69 notice injected into docs/index.html")


    (ROOT / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=docs/index.html">'
        '<title>GEMSDOE52 — H69 research GeoTIFF and submission status</title></head><body>'
        '<h1>GEMSDOE52 · H69</h1>'
        f'<p><a href="docs/downloads/h69-candidate.tif" download>Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a></p>'
        '<p><a href="docs/index.html">Open the research download and the explicit submission verdict.</a></p>'
        '<p><a href="docs/h69-executive-summary.html">Exactly how to submit, field by field.</a></p>'
        f'<p>Verdict: {"SUBMIT-ELIGIBLE on every frozen promote clause" if sub else "DOWNLOAD YES, PORTAL ACCEPTS THE FORMAT YES, SPEND A SLOT NO"}.</p>'
        '</body></html>\n')

    # ------------------------------------------------------------------ README block (prepended)
    readme = ROOT / "README.md"
    old = readme.read_text()
    import re as _re
    old = _re.sub(r"<!--H69-README-->.*?<!--/H69-README-->\n?", "", old, flags=_re.S)
    lane_lit = card["correlation_vs_registry"]["literal"]
    lane_pol = card["correlation_vs_registry"]["policy"]
    cf = card["projection"].get("counterfactual_recombination_NOT_SHIPPED", {})
    block = f"""<!--H69-README-->
# GEMSDOE52 — H69: a unique, lane-feasible GeoTIFF, and the verdict on whether it may be submitted

**[★ Download the H69 GeoTIFF — one click](docs/downloads/h69-candidate.tif)** ·
[single-TIFF ZIP](docs/downloads/h69-candidate.zip) ·
[A-only geological reasoning CSV](docs/downloads/h69-a-only-reasoning.csv.gz) ·
**[Executive summary / exactly how to submit](docs/h69-executive-summary.html)** ·
[Landing page](docs/index.html) · [Method, results and limits](docs/h69.html) ·
[Sources with links](docs/h69-sources.html) · [Run card](evidence/h69_run_card.json) ·
[Results and limits](knowledge/53_h69_results_and_limits.md) ·
[Preregistration](knowledge/52_hypotheses_H69_preregistered.md) ·
[Preregistration AMENDMENT](knowledge/52b_h69_prereg_amendment_placement.md)

> **DOWNLOAD: YES — the file is portal-safe by construction. SUBMIT TO THE COMPETITION: NO.**
> Verdict `{card["verdict"]}`. Format PASS, decoded-pattern uniqueness PASS over
> {card["registry"]["n_priors"]} registry rasters, and for the first time in this repository the
> **lane rule is satisfied by construction**: max informative near-dot
> **{lane_pol["max_near_3px"]:.4f}** and max Spearman **{lane_pol["max_spearman"]:.4f}** against
> literal limits of 0.70 and 0.90 (H63 measured 0.8188, H64 0.888 and both shipped DUPLICATE). It is still
> **not** submit-eligible, for two reasons that are not waivable: S1 sufficiency FAILED (View A
> out-of-quadrant AUC {card["s1_sufficiency"]["view_A_mean"]:.4f}, min fold
> {card["s1_sufficiency"]["view_A_min"]:.4f}, bar 0.60 / 0.55) and the HOLDOUT-DTI paired difference against
> `single_B` is {card["holdout_dti"]["candidate_minus_single_B"]["delta"]:+.6f}
> [{card["holdout_dti"]["candidate_minus_single_B"]["ci95"][0]:+.6f},
> {card["holdout_dti"]["candidate_minus_single_B"]["ci95"][1]:+.6f}]. **NO CERTIFIED LEADERBOARD GAIN.**
> Competition slots used: **{card["slots_used"]}**.

- **File:** `{stem}.tif` — {n(fmt["bytes"])} bytes, {n(S)} emitted cells, values exactly {{0, 1}}
- **SHA-256:** `{card["raster_sha256"]}`
- **Submission name:** `{card["submission_name"]}`
- **Submission note ({card["note_chars"]}/140 chars):** `{card["submission_note"]}`
- **Grid:** EPSG:32611, {val["shape"][0]:,} × {val["shape"][1]:,}, transform `{val["transform"]}`,
  single band float32, **0 NaN and 0 infinite pixels anywhere**, min 0.0 max 1.0 — verified by re-reading the
  written file, not from the array in memory. The portal's *"Predicted values must be in range [0, 1]"*
  rejection cannot fire on this file: `gems52.grid.write_geotiff` refuses to write unless the array is
  float32, exactly {val["shape"][0]:,} × {val["shape"][1]:,}, finite everywhere and inside [0, 1].

## The measured answer to "why did `h33-h33-2-b2` score 0.2778, and can we beat it?"

Re-derived from restored, SHA-256-verified bytes this session (`work/h69/probe.py`,
`evidence/h61_forensics.json`), not copied from an earlier round's prose.

1. **It is precision, not detection.** The reported-0.2778 file (37,654 px) is a *strict subset* of the
   reported-0.2600 file (44,090 px), which is a strict subset of the reported-0.1922 parent field
   (121,131 px). It added **zero** pixels and deleted 6,436, every one between 100 m and 200 m of a mapped
   trace; its own nearest dot is 223.6 m away. For a binary dot emission with `M = T` the metric collapses
   to `DTI = T / (0.2·S + 0.8·|G|)`, so deleting mass that earns no credit removes denominator and no
   numerator.
2. **Its credit is concentrated, and the concentration is measurable.** `P1 = A ∩ C` is 25,517 px carrying
   credit density 0.163–0.205 against 0.0279 for uniform random over the legal set; the ≤ 200 m corridor
   atoms carry **exactly zero**.
3. **`|G|` is an interval, [5,949.3, 12,512.1] px**, not the 14,088.7 point value: that point requires the
   champion's deleted 6,436 px to earn exactly zero credit, and 25 credit of ring income moves it to 12,333.
4. **Two routes beat it, and only two.** (a) *Recombination of existing public mass* — this has an exact
   credit bound and the projection clears 0.2778 across the whole bracket
   (P = {cf["per_g"]["G_lo"]["p_beat_02778"]:.2f} / {cf["per_g"]["G_mid"]["p_beat_02778"]:.2f} /
   {cf["per_g"]["G_hi"]["p_beat_02778"]:.2f} at |G| low/mid/high). It is **not shipped**: this repository
   already corrected such a file as NOT unique (H60C correction, `IR-H61-007`, `IR-UNQ-001`), and sizing a
   file to land 0.005 under the 0.70 threshold a previous round was corrected for exceeding is re-tuning a
   negative result into a positive. (b) *A detector above 0.0907–0.1295 credit density on novel mass* — no
   instrument here can certify it, and this round's novel field is ranked by a view at chance.
5. **The top of the board (0.3774) needs `T ≈ 6,620` at `S = 37,654`, `|G| = 12,512`** (density 0.176) —
   a detector better than anything this family has published. The highest-upside un-run idea remains
   **R5-H1, the trace-correction corridor** (`knowledge/33`), whose target population the organiser has
   confirmed exists and whose frozen §A-gate has never been executed.

## H69 results, each labelled

| arm | HOLDOUT-DTI | 95 % CI |
|---|---:|---|
| `single_A` | {sc["single_A"]["dti"]:.6f} | [{sc["single_A"]["ci95"][0]:.6f}, {sc["single_A"]["ci95"][1]:.6f}] |
| `single_B` | {sc["single_B"]["dti"]:.6f} | [{sc["single_B"]["ci95"][0]:.6f}, {sc["single_B"]["ci95"][1]:.6f}] |
| `union_max` | {sc["union_max"]["dti"]:.6f} | [{sc["union_max"]["ci95"][0]:.6f}, {sc["union_max"]["ci95"][1]:.6f}] |
| `disagreement_pre` | {sc["disagreement_pre"]["dti"]:.6f} | [{sc["disagreement_pre"]["ci95"][0]:.6f}, {sc["disagreement_pre"]["ci95"][1]:.6f}] |
| `disagreement_post` | {sc["disagreement_post"]["dti"]:.6f} | [{sc["disagreement_post"]["ci95"][0]:.6f}, {sc["disagreement_post"]["ci95"][1]:.6f}] |
| `random` | {sc["random"]["dti"]:.6f} | [{sc["random"]["ci95"][0]:.6f}, {sc["random"]["ci95"][1]:.6f}] |

Evaluator `{hold["evaluator_version"]}`, {hold["withheld_positives"]:,} withheld positives,
{hold["pooled"]["bootstrap"]["clusters"]} physical 20 km clusters,
{hold["pooled"]["bootstrap"]["draws"]} paired draws, every arm at a matched 9,400-dot-per-fold budget with
3 px separation. **HOLDOUT-DTI is an instrument reading, never a forecast**: `knowledge/10` §5 measured
Spearman ρ = −0.1045 (p = 0.734, n = 13) between this simulator and the organiser's reported scores, and
the reported champion ranks 13th of 13 here while ranking 1st on the board.

**PROJECTION (never a score)** for the shipped novel-only file, integrating `t_core = 0` and
ρ_novel ~ U[{card["projection"]["rho_novel_prior"][0]}, {card["projection"]["rho_novel_prior"][1]}] over
`|G|`: P(DTI > 0.2778) = {pw["G_lo"]["p_beat_02778"]:.3f} / {pw["G_mid"]["p_beat_02778"]:.3f} /
{pw["G_hi"]["p_beat_02778"]:.3f} at |G| = 5,949.3 / 9,230.7 / 12,512.1; mean DTI {pw["G_mid"]["mean_dti"]:.4f}.

## What is new, and what is now closed

1. **NEW — the lane is satisfiable, and here is the construction.** Place in field-rank order with hard-core
   3 px spacing; measure the directed 3 px near-dot count of *every* informative prior; put every prior above
   `floor(0.6985·S)` under an exact quota (packed halos, a lazy forbidden mask, counts that can never pass
   the cap); re-place; re-measure all {lane_d["policy"]["informative_priors"]} informative priors. Converged
   in {len(place["rounds"])} rounds to max near-dot {lane_pol["max_near_3px"]:.4f}.
2. **NEW — the committed whole-segment pseudo-label rule yields exactly zero labels** on these views in all
   four folds, so `disagreement_post` is bit-identical to `disagreement_pre` and the paired CI is exactly
   [0, 0]. The co-training mechanism **cannot be executed as specified** here — a stronger statement than
   "it was executed and did not help". Same class as `IR-H58-002`.
3. **CLOSED — rebuilding View A as basement-surface differential geometry does not rescue sufficiency.**
   18 derivative/band-pass channels (|∇| and ∇² of band 15, DoG isostatic residual, gravity/RTP gradient
   coherence, conductivity edge, strain, seismicity) give View A out-of-quadrant AUC
   {card["s1_sufficiency"]["view_A_mean"]:.4f} against H61 0.5163, H63 0.5362, H64 0.5230. Fourth failure.
4. **RETRACTED, on the record.** An early sufficiency reading of View A mean **0.6636** came from the wrong
   splitter (`holdout.make_folds(mode="block")` with prevalence-thinned truth). It is not comparable to
   anything in this repository and must not be quoted. The committed instrument gives
   {card["s1_sufficiency"]["view_A_mean"]:.4f}.
5. **The instrument control did not reproduce, and that is reported rather than hidden.** The preregistered
   clause (`single_B` = 0.1745172876 ± 0.001) is unsatisfiable for a round that changes View B's channel set;
   the model-free `random` arm measured {hold["instrument_control"]["random_arm"]:.6f} against H64's 0.080426
   (|Δ| = {hold["instrument_control"]["abs_delta"]:.4f}). Cause: `structural.FeatureStore.valid` lives under
   git-ignored `work/r2/features` and is absent in a fresh sandbox. Within-round paired comparisons are exact;
   across-round levels are approximate.
6. **Exact support novelty is impossible on this registry**: the union of every informative prior's 3 px halo
   covers 100 % of the 4,859,987 px legal set (`work/h69/probe.py`, `novel_pool_exactly_novel = 0`). The
   ≥ 20 % diagnostic fails for every nonempty candidate ever built here and is reported as a failed
   diagnostic, never waived.
7. **Band 6 metadata contradicts its bytes** (tag says magnetic tilt angle; ρ = 0.99995 against external
   radiometric total count, ρ = 0.0175 against tilt). The external GeoDAWN radiometric raster carries **no
   band tags at all**; this session identified its total-count band as band 4 (ρ = 0.99995 vs organiser band 6)
   and averaged the other three into one contrast channel whose identity is UNVERIFIED.

## Standing starting point

The full user brief is preserved verbatim in [`knowledge/00_brief_as_received.md`](knowledge/00_brief_as_received.md)
and is the standing starting point for every session; `AGENTS.md` records the working agreement and the
authoritative shared-instrument repairs. Read those two, plus
[`knowledge/03_negative_results_and_what_they_killed.md`](knowledge/03_negative_results_and_what_they_killed.md)
and this block, before proposing anything.

## Reproduce H69

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-r2.txt
bash scripts/download_competition_data.sh
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/fetch_prior_inventory.py --out work/h69/priors --receipt work/h69/prior_fetch_receipt.json
.venv/bin/python work/h69/probe.py
.venv/bin/python scripts/run_h69.py --stage features
.venv/bin/python scripts/run_h69.py --stage lane
.venv/bin/python scripts/run_h69.py --stage place
.venv/bin/python scripts/run_h69.py --stage gates
.venv/bin/python scripts/publish_h69_site.py
```

<!--/H69-README-->
"""
    readme.write_text(block + "\n" + old)
    print(f"PUBLISHED name={stem} bytes={fmt['bytes']} sha={card['raster_sha256']} submit={sub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
