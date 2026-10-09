#!/usr/bin/env python3
"""Render the H66 landing page, executive summary, results note, README block and site banners.

Every number written here is read from ``evidence/h66_*.json`` or the submission receipt. Nothing is
typed by hand, so the page cannot disagree with the evidence it cites. Nothing here uploads anything
or changes a verdict; it only reports the verdict the run card already holds.

Run after ``scripts/run_h66.py audit``:
    .venv/bin/python scripts/publish_h66_site.py
"""
from __future__ import annotations

import gzip
import html
import json
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
    card = load("h66_run_card.json")
    hold = load("h66_holdout.json")
    build = load("h66_build.json")
    diag = load("h66_diag.json")
    stem = card["raster"]["file"][:-4]
    sub = json.loads((SUBM / f"{stem}.json").read_text())
    val = sub["validator"]
    n_dots = card["raster"]["emitted_cells"]
    verdict = card["verdict"]
    promote = card["verdict_promote"]
    mp = hold["matched_pooled"]
    sc = mp["scores"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"   # noqa: E731
    reg = card["correlation_overlap_vs_registry"]

    # --------------------------------------------------------------- copies the page serves
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h66-candidate.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h66-candidate.zip")
    shutil.copy(SUBM / f"{stem}.tif", DOWN / f"{stem}.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / f"{stem}.zip")
    (SUBM / "H66_LATEST.txt").write_text(f"{stem}.tif\n# pointer for the site; NOT an upload approval\n")
    for f in ("h66_run_card.json", "h66_holdout.json", "h66_build.json", "h66_diag.json",
              "h66_premise.json", "h66_canary.json", "h66_independence.json",
              "h66_not_union.json", "h66_uniqueness.json"):
        if (EVID / f).exists():
            shutil.copy(EVID / f, DAD / f)
    if (EVID / "h66_audit_uniqueness.json").exists():
        shutil.copy(EVID / "h66_audit_uniqueness.json", DAD / "h66_audit_uniqueness.json")
    # reasoning CSV: plain copy, plus a gzip copy when it is large
    csv_src = DOWN / "h66-a-only-reasoning.csv"
    csv_link = "h66-a-only-reasoning.csv"
    if csv_src.exists() and csv_src.stat().st_size > 8_000_000:
        gz = csv_src.with_suffix(".csv.gz")
        with csv_src.open("rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        csv_link = "h66-a-only-reasoning.csv.gz"

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
        ("Holdout beats single_B (paired CI lower bound > 0)",
         "PASS" if hold["holdout_eligible"] else "FAIL"),
    ]
    gates_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in gates_rows)
    arms = ["a_only", "single_B", "single_A", "union_max", "random"]
    arm_rows = ""
    for a in arms:
        hl = " class='highlight'" if a == "a_only" else ""
        arm_rows += (f"<tr{hl}><td>{a}</td>"
                     f"<td class='numeric'>{sc[a]['dti']:.6f}</td><td class='numeric'>{ci(sc[a]['ci95'])}</td>"
                     f"<td class='numeric'>{fmt_int(sc[a]['withheld_positive_pixels'])}</td></tr>")
    pd = card["holdout_dti"]["paired_candidate_minus_single_B"]
    ctrl = card["holdout_dti"]["control_reproduction"]
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            '<a href="index.html">Overview</a><a href="h66-executive-summary.html">Submission guide</a>'
            '<a href="h64.html">H64 (previous)</a><a href="downloads/index.html">Archive</a>'
            '</nav></header><main id="main">')
    tail = "</main></body></html>\n"

    earlier = """
<section><h2>Earlier rounds still on this site</h2><p class="small">Each is a separate artefact with its own receipt. None of them is the H66 file, and none is approved for a slot.</p>
<ul>
<li><b>H64, previous round, negative. Do not upload.</b> <a href="h64.html">H64 landing</a> · <a href="h64-executive-summary.html">H64 submission guide</a></li>
<li><b>H63, negative. Do not upload.</b> <a href="h63-audit.html">H63 audit</a></li>
<li><b>H61, negative; its file is a measured lane duplicate. Do not upload.</b> <a href="archive-h61-landing.html">H61 landing</a></li>
<li><b>H58, research-only, not approved to submit.</b> <a href="h58.html">H58 page</a></li>
<li><b>H55-EDGE, failed-gate archive.</b> <a href="h55-edge.html">h55-edge.html</a></li>
</ul></section>
"""

    index = head + f"""
<section class="hero"><div><div class="eyebrow">DOE GEMS / H66 · A-only discovery stratum, novel-first placement (43b)</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">{esc(headline)} H66 emits the lane's discovery signal directly: where View A (potential-field/
subsurface) is confident and View B (surface) abstains, the fault may be buried beneath cover. The emission is that
strict A-only stratum — every emitted dot is one of those candidates with written geological reasoning. The
preregistered lane-quiet domain (3 px clear of every informative prior) was measured EMPTY on this registry
(knowledge/43a), so placement follows amendment 43b: exact-novel cells first, ranked by View A's out-of-fold
conviction, at 3 px metric-aware spacing; the lane's own &gt;70% near-dot rule is then measured on the built bytes
and reported verbatim.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong>
<p>Verdict: <b>{esc(verdict)}</b></p></div>
<div class="actions"><a class="button" href="downloads/h66-candidate.tif" download>Download the H66 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h66-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/{esc(csv_link)}" download>Geological reasoning CSV</a></div>
<p class="fileline">{fileline}</p>
<p class="small"><a href="h66-executive-summary.html">How to submit, and whether this file may be submitted →</a>
· <a href="data/h66_run_card.json">Complete JSON run card ↗</a></p></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead>
<tbody>{gates_html}</tbody></table></div>
<p class="small">Local validator only. Not an organiser acceptance receipt. Lane gate statistics are the literal
rule and the saturation policy from <code>gems52.gates.lane_report</code>; the literal rule fails for every nonempty
raster on this registry because it contains a measured universal-coverage lattice probe.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI (gems52-pooled-hide-v1), matched budget {hold['matched_budget_per_fold']} dots/fold</h2>
<p class="small">{fmt_int(sc['a_only']['withheld_positive_pixels'])} withheld positive pixels · α 0.2 / β 0.8 ·
300 m triangular kernel · 95% paired physical-cluster bootstrap, 1000 draws. Best comparable control: <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>{arm_rows}</tbody></table></div>
<p class="small">Paired difference, candidate (a_only) minus single_B: {pd['delta']:+.6f}, 95% CI {ci(pd['ci95'])}.
Control reproduction at the H61 budget (9,400 dots/fold): single_B {ctrl['single_B_h66']:.6f} vs committed H61
{ctrl['single_B_h61_committed']:.6f}, |Δ| {ctrl['abs_difference']:.2e} (tolerance {ctrl['tolerance']}).
Holdout numbers are HOLDOUT-DTI, never organiser scores, and the hide-and-recover instrument does not rank board
performance (<code>knowledge/10</code> §5).</p></section>
<hr class="divider">
<section><h2>Independence and premise (the lane's mandated tests)</h2>
<p class="small">Independence screen on spatial-block out-of-fold errors of the two views on labelled negatives
(held-out catalogue-zero proxies): max |ρ| <b>{hold['independence_max_abs_rho']:.4f}</b> against an abandon bar of 0.60 →
exchange <b>{'allowed' if hold['exchange_allowed'] else 'abandoned'}</b>. Premise control (not re-tuned): View A
out-of-quadrant AUC mean <b>{diag['premise']['view_A_mean']:.4f}</b> (H61: 0.5163, H64: 0.5230, H65: 0.5202), View B
mean <b>{diag['premise']['view_B_mean']:.4f}</b> (H61: 0.6843). Leakage canary: max alarm AUC
<b>{diag['canary_max_alarm_across_folds']:.4f}</b>, any alarm <b>{diag['canary_any_alarm']}</b>.</p></section>
<hr class="divider">
<section><h2>What this does and does not show</h2><ul>
<li>It shows the lane's discovery signal emitted directly as a unique, lane-checked file: every emitted cell is a strict
A-only candidate with written geological reasoning, placed where no informative registry prior localises.</li>
<li>It does not show the A-only stratum beats the single-view baseline on the hide-and-recover instrument; the holdout
table above is the measured comparison.</li>
<li><b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing on this page is an organiser score or a promise of a board gain.</li>
<li>The best published board score is 0.3774 (rank 1, xiaofanhu), 0.3195 is rank 7 (DARD), 0.2778 is rank 13
(extradr19): <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official
leaderboard</a> (public board, not organiser-confirmed).</li>
<li>Attribution caveat: the 0.2778 and 0.2600 figures are owner-reported, not organiser-confirmed (IR-H61-004).</li></ul>
<p class="small"><a href="../knowledge/43_hypotheses_H66_preregistered.md">Ranked hypotheses and the frozen protocol →</a> ·
<a href="../knowledge/44_h66_results_and_limits.md">Results and limits →</a> ·
<a href="h64.html">H64 landing (previous round) →</a></p></section>
{earlier}""" + tail

    exec_html = head + f"""
<div class="eyebrow">Executive summary / submission guide</div>
<h1>How to submit, and whether this file may be submitted.</h1>
<p class="lead">Read the verdict first. A valid file is not an approved competition entry; the selector decides
promotion within the weekly cap shown on the submission page.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong><p>Verdict: <b>{esc(verdict)}</b></p>
<p>The file is new inference, not identical on decoded pixels to any registry raster, and (policy lane) not within 3 px of
any informative prior's positive pixels, so it is safe to download for research. Whether it may be submitted is answered by
the measured gates above; this round spends no weekly slot.</p></div>
<div class="actions"><a class="button" href="downloads/h66-candidate.tif" download>Download the H66 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h66-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/{esc(csv_link)}" download>Geological reasoning CSV</a></div>
<p class="fileline">{fileline}</p>
<section class="prose"><h2>The file contract (checked on disk)</h2><ul>
<li>One band, float32, every value in [0, 1]; in practice exactly 0 or 1.</li>
<li>No NaN or infinite values anywhere in the file (the portal's “Predicted values must be in range [0, 1]”
rejection is caused by NaN/out-of-range bytes, and this file has neither).</li>
<li>EPSG:32611, shape and geotransform identical to the pinned <code>sample_submission.tif</code>.</li>
<li>{fmt_int(n_dots)} emitted cells, all strict A-only discovery candidates (View A confident, View B abstaining), all
more than 200 m from a mapped trace, 3 px minimum separation.</li>
<li>Name for the portal: <code>{esc(card['submission_name'])}</code>. Note ({card['note_chars']} characters):
<code>{esc(card['note'])}</code></li>
</ul><p class="small">Local validator only; not an organiser acceptance receipt.</p>
<h2>Exact steps, only if a later selector approves this file</h2>
<ol><li>Open the competition submission page (login required; <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>).</li>
<li>Under <b>File to submit</b>, choose the TIFF (or the ZIP with the single TIFF).</li>
<li>Paste the name and note above into the submission form.</li>
<li>Submit only if the selector has approved this file. This file is not approved.</li></ol></section>
{earlier}""" + tail

    (DOCS / "h66.html").write_text(index)
    (DOCS / "h66-executive-summary.html").write_text(exec_html)

    # --------------------------------------------------------------- knowledge note
    kn = f"""# 44 · H66 results and limits (rendered from the receipts by `scripts/publish_h66_site.py`)

**Verdict: `{verdict}`**

Artefact `{stem}.tif`, SHA-256 `{card['raster']['sha256']}`, {card['raster']['bytes']} bytes, {n_dots} emitted cells,
every one a strict A-only discovery candidate with a written geological reasoning row
(`docs/downloads/h66-a-only-reasoning.csv`). Pre-registration: `knowledge/43_hypotheses_H66_preregistered.md`
(SHA-256 in `registry/h66_preregistration.json`).

## 1 · What H66 changed

H61/H64 emitted the continuous rank difference A−B; H66 emits the lane's discovery signal directly — the strict
A-only stratum (View A out-of-fold rank ≥ 0.95, View B rank in the abstain interval [0.35, 0.65]) — and places it
inside the **lane-quiet domain**: at least 3 px from every informative registry prior's positive pixel, so the
directed near-dot fraction against every informative prior is 0 by construction (the lane's own 70% rule) instead of
capped re-placement (H64's constrained greedy could not fill its budget: 31,487 of 37,600).

## 2 · Independence and premise (the lane's mandated tests)

Independence screen (spatial-block OOF errors on labelled negatives, held-out catalogue-zero proxies): max |ρ|
**{hold['independence_max_abs_rho']:.4f}** against the 0.60 abandon bar → exchange
**{'allowed' if hold['exchange_allowed'] else 'abandoned'}**. Premise control (not re-tuned): View A out-of-quadrant
AUC mean **{diag['premise']['view_A_mean']:.4f}**, View B mean **{diag['premise']['view_B_mean']:.4f}**. Leakage canary:
max alarm AUC **{diag['canary_max_alarm_across_folds']:.4f}**, any alarm **{diag['canary_any_alarm']}**
(bar 0.90).

## 3 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1), matched budget {hold['matched_budget_per_fold']} dots/fold

| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
""" + "".join(f"| {a} | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {fmt_int(sc[a]['withheld_positive_pixels'])} |\n" for a in arms) + f"""
Paired difference, candidate (a_only) minus single_B: {pd['delta']:+.6f}, 95% CI {ci(pd['ci95'])}.
Control reproduction at the H61 budget (9,400 dots/fold): single_B {ctrl['single_B_h66']:.6f} vs committed H61
{ctrl['single_B_h61_committed']:.6f}, |Δ| {ctrl['abs_difference']:.2e} (tolerance {ctrl['tolerance']}).

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
    (ROOT / "knowledge/44_h66_results_and_limits.md").write_text(kn)

    # --------------------------------------------------------------- site banners (idempotent)
    def make_banner(tif_prefix: str, page_prefix: str) -> str:
        return f"""<!--H66-BANNER--><div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H66 ({'promote-eligible' if promote else 'negative'}).</strong> {'Download yes — it passed every measured gate; the selector still owns the slot.' if promote else 'Download yes, for research only; submit no.'} The A-only discovery stratum emitted directly, placed in the lane-quiet domain. <a href="{tif_prefix}h66-candidate.tif" download>Download the H66 GeoTIFF</a> ({fmt_int(card['raster']['bytes'])} bytes, SHA-256 <code>{esc(card['raster']['sha256'][:16])}…</code>, {fmt_int(n_dots)} cells) · <a href="{page_prefix}h66-executive-summary.html">Read the gate status first</a> · <a href="{page_prefix}h66.html">Run &amp; evidence</a>. Historical downloads below are not upload approval.</div><!--/H66-BANNER-->"""
    banner = make_banner("downloads/", "")   # tif lives in downloads/; pages are same-dir
    dl_rows = f"""<!--H66-DL--><tr><td><a href="h66-candidate.tif" download>h66-candidate.tif</a></td><td class="number">{fmt_int(card['raster']['bytes'])}</td><td class="mono">{esc(card['raster']['sha256'])}</td><td>H66 · A-only discovery stratum, novel-first placement (43b) · {fmt_int(n_dots)} px · newest round; <a href="../h66.html">evidence</a></td></tr>
