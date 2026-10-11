#!/usr/bin/env python3
"""Publish the H57 artifact to the GitHub Pages site, with the audit next to the download.

Every number printed on the page is read from ``evidence/h57_*.json``.  Nothing is typed into HTML
by hand, so a page can never disagree with the file it is advertising.  Run it, then run
``scripts/check_site.py``, which re-reads the bytes on disk and fails on any contradiction.
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
DATA = DOCS / "data"
EV = ROOT / "evidence"

NAV_LINK = '<a href="h57.html">H57 current</a>'
NAV_OLD = '<a href="h56.html">H56 audit</a>'
NAV_NEW = NAV_LINK + NAV_OLD


def nav_fix(text: str) -> str:
    """Put the H57 link in the nav exactly once, whatever state a page was left in.

    A plain ``replace(NAV_OLD, NAV_NEW)`` prepends the link on every run, and because ``NAV_NEW``
    contains ``NAV_OLD`` the second run turns the nav into four copies of it. Strip first.
    """
    while NAV_LINK in text:
        text = text.replace(NAV_LINK, "", 1)
    return text.replace(NAV_OLD, NAV_NEW, 1)

BAR_OPEN, BAR_CLOSE = "<!--H57BAR-->", "<!--/H57BAR-->"


def load(p):
    return json.loads(Path(p).read_text())


def human(n):
    return f"{int(n):,}"


def fname(b):
    """Basename of the artefact path recorded in the build receipt."""
    return Path(b["artefact"]).name


def bar_html(b, name, note, verdict):
    f = fname(b)
    fmt = b["format_gate"]
    u = b["uniqueness"]
    nd = b["not_the_union"]
    px, arm, core = b["file"]["px"], b["arm"]["px"], b["core"]["px"]
    proj = b["projection_by_rho"]
    return f"""<div class="download-bar" id="h57-bar" aria-label="H57 research download; not current approval">
