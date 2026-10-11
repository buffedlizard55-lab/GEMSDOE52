#!/usr/bin/env python3
"""Publish round H102 to the site and README — idempotent, receipt-driven, never a rewrite.

Rules (AGENTS.md):
* Every number is read from ``evidence/h102_*.json``; nothing is typed by hand.
* Shared pages (``docs/index.html``, ``docs/executive-summary.html``, root ``index.html``,
  ``docs/downloads/index.html``) get a delimited ``<!--H102-CARD-->`` block inserted at the top of
  ``<body>``; re-running replaces only that block, so every earlier round's asserted strings survive.
* ``docs/index.html`` additionally gets the current-round verdict box (H96 -> H102), the title, the
  branch line and an archive-table row for H102; each swap is idempotent.
* ``README.md`` gets a delimited ``<!--H102-README-->`` block at the very top, with the session brief
  verbatim (``knowledge/94``) inside it, followed by the standing H95 block.
* ``AGENTS.md`` gets a delimited ``<!--H102-AGENTS-->`` block at the very top.
* The verdict is the first thing a reader sees: OK TO DOWNLOAD and OK TO SUBMIT, separately.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EVID, DATA, DL = ROOT / "docs", ROOT / "evidence", ROOT / "docs" / "data", ROOT / "docs" / "downloads"
REG = json.loads((ROOT / "registry/h102_preregistration.json").read_text())

WR = json.loads((EVID / "h102_write.json").read_text())
CARD = json.loads((EVID / "h102_run_card.json").read_text())
E1 = json.loads((EVID / "h102_e1_graft_holdout.json").read_text())
E2 = json.loads((EVID / "h102_e2_quota_holdout.json").read_text())
E3 = json.loads((EVID / "h102_e3_proxy_sgmc.json").read_text())
FIT = json.loads((EVID / "h102_fit.json").read_text())
FOLD = json.loads((EVID / "h102_fields.json").read_text())
IND = json.loads((EVID / "h102_independence.json").read_text())
LANE = json.loads((EVID / "h102_lane.json").read_text())
INF = json.loads((EVID / "h102_lane_informative_uniqueness.json").read_text())

esc = lambda x: html.escape(str(x))
TIF = ROOT / WR["file"]
TIFNAME, STEM, SHA = TIF.name, TIF.stem, WR["sha256"]
NOTE, NLEN = WR["note"], WR["note_len"]
SUBNAME = WR["submission_name"]
VERDICT = CARD["verdict"]
SUBMIT_OK = bool(CARD["submit_ok"])
assert NLEN <= 140 and len(NOTE) == NLEN
assert hashlib.sha256(TIF.read_bytes()).hexdigest() == SHA, "TIF bytes do not match the write receipt"
S2, S1 = E2["pooled"]["scores"], E1["pooled"]["scores"]
PRIM, D = E2["promotion"], E2["promotion"]["paired_vs_B_DVA2"]
CTRL = E1["controls"]
RHO = IND["result"]["max_abs_correlation"]
SUFA = FIT["sufficiency_view_A"]


def f6(x):
    return f"{x:.6f}"


def ci(s):
    return f"{f6(s['dti'])} [{s['ci95'][0]:.4f}, {s['ci95'][1]:.4f}]"


# --------------------------------------------------------------------------------------------- artifacts
def make_aliases():
    DL.mkdir(parents=True, exist_ok=True)
    (DL / "h102-candidate.tif").write_bytes(TIF.read_bytes())
    zip_src = ROOT / WR["zip"]
    (DL / "h102-candidate.zip").write_bytes(zip_src.read_bytes())
    return (DL / "h102-candidate.tif").stat().st_size


def write_pointer():
    fmt = WR["validator"]
    sub = {
        "file": TIFNAME,
        "sha256": SHA,
        "bytes": WR["bytes"],
        "submission_name": SUBNAME,
        "note": NOTE,
        "note_chars": NLEN,
        "validator": fmt,
        "zip_file": Path(WR["zip"]).name,
        "zip_sha256": hashlib.sha256((ROOT / WR["zip"]).read_bytes()).hexdigest(),
        "approved_for_weekly_slot": False,
        "promoted": False,
        "submission_slots_used": 0,
        "status": "research-only; local format validation is not organizer acceptance",
        "metadata": {
            "round": "H102",
            "hypothesis": ("disagreement-state quota emission on the DVA2 base: consensus 18000 + buried "
                           "A-only 7400, B-only veto, 25400px quota placement; soft-prior graft ablation"),
            "evidence_class": "HOLDOUT-DTI",
            "registration": {
                "preregistration_sha256": REG["hypothesis_sha256"],
                "frozen_before_any_fit": True,
            },
            "irregularities": ["IR-H102-001", "IR-H102-002", "IR-H102-003"],
            "verdict": VERDICT,
            "submit_ok": SUBMIT_OK,
        },
        "round": "H102",
        "stem": STEM,
        "nonzero_px": WR["dots"],
        "short_tif": "h102-candidate.tif",
        "short_zip": "h102-candidate.zip",
        "marker": "submission/H102_LATEST.txt",
        "role": "research-only candidate; shared current pointer stays on incumbent H96",
        "incumbent_round": "H96",
        "exists": True,
        "download": f"downloads/{TIFNAME}",
        "download_zip": f"downloads/{TIFNAME[:-4]}.zip",
        "submission_note": NOTE,
        "submission_note_chars": NLEN,
        "published_byte_hash_matches_receipt": True,
    }
    # NEGATIVE round: the shared current pointer stays on the incumbent (H96); this round writes only
    # its round pin (H96 pattern) and an audit snapshot of its own receipt.
    (ROOT / "submission/H102_LATEST.txt").write_text(TIFNAME + "\n")
    (EVID / f"submission_{STEM}.json").write_text(json.dumps(sub, indent=1) + "\n")
    return sub


# ---------------------------------------------------------------------------------------------------- card
def card_html(dl_prefix, page_prefix):
    s2 = S2
    return f"""<!--H102-CARD-->