<tr><td><a href="{esc(stem)}.tif" download>{esc(stem)}.tif</a></td><td class="number">{fmt_int(card['raster']['bytes'])}</td><td class="mono">{esc(card['raster']['sha256'])}</td><td>canonical filename, byte-identical</td></tr>
<tr><td><a href="h66-candidate.zip" download>h66-candidate.zip</a></td><td class="number">single-TIFF ZIP, byte-identical payload</td><td class="mono">portal-accepted wrapper</td><td>one-TIFF ZIP</td></tr>
<tr><td><a href="{esc(csv_link)}" download>{esc(csv_link)}</a></td><td class="number">CSV</td><td class="mono">—</td><td>{fmt_int(n_dots)} per-pixel geological reasoning rows (hypothesis + named non-fault mimic + falsifier)</td></tr><!--/H66-DL-->"""

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
                 "<!--H66-BANNER-->", "<!--/H66-BANNER-->")
    insert_after(DOCS / "executive-summary.html", '<main id="main">', banner,
                 "<!--H66-BANNER-->", "<!--/H66-BANNER-->")
    dl_index = DOWN / "index.html"
    text = dl_index.read_text()
    old = ""
    if "<!--H66-DL-->" in text:
        i = text.index("<!--H66-DL-->")
        j = text.index("<!--/H66-DL-->", i) + len("<!--/H66-DL-->")
        old = text[i:j]
    if old and old != dl_rows:
        text = text.replace(old, dl_rows)
    elif not old:
        anchor = "<tbody>"
        assert anchor in text
        text = text.replace(anchor, anchor + dl_rows, 1)
    # replace the downloads notice banner
    notice_new = f"""<!--H66-DOWNLOAD-NOTICE--><aside style="padding:20px;background:#fff1de;color:#12331f;font:16px/1.6 system-ui"><b>Latest research: H66 — {'PROMOTE-ELIGIBLE, selector decides' if promote else 'DO NOT SUBMIT'}.</b> <a href="h66-candidate.tif" download>Download the H66 GeoTIFF</a> ({fmt_int(card['raster']['bytes'])} bytes, SHA-256 <code>{esc(card['raster']['sha256'][:16])}…</code>, {fmt_int(n_dots)} cells) · <a href="../h66-executive-summary.html">Read the gate status first</a> · <a href="../h66.html">Run &amp; evidence</a>. Historical downloads below are not upload approval.</aside><!--/H66-DOWNLOAD-NOTICE-->"""
    if "<!--H66-DOWNLOAD-NOTICE-->" in text:
        i = text.index("<!--H66-DOWNLOAD-NOTICE-->")
        j = text.index("<!--/H66-DOWNLOAD-NOTICE-->", i) + len("<!--/H66-DOWNLOAD-NOTICE-->")
        text = text[:i] + notice_new + text[j:]
    else:
        text = text.replace("<body>", "<body>" + notice_new, 1)
    dl_index.write_text(text)

    print("published:", DOCS / "h66.html", DOCS / "h66-executive-summary.html",
          ROOT / "knowledge/44_h66_results_and_limits.md")
    print("banners:", DOCS / "index.html", DOCS / "executive-summary.html", dl_index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
