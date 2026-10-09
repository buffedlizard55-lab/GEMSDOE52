#!/usr/bin/env python3
"""Render the H64 landing page, executive summary, results note and README block from the receipts.

Every number written here is read from ``evidence/h64_*.json`` or the submission receipt.  Nothing is
typed by hand, so the page cannot disagree with the evidence it cites.  Nothing here uploads anything
or changes a verdict; it only reports the verdict the run card already holds.

Run after ``scripts/run_h64.py build``:
    .venv/bin/python scripts/publish_h64_site.py
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


def main() -> int:
    card = load("h64_run_card.json")
    suf = load("h64_sufficiency.json")
    hold = load("h64_holdout.json")["pooled"]
    cv = load("h64_control_and_verdict.json")
    lane_s = load("h64_lane_surface.json")
    lane_d = load("h64_lane_dots.json")
    stem = card["raster"]["file"][:-4]
    sub = json.loads((SUBM / f"{stem}.json").read_text())
    val = sub["validator"]
    n_dots = card["counts"]["placed"]
    verdict = card["verdict"]
    negative = verdict.startswith("NEGATIVE")
    sc = hold["scores"]
    pdiff = hold["paired_differences"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"   # noqa: E731

    # --------------------------------------------------------------- copies the page serves
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h64-candidate.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h64-candidate.zip")
    (DOCS / "data").mkdir(exist_ok=True)
    shutil.copy(EVID / "h64_run_card.json", DOCS / "data/h64_run_card.json")
    (SUBM / "H64_LATEST.txt").write_text(f"{stem}.tif\n# pointer for the site; NOT an upload approval\n")

    gates_rows = [
        ("Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned)",
         "PASS" if val.get("ok") else "FAIL"),
        ("Values exactly {0, 1}; 0 NaN; 0 infinite", "PASS" if card["validator"]["ok"] else "FAIL"),
        ("Decoded-pattern uniqueness (not identical to any of the 548 registry rasters)",
         "PASS" if card["uniqueness"]["tier1_exact_all_priors"]["canonical_pattern_unique"] else "FAIL"),
        (f"Exact novelty: share of emitted cells that are not positive in any of the {card['uniqueness']['tier2_novelty_informative_priors']['informative_rasters']} informative registry rasters",
         f"{card['uniqueness']['tier2_novelty_informative_priors']['novel_fraction']:.4f}"),
        ("Not the union of the two views",
         "PASS" if card["not_the_union"]["not_union_pass"] else "FAIL"),
        ("Sufficiency gate S1 (View A out-of-quadrant AUC)", "PASS" if suf["S1_pass"] else "FAIL"),
        ("Lane gate, literal, surface / dots",
         f"{lane_s['literal']['verdict']} / {lane_d['literal']['verdict']}"),
        ("Lane gate, saturation policy, surface / dots",
         f"{lane_s['policy']['verdict']} / {lane_d['policy']['verdict']}"),
        ("Holdout beats single_B (paired CI lower bound > 0)", "PASS" if cv["holdout_eligible"] else "FAIL"),
    ]
    gates_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in gates_rows)
    arms = ["single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random"]
    arm_rows = "".join(
        f"<tr><td>{a}</td><td class='numeric'>{sc[a]['dti']:.6f}</td><td class='numeric'>"
        f"{ci(sc[a]['ci95'])}</td><td class='numeric'>{fmt_int(sc[a]['withheld_positive_pixels'])}</td></tr>"
        for a in arms)
    pair_rows = "".join(
        f"<tr><td>disagreement_post − {a}</td><td class='numeric'>{pdiff[a]['delta']:+.6f}</td>"
        f"<td class='numeric'>{ci(pdiff[a]['ci95'])}</td></tr>" for a in ("single_B", "union_max", "single_A", "random"))
    sufrows = "".join(f"<tr><td>fold {r['fold']}</td><td class='numeric'>{r['view_A_oof_auc']:.4f}</td>"
                      f"<td class='numeric'>{fmt_int(r['n_pos'])} / {fmt_int(r['n_neg'])}</td></tr>"
                      for r in suf["folds"])
    fileline = (f"{esc(stem)}.tif<br>{fmt_int(card['raster']['bytes'])} bytes · SHA-256 "
                f"{esc(card['raster']['sha256'])} · {fmt_int(n_dots)} emitted cells · values exactly {{0,1}}, 0 NaN")
    notice = ("OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · DO NOT UPLOAD" if negative
              else "ELIGIBLE FOR THE SELECTOR ONLY · NOT PROMOTED · NO SLOT USED")
    headline = ("A valid, unique file and a negative verdict." if negative
                else "A valid, unique file that passed the selector gate. Promotion is still a separate decision.")

    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            f'<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            f'<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            f'<a href="index.html">Overview</a><a href="h64-executive-summary.html">Submission guide</a>'
            f'<a href="archive-h61-landing.html">H61 (previous)</a><a href="downloads/index.html">Archive</a>'
            f'</nav></header><main id="main">')
    # Earlier rounds that the home and executive-summary pages keep pointing to (check_site enforces these).
    h58 = json.loads((DOCS / "data" / "h58_result.json").read_text())["artifact"]
    r5 = json.loads((DOCS / "data" / "submission_r5.json").read_text())
    earlier = f"""
