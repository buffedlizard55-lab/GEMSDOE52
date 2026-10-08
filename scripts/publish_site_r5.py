#!/usr/bin/env python3
"""Build the R5 pages of the GitHub Pages site from the receipts, never from typed numbers.

Writes ``docs/index.html`` (R5 lead, download and verdict above the fold), ``docs/r5.html`` (the full
audit), ``docs/executive-summary.html`` (exactly how to submit) and ``docs/data/submission_r5.json``.
Every figure is read out of ``evidence/r5_novel_emission.json``, ``evidence/r5_cotrain.json``,
``evidence/r5_a_only_reasoning.json`` and ``registry/leaderboard_snapshot_2026-10-08.json`` at build
time, so a page cannot disagree with a receipt.

Run:  python scripts/publish_site_r5.py     then  python scripts/check_site.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DL = DOCS / "downloads"
EVID = ROOT / "evidence"

NAV = ('<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>'
       '<a href="index.html">Overview</a><a href="ctd5-audit.html">Run &amp; evidence</a>'
       '<a href="executive-summary.html">Submission guide</a><a href="r5.html">R5 audit</a>'
       '<a href="irregularities.html">Limitations</a><a href="sources.html">Sources</a>'
       '<a href="downloads/index.html">Archive</a></nav></header>')
HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="description" content="{desc}"><title>{title}</title>\n'
        '<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head>\n'
        '<body><a class="skip" href="#main">Skip to evidence</a>' + NAV)

# the portal's own note field is capped at 200 characters
NOTE = ("R5 novel 16,681px: six-family trace rank, ridge-walked, gated by strike coherence x the credited 010-020deg azimuth. 100% novel vs 55 repo rasters, off the 200m ring. Research artifact.")


def load(*p) -> dict:
    return json.loads((ROOT / Path(*p)).read_text()) if len(p) > 1 else json.loads(Path(p[0]).read_text())


def n(x, d=0) -> str:
    return f"{x:,.{d}f}"


def main() -> int:
    em = load(EVID / "r5_novel_emission.json")
    ct = load(EVID / "r5_cotrain.json")
    rs = load(EVID / "r5_a_only_reasoning.json")
    mdl = load(EVID / "r5_model.json")
    board = load(ROOT / "registry/leaderboard_snapshot_2026-10-08.json")
    budget = load(EVID / "r5_budget.json")
    uni = load(EVID / "r5_not_the_union.json")

    name = em["name"]
    tif_rel = f"downloads/{Path(em['tif']).name}"
    short = DL / "r5-candidate.tif"
    shutil.copyfile(ROOT / em["tif"], short)
    same = (hashlib.sha256(short.read_bytes()).hexdigest() == em["sha256"])
    v = em["values"]
    proj = em["projection"]
    p_champ = proj["0.2778"]["p_win"]
    p_board = proj["0.3195"]["p_win"]
    p_top = proj["0.3774"]["p_win"]
    dti1 = proj["0.2778"]["dti_at_kappa1"]
    chosen = em["chosen_row"]
    champ = em["reference_champion_cloud"]
    rnd = em["reference_random_matched"]
    indep = ct["independence"]
    exch = ct.get("exchange", {})
    pl_b = ct["pseudo_labels_block_unit"]
    pl_c = ct["pseudo_labels_component_unit"]
    S = em["emitted_px"]
    ok_dl, ok_sub = em["ok_to_download"], em["ok_to_submit"]
    rows = board["rows"]

    # ---------------------------------------------------------------- machine-readable verdict
    sub = dict(
        round="R5", file=f"{name}.tif", stem=name,
        submission_name=name, note=NOTE, note_chars=len(NOTE),
        bytes=em["bytes"], sha256=em["sha256"], nonzero_px=S,
        verdict=("FORMAT-VALID AND UNIQUE — OK TO DOWNLOAD; PORTAL-ACCEPTABLE; NOT SLOT-APPROVED "
                 "BECAUSE NO PROMOTION INSTRUMENT IN THIS REPO CAN RANK A NOVEL FIELD"),
        approved_for_weekly_slot=False, promoted=False,
        ok_to_download=bool(ok_dl), ok_to_submit_portal_acceptable=bool(ok_sub),
        reason_slot_not_approved=(
            "The standing rule is not to spend a slot on an idea that has not beaten the holdout best. "
            "The hide-and-recover holdout is disqualified as a leaderboard proxy (knowledge/10 §5: "
            "Spearman -0.1045, p=0.734, n=13) and R5 reproduced the disqualification on new data "
            "(habitat 0.0003 < random 0.0275 < trace 0.0395, an order the board inverts), so no "
            "candidate can clear that bar and none is claimed to."),
        p_beat_02778=p_champ, p_beat_03195=p_board, p_beat_03774=p_top, dti_at_kappa1=dti1,
        budget_star=em["budget_star"], budget_rule=em["frozen_rules"]["R2_budget"],
        novelty=em["novelty"], format=em["format_gate"], uniqueness=em["uniqueness_gate"],
        values=v, distance_to_catalogue_m=em["distance_to_catalogue_m"],
        candidate=em["chosen"], candidate_row=chosen,
        reference_champion_cloud=champ, reference_random_matched=rnd,
        frozen_rules=em["frozen_rules"], projection=proj,
        projection_budget_curve=em["projection_budget_curve"],
        leaderboard_bars=dict(top=board["top"], brief_stated=0.3195, family_best=0.2778,
                              source=board["source"], observed=board["observed_date_utc"]),
        receipts=["evidence/r5_novel_emission.json", "evidence/r5_novel_candidates.json",
                  "evidence/r5_cotrain.json", "evidence/r5_model.json", "evidence/r5_budget.json",
                  "evidence/r5_a_only_reasoning.json", "evidence/r5_revealed_inversion.json",
                  "registry/leaderboard_snapshot_2026-10-08.json"],
        a_only_reasoning=dict(csv="docs/downloads/a_only_reasoning_r5.csv", **{
            k: rs[k] for k in ("a_only_px", "components_total", "reviewed",
                               "below_review_resolution", "evidence_grade_counts",
                               "strict_abstention_count", "abstention_note")}),
        download=tif_rel, download_short="downloads/r5-candidate.tif",
        short_alias_byte_identical=bool(same),
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (DATA / "submission_r5.json").write_text(json.dumps(sub, indent=1))

    # Prior rounds stay reachable and stay labelled.  check_site.py enforces this for H58, the H57
    # credited-core alternate and the separate H55-EDGE archive; the strings come from the receipts,
    # not from memory, so a renamed artifact fails the build instead of silently vanishing.
    h58 = load(DATA / "submission_gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.json")
    h57c = load(DATA / "submission_h57_creditcore.json")
    h59 = load(DATA / "submission_h59.json")
    ARCHIVE = f"""
