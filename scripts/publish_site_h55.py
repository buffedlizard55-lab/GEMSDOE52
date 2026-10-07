#!/usr/bin/env python3
"""Render the current public site from H55/R2 receipts and the dated official snapshot.

Does not access DrivenData, upload a submission, or claim a leaderboard outcome.
Run scripts/refresh_feed.py first so docs/data contains the current local receipts.
"""
from __future__ import annotations

from pathlib import Path
import html
import json
import re

import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
EV = ROOT / "evidence"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def esc(value) -> str:
    return html.escape(str(value))


def a(path: str, text: str | None = None) -> str:
    return f'<a href="{esc(path)}">{esc(text or path)}</a>'


def table(headers, rows, primary=None):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cls = ' class="primary"' if primary is not None and row[0] == primary else ""
        body.append("<tr" + cls + ">" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return '<div class="table-wrap"><table><thead><tr>' + head + '</tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'


def page(title: str, body: str) -> str:
    nav = "".join(a(path, label) for path, label in [
        ("index.html", "Overview"),
        ("executive-summary.html", "Submission guide"),
        ("h55.html", "H55 candidate"),
        ("validation.html", "Validation"),
        ("hypotheses.html", "Hypotheses"),
        ("forensics.html", "0.2778 autopsy"),
        ("sources.html", "Sources"),
        ("irregularities.html", "Limitations"),
        ("h53.html", "Parallel H53"),
    ])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="H55 paired potential-field edges, spatial holdout validation, a prominent research-only GeoTIFF, and source-audited limitations."><title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body><a class="skip" href="#main">Skip to evidence</a><header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{nav}</nav></header><main id="main">{body}</main><footer>Competition 306 · Fault-prediction research, not confirmed faults or geothermal vents · {a('sources.html','Sources')} · {a('irregularities.html','Limitations')} · {a('https://github.com/buffedlizard55-lab/GEMSDOE52','Code & full prompt')}</footer></body></html>'''


def download_bar(sub: dict) -> str:
    name = sub["file"]
    note = sub.get("submission_note", "")
    fmt = sub.get("format") or {}
    uni = sub.get("uniqueness") or {}
    download = sub.get("download") or f"downloads/{name}"
    zip_path = sub.get("download_zip") or f"downloads/{Path(name).stem}.zip"
    return f'''<section class="download-bar" aria-label="Current research GeoTIFF download"><div><strong>H55 research GeoTIFF — prominent download</strong><small><code>{esc(name)}</code></small><small>{int(sub.get('bytes',0)):,} bytes · single band · float32 · EPSG:32611 · {fmt.get('width','?')} × {fmt.get('height','?')} · decoded values [{esc(fmt.get('min'))}, {esc(fmt.get('max'))}] · {int(fmt.get('n_nan',0))} non-finite</small><small>format: {esc(fmt.get('ok'))} · exact decoded-pattern comparison: {esc(uni.get('canonical_pattern_unique'))} · strict support-novelty diagnostic: {esc(uni.get('support_novelty_gate_ok'))}</small><small>Protocol limit: new LoG transforms on bands 13 and 2 only · {a('data/protocol_deviation_h55.json','post-run deviation audit')}</small><small>submission note ({len(note)} / 200 chars): <code>{esc(note)}</code></small></div><a class="button" href="{esc(download)}" download>↓ Download .TIF</a><a class="button" href="{esc(zip_path)}" download>↓ Download one-TIFF .ZIP</a><a class="button" href="h55.html">Read the gate →</a></section>'''


def warning(sub: dict) -> str:
    gate = sub.get("slot_gate") or {}
    if sub.get("approved_for_weekly_slot"):
        return '<div class="status"><strong>Locally slot-eligible, not scored.</strong> No portal upload or organizer score is recorded. This local research gate is not a guarantee of leaderboard performance or organizer acceptance.</div>'
    return ('<div class="status"><strong>Research-only. Do not spend a weekly upload slot on this file.</strong> '
            + esc((gate.get("reason") or "The preregistered holdout/uniqueness gate did not pass."))
            + ' No portal upload, official score, or organizer acceptance is claimed.</div>')


def make_preview(sub: dict):
    assets = DOCS / "assets"
    assets.mkdir(exist_ok=True)
    with rasterio.open(DOCS / sub.get("download", f"downloads/{sub['file']}")) as src:
        pred = src.read(1) > 0
        footprint = src.dataset_mask() > 0
    with rasterio.open(ROOT / "data/labels.tif") as src:
        catalogue = src.read(1) == 1
    def pool(array, factor=4):
        h, w = array.shape
        padded = np.pad(array, ((0, (-h) % factor), (0, (-w) % factor)))
        return padded.reshape(padded.shape[0] // factor, factor, padded.shape[1] // factor, factor).max((1, 3))
    fp, known, new = pool(footprint), pool(catalogue), pool(pred)
    rgb = np.full(fp.shape + (3,), (237, 241, 233), dtype=np.uint8)
    rgb[fp] = (217, 226, 215)
    rgb[known & fp] = (74, 113, 151)
    rgb[new & fp] = (202, 133, 57)
    im = Image.fromarray(rgb)
    draw = ImageDraw.Draw(im)
    draw.line((35, 60, 35, 24), fill=(24, 51, 46), width=3)
    draw.polygon([(35, 19), (29, 30), (41, 30)], fill=(24, 51, 46))
    draw.text((30, 6), "N", fill=(24, 51, 46))
    im.save(assets / "prediction-h55.png")


def main():
    sub = load_json(EV / "submission_h55.json")
    deviation = load_json(EV / "protocol_deviation_h55.json")
    if deviation.get("preregistration_sha256_at_validation") != sub.get("preregistration_sha256"):
        raise ValueError("post-run protocol audit does not match the H55 preregistration hash")
    if deviation.get("holdout_result_for_implemented_subset", {}).get("gate_passed") is not False:
        raise ValueError("protocol audit must preserve the failed implemented-subset gate")
    hold = load_json(EV / "holdout_h55.json")
    indep = load_json(EV / "independence_h55.json")
    exchange = load_json(EV / "pseudo_exchange_h55.json")
    source = load_json(EV / "source_review_h55.json")
    source_date = str(source.get("generated_utc") or "date unavailable")[:10]
    board_path = DATA / "leaderboard.json"
    board = load_json(board_path) if board_path.exists() else load_json(ROOT / "registry/leaderboard_snapshot_2026-10-07.json")
    board_rows = board.get("rows") or []
    board_date = str(board.get("fetched_utc") or board.get("observed_utc") or "date unavailable")[:10]
    leader_score = board.get("top")
    if leader_score is None and board_rows:
        leader_score = board_rows[0].get("score")
    reported_best = board.get("owner_best_reported")
    reference_row = next((row for row in board_rows if reported_best is not None
                          and abs(float(row.get("score", float("inf"))) - float(reported_best)) < 1e-9), None)
    dard_row = next((row for row in board_rows if str(row.get("team", "")).casefold() == "dard"), None)
    make_preview(sub)
    bar = download_bar(sub)
    fail = warning(sub)
    candidate = hold["candidate"]
    best = hold["best_comparable_baseline"]
    lift = hold["mean_dti_lift"]
    positive = hold["positive_folds"]
    budget = sub["budget"]
    unique = sub["uniqueness"]
    current_link = a("https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/", "official DrivenData leaderboard")
    leader_text = f"{float(leader_score):.4f}" if leader_score is not None else "not available"
    if reference_row:
        reported_reference = (f"The brief-reported value {float(reported_best):.4f} appears for participant "
                              f"{esc(reference_row.get('team','unknown'))} at rank {esc(reference_row.get('rank','unknown'))}; "
                              "the page shows no file hash or score-to-H33 mapping.")
    else:
        reported_reference = (f"The brief-reported score {esc(reported_best if reported_best is not None else 'unknown')} "
                              "has no matching row in this snapshot; no file mapping is verified.")
    dard_reference = (f"DARD appears at rank {esc(dard_row.get('rank','unknown'))} with {float(dard_row['score']):.4f}."
                      if dard_row else "DARD is not listed in this snapshot.")

    # Overview / landing page.
    overview = f'''{bar}<div class="eyebrow">H55 · preregistered potential-field edge test · board observation {esc(board_date)}</div><h1>One-click research TIFF.<br>Evidence before upload.</h1><p class="lede">A newly fitted gravity–RTP signed-LoG edge-pair model was compared with the surface-only baseline on spatially blocked, whole-component folds. The local artifact is new and format-checked; the scientific promotion gate failed.</p>{fail}<div class="grid"><div class="card"><div class="metric">{budget:,}</div><div class="label">metric-placed candidate pixels</div></div><div class="card"><div class="metric">{hold['means'][candidate]:.6f}</div><div class="label">mean local catalogue-holdout DTI</div></div><div class="card"><div class="metric">{lift:+.6f}</div><div class="label">paired lift vs {esc(best)} · {positive}/4 folds positive</div></div><div class="card"><div class="metric">0 / 3</div><div class="label">competition slots used / weekly website limit</div></div></div><div class="two"><div><h2>What H55 computes</h2><p>At one- and three-pixel scales, signed scale-normalized Laplacian-of-Gaussian responses and local sign reversals are computed from gravity band 13 and RTP magnetic band 2. Co-located edge responses are weighted by axial normal agreement; a separate interaction conditions them on modelled cover (band 15) and slope (band 19). Edges can be lithologic contacts, intrusions, survey seams or processing artifacts—not confirmed faults.</p><div class="status"><strong>Protocol-fidelity limitation.</strong> The frozen H55-1 feature list included new LoG transforms for bands 13/11/18 and 2/9; the implemented transform covers only bands 13 and 2. Bands 11/18/9 remain raw or pre-existing R2 features. The reported gate therefore applies to this narrower implementation, not the complete registered transform set. {a('data/protocol_deviation_h55.json','See the post-run deviation receipt')}.</div><p><strong>The implemented H55 variant did not clear its frozen +0.005 / 3-of-4 gate.</strong> Its mean local DTI is {hold['means'][candidate]:.6f}; the strongest comparable baseline ({esc(best)}) is {hold['means'][best]:.6f}. This is known-catalogue hide/recover, not an estimate of hidden-label or leaderboard performance.</p><div class="actions">{a('h55.html','H55 method and artifact →')} {a('validation.html','Every fold and co-training diagnostic →')}</div><h2>Uniqueness scope</h2><p>{unique['n_priors_checked']} accessible aligned prior rasters were checked by decoded values. Canonical pattern unique: <strong>{esc(unique['canonical_pattern_unique'])}</strong>. Strict ≥20% support novelty: <strong>{esc(unique['support_novelty_gate_ok'])}</strong>. The latter remains a failed slot diagnostic because an all-prior union is saturated by dense/diagnostic layers; this is not silently waived. The linked inventory is finite and does not include private, unlinked or inaccessible files.</p>{a('data/uniqueness_h55.json','Open uniqueness audit →')}<h2>Leaderboard, dated</h2><p>On {esc(board_date)} the official public board snapshot showed a leader at <strong>{esc(leader_text)}</strong>. {reported_reference} {current_link}. Automated polling is disabled by source policy, so this is a dated observation rather than a live feed.</p>{a('feed.html','Open local evidence feed →')}</div><figure><img src="assets/prediction-h55.png" alt="North-up overview of the H55 research predictions, mapped catalogue, and sample footprint."><figcaption>H55 decoded TIFF · proposals amber, known catalogue blue, footprint grey-green. Downsampled for display; pixels are not expert-verified faults or vents.</figcaption></figure></div><h2>A-only geology is explicit, not certified</h2><p>{sub['view_comparison']['a_only_reasoning']['rows']:,} emitted H55 pixels fell in the training-reference A-confident / B-abstaining stratum. Each has coordinates, feature values, alternate explanations and a verification caveat.</p>{a('downloads/'+sub['view_comparison']['a_only_reasoning']['file'],'Download the per-pixel A-only reasoning CSV →')}<p class="small">Core input rasters match owner-side SHA pins, not independently authenticated organizer bytes. No new external GDR data, radiometrics, prior-submission pixels or hidden labels were used as model inputs.</p>'''
    (DOCS / "index.html").write_text(page("Fault prediction, evidence first", overview))

    # Dedicated H55 method/release page.
    fmt = sub["format"]
    release = f'''{bar}<div class="eyebrow">H55-1 · release receipt</div><h1>Paired-edge features,<br>tested against a hard control.</h1>{fail}<p class="lede">This is a single-band research GeoTIFF from a fresh model fit. It is not a copied, renamed, re-compressed, or unioned prior prediction. No official score is available because the portal was not used.</p><h2>What was computed</h2><ol><li>Read 1-based training-feature bands 13 (isostatic gravity), 2 (RTP magnetics), 15 (modelled cover/basement depth) and 19 (slope); the R2 structural-contrast control retains its original inputs.</li><li>For σ=1 and 3 pixels, normalized-convolution smooth each potential-field surface; compute the signed scale-normalized response <code>−σ²·gaussian_laplace</code>; mark a crossing where a 3×3 neighborhood has both negative and positive LoG values; weight it by gradient magnitude per metre.</li><li>At σ=3, pair gravity and RTP edge responses using <code>sqrt(Eg·Em) × |nG·nM|</code>. A separate interaction multiplies that by <code>log1p(max(cover,0)) / (1 + max(slope,0)/10)</code>. The feature support was eroded by the registered 36 pixels; folds keep an 80-pixel training/evaluation buffer.</li><li>Fit the frozen 120-iteration histogram-gradient-boosting learner on each registered training split; place the 37,654-cell global budget with the repository's triangular 300 m expected-max-coverage greedy. This is a coverage surrogate—not an estimate of expected leaderboard DTI.</li><li>Re-open the written TIFF and compare decoded values, format, all supplied prior predictions and a same-budget View-A/View-B maximum control.</li></ol><div class="status"><strong>Post-run protocol audit.</strong> The registry lists signed-LoG transforms on bands 13/11/18 and 2/9, while this implementation applies the new transforms only to bands 13 and 2. The inherited R2 structural-contrast model includes bands 11/18/9 as raw/pre-existing features, but does not apply these H55 transforms to them. The holdout and TIFF describe the narrower implementation; the complete registered transform set was not tested. {a('data/protocol_deviation_h55.json','Machine-readable deviation record')}.</div><h2>Written-byte format checks</h2>{table(["check","measured result"],[["file",f"<code>{esc(sub['file'])}</code>"],["SHA-256",f"<code>{esc(sub['sha256'])}</code>"],["storage",f"{int(sub['bytes']):,} bytes · 1 band · {esc(fmt['dtype'])}"],["grid",f"{fmt['width']} × {fmt['height']} · {esc(fmt['crs'])} · 100 m · exact sample transform/bounds"],["raw decoded range",f"[{fmt['min']}, {fmt['max']}] · finite pixels {fmt['width']*fmt['height']:,} · NaN/Inf {fmt['n_nan']}"],["validity mask","internal GeoTIFF mask matches the sample footprint; outside-footprint raw values are finite zeros"],["format check",f"<strong>{esc(fmt['ok'])}</strong> · local format/range check, not proof of portal acceptance"],["note",f"{sub['submission_note_chars']} / 200 chars · <code>{esc(sub['submission_note'])}</code>"]])}<p><strong>Range error:</strong> the actual saved file—not an in-memory array—was read back and has raw values in [0,1], no NaN/Inf, one float32 band and the exact sample template. No upload was performed; only the organizer can confirm portal acceptance.</p><h2>Not a max/union</h2><p>The emitted field differs from the matched-budget pointwise max of H55 View A and View B: {sub['view_comparison']['matched_budget_max_union']['candidate_only']:,} candidate-only and {sub['view_comparison']['matched_budget_max_union']['union_only']:,} control-only pixels. The max field is retained as a diagnostic and was not the candidate.</p><h2>Audit files</h2><ul><li>{a('data/holdout_h55.json','four-fold spatial holdout')}</li><li>{a('data/independence_h55.json','negative-error block independence diagnostic')}</li><li>{a('data/pseudo_exchange_h55.json','buffered whole-segment pseudo-label comparison')}</li><li>{a('data/uniqueness_h55.json','per-prior decoded-value comparisons')}</li><li>{a('downloads/'+sub['view_comparison']['a_only_reasoning']['file'],'A-only geology CSV')}</li><li>{a('downloads/'+Path(sub['file']).stem+'-audit.json','full on-disk receipt')}</li><li>{a('../knowledge/12_h55_hypotheses_preregistered.md','frozen hypothesis ranking and validation plan')}</li></ul><p>AI-use disclosure for a future narrative: {a('../knowledge/13_ai_use_h55.md','read the exact statement and limits')}.</p>'''
    (DOCS / "h55.html").write_text(page("H55 research GeoTIFF and release receipt", release))

    # Validation table from actual JSON, no manually copied fold scores.
    fold_ids = [f["fold"] for f in hold["folds"]]
    labels = {
        "view_A": "Baseline A · potential/subsurface",
        "view_B": "Baseline B · surface-only",
        "R2_structural_contrast": "R2 structural contrast",
        "H55_view_A": "H55 View A · edge-augmented",
        "H55_structural_contrast": "H55 primary · edge-pair contrast",
        "H55_A_B_max_union_control": "Diagnostic · A/B max-union field",
        "H55_disagreement_router_control": "Diagnostic · disagreement router",
    }
    arms = list(hold["folds"][0]["arms"])
    rows = []
    for arm in arms:
        value_by_fold = [f["arms"][arm]["dti"] for f in hold["folds"]]
        cells = [f"{v:.6f}" for v in value_by_fold]
        rows.append([esc(labels.get(arm, arm)), *cells, f"<strong>{hold['means'][arm]:.6f}</strong>"])
    rows.insert(0, ["NW", "NE", "SW", "SE", "Mean"])
    fold_table = table(["model / control", "NW", "NE", "SW", "SE", "Mean local DTI"], rows[1:], primary=labels["H55_structural_contrast"])
    diffs = hold["paired_differences"]
    validation = f'''{bar}<div class="eyebrow">Four fixed spatial folds · catalogue hide/recover</div><h1>The edge idea improved a little.<br>Not enough to promote.</h1>{fail}<p>Whole original 8-connected catalogue components are assigned to four contiguous quadrants. The held component and 80-pixel Euclidean buffer are excluded from training. Same learner family, feature-support erosion, training-row seed policy and 37,654-pixel matched global budget as the registered R2 comparison. Truth is used only for holdout scoring, never for fitting or placement.</p><div class="status"><strong>Scope note:</strong> the H55 LoG transforms executed for this report use gravity band 13 and RTP band 2 only. The preregistered list also named bands 11, 18 and 9; those remain raw/pre-existing R2 features here. This is a measured result for the narrower implementation, not the complete registered H55-1 transform set. {a('data/protocol_deviation_h55.json','Open the deviation receipt')}.</div>{fold_table}<p>Best comparable single-view/learned baseline: <strong>{esc(best)}</strong> (mean {hold['means'][best]:.6f}). H55 paired fold differences: {', '.join(f'{x:+.6f}' for x in diffs)}. Mean lift <strong>{lift:+.6f}</strong>; positive in <strong>{positive}/4</strong>. Required: at least +0.005 mean and ≥3/4 positive. Both conditions fail. No score forecast follows from this proxy experiment.</p><h2>Co-training assumption check</h2><p>{indep['n_negative_predictions']:,} finite held-out catalogue-zero proxy-negative predictions in {indep['n_blocks']:,} 50×50 blocks. Maximum absolute correlation {indep['max_abs_correlation']:.6f}, below the preregistered 0.60 rejection threshold. This is only a weak-dependence diagnostic; it does not prove view sufficiency or conditional independence.</p>{table(["OOF negative error","Pearson","tie-aware Spearman","blocks"],[["Negative MSE",f"{indep['tests']['negative_mean_squared_error']['pearson']:.6f}",f"{indep['tests']['negative_mean_squared_error']['spearman']:.6f}",str(indep['tests']['negative_mean_squared_error']['n'])],["False-positive rate",f"{indep['tests']['negative_false_positive_rate']['pearson']:.6f}",f"{indep['tests']['negative_false_positive_rate']['spearman']:.6f}",str(indep['tests']['negative_false_positive_rate']['n'])]])}<h2>Buffered whole-segment pseudo-label exchange</h2><p>One separate round was gated by the negative-error diagnostic. Whole connected proposals were confined to one 50-pixel block, restricted to training pixels, excluded near visible catalogue labels and held 80 pixels from evaluation. This did not enter the primary H55 output.</p>{exchange_table(exchange)}<p>View B after receiving H55-A pseudo labels: mean {exchange_mean(exchange,'view_B_from_H55_A'):+.6f} over baseline across four folds ({exchange_count(exchange,'view_B_from_H55_A')}/4 positive); the mean absolute DTI is {exchange_abs_mean(exchange,'view_B_from_H55_A'):.6f}. This is below the +0.005 promotion bar. Sending B labels into H55 View A lowered mean DTI by {exchange_mean(exchange,'view_A_h55_from_B'):+.6f} ({exchange_count(exchange,'view_A_h55_from_B')}/4 positive). Co-training was therefore not used in the emitted primary.</p><h2>Interpretation</h2><p>The results show a modest, heterogeneous fold change, not validated fault discovery. H55 did best in the southeast held region and lost relative to View B in two other folds. The local known-fault catalogue may omit real faults, so catalogue-zero proxies can be mislabeled; four folds do not establish statistical or leaderboard significance.</p><p>{a('data/holdout_h55.json','full metric components and fold receipts')} · {a('data/independence_h55.json','all negative-error blocks')} · {a('data/pseudo_exchange_h55.json','all accepted/rejected pseudo proposals')}</p>'''
    (DOCS / "validation.html").write_text(page("H55 spatial validation and failed promotion gate", validation))

    # Hypothesis ranking registered before H55 code/feature run.
    hypotheses = f'''{bar}<div class="eyebrow">Four hypotheses registered before implementation</div><h1>Geology sets the test.<br>Holdout sets the decision.</h1><p>Ranks and expected-value labels below were planning judgments, not measured score gains. H55-1 is the only idea implemented in this round. “Not tried in this repository” is not a claim of worldwide novelty.</p><div class="status"><strong>Post-run protocol fidelity:</strong> the frozen H55-1 list includes LoG transforms for bands 13/11/18 and 2/9, but the actual transform covered only bands 13 and 2; raw bands 11/18/9 remained in inherited R2 feature sets. The holdout is for that narrower implementation, not the complete listed hypothesis. {a('data/protocol_deviation_h55.json','Read the audit')}.</div>{table(["Rank","hypothesis / layers","physical signature and alternative","cost / status"],[
        ["1 · H55-1","Bands 13/11/18 gravity, 2/9 RTP magnetics, 15 cover, 12/19 surface control","Scale-normalized signed LoG zero-crossing pairs with local axial-normal agreement, conditioned on cover and weak surface expression. Contacts, intrusions, processing seams remain alternatives.","Medium · partial implementation (new LoG only on 13/2); +0.000546 vs B, 2/4 positive; failed"],
        ["2 · H55-2","Official GDR 1391 well/spring temperature/chemistry + paleo-sinter/tufa points and core potential-field edge context","Independent manifestations could occur on geothermal-fluid pathways, but are not faults or complete coverage. Raw archives could not be retrieved here; not used or promoted as viable for this release.","High · blocked by archive access/provenance"],
        ["3 · H55-3","Bands 4/7/8 scalar strain fields with gravity, magnetics and cover","Signed spatial shear/dilatation gradients co-located with low-relief potential-field edges; model fields are smoothed and not independent at 100 m.","Low–medium · not implemented"],
        ["4 · H55-4","Bands 12/19 DEM/slope, signed curvature, bands 2/3/9/13/18 potential fields","Graph-segment surface breaks; bridge a gap only when potential-field edge sign/normal continue. Redundant with earlier gap/stepover ideas; no global novelty claim.","Medium · not implemented"],
    ])}<p>Full layer definitions, decision rules and source boundary: {a('../knowledge/12_h55_hypotheses_preregistered.md','knowledge/12_h55_hypotheses_preregistered.md')} · {a('data/h55_preregistration.json','frozen JSON parameters')}</p><h2>Why the source-boundary matters</h2><p>USGS Death Valley/Amargosa reports support the broad possibility of concealed-fault gravity/magnetic expression, while documenting fluvial and lithologic alternatives. They do not validate these H55 pixels or transfer a score. The public competition task is fault prediction; a fault raster is not a geothermal-vent map.</p>{a('sources.html','Review linked primary sources →')}'''
    (DOCS / "hypotheses.html").write_text(page("Preregistered H55 geological hypotheses", hypotheses))

    # Executive summary: exact UI instructions, with an explicit warning that current candidate is not for upload.
    guide = f'''{bar}<div class="eyebrow">Executive summary · submission guide</div><h1>Download is one click.<br>Promotion is not assumed.</h1>{fail}<p class="lede">The current TIF is downloadable for review and reproduction, but it is research-only. Do not spend a limited weekly slot on it. No portal interaction has occurred.</p><div class="status"><strong>Protocol scope:</strong> this output uses the implemented subset of H55-1; the registered LoG transforms for bands 11, 18 and 9 were omitted. The measured gate is not a validation of the complete registered feature set. {a('data/protocol_deviation_h55.json','Read the post-run audit')}.</div><div class="card"><h2>Current artifact identity</h2><p><strong>File:</strong> <code>{esc(sub['file'])}</code></p><p><strong>SHA-256:</strong> <code>{esc(sub['sha256'])}</code></p><label for="submission-note">Current research note ({sub['submission_note_chars']} / 200 chars)</label><textarea id="submission-note" readonly>{esc(sub['submission_note'])}</textarea><button data-copy="submission-note">Copy note</button><p>{a(sub.get('download') or 'downloads/'+sub['file'],'Download the single-band .TIF')} · {a(sub.get('download_zip') or 'downloads/'+Path(sub['file']).stem+'.zip','Download ZIP containing exactly one GeoTIFF')}</p></div><h2>When a future candidate passes its gate, submit it</h2><ol><li>Open the official {a('https://www.drivendata.org/competitions/306/competition-doe-gems/','GEMS competition')} and sign in to the participant account. This repository cannot log in or upload on your behalf.</li><li>Choose the competition's new-submission/upload control, then select either the `.tif` file or the `.zip` containing exactly one GeoTIFF.</li><li>Paste that artifact's unique identifying note into the optional Note field. The current H55 note above is for provenance, not upload approval.</li><li>Review the selected file and note, submit through the website, and retain the portal's receipt/score. No score exists until the organizer returns one.</li><li>Because the official rules page states at most three automated-score submissions per week and one final file across both rounds, keep a slot for a candidate that has passed preregistered validation and format checks.</li></ol><h2>Why this file avoids the reported [0,1] range error</h2><p>The exact saved file was re-opened and decoded. It is one `float32` band on the exact sample CRS/shape/geotransform. Decoded raw minimum is <strong>{fmt['min']}</strong>, maximum is <strong>{fmt['max']}</strong>; non-finite count is <strong>{fmt['n_nan']}</strong>. The GeoTIFF's internal validity mask matches the sample footprint, while raw outside-footprint values remain finite zero. This is a local check, not proof of the organizer portal's undocumented validator or actual acceptance.</p><h2>Required narrative disclosure</h2><p>The official rules require the extent and manner of generative-AI use to be disclosed if applicable. This work used AI for repository/source review, hypothesis drafting, code assistance and documentation; scripts executed numerical analyses and release checks. Full wording and limits: {a('../knowledge/13_ai_use_h55.md','H55 AI-use disclosure')}.</p><h2>Official checks, no automation</h2><ul><li>{a('https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/','problem description and submission metric')}</li><li>{a('https://docs.nlr.gov/docs/fy26osti/96647.pdf','official competition rules PDF')}</li><li>{a('feed.html','dated leaderboard and local-evidence feed')}</li></ul><p>No automatic portal upload, leaderboard scraping, score attribution or slot use is performed by this project.</p>'''
    (DOCS / "executive-summary.html").write_text(page("Executive summary and submission guide", guide))

    # Method page.
    method = f'''{bar}<div class="eyebrow">Methods and data boundary</div><h1>Two views.<br>Evidence, not certainty.</h1>{fail}<h2>Views</h2><ul><li><strong>A · potential/subsurface:</strong> core gravity, RTP magnetic, strain/seismic and modelled cover/basement bands, plus H55 local gravity/RTP signed LoG channels.</li><li><strong>B · surface:</strong> detrended DEM, slope, signed curvature and local surface context. The 19-band training cube contains no radiometric band; no radiometric channel was invented.</li></ul><h2>H55 edge transform</h2><p>In the implemented variant, gravity band 13 and RTP magnetic band 2 are transformed at σ=1,3 pixels: normalized-convolution Gaussian smoothing is followed by <code>−σ²·gaussian_laplace</code> and an 8-neighbour 3×3 sign-reversal response. Gradient magnitude is calculated per metre. At σ=3, gravity/RTP edge responses are paired by the absolute dot product of their unit gradient normals. A cross-view term multiplies that pair by a cover/slope factor. These features are deterministic and label-free; they can detect contacts or artifacts as well as faults.</p><p><strong>Protocol deviation:</strong> the preregistration also named bands 11, 18 and 9 for new LoG transforms, but those channels were not transformed. They remain raw/pre-existing R2 features. The measured result is for the narrower implementation only; see the {a('data/protocol_deviation_h55.json','post-run audit')}.</p><h2>Spatial tests</h2><p>Four contiguous quadrants hold out complete original 8-connected label components and tails. An 80-pixel buffer exceeds the registered 36-pixel transform support. Negative-error correlations use actual out-of-fold predictions on catalogue-zero proxy negatives in 50×50 blocks. Missing/degenerate correlations disable exchange; a low correlation only permits a separate pseudo-label experiment and does not prove conditional independence.</p><h2>Placement and output</h2><p>The fixed 37,654-pixel placement greedily maximizes a triangular 300 m expected max-coverage surrogate. The greedy field uses a model-derived proxy density and no held-out labels, public leaderboard scores, or prior prediction pixels. It is <strong>not</strong> a guaranteed optimizer of the hidden DTI. The written candidate is single-band float32, [0,1], exact template grid, with no NaN/Inf.</p><h2>Not established</h2><ul><li>That catalogue-zero cells are truly fault-free.</li><li>That hidden evaluation faults are distributed like known faults.</li><li>That weak blockwise error correlations prove the co-training assumptions.</li><li>That the H33 owner-reported score is attributable to a particular TIFF.</li><li>That a local range/format check guarantees portal acceptance or a public score.</li><li>That gravity/magnetics, cover and DEM values have independent organizer-byte authentication.</li></ul>{a('validation.html','Full spatial holdout results →')} · {a('sources.html','Primary sources and access outcomes →')}'''
    (DOCS / "method.html").write_text(page("H55 method and limitations", method))

    # Irregularities are first-class outputs, not buried.
    irregularities = f'''{bar}<div class="eyebrow">Errors, stale claims, and unresolved limits</div><h1>Flagged for review.<br>Nothing silently promoted.</h1>{fail}<ul><li><strong>H55 slot gate failed for the implemented subset.</strong> Mean lift {lift:+.6f} vs the strongest comparable baseline; {positive}/4 positive folds, below +0.005 and 3/4.</li><li><strong>Post-run protocol discrepancy.</strong> The registration includes new LoG channels on bands 13/11/18 and 2/9, but the code computes them only for 13 and 2. The failed result is for that narrower implementation; the full registered transform set was not tested. Preserve the original preregistration and do not tune the omitted features on the same folds. {a('data/protocol_deviation_h55.json','Deviation receipt')}.</li><li><strong>Co-training did not qualify for the output.</strong> OOF error correlations were low enough to run a separate trial, but this is not conditional-independence proof. Exchange helped only some View-B folds and hurt View A; no exchange entered the primary TIFF.</li><li><strong>Leaderboard attribution remains unresolved.</strong> On the {esc(board_date)} snapshot, the leader was {esc(leader_text)}; {dard_reference} {reported_reference} The public board does not identify any TIFF or map its scores to repository artifacts.</li><li><strong>H33 causal explanation remains unproven.</strong> Local decoded-pixel comparison confirms a flank-pruning relation to the cited base. It cannot show that those 2,545 deletions caused the reported score.</li><li><strong>Support-novelty diagnostic failed.</strong> The strict ≥20% support-novelty measure uses a saturated union containing dense/diagnostic prior rasters. Exact decoded-value uniqueness and the non-union control are reported separately; strict slot approval is not waived.</li><li><strong>Inventory finite and refreshed.</strong> 395 distinct linked TIFF URLs, 389 aligned single-band eligible priors downloaded; four linked TIFFs were not eligible predictions and two old links no longer resolve. No supplied links for 53GEMSDOE or 54GEMSDOE. Private/unlinked/external files remain unchecked.</li><li><strong>Input authenticity limitation.</strong> Restored core rasters match owner-side SHA-256 pins, but are not independently authenticated to organizer bytes.</li><li><strong>GDR data could not be obtained here.</strong> GDR 1391 metadata is public; well/spring archive TLS failed and paleo-geothermal ZIP returned HTTP 500. Neither raw archive nor derivative was used.</li><li><strong>No radiometric bands in the competition cube.</strong> The available `training_features.tif` has 19 bands and none is radiometric.</li><li><strong>The public feed is dated, not live.</strong> This session manually fetched the official public board on 2026-10-07. Automated DrivenData access is disabled absent written permission. No automatic score fetch or portal upload occurs.</li><li><strong>No organizer evaluation.</strong> No H55 file was uploaded, no weekly slot was used, and the receipt's official score is null.</li><li><strong>Task is fault mapping, not vent mapping.</strong> Neither a fault candidate nor a geothermal manifestation alone verifies a geothermal vent.</li></ul><h2>Next steps, ordered</h2><ol><li>Keep the failed H55 result as a negative/weak positive; do not tune it against these same four folds.</li><li>Before a new candidate, preregister an untouched confirmation split and refit the historical incumbent's actual generative algorithm on identical folds.</li><li>Authenticate core input bytes against organizer-provided data when access/terms permit.</li><li>Obtain and hash original official GDR archives before any H55-2 test; if retrieval remains blocked, keep it untested.</li><li>Request independent geologic review of A-only candidates before any scientific or field claim.</li><li>Only consider a weekly upload after the frozen DTI, fold, format, uniqueness and non-union gates pass.</li></ol><p>{a('data/source_review_h55.json','Open source/access audit')} · {a('data/review_execution_r2.json','Prior R2 review receipt')} · {a('../knowledge/06_provenance_and_irregularities.md','Full carried-forward irregularities')}</p>'''
    (DOCS / "irregularities.html").write_text(page("Irregularities, limitations and next steps", irregularities))

    # Source catalogue: official/primary links and exact scope.
    sources = source["sources"]
    src_rows = []
    for s in sources:
        src_rows.append([a(s["url"], s["name"]), esc(s.get("source_class", "")),
                         esc(s.get("verified_takeaway", "")), esc(s.get("scope_limit") or s.get("access_status") or s.get("automated_access") or "" )])
    source_page = f'''{bar}<div class="eyebrow">Primary-source ledger · review {esc(source_date)}</div><h1>Links, uses,<br>and known boundaries.</h1>{table(["source","class","verified takeaway","limit / access"],src_rows)}<h2>Owner-linked TIFF inventory</h2><p>{source['prior_raster_refresh']['distinct_linked_tiff_urls']} distinct linked TIFF URLs were re-enumerated; {source['prior_raster_refresh']['eligible_aligned_single_band_tiffs']} decoded as aligned single-band competition-grid rasters and all eligible bytes are now local under ignored <code>data/review/</code>. Four linked TIFFs were not prediction-format priors; two repository blobs could not be found. Links not supplied for 53/54 and private/unlinked storage are outside the inventory. Owners' reported public scores are not authenticated file-to-score mappings.</p><p>{a('data/source_review_h55.json','Source-review JSON')} · {a('data/prior_inventory_r2.json','Every prior URL, bytes/hash, and alignment result')} · {a('data/leaderboard.json','Dated official leaderboard snapshot')}</p><p>The GDR source list is discoverable, but the advertised well/spring and paleo-feature archives could not be retrieved from this sandbox. No third-party GDR data entered the current model.</p>'''
    (DOCS / "sources.html").write_text(page("Verified sources and provenance limits", source_page))

    # Feed landing page. The data files are refreshed by scripts/refresh_feed.py.
    feed = f'''{bar}<div class="eyebrow">Evidence feed · external freshness is explicit</div><h1>Local receipts update.<br>Official snapshot stays dated.</h1><div class="live-feed" id="feed">Loading local feed metadata.</div><p>DrivenData automated access is disabled by source policy without written permission. The official leaderboard observation shown here was fetched manually on {esc(board_date)}, not auto-polled. Regenerating this page never changes the board's original observation timestamp.</p><ul><li>{a('data/feed.json','Feed status JSON')}</li><li>{a('data/leaderboard.json','Official dated leaderboard snapshot')}</li><li>{a('data/submission.json','Current artifact receipt')}</li><li>{a('data/r2_preregistration.json','R2 registration')}</li><li>{a('data/h55_preregistration.json','H55 registration')}</li></ul>'''
    (DOCS / "feed.html").write_text(page("Dated evidence feed", feed))

    # Top-level all-downloads page, refreshed after assets are staged.
    (DOCS / "downloads/index.html").write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Audited research downloads · GEMSDOE52</title><link rel="stylesheet" href="../style.css"></head><body><main><p>{a('../index.html','← Overview')}</p><h1>Current research download</h1>{warning(sub)}<p>{a(sub.get('download') or sub['file'],'Download H55 .TIF')} · {a(sub.get('download_zip') or (Path(sub['file']).stem+'.zip'),'single-TIFF ZIP')} · {a(sub['view_comparison']['a_only_reasoning']['file'],'A-only reasoning CSV')} · {a(Path(sub['file']).stem+'-audit.json','release audit')}</p><h2>Historical artifacts</h2><p>Older H53/H54/R2 rasters and their receipts remain available for reproduction/audit; none replaces the current H55 research artifact's failed gate. No prior TIFF was used as H55 output.</p><p>See {a('../validation.html','validation')} and {a('../irregularities.html','limits')} before downloading.</p></main></body></html>''')

    # Reframe older pages so they cannot look like the current submission.
    historical_bar = ('<div class="status"><strong>Historical H54 analysis — not the current candidate.</strong> '
                      'The scenario values on this page are not forecasts or organizer scores. H54 is retained '
                      'for audit; the current H55 TIFF is research-only and failed its frozen gate. '
                      '<a href="index.html">See current status</a> · <a href="validation.html">See H55 holdout</a>.</div>')
    h54_path = DOCS / "h54.html"
    if h54_path.exists():
        old = h54_path.read_text()
        old = re.sub(r'<!--H54BAR-->.*?<!--/H54BAR-->', historical_bar, old, flags=re.S)
        old = old.replace('<title>H54 revealed preference ·', '<title>Historical H54 revealed-preference analysis ·')
        old = old.replace('<a href="h54.html">H54&nbsp;revealed-preference</a>', '<a href="h55.html">Current H55 research</a>')
        if '<main id="main">' in old and 'Historical H54 analysis — not the current candidate' not in old:
            old = old.replace('<main id="main">', '<main id="main">' + historical_bar, 1)
        h54_path.write_text(old)

    forensics_path = DOCS / "forensics.html"
    if forensics_path.exists():
        old = forensics_path.read_text()
        old = re.sub(r'<(?:div|section) class="download-bar".*?(?:</div></div>|</section>)<div class="eyebrow">', bar + '<div class="eyebrow">', old, count=1, flags=re.S)
        if reference_row:
            board_claim = (f"The official {board_date} board lists participant {esc(reference_row.get('team','unknown'))} "
                           f"at rank {esc(reference_row.get('rank','unknown'))} with {float(reference_row['score']):.4f}; "
                           f"{current_link} provides no file hash or H33 attribution. The score-to-file link is unverified.")
        else:
            board_claim = (f"The official {board_date} snapshot has no matching row for the brief-reported value "
                           f"{esc(reported_best if reported_best is not None else 'unknown')}; {current_link} "
                           "contains no H33 file attribution.")
        board_pattern = (r'(?:The brief attributes 0\.2778 to H33\.|The dated official board lists )'
                         r'.*?(?:The H33 attribution is unverified\.|The H33 filename attribution is unverified\.|The score-to-file link is unverified\.|contains no H33 file attribution\.)')
        old = re.sub(board_pattern, board_claim, old, count=1, flags=re.S)
        old = old.replace('<a href="executive-summary.html">Submission guide</a><a href="validation.html">', '<a href="executive-summary.html">Submission guide</a><a href="h55.html">H55 candidate</a><a href="validation.html">')
        forensics_path.write_text(old)

    h53_body = f'''<div class="eyebrow">Preserved prior experiment · H53</div><h1>Historical artifact,<br>different protocol.</h1><div class="status"><strong>H53 is not the current pointer or an upload recommendation.</strong> The current <code>submission/LATEST.txt</code> points to H55, whose scientific gate failed; no slot was used.</div><p>The H53 TIFF, code, tests and original receipts remain available for audit. H53's earlier tip/whole-hide numbers use a different protocol and are not comparable to H55's four quadrant, whole-component folds. No official score is authenticated for H53.</p><div class="card"><p>{a('downloads/gems52-h53-coincidence-gated-singles-37654px-r1.tif','Download archived H53 TIFF')} · {a('downloads/gems52-h53-coincidence-gated-singles-37654px-r1.zip','Archived single-TIFF ZIP')}</p><p>Prior SHA-256 <code>9ffe11b2b56a2cb43e7da5ce3613a626b1a5503dc72e91cee694376d15f4420f</code></p></div><p>{a('data/h53_holdout.json','H53 holdout')} · {a('data/submission_h53_audit.json','H53 audit')} · {a('index.html','Current H55 overview')}</p>'''
    (DOCS / "h53.html").write_text(page("Archived H53 experiment", h53_body))

    print(f"Published H55 site pages for {sub['file']} — score gate failed; no upload implied.")


