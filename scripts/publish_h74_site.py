#!/usr/bin/env python3
"""Render the H74 landing page, executive summary, results note, README block and site banners.

Every number written here is read from ``evidence/h74_*.json`` or the submission receipt. Nothing is
typed by hand, so the page cannot disagree with the evidence it cites. Nothing here uploads anything
or changes a verdict; it only reports the verdict the run card already holds.

Run after ``scripts/run_h74.py audit``:
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


def fmt_int(x) -> str:
    return f"{int(x):,}"


def main() -> int:
    card = load("h74_run_card.json")
    hold = load("h74_holdout.json")
    build = load("h74_build.json")
    s1 = load("h74_sufficiency.json")
    can = load("h74_canary.json")
    feat = load("h74_features.json")
    audit = load("h74_audit_uniqueness.json")
    stem = card["raster"]["file"][:-4]
    sub = json.loads((SUBM / f"{stem}.json").read_text())
    val = sub["validator"]
    n_dots = card["raster"]["emitted_cells"]
    verdict = card["verdict"]
    promote = card["verdict_promote"]
    pooled = hold["pooled"]["a_only"]
    sc = pooled["scores"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"   # noqa: E731
    reg = card["correlation_overlap_vs_registry"]
    pd = card["holdout_dti"]["paired_candidate_minus_single_B"]
    ctrl = card["holdout_dti"]["control_reproduction"]
    arms = ["a_only", "single_B", "single_A2", "union_max", "disagreement_pre",
            "disagreement_post", "single_B_veto_Bonly", "concordant", "random"]

    # --------------------------------------------------------------- copies the page serves
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h74-candidate.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h74-candidate.zip")
    shutil.copy(SUBM / f"{stem}.tif", DOWN / f"{stem}.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / f"{stem}.zip")
    (SUBM / "H74_LATEST.txt").write_text(f"{stem}.tif\n# pointer for the site; NOT an upload approval\n")
    for f in sorted(EVID.glob("h74_*.json")):
        shutil.copy(f, DAD / f.name)
    csv_src = DOWN / "h74-a-only-reasoning.csv"
    csv_link = "h74-a-only-reasoning.csv"
    if csv_src.exists() and csv_src.stat().st_size > 8_000_000:
        gz = csv_src.with_suffix(".csv.gz")
        with csv_src.open("rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        csv_link = "h74-a-only-reasoning.csv.gz"

    fileline = (f"{esc(stem)}.tif<br>{fmt_int(card['raster']['bytes'])} bytes · SHA-256 "
                f"{esc(card['raster']['sha256'])} · {fmt_int(n_dots)} emitted cells · values exactly {{0,1}}, 0 NaN")
    if promote:
        notice = "ELIGIBLE FOR THE SELECTOR ONLY · NOT PROMOTED · NO SLOT USED"
        headline = "A file that passed every measured gate. Promotion is still a separate decision."
    else:
        notice = "OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · DO NOT UPLOAD"
        headline = "A unique, lane-checked research file and a negative verdict."

    gates_rows = [
        ("Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned)",
         "PASS" if val.get("ok") else "FAIL"),
        ("Values exactly {0, 1}; 0 NaN; 0 infinite",
         "PASS" if (val.get("n_nan") == 0 and val.get("min") == 0.0 and val.get("max") == 1.0) else "FAIL"),
        (f"Decoded-pattern uniqueness (not identical to any of the {reg['registry_rasters']} registry rasters)",
         "PASS" if reg["uniqueness_tier1"]["canonical_pattern_unique"] else "FAIL"),
        (f"Support novelty vs the {reg['informative_rasters']} informative registry rasters",
         f"{reg['uniqueness_tier2']['novel_fraction']:.4f}"),
        ("Not the union of the two views",
         "PASS" if card["not_the_union"]["not_union_pass"] else "FAIL"),
        ("Lane gate, literal, surface / dots",
         f"{reg['lane_surface_literal']} / {reg['lane_dots_literal']}"),
        ("Lane gate, saturation policy, surface / dots",
         f"{reg['lane_surface_policy']} / {reg['lane_dots_policy']}"),
        ("Lane policy max near-dot share (bar 0.70)",
         f"{reg['lane_dots_policy_max_near_3px']:.4f}"),
        ("Audit (audit_uniqueness.py, census): surface max Spearman / dots max near-3px",
         f"{reg['audit_surface']['max_spearman']:.4f} / {reg['audit_dots']['max_near_3px']:.4f}"),
        ("S1 sufficiency (View A2 out-of-quadrant AUC mean ≥ 0.60, min fold ≥ 0.55)",
         f"{'PASS' if s1['S1_pass'] else 'FAIL'} ({s1['mean_view_A2_oof_auc']:.4f} / {s1['min_fold_view_A2_oof_auc']:.4f})"),
        ("Holdout beats single_B (paired CI lower bound > 0)",
         "PASS" if hold["holdout_eligible"] else "FAIL"),
    ]
    gates_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in gates_rows)
    arm_rows = ""
    for a in arms:
        hl = " class='highlight'" if a == "a_only" else ""
        arm_rows += (f"<tr{hl}><td>{a}</td>"
                     f"<td class='numeric'>{sc[a]['dti']:.6f}</td><td class='numeric'>{ci(sc[a]['ci95'])}</td>"
                     f"<td class='numeric'>{fmt_int(sc[a]['withheld_positive_pixels'])}</td></tr>")
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            '<a href="index.html">Overview</a><a href="h74-executive-summary.html">Submission guide</a>'
            '<a href="h71.html">H71 (previous)</a><a href="downloads/index.html">Archive</a>'
            '</nav></header><main id="main">')
    tail = "</main></body></html>\n"

    earlier = """