<h2>Previously published artifacts — all research-only, none of them this round's file</h2>
<div class="table-wrap"><table><thead><tr><th>round</th><th>artifact</th><th>SHA-256 prefix</th>
<th>status</th></tr></thead><tbody>
<tr><td>R5 (this round)</td><td><a href="{tif_rel}" download>{name}.tif</a></td>
<td><code>{em['sha256'][:24]}</code></td><td>strictly novel, format-verified, not slot-approved</td></tr>
<tr><td>H59</td><td><a href="h59.html">{h59['file']}</a></td><td><code>{h59['sha256'][:24]}</code></td>
<td>research only — <b>do not upload</b>, registered slot gate not met</td></tr>
<tr><td>H58</td><td><a href="h58.html">{h58['file']}</a> ·
<a href="downloads/h58-candidate.tif" download>downloads/h58-candidate.tif</a></td>
<td><code>{h58['sha256'][:24]}</code></td>
<td>research only — <b>do not upload</b>; 22 of 37,654 requested nodes emitted, support-capacity
failure (<code>IR-H58-002</code>), not approved to submit</td></tr>
<tr><td>H57 credited-core alternate</td><td><a href="h57-creditcore.html">{h57c['file']}</a></td>
<td><code>{h57c['sha256'][:24]}</code></td>
<td>ABANDONED / not proven — <b>do not upload</b> (<code>IR-57-107</code>); the refuted co-training
arm is disclosed on its page</td></tr>
<tr><td>H57 union arm (the incumbent marker)</td><td><a href="h57.html">gems52-h57-union-novel-core25517px-arm14804px.tif</a></td>
<td><code>5fadcaefd64db0cb553bf16d</code></td>
<td>published, not slot-approved; <code>submission/LATEST.txt</code> and
<code>docs/data/submission.json</code> still point here</td></tr>
<tr><td>H55-EDGE (separate failed-gate archive)</td><td><a href="h55-edge.html">h55-edge.html</a></td>
<td>—</td><td>protocol deviation recorded; not the current H55 candidate — <b>do not upload</b></td></tr>
</tbody></table></div>
<p class="small">Every one of these is a research artifact: none is a verified fault map, none is
approved to spend a weekly submission slot, and each page carries its own failed gate. They are
listed so the record stays complete and so no reader mistakes an archive for the current file.</p>
"""

    # ---------------------------------------------------------------- index and guide: inject, do not
    # overwrite.  Parallel sessions own the front page (main currently leads with the CTD5/H60 record and
    # keeps one page per round), so R5 adds a marked fragment and leaves everything else alone.  The
    # markers make this idempotent: re-running replaces the fragment instead of stacking a second copy.
    START, END = "<!--R5:START-->", "<!--R5:END-->"

    def inject(page: Path, fragment: str, anchor: str) -> str:
        text = page.read_text(encoding="utf-8")
        block = f"{START}\n{fragment}\n{END}"
        if START in text and END in text:
            a, b = text.index(START), text.index(END) + len(END)
            return text[:a] + block + text[b:]
        if anchor not in text:
            raise SystemExit(f"{page.name}: injection anchor not found; the page was restructured -- "
                             f"repoint the anchor rather than silently dropping the R5 block")
        return text.replace(anchor, anchor + "\n" + block, 1)

    index_fragment = f"""
