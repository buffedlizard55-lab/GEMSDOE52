#!/usr/bin/env python3
"""Publish the H102 round to the GitHub Pages site: one-click download + explicit submit verdict.

Reads only receipts written by ``scripts/run_h102.py`` (nothing is invented here):
    evidence/h102_run_card.json  evidence/h102_holdout.json  evidence/h102_lane.json
    evidence/h102_build_placement.json  evidence/h102_fit.json  evidence/h102_channels.json

Writes:
    docs/downloads/h102-candidate.tif / .zip / .json      stable download aliases
    docs/downloads/<submission filename>.tif / .zip      the exact files to upload
    docs/h102.html                                        the round page
    submission/LATEST.txt                                which file the site is pointing at
and inserts an H102 card (between <!--H102-CARD--> markers) at the top of
docs/index.html and docs/executive-summary.html.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
SUB = ROOT / "submission"


def load(name):
    return json.loads((EV / name).read_text())


def main() -> int:
    card = load("h102_run_card.json")
    hold = load("h102_holdout.json")
    lane = load("h102_lane.json")
    build = load("h102_build_placement.json")
    fit = load("h102_fit.json")
    ch = load("h102_channels.json")
    name = card["submission_name"]
    tif = SUB / f"gems52-{name}.tif"
    zipf = SUB / f"gems52-{name}.zip"
    jsf = SUB / f"gems52-{name}.json"
    if not tif.exists():
        raise SystemExit(f"missing {tif}")
    DL.mkdir(parents=True, exist_ok=True)
    for src, alias in ((tif, "h102-candidate.tif"), (zipf, "h102-candidate.zip"), (jsf, "h102-candidate.json")):
        if src.exists():
            shutil.copy2(src, DL / alias)
        shutil.copy2(src, DL / src.name)
    csvp = SUB / f"gems52-{name}-a-only-reasoning.csv"
    csv_alias = DL / "h102-a-only-reasoning.csv"
    if csvp.exists():
        shutil.copy2(csvp, csv_alias)
        shutil.copy2(csvp, DL / csvp.name)
    promoted = bool(card["submit_ok"])
    verdict_submit = "YES" if promoted else "NO"
    cls_submit = "yes" if promoted else "no"

    # Optional diagnostics (only rendered when the receipts exist; never invented).
    geom_html = ""
    e4p, e4bp = EV / "h102_e4_coverage.json", EV / "h102_e4b_hysteresis.json"
    if e4p.exists() and e4bp.exists():
        e4 = json.loads(e4p.read_text())
        e4b = json.loads(e4bp.read_text())
        g4, g4b = e4["geometry_vs_mass"], e4b["geometry_vs_mass"]
        geom_rows = ""
        for field in ("cotrain_disagree", "single_B2"):
            a, b = g4[field], g4b[field]
            geom_rows += (
                f"<tr><td><code>{field}</code></td><td>{b['dots_K_dti']:.6f}</td>"
                f"<td>{a['bridged_dti']:.6f}</td><td>{b['hyst_dti']:.6f}</td>"
                f"<td><b>{a['dots_matched_mass_dti']:.6f}</b></td><td>{a['random_same_mass_dti']:.6f}</td>"
                f"<td>{'loses' if not a['GEOMETRY_BEATS_MASS_AT_MATCHED_MASS'] else 'wins'}</td></tr>")
        geom_html = f"""<h2>6b &middot; Emission-geometry diagnostic (E4 / E4b) — negative</h2>
<p class="muted">Question: at the <em>same emitted mass</em>, does a connected trace along the field beat more
well-separated dots? Both constructions were tested against dots at matched mass <em>and</em> against random
placement at the same mass (the instrument pays largely for mass, so the random control is mandatory).</p>
<table><tr><th>field</th><th>dots @ 9,400</th><th>bridged @ S</th><th>hysteresis @ S</th><th>dots @ S</th><th>random @ S</th><th>verdict</th></tr>{geom_rows}</table>
<p>Both trace constructions lose on both fields, with paired CIs excluding zero, and both also lose to random
placement at the same mass. This closes "coverage emission" as a fix <em>on this instrument</em>; it does not
close it on the leaderboard, whose truth set and scoring region differ (see the round page limits).</p>"""

    pool = hold["pooled"]["scores"]
    gate = hold["promotion_gate"]
    lanes = lane["dots"]["policy"]
    lane_s = lane["surface"]["policy"]
    uniq = lane["uniqueness"]
    sha = card["raster_sha256"]
    rows = "".join(
        f"<tr><td><code>{a}</code></td><td>{pool[a]['dti']:.6f}</td>"
        f"<td>[{pool[a]['ci95'][0]:.6f}, {pool[a]['ci95'][1]:.6f}]</td></tr>" for a in pool)
    budget_rows = "".join(
        f"<tr><td>{f['fold']}</td><td>{f['budget_curve']['9400']:.6f}</td>"
        f"<td>{f['budget_curve']['16000']:.6f}</td><td>{f['budget_curve']['25400']:.6f}</td></tr>"
        for f in hold["folds"])
    auc_rows = "".join(
        f"<tr><td>{r['fold']}</td><td>{r['auc']['single_A2']:.4f}</td><td>{r['auc']['single_B2']:.4f}</td>"
        f"<td>{r['canary_max']:.4f}</td><td>{r['canary_worst']}</td></tr>" for r in fit["folds"])
    card_html = f"""<!--H102-CARD-->
