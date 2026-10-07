#!/usr/bin/env python3
"""Render the H54 audit page and the separate H55-1 paired-shoulder experiment page.

H54 and H55-1 are historical research/audit artifacts, not the current main H56 candidate. This
script consumes the dedicated docs/data/h54_audit.json feed record for H54 and explicitly scoped
paired-shoulder receipts for H55-1; it never reads or rewrites docs/data/submission.json or
submission/LATEST.txt. It updates only these two research pages and idempotent, separate site cards.
"""
from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"
NAV = ('<a href="index.html">Overview</a><a href="executive-summary.html">Submission&nbsp;guide</a>'
       '<a href="h54.html">H54&nbsp;audit-only</a><a href="h55-paired-shoulders.html">H55-1&nbsp;failed gate</a>'
       '<a href="hypotheses.html">H55&nbsp;hypotheses</a><a href="validation.html">Validation</a>'
       '<a href="forensics.html">0.2778&nbsp;autopsy</a><a href="irregularities.html">Irregularities</a>'
       '<a href="sources.html">Sources</a>')


def esc(x) -> str:
    return html.escape(str(x))


def load(name: str) -> dict:
    p = EV / f"{name}.json"
    if not p.exists():
        return {"__missing__": str(p)}
    return json.loads(p.read_text())


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="GEMSDOE52 research artifact, holdout status, and audit evidence.">'
            f'<title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css">'
            f'</head><body><a class="skip" href="#main">Skip to content</a>'
            f'<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{NAV}</nav></header>'
            f'<main id="main">{body}</main>'
            f'<footer>Competition 306 · figures are rendered from the dedicated research receipts in '
            f'<code>evidence/</code> and <code>docs/data/</code> by <code>scripts/make_site_pages.py</code></footer>'
            f'</body></html>')


def download_bar(sub: dict) -> str:
    """Prominent one-click audit links with an explicit no-upload warning."""
    if not sub.get("exists"):
        return ('<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
                '<strong>No slot-approved submission exists.</strong>'
                '<small>H54 is a legacy research artifact; no new candidate passed the required spatial gate.</small>'
                '</div></div><!--/H54BAR-->')
    uni = sub.get("uniqueness") or {}
    fmt = sub.get("format") or {}
    note = sub.get("submission_note") or "H54 research artifact; no comparable holdout; not approved for submission."
    download = sub.get("short_download") or sub.get("download")
    download_zip = sub.get("short_download_zip") or sub.get("download_zip")
    return (
        '<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
        '<strong>H54 legacy GeoTIFF — research/audit only · DO NOT UPLOAD</strong>'
        f'<small>{esc(sub.get("file"))}</small>'
        f'<small>{esc(sub.get("bytes"))} bytes · local format check {esc(fmt.get("ok"))} · '
        f'{esc(uni.get("n_priors_checked"))} bounded prior files checked · full-inventory decoded uniqueness unknown</small>'
        '<small>No comparable spatial holdout · not a new result · no weekly-slot approval</small>'
        f'<small>Audit-only note ({esc(sub.get("submission_note_chars", len(note)))} chars): '
        f'<code>{esc(note)}</code></small></div>'
        f'<a class="button" href="{esc(download)}" download>↓ Download audit .TIF</a>'
        f'<a class="button" href="{esc(download_zip)}" download>↓ Download audit .ZIP</a>'
        '<a class="button" href="h54.html">Read limitations →</a>'
        '</div><!--/H54BAR-->')


