#!/usr/bin/env python3
"""Publish the H60D round to the GitHub Pages site under docs/ — ADDITIVELY.

The round was renamed H60D because a parallel H60 session (H60C) merged to main first and
occupies the plain ``h60`` names (IR-H60D-006).  This publisher therefore:

1. renders ``docs/h60d.html`` — the standalone audit page (full gates, run card, receipts);
2. inserts an H60D block into ``docs/downloads/index.html`` (after the H60C block);
3. inserts a concurrent-round line into ``docs/index.html`` (matching the existing
   concurrent-round convention);
4. inserts an H60D status note into ``docs/executive-summary.html`` (before ``</main>``).

It does NOT touch the top download bar or any other round's section: the CTD5 session owns
the current top slot, and this round is a NEGATIVE research-only result that must not take
it.  The H59 rule is kept: the HTML quotes no number that is not present in a JSON receipt
under ``docs/data/``.  Every holdout number is rendered with its HOLDOUT-DTI label; every
leaderboard number is rendered as owner-reported.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAD = ROOT / "docs/data"
DOCS = ROOT / "docs"


def load(name: str) -> dict:
    return json.loads((DAD / name).read_text())


def pill(kind: str, text: str) -> str:
    return f'<span class="pill {kind}">{text}</span>'


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


NAV = ('<nav><a class="brand" href="{p}index.html">GEMS / DOE 52</a>'
       '<a href="{p}index.html">Overview</a>'
       '<a href="{p}executive-summary.html">Submission guide</a>'
       '<a href="{p}h60d.html" aria-current="page">H60D audit</a>'
       '<a href="{p}h60c.html">H60C audit</a>'
       '<a href="{p}h59.html">H59 audit</a>'
       '<a href="{p}irregularities.html">Limitations</a>'
       '<a href="{p}sources.html">Sources</a>'
       '<a href="{p}downloads/index.html">Downloads</a></nav>')


def nav(prefix: str) -> str:
    return NAV.format(p=prefix)


def header(prefix: str, title: str, desc: str) -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="{esc(desc)}">'
            f'<title>{esc(title)} · GEMSDOE52</title>'
            f'<link rel="stylesheet" href="{prefix}style.css">'
            f'<script src="{prefix}site.js" defer></script></head>\n'
            f'<body><a class="skip" href="#main">Skip to evidence</a>'
            f'<header>{nav(prefix)}</header>\n<main id="main">')


FOOT = ('</main><footer>DOE GEMS competition 306 · Reproducible local research · Predictions '
        'are not verified faults or geothermal discoveries. '
        '<a href="{p}irregularities.html">Limitations</a> · '
        '<a href="{p}sources.html">Sources</a> · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a>'
        '</footer></body></html>')


def foot(prefix: str) -> str:
    return FOOT.format(p=prefix)


def main() -> int:
    sub = load("submission_h60d.json")
    cot = load("h60d_cotrain.json")
    val = load("h60d_validation.json")
    slot = load("h60d_slot_gate.json")
    card = load("h60d_run_card.json")
    fmt = load("h60d_format_gate.json")
    uniq = load("h60d_uniqueness.json")
    lane = load("h60d_lane_gate.json")
    lane_s = load("h60d_lane_surface.json")

    name = sub["submission_name"]
    note = sub["note"]
    fname = sub["file"]
    verdict = sub["verdict"]
    approved = bool(sub["approved_for_weekly_slot"])
    status_pill = (pill("ok", "PROMOTION MET — DOWNLOAD AND SUBMIT")
                   if approved else
                   pill("warn", "NEGATIVE RESULT — OK TO DOWNLOAD FOR REVIEW · "
                                "DO NOT SPEND A WEEKLY SLOT"))
    n_px = sub["nonzero_px"]
    sha = sub["sha256"]
    nbytes = sub["bytes"]
    field = sub["promoted_field"]
    mincat = sub["min_distance_to_catalogue_m"]
    dl_tif = f"downloads/h60d-candidate.tif"
    dl_zip = f"downloads/h60d-candidate.zip"

    # ------------------------------------------------------------------ docs/h60.html (audit)
    ind = cot["independence"]
    canary = cot["leakage_canary"]
    strata = cot["strata"]
    depths = strata["median_depth_to_basement_m"]
    pseudo = cot["cotraining_round"]
    table = val["field_table"]
    gates = val["gates"]
    pooled = val["pooled_dti"]
    shipped = sub["shipped_raster_holdout"]

    rows_html = []
    for fname_, g in sorted(gates.items(), key=lambda kv: -kv[1]["hide37654_fold_mean"]):
        rows_html.append(
            "<tr><td>{}</td><td class=\"number\">{:+.6f}</td>"
            "<td class=\"number\">{:+.6f}</td><td>{}/4 · {}/4</td>"
            "<td>{}</td><td>{}</td></tr>".format(
                esc(fname_), g["mean_lift_vs_random_at_37654"]["tip"],
                g["mean_lift_vs_random_at_37654"]["hide"],
                g["folds_won_vs_random_at_37654"]["tip"],
                g["folds_won_vs_random_at_37654"]["hide"],
                pill("ok", "yes") if g["promotes"] else pill("no", "no"),
                pill("ok", "met") if g["slot_bar_met"] else pill("no", "below +0.005")))
    field_rows = "\n".join(rows_html)

    gate_rows = []
    for label, ok in slot["checks"].items():
        gate_rows.append(f"<tr><td>{esc(label)}</td><td>"
                         f"{pill('ok', 'PASS') if ok else pill('no', 'FAIL')}</td></tr>")
    gate_rows = "\n".join(gate_rows)

    exchange_html = ""
    if pseudo.get("ran"):
        ex = pseudo["exchange"]
        cells = []
        for side in ("A_labels_B", "B_labels_A"):
            e = ex.get(side, {})
            if e.get("ran"):
                cells.append(f"<tr><td>{side}</td><td class=\"number\">{e['n_pseudo_px']}</td>"
                             f"<td class=\"number\">{e['n_segments']}</td>"
                             f"<td class=\"number\">{e['auc_before']:.4f} → "
                             f"{e['auc_after']:.4f}</td>"
                             f"<td class=\"number\">{e['delta_auc']:+.4f}</td></tr>")
            else:
                cells.append(f"<tr><td>{side}</td><td colspan=\"4\">"
                             f"{esc(e.get('reason', 'not run'))}</td></tr>")
        exchange_html = (
            "<h2>The co-training round (H60-3, both directions)</h2>"
            "<div class=\"table-wrap\"><table><thead><tr><th>exchange</th>"
            "<th>pseudo px</th><th>whole segments</th><th>fold-0 AUC before → after</th>"
            "<th>Δ AUC</th></tr></thead><tbody>" + "\n".join(cells) +
            "</tbody></table></div>"
            "<p class=\"small\">Registered correction of the H59 exchange direction: the donor "
            "view's confident predictions label the <b>other</b> view (Blum–Mitchell), not the "
            "donor itself. Whole 8-connected segments, one 50×50 block each, entirely inside "
            "the fold-0 fit region (≥400 m buffer around every held segment), never on a "
            "catalogue or corridor pixel. The paired holdout read of the treated fold is in "
            "<a href=\"data/h60d_validation.json\">h60d_validation.json</a> "
            "(<code>cotreatment</code>).</p>")

    audit = header("", f"H60D audit — co-training with disagreement as the discovery signal",
                   "H60D two-view co-training round: independence test, leakage canary, "
                   "disagreement fields, holdout validation and every gate, rendered from "
                   "the receipts.") + f"""
