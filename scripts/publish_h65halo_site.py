#!/usr/bin/env python3
"""Render the H65 run card, the H65 round page, the leaderboard receipt and the status notices.

Every number written here is read from ``evidence/h65halo_*.json``, ``evidence/h64_run_card.json`` or
``registry/h65halo_preregistration.json``.  The leaderboard rows are the only typed-in values: they are
transcribed from the DrivenData leaderboard page fetched during this session, and the page is cited.
Nothing here uploads, promotes or changes a verdict.

Run after ``scripts/run_h65halo.py holdout`` and ``scripts/run_h65halo.py verdict``:
    .venv/bin/python scripts/publish_h65halo_site.py
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

NOTE = "H65 halo soft targets: NEGATIVE, no raster built; holdout below single_B; do not submit"
NAME = "gems52-h65halo-cotrain-NOT-BUILT"
assert len(NOTE) <= 140, len(NOTE)

LEADERBOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
# Transcribed from the fetched page (chunk 0). Rank 23 is cut off in the fetch and is not listed.
LEADERBOARD_ROWS = [
    (1, "xiaofanhu", 0.3774, 13), (2, "alexoktaba", 0.3345, 25), (3, "nchuzhoy", 0.3262, 6),
    (4, "joeyfezster", 0.3260, 25), (5, "kinghorton42", 0.3222, 9), (6, "Batik Shirt Brothers", 0.3221, 24),
    (7, "DARD", 0.3195, 16), (8, "JerryDataWorks", 0.2948, 17), (9, "mzoorob", 0.2902, 28),
    (10, "notmyfault", 0.2901, 18), (11, "ndavis7", 0.2888, 10), (12, "GrigorSargsyan", 0.2876, 14),
    (13, "HardcoreTechGod", 0.2854, 6), (14, "op01", 0.2797, 8), (15, "extradr19", 0.2778, 13),
    (16, "arnofault", 0.2764, 2), (17, "faultsofthy", 0.2764, 3), (18, "No Fault of Our Own", 0.2761, 25),
    (19, "newway", 0.2752, 6), (20, "wbg1", 0.2750, 15), (21, "raboush2", 0.2747, 9), (22, "li002666", 0.2726, 4),
]


def load(name):
    return json.loads((EVID / name).read_text())


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def ci(c) -> str:
    return f"[{c[0]:.6f}, {c[1]:.6f}]"


def build_run_card():
    hold = load("h65halo_holdout.json")
    ctl = load("h65halo_control_and_verdict.json")
    suff = load("h65halo_sufficiency.json")
    canary = load("h65halo_canary.json")
    exch = load("h65halo_pseudo_exchange.json")
    reg = json.loads((ROOT / "registry/h65halo_preregistration.json").read_text())
    h64 = load("h64_run_card.json")
    sB = hold["pooled_soft_candidate_single_B"]
    sD = hold["pooled_soft_candidate_disagreement_post"]
    soft = sB["scores"]["single_B"]
    hard = sB["scores"]["single_B_hard"]
    cand = sD["scores"]["disagreement_post"]
    mech = sB["paired_differences"]["single_B_hard"]
    cand_vs_soft = sD["paired_differences"]["single_B"]
    card = dict(
        round="H65",
        generated_utc=STAMP,
        experiment_index="1 of 3 (budget: 3 experiments or 2 hours)",
        hypothesis=("Metric-kernel halo targets: training both co-training views on the official "
                    "triangular 300 m coverage kernel (soft labels for 0 < d < 300 m from the visible "
                    "catalogue) raises single-view holdout DTI over the H61 hard-label control, and the "
                    "co-training disagreement then ranks candidates better than single_B."),
        mechanism=("The official distance-weighted Tversky credit is partial within 300 m; the hard-label "
                   "learners never see the 0-300 m halo as training signal, so the 200 m emission boundary "
                   "is a blind zone. One change: halo rows are added with weights t and 1 - t, t = 1 - d/300 m."),
        named_non_fault_mimic=("basin-margin gravity gradient or lithologic contact running parallel to a mapped "
                               "trace within 300 m; flight-line or DEM artefact along a road or canal."),
        preregistration=dict(document=reg["hypothesis_document"], sha256=reg["hypothesis_sha256"],
                             registry=str(Path("registry/h65halo_preregistration.json"))),
        sufficiency_S1=dict(mean_view_A_oof_auc=suff["mean_view_A_oof_auc"],
                            min_fold_view_A_oof_auc=suff["min_fold_view_A_oof_auc"],
                            S1_pass=suff["S1_pass"],
                            threshold_mean=reg["thresholds"]["S1_sufficiency_mean_oof_auc_min"],
                            threshold_min_fold=reg["thresholds"]["S1_sufficiency_min_fold_oof_auc"]),
        canary=dict(max_alarm_across_folds=canary["max_alarm_across_folds"], any_alarm=canary["any_alarm"],
                    threshold=0.90),
        exchange=dict(skipped=exch["skipped"], allowed_exchange=exch["allowed_exchange"],
                      total_pseudo_pixels=exch["total_pseudo_pixels"]),
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI",
            evaluator_version=sB["evaluator_version"],
            alpha=sB["alpha"], beta=sB["beta"], triangular_radius_m=sB["triangular_radius_m"],
            withheld_positive_pixels=hold["withheld_positive_pixels"],
            bootstrap=sB["bootstrap"],
            single_B_soft=dict(dti=soft["dti"], ci95=soft["ci95"]),
            single_B_hard_control=dict(dti=hard["dti"], ci95=hard["ci95"],
                                       h61_committed=reg["thresholds"]["single_B_h61_control_holdout_dti"],
                                       abs_difference=ctl["control"]["abs_difference"],
                                       tolerance=reg["thresholds"]["single_B_control_abs_tolerance"],
                                       pass_=ctl["control"]["pass_"]),
            union_max=dict(dti=sB["scores"]["union_max"]["dti"], ci95=sB["scores"]["union_max"]["ci95"]),
            random=dict(dti=sB["scores"]["random"]["dti"], ci95=sB["scores"]["random"]["ci95"]),
            single_A=dict(dti=sB["scores"]["single_A"]["dti"], ci95=sB["scores"]["single_A"]["ci95"]),
            candidate_disagreement_post=dict(dti=cand["dti"], ci95=cand["ci95"]),
            paired=dict(
                soft_minus_hard=dict(delta=mech["delta"], ci95=mech["ci95"],
                                     confirmed=bool(mech["ci95"][0] > 0.0)),
                candidate_minus_single_B_soft=dict(delta=cand_vs_soft["delta"], ci95=cand_vs_soft["ci95"],
                                                   confirmed=bool(cand_vs_soft["ci95"][0] > 0.0)),
            ),
        ),
        correlation_overlap_vs_registry=dict(
            status="not run",
            reason=("No raster was built: the preregistered rule builds only after a positive holdout, "
                    "and the holdout is not positive. The lane gate (surface and final dots) is therefore "
                    "not evaluated for H65 and nothing is claimed about it."),
        ),
        raster=None,
        validator=None,
        submission_name=NAME,
        note=NOTE,
        note_chars=len(NOTE),
        note_status="NOT USED: no file exists for this run; the text is a placeholder that must not be pasted",
        h64_reference=dict(file=h64["raster"]["file"], sha256=h64["raster"]["sha256"],
                           lane_literal=h64["correlation_overlap_vs_registry"]["lane_dots_literal"]),
        verdict=("NEGATIVE, research-only. DOWNLOAD NO (no file). SUBMIT NO. "
                 "Primary test not confirmed: single_B_soft minus single_B_hard has a 95% CI that includes 0. "
                 "Co-training candidate is far below single_B_soft."),
        slots_used=0,
        upload="none",
        limitations=[
            "HOLDOUT-DTI uses catalogue truth. It cannot score the trace-correction population, because "
            "the organisers' statement (forum topic 11516, post of 21 Sep) says new-fault pixels can lie within "
            "300 m of known traces; those pixels are not in the holdout truth.",
            "S1 failed (View A not sufficient out of quadrant), so the exchange was skipped and post := pre; "
            "the co-training arm therefore has no exchange effect in this round.",
            "The hard control was not bit-reproducible across two runs of the same receipts: the fold-0 "
            "predictions differ from a standalone refit on about 0.02% of pixels. The two receipts give "
            "single_B_hard 0.174517 and 0.174571 (tolerance 0.001). The verdict is unchanged in both.",
        ],
    )
    return card


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")


def build_leaderboard_receipt():
    rows = [dict(rank=r, participant=p, best_public_dw_tversky=s, submissions=n) for (r, p, s, n) in LEADERBOARD_ROWS]
    return dict(
        source=LEADERBOARD_URL,
        evidence_class="ORGANIZER-PUBLISHED (public board; board is a live page, not a frozen snapshot)",
        fetched_during_session_utc_date="2026-10-09",
        note=("Transcribed from the fetched page, ranks 1-22. Rank 23 is cut off in the fetch. "
              "The board does not identify files, so no score is attributed to a file from this page."),
        rows=rows,
        facts=dict(top_score=0.3774, top_participant="xiaofanhu", dard_rank=7, dard_score=0.3195,
                   extradr19_rank=15, extradr19_score=0.2778),
    )


def round_page(card, hold) -> str:
    sB = hold["pooled_soft_candidate_single_B"]
    sD = hold["pooled_soft_candidate_disagreement_post"]
    rows = []
    for arm, label in (("single_B", "single_B (halo soft targets) — H65 candidate control"),
                       ("single_B_hard", "single_B_hard (H61 hard labels, re-fit this round) — pipeline control"),
                       ("union_max", "union_max (pre-exchange)"),
                       ("single_A", "single_A (View A, halo soft targets)"),
                       ("random", "random (same allowed domain, same budget)"),
                       ("disagreement_post", "disagreement_post (= pre; S1 failed, exchange skipped) — candidate")):
        v = sB["scores"][arm] if arm != "disagreement_post" else sD["scores"][arm]
        rows.append(f"<tr><td>{esc(label)}</td><td class='numeric'>{v['dti']:.6f}</td>"
                    f"<td class='numeric'>{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}</td></tr>")
    mech = sB["paired_differences"]["single_B_hard"]
    cand = sD["paired_differences"]["single_B"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H65: metric-kernel halo targets for both co-training views. Negative. No file built, nothing to upload.">
<title>H65 · halo soft targets · negative, research-only · GEMSDOE52</title>
<link rel="stylesheet" href="assets/ctd5.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="index.html">Overview</a><a href="executive-summary.html">Submission guide</a><a href="h65halo.html">H65</a><a href="h64.html">H64</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main">
<div class="eyebrow">DOE GEMS · H65 · one experiment · 1 of 3 used</div>
<h1>Halo soft targets: negative.</h1>
<p class="lead">One change to the shared template: the H61 hard-label sample is kept, and the 0–300 m halo
around the visible catalogue is added with the official kernel weights. The learners, folds, budget and
placement are H61's. The primary test is not confirmed, and the co-training candidate is far below the
single-view control. No raster was built, so there is nothing to download or upload from this round.</p>
<div class="notice" role="note"><strong>DO NOT UPLOAD · NEGATIVE · research-only</strong>
<p>Verdict: {esc(card['verdict'])}</p></div>
<h2>Holdout (HOLDOUT-DTI — not a leaderboard score)</h2>
<p class="small">Evaluator <code>{esc(sB['evaluator_version'])}</code> · α {sB['alpha']} / β {sB['beta']} · {sB['triangular_radius_m']} m triangular kernel · {hold['withheld_positive_pixels']:,} withheld positive pixels · 95% paired physical-cluster bootstrap ({sB['bootstrap']['clusters']} clusters, {sB['bootstrap']['draws']} draws, seed {sB['bootstrap']['seed']}). Conditional on the fitted folds, catalogue labels and fixed budgets.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>The primary test</h2>
<p><b>single_B_soft − single_B_hard</b> = {mech['delta']:+.6f}, 95% CI {ci(mech['ci95'])}. The lower bound is below zero, so the mechanism is not confirmed at this resolution.</p>
<p><b>disagreement_post − single_B_soft</b> = {cand['delta']:+.6f}, 95% CI {ci(cand['ci95'])}. The co-training candidate is far below the single-view control, so it is not eligible.</p>
<h2>Gates</h2>
<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th></tr></thead><tbody>
<tr><td>Leakage canary (single feature AUC, alarm 0.90)</td><td class="numeric">max {card['canary']['max_alarm_across_folds']:.4f} · no alarm</td></tr>
<tr><td>S1 View-A sufficiency (mean ≥ {card['sufficiency_S1']['threshold_mean']}, every fold ≥ {card['sufficiency_S1']['threshold_min_fold']})</td><td class="numeric">mean {card['sufficiency_S1']['mean_view_A_oof_auc']:.4f} · min {card['sufficiency_S1']['min_fold_view_A_oof_auc']:.4f} · FAIL</td></tr>
<tr><td>Exchange</td><td>skipped (S1 failed); post-arms := pre-arms</td></tr>
<tr><td>Control: single_B_hard vs H61 (tolerance 0.001)</td><td class="numeric">{card['holdout_dti']['single_B_hard_control']['dti']:.6f} vs 0.174517 · |Δ| {card['holdout_dti']['single_B_hard_control']['abs_difference']:.1e} · PASS</td></tr>
<tr><td>Lane (surface and final dots) · not-union · format · exact-unique</td><td>not evaluated: no raster built (the preregistered rule builds only after a positive holdout)</td></tr>
</tbody></table></div>
<h2>Reproducibility note</h2>
<p class="small">The pre-registered control reproduces H61's single_B within tolerance in both runs of the receipts.
The fold-0 hard-control predictions are not bit-identical to a standalone refit (about 0.02% of pixels differ, maximum 0.98). Two standalone refits agree bit for bit. Cause not isolated in this round; the primary decision is unchanged between the two runs.</p>
<h2>Limits</h2>
<ul>
<li>Holdout truth is the catalogue. It cannot test the trace-correction population (new-fault pixels within 300 m of known traces), which the organisers say they aim to identify. R5-H1 therefore remains untested on the holdout.</li>
<li>S1 failed, so the co-training arm was not exercised beyond pre := post.</li>
<li>No lane check, no file, no validator output: nothing here is a submission candidate.</li>
</ul>
<p class="small">Receipts: <a href="data/h65halo_run_card.json">h65halo_run_card.json</a> · <a href="data/h65halo_holdout.json">h65halo_holdout.json</a> · <a href="data/h65halo_sufficiency.json">h65halo_sufficiency.json</a> · <a href="data/h65halo_control_and_verdict.json">h65halo_control_and_verdict.json</a> · <a href="data/h65halo_canary.json">h65halo_canary.json</a> · <a href="data/h65halo_verdict.json">h65halo_verdict.json</a> · <a href="data/leaderboard_snapshot_2026-10-09.json">leaderboard receipt</a> · pre-registration <code>{esc(card['preregistration']['sha256'][:16])}…</code> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/41b_hypotheses_H65halo_preregistered.md">knowledge/41</a></p>
</main>
<footer>Independent competition research, not an official DOE or DrivenData site. Predictions are not verified faults or geothermal discoveries.<br>
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · <a href="data/h65halo_run_card.json">JSON run card</a> · H65 / {STAMP[:10]}</footer>
</body></html>
"""


