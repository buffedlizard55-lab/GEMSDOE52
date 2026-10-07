#!/usr/bin/env python3
"""Publish separate R3 experiment pages and the current H55 executive guide from local receipts.

Run `scripts/refresh_feed.py` first. The R3 TIFF is visibly marked research-only because its
preregistered local lift gate failed; the top-level executive guide is rendered from H55's own
submission receipt and must not inherit R3's status. This script never uploads or submits anything.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"


def load(name: str):
    path = DATA / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"run scripts/refresh_feed.py first; missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text())


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fnum(value, digits=6):
    return "not measured" if value is None else f"{float(value):.{digits}f}"


def nav(prefix: str = "") -> str:
    links = (
        ("index.html", "Overview"),
        ("executive-summary.html", "Submission guide"),
        ("h55.html", "Current H55"),
        ("r3.html", "R3 experiment"),
        ("r3-hypotheses.html", "R3 hypotheses"),
        ("validation.html", "R2 validation"),
        ("forensics.html", "0.2778 autopsy"),
        ("hypotheses.html", "Hypotheses"),
        ("sources.html", "Sources"),
        ("irregularities.html", "Limitations"),
    )
    return "".join(f'<a href="{prefix}{href}">{label}</a>' for href, label in links)


def page(title: str, description: str, body: str, prefix: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="description" content="{esc(description)}">'
        f'<title>{esc(title)} · GEMSDOE52</title>'
        f'<link rel="stylesheet" href="{prefix}style.css"><script src="{prefix}site.js" defer></script>'
        '</head><body><a class="skip" href="#main">Skip to content</a>'
        f'<header><nav><a class="brand" href="{prefix}index.html">GEMS / DOE 52</a>{nav(prefix)}</nav></header>'
        f'<main id="main">{body}</main>'
        '<footer>Competition 306 · Local checks only; organizer acceptance and score are not recorded here. '
        'Fault predictions are not confirmed faults or geothermal vents. '
        f'<a href="{prefix}irregularities.html">Limitations &amp; review</a> · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and complete prompt</a></footer>'
        '</body></html>'
    )


def download_bar(sub: dict, prefix: str = "") -> str:
    uniqueness = sub.get("uniqueness") or {}
    format_gate = sub.get("format") or {}
    note = sub.get("submission_note") or sub.get("note") or ""
    novel_fraction = uniqueness.get("novel_fraction")
    novel_text = "not measured" if novel_fraction is None else f"{100 * float(novel_fraction):.1f}%"
    return (
        '<section class="download-bar" aria-label="Research-only R3 artifact download">'
        '<div><strong>R3-H1 research GeoTIFF — NOT APPROVED FOR UPLOAD</strong>'
        f'<small>{esc(sub.get("file"))}</small>'
        f'<small>{esc(sub.get("bytes"))} bytes · single-band float32 · EPSG:32611 · finite [0,1] · '
        f'sha256 <code>{esc((sub.get("sha256") or "")[:16])}…</code></small>'
        f'<small>on-disk format gate: {"PASS" if format_gate.get("ok") else "FAIL"} · '
        f'canonical pattern unique: {"PASS" if uniqueness.get("canonical_pattern_unique") else "FAIL"} · '
        f'all-prior ≥20% support-novelty diagnostic: '
        f'{"PASS" if uniqueness.get("support_novelty_gate_ok") else "FAIL"} '
        f'({novel_text} support outside comparison union)</small>'
        f'<small>submission note ({esc(sub.get("submission_note_chars", len(note)))} chars): '
        f'<code>{esc(note)}</code></small></div>'
        f'<a class="button" href="{esc(prefix + str(sub.get("download", "")))}" download>↓ Download .TIF</a>'
        f'<a class="button" href="{esc(prefix + str(sub.get("download_zip", "")))}" download>↓ Download .ZIP</a>'
        f'<a class="button secondary" href="{esc(prefix)}r3.html">Validation details →</a>'
        '<small style="width:100%"><strong>Research-only:</strong> the registered spatial-holdout '
        'gate failed; no weekly submission slot has been used. Do not upload this file.</small></section>'
    )


def render_index(sub, holdout, board, feed) -> str:
    gate = holdout["slot_gate"]
    summary = holdout["summary"]
    top = board.get("top")
    rows = {str(row.get("rank")): row for row in board.get("rows", [])}
    our_rank = next((row.get("rank") for row in board.get("rows", [])
                     if float(row.get("score", -1)) == 0.2778), "not recorded")
    body = [download_bar(sub)]
    body.append(
        '<div class="eyebrow">R3 · paired DEM-normal scarp-profile test · 2026-10-07</div>'
        '<h1>A new geological test.<br>An honest negative result.</h1>'
        '<p class="lede">R3-H1 adds two signed, paired-flank profile features to the existing surface-view '
        'model. The preregistered spatial validation showed only a tiny, inconsistent lift. The artifact '
        'is published for audit and reproduction, not as a recommended competition submission.</p>'
    )
    body.append(
        '<div class="status"><strong>Do not upload this R3 file.</strong>'
        f'The mean local DTI lift was {fnum(gate["mean_dti_lift"], 6)} versus View B, with '
        f'{gate["positive_folds"]}/{gate["total_folds"]} positive folds. The preregistered gate required '
        f'+{fnum(gate["required_mean_lift"], 3)} and at least {gate["required_positive_folds"]} positive '
        'folds. No portal slot was used. This local proxy test does not predict the organizer score.</div>'
    )
    body.append(
        '<div class="grid">'
        f'<div class="card"><div class="metric">{fnum(summary["baseline_mean_dti"], 5)}</div>'
        '<div class="label">View B mean spatial holdout DTI</div></div>'
        f'<div class="card"><div class="metric">{fnum(summary["candidate_mean_dti"], 5)}</div>'
        '<div class="label">View B + paired profile mean DTI</div></div>'
        f'<div class="card"><div class="metric">{gate["positive_folds"]}/{gate["total_folds"]}</div>'
        '<div class="label">positive paired folds · 0 weekly slots used</div></div>'
        '</div>'
    )
    body.append(
        '<div class="two"><section><h2>What R3-H1 tested</h2>'
        '<p>Band 12 is detrended elevation; band 19 is its slope. Smooth elevation at σ=2 pixels, sample '
        'bilinearly at ±2 pixels along the local DEM-gradient normal, and encode signed flank concordance '
        'and shoulder asymmetry. The features are dimensionless, label-free, clipped to [−1,1], and kept '
        'out of the historical View B feature list so the control remains unchanged.</p>'
        '<p>This is a surface scarp hypothesis. It can miss buried faults and can respond to roads, fan '
        'margins, erosion, lithologic contacts, grading, or DEM artifacts.</p>'
        '<div class="actions"><a href="r3.html">Read the fold-by-fold result →</a>'
        '<a href="r3-hypotheses.html">Open the frozen four-hypothesis ranking →</a></div>'
        '<h2>Why 0.2778 did well (what we can and cannot say)</h2>'
        '<p>The 2026-10-07 public board showed 0.2778 at rank '
        f'{esc(our_rank)}; 0.3195 at rank 7; and {esc(top)} at rank 1. The board reports team-level best '
        'scores, not TIFF filenames or hashes. Local byte comparisons are consistent with a sparse, '
        'distance-aware placement effect: in a tracked nested raster comparison, 2,545 off-catalogue '
        'points within 200 m of mapped traces were removed between the owner-attributed 0.2708 and 0.2778 '
        'files. That does <em>not</em> mean those pixels were on the known-fault mask, and the local '
        'filename-to-score attribution is not organizer-authenticated. Avoiding weak off-catalogue mass '
        'is a plausible explanation under the distance-weighted metric, not a proven causal account.</p>'
        '<a href="forensics.html">Read the corrected 0.2778 byte-level autopsy →</a>'
        '</section><aside><div class="card"><h3>Current board snapshot</h3>'
        f'<p>Leader: <strong>{esc(top)}</strong> · our reported result: <strong>0.2778</strong> · '
        f'rank {esc(our_rank)} (participant-level observation).</p>'
        '<p class="small">One-off official observation from '
        f'{esc(board.get("observed_date_utc", board.get("fetched_utc", "not recorded")))}. '
        'No automated DrivenData requests are made; see the Terms-of-Use note in the source ledger.</p>'
        '<a href="data/leaderboard.json">Open dated board evidence →</a></div>'
        '<div class="card" style="margin-top:16px"><h3>What a zero result means</h3>'
        '<p>The local “negative” examples are catalogue-zero proxies, not verified fault absence. The '
        'holdout re-tests known components; it does not reproduce the hidden expert-mapped test task.</p>'
        '<p><strong>No public-score forecast is claimed.</strong></p></div></aside></div>'
    )
    body.append(
        '<h2>Separate co-training diagnostic</h2>'
        '<p>The block-level proxy-error correlation test fell below its frozen 0.60 cutoff and allowed a '
        'separate one-round exchange. This is not proof of conditional independence. A-to-B+H1 changed '
        'mean local DTI by +0.000794 in 2/4 folds; B+H1-to-A changed it by −0.002259 in 2/4. Neither '
        'direction entered the artifact. Forty-eight accepted A-only whole components have individual '
        'geological caveats and measured raster context in the review CSV.</p>'
        '<a href="downloads/a_only_reasoning_r3.csv">Download A-only reasoning CSV →</a> · '
        '<a href="r3.html#independence">Inspect the independence and exchange gates →</a>'
    )
    body.append(
        '<div class="live-feed" id="feed">Local evidence feed. The official board remains a dated snapshot.</div>'
        f'<p class="small">Feed generated {esc(feed.get("generated_utc", "not recorded"))}; board observed '
        f'{esc(feed.get("leaderboard_last_observed_utc", "not measured"))}. No portal submission is automated.</p>'
    )
    return page("R3 research result", "R3-H1 paired DEM profile research artifact; holdout gate failed; no upload approval.", "".join(body))


def a_only_comparison_summary(sweep: dict) -> str:
    """Report the A-only fold gate and matched-random means without conflating the tests."""
    def row(mode, arm, emitter_name):
        return next((item for item in (sweep.get(mode, {}).get("summary") or {}).get("ranked", [])
                     if item.get("arm") == arm and item.get("emitter") == emitter_name), None)

    comparisons = {}
    for mode in ("hide", "tip"):
        candidate = row(mode, "A_only", "hc4|37654")
        random = row(mode, "random", "hc|37654")
        if not candidate or not random:
            return "A-only matched-random fold comparison: not measured in the published sweep."
        comparisons[mode] = (candidate, random)

    hide, random_hide = comparisons["hide"]
    tip, random_tip = comparisons["tip"]
    hide_wins = int(hide.get("fold_wins_vs_random") or 0)
    tip_wins = int(tip.get("fold_wins_vs_random") or 0)
    passes = hide_wins >= 3 and tip_wins >= 3
    return (
        f"A-only mean DTI: {float(hide['mean_dti']):.5f} vs matched random "
        f"{float(random_hide['mean_dti']):.5f} on hide, and {float(tip['mean_dti']):.5f} vs "
        f"{float(random_tip['mean_dti']):.5f} on tip. Its fold wins are {hide_wins}/4 and "
        f"{tip_wins}/4; it {'passes' if passes else 'does not pass'} the preregistered "
        "≥3/4-wins-per-instrument promotion comparison. The means are mixed: below random on "
        "hide, above random on tip. This is separate from the conditional-independence test."
    )


def render_summary(sub, verification, sweep) -> str:
    """Render the executive guide from the current H55 receipt, not the separate R3 artifact."""
    note = str(sub.get("submission_note") or "")
    fmt = sub.get("format_gate") or {}
    uniqueness = sub.get("uniqueness") or {}
    geometry = sub.get("geometry") or {}
    emitter = sub.get("emitter_stats") or {}
    projection = sub.get("projection") or {}
    selection = sub.get("selection") or {}
    approved = sub.get("approved_for_weekly_slot")
    format_ok = bool(fmt.get("ok", sub.get("format_ok")))
    unique_ok = bool(uniqueness.get("research_publication_ok", sub.get("uniqueness_ok")))
    independently_verified = bool((verification.get("shipped_file") or {}).get("all_ok"))
    byte_match = bool(sub.get("published_byte_hash_matches_receipt"))
    local_ready = approved is True and format_ok and unique_ok and independently_verified and byte_match

    if local_ready:
        status = (
            '<div class="status"><strong>Local scientific slot gate: PASS.</strong> '
            'The H55 receipt marks this exact artifact <code>approved_for_weekly_slot: true</code>; '
            f'{esc(sub.get("promotion") or "No promotion rationale is recorded.")} '
            'This is an in-repository promotion decision, not organizer approval, not portal acceptance, '
            'and not a public-score forecast. No organizer submission receipt or official score is recorded '
            'here, and this publisher never uploads to the competition.</div>'
        )
    elif approved is False:
        status = (
            '<div class="status"><strong>Research only — do not upload.</strong> '
            'The current H55 receipt does not approve this artifact for a weekly slot. A file-format '
            'pass, if present, is not scientific approval or portal acceptance.</div>'
        )
    else:
        status = (
            '<div class="status"><strong>Submission status: not established.</strong> '
            'The receipt does not contain a true or false local slot-approval flag. Do not infer '
            'approval from the existence of a downloadable TIFF.</div>'
        )

    comparisons = (verification.get("union_audit") or {}).get("comparisons") or []
    comparison_by_name = {str(row.get("name")): row for row in comparisons}
    topk_union = comparison_by_name.get("union of the two views' top-K")
    greedy_union = comparison_by_name.get("union of the two views' coverage-greedy emissions")

    def overlap_text(row):
        if row is None or row.get("frac_of_shipped") is None:
            return "not measured"
        return f"{100 * float(row['frac_of_shipped']):.1f}%"

    a_only_status = a_only_comparison_summary(sweep)

    independence = verification.get("independence_summary") or {}
    hide_ind = independence.get("hide") or {}
    tip_ind = independence.get("tip") or {}
    transform = fmt.get("transform") or []
    transform_text = ", ".join(fnum(value, 0) for value in transform) if transform else "not recorded"
    bounds = fmt.get("bounds") or []
    bounds_text = ", ".join(fnum(value, 1) for value in bounds) if bounds else "not recorded"
    emitted = sub.get("emitted", sub.get("positive_px"))
    novel_px = uniqueness.get("novel_vs_all_priors")
    emitted_text = "not recorded" if emitted is None else f"{int(emitted):,}"
    novel_px_text = "not recorded" if novel_px is None else f"{int(novel_px):,}"
    note_len = len(note)
    tag = str(sub.get("tag") or "not recorded")
    evidence_name = f"h55_verification_{tag}.json"
    h55_reasoning = f"h55_reasoning_{tag}.json"

    body = [
        '<div class="eyebrow">Current H55 artifact · auditable submission guide</div>',
        '<h1>One exact file.<br>A clear local gate.</h1>',
        '<p class="lede">This guide is about the current H55 candidate only. R3-H1, H55-PROFILE, '
        'and H55-EDGE are separate experiments with their own receipts; their research-only labels '
        'do not apply to this H55 file, and this H55 status does not approve those experiments.</p>',
        status,
        '<section class="card"><h2>File identification and one-click download</h2>'
        f'<p>Filename: <code>{esc(sub.get("file"))}</code></p>'
        f'<p>Submission name: <code>{esc(sub.get("submission_name"))}</code></p>'
        f'<p>SHA-256: <code class="mono">{esc(sub.get("sha256"))}</code> · '
        f'{esc(sub.get("bytes"))} bytes</p>'
        f'<label for="h55-submission-note">Portal note ({note_len} characters; '
        f'{200 - note_len} characters below the documented 200-character project limit)</label>'
        f'<textarea id="h55-submission-note" readonly>{esc(note)}</textarea>'
        '<button data-copy="h55-submission-note">Copy note</button>'
        f'<div class="actions"><a class="button" href="{esc(sub.get("download"))}" download>↓ Download exact .TIF</a>'
        f'<a class="button secondary" href="{esc(sub.get("download_zip"))}" download>↓ Download audit .ZIP</a>'
        '<a class="button secondary" href="h55.html">Full H55 analysis →</a></div>'
        '<p class="small">The .TIF is the prediction file. The ZIP is for audit/review; do not upload '
        'the ZIP unless the portal explicitly asks for it.</p></section>'
    ]

    body.append(
        '<h2>What the local file checks establish</h2>'
        f'<p>On-disk format gate: <strong>{"PASS" if format_ok else "FAIL"}</strong>. '
        f'{esc(fmt.get("bands", "not recorded"))} band(s), {esc(fmt.get("dtype", "not recorded"))}, '
        f'{esc(fmt.get("crs", "not recorded"))}, {esc(fmt.get("width", sub.get("width")))} × '
        f'{esc(fmt.get("height", sub.get("height")))} cells; observed values '
        f'[{fnum(fmt.get("min"), 1)}, {fnum(fmt.get("max"), 1)}], '
        f'{esc(fmt.get("nan_pixels", fmt.get("n_nan", sub.get("nan_px"))))} NaN cells and '
        f'{esc(fmt.get("infinity_pixels", 0))} infinities. The affine transform is '
        f'<code>{esc(transform_text)}</code> and the raster bounds are '
        f'<code>{esc(bounds_text)}</code>. The local gate also records a template-bound comparison '
        f'({"PASS" if fmt.get("bounds") == fmt.get("ref_bounds") else "FAIL/NOT RECORDED"}). '
        'These checks reduce the known [0,1] rejection risk, but do not establish behavior of an '
        'undocumented portal validator or guarantee upload acceptance.</p>'
        f'<p>Full receipts: <a href="data/submission.json">current H55 artifact and promotion receipt</a> · '
        f'<a href="data/{esc(evidence_name)}">independent on-disk verification</a>.</p>'
    )

    novel_fraction = uniqueness.get("novel_fraction")
    n_priors = uniqueness.get("n_priors_checked")
    body.append(
        '<h2>Bounded uniqueness and the explicit non-union check</h2>'
        f'<p>The decoded binary pattern is {"canonical-distinct" if uniqueness.get("canonical_pattern_unique") else "not verified canonical-distinct"}; '
        f'{esc(n_priors)} accessible, grid-aligned prior TIFFs were scanned. '
        f'{esc(novel_px_text)} of {esc(emitted_text)} emitted pixels '
        f'({"not measured" if novel_fraction is None else f"{100 * float(novel_fraction):.1f}%"}) '
        'fall outside that comparison union. The receipt records the check as '
        f'<code>{esc(uniqueness.get("relation_to_union", "not recorded"))}</code>. '
        'This is a bounded inventory result, not proof of global uniqueness, independent geology, '
        'or fault discovery; private, inaccessible, and unlinked submissions are outside the claim.</p>'
        f"<p>Separately, the candidate is unequal to the same-budget union of the two views' top-K outputs "
        f'and the union of their coverage-greedy emissions. It overlaps {overlap_text(topk_union)} of its '
        f'pixels with the top-K union and {overlap_text(greedy_union)} with the coverage-greedy union. '
        'The selected emission is View B coverage-greedy with a thermal rank bonus, not a literal A/B '
        'union. <a href="h55.html#non-union">See the complete comparison table</a> · '
        f'<a href="data/{esc(evidence_name)}">machine-readable union audit</a>.</p>'
    )

    ceiling = emitter.get("disc_ceiling")
    eff = geometry.get("spacing_efficiency")
    body.append(
        '<h2>Metric-aware placement and spatial holdout</h2>'
        f'<p>The placement uses the official 300 m distance-weighted Tversky kernel documented by '
        f'<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DrivenData</a>. '
        f'The current file contains {esc(emitted_text)} positive pixels; measured weighted-coverage '
        f'efficiency is A/S = {fnum(geometry.get("A_per_S"), 4)} '
        f'({"not measured" if eff is None else f"{100 * float(eff):.2f}%"} of the recorded '
        f'{fnum(ceiling, 6)} kernel-disc ceiling). This is a placement statistic, not a score forecast.</p>'
        f'<p>The registered local holdout selected <code>{esc(selection.get("arm", "not recorded"))}</code> '
        f'with <code>{esc(selection.get("emitter", "not recorded"))}</code>: hide mean DTI '
        f'{fnum(selection.get("hide"), 5)} vs matched random {fnum((projection.get("random_control") or {}).get("hide"), 5)} '
        f'({esc(selection.get("hide_wins", "not recorded"))}/4 folds), and tip mean DTI '
        f'{fnum(selection.get("tip"), 5)} vs {fnum((projection.get("random_control") or {}).get("tip"), 5)} '
        f'({esc(selection.get("tip_wins", "not recorded"))}/4 folds). These are spatial proxy tests '
        'against held-out mapped-catalogue components, not validation against the hidden expert-mapped '
        'new-fault task.</p>'
    )

    body.append(
        '<h2>Two views, co-training gate, and A-only comparison</h2>'
        f'<p>The pre-registered spatial-block out-of-fold error-correlation statistic on '
        f'catalogue-zero proxy negatives reached |ρ|={fnum(hide_ind.get("max_abs_spearman_mean_overprediction"), 4)} '
        f'on hide and |ρ|={fnum(tip_ind.get("max_abs_spearman_mean_overprediction"), 4)} on tip, '
        f'exceeding the {fnum(hide_ind.get("abandon_threshold"), 2)} abandonment threshold '
        f'({esc(hide_ind.get("usable_blocks_per_fold", "not recorded"))} usable blocks of '
        f'{esc(hide_ind.get("blocks_available", "not recorded"))} per fold). The preregistered verdict '
        'is to abandon co-training; these proxy negatives do not prove geological absence or conditional '
        'independence. ' + a_only_status + '</p>'
        f'<p>The H55 analysis records {esc(sub.get("a_only_components", "not recorded"))} A-only '
        f'components and {esc(sub.get("a_only_emitted_px", "not recorded"))} A-only emitted pixels with '
        f'measured, cautious geological reasoning in <a href="downloads/{esc(h55_reasoning)}">the '
        'per-candidate H55 reasoning record</a>. Those are hypotheses for review, not confirmed faults. '
        f'The separate H55-JUNCTION hypothesis remains untested; see the <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/12_hypotheses_H55_preregistered.md">'
        'frozen hypothesis register</a>. This H55 receipt is not evidence for that untested idea.</p>'
    )

    body.append(
        '<h2>Download and portal caveats</h2>'
        '<ol><li>Download the exact .TIF above and retain its SHA-256. Do not reproject, edit, or substitute '
        'the audit ZIP for the raster.</li>'
        '<li>Before using a weekly slot, confirm the current quota/rules and sign into the authorized '
        'team account on the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">'
        'official competition page</a>. Start a new submission only if you choose to proceed.</li>'
        '<li>Upload only this exact .TIF and paste the identifying portal note above verbatim. The local '
        'format check reduces the known [0,1] risk but cannot guarantee portal acceptance.</li>'
        '<li>Follow the Prize Rules for generative-AI disclosure; report use, extent, and manner as the '
        'current portal requires.</li>'
        '<li>Save any organizer receipt, submission ID, timestamp, and returned score separately. None '
        'is recorded in the H55 artifact receipt here; this publisher never submits anything.</li></ol>'
        '<p>Input grids are integrity-pinned owner mirrors, not independently authenticated against '
        'organizer downloads. A predicted high-value pixel is not a field-confirmed fault, geothermal '
        'vent, or guarantee of competition performance.</p>'
        '<p>Official review links: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">'
        'competition</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">'
        'problem and scoring</a> · <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">'
        'Prize Rules, including generative-AI disclosure</a> · '
        '<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">'
        'USGS GeoDAWN</a> · <a href="https://gdr.openei.org/submissions/1391">'
        'DOE GDR INGENIOUS</a> · <a href="sources.html">source ledger and limitations</a>.</p>'
        '<p>A separate <a href="r3.html">R3-H1 research result</a> failed its own local gate and is clearly '
        'marked research-only there. That status does not apply to this H55 file.</p>'
    )

    return page(
        "H55 submission guide",
        "Current H55 artifact, exact download, local promotion status, file checks, bounded uniqueness, and limitations.",
        "".join(body),
    )

def render_r3(sub, holdout, independence, cotrain, board) -> str:
    gate = holdout["slot_gate"]
    folds = holdout["folds"]
    summary = holdout["summary"]
    fold_rows = []
    for fold in folds:
        base = fold["arms"]["view_B"]["dti"]
        candidate = fold["arms"]["view_B_paired_shoulder"]["dti"]
        fold_rows.append(
            f'<tr><td>{fold["fold"]}</td><td class="number">{base:.6f}</td>'
            f'<td class="number">{candidate:.6f}</td>'
            f'<td class="number">{candidate - base:+.6f}</td>'
            f'<td class="number">{fold["arms"]["view_B_paired_shoulder"]["emitted"]:,}</td></tr>'
        )
    baseline_rows = []
    for arm, mean in summary["refitted_baseline_arm_means"].items():
        baseline_rows.append(f'<tr><td>{esc(arm)}</td><td class="number">{float(mean):.6f}</td></tr>')
    uniqueness = sub["uniqueness"]
    view_comparison = sub["view_comparison"]
    literal_union = view_comparison["view_union"]
    matched_union = view_comparison["matched_budget_max_view_union"]

    base_ind = independence["baseline_view_pair"]
    cand_ind = {k: v for k, v in independence.items()
                if k not in ("blocks", "baseline_view_pair", "primary_pair")}
    direction_rows = []
    for direction in cotrain.get("directions", []):
        direction_rows.append(
            f'<tr><td>{esc(direction["donor_view"])} → {esc(direction["receiver_view"])}</td>'
            f'<td class="number">{direction["pseudo_pixels"]:,}</td>'
            f'<td class="number">{float(direction["mean_baseline_dti"]):.6f}</td>'
            f'<td class="number">{float(direction["mean_after_exchange_dti"]):.6f}</td>'
            f'<td class="number">{float(direction["mean_paired_lift"]):+.6f}</td>'
            f'<td>{direction["positive_folds"]}/{direction["total_folds"]}</td></tr>'
        )
    board_observed = board.get("observed_date_utc", board.get("fetched_utc", "not recorded"))
    note = sub.get("submission_note") or sub.get("note") or ""
    body = [download_bar(sub)]
    body.append(
        '<div class="eyebrow">R3-H1 · preregistered before implementation</div>'
        '<h1>Paired scarp-profile shoulders<br>on the 100 m DEM</h1>'
        '<p class="lede">A narrow geomorphic hypothesis: asymmetric paired slopes on opposite flanks '
        'of a subtle scarp may add information beyond the existing surface view. The feature was fixed '
        'before model fitting; the result below is a holdout diagnostic, not an organizer-score forecast.</p>'
        '<div class="status"><strong>Result: local gate failed; no weekly-slot approval.</strong>'
        f'Mean lift {float(gate["mean_dti_lift"]):+.6f} versus View B; positive folds '
        f'{gate["positive_folds"]}/{gate["total_folds"]}; thresholds +{gate["required_mean_lift"]:.3f} '
        f'and ≥{gate["required_positive_folds"]}/4. The TIF is published only as a research artifact.</div>'
    )
    body.append(
        '<h2>Frozen transform</h2><ul>'
        '<li>Band 12 is detrended elevation; band 19 is its detrended-elevation slope and remains in the existing View B model.</li>'
        '<li>The new H1 transform smooths band 12 with a normalized Gaussian (sigma 2 pixels) and uses its local DEM-gradient normal.</li>'
        '<li>Bilinear elevation samples at ±2 pixels (200 m at the 100 m grid); derive signed flank-slope concordance and shoulder asymmetry.</li>'
        '<li>Two features, clipped to [−1,1], with 10-pixel registered maximum support; no external data.</li>'
        '<li>Baseline `view_B` and candidate `view_B_paired_shoulder` use identical fold rows, learner, placement, and per-fold budget.</li>'
        '</ul><p>Expected physical interpretation: a displaced, asymmetric scarp could be a surface expression of a fault. The same profile can arise from roads, erosion, fan margins, lithology, grading, or DEM artifacts. A 100 m DEM cannot resolve metre-scale morphology or buried faults without surface expression.</p>'
    )
    body.append(
        '<h2>Primary holdout table</h2><div class="table-wrap"><table><thead><tr>'
        '<th>fold</th><th>View B DTI</th><th>View B + H1 DTI</th><th>paired lift</th><th>emitted</th>'
        '</tr></thead><tbody>' + "".join(fold_rows) + '</tbody></table></div>'
        '<p>Four spatial quadrants; whole original 8-connected catalogue components; 80-pixel Euclidean '
        'train/evaluation buffer; negatives are held-out catalogue-zero proxies. The refit reproduced all '
        'six previously published R2 baseline means exactly. Local component recovery is not validation '
        'against the hidden expert-mapped new-fault labels.</p>'
    )
    body.append(
        '<h3>Refitted comparators</h3><div class="table-wrap"><table><thead><tr><th>arm</th><th>mean local DTI</th></tr></thead><tbody>'
        + "".join(baseline_rows) + '</tbody></table></div>'
        f'<p>Best refitted incumbent: <strong>{esc(summary["refitted_local_incumbent"])}</strong> '
        f'({float(summary["refitted_local_incumbent_mean_dti"]):.6f}). Candidate mean '
        f'{float(summary["candidate_mean_dti"]):.6f}; increase {float(summary["candidate_lift_over_incumbent"]):+.6f}. '
        'This does not translate to an organizer score.</p>'
    )
    body.append(
        '<h2>Accessible-prior uniqueness and non-union check</h2>'
        f'<p>The emitted pattern has {int(sub["stats"]["emitted"]):,} positive pixels. It differs from '
        f'all {int(uniqueness["n_priors_checked"])} aligned accessible prior rasters; '
        f'{int(uniqueness["novel_vs_all_priors"]):,} pixels '
        f'({100 * float(uniqueness["novel_fraction"]):.1f}%) are outside their comparison union, '
        f'and {int(uniqueness["prior_px_dropped"]):,} prior-support pixels are not re-emitted. '
        'This is limited to the supplied accessible inventory, not private or unlinked submissions.</p>'
        f'<p>Against the separately placed View A ∪ View B support union, the candidate has '
        f'{int(literal_union["candidate_only"]):,} candidate-only pixels and the union has '
        f'{int(literal_union["union_only"]):,} pixels absent from the candidate. Against a max-view '
        f'control at the same budget, the intersection is {int(matched_union["intersection"]):,} pixels; '
        f'each pattern also has {int(matched_union["candidate_only"]):,} pixels the other lacks. '
        'It is neither a copied raster nor a literal or matched-budget max-view union.</p>'
        '<a href="data/uniqueness_r3.json">Accessible-prior comparison receipt →</a> · '
        '<a href="data/not_union_r3.json">View-union comparison receipt →</a>'
    )
    body.append(
        '<h2 id="independence">Independence gate and one-round co-training diagnostic</h2>'
        f'<p>The proxy-negative block test used {cand_ind["n_blocks"]:,} blocks and '
        f'{cand_ind["n_negative_predictions"]:,} negative predictions. The frozen abandonment threshold '
        f'was {cand_ind["threshold"]:.2f}; maximum absolute correlation was '
        f'{cand_ind["max_abs_correlation"]:.5f} for A vs B+H1. Baseline A vs B was '
        f'{base_ind["max_abs_correlation"]:.5f}. Both diagnostics were defined and below the threshold, '
        'so the preregistered secondary exchange ran. Catalogue-zero blocks are proxies, not verified '
        'fault absences; low error correlation does not prove sufficient views or conditional independence.</p>'
        '<div class="table-wrap"><table><thead><tr><th>donor → receiver</th><th>pseudo pixels</th>'
        '<th>baseline DTI</th><th>after exchange DTI</th><th>paired lift</th><th>positive folds</th></tr></thead><tbody>'
        + "".join(direction_rows) + '</tbody></table></div>'
        '<p>The secondary round did not alter the primary artifact. All pseudo pixels were in training '
        'regions; zero fell in an evaluation region. Accepted whole A-only components are documented '
        'one by one, including measured context and alternative explanations: '
        '<a href="downloads/a_only_reasoning_r3.csv">A-only reasoning CSV</a>. A-only is a buried-structure '
        'hypothesis, not a confirmed fault; B-only is treated as a possible surface artifact.</p>'
        '<a href="data/independence_r3.json">Full block-level independence evidence →</a> · '
        '<a href="data/cotraining_summary_r3.json">Machine-readable co-training summary →</a>'
    )
    body.append(
        '<h2>Why 0.2778 is not a causal proof</h2>'
        f'<p>The public snapshot from {esc(board_observed)} reports 0.2778 at rank '
        f'{esc(next((row.get("rank") for row in board.get("rows", []) if float(row.get("score", -1)) == 0.2778), "not recorded"))}; '
        'the board does not expose the scoring TIFF or its hash. The local forensic byte comparisons '
        'support a plausible sparse-placement explanation, but the participant filename-to-score link is '
        'owner-reported. No hidden new-fault labels are available to this project.</p>'
        '<p>Sources: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">'
        'official task, metric and format</a>; <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">'
        'official participant leaderboard</a>; <a href="https://www.drivendata.org/termsofuse/">DrivenData Terms</a>; '
        '<a href="https://www.cs.cmu.edu/~avrim/Papers/cotrain.pdf">Blum–Mitchell co-training paper</a>; '
        '<a href="https://data.usgs.gov/datacatalog/data/USGS:77ae0551-c61e-4979-aedd-d797abdcde0e">USGS 1 m DEM catalog</a> '
        '(exact footprint coverage not checked).</p>'
        '<p><a href="r3-hypotheses.html">Four ranked hypotheses and outcome →</a> · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/13_r3_h1_validation.md">'
        'Full technical report and limitations in the repository →</a> · '
        '<a href="data/verified_claims_r3.json">R3 claim/source ledger →</a> · '
        '<a href="data/r3_preregistration.json">Frozen preregistration →</a></p>'
    )
    return page("R3-H1 validation", "Preregistered paired scarp-profile feature, spatial holdout, independence gate, and no-slot decision.", "".join(body))


def render_hypotheses(sub, holdout) -> str:
    gate = holdout["slot_gate"]
    body = [download_bar(sub)]
    body.append(
        '<div class="eyebrow">R3 · registered 2026-10-07 · four ranked hypotheses</div>'
        '<h1>Geological hypotheses,<br>ranked before the test</h1>'
        '<p class="lede">Ranked by qualitative expected local value relative to implementation effort. '
        'These are testable physical ideas, not proven faults or quantified score forecasts. Only R3-H1 '
        'was selected for this round; it failed its preregistered gate and consumed no submission slot.</p>'
        '<div class="status"><strong>R3-H1 outcome: gate failed.</strong>'
        f'Mean local DTI lift {fnum(gate["mean_dti_lift"], 6)} vs View B, with '
        f'{gate["positive_folds"]}/{gate["total_folds"]} positive folds; the registered thresholds were '
        f'+{fnum(gate["required_mean_lift"], 3)} and {gate["required_positive_folds"]}/4. No public-score '
        'forecast or geological confirmation is claimed.</div>'
        '<div class="table-wrap"><table><thead><tr><th>Rank / effort</th><th>Layers and physical signature</th>'
        '<th>Why it could find an unmapped structure / how it differs</th><th>Status and key limitation</th></tr></thead><tbody>'
        '<tr><td><strong>1 · R3-H1</strong><br>medium</td>'
        '<td>Band 12 (detrended elevation) supplies the two new paired-flank measurements; band 19 (its slope) '
        'remains in the existing View B model. Smooth band 12; sample paired flanks at ±2 pixels along its '
        'DEM-gradient normal; encode signed concordance and shoulder asymmetry.</td>'
        '<td>A coherent asymmetric scarp can be absent from a generalized or incomplete fault inventory. '
        'Adds paired-profile geometry not explicit in this repository’s scalar curvature/slope features.</td>'
        '<td><strong>Tested; gate failed.</strong> Lift '
        f'{float(gate["mean_dti_lift"]):+.6f}, {gate["positive_folds"]}/{gate["total_folds"]} positive folds. '
        'Surface-only; roads, fan margins, erosion, lithology, grading and DEM artifacts can mimic it.</td></tr>'
        '<tr><td><strong>2 · R3-H2</strong><br>medium</td>'
        '<td>Bands 2, 3, 9 (magnetic field/derivatives), 13 and 18 (gravity), and 15 (basement depth); band 17 '
        'conductivity only as separately reported context. Detect persistent lineament endpoints, T-junctions, '
        'offsets and relay geometry across scales.</td>'
        '<td>Buried transfer structures can be omitted from surface mapping. The new part would be explicit '
        'endpoint/junction graph topology, not another gradient, orientation-coincidence or lineament score.</td>'
        '<td>Not tested; roughly 4–8 CPU hours. Intrusions, lithologic contacts, stripes and model boundaries '
        'are strong confounders. USGS examples motivate testing, not labels.</td></tr>'
        '<tr><td><strong>3 · R3-H3</strong><br>medium-high</td>'
        '<td>Bands 12 and 19 with gravity band 13 and basement-depth band 15 as coarse context. Trace connected '
        'drainage azimuth changes / knickpoints where a reach crosses a subsurface edge.</td>'
        '<td>A fault may deflect drainage, while conditioning on a coarse subsurface edge could '
        'focus the test. This extends a prior negative pixelwise drainage-asymmetry screen to connected channel '
        'topology; lithology and fan deposition remain alternatives.</td>'
        '<td>Not tested; roughly 6–10 CPU hours. At 100 m, channel features may be erased or created by '
        'detrending/DEM conditioning.</td></tr>'
        '<tr><td><strong>4 · R3-H4</strong><br>high</td>'
        '<td>Official USGS 3DEP one-metre bare-earth DEM tiles aligned to competition bands 12/19; optionally '
        'compare the official 1 m link list.</td>'
        '<td>Higher-resolution profiles could resolve small scarps or offset geomorphic surfaces that the '
        '100 m raster smooths away. It cannot detect buried faults without surface expression.</td>'
        '<td>Not viable for a score claim yet; likely 1–3 days. Exact competition-footprint coverage, tile bytes, '
        'and link-list acquisition were not verified.</td></tr>'
        '</tbody></table></div>'
        '<h2>Test and evidence rules</h2>'
        '<ul><li>Use spatially blocked, whole-component holdouts and the same View B baseline, fixed learner, '
        'metric-aware placement and emission budget.</li>'
        '<li>Catalogue-zero pixels are incomplete-label proxies, not verified fault absences; no hidden expert '
        'labels are available here.</li>'
        '<li>A-only components require individual geological reasoning and competing explanations. B-only '
        'components may be surface artifacts. Neither class is independently confirmed.</li>'
        '<li>Co-training disagreement is secondary unless weak proxy-error dependence is measured; a low '
        'correlation is not proof of conditional independence or sufficient views.</li></ul>'
        '<p>Sources: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">'
        'official task, metric and output format</a>; <a href="https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and">'
        'USGS Great Basin blind-system report</a>; <a href="https://data.usgs.gov/datacatalog/data/USGS:77ae0551-c61e-4979-aedd-d797abdcde0e">'
        'USGS 1 m DEM catalog</a> (specific footprint coverage unverified); and '
        '<a href="https://doi.org/10.1145/279943.279962">Blum–Mitchell co-training paper</a>.</p>'
        '<p><a href="r3.html">Read the fold-by-fold R3-H1 report →</a> · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/12_hypotheses_r3_preregistered.md">'
        'Open the full preregistered source note →</a></p>'
    )
    return page("R3 ranked hypotheses", "Four preregistered geological hypotheses ranked by qualitative value and implementation cost.", "".join(body))


def render_downloads(sub) -> str:
    body = [download_bar(sub, prefix="../")]
    body.append(
        '<div class="eyebrow">Files</div><h1>Downloads and receipts</h1>'
        '<p class="lede">The first file is the current R3 research artifact. Its failed local gate is part '
        'of the receipt; it is not approved for upload.</p>'
        f'<div class="card"><h2>{esc(sub.get("file"))}</h2>'
        f'<p>{esc(sub.get("artifact_status"))}</p>'
        f'<p><a href="../{esc(sub.get("download"))}" download>Download TIFF</a> · '
        f'<a href="../{esc(sub.get("download_zip"))}" download>Download ZIP</a> · '
        f'<a href="{esc(Path(sub.get("download", "")).name.replace(".tif", "-audit.json"))}">Audit receipt</a></p>'
        f'<p class="small">SHA-256 {esc(sub.get("sha256"))}</p></div>'
        '<h2>Research support files</h2><ul>'
        '<li><a href="a_only_reasoning_r3.csv">R3 A-only geological reasoning CSV (one row per accepted whole component)</a></li>'
        '<li><a href="../data/holdout_r3_paired_profile.json">Fold-level holdout receipt</a></li>'
        '<li><a href="../data/independence_r3.json">Block-level independence diagnostic</a></li>'
        '<li><a href="../data/submission_r3.json">Artifact receipt</a></li>'
        '<li><a href="../data/independent_tiff_check_r3.json">Independent TIFF readback, grid, mask, range, and hash check</a></li>'
        '</ul><h2>Historical submissions</h2>'
        '<p>Older R2/H53/H54 TIFFs remain in the repository for reproducibility and prior comparison; '
        'they are not the current R3 experiment. See the linked historical audits before using them.</p>'
    )
    return page("Downloads", "Current research-only artifact, notes, and historical downloads.", "".join(body), prefix="../")


def insert_h55_review(current: dict, verification: dict, sweep: dict) -> None:
    """Put receipt-backed H55 status above the historical R2 notes on the irregularities page."""
    path = DOCS / "irregularities.html"
    if not path.exists():
        raise FileNotFoundError("missing docs/irregularities.html; current H55 review must not be silently omitted")
    independent = verification.get("independence_summary") or {}
    hide = independent.get("hide") or {}
    tip = independent.get("tip") or {}
    if current.get("approved_for_weekly_slot") is True:
        local_status = (
            "Local H55 slot gate: PASS for this exact receipt; this is not organizer approval, "
            "and no H55 portal receipt or official score is recorded."
        )
    elif current.get("approved_for_weekly_slot") is False:
        local_status = "Local H55 slot gate: FAIL; this artifact is research-only and not approved for upload."
    else:
        local_status = "H55 slot status is not established by the receipt; do not infer approval."
    block = (
        '<!--H55-CURRENT-REVIEW--><section id="h55-current-review" class="card">'
        '<div class="eyebrow">Current H55 status · 2026-10-07</div>'
        '<h2>Current artifact review; older notes below are historical</h2>'
        f'<p><strong>{esc(local_status)}</strong> Current file: <code>{esc(current.get("file"))}</code>. '
        '<a href="executive-summary.html">Open the current H55 download and submission guide</a> · '
        '<a href="h55.html">Full H55 analysis</a>.</p>'
        '<p>Band 6 was re-audited as GeoDAWN total-count radiometry, not a magnetic derivative, despite its TIFF tag; '
        'see <a href="h55.html">the H55 evidence page</a>. The pre-registered block-level proxy error-correlation '
        f'test reached |ρ|={fnum(hide.get("max_abs_spearman_mean_overprediction"), 4)} on hide and '
        f'{fnum(tip.get("max_abs_spearman_mean_overprediction"), 4)} on tip against the '
        f'{fnum(hide.get("abandon_threshold"), 2)} cutoff; co-training was abandoned under that registered test. '
        'Catalogue-zero pixels are incomplete-label proxies, so this is not proof of geological absence or '
        'conditional independence.</p>'
        f'<p>{esc(a_only_comparison_summary(sweep))}</p>'
        '<p>H55-JUNCTION remains untested; no new TIFF or weekly submission slot is part of this review. '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/12_hypotheses_H55_preregistered.md">'
        'Open the frozen H55 hypothesis register</a>.</p>'
        '</section><!--/H55-CURRENT-REVIEW-->'
    )
    text = path.read_text(encoding="utf-8")
    start_tag, end_tag = "<!--H55-CURRENT-REVIEW-->", "<!--/H55-CURRENT-REVIEW-->"
    if start_tag in text and end_tag in text:
        start = text.index(start_tag)
        end = text.index(end_tag, start) + len(end_tag)
        text = text[:start] + block + text[end:]
    else:
        marker = '<main id="main">'
        if marker not in text:
            raise ValueError("docs/irregularities.html lacks the expected main container")
        text = text.replace(marker, marker + block, 1)

    # Replace two stale H53/H54-era assertions that contradicted the current H55 source audit.
    text = text.replace(
        '<li><strong>No radiometric bands in the available stack.</strong> No invented data layers, LiDAR-only hidden-label claims or local microseismic locations.</li>',
        '<li><strong>H55 corrected the H52-era radiometry interpretation.</strong> Band 6 is measured as GeoDAWN total-count radiometry, not a magnetic derivative. External layers and catalogues remain bounded context, not confirmed hidden labels.</li>')
    text = text.replace(
        '<li><strong>Geophysical view is weaker here.</strong> Low negative-error correlation did not make co-training win. Strong surface-only control prevented a false promotion.</li>',
        '<li><strong>H55 co-training and A-only results are separate.</strong> The registered block-error-correlation test exceeded its cutoff and co-training was abandoned. A-only fails the ≥3/4 fold-win gate with mixed means: below random on hide and above on tip.</li>')
    text = text.replace('<h2>Next session, in order</h2>', '<h2>Historical R2 next-session plan</h2>')
    path.write_text(text, encoding="utf-8")


def insert_nav_link(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text()
    updated = text.replace("<strong>New R2 research GeoTIFF</strong>",
                           "<strong>Historical R2 research GeoTIFF</strong>")
    additions = ""
    if 'href="r3.html"' not in updated:
        additions += '<a href="r3.html">R3 experiment</a>'
    if 'href="r3-hypotheses.html"' not in updated:
        additions += '<a href="r3-hypotheses.html">R3 hypotheses</a>'
    marker = "</nav>"
    index = updated.find(marker)
    if index >= 0 and additions:
        updated = updated[:index] + additions + updated[index:]
    if updated != text:
        path.write_text(updated)


def insert_r3_home_bar(sub: dict) -> None:
    path = DOCS / "index.html"
    text = path.read_text(encoding="utf-8")
    bar = download_bar(sub).replace(
        '<section class="download-bar"',
        '<section class="download-bar" id="r3-h1-research-bar"', 1)
    block = "<!--R3-H1-RESEARCH-BAR-->" + bar + "<!--/R3-H1-RESEARCH-BAR-->"
    start_tag, end_tag = "<!--R3-H1-RESEARCH-BAR-->", "<!--/R3-H1-RESEARCH-BAR-->"
    if start_tag in text and end_tag in text:
        start = text.index(start_tag)
        end = text.index(end_tag, start) + len(end_tag)
        text = text[:start] + block + text[end:]
    else:
        anchor = "<!--/H55BAR-->"
        if anchor in text:
            index = text.index(anchor) + len(anchor)
        else:
            main = text.find("<main")
            index = text.find(">", main) + 1 if main >= 0 else 0
        text = text[:index] + block + text[index:]
    path.write_text(text, encoding="utf-8")


def insert_r3_download_section(sub: dict) -> None:
    path = DOCS / "downloads/index.html"
    text = path.read_text(encoding="utf-8") if path.exists() else "<!doctype html><html><body><main>"
    name = str(sub["file"])
    stem = name.removesuffix(".tif")
    block = (
        '<!--R3-H1-RESEARCH-DOWNLOADS--><section class="card" id="r3-h1-research-download">'
        '<h2>R3-H1 research-only artifact — DO NOT UPLOAD</h2>'
        f'<p>{esc(sub.get("artifact_status"))}</p>'
        f'<p><a href="{esc(name)}" download>Download R3 research TIFF</a> · '
        f'<a href="{esc(stem)}.zip" download>Download ZIP and audit receipt</a> · '
        f'<a href="{esc(stem)}-audit.json">Audit JSON</a> · '
        '<a href="a_only_reasoning_r3.csv">A-only reasoning CSV</a></p>'
        f'<p class="small">{esc(sub.get("submission_name"))} · '
        f'{esc(sub.get("submission_note"))} · no weekly slot used.</p>'
        '</section><!--/R3-H1-RESEARCH-DOWNLOADS-->'
    )
    start_tag, end_tag = "<!--R3-H1-RESEARCH-DOWNLOADS-->", "<!--/R3-H1-RESEARCH-DOWNLOADS-->"
    if start_tag in text and end_tag in text:
        start = text.index(start_tag)
        end = text.index(end_tag, start) + len(end_tag)
        text = text[:start] + block + text[end:]
    else:
        index = text.lower().rfind("</main>")
        if index < 0:
            index = text.lower().rfind("</body>")
        if index < 0:
            text += block
        else:
            text = text[:index] + block + text[index:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    # R3 owns its experiment pages only. The top-level executive guide describes the current H55
    # artifact from submission.json; it must never relabel R3 as the current upload candidate.
    sub = load("submission_r3")
    current = load("submission")
    h55_verification = load(f"h55_verification_{current.get('tag', '')}")
    h55_sweep = load("h55_sweep_hardcore")
    holdout = load("holdout_r3_paired_profile")
    independence = load("independence_r3")
    cotrain = load("cotraining_summary_r3")
    board = load("leaderboard")
    if sub.get("file") is None or sub.get("approved_for_weekly_slot") is not False:
        raise ValueError("the R3 receipt must name a non-approved research artifact")
    sub["download"] = "downloads/" + sub["file"]
    sub["download_zip"] = "downloads/" + sub["file"].removesuffix(".tif") + ".zip"
    sub["exists"] = (DOCS / sub["download"]).exists()
    sub["submission_note"] = sub.get("submission_note") or sub.get("note") or ""
    sub["submission_note_chars"] = len(sub["submission_note"])
    if not sub["exists"]:
        raise FileNotFoundError(f"missing R3 research raster: {sub['download']}")
    if not (DOCS / sub["download_zip"]).exists():
        raise FileNotFoundError(f"missing R3 research archive: {sub['download_zip']}")

    if current.get("file") is None or current.get("approved_for_weekly_slot") not in (True, False):
        raise ValueError("the current H55 receipt must name an artifact and an explicit local gate status")
    current_file = DOCS / str(current.get("download") or "")
    if not current_file.is_file():
        raise FileNotFoundError(f"missing current H55 raster: {current_file.relative_to(ROOT)}")
    if h55_verification.get("tag") != current.get("tag") or \
            (h55_verification.get("shipped_file") or {}).get("file") != current.get("file"):
        raise ValueError("the H55 verification receipt does not describe the current submission.json artifact")
    checks = (h55_verification.get("shipped_file") or {}).get("checks") or {}
    hash_gate_ok = (current.get("published_byte_hash_matches_receipt") is True
                    and current.get("sha256") == (current.get("format_gate") or {}).get("sha256")
                    and checks.get("sha256_matches_record") is True)
    if current.get("approved_for_weekly_slot") is True and not (
            (current.get("format_gate") or {}).get("ok") is True
            and (current.get("uniqueness") or {}).get("research_publication_ok") is True
            and (h55_verification.get("shipped_file") or {}).get("all_ok") is True
            and hash_gate_ok):
        raise ValueError("H55 is marked locally approved, but one or more independent artifact gates failed")

    (DOCS / "executive-summary.html").write_text(
        render_summary(current, h55_verification, h55_sweep), encoding="utf-8")
    (DOCS / "r3.html").write_text(render_r3(sub, holdout, independence, cotrain, board), encoding="utf-8")
    (DOCS / "r3-hypotheses.html").write_text(render_hypotheses(sub, holdout), encoding="utf-8")
    insert_h55_review(current, h55_verification, h55_sweep)
    insert_r3_home_bar(sub)
    insert_r3_download_section(sub)
    for name in ("index.html", "validation.html", "forensics.html", "hypotheses.html", "sources.html",
                 "irregularities.html", "feed.html", "h54.html", "executive-summary.html"):
        insert_nav_link(DOCS / name)
    print("wrote R3 research pages and top-level callouts without replacing the current submission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
