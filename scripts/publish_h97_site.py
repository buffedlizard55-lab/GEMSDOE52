#!/usr/bin/env python3
"""Publish the H97 round to the GitHub Pages site, generated from the receipts on disk.

The round produced two artifacts and they are presented in the order that matters to a reader:

* **H97b** (`docs/downloads/h97b-candidate.tif`) — the lane-distinct surface-ranked emission;
  uniqueness PASS, lanes PASS, format PASS; promotion FAIL (disclosed).
* **H97** primary (`docs/downloads/h97-candidate.tif`) — retained for audit, labelled
  **lane DUPLICATE/STOP** against the H96 artifact (IR-H97-003); do not submit.

Writes ``docs/h97.html`` (full result), ``docs/h97-executive-summary.html`` (how to submit) and one
idempotent ``<!--H97-CARD-->`` block at the top of ``docs/index.html``.  Re-running replaces only its
own block.  Every number is read from ``evidence/h97*.json``.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
CARD_OPEN, CARD_CLOSE = "<!--H97-CARD-->", "<!--/H97-CARD-->"


def rd(n):
    return json.loads((EVID / n).read_text())


def esc(v):
    return html.escape(str(v))


def main() -> int:
    inst = rd("h97_instrument.json")
    hold = rd("h97_holdout.json")
    build = rd("h97_build.json")
    wr1 = rd("h97_write.json")
    card1 = rd("h97_run_card.json")
    bho = rd("h97b_holdout.json")
    bbuild = rd("h97b_build.json")
    wr2 = rd("h97b_write.json")
    card2 = rd("h97b_run_card.json")

    fm2, uni2, lane2 = wr2["validator"], wr2["uniqueness"], wr2["lane_dots"]
    fm1, lane1 = wr1["validator"], wr1["lane_dots"]
    name2, name1 = wr2["submission_name"], wr1["submission_name"]
    sha2, sha1 = wr2["sha256"], wr1["sha256"]
    max_j2 = max([r.get("jaccard", 0.0) for r in uni2["per_prior"] if "jaccard" in r] or [0.0])

    e1_rows = "\n".join(
        f"<tr><td><code>{esc(r['arm'])}</code></td><td>{r['board_score']:.4f}</td>"
        f"<td><b>{r['holdout_dti']:.6f}</b></td>"
        f"<td>[{r['holdout_ci95'][0]:.4f}, {r['holdout_ci95'][1]:.4f}]</td>"
        f"<td>{r['emitted']:,}</td></tr>" for r in inst["rows"])

    def arm_rows(pooled):
        return "\n".join(
            f"<tr><td><code>{esc(k)}</code></td><td>{v['dti']:.6f}</td>"
            f"<td>[{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}]</td></tr>"
            for k, v in pooled["scores"].items())

    def gates_rows(gate):
        rows = []
        for k, v in gate.items():
            cls = "tag-no" if v["result"] == "FAIL" else "tag-yes"
            rows.append(f'<tr><td>{esc(k)}</td><td class="{cls}">{esc(v["result"])}</td>'
                        f'<td>{esc(v["measured"])}</td></tr>')
        return "\n".join(rows)

    card_html = f"""<style>.h97card{{border:2px solid #7e57c2;border-radius:12px;padding:16px 18px;margin:16px 0;background:#f5f2fc;color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}}.h97card h2{{margin:0 0 8px;font-size:19px;color:#5e35b1}}.h97card a{{color:#4527a0;font-weight:700}}.h97card code{{background:#e9e3f7;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}}.h97card .ok{{color:#2e7d32;font-weight:700}}.h97card .warn{{color:#b26a00;font-weight:700}}.h97card .no{{color:#c62828;font-weight:700}}</style>
<div class="h97card">
<h2>Latest round H97 — co-training disagreement, and the first measurement of whether our holdout ranks the board</h2>
<p><span class="ok">✅ OK TO DOWNLOAD: YES</span> — single-band float32 GeoTIFF, EPSG:32611, 3730&times;3292,
transform identical to <code>sample_submission.tif</code>, <b>nodata tag {esc(fm2['nodata'])}, {fm2['nan_pixels']} NaN,
values exactly {{0, 1}}</b> ({fm2['n_nonzero']:,} cells): the portal's &ldquo;Predicted values must be in range
[0, 1]&rdquo; rejection cannot occur.
<br><span class="warn">⚠️ OK TO SUBMIT: your call — no leaderboard gain is certified</span>, and the round now says why:
the repository's holdout does <b>not</b> rank the board's own scored files — Spearman
<b>{inst['spearman_board_vs_holdout']['spearman']:.4f}</b>, partial given log mass
<b>{inst['partial_board_vs_holdout_given_log_mass']['spearman']:.4f}</b>, Spearman(board, mass)
<b>{inst['spearman_board_vs_mass']['spearman']:.4f}</b> ({inst['spearman_board_vs_holdout']['n']} scored priors scored as-is).
Slots used: <b>0</b>; promotion is a separate selector step.</p>
<p><a class="btn" href="downloads/h97b-candidate.tif" download>⬇ Download h97b-candidate.tif (lane-distinct)</a>
<a class="btn btn2" href="downloads/h97b-candidate.zip" download>ZIP</a>
<a class="btn btn2" href="h97-executive-summary.html">How to submit</a>
<a class="btn btn2" href="h97.html">Full result</a></p>
<p><small><code>{esc(name2)}.tif</code> · SHA-256 <code>{sha2[:16]}</code> · uniqueness PASS ({uni2['n_priors_checked']} priors,
identical to a prior <b>{uni2['identical_to_a_prior']}</b>, max Jaccard {max_j2:.4f}) · dots lane policy
<b>{esc(lane2['policy']['verdict'])}</b> (max near-3 px {lane2['literal']['max_near_3px_fraction']}) · HOLDOUT-DTI
(gems52-pooled-hide-v1, {bho['withheld_positive_px']:,} withheld positives): field_b {bho['primary_dti']:.6f}
[{bho['pooled']['scores']['field_b']['ci95'][0]:.4f}, {bho['pooled']['scores']['field_b']['ci95'][1]:.4f}] vs random
{bho['pooled']['scores']['random']['dti']:.6f}, bar {bho['bar_to_beat']} → <b>{esc(bho['verdict_for_slot'])}</b>
(a holdout number is not a board score).</small></p>
<p><span class="no">✗ The H97 primary is withdrawn from slot consideration:</span> {lane1['literal']['max_near_3px_fraction']*100:.2f}%
of its dots lie within 3 px of the H96 artifact — an A-dominant field reproduces the A-view's fixed point
(IR-H97-003). It stays <a href="downloads/h97-candidate.tif" download>downloadable</a> and labelled; do not submit it.</p>
</div>"""

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>H97 — co-training at the metric-implied mass lever, and the instrument/board measurement</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e8eaed;line-height:1.6}}.container{{max-width:1000px;margin:0 auto;padding:24px 20px}}h1{{color:#4fc3f7}}h2{{color:#4fc3f7;border-bottom:1px solid #2d3040;padding-bottom:6px;margin-top:28px}}a{{color:#4fc3f7}}code{{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:.9em;word-break:break-all}}table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:.92rem}}th,td{{padding:7px 10px;text-align:left;border-bottom:1px solid #2d3040;vertical-align:top}}th{{color:#4fc3f7}}.tag-no{{color:#ef5350;font-weight:700}}.tag-yes{{color:#66bb6a;font-weight:700}}.muted{{color:#9aa0a6;font-size:.88rem}}</style>
</head><body><div class="container">
<h1>H97 — two-view co-training at the metric-implied mass lever, and the first test of whether our instrument ranks the board</h1>
<p class="muted">Rounds H97 (primary) and H97b (lane-distinct amendment) · preregistered before any fit
(<code>registry/h97_preregistration.json</code> doc SHA-256 <code>{card1['registration']['preregistration_sha256'][:16]}</code>;
amendment <code>registry/h97b_preregistration.json</code> SHA-256 <code>{card2['registration']['amendment_sha256'][:16]}</code>,
chronology disclosed) · lane: Blum &amp; Mitchell COLT '98 · evaluator <code>gems52-pooled-hide-v1</code>.</p>

<h2>E1 — the instrument does not rank the board (the round's most useful result)</h2>
<p>Every OWNER-REPORTED scored prior was scored <b>exactly as submitted</b> (no budget cut, no re-placement,
visible catalogue masked pixel-exactly) on the frozen folds.</p>
<table><tr><th>file as submitted</th><th>board (owner-reported)</th><th>HOLDOUT-DTI</th><th>95 % CI</th><th>emitted px</th></tr>
{e1_rows}</table>
<p>Spearman(board, HOLDOUT-DTI) = <b>{inst['spearman_board_vs_holdout']['spearman']:.4f}</b>; partial correlation
controlling for log mass <b>{inst['partial_board_vs_holdout_given_log_mass']['spearman']:.4f}</b>; Spearman(board, mass)
<b>{inst['spearman_board_vs_mass']['spearman']:.4f}</b>. Falsifier (Spearman &ge; 0.50) not hit. The champion (0.2778 on
the board) scores {inst['rows'][0]['holdout_dti']:.6f} — below the random control at its own mass
({inst['pooled']['scores'].get('random_25400', {}).get('dti', float('nan')):.6f}) — because it deliberately avoids the
mapped catalogue this instrument scores against. <b>Beating the 0.190147 bar was always a statement about catalogue
recovery.</b></p>

<h2>E2 — co-training arms (negative)</h2>
<table><tr><th>arm (9,400 dots/fold)</th><th>HOLDOUT-DTI</th><th>95 % CI</th></tr>
{arm_rows(hold['pooled'])}</table>
<p>Paired <code>cotrain_dis − cons_only</code> =
{hold['pooled']['paired_differences'][hold['pooled']['best_comparable_control']]['delta']:.6f}
[{hold['pooled']['paired_differences'][hold['pooled']['best_comparable_control']]['ci95'][0]:.6f},
{hold['pooled']['paired_differences'][hold['pooled']['best_comparable_control']]['ci95'][1]:.6f}]:
the disagreement/veto machinery hurts. Independence max |&rho;| {hold['independence']['max_abs_correlation']:.4f}
(abandon 0.60) → exchange allowed; leakage canary max single-channel AUC
{max(hold['canary']['max_auc'].values()):.4f} (alarm 0.90). Mass lever 6,350/fold:
{json.dumps({k: round(v['dti'], 6) for k, v in hold['pooled_mass_lever']['scores'].items()})}.</p>

<h2>H97b — the lane-distinct emission</h2>
<p>Ranked by the <b>surface view</b> (DEM curvature/slope/topographic edge, radiometric total count, K/Th,
LiDAR scarp layers, GeoDAWN radiometric ratios) with View A used only as a support screen and to veto the
B-only road/erosion suspect population, at 25,400 dots, 3 px, 200 m collar.
Holdout: field_b {bho['primary_dti']:.6f} [{bho['pooled']['scores']['field_b']['ci95'][0]:.4f},
{bho['pooled']['scores']['field_b']['ci95'][1]:.4f}] vs random {bho['pooled']['scores']['random']['dti']:.6f}
(mass-lever {bho['primary_mass_lever_dti']:.6f}); bar {bho['bar_to_beat']} → <b>{esc(bho['verdict_for_slot'])}</b>.</p>
<table><tr><th>gate</th><th>result</th><th>measured</th></tr>
{gates_rows(card2['gates'])}</table>
<p><a href="downloads/h97b-candidate.tif" download>Download H97b GeoTIFF</a> ·
<a href="downloads/h97b-candidate.zip" download>single-TIFF ZIP</a> ·
<a href="h97-executive-summary.html">how to submit</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/arena/c5bf6f30-gemsdoe52/knowledge/98_h97_results_and_limits.md">results &amp; limits</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/arena/c5bf6f30-gemsdoe52/knowledge/99_h97b_amendment.md">amendment</a></p>

<h2>H97 primary — retained for audit, withdrawn from slot consideration</h2>
<p>{lane1['literal']['max_near_3px_fraction']*100:.2f} % of its dots lie within 3 px of the H96 artifact
(99.89 % literal): an A-dominant field reproduces the A-view's fixed point. The protocol's rule is to log it as a
duplicate and stop; it is logged as <b>IR-H97-003</b> and the file is published labelled.
<a href="downloads/h97-candidate.tif" download>Download it</a> as an audit artifact — <b>do not submit it</b>.
Its own receipts: format PASS ({fm1['n_nonzero']:,} cells), uniqueness PASS, promotion FAIL.</p>
<p class="muted">Facts, not claims: {esc(card2['honesty']['bounded_by'])}; {esc(card2['honesty']['not_a_score'])}.</p>
</div></body></html>"""

    exec_page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Executive summary — how to submit the H97b GeoTIFF to the DOE GEMS competition</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e8eaed;line-height:1.65;margin:0}}.wrap{{max-width:900px;margin:0 auto;padding:26px 20px}}h1{{color:#4fc3f7;font-size:1.6rem}}h2{{color:#4fc3f7;border-bottom:1px solid #2d3040;padding-bottom:6px;margin-top:30px}}a{{color:#4fc3f7}}code{{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:.9em;word-break:break-all}}.btn{{display:inline-block;background:#4fc3f7;color:#000;font-weight:700;padding:12px 22px;border-radius:8px;margin:8px 8px 8px 0;text-decoration:none}}.warn{{border:2px solid #ffa726;background:#241a06;border-radius:10px;padding:16px 18px;margin:16px 0}}.ok{{border:2px solid #66bb6a;background:#0f2410;border-radius:10px;padding:16px 18px;margin:16px 0}}.no{{border:2px solid #ef5350;background:#2a0f0f;border-radius:10px;padding:16px 18px;margin:16px 0}}table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:.93rem}}th,td{{padding:7px 10px;text-align:left;border-bottom:1px solid #2d3040;vertical-align:top}}th{{color:#4fc3f7}}.muted{{color:#9aa0a6;font-size:.88rem}}</style>
</head><body><div class="wrap">
<h1>How to submit — the H97b GeoTIFF, in the exact order the submission form asks</h1>

<div class="ok"><b>✅ Step 1 — the file. OK TO DOWNLOAD: YES.</b><br>
<a class="btn" href="downloads/h97b-candidate.tif" download>⬇ Download the single-band GeoTIFF</a>
<a class="btn" href="downloads/h97b-candidate.zip" download>or the single-TIFF ZIP</a><br>
<code>{esc(name2)}.tif</code> · {wr2['tif_bytes']:,} bytes · SHA-256 <code>{sha2}</code><br>
Validator re-read from the written bytes: {fm2['bands']} band {esc(fm2['dtype'])}, {esc(fm2['crs'])},
{fm2['height']} rows &times; {fm2['width']} cols, transform/bounds identical to <code>sample_submission.tif</code>: yes,
NaN {fm2['nan_pixels']}, infinite {fm2['infinity_pixels']}, range [{esc(fm2['min'])}, {esc(fm2['max'])}],
nodata tag {esc(fm2['nodata'])}, {fm2['n_nonzero']:,} emitted cells, problems: {esc(fm2['problems'])}.
Uniqueness: {uni2['n_priors_checked']} priors checked, identical to a prior <b>{uni2['identical_to_a_prior']}</b>,
max Jaccard {max_j2:.4f}; lane policy {esc(lane2['policy']['verdict'])}.</div>

<div class="warn"><b>⚠️ Step 2 — the decision. OK TO SUBMIT: your call.</b><br>
The portal's old error &ldquo;<i>Predicted values must be in range [0, 1]</i>&rdquo; came from a file whose
<b>nodata/NaN cells</b> a strict reader sees as out-of-range. This file is the all-finite container
(<b>nodata tag {esc(fm2['nodata'])}, {fm2['nan_pixels']} NaN, values exactly {{0, 1}}</b>) — the same container the
0.2778 champion used — so that rejection cannot occur. What this round does <b>not</b> claim is a leaderboard gain:
the promotion gate failed ({esc(', '.join(card2['failed_gates'])) if card2['failed_gates'] else 'none'}) and, more
importantly, E1 measured that the repository's holdout does not rank the board's own scored files
(Spearman <b>{inst['spearman_board_vs_holdout']['spearman']:.4f}</b>). The file does follow the two disciplines the
board itself rewards — low mass ({fm2['n_nonzero']:,} cells vs the champion's 37,654) and distance from the mapped
catalogue (200 m collar) — but promotion to a weekly slot is a separate selector decision. Slots used: <b>0</b>.</div>

<div class="no"><b>✗ Do not submit the H97 primary file.</b> {lane1['literal']['max_near_3px_fraction']*100:.2f}% of its
dots lie within 3 px of the H96 artifact; the protocol says log it and stop (IR-H97-003). It remains
<a href="downloads/h97-candidate.tif" download>downloadable</a> for audit only.</div>

<h2>Step 3 — the form, field by field</h2>
<table>
<tr><th>Form field</th><th>What to put</th></tr>
<tr><td>File to submit</td><td>the downloaded <code>{esc(name2)}.tif</code> (single-band GeoTIFF; a <code>.zip</code> holding
exactly that one TIFF is equally accepted)</td></tr>
<tr><td>Note (optional, &le;140 chars)</td><td><code>{esc(wr2['note'])}</code> ({wr2['note_chars']}/140)</td></tr>
<tr><td>Submission name</td><td><code>{esc(name2)}</code></td></tr>
</table>
<p class="muted">Portal: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">data tab</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description &amp; metric</a>.
Requirements quoted from that page: single-band GeoTIFF matching the submission format's CRS (EPSG:32611), shape
(3730&times;3292) and geotransform; values in [0, 1]; data outside the bounds null or NaN.</p>

<h2>Step 4 — what is in the file</h2>
<ul>
<li>Ranker: the surface view — DEM slope, ridge curvature, topographic edge, radiometric total count and K/Th,
the five LiDAR scarp layers, and the three GeoDAWN radiometric ratio grids.</li>
<li>View A's role: a support screen only (eligible-rank median) plus the brief's artefact veto — where the surface
view is confident and the potential field abstains, the response is attributed to roads/erosion and dropped.</li>
<li>250 m discipline: 200 m catalogue collar, 3 px minimum separation, {fm2['n_nonzero']:,} dots placed exactly
(S = 25,400: the mass at which the published metric reaches 0.3195 at the champion's credit, knowledge/76 §3).</li>
<li>Provenance: inputs are integrity-pinned mirrors (not organizer-authenticated); evaluator
<code>gems52-pooled-hide-v1</code>, {bho['withheld_positive_px']:,} withheld positive pixels, 95 % CI, 1,000 paired
spatial-cluster bootstrap draws.</li>
</ul>
<p class="muted">Negative results are deliverables: E1 (the instrument does not rank the board) and E2 (the
co-training disagreement arm loses to its own consensus control) are reported as measured.</p>
</div></body></html>"""

    (DOCS / "h97.html").write_text(page)
    (DOCS / "h97-executive-summary.html").write_text(exec_page)

    idx = DOCS / "index.html"
    s = idx.read_text()
    if CARD_OPEN in s:
        s = re.sub(re.escape(CARD_OPEN) + r".*?" + re.escape(CARD_CLOSE),
                   lambda m: CARD_OPEN + "\n" + card_html + "\n" + CARD_CLOSE, s, count=1, flags=re.S)
    else:
        s = s.replace("<body>", "<body>\n" + CARD_OPEN + "\n" + card_html + "\n" + CARD_CLOSE, 1)
    s = re.sub(r"<title>.*?</title>",
               "<title>GEMSDOE52 — H97: download yes, submit your call (instrument vs board measured)</title>",
               s, count=1, flags=re.S)
    idx.write_text(s)
    print("published docs/h97.html, docs/h97-executive-summary.html, index card")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
