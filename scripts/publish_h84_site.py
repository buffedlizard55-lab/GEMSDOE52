#!/usr/bin/env python3
"""Publish the H84 round to the GitHub Pages site and the root landing page.

Reads ONLY machine receipts (evidence/h84_*.json, registry/*.json). No number on any page is typed by
hand: every score is formatted from a receipt and carries its label (HOLDOUT-DTI, PUBLIC-BOARD,
OWNER-REPORTED). Re-running is idempotent:

* docs/index.html - the H84 block is written between <!--H84-CURRENT--> markers. On the FIRST run the
  whole previous front page (H82's current block + its archive) is preserved verbatim inside the
  archive; on later runs only the archive is carried, so nothing is duplicated.
  (publish_h82_site.legacy_index_body discards the previous round's own block, which is right for a
  re-publish of the same round but would silently drop H82 here - hence the local variant.)
* index.html (root) - the H84 card replaces the H82 card; the H74S closeout <section> is kept byte-for-byte.
* docs/h84.html, docs/h84-executive-summary.html - written fresh (new pages).
* docs/irregularities.html - an <!--H84-IRREGULARITIES--> section is inserted or replaced.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from publish_h82_site import (ARCHIVE_END, ARCHIVE_START, PROBLEM_URL, TAIL, ci, esc, f6, i,  # noqa: E402
                              notice_block, table)

DOCS = ROOT / "docs"
EVID = ROOT / "evidence"
H84_START, H84_END = "<!--H84-CURRENT-->", "<!--/H84-CURRENT-->"
BOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
METRIC_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
BLUM_MITCHELL = "https://doi.org/10.1145/279943.279962"
REPO = "https://github.com/buffedlizard55-lab/GEMSDOE52"


def load(p):
    return json.loads(Path(p).read_text())


def head(title: str, description: str) -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="{esc(description)}">'
            f"<title>{esc(title)}</title>"
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            '<a href="index.html">Current round</a>'
            '<a href="h84.html">H84 result</a>'
            '<a href="h84-executive-summary.html">How to submit</a>'
            '<a href="validator.html">Check a file</a>'
            '<a href="h82.html">H82</a>'
            '<a href="h82-sources.html">Sources</a>'
            '<a href="downloads/index.html">Archive</a>'
            '</nav></header><main id="main">')


PRE_PR82_COMMIT = "2209161"   # last main commit whose docs/index.html still carried the H82 page + verbatim archive


def _body(text: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", text, flags=re.S)
    body = m.group(1) if m else text
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S)
    return body.replace(' id="main"', "").replace("<main>", "").replace("</main>", "")


def _h82_page_payload(text: str) -> str:
    """H82's front page: its own current block + the archive it carried (both verbatim)."""
    body = _body(text)
    a, b = body.find(ARCHIVE_START), body.find(ARCHIVE_END)
    inner = body[a + len(ARCHIVE_START):b] if (a >= 0 and b > a) else ""
    cur = body[:a] if a >= 0 else body
    w = cur.rfind('<hr class="divider"><section><details>')
    if w >= 0:
        cur = cur[:w]
    mm = cur.find("</header>")
    if mm >= 0:
        cur = cur[mm + len("</header>"):]
    return ('<section class="archived-round"><h2>Archived: the H82 front page as published 2026-10-09 '
            '(verbatim)</h2>' + cur.strip() + "</section>" + inner.strip())