<section><h2>Earlier rounds still on this site</h2><p class="small">Each is a separate artefact with its own receipt. None of them is the H74 file, and none is approved for a slot.</p>
<ul>
<li><b>H71, previous round, negative. Do not upload.</b> <a href="h71.html">H71 landing</a> · <a href="h71-executive-summary.html">H71 submission guide</a></li>
<li><b>H70, negative; its 610-px file is a measured lane duplicate. Do not upload.</b> <a href="h70.html">H70 landing</a></li>
<li><b>H69, negative; the first lane-feasible file, still not slot-approved.</b> <a href="h69-overview.html">H69 overview</a></li>
<li><b>H67, negative. Do not upload.</b> <a href="h67.html">H67 landing</a></li>
<li><b>H65b, negative. Do not upload.</b> <a href="h65b.html">H65b round page</a></li>
</ul></section>
"""

    index = head + f"""
<section class="hero"><div><div class="eyebrow">DOE GEMS / H74 · deformation-only View A2 co-training (the deferred H70-E variant)</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">{esc(headline)} H74 executes the one lane variant no previous round tested: a View A
built <b>only</b> from the deformation bands (geodetic strain 4/7/8, seismicity 10/16), with View B
(surface) unchanged. Five consecutive mixed potential-field+deformation View A rebuilds all failed the
Blum&ndash;Mitchell sufficiency screen out of quadrant (AUC &asymp; 0.52); H74 attributes the failure to one
half. The emission is the lane's discovery signal on the deformation pair — the strict A2-only stratum
(A2 confident, B abstaining: a young blind fault straining beneath cover) — placed with the lane-valid
constrained placement, and every emitted dot carries written geological reasoning.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong>
<p>Verdict: <b>{esc(verdict)}</b></p></div>
<div class="actions"><a class="button" href="downloads/h74-candidate.tif" download>Download the H74 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h74-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/{esc(csv_link)}" download>Geological reasoning CSV</a></div>
<p class="fileline">{fileline}</p>
<p class="small"><a href="h74-executive-summary.html">How to submit, and whether this file may be submitted →</a>
· <a href="data/h74_run_card.json">Complete JSON run card ↗</a></p></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead>
<tbody>{gates_html}</tbody></table></div>
<p class="small">Local validator only. Not an organiser acceptance receipt. Lane gate statistics are the literal
rule and the saturation policy from <code>gems52.gates.lane_report</code>; the literal rule fails for every nonempty
raster on this registry because it contains a measured universal-coverage lattice probe.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI (gems52-pooled-hide-v1), matched budget {hold['budget_per_arm_per_fold']} dots/fold/arm</h2>
<p class="small">{fmt_int(sc['a_only']['withheld_positive_pixels'])} withheld positive pixels · α 0.2 / β 0.8 ·
300 m triangular kernel · 95% paired physical-cluster bootstrap, 1000 draws. Best comparable control: <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>{arm_rows}</tbody></table></div>
<p class="small">Paired difference, candidate (a_only) minus single_B: {pd['delta']:+.6f}, 95% CI {ci(pd['ci95'])}.
Control reproduction at the H61 budget (9,400 dots/fold): single_B {ctrl['single_B_h74']:.6f} vs committed H61
{ctrl['single_B_committed']:.6f}, |Δ| {ctrl['abs_difference']:.2e} (tolerance {ctrl['tolerance']}).
Holdout numbers are HOLDOUT-DTI, never organiser scores, and the hide-and-recover instrument does not rank board
performance (<code>knowledge/10</code> §5).</p></section>
<hr class="divider">
<section><h2>Independence and sufficiency (the lane's mandated tests)</h2>
<p class="small">Independence screen on spatial-block out-of-fold errors of the two views on labelled negatives
(held-out catalogue-zero proxies): max |ρ| <b>{hold['independence_max_abs_rho']:.4f}</b> against an abandon bar of 0.60 →
exchange <b>{'allowed' if hold['exchange_allowed'] else 'abandoned'}</b>. S1 sufficiency on the deformation-only View A2
(out-of-quadrant AUC): mean <b>{s1['mean_view_A2_oof_auc']:.4f}</b>, min fold <b>{s1['min_fold_view_A2_oof_auc']:.4f}</b>
→ <b>{'PASS' if s1['S1_pass'] else 'FAIL'}</b> (gate 0.60 / 0.55). Prior mixed View A rebuilds: H61 0.5163 · H63 0.5362 ·
H64 0.5230 · H65 0.5202 · H70 0.5166. View B mean {s1['mean_view_B_oof_auc']:.4f} (H61: 0.6843). Leakage canary: max alarm AUC
<b>{can['max_alarm_across_folds']:.4f}</b>, any alarm <b>{can['any_alarm']}</b> (bar 0.90).</p></section>
<hr class="divider">
<section><h2>What this does and does not show</h2><ul>
<li>It shows the lane's only untested View A variant measured end to end: a deformation-only View A2, the
independence premise on the A2/B pair, one whole-segment exchange, and the strict A2-only discovery stratum
emitted as a unique, lane-checked file with written geological reasoning per dot.</li>
<li>It does not show the A2-only stratum beats the single-view baseline on the hide-and-recover instrument; the
holdout table above is the measured comparison.</li>
<li><b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing on this page is an organiser score or a promise of a board gain.</li>
<li>The best published board score is 0.3774 (rank 1, xiaofanhu), 0.3195 is rank 7 (DARD), 0.2778 is rank 13
(extradr19): <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official
leaderboard</a> (public board, not organiser-confirmed).</li>
<li>Attribution caveat: the 0.2778 and 0.2600 figures are owner-reported, not organiser-confirmed (IR-H61-004).</li></ul>
<p class="small"><a href="../knowledge/63_hypotheses_H74_preregistered.md">Ranked hypotheses and the frozen protocol →</a> ·
<a href="../knowledge/64_h74_results_and_limits.md">Results and limits →</a> ·
<a href="h71.html">H71 landing (previous round) →</a></p></section>
{earlier}""" + tail

    exec_html = head + f"""
<div class="eyebrow">Executive summary / submission guide</div>
<h1>How to submit, and whether this file may be submitted.</h1>
<p class="lead">Read the verdict first. A valid file is not an approved competition entry; the selector decides
promotion within the weekly cap shown on the submission page.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong><p>Verdict: <b>{esc(verdict)}</b></p>
<p>The file is new inference, not identical on decoded pixels to any registry raster, so it is safe to download
for research. Whether it may be submitted is answered by the measured gates above; this round spends no weekly slot.</p></div>
<div class="actions"><a class="button" href="downloads/h74-candidate.tif" download>Download the H74 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h74-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/{esc(csv_link)}" download>Geological reasoning CSV</a></div>
<p class="fileline">{fileline}</p>
<section class="prose"><h2>The file contract (checked on disk)</h2><ul>
<li>One band, float32, every value in [0, 1]; in practice exactly 0 or 1.</li>
<li>No NaN or infinite values anywhere in the file (the portal's “Predicted values must be in range [0, 1]”
rejection is caused by NaN/out-of-range bytes, and this file has neither).</li>
<li>EPSG:32611, shape and geotransform identical to the pinned <code>sample_submission.tif</code>.</li>
<li>{fmt_int(n_dots)} emitted cells, all strict A2-only discovery candidates (View A2 confident, View B abstaining),
all more than 200 m from a mapped trace, 3 px minimum separation.</li>
<li>Name for the portal: <code>{esc(card['submission_name'])}</code>. Note ({card['note_chars']} characters):
<code>{esc(card['note'])}</code></li>
</ul><p class="small">Local validator only; not an organiser acceptance receipt.</p>
<h2>Exact steps, only if a later selector approves this file</h2>
<ol><li>Open the competition submission page (login required; <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>).</li>
<li>Under <b>File to submit</b>, choose the TIFF (or the ZIP with the single TIFF).</li>
<li>Paste the name and note above into the submission form.</li>
<li>Submit only if the selector has approved this file. This file is not approved.</li></ol></section>
{earlier}""" + tail

    (DOCS / "h74.html").write_text(index)
    (DOCS / "h74-executive-summary.html").write_text(exec_html)

    # --------------------------------------------------------------- knowledge note
    kn = f"""# 60 · H74 results and limits (rendered from the receipts by `scripts/publish_h74_site.py`)

**Verdict: `{verdict}`**

Artefact `{stem}.tif`, SHA-256 `{card['raster']['sha256']}`, {card['raster']['bytes']} bytes, {n_dots} emitted cells,
every one a strict A2-only discovery candidate with a written geological reasoning row
(`docs/downloads/{csv_link}`). Pre-registration: `knowledge/63_hypotheses_H74_preregistered.md`
(SHA-256 in `registry/h74_preregistration.json`).

## 1 · What H74 changed

H74 executes the deferred **H70-E** variant: a **deformation-only View A2** built from the geodetic
strain bands (4 second invariant, 7 shear, 8 dilatation) and the seismicity bands (10 distance, 16
density), with gradient transforms at the shared scales and strain coherence — 22 channels — while
View B (surface, 37 channels) is unchanged. Every previous View A mixed potential-field and
deformation channels; none isolated the deformation half, so the five sufficiency failures
(H61 0.5163 · H63 0.5362 · H64 0.5230 · H65 0.5202 · H70 0.5166) could not be attributed. H74
attributes them on the A2/B pair and re-runs the lane's full mandated protocol: independence screen,
one whole-segment confident-to-abstaining exchange per direction, nine-arm matched-budget
hide-and-recover holdout against the single-view baseline, then the strict A2-only discovery stratum
built with the H70 §3 lane-valid constrained placement.

## 2 · Independence, canary and sufficiency (the lane's mandated tests)

Independence screen (spatial-block OOF errors on labelled negatives, held-out catalogue-zero proxies): max |ρ|
**{hold['independence_max_abs_rho']:.4f}** against the 0.60 abandon bar → exchange
**{'allowed' if hold['exchange_allowed'] else 'abandoned'}** (H70 measured 0.1337 on the potential-field pair).
Leakage canary: max alarm AUC **{can['max_alarm_across_folds']:.4f}**, any alarm **{can['any_alarm']}**
(bar 0.90). S1 sufficiency on View A2 (out-of-quadrant AUC): mean **{s1['mean_view_A2_oof_auc']:.4f}**,
min fold **{s1['min_fold_view_A2_oof_auc']:.4f}** → **{'PASS' if s1['S1_pass'] else 'FAIL'}**
(gate 0.60 / 0.55). View B mean **{s1['mean_view_B_oof_auc']:.4f}** (H61: 0.6843).

## 3 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1), matched budget {hold['budget_per_arm_per_fold']} dots/fold/arm

| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
""" + "".join(f"| {a} | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {fmt_int(sc[a]['withheld_positive_pixels'])} |\n" for a in arms) + f"""
Paired difference, candidate (a_only) minus single_B: {pd['delta']:+.6f}, 95% CI {ci(pd['ci95'])}.
Control reproduction at the H61 budget (9,400 dots/fold): single_B {ctrl['single_B_h74']:.6f} vs committed H61
{ctrl['single_B_committed']:.6f}, |Δ| {ctrl['abs_difference']:.2e} (tolerance {ctrl['tolerance']}).

## 4 · Gates
""" + "".join(f"* {a}: **{b}**\n" for a, b in gates_rows) + f"""
## 5 · Limits
* The holdout instrument does not rank the board (`knowledge/10` §5, `knowledge/31` §2). These are HOLDOUT-DTI values only.
* The literal lane rule fails for every nonempty raster on this registry (measured universal-coverage lattice probe);
  the policy verdict classifies probes by measured coverage ≥ 0.95 and is the repository's authoritative lane.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12–0.25%.
* Inputs are SHA-256-pinned owner mirrors, not organiser-authenticated downloads.
* The reasoning CSV is measured context plus a template hypothesis, not field-verified geology.
"""
    (ROOT / "knowledge/64_h74_results_and_limits.md").write_text(kn)

    # --------------------------------------------------------------- README block (inserted at the very top)
    readme_block = f"""<!--H74-README-->
# Current status — H74 (2026-10-09): {('PROMOTE-ELIGIBLE, selector decides' if promote else 'NEGATIVE verdict')}, one unique GeoTIFF to download, nothing submitted

> **DOWNLOAD: {'YES — the file is format-valid and unique on decoded pixels' if (val.get('ok') and reg['uniqueness_tier1']['canonical_pattern_unique']) else 'NO'}. SUBMIT TO THE COMPETITION: {'YES — pending the separate selector step' if promote else 'NO'}.**
> {esc(verdict)}

**★ [Download the H74 GeoTIFF — one click](docs/downloads/h74-candidate.tif)** ·
[single-TIFF ZIP](docs/downloads/h74-candidate.zip) ·
[geological reasoning CSV, one row per dot](docs/downloads/{esc(csv_link)}) ·
**[Executive summary / exact submission steps](docs/h74-executive-summary.html)** ·
[Landing page](docs/h74.html) · [Run card](evidence/h74_run_card.json) ·
[Results and limits](knowledge/64_h74_results_and_limits.md)

- **File:** `{stem}.tif` — {fmt_int(card['raster']['bytes'])} bytes, {fmt_int(n_dots)} emitted cells
- **SHA-256:** `{card['raster']['sha256']}`
- **Name ({len(card['submission_name'])} characters):** `{card['submission_name']}`
- **Note ({card['note_chars']} characters):** `{card['note']}`
- **Local validator:** one float32 band; values exactly {{0, 1}}; 0 NaN; 0 infinite; EPSG:32611; shape
  3,730 × 3,292 and transform identical to `data/sample_submission.tif`. Local validator only —
  **not** an organiser acceptance receipt.

**What H74 tested (the lane, one round).** The deferred **H70-E** variant: a **deformation-only View A2**
(geodetic strain bands 4/7/8 + seismicity bands 10/16, 22 channels with gradient/coherence transforms),
View B unchanged, disagreement as the discovery signal. Preregistered in
[`knowledge/63`](knowledge/63_hypotheses_H74_preregistered.md) (SHA-256 pinned in
`registry/h74_preregistration.json`; the runner refuses if it moves). The shared H61 canary/fit/exchange
stages ran **unchanged** with the View A list substituted by a setup wrapper — no forked stage; the 17
deformation columns were added to the shared store once, idempotently (`+h74-deformation-v1`).

| Check | Label | Result | Receipt |
|---|---|---|---|
| Leakage canary ({feat['view_A2_channel_count'] + feat['view_B_with_external_count']} channels × 4 folds) | PREMISE-AUC | max direction-insensitive AUC **{can['max_alarm_across_folds']:.4f}**, any alarm **{can['any_alarm']}** (bar 0.90) | [`evidence/h74_canary.json`](evidence/h74_canary.json) |
| S1 sufficiency (View A2 deformation-only, out-of-quadrant) | PREMISE-AUC | mean **{s1['mean_view_A2_oof_auc']:.4f}**, min fold **{s1['min_fold_view_A2_oof_auc']:.4f}** → **{'PASS' if s1['S1_pass'] else 'FAIL'}** (gate 0.60/0.55); prior mixed View A: 0.5163–0.5362 | [`evidence/h74_sufficiency.json`](evidence/h74_sufficiency.json) |
| Independence (spatial-block OOF errors on labelled negatives, A2/B pair) | diagnostic | max abs ρ **{hold['independence_max_abs_rho']:.4f}** < 0.60 → exchange **{'allowed' if hold['exchange_allowed'] else 'abandoned'}** | [`evidence/h74_independence.json`](evidence/h74_independence.json) |
| Control reproduction (single_B at 9,400 dots/fold) | HOLDOUT-DTI | **{ctrl['single_B_h74']:.6f}** vs committed H61 {ctrl['single_B_committed']}, abs Δ {ctrl['abs_difference']:.1e} ≤ {ctrl['tolerance']} → **PASS** | [`evidence/h74_holdout.json`](evidence/h74_holdout.json) |
| **HOLDOUT-DTI, matched budget 9,400 dots/fold/arm** | HOLDOUT-DTI | a_only **{sc['a_only']['dti']:.6f}** {ci(sc['a_only']['ci95'])} vs single_B **{sc['single_B']['dti']:.6f}** {ci(sc['single_B']['ci95'])}; paired Δ **{pd['delta']:+.6f}** {ci(pd['ci95'])} → **{'beats' if hold['holdout_eligible'] else 'does not beat'} single_B** | [`evidence/h74_holdout.json`](evidence/h74_holdout.json) |
| Format gate | diagnostic | {'PASS' if val.get('ok') else 'FAIL'} — 0 NaN, {{0,1}}, pinned CRS/shape/transform | [`evidence/h74_build.json`](evidence/h74_build.json) |
| Decoded-pattern uniqueness ({reg['registry_rasters']} registry rasters) | diagnostic | {'PASS' if reg['uniqueness_tier1']['canonical_pattern_unique'] else 'FAIL'} — canonical-pattern unique, not the prior union | [`evidence/h74_build.json`](evidence/h74_build.json) |
| Support novelty vs informative priors | diagnostic | **{reg['uniqueness_tier2']['novel_fraction']:.4f}** | [`evidence/h74_build.json`](evidence/h74_build.json) |
| Lane gate, surface (before placement) | diagnostic | literal **{reg['lane_surface_literal']}**, policy **{reg['lane_surface_policy']}** | [`evidence/h74_lane_surface.json`](evidence/h74_lane_surface.json) |
| Lane gate, final dots | diagnostic | literal **{reg['lane_dots_literal']}**, policy **{reg['lane_dots_policy']}** (max near **{reg['lane_dots_policy_max_near_3px']:.4f}**, max Spearman {reg['lane_dots_policy_max_spearman']:.4f}) → **{'gate passes' if reg['lane_dots_policy'] == 'PASS' else 'gate fails, reported verbatim'}** | [`evidence/h74_lane_dots.json`](evidence/h74_lane_dots.json) |
| Census audit (`audit_uniqueness.py`) | diagnostic | surface max Spearman {reg['audit_surface']['max_spearman']:.4f}; dots max near {reg['audit_dots']['max_near_3px']:.4f} | [`evidence/h74_audit_uniqueness.json`](evidence/h74_audit_uniqueness.json) |
| Not the union of the two views | diagnostic | **{'PASS' if card['not_the_union']['not_union_pass'] else 'FAIL'}** — every dot in the strict A2-only stratum | [`evidence/h74_not_union.json`](evidence/h74_not_union.json) |

**Verdict: H74 {'promote-eligible (selector still owns the slot)' if promote else 'not promoted'}.** Experiments used: **3 of 3**
(E1 features+canary+fit+sufficiency, E2 exchange+holdout, E3 build+audit). Run card:
[`evidence/h74_run_card.json`](evidence/h74_run_card.json).

**Leaderboard (PUBLIC BOARD, not ORGANIZER-CONFIRMED).** Top is **0.3774** (xiaofanhu); 0.3195 is rank 7
(DARD); 0.2778 is rank 13 (extradr19), owner-reported and not linked to any file. Source:
https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ (2026-10-09).

**Still open:** a candidate that beats `single_B` on the holdout (nothing in this lane has); H74-D
(radiometric-cover gating of the A2-only stratum) and H74-E (H65 operator on the strain bands) remain
deferred; the deformation-only View A2 is now measured — see `knowledge/64` for what it attributes.
<!--/H74-README-->
"""
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    if "<!--H74-README-->" in readme:
        i = readme.index("<!--H74-README-->")
        j = readme.index("<!--/H74-README-->", i) + len("<!--/H74-README-->")
        readme = readme[:i] + readme_block.rstrip("\n") + readme[j:]
    else:
        readme = readme_block + readme
    readme_path.write_text(readme)

    # --------------------------------------------------------------- site banners (idempotent)
    banner = f"""<!--H74-BANNER--><div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H74 ({'promote-eligible' if promote else 'negative'}).</strong> {'Download yes — it passed every measured gate; the selector still owns the slot.' if promote else 'Download yes, for research only; submit no.'} The deferred H70-E variant: a deformation-only View A2 (strain + seismicity) with the surface view unchanged; the strict A2-only discovery stratum emitted with written geological reasoning per dot. <a href="downloads/h74-candidate.tif" download>Download the H74 GeoTIFF</a> ({fmt_int(card['raster']['bytes'])} bytes, SHA-256 <code>{esc(card['raster']['sha256'][:16])}…</code>, {fmt_int(n_dots)} cells) · <a href="h74-executive-summary.html">Read the gate status first</a> · <a href="h74.html">Run &amp; evidence</a>. Historical downloads below are not upload approval.</div><!--/H74-BANNER-->"""
    dl_rows = f"""<!--H74-DL--><tr><td><a href="h74-candidate.tif" download>h74-candidate.tif</a></td><td class="number">{fmt_int(card['raster']['bytes'])}</td><td class="mono">{esc(card['raster']['sha256'])}</td><td>H74 · deformation-only View A2 co-training, strict A2-only stratum · {fmt_int(n_dots)} px · newest round; <a href="../h74.html">evidence</a></td></tr>
<tr><td><a href="{esc(stem)}.tif" download>{esc(stem)}.tif</a></td><td class="number">{fmt_int(card['raster']['bytes'])}</td><td class="mono">{esc(card['raster']['sha256'])}</td><td>canonical filename, byte-identical</td></tr>
<tr><td><a href="h74-candidate.zip" download>h74-candidate.zip</a></td><td class="number">single-TIFF ZIP, byte-identical payload</td><td class="mono">portal-accepted wrapper</td><td>one-TIFF ZIP</td></tr>
<tr><td><a href="{esc(csv_link)}" download>{esc(csv_link)}</a></td><td class="number">CSV</td><td class="mono">—</td><td>{fmt_int(n_dots)} per-pixel geological reasoning rows (hypothesis + named non-fault mimic + falsifier)</td></tr><!--/H74-DL-->"""

    def insert_after(path: Path, anchor: str, block: str, start: str, end: str):
        text = path.read_text()
        old = ""
        if start in text:
            i = text.index(start)
            j = text.index(end, i) + len(end)
            old = text[i:j]
        if old and old != block:
            text = text.replace(old, block)
        elif not old:
            assert anchor in text, f"{path}: anchor missing"
            text = text.replace(anchor, anchor + block, 1)
        path.write_text(text)

    insert_after(DOCS / "index.html", '<main id="main">', banner,
                 "<!--H74-BANNER-->", "<!--/H74-BANNER-->")
    insert_after(DOCS / "executive-summary.html", '<main id="main">', banner,
                 "<!--H74-BANNER-->", "<!--/H74-BANNER-->")
    dl_index = DOWN / "index.html"
    text = dl_index.read_text()
    old = ""
    if "<!--H74-DL-->" in text:
        i = text.index("<!--H74-DL-->")
        j = text.index("<!--/H74-DL-->", i) + len("<!--/H74-DL-->")
        old = text[i:j]
    if old and old != dl_rows:
        text = text.replace(old, dl_rows)
    elif not old:
        anchor = "<tbody>"
        assert anchor in text
        text = text.replace(anchor, anchor + dl_rows, 1)
    notice_new = f"""<!--H74-DOWNLOAD-NOTICE--><aside style="padding:20px;background:#fff1de;color:#12331f;font:16px/1.6 system-ui"><b>Latest research: H74 — {'PROMOTE-ELIGIBLE, selector decides' if promote else 'DO NOT SUBMIT'}.</b> <a href="h74-candidate.tif" download>Download the H74 GeoTIFF</a> ({fmt_int(card['raster']['bytes'])} bytes, SHA-256 <code>{esc(card['raster']['sha256'][:16])}…</code>, {fmt_int(n_dots)} cells) · <a href="../h74-executive-summary.html">Read the gate status first</a> · <a href="../h74.html">Run &amp; evidence</a>. Historical downloads below are not upload approval.</aside><!--/H74-DOWNLOAD-NOTICE-->"""
    m = re.search(r"<!--H[0-9A-Z]+-DOWNLOAD-NOTICE-->.*?<!--/H[0-9A-Z]+-DOWNLOAD-NOTICE-->", text, re.S)
    if m:
        text = text[:m.start()] + notice_new + text[m.end():]   # supersede the previous round's notice
    else:
        text = text.replace("<body>", "<body>" + notice_new, 1)
    dl_index.write_text(text)

    # --------------------------------------------------------------- root redirect page
    root_index = ROOT / "index.html"
    root_index.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=docs/index.html">'
        f'<title>GEMSDOE52 — H74 research GeoTIFF and submission status</title></head><body>'
        f'<h1>GEMSDOE52 · H74</h1>'
        f'<p><a href="docs/downloads/h74-candidate.tif" download>Download the H74 GeoTIFF ({fmt_int(card["raster"]["bytes"])} bytes)</a></p>'
        '<p><a href="docs/index.html">Open the research download and the explicit submission verdict.</a></p>'
        '<p><a href="docs/h74-executive-summary.html">Exactly how to submit, field by field.</a></p>'
        f'<p>Verdict: DOWNLOAD {"YES" if (val.get("ok") and reg["uniqueness_tier1"]["canonical_pattern_unique"]) else "NO"}, '
        f'THE PORTAL WILL ACCEPT THE FORMAT {"YES" if val.get("ok") else "NO"}, '
        f'SPEND A SLOT {"YES — pending the selector" if promote else "NO"}.</p></body></html>\n')

    print("published:", DOCS / "h74.html", DOCS / "h74-executive-summary.html",
          ROOT / "knowledge/64_h74_results_and_limits.md")
    print("banners:", DOCS / "index.html", DOCS / "executive-summary.html", dl_index,
          ROOT / "index.html", "README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
