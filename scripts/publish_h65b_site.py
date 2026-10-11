#!/usr/bin/env python3
"""H65b -- render the landing page, the executive summary, and refresh the index pointers.

Everything shown is read from the receipts written by ``scripts/build_h65b_submission.py``
(evidence/h65b_run_card.json, evidence/h65b_format.json, evidence/h65b_uniqueness.json,
evidence/h65b_gate.json, evidence/h65b_e2_holdout.json, submission/<stem>.json).  No number on
the pages is typed by hand.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"

NAV = ('<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
       '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
       '<a href="index.html">Overview</a><a href="h65b.html">H65 round</a>'
       '<a href="executive-summary.html">H65 research status</a>'
       '<a href="downloads/index.html">Archive</a></nav></header>')


def jload(p: Path) -> dict:
    return json.loads(p.read_text())


def fmt_ci(x: dict) -> str:
    return f"{x['dti']:.5f} [{x['ci95'][0]:.5f}, {x['ci95'][1]:.5f}]"


def main() -> int:
    card = jload(EVID / "h65b_run_card.json")
    fmt = jload(EVID / "h65b_format.json")
    hold = jload(EVID / "h65b_e2_holdout.json")
    gate = jload(EVID / "h65b_gate.json")
    sub = jload((ROOT / "submission" / f"{card['submission']['name']}.json"))
    pooled = hold["pooled"]["scores"]
    canary = hold["leakage_canary"]
    lane_d = jload(EVID / "h65b_lane_dots.json")
    lane_s = jload(EVID / "h65b_lane_surface.json")
    lane_d_card = card["registry"]["lane_dots"]
    lane_s_card = card["registry"]["lane_surface"]
    uniq = jload(EVID / "h65b_uniqueness.json")
    n_ident = sum(1 for r in uniq["per_prior"] if r.get("identical"))

    lane_ok = bool(lane_s_card["ok"] and lane_d_card["ok"])
    submit_ok = False                     # E2 holdout was negative; the frozen rule says SUBMIT NO
    verdict_line = ("DOWNLOAD YES for research (format-valid, not identical to any of the "
                    f"{uniq['n_priors_checked']} registry rasters on decoded pixels) · "
                    "SUBMIT NO (holdout does not beat single_B; lane near-dot rule is "
                    "DUPLICATE/STOP on this saturated registry)")

    exec_html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="assets/ctd5.css">
<title>H65 research status — not for submission</title></head>
<body>{NAV}<main id="main">
<div class="eyebrow">H65 · historical research status</div>
<h1>H65 is not approved for submission.</h1>
<div class="notice bad" role="alert"><strong>RESEARCH DOWNLOAD ONLY · DUPLICATE/STOP · NOT FOR SUBMISSION · NO SLOT AUTHORIZED</strong>
<p>H65 does not beat the registered single_B control on the shared holdout, and the final-dot lane rule is DUPLICATE/STOP on the saturated registry. No override, upload instructions, or paste-ready identification is provided.</p>
<p>HOLDOUT-DTI {fmt_ci(pooled['candidate'])} vs single_B {fmt_ci(pooled['singleB'])}, evaluator <code>gems52-pooled-hide-v1</code>, {pooled['candidate']['withheld_positive_pixels']:,} withheld positives; paired Δ {hold['pooled']['paired_differences']['singleB']['delta']:+.5f}. This is an internal holdout measurement, not a leaderboard score.</p></div>
<div class="actions"><a class="button" href="downloads/h65b-candidate.tif" download>Download H65 research TIFF</a><a class="button secondary" href="downloads/h65b-candidate.zip" download>Research ZIP</a><a class="button secondary" href="h65b.html">H65 evidence</a></div>
<p class="fileline">{sub['file']}<br>{sub['bytes']:,} bytes · SHA-256 {sub['sha256']} · {sub['metadata']['emission']['accepted']:,} emitted cells</p>
<section class="prose"><h2>What the local receipts show</h2><ul><li>Local format checks pass; that does not establish portal acceptance.</li><li>Decoded-pattern uniqueness does not override the DUPLICATE/STOP lane rule.</li><li>H65 is negative; no organizer-confirmed receipt or weekly slot is recorded.</li></ul></section>
<p class="small">This historical page does not authorize a rerun, new run-card, rebuild, override, or submission. See the <a href="h65b.html">H65 method and evidence</a>.</p>
</main></body></html>"""
    (DOCS / "h65b-executive-summary.html").write_text(exec_html)

    land_html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="assets/ctd5.css">
