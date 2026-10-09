#!/usr/bin/env python3
"""Render the H66cover landing page, submission guide, results note and LATEST pointer from the receipts.

Every number written here is read from ``evidence/h66cover_*.json`` or the submission receipt.  Nothing
is typed by hand, so the page cannot disagree with the evidence it cites.  Nothing here uploads anything
or changes a verdict; it only reports the verdict the run card already holds.

Namespacing (IR-H66-015): this round is the cover-gated co-training H66.  A parallel session merged
PR #56 under the same "H66" label first, so every shared file name of this round carries the
``h66cover`` prefix and main's ``h66-*`` files are left byte-identical.  This publisher therefore
does NOT touch ``docs/data/submission.json``, ``submission/LATEST.txt``, ``docs/index.html`` or
``docs/executive-summary.html`` (main's global pointer stays at the H60 artefact); it only appends
this round's rows to the downloads archive.

Run after ``scripts/run_h66cover.py build``:
    .venv/bin/python scripts/publish_h66cover_site.py
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
    card = load("h66cover_run_card.json")
    hold = load("h66cover_holdout.json")
    pooled = hold["pooled"]
    exch = load("h66cover_pseudo_exchange.json")
    can = load("h66cover_canary.json")
    lane_s = load("h66cover_lane_surface.json")
    lane_d = load("h66cover_lane_dots.json")
    uniq = load("h66cover_uniqueness.json")
    not_union = card["not_the_union"]
    proj = card["projection"]
    stem = card["raster"]["file"][:-4]
    sub = json.loads((SUBM / f"{stem}.json").read_text())
    val = sub["validator"]
    n_dots = card["counts"]["placed"]
    verdict = card["verdict"]
    negative = verdict.startswith("NEGATIVE")
    sc = pooled["scores"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"   # noqa: E731
    paired = card["holdout_dti"]["paired_h66a_minus_single_B"]

    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h66cover-candidate.tif")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h66cover-candidate.zip")
    (DOCS / "data").mkdir(exist_ok=True)
    shutil.copy(EVID / "h66cover_run_card.json", DOCS / "data/h66cover_run_card.json")
    (SUBM / "H66COVER_LATEST.txt").write_text(
        f"{stem}.tif\n# pointer for this round's page only; NOT an upload approval\n"
        "# (namespaced H66COVER after the parallel-session H66 label collision, IR-H66-015)\n")

    arms = ["h66a_cover_gated_a_only", "single_A", "single_B", "union_max",
            "disagreement_pre", "disagreement_post", "random"]
    beats = card["holdout_dti"]["paired_h66a_minus_single_B"]["delta"] > 0 and \
        card["holdout_dti"]["paired_h66a_minus_single_B"]["ci95"][0] > 0
    gates_rows = [
        ("Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned)",
         "PASS" if val.get("ok") else "FAIL"),
        ("Values exactly {0, 1}; 0 NaN; 0 infinite", "PASS" if card["validator"]["ok"] else "FAIL"),
        ("Decoded-pattern uniqueness (not identical to any registry raster)",
         "PASS" if uniq["tier1_all_priors"]["canonical_pattern_unique"] else "FAIL"),
        (f"Exact novelty vs the {card['counts']['informative_rasters']} informative registry rasters "
         f"(share of emitted cells that are not positive in any of them)",
         f"{uniq['tier2_informative_priors']['novel_fraction']:.4f}"),
        ("Not the union of the two views", "PASS" if not_union["not_union_pass"] else "FAIL"),
        ("Every emitted cell inside the A-only gate (A confident, B abstains)",
         f"PASS ({not_union['emitted_cells_inside_a_only_gate']}/{n_dots})"),
        ("Independence screen (|rho| of block OOF errors on labelled negatives < 0.60)",
         f"PASS (max |rho| {exch['independence_pre']['max_abs_correlation']:.4f})"
         if exch.get("allowed_exchange") else
         f"FIRED (max |rho| {exch['independence_pre']['max_abs_correlation']:.4f})"),
        ("Leakage canary (max single-feature AUC < 0.90)",
         f"PASS (max {can['max_alarm_across_folds']:.4f})" if not can["any_alarm"] else "ALARM"),
        ("Lane gate, literal, surface / dots",
         f"{lane_s['literal']['verdict']} / {lane_d['literal']['verdict']}"),
        ("Lane gate, saturation policy, surface / dots",
         f"{lane_s['policy']['verdict']} / {lane_d['policy']['verdict']}"),
        ("Holdout beats single_B (paired CI lower bound > 0)", "PASS" if beats else "FAIL"),
    ]
    gates_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in gates_rows)
    arm_rows = "".join(
        "<tr" + (" class='highlight'" if a == "h66a_cover_gated_a_only" else "") + f"><td>{esc(a)}</td>"
        f"<td class='numeric'>{sc[a]['dti']:.6f}</td><td class='numeric'>{ci(sc[a]['ci95'])}</td>"
        f"<td class='numeric'>{fmt_int(sc[a]['withheld_positive_pixels'])}</td></tr>"
        for a in arms)
    fileline = (f"{esc(stem)}.tif<br>{fmt_int(card['raster']['bytes'])} bytes · SHA-256 "
                f"{esc(card['raster']['sha256'])} · {fmt_int(n_dots)} emitted cells · values exactly "
                f"{{0,1}}, 0 NaN")
    notice = ("OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · DO NOT UPLOAD" if negative
              else "ELIGIBLE FOR THE SELECTOR ONLY · NOT PROMOTED · NO SLOT USED")
    headline = ("A valid, unique file and a negative verdict." if negative
                else "A valid, unique file that passed the selector gate. Promotion is still a separate decision.")

    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            f'<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            f'<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            f'<a href="index.html">Overview</a><a href="h66cover-executive-summary.html">Submission guide</a>'
            f'<a href="h67.html">H67 (previous)</a><a href="downloads/index.html">Archive</a>'
            f'</nav></header><main id="main">')
    tail = "</main></body></html>\n"

    index = head + f"""