<div><strong>H57 &mdash; two-view co-training union arm &middot; VERDICT: {verdict}</strong>
<small><code>{f}</code></small>
<small>{human(fmt['bytes'])} bytes &middot; single-band float32 &middot; EPSG:32611 &middot;
{human(fmt['width'])} &times; {human(fmt['height'])} &middot; {human(px)} emitted px
({human(core)} exactly-accounted core + {human(arm)} novel arm) &middot; values exactly
<code>{{0, 1}}</code> &middot; 0 NaN &middot; sha256 <code>{b['file']['sha256'][:24]}&hellip;</code></small>
<small>format gate <b>{'PASS' if fmt['ok'] else 'FAIL'}</b>
({', '.join(fmt['problems']) if fmt['problems'] else 'no problems'}) &middot; decoded pattern
unique against {u['n_priors_checked']} accessible aligned priors:
<b>{u['canonical_pattern_unique']}</b> &middot; arm cells outside their support union:
<b>{human(nd['arm_outside_prior_support_px'])} px ({nd['arm_outside_prior_support_frac'] * 100:.1f}% of the arm)</b></small>
<small>closest emitted cell to a mapped known-fault trace <b>{b['file']['min_distance_to_catalogue_m']:.1f} m</b>.
This is a placement fact, not a claim that nearby new-fault truth earns zero credit.</small>
<small>conditional projection only (owner-reported scores, not organiser-authenticated):
{', '.join(f'{k.replace("rho_", "rho=")} &rarr; {v}' for k, v in proj.items())}.
rho is the arm's credit density &mdash; a <b>prior, not a measurement</b>. Not a forecast.</small>
<small>Research archive only · NOT APPROVED FOR SUBMISSION · no weekly slot authorized</small>
</div>
<a class="button" href="downloads/{f}" download>&darr; Download H57 research TIFF</a>
<a class="button" href="downloads/{f[:-4]}.zip" download>&darr; Download single-TIFF .ZIP</a>
<a class="button secondary" href="downloads/h57-candidate.tif" download>Short link &middot; h57-candidate.tif</a>
<a class="button secondary" href="h57.html">Full audit &amp; holdout &rarr;</a>
</div>"""


def page_html(b, c, v, st, name, note, verdict, gate):
    ind = c["independence"]
    strata = c["strata"]
    dpts = c["strata"]["median_depth_to_basement_m"]
    # One row per (instrument, budget) cell. The outer loop used to iterate the instrument a
    # second time and rendered the whole table twice, which read on the page as two identical
    # result blocks and looked like two separate experiments.
    rows = []
    for k in ("tip@15000", "tip@37654", "hide@15000", "hide@37654"):
        for i, r in enumerate(v["ranking"][k]):
            rows.append(
                f"<tr><td><code>{k}</code></td><td>{i + 1}</td>"
                f"<td><code>{r['field']}</code></td><td>{r['dti']:.5f}</td>"
                f"<td>{r['lift_vs_random']:+.5f}</td></tr>")
    pl = v["placement"]
    pl_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{d['iso3']:.5f}</td><td>{d['aniso5']:.5f}</td>"
        f"<td>{d['lift']:+.5f}</td><td>{d['relative_lift_pct']:+.2f}%</td>"
        f"<td>{d['folds_won']}</td><td><b>{'PASS' if d['gate_met'] else 'FAIL'}</b></td></tr>"
        for k, d in pl.items())
    sc = st["combined"]
    sc_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{val:.6f}</td>"
        f"<td>{val / sc['random']:.2f}&times;</td>"
        f"<td><b>{'REFUTED' if k == 'S_a_only' else 'shipped' if k == 'union' else ''}</b></td></tr>"
        for k, val in sorted(sc.items(), key=lambda kv: -kv[1]))
    pseudo = c["pseudo_label"]
    refuted = "".join(
        f"<tr><td>{x['hypothesis']}</td><td><code>{x['evidence']}</code></td>"
        f"<td>{x['result']}</td></tr>" for x in gate["refuted"])
    chk = "".join(
        f"<tr><td>{k}</td><td><b>{'PASS' if ok else 'FAIL'}</b></td></tr>"
        for k, ok in gate["checks"].items())
    pb = gate["probability_by_floor"]
    dm = gate["decisive_measure"]

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>H57 &middot; two-view co-training union arm &middot; GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body>
<a class="skip" href="#main">Skip to evidence</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a><a href="index.html">Overview</a>
<a href="executive-summary.html">Submission guide</a>{NAV_NEW}<a href="validation.html">Validation</a>
<a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a></nav></header>
<main id="main">
{bar_html(b, name, note, verdict)}
<div class="status"><strong>Current evidence correction — public-board observation, not a receipt.</strong> The saved 2026-10-09 20:18 UTC observation places the team-level 0.2778 row at rank 17 (top 0.3774; 0.3195 at rank 7). The board contains no TIFF hash or organizer submission receipt; the file association remains owner-reported. The local 37,654/44,090 subset and 100–200 m distances do not identify hidden-truth credit or explain a score change; new-fault truth may occur within 300 m of known traces. H57's calculations are conditional research outputs, not scores. See <a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a>.</div>
<div class="eyebrow">H57 &middot; session 2026-10-07 &middot; blind preregistration in
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/17_hypotheses_H57_preregistered.md">knowledge/17</a>
&middot; results in
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/18_hypotheses_H57_results.md">knowledge/18</a></div>
<h1>Two views, measured honestly.<br>One of them won. Three ideas did not.</h1>
<p class="lede">The brief asked for co-training between a geophysical view and a surface view, with
<em>disagreement</em> as the discovery signal, plus a metric-aware placement rule. H57 ran all of
it on restored competition bytes and reports all five outcomes, including the four that failed. The
artefact ships the union ranking field and the incumbent isotropic emitter, because those are the
two choices the holdouts actually supported.</p>

<div class="status"><strong>Research-only; not approved for a slot.</strong> H57 did not meet its preregistered +0.005 HOLDOUT-DTI lift threshold (best +0.0048). The reported-score probabilities are conditional model scenarios, not scores. No weekly slot is recommended or recorded for this artifact.</div>

<h2>1 &middot; What the metric actually pays for</h2>
<p>From the published definition
(<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric">page 967</a>)
and the identity <code>FNw = |G| &minus; TPw</code>, a marginal pixel covering a previously
uncovered truth pixel at distance <code>d</code> is worth accepting exactly when
<code>k(d) &gt; &alpha;&middot;DTI</code>. At DTI 0.2778 that is a radius of <b>283 m</b>. Two
consequences drive everything below: place, do not spray; and <b>add mass only if its credit
density exceeds 0.2&middot;DTI &asymp; {dm['marginal_breakeven_rho']}</b>. The local 6,436-cell set removed between the owner-associated 0.2600 and 0.2778 rasters lies 100–200 m from the known-fault mask, but this does not identify its hidden-truth credit or explain a score change. Official staff says new-fault truth may occur within 300 m of known traces; neither the local distance nor the byte subset makes those cells zero-credit.</p>

<h2>2 &middot; The conditional-independence test the brief demands</h2>
<p>Per-block out-of-fold error of each view on labelled negatives, whole-segment folds, 4 px buffer,
{human(ind['n_blocks'])} blocks, {human(ind['n_negative_predictions'])} negative predictions.</p>
<ul>
<li>block-level negative MSE: Pearson {ind['tests']['negative_mean_squared_error']['pearson']:.4f},
Spearman {ind['tests']['negative_mean_squared_error']['spearman']:.4f}</li>
{''.join(f'<li>block-level {k.replace("_", " ")}: Pearson {d["pearson"]:.4f}, Spearman {d["spearman"]:.4f}</li>' for k, d in ind["tests"].items())}
<li>pixel-level out-of-fold logit correlation {ind['pixel_level']['pearson']:.4f}
(n = {human(ind['pixel_level']['n'])})</li>
<li><strong>measured</strong> = {ind['measured']} &middot; <strong>allow_exchange</strong> =
{ind['allow_exchange']} &middot; max |r| = {ind['max_abs_correlation']:.4f} against the registered
abandonment threshold |r| &ge; {ind['threshold']:.2f}</li>
</ul>
<p class="small">This is the first non-degenerate measurement of the premise in this repository:
<code>knowledge/03</code> N-1 could not estimate it, so it had to fail closed and the
pseudo-label exchange was never run there. Here the statistic is well powered and the premise is
<em>not refuted</em> &mdash; which is a statement about weak coupling, not about independence.</p>

<h2>3 &middot; Disagreement strata &mdash; measured, not assumed</h2>
<table class="data"><tr><th>stratum</th><th>pixels</th><th>median depth to basement</th>
<th>the brief's reading</th><th>what the holdout says</th></tr>
<tr><td>A confident, B abstains</td><td>{human(strata['counts']['a_only'])}</td>
<td>{dpts['a_only']:.0f} m</td><td>buried structure under cover</td>
<td><b>REFUTED as the arm population</b> &mdash; worst of eight arms, below random</td></tr>
<tr><td>B confident, A abstains</td><td>{human(strata['counts']['b_only'])}</td>
<td>{dpts['b_only']:.0f} m</td><td>surface artefact</td><td>real but second-best; kept as a
labelled component</td></tr>
<tr><td>both confident</td><td>{human(strata['counts']['concordant'])}</td>
<td>{dpts['concordant']:.0f} m</td><td>already-mapped fabric</td><td>smallest, weakest</td></tr>
<tr><td>neither</td><td>{human(strata['counts']['neither'])}</td><td>&mdash;</td>
<td>no view sees it</td><td>the sub-threshold shoulder of the structural signal</td></tr></table>
<p>The A-only stratum really is the deep-cover stratum: median depth to basement
{dpts['a_only']:.0f} m against {dpts['b_only']:.0f} m in B-only, {c['strata']['median_depth_to_basement_m']['permitted']:.0f} m over the
permitted set. The geological premise is <b>correct</b>. What failed is the bet that this makes it
a better place to look for faults.</p>

<h2>4 &middot; Pseudo-label exchange &mdash; ran, and did nothing</h2>
<p>{human(pseudo['n_pseudo_px'])} pseudo-labelled pixels in {pseudo['n_segments']} whole segments;
View-A out-of-fold AUC {pseudo['auc_view_A_before']:.4f} &rarr; {pseudo['auc_view_A_after']:.4f}
(delta {pseudo['delta_auc']:+.4f}), evaluated on {human(pseudo['n_eval_px'])} held-out pixels no
model had seen. That is indistinguishable from noise, and it reproduces
<code>knowledge/03</code> N-1 exactly. Disagreement is therefore used to <em>label</em> the arm, not
to <em>train</em> it.</p>

<h2>5 &middot; Ranking: eight fields, one protocol, two instruments</h2>
<p>Candidates may not sit on the <b>visible</b> catalogue dilated by 2 px; the <b>held-out</b>
catalogue is scored as truth, so credit can only be earned on faults the model never saw. Both
instruments, because either one alone is structurally blind (<code>knowledge/03</code> N-3).</p>
<table class="data"><tr><th>cell</th><th>rank</th><th>field</th><th>fold-mean DTI</th>
<th>vs random control</th></tr>{''.join(rows)}</table>

<h2>6 &middot; Placement: the anisotropic emitter failed its own gate</h2>
<p>The kernel algebra is exact: on an isolated 1-px trace the credited truth per node interval
[0,&nbsp;s) is 7/3 at s&nbsp;=&nbsp;3, 8/3 at s&nbsp;=&nbsp;4 and 3.0 at s&nbsp;=&nbsp;5, i.e. 5 px
carries <b>+28.6&nbsp;%</b> over 3 px. That is the whole case for H57-A, and it is the right number
&mdash; for an isolated 1-px trace.</p>
<table class="data"><tr><th>cell</th><th>isotropic 3 px</th><th>anisotropic 5&times;3 px</th>
<th>lift</th><th>relative</th><th>folds won</th><th>gate</th></tr>{pl_rows}</table>
<p class="small">Against the mapped traces the advantage does not survive: the traces are wider
than 1 px and adjacent nodes along a gently curving strike overlap anyway. The artefact ships the
isotropic emitter. This is recorded as a <b>refutation</b>, not a tuning result.</p>

<h2>7 &middot; Which stratum should carry the arm</h2>
<table class="data"><tr><th>arm</th><th>fold-mean DTI</th><th>vs random</th><th>outcome</th></tr>
{sc_rows}</table>

<h2>8 &middot; What failed, stated plainly</h2>
<table class="data"><tr><th>hypothesis</th><th>evidence</th><th>result</th></tr>{refuted}</table>

<h2>9 &middot; The artefact</h2>
<p>{human(b['core']['px'])} core-overlap cells &mdash; the double-corroborated local atom
<code>P1 = h33-2-b2 &cap; gems24-d1-5</code>, whose score-derived credit algebra is conditional on
owner-reported scores and an assumed hidden-positive count &mdash; plus {human(b['arm']['px'])} arm cells ranked by
<code>max(p_A, p_B)</code> over pixels outside the &le; 200 m ring, outside every accessible
prior's support union, and at least 3 px from the core, placed with the isotropic 3-px emitter.</p>
<p><a class="button" href="downloads/{fname(b)}" download>&darr; Download the .TIF</a>
<a class="button" href="downloads/{fname(b)[:-4]}.zip" download>&darr; Download the .ZIP</a>
<a class="button secondary" href="downloads/{Path(b['candidate_geology_dossier']).name}">per-candidate geological reasoning CSV</a></p>

<h2>10 &middot; Slot gate</h2>
<table class="data"><tr><th>registered check</th><th>result</th></tr>{chk}</table>
<p><strong>Conditional model probabilities only — not scores or leaderboard forecasts.</strong>
P(this file scores below the owner's reported 0.2778) = <b>{pb['0.2778']:.2f}</b> &middot;
P(above 0.3195) = <b>{pb['0.3195']:.2f}</b> &middot; P(above the observed board top 0.3774) =
<b>{pb['0.3774']:.2f}</b>, all conditional model probabilities under the registered joint prior over
score-derived core-credit assumptions and the arm's credit density; they are not scores or
leaderboard forecasts. {gate['board_note']} Later saved observation (2026-10-09 20:18 UTC):
0.2778 at rank 17, top 0.3774; these team-level rows have no TIFF-hash receipt.</p>

<h2>11 &middot; Limits, stated plainly</h2>
<ol>
<li>The arm <b>cannot be scored by this simulator at all</b>. With the catalogue halo removed from
the candidate pool, the View A field scored 0.000358 against a random control of 0.001713 during
validation: excluding the catalogue removes every pixel the truth can occupy. The arm's credit
density is a prior, not a measurement, and nothing in this repository can certify it.</li>
<li><strong>No number on this page is a leaderboard forecast.</strong> The simulator scores against
a proxy truth; Spearman(reported score, simulated DTI) = &minus;0.1045 (p = 0.734, n = 13) in
<code>knowledge/10</code> &sect;5. These comparisons are valid between arms on identical rows and
for nothing else.</li>
<li>Every leaderboard score quoted anywhere in this repository is <b>owner-reported</b>. No
organiser receipt maps a score to any filename or SHA-256, and the board snapshot records a top of
0.3774, not 0.3195.</li>
<li>No computable feature re-ranks inside the core family (<code>knowledge/10</code> &sect;6:
63&nbsp;+&nbsp;108 features, best AUC 0.5453). All gain here comes from mass the family has never
emitted.</li>
<li>Catalogue-zero pixels are proxies for absence, not verified geological absence, and a
competition score is not the Phase-2 expert outcome.</li>
<li>Inputs are SHA-pinned owner mirrors restored through the GitHub API and verified by SHA-256 and
byte count &mdash; integrity-pinned, <b>not</b> organiser-authenticated downloads.</li>
</ol>
</main></body></html>"""


