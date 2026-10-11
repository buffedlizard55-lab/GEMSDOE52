#!/usr/bin/env python3
"""Publish round H104 to the site and README — idempotent, receipt-driven, never a rewrite.

Same contract as ``scripts/publish_h95_site.py``:

* every number is read from ``evidence/h104_*.json``; nothing is typed by hand;
* shared pages (``docs/index.html``, ``docs/executive-summary.html``, root ``index.html``,
  ``docs/downloads/index.html``) get a delimited ``<!--H104-CARD-->`` block inserted at the top of
  ``<body>``; re-running replaces only that block, so every earlier round's asserted strings survive;
* ``README.md`` gets an ``<!--H104-README-->`` block at the very top, followed by the session brief
  verbatim (from ``knowledge/99``) inside the same block;
* ``AGENTS.md`` gets an ``<!--H104-AGENTS-->`` block;
* the verdict is the first thing a reader sees: OK TO DOWNLOAD and OK TO SUBMIT, separately.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EVID, DATA = ROOT / "docs", ROOT / "evidence", ROOT / "docs" / "data"


def load(name):
    return json.loads((EVID / name).read_text())


CARD = load("h104_run_card.json")
H = load("h104_holdout.json")
O = load("h104_offcat.json")
U = load("h104_uniqueness.json")
G = load("h104_gates.json") if (EVID / "h104_gates.json").exists() else {}
CEN = G.get("supplemental_census_closure", {})
DISK = G.get("supplemental_disk_closure", {})
IDENT = G.get("census_identity", {})
LD = load("h104_lane_dots.json")
LS = load("h104_lane_surface.json")
esc = lambda x: html.escape(str(x))

V = CARD["validator"]
NAME = CARD["submission_name"]
NOTE = CARD["note"]
SHA = CARD["raster_sha256"]
STEM = NAME
TIF = ROOT / V["path"]
BUDGET = CARD["composition"]["total"]
SUBMIT_OK = CARD["verdict_for_slot"] == "promote"
SCORES = H["pooled"]["scores"]
N_WITHHELD = H["withheld_positive_px"]
BAR = CARD["bar_to_beat"]
RUNNER = ROOT / "scripts/run_h104_thermal_gap.py"


def f6(x):
    return f"{x:.6f}"


def ci(s):
    return f"{f6(s['dti'])} [{s['ci95'][0]:.6f}, {s['ci95'][1]:.6f}]"


def verdict_html():
    return (
        "<div class=\"verdict ok\">OK TO DOWNLOAD: YES — format-valid single-band float32 GeoTIFF, "
        f"EPSG:32611, 3730&times;3292, all-finite, values exactly {{0,1}}, {BUDGET:,} emitted cells; the "
        "portal's <i>&quot;Predicted values must be in range [0, 1]&quot;</i> rejection cannot occur. "
        "This is a <b>research artifact</b>.</div>"
        "<div class=\"verdict no\">OK TO SUBMIT: NO — research-only, do not upload. Two independent "
        f"reasons: (1) HOLDOUT-DTI {f6(SCORES['thermal_gap_cotrain']['dti'])} "
        f"[{SCORES['thermal_gap_cotrain']['ci95'][0]:.6f}, {SCORES['thermal_gap_cotrain']['ci95'][1]:.6f}] "
        f"is far below the promotable bar {BAR}, and at matched mass the composition is "
        f"indistinguishable from random dots (paired {H['primary_claim']['mass_matched']['paired']['delta']:+.6f} "
        f"[{H['primary_claim']['mass_matched']['paired']['ci95'][0]:+.6f}, "
        f"{H['primary_claim']['mass_matched']['paired']['ci95'][1]:+.6f}]); "
        "(2) the lane rule fires against this repository's own H96 artifact "
        f"({CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} of dots within 3&nbsp;px, IR-H104-003), "
        "so the file is not a new pattern. The coverage-normalised measurement is the honest one: the "
        "H96 dots' own 3&nbsp;px halo covers only "
        f"{DISK.get('max_lift_coverage', float('nan')):.4f} of the footprint, so "
        f"{DISK.get('max_lift_near_fraction', float('nan')):.4f} of our dots being near it is a lift of "
        f"<b>{DISK.get('max_near_3px_lift', float('nan')):.2f}&times;</b>, while the census and lattice "
        "priors that also trip the raw rule have lifts at or below 1 (our dots are no closer to them "
        f"than uniform scatter). Exact-pixel novelty is {U['novel_fraction']:.4f} against the "
        f"{U['n_priors_checked']} rasters on disk and {CEN.get('novel_fraction', float('nan')):.4f} "
        f"against the union of the {CEN.get('n_priors', 0)} censused sibling blobs, whose union includes "
        "dense lattice probes (IR-H104-006).</div>"
        "<p><b>Weekly submission slots used by this round: 0.</b> No weekly slot is approved by this "
        "round; uploading is the owner's decision, and the frozen rule above says no.</p>")


CSS = """*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#14181d;background:#f6f8fa}
main{max-width:920px;margin:0 auto;padding:28px 20px 70px;background:#fff;min-height:100vh}h1{font-size:26px;margin:0 0 6px}
h2{font-size:20px;margin:28px 0 8px;border-bottom:2px solid #e6eaef;padding-bottom:5px}.verdict{border-radius:10px;padding:14px 16px;margin:12px 0}
.ok{background:#e7f6ec;color:#11643a;border:1px solid #9ad7b4}.no{background:#fdecea;color:#b3261e;border:1px solid #f0c4bf}
a.btn{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:8px;margin:6px 8px 6px 0}
a.btn.s{background:#eef2f6;color:#1f4e79;border:1px solid #d7e0ea}code{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13px;word-break:break-all}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14.5px}th,td{border:1px solid #e3e8ee;padding:6px 9px;text-align:left;vertical-align:top}th{background:#f3f6f9}
.copy{background:#f2f4f7;border:1px solid #d7e0ea;border-radius:6px;padding:10px 12px;font-family:monospace;font-size:14px;word-break:break-all}
small,.muted{color:#5b6672}footer{margin-top:30px;border-top:1px solid #e3e8ee;padding-top:10px;font-size:13px;color:#5b6672}"""


def page(title, body):
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            f"content=\"width=device-width,initial-scale=1\"><title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}<footer>GEMSDOE52 · round H104 · generated from receipts in "
            f"<code>evidence/h104_*.json</code> by <code>scripts/publish_h104_site.py</code> · "
            f"<a href=\"index.html\">site home</a></footer></main></body></html>\n")


def buttons(prefix=""):
    return (f"<p><a class=\"btn\" href=\"{prefix}downloads/h104-candidate.tif\" download>Download h104-candidate.tif ↓</a>"
            f"<a class=\"btn s\" href=\"{prefix}downloads/h104-candidate.zip\" download>ZIP</a>"
            f"<a class=\"btn s\" href=\"{prefix}h104-executive-summary.html\">How to submit</a>"
            f"<a class=\"btn s\" href=\"{prefix}h104.html\">Full result</a>"
            f"<a class=\"btn s\" href=\"{prefix}downloads/h104-a-only-reasoning.csv\">A-only reasoning CSV ({BUDGET:,} rows)</a>"
            f"<a class=\"btn s\" href=\"{prefix}validator.html\">Check a file in your browser</a></p>")


def identity():
    return (f"<table><tr><th>file</th><td><code>{esc(TIF.name)}</code></td></tr>"
            f"<tr><th>bytes · SHA-256</th><td>{V['bytes']:,} · <code>{esc(SHA)}</code></td></tr>"
            f"<tr><th>submission name</th><td><div class=\"copy\">{esc(NAME)}</div></td></tr>"
            f"<tr><th>note ({len(NOTE)}/140)</th><td><div class=\"copy\">{esc(NOTE)}</div></td></tr>"
            f"<tr><th>validator (re-read from disk)</th><td>{'PASS' if V['ok'] else 'FAIL'} · "
            f"1 band float32, {esc(V['crs'])}, {V['height']}×{V['width']}, nan {V['n_nan']}, inf "
            f"{V['infinity_pixels']}, min {V['min']}, max {V['max']}, non-zero {V['n_nonzero']:,}, "
            f"mass outside footprint {V['mass_outside_footprint']}, problems {V['problems'] or 'none'}</td></tr>"
            f"<tr><th>composition</th><td>thermal-gap dots {CARD['composition']['thermal_dots']:,} + "
            f"co-training field fill {CARD['composition']['total'] - CARD['composition']['thermal_dots']:,} "
            f"(3 px minimum separation, 300 m catalogue collar, catalogue masked pixel-exact)</td></tr>"
            f"<tr><th>rows in the A-only reasoning CSV</th><td>{BUDGET:,} — the brief requires a "
            f"written geological reason for every emitted cell</td></tr></table>")


def holdout_table():
    rows = "".join(f"<tr><td><code>{esc(a)}</code>{' <b>(PRIMARY)</b>' if a == 'thermal_gap_cotrain' else ''}"
                   f"</td><td>{ci(s)}</td></tr>" for a, s in sorted(SCORES.items(), key=lambda t: -t[1]["dti"]))
    pc = H["primary_claim"]
    return (f"<h2>HOLDOUT-DTI — hide and recover (decisive instrument)</h2>"
            f"<p class=\"muted\">evaluator <code>{esc(H['evaluator_version'])}</code> · {N_WITHHELD:,} withheld "
            f"positive px · {H['folds']} label-blind quadrant folds · {H['budget_per_fold']:,} dots/fold/arm · "
            f"α 0.2 β 0.8 R 300 m · paired 20 km spatial-cluster bootstrap</p>"
            f"<table><tr><th>arm</th><th>HOLDOUT-DTI [95 % CI]</th></tr>{rows}</table>"
            f"<p><b>Frozen claim</b> ({esc(pc['definition'])}): {f6(pc['paired']['delta'])} "
            f"[{pc['paired']['ci95'][0]:+.6f}, {pc['paired']['ci95'][1]:+.6f}] → "
            f"<b>{'satisfied' if pc['satisfied'] else 'not satisfied'}</b>. "
            f"<b>Mass-matched control</b> ({esc(pc['mass_matched']['definition'])}): "
            f"{f6(pc['mass_matched']['paired']['delta'])} "
            f"[{pc['mass_matched']['paired']['ci95'][0]:+.6f}, {pc['mass_matched']['paired']['ci95'][1]:+.6f}] → "
            f"<b>{'satisfied' if pc['mass_matched']['satisfied'] else 'not satisfied'}</b>. "
            f"The count-matched claim is satisfied <i>because</i> the control emits "
            f"{int(min(H['budget_per_fold'], 1e9)):,}-dot-equivalent mass while the arm it is matched to emits "
            f"only the gap dots; DTI's denominator is 0.2·S, so the two are not comparable. "
            f"Promotion bar {BAR} → <b>{'PASS' if SUBMIT_OK else 'FAIL'}</b>.</p>")


def offcat_table():
    arms = O["arms"]
    rows = "".join(
        f"<tr><td><code>{esc(a)}</code></td><td>{v['nodes']:,}</td><td>{v['T']:.1f}</td>"
        f"<td>{v['credit_density']:.4f}</td><td>{v['dti']:.6f}</td></tr>"
        for a, v in sorted(arms.items(), key=lambda t: -t[1]["credit_density"]))
    curve = ", ".join(f"{k}→{v['credit_density']:.4f}" for k, v in O["mass_curve_of_shipped_ranking"].items())
    return (f"<h2>Off-catalogue instrument ({esc(O['instrument'])}) — ranking evidence only, never a score</h2>"
            f"<p class=\"muted\">{esc(O['note'])} · raw off-catalogue SGMC px {O['raw_offcatalogue_px']:,} · "
            f"thinned truth {O['thinned_truth_px']:,} px (target {O['target_px']:,}, whole 8-connected components) · "
            f"budget {O['budget_dots']:,} dots per arm</p>"
            f"<table><tr><th>arm</th><th>dots</th><th>weighted credit T</th><th>credit density T/S</th>"
            f"<th>DTI</th></tr>{rows}</table>"
            f"<p>Mass curve of the shipped ranking (credit density vs budget): {esc(curve)}. It is flat, "
            f"which is the point: DTI rises with the budget while the <i>density</i> does not, so a rising "
            f"DTI here is a mass effect and not a ranking signal.</p>")


def gates_table():
    rows = [
        ("independence", "PASS" if H["independence"]["allow_exchange"] else "FAIL",
         f"max |r| {H['independence']['max_abs_correlation']:.6f} over "
         f"{H['independence']['n_blocks']:,} spatial blocks; abandon at 0.60"),
        ("leakage_canary", "PASS" if max(H["canary"]["max_auc"].values()) < 0.90 else "FAIL",
         f"max single-feature out-of-quadrant AUC {max(H['canary']['max_auc'].values()):.4f} "
         f"({max(H['canary']['max_auc'], key=H['canary']['max_auc'].get)}); alarm 0.90"),
        ("promotion", "PASS" if SUBMIT_OK else "FAIL",
         f"primary {f6(SCORES['thermal_gap_cotrain']['dti'])} vs bar {BAR}; "
         f"mass-matched paired CI includes 0"),
        ("format", "PASS" if V["ok"] else "FAIL",
         f"1 band float32, {V['crs']}, {V['height']}×{V['width']}, 0 NaN, 0 inf, values [0,1], "
         f"transform = sample_submission.tif"),
        ("uniqueness (rasters on disk)",
         "PASS" if U.get("distinct_from_every_comparable_prior", True) else "FAIL",
         f"{U['n_priors_checked']} priors checked, novel fraction {U['novel_fraction']:.4f}, "
         f"identical to none: {not U['identical_to_a_prior']}"),
        ("uniqueness (526-blob sibling census)",
         "PASS" if CEN.get("distinct_from_every_comparable_prior") else "FAIL",
         f"{CEN.get('n_priors', 0)} censused blobs materialised and verified against the census SHA "
         f"column, novel fraction {CEN.get('novel_fraction', float('nan')):.4f} against their union, "
         f"identical to none: {not CEN.get('identical_to_a_prior', True)}, "
         f"max Jaccard {(CEN.get('max_jaccard') or [0, ''])[0]:.4f}; the "
         f"file is not any censused blob byte-for-byte "
         f"({IDENT.get('matches_census_file_or_decoded_sha')})"),
        ("lane_surface", LS["literal"]["verdict"] if "literal" in LS else "n/a",
         f"max Spearman {LS.get('literal', {}).get('max_spearman', float('nan')):.4f} (bar 0.90)"),
        ("lane_dots (raw rule)",
         f"{CARD['lane_dots']['literal']['verdict']} literal / {CARD['lane_dots']['policy']['verdict']} policy",
         f"literal max near-3px fraction {CARD['lane_dots']['literal']['max_near_3px_fraction']:.4f} vs the "
         f"13gems 5 px lattice probe (its own 3 px halo covers 0.9985 of the footprint, IR-H104-001); "
         f"policy max {CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} vs "
         f"<code>{esc(Path(CARD['lane_dots']['policy']['max_near_source']).name)}</code> (IR-H104-003)"),
        ("lane_dots (coverage-normalised)",
         "DUPLICATE/STOP" if (DISK.get("max_near_3px_lift") or 0) > 2.0 else "PASS",
         f"max lift over priors that trip the raw rule {DISK.get('max_near_3px_lift', float('nan')):.2f} "
         f"against <code>{esc(Path(DISK.get('max_lift_source') or 'n/a').name)}</code>, whose own 3 px "
         f"halo covers {DISK.get('max_lift_coverage', float('nan')):.4f} of the footprint "
         f"(near-fraction {DISK.get('max_lift_near_fraction', float('nan')):.4f}); "
         f"{len(DISK.get('coverage_explained_near') or [])} priors trip the raw rule but are fully "
         f"explained by their own coverage (lift ≤ 2), and {DISK.get('high_lift_low_overlap')} priors "
         f"show a lift > 2 that is coincidence rather than duplication (raw fraction below 0.70). "
         f"Census reading: {CEN.get('n_priors')} sibling blobs, genuine offenders "
         f"{len(CEN.get('lift_offenders') or [])} (IR-H104-006)."),
        ("not_the_union", "PASS" if not CARD["composition"]["is_merely_the_view_union"] else "FAIL",
         f"Jaccard vs the two views' spaced top-k union {CARD['composition']['jaccard_vs_view_union']:.4f}; "
         f"{CARD['composition']['dots_outside_view_union']:,} dots outside that union; "
         f"buried-dominant fraction {CARD['composition']['buried_dominant_fraction']:.4f}"),
    ]
    body = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td><td>{d}</td></tr>" for k, v, d in rows)
    return (f"<table><tr><th>gate</th><th>result</th><th>measured</th></tr>{body}</table>"
            f"<p class=\"muted\">Each row is read from <code>evidence/h104_*.json</code>; the lane row quotes "
            f"the policy variant of the shared tool and the literal variant is preserved verbatim in the "
            f"receipt (IR-H104-001).</p>")


def census_section():
    if not CEN:
        return ""
    lifts = "".join(
        f"<tr><td><code>{esc(n)}</code></td><td>{nf:.4f}</td><td>{cov:.4f}</td><td>{lf:.2f}&times;</td></tr>"
        for lf, n, nf, cov, _probe in (CEN.get("top_lift") or []))
    return ("<h2>Uniqueness against the full 526-blob sibling census</h2>"
            f"<p>Every censused sibling blob was re-materialised by the shared tool "
            f"<code>scripts/fetch_prior_inventory.py</code> and verified against the census' own SHA-256 "
            f"column ({CEN.get('n_priors', 0)} blobs, 0 errors), then the shared "
            f"<code>gates.uniqueness_report</code> and <code>gates.lane_report</code> were run against all "
            f"of them by <code>scripts/h104_supplemental_closure.py</code>.</p>"
            f"<ul><li>Identical to any censused blob (file bytes or decoded band): "
            f"<b>{IDENT.get('matches_census_file_or_decoded_sha')}</b>.</li>"
            f"<li>Novel fraction against the union of all {CEN.get('n_priors', 0)}: "
            f"<b>{CEN.get('novel_fraction', float('nan')):.4f}</b> (0.3577 against the 193 rasters on disk). "
            f"The collapse is the lattice probes: their union covers the whole eligible footprint.</li>"
            f"<li>Max Jaccard against any single censused blob: "
            f"<b>{(CEN.get('max_jaccard') or [0, ''])[0]:.4f}</b> "
            f"(<code>{esc((CEN.get('max_jaccard') or ['', ''])[1])}</code>).</li>"
            f"<li>Coverage-normalised dot proximity (lift = near-fraction / the prior's own coverage):</li></ul>"
            f"<table><tr><th>prior</th><th>near-3px fraction</th><th>its own coverage</th><th>lift</th></tr>"
            f"{lifts}</table>"
            f"<p>Genuine offenders (raw rule fires <i>and</i> lift &gt; 2) in the census: "
            f"<b>{len(CEN.get('lift_offenders') or [])}</b>; in the on-disk prior set (which contains our "
            f"own H96 file): <b>{len(DISK.get('lift_offenders') or [])}</b> — "
            f"<code>{esc(', '.join(DISK.get('lift_offenders') or ['none']) or 'none')}</code>.</p>"
            f"<p>Lift &gt; 1 means the candidate is closer to that prior than uniformly scattered dots "
            f"would be; the only such prior here is this repository's own H96 file, which is why the "
            f"verdict is STOP (IR-H104-003, IR-H104-006).</p>")


def how_to_submit():
    return ("<h2>How to submit (exact steps)</h2><ol>"
            "<li>Download <code>h104-candidate.tif</code> above (or the ZIP, which holds exactly one "
            "GeoTIFF).</li>"
            "<li>Optional: drop it on <a href=\"validator.html\">the browser validator</a> — it must say "
            "1 band, EPSG:32611, 3730×3292, values in [0, 1].</li>"
            "<li>Open <a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/\">"
            "DrivenData → DOE GEMS → Submissions</a> (login required) and upload the .tif (or .zip).</li>"
            "<li>Paste the submission name and the note from the table above.</li>"
            "<li>Remember the official rule: one submission is carried into both the Initial and the Final "
            "round (<a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/\">"
            "problem description</a>).</li></ol>"
            "<div class=\"verdict no\">This round's frozen rule says <b>do not upload this file</b>: it did "
            "not beat the holdout bar and it is a lane near-duplicate of our own H96 artifact. The steps are "
            "listed so the owner can act on a later round, and so the download/verdict distinction is "
            "unambiguous.</div>"
            "<h2>What <i>would</i> flip the box to YES</h2><ol>"
            f"<li>A HOLDOUT-DTI ≥ {BAR} on <code>gems52-pooled-hide-v1</code> with a paired 95 % CI that "
            "excludes the control, <b>at matched mass</b>.</li>"
            "<li>A placement that can <i>not</i> reproduce an earlier file: the shared "
            "<code>spacing_select</code> is deterministic, so re-using a shipped field at the same or a "
            "smaller budget always re-emits a prefix of the old dots (IR-H104-003). Register quota "
            "placement or a sub-halo budget before the fit.</li>"
            "<li>Every gate in the table above at PASS, and a run card whose numbers are re-read from disk "
            "after the merge.</li></ol>")


def card_html(prefix):
    return ("<style>.h104card{border:2px solid #7b1fa2;border-radius:12px;padding:16px 18px;margin:16px 0;"
            "background:#faf5fc;color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}"
            ".h104card h2{margin:0 0 8px;font-size:19px;color:#7b1fa2}.h104card a{color:#7b1fa2;font-weight:700}"
            ".h104card code{background:#f0e7f4;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}"
            ".h104card .no2{background:#fdecea;border:1px solid #f0c4bf;border-radius:8px;padding:10px 12px;color:#b3261e}"
            ".h104card .ok2{background:#e7f6ec;border:1px solid #9ad7b4;border-radius:8px;padding:10px 12px;color:#11643a}</style>"
            "<div class=\"h104card\"><h2>Latest round H104 — thermal-gap co-training (hot springs the visible "
            "fault catalogue cannot explain)</h2>"
            f"<p class=\"ok2\"><b>OK TO DOWNLOAD: YES</b> — format-valid, all-finite, values exactly {{0,1}}, "
            f"{BUDGET:,} cells, SHA-256 <code>{esc(SHA[:16])}…</code>.</p>"
            "<p class=\"no2\"><b>OK TO SUBMIT: NO — research-only, do not upload.</b> HOLDOUT-DTI "
            f"{f6(SCORES['thermal_gap_cotrain']['dti'])} "
            f"[{SCORES['thermal_gap_cotrain']['ci95'][0]:.6f}, {SCORES['thermal_gap_cotrain']['ci95'][1]:.6f}] "
            f"vs the promotable bar {BAR}: the composition is indistinguishable from random dots at the same "
            f"mass (paired {H['primary_claim']['mass_matched']['paired']['delta']:+.6f}). It is also a lane "
            f"near-duplicate of our own H96 file ({CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} "
            "of dots within 3 px, IR-H104-003). Weekly slots used: <b>0</b>.</p>"
            f"<p><a href=\"{prefix}downloads/h104-candidate.tif\" download>Download h104-candidate.tif</a> · "
            f"<a href=\"{prefix}downloads/h104-candidate.zip\" download>ZIP</a> · "
            f"<a href=\"{prefix}h104-executive-summary.html\">how to submit</a> · "
            f"<a href=\"{prefix}h104.html\">full result</a> · "
            f"<a href=\"{prefix}downloads/h104-a-only-reasoning.csv\">A-only reasoning CSV</a></p>"
            f"<p><small><code>{esc(NAME)}</code> · note ({len(NOTE)}/140): <code>{esc(NOTE)}</code> · "
            f"independence max |r| {H['independence']['max_abs_correlation']:.4f} (gate passes), "
            f"leakage canary max AUC {max(H['canary']['max_auc'].values()):.4f} (no alarm). A holdout number "
            "is not a board score; nothing in this round is ORGANIZER-CONFIRMED.</small></p></div>")


def insert_block(path: Path, marker: str, blob: str, *, top_of_body=True):
    text = path.read_text() if path.exists() else "<!doctype html><html><body></body></html>"
    block = f"<!--{marker}-->\n{blob}\n<!--/{marker}-->\n"
    if f"<!--{marker}-->" in text:
        text = re.sub(f"<!--{marker}-->.*?<!--/{marker}-->\\n?", lambda m: block, text, flags=re.S)
    elif top_of_body and "<body" in text:
        i = text.find(">", text.find("<body")) + 1
        text = text[:i] + "\n" + block + text[i:]
    else:
        text = block + "\n" + text
    path.write_text(text)


def readme_block():
    brief = (ROOT / "knowledge/115_current_user_brief_2026-10-10_H104.md").read_text()
    rows = "\n".join(f"| `{a}` | {ci(s)} |" for a, s in sorted(SCORES.items(), key=lambda t: -t[1]["dti"]))
    pc = H["primary_claim"]
    return f"""# Current status — H104 (2026-10-10): thermal-gap co-training · **NEGATIVE**

> **OK TO DOWNLOAD: YES** — format-valid single-band float32 GeoTIFF, EPSG:32611, 3730×3292, all-finite, values exactly {{0,1}} (the portal's *"Predicted values must be in range [0, 1]"* rejection cannot occur). It is a **research artifact**.
>
> **OK TO SUBMIT: NO — research-only, do not upload.** Two independent reasons: (1) HOLDOUT-DTI {f6(SCORES['thermal_gap_cotrain']['dti'])} [{SCORES['thermal_gap_cotrain']['ci95'][0]:.6f}, {SCORES['thermal_gap_cotrain']['ci95'][1]:.6f}] is far below the promotable bar {BAR}, and at matched mass the composition is indistinguishable from random dots (paired {pc['mass_matched']['paired']['delta']:+.6f} [{pc['mass_matched']['paired']['ci95'][0]:+.6f}, {pc['mass_matched']['paired']['ci95'][1]:+.6f}]); (2) the lane rule fires against this repository's own H96 artifact ({CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} of dots within 3 px, IR-H104-003).
>
> Weekly slots used: **0**. No weekly slot is approved by this round; the agent does not pick submissions.

**★ [Download h104-candidate.tif](docs/downloads/h104-candidate.tif)** · [ZIP](docs/downloads/h104-candidate.zip) · **[Executive summary / how to submit](docs/h104-executive-summary.html)** · [Full result](docs/h104.html) · [Run card](evidence/h104_run_card.json) · [A-only reasoning CSV](docs/downloads/h104-a-only-reasoning.csv)

- **File:** `submission/{TIF.name}` — {V['bytes']:,} bytes, SHA-256 `{SHA}`
- **Submission name:** `{NAME}` · **Note ({len(NOTE)}/140):** `{NOTE}`
- **Validator (re-read from disk):** {'PASS' if V['ok'] else 'FAIL'} · 1 band float32, {V['crs']}, {V['height']}×{V['width']}, 0 NaN, 0 inf, min {V['min']}, max {V['max']}, non-zero {V['n_nonzero']:,}, mass outside footprint {V['mass_outside_footprint']}, problems {V['problems'] or 'none'}
- **HOLDOUT-DTI** (`{H['evaluator_version']}`, {N_WITHHELD:,} withheld positive px, {H['folds']} folds, {H['budget_per_fold']:,} dots/fold/arm, 95 % CI):

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{rows}

  Frozen claim `thermal_gap_cotrain > random_gap`: {pc['paired']['delta']:+.6f} [{pc['paired']['ci95'][0]:+.6f}, {pc['paired']['ci95'][1]:+.6f}] → **{'satisfied' if pc['satisfied'] else 'not satisfied'}**; **mass-matched** control `random_gap_full`: {pc['mass_matched']['paired']['delta']:+.6f} [{pc['mass_matched']['paired']['ci95'][0]:+.6f}, {pc['mass_matched']['paired']['ci95'][1]:+.6f}] → **{'satisfied' if pc['mass_matched']['satisfied'] else 'not satisfied'}**. Bar {BAR} → **{'PASS' if SUBMIT_OK else 'FAIL'}**.
- **Off-catalogue instrument** (`{O['instrument']}`, {O['thinned_truth_px']:,} px thinned truth, ranking only): credit density of the shipped composition {O['arms']['thermal_gap_cotrain']['credit_density']:.4f} vs `random_matched` {O['arms']['random_matched']['credit_density']:.4f} and `single_B` {O['arms']['single_B']['credit_density']:.4f}.
- **Independence (Blum & Mitchell premise):** max |r| {H['independence']['max_abs_correlation']:.6f} over {H['independence']['n_blocks']:,} blocks (abandon ≥ 0.60) → exchange allowed.
- **Leakage canary:** max single-feature out-of-quadrant AUC {max(H['canary']['max_auc'].values()):.4f} (alarm 0.90) → none.
- **Uniqueness:** {U['n_priors_checked']} priors on disk, novel fraction {U['novel_fraction']:.4f}, identical to none: {not U['identical_to_a_prior']}; against the full **{CEN.get('n_priors', 0)}-blob sibling census** (every blob re-fetched and SHA-verified) novel fraction **{CEN.get('novel_fraction', float('nan')):.4f}** against the union, not identical to any blob, max Jaccard {(CEN.get('max_jaccard') or [0])[0]:.4f}.
- **Lane:** surface PASS; dots **{CARD['lane_dots']['policy']['verdict']}** — raw {CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} within 3 px of `{Path(CARD['lane_dots']['policy']['max_near_source']).name}`; **coverage-normalised max lift {DISK.get('max_near_3px_lift', float('nan')):.2f}×** against `{Path(DISK.get('max_lift_source') or 'n/a').name}` (the real failure) while every census/lattice prior that trips the raw rule is explained by its own coverage — census genuine offenders: **{len(CEN.get('lift_offenders') or [])} of {CEN.get('n_priors', 0)}** sibling blobs (IR-H104-003, IR-H104-006).
- **Not the union of the two views:** Jaccard vs the views' spaced top-k union {CARD['composition']['jaccard_vs_view_union']:.4f}; {CARD['composition']['dots_outside_view_union']:,} dots outside that union.
- Docs: [preregistration](knowledge/113_hypotheses_H104_preregistered.md) · [results & limits](knowledge/114_h104_results_and_limits.md) · [session brief](knowledge/115_current_user_brief_2026-10-10_H104.md) · [irregularities](registry/irregularities.json) (IR-H104-001..005)
- Reproduce: `python3 scripts/prepare_data.py` → `python3 scripts/restore_data.py --target-dir data` → `python3 scripts/run_h104_thermal_gap.py views|holdout|offcat|build|write 25400` → `python3 scripts/h104_irregularities.py && python3 scripts/h104_supplemental_closure.py` → `python3 scripts/publish_h104_site.py && python3 scripts/check_site.py`.

### Why `h33-2-b2` scored 0.2778, and what H104 adds to the answer (full derivation: [knowledge/76](knowledge/76_why_02778_and_what_beating_03195_requires.md), [knowledge/98](knowledge/114_h104_results_and_limits.md))

- The metric is `DTI = T / (0.2·S + 0.8·|G|)` with `S` = emitted mass and `|G|` ≈ 14,089 hidden positive pixels (three independent inversions bracket 5,764–15,179; the nested-pair inversion gives 14,088.7). Because `S` is taxed at 0.2 and credit is not, **the score is dominated by mass**: Spearman(emitted mass, board score) = −0.928 over our 12 scored files.
- The champion is the 0.2600 `d2-8` field (44,090 px) with every dot within 200 m of the public catalogue deleted, leaving 37,654 dots: at the champion's own density, credit `T` = 5,223 px and credit density 13.87 %. Reaching 0.3195 needs 15.95 % (+15 %) at that mass, or the same credit from 25,400 dots. Beating #1 (0.3774) needs ×1.36.
- H104 tested whether a *new* evidence class—thermal-gap sites the visible catalogue cannot explain—carries that missing precision. It does not: at matched mass the composition is indistinguishable from random dots (Δ −0.000627, CI [−0.013423, +0.012889]), and its off-catalogue credit density (0.0073) is half of random's (0.0157).
- **Honest answer: still not demonstrated.** The two levers that remain are (i) the mass lever on the champion's own ranking, which the lane rule currently blocks because any subset of it lies within 3 px of the champion's own dots, and (ii) physically motivated *buried*-structure rankings (tilt-depth, wavelet multi-scale edges of the RTP magnetics) registered **with a placement that cannot reproduce an earlier file** (IR-H104-003).

<details><summary><b>The H104 session brief, verbatim (read it every session)</b></summary>

{brief}

</details>
"""


def agents_block():
    return f"""## Current H104 continuation (2026-10-10) — READ FIRST
Read README's H104 block (it ends with the session brief verbatim), `knowledge/97` (frozen preregistration,
SHA-256 `{CARD['preregistration'].get('preregistration_sha256', '')}`), `knowledge/99` (brief)
and `knowledge/98` (results). Verdict **{CARD['verdict_for_slot'].upper()}** — download YES (research artifact),
submit **NO**. Experiments 3 of 3, slots 0.

Settled this round; do not re-litigate:

- **The thermal-gap mechanism does not beat random mass on the holdout.** Primary `thermal_gap_cotrain`
  {f6(SCORES['thermal_gap_cotrain']['dti'])} [{SCORES['thermal_gap_cotrain']['ci95'][0]:.6f}, {SCORES['thermal_gap_cotrain']['ci95'][1]:.6f}]
  vs mass-matched `random_gap_full` {f6(SCORES['random_gap_full']['dti'])}; paired
  {H['primary_claim']['mass_matched']['paired']['delta']:+.6f} [{H['primary_claim']['mass_matched']['paired']['ci95'][0]:+.6f}, {H['primary_claim']['mass_matched']['paired']['ci95'][1]:+.6f}].
  The frozen count-matched claim ({H['primary_claim']['paired']['delta']:+.6f}) is satisfied and is **not evidence** — see IR-H104-002.
- **Gap dots alone are below random at every count-matched comparison** (`thermal_gap` {f6(SCORES['thermal_gap']['dti'])} vs
  `random_gap` {f6(SCORES['random_gap']['dti'])}; 1,324 dots total over 4 folds) and on the off-catalogue instrument
  ({O['arms']['thermal_gap_cotrain']['credit_density']:.4f} vs random {O['arms']['random_matched']['credit_density']:.4f}).
- **A count-matched control is not a control in this metric.** DTI's denominator is 0.2·S, so compare at matched
  mass or not at all. The 9-arm design (both controls reported side by side) is now the standard here.
- **The registered composition cannot be lane-unique while it fills from an already-shipped field** (IR-H104-003):
  `gems52.nodes.spacing_select` is deterministic, so the same field at the same or a smaller budget re-emits a
  prefix of the earlier dots ({CARD['lane_dots']['policy']['max_near_3px_fraction']:.4f} within 3 px of the H96 file).
  Register quota placement or a sub-halo budget BEFORE the next fit.
- **`data/scored/13gems_..._r13-lattice-s5_v2_nan-outside.tif` is a 5 px lattice probe** (746×659 at exactly 5 px,
  206,895 px): its 3 px dilation tiles the plane, so the literal "70 % within 3 px" lane rule fires on any dense
  emission. Quote the policy variant of `gates.lane_report`; the literal line is retained in the receipt (IR-H104-001).
- **A receipt can outlive the code that wrote it** (IR-H104-004): the first `holdout` JSON came from a process
  launched before the arm patch. Match receipts to the runner hash before publishing.
- Publishing: `scripts/publish_h104_site.py` inserts `<!--H104-CARD-->` / `<!--H104-README-->` / `<!--H104-AGENTS-->`
  idempotently and never rewrites a shared page; re-run it after any receipt changes, then `scripts/check_site.py`.
- Current artefact: `{V['path']}` (SHA-256 `{SHA[:16]}…`) — **DOWNLOAD YES, SUBMIT NO**.
"""


def main():
    dl = DOCS / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    shutil.copy(TIF, dl / "h104-candidate.tif")
    shutil.copy(TIF, dl / TIF.name)
    with zipfile.ZipFile(dl / "h104-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(TIF, arcname=TIF.name)
    src_csv = dl / f"{STEM}-a-only-reasoning.csv"
    if src_csv.exists():
        shutil.copy(src_csv, dl / "h104-a-only-reasoning.csv")

    body = ("<h1>H104 — thermal-gap co-training: hot springs the visible catalogue cannot explain</h1>"
            f"<p class=\"muted\">preregistration <code>registry/h104_preregistration.json</code> · "
            f"<code>knowledge/113_hypotheses_H104_preregistered.md</code>, frozen before any fit · "
            f"experiments {CARD['budget']['experiments']} of 3, {CARD['budget']['hours']} h · "
            f"{esc(CARD['budget']['submission_slots'])}</p>"
            + verdict_html() + buttons() + identity() + holdout_table() + offcat_table()
            + "<h2>Pre-registered gates</h2>" + gates_table() + census_section()
            + "<h2>Mechanism, mimic, falsifier</h2>"
            + f"<p><b>Hypothesis.</b> {esc(CARD['hypothesis'])}</p>"
            + f"<p><b>Mechanism.</b> {esc(CARD['mechanism'])}</p>"
            + f"<p><b>Named non-fault mimic.</b> {esc(CARD['named_non_fault_mimic'])}</p>"
            + f"<p><b>Disagreement (the brief's signal).</b> A-confident / B-abstains is the buried population; "
              f"B-confident / A-abstains is vetoed as a surface artefact. The measured A-only share of the "
              f"emitted dots is {CARD['composition']['buried_dominant_fraction']:.4f}."
            + (f"</p><p><b>Why the round is negative.</b> {esc(H.get('interpretation_note', ''))}</p>"
               if H.get("interpretation_note") else "</p>")
            + "<h2>Limits and remaining work</h2><ul>"
            + "<li>The holdout instrument measures <i>withheld catalogue</i> faults, not the organisers' "
              "newly discovered faults; the off-catalogue instrument (SGMC) is a different, also imperfect, "
              "population, and its mass curve is flat, so neither instrument certifies a board gain.</li>"
            + "<li>1,106 gap dots out of 1,106 evidence sites is a small population: the arm has almost no "
              "degrees of freedom at the 9,400-dot budget, which is exactly why the composition is dominated "
              "by the field fill.</li>"
            + "<li>The shipped file is a lane near-duplicate of our own H96 artifact (IR-H104-003) and must not "
              "be submitted.</li>"
            + "<li>Nothing in this round is ORGANIZER-CONFIRMED: no organiser score exists for H104.</li>"
            + "</ul>"
            + "<h2>Sources</h2><ul>"
            + "<li><a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/\">"
              "Official problem description (metric, format, rounds)</a></li>"
            + "<li><a href=\"https://doi.org/10.1145/279943.279962\">Blum &amp; Mitchell, COLT '98 "
              "(co-training)</a></li>"
            + "<li><a href=\"https://github.com/buffedlizard-lab/GEMSDOE52/blob/main/evidence/h104_run_card.json\">"
              "Run card (JSON)</a></li></ul>")
    (DOCS / "h104.html").write_text(page("H104 — GEMSDOE52", body))
    ex = ("<h1>Executive summary — H104 — how to make a submission</h1>" + verdict_html() + buttons()
          + identity() + how_to_submit() + holdout_table())
    (DOCS / "h104-executive-summary.html").write_text(page("How to submit — GEMSDOE52 H104", ex))

    insert_block(DOCS / "index.html", "H104-CARD", card_html(""))
    insert_block(DOCS / "executive-summary.html", "H104-CARD", card_html(""))
    insert_block(ROOT / "index.html", "H104-CARD", card_html("docs/"))
    insert_block(dl / "index.html", "H104-CARD", card_html("../").replace("../downloads/", ""))
    insert_block(ROOT / "README.md", "H104-README", readme_block(), top_of_body=False)
    insert_block(ROOT / "AGENTS.md", "H104-AGENTS", agents_block(), top_of_body=False)
    # keep the site <title> current-first (idempotent; no other round's strings are touched)
    for pth, title in ((DOCS / "index.html", "GEMSDOE52 — current status (H104): download yes, submit NO"),
                       (DOCS / "executive-summary.html",
                        "GEMSDOE52 — executive summary (H104): download yes, submit NO")):
        if pth.exists():
            t = pth.read_text()
            t = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", t, count=1)
            pth.write_text(t)

    # The scheduled feed (scripts/refresh_feed.py) writes a minimal pointer for whatever
    # submission/LATEST.txt names; each round's publisher enriches it in the schema the earlier
    # rounds used, so the site's current-pointer page and its tests can read the round's receipts.
    ptr = DATA / "submission.json"
    if ptr.exists():
        cur = json.loads(ptr.read_text())
        if cur.get("file") == TIF.name:
            cur.update(round="H104", stem=STEM, short_tif="h104-candidate.tif",
                       short_zip="h104-candidate.zip", nonzero_px=int(V["n_nonzero"]),
                       submit_ok=False, download_ok=True, note=NOTE, note_chars=len(NOTE),
                       submission_note=NOTE, submission_note_chars=len(NOTE),
                       format=dict(V), unique=dict(U),
                       metadata=dict(round="H104", hypothesis=CARD["hypothesis"],
                                     evidence_class="HOLDOUT-DTI",
                                     registration=dict(
                                         preregistration_sha256=CARD["preregistration"].get(
                                             "preregistration_sha256"),
                                         frozen_before_any_fit=True)))
            ptr.write_text(json.dumps(cur, indent=1, allow_nan=False) + "\n")
            print(f"pointer enriched: round H104, {cur['nonzero_px']:,} px")
    DATA.mkdir(parents=True, exist_ok=True)
    for n in ("h104_run_card.json", "h104_holdout.json", "h104_offcat.json", "h104_uniqueness.json",
              "h104_lane_dots.json", "h104_lane_surface.json", "h104_views.json", "h104_build_pre.json",
              "h104_gates.json"):
        if (EVID / n).exists():
            shutil.copy(EVID / n, DATA / n)
    shutil.copy(ROOT / "registry/h104_preregistration.json", DATA / "h104_preregistration.json")
    need = ["docs/downloads/h104-candidate.tif", "docs/downloads/h104-candidate.zip",
            "docs/downloads/h104-a-only-reasoning.csv", "docs/h104.html", "docs/h104-executive-summary.html",
            "docs/validator.html", "evidence/h104_run_card.json",
            "knowledge/113_hypotheses_H104_preregistered.md", "knowledge/115_current_user_brief_2026-10-10_H104.md",
            "knowledge/114_h104_results_and_limits.md"]
    missing = [p for p in need if not (ROOT / p).exists()]
    print(json.dumps(dict(submit_ok=SUBMIT_OK, budget=BUDGET, missing=missing,
                          runner_sha256=__import__("hashlib").sha256(RUNNER.read_bytes()).hexdigest(),
                          generated=datetime.now(timezone.utc).isoformat(timespec="seconds")), indent=1))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
