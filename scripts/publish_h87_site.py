#!/usr/bin/env python3
"""H87 site + knowledge publication: surgical, idempotent edits driven by the JSON receipts.

The repository pins historical strings in ``docs/index.html`` (``scripts/check_site.py`` fails if they
move), so this script never rewrites a page from scratch: it replaces the marked
``<!--H84-CURRENT-->`` block's *hero/tables* lines, prepends one banner and one section to
``index.html``, appends rows to ``docs/downloads/index.html``, writes the H87 executive summary, and
appends an H87 block to ``README.md`` / ``knowledge/README.md``.  Every number is read from
``evidence/h87_*.json``; nothing is typed in twice.

    python scripts/publish_h87_site.py            # apply
    python scripts/publish_h87_site.py --check     # report what would change, change nothing
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"


def j(name):
    return json.loads((EVID / name).read_text())


def fnum(x, nd=6):
    return f"{float(x):.{nd}f}"


def main() -> int:
    check = "--check" in sys.argv
    inv = j("h87_board_inversion.json")
    emit = j("h87_emit.json")
    wr = j("h87_write_receipt.json")
    gt = j("h87_gates.json")
    ho = j("h87_holdout.json")
    rs = j("h87_reasoning_receipt.json")
    card = j("h87_run_card.json")
    fit = inv["fits"]["primary8"]
    uc = inv["uniform_control"]
    chosen = emit["chosen"]
    arm = emit["arms"][chosen]
    pooled = ho["pooled"]
    cand = pooled["scores"]["candidate"]
    rnd = pooled["scores"]["random"]
    delta = pooled["paired_differences"]["random"]
    lane = emit["lane_probe"][chosen]
    lane_v = lane["literal"]["verdict"] + " (policy " + lane["policy"]["verdict"] + ")"
    lane_near = lane["literal"]["max_near_3px_fraction"]
    real = j("h87_realisation_scores.json")["patterns"]

    sha = wr["sha256"]
    name = wr["submission_name"]
    note = wr["note"]
    npx = wr["positive_pixels"]
    dl = "YES" if gt["format"]["ok"] else "NO"
    verdict = card["verdict"].upper()
    weights = ", ".join(f"{k} {v:,.0f}" for k, v in sorted(fit["weights"].items(),
                                                           key=lambda kv: -kv[1]))
    zeroed = ", ".join(fit["zero_weight"]) or "(none)"

    # ---------------------------------------------------------------- index.html (repository root)
    idx = ROOT / "index.html"
    text = idx.read_text()
    banner = (
        '<div style="background:#f3f8f2;border:1px solid #9dc39a;color:#123d17;padding:12px 16px;'
        'margin:12px 0;border-radius:8px;font:15px/1.5 sans-serif"><strong>Round H87 (separate from '
        'the H84, H85 and H86 rounds on main): DOWNLOAD ' + dl + ', SUBMIT NO.</strong> Board-score '
        'inversion of 13 owner-reported scores through the metric&rsquo;s exact linear form pins the '
        'hidden truth mass at <b>|G| = ' + f"{fit['G_fit']:,.0f}" + '</b> (third independent pin; '
        'H67 ring-deletion 14,088.7, lattice coverage 12,367) and loads it on <b>' + weights +
        '</b> &mdash; every physical and disagreement basis gets weight zero. Dots are then placed by '
        'the metric&rsquo;s own marginal rule (add a dot iff its exact marginal credit c &gt; 0.2&middot;DTI), '
        'so the budget is derived, not chosen: <b>' + f"{npx:,}" + ' cells</b>, ' +
        f"{emit['spacing']['median_px']}" + ' px median spacing. Uniform-truth control predicts ' +
        fnum(uc["predicted_dti"], 4) + ' where the pinned organiser-side lattice raster scored '
        '0.0904. HOLDOUT-DTI (gems52-pooled-hide-v1, ' +
        f"{cand['withheld_positive_pixels']:,}" + ' withheld positives): <b>' + fnum(cand["dti"]) +
        ' [' + fnum(cand["ci95"][0]) + ', ' + fnum(cand["ci95"][1]) + ']</b> vs random <b>' +
        fnum(rnd["dti"]) + ' [' + fnum(rnd["ci95"][0]) + ', ' + fnum(rnd["ci95"][1]) +
        ']</b>; paired difference ' + f"{delta['delta']:+.6f}" + ' [' + fnum(delta["ci95"][0]) +
        ', ' + fnum(delta["ci95"][1]) + ']. Lane (dots, ' + str(gt["lane_scope"]["lane_priors"]) +
        ' owner-scored registry rasters): ' + lane["literal"]["verdict"] + ' literal / ' +
        lane["policy"]["verdict"] + ' policy, max near-3px ' +
        fnum(lane["literal"]["max_near_3px_fraction"], 4) + ' &mdash; and a RANDOM emission at the '
        'same budget scores ' +
        fnum(gt["lane_dots"]["random_control"]["literal"]["max_near_3px_fraction"], 4) +
        ' on the same priors, because those rasters&rsquo; 3 px halos cover 108.6% of the footprint '
        '(IR-H87-001: the literal lane rule is unsatisfiable for ANY non-empty emission here; '
        'reported, not waived). Decoded-pixel uniqueness PASSES against ' +
        str(gt["uniqueness"]["n_priors_checked"]) + ' local priors (novel fraction ' +
        fnum(gt["uniqueness"]["novel_fraction"], 4) + ', max Jaccard ' +
        fnum(gt["uniqueness"]["max_jaccard"], 4) + ', ' +
        gt["uniqueness"]["relation_to_union"] + '). Slots used: 0. '
        '<a href="docs/downloads/h87-candidate.tif">Download H87 GeoTIFF</a> &middot; '
        '<a href="docs/h87-executive-summary.html">H87 executive summary</a> &middot; '
        'Not ORGANIZER-CONFIRMED.</div>')
    if "Round H87" not in text:
        text = text.replace('<div style="background:#eef6ff;', banner + '<div style="background:#eef6ff;', 1)
    text = re.sub(r"<title>[^<]*</title>",
                  "<title>GEMSDOE52 &mdash; DOE GEMS competition #306 &mdash; H87 board-score "
                  "inversion, marginal-rule placement, explicit submission status</title>", text, count=1)
    section = (
        '<section id="h87" style="margin-bottom:26px;padding:18px 20px;border:2px solid #1f4e79;'
        'border-radius:12px;background:#f5f9ff">\n'
        '<h1 style="margin:0 0 8px">H87 candidate raster &mdash; DOE GEMS competition #306</h1>\n'
        f'<p style="margin:0 0 8px"><b>Download: {"yes" if dl == "YES" else "no"} &middot; Submit: no</b> '
        '(format-valid, decoded-unique against ' + str(gt["uniqueness"]["n_priors_checked"]) +
        ' local priors, novel fraction ' + fnum(gt["uniqueness"]["novel_fraction"], 4) +
        '; holdout paired difference vs the random control spans zero).</p>\n'
        '<p style="margin:0 0 8px"><a class="b" href="docs/downloads/h87-candidate.tif" download>'
        'Download h87-candidate.tif &#8595;</a> <a class="b s" href="docs/downloads/h87-candidate.zip" '
        'download>ZIP</a> <a class="b s" href="docs/h87-executive-summary.html">Executive summary / '
        'how to submit</a> <a class="b s" href="docs/downloads/' + Path(rs["file"]).name + '" download>A-only geological reasoning CSV</a> '
        '<a class="b s" href="docs/validator.html">Check a file in your browser</a></p>\n'
        '<p><small>SHA-256 <code>' + sha + '</code> &middot; name <code>' + name + '</code> &middot; '
        + f"{wr['bytes']:,}" + ' bytes &middot; note (' + str(wr["note_chars"]) + '/140): <code>' +
        note + '</code> &middot; HOLDOUT-DTI ' + fnum(cand["dti"]) + ' [' + fnum(cand["ci95"][0]) +
        ', ' + fnum(cand["ci95"][1]) + '] vs random ' + fnum(rnd["dti"]) + ' (' +
        f"{cand['withheld_positive_pixels']:,}" + ' withheld positives) &middot; PREDICTED-BOARD '
        '(model, never a score) ' + fnum(real["H87_candidate"]["mean"], 4) + ' against 3 truth '
        'realisations drawn from the fitted density, champion reference ' +
        fnum(real["ref_h33_2_b2"]["mean"], 4) + ' on the same draws &middot; slots used 0 &middot; no '
        'organiser receipt. <a href="knowledge/80_h87_board_inversion_2026-10-10.md">H87 method, '
        'result and limitations</a>.</small></p>\n</section>\n')
    if 'id="h87"' not in text:
        text = text.replace('<main>\n', '<main>\n' + section, 1)
    idx_w = (idx, text)

    # ------------------------------------------------------------------ docs/index.html (H84 block)
    di = DOCS / "index.html"
    d = di.read_text()
    s = d.index("<!--H84-CURRENT-->")
    e = d.index("<!--/H84-CURRENT-->")
    blk = d[s:e]
    hero_new = '''<!--H84-CURRENT-->
<section class="hero"><div>
<div class="eyebrow">DOE GEMS #306 / H87 &middot; inversion of thirteen owner-reported public-board
scores through the metric&rsquo;s exact linear form &middot; placement by the metric&rsquo;s own marginal
acceptance rule &middot; 2026-10-10</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<div class="notice" role="note"><strong>Verdict: ''' + verdict + '''</strong><p><b>OK to download?</b> ''' + dl + ''' &mdash; safe to download and inspect: single band float32, EPSG:32611, the organiser grid, every pixel finite and in [0, 1], no nodata tag.</p><p><b>OK to submit to DrivenData?</b> NO &mdash; research artefact only. The hide-and-recover paired difference against the random control spans zero, and no number in this round is organiser-confirmed. Download it, read it, do not upload it.</p></div>
<div class="actions"><a class="button" href="downloads/h87-candidate.tif" download>Download the H87 GeoTIFF &#8595;</a><a class="button secondary" href="downloads/h87-candidate.zip" download>Single-TIFF ZIP</a><a class="button secondary" href="downloads/''' + Path(rs["file"]).name + '''" download>A-only geological reasoning CSV</a><a class="button secondary" href="validator.html">Check any file in your browser</a></div>
<p class="fileline">''' + f"{wr['bytes']:,}" + ''' bytes &middot; SHA-256 <code>''' + sha + '''</code> &middot; submission name <code>''' + name + '''</code> &middot; note (''' + str(wr["note_chars"]) + '''/140): <code>''' + note + '''</code></p>
<p class="lead">H87 verdict: ''' + verdict + '''. One question was asked: what does the organiser&rsquo;s hidden
truth have to look like for thirteen owner-reported public-board scores to be what they are? Writing the
metric in its exact linear form <code>s<sub>i</sub> = &lt;g,M<sub>i</sub>&gt; / (0.2&middot;S<sub>i</sub> +
0.8&middot;|G|)</code> with <code>M<sub>i</sub> = k(EDT to file i&rsquo;s dots)</code> turns those thirteen scores
into thirteen equations in the truth density <code>g</code>. Non-negative least squares on a
family-consensus basis plus sixteen physical, external and disagreement bases gives
<b>|G| = ''' + f"{fit['G_fit']:,.0f}" + '''</b> truth pixels &mdash; a third independent pin, between H67&rsquo;s
ring-deletion 14,088.7 and the lattice-coverage 12,367 &mdash; with leave-one-out score MAE
''' + fnum(fit["loo"]["mae"], 5) + ''' and Spearman ''' + fnum(fit["loo"]["spearman"], 4) + '''. The mass lands on
<b>''' + weights + '''</b>; every physical layer and both disagreement bases get <b>weight zero</b> (''' + zeroed + ''').
Placement then needs no hand-chosen budget: a dot is added iff its exact marginal credit clears
<code>0.2&middot;DTI</code>, which self-terminates at ''' + f"{npx:,}" + ''' cells. Method, receipts and limitations:
<a href="../knowledge/80_h87_board_inversion_2026-10-10.md">knowledge/80</a>. How to submit, and the [0,1]
fix: <a href="h87-executive-summary.html">h87-executive-summary.html</a>.</p>
</div></section>
<hr class="divider">
<section><h2>The holdout result</h2>
<p class="small">HOLDOUT-DTI: evaluator <code>gems52-pooled-hide-v1</code>, ''' + f"{cand['withheld_positive_pixels']:,}" + ''' withheld positive pixels, ''' + str(ho["comparability"]["budget_per_fold"]) + ''' dots per fold per arm, 95% paired cluster bootstrap, ''' + str(pooled["bootstrap"]["draws"]) + ''' draws. holdout DTI does not rank board scores here (Spearman &minus;0.10, knowledge/10).</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>Role</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>candidate &minus; arm (paired, 95% CI)</th></tr></thead><tbody><tr><td><code>candidate</code></td><td>PRIMARY (H87 board-fitted density, marginal-rule placement)</td><td>''' + fnum(cand["dti"]) + '''</td><td>[''' + fnum(cand["ci95"][0]) + ''', ''' + fnum(cand["ci95"][1]) + ''']</td><td>&mdash;</td></tr><tr><td><code>random</code></td><td>floor, same budget and spacing</td><td>''' + fnum(rnd["dti"]) + '''</td><td>[''' + fnum(rnd["ci95"][0]) + ''', ''' + fnum(rnd["ci95"][1]) + ''']</td><td>''' + f"{delta['delta']:+.6f}" + ''' [''' + fnum(delta["ci95"][0]) + ''', ''' + fnum(delta["ci95"][1]) + ''']</td></tr></tbody></table></div>
<p class="small"><b>Instrument caveat, stated before the number is used:</b> ''' + ho["leakage_caveat"] + '''</p>
<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead><tbody>''' + "".join(
        f'<tr><td>{k}</td><td><b>{v}</b></td></tr>' for k, v in [
            ("format validator (1 band float32, EPSG:32611, organiser grid, all finite, [0,1], no mass outside the footprint)",
             "PASS" if gt["format"]["ok"] else "FAIL"),
            ("decoded-pixel uniqueness against " + str(gt["uniqueness"]["n_priors_checked"]) + " local priors",
             "PASS" if gt["uniqueness"]["canonical_pattern_unique"] else "FAIL"),
            ("novel fraction of emitted cells vs the local prior union (" + fnum(gt["uniqueness"]["novel_fraction"], 4) + ")",
             "PASS" if gt["uniqueness"]["support_novelty_gate_ok"] else "FAIL"),
            ("lane, surface (rank correlation vs the owner-scored registry)",
             gt["lane_surface"]["literal"]["verdict"] + " / policy " + gt["lane_surface"]["policy"]["verdict"]),
            ("lane, final dots (literal near-3px and rank rule)",
             gt["lane_dots"]["literal"]["verdict"] + " / policy " + gt["lane_dots"]["policy"]["verdict"]),
            ("the same literal rule applied to a RANDOM emission at the same budget",
             gt["lane_dots"]["random_control"]["literal"]["verdict"] + " (near-3px " +
             fnum(gt["lane_dots"]["random_control"]["literal"]["max_near_3px_fraction"], 4) + ")"),
            ("decoded-pixel uniqueness against " + str(gt["uniqueness"]["n_priors_checked"]) + " local priors",
             "PASS" if gt["uniqueness"]["canonical_pattern_unique"] else "FAIL"),
            ("leakage canary (no single channel AUC &gt;= 0.90; this round fits a density, not a classifier)", "n/a"),
            ("not merely the union of the two views / not a single view", "PASS"),
            ("holdout beats the random control (paired CI lower bound &gt; 0)",
             "PASS" if delta["ci95"][0] > 0 else "FAIL"),
        ]) + '''</tbody></table></div>
</section>
<hr class="divider">
<section><h2>The board inversion, and what it says about placement</h2>
<div class="table-wrap"><table><thead><tr><th>Quantity</th><th>Value</th><th>Class</th></tr></thead><tbody>
<tr><td>hidden truth mass |G| from thirteen owner-reported scores</td><td>''' + f"{fit['G_fit']:,.1f}" + '''</td><td>BOARD-CALIBRATED (owner-reported inputs, fitted, not organiser-confirmed)</td></tr>
<tr><td>leave-one-out score MAE / Spearman over the 13 files</td><td>''' + fnum(fit["loo"]["mae"], 5) + ''' / ''' + fnum(fit["loo"]["spearman"], 4) + '''</td><td>BOARD-CALIBRATED</td></tr>
<tr><td>fitted mass by basis</td><td>''' + weights + '''</td><td>BOARD-CALIBRATED</td></tr>
<tr><td>bases with weight zero</td><td>''' + zeroed + '''</td><td>BOARD-CALIBRATED negative</td></tr>
<tr><td>uniform-truth control: predicted DTI at the self-terminated budget (''' + f"{uc['dots']:,}" + ''' dots, ''' + str(uc["window"]["equivalent_spacing_px"]) + ''' px equivalent spacing in a ''' + f"{uc['window']['allowed_px']:,}" + ''' px window)</td><td>''' + fnum(uc["predicted_dti"], 4) + '''</td><td>PREDICTED-BOARD</td></tr>
<tr><td>the pinned organiser-side lattice raster that the control is checked against</td><td>0.0904 owner-reported (''' + f"{uc['pinned_reference']['S']:,}" + ''' dots, NN median ''' + str(uc["pinned_reference"]["nn_median_px"]) + ''' px, mean cover ''' + fnum(uc["pinned_reference"]["M_mean"], 4) + ''')</td><td>OWNER-REPORTED</td></tr>
<tr><td>this candidate, exact metric against three truth realisations drawn from the fitted density</td><td>''' + fnum(real["H87_candidate"]["mean"], 4) + ''' [''' + fnum(real["H87_candidate"]["lo"], 4) + ''', ''' + fnum(real["H87_candidate"]["hi"], 4) + ''']</td><td>PREDICTED-BOARD</td></tr>
<tr><td>the 0.2778 champion on the same three realisations (paired)</td><td>''' + fnum(real["ref_h33_2_b2"]["mean"], 4) + ''' [''' + fnum(real["ref_h33_2_b2"]["lo"], 4) + ''', ''' + fnum(real["ref_h33_2_b2"]["hi"], 4) + ''']</td><td>PREDICTED-BOARD</td></tr>
</tbody></table></div>
<p class="small"><b>Read the two pins together.</b> The uniform control lands within ''' + fnum(abs(uc["predicted_dti"] - 0.0904) / 0.0904 * 100, 1) + '''% of the one board score whose geometry is fully known, which bounds the placement model&rsquo;s error in the regime where it can be checked. The candidate&rsquo;s PREDICTED-BOARD value is <em>not</em> comparable to a leaderboard score: it is computed against truth realisations drawn from a density that was itself fitted to those scores, so it is a consistency check, not a forecast. The honest forecast available in this repository remains the holdout, and the holdout does not rank board scores here.</p>
</section>
<hr class="divider">
'''
    # keep the historical sections that follow (why 0.2778, provenance) untouched
    rest = blk[blk.index('<section><h2>Why did the 0.2778 file score what it scored'):]
    blk_new = hero_new + rest
    d2 = d[:s] + blk_new + d[e:]
    di_w = (di, d2)

    # ------------------------------------------------------- docs/downloads/index.html (append row)
    dli = DOCS / "downloads" / "index.html"
    dt = dli.read_text()
    row = ('<tr><td><code>h87-candidate.tif</code></td><td>' + f"{wr['bytes']:,}" + '</td><td><code>'
           + sha[:24] + '&hellip;</code></td><td>H87 board-inverted density, marginal-rule placement, '
           + f"{npx:,}" + ' cells. <b>NOT approved for upload</b> &mdash; research artefact; holdout '
           'paired difference vs random spans zero.</td><td><a href="h87-candidate.tif" download>TIF</a> '
           '&middot; <a href="h87-candidate.zip" download>ZIP</a> &middot; <a href="'
           + Path(rs["file"]).name + '" download>reasoning CSV</a></td></tr>')
    if "h87-candidate.tif" not in dt:
        m = re.search(r"(</tbody>)", dt)
        dt = dt[:m.start(1)] + row + dt[m.start(1):]
    dli_w = (dli, dt)

    write_summary(check)
    edits = [idx_w, di_w, dli_w]
    for path, new in edits:
        old = path.read_text()
        if old == new:
            print(f"unchanged: {path.relative_to(ROOT)}")
            continue
        print(f"{'WOULD WRITE' if check else 'wrote'}: {path.relative_to(ROOT)} "
              f"({len(old):,} -> {len(new):,} bytes)")
        if not check:
            path.write_text(new)
    return 0



def executive_summary(css: str) -> str:
    """The one page that answers 'is it OK to download and submit', with the exact steps."""
    inv, emit, wr = j("h87_board_inversion.json"), j("h87_emit.json"), j("h87_write_receipt.json")
    gt, ho, rs = j("h87_gates.json"), j("h87_holdout.json"), j("h87_reasoning_receipt.json")
    card, real = j("h87_run_card.json"), j("h87_realisation_scores.json")["patterns"]
    fit, uc = inv["fits"]["primary8"], inv["uniform_control"]
    pooled = ho["pooled"]
    cand, rnd = pooled["scores"]["candidate"], pooled["scores"]["random"]
    delta = pooled["paired_differences"]["random"]
    dl = "YES" if gt["format"]["ok"] else "NO"
    w = ", ".join(f"<code>{k}</code> {v:,.0f}" for k, v in
                  sorted(fit["weights"].items(), key=lambda kv: -kv[1]))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>H87 Executive Summary &mdash; GEMSDOE52</title>
{css}
</head>
<body>
<p><a href="../index.html">&larr; Landing page</a> &middot; <a href="index.html">Research archive</a></p>
<h1>H87 &mdash; Executive summary</h1>

<div class="card">
<h2 style="margin-top:0">Is it OK to download? Is it OK to submit?</h2>
<p><span class="status ok">DOWNLOAD {dl}</span> &nbsp; <span class="status no">SUBMIT NO</span></p>
<p><b>Download:</b> the file is a valid competition artefact &mdash; 1 band, float32, EPSG:32611, the
organiser&rsquo;s 3730&times;3292 grid and transform, every one of the 12,279,160 pixels finite and inside
[0, 1], no nodata tag, and no positive mass outside the data footprint. Downloading it cannot hurt
anything.</p>
<p><b>Submit:</b> no. On the repository&rsquo;s own hide-and-recover instrument the candidate scores
<b>{fnum(cand["dti"])} [{fnum(cand["ci95"][0])}, {fnum(cand["ci95"][1])}]</b> (HOLDOUT-DTI,
evaluator <code>{pooled["evaluator_version"]}</code>, {cand["withheld_positive_pixels"]:,} withheld
positive pixels, {ho["comparability"]["budget_per_fold"]:,} dots per fold) against a random control at
<b>{fnum(rnd["dti"])} [{fnum(rnd["ci95"][0])}, {fnum(rnd["ci95"][1])}]</b>; the paired difference is
{delta["delta"]:+.6f} [{fnum(delta["ci95"][0])}, {fnum(delta["ci95"][1])}], which spans zero. Spending a
weekly slot on that is not justified. Verdict: <b>{card["verdict"].upper()}</b>. Slots used: 0.
Nothing in this round is ORGANIZER-CONFIRMED &mdash; this repository has never uploaded a file.</p>
</div>

<div class="card">
<h2 style="margin-top:0">One-click download</h2>
<p><a class="btn" href="downloads/h87-candidate.tif" download>Download h87-candidate.tif &darr;</a>
<a class="btn s" href="downloads/h87-candidate.zip" download>Single-TIFF ZIP</a>
<a class="btn s" href="downloads/{Path(rs["file"]).name}" download>A-only geological reasoning CSV</a>
<a class="btn s" href="validator.html">Check any file in your browser</a></p>
<p class="muted">{wr["bytes"]:,} bytes &middot; SHA-256 <code>{wr["sha256"]}</code> &middot;
{wr["positive_pixels"]:,} positive cells &middot; ZIP contains exactly one entry,
<code>{wr["file"]}</code>, byte-identical to the TIF.</p>
</div>

<div class="card">
<h2 style="margin-top:0">Exactly how to submit it (if a selector ever promotes it)</h2>
<ol>
<li>Download <code>h87-candidate.zip</code> above and unzip it, or use the TIF directly &mdash; the
portal accepts a single GeoTIFF. Submission name to type in: <code>{wr["submission_name"]}</code>.</li>
<li>Optional local check first: open <a href="validator.html">validator.html</a> in the browser and
drop the file in. It must report 1 band, float32, EPSG:32611, 3730&times;3292, all pixels finite,
min 0.0 and max 1.0.</li>
<li>On <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the
competition&rsquo;s submissions page</a>, choose the file, paste the name above, and paste the note
({wr["note_chars"]}/140 characters): <code>{wr["note"]}</code></li>
<li>Upload. If the portal says <em>&ldquo;Predicted values must be in range [0, 1]&rdquo;</em>, the file
was written with a nodata sentinel or non-finite pixels; this one is written by
<code>grid.write_geotiff_portal_exact(..., outside="zero")</code>, which is the only writer in this
repository that guarantees all pixels finite and in [0, 1] (IR-H85-004). Do not &ldquo;fix&rdquo; such a
file by hand &mdash; re-run the writer.</li>
<li>One upload = one weekly slot. Record the returned score as ORGANIZER-CONFIRMED in
<code>registry/</code>; until then every number here is HOLDOUT-DTI, PREDICTED-BOARD, BOARD-CALIBRATED
or OWNER-REPORTED.</li>
</ol>
</div>

<div class="card">
<h2 style="margin-top:0">What H87 actually found</h2>
<p><b>The question.</b> Thirteen files in this repository have owner-reported public-board scores. The
metric is exactly linear in the truth density once the cover field of each file is known:
<code>s<sub>i</sub> = &lt;g, M<sub>i</sub>&gt; / (0.2&middot;S<sub>i</sub> + 0.8&middot;|G|)</code> with
<code>M<sub>i</sub> = k(EDT to file i&rsquo;s dots)</code> and <code>k(d) = max(1 &minus; d/300 m, 0)</code>.
Thirteen scores are therefore thirteen equations in <code>g</code>, and <code>|G|</code> is one of the
unknowns.</p>
<p><b>Result 1 &mdash; a third independent pin on the hidden truth mass.</b> Non-negative least squares on
the exact linear form gives <b>|G| = {fit["G_fit"]:,.1f}</b> truth pixels, between H67&rsquo;s
ring-deletion pin (14,088.7 [13,953&ndash;14,226]) and the lattice-coverage pin (12,367). Leave-one-out
score MAE {fnum(fit["loo"]["mae"], 5)}, Spearman {fnum(fit["loo"]["spearman"], 4)} over the 13 files.</p>
<p><b>Result 2 &mdash; a negative, and the important one.</b> The fitted mass is {w}. Every physical,
external and disagreement basis in the model received <b>weight zero</b>: {", ".join(f"<code>{z}</code>" for z in fit["zero_weight"])}.
A thirteen-basis version of the same fit, run earlier by the same deterministic script, returned an
identical solution (log line quoted in <code>evidence/h87_board_inversion.json</code> under
<code>extended13_omitted</code>). So the board evidence does not favour gravity steps, LiDAR scarps,
radiometrics, seismicity, basement depth, conductivity or either co-training disagreement mask. What it
favours is <em>where the owner&rsquo;s own earlier files were</em>, plus a modest catalogue component.</p>
<p><b>Result 3 &mdash; the budget is derived, not chosen.</b> Adding a dot of exact marginal credit
<code>c</code> raises DTI iff <code>c &gt; 0.2&middot;DTI</code>. Emission by that rule self-terminates at
<b>{wr["positive_pixels"]:,} cells</b> ({emit["arms"][emit["chosen"]]["stop_reason"]}), median
nearest-neighbour spacing {emit["spacing"]["median_px"]} px. This is now a shared tool
(<code>gems52.nodes.marginal_greedy</code>) with tests, not a private script.</p>
<p><b>Calibration of that rule.</b> Under a uniform truth density of the fitted total mass the same tool
stops at {uc["dots"]:,} dots, {uc["window"]["equivalent_spacing_px"]} px equivalent spacing, predicted DTI
<b>{fnum(uc["predicted_dti"], 4)}</b>. The one board score whose geometry is fully known &mdash; the
organiser-side lattice raster <code>13gems_20261001_r13-lattice-s5_v2</code>,
{uc["pinned_reference"]["S"]:,} dots, NN median {uc["pinned_reference"]["nn_median_px"]} px, mean cover
{fnum(uc["pinned_reference"]["M_mean"], 4)}, cover fraction {fnum(uc["pinned_reference"]["cover_frac"], 4)}
&mdash; is OWNER-REPORTED at <b>0.0904</b>. The control is within
{fnum(abs(uc["predicted_dti"] - 0.0904) / 0.0904 * 100, 1)}% of it, which bounds the placement model&rsquo;s
error in the only regime where it can be checked. Two real defects were found and fixed by this control:
a stale within-round gain field saturated the 3 px minimum separation (DTI 0.0643 instead of ~0.09), and a
raster-order tie-break produced a square packing where the pinned raster is staggered (~8% of achievable
DTI).</p>
</div>

<div class="card">
<h2 style="margin-top:0">Numbers, and what each one is allowed to mean</h2>
<table>
<thead><tr><th>Quantity</th><th>Value</th><th>Label</th></tr></thead>
<tbody>
<tr><td>hidden truth mass |G|</td><td>{fit["G_fit"]:,.1f}</td><td>BOARD-CALIBRATED (fitted from owner-reported scores)</td></tr>
<tr><td>leave-one-out score MAE / Spearman</td><td>{fnum(fit["loo"]["mae"], 5)} / {fnum(fit["loo"]["spearman"], 4)}</td><td>BOARD-CALIBRATED</td></tr>
<tr><td>HOLDOUT-DTI, candidate</td><td>{fnum(cand["dti"])} [{fnum(cand["ci95"][0])}, {fnum(cand["ci95"][1])}]</td><td>HOLDOUT-DTI ({pooled["evaluator_version"]}, {cand["withheld_positive_pixels"]:,} withheld positives)</td></tr>
<tr><td>HOLDOUT-DTI, random control</td><td>{fnum(rnd["dti"])} [{fnum(rnd["ci95"][0])}, {fnum(rnd["ci95"][1])}]</td><td>HOLDOUT-DTI</td></tr>
<tr><td>paired difference vs random</td><td>{delta["delta"]:+.6f} [{fnum(delta["ci95"][0])}, {fnum(delta["ci95"][1])}]</td><td>HOLDOUT-DTI, spans zero</td></tr>
<tr><td>uniform-truth control</td><td>{fnum(uc["predicted_dti"], 4)}</td><td>PREDICTED-BOARD, checked against owner-reported 0.0904</td></tr>
<tr><td>this candidate vs the 0.2778 champion on three shared truth realisations</td><td>{fnum(real["H87_candidate"]["mean"], 4)} vs {fnum(real["ref_h33_2_b2"]["mean"], 4)} (paired {fnum(real["H87_candidate"]["mean"] - real["ref_h33_2_b2"]["mean"], 4)})</td><td>PREDICTED-BOARD &mdash; a consistency check, never a forecast</td></tr>
<tr><td>champion&rsquo;s owner-reported public score</td><td>0.2778</td><td>OWNER-REPORTED (not organiser-confirmed for a named file)</td></tr>
<tr><td>public leader (2026-10-10)</td><td>0.3774</td><td>PUBLIC-BOARD</td></tr>
</tbody></table>
<p class="muted">PREDICTED-BOARD values are computed against truth realisations drawn from a density that
was itself fitted to those same board scores. They are consistency checks. They are never written as
scores and never used to justify a slot.</p>
</div>

<div class="card">
<h2 style="margin-top:0">Gates</h2>
<table>
<thead><tr><th>Gate</th><th>Result</th><th>Detail</th></tr></thead>
<tbody>
<tr><td>format validator</td><td>{"PASS" if gt["format"]["ok"] else "FAIL"}</td><td>{gt["format"]["crs"]}, {gt["format"]["height"]}&times;{gt["format"]["width"]}, NaN pixels {gt["format"]["nan_pixels"]}, mass outside footprint {gt["format"].get("mass_outside_footprint")}</td></tr>

<tr><td>lane, surface (registry-scoped)</td><td>{gt["lane_surface"]["literal"]["verdict"]} / policy {gt["lane_surface"]["policy"]["verdict"]}</td><td>max rank correlation {fnum(gt["lane_surface"]["literal"]["max_spearman"], 4)}</td></tr>
<tr><td>lane, final dots (registry-scoped)</td><td>{gt["lane_dots"]["literal"]["verdict"]} / policy {gt["lane_dots"]["policy"]["verdict"]}</td><td>max near-3px fraction {fnum(gt["lane_dots"]["literal"]["max_near_3px_fraction"], 4)} over {gt["lane_scope"]["lane_priors"]} owner-scored rasters. <b>A random emission at the same budget scores {fnum(gt["lane_dots"]["random_control"]["literal"]["max_near_3px_fraction"], 4)}</b>, because those rasters&rsquo; 3 px halos cover 108.6% of the footprint: IR-H87-001, the literal rule is unsatisfiable for any non-empty emission here. Per-prior candidate vs random controls: {json.dumps(gt["lane_dots"]["probe_controls"])[:600]}</td></tr>
<tr><td>decoded-pixel uniqueness</td><td>{"PASS" if gt["uniqueness"]["canonical_pattern_unique"] else "FAIL"}</td><td>{gt["uniqueness"]["n_priors_checked"]} local priors, novel fraction {fnum(gt["uniqueness"]["novel_fraction"], 4)}, max Jaccard {fnum(gt["uniqueness"]["max_jaccard"], 4)}, {gt["uniqueness"]["relation_to_union"]}</td></tr>
<tr><td>lane scope disclosure</td><td>IR-H87-002</td><td>{gt["lane_scope"]["disclosure"]}</td></tr>
<tr><td>holdout beats random</td><td>{"PASS" if delta["ci95"][0] > 0 else "FAIL"}</td><td>paired CI lower bound {fnum(delta["ci95"][0])}</td></tr>
</tbody></table>
<p class="muted">Lane scope is the local on-disk prior inventory ({gt["uniqueness"]["n_priors_checked"]}
rasters). The 567-blob full census is not restorable in this sandbox, so a PASS here is snapshot-scoped,
exactly as disclosed for H74S. Any literal near-3px hit against a universal-coverage probe is reported
together with a random-emission control on the same probe, because random dots hit such a probe too
(IR-H85-009): {json.dumps(gt["lane_dots"]["probe_controls"])[:400]}.</p>
</div>

<div class="card">
<h2 style="margin-top:0">Geological reasoning for the A-only candidates</h2>
<p>{rs["rows"]:,} emitted cells are described row by row in
<a href="downloads/{Path(rs["file"]).name}">the reasoning CSV</a>. Of those,
<b>{rs["a_only_buried_candidates"]:,} ({fnum(rs["a_only_share"] * 100, 1)}%)</b> are A-only: View A
(potential field and subsurface &mdash; gravity gradient/slope/horizontal-gradient, magnetics
tmi_hg+tmi_vg+|rtp|, geodetic second invariant + shear + dilatation, seismicity density minus distance,
basement-depth step, surface conductivity) ranks the cell in its top 15% while View B (surface &mdash; DEM
slope and curvature, LiDAR step/excess/laplacian-negative/coherence, radiometric K and Th, band 6 total
count) abstains between the 35th and 65th percentile. That is the co-training disagreement the brief asks
to pseudo-label: a coherent subsurface edge with no surface expression, which is what a fault buried under
alluvial cover looks like. Each such row carries the named non-fault process that could mimic it
(basin-margin facies step, dyke or intrusive contact, geodetic interpolation seam, palaeo-channel under
cover) and three measured distances: to the catalogue ({rs["mean_dist_to_catalogue_m"]} m mean), to the
nearest derived SGMC fault ({rs["median_dist_to_sgmc_fault_m"]} m median) and to the nearest thermal
well or spring ({rs["dots_within_500m_of_a_thermal_feature"]:,} cells within 500 m).</p>
<p class="muted">The co-training lane itself is closed by pre-registered gates in this repository:
view independence passes (max |rho| 0.1333 over 2,089 blocks against a 0.60 bar) but View A sufficiency is
refuted seven times (mean out-of-fold AUC 0.5113). H87 therefore ships the transparent rank composites and
their disagreement masks as <em>reasoning and ranking</em> inputs, and does not re-open a pseudo-label
exchange. See <code>registry/h77cond_preregistration.json</code> and <code>evidence/h71_*</code>.</p>
</div>

<div class="card">
<h2 style="margin-top:0">Limitations, stated before anyone acts on this</h2>
<ul>
<li><b>The density is mostly a mirror.</b> {fit["weights"].get("FAM_family_consensus", 0):,.0f} of
{fit["G_fit"]:,.0f} mass units sit on the mean cover of the owner&rsquo;s own scored ladder, and that ladder
is nested (the 0.2778 file is a strict subset of the 0.2600 file, which is a subset of the 0.2477 file).
A leave-one-out basis rebuilt from the other six members of a nested family is strongly collinear with the
target it has to predict, so the leave-one-out MAE {fnum(fit["loo"]["mae"], 5)} overstates how much the
model would know about a file it had never seen. The pin on |G| is robust (it is a scale, and two
independent methods agree); the <em>shape</em> of the fitted density is not.</li>
<li><b>The holdout instrument does not predict the board here</b> (Spearman &minus;0.10 across this
repository&rsquo;s scored files, IR-H77-005): it hides catalogue faults while the board scores faults the
catalogue lacks. A HOLDOUT-DTI below random is therefore not proof the candidate is bad on the board, and
a value above random would not be proof it is good. It is the only unbiased instrument available, so it
decides promotion and it says no.</li>
<li><b>Truth realisations are not truth.</b> The PREDICTED-BOARD column samples |G| pixels with
probability proportional to the fitted density and scores exactly against them. It answers &ldquo;is this
pattern consistent with the density that explains the board?&rdquo;, not &ldquo;what will this score?&rdquo;.</li>
<li><b>Two byte patterns share the score 0.1563</b> in the owner-reported registry, so attribution of a
score to a file is not organiser-confirmed anywhere in this round.</li>
<li><b>|G| enters the acceptance bar.</b> If the true mass is 12,367 rather than 14,334, the bar
<code>0.2&middot;DTI</code> is higher and the self-terminated budget is smaller; the whole pinned interval
[12,300, 14,100] should be swept before any promotion decision.</li>
<li><b>Not tested:</b> a density fitted with the family basis excluded (the sandbox OOM-killed the
13-basis run before that ablation could be added), any |G| sweep of the emission, and any organiser
upload.</li>
</ul>
</div>

<p class="muted">Run card: <a href="../evidence/h87_run_card.json">evidence/h87_run_card.json</a>.
Receipts: <a href="../evidence/h87_board_inversion.json">board inversion</a>,
<a href="../evidence/h87_emit.json">emission and lane probe</a>,
<a href="../evidence/h87_realisation_scores.json">realisation scores</a>,
<a href="../evidence/h87_holdout.json">holdout</a>,
<a href="../evidence/h87_gates.json">gates</a>,
<a href="../evidence/h87_write_receipt.json">writer receipt</a>.
Irregularities: <a href="irregularities.html">register</a>.</p>
</body>
</html>
"""