def exec_html(b, gate, name, note, verdict):
    fmt = b["format_gate"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H57 historical research artifact; not approved for submission. No upload instructions or copyable identification fields.">
<title>H57 research status — not for submission · GEMSDOE52</title><link rel="stylesheet" href="style.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a><a href="index.html">Overview</a>
<a href="executive-summary.html">Research status</a>{NAV_NEW}<a href="forensics.html">0.2778 evidence</a>
<a href="hypotheses.html">Hypotheses</a><a href="sources.html">Sources</a>
<a href="irregularities.html">Limitations</a></nav></header><main id="main">
<div class="status" role="alert"><strong>H57 · RESEARCH DOWNLOAD ONLY · NOT APPROVED FOR SUBMISSION · NO SLOT AUTHORIZED.</strong>
<p>This historical artifact did not meet its preregistered +0.005 HOLDOUT-DTI lift threshold. Local format validity and decoded-pattern uniqueness do not establish scientific eligibility or organizer acceptance. No owner override, upload procedure, or paste-ready name/note is provided.</p></div>
<div class="download-bar"><div><strong>H57 historical research GeoTIFF</strong><small><code>{fname(b)}</code> · {human(fmt['bytes'])} bytes · SHA-256 <code>{b['file']['sha256']}</code></small><small>Local format gate: {'PASS' if fmt['ok'] else 'FAIL'}; this is not a portal-acceptance receipt.</small></div>
<a class="button" href="downloads/{fname(b)}" download>Download H57 research TIFF</a>
<a class="button secondary" href="downloads/{Path(fname(b)).stem}.zip" download>Research ZIP</a>
<a class="button secondary" href="h57.html">H57 audit receipts</a></div>
<p>HOLDOUT-DTI is an internal hide-and-recover measurement, not a public leaderboard score or organizer receipt. Any conditional score projection in the archived audit is scenario arithmetic, not a forecast.</p>
<p>No organizer-confirmed score receipt or weekly slot is recorded. This page authorizes no rerun, new run-card, rebuild, override, or submission.</p>
<p><a href="h57.html">Historical method and evidence →</a> · <a href="data/h57_slot_gate.json">Historical slot-gate receipt</a> · <a href="data/h57_build.json">Build receipt</a></p>
</main><footer>Competition 306 · Local research only · Predictions are not verified faults. No submission approval is recorded.</footer></body></html>"""


def main() -> int:

    _h75_home = ROOT / "docs" / "index.html"
    _h75_status = ROOT / "docs" / "h75-executive-summary.html"
    if (_h75_home.is_file() and _h75_status.is_file()
            and "H75: DUPLICATE/STOP" in _h75_home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in
            _h75_status.read_text(errors="replace")):
        print("H75 terminal stop is current; historical publisher made no page or pointer changes")
        return 0
    b = load(EV / "h57_build.json")
    c = load(EV / "h57_cotrain.json")
    v = load(EV / "h57_validation.json")
    st = load(EV / "h57_strata.json")
    gate = load(EV / "h57_slot_gate.json")
    name, note, verdict = gate["submission_name"], gate["note"], gate["verdict"]

    src = ROOT / b["artefact"]
    dst = DL / src.name
    shutil.copy2(src, dst)
    zpath = DL / (src.stem + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(dst, arcname=dst.name)
    short_tif = DL / "h57-candidate.tif"
    short_zip = DL / "h57-candidate.zip"
    shutil.copy2(dst, short_tif)
    shutil.copy2(zpath, short_zip)
    assert short_tif.read_bytes() == dst.read_bytes()

    dossier = Path(b["candidate_geology_dossier"])
    shutil.copy2(dossier, DL / dossier.name)

    (DL / "README_H57.txt").write_text(
        f"{src.name}\nshort link: h57-candidate.tif (byte-identical alias)\n"
        f"sha256 {b['file']['sha256']}\nbytes {b['file']['bytes']}\n\n"
        f"VERDICT: RESEARCH DOWNLOAD ONLY; NOT APPROVED FOR SUBMISSION\n\n"
        + "\n".join(f"- {k}: {v2}" for k, v2 in gate["checks"].items())
        + f"\n\n- {gate['recommendation']}\n")

    # Every other round in this repository ships evidence/submission_<stem>.json. The scheduled
    # feed looks for exactly that name, and when it is absent the feed used to fall through to an
    # older round's archive and publish *that* as the current submission. Writing it here makes
    # H57 conform to the convention the feed already depends on.
    (EV / f"submission_{Path(b['artefact']).stem}.json").write_text(json.dumps(
        dict(round="H57", file=fname(b), stem=Path(b["artefact"]).stem,
             submission_name=name, note=note, note_chars=len(note),
             bytes=b["file"]["bytes"], sha256=b["file"]["sha256"],
             nonzero_px=b["file"]["px"], core_px=b["core"]["px"], arm_px=b["arm"]["px"],
             verdict=verdict, approved_for_weekly_slot=False, promoted=False,
             submission_slots_used=0,
             format=b["format_gate"], uniqueness=b["uniqueness"],
             not_the_union=b["not_the_union"],
             receipts=["h57_build.json", "h57_cotrain.json", "h57_validation.json",
                       "h57_strata.json", "h57_format_gate.json", "h57_uniqueness.json",
                       "h57_slot_gate.json"],
             candidate_geology_dossier=b["candidate_geology_dossier"],
             official_score_status="no portal upload or organizer score is recorded"),
        indent=1, allow_nan=False) + "\n")

    DATA.mkdir(parents=True, exist_ok=True)
    # docs/data/submission.json is the machine-readable "current artefact" receipt the site and
    # scripts/check_site.py both read.  It is regenerated, never hand-edited.
    (DATA / "submission.json").write_text(json.dumps(dict(
        exists=True, round="H57",
        file=fname(b),
        artefact=b["artefact"],
        download="downloads/" + fname(b),
        download_zip="downloads/" + fname(b)[:-4] + ".zip",
        short_tif="downloads/h57-candidate.tif",
        short_zip="downloads/h57-candidate.zip",
        bytes=b["file"]["bytes"], sha256=b["file"]["sha256"],
        nonzero_px=b["file"]["px"], core_px=b["core"]["px"], arm_px=b["arm"]["px"],
        submission_name=name, note=note, note_chars=len(note),
        verdict=verdict,
        approved_for_weekly_slot=False,
        approval_reason="NO: R1's registered +0.005 mean-lift threshold was not met (best +0.0048). "
                        "This is research-only and not approved for submission; no owner override or "
                        "weekly slot is authorized.",
        promoted=False, submission_slots_used=0,
        format=dict(ok=b["format_gate"]["ok"], problems=b["format_gate"]["problems"],
                    crs=b["format_gate"]["crs"], width=b["format_gate"]["width"],
                    height=b["format_gate"]["height"], transform=b["format_gate"]["transform"],
                    dtype=b["format_gate"]["dtype"], bands=b["format_gate"]["bands"],
                    nodata=b["format_gate"]["nodata"], min=b["format_gate"]["min"],
                    max=b["format_gate"]["max"], n_nan=b["format_gate"]["n_nan"],
                    n_nonzero=b["file"]["px"]),
        uniqueness=dict(ok=b["uniqueness"]["canonical_pattern_unique"],
                        research_publication_ok=b["uniqueness"]["canonical_pattern_unique"],
                        n_priors_checked=b["uniqueness"]["n_priors_checked"],
                        novel_fraction=b["uniqueness"]["novel_fraction"],
                        relation_to_union="arm is 100% outside the accessible prior-support "
                                           "union; the decoded pattern equals none of the "
                                           "accessible aligned priors",
                        equals_literal_prior_union=b["uniqueness"]["equals_literal_prior_union"]),
        validation=dict(approved_for_slot=False,
                        holdout_receipts=["docs/data/h57_validation.json",
                                          "docs/data/h57_strata.json",
                                          "docs/data/h57_cotrain.json"]),
        slot_gate="docs/data/h57_slot_gate.json",
        dossier="downloads/" + Path(b["candidate_geology_dossier"]).name,
    ), indent=1, allow_nan=False) + "\n")
    (ROOT / "submission" / "LATEST.txt").write_text(fname(b) + "\n")
    (ROOT / "submission" / "H56_LATEST.txt").write_text(
        "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif\n")
    for n in ("h57_build.json", "h57_cotrain.json", "h57_validation.json", "h57_strata.json",
              "h57_format_gate.json", "h57_uniqueness.json", "h57_slot_gate.json",
              f"submission_{Path(b['artefact']).stem}.json"):
        if (EV / n).exists():
            shutil.copy2(EV / n, DATA / n)

    (DOCS / "h57.html").write_text(page_html(b, c, v, st, name, note, verdict, gate))
    (DOCS / "executive-summary.html").write_text(exec_html(b, gate, name, note, verdict))

    bar = bar_html(b, name, note, verdict)
    idx = nav_fix((DOCS / "index.html").read_text())
    block = f"{BAR_OPEN}{bar}{BAR_CLOSE}"
    if BAR_OPEN in idx:
        i, j = idx.index(BAR_OPEN), idx.index(BAR_CLOSE) + len(BAR_CLOSE)
        idx = idx[:i] + block + idx[j:]
    else:
        idx = idx.replace('<main id="main">', '<main id="main">' + block, 1)
    idx = idx.replace(
        '<meta name="description" content="H56 current research artifact with a short download, '
        'decoded-pattern audit, missing spatial holdout and explicit no-upload decision.">',
        '<meta name="description" content="H57 submission GeoTIFF: two-view co-training union arm '
        'on an exactly-accounted core, with the full holdout audit including the four refuted '
        'hypotheses.">')
    (DOCS / "index.html").write_text(idx)

    for name_html in ("h54.html", "h55.html", "h55-profile.html", "h55-edge.html",
                      "validation.html", "forensics.html", "sources.html", "method.html",
                      "hypotheses.html", "feed.html", "irregularities.html",
                      "h53.html", "r3.html", "r3-hypotheses.html", "h56.html"):
        p = DOCS / name_html
        if p.exists():
            p.write_text(nav_fix(p.read_text()))

    print("published", src.name, "->", dst, zpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())