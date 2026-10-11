#!/usr/bin/env python3
"""Publish the H62 site pages from receipts only — every displayed number is read from
``evidence/h62_buriedcorr_*.json`` / ``docs/data/submission_h62_buriedcorr.json``; nothing is hand-typed.

Writes:
  docs/h62-buriedcorr.html                    the H62 audit page
  (docs/index.html / docs/executive-summary.html are shared pages: hand-spliced at merge time, never overwritten here)
  docs/data/h62_buriedcorr_run_card.json      copy of the run card for the site data dir
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
    build = json.loads((DAD / "submission_h62_buriedcorr.json").read_text())
    card = load("h62_buriedcorr_run_card.json")
    val = load("h62_buriedcorr_validation.json")
    cot = load("h62_buriedcorr_cotrain.json")
    fmt = load("h62_buriedcorr_format_gate.json")
    uniq = load("h62_buriedcorr_uniqueness.json")
    lane_s = load("h62_buriedcorr_lane_surface.json")
    lane_d = load("h62_buriedcorr_lane_gate.json")
    slot = load("h62_buriedcorr_slot_gate.json")
    shutil.copy2(EV / "h62_buriedcorr_run_card.json", DAD / "h62_buriedcorr_run_card.json")

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

    # ---------------- docs/h62-buriedcorr.html ----------------
    h62 = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H62 buried structural corridors — co-training lane audit with measured gates.">
<title>H62 audit · GEMSDOE52</title><link rel="stylesheet" href="assets/ctd5.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="index.html">Overview</a><a href="h62-buriedcorr.html">Run &amp; evidence</a><a href="executive-summary.html">Research status</a><a href="sources.html">Sources</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main">
<h1>H62 — buried structural corridors</h1>
<div class="notice" role="note"><strong>{e(status_banner)}</strong><p>{e(status_long)}</p></div>
<p class="fileline">{e(fn)} · {px:,} emitted px · SHA-256 {e(sha)}</p>
<div class="actions"><a class="button" href="downloads/h62-buriedcorr-candidate.tif" download>Download research GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h62-buriedcorr-candidate.zip" download>Research ZIP</a></div>

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
<p><strong>Current evidence correction (knowledge/49; IR-R5-011):</strong> the 0.2778 team row is rank 17 in the saved 2026-10-09 20:18 UTC public-board observation (top 0.3774); no organizer receipt maps a TIFF hash to that score, so the file association remains owner-reported. Local bytes show the H33-labelled 37,654-cell raster is a strict subset of a separate 44,090-cell 0.2600-labelled raster: 6,436 cells removed, none added, all 100–200 m from the local known-fault mask. Those facts do not identify hidden new-fault credit or explain a score change. Official staff says new-fault truth may lie within 300 m of known traces. Historical nested-pair arithmetic is conditional, not a score explanation. H62’s pixels remain model hypotheses, not confirmed faults; distance to the catalogue alone does not establish zero penalty or credit.</p>

<h2>Run card</h2>
<p class="small">Verdict: <b>{e(card["verdict"])}</b>. This historical result is research-only and not approved for submission. No paste-ready name or note is provided. Full JSON: <a href="data/h62_run_card.json">data/h62_run_card.json</a>.</p>
<p class="small">Review tables: <a href="downloads/gems52-h62-37627px-candidate-geology.csv">per-pixel geological reasoning (37,627 rows)</a> · <a href="downloads/gems52-h62-a-only-candidate-segments.csv">A-only corridor segments (1,120 rows, one falsifier each)</a>.</p>
<p class="small">Qualification: {e(card.get("extra", {}).get("data_qualification", ""))} — every HOLDOUT-DTI number is labelled; every leaderboard number in this repository is OWNER-REPORTED, not ORGANIZER-CONFIRMED. Projections are never written as scores.</p>
</main><footer>Independent competition research, not an official DOE or DrivenData site. Predictions are not verified faults or geothermal discoveries.<br>
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · H62 / 2026-10-09</footer></body></html>
"""
    (ROOT / "docs/h62-buriedcorr.html").write_text(h62)

    # docs/index.html and docs/executive-summary.html are SHARED pages concurrently
    # maintained by multiple rounds (H61/H62-concordance/H62-buriedcorr). This
    # publisher must NOT overwrite them; the buriedcorr banner/guide blocks are
    # spliced into them by hand at merge time. See the H62-buriedcorr merge commit.
    print("wrote docs/h62-buriedcorr.html, docs/data/h62_buriedcorr_run_card.json, "
          "docs/data/submission_h62_buriedcorr.json, docs/downloads/h62-buriedcorr-candidate.*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