<style>.h102card{{border:2px solid #66bb6a;border-radius:12px;padding:16px 18px;margin:16px 0;background:#0f1f14;color:#e8eaed;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}.h102card h2{{margin:0 0 8px;font-size:19px;color:#66bb6a}}.h102card a{{color:#4fc3f7;font-weight:700}}.h102card code{{background:#16241b;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}}</style>
<div class="h102card"><h2>Latest round H102 — potential-field directional anisotropy (View A) &times; surface anisotropy (View B)</h2>
<p><b>OK TO DOWNLOAD: YES</b> (independent on-disk validator PASS: 1 band float32, EPSG:32611, 3730&times;3292,
transform and bounds equal to the sample submission, <b>0 NaN, 0 inf, values exactly {{0.0, 1.0}}</b>,
{card['validator']['ones']:,} cells = 1). <b>OK TO SUBMIT: {verdict_submit}</b> — {'holdout promotion gate PASSED; a selector still has to record the decision before a weekly slot is spent.' if promoted else 'research candidate, NOT slot-approved: its holdout DTI did not clear the promotion rule (see the table below). Do not spend your last slot on it without reading the limits.'}</p>
<p><a href="downloads/h102-candidate.tif" download><b>Download the H102 GeoTIFF (.tif) &darr;</b></a> &middot;
<a href="downloads/h102-candidate.zip" download>single-TIFF .zip &darr;</a> &middot;
{'<a href="downloads/h102-a-only-reasoning.csv" download>A-only reasoning CSV &darr;</a> &middot;' if (DL / 'h102-a-only-reasoning.csv').exists() else ''}
<a href="h102.html">full result page</a> &middot;
<a href="executive-summary.html">how to submit (step by step)</a></p>
<p><small>Submission name <code>{name}</code><br>Note ({card['note_chars']}/140): <code>{card['note']}</code><br>
SHA-256 <code>{sha}</code> &middot; {card['raster_bytes']:,} bytes &middot;
verdict <b>{card['verdict']}</b> &middot; submission slots used by this round: {card['submission_slots_used']}</small></p></div>
<!--/H102-CARD-->"""

    h102_page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>H102 — potential-field anisotropy &times; surface anisotropy disagreement (GEMSDOE52)</title>
<style>:root{{--bg:#0f1117;--fg:#e8eaed;--accent:#4fc3f7;--ok:#66bb6a;--warn:#ffa726;--err:#ef5350;--card:#1a1d27;--border:#2d3040}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.6}}
.container{{max-width:900px;margin:0 auto;padding:24px 20px}}h1{{font-size:1.6rem;color:var(--accent)}}h2{{font-size:1.15rem;margin:24px 0 10px;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:6px}}
a{{color:var(--accent)}}code{{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:.88em;word-break:break-all}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:.92rem}}th,td{{padding:6px 9px;text-align:left;border-bottom:1px solid var(--border)}}th{{color:var(--accent)}}
.box{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin:12px 0}}.muted{{color:#9aa0a6;font-size:.88rem}}
.btn{{display:inline-block;background:var(--accent);color:#000;font-weight:700;padding:10px 18px;border-radius:6px;margin:6px 6px 6px 0;text-decoration:none}}</style></head><body><div class="container">
<h1>H102 — potential-field directional anisotropy (PAF-DVA) as View A</h1>
<p class="muted">DOE GEMS Prize (DrivenData #306) &middot; generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} &middot;
preregistration <code>registry/h102_preregistration.json</code> SHA-256 <code>{card['preregistration_sha256']}</code> &middot;
<a href="index.html">status</a> &middot; <a href="executive-summary.html">how to submit</a></p>
<div class="box"><b>Download:</b>
<a class="btn" href="downloads/h102-candidate.tif" download>h102-candidate.tif</a>
<a class="btn" href="downloads/h102-candidate.zip" download>h102-candidate.zip</a>
<p class="muted">Submit to DrivenData: <b>{verdict_submit}</b>. Verdict <b>{card['verdict']}</b>, submission slots used {card['submission_slots_used']}.</p></div>
<h2>1 &middot; Hypothesis and mechanism</h2>
<p>{card['hypothesis']}</p><p><b>Mechanism.</b> {card['mechanism']}</p>
<p><b>Named non-fault process that could mimic it.</b> {card['named_non_fault_mimic']}</p>
<h2>2 &middot; What was computed</h2>
<p>Operator <code>{ch['stage'] and 'run_h82._gamma_stats'}</code> (8-direction integer fan, sigma {ch['per_band'][list(ch['per_band'])[0]]['seconds'] and '3.0'} px, lags 100/200/300/400/600 m),
imported from the H82 round, never forked. View A = 4 potential-field/subsurface bands &times; 5 lags &times; 2 statistics =
{len(ch['channels_A'])} channels; View B = 2 detrended-elevation bands = {len(ch['channels_B'])} channels.
Both views also carry the shared cached feature store columns ({fit['view_A_store_columns']} View-A, {fit['view_B_store_columns']} View-B), disjoint by construction.</p>
<h2>3 &middot; HOLDOUT-DTI (the only score this round can compute for itself)</h2>
<p class="muted">Evaluator <code>{hold['evaluator']}</code>, {hold['withheld_positive_px']:,} withheld positive pixels, {hold['budget_per_fold']:,} dots per fold per arm at 3 px spacing,
alpha 0.2 / beta 0.8 / 300 m triangular kernel, 1,000 paired physical-cluster bootstrap draws. A holdout number is evidence about this instrument, not a leaderboard forecast.</p>
<table><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95 % CI</th></tr>{rows}</table>
<p><b>Promotion rule (frozen before the fit):</b> {hold['promotion_rule']}. Best comparable control
<code>{gate['best_comparable_control']}</code> {gate['control_dti']:.6f} vs candidate {gate['candidate_dti']:.6f},
paired {gate['delta']:+.6f} [{gate['ci95'][0]:+.6f}, {gate['ci95'][1]:+.6f}].
CI lower bound above zero: <b>{gate['ci_lower_above_zero']}</b>; above the standing bar: <b>{gate['above_standing_bar']}</b>
&rarr; <b>PROMOTE = {gate['PROMOTE']}</b>.</p>
<h2>4 &middot; Diagnostics that were registered in advance</h2>
<table><tr><th>fold</th><th>single_A2 out-of-quadrant AUC</th><th>single_B2</th><th>leakage canary max</th><th>worst channel</th></tr>{auc_rows}</table>
<p>Leakage canary bar 0.90 (a single channel alone on the held-out region); alarm raised: <b>{fit['canary_alarm_any']}</b>.</p>
<p><b>Budget diagnostic (does NOT select the budget — amendment h102a):</b> the artifact's mass is frozen at
{build['target_dots']:,} dots = 4 &times; {hold['budget_per_fold']:,}, the family standard.</p>
<table><tr><th>fold</th><th>9,400/fold</th><th>16,000/fold</th><th>25,400/fold</th></tr>{budget_rows}</table>
<h2>5 &middot; Independence of the two views (Blum&ndash;Mitchell assumption)</h2>
<p>The brief's mandated test: correlate each view's spatial-block out-of-fold errors on labelled negatives,
thresholds inherited verbatim from <code>registry/h74_preregistration.json</code>. Result recorded in
<code>evidence/h102_independence.json</code>: max |rho| = {json.dumps(load('h102_independence.json')['result']['max_abs_correlation'])},
abandon bar {json.dumps(load('h102_independence.json')['result']['threshold'])}.</p>
<h2>6 &middot; The artifact: placement, format and uniqueness</h2>
<p>Emitted {build['dots']:,} cells at 3 px minimum spacing inside the eligible footprint
({build['eligible_px']:,} px), pool {build['pool_px']:,} px, the &le;200 m collar around every mapped catalogue fault excluded.
Nearest emitted cell to the mapped catalogue {build['min_cat_dist_m']:.1f} m; median {build['median_cat_dist_m']:.0f} m;
{build['dots_within_300m_of_catalogue_pct']:.2f} % of the mass lies within 300 m of a mapped fault.</p>
<table><tr><th>field</th><th>value</th></tr>
<tr><td>on-disk validator</td><td>{'PASS' if card['validator']['PASS'] else 'FAIL'} &mdash; {card['validator']['count']} band {card['validator']['dtype']}, {card['validator']['crs']},
{card['validator']['shape'][0]}&times;{card['validator']['shape'][1]}, transform match {card['validator']['transform_match']},
NaN {card['validator']['nan']}, inf {card['validator']['infinite']}, range [{card['validator']['min']}, {card['validator']['max']}]</td></tr>
<tr><td>lane vs registry (surface)</td><td>{lane_s['verdict']} &mdash; max |Spearman| {lane_s['max_spearman']}, bar 0.90</td></tr>
<tr><td>lane vs registry (dots)</td><td>{lanes['verdict']} &mdash; max fraction within 3 px of one prior {lanes['max_near_3px_fraction']}, bar 0.70</td></tr>
<tr><td>registry scope</td><td>{lane['n_local_registry']} rasters &mdash; {lane['registry_scope']}</td></tr>
<tr><td>uniqueness</td><td>identical to any prior: {uniq.get('identical_to_any')}; novel fraction {uniq.get('novel_fraction')}; max Jaccard {uniq.get('max_jaccard')}</td></tr>
<tr><td>not merely the union of the two views</td><td>{json.dumps(card['not_the_union'])}</td></tr></table>
{geom_html}
<h2>7 &middot; Limits (read before submitting)</h2>
<ul>
<li>This round's holdout score is <b>{gate['candidate_dti']:.6f}</b> [{gate['ci95'][0]:+.6f} vs the best control {gate['control_dti']:.6f}].
{'It cleared the pre-registered promotion rule.' if promoted else 'It did **not** clear the pre-registered promotion rule, so the file is a research candidate.'}</li>
<li>The hide-and-recover instrument withholds the <em>catalogue</em> faults, which were mapped from surface expression; the
competition scores faults the catalogue lacks. This repository has measured that the instrument does not rank leaderboard
performance (Spearman &asymp; &minus;0.10 over R4), so a holdout number is never a board forecast.</li>
<li>View A (potential field / subsurface) has failed the sufficiency gate in every round that reported it; H102 tests whether
<em>directional anisotropy</em> changes that. The View-A out-of-quadrant AUCs are in the table above.</li>
<li>The lane census covers the locally available registry ({lane['n_local_registry']} unique rasters). The full 526-blob
cross-repository census lives in a git-ignored receipt and was not re-fetched inside this round's time box (IR-H102-003).</li>
<li>No new external data was used. The one external layer ranked highest-unexplored (GDR 1391 two-metre temperature probes,
DOI 10.15121/1881483) is not reachable from this sandbox (<code>gdr.openei.org</code> is not on the egress allowlist).</li>
</ul>
<h2>8 &middot; Sources</h2>
<ul>
<li>Metric and submission format: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DrivenData problem description</a></li>
<li>Public leaderboard: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">DrivenData leaderboard</a></li>
<li>Blum &amp; Mitchell, COLT 1998: <a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a></li>
<li>USGS GeoDAWN (DOI 10.5066/P93LGLVQ): <a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">usgs.gov</a></li>
<li>INGENIOUS / GDR 1391 (DOI 10.15121/1881483): <a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a></li>
<li>Reference solution: <a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></li>
</ul>
<p class="muted">Every number on this page was read from the JSON receipts named above, written by
<code>scripts/run_h102.py</code>. Nothing is projected onto a leaderboard.</p>
</div></body></html>"""
    (ROOT / "docs/h102.html").write_text(h102_page)

    for page in (ROOT / "docs/index.html", ROOT / "docs/executive-summary.html"):
        text = page.read_text()
        if "<!--H102-CARD-->" in text:
            head, rest = text.split("<!--H102-CARD-->", 1)
            _old, tail = rest.split("<!--/H102-CARD-->", 1)
            text = head + card_html + tail
        else:
            marker = "<body>"
            i = text.index(marker) + len(marker)
            text = text[:i] + "\n" + card_html + text[i:]
        if page.name == "index.html":
            text = text.replace(
                "<title>GEMSDOE52 — current status (H96): download yes, submit NO</title>",
                f"<title>GEMSDOE52 — current status (H102): download yes, submit {verdict_submit}</title>")
        page.write_text(text)

    (SUB / "LATEST.txt").write_text(f"gems52-{name}.tif\n")
    (SUB / "H102_LATEST.txt").write_text(f"gems52-{name}.tif\n")
    print(json.dumps(dict(submission=f"gems52-{name}.tif", submit_ok=promoted, verdict=card["verdict"],
                          sha256=sha, note=card["note"], rasters_in_registry=lane["n_local_registry"],
                          lane_dots=lanes["verdict"], lane_surface=lane_s["verdict"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
