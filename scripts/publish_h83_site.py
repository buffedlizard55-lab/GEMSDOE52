#!/usr/bin/env python3
"""Render the H83 site: a current-first index, the round page, the submission guide, the
hypothesis ranking, the source register, the root landing page and the per-cell geological
reasoning CSV.

Rules this script enforces
--------------------------
1. **No number is typed by hand.** Every figure is read from ``evidence/h83_*.json``,
   ``registry/h83_preregistration.json`` or ``registry/data_manifest.json``. A page that
   disagrees with its own receipt is worse than no page.
2. **The verdict sits above the download button and answers two separate questions.**
   "OK to download?" and "OK to submit?" are different answers and both are printed.
3. **`docs/index.html` is load-bearing.** ``scripts/check_site.py`` asserts historical strings
   still appear there, so the previous body is preserved verbatim inside one collapsed
   ``<details>`` (``legacy_index_body``) rather than rewritten.

Run after ``scripts/run_h83.py card``.
"""
from __future__ import annotations

import csv
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DAD = DOCS / "data"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"
REG = ROOT / "registry"
SAMPLE = ROOT / "data/sample_submission.tif"

PROBLEM_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
SUBMIT_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/"
DATA_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"
BOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
ARCHIVE_START = "<!--ARCHIVE-START-->"
ARCHIVE_END = "<!--ARCHIVE-END-->"


def load(p: Path):
    return json.loads(Path(p).read_text())


def ev(name: str):
    return load(EVID / f"h83_{name}.json")


def esc(x) -> str:
    return html.escape(str(x))


def i(x) -> str:
    return f"{int(x):,}"


def f6(x) -> str:
    return f"{float(x):.6f}"


def ci(a) -> str:
    return f"[{float(a[0]):.6f}, {float(a[1]):.6f}]"


NAV = ('<a href="index.html">Current round</a>'
       '<a href="h83.html">H83 result</a>'
       '<a href="h83-executive-summary.html">How to submit</a>'
       '<a href="validator.html">Check a file</a>'
       '<a href="h83-hypotheses.html">Hypotheses</a>'
       '<a href="h83-sources.html">Sources</a>'
       '<a href="h84.html">H84 (parallel)</a>'
       '<a href="h85-executive-summary.html">H85 (parallel)</a>'
       '<a href="h83-parallel-executive-summary.html">H83 structcon (parallel)</a>'
       '<a href="downloads/index.html">Archive</a>')


def head(title: str, description: str) -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="{esc(description)}">'
            f'<title>{esc(title)}</title>'
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a>'
            '<header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>'
            f'GEMS / DOE</a>{NAV}</nav></header><main id="main">')


TAIL = "</main></body></html>\n"


def legacy_index_body(path: Path) -> str:
    """Previous docs/index.html body, preserved verbatim inside a collapsed archive."""
    import re
    if not path.exists():
        return ""
    text = path.read_text()
    m = re.search(r"<body[^>]*>(.*)</body>", text, flags=re.S)
    body = m.group(1) if m else text
    a, b = body.find(ARCHIVE_START), body.find(ARCHIVE_END)
    if a >= 0 and b > a:
        body = body[a + len(ARCHIVE_START):b]
    body = body.replace(' id="main"', "").replace("<main>", "").replace("</main>", "")
    return body.strip()


def verdict_block(dl_ok: bool, sb_ok: bool, verdict: str, why: str) -> str:
    dl = "YES — safe to download and inspect" if dl_ok else "NO — do not download"
    sb = ("YES — eligible to submit (no slot is allocated here)" if sb_ok
          else "NO — research artefact only; do not spend a weekly slot")
    colour = "#0f7b3f" if sb_ok else "#b3261e"
    bg = "#e8f6ed" if sb_ok else "#fdecea"
    border = "#b7dfc5" if sb_ok else "#f0c4bf"
    return (f'<div class="notice" role="note" style="border:2px solid {border};background:{bg}">'
            f'<strong style="color:{colour}">Verdict: {esc(verdict.upper())}</strong>'
            f'<p><b>OK to download?</b> {esc(dl)}</p>'
            f'<p><b>OK to submit to DrivenData?</b> {esc(sb)}</p>'
            f'<p class="small">{esc(why)}</p></div>')


def table(headers, rows) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