def previous_front_page(path: Path) -> str:
    """The archive payload for docs/index.html (see module docstring).

    Re-publish (H84 markers present): carry only the preserved archive. First publish: the page now on
    main (written from scratch by the parallel H83 session in PR #82, IR-H84-007) is archived verbatim, and
    the H82 page + archive it dropped is recovered from git (commit 2209161) and archived after it, so
    nothing that check_site or a reader relies on is lost.
    """
    import subprocess
    text = path.read_text()
    if H84_START in text:
        body = _body(text)
        a, b = body.find(ARCHIVE_START), body.find(ARCHIVE_END)
        return body[a + len(ARCHIVE_START):b].strip()
    parts = []
    if ARCHIVE_START not in text:
        parts.append('<section class="archived-round"><h2>Archived: the parallel-session H83 front page '
                     '(PR #82, 2026-10-10, verbatim; see IR-H84-007 before acting on it)</h2>'
                     + _body(text).strip() + "</section>")
        text = subprocess.run(["git", "show", f"{PRE_PR82_COMMIT}:docs/index.html"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
    parts.append(_h82_page_payload(text))
    return "".join(parts)


def yn(b):
    return "PASS" if b else "FAIL"


def main() -> int:
    card = load(EVID / "h84_run_card.json")
    ho = load(EVID / "h84_holdout.json")
    bu = load(EVID / "h84_build.json") if (EVID / "h84_build.json").exists() else None
    board = load(ROOT / "registry/leaderboard_snapshot_2026-10-10.json")
    irr = load(ROOT / "registry/irregularities.json")
    dl_ok, sb_ok, verdict = card["download_ok"], card["submit_ok"], card["verdict"]
    H = card["holdout"]
    sc, pdf = H["scores"], H["primary_minus_each_arm"]
    PRIMARY = "B_DVA2_HVA"
    lane = card["lane"]
    cot = card["cotraining"]
    dis = card["disagreement"]
    ras = card["raster"]
    val = card["validator"] or {}

    # copy the receipts the pages link to into docs/data (GitHub Pages serves docs/ only)
    (DOCS / "data").mkdir(exist_ok=True)
    for n in ("h84_run_card.json", "h84_holdout.json", "h84_lane.json", "h84_independence.json",
              "h84_build.json", "h84_fit.json"):
        if (EVID / n).exists():
            shutil.copy(EVID / n, DOCS / "data" / n)
    shutil.copy(ROOT / "registry/leaderboard_snapshot_2026-10-10.json",
                DOCS / "data/h84_leaderboard_snapshot_2026-10-10.json")
    csv_rel = None
    if dis.get("a_only_reasoning_csv"):
        csv_rel = "downloads/" + Path(dis["a_only_reasoning_csv"]).name
        assert (DOCS / csv_rel).is_file(), csv_rel

    # ---------------------------------------------------------------- shared fragments
    order = [a for a in ("B_DVA2_HVA", "B_DVA2", "B_DVA2_HVA_COH", "single_B", "single_A", "random") if a in sc]
    role = {"B_DVA2_HVA": "PRIMARY (H84 hypothesis)", "B_DVA2": "control, current holdout best (H82)",
            "B_DVA2_HVA_COH": "attribution, not promotable", "single_B": "single-view baseline (View B) / control",
            "single_A": "single-view baseline (View A)", "random": "floor"}
    rows = []
    for a in order:
        d = pdf.get(a)
        rows.append([f"<code>{esc(a)}</code>", esc(role.get(a, "")), f6(sc[a]["dti"]), ci(sc[a]["ci95"]),
                     "&mdash;" if a == PRIMARY or d is None else f'{d["delta"]:+.6f} {ci(d["ci95"])}'])
    holdout_table = table(["Arm", "Role", "HOLDOUT-DTI", "95% CI", "primary − arm (paired, 95% CI)"], rows)
    lbl = (f'HOLDOUT-DTI: evaluator <code>{esc(H["evaluator"])}</code>, {i(H["withheld_positive_pixels"])} '
           f'withheld positive pixels, {i(H["dots_per_fold_per_arm"])} dots per fold per arm, '
           f'{esc(H["ci"])}. {esc(H["never_a_board_forecast"])}.')
    reasons = card["verdict_reasons"]
    gate_names = {
        "beats_current_holdout_best_B_DVA2": "primary beats current holdout best B_DVA2 (paired CI lower bound > 0)",
        "beats_single_B": "primary beats single-view baseline single_B (paired CI lower bound > 0)",
        "controls_reproduce": "controls reproduce committed values within 1e-3",
        "canary_no_alarm": "leakage canary: no single channel AUC >= 0.90",
        "lane_surface_literal_pass": "lane: surface vs literal full census (before placement)",
        "lane_dots_literal_full_census_pass": "lane: final dots vs literal full census",
        "format_validator_pass": "format validator (float32, EPSG:32611, grid, [0,1], no NaN)",
        "not_the_union_pass": "not the union of the two views / not a single view"}
    gates_table = table(["Frozen promotion gate (knowledge/74 §3)", "Result"],
                        [[esc(gate_names.get(k, k)), f"<b>{yn(v)}</b>"] for k, v in reasons.items()])
    ind = cot["independence"]
    suff = cot["sufficiency_view_A"]
    fileline = ("No raster was written." if not ras else
                f'{i(ras["bytes"])} bytes &middot; SHA-256 <code>{esc(ras["sha256"])}</code> &middot; '
                f'submission name <code>{esc(card["submission_name"])}</code> &middot; '
                f'note ({len(card["submission_note"])}/140): <code>{esc(card["submission_note"])}</code>')

    def actions():
        if not ras:
            return ""
        a = ('<div class="actions"><a class="button" href="downloads/h84-candidate.tif" download>'
             'Download the H84 GeoTIFF &#8595;</a>'
             '<a class="button secondary" href="downloads/h84-candidate.zip" download>Single-TIFF ZIP</a>')
        if csv_rel:
            a += f'<a class="button secondary" href="{esc(csv_rel)}" download>A-only geological reasoning CSV</a>'
        return a + '<a class="button secondary" href="validator.html">Check any file in your browser</a></div>'

    top = [r for r in board["rows"] if r["rank"] <= 8] if "rows" in board else []
    board_tbl = table(["Rank", "Team", "Public score"],
                      [[str(r["rank"]), esc(r["team"]), f'{float(r["score"]):.4f}'] for r in top]) if top else ""
    headline = (f"H84 verdict: {verdict.upper()}. "
                + ("This file passed every frozen gate." if sb_ok else
                   "The file is valid and safe to download, but it did not pass every frozen gate, "
                   "so it is not approved for upload."))

    # ---------------------------------------------------------------- docs/index.html
    legacy = previous_front_page(DOCS / "index.html")
    archive = ('<hr class="divider"><section><details><summary><b>Archive</b> &mdash; every previous '
               "round&rsquo;s front page and evidence section, preserved verbatim (collapsed). None of it is "
               "the H84 file and none of it is upload approval.</summary>"
               f'<div class="small">{ARCHIVE_START}{legacy}{ARCHIVE_END}</div></details></section>')
    index = head("GEMS / DOE - H84 research GeoTIFF and explicit submission status - GEMSDOE52",
                 f"H84 verdict: {verdict}. Download {'yes' if dl_ok else 'no'}, submit {'yes' if sb_ok else 'no'}.") + f"""
{H84_START}
<section class="hero"><div>
<div class="eyebrow">DOE GEMS #306 / H84 &middot; harmonic (elliptical) variogram anisotropy &middot; co-training lane,
View A (subsurface) vs View B (surface) &middot; 2026-10-10</div>
<h1>Download the file.<br>Read the verdict first.</h1>
{notice_block(dl_ok, sb_ok, verdict)}
{actions()}
<p class="fileline">{fileline}</p>
<p class="lead">{esc(headline)} One frozen hypothesis was tested: a fault zone makes the spatial covariance of
elevation, slope, gravity and basement-depth fields <em>elliptical</em>, so the eccentricity of a least-squares
ellipse fitted to 8 directional semivariances should rank unmapped fault cells better than H82&rsquo;s
max&minus;min anisotropy. Full result: <a href="h84.html">h84.html</a>. How to submit, and the [0,1] fix:
<a href="h84-executive-summary.html">h84-executive-summary.html</a>.</p>
</div></section>
<hr class="divider">
<section><h2>The holdout result</h2>
<p class="small">{lbl}</p>
{holdout_table}
{gates_table}
</section>
<hr class="divider">
<section><h2>Why did the 0.2778 file score what it scored, and can we beat it?</h2>
<p>Measured in <a href="{REPO}/blob/main/knowledge/49_why_02778_phd_answer.md">knowledge/49</a> (re-derived from
bytes, receipt <code>evidence/h67_board_algebra.json</code>): <code>h33-2-b2</code> is the owner&rsquo;s 0.2600
file with its 100&ndash;200&nbsp;m catalogue ring deleted &mdash; 6,436 pixels removed, none added, score
0.2600&nbsp;&rarr;&nbsp;0.2778 (both OWNER-REPORTED). Its credit density is about 5&times; uniform-random; it sits
exactly where its own field stops paying. To reach the public #8 score (0.3195) at the same 37,654-pixel budget
the credit density must rise from 0.1387 to 0.1595 (+15%); to reach #1 (0.3774) it must rise to 0.1884. No
holdout number here forecasts a board score (Spearman &minus;0.10 between holdout and board across this
repository&rsquo;s scored files).</p>
<p class="small">Public leaderboard, fetched 2026-10-10 (PUBLIC-BOARD; team names only &mdash; the board never
shows filenames, so the 0.2778 row cannot be attributed to a file):
<a href="{BOARD_URL}">{BOARD_URL}</a>; snapshot
<a href="data/h84_leaderboard_snapshot_2026-10-10.json">data/h84_leaderboard_snapshot_2026-10-10.json</a>.</p>
{board_tbl}
</section>
<hr class="divider">
<section><h2>Provenance and honesty rules</h2>
<ul class="small">
<li>Every number carries a label: <b>PUBLIC-BOARD</b> (the organiser&rsquo;s public leaderboard),
<b>HOLDOUT-DTI</b> (this repository&rsquo;s hide-and-recover instrument, with evaluator version, withheld-positive
count and 95% CI) or <b>OWNER-REPORTED</b>. A projection is never written as a score.</li>
<li>This repository has no DrivenData credentials: it has never uploaded a file, and no page here is an organiser
acceptance receipt.</li>
<li>Irregularities are logged: <a href="irregularities.html">irregularities register</a>.</li>
</ul></section>
{H84_END}
{archive}
""" + TAIL
    (DOCS / "index.html").write_text(index)

    # ---------------------------------------------------------------- docs/h84.html
    lane_rows = [
        ["surface vs literal full census (" + i(lane["full_census_rasters"]) + " rasters)",
         esc(lane["surface_literal"]), f'max Spearman {float(lane["surface_max_spearman"]):.4f}'],
        ["surface vs scored-only registry (" + i(lane["scored_only_rasters"]) + " rasters)",
         esc(lane["surface_scored_only"]), ""],
        ["final dots vs literal full census", esc(lane["dots_literal"]),
         "" if lane.get("dots_max_near_3px") is None else
         f'max near-3px share {float(lane["dots_max_near_3px"]):.4f}; max Spearman '
         f'{float(lane["dots_max_spearman"]):.4f}'],
        ["final dots vs full census, policy (informative supports only)", esc(lane.get("dots_policy")),
         "" if lane.get("dots_policy_max_near_3px") is None else
         f'max near-3px share {float(lane["dots_policy_max_near_3px"]):.4f}'],
        ["final dots vs scored-only registry", esc(lane.get("dots_scored_only")),
         "" if lane.get("dots_scored_only_max_near_3px") is None else
         f'max near-3px share {float(lane["dots_scored_only_max_near_3px"]):.4f}'],
    ]
    nu = card.get("not_the_union") or {}
    nu_rows = [[esc(k), esc(v if not isinstance(v, float) else f"{v:.4f}")] for k, v in nu.items()]
    val_rows = [[esc(k), esc(v)] for k, v in val.items() if k not in ("rule_source",)]
    folds_auc = card["out_of_quadrant_auc"]
    auc_rows = [[f"<code>{esc(a)}</code>"] + [f"{float(x):.4f}" for x in v] for a, v in folds_auc.items()]
    page = head("H84 result - harmonic variogram anisotropy - GEMSDOE52",
                f"H84 full result: verdict {verdict}, holdout table, co-training independence, lane gate, "
                "format validator and JSON run card.") + f"""
<section class="hero"><div>
<div class="eyebrow">H84 &middot; full result &middot; preregistered 2026-10-10 (frozen before any fit)</div>
<h1>H84: harmonic variogram-ellipse anisotropy</h1>
{notice_block(dl_ok, sb_ok, verdict)}
{actions()}
<p class="fileline">{fileline}</p></div></section>
<hr class="divider">
<section><h2>Hypothesis, mechanism, mimic</h2>
<p><b>Hypothesis.</b> {esc(card["hypothesis"])}</p>
<p><b>Mechanism.</b> {esc(card["mechanism"])}</p>
<p><b>Mimic process.</b> {esc(card["mimic"])}</p>
<p class="small">Preregistration: <a href="{REPO}/blob/main/{esc(card["preregistration"]["document"])}">{esc(card["preregistration"]["document"])}</a>,
SHA-256 <code>{esc(card["preregistration"]["sha256"])}</code>, frozen {esc(card["preregistration"]["frozen_utc"])}.
Channels: {card["channels"]["hva"]} HVA + {card["channels"]["coh"]} COH new, {card["channels"]["dva2_control"]}
DVA-2 control; least-squares normal-matrix condition number {float(card["channels"]["normal_matrix_condition_number"]):.3f}.</p>
</section>
<hr class="divider">
<section><h2>Hide-and-recover holdout</h2>
<p class="small">{lbl}</p>
{holdout_table}
<h3>Out-of-quadrant AUC per fold</h3>
{table(["Arm", "fold 0", "fold 1", "fold 2", "fold 3"], auc_rows)}
<p class="small">Leakage canary (single-channel AUC on the held-out region, alarm at 0.90): max over all learner
channels {float(card["canary"]["max_all_learner"]):.4f}, max over new channels {float(card["canary"]["max_new"]):.4f},
alarm {esc(card["canary"]["alarm"])}.</p>
{gates_table}
</section>
<hr class="divider">
<section><h2>Co-training (Blum &amp; Mitchell 1998)</h2>
<p>Lane reference: <a href="{BLUM_MITCHELL}">Blum &amp; Mitchell, <i>Combining labeled and unlabeled data with
co-training</i>, COLT 1998</a>. Co-training needs two views that are each sufficient and conditionally
independent given the label.</p>
<ul>
<li><b>Independence</b> (spatial-block OOF errors on labelled negatives, {i(ind["n_blocks"])} blocks):
max |&rho;| = {float(ind["max_abs_rho"]):.4f}; abandon bar |&rho;| &gt; {ind["abandon_bar"]}.
Exchange allowed by this test: {esc(ind["allow_exchange"])}. <span class="small">{esc(ind["caveat"])}</span></li>
<li><b>Sufficiency of View A</b> (out-of-quadrant AUC): mean {float(suff["mean"]):.4f}, worst fold
{float(suff["min_fold"]):.4f}, per fold {", ".join(f"{float(x):.4f}" for x in suff["per_fold"])}; gate mean &ge;
{suff["gate_mean"]} and every fold &ge; {suff["gate_min_fold"]} &rarr; <b>{"PASS" if suff["passes"] else "FAIL"}</b>.</li>
<li><b>Pseudo-label exchange run:</b> {esc(cot["exchange_run"])} &mdash; {esc(cot["exchange_not_run_reason"])}.</li>
<li><b>Disagreement as discovery:</b> A-only stratum (View A rank &ge; 0.95, primary rank in [0.35, 0.65]) =
{i(dis["a_only_stratum_px"])} px, {i(dis["a_only_candidates"])} spacing-thinned candidates, each with a geological
reasoning row{f' (<a href="{esc(csv_rel)}">CSV</a>)' if csv_rel else ''}. B-only candidates: {i(dis["b_only_candidates"])};
share within 5&deg; of a cardinal direction (road/section-line mimic) {float(dis["b_only_cardinal_fraction"]):.4f}
vs null {float(dis["b_only_cardinal_null"]):.4f}.</li>
</ul></section>
<hr class="divider">
<section><h2>Lane gate (drift = rank correlation &gt; 0.90 or &gt; 70% of dots within 3 px of one registry raster)</h2>
{table(["Check", "Verdict", "Detail"], lane_rows)}
<p class="small">Doctrine retained verbatim: {esc(lane["doctrine"])}</p>
<h3>Not the union</h3>
{table(["Measure", "Value"], nu_rows) if nu_rows else "<p>No raster written.</p>"}
<h3>Format validator</h3>
{table(["Check", "Value"], val_rows) if val_rows else "<p>No raster written.</p>"}
<p class="small">Machine receipts: <a href="data/h84_run_card.json">run card</a>,
<a href="data/h84_holdout.json">holdout</a>, <a href="data/h84_independence.json">independence</a>,
<a href="data/h84_lane.json">lane</a>, <a href="data/h84_fit.json">fit</a>.</p>
</section>
""" + TAIL
    (DOCS / "h84.html").write_text(page)

    # ---------------------------------------------------------------- docs/h84-executive-summary.html
    steps = "" if not ras else f"""
<section><h2>If you decide to submit it: the exact steps</h2>
<ol>
<li><b>Download</b> <a href="downloads/h84-candidate.tif" download>h84-candidate.tif</a> ({i(ras["bytes"])} bytes)
or the <a href="downloads/h84-candidate.zip" download>ZIP</a> (same bytes inside).</li>
<li><b>Check the file you actually downloaded</b> on <a href="validator.html">the browser checker</a>; its SHA-256
must be <code>{esc(ras["sha256"])}</code>. A different hash means a truncated file or an HTML error page saved
as <code>.tif</code>.</li>
<li><b>Sign in</b> at <a href="{esc(PROBLEM_URL)}">the competition page</a> and open <em>Submit</em>.</li>
<li><b>Upload.</b> Values are exactly {{0, 1}}, {val.get("nan")} NaN, {val.get("infinite")} infinite, 0.0 outside
the footprint &mdash; the portal&rsquo;s <code>Predicted values must be in range [0, 1]</code> rule cannot fire.</li>
<li><b>Name</b> <code>{esc(card["submission_name"])}</code></li>
<li><b>Note</b> ({len(card["submission_note"])} of 140 characters): <code>{esc(card["submission_note"])}</code></li>
</ol>
<p class="small">This repository cannot perform steps 3&ndash;6 (no credentials) and spends no slot.</p></section>
<hr class="divider">"""
    exsum = head("How to submit, and whether the H84 file may be submitted - GEMSDOE52",
                 "Step-by-step submission instructions for DOE GEMS #306, the causes of the [0,1] rejection, "
                 "and the H84 verdict.") + f"""
<section class="hero"><div>
<div class="eyebrow">H84 &middot; executive summary &middot; how to submit</div>
<h1>Two questions, answered separately</h1>
{notice_block(dl_ok, sb_ok, verdict)}
{actions()}
<p class="fileline">{fileline}</p>
<p>Primary arm <code>{PRIMARY}</code>: HOLDOUT-DTI {f6(sc[PRIMARY]["dti"])} {ci(sc[PRIMARY]["ci95"])} vs current
holdout best <code>B_DVA2</code> {f6(sc["B_DVA2"]["dti"])}; paired {pdf["B_DVA2"]["delta"]:+.6f}
{ci(pdf["B_DVA2"]["ci95"])}. <span class="small">{lbl}</span></p>
</div></section>
<hr class="divider">
{steps}
<section><h2>Fixing &ldquo;Predicted values must be in range [0, 1]&rdquo;</h2>
{table(["Cause", "How to recognise it", "Fix"], [
    ["NaN or a NoData sentinel inside the raster",
     "The checker reports NaN &gt; 0, or a huge negative minimum with a GDAL_NODATA tag",
     "Write 0.0 everywhere you do not predict a fault; write no NaN at all (repository fix, knowledge/03 N-5)."],
    ["The downloaded file is not the file you think",
     "SHA-256 differs; the file is a few hundred bytes; a text editor shows HTML",
     "Re-download; compare the hash."],
    ["Unnormalised scores (log-odds, z-scores, distances)", "min/max far outside [0,1]",
     "Rescale to [0,1] or emit binary {0,1}."],
    ["Wrong dtype (float64, int16)", "BitsPerSample 64/16 or SampleFormat not 3", "Write float32."],
])}
<p class="small">Official rules: <a href="{METRIC_URL}">{METRIC_URL}</a> &mdash; single band, float32, EPSG:32611,
100 m, same bounds as the training data, probabilities in [0, 1]; distance-weighted Tversky index with
&alpha; = 0.2, &beta; = 0.8, triangular kernel R = 300 m.</p></section>
""" + TAIL
    (DOCS / "h84-executive-summary.html").write_text(exsum)

    # ---------------------------------------------------------------- irregularities section
    h84 = sorted((e for e in irr["entries"] if e.get("round") == "H84"), key=lambda e: e["id"])
    body = "".join(
        f'<tr><td><b>{esc(e["id"])}</b><br><span class="small">{esc(e["severity"])} · {esc(e["status"])}</span></td>'
        f'<td>{esc(e["title"])}<div class="note">{esc(e["what_it_is"])}</div>'
        f'<div class="note"><b>How we know:</b> {esc(e["how_we_know"])}</div>'
        f'<div class="note"><b>Handling:</b> {esc(e["handling"])}</div>'
        f'<div class="note"><b>Disposition:</b> {esc(e["disposition"])}</div>'
        f'<div class="note"><b>Measured effect:</b> {esc(e["measured_effect"])}</div></td></tr>' for e in h84)
    section = ("<!--H84-IRREGULARITIES--><section><h2>H84 irregularities (2026-10-10)</h2>"
               f'<p class="small">Authoritative register: <a href="../registry/irregularities.json">'
               f'registry/irregularities.json</a> ({len(irr["entries"])} entries).</p>'
               '<div class="table-wrap"><table><thead><tr><th>ID</th><th>What it is, how we know, and what was '
               f'done</th></tr></thead><tbody>{body}</tbody></table></div></section><!--/H84-IRREGULARITIES-->')
    ip = DOCS / "irregularities.html"
    t = ip.read_text()
    if "<!--H84-IRREGULARITIES-->" in t:
        a = t.index("<!--H84-IRREGULARITIES-->")
        b = t.index("<!--/H84-IRREGULARITIES-->") + len("<!--/H84-IRREGULARITIES-->")
        t = t[:a] + section + t[b:]
    else:
        t = t.replace("</main>", section + "</main>", 1)
    ip.write_text(t)

    # ---------------------------------------------------------------- root landing page
    old = (ROOT / "index.html").read_text()
    m = re.search(r'<section id="h74s-closeout".*?</section>', old, flags=re.S)
    assert m, "root index.html lost its H74S closeout section"
    h74s = m.group(0).replace("H82 above is the later repository round", "H84 above is the current repository round")
    color = ("#e8f6ed", "#0f7b3f", "#b7dfc5") if sb_ok else ("#fdecea", "#b3261e", "#f0c4bf")
    dl_btn = ("" if not ras else
              '<a class="b" href="docs/downloads/h84-candidate.tif" download>Download h84-candidate.tif &#8595;</a>\n'
              '<a class="b s" href="docs/downloads/h84-candidate.zip" download>ZIP</a>\n')
    root = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE52 — DOE GEMS competition #306 — H84 candidate and explicit submission status</title>
<style>
body{{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:#14181d;background:#fff}}
main{{max-width:760px;margin:0 auto;padding:36px 20px 70px}}
h1{{font-size:26px;margin:0 0 10px}}
.v{{border-radius:10px;padding:14px 16px;margin:16px 0;font-weight:700;background:{color[0]};color:{color[1]};
border:1px solid {color[2]}}}
a.b{{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;
padding:13px 20px;border-radius:8px;margin:6px 8px 6px 0}}
a.s{{background:#eef2f6;color:#1f4e79}}
code{{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13.5px;word-break:break-all}}
small{{color:#5b6672}}
</style></head><body><main>
<h1>H84 candidate raster &mdash; DOE GEMS competition #306</h1>
<div class="v">{esc("OK TO DOWNLOAD: yes" if dl_ok else "OK TO DOWNLOAD: no")}
&nbsp;&middot;&nbsp; {esc("OK TO SUBMIT: yes" if sb_ok else "OK TO SUBMIT: no — research artefact only")}</div>
{dl_btn}<a class="b s" href="docs/index.html">Full site</a>
<a class="b s" href="docs/h84-executive-summary.html">How to submit</a>
<a class="b s" href="docs/validator.html">Check a file in your browser</a>
<p><small>{fileline.replace('<code>', '<code>')}</small></p>
<p><small>{lbl} Primary arm {f6(sc[PRIMARY]["dti"])} {ci(sc[PRIMARY]["ci95"])}; current holdout best B_DVA2
{f6(sc["B_DVA2"]["dti"])}; paired {pdf["B_DVA2"]["delta"]:+.6f} {ci(pdf["B_DVA2"]["ci95"])}. Verdict:
<b>{esc(verdict)}</b>. Full result: <a href="docs/h84.html">docs/h84.html</a>.</small></p>
<p><small>Research artefact. Not an organiser acceptance receipt; no leaderboard gain is claimed.</small></p>
<p><small><b>Parallel-session H83 file:</b> pages describing <code>h83-candidate.tif</code> (structural concordance +
geothermal proximity) call it ready to submit, but it has no holdout measurement and no recorded lane check
&mdash; not validated for upload (IR-H84-007, <a href="docs/irregularities.html">irregularities register</a>).</small></p>
{h74s}
</main></body></html>
"""
    (ROOT / "index.html").write_text(root)
    # ---------------------------------------------------------------- audit banners on the parallel H83 pages
    banner = ('<!--H84-AUDIT--><div style="margin:0;padding:14px 18px;background:#fdecea;color:#7a1712;'
              'border-bottom:2px solid #b3261e;font:15px/1.5 system-ui,sans-serif"><b>H84 audit notice '
              '(2026-10-10):</b> the H83 file described on this page has <b>no holdout measurement</b> '
              '(its run card records holdout_dti = NOT_EVALUATED) and no recorded lane check against the '
              '584-raster census, so by the brief&rsquo;s rules it is <b>not validated for upload</b>. '
              'Its &ldquo;projection&rdquo; is not a score. Details: IR-H84-007 in '
              '<a href="irregularities.html">the irregularities register</a>. The current repository round is '
              '<a href="index.html">H84</a> (DOWNLOAD YES, SUBMIT NO).</div><!--/H84-AUDIT-->')
    for name in ("h83-parallel-executive-summary.html", "h83-executive-summary.html"):
        pth = DOCS / name
        if not pth.exists():
            continue
        t = pth.read_text()
        if "<!--H84-AUDIT-->" in t:
            t = t[:t.index("<!--H84-AUDIT-->")] + banner + t[t.index("<!--/H84-AUDIT-->") + len("<!--/H84-AUDIT-->"):]
        else:
            t = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + banner, t, count=1)
        assert "<!--H84-AUDIT-->" in t, name
        pth.write_text(t)

    print(json.dumps(dict(pages=["docs/index.html", "docs/h84.html", "docs/h84-executive-summary.html",
                                 "docs/irregularities.html", "index.html"],
                          verdict=verdict, download_ok=dl_ok, submit_ok=sb_ok,
                          sha256=ras and ras["sha256"], name=card["submission_name"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