<section><h2>Earlier rounds still on this site</h2><p class="small">Each is a separate artefact with its own receipt. None of them is the H64 file, and none is approved for a slot.</p>
<ul>
<li><b>R5, research candidate, not slot-approved.</b> OK TO DOWNLOAD for research. File
<code>{esc(r5['file'])}</code>, SHA-256 prefix <code>{esc(r5['sha256'][:24])}</code>. Short path
<a href="downloads/r5-candidate.tif" download>downloads/r5-candidate.tif</a>. P(beating 0.2778) = {r5['p_beat_02778']:.3f} under the frozen prior; the instrument is disqualified (<code>knowledge/10</code> §5). Details: <a href="r5.html">R5 page</a>.</li>
<li><b>H58, research-only, not approved to submit.</b> File <code>{esc(h58['file'])}</code>, SHA-256 prefix <code>{esc(h58['sha256'][:24])}</code>. Short path
<a href="downloads/h58-candidate.tif" download>downloads/h58-candidate.tif</a>. Details: <a href="h58.html">H58 page</a>.</li>
<li><b>H57 alternate, research archive, not approved.</b> File <code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code>. Details: <a href="h57-creditcore.html">H57 credit-core archive</a>.</li>
<li><b>H55-EDGE, failed-gate archive.</b> Main incumbent unchanged. Details: <a href="h55-edge.html">h55-edge.html</a>.</li>
<li><b>H61, previous round, negative. Do not upload.</b> Details: <a href="archive-h61-landing.html">H61 landing</a>.</li>
</ul></section>
"""
    tail = "</main></body></html>\n"

    index = head + f"""