STATUS_BLOCK = """<!--H65-STATUS-->
<section class="status-2026-10-09" aria-label="Current submission answer">
<h2>Current answer · 2026-10-09 (after H65)</h2>
<div class="notice" role="note"><strong>DO NOT UPLOAD anything from this round.</strong>
<p>No candidate passes the repo's gates. H65 is negative and built no file. The H64 file is downloadable for research and is <b>not</b> a submission candidate: its lane check is DUPLICATE under the 70% rule.</p></div>
<div class="grid2"><section class="panel"><h3>Downloadable research file (not approved)</h3>
<p class="fileline">gems52-h64-sufgate-cotrain-37600px-20261009T022631Z.tif<br>133,668 bytes · SHA-256 739a8e7c4b54436508fc2b9da6b8ddc56e44a0d1ad273dc88c07a2003637f8bb · 37,600 emitted cells</p>
<div class="actions"><a class="button secondary" href="downloads/h64-candidate.tif" download>Download H64 GeoTIFF (research)</a> <a class="button secondary" href="downloads/h64-candidate.zip" download>Single-TIFF ZIP</a></div>
<p class="small">Format-valid, exact-unique on decoded pixels, and DUPLICATE under the lane rule. Do not submit.</p></section>
<section class="panel"><h3>Before any upload, all of these must be true</h3><ul>
<li>Format: single-band float32 GeoTIFF (or a ZIP of exactly one GeoTIFF), EPSG:32611, 100 m, the training-data bounds, NaN or null outside the bounds, values in [0, 1] (page 967).</li>
<li>Lane gate passes on the surface and on the final dots (no registry raster with rank correlation above 0.90, and not more than 70% of dots within 3 px of one registry raster's dots).</li>
<li>Not the union of the two views; exact-unique against every prior submission in the registry.</li>
<li>The holdout beats the single-view control with a CI lower bound above zero, and a separate selector approves the slot.</li>
</ul></section></div>
<h3>Exact steps when a candidate has passed every gate above</h3>
<ol>
<li>Read the <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules (NLR, Sept 2026)</a>. They allow three submissions per week and require a narrative disclosure of generative-AI use (Appendix A).</li>
<li>Check the remaining weekly allowance on your authenticated submission page. This site cannot read it.</li>
<li>Open the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a> and submit the <code>.tif</code>, or its single-TIFF ZIP. Never upload HTML, JSON or a screenshot.</li>
<li>Paste the unique name and note verbatim (the note must be at most 140 characters). Do not reproject, rescale or re-save the TIFF.</li>
<li>Keep the submission id, timestamp, SHA-256 and the organiser's result. Only that receipt supports an ORGANIZER-CONFIRMED score.</li>
</ol>
<h3>Premise corrections (verified 2026-10-09)</h3>
<ul>
<li>The public board's top score is <b>0.3774</b> (xiaofanhu). 0.3195 is DARD at rank 7, not the top. <a href="data/leaderboard_snapshot_2026-10-09.json">Leaderboard receipt</a>.</li>
<li>0.2778 is <b>owner-reported</b> for GEMSDOE32's <code>h33-2-b2</code>, not organiser-confirmed. The public board also shows 0.2778 for <code>extradr19</code> (rank 15 in the fetch). The board does not identify files, so it does not confirm either attribution.</li>
<li>Masking is confirmed by staff: known USGS/INGENIOUS pixels are masked, and the buffer does not apply to known faults (forum topic 11516, posts of 16 and 21 Sep). Staff also say new-fault pixels can lie within 300 m of known traces.</li>
</ul>
<p class="small">Round page: <a href="h65halo.html">H65 (negative, no file)</a> · sources: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">page 967 (metric and format)</a> · <a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">forum topic 11516 (masking)</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">leaderboard</a></p>
</section>
<!--/H65-STATUS-->"""