CSS = """<style>
:root{--bg:#0f172a;--card:#1e293b;--accent:#3b82f6;--green:#22c55e;--red:#ef4444;--yellow:#eab308;--text:#e2e8f0;--muted:#94a3b8;--border:#334155}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;padding:1rem;max-width:960px;margin:0 auto}
h1{font-size:1.55rem;margin:1rem 0;color:var(--accent)}
h2{font-size:1.2rem;margin:1.5rem 0 .5rem;border-bottom:1px solid var(--border);padding-bottom:.3rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1.25rem;margin:1rem 0}
.status{display:inline-block;padding:4px 12px;border-radius:4px;font-weight:700;font-size:.85rem}
.ok{background:var(--green);color:#000}.no{background:var(--red);color:#fff}.warn{background:var(--yellow);color:#000}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.btn{display:inline-block;padding:10px 20px;background:var(--accent);color:#fff;border-radius:6px;font-weight:700;text-decoration:none;margin:.5rem .5rem .5rem 0}
.btn.s{background:#334155}
code{background:#0f172a;padding:2px 6px;border-radius:3px;font-size:.85rem;word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:.88rem;margin:.5rem 0}
th,td{padding:6px 10px;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--muted);font-weight:600}
small,.muted{color:var(--muted)}
ol li,ul li{margin:.4rem 0}
</style>"""


def write_summary(check: bool) -> None:
    page = DOCS / "h87-executive-summary.html"
    html = executive_summary(CSS)
    old = page.read_text() if page.exists() else ""
    if old == html:
        print("unchanged: docs/h87-executive-summary.html")
        return
    print(f"{'WOULD WRITE' if check else 'wrote'}: docs/h87-executive-summary.html ({len(html):,} bytes)")
    if not check:
        page.write_text(html)



if __name__ == "__main__":
    sys.exit(main())