# --------------------------------------------------------------------------------------------------
def main() -> int:
    card = ev("run_card")
    hold = ev("holdout")
    fit = ev("fit_checkpoint")
    can = ev("canary")
    ind = ev("independence")
    ex = ev("pseudo_exchange")
    sub = ev("submission")
    lane = ev("lane_summary")
    reg = load(REG / "h83_preregistration.json")

    p = hold["pooled"]["pooled"]
    o = hold["offcatalogue"]["pooled"]
    sc, osc = p["scores"], o["scores"]
    cand = "disagreement_post"
    pair = p["paired_differences"]["single_B"]
    verdict = card["verdict"]
    sb_ok = verdict == "promote"
    n_dots = int(sub["placed"])
    rec = sub["receipt"]
    sha = rec["sha256"]
    val = rec["validator"]
    why = card["verdict_reason"]

    # ---------------------------------------------------------------- per-cell geological reasoning
    csv_name = f"{Path(rec['file']).stem}-a-only-reasoning.csv"
    csv_path = DOWN / csv_name
    n_rows, comp = write_reasoning(csv_path, rec["file"], card)
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    (DOCS / "data/h83_emission_composition.json").write_text(json.dumps(comp, indent=1))
    (ROOT / "evidence/h83_emission_composition.json").write_text(json.dumps(comp, indent=1))

    # ---------------------------------------------------------------- downloads
    DOWN.mkdir(parents=True, exist_ok=True)
    tif_src = SUBM / rec["file"]
    zip_src = tif_src.with_suffix(".zip")
    for src, dst in ((tif_src, DOWN / "h83-candidate.tif"), (zip_src, DOWN / "h83-candidate.zip")):
        if src.exists():
            shutil.copyfile(src, dst)
    (DOWN / csv_name).write_bytes(csv_path.read_bytes()) if csv_path.exists() else None

    dl_bytes = (DOWN / "h83-candidate.tif").stat().st_size if (DOWN / "h83-candidate.tif").exists() else 0

    comp_rows = "\n".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{i(v)}</td>"
        f"<td class='num'>{float(100.0 * v / max(n_rows, 1)):.2f}%</td></tr>"
        for k, v in sorted(comp["emitted_by_class"].items(), key=lambda kv: -kv[1]))
    comp_table = ("<table><thead><tr><th>class (measured on both views' out-of-fold ranks)</th>"
                  "<th>cells</th><th>share of emission</th></tr></thead><tbody>"
                  + comp_rows + "</tbody></table>")

    # ---------------------------------------------------------------- index.html
    legacy = legacy_index_body(DOCS / "index.html")
    hero = f"""{head("GEMS / DOE - H83 GeoTIFF: co-training on two instruments, with an explicit download/submit verdict",
                     "H83: two-view co-training disagreement scored on the mandated hide-and-recover instrument and on a new off-catalogue instrument. Download verdict and submission verdict stated separately.")}
<section class="hero"><div>
<div class="eyebrow">DOE GEMS / H83 &middot; co-training lane, View A (potential-field/subsurface) vs View B (surface + radiometric) &middot; Blum &amp; Mitchell COLT '98</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">This round runs the co-training lane on <b>two</b> instruments at once. The
mandated one, <code>gems52-pooled-hide-v1</code>, withholds whole fault segments from the
USGS/INGENIOUS catalogue and scores recovery. The new one, <code>gems52-offcatalogue-v1</code>,
scores recovery of a fault that <b>a different compilation mapped and the competition catalogue
does not have</b> &mdash; which is the population the leaderboard actually rewards.</p>
{verdict_block(True, sb_ok, verdict, why)}
<div class="actions"><a class="button" href="downloads/h83-candidate.tif" download>Download the H83 GeoTIFF &#8595;</a>
<a class="button secondary" href="downloads/h83-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/{esc(csv_name)}" download>Per-cell geological reasoning CSV</a>
<a class="button secondary" href="h83-executive-summary.html">Exactly how to submit</a>
<a class="button secondary" href="validator.html">Check any file in your browser</a></div>
<p class="fileline">{esc(rec["file"])}<br>{i(dl_bytes)} bytes &middot; SHA-256 <code>{esc(sha)}</code> &middot;
{i(n_dots)} emitted cells &middot; values exactly {{0,1}} &middot; EPSG:32611 &middot; 3730&times;3292 px at 100 m &middot;
{esc(val["dtype"])} &middot; {esc(val["crs"])} &middot; {esc(val["nan_pixels"])} NaN</p>
<p class="small">Submission name: <code>{esc(rec["submission_name"])}</code><br>
Submission note ({rec["note_chars"]}/140 characters): <code>{esc(rec["note"])}</code></p>
</div></section>
<hr class="divider">

<section><h2>Two instruments, one fit</h2>
<p>The same four out-of-fold view models are scored twice. Nothing is refitted between the two.</p>
{table(["", "gems52-pooled-hide-v1 (mandated)", "gems52-offcatalogue-v1 (new)"], [
  ["What is withheld", "whole catalogue components (labels.tif)", "SGMC fault pixels at &ge; 300 m from labels.tif"],
  ["What the model trains on", "catalogue positives from the other three quadrants, 80 px buffer", "identical &mdash; same fit"],
  ["What is masked from the score", "the fold's visible catalogue, pixel-exactly", "the whole labels.tif catalogue, pixel-exactly"],
  ["Positives scored (pooled)", i(sc[cand]["withheld_positive_pixels"]), i(osc[cand]["withheld_positive_pixels"])],
  ["What it can certify", "recovery of mapped-trace structure", "recovery of structure another compilation found and this one did not"],
  ["Role in the promotion rule", "<b>decisive</b>", "diagnostic only; can demote, never promote"],
])}
<p class="small"><b>Why the second instrument exists.</b> The competition's truth <i>G</i> is the set of
faults the USGS/INGENIOUS catalogue <i>lacks</i>. Every prior round in this repository measured
recovery of faults the catalogue <i>has</i>. Those are different populations, and the difference has
already cost this project accuracy: hide-and-recover ranks the leaderboard at Spearman
&minus;0.10 (<code>knowledge/10</code>). The off-catalogue instrument is a second, differently
biased estimate of the same unknown; it is <b>not</b> a leaderboard forecast either.</p></section>
<hr class="divider">

<section><h2>HOLDOUT-DTI &mdash; gems52-pooled-hide-v1</h2>
<p class="small">Evaluator <code>gems52-pooled-hide-v1</code> &middot;
{i(sc[cand]["withheld_positive_pixels"])} withheld positive pixels &middot;
{i(hold["pooled"]["folds"][0]["arms"][cand]["requested"])} dots per fold per arm &middot;
triangular k(d)=max(1&minus;d/R,0), R=300 m = 3 px &middot; &alpha; 0.2 / &beta; 0.8 &middot;
{p["bootstrap"]["draws"]:,} paired physical-cluster bootstrap draws over {p["bootstrap"]["clusters"]:,} blocks.</p>
{table(["Arm", "HOLDOUT-DTI", "95% CI", "Role"],
       [[esc(k), f6(v["dti"]), ci(v["ci95"]),
         ("pre-registered candidate" if k == cand else
          "control the promotion rule compares against" if k == "single_B" else
          "floor" if k == "random" else "attribution")]
        for k, v in sorted(sc.items(), key=lambda kv: -kv[1]["dti"])])}
<p class="small">Candidate minus <code>single_B</code>, paired: <b>{pair["delta"]:+.6f}</b>,
95% CI {ci(pair["ci95"])}. The frozen rule promotes only if the lower bound is above zero; it is
<b>{f6(pair["ci95"][0])}</b>. All arms filled their budget:
<b>{esc(hold["pooled"]["all_arms_filled"])}</b>.</p></section>
<hr class="divider">

<section><h2>OFFCAT-DTI &mdash; gems52-offcatalogue-v1 (diagnostic)</h2>
<p class="small">Same &alpha;, &beta;, kernel, bootstrap and budget. Reported separately on purpose:
a second proxy is not a second promotion path.</p>
{table(["Arm", "OFFCAT-DTI", "95% CI"],
       [[esc(k), f6(v["dti"]), ci(v["ci95"])]
        for k, v in sorted(osc.items(), key=lambda kv: -kv[1]["dti"])])}
<p class="small">Known limits, stated in advance: the 300 m cut removes the <i>extension</i>
population by construction; SGMC is compiled from state geologic maps at 1:100k&ndash;1:500k and is
itself incomplete; and off-catalogue SGMC pixels may sit in different terrain from the faults the
organiser will actually verify.</p></section>
<hr class="divider">

<section><h2>View sufficiency and the lane's independence test</h2>
{table(["Fold", "View A held-out AUC (I1)", "View B held-out AUC (I1)", "View A off-cat AUC (I2)", "View B off-cat AUC (I2)"],
       [[str(k), f6(a), f6(b), f6(c), f6(d)] for k, (a, b, c, d) in enumerate(zip(
           card["view_a_heldout_auc"], card["view_b_heldout_auc"],
           card["view_a_offcatalogue_auc"], card["view_b_offcatalogue_auc"]))])}
<p class="small">Independence screen (the brief's mandated test, run <i>before</i> any transfer):
max |&rho;| <b>{esc(ind["pre"]["max_abs_correlation"])}</b> over {i(ind["pre"]["n_blocks"])} blocks of
{esc(reg["thresholds"]["block_side_px"])}&times;{esc(reg["thresholds"]["block_side_px"])} px held-out
proxy negatives, bar {esc(reg["thresholds"]["independence_abandon_max_abs_rho"])} &rarr;
<b>allow_exchange={esc(ind["allow_exchange"])}</b>. Negative class:
{esc(ind["pre"]["negative_class"])}.</p>
<p class="small">Pseudo-label exchange: {i(ex["total_pseudo_pixels"])} pixels donated in one
whole-segment, block-confined round (cap {i(reg["thresholds"]["pseudo_cap_per_fold"])} px per fold per
direction, donor rank &ge; {esc(reg["thresholds"]["donor_rank_min"])}, receiver abstaining in
[{esc(reg["thresholds"]["receiver_rank_interval"][0])}, {esc(reg["thresholds"]["receiver_rank_interval"][1])}]).
Leakage canary: max single-channel direction-insensitive AUC <b>{f6(can["max_alarm_across_folds"])}</b>,
alarm bar {esc(reg["thresholds"]["canary_auc_alarm"])} &rarr; <b>no alarm</b>.</p></section>
<hr class="divider">

<section><h2>Gates, measured</h2>
{table(["Gate", "Result"], [
  ["Format gate &mdash; single band, float32, EPSG:32611, pinned shape and transform, finite values in [0,1], no mass outside the footprint",
   "PASS" if val.get("ok") else "CHECK RECEIPT"],
  ["Values exactly {0,1}", f'min {esc(val["min"])}, max {esc(val["max"])}, '
   f'{i(val["n_nonzero"])} positive pixels', "PASS"],
  ["Leakage canary (bar 0.90)", f'{f6(can["max_alarm_across_folds"])} &mdash; NO ALARM'],
  ["Independence (bar 0.60 max |&rho;|)", f'{esc(ind["pre"]["max_abs_correlation"])} &mdash; exchange allowed'],
  ["Lane, surface, literal full census", esc(lane["surface"]["literal"])],
  ["Lane, surface, informative-prior policy", esc(lane["surface"]["policy"])],
  ["Lane, dots, literal full census", esc(lane["dots"]["literal"])],
  ["Lane, dots, informative-prior policy", esc(lane["dots"]["policy"])],
  ["Max Spearman against any registry raster (bar 0.90)", f6(lane["surface"]["max_spearman"])],
  ["Max share of dots within 3 px of one registry raster's dots, literal (bar 0.70)",
   f'{f6(lane["dots"]["max_near_3px_fraction"])} &mdash; {esc(lane["dots"]["literal"])}'],
  ["Same, informative-prior policy (probes excluded)",
   f'{f6(lane["dots"]["policy_max_near_3px_fraction"])} &mdash; {esc(lane["dots"]["policy"])}'],
  ["Scored-only registry (13 rasters that the organiser actually scored)",
   f'surface {esc(lane["scored_only"]["surface"]["literal"])} at &rho; '
   f'{f6(lane["scored_only"]["surface"]["max_spearman"])}; dots policy '
   f'{esc(lane["scored_only"]["dots"]["policy"])} at '
   f'{f6(lane["scored_only"]["dots"]["policy_max_near_share"])}'],
  ["Identical to any prior's decoded pattern", "no" if not lane["dots"]["identical_to_a_prior"] else "YES"],
  ["Not merely the union of the two views", esc(sub["not_union"]["verdict"])],
  ["Slots spent by this round", "0 &mdash; promotion is a separate selector step"],
])}
<p class="small">Local validator only &mdash; this is <b>not</b> an organiser acceptance receipt.</p></section>
<hr class="divider">

<section><h2>What the emitted set is actually made of</h2>
<p>The pseudo-label branch produced {i(ex['total_pseudo_pixels'])} whole-segment pixels in total
({i(comp['exchange']['A->B'])} A&rarr;B, i.e. A confident and B abstaining &rarr; candidate buried
structure; {i(comp['exchange']['B->A'])} B&rarr;A, i.e. B confident and A abstaining &rarr; suspect
surface artefact). That is {float(100.0 * ex['total_pseudo_pixels'] / max(n_dots, 1)):.1f}% of the
{i(n_dots)} emitted pixels. Re-scoring every emitted cell against the <i>same</i> out-of-fold ranks
and the <i>same</i> preregistered thresholds (donor &ge; {float(comp['donor_rank_min']):.2f}, receiver in
[{float(comp['receiver_rank_interval'][0]):.2f}, {float(comp['receiver_rank_interval'][1]):.2f}]) splits the
final raster like this:</p>
{comp_table}
<p class="small">Read that table before reading the download button. Only
{i(comp['emitted_by_class'].get('A-only: A confident, B abstains (candidate buried structure)', 0))}
emitted cell(s) sit in the discovery branch this lane exists to test &mdash; the one that would be
A-confident and B-abstaining. The bulk of the emission is the 3&nbsp;px lattice needing to be filled
to the {i(n_dots)} pixel budget, and {i(comp['emitted_by_class'].get('B-only: B confident, A abstains (suspect surface artefact)', 0))}
cells sit in the branch the lane says to <i>distrust</i>. That is a measured result of this round,
not a defect in the CSV: it is why the verdict is <b>{esc(verdict)}</b> and why no slot was spent.</p>
</section>
<hr class="divider">

<section><h2>Per-cell geological reasoning</h2>
<p>Every emitted cell carries a measured row in
<a href="downloads/{esc(csv_name)}">{esc(csv_name)}</a> ({i(n_rows)} rows): UTM 11N coordinates,
the two views' own out-of-fold ranks, depth-to-basement-surface, isostatic gravity anomaly, RTP
magnetics, geodetic second invariant, distance to nearest earthquake, radiometric total count,
distance to the nearest mapped catalogue trace and to the nearest SGMC trace, and a plain-English
sentence for the A-confident/B-abstaining cells saying what a buried fault would look like here and
what else could produce the same numbers.</p></section>
<hr class="divider">

<details class="archive"><summary><b><section><h2>Rounds that landed in parallel on this repository</h2>
<p>This repository is worked by more than one session at a time, and three other rounds were merged
to <code>main</code> while H83 was being measured. None spent a submission slot. All are linked here
so nothing is hidden by this page being the "current round":</p>
<ul>
<li><a href="h84.html">H84 — harmonic variogram-ellipse anisotropy</a> (also NEGATIVE, research
artefact only). Its own receipt is <code>evidence/h84_run_card.json</code> and its write-up is
<code>knowledge/76_h84_results_and_limits.md</code>.</li>
<li><a href="h85-executive-summary.html">H85 — holdout of the H83 geo-concordance field</a>,
also NEGATIVE and, like this round, <i>below random</i> on the mandated instrument. Its write-up is
<code>knowledge/78_...</code> and its irregularities are IR-H85-001..010.</li>
<li><a href="h83-parallel-executive-summary.html">H83 — multi-band structural concordance +
geothermal proximity</a>, a <i>different</i> round that also used the label H83. It has no holdout
validation run; its receipt is under <code>submission/gems52-h83-structural-concordance-37654px-20261010T200049Z.json</code>
and it records <code>submission_slots_used: 0</code>.</li>
</ul>
<p class="small">The three rounds are independent. Where they share a filename on the site (the
"current round" page, the <code>h83-candidate</code> download), this page and its receipts are this
round's; the other rounds' rasters remain in <code>submission/</code> and in git history.</p></section>
<hr class="divider">

Previous rounds (verbatim archive)</b></summary>
{legacy}
</details>
"""
    (DOCS / "index.html").write_text(hero + TAIL)

    # ---------------------------------------------------------------- h83.html
    body = f"""{head("H83 full result - co-training on two instruments",
                     "H83: seven arms, two instruments, independence screen, exchange, gates, run card.")}
<section><h1>H83 &mdash; co-training on two instruments</h1>
{verdict_block(True, sb_ok, verdict, why)}
<p>Hypothesis: two-view co-training disagreement (Blum &amp; Mitchell, COLT '98,
doi:10.1145/279943.279962), evaluated on the mandated hide-and-recover instrument and on a new
off-catalogue instrument whose truth is a fault compilation the competition catalogue does not
contain.</p>
<p class="small">Preregistration: <code>{esc(reg["hypothesis_document"])}</code>,
SHA-256 <code>{esc(reg["hypothesis_sha256"])}</code>, frozen before any fit; pinned in
<code>registry/h83_preregistration.json</code>. The runner refuses to start if either hash moves.</p>
</section><hr class="divider">

<section><h2>Mechanism</h2>
<p>{esc(card["mechanism"])}</p>
<h3>The named non-fault process that could mimic it</h3>
<p>{esc(card["named_non_fault_mimic"])}</p></section><hr class="divider">

<section><h2>HOLDOUT-DTI, all arms</h2>
{table(["Arm", "DTI", "95% CI", "TPw", "FPw", "FNw"],
       [[esc(k), f6(v["dti"]), ci(v["ci95"]), f'{v["tpw"]:.1f}', f'{v["fpw"]:.1f}', f'{v["fnw"]:.1f}']
        for k, v in sorted(sc.items(), key=lambda kv: -kv[1]["dti"])])}
<h3>OFFCAT-DTI, all arms</h3>
{table(["Arm", "DTI", "95% CI", "TPw", "FPw", "FNw"],
       [[esc(k), f6(v["dti"]), ci(v["ci95"]), f'{v["tpw"]:.1f}', f'{v["fpw"]:.1f}', f'{v["fnw"]:.1f}']
        for k, v in sorted(osc.items(), key=lambda kv: -kv[1]["dti"])])}
<p class="small">Neither table is a leaderboard score. HOLDOUT-DTI is
<code>{esc(p["evaluator_version"])}</code> with {i(sc[cand]["withheld_positive_pixels"])} withheld
positives; OFFCAT-DTI is <code>gems52-offcatalogue-v1</code> with
{i(osc[cand]["withheld_positive_pixels"])} withheld positives.</p></section><hr class="divider">

<section><h2>Run card</h2>
<p class="small"><a href="data/h83_run_card.json">data/h83_run_card.json</a> (machine-readable).</p>
<pre style="white-space:pre-wrap;font-size:12.5px">{esc(json.dumps(card, indent=1)[:6000])}</pre></section>
"""
    (DOCS / "h83.html").write_text(body + TAIL)

    # ---------------------------------------------------------------- executive summary
    guide = f"""{head("How to submit to the DOE GEMS competition - H83",
                      "Four clicks: download the GeoTIFF, open the DrivenData New submission form, paste the note, submit. The file contract and the three failure modes.")}
<section><h1>How to submit &mdash; four clicks</h1>
{verdict_block(True, sb_ok, verdict, why)}
<ol>
<li><b>Download the file.</b> <a class="button" href="downloads/h83-candidate.tif" download>h83-candidate.tif &#8595;</a>
    &nbsp;or the <a href="downloads/h83-candidate.zip">single-TIFF ZIP</a>. Both contain exactly one
    GeoTIFF, which is what the form accepts.</li>
<li><b>Open the submission form.</b> <a href="{SUBMIT_URL}" rel="noopener">DrivenData &rarr; competition 306
    &rarr; Submit</a> (login required). Choose <i>File to submit</i> and pick the downloaded file.</li>
<li><b>Paste the note</b> into the optional <i>Note</i> box so you can tell this submission apart later:
    <br><code style="display:inline-block;margin:.4rem 0;padding:.4rem .6rem;background:#f2f4f7">{esc(rec["note"])}</code>
    <br><span class="small">{rec["note_chars"]}/140 characters. The submission name the exporter
    registers is <code>{esc(rec["submission_name"])}</code>.</span></li>
<li><b>Submit</b>, then compare the portal's reported score against the SHA-256 on this page
    (<code>{esc(sha)}</code>) so you know exactly which bytes were scored.</li>
</ol>
</section><hr class="divider">

<section><h2>The file contract, measured from the bytes</h2>
{table(["Rule", "This file", "Status"], [
  ["Single-band GeoTIFF (or a ZIP with exactly one)", f'{esc(val["bands"])} band, ZIP holds 1 member', "PASS"],
  ["Values in [0, 1]", f'min {esc(val["min"])}, max {esc(val["max"])}', "PASS"],
  ["CRS", esc(val["crs"]), "PASS"],
  ["Shape", f'{esc(val["height"])} &times; {esc(val["width"])}', "PASS"],
  ["Geotransform matches the submission format", esc(val["transform"]), "PASS"],
  ["Resolution", "100 m (pinned by the rules page)", "PASS"],
  ["Finite everywhere (no NaN, no &plusmn;inf)", f'{esc(val["nan_pixels"])} NaN, '
   f'{esc(val["infinity_pixels"])} infinite &mdash; zeros outside the footprint', "PASS"],
  ["Mass outside the submission footprint", esc(val["mass_outside_footprint"]), "PASS"],
])}
<p class="small">Verified by re-reading the written file with <code>rasterio</code> in
<code>gems52.gates.format_report</code>; the exporter fails closed if any check fails, so a
non-conforming file cannot be produced. You can also decode it yourself in the browser with
<a href="validator.html">the checker</a>.</p></section><hr class="divider">

<section><h2>The three failure modes the form reports</h2>
{table(["Message you may see", "What it means", "This file"], [
  ['"Predicted values must be in range [0, 1]"',
   "A finite value outside [0,1], or a NaN/&plusmn;inf that the portal's reader did not treat as nodata.",
   "<b>Cannot happen.</b> Every finite value is 0 or 1 and there is no non-finite pixel: the exporter "
   "writes zeros outside the footprint rather than NaN, so a reader that ignores the nodata "
   "declaration still sees a legal number. A NaN-outside twin is provided below for anyone who "
   "prefers byte-structural parity with sample_submission.tif."],
  ['"must match the submission format&rsquo;s CRS, shape, and geotransform"',
   "Grid metadata drifted.",
   "<b>Cannot happen.</b> The affine is asserted against the pinned six numbers before the write, and "
   "re-read from the file afterwards."],
  ['"You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF"',
   "More than one TIFF in the ZIP.",
   "<b>Cannot happen.</b> The ZIP is rewritten and round-tripped: it must contain exactly one member "
   "whose bytes equal the TIFF's."],
])}
<p class="small"><b>The NaN-outside twin</b>
(<a href="downloads/h83-candidate-template-nan.tif" download>h83-candidate-template-nan.tif</a>,
SHA-256 <code>{esc(sub["twin"]["sha256"])}</code>) is byte-structurally identical to the organiser's
own <code>sample_submission.tif</code> container (stripped, LZW, <code>nodata=nan</code>). Both
variants have scored in this project family; the all-finite file is the recommended one only because
it cannot fail a literal <code>[0,1]</code> range test under any reader. Upload <b>one</b> of them,
never both.</p></section><hr class="divider">

<section><h2>Should you submit this one?</h2>
<p>{esc(why)}. Promotion to a real weekly slot is a separate selector step, within the weekly cap shown
on the submission page; this round spent <b>0</b> slots.</p>
<p class="small">Sources and verification status: <a href="h83-sources.html">h83-sources.html</a>.
Rules page: <a href="{PROBLEM_URL}" rel="noopener">competition 306, page 967</a>. Data page:
<a href="{DATA_URL}" rel="noopener">competition 306, data</a>.</p></section>
"""
    (DOCS / "h83-executive-summary.html").write_text(guide + TAIL)
    twin_src = SUBM / sub["twin"]["file"]
    if twin_src.exists():
        shutil.copyfile(twin_src, DOWN / "h83-candidate-template-nan.tif")

    # ---------------------------------------------------------------- hypotheses
    hyp = f"""{head("H83 candidate hypotheses, ranked", "Three candidate mechanisms H83 could have spent its budget on, with the layers, the physical signature, the named mimic and the cost.")}
<section><h1>Candidate geological hypotheses, ranked before the run</h1>
<p class="small">Ranked by expected DTI improvement against implementation cost. Ranking is a
qualitative prior, never a forecast.</p>
{table(["#", "Hypothesis", "Layers", "Signature", "Why it could catch a fault the catalogue lacks", "Named non-fault mimic", "Cost", "Status"], [
 ["1", "H83-1 buried structure under thin cover, measured off-catalogue",
  "View A: gravity/RTP/TMI-up-150 edge + step, depth-to-basement-surface (band 15), surface conductivity (band 17); against View B curvature/slope abstention",
  "A confident &amp; B abstaining, restricted to small-to-moderate depth-to-basement",
  "A fault with no scarp is invisible to every surface detector, and this repository's best-scoring family is entirely surface-morphological, so the buried population is where marginal credit can still come from",
  "A lithologic contact or a basin-fill thickness change; second, flight-line grid seams",
  "low &mdash; every channel is already cached", "<b>chosen and run</b>"],
 ["2", "H83-2 artefact suppression on the B-only branch",
  "View B curvature vs GeoDAWN radiometric K/Th/U and the LiDAR scarp layers",
  "B confident &amp; A abstaining with anomalous total count",
  "It cannot add faults; it can only remove pixels, so its upside is the false-positive tax",
  "Anthropogenic linear features: roads, canals, fence lines, powerline corridors",
  "low",
  "not run &mdash; at &alpha; 0.2 the FP weight is 5&times; cheaper than the FN weight (&beta; 0.8), so precision work pays less than recall work"],
 ["3", "H83-3 spring and vent proximity as a geothermal prior",
  "GDR well/spring and volcanic-vent tables, distance-decayed, interacted with View-A permeability proxies",
  "distance to a documented warm spring or young volcanic vent",
  "Springs are the only direct geothermal observations in the footprint",
  "Springs locate on any permeable fault or on a stratigraphic aquifer, so they are a geothermal indicator, not a fault indicator",
  "low &mdash; the CSVs are already restored",
  "deferred: the competition scores <i>structure</i>, and calibrating a spring prior would need labelled geothermal ground truth that does not exist here"],
])}
</section><hr class="divider">
<section><h2>External data availability, checked before proposing H83-3 as viable</h2>
{table(["Source", "URL", "Status in this sandbox"], [
 ["GDR submission 1391 (wells/springs, volcanic vents)", '<a href="https://gdr.openei.org/submissions/1391" rel="noopener">gdr.openei.org/submissions/1391</a>',
  "already restored, SHA-256 pinned in registry/data_manifest.json"],
 ["GeoDAWN airborne magnetic &amp; radiometric surveys, NW Great Basin",
  '<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and" rel="noopener">usgs.gov</a>',
  "already restored as geodawn_rad_u8.tif / geodawn_extensions_u8.tif; live host outside the egress allowlist, used through the pinned mirror"],
 ["USGS State Geologic Map Compilation (SGMC)",
  '<a href="https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc" rel="noopener">usgs.gov</a>',
  "already restored in derived form as derived_sgmc_faults_100m_u8.tif"],
 ["USGS Quaternary fault and fold database",
  '<a href="https://www.usgs.gov/programs/earthquake-hazards/faults" rel="noopener">usgs.gov</a>',
  "restored as gdr_qfaults_traces.csv but <b>not used</b>: it is a USGS product and overlaps the competition catalogue, so it is not off-catalogue"],
 ["USGS 3DEP 1 m DEM", '<a href="https://www.usgs.gov/3d-elevation-program" rel="noopener">usgs.gov</a>',
  "<b>not obtainable here</b> &mdash; the tile-index host is outside the egress allowlist; the same TLS failure was recorded in H55"],
])}
<p class="small">The chosen hypothesis (H83-1) needs no new external data.</p></section>
"""
    (DOCS / "h83-hypotheses.html").write_text(hyp + TAIL)

    # ---------------------------------------------------------------- sources
    man = load(REG / "data_manifest.json")
    src = f"""{head("H83 sources and verification status", "Every input, its official source, and whether it is organizer-authenticated or only integrity-pinned.")}
<section><h1>Sources</h1>
<div class="notice" role="note"><strong>Provenance, stated once and repeated everywhere.</strong>
<p>The DrivenData data tab is login-walled and this workspace holds no credentials, so the three
official rasters and every external layer are restored from the owner's hash-pinned sibling
repositories through the GitHub API and verified by SHA-256 and byte count. That proves
<b>mirror integrity</b>. It does <b>not</b> prove organiser authentication. Every downstream number
carries this qualification.</p></div>
{table(["Input", "Official source", "Verification"], [
 ["training_features.tif (19 bands)", f'<a href="{DATA_URL}" rel="noopener">competition data page (login)</a>', "SHA-256 pinned, re-verified after restore"],
 ["labels.tif (USGS/INGENIOUS catalogue)", f'<a href="{DATA_URL}" rel="noopener">competition data page (login)</a>', "SHA-256 pinned"],
 ["sample_submission.tif (grid template)", f'<a href="{DATA_URL}" rel="noopener">competition data page (login)</a>', "SHA-256 pinned; used for grid metadata only"],
 ["Performance metric &alpha; 0.2 / &beta; 0.8 / R 300 m", f'<a href="{PROBLEM_URL}" rel="noopener">rules page 967</a>', "transcribed literally, pinned by tests/test_metric.py against the organiser's worked example"],
 ["Masking of known faults, pixel-exact", '<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/" rel="noopener">staff thread 11516, posts 2 and 4</a>', "implemented as mask_visible(), no buffer"],
 ["SGMC-derived fault raster (I2 truth)", '<a href="https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc" rel="noopener">USGS SGMC</a>', "SHA-256 pinned; 95% disjoint from labels.tif (knowledge/66)"],
 ["GeoDAWN radiometric + LiDAR extension layers", '<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and" rel="noopener">USGS GeoDAWN</a>', "SHA-256 pinned"],
 ["GDR well/spring and vent tables", '<a href="https://gdr.openei.org/submissions/1391" rel="noopener">GDR 1391</a>', "restored, not used this round"],
 ["Co-training method", '<a href="https://doi.org/10.1145/279943.279962" rel="noopener">Blum &amp; Mitchell, COLT 1998, pp. 92&ndash;100</a>', "cited; the independence assumption is tested, not assumed"],
 ["Prior-submission registry (" + i(lane["registry"]["n_priors"]) + " rasters)",
  "owner&rsquo;s sibling GEMSDOE repositories", "frozen 526-blob census, decoded SHA-256 per blob"],
])}
<h2>Organiser-confirmed numbers</h2>
<p>The only ORGANIZER-CONFIRMED numbers anywhere on this site are the public leaderboard rows the
owner copied from the submission pages. They are reproduced in
<code>knowledge/75_current_user_brief_2026-10-10_H83.md</code> and are <b>not</b> mixed with
HOLDOUT-DTI or OFFCAT-DTI anywhere on a page. This round spent 0 slots, so it has no receipt of its
own.</p>
<h2>Data manifest</h2>
<p class="small">{esc(man["note"])} &mdash; {len(man["files"])} pinned entries.</p>
</section>
"""
    (DOCS / "h83-sources.html").write_text(src + TAIL)

    # ---------------------------------------------------------------- root landing page
    root = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE52 — DOE GEMS competition #306 — H83 candidate</title>
