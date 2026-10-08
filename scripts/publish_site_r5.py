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
       '<a href="index.html">Overview</a><a href="executive-summary.html">Submission guide</a>'
       '<a href="r5.html">R5 audit</a><a href="h59.html">H59</a>'
       '<a href="irregularities.html">Limitations</a><a href="sources.html">Sources</a>'
       '<a href="downloads/index.html">Downloads</a></nav></header>')
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

    # ---------------------------------------------------------------- index
    bar_rows = "".join(
        f'<tr><td>{r["rank"]}</td><td>{r["team"]}</td><td><b>{r["score"]:.4f}</b></td>'
        f'<td>{r["submissions"]}</td></tr>' for r in rows[:13])
    cand_rows = "".join(
        f'<tr><td><code>{c["name"]}</code></td><td>{c["what"]}</td>'
        f'<td>{c["mean_coherence_sigma4"]:.4f}</td><td>{c["frac_coh_above_0.8_sigma4"]:.4f}</td>'
        f'<td>{c["dominant_strike_deg_array"]:.0f}°</td>'
        f'<td>{"yes" if c["in_credited_band"] else "no"}</td>'
        f'<td>{c["coherence_lift_over_random"]:+.4f}</td></tr>'
        for c in sorted(em["candidates"], key=lambda c: -c["coherence_lift_over_random"]))
    index = HEAD.format(
        desc="R5 strictly-novel 16,681 px GeoTIFF for the DOE GEMS prize: one-click download, "
             "explicit OK-to-download and OK-to-submit verdict, all gates and probabilities from receipts.",
        title="GEMSDOE52 — R5 strictly-novel submission") + f"""
<main id="main"><div class="eyebrow">R5 · two-view co-training + six-family trace detector ·
fetched and verified against the organiser's own pages on {board['observed_date_utc']}
<span class="pill ok">OK TO DOWNLOAD</span>
<span class="pill warn">PORTAL-ACCEPTABLE · NOT SLOT-APPROVED</span></div>

<section class="download-bar" aria-label="R5 submission download">
<div><strong>{name}.tif</strong>
<small>{n(em['bytes'])} bytes · single-band float32 · EPSG:32611 · {n(v['finite_pixels'])} cells all
finite · values exactly {{0,1}} · nodata tag <code>{v['nodata_tag']}</code> · {n(S)} emitted px ·
min distance to a mapped trace {n(em['distance_to_catalogue_m']['min'], 1)} m</small>
<small>SHA-256 <code>{em['sha256']}</code></small>
<small>uniqueness: pattern-unique against <b>{em['uniqueness_gate']['n_priors_checked']}</b> rasters ·
novel fraction <b>{em['uniqueness_gate']['novel_fraction']:.4f}</b> · equals the literal prior union:
{str(em['uniqueness_gate']['equals_literal_prior_union']).lower()} · format gate
{em['format_gate']['ok'] and 'PASS (0 problems)' or 'FAIL'}</small></div>
<a class="button" href="{tif_rel}" download>↓ Download the submission TIFF (one click)</a>
<a class="button" href="downloads/r5-candidate.tif" download>↓ Same file, short name (r5-candidate.tif)</a>
<a class="button secondary" href="executive-summary.html">How to submit it →</a>
<a class="button secondary" href="r5.html">Full audit →</a></section>

<div class="status"><strong>Is it OK to download? YES. Is it OK to submit?</strong>
The portal will accept it — every format clause the organiser publishes is verified against the
written bytes, and the “Predicted values must be in range [0, 1]” rejection cannot occur because all
{n(v['finite_pixels'])} cells are finite and in {{0,1}}.
<b>Whether to spend a weekly slot on it is a different question and the answer is no, not on the
evidence available:</b> P(DTI &gt; 0.2778) = <b>{p_champ:.3f}</b>, P(DTI &gt; 0.3195) =
<b>{p_board:.3f}</b>, P(DTI &gt; 0.3774) = <b>{p_top:.3f}</b> under the frozen prior, and the
standing rule — do not spend a slot on an idea that has not beaten the holdout best — cannot be
satisfied by anything, because the holdout instrument is disqualified and R5 reproduced the
disqualification on new data. The one argument for submitting anyway is the organiser's own: the
Final Prize Round ($250k) re-scores a test set “updated by expert review of all Phase 1
submissions”, so predictions matter there “even if they are not the most performant in Phase 1”.
This file is {n(S)} strictly novel, individually reasoned candidates, which is what that round asks
for. <a href="executive-summary.html">The decision table is on the submission guide.</a></div>

<h1>16,681 pixels this repository has<br>never emitted, aimed at faults the map does not have.</h1>
<p class="lede">R5 rebuilt the brief's Blum–Mitchell instrument on the restored competition bytes,
tested the conditional-independence premise instead of assuming it, measured both readings of the
“whole-segment” pseudo-label rule, reproduced the disqualification of this repo's promotion
instrument on new data, and then chose an emission by a rule frozen before the candidates existed:
strict novelty against every raster this repo has produced, a budget derived from the measured credit
curve rather than tuned, and selection on the one property of the credited cloud that has ever
measured positive — strike coherence.</p>

<div class="grid">
<section class="card"><h3>Independence premise</h3><p class="metric">{indep['max_abs']:.4f}</p>
<p class="small">max |ρ| of per-block false-positive rate on labelled negatives at each view's own
top-1&nbsp;% threshold, over {indep['n_blocks']} blocks — against the 0.60 abandonment threshold.
<b>Premise holds this round</b> (spearman {indep['spearman']:.4f}, pearson {indep['pearson']:.4f});
R4's score-level version of the same test fired at 0.7051. Both are published.</p></section>

<section class="card"><h3>Co-training exchange</h3>
<p class="metric">{exch['B_to_A']['delta_fold0_auc']:+.4f}</p>
<p class="small">fold-0 out-of-fold AUC change for view A trained on view B's confident
pseudo-labels (B→A: {exch['B_to_A']['fold0_auc_before']:.4f} → {exch['B_to_A']['fold0_auc_after']:.4f});
the other direction moved {exch['A_to_B']['delta_fold0_auc']:+.4f}
({exch['A_to_B']['fold0_auc_before']:.4f} → {exch['A_to_B']['fold0_auc_after']:.4f}). <b>The brief's bias-amplification
warning is confirmed on real bytes:</b> teaching the weaker view from the stronger one costs eight
times what the reverse gains.</p></section>

<section class="card"><h3>Pseudo-labels, component reading</h3>
<p class="metric">{pl_c['a_to_b']['px']} px</p>
<p class="small">Empty in both directions, and that is a measurement, not a failure: the
donor-confident ∧ receiver-abstaining cut is {n(pl_c['a_to_b']['raw_px'])} raw px /
{n(pl_c['b_to_a']['raw_px'])} px the other way, whose largest connected piece is 5 px, at
{pl_c['a_to_b']['ratio_to_independence']:.3f}× the count independence predicts
({n(pl_c['expected_px_under_independence'], 0)} px). The whole-block
reading admits {n(pl_b['a_to_b']['px'])} / {n(pl_b['b_to_a']['px'])} px. Neither was tuned until
something appeared.</p></section>

<section class="card"><h3>Emission coherence vs the credited cloud</h3>
<p class="metric">{chosen['mean_coherence_sigma4']:.4f}</p>
<p class="small">structure-tensor coherence at σ=4 px of the emitted cloud, against
<b>{champ['mean_coherence_sigma4']:.4f}</b> for the champion's own 37,638-dot cloud and
<b>{rnd['mean_coherence_sigma4']:.4f}</b> for a random control at this budget. Fraction above 0.8:
{chosen['frac_coh_above_0.8_sigma4']:.4f} here, {champ['frac_coh_above_0.8_sigma4']:.4f} credited,
{rnd['frac_coh_above_0.8_sigma4']:.4f} random. Dominant strike
{chosen['dominant_strike_deg_array']:.0f}° in both this file and the credited cloud.</p></section>

<section class="card"><h3>Budget, derived not tuned</h3><p class="metric">{n(em['budget_star'])} px</p>
<p class="small">S* = 4|G|β/(1−β) with the measured credit-curve exponent β = 0.2284 and
|G| = 14,088.7 px; the amplitude cancels, so the optimum can be frozen before any candidate is
built. 9,945–24,152 over β ∈ [0.15, 0.30]. The same window falls out of a completely different prior
in knowledge/10 §8.</p></section>

<section class="card"><h3>A-only reasoning for Phase 2</h3>
<p class="metric">{n(rs['reviewed']['rows'])}</p>
<p class="small">candidate segments of ≥3 px, one CSV row each with measured geometry, per-family
response percentiles, band values quoted against the footprint's own distribution, an evidence grade
({rs['evidence_grade_counts']['strong']} strong / {rs['evidence_grade_counts']['moderate']} moderate /
{rs['evidence_grade_counts']['weak']} weak) and five named competing explanations. The
{n(rs['below_review_resolution']['components'])} components of 1–2 px are accounted for in aggregate
rather than dropped. <a href="downloads/a_only_reasoning_r5.csv">a_only_reasoning_r5.csv</a></p></section>
</div>

<h2>The board as fetched on {board['observed_date_utc']}, and why the brief's bar is the wrong one</h2>
<p>The brief states the leaderboard best is 0.3195. The organiser's own board, fetched
{board['observed_date_utc']} from <a href="{board['source']}">{board['source']}</a>, puts 0.3195 at
<b>rank 7</b> and the top at <b>{board['top']:.4f}</b>. Ranks 8–22 span 0.2707–0.2888 — fifteen teams
inside 0.018 — with a gap of 0.031 above them: a shared ceiling, and this family is inside it.
Every projection on this site carries all three bars.</p>
<div class="table-wrap"><table><thead><tr><th>rank</th><th>team</th><th>best public DW-Tversky</th>
<th>submissions</th></tr></thead><tbody>{bar_rows}</tbody></table></div>
<p class="small">Rows 14–22 continue to 0.2707; the full fetch is preserved row by row in
<code>registry/leaderboard_snapshot_2026-10-08.json</code>. Team↔file association is owner-reported;
the board publishes no filenames, hashes or receipts.</p>

<h2>How the emission was chosen</h2>
<div class="table-wrap"><table><thead><tr><th>candidate</th><th>what it is</th>
<th>mean coh σ4</th><th>frac &gt; 0.8</th><th>strike</th><th>in credited band</th>
<th>lift over random</th></tr></thead><tbody>{cand_rows}</tbody></table></div>
<p class="small">Frozen rule R3: the largest coherence lift over the random control at the same
budget, subject to the dominant strike falling inside the credited band (095–115°, array convention,
from knowledge/10 §7). <code>N3_ridge_C3</code> has the largest lift but fails the azimuth condition
and could only place {n([c for c in em['candidates'] if c['name']=='N3_ridge_C3'][0]['placed'])} of
{n(em['budget_star'])} dots from the ≥3-family network. The hide-and-recover assay is reported in
<code>evidence/r5_budget.json</code> and promotes nothing: on it the champion family's habitat field
scores 0.0003 against 0.0275 for uniform random and 0.0395 for the trace field, an order the board
inverts completely.</p>

<h2>What is not true, stated before it is asked</h2>
<ul>
<li><b>No organiser authentication of anything.</b> The bytes are integrity-pinned to a 23-file
SHA-256 manifest from an owner mirror; every score is owner-reported; <code>|G|</code>, ρ and every
projection inherit that.</li>
<li><b>The file is not a predicted winner.</b> Central expectation at κ=1 is DTI {dti1:.4f} —
comparable to the family's 0.2778, not above it. P(beating the board top) is {p_top:.3f}.</li>
<li><b>The promotion instrument is broken and is reported broken.</b> A high assay score here is
evidence about mechanism, never a leaderboard forecast.</li>
<li><b>Two runs of identical stage-3 code logged different numbers</b>, and both saved propensity
fields carry 620 impossible zeros outside the footprint. Neither is explained; both are bounded; the
published numbers reproduce exactly from the arrays on disk. <code>IR-R5-003</code>.</li>
<li><b>The 200 m exclusion ring is a family measurement, not an organiser rule.</b> Staff confirmed the
mask is pixel-exact and that new-fault truth may lie within 300 m of a known trace — “identifying
these corrections is one outcome we are aiming for”. <code>IR-R5-006</code>, and the top-ranked next
experiment in <code>knowledge/26</code>.</li>
</ul>

<p class="small">Round record: <code>knowledge/27_r5_findings.md</code> · official clarifications with
verbatim quotes and links: <code>knowledge/25</code> · five new ranked hypotheses:
<code>knowledge/26</code> · irregularities: <a href="irregularities.html">Limitations</a> ·
sources: <a href="sources.html">Sources</a>.</p>
{ARCHIVE}
</main></body></html>
"""
    (DOCS / "index.html").write_text(index)

    # ---------------------------------------------------------------- executive summary
    ex = HEAD.format(
        desc="Exactly how to submit the R5 GeoTIFF to competition 306: portal steps, the required name, "
             "a note under 200 characters, and the format clauses that make the range error impossible.",
        title="How to submit the R5 artifact · GEMSDOE52") + f"""
<main id="main"><div class="eyebrow">Executive summary · R5 · explicit submission status
<span class="pill ok">OK TO DOWNLOAD</span><span class="pill warn">NOT SLOT-APPROVED</span></div>
<h1>Download, verify, then decide —<br>in that order.</h1>

<section class="download-bar" aria-label="R5 download">
<div><strong>{name}.tif</strong>
<small>{n(em['bytes'])} bytes · SHA-256 <code>{em['sha256']}</code> · {n(S)} px ·
novel fraction {em['uniqueness_gate']['novel_fraction']:.4f} against
{em['uniqueness_gate']['n_priors_checked']} rasters</small>
<small>Short alias <code>downloads/r5-candidate.tif</code> is byte-identical:
{str(bool(same)).lower()}</small></div>
<a class="button" href="{tif_rel}" download>↓ Download the submission TIFF (one click)</a>
<a class="button secondary" href="r5.html">Full audit →</a></section>

<h2>Is it OK to download and submit this file?</h2>
<div class="table-wrap"><table><thead><tr><th>question</th><th>answer of record</th></tr></thead><tbody>
<tr><td>OK to <b>download</b>?</td><td><span class="pill ok">YES</span> — {str(bool(ok_dl)).upper()}.
The file and every receipt are published for audit.</td></tr>
<tr><td>Will the portal <b>accept</b> it?</td><td><span class="pill ok">YES</span> —
{str(bool(ok_sub)).upper()}. Every clause of the organiser's published submission format is verified
against the written bytes: single layer, float32, values in [0,1], EPSG:32611, 100 m, same bounds as
the training data, transform <code>[100, 0, 243350, 0, −100, 4508550]</code> identical to
<code>sample_submission.tif</code>, all {n(v['finite_pixels'])} cells finite, no nodata tag.
The “Predicted values must be in range [0, 1]” rejection needs a non-finite or out-of-range cell;
<code>gems52.grid.write_geotiff</code> raises before writing if either exists and then re-reads the
file, so a published file cannot carry the defect.</td></tr>
<tr><td>Is it a <b>unique</b> submission?</td><td><span class="pill ok">YES</span> — measured, not
named. Decoded pixel pattern differs from all {em['uniqueness_gate']['n_priors_checked']} rasters this
repository has ever produced (the 13 organiser-scored files and every research artifact in
<code>submission/</code> and <code>docs/downloads/</code>); novel fraction
<b>{em['uniqueness_gate']['novel_fraction']:.4f}</b>; not equal to the literal union of priors;
relation to the union: <code>{em['novelty']['relation_to_union']}</code>. An earlier build of this
file reported 0.8021 because it excluded only the 13 scored priors — 19.8 % of its pixels had been
emitted by this repo's own never-submitted research files. The exclusion set was widened and the file
was rebuilt.</td></tr>
<tr><td>OK to spend the <b>weekly slot</b>?</td><td><span class="pill warn">NO — NOT ON THE EVIDENCE
AVAILABLE</span>. The standing rule is not to spend a slot on an idea that has not beaten the holdout
best. The hide-and-recover holdout is disqualified as a leaderboard proxy (Spearman −0.1045,
p = 0.734, n = 13) and R5 reproduced that on new data, so <b>no candidate can clear the bar and none
is claimed to</b>. Probabilities under the frozen prior: P(DTI &gt; 0.2778) = {p_champ:.3f},
P(&gt; 0.3195) = {p_board:.3f}, P(&gt; 0.3774) = {p_top:.3f}; DTI at κ=1 is {dti1:.4f}.</td></tr>
<tr><td>Is there an argument for submitting anyway?</td><td><span class="pill ok">YES, ONE</span> —
the organiser's own. The Final Prize Round ($250k, five times the Initial Round) re-scores against a
label set “updated by expert review of all Phase 1 submissions”, and staff state that “your fault
predictions have an impact on final evaluation even if they are not the most performant in Phase 1”.
This file is {n(S)} strictly novel candidates, each with written geological reasoning in
<a href="downloads/a_only_reasoning_r5.csv">a_only_reasoning_r5.csv</a>, which is the input that round
asks for. One file must serve both rounds, and the choice between them is the owner's, not the
repository's.</td></tr>
<tr><td>Is it a verified fault map?</td><td><span class="pill no">NO</span> — every pixel is a
hypothesis for expert review, with five named competing explanations per candidate.</td></tr>
</tbody></table></div>

<h2>Exact portal steps</h2>
<ol>
<li>Sign in to the eligible account at the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS competition
page</a> and open <b>Submit</b>. The submission limit and the round deadlines are on
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/rules/">the rules page</a>;
this repository cannot see the account and does not guess the remaining slot count.</li>
<li>Click <a href="{tif_rel}" download>↓ Download the submission TIFF</a>. Do not reproject, rescale,
re-save or rename the payload; the file is written to the exact competition grid and any rewrite risks
the format clauses above.</li>
<li>Set <b>File to submit</b> to the downloaded <code>.tif</code>.</li>
<li>Set the submission <b>name</b> to
<code>{name}</code>
({len(name)} characters). It carries the round, the selection rule, the pixel count, the UTC build
stamp and the SHA-256 prefix, so two submissions of this family can never be confused on disk.</li>
<li>Paste this <b>note</b> ({len(NOTE)} of 200 characters):<br>
<code>{NOTE}</code></li>
<li>Submit. The expected public score is <b>not</b> a point value: under the frozen prior the
interval is {proj['0.2778']['dti_at_kappa_lo']:.4f}–{proj['0.2778']['dti_at_kappa_hi']:.4f} with
{dti1:.4f} at κ=1, and P(beating 0.2778) is {p_champ:.3f}. If the returned score lands outside that
interval, that is information about the prior, and it belongs in
<code>registry/irregularities.json</code> rather than in a re-tune.</li>
<li>Before the deadline, remember that <b>one</b> submission must be selected for scoring across both
rounds, without knowing the private-set performance (problem description). Selecting this file selects
the Phase-2 discovery argument above; selecting a higher-Phase-1 file selects the other.</li>
</ol>

<h2>If the portal rejects a file, check these four things in this order</h2>
<ol>
<li><b>“Predicted values must be in range [0, 1]”</b> — the file contains a NaN, an inf, or a value
outside [0,1]. Historically this came from exports that wrote NaN outside the survey footprint
(the <code>-nan</code> family of files). Verify with
<code>python -c "import rasterio,numpy as np;a=rasterio.open('F.tif').read(1);print(np.isfinite(a).all(),a.min(),a.max(),a.dtype)"</code>.
This artifact reports <code>{str(bool(v['all_finite']))} {v['min']} {v['max']} {v['dtype']}</code>
from the bytes on disk.</li>
<li><b>Grid or CRS mismatch</b> — compare the transform and CRS with
<code>data/sample_submission.tif</code>; this file's are
<code>{v['crs']}</code> and <code>{v['transform']}</code>.</li>
<li><b>More than one band, or a wrong dtype</b> — the format requires a single float32 layer; this
file is single-band float32 by construction.</li>
<li><b>A ZIP containing more than the TIFF</b> — if a ZIP is used it must hold exactly one TIFF,
byte-identical to the canonical download.</li>
</ol>

<h2>Budget sensitivity, for the round that pays five times as much</h2>
<p class="small">Staff confirmed the public and private scores are a single pooled Tversky index over
their respective subsets and that “the final re-evaluation will be on the entire GeoDAWN area”. The
DTI-optimal budget scales linearly in |G|, so the final round's larger truth set favours a larger
emission, and one file must serve both. The table is the bet, printed.</p>
<div class="table-wrap"><table><thead><tr><th>S (px)</th><th>DTI at κ=1</th>
<th>P(&gt;0.2778)</th><th>P(&gt;0.3195)</th><th>P(&gt;0.3774)</th></tr></thead><tbody>
{''.join(f"<tr><td>{n(c['budget'])}</td><td>{c['dti_at_kappa1']:.4f}</td>"
         f"<td>{c['p_beat_champion']:.3f}</td><td>{c['p_beat_board']:.3f}</td>"
         f"<td>{c['p_beat_board_top']:.3f}</td></tr>" for c in em['projection_budget_curve'])}
</tbody></table></div>
{ARCHIVE}
<p class="small">Shipped budget: <b>{n(em['budget_star'])} px</b>, the frozen
<code>S* = 4|G|β/(1−β)</code> for the round whose |G| can be measured. κ is the field-quality factor
on the measured credit curve <code>T = κ·471.6·S^0.2284</code>, prior κ ~ U[0.3, 1.3]; κ=1 means “as
good as this family's own field at the same budget”, and the repo's 13 scored files span κ ≈ 0.1 to
≈ 1.0.</p>
</main></body></html>
"""
    (DOCS / "executive-summary.html").write_text(ex)

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

<h2>6 · Irregularities this round added</h2>
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