<div class="eyebrow">H60D · co-training, disagreement as the discovery signal · {status_pill}</div>
<h1>The discovery signal is disagreement.</h1>
<p class="lede">Two views were trained out-of-fold on hide-and-recover whole-segment folds —
View A (potential-field/subsurface: gravity, magnetics, strain, seismicity, depth,
conductivity) and View B (surface: DEM slope/elevation, radiometric total count, restored
1 m LiDAR scarp stack and GeoDAWN radiometrics). The Blum–Mitchell independence premise was
measured, not assumed; the leakage canary ran on every cached layer; and the arms were ranked
by the <b>disagreement itself</b> — <code>pA·(1−pB)</code> and <code>max(pA−pB,0)</code> —
against the single-view baselines and the union incumbent on the exact DTI. The shipped file
is the pure disagreement arm: no credited core, every pixel outside the 200 m ring and outside
all accessible prior support.</p>
<section class="download-bar" aria-label="H60D artifact download">
<div><strong>{esc(fname)}</strong>
<small>{nbytes:,} bytes · single-band float32 · EPSG:32611 · 3,730 × 3,292 ·
all finite · values exactly {{0,1}} — the portal range check cannot trip on this file ·
{n_px:,} emitted px · SHA-256 <code>{esc(sha)}</code></small>
<small>{esc(verdict)}</small></div>
<a class="button" href="{dl_tif}" download>↓ Download the submission TIFF (one click)</a>
<a class="button" href="{dl_zip}" download>↓ Download the one-TIFF ZIP</a></section>
<h2>Premises, measured</h2>
<div class="grid">
<section class="card"><h3>Independence premise</h3>
<p class="metric">{ind['max_abs_correlation']:.4f}</p>
<p class="small">max |correlation| of the two views' per-50×50-block out-of-fold errors on
labelled negatives ({ind['n_blocks']} blocks, {ind['n_negative_predictions']:,} negative
predictions; pixel-level Pearson {ind['pixel_level']['pearson']:+.4f} / Spearman
{ind['pixel_level']['spearman']:+.4f}) against the registered abandonment threshold
{ind['threshold']}. {esc(ind['reason'])}.</p></section>
<section class="card"><h3>Leakage canary</h3>
<p class="metric">{canary['worst_auc']:.4f}</p>
<p class="small">worst single-layer holdout AUC of {canary['n_layers']} cached layers
(layer <code>{esc(canary['worst_layer'])}</code>) against the registered leakage bar
{canary['threshold']}. {esc(canary['verdict'])}</p></section>
<section class="card"><h3>A-only stratum</h3>
<p class="metric">{strata['counts']['a_only']:,}</p>
<p class="small">A-only (buried-structure) px vs {strata['counts']['b_only']:,} B-only
(suspect surface artefact) px; median depth to basement {depths['a_only']:.0f} m under cover
vs {depths['b_only']:.0f} m.</p></section>
</div>
{exchange_html}
<h2>Holdout validation (HOLDOUT-DTI, evaluator version pinned in the receipt)</h2>
<p class="small">Whole-segment hide-and-recover folds (4 folds, 4 px buffer, prevalence 0.002,
seed 20261009), visible catalogue masked pixel-exactly, exact DTI (α 0.2, β 0.8, 300 m
triangular kernel, lattice-exact), isotropic 3 px emitter, budget 37,654 px, identical pool.
HOLDOUT-DTI numbers are relative-instrument readings — never leaderboard scores.</p>
<div class="table-wrap"><table><thead><tr><th>field (arm ranking)</th>
<th>tip lift vs random</th><th>hide lift vs random</th><th>folds won (tip · hide)</th>
<th>promotion</th><th>slot bar</th></tr></thead>
<tbody>
{field_rows}
</tbody></table></div>
<p class="small">Pooled DTI (metric components pooled across folds) and fold-bootstrap 95 % CIs
are in <a href="data/h60d_validation.json">h60d_validation.json</a>; the SHIPPED raster's own
holdout read is <b>hide {shipped['hide']['pooled_dti']:.6f}</b>
(95 % CI {shipped['hide']['ci95_lo']:.6f}–{shipped['hide']['ci95_hi']:.6f},
{shipped['hide']['withheld_positives']:,} withheld positives) and <b>tip
{shipped['tip']['pooled_dti']:.6f}</b> — HOLDOUT-DTI of the exact file on this page.</p>
<h2>Gates on the artifact</h2>
<div class="table-wrap"><table><thead><tr><th>registered gate</th><th>verdict</th></tr></thead>
<tbody>
{gate_rows}
</tbody></table></div>
<h2>Lane drift gate (parallel-run protocol)</h2>
<p class="small">Surface check before placement: max |Spearman| vs any registry raster
<b>{lane_s['surface_max_abs_spearman']:.4f}</b> (bar {lane_s['max_rank_corr']}) —
{pill('ok', 'clean') if lane_s['surface_check_passed'] else pill('no', 'DRIFT')}.
Final-dots check: max |Spearman| <b>{lane['dots_max_abs_spearman']:.4f}</b> (bar
{lane['max_rank_corr']}).  Dots within 3 px of one registry raster's dots:
<b>{lane['dots_max_within_3px_frac']:.4f}</b> raw — that maximum is against
<code>{Path(lane['dots_max_within_3px_prior']).name}</code>, an owner-supplied
CALIBRATION lattice (registry/data_manifest.json id <code>calib_…</code>,
source <code>inputs/calibration/</code>) whose 3-px dilation covers about half the grid,
so any budget-sized placement reads 70-84 % against it by geometry, not duplication.
Registered correction H60-6 excludes calibration rasters from the proximity component
only; the gate value over the {lane['n_priors'] - len(lane['calibration_rasters_excluded_from_proximity'])}
non-calibration priors is <b>{lane['dots_max_within_3px_frac_gate']:.4f}</b>
(bar {lane['max_dots_frac']}) —
{pill('ok', 'clean') if lane['dots_check_passed'] else pill('no', 'DRIFT')}.
Both Spearman components apply to every prior, calibration included; raw readings are
reported per prior in <a href="data/h60_lane_gate.json">the gate receipt</a>.
Uniqueness: decoded pattern distinct from all {uniq['n_priors_checked']} accessible aligned
priors; support novelty {uniq['novel_fraction']:.1%};
not a literal prior union: {str(not uniq['equals_literal_prior_union']).lower()}.
Not merely the union of the two views: {sub['not_merely_union']['outside_union_greedy_px']:,}
of {n_px:,} emitted px lie outside the union field's own greedy emission.</p>
<h2>Run card (lane protocol item 5)</h2>
<div class="table-wrap"><table><tbody>
<tr><td>hypothesis</td><td>{esc(card['hypothesis'])}</td></tr>
<tr><td>mechanism</td><td>{esc(card['mechanism'])}</td></tr>
<tr><td>non-fault processes that could mimic it</td><td>{esc('; '.join(card['named_non_fault_processes_that_could_mimic_it']))}</td></tr>
<tr><td>holdout DTI + CI</td><td>HOLDOUT-DTI hide {shipped['hide']['pooled_dti']:.6f}
(95 % CI {shipped['hide']['ci95_lo']:.6f}–{shipped['hide']['ci95_hi']:.6f},
{shipped['hide']['withheld_positives']:,} withheld positives); tip
{shipped['tip']['pooled_dti']:.6f}; evaluator version pinned by SHA-256 in
<a href="data/h60d_run_card.json">h60d_run_card.json</a></td></tr>
<tr><td>raster sha256</td><td class="mono">{esc(sha)}</td></tr>
<tr><td>validator output</td><td>format problems: {len(fmt['problems'])};
no NaN ({fmt['n_nan'] == 0}); values in [0,1] ({fmt.get('min')}–{fmt.get('max')});
CRS/shape/transform match: {str(fmt['crs'] == 'EPSG:32611' and fmt['width'] == 3292 and fmt['height'] == 3730 and not fmt['problems']).lower()}</td></tr>
<tr><td>submission name</td><td class="mono">{esc(name)}</td></tr>
<tr><td>note (≤140 chars)</td><td>{esc(note)} ({card['submission_note_chars']} chars)</td></tr>
<tr><td>verdict</td><td>{pill('ok', 'promote') if card['verdict'] == 'promote' else pill('warn', 'negative')}</td></tr>
</tbody></table></div>
<h2>Receipts</h2>
<p class="small"><a href="data/h60d_preflight_integrity.json">input integrity (23/23 pins)</a> ·
<a href="data/h60d_cotrain.json">co-training + independence + canary + strata</a> ·
<a href="data/h60_validation.json">holdout validation</a> ·
<a href="data/h60d_build.json">build receipt</a> ·
<a href="data/h60d_format_gate.json">format gate</a> ·
<a href="data/h60d_uniqueness.json">uniqueness gate</a> ·
<a href="data/h60d_lane_gate.json">lane drift gate</a> ·
<a href="data/h60d_slot_gate.json">slot gate</a> ·
<a href="data/h60_run_card.json">run card</a> ·
<a href="data/h60d_preregistration.json">frozen preregistration</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/30_hypotheses_H60D_preregistered.md">hypothesis document</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/31_what_h60D_found.md">what H60D found</a>.</p>
<p class="small">Downloads: <a href="downloads/gems52-h60d-{n_px}px-candidate-geology.csv" download>per-pixel
geology reasoning CSV</a> · <a href="{dl_tif}" download>TIFF</a> ·
<a href="{dl_zip}" download>ZIP</a>. Every emitted pixel carries a written geological
reasoning + falsifier; every A-only candidate segment in the legal pool has a dossier row.
These are hypotheses for Phase-2 review, not verified faults.</p>
""" + foot("")

    (DOCS / "h60d.html").write_text(audit)
    print("wrote docs/h60d.html")

    # ------------------------------------------------- docs/downloads/index.html (additive)
    dl_path = DOCS / "downloads" / "index.html"
    dl = dl_path.read_text()
    h60d_block = (
        f'<hr><h2>H60D — co-training with disagreement as the discovery signal '
        f'(research only)</h2>\n<p><a href="h60d-candidate.tif" download>h60d-candidate.tif</a>'
        f' · <a href="h60d-candidate.zip" download>one-TIFF ZIP</a>'
        f' · <a href="gems52-h60d-{n_px}px-candidate-geology.csv" download>per-pixel geological'
        f' reasoning CSV</a>'
        f' · <a href="gems52-h60d-a-only-candidate-segments.csv" download>A-only segment'
        f' reasoning CSV</a>'
        f' · <a href="../h60d.html">audit</a></p>\n'
        f'<p>{n_px:,} px · sha256 <code>{sha[:16]}…</code> · support novelty '
        f'{uniq["novel_fraction"]:.1%} vs {uniq["n_priors_checked"]} accessible priors · '
        f'pattern unique · not the union field. <b>Download: YES for review. Competition slot:'
        f' NO</b> — NEGATIVE RESULT: the disagreement field does not beat the union or the'
        f' surface view on the holdout; the registered promotion/slot bar was not met.</p>\n')
    assert '</body></html>' in dl, "downloads index: closing body not found"
    assert 'h60d-candidate.tif' not in dl, "downloads index: H60D block already present"
    dl = dl.replace('</body></html>', h60d_block + '</body></html>')
    dl_path.write_text(dl)
    print("updated docs/downloads/index.html (additive H60D block)")

    # ------------------------------------------------------- docs/index.html (additive)
    idx_path = DOCS / "index.html"
    idx = idx_path.read_text()
    anchor = '<details><summary>Preserved research archives'
    assert anchor in idx, "index.html: preserved-archives anchor not found"
    assert 'h60d.html' not in idx, "index.html: H60D line already present"
    idx_line = (
        '<p class="small">A fourth, independent H60-family round is at '
        '<a href="h60d.html">H60D</a> — co-training with disagreement as the discovery '
        'signal, artifact <code>' + esc(fname) + '</code>, '
        '<a href="downloads/h60d-candidate.tif" download>download</a>. '
        'NEGATIVE RESULT — download for review only; do not spend a weekly slot.</p>\n')
    idx = idx.replace(anchor, idx_line + anchor, 1)
    idx_path.write_text(idx)
    print("updated docs/index.html (additive concurrent-round line)")

    # ------------------------------------------- docs/executive-summary.html (additive)
    ex_path = DOCS / "executive-summary.html"
    ex = ex_path.read_text()
    assert '</main>' in ex, "executive-summary: </main> not found"
    assert 'h60d.html' not in ex, "executive-summary: H60D note already present"
    ex_note = (
        '<p class="small"><b>H60D (co-training, disagreement as the discovery signal):</b> '
        'NEGATIVE RESULT — the disagreement field does not beat the union or the surface view '
        'on the holdout; the promotion/slot bar was not met. '
        '<b>Download for review: YES. Competition slot: NO.</b> '
        'Audit: <a href="h60d.html">h60d.html</a> · '
        'TIFF: <a href="downloads/h60d-candidate.tif" download>h60d-candidate.tif</a> · '
        'receipt: <a href="data/submission_h60d.json">submission_h60d.json</a>.</p>\n')
    ex = ex.replace('</main>', ex_note + '</main>', 1)
    ex_path.write_text(ex)
    print("updated docs/executive-summary.html (additive H60D note)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