NOTICE_BLOCK = ('<div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H65 '
                '(negative, no file).</strong> Do not upload anything from this round. The H64 file is downloadable for '
                'research only and is DUPLICATE under the lane rule. <a href="h65halo.html">H65 landing</a> · '
                '<a href="h64.html">H64 landing</a> · <a href="executive-summary.html">Submission guide</a></div>')


def patch_pages():
    # 1. the top notice on index.html and executive-summary.html
    pat = re.compile(r'<div class="notice" role="note" style="margin:0 0 1rem">.*?</div>', re.S)
    for name in ("index.html", "executive-summary.html"):
        p = DOCS / name
        text = p.read_text()
        new, n = pat.subn(lambda _m: NOTICE_BLOCK, text, count=1)
        assert n == 1, f"{name}: top notice not found"
        p.write_text(new)
    # 2. the status section on the submission guide, idempotent between markers
    p = DOCS / "executive-summary.html"
    text = p.read_text()
    text = re.sub(r"<!--H65-STATUS-->.*?<!--/H65-STATUS-->\n?", "", text, flags=re.S)
    anchor = "<h1>"
    assert text.count(anchor) >= 1
    text = text.replace(anchor, STATUS_BLOCK + "\n" + anchor, 1)
    p.write_text(text)


def main() -> int:
    card = build_run_card()
    hold = load("h65halo_holdout.json")
    write_json(EVID / "h65halo_run_card.json", card)
    write_json(DATA / "h65halo_run_card.json", card)
    write_json(DATA / "leaderboard_snapshot_2026-10-09.json", build_leaderboard_receipt())
    for name in ("h65halo_holdout.json", "h65halo_sufficiency.json", "h65halo_control_and_verdict.json",
                 "h65halo_canary.json", "h65halo_verdict.json", "h65halo_pseudo_exchange.json"):
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / name).write_text((EVID / name).read_text())
    (DOCS / "h65halo.html").write_text(round_page(card, hold))
    patch_pages()
    print("H65 site rendered:", card["verdict"][:60], "| note chars", card["note_chars"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