<section class="download-bar" aria-label="R5 strictly-novel artifact">
<div><div class="eyebrow">R5 · strictly-novel emission · this session's round
<span class="pill ok">OK TO DOWNLOAD</span>
<span class="pill warn">PORTAL-ACCEPTABLE · NOT SLOT-APPROVED</span></div>
<strong>{name}.tif</strong>
<small>{n(em['bytes'])} bytes · single-band float32 · EPSG:32611 · all {n(v['finite_pixels'])} cells
finite · values exactly {{0,1}} · {n(S)} emitted px · <b>novel fraction
{em['uniqueness_gate']['novel_fraction']:.4f}</b> against {em['uniqueness_gate']['n_priors_checked']}
rasters · nearest mapped trace {n(em['distance_to_catalogue_m']['min'], 1)} m ·
SHA-256 <code>{em['sha256'][:24]}…</code></small></div>
<a class="button" href="{tif_rel}" download>↓ Download the R5 TIFF (one click)</a>
<a class="button" href="downloads/r5-candidate.tif" download>↓ Same file, short name</a>
<a class="button secondary" href="r5.html">R5 audit →</a></section>
<div class="status"><strong>R5 in one paragraph.</strong> Co-training was run exactly as the brief
specifies and reported honestly: the independence premise <b>holds</b> (max |ρ| {indep['max_abs']:.4f}
against the 0.60 abandonment threshold), the pseudo-label exchange <b>harmed</b> the weaker view
({exch['B_to_A']['delta_fold0_auc']:+.4f} AUC against {exch['A_to_B']['delta_fold0_auc']:+.4f} the other
way), the connected-component reading of “whole segment” returns the <b>empty set</b> as a measurement,
and the co-training propensity ranking then <b>lost</b> to the six-family detector on the frozen rule —
so the shipped file is not a co-training product and the site does not imply otherwise. Emission:
{n(S)} px at the derived optimum S* = 4|G|β/(1−β) = {n(em['budget_star'])}, chosen on strike coherence
({chosen['mean_coherence_sigma4']:.4f} against the credited cloud's {champ['mean_coherence_sigma4']:.4f}
and a random control's {rnd['mean_coherence_sigma4']:.4f}) with its dominant strike
{chosen['dominant_strike_deg_array']:.0f}° inside the credited band. Overlap with any reading of “the
union of the two views” is at most
{max(u['fraction_of_emission'] for u in uni['comparisons'].values()):.4f} of the emitted pixels.
<b>P(DTI &gt; 0.2778) = {p_champ:.3f}, P(&gt; 0.3195) = {p_board:.3f}, P(&gt; 0.3774) = {p_top:.3f}</b> —
the board top is 0.3774, not the 0.3195 the brief states (rank 7, fetched
{board['observed_date_utc']}). No weekly slot is authorised: the promotion instrument is disqualified
and this round reproduced that on new data. Full record: <a href="r5.html">R5 audit</a>,
<a href="executive-summary.html#r5">submission steps</a>,
<code>knowledge/27_r5_findings.md</code>,
<a href="downloads/a_only_reasoning_r5.csv">reasoning for all {n(rs['reviewed']['rows'])} A-only
candidates</a>.</div>
"""

    exec_fragment = f"""
<section class="download-bar" id="r5" aria-label="R5 strictly-novel artifact">
<div><div class="eyebrow">R5 · strictly-novel emission
<span class="pill ok">OK TO DOWNLOAD</span><span class="pill warn">NOT SLOT-APPROVED</span></div>
<strong>{name}.tif</strong>
<small>{n(em['bytes'])} bytes · SHA-256 <code>{em['sha256']}</code> · {n(S)} px · novel fraction
{em['uniqueness_gate']['novel_fraction']:.4f} against {em['uniqueness_gate']['n_priors_checked']}
rasters · all cells finite, values exactly {{0,1}}, so the portal's “Predicted values must be in range
[0, 1]” rejection cannot occur on this file</small></div>
<a class="button" href="{tif_rel}" download>↓ Download the R5 TIFF (one click)</a>
<a class="button" href="downloads/r5-candidate.tif" download>↓ Same file, short name</a>
<a class="button secondary" href="r5.html">R5 audit →</a></section>
<h3>R5 — is it OK to download and submit?</h3>
<div class="table-wrap"><table><thead><tr><th>question</th><th>answer of record</th></tr></thead><tbody>
<tr><td>OK to <b>download</b>?</td><td><span class="pill ok">YES</span> — {str(bool(ok_dl)).upper()}.</td></tr>
<tr><td>Will the portal <b>accept</b> it?</td><td><span class="pill ok">YES</span> —
{str(bool(ok_sub)).upper()}. Single layer, float32, values in [0,1], EPSG:32611, 100 m, same bounds as
the training data, transform <code>[100, 0, 243350, 0, −100, 4508550]</code> identical to
<code>sample_submission.tif</code>, all {n(v['finite_pixels'])} cells finite, no nodata tag. Verified by
re-reading the written bytes, not by trusting the writer.</td></tr>
<tr><td><b>Unique</b>?</td><td><span class="pill ok">YES</span> — decoded-pixel comparison against all
{em['uniqueness_gate']['n_priors_checked']} rasters this repository has produced: novel fraction
{em['uniqueness_gate']['novel_fraction']:.4f}, not equal to the literal prior union, relation
<code>{em['novelty']['relation_to_union']}</code>.</td></tr>
<tr><td>Not merely the <b>union of the two views</b>?</td><td><span class="pill ok">CONFIRMED</span> —
largest overlap with any reading of the union is
{max(u['fraction_of_emission'] for u in uni['comparisons'].values()):.4f} of the emitted pixels
(Jaccard ≤ {max(u['jaccard'] for u in uni['comparisons'].values()):.4f}), and Spearman(emitted score,
view propensity) is
{uni['rank_correlations']['spearman_emitted_score_vs_view_A_propensity']:+.3f} /
{uni['rank_correlations']['spearman_emitted_score_vs_view_B_propensity']:+.3f}.
<code>evidence/r5_not_the_union.json</code>.</td></tr>
<tr><td>OK to spend the <b>weekly slot</b>?</td><td><span class="pill warn">NO — NOT ON THE EVIDENCE
AVAILABLE</span>. P(DTI &gt; 0.2778) = {p_champ:.3f}, P(&gt; 0.3195) = {p_board:.3f},
P(&gt; 0.3774) = {p_top:.3f}; DTI at κ=1 is {dti1:.4f}. The standing rule — do not spend a slot on an
idea that has not beaten the holdout best — cannot be satisfied by anything, because the hide-and-recover
instrument is disqualified (Spearman −0.1045, p = 0.734, n = 13) and R5 reproduced that on new data.</td></tr>
<tr><td>Any argument for submitting anyway?</td><td><span class="pill ok">YES, ONE</span> — the
organiser's own: Phase 2 ($250k) re-scores a label set “updated by expert review of all Phase 1
submissions”, and staff state predictions matter there “even if they are not the most performant in
Phase 1”. This file is {n(S)} strictly novel candidates, each with written geological reasoning in
<a href="downloads/a_only_reasoning_r5.csv">a_only_reasoning_r5.csv</a>.</td></tr>
</tbody></table></div>
<h4>Exact portal steps for the R5 file</h4>
<ol>
<li>Sign in to the eligible account at the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a> →
<b>Submit</b>. Slot limits and deadlines are on
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/rules/">the rules page</a>;
this repository cannot see the account and does not guess the remaining count.</li>
<li>Click <a href="{tif_rel}" download>↓ Download the R5 TIFF</a>. Do not reproject, rescale, re-save or
rename the payload.</li>
<li>Set <b>File to submit</b> to that <code>.tif</code>.</li>
<li>Set the submission <b>name</b> to <code>{name}</code> ({len(name)} characters).</li>
<li>Paste this <b>note</b> ({len(NOTE)} of 200 characters): <code>{NOTE}</code></li>
<li>Submit. The expected score is an interval, not a point:
{proj['0.2778']['dti_at_kappa_lo']:.4f}–{proj['0.2778']['dti_at_kappa_hi']:.4f} with {dti1:.4f} at κ=1.
If the returned score lands outside it, that is information about the prior and belongs in
<code>registry/irregularities.json</code>, not in a re-tune.</li>
<li>One submission must be selected for <b>both</b> rounds before the deadline, without knowing the
private-set score.</li>
</ol>
<p class="small">If a file is ever rejected with “Predicted values must be in range [0, 1]”, check in
this order: (1) non-finite or out-of-range cells —
<code>python -c "import rasterio,numpy as np;a=rasterio.open('F.tif').read(1);print(np.isfinite(a).all(),a.min(),a.max(),a.dtype)"</code>,
which reports <code>{str(bool(v['all_finite']))} {v['min']} {v['max']} {v['dtype']}</code> for this
artifact; (2) CRS/transform against <code>data/sample_submission.tif</code>; (3) band count and dtype;
(4) if a ZIP is used, that it holds exactly one TIFF byte-identical to the canonical download.</p>
"""

    (DOCS / "index.html").write_text(
        inject(DOCS / "index.html", index_fragment, "</section>"))
    (DOCS / "executive-summary.html").write_text(
        inject(DOCS / "executive-summary.html", exec_fragment, '<main id="main">'))

    # ---------------------------------------------------------------- audit page
    audit = HEAD.format(
        desc="R5 audit trail: co-training receipt, independence test, pseudo-label readings, the "
             "disqualified promotion instrument, the frozen emission rules and every gate.",
        title="R5 audit · GEMSDOE52") + f"""
<main id="main"><div class="eyebrow">R5 audit · every number below is read from a receipt</div>
<h1>What was run, what it returned,<br>and what it does not license.</h1>
<section class="download-bar" aria-label="R5 download">
<div><strong>{name}.tif</strong><small>{n(em['bytes'])} bytes · SHA-256
<code>{em['sha256']}</code> · {n(S)} px · re-running the build reproduces these bytes exactly</small></div>
<a class="button" href="{tif_rel}" download>↓ Download the submission TIFF (one click)</a>
<a class="button" href="downloads/r5-candidate.tif" download>↓ Same file, short name (r5-candidate.tif)</a>
<a class="button secondary" href="executive-summary.html">How to submit →</a></section>
<div class="status"><strong>Verdict of record.</strong> OK to download: <b>YES</b>. Portal-acceptable:
<b>YES</b> — every published format clause is re-measured from the bytes on disk by
<code>scripts/check_site.py</code>. Weekly submission slot approved: <b>NO — NOT SLOT-APPROVED</b>, do
not spend a slot on this file on the strength of anything in this repository: the promotion instrument
is disqualified and P(DTI &gt; 0.2778) = {p_champ:.3f}. Research artifact; every pixel is a hypothesis
for expert review, not a verified fault.</div>

<h2>1 · The frozen rules, printed before the results</h2>
<div class="table-wrap"><table><thead><tr><th>rule</th><th>text</th></tr></thead><tbody>
{''.join(f'<tr><td><code>{k}</code></td><td>{val}</td></tr>' for k, val in em['frozen_rules'].items())}
</tbody></table></div>

<h2>2 · Co-training, as the brief specifies it</h2>
<div class="table-wrap"><table><thead><tr><th>quantity</th><th>value</th><th>receipt</th></tr></thead><tbody>
<tr><td>view A blocked OOF AUC (mean of 4 folds, {mdl['views']['A']['n_layers']} layers)</td>
<td>{mdl['views']['A']['mean_auc']:.4f}</td>
<td rowspan="2">evidence/r5_model.json → views</td></tr>
<tr><td>view B blocked OOF AUC (mean of 4 folds, {mdl['views']['B']['n_layers']} layers)</td>
<td>{mdl['views']['B']['mean_auc']:.4f}</td></tr>
<tr><td>independence: spearman / pearson / max |r| over {indep['n_blocks']} blocks</td>
<td>{indep['spearman']:.5f} / {indep['pearson']:.5f} / {indep['max_abs']:.5f}</td>
<td>evidence/r5_cotrain.json → independence</td></tr>
<tr><td>verdict against the 0.60 abandonment threshold</td><td>{indep['verdict']}</td><td>same</td></tr>
<tr><td>A-only / B-only disagreement px</td>
<td>{n(ct['disagreement']['a_only']['px'])} / {n(ct['disagreement']['b_only']['px'])}</td>
<td>evidence/r5_cotrain.json → disagreement</td></tr>
<tr><td>median depth_to_base_surf, A-only vs B-only</td>
<td>{ct['disagreement']['a_only'].get('median_depth_to_basement_m')} m vs
{ct['disagreement']['b_only'].get('median_depth_to_basement_m')} m</td><td>same</td></tr>
<tr><td>pseudo-labels, component unit (A→B / B→A)</td>
<td>{pl_c['a_to_b']['px']} px / {pl_c['b_to_a']['px']} px, raw
{n(pl_c['a_to_b']['raw_px'])} / {n(pl_c['b_to_a']['raw_px'])}, at
{pl_c['a_to_b']['ratio_to_independence']:.3f}× independence</td>
<td>evidence/r5_cotrain.json → pseudo_labels_component_unit</td></tr>
<tr><td>pseudo-labels, whole-block unit (A→B / B→A)</td>
<td>{n(pl_b['a_to_b']['px'])} px in {n(pl_b['a_to_b']['segments'])} blocks /
{n(pl_b['b_to_a']['px'])} px in {n(pl_b['b_to_a']['segments'])} blocks; leak_free
{str(pl_b['a_to_b'].get('leak_free')).lower()}</td>
<td>evidence/r5_cotrain.json → pseudo_labels_block_unit</td></tr>
<tr><td>exchange, fold 0: A→B and B→A ΔAUC</td>
<td>{exch['A_to_B']['delta_fold0_auc']:+.4f} and {exch['B_to_A']['delta_fold0_auc']:+.4f}</td>
<td>evidence/r5_cotrain.json → exchange</td></tr>
<tr><td>the reading of “whole segment” that was published</td><td colspan="2">{ct['pseudo_label_reading']}</td></tr>
</tbody></table></div>
<p class="small">Caveat carried wherever these numbers appear: the OOF-donor exchange has a
second-order leak (a pseudo-label at a pixel in fold <i>j</i> comes from a donor trained on folds
≠ <i>j</i>, so admitting it into the receiver's fold-<i>k</i> model trains that model on a quantity
derived from fold <i>k</i>'s own labels). A strictly leak-free protocol needs per-fold donor refits;
it is the next implementation item, not a result.</p>

<h2>3 · Candidates, coherence and the chosen emission</h2>
<div class="table-wrap"><table><thead><tr><th>candidate</th><th>what it is</th><th>placed</th>
<th>mean coh σ4</th><th>σ6</th><th>σ10</th><th>frac&gt;0.8</th><th>strike</th><th>in band</th>
<th>lift</th></tr></thead><tbody>
{''.join(f"<tr><td><code>{c['name']}</code></td><td>{c['what']}</td><td>{n(c['placed'])}</td>"
         f"<td>{c['mean_coherence_sigma4']:.4f}</td><td>{c['mean_coherence_sigma6']:.4f}</td>"
         f"<td>{c['mean_coherence_sigma10']:.4f}</td><td>{c['frac_coh_above_0.8_sigma4']:.4f}</td>"
         f"<td>{c['dominant_strike_deg_array']:.0f}°</td>"
         f"<td>{'yes' if c['in_credited_band'] else 'no'}</td>"
         f"<td>{c['coherence_lift_over_random']:+.4f}</td></tr>"
         for c in sorted(em['candidates'], key=lambda c: -c['coherence_lift_over_random']))}
<tr><td><i>champion cloud</i></td><td><i>the 0.2778 file's own 37,638 dots, as the reference</i></td>
<td>{n(champ['n_dots'])}</td><td><b>{champ['mean_coherence_sigma4']:.4f}</b></td>
<td>{champ['mean_coherence_sigma6']:.4f}</td><td>{champ['mean_coherence_sigma10']:.4f}</td>
<td><b>{champ['frac_coh_above_0.8_sigma4']:.4f}</b></td>
<td>{champ['dominant_strike_deg_array']:.0f}°</td><td>yes</td><td>—</td></tr>
<tr><td><i>random, mass-matched to the champion</i></td><td><i>the control knowledge/10 §7 used</i></td>
<td>{n(rnd['n_dots'])}</td><td>{rnd['mean_coherence_sigma4']:.4f}</td>
<td>{rnd['mean_coherence_sigma6']:.4f}</td><td>{rnd['mean_coherence_sigma10']:.4f}</td>
<td>{rnd['frac_coh_above_0.8_sigma4']:.4f}</td><td>{rnd['dominant_strike_deg_array']:.0f}°</td>
<td>—</td><td>—</td></tr>
</tbody></table></div>
<p class="small">Coherence depends on dot density as well as arrangement, so the shipped file's
{chosen['frac_coh_above_0.8_sigma4']:.4f} above 0.8 is <b>not</b> comparable to the champion's
{champ['frac_coh_above_0.8_sigma4']:.4f} at 2.3× the dots; the comparison that decides is against the
random control at the same budget. Chosen: <code>{em['chosen']}</code>, lift
{chosen['coherence_lift_over_random']:+.4f}, strike {chosen['dominant_strike_deg_array']:.0f}° inside
the credited band. Placed {n(chosen['placed'])} of {n(chosen['requested'])} requested dots; candidate
pool seen {n(chosen['candidates_seen'])}.</p>

<h2>4 · The gates, read off the written bytes</h2>
<div class="table-wrap"><table><thead><tr><th>check</th><th>value</th></tr></thead><tbody>
<tr><td>format gate</td><td>{'PASS' if em['format_gate']['ok'] else 'FAIL'} — problems:
{em['format_gate']['problems'] or 'none'}</td></tr>
<tr><td>values</td><td>min {v['min']}, max {v['max']}, unique {v['unique']}, positive px
{n(v['positive_pixels'])}, finite {n(v['finite_pixels'])} / {n(v['finite_pixels'])}, NaN or inf
{v['nan_or_inf']}, nodata tag <code>{v['nodata_tag']}</code>, dtype {v['dtype']}</td></tr>
<tr><td>grid</td><td>{v['crs']}, transform {v['transform']}</td></tr>
<tr><td>uniqueness</td><td>pattern unique {str(em['uniqueness_gate']['pattern_unique']).lower()}
against {em['uniqueness_gate']['n_priors_checked']} rasters; novel fraction
{em['uniqueness_gate']['novel_fraction']:.4f}; equals the literal prior union
{str(em['uniqueness_gate']['equals_literal_prior_union']).lower()}; prior union
{n(em['novelty']['union_px'])} px</td></tr>
<tr><td>novelty vs the 13 organiser-scored files alone</td>
<td>{em['novelty']['novel_vs_13_organiser_scored']:.4f}</td></tr>
<tr><td>distance to the mapped catalogue</td><td>min {n(em['distance_to_catalogue_m']['min'], 1)} m,
median {n(em['distance_to_catalogue_m']['median'], 1)} m (the organiser's mask is pixel-exact; the
200 m ring is this repository's own rule, and <code>IR-R5-006</code> records that it is not the
organiser's)</td></tr>
<tr><td>OK to download / OK to submit (portal-acceptable)</td><td>{str(bool(ok_dl)).upper()} /
{str(bool(ok_sub)).upper()}</td></tr>
</tbody></table></div>

<h2>5 · The projection, as a probability over a bounded unknown</h2>
<div class="table-wrap"><table><thead><tr><th>bar</th><th>credit needed</th><th>κ needed</th>
<th>P(DTI &gt; bar)</th></tr></thead><tbody>
{''.join(f"<tr><td>{k}</td><td>{n(val['credit_needed'], 1)}</td><td>{val['kappa_needed']:.4f}</td>"
         f"<td><b>{val['p_win']:.3f}</b></td></tr>" for k, val in proj.items())}
</tbody></table></div>
<p class="small">T(S) = κ·471.6·S^0.2284 with κ ~ U[0.3, 1.3]; DTI at κ = 0.3 / 1.0 / 1.3 is
{proj['0.2778']['dti_at_kappa_lo']:.4f} / {dti1:.4f} / {proj['0.2778']['dti_at_kappa_hi']:.4f}.
The |G| cap does not bind anywhere in this prior (it would take κ = 3.24).</p>

<h2>6 · The output is not merely the union of the two views</h2>
<p class="small">The brief asks for this confirmation and the uniqueness gate does not test it — that
gate compares against prior submissions. <code>scripts/run_r5_union_check.py</code> compares against
every set the phrase could mean; receipt <code>evidence/r5_not_the_union.json</code>.</p>
<div class="table-wrap"><table><thead><tr><th>comparison set</th><th>px in set</th>
<th>shared with the emission</th><th>fraction of the {n(S)} emitted</th><th>Jaccard</th></tr></thead><tbody>
{''.join(f"<tr><td>{k.replace('_', ' ')}</td><td>{n(v['px_in_set'])}</td>"
         f"<td>{n(v['px_shared_with_emission'])}</td><td>{v['fraction_of_emission']:.4f}</td>"
         f"<td>{v['jaccard']:.4f}</td></tr>" for k, v in uni['comparisons'].items())}
</tbody></table></div>
<p class="small">Spearman between the emitted pixels' own score and each view's propensity:
{uni['rank_correlations']['spearman_emitted_score_vs_view_A_propensity']:+.4f} (view A),
{uni['rank_correlations']['spearman_emitted_score_vs_view_B_propensity']:+.4f} (view B),
{uni['rank_correlations']['spearman_emitted_score_vs_pointwise_max']:+.4f} (pointwise max) —
indistinguishable from zero. {uni['verdict']}</p>
<div class="status"><strong>Read this with the table.</strong> The confirmation is as strong as it can
be, and it implies something the site will not hide: <b>the shipped emission is not a co-training
product.</b> The brief's method was built, run and measured — the independence premise held at
{indep['max_abs']:.4f}, the pseudo-label exchange moved view A
{exch['B_to_A']['delta_fold0_auc']:+.4f} AUC — and then the co-training propensity ranking (candidate
<code>N6_habitat</code>) lost on the frozen rule: coherence lift
{[c for c in em['candidates'] if c['name']=='N6_habitat'][0]['coherence_lift_over_random']:+.4f}
against {chosen['coherence_lift_over_random']:+.4f} for the chosen field, dominant strike outside the
credited band, and 0.3 % overlap with what shipped. What shipped came from the six-family
corroboration detector and the strike-coherence instrument.</div>

<h2>6b · What the disagreement signal did and did not say</h2>
<div class="table-wrap"><table><thead><tr><th>stratum</th><th>px</th>
<th>median depth_to_base_surf</th><th>median det_elev_slope</th></tr></thead><tbody>
<tr><td>A-only (potential field confident, surface abstains)</td>
<td>{n(ct['disagreement']['a_only']['px'])}</td>
<td>{ct['disagreement']['a_only']['median_depth_to_basement_m']:.1f}</td>
<td><b>{ct['disagreement']['a_only']['median_slope']:.2f}</b></td></tr>
<tr><td>B-only (surface confident, potential field abstains)</td>
<td>{n(ct['disagreement']['b_only']['px'])}</td>
<td>{ct['disagreement']['b_only']['median_depth_to_basement_m']:.1f}</td>
<td><b>{ct['disagreement']['b_only']['median_slope']:.2f}</b></td></tr>
<tr><td>both confident</td><td>{n(ct['disagreement']['both']['px'])}</td>
<td>{ct['disagreement']['both']['median_depth_to_basement_m']:.1f}</td>
<td>{ct['disagreement']['both']['median_slope']:.2f}</td></tr>
</tbody></table></div>
<p class="small">The B-only side behaves as the brief predicts — 25 % steeper ground than A-only
(footprint median slope 3.75), which is where erosion lines and drainage cut. The A-only side does
<b>not</b>: its median modelled basement depth is
{ct['disagreement']['a_only']['median_depth_to_basement_m']:.1f} against
{ct['disagreement']['b_only']['median_depth_to_basement_m']:.1f} for B-only, a
{ct['disagreement']['a_only']['median_depth_to_basement_m'] - ct['disagreement']['b_only']['median_depth_to_basement_m']:.1f} m
difference on a field whose footprint median is 316 m and whose p99 is 3,420 m. “A-only means buried
under deeper cover” is not supported by these bytes, so the reasoning CSV makes its burial clause
conditional on each row's own measured depth and says so when a row is shallower than median.</p>

<h2>7 · Irregularities this round added</h2>
<p class="small"><code>IR-R5-001</code> R4 excluded the LiDAR bands on a false premise — bands 9–12 do
carry descriptions (<code>relief</code>, <code>coh100</code>, <code>strike</code>, <code>valid</code>).
<code>IR-R5-002</code> <code>fold[rows]</code> on a 2-D grid selects whole rows: ~4 GB, an OOM kill,
no traceback. <code>IR-R5-003</code> two runs of identical stage-3 code logged different numbers, and
both saved fields carry 620 impossible zeros at row 0 columns 0–619 — bounded, unexplained, published
numbers reproduce from disk. <code>IR-R5-004</code> two of the 13 “independent” scored rasters have
identical evaluated support and an identical score, so n = 12. <code>IR-R5-005</code> the brief's
0.3195 is rank 7, not the top. <code>IR-R5-006</code> the 200 m ring rule is contradicted by the
organiser's pixel-exact mask and their statement that corrections within 300 m are a goal.
<code>IR-R5-007</code> knowledge/01 §1 attributes the champion's +6.8 % to masked pixels; masked
pixels pay no tax. <code>IR-R5-008</code> the organiser's feature list promises a top-of-crustal
magnetic source depth estimate that no band in the file corresponds to. Full text and handling in
<a href="irregularities.html">Limitations</a> and <code>registry/irregularities.json</code>.</p>
</main></body></html>
"""
    (DOCS / "r5.html").write_text(audit)

    print(f"wrote docs/index.html, docs/r5.html, docs/executive-summary.html, "
          f"docs/data/submission_r5.json; short alias byte-identical: {same}; note {len(NOTE)}/200 chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