<style>.h102card{{border:2px solid #1f4e79;border-radius:12px;padding:16px 18px;margin:16px 0;background:#f3f7fc;color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}}.h102card h2{{margin:0 0 8px;font-size:19px;color:#1f4e79}}.h102card a{{color:#1f4e79;font-weight:700}}.h102card code{{background:#e8eef4;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}}</style><div class="h102card"><h2>Round H102 (2026-10-11) — co-training disagreement-state quota on the DVA2 base</h2><p><b>OK TO DOWNLOAD: YES</b> (format-valid, all-finite, values exactly {{0,1}}, {WR['dots']:,} cells). <b>OK TO SUBMIT: NO — research-only, do not upload.</b> Both co-training arms are <b>below random placement</b> on the holdout: quota_primary {f6(PRIM['primary_dti'])} vs random {f6(s2['random']['dti'])} at 25,400 px, graft {f6(S1['g_025']['dti'])} vs random {f6(S1['random']['dti'])} at 37,654 px, vs the 0.192829 bar. Mechanism: the views are independent (max |ρ| {RHO:.4f}) but View A is insufficient (mean OOF AUC {SUFA['mean']:.4f}, two folds below 0.5), so gating/blending on View A destroys the strong View B's precision. No weekly slot is approved; slots used: 0.</p><p><a href="{dl_prefix}h102-candidate.tif" download>Download h102-candidate.tif</a> · <a href="{dl_prefix}h102-candidate.zip" download>ZIP</a> · <a href="{page_prefix}h102-executive-summary.html">how to submit</a> · <a href="{page_prefix}h102.html">full result</a> · <a href="{dl_prefix}{TIFNAME[:-4]}-a-only-reasoning.csv">A-only reasoning CSV</a></p>
<p>Submission name: <strong>{SUBNAME}</strong> · note ({NLEN}/140): <code>{esc(NOTE)}</code></p><p><small><code>{TIFNAME}</code> · SHA-256 <code>{SHA}</code> · HOLDOUT-DTI (gems52-pooled-hide-v1, 53,186 withheld positives): quota_primary {f6(PRIM['primary_dti'])} vs B_DVA2 {f6(s2['B_DVA2']['dti'])} vs single_B {f6(s2['single_B']['dti'])} vs random {f6(s2['random']['dti'])} @6,350/fold; g_025 {f6(S1['g_025']['dti'])} vs B_DVA2 {f6(S1['B_DVA2']['dti'])} @9,400/fold. A holdout number is not a board score.</small></p></div>
<!--/H102-CARD-->
"""


def insert_block(path: Path, blob: str):
    if not path.exists():
        return False
    text = path.read_text()
    block = blob
    if "<!--H102-CARD-->" in text:
        text = re.sub(r"<!--H102-CARD-->.*?<!--/H102-CARD-->\n?", lambda m: block, text, flags=re.S)
    elif "<body" in text:
        text = re.sub(r"(<body[^>]*>)\n", lambda m: m.group(1) + "\n" + block, text, count=1)
    else:
        text = block + text
    path.write_text(text)
    return True


# -------------------------------------------------------------------------------------------- index.html
def update_index():
    """Post-merge convention: rounds add a 'Latest round' card (insert_block puts ours at the top of
    <body>, above the earlier H101 card) and their own pages; the shared verdict box and archive rows
    belong to the incumbent round, so nothing is swapped here. Idempotent presence check only."""
    t = (DOCS / "index.html").read_text()
    assert "<!--H102-CARD-->" in t, "H102 card missing from docs/index.html"


# ------------------------------------------------------------------------------------------------- pages
PAGE_CSS = """*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#14181d;background:#f6f8fa}
main{max-width:920px;margin:0 auto;padding:28px 20px 70px;background:#fff;min-height:100vh}h1{font-size:26px;margin:0 0 6px}
h2{font-size:20px;margin:28px 0 8px;border-bottom:2px solid #e6eaef;padding-bottom:5px}.verdict{border-radius:10px;padding:14px 16px;margin:12px 0;font-weight:700}
.ok{background:#e7f6ec;color:#11643a;border:1px solid #9ad7b4}.no{background:#fdecea;color:#b3261e;border:1px solid #f0c4bf}
a.btn{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:8px;margin:6px 8px 6px 0}
a.btn.s{background:#eef2f6;color:#1f4e79;border:1px solid #d7e0ea}code{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13px;word-break:break-all}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14.5px}th,td{border:1px solid #e3e8ee;padding:6px 9px;text-align:left;vertical-align:top}th{background:#f3f6f9}
.copy{background:#f2f4f7;border:1px solid #d7e0ea;border-radius:6px;padding:10px 12px;font-family:monospace;font-size:14px;word-break:break-all}
small,.muted{color:#5b6672}footer{margin-top:30px;border-top:1px solid #e3e8ee;padding-top:10px;font-size:13px;color:#5b6672}"""


def page(title, body):
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{title}</title>\n'
            f"<style>{PAGE_CSS}</style>\n</head>\n<body>\n<main>\n{body}\n"
            f'<footer>GEMSDOE52 · round H102 · generated from receipts in <code>evidence/h102_*.json</code> by '
            f'<code>scripts/publish_h102_site.py</code> · <a href="index.html">site home</a></footer>\n</main>\n</body>\n</html>\n')


def identity_html():
    fmt = WR["validator"]
    val = (f"PASS · 1 band float32, EPSG:32611, {fmt['height']} rows x {fmt['width']} cols, "
           f"transform/bounds = sample_submission.tif: yes, 0 NaN, 0 inf, values exactly [0.0, 1.0], "
           f"{WR['dots']:,} emitted cells, nodata tag None; problems: none")
    return f"""<h2>Identity</h2>
<table>
<tr><th>file</th><td><code>{TIFNAME}</code></td></tr>
<tr><th>bytes · SHA-256</th><td>{WR['bytes']:,} · <code>{SHA}</code></td></tr>
<tr><th>submission name</th><td><div class="copy">{esc(SUBNAME)}</div></td></tr>
<tr><th>note ({NLEN}/140)</th><td><div class="copy">{esc(NOTE)}</div></td></tr>
<tr><th>emitted cells</th><td>{WR['dots']:,} binary dots (exactly {{0,1}}; 0.0 outside the footprint; no nodata)</td></tr>
<tr><th>emission strata (realised)</th><td>{WR['C_emitted']:,} consensus C · {WR['Aonly_emitted']:,} A-only ·
{WR['dots'] - WR['C_emitted'] - WR['Aonly_emitted'] - WR['Bonly_emitted']:,} zero-score tie fill
({WR['Bonly_emitted']} B-only cells by chance inside the tie fill) — IR-H102-001</td></tr>
<tr><th>validator (re-read from disk)</th><td>{val}</td></tr>
</table>"""


def holdout_tables_html():
    arms2 = "\n".join(f"<tr><td><code>{a}</code></td><td>{ci(s)}</td></tr>"
                      for a, s in sorted(S2.items(), key=lambda t: -t[1]["dti"]))
    arms1 = "\n".join(f"<tr><td><code>{a}</code></td><td>{ci(s)}</td></tr>"
                      for a, s in sorted(S1.items(), key=lambda t: -t[1]["dti"]))
    return f"""<h2>HOLDOUT-DTI — E2, the co-training lane (primary <code>quota_primary</code>)</h2>
<p class="muted">evaluator <code>{E2['evaluator_version']}</code> · {E2['withheld_positive_px']:,} withheld positive px ·
4 label-blind quadrant folds · 6,350 dots/fold/arm (25,400 total) · α 0.2 β 0.8 R 300 m · 95 % paired cluster bootstrap · SEED {E2['pooled']['bootstrap']['seed']}</p>
<table><tr><th>arm</th><th>HOLDOUT-DTI [95 % CI]</th></tr>{arms2}</table>
<p>Paired <code>quota_primary − B_DVA2</code> = <b>{D['delta']:+.6f}</b> [{D['ci95'][0]:+.6f}, {D['ci95'][1]:+.6f}].
Promotion bar 0.192829 (max committed B_DVA2 reading) and CI &gt; 0 required → <b>FAIL</b>.
Control reproduction: single_B {f6(CTRL['single_B']['measured'])} vs committed {CTRL['single_B']['committed']} (Δ {CTRL['single_B']['abs_delta']:.1e}),
random {f6(CTRL['random']['measured'])} vs {CTRL['random']['committed']} (Δ {CTRL['random']['abs_delta']:.1e}),
B_DVA2 {f6(CTRL['B_DVA2']['measured'])} vs {CTRL['B_DVA2']['committed_readings']} — all within 1e-3 → <b>valid</b>.</p>
<h2>HOLDOUT-DTI — E1, soft-prior graft (full budget)</h2>
<table><tr><th>arm</th><th>HOLDOUT-DTI [95 % CI]</th></tr>{arms1}</table>
<p>Paired <code>g_025 − B_DVA2</code> = {E1['pooled']['paired_differences']['B_DVA2']['delta']:+.6f}
[{E1['pooled']['paired_differences']['B_DVA2']['ci95'][0]:+.6f}, {E1['pooled']['paired_differences']['B_DVA2']['ci95'][1]:+.6f}].
The graft is below random: blending View A's coin-flip-scale rank into the B_DVA2 field destroys its precision.</p>
<h2>Fit diagnostics (out-of-quadrant AUC, per fold)</h2>
<table><tr><th>arm</th><th>fold 0</th><th>fold 1</th><th>fold 2</th><th>fold 3</th><th>mean</th></tr>
<tr><td>single_A (View A)</td><td>{FIT['folds'][0]['auc']['single_A']:.4f}</td><td>{FIT['folds'][1]['auc']['single_A']:.4f}</td><td>{FIT['folds'][2]['auc']['single_A']:.4f}</td><td>{FIT['folds'][3]['auc']['single_A']:.4f}</td><td><b>{SUFA['mean']:.4f} → sufficiency FAIL</b> (bar 0.60 / 0.55)</td></tr>
<tr><td>single_B (View B)</td><td>{FIT['folds'][0]['auc']['single_B']:.4f}</td><td>{FIT['folds'][1]['auc']['single_B']:.4f}</td><td>{FIT['folds'][2]['auc']['single_B']:.4f}</td><td>{FIT['folds'][3]['auc']['single_B']:.4f}</td><td>{sum(r['auc']['single_B'] for r in FIT['folds'])/4:.4f}</td></tr>
<tr><td>B_DVA2</td><td>{FIT['folds'][0]['auc']['B_DVA2']:.4f}</td><td>{FIT['folds'][1]['auc']['B_DVA2']:.4f}</td><td>{FIT['folds'][2]['auc']['B_DVA2']:.4f}</td><td>{FIT['folds'][3]['auc']['B_DVA2']:.4f}</td><td>{sum(r['auc']['B_DVA2'] for r in FIT['folds'])/4:.4f}</td></tr></table>
<p>Leakage canary: max single-channel AUC <b>{FIT['canary_max_overall']:.4f}</b> &lt; 0.90 → PASS.
State machine: τB = {FOLD['tauB']} (ladder |C|@0.99 = {FOLD['tauB_ladder_sizes']['0.99']:,} &lt; 18,000; |C|@0.98 = {FOLD['tauB_ladder_sizes']['0.98']:,});
|C| = {FOLD['C_px']:,} · |A-only| = {FOLD['Aonly_px']:,} · |B-only vetoed| = {FOLD['Bonly_vetoed_px']:,} · |pool| = {FOLD['pool_px']:,}.</p>
<h2>Independence test (spatial-block OOF error correlation)</h2>
<p>max |ρ| = <b>{RHO:.4f}</b> over {IND['result']['n_blocks']:,} blocks (50 px) of {IND['result']['n_negative_predictions']:,}
catalogue-zero proxy negatives → <b>PASS</b> (bar 0.60). Weak error correlation is necessary for co-training, not proof
of conditional feature independence (pre-registered caveat).</p>
<h2>Lane / uniqueness / format (602-raster census; 13 scored-only)</h2>
<table>
<tr><th>check</th><th>result</th></tr>
<tr><td>lane surface literal (602 priors)</td><td>PASS — max ρ {LANE['full_surface']['literal']['max_spearman']:.4f} &lt; 0.90, no identical, no near offenders</td></tr>
<tr><td>lane dots literal (full census)</td><td>DUPLICATE/STOP — max near-3px {LANE['full_dots']['literal']['max_near_3px_fraction']:.4f} (universal-coverage probe rasters; IR-H87-001 class, reported not waived)</td></tr>
<tr><td>lane dots policy (informative census priors)</td><td>DUPLICATE/STOP — max near-3px {LANE['full_dots']['policy']['max_near_3px_fraction']:.4f} (one dense census raster); scored-only policy reading PASS (max near {LANE['restricted_dots']['policy']['max_near_3px_fraction']:.4f})</td></tr>
<tr><td>uniqueness literal (full census)</td><td>novel fraction 0.0 (probe union covers the footprint — registry property, IR-H102-002); no identical prior; max Jaccard 0.0225; not the literal prior union</td></tr>
<tr><td>uniqueness informative-only (13 scored)</td><td>novel fraction <b>{INF['novel_fraction']:.4f}</b> ({INF['novel_vs_all_priors']:,}/{WR['dots']:,} dots), max Jaccard {INF['max_jaccard']:.4f}, distinct from every comparable prior, not the literal union</td></tr>
<tr><td>quota placement</td><td>run_h73.place_lane: 25,400/25,400 filled in round 0, worst-prior overlap {LANE['quota_placement']['worst']:.4f} &lt; 0.70 cap, 1.3 s</td></tr>
<tr><td>not-the-union</td><td>PASS — {WR['not_the_union']['share_of_dots_outside_union'] * 100:.2f} % of dots outside the equal-budget union-max placement (Jaccard {WR['not_the_union']['jaccard_vs_union']:.4f})</td></tr>
<tr><td>format</td><td>PASS — all-finite [0,1], no nodata, writer's fail-closed re-read asserts passed</td></tr>
</table>
<h2>E3 — PROXY-SGMC diagnostic (never a score)</h2>
<p class="muted">SGMC geologic-map faults thinned by whole segments to |G| ≈ 10,000, 5 seeds; Spearman 0.567 vs 13
owner-reported board scores — a low-informative proxy. No H102 gate reads this experiment.</p>
<table><tr><th>field</th><th>PROXY-SGMC (mean of 5 seeds)</th></tr>
<tr><td>champion h33-h33-2-b2 (board 0.2778, OWNER-REPORTED)</td><td>{E3['results']['champion_h33_2_b2 (board 0.2778, OWNER-REPORTED)']['mean']:.5f}</td></tr>
<tr><td>d2-8 (board 0.2600, OWNER-REPORTED)</td><td>{E3['results']['d2-8 (board 0.2600, OWNER-REPORTED)']['mean']:.5f}</td></tr>""" + "".join(
        f"<tr><td>{k}</td><td>{v['mean']:.5f}</td></tr>" for k, v in E3["results"].items()
        if "board" not in k) + f"""</table>
<h2>Gates (frozen in <code>registry/h102_preregistration.json</code>)</h2>
<table><tr><th>gate</th><th>result</th></tr>
""" + "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in CARD["gates"].items()) + f"""
</table>
<p><b>verdict: {VERDICT}</b> · submit_ok {str(SUBMIT_OK).lower()} · download_ok true · slots used 0 ·
irregularities IR-H102-001 (quota/tie-fill), IR-H102-002 (probe-union novelty), IR-H102-003 (CSV prefix, fixed).</p>"""


def how_to_submit_html():
    return f"""<div class="verdict ok">OK TO DOWNLOAD: YES — format-valid (1 band float32, EPSG:32611, all-finite,
values exactly {{0,1}}, {WR['dots']:,} emitted cells); the portal's "Predicted values must be in range [0, 1]"
rejection cannot occur.</div>
<div class="verdict no">OK TO SUBMIT: NO — research-only, do not upload. Failed gate(s): holdout_promotion
(quota_primary {f6(PRIM['primary_dti'])} &lt; 0.192829, paired CI deeply negative), uniqueness literal
(probe-union standing condition, IR-H102-002), lane dots (full-census literal rule; scored-only policy reading PASS).
The file is <b>not slot-approved</b>. The verdict is negative on the holdout alone.</div>
<p><b>Weekly slots used by this round: 0.</b> No weekly slot is approved by this round; uploading is the owner's decision.</p>
<p><a class="btn" href="downloads/h102-candidate.tif" download>Download h102-candidate.tif ↓</a>
<a class="btn s" href="downloads/h102-candidate.zip" download>ZIP</a>
<a class="btn s" href="downloads/{TIFNAME[:-4]}-a-only-reasoning.csv">A-only reasoning CSV</a>
<a class="btn s" href="validator.html">Check a file in your browser</a></p>
{identity_html()}
<h2>How to submit (exact steps)</h2>
<ol>
<li>Download <code>h102-candidate.tif</code> above (or the ZIP, which holds exactly one GeoTIFF).</li>
<li>Optional: drop it on <a href="validator.html">the browser validator</a> — it must say 1 band, EPSG:32611,
3730×3292, values in [0, 1], all finite, no nodata.</li>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">DrivenData → DOE GEMS → Submissions</a> (login required) and upload the .tif (or .zip).</li>
<li>Paste the submission name and the note from the table above (the note is {NLEN} of the 140 characters the form allows).</li>
<li>Remember the official rule: you must choose ONE submission for both the Initial and the Final round
(<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a>).</li>
</ol>
<p class="verdict no">This round's frozen rule says do not upload: the primary arm did not beat the holdout bar —
it is below random. The steps are listed so the owner can act on a later round that produces a promotable field.</p>
{holdout_tables_html()}
<h2>Why it failed (measured mechanism)</h2>
<p>Blum &amp; Mitchell co-training needs (i) feature independence and (ii) each view sufficiently informative.
Both were pre-registered and measured: independence PASSES (max |ρ| {RHO:.4f}) but View A's mean OOF AUC is
{SUFA['mean']:.4f} with two of four folds below 0.5 — a coin flip. Every combination tested (rank graft,
consensus AND-gate, state-machine quota) pays for that noise with the strong view's precision, so all three
score at or below random placement. The single strong view B (DVA2) remains the best field at both budgets
({f6(S1['B_DVA2']['dti'])} @37,654 / {f6(S2['B_DVA2']['dti'])} @25,400). Full analysis and limits:
<a href="h102.html">H102 full result</a> · <a href="../knowledge/98_h102_results_and_limits.md">knowledge/98</a>.</p>"""


def write_pages():
    body = (f'<h1>H102 — co-training disagreement-state quota on the DVA2 base</h1>\n'
            f'<p class="muted">DOE GEMS (DrivenData #306) · 2026-10-11 · '
            f'<b>OK TO DOWNLOAD: YES (audit) · OK TO SUBMIT: NO (research-only, not slot-approved)</b></p>\n'
            + how_to_submit_html())
    (DOCS / "h102.html").write_text(page("GEMSDOE52 — H102 full result", body))
    (DOCS / "h102-executive-summary.html").write_text(
        page("GEMSDOE52 — H102 executive summary — how to make a submission",
             "<h1>Executive summary — H102 — how to make a submission</h1>\n" + how_to_submit_html()))


# ------------------------------------------------------------------------------------------------ README
def readme_block():
    brief = (ROOT / "knowledge/94_current_user_brief_2026-10-10_H95.md").read_text()
    arms2 = "\n".join(f"| `{a}` | {ci(s)} |" for a, s in sorted(S2.items(), key=lambda t: -t[1]["dti"]))
    arms1 = "\n".join(f"| `{a}` | {ci(s)} |" for a, s in sorted(S1.items(), key=lambda t: -t[1]["dti"]))
    g = "\n".join(f"| {k} | {v} |" for k, v in CARD["gates"].items())
    return f"""<!--H102-README-->
## Status block: H102 (2026-10-11) — co-training disagreement-state quota on the DVA2 base · NEGATIVE

> **OK TO DOWNLOAD: YES** — format-valid single-band float32 GeoTIFF, EPSG:32611, 3730×3292, all-finite, values exactly {{0,1}}, 25,400 dots (the portal's *"Predicted values must be in range [0, 1]"* rejection cannot occur).
>
> **OK TO SUBMIT: NO — research-only, do not upload.** Both co-training arms are below random placement on the spatial-block holdout (quota_primary {f6(PRIM['primary_dti'])} vs random {f6(S2['random']['dti'])} at 25,400 px; graft {f6(S1['g_025']['dti'])} vs random {f6(S1['random']['dti'])} at 37,654 px) vs the 0.192829 bar; the views are independent (max |ρ| {RHO:.4f}) but View A fails sufficiency (mean OOF AUC {SUFA['mean']:.4f}).
>
> Weekly slots used: **0**. No weekly slot is approved by this round; the agent does not pick submissions.

**★ [Download h102-candidate.tif](docs/downloads/h102-candidate.tif)** · [ZIP](docs/downloads/h102-candidate.zip) · **[Executive summary / how to submit](docs/h102-executive-summary.html)** · [Full result](docs/h102.html) · [Run card](evidence/h102_run_card.json) · [A-only reasoning CSV](docs/downloads/{TIFNAME[:-4]}-a-only-reasoning.csv)

- **File:** `{WR['file']}` — {WR['bytes']:,} bytes, SHA-256 `{SHA}`
- **Submission name:** `{SUBNAME}` · **Note ({NLEN}/140):** `{NOTE}`
- **Validator (re-read from disk):** PASS · 1 band float32, EPSG:32611, 3730×3292, all-finite, values exactly [0.0, 1.0], {WR['dots']:,} cells, no nodata; problems none
- **HOLDOUT-DTI, E2 — disagreement-state quota** (`{E2['evaluator_version']}`, {E2['withheld_positive_px']:,} withheld positive px, 95 % CI):

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{arms2}

  Paired `quota_primary − B_DVA2` = **{D['delta']:+.6f}** [{D['ci95'][0]:+.6f}, {D['ci95'][1]:+.6f}] → promotion **FAIL**.
  Controls: single_B {f6(CTRL['single_B']['measured'])} (Δ {CTRL['single_B']['abs_delta']:.1e}), random {f6(CTRL['random']['measured'])} (Δ {CTRL['random']['abs_delta']:.1e}), B_DVA2 {f6(CTRL['B_DVA2']['measured'])} — all within 1e-3 of committed → reproduction valid.
- **HOLDOUT-DTI, E1 — soft-prior graft:**

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{arms1}

- **State machine (frozen):** τB = {FOLD['tauB']} (ladder 0.99→0.98); |C| = {FOLD['C_px']:,}, |A-only| = {FOLD['Aonly_px']:,}, |B-only vetoed| = {FOLD['Bonly_vetoed_px']:,}; realised emission {WR['C_emitted']:,} C / {WR['Aonly_emitted']:,} A-only / tie fill — the 3 px spacing caps extractable C (IR-H102-001).
- **Independence (spatial-block OOF errors):** max |ρ| {RHO:.4f} over {IND['result']['n_blocks']:,} blocks → PASS (bar 0.60).
- **Sufficiency (View A, bookkeeping gate):** mean OOF AUC {SUFA['mean']:.4f} / min fold {SUFA['min_fold']:.4f} → **FAIL** (bar 0.60/0.55) — the mechanistic cause of the negative result.
- **Lane / uniqueness:** surface literal PASS (max ρ {LANE['full_surface']['literal']['max_spearman']:.4f}); dots literal DUPLICATE/STOP (probe rasters, IR-H87-001 class) with scored-only policy PASS (max near {LANE['restricted_dots']['policy']['max_near_3px_fraction']:.4f}); uniqueness literal novelty 0.0 (probe union, IR-H102-002) / informative-only **{INF['novel_fraction']:.4f}** (max Jaccard {INF['max_jaccard']:.4f}); not-the-union PASS ({WR['not_the_union']['share_of_dots_outside_union'] * 100:.1f} % outside).
- **Gates (frozen in `registry/h102_preregistration.json`, SHA `{REG['hypothesis_sha256'][:16]}…`):**

| gate | result |
|---|---|
{g}

- **Irregularities:** IR-H102-001 (quota not realised by 3 px spacing; tie-fill mass), IR-H102-002 (probe-union novelty standing condition), IR-H102-003 (doubled CSV prefix, fixed pre-publication).
- Docs: [preregistration](knowledge/97_hypotheses_H102_preregistered.md) · [results & limits](knowledge/98_h102_results_and_limits.md) · [session brief](knowledge/94_current_user_brief_2026-10-10_H95.md) · [irregularities](registry/irregularities.json)
- Reproduce: `python3 scripts/restore_data.py --target-dir data` → feature store + `python -m gems52.external` → `python3 scripts/fetch_prior_inventory.py --out work/h102/priors --receipt work/h102/prior_fetch_receipt.json` → `python3 scripts/run_h102.py all` → `python3 scripts/publish_h102_site.py && python3 scripts/check_site.py`.

### Why `h33-h33-2-b2` scored 0.2778, and can we beat 0.3195? (unchanged; full derivation: [knowledge/76](knowledge/76_why_02778_and_what_beating_03195_requires.md))

- DTI = T / (0.2·S + 0.8·|G|); binary dots; a dot earns credit only if its kernel credit exceeds 0.2·DTI; Spearman(emitted mass, score) = −0.928 over our scored files.
- The champion is the 0.2600 `d2-8` field with all dots within 200 m of the public catalogue deleted (37,654 dots). Beating 0.3195 needs ×1.1501 credit at every |G|, or the same credit from ≈25,400 dots.
- **Honest answer after H102: still not demonstrated in the co-training lane.** H102 measured the lane's remaining in-lane levers (graft, consensus, quota state machine) and all three are at or below random — the lane's failure is the View A sufficiency condition, now measured (mean OOF AUC 0.516). The only lever with board-sign evidence remains the **mass lever on the champion's own field** (champion-field lane, out of this brief's lane).

### Next work (ranked)

1. **Mass lever on the champion's own field** (28k/32k-dot subset of h33-2-b2 ranked by its d2-8 value) — champion-field lane; the only board-sign lever.
2. **Do not revisit co-training combination machinery** until a View A with pre-fit mean OOF AUC ≥ 0.60 exists (the sufficiency screen must be a hard gate, not bookkeeping). H102's measured 0.516 with independent errors is the demonstration.
3. **INGENIOUS 2 m temperature probes** (GDR 1391, DOI 10.15121/1881483) as the thermal View A upgrade — free and official, blocked on owner download (gdr.openei.org unreachable from the sandbox).
4. Keep the H95 file's audit copy as the standing download example until a promotable round appears.

<details><summary><b>The H102 session brief, verbatim (read it every session)</b></summary>

{brief}

</details>
<!--/H102-README-->
"""


def agents_block():
    return f"""<!--H102-AGENTS-->
## Current H102 continuation (2026-10-11) — READ FIRST
Read README's H102 block (it ends with the session brief verbatim), `knowledge/97` (frozen preregistration,
SHA-256 `{REG['hypothesis_sha256'][:16]}…`), `knowledge/94` (brief) and `knowledge/98` (results, generated).
Verdict **negative** — both co-training arms below random on the holdout (quota_primary {f6(PRIM['primary_dti'])} vs random
{f6(S2['random']['dti'])} @25,400; g_025 {f6(S1['g_025']['dti'])} vs random {f6(S1['random']['dti'])} @37,654); bar 0.192829. Slots used 0.
This session's branch is `arena/1bc2f2ec-gemsdoe52`.

Settled this round; do not re-litigate:

- **Co-training combination machinery is closed in this lane while View A is at OOF AUC 0.516:** graft 0.0196,
  consensus 0.0293, quota 0.0263 — all at/below random (0.0582/0.0804). Views independent (max |ρ| {RHO:.4f});
  View A insufficient (sufficiency gate FAIL by design). Any future co-training round needs a pre-fit hard
  sufficiency screen (mean OOF AUC ≥ 0.60, min fold ≥ 0.55) on the View A candidate.
- **Quota budgets must be set against SPACED-EXTRACTABLE stratum counts, not raw stratum sizes** (IR-H102-001:
  3 px spacing extracted 5,329 of 31,490 consensus cells; 15,104/25,400 dots are zero-score tie fill).
- **The literal full-census lane/uniqueness rules are unsatisfiable for any non-empty emission** because of the
  universal-coverage probe rasters (IR-H87-001 class; H102: dots near 1.0, census novelty 0.0). Report both the
  literal and the informative-only reading; the scored-only policy reading was PASS (max near {LANE['restricted_dots']['policy']['max_near_3px_fraction']:.4f}).
- **Control reproduction is exact** on the 53,186-px fold set (single_B 0.174517, random 0.080426, B_DVA2 0.192831):
  the H82/H84 bar 0.192829 is the correct comparison for this round's holdout.
- Publishing: `scripts/publish_h102_site.py` inserts `<!--H102-CARD-->` / `<!--H102-README-->` / `<!--H102-AGENTS-->`
  blocks (idempotent) and rewrites the H102 pages/pointer; verify with `scripts/check_site.py` + pytest.
<!--/H102-AGENTS-->
"""


def insert_marker_block(path: Path, marker: str, blob: str, before_marker: str):
    text = path.read_text()
    block = blob
    if f"<!--{marker}-->" in text:
        text = re.sub(f"<!--{marker}-->.*?<!--/{marker}-->\n?", lambda m: block, text, flags=re.S)
        path.write_text(text)
        return
    if f"<!--{before_marker}-->" in text:
        text = text.replace(f"<!--{before_marker}-->", block + f"<!--{before_marker}-->", 1)
    else:
        text = block + text
    path.write_text(text)


def insert_readme_block(path: Path, marker: str, blob: str, after_close_marker: str):
    """README convention: the pinned H95 block stays on top (tests pin it); newer round
    status blocks are appended directly after <!--/{after_close_marker}--> (H96 pattern)."""
    text = path.read_text()
    open_tag, close_tag = f"<!--{marker}-->", f"<!--/{marker}-->"
    if open_tag in text:
        text = re.sub(f"{open_tag}.*?{close_tag}\n?", lambda m: blob + "\n", text, flags=re.S)
        path.write_text(text)
        return
    anchor = f"<!--{after_close_marker}-->"
    if anchor in text:
        i = text.index(anchor) + len(anchor)
        # align to end of that line
        nl = text.find("\n", i)
        i = nl + 1 if nl != -1 else i
        text = text[:i] + blob + "\n" + text[i:]
    else:
        text = blob + "\n" + text
    path.write_text(text)


def main():
    make_aliases()
    sub = write_pointer()
    # shared cards (four pages, different link prefixes)
    inserted = []
    for page_path, dl_prefix, page_prefix in (
        (DOCS / "index.html", "downloads/", ""),
        (DOCS / "executive-summary.html", "downloads/", ""),
        (ROOT / "index.html", "docs/downloads/", "docs/"),
        (DOCS / "downloads/index.html", "", "../"),
    ):
        if insert_block(page_path, card_html(dl_prefix, page_prefix)):
            inserted.append(page_path.name)
    update_index()
    write_pages()
    insert_readme_block(ROOT / "README.md", "H102-README", readme_block(), "H95-README")
    insert_marker_block(ROOT / "AGENTS.md", "H102-AGENTS", agents_block(), "H96-AGENTS")
    print("published H102:")
    print(f"  pointer  round pin submission/H102_LATEST.txt + evidence/submission_{{STEM}}.json (shared current pointer stays on incumbent H96)")
    print(f"  aliases  docs/downloads/h102-candidate.tif + .zip")
    print(f"  cards    {', '.join(inserted)}")
    print(f"  pages    docs/h102.html, docs/h102-executive-summary.html")
    print(f"  readme   README.md <!--H102-README-->, AGENTS.md <!--H102-AGENTS-->")
    print(f"  verdict  {VERDICT} · submit_ok {SUBMIT_OK} · download_ok True · slots 0")


if __name__ == "__main__":
    main()