def exchange_rows(exchange):
    result = []
    for fold in exchange["rounds"]:
        for view in fold["views"]:
            result.append([str(fold["fold"]), esc(view["target"]), str(view["pseudo_pixels"]),
                           f"{view['baseline_dti']:.6f}",
                           "—" if view["dti_after_exchange"] is None else f"{view['dti_after_exchange']:.6f}",
                           "—" if view.get("positive_lift_after_exchange") is None else f"{view['positive_lift_after_exchange']:+.6f}"])
    return result


def exchange_table(exchange):
    return table(["fold","receiver view","pseudo pixels","before","after","paired change"], exchange_rows(exchange))


def exchange_mean(exchange, target):
    vals = [v["positive_lift_after_exchange"] for f in exchange["rounds"] for v in f["views"]
            if v["target"] == target and v.get("positive_lift_after_exchange") is not None]
    return float(np.mean(vals)) if vals else float("nan")


def exchange_count(exchange, target):
    return sum(v.get("positive_lift_after_exchange", -1) > 0 for f in exchange["rounds"] for v in f["views"] if v["target"] == target)


def exchange_abs_mean(exchange, target):
    vals = [v["dti_after_exchange"] for f in exchange["rounds"] for v in f["views"]
            if v["target"] == target and v["dti_after_exchange"] is not None]
    return float(np.mean(vals)) if vals else float("nan")


if __name__ == "__main__":
    main()