def insert_bar(path: pathlib.Path, bar: str) -> bool:
    """Update the legacy H54 bar without outranking the current main H56 candidate."""
    if not path.exists():
        return False
    s = path.read_text()
    if "<!--H54BAR-->" in s and "<!--/H54BAR-->" in s:
        a = s.index("<!--H54BAR-->")
        b = s.index("<!--/H54BAR-->") + len("<!--/H54BAR-->")
        path.write_text(s[:a] + bar + s[b:])
        return True
    # If missing, keep the current candidate and all existing research cards first.
    # The summary guide has no main-candidate block, so put the legacy audit link last.
    for marker in ("<!--/R3-H1-RESEARCH-BAR-->", "<!--/H55BAR-->"):
        if marker in s:
            i = s.index(marker) + len(marker)
            path.write_text(s[:i] + bar + s[i:])
            return True
    i = s.rfind("</main>")
    if i < 0:
        return False
    path.write_text(s[:i] + bar + s[i:])
    return True


def paired_card() -> str:
    data = DOCS / "data"
    hold = json.loads((data / "h55_paired_shoulders_holdout.json").read_text())
    arms = hold["arms"]
    gate = hold["slot_gate"]
    lift = arms["mean_dti_lift"]
    positive = hold["positive_outer_folds"]
    total = hold["total_outer_folds"]
    return (
        '<!--H55PAIRED--><section class="card" id="h55-paired-shoulders">'
        '<h2>H55-1 paired DEM shoulders — preregistered gate failed</h2>'
        f'<p>Matched View-B mean DTI {arms["matched_view_B_mean_dti"]:.6f}; '
        f'paired-shoulder mean {arms["h55_paired_shoulders_mean_dti"]:.6f}; '
        f'lift {lift:+.6f} ({positive}/{total} folds positive). The frozen minimum was '
        f'{gate["minimum_mean_lift"]:+.3f}; this result remains research-only.</p>'
        '<p><strong>No TIFF was generated for this failed follow-up.</strong> The main H56 artifact '
        'and <code>submission/LATEST.txt</code> were not replaced. '
        '<a href="h55-paired-shoulders.html">Full result, protocol and geological hypotheses →</a></p>'
        '</section><!--/H55PAIRED-->'
    )


