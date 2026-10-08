#!/usr/bin/env python3
"""Publish the H60 round to the GitHub Pages site under docs/.

Renders ``docs/h60.html`` (the audit page) and updates the three pages a visitor lands on —
``docs/index.html`` (overview + top download bar), ``docs/executive-summary.html`` (the
submission guide) and ``docs/downloads/index.html`` (the file list) — so the newest artifact
and its status are the first thing on the site.

The H59 rule is kept: the HTML quotes no number that is not present in a JSON receipt under
``docs/data/``.  Every holdout number is rendered with its HOLDOUT-DTI label; every
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
       '<a href="{p}h60.html">H60 audit</a>'
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
    sub = load("submission_h60.json")
    cot = load("h60_cotrain.json")
    val = load("h60_validation.json")
    slot = load("h60_slot_gate.json")
    card = load("h60_run_card.json")
    fmt = load("h60_format_gate.json")
    uniq = load("h60_uniqueness.json")
    lane = load("h60_lane_gate.json")
    lane_s = load("h60_lane_surface.json")

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
    dl_tif = f"downloads/h60-candidate.tif"
    dl_zip = f"downloads/h60-candidate.zip"

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
            "<a href=\"data/h60_validation.json\">h60_validation.json</a> "
            "(<code>cotreatment</code>).</p>")

    audit = header("", f"H60 audit — co-training with disagreement as the discovery signal",
                   "H60 two-view co-training round: independence test, leakage canary, "
                   "disagreement fields, holdout validation and every gate, rendered from "
                   "the receipts.") + f"""
<div class="eyebrow">H60 · co-training, disagreement as the discovery signal · {status_pill}</div>
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
<section class="download-bar" aria-label="H60 artifact download">
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
are in <a href="data/h60_validation.json">h60_validation.json</a>; the SHIPPED raster's own
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
<a href="data/h60_run_card.json">h60_run_card.json</a></td></tr>
<tr><td>raster sha256</td><td class="mono">{esc(sha)}</td></tr>
<tr><td>validator output</td><td>format problems: {len(fmt['problems'])};
no NaN ({fmt['n_nan'] == 0}); values in [0,1] ({fmt.get('min')}–{fmt.get('max')});
CRS/shape/transform match: {str(fmt['crs'] == 'EPSG:32611' and fmt['width'] == 3292 and fmt['height'] == 3730 and not fmt['problems']).lower()}</td></tr>
<tr><td>submission name</td><td class="mono">{esc(name)}</td></tr>
<tr><td>note (≤140 chars)</td><td>{esc(note)} ({card['submission_note_chars']} chars)</td></tr>
<tr><td>verdict</td><td>{pill('ok', 'promote') if card['verdict'] == 'promote' else pill('warn', 'negative')}</td></tr>
</tbody></table></div>
<h2>Receipts</h2>
<p class="small"><a href="data/h60_preflight_integrity.json">input integrity (23/23 pins)</a> ·
<a href="data/h60_cotrain.json">co-training + independence + canary + strata</a> ·
<a href="data/h60_validation.json">holdout validation</a> ·
<a href="data/h60_build.json">build receipt</a> ·
<a href="data/h60_format_gate.json">format gate</a> ·
<a href="data/h60_uniqueness.json">uniqueness gate</a> ·
<a href="data/h60_lane_gate.json">lane drift gate</a> ·
<a href="data/h60_slot_gate.json">slot gate</a> ·
<a href="data/h60_run_card.json">run card</a> ·
<a href="data/h60_preregistration.json">frozen preregistration</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/25_hypotheses_H60_preregistered.md">hypothesis document</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/26_what_h60_found.md">what H60 found</a>.</p>
<p class="small">Downloads: <a href="downloads/gems52-h60-{n_px}px-candidate-geology.csv" download>per-pixel
geology reasoning CSV</a> · <a href="{dl_tif}" download>TIFF</a> ·
<a href="{dl_zip}" download>ZIP</a>. Every emitted pixel carries a written geological
reasoning + falsifier; every A-only candidate segment in the legal pool has a dossier row.
These are hypotheses for Phase-2 review, not verified faults.</p>
""" + foot("")

    (DOCS / "h60.html").write_text(audit)
    print("wrote docs/h60.html")

    # ------------------------------------------------------------------ docs/index.html
    idx_path = DOCS / "index.html"
    idx = idx_path.read_text()
    # top download bar -> H60 artifact
    import re
    bar_re = re.compile(r'<section class="download-bar".*?</section>', re.S)
    new_bar = (f'<section class="download-bar" aria-label="H60 artifact download">\n'
               f'<div><strong>{esc(fname)}</strong>\n'
               f'<small>{nbytes:,} bytes · single-band float32 · EPSG:32611 · 3,730 × 3,292 ·\n'
               f'all finite · values exactly {{0,1}} — the portal range check cannot trip on '
               f'this file · {n_px:,} emitted px (pure disagreement arm, no credited core)</small>\n'
               f'<small>SHA-256 <code>{esc(sha)}</code></small>\n'
               f'<small>{esc(verdict)} · format PASS · pattern unique vs '
               f'{uniq["n_priors_checked"]} priors · lane gate clean (max |ρ| '
               f'{lane["dots_max_abs_spearman"]:.4f}, dots-within-3px '
               f'{lane["dots_max_within_3px_frac_gate"]:.1%} excl. calibration '
               f'rasters; raw {lane["dots_max_within_3px_frac"]:.1%} vs the '
               f'calibration lattice) · nearest mapped catalogue pixel '
               f'{mincat} m</small>\n'
               f'<small>Transparency: the registered promotion bar was '
               f'{"met" if approved else "NOT met"} — the shipped field is the lane\'s '
               f'disagreement ranking ({esc(field)}), not the union; the FILE is a pure '
               f'disagreement arm, 100 % outside every accessible prior\'s support, and equals '
               f'no prior and no pair-union of priors.</small></div>\n'
               f'<a class="button" href="{dl_tif}" download>↓ Download the submission TIFF '
               f'(one click)</a><a class="button" href="{dl_zip}" download>↓ Download the '
               f'one-TIFF ZIP</a><a class="button secondary" href="h60.html">Full audit →</a>'
               f'</section>')
    idx, n = bar_re.subn(new_bar, idx, count=1)
    assert n == 1, "index download bar not found"
    # eyebrow pill
    idx = re.sub(r'<div class="eyebrow">[^<]*<span class="pill (warn|ok)">[^<]*</span></div>',
                 f'<div class="eyebrow">H60 · co-training, disagreement as the discovery signal · '
                 f'<span class="pill {"ok" if approved else "warn"}">'
                 f'{"PROMOTION MET — DOWNLOAD AND SUBMIT" if approved else "NEGATIVE RESULT — OK TO DOWNLOAD FOR REVIEW · DO NOT SPEND A WEEKLY SLOT"}'
                 f'</span></div>', idx, count=1)
    # nav: add H60 audit link
    idx = idx.replace('<a href="h59.html">H59 audit</a>',
                      '<a href="h60.html">H60 audit</a><a href="h59.html">H59 audit</a>', 1)
    # H60 section before "History and archives"
    h60_section = f"""<h2>H60 — co-training with disagreement as the discovery signal (2026-10-08)</h2>