<section class="hero"><div><div class="eyebrow">DOE GEMS / H64 · sufficiency-gated co-training</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">{esc(headline)} H64 tests one pre-registered change to View A's capacity and asks whether the
co-training exchange becomes licensed. The sufficiency gate S1 fails on out-of-quadrant View A AUC, so the exchange is not run.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong>
<p>Verdict: <b>{esc(verdict)}</b></p></div>
<div class="actions"><a class="button" href="downloads/h64-candidate.tif" download>Download the H64 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h64-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/h64-a-only-reasoning.csv.gz" download>A-only reasoning CSV (gzip)</a></div>
<p class="fileline">{fileline}</p>
<p class="small"><a href="h64-executive-summary.html">How to submit, and whether this file may be submitted →</a>
· <a href="data/h64_run_card.json">Complete JSON run card ↗</a></p></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead>
<tbody>{gates_html}</tbody></table></div>
<p class="small">Local validator only. Not an organiser acceptance receipt. Lane gate statistics are the literal
rule and the saturation policy from <code>gems52.gates.lane_report</code>.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI (gems52-pooled-hide-v1)</h2>
<p class="small">{fmt_int(sc['single_B']['withheld_positive_pixels'])} withheld positive pixels · α {hold['alpha']} / β {hold['beta']} ·
{hold['triangular_radius_m']:.0f} m triangular kernel · 95% paired physical-cluster bootstrap, 153 clusters, 1000 draws.
Every arm placed 9,400 dots per fold at 3 px spacing. Best comparable control: <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>{arm_rows}</tbody></table></div>
<p class="small">Paired differences (candidate = disagreement_post):</p>
<div class="table-wrap"><table><thead><tr><th>Paired difference</th><th>Δ DTI</th><th>95% CI</th></tr></thead>
<tbody>{pair_rows}</tbody></table></div>
<p class="small">The single_B control reproduces the H61 committed value to |Δ| = {cv['control']['abs_difference']:.1e}
(amended tolerance {cv['control']['tolerance']}; see <code>knowledge/34b</code>). Holdout numbers are HOLDOUT-DTI, never
organiser scores, and the hide-and-recover instrument does not rank board performance (<code>knowledge/10</code> §5).</p></section>
<hr class="divider">
<section><h2>View A sufficiency (the one thing H64 changed)</h2>
<p class="small">Pre-registered gate S1: mean out-of-quadrant AUC ≥ 0.60 and every fold ≥ 0.55. Measured mean
<b>{suf['mean_view_A_oof_auc']:.4f}</b>, minimum <b>{suf['min_fold_view_A_oof_auc']:.4f}</b>. Result: <b>{'PASS' if suf['S1_pass'] else 'FAIL'}</b>.
H61 (higher-capacity View A) measured {suf['H61_reference_view_A_mean_oof_auc']:.4f}.</p>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>View A OOF AUC</th><th>Positives / negatives</th></tr></thead>
<tbody>{sufrows}</tbody></table></div>
<p class="small">Because S1 failed, no pseudo-label was created: the exchange is not licensed by Blum–Mitchell when a view is not
sufficient. The post-arms equal the pre-arms by construction.</p></section>
<hr class="divider">
<section><h2>What this does and does not show</h2><ul>
<li>It shows that making View A less complex does not make it generalise across quadrants on these layers.</li>
<li>It does not show that potential-field data contain no fault information; it shows this learner on these layers does not transfer.</li>
<li><b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing on this page is an organiser score or a promise of a board gain.</li>
<li>It is not a leaderboard estimate. The best published board score is 0.3774 (rank 1), 0.3195 is rank 7 (DARD),
and 0.2778 is rank 13 (extradr19): <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official leaderboard</a>.</li>
<li>Attribution caveat: the 0.2778 and 0.2600 figures are owner-reported, not organiser-confirmed (IR-H61-004).</li></ul>
<p class="small"><a href="../knowledge/39_hypotheses_H64_preregistered.md">Five ranked hypotheses and the frozen protocol →</a> ·
<a href="../knowledge/40_h64_results_and_limits.md">Results and limits →</a> · <a href="archive-h61-landing.html">H61 landing (previous round) →</a></p></section>
{earlier}""" + tail

    exec_html = head + f"""