def insert_paired_card(path: pathlib.Path, card: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text()
    start, end = "<!--H55PAIRED-->", "<!--/H55PAIRED-->"
    if start in text and end in text:
        a, b = text.index(start), text.index(end) + len(end)
        path.write_text(text[:a] + card + text[b:])
        return True
    for marker in ("<!--/H55PROFILE-->", "<!--/H55BAR-->"):
        if marker in text:
            i = text.index(marker) + len(marker)
            path.write_text(text[:i] + card + text[i:])
            return True
    i = text.rfind("</main>")
    if i < 0:
        return False
    path.write_text(text[:i] + card + text[i:])
    return True


def paired_body() -> str:
    data = DOCS / "data"
    hold = json.loads((data / "h55_paired_shoulders_holdout.json").read_text())
    gate = json.loads((data / "h55_paired_shoulders_protocol_gate.json").read_text())
    integrity = json.loads((data / "h55_paired_shoulders_run_integrity.json").read_text())
    review_path = data / "review_execution_h55_paired_shoulders.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    prereg = json.loads((data / "h55_paired_shoulders_preregistration.json").read_text())
    main_pointer_path = ROOT / "submission/LATEST.txt"
    main_file = main_pointer_path.read_text().strip() if main_pointer_path.exists() else "not recorded"
    arms = hold["arms"]
    slot = hold["slot_gate"]
    candidate = "view_B_h55_paired_shoulders"
    fold_rows = []
    for row in hold["folds"]:
        control = row["scores"]["view_B"]["dti"]
        value = row["scores"][candidate]["dti"]
        fold_rows.append([row["fold"], f"{control:.6f}", f"{value:.6f}", f"{value - control:+.6f}"])
    hold_table = table(["Outer fold", "Matched View-B DTI", "H55-1 DTI", "Paired lift"], fold_rows)
    hypothesis_rows = []
    for item in prereg.get("ranked_hypotheses", []):
        status = item.get("status", "not recorded")
        if item.get("id") == "H55-1":
            status = "tested; preregistered promotion gate failed"
        hypothesis_rows.append(
            '<tr>'
            f'<td>{esc(item.get("rank"))}. {esc(item.get("id"))}<br><strong>{esc(item.get("title"))}</strong></td>'
            f'<td>{esc(item.get("layers"))}</td>'
            f'<td>{esc(item.get("physical_signature"))}</td>'
            f'<td>{esc(item.get("why_uncatalogued_faults"))}<br><em>Alternatives:</em> {esc(item.get("alternatives"))}</td>'
            f'<td>{esc(item.get("novelty"))}</td>'
            f'<td>{esc(item.get("expected_dti_effect"))}</td>'
            f'<td>{esc(item.get("implementation_cost"))}<br>External data: {esc(item.get("external_data_required"))}</td>'
            f'<td>{esc(status)}</td></tr>'
        )
    hypotheses = ('<div class="table-wrap"><table><thead><tr>'
                  '<th>Rank / hypothesis</th><th>Layers</th><th>Physical signature</th>'
                  '<th>Rationale / alternatives</th><th>Novelty boundary</th>'
                  '<th>Expected effect</th><th>Cost / data</th><th>Status</th>'
                  f'</tr></thead><tbody>{"".join(hypothesis_rows)}</tbody></table></div>')
    caveats = " ".join(esc(c) for c in hold.get("caveats", []))
    namespace = integrity.get("execution_path_namespace", {})
    source_note = namespace.get("note", "Execution sources are hash-pinned in the integrity receipt.")
    gate_gap = namespace.get("protocol_gate_preservation_gap", {})
    gate_gap_text = ""
    if gate_gap and not gate_gap.get("preholdout_gate_exact_bytes_preserved", True):
        gate_gap_text = (
            "Integrity exception: frozen holdout binds pre-holdout protocol-gate SHA-256 "
            f"{gate_gap.get('holdout_bound_preholdout_gate_sha256')}; the surviving post-run gate "
            f"SHA-256 is {gate_gap.get('currently_preserved_post_run_gate_sha256')}. The original "
            "pre-holdout bytes are not preserved. The current gate receipt is not byte-identical "
            "evidence of the preflight state."
        )
    pass_text = "Historical pre-rebase review only; its test/site counts do not certify the merged tree."
    if review:
        pass_text = (
            f"The {len(review.get('passes', []))}-pass review receipt records the original pre-rebase "
            "implementation/review/re-check. Its claims remain historical and do not substitute for "
            "the post-integration checks recorded for this merged tree."
        )
    body = (
        '<div class="eyebrow">H55-1 · frozen matched spatial holdout · local research only</div>'
        '<h1>Paired DEM shoulders: a measured but insufficient lift.</h1>'
        '<div class="status"><strong>Preregistered gate failed; do not spend a slot.</strong>'
        f'Paired mean lift {arms["mean_dti_lift"]:+.6f} versus the required '
        f'{slot["minimum_mean_lift"]:+.3f}; {hold["positive_outer_folds"]}/{hold["total_outer_folds"]} '
        f'folds positive (minimum {slot["minimum_positive_folds"]}). No TIFF was generated for this '
        'follow-up and no portal upload was performed.</div>'
        '<h2>Matched holdout, fold by fold</h2>' + hold_table +
        f'<p>Mean View-B DTI {arms["matched_view_B_mean_dti"]:.8f}; '
        f'mean paired-shoulder DTI {arms["h55_paired_shoulders_mean_dti"]:.8f}; '
        f'mean lift {arms["mean_dti_lift"]:+.8f}. The model used identical training rows, seed and '
        'learner for each fold, with a frozen four-fold, 80-pixel buffered whole-component protocol. '
        'These are local catalogue-proxy scores, not portal or leaderboard scores.</p>'
        '<h2>Decision and scope</h2>'
        f'<p><strong>{esc(slot.get("reason"))}</strong> The protocol checker status '
        f'<code>{esc(gate.get("status"))}</code> authorized only execution of the preregistered '
        'holdout; “READY” was not a pass/slot approval. Score-to-file mapping and organizer input-byte '
        'authentication remain false. {}</p>'.format(caveats) +
        f'<p>Main H56 pointer remains <code>{esc(main_file)}</code>. This separate failed result does '
        'not replace or validate the main candidate. The H55-1 experiment did not generate a downloadable '
        'raster; no copied prior is being represented as a new prediction.</p>'
        '<h2>Ranked geological hypotheses and decision record</h2>' + hypotheses +
        '<h2>Provenance and audit files</h2>'
        f'<p>{esc(source_note)}</p>'
        + (f'<div class="status"><strong>Preservation gap:</strong> {esc(gate_gap_text)}</div>' if gate_gap_text else '')
        + f'<p>{esc(pass_text)}</p>'
        '<ul>'
        '<li><a href="data/h55_paired_shoulders_preregistration.json">Frozen H55-1 registration</a></li>'
        '<li><a href="data/h55_paired_shoulders_protocol_gate.json">Pre-holdout protocol/integrity gate</a></li>'
        '<li><a href="data/h55_paired_shoulders_holdout.json">Frozen four-fold holdout receipt</a></li>'
        '<li><a href="data/h55_paired_shoulders_run_integrity.json">Run source/input hash receipt and path-namespace note</a></li>'
        '<li><a href="data/review_execution_h55_paired_shoulders.json">Three-pass execution review (historical pre-rebase)</a></li>'
        '<li><a href="data/h55_paired_shoulders_hypotheses.md">Preregistered hypotheses in Markdown</a></li>'
        '</ul>'
        '<p class="small">The repeated-run guard prevents refitting this exact registration/input set. '
        'Any new experiment requires a new preregistration. Owner-mirror input pins are not organizer '
        'authentication. H55-1 was a repository-level concept preregistered earlier as R2-H2; its '
        'execution is new, not the geological idea itself.</p>'
    )
    return body


def table(head, rows) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(
        f'<td class="num">{esc(c)}</td>' if isinstance(c, (int, float)) else f"<td>{esc(c)}</td>"
        for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def h54_body() -> str:
    # Read the *feed* copy, not the evidence copy: scripts/refresh_feed.py enriches it with
    # `exists`, `download`, `download_zip` and `submission_note`, which is what download_bar() needs.
    # Reading evidence/submission_<stem>.json here rendered the "not built" branch on a page whose
    # subject was the built file.
    sub = json.loads((DOCS / "data/h54_audit.json").read_text())
    prior_inv = json.loads((DOCS / "data/h54_prior_inventory_availability.json").read_text())
    a_only = json.loads((DOCS / "data/a_only_geological_reasoning54.json").read_text())
    a_check = a_only.get("candidate_raster_check") or {}
    h54_review = json.loads((DOCS / "data/h54_artifact_review_2026-10-07.json").read_text())
    cal = load("revealed_calibration")
    bud = load("revealed_budget")
    ind = load("independence_revealed")
    views = load("cotraining_views54")
    audit = load("revealed_submission_audit")
    B = []
    B.append('<div class="eyebrow">H54 · conditional owner-mirror audit</div>'
             '<h1>What the bytes show — and what scores do not authenticate</h1>'
             '<p class="lede">Locally mirrored raster bytes can be compared and their spatial nesting can be checked. The associated scores are owner-reported/public-board observations, but no organizer receipt maps a score to an exact filename or hash. Every hidden-truth, credit, ring, or budget calculation below is conditional on those unverified associations; it is not an authenticated calibration, holdout result, fault truth, or submission approval.</p>')
    B.append(download_bar(sub))
    B.append('<div class="status"><strong>H54 is a legacy audit artifact; do not spend a slot.</strong> Retained-core credit and budget values are conditional on unauthenticated file/score mappings. The additional-cell credit density is unknown; 171 exploratory features were screened against an owner-mirror-derived target, not organizer labels. The stated prior below is a scenario assumption, not calibrated probability or a score forecast. H54 has no comparable spatial holdout and full-inventory uniqueness is unknown.</div>')
    B.append(table(["promotion/evidence check", "recorded result"], [
        ["artifact disposition", h54_review.get("artifact_status")],
        ["score-to-file mapping", h54_review.get("score_link_authentication")],
        ["comparable spatial holdout", h54_review.get("spatial_holdout")],
        ["weekly slots used", h54_review.get("weekly_slots_used")],
        ["global decoded uniqueness", (h54_review.get("bounded_uniqueness") or {}).get("global_decoded_pattern_unique")
         if (h54_review.get("bounded_uniqueness") or {}).get("global_decoded_pattern_unique") is not None
         else "unknown; only 23 historical rasters checked, 377 eligible inventory files unavailable"],
        ["H54 artifact SHA-256", h54_review.get("file_sha256")],
    ]))

    B.append("<h2>1 · Conditional arithmetic under the assumed file/score mapping</h2>")
    rows = [["|G| (scenario-inferred hidden count, px)", cal.get("g_estimate_px"),
             "conditional algebra from local byte nesting plus unverified owner-reported score links"]]
    rows.append(["conditional credit of selected ≤200 m ring", cal.get("corridor_credit"), "scenario-derived only; not an organizer mask rule or authenticated score fact"])
    rows.append(["score/file authentication", cal.get("score_link_authentication"), "no organizer receipt maps the public score to an exact filename/hash"])
    for k, v in (cal.get("size_of") or {}).items():
        rows.append([f"atom {k}", v,
                     f"conditional credit {(cal.get('credit_of') or {}).get(k)} · density "
                     f"{(cal.get('density_of') or {}).get(k)}"])
    rd = cal.get("reference_densities") or {}
    rows.append(["uniform-random density", rd.get("uniform_random_over_permitted_set"),
                 "credit per emitted pixel for a Poisson dot cloud of 37,654 px"])
    rows.append(["champion file as a whole", rd.get("champion_file_as_a_whole"),
                 f"credit {rd.get('champion_file_credit')} over 37,654 px"])
    rows.append(["retained core credit", f"{(cal.get('t_core_bounds') or ['?'])[0]} – "
                 f"{(cal.get('t_core_bounds') or ['?'])[1]}, central {cal.get('t_core_central')}",
                 "conditional interval from t ≥ 0 under the assumed score mapping; central value is an explicit split assumption"])
    rows.append(["scenario DTI (core emitted alone)", f"{(cal.get('dti_core_bounds') or ['?'])[0]} – "
                 f"{(cal.get('dti_core_bounds') or ['?'])[1]}, central {cal.get('dti_core_central')}",
                 "conditional metric calculation; no spatial validation and no new-geology inference"])
    B.append(table(["quantity", "value", "status"], rows))
    B.append("<h3>What was verified on the bytes</h3><ul>"
             + "".join(f"<li>{esc(n)}</li>" for n in (cal.get("notes") or [])) + "</ul>")

    B.append("<h2>2 · A budget scenario under a stated prior (not a P(win) forecast)</h2>")
    B.append(f'<p><code>DTI = (t_core + ρ_novel·n_novel) / (0.2·S + 0.8·|G|)</code>, capped by '
             f'<code>T ≤ |G|</code>. <code>t_core</code> is bounded exactly, so it gets a uniform prior '
             f'over {esc(json.dumps(bud.get("t_core_bounds")))}. <code>ρ_novel</code> is unknowable, so it '
             f'gets a uniform prior over {esc(json.dumps(bud.get("rho_prior")))} — from "no better than '
             f'uniform random" to "as good as the owner-labelled champion file\'s average". Under this '
             f'artificial prior only, the rule maximises conditional P(DTI &gt; {esc(bud.get("floor"))}) '
             f'and breaks ties toward the larger additional-cell fraction. This is not calibrated to the '
             f'organizer, authenticated score mapping, hidden labels, or future performance.</p>')
    sel = (bud.get("selected") or {}).get("n_novel")
    B.append(table(["additional px", "total px", "fraction", "scenario P(DTI>bar)", "scenario mean", "scenario low", "scenario high"],
                   [[r["n_novel"], r["total"], round(100 * r["novel_fraction"], 1),
                     r["p_win"], r["mean_dti"], r["worst_dti"], r["best_dti"]]
                    for r in (bud.get("rows") or [])])
             + f'<p class="small">selected scenario row: <b>{esc(sel)}</b> additional pixels under the registered prior—not a validated budget.</p>')

    B.append("<h2>3 · Descriptive view-error diagnostics (not a valid independence test)</h2>")
    sb = (views.get("single_view_baseline") or {})
    va, vb = views.get("view_a") or {}, views.get("view_b") or {}
    B.append(table(["quantity", "value", "reading"], [
        ["View A out-of-fold AUC", va.get("oof_auc"),
         f"potential field / subsurface, {va.get('n_features')} features; block mean "
         f"{sb.get('view_a_mean')}"],
        ["View B out-of-fold AUC", vb.get("oof_auc"),
         f"surface / detrended elevation and slope (no radiometric band in the supplied 19-band stack), "
         f"{vb.get('n_features')} features; block mean {sb.get('view_b_mean')}"],
        ["blended", views.get("blended_oof_auc"),
         f"co-training wins: {sb.get('co_training_wins')} — View B alone beats the blend, and that is "
         f"printed rather than buried"],
        ["independence, pixel Pearson r", ind.get("pixel_pearson_r"),
         f"threshold {ind.get('threshold')} → {ind.get('verdict')}"],
        ["independence, block mean r", ind.get("block_mean_r"),
         f"variance {ind.get('block_var_r')} over {ind.get('n_blocks')} blocks; degenerate: "
         f"{ind.get('degenerate_block_variance')}"],
    ]))
    B.append(f'<p class="small">{esc(sb.get("label_caveat") or "")}</p>')
    B.append('<div class="status">These retrospective OOF diagnostics target owner-mirror-derived labels with unauthenticated file/score associations; they are not organizer truth. Only 11 spatial blocks are reported, fewer than the registered minimum of 20. They do not establish conditional feature independence or support a public-score forecast.</div>')

    B.append("<h2>4 · What the artefact is</h2>")
    fab = audit.get("fabric") or {}
    B.append(table(["property", "value"], [
        ["file", audit.get("file") or audit.get("name")], ["sha256", (sub.get("sha256") or "")],
        ["bytes", sub.get("bytes")],
        ["emitted pixels", audit.get("pixels")],
        ["retained core (= A & C)", audit.get("retained_core_px")],
        ["additional cells relative to retained core (not global uniqueness)", audit.get("novel_px")],
        ["…of which along the recovered strike", audit.get("novel_along_strike_px")],
        ["…of which additional candidates on the same fabric", audit.get("novel_far_px")],
        ["bounded prior rasters checked", (sub.get("uniqueness") or {}).get("n_priors_checked")],
        ["eligible aligned prior rasters present / eligible", f"{prior_inv.get('eligible_inventory_rasters_present_locally')} / {prior_inv.get('eligible_grid_aligned_inventory_entries')}"],
        ["global decoded uniqueness", "not performed; unknown"],
        ["bounded local prior-union pixels not re-emitted",
         (sub.get("uniqueness") or {}).get("prior_px_dropped")],
        ["corridor excluded", f"{audit.get('corridor_excluded_m')} m"],
        ["emitted inside the corridor",
         (sub.get("writer_receipt") or {}).get("mass_within_corridor")],
        ["emitted on the catalogue", (sub.get("writer_receipt") or {}).get("mass_on_catalogue")],
        ["emitted outside the footprint",
         (sub.get("writer_receipt") or {}).get("mass_outside_footprint")],
        ["NaN pixels", (sub.get("writer_receipt") or {}).get("nan_pixels")],
        ["distinct values", (sub.get("writer_receipt") or {}).get("values")],
        ["A-only candidates with a written geological reason",
         audit.get("n_a_only_candidates_reasoned")],
        ["A-only unique coordinates checked against exact TIFF",
         f"{a_check.get('unique_coordinates')} / {a_check.get('candidate_count')}; all emitted: {a_check.get('every_candidate_is_emitted')}"],
        ["stale A-only documentation copy replaced",
         f"{(h54_review.get('a_only_reasoning') or {}).get('pre_repair_docs_copy', {}).get('candidate_count')} rows; "
         f"{(h54_review.get('a_only_reasoning') or {}).get('pre_repair_docs_copy', {}).get('non_emitted_coordinates')} were not emitted"],
        ["recovered fabric: coherence of the credited cloud", fab.get("coherence_credited_mean")],
        ["…against a matched uniform-random cloud", fab.get("coherence_random_mean")],
        ["dominant recovered strike (array deg)", fab.get("dominant_strike_deg")],
    ]))
    B.append('<p class="small muted">H54 additional-cell counts describe construction relative to the retained owner-mirror-derived core, not global decoded-pattern novelty. The local comparison was bounded; the inventory reports 377 eligible aligned prior rasters with none present for a full decoded comparison. The 200 m exclusion is a legacy selection rule, not the organizer mask: staff clarification says known pixels are masked pixel-exactly and does not authenticate zero credit for a surrounding ring.</p>')
    B.append(f'<p class="small muted">{esc(fab.get("reading") or "")}</p>')
    B.append('<h2>5 · Why the holdout did not select this</h2>'
             '<p>The whole-component hide-and-recover simulator this repo used to select on does not '
             'predict the organiser\'s score: over the 13 restored scored files, Spearman '
             'ρ(reported, simulated DTI) = −0.1045, p = 0.734. The group\'s best file on the board is '
             'the <em>worst</em> of the 13 on the instrument (lift 0.09× mass-matched random) and the '
             'file the instrument ranks first scored 0.1563. Its premise — that the hidden truth is a '
             'held-out part of the mapped catalogue — is false by §1. Recorded as '
             '<code>knowledge/03</code> N-9 and <code>IR-52-023</code>; the derivation, the confound '
             'that was checked and excluded, and the four further negative results are in '
             '<a href="../knowledge/10_revealed_preference_inverse.md">'
             '<code>knowledge/10_revealed_preference_inverse.md</code></a> and '
             '<a href="../knowledge/11_hypotheses_H54.md">'
             '<code>knowledge/11_hypotheses_H54.md</code></a>.</p>')
    B.append('<p><a href="downloads/a_only_reasoning54.csv">Download the 11,996-row A-only geological-reasoning CSV</a> · '
             '<a href="data/h54_artifact_review_2026-10-07.json">artifact review</a> · '
             '<a href="data/h54_prior_inventory_availability.json">prior-inventory availability</a></p>')
    return "".join(B)


def main() -> int:
    (DOCS / "h54.html").write_text(page("H54 audit-only", h54_body()))
    print("wrote docs/h54.html from docs/data/h54_audit.json")
    (DOCS / "h55-paired-shoulders.html").write_text(
        page("H55-1 paired shoulders: failed gate", paired_body())
    )
    print("wrote docs/h55-paired-shoulders.html from paired-shoulder receipts")
    sub = json.loads((DOCS / "data/h54_audit.json").read_text())
    bar = download_bar(sub)
    for name in ("index.html", "executive-summary.html"):
        ok = insert_bar(DOCS / name, bar)
        print(("updated" if ok else "SKIPPED (no insertion point)") + f" the H54 audit bar in docs/{name}")
    ok = insert_paired_card(DOCS / "index.html", paired_card())
    print(("updated" if ok else "SKIPPED (no insertion point)") + " the H55-1 result card in docs/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