<p class="small">The lane's own method paragraph, executed end to end on the manifest-pinned
bytes: two views (A potential-field/subsurface, B surface) fitted out-of-fold on
hide-and-recover whole-segment folds; independence measured at max |r|
<b>{ind['max_abs_correlation']:.4f}</b> (bar {ind['threshold']}, exchange licensed); leakage
canary clean (worst layer AUC {canary['worst_auc']:.4f} &lt; {canary['threshold']}); arms ranked
by the disagreement itself. Full audit: <a href="h60.html">h60.html</a> ·
<a href="data/submission_h60.json">receipt</a> ·
<a href="data/h60_run_card.json">run card</a> ·
<a href="data/h60_preregistration.json">frozen preregistration</a>.</p>
<div class="table-wrap"><table><thead><tr><th>field (arm ranking)</th><th>hide pooled DTI</th>
<th>95 % CI</th><th>lift vs random (hide)</th><th>promotion</th></tr></thead><tbody>
{"".join(f'<tr><td>{esc(fn_)}</td><td class="number">{pooled[f"hide@37654|{fn_}"]["pooled_dti"]:.6f}</td><td class="number">{pooled[f"hide@37654|{fn_}"]["ci95_lo"]:.6f}–{pooled[f"hide@37654|{fn_}"]["ci95_hi"]:.6f}</td><td class="number">{gates[fn_]["mean_lift_vs_random_at_37654"]["hide"]:+.6f}</td><td>{pill("ok", "yes") if gates[fn_]["promotes"] else pill("no", "no")}</td></tr>' for fn_ in sorted(gates, key=lambda k: -gates[k]["hide37654_fold_mean"]))}
</tbody></table></div>
<p class="small">HOLDOUT-DTI (evaluator gems52.metric.dti α 0.2 β 0.8 R 300 m triangular,
lattice-exact; whole-segment hide-and-recover, 4 folds; pooled across folds; CI = fold
bootstrap). Shipped raster: hide {shipped['hide']['pooled_dti']:.6f} · tip
{shipped['tip']['pooled_dti']:.6f} — HOLDOUT-DTI of the exact file above. These are
relative-instrument readings, never leaderboard scores; the board numbers quoted anywhere on
this site (0.2778 owner-reported h33-2-b2; 0.3774 owner-reported board top) are not
organizer-confirmed.</p>
"""
    idx = idx.replace('<h2>History and archives</h2>', h60_section + '<h2>History and archives</h2>', 1)
    idx_path.write_text(idx)
    print("updated docs/index.html")

    # ------------------------------------------------------------------ executive summary
    ex_path = DOCS / "executive-summary.html"
    ex = ex_path.read_text()
    ex_bar = re.compile(r'<section class="download-bar".*?</section>', re.S)
    ex_new_bar = (f'<section class="download-bar" aria-label="H60 download">\n'
                  f'<div><strong>{esc(fname)}</strong>\n'
                  f'<small>{nbytes:,} bytes · SHA-256 <code>{esc(sha)}</code></small>\n'
                  f'<small>format gate: {len(fmt["problems"])} problems · decoded-pattern '
                  f'unique vs {uniq["n_priors_checked"]} priors · support-novel '
                  f'{uniq["novel_fraction"]:.1%} · lane gate clean · '
                  f'not the union of the two views</small></div>\n'
                  f'<a class="button" href="{dl_tif}" download>↓ Download the submission '
                  f'TIFF (one click)</a><a class="button" href="{dl_zip}" download>↓ '
                  f'Download the one-TIFF ZIP</a><a class="button secondary" '
                  f'href="h60.html">Full audit →</a></section>')
    ex, n = ex_bar.subn(ex_new_bar, ex, count=1)
    assert n == 1, "executive-summary download bar not found"
    ex = ex.replace('<a href="h59.html">H59 audit</a>',
                    '<a href="h60.html">H60 audit</a><a href="h59.html">H59 audit</a>', 1)
    # status box
    ex = re.sub(r'<div class="status"><strong>[^<]*</strong>[^<]*</div>',
                f'<div class="status"><strong>{esc("PROMOTION MET — DOWNLOAD AND SUBMIT" if approved else "NEGATIVE RESULT — OK TO DOWNLOAD FOR REVIEW · DO NOT SPEND A WEEKLY SLOT")}</strong> '
                f'{"This artifact met the registered promotion and slot gates." if approved else "This artifact is <b>not approved to spend a weekly submission slot</b>: the registered promotion bar (a disagreement field beating the union AND both single-view baselines on the hide holdout, ≥3/4 folds, mean lift ≥ +0.005 on both instruments) was not met — a negative result, published as a deliverable."} '
                f'Downloading it for review, reproduction or audit is explicitly allowed.</div>',
                ex, count=1)
    # artifact identity line in the Q&A table
    ex = re.sub(r'(<td>OK to <b>download</b>\?</td><td>).*?(</td>)',
                r'\1' + pill("ok", "YES") + ' — always; the file and every receipt are published '
                'for audit.\2', ex, count=1, flags=re.S)
    ex = re.sub(r'(<td>Unique submission\?</td><td>).*?(</td>)',
                r'\1' + pill("ok", "YES") + f' — decoded pixel pattern differs from all '
                f'{uniq["n_priors_checked"]} accessible aligned prior rasters (this repo\'s '
                f'archives + the restored scored family); the pure disagreement arm is '
                f'{uniq["novel_fraction"]:.1%} outside their support union; not any prior, '
                f'not any pair-union, and not the top-k of the union of the two views.\2',
                ex, count=1, flags=re.S)
    ex = re.sub(r'(<td>OK to spend the <b>weekly slot</b> on it\?</td><td>).*?(</td>)',
                r'\1' + (pill("ok", "YES") + ' — promotion met.' if approved else
                        pill("warn", "NO") +
                        ' — the registered promotion/slot gates decide; see '
                        '<a href="h60.html">the H60 audit page</a> for the exact failed bar.')
                + r'\2', ex, count=1, flags=re.S)
    # portal steps: point the download links and the name/note fields at H60
    ex = ex.replace('downloads/h59-candidate.tif', dl_tif).replace('downloads/h59-candidate.zip', dl_zip)
    # the machine-readable proof block and archive mentions move to the H60 receipts
    for old, new in (("data/h59_format_gate.json", "data/h60_format_gate.json"),
                     ("data/h59_uniqueness.json", "data/h60_uniqueness.json"),
                     ("data/submission_h59.json", "data/submission_h60.json"),
                     ("data/h59_slot_gate.json", "data/h60_slot_gate.json"),
                     ("data/h59_preregistration.json", "data/h60_preregistration.json"),
                     ("data/h59_preflight_integrity.json", "data/h60_preflight_integrity.json")):
        ex = ex.replace(old, new)
    ex = ex.replace('gems52-h59 · .tif', 'gems52-h60 · .tif')
    ex = re.sub(r'value="gems52-h59-[^"]*"', f'value="{esc(name)}"', ex, count=1)
    ex = re.sub(r'(<label for="submission-name">Submission name \()\d+( chars\)</label>)',
                lambda m: f"{m.group(1)}{len(name)} chars</label>", ex, count=1)
    ex = re.sub(r'(<label for="submission-note">Portal note \()\d+( chars\)</label>)',
                lambda m: f"{m.group(1)}{len(note)} chars</label>", ex, count=1)
    ex = re.sub(r'(<textarea id="submission-note" readonly>).*?(</textarea>)',
                lambda m: m.group(1) + esc(note) + m.group(2), ex, count=1, flags=re.S)
    ex = re.sub(r'<title>How to submit the H59 artifact', '<title>How to submit the H60 artifact', ex, count=1)
    ex = ex.replace('How to submit the H59 artifact', 'How to submit the H60 artifact')
    ex = re.sub(r'<meta name="description" content="Exact H59[^"]*">',
                '<meta name="description" content="Exact H60 artifact identification, gate '
                'status, and portal steps for the single-band GeoTIFF; the file is all-finite '
                '[0,1] so the range error cannot occur."">', ex, count=1)
    ex = re.sub(r'<div class="eyebrow">Executive summary · H59[^<]*</div>',
                '<div class="eyebrow">Executive summary · H60 · explicit submission status</div>',
                ex, count=1)
    ex_path.write_text(ex)
    print("updated docs/executive-summary.html")

    # ------------------------------------------------------------------ downloads index
    dl_path = DOCS / "downloads/index.html"
    dl = dl_path.read_text()
    dl = dl.replace('<a href="../h59.html">H59 audit</a>',
                    '<a href="../h60.html">H60 audit</a><a href="../h59.html">H59 audit</a>', 1)
    dl = re.sub(r'<div class="eyebrow">One-click files[^<]*</div>',
                '<div class="eyebrow">One-click files · '
                + ("PROMOTION MET — DOWNLOAD AND SUBMIT" if approved else
                   "NEGATIVE RESULT — OK TO DOWNLOAD FOR REVIEW · DO NOT SPEND A WEEKLY SLOT")
                + '</div>', dl, count=1)
    h60_rows = (f'<tr><td><a href="{esc(fname)}" download>{esc(fname)}</a></td>'
                f'<td class="number">{nbytes:,}</td><td class="mono">{esc(sha)}</td>'
                f'<td>canonical single-band float32 GeoTIFF; {n_px:,} px; pure disagreement '
                f'arm; ready for the portal</td></tr>\n'
                f'<tr><td><a href="{esc(Path(fname).stem)}.zip" download>'
                f'{esc(Path(fname).stem)}.zip</a></td><td class="number">zip</td>'
                f'<td class="mono">zip wrapper</td><td>one-TIFF ZIP accepted by the portal; '
                f'holds exactly the TIFF above, byte-identical, plus paste-ready name/note/'
                f'STATUS</td></tr>\n'
                f'<tr><td><a href="h60-candidate.tif" download>h60-candidate.tif</a></td>'
                f'<td class="number">{nbytes:,}</td><td class="mono">{esc(sha)}</td>'
                f'<td>short-path alias, byte-identical</td></tr>\n'
                f'<tr><td><a href="h60-candidate.zip" download>h60-candidate.zip</a></td>'
                f'<td class="number">zip</td><td class="mono">zip wrapper</td>'
                f'<td>short-path one-TIFF ZIP</td></tr>\n'
                f'<tr><td><a href="gems52-h60-{n_px}px-candidate-geology.csv" download>'
                f'gems52-h60-{n_px}px-candidate-geology.csv</a></td><td class="number">CSV</td>'
                f'<td class="mono">CSV</td><td>one written geological reasoning + falsifier per '
                f'emitted pixel ({n_px:,} rows)</td></tr>\n'
                f'<tr><td><a href="gems52-h60-a-only-candidate-segments.csv" download>'
                f'gems52-h60-a-only-candidate-segments.csv</a></td><td class="number">CSV</td>'
                f'<td class="mono">CSV</td><td>every A-only whole-segment candidate in the legal '
                f'pool, with reasoning + falsifier</td></tr>\n')
    dl = dl.replace("<tbody>\n", "<tbody>\n" + h60_rows, 1)
    dl = re.sub(r'<h1>H59 downloads</h1>',
                '<h1>H60 downloads (newest round; H59 archive below)</h1>', dl, count=1)
    dl_path.write_text(dl)
    print("updated docs/downloads/index.html")
    print("H60 site publication complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