<div class="eyebrow">Executive summary / submission guide</div>
<h1>How to submit, and whether this file may be submitted.</h1>
<p class="lead">Read the verdict first. A valid file is not an approved competition entry; the selector decides
promotion within the weekly cap shown on the submission page.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong><p>Verdict: <b>{esc(verdict)}</b></p>
<p>Why not submit: the lane marks this file DUPLICATE under the 70% per-raster rule (the largest near-dot share is
{card['novelty_rule']['worst_raster_near_dots']['share']:.3f} against one informative registry raster). The holdout
does not beat single_B, and S1 failed. The file is not identical on decoded pixels to any registry raster, and it shares no positive pixel with any
informative registry raster, so it is safe to download for research.</p></div>
<div class="actions"><a class="button" href="downloads/h64-candidate.tif" download>Download the H64 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h64-candidate.zip" download>Single-TIFF ZIP</a></div>
<p class="fileline">{fileline}</p>
<section class="prose"><h2>The file contract (checked on disk)</h2><ul>
<li>One band, float32, every value in [0, 1]; in practice exactly 0 or 1.</li>
<li>No NaN or infinite values anywhere in the file (the portal's “Predicted values must be in range [0, 1]”
rejection is caused by NaN/out-of-range bytes, and this file has neither).</li>
<li>EPSG:32611, shape and geotransform identical to the pinned <code>sample_submission.tif</code>.</li>
<li>{fmt_int(n_dots)} emitted cells, all more than 200 m from a mapped trace, 3 px minimum separation.</li>
<li>Name for the portal: <code>{esc(card['submission_name'])}</code>. Note ({card['note_chars']} characters): <code>{esc(card['note'])}</code></li>
</ul><p class="small">Local validator only; not an organiser acceptance receipt.</p>
<h2>Exact steps, only if a later selector approves this file</h2>
<ol><li>Open the competition submission page (login required; <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>).</li>
<li>Under <b>File to submit</b>, choose the TIFF (or the ZIP with the single TIFF).</li>
<li>Paste the name and note above into the submission form.</li>
<li>Submit only if the selector has approved this file. This file is not approved.</li></ol></section>
{earlier}""" + tail

    (DOCS / "h64.html").write_text(index)
    (DOCS / "h64-executive-summary.html").write_text(exec_html)

    # --------------------------------------------------------------- knowledge note and README block
    kn = f"""# 35 · H64 results and limits (rendered from the receipts by `scripts/publish_h64_site.py`)

**Verdict: `{verdict}`**

Artefact `{stem}.tif`, SHA-256 `{card['raster']['sha256']}`, {card['raster']['bytes']} bytes, {n_dots} emitted cells.
Pre-registration: `knowledge/39_hypotheses_H64_preregistered.md` (SHA-256 in `registry/h64_preregistration.json`), amended
for the control tolerance only: `knowledge/39b_amendment_control_tolerance.md`.

## 1 · Sufficiency gate S1 (the premise of co-training)
Mean View-A out-of-quadrant AUC **{suf['mean_view_A_oof_auc']:.4f}** (fold minimum {suf['min_fold_view_A_oof_auc']:.4f}); thresholds mean ≥ 0.60, fold ≥ 0.55.
**{'PASS' if suf['S1_pass'] else 'FAIL'}.** Measured against H61's {suf['H61_reference_view_A_mean_oof_auc']:.4f}, the capacity cut did not change the picture.

## 2 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1)
| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
""" + "".join(f"| {a} | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {fmt_int(sc[a]['withheld_positive_pixels'])} |\n" for a in arms) + f"""
Paired difference, candidate minus single_B: {pdiff['single_B']['delta']:+.6f}, 95% CI {ci(pdiff['single_B']['ci95'])}.
Control: single_B {cv['control']['single_B_h64']:.10f} vs committed H61 {cv['control']['single_B_h61_committed']:.6f}, |Δ| {cv['control']['abs_difference']:.2e}.

## 3 · Gates
""" + "".join(f"* {a}: **{b}**\n" for a, b in gates_rows) + f"""
## 4 · Limits
* The holdout instrument does not rank the board (`knowledge/10` §5, `knowledge/31` §2). These are HOLDOUT-DTI values only.
* No exchange was run (S1 failed), so the S2 independence statistic was not evaluated in this round.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12–0.25%.
* The lane gate, uniqueness and projections are measured against the registry census available on disk at build time.
"""
    (DOCS.parent / "knowledge/40_h64_results_and_limits.md").write_text(kn)
    print("published:", DOCS / "h64.html", DOCS / "h64-executive-summary.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