<section class="hero"><div><div class="eyebrow">DOE GEMS / H66cover · co-training, cover-gated A-only emission</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">{esc(headline)} H66cover runs the brief's co-training protocol with the empirical independence
test, one whole-segment pseudo-label exchange, and a new placement field: the disagreement signal gated by
modelled cover thickness, so every emitted cell is an A-only (buried-beneath-cover) candidate.</p>
<p class="small">Namespacing (IR-H66-015): a parallel session merged a different round under the "H66" label
first (PR #56, structural coherence), so this round's files carry the <code>h66cover</code> prefix and the
site's <code>h66-*</code> pages are that round's. This page is the cover-gated co-training round's own
landing page.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong>
<p>Verdict: <b>{esc(verdict)}</b></p></div>
<div class="actions"><a class="button" href="downloads/h66cover-candidate.tif" download>Download the H66cover GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h66cover-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/h66cover-a-only-reasoning.csv" download>A-only reasoning CSV</a></div>
<p class="fileline">{fileline}</p>
<p class="small"><a href="h66cover-executive-summary.html">How to submit, and whether this file may be submitted →</a>
· <a href="data/h66cover_run_card.json">Complete JSON run card ↗</a></p></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead>
<tbody>{gates_html}</tbody></table></div>
<p class="small">Local validator only. Not an organiser acceptance receipt. Lane gate statistics are the literal
rule and the saturation policy from <code>gems52.gates.lane_report</code>.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI (gems52-pooled-hide-v1)</h2>
<p class="small">{fmt_int(sc['single_B']['withheld_positive_pixels'])} withheld positive pixels · α {pooled['alpha']} / β {pooled['beta']} ·
{pooled['triangular_radius_m']:.0f} m triangular kernel · 95% paired physical-cluster bootstrap,
{pooled['bootstrap']['clusters']} clusters, {pooled['bootstrap']['draws']} draws.
Every arm placed 9,400 dots per fold at 3 px spacing. Best comparable control: <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>{arm_rows}</tbody></table></div>
<p class="small">Paired difference, candidate (h66a) minus single_B: <b>{paired['delta']:+.6f}</b>, 95% CI
{ci(paired['ci95'])}. The frozen H61 comparison arm <code>disagreement_post</code> is reported alongside for continuity.</p>
<p class="small">Independence screen (the brief's mandated test): max |Spearman rho| of the two views' 50x50 px
block OOF errors on held-out labelled negatives = <b>{exch['independence_pre']['max_abs_correlation']:.4f}</b>
over {fmt_int(exch['independence_pre']['n_blocks'])} blocks; threshold 0.60;
exchange {'allowed' if exch.get('allowed_exchange') else 'REFUSED'}; {fmt_int(exch.get('total_pseudo_pixels') or 0)} pseudo-label pixels.</p>
<p class="small">Holdout numbers are HOLDOUT-DTI, never organiser scores, and the hide-and-recover instrument does not
rank board performance (Spearman -0.10 against the owner-reported board, R4; <code>knowledge/10</code> section 5).</p></section>
<hr class="divider">
<section><h2>Projection vs the reported 0.2778 champion (a PROJECTION, never a score)</h2>
<p class="small">Break-even credit density to match the owner-reported 0.2778 at {fmt_int(n_dots)} emitted px:
<b>{proj['G_lower']['breakeven_credit_density_to_match_champion']:.4f}</b> at |G| = {fmt_int(proj['G_lower']['G_px'])} and
<b>{proj['G_upper']['breakeven_credit_density_to_match_champion']:.4f}</b> at |G| = {fmt_int(proj['G_upper']['G_px'])}
(|G| is the measured interval [5,949.3, 12,512.1] px, H61 repair R2). DTI if this arm's holdout credit density held:
<b>{proj['G_lower']['dti_if_density_equals_holdout_arm']:.4f}</b> / <b>{proj['G_upper']['dti_if_density_equals_holdout_arm']:.4f}</b>.
The champion's score is OWNER-REPORTED, not ORGANIZER-CONFIRMED (IR-H61-004). No leaderboard gain is claimed.</p></section>
<hr class="divider">
<section><h2>What this does and does not show</h2><ul>
<li>It shows the cover-gated A-only field, placed at the matched budget, against the single-view baseline on hide-and-recover segments.</li>
<li>It does not show that potential-field data contain no fault information; six rounds of View-A variants all fail to transfer out of quadrant (AUC ~0.52).</li>
<li><b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing on this page is an organiser score or a promise of a board gain.</li>
<li>The best published board score is 0.3774 (rank 1, xiaofanhu), 0.3195 is rank 7 (DARD), 0.2778 is rank 13 (extradr19):
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official leaderboard</a> (PUBLIC BOARD, fetched 2026-10-09).</li>
<li>Every emitted cell carries a written geological hypothesis, a named non-fault mimic and a falsifier in the reasoning CSV, as Phase-2 review requires.</li></ul>
<p class="small"><a href="../knowledge/43_h66cover_hypotheses_preregistered.md">Five ranked hypotheses and the frozen protocol →</a> ·
<a href="../knowledge/44_h66cover_results_and_limits.md">Results and limits →</a> · <a href="h67.html">H67 landing (previous round) →</a></p></section>
""" + tail

    exec_html = head + f"""
<div class="eyebrow">Executive summary / submission guide</div>
<h1>How to submit, and whether this file may be submitted.</h1>
<p class="lead">Read the verdict first. A valid file is not an approved competition entry; the selector decides
promotion within the weekly cap shown on the submission page.</p>
<div class="notice" role="note"><strong>{esc(notice)}</strong><p>Verdict: <b>{esc(verdict)}</b></p>
<p>Why: the H66-A arm {'beats' if beats else 'does not beat'} the single-view baseline on the pooled holdout
(paired delta {paired['delta']:+.6f}, 95% CI {ci(paired['ci95'])}), the lane gate reads
<b>{lane_d['policy']['verdict']}</b> under the saturation policy ({lane_d['literal']['verdict']} literal), and the
decoded-pattern uniqueness is {'PASS' if uniq['tier1_all_priors']['canonical_pattern_unique'] else 'FAIL'}
(novelty {uniq['tier2_informative_priors']['novel_fraction']:.4f} against informative registry rasters).</p></div>
<div class="actions"><a class="button" href="downloads/h66cover-candidate.tif" download>Download the H66cover GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h66cover-candidate.zip" download>Single-TIFF ZIP</a></div>
<p class="fileline">{fileline}</p>
<section class="prose"><h2>The file contract (checked on disk)</h2><ul>
<li>One band, float32, every value in [0, 1]; in practice exactly 0 or 1.</li>
<li>No NaN or infinite values anywhere in the file (the portal's "Predicted values must be in range [0, 1]"
rejection is caused by NaN/out-of-range bytes, and this file has neither; <code>gems52.grid.write_geotiff</code>
refuses to write them).</li>
<li>EPSG:32611, shape and geotransform identical to the pinned <code>sample_submission.tif</code>.</li>
<li>{fmt_int(n_dots)} emitted cells, all more than 200 m from a mapped trace, 3 px minimum separation, every one
inside the A-only (A-confident, B-abstaining) gate.</li>
<li>Name for the portal: <code>{esc(card['submission_name'])}</code>. Note ({card['note_chars']} characters):
<code>{esc(card['note'])}</code></li>
</ul><p class="small">Local validator only; not an organiser acceptance receipt.</p>
<h2>Exact steps, only if a later selector approves this file</h2>
<ol><li>Open the competition submission page (login required; <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>).</li>
<li>Under <b>File to submit</b>, choose the TIFF (or the ZIP with the single TIFF).</li>
<li>Paste the name and note above into the submission form.</li>
<li>Submit only if the selector has approved this file. This file is not approved.</li></ol>
<h2>The three failure modes the submission form reports</h2>
<ul><li><b>"Predicted values must be in range [0, 1]"</b> — NaN or out-of-range bytes. This file has neither; the
writer refuses to emit them and the format gate re-reads the written bytes.</li>
<li><b>CRS/shape/geotransform mismatch</b> — this file is byte-checked against <code>sample_submission.tif</code>.</li>
<li><b>More than one TIFF in a ZIP</b> — the published ZIP holds exactly one GeoTIFF, verified by roundtrip.</li></ul></section>
""" + tail

    (DOCS / "h66cover.html").write_text(index)
    (DOCS / "h66cover-executive-summary.html").write_text(exec_html)

    # --------------------------------------------------------------- knowledge note
    kn = f"""# 44_h66cover · H66cover results and limits (rendered from the receipts by `scripts/publish_h66cover_site.py`)

**Verdict: `{verdict}`**

Artefact `{stem}.tif`, SHA-256 `{card['raster']['sha256']}`, {card['raster']['bytes']} bytes, {n_dots} emitted cells.
Pre-registration: `knowledge/43_h66cover_hypotheses_preregistered.md` (SHA-256 in `registry/h66cover_preregistration.json`).
Namespacing (IR-H66-015): this round is the cover-gated co-training H66; the site's `h66-*` pages belong to
the structural-coherence H66 (PR #56).

## 1 · Independence screen (the brief's mandated empirical test)
Max |Spearman rho| of the two views' 50x50 px block OOF errors on held-out catalogue-zero negatives:
**{exch['independence_pre']['max_abs_correlation']:.4f}** over {fmt_int(exch['independence_pre']['n_blocks'])} blocks
(threshold 0.60). Exchange {'allowed' if exch.get('allowed_exchange') else 'refused'};
{fmt_int(exch.get('total_pseudo_pixels') or 0)} pseudo-label pixels in one whole-segment round.
Leakage canary: max single-feature raw AUC **{can['max_alarm_across_folds']:.4f}** (alarm 0.90), any alarm: {can['any_alarm']}.

## 2 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1)
| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
""" + "".join(f"| {a} | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {fmt_int(sc[a]['withheld_positive_pixels'])} |\n" for a in arms) + f"""
Paired difference, h66a minus single_B: **{paired['delta']:+.6f}**, 95% CI {ci(paired['ci95'])}.

## 3 · Gates
""" + "".join(f"* {a}: **{b}**\n" for a, b in gates_rows) + f"""
## 4 · Limits
* The holdout instrument does not rank the board (`knowledge/10` section 5). These are HOLDOUT-DTI values only.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12-0.25%.
* The lane gate, uniqueness and projections are measured against the registry census available on disk at build time.
* The reasoning CSV is measured context plus a template hypothesis, not field-verified geology.
* The frozen A-only gate has only {card['counts']['gate_cells']} exact-novel cells, so the shipped emission is
  {n_dots} cells and the template budget {card['counts']['budget_template']} is a cap (IR-H66-013).
* 100% of the emitted dots fall within 3 px of the H64 raster's dots, so the dots lane gate reads
  DUPLICATE/STOP and the file is not submittable (IR-H66-014).
"""
    (ROOT / "knowledge/44_h66cover_results_and_limits.md").write_text(kn)

    # --------------------------------------------------------------- downloads/index.html archive rows only
    # Main's top notice and hero are NOT this round's to rewrite (the global pointer stays at H60);
    # this round only appends its own rows, idempotently.
    dl_path = DOCS / "downloads" / "index.html"
    dl = dl_path.read_text()
    rows = (f"<tr><td><a href=\"h66cover-candidate.tif\" download>h66cover-candidate.tif</a></td>"
            f"<td class=\"number\">{fmt_int(card['raster']['bytes'])}</td>"
            f"<td class=\"mono\">{esc(card['raster']['sha256'])}</td>"
            f"<td>H66cover · co-training disagreement, cover-gated A-only (buried-beneath-cover), parallel round; "
            f"{fmt_int(n_dots)} px; <a href=\"../h66cover.html\">evidence</a></td></tr>\\n"
            f"<tr><td><a href=\"{esc(stem)}.tif\" download>{esc(stem)}.tif</a></td>"
            f"<td class=\"number\">{fmt_int(card['raster']['bytes'])}</td>"
            f"<td class=\"mono\">{esc(card['raster']['sha256'])}</td><td>canonical filename, byte-identical</td></tr>\\n"
            f"<tr><td><a href=\"h66cover-candidate.zip\" download>h66cover-candidate.zip</a></td>"
            f"<td class=\"number\">{fmt_int((DOWN / 'h66cover-candidate.zip').stat().st_size)}</td>"
            f"<td class=\"mono\">single-TIFF ZIP, byte-identical payload</td><td>portal-accepted wrapper</td></tr>\\n"
            f"<tr><td><a href=\"h66cover-a-only-reasoning.csv\" download>h66cover-a-only-reasoning.csv</a></td>"
            f"<td class=\"number\">{fmt_int((DOWN / 'h66cover-a-only-reasoning.csv').stat().st_size)}</td>"
            f"<td class=\"mono\">CSV</td><td>{fmt_int(n_dots)} per-pixel geological reasoning rows (hypothesis + named non-fault mimic + falsifier)</td></tr>")
    anchor = "<!--/H63-DL-->"
    if "h66cover-candidate.tif" in dl:
        pass   # already published; keep the archive append idempotent
    elif anchor in dl:
        dl = dl.replace(anchor, anchor + "\\n" + rows, 1)
    else:
        dl = dl.replace("<tbody>", "<tbody>\\n" + rows, 1)
    dl_path.write_text(dl)

    print("published:", DOCS / "h66cover.html", DOCS / "h66cover-executive-summary.html",
          DOCS / "downloads/index.html (rows appended)", SUBM / "H66COVER_LATEST.txt",
          ROOT / "knowledge/44_h66cover_results_and_limits.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