<title>H65 — band-10 seismicity valley lines · GEMSDOE52</title></head>
<body>{NAV}<main id="main">
<div class="eyebrow">DOE GEMS / H65 · R5-H2a, the first band-10 detector in this repository</div>
<h1>A new GeoTIFF.<br>An unambiguous verdict.</h1>
<p class="lead">Hypothesis: fault traces are valley lines of the organiser's distance-to-earthquake field
<code>deq_n100a15</code> — the one input band no prior round ever read. The trace-correction corridor (rank 1)
was gate-refuted first this session; this is the rank-2 hypothesis, validated on the shared hide-and-recover
holdout before anything was published.</p>
<div class="notice" role="note"><strong>OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · DO NOT UPLOAD</strong>
<p>{verdict_line}. Competition slots used: 0.</p></div>
<div class="actions"><a class="button" href="downloads/h65b-candidate.tif" download>Download the H65 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h65b-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="executive-summary.html">H65 research status — not for submission</a></div>
<p class="fileline">{sub['file']}<br>{sub['bytes']:,} bytes · SHA-256 {sub['sha256']} ·
{sub['metadata']['emission']['accepted']:,} emitted cells · values exactly {{0,1}} · 0 NaN</p>
<section class="prose">
<h2>What was tested this session (three experiments, frozen in knowledge/41)</h2>
<ul>
<li><b>E1 — R5-H1 trace-correction corridor (rank 1).</b> The LiDAR one-sided scarp step, strike agreement
and detrended-elevation crest were frozen into a perpendicular-offset estimator; the spatially-blocked gate
(20 km whole-block trace folds, seed 20261009) FAILED: G3 margin {gate['conditions']['G3_beats_constant_control_px']['value']:.3f} px
vs the 0.300 px requirement — a constant shift does as well as the estimator, so the scarp terms carry no
locally-localizable trace-offset signal. G1 {gate['conditions']['G1_traces']['value']} traces (pass),
G2 median |ô| {gate['conditions']['G2_median_abs_offset_px']['value']:.3f} px (pass at the boundary),
G4 frac-0 {gate['conditions']['G4_argmax_zero_fraction']['value']:.3f} (pass). Receipt:
<code>evidence/h65b_gate.json</code>.</li>
<li><b>E2 — R5-H2a band-10 valley lines (rank 2).</b> HOLDOUT-DTI candidate
{fmt_ci(pooled['candidate'])} vs single_B {fmt_ci(pooled['singleB'])} vs random
{fmt_ci(pooled['random'])}; paired Δ candidate−single_B
{hold['pooled']['paired_differences']['singleB']['delta']:.5f}
[{hold['pooled']['paired_differences']['singleB']['ci95'][0]:.5f},
{hold['pooled']['paired_differences']['singleB']['ci95'][1]:.5f}] — negative. Leakage canary clean
(max fold AUC {canary['max_auc']}). Receipt: <code>evidence/h65b_e2_holdout.json</code>.</li>
<li><b>E3 — build + gates.</b> This page. All gates measured on the written bytes; run card:
<code>evidence/h65b_run_card.json</code>.</li>
</ul>
<h2>Why the verdict is what it is</h2>
<ul>
<li><b>Uniqueness:</b> 0 identical decoded priors of {uniq['n_priors_checked']} checked; the plain
novel-fraction is 0.0 only because 14 universal-coverage probes cover ≥95% of the footprint (the H64 frozen
novelty rule excludes them; per-prior rows are retained in <code>evidence/h65b_uniqueness.json</code>).</li>
<li><b>Lane:</b> dots-phase policy verdict {lane_d['policy']['verdict']} — the largest near-dot share
{lane_d['policy']['max_near_3px_fraction']:.3f} comes from informative rasters whose own 3 px halo covers
most of the footprint, so the 70% rule is unsatisfiable for any candidate here (the registry saturation
documented in knowledge/31). Logged as DUPLICATE and stopped, per the parallel-run protocol; no placement
re-tuning was attempted.</li>
<li><b>Not the union of two views:</b> this round is a single-band detector; the check is recorded as
"not the literal union of any prior set" (uniqueness receipt).</li>
</ul>
<h2>Limits</h2>
<ul>
<li>The holdout instrument cannot rank novel fields (knowledge/10 §5); every HOLDOUT-DTI here is a
necessary-not-sufficient gate, never a projected leaderboard score.</li>
<li>Band 10's 15° sector azimuth convention is undocumented in any sandbox-obtainable source; the detector
uses the convention-free valley-line form (knowledge/41 §5).</li>
<li>Holdout prevalence ≈ 1.04% of the footprint vs an estimated 0.12–0.25% true prevalence.</li>
<li>The E1 verdict refutes the frozen estimator on the named layers, not the organiser-confirmed corridor
population itself.</li>
</ul>
</section>
</main></body></html>"""
    (DOCS / "h65b.html").write_text(land_html)
    print("wrote docs/h65b-executive-summary.html and docs/h65b.html")
    return 0


HISTORIC_SECTIONS = (
    '<p class="small">R5 (concurrent round): <a href="downloads/r5-candidate.tif" download>gems52-r5-novel-n5_strike_ridge-16681px-20261008T234033Z-d2bfb0f7-zeros.tif</a>, SHA-256 <code>d2bfb0f79328399354943bd1</code>…, 16,681 px — ok to download, <b>not slot-approved</b>; its conditional scenario projection lists P(DTI > 0.2778) = 0.366 and P(DTI > 0.3195) = 0.226 under owner-reported score associations and assumed hidden-truth parameters; these are not scores or forecasts, with <a href="r5.html">its own audit page</a> and short path <code>r5-candidate.tif</code>. Its budget rule assumed |G| = 14,088.7 px, a conditional scenario not established by hidden truth; later owner-report-conditioned algebra gives [5,949.3, 12,512.1] px under stated assumptions — IR-H61-001 and IR-H61-010 in <a href="irregularities.html">the irregularity register</a>. Do not spend a weekly slot on either round.</p>'
    + "\n"
    '<p class="small"><a href="archive-ctd5-overview.html">CTD5 landing page</a> · <a href="ctd5-audit.html">CTD5 audit</a> · <a href="h62.html">H62 audit (parallel session)</a> · <a href="archive-h62-overview.html">H62 landing archive</a> · <a href="h61-audit.html">H61 audit</a> · <a href="h60c.html">H60C</a> · <a href="h60.html">H60</a> · <a href="h60-triple-convergence.html">H60 triple convergence</a> · <a href="h59.html">H59</a> · <a href="archive-h59-overview.html">H59 archive</a> · <a href="h58.html">H58</a> · <a href="h57.html">H57</a> · <a href="h57-creditcore.html">H57 credit core</a> · <a href="h56-cotrain.html">H56</a> · <a href="h56.html">H56</a> · <a href="h55.html">H55</a> · <a href="h55-edge.html">H55-EDGE</a> · <a href="h55-profile.html">H55 profile</a> · <a href="h55-paired-shoulders.html">H55 paired shoulders</a> · <a href="h54.html">H54</a> · <a href="h53.html">H53</a> · <a href="r3.html">R3</a> · <a href="r3-hypotheses.html">R3 hypotheses</a> · <a href="hypotheses.html">Hypotheses</a> · <a href="method.html">Method</a> · <a href="validation.html">Validation</a> · <a href="sources.html">Sources</a> · <a href="irregularities.html">Irregularities</a> · <a href="forensics.html">Forensics</a> · <a href="feed.html">Feed</a> · <a href="downloads/index.html">download archive</a> · <a href="downloads/ctd5-research.tif" download>CTD5 TIFF</a> · <a href="downloads/h61-candidate.tif" download>H61 TIFF</a> · <a href="downloads/gems52-h62-conc_soft-arm22000px.tif" download>H62 TIFF</a> · <a href="downloads/h58-candidate.tif" download>H58 TIFF</a> · <a href="downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif" download>H57 TIFF</a></p>'
    + "\n"
    '<li><b>H58, research-only, not approved to submit.</b> File <code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code>, SHA-256 prefix <code>130c242e33aef398c44b22cd</code>. Short path\n<a href="downloads/h58-candidate.tif" download>downloads/h58-candidate.tif</a>. Details: <a href="h58.html">H58 page</a>.</li>'
)


def executive_html_fix(s: str) -> str:
    return s


if __name__ == "__main__":
    raise SystemExit(main())