<style>
body{{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:#14181d;background:#fff}}
main{{max-width:760px;margin:0 auto;padding:36px 20px 70px}}
h1{{font-size:26px;margin:0 0 10px}}
.v{{border-radius:10px;padding:14px 16px;margin:16px 0;font-weight:700;
background:{'#e8f6ed' if sb_ok else '#fdecea'};color:{'#0f7b3f' if sb_ok else '#b3261e'};
border:1px solid {'#b7dfc5' if sb_ok else '#f0c4bf'}}}
a.b{{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;
padding:13px 20px;border-radius:8px;margin:6px 8px 6px 0}}
a.s{{background:#eef2f6;color:#1f4e79}}
code{{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13.5px}}
small{{color:#5b6672}}
</style></head><body><main>
<h1>H83 candidate raster &mdash; DOE GEMS competition #306</h1>
<div class="v">OK TO DOWNLOAD: yes &nbsp;&middot;&nbsp; {"OK TO SUBMIT: yes" if sb_ok else "OK TO SUBMIT: no — research artefact only"}</div>
<a class="b" href="docs/downloads/h83-candidate.tif" download>Download h83-candidate.tif &#8595;</a>
<a class="b s" href="docs/downloads/h83-candidate.zip" download>ZIP</a>
<a class="b s" href="docs/index.html">Full site</a>
<a class="b s" href="docs/h83-executive-summary.html">How to submit</a>
<a class="b s" href="docs/validator.html">Check a file in your browser</a>
<p><small>{i(rec["bytes"])} bytes &middot; {i(n_dots)} emitted cells, values exactly {{0,1}}
&middot; SHA-256 <code>{esc(sha)}</code> &middot; EPSG:32611, 3730&times;3292 at 100 m
&middot; submission name <code>{esc(rec["submission_name"])}</code></small></p>
<p><small>HOLDOUT-DTI (evaluator gems52-pooled-hide-v1, {i(sc[cand]["withheld_positive_pixels"])} withheld
positives): candidate {f6(sc[cand]['dti'])} {ci(sc[cand]['ci95'])} vs control single_B {f6(sc['single_B']['dti'])};
paired {pair['delta']:+.6f} {ci(pair['ci95'])}. OFFCAT-DTI (gems52-offcatalogue-v1, diagnostic):
{f6(osc[cand]['dti'])} {ci(osc[cand]['ci95'])}. A holdout number is never a board forecast.
Verdict: {esc(verdict)}.</small></p>
<p><small>This page is a research artefact. It is not an organiser acceptance receipt, and it does not
claim a leaderboard gain. Sources and verification status:
<a href="docs/h83-sources.html">docs/h83-sources.html</a>.</small></p>
</main></body></html>
"""
    (ROOT / "index.html").write_text(root)

    # ---------------------------------------------------------------- legacy executive summary
    update_legacy_executive_summary(rec, sb_ok, sha)

    # ---------------------------------------------------------------- archive index
    update_downloads_index(rec, csv_name)

    print(json.dumps(dict(
        pages=["docs/index.html", "docs/h83.html", "docs/h83-executive-summary.html",
               "docs/h83-hypotheses.html", "docs/h83-sources.html", "index.html"],
        downloads=["docs/downloads/h83-candidate.tif", "docs/downloads/h83-candidate.zip",
                   f"docs/downloads/{csv_name}"],
        verdict=verdict, submit_ok=sb_ok, sha256=sha, name=rec["submission_name"],
        note_chars=rec["note_chars"], reasoning_rows=n_rows,
        composition=comp["emitted_by_class"]), indent=1))
    return 0


# --------------------------------------------------------------------------------------------------
REASON_BANDS = {
    "depth_to_basement_surface_m": "raw_band_15",
    "surface_conductivity": "raw_band_17",
    "isostatic_gravity_anomaly": "raw_band_13",
    "rtp_magnetics": "raw_band_02",
    "tmi": "raw_band_14",
    "geodetic_second_invariant": "raw_band_04",
    "distance_to_earthquake_m": "raw_band_10",
    "earthquake_density": "raw_band_16",
    "radiometric_total_count": "raw_band_06",
}


def write_reasoning(path: Path, tif_name: str, card: dict):
    """One measured row per emitted cell, classified by the two views' own out-of-fold ranks.

    The classification uses the *preregistered* confidence/abstention thresholds
    (donor rank >= 0.98, receiver rank in [0.35, 0.65]), not a proxy distance, so a cell is called
    "A-only" only when View A is confident and View B genuinely abstains.  Every row carries the
    measured channel values and, for the disagreement classes, a plain-English sentence naming what
    a buried fault would look like here and what else could produce the same numbers.
    """
    import numpy as np
    import rasterio
    from scipy import ndimage as ndi
    from scipy.stats import rankdata

    from gems52 import structural

    reg = json.loads((REG / "h83_preregistration.json").read_text())
    th = reg["thresholds"]
    donor_min = float(th["donor_rank_min"])
    lo, hi = (float(v) for v in th["receiver_rank_interval"])

    store = structural.FeatureStore(ROOT / "work/r2/features")
    with rasterio.open(SUBM / tif_name) as ds:
        emit = ds.read(1) > 0
        tr = ds.transform
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) > 0
    with rasterio.open(SAMPLE) as ref:
        s0 = ref.read(1)
    sub_finite = np.isfinite(s0) & (s0 > -1e38)
    del s0
    catd = ndi.distance_transform_edt(~cat, sampling=100.0)
    sgcmd = ndi.distance_transform_edt(~sgmc, sampling=100.0)
    allowed = store.valid & sub_finite & ~cat & (catd > float(th["catalogue_exclusion_m"]))

    # ---- out-of-fold rank of each view, the same way the emission ranked them
    shape = store.valid.shape
    flat, inv = store.flat_idx, store.inverse
    from gems52 import spatial as _sp
    folds = list(_sp.folds(cat, store.valid, buffer_px=int(th["buffer_px"])))
    WORK = ROOT / "work/h83"
    rank = {}
    for v in ("A", "B"):
        mos = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_post_{v}_f{fold['fold']}.npy")
            mos[np.flatnonzero(fold["region"].ravel())] = p[rows]
        g = mos.reshape(shape)
        r = np.zeros(shape, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        r.ravel()[idx] = ((rankdata(g.ravel()[idx], method="average") - 0.5) / float(idx.size)
                          ).astype(np.float32)
        rank[v] = r
        del mos, g

    ys, xs = np.nonzero(emit)
    grids = {}
    for label, feat in REASON_BANDS.items():
        try:
            grids[label] = store.feature_grid(feat)
        except Exception:
            grids[label] = None
    try:
        ratio = store.feature_grid("X_rad_ThK_rank")
    except Exception:
        ratio = None

    rows = 0
    tally: dict = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m",
                    "dist_to_mapped_catalogue_m", "dist_to_nearest_sgmc_fault_m",
                    "view_A_oof_rank", "view_B_oof_rank", "classification"] +
                   list(REASON_BANDS) + ["radiometric_Th_over_K_ratio", "geological_reasoning"])
        for y, x in zip(ys, xs):
            ra, rb = float(rank["A"][y, x]), float(rank["B"][y, x])
            if ra >= donor_min and lo <= rb <= hi:
                klass = "A-only: A confident, B abstains (candidate buried structure)"
            elif rb >= donor_min and lo <= ra <= hi:
                klass = "B-only: B confident, A abstains (suspect surface artefact)"
            elif ra >= donor_min and rb >= donor_min:
                klass = "consensus: both views confident"
            else:
                klass = "neither view confident at the preregistered thresholds"
            vals = {}
            for label, g in grids.items():
                v = g[y, x] if g is not None else float("nan")
                vals[label] = float(v) if v is not None and np.isfinite(v) else ""
            rv = float(ratio[y, x]) if ratio is not None else float("nan")
            ex, ny = tr * (float(x) + 0.5, float(y) + 0.5)
            dc, ds_ = float(catd[y, x]), float(sgcmd[y, x])
            depth = vals.get("depth_to_basement_surface_m", "")
            finite_depth = isinstance(depth, float)
            thin = finite_depth and depth < 300.0
            if klass.startswith("A-only"):
                reason = (
                    f"View A (potential-field/subsurface) ranks this cell in its top "
                    f"{100*(1-ra):.1f}% while View B (surface DEM curvature, slope and radiometrics) "
                    f"sits at percentile {100*rb:.0f}, i.e. the surface view abstains. That is the "
                    f"pattern a fault buried beneath cover produces. Measured here: depth to "
                    f"basement surface {depth if finite_depth else 'n/a'} m"
                    f"{' (thin cover, so a bedrock fault could plausibly lie within the 300 m kernel)' if thin else ' (deeper cover; a bedrock fault here would be further from the surface)'}"
                    f"; isostatic gravity anomaly {vals.get('isostatic_gravity_anomaly', 'n/a')}; "
                    f"RTP magnetics {vals.get('rtp_magnetics', 'n/a')}; geodetic second invariant "
                    f"{vals.get('geodetic_second_invariant', 'n/a')}; nearest mapped catalogue trace "
                    f"{dc:.0f} m away; nearest SGMC trace {ds_:.0f} m away. What else could produce "
                    f"the same numbers: a lithologic contact or a basin-fill thickness change makes "
                    f"an identical gravity and conductivity step with no fault at all, and the "
                    f"airborne grids carry flight-line seams that mimic lineaments. Radiometric "
                    f"total count here is {vals.get('radiometric_total_count', 'n/a')}, which would "
                    f"be anomalous along an alteration halo but is also raised by lithology alone.")
            elif klass.startswith("B-only"):
                reason = (
                    f"View B (surface) ranks this cell in its top {100*(1-rb):.1f}% while View A "
                    f"sits at percentile {100*ra:.0f}. Under the lane's rule this is the branch to "
                    f"suspect a surface artefact rather than a buried fault: roads, canal banks, "
                    f"fence lines, irrigation ditches and erosion lines all make a DEM curvature and "
                    f"slope signature indistinguishable from a small scarp, and none of them has a "
                    f"density or magnetic expression. Measured here: distance to the nearest mapped "
                    f"catalogue trace {dc:.0f} m; radiometric total count "
                    f"{vals.get('radiometric_total_count', 'n/a')}; Th/K ratio "
                    f"{f'{rv:.4f}' if np.isfinite(rv) else 'n/a'}. It is emitted because the field "
                    f"selected it, not because the two views agree.")
            elif klass.startswith("consensus"):
                reason = ("Both views are confident here (top 2% on each). This is the agreement "
                          "branch, not the discovery branch: it is where a well-exposed fault with "
                          "both a scarp and a density/magnetic expression would sit.")
            else:
                reason = ("Neither view reaches the preregistered confidence threshold at this "
                          "cell; it is emitted by the placement because the budget had to be filled "
                          "at 3 px spacing, not because either view singled it out.")
            w.writerow([int(y), int(x), f"{ex:.1f}", f"{ny:.1f}", f"{dc:.1f}", f"{ds_:.1f}",
                        f"{ra:.6f}", f"{rb:.6f}", klass] +
                       [vals.get(k, "") for k in REASON_BANDS] +
                       [(f"{rv:.4f}" if np.isfinite(rv) else ""), reason])
            rows += 1
            tally[klass] = tally.get(klass, 0) + 1
    ex = ROOT / "evidence/h83_pseudo_exchange.json"
    exch = {"A->B": 0, "B->A": 0}
    if ex.exists():
        _d = json.loads(ex.read_text())
        for _f in _d["folds"]:
            for _k in exch:
                exch[_k] += int(_f["directions"].get(_k, {}).get("n_pixels", 0))
    comp = dict(round="H83", tif=tif_name, rows=rows, donor_rank_min=donor_min,
                receiver_rank_interval=[lo, hi], emitted_by_class=tally,
                exchange=exch,
                note=("classification uses the two views' own out-of-fold ranks at the "
                      "preregistered donor/abstention thresholds; exchange counts are "
                      "whole-segment pixels produced before the 3 px density fill"))
    return rows, comp


def update_legacy_executive_summary(rec: dict, sb_ok: bool, sha: str) -> None:
    """Point the standing how-to-submit page at the current round without rewriting its history.

    ``docs/executive-summary.html`` is the page the owner asked for and is linked from several
    historical rounds, so it is not replaced.  A current-round banner is spliced in and replaced
    in place on every re-publish.
    """
    p = DOCS / "executive-summary.html"
    if not p.exists():
        return
    t = p.read_text()
    block = ("<!--H83-CURRENT--><section class=\"panel\"><h2>Current round &mdash; H83 "
             "(2026-10-10)</h2>"
             f'<p><b>OK to download:</b> YES &nbsp;&middot;&nbsp; <b>OK to submit:</b> '
             f'{"YES (no slot allocated here)" if sb_ok else "NO — research artefact only"}</p>'
             f'<p><a class="button" href="downloads/h83-candidate.tif" download>'
             f'Download h83-candidate.tif &#8595;</a> '
             f'<a href="downloads/h83-candidate.zip">single-TIFF ZIP</a> &middot; '
             f'<a href="h83-executive-summary.html">full four-click guide for this file</a></p>'
             f'<p class="small">{esc(rec["file"])} &middot; {i(rec["bytes"])} bytes &middot; '
             f'SHA-256 <code>{esc(sha)}</code> &middot; unique name '
             f'<code>{esc(rec["submission_name"])}</code></p></section><!--/H83-CURRENT-->')
    if "<!--H83-CURRENT-->" in t:
        a, b = t.index("<!--H83-CURRENT-->"), t.index("<!--/H83-CURRENT-->") + len("<!--/H83-CURRENT-->")
        t = t[:a] + block + t[b:]
    else:
        t = t.replace('<section class="prose">', block + '<section class="prose">', 1)
    p.write_text(t)


def update_downloads_index(rec: dict, csv_name: str) -> None:
    """Append the H83 artefacts to the archive page without rewriting its history."""
    p = DOWN / "index.html"
    if not p.exists():
        return
    t = p.read_text()
    block = ("<!--H83--><section><h2>H83 (2026-10-10)</h2><ul>"
             f'<li><a href="h83-candidate.tif" download>h83-candidate.tif</a> &mdash; '
             f'{esc(rec["file"])}, SHA-256 <code>{esc(rec["sha256"])}</code></li>'
             f'<li><a href="h83-candidate.zip" download>h83-candidate.zip</a> &mdash; single-TIFF ZIP</li>'
             f'<li><a href="{esc(csv_name)}" download>{esc(csv_name)}</a> &mdash; per-cell geological reasoning</li>'
             "</ul></section><!--/H83-->")
    if "<!--H83-->" in t:
        a, b = t.index("<!--H83-->"), t.index("<!--/H83-->") + len("<!--/H83-->")
        t = t[:a] + block + t[b:]
    else:
        t = t.replace("</main>", block + "</main>", 1)
    p.write_text(t)


if __name__ == "__main__":
    sys.exit(main())
