#!/usr/bin/env python3
"""Publish the audited H57 research artifact without changing the competitive LATEST pointer.

This publisher is intentionally separate from the existing R2/H56 site generators: it inserts an
idempotent H57 card above the historical cards, writes an H57-specific audit page and submission
guide, and copies small receipts into docs/data. It never rewrites submission/LATEST.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DOWNLOADS = DOCS / "downloads"
EVIDENCE = ROOT / "evidence"
H56_CURRENT_FILE = "gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif"
REG_PATH = ROOT / "registry/h57_preregistration.json"
HYP_PATH = ROOT / "knowledge/17_hypotheses_H57_preregistered.md"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def mean_dti(holdout: dict, arm: str) -> float:
    return float(holdout["controls"]["means"][arm])


def fmt_score(value) -> str:
    return "not measured" if value is None else f"{float(value):.6f}"


def h57_bar(receipt: dict, holdout: dict) -> str:
    if not receipt.get("safe_to_download_for_research"):
        raise RuntimeError("H57 TIFF did not pass local format and decoded-pattern gates; refusing a public download link")
    file = esc(receipt["file"])
    name = esc(receipt["submission_name"])
    note = esc(receipt["submission_note"])
    hist = float(holdout["comparisons"]["historical_best_comparable_mean_dti"])
    score = float(holdout["primary"]["mean_dti"])
    enabled = bool(holdout["exchange"]["enabled"])
    approval = bool(receipt["approved_to_submit"])
    approval_text = "YES — registered local promotion gates passed; portal acceptance is still unverified." if approval else "NO — research only; do not upload or spend a competition slot."
    return f'''<!--H57-BAR--><section class="download-bar" id="h57-bar" aria-label="H57 research GeoTIFF download">
<div>
<strong>H57 real-data research TIFF — {"locally approved, not organizer-accepted" if approval else "safe to download for review; NOT approved to submit"}</strong>
<small><code>{file}</code> · {int(receipt['bytes']):,} bytes · 1 band float32 · EPSG:32611 · 3730×3292 · finite values [0,1] · {int(receipt['emitted_pixels']):,} emitted pixels</small>
<small>On-disk format gate: <b>PASS</b> · exact decoded-pattern uniqueness: <b>PASS</b> against {int(receipt['uniqueness']['n_priors_checked'])} supplied aligned accessible rasters · literal prior-union check: <b>{'PASS' if receipt['uniqueness']['not_literal_prior_union'] else 'FAIL'}</b> · SHA-256 <code>{esc(receipt['sha256'][:16])}…</code></small>
<small>Spatial holdout: H57 fallback mean DTI <b>{score:.6f}</b>; best same-run single-view control <b>{mean_dti(holdout, 'view_B_corrected'):.6f}</b>; historical comparable mean <b>{hist:.6f}</b> (lift {score-hist:+.6f}). Co-training exchange: <b>{'enabled' if enabled else 'disabled by the frozen OOF error gate'}</b>.</small>
<small><b>Safe to download for research?</b> YES — local format/range and decoded-pattern checks passed. &nbsp; <b>Approved to submit?</b> {esc(approval_text)}</small>
<small>Submission name: <code>{name}</code> ({int(receipt['submission_name_chars'])} chars) · note ({int(receipt['submission_note_chars'])} chars): <code>{note}</code></small>
<small>No portal upload or slot use. A participant-level public score is not predicted or attributed to this file. The existing competitive <code>submission/LATEST.txt</code> pointer is unchanged.</small>
</div>
<a class="button" href="downloads/{file}" download>↓ Download H57 .TIF</a>
<a class="button" href="downloads/{esc(receipt['zip'])}" download>↓ Download single-TIFF .ZIP</a>
<a class="button secondary" href="h57.html">Holdout and audit →</a>
<a class="button secondary" href="executive-summary.html">Submission guide →</a>
</section><!--/H57-BAR-->'''


def insert_marker(path: Path, start: str, end: str, markup: str, before: str | None = None) -> None:
    text = path.read_text()
    has_start, has_end = start in text, end in text
    if has_start != has_end:
        raise RuntimeError(f"unpaired publication markers in {path}")
    if has_start:
        left = text.index(start)
        right = text.index(end, left) + len(end)
        text = text[:left] + text[right:]
    if before is None or before not in text:
        raise RuntimeError(f"cannot find safe insertion anchor {before!r} in {path}")
    index = text.index(before)
    text = text[:index] + markup + text[index:]
    path.write_text(text)


def nav() -> str:
    return '''<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>
<a href="index.html">Overview</a><a href="h57.html">H57 real-data test</a>
<a href="executive-summary.html">Submission guide</a><a href="validation.html">Validation</a>
<a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a>
<a href="irregularities.html">Limitations</a></nav></header>'''


def page(title: str, description: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(description)}"><title>{esc(title)} · GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head>
<body><a class="skip" href="#main">Skip to content</a>{nav()}<main id="main">{body}</main>
<footer>Competition 306 · H57 is local model research, not verified fault discovery, geothermal resource confirmation, organizer validation, or a public-score forecast. <a href="irregularities.html">Limitations &amp; review</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Repository and complete prompt</a></footer></body></html>'''


def reasoning_status(receipt: dict, holdout: dict) -> str:
    if not holdout["exchange"]["enabled"] or not receipt["candidate_arm_is_cotrain"]:
        return ("Not applicable to this artifact: the OOF independence gate disabled co-training, so the exported field is corrected View B only. "
                "There is no H57 A-only stratum or A-only candidate to interpret; this is recorded as a failed promotion requirement, not as missing evidence for a co-trained prediction.")
    detail = receipt.get("reasoning_json") or {}
    return (f"A-only reasoning record: {esc(detail.get('groups', 0))} review neighborhoods for "
            f"{esc(detail.get('emitted_a_only_pixels', 0))} emitted A-only pixels. Completeness: "
            f"{esc(detail.get('complete', False))}. Every candidate remains an unverified hypothesis.")


def build_audit_page(receipt: dict, holdout: dict, independence: dict, prefit: dict) -> str:
    arm_means = holdout["controls"]["means"]
    folds = []
    for item in holdout["folds"]:
        scores = item["scores"]
        folds.append(f'''<tr><th>Fold {int(item['fold'])}</th><td>{float(scores['view_A']['dti']):.6f}</td>
<td>{float(scores['view_B_corrected']['dti']):.6f}</td><td>{float(scores['early_fusion']['dti']):.6f}</td>
<td>{float(scores['max_AB_union_control']['dti']):.6f}</td><td>{float(scores['round0_disagreement_no_exchange']['dti']):.6f}</td>
<td>{float(scores['matched_random']['dti']):.6f}</td></tr>''')
    folds_html = "\n".join(folds)
    errors = []
    for fold, report in sorted(independence["per_fold"].items(), key=lambda item: int(item[0])):
        mse = report["tests"]["negative_mean_squared_error"]
        fpr = report["tests"]["negative_false_positive_rate"]
        errors.append(f'''<tr><th>{esc(fold)}</th><td>{int(report['n_blocks'])}</td>
<td>{fmt_score(mse.get('pearson'))} / {fmt_score(mse.get('spearman'))}</td>
<td>{fmt_score(fpr.get('pearson'))} / {fmt_score(fpr.get('spearman'))}</td>
<td>{'PASS' if report['allow_exchange'] else 'FAIL CLOSED'}</td><td>{esc(report['reason'])}</td></tr>''')
    error_html = "\n".join(errors)
    hist = holdout["comparisons"]["historical_best_comparable_mean_dti"]
    score = holdout["primary"]["mean_dti"]
    exact = receipt["uniqueness"]
    row = receipt["local_gates"]
    prefit_sha = esc(prefit.get("lock_sha256") or receipt.get("prefit_lock_sha256"))
    body = f'''{h57_bar(receipt, holdout)}
<div class="eyebrow">H57 · registered real-data test · 2026-10-07</div>
<h1>Corrected views.<br>Fail-closed validation.</h1>
<p class="lede">H57 tested whether corrected potential-field/subsurface View A and surface, radiometric and LiDAR View B could support a one-round whole-component co-training experiment. It did <strong>not</strong> meet the registered OOF-independence gate. The model was therefore not co-trained; the released TIFF is explicitly a corrected View-B research fallback.</p>
<div class="status"><strong>Download is safe for research review; submission is not approved.</strong>
The TIFF passed local format/range checks and is decoded-pattern distinct from all {int(exact['n_priors_checked'])} supplied aligned accessible priors. The OOF false-positive-rate errors were constant in fold 1, so the registered co-training mechanism failed closed. The fallback mean ({score:.6f}) is below the prior comparable local mean ({float(hist):.6f}); no weekly slot was used.</div>
<div class="grid"><div class="card"><div class="metric">{score:.5f}</div><div class="label">four-fold mean DTI, corrected View-B fallback</div></div>
<div class="card"><div class="metric">{score-hist:+.5f}</div><div class="label">difference vs historical comparable local mean {float(hist):.7f}</div></div>
<div class="card"><div class="metric">0</div><div class="label">portal uploads / slots used</div></div></div>
<h2>Four-fold matched-control results</h2>
<p>All round-0 arms used the same training rows, seed, learner, 80-pixel buffer, fold-specific proportional budget, and metric-aware placement. The fixed strongest same-run control is corrected View B itself (mean {float(arm_means['view_B_corrected']):.6f}); therefore no co-training lift is claimed. Fold scores below are local catalogue-holdout DTI, not public leaderboard scores.</p>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>View A</th><th>View B</th><th>Early fusion</th><th>Max A/B</th><th>Round-0 router</th><th>Matched random</th></tr></thead><tbody>{folds_html}</tbody></table></div>
<p>Mean controls: A {float(arm_means['view_A']):.6f}; corrected B {float(arm_means['view_B_corrected']):.6f}; early fusion {float(arm_means['early_fusion']):.6f}; max(A,B) {float(arm_means['max_AB_union_control']):.6f}; round-0 disagreement router {float(arm_means['round0_disagreement_no_exchange']):.6f}; matched random {float(holdout['controls']['matched_random_mean']):.6f}.</p>
<h2>Why the registered co-training gate failed</h2>
<p>The predeclared diagnostic required both block-level negative MSE and FPR error correlations to be defined in every fold and pooled, with at least 20 non-degenerate 50×50 blocks and absolute Pearson/Spearman values below 0.60. Pooled proxy-error correlations were weak, but fold 1's FPR error was constant, making Pearson and Spearman undefined. The correct action was to disable co-training—not to impute, change thresholds, or switch diagnostics.</p>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>Usable blocks</th><th>Negative MSE r / ρ</th><th>Negative FPR r / ρ</th><th>Gate</th><th>Reason</th></tr></thead><tbody>{error_html}
<tr><th>Pooled</th><td>{int(independence['pooled']['n_blocks'])}</td>
<td>{fmt_score(independence['pooled']['tests']['negative_mean_squared_error'].get('pearson'))} / {fmt_score(independence['pooled']['tests']['negative_mean_squared_error'].get('spearman'))}</td>
<td>{fmt_score(independence['pooled']['tests']['negative_false_positive_rate'].get('pearson'))} / {fmt_score(independence['pooled']['tests']['negative_false_positive_rate'].get('spearman'))}</td>
<td>{'PASS' if independence['pooled']['allow_exchange'] else 'FAIL CLOSED'}</td><td>{esc(independence['pooled']['reason'])}</td></tr>
</tbody></table></div>
<p><strong>No pseudo-labels were generated, no round-1 model was fit, and no co-training score exists.</strong> {reasoning_status(receipt, holdout)}</p>
<h2>Local TIFF / uniqueness checks</h2>
<ul><li>Single-band float32; {int(receipt['shape'][0])}×{int(receipt['shape'][1])}; EPSG:32611; 100 m cell size; exact sample transform.</li>
<li>All pixels finite and within [0,1]; {int(receipt['emitted_pixels']):,} positive cells; output pixels re-read and matched the in-memory emission exactly.</li>
<li>Decoded-pixel SHA-256: <code>{esc(receipt['decoded_pixels_sha256'])}</code>; TIFF-byte SHA-256: <code>{esc(receipt['sha256'])}</code>.</li>
<li>Canonical decoded pattern unique: PASS against {int(exact['n_priors_checked'])} accessible aligned prior rasters; literal prior-union equality: {'PASS' if exact['not_literal_prior_union'] else 'FAIL'}; support novelty {float(exact['novel_fraction']):.1%} is reported as a diagnostic only.</li>
<li>Same-run A/B union gate: not applicable because co-training was disabled. Local slot gates: {esc(json.dumps(row, sort_keys=True))}.</li></ul>
<p>A local format pass or decoded uniqueness pass is not evidence of geological quality, organizer authentication, portal acceptance, or a leaderboard score.</p>
<h2>Why 0.2778, and what the leaderboard says</h2>
<p>The public board snapshot fetched 2026-10-07 lists xiaofanhu at <strong>0.3774 (#1)</strong>, DARD at <strong>0.3195 (#7)</strong>, and extradr19 at <strong>0.2778 (#13)</strong>. The table is participant-level and does not authenticate a particular TIFF, filename, or hash. The user-supplied mapping of 0.2778 to the H33 file is owner-reported. Local byte forensics on an available related mirror show 2,545 off-catalogue flank pixels removed and none on the known-label mask; reducing weak false-positive mass is a plausible explanation, not a proven cause of the score. See the <a href="forensics.html">0.2778 autopsy</a>.</p>
<p>H57's local B-only fallback does <strong>not</strong> beat the registered comparable mean and no public-score improvement is forecast. No upload or weekly slot was used.</p>
<h2>Ranked geological hypotheses</h2>
<p>The leading H57-1 test combined corrected potential-field/subsurface View A with radiometric/LiDAR-aware surface View B and failed its co-training gate; it did not validate a buried fault. Three alternatives remain unrun.</p>
<div class="table-wrap"><table><thead><tr><th>Rank</th><th>Hypothesis</th><th>Target signature / expected missing-fault mechanism</th><th>Difference / cost</th></tr></thead><tbody>
<tr><th>1</th><td>H57-1 · corrected two-view covered range fronts</td><td>Potential-field/deep-cover contrast with weak DEM/LiDAR scarp; test buffered whole-segment co-training only if OOF errors permit.</td><td>Corrected band-6 TC routing plus external radiometric/LiDAR stack; H56 was synthetic. Actual test failed closed. Low-to-medium expectation; 2–4 CPU h.</td></tr>
<tr><th>2</th><td>H57-2 · LiDAR scarp-network endpoints/relays</td><td>Strike-consistent fragment terminations or en-echelon relays with a broad structural edge; potential secondary scarps may be unmapped.</td><td>Topology/coverage censoring rather than another local scarp maximum. 2–3 h; owner-mirrored derivatives exist; raw 3DEP tile QA would be separate.</td></tr>
<tr><th>3</th><td>H57-3 · conductivity-edge T-junctions</td><td>Scale-persistent conductivity edge termination against a differently oriented gravity/RTP edge.</td><td>Endpoint/intersection geometry, not conductivity magnitude. 3–5 h; conductivity depth and geological independence remain uncertain.</td></tr>
<tr><th>4</th><td>H57-4 · event-level ComCat lineaments</td><td>Filtered event clusters aligned with potential-field edges where surface scarps are weak.</td><td>Declustering/completeness/depth workflow, not 100-km smoothed seismic context. 4–6 h; ComCat query availability checked, but events are not a fault layer.</td></tr>
</tbody></table></div>
<p><a href="h57-hypotheses.md">Read the full preregistration, exact channel lists, gate rules, limits and official sources →</a> · <a href="data/h57_submission.json">Artifact receipt</a> · <a href="data/h57_holdout.json">Fold-level holdout JSON</a> · <a href="data/h57_independence.json">OOF block-error diagnostic</a> · <a href="data/h57_pseudo_exchange.json">Pseudo-label gate receipt</a> · <a href="data/h57_prefit_lock.json">Pre-fit lock</a></p>
<h2>Official sources and limitations</h2>
<ul><li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DrivenData problem, scoring and GeoTIFF format</a>.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official participant leaderboard</a> (dated observation, no candidate hash attribution).</li>
<li><a href="https://doi.org/10.1145/279943.279962">Blum &amp; Mitchell, COLT 1998</a> (co-training assumptions, not proof they hold here).</li>
<li><a href="https://doi.org/10.5066/P93LGLVQ">USGS GeoDAWN data release</a>; H57 uses owner-mirrored derivatives, not independently authenticated raw arrays.</li>
<li><a href="https://doi.org/10.2172/1724080">USGS/DOE Great Basin blind-system report</a> (mechanism context, not validation of H57 predictions).</li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> and <a href="https://earthquake.usgs.gov/fdsnws/event/1/">USGS ComCat</a>.</li>
<li><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">DOE/NREL GEMS Prize rules, September 2026</a>.</li></ul>
<p>Frozen registration SHA-256: <code>{esc(receipt['registration_sha256'])}</code> · pre-fit lock SHA-256: <code>{prefit_sha}</code> · run signature: <code>{esc(receipt['run_signature'])}</code>.</p>
<h2>Limitations and next work</h2>
<ul><li>SHA/size pins establish consistency with local owner mirrors, not organizer downloads; GeoDAWN/LiDAR features are owner-mirror derivatives.</li>
<li>Catalogue-zero cells are proxy negatives, not verified fault absence. Whole 8-connected raster components are not authenticated geological fault segments.</li>
<li>The four-fold holdout tests recovery of known catalogue components; it is not validation against expert-hidden new faults, verified geothermal vents, or prize outcomes.</li>
<li>The supplied board is team-level; the H33 filename/score mapping remains owner-reported. Do not infer a public score from local DTI.</li>
<li>Next: keep the slot unused; review false-positive/constant FPR diagnostics and feature-domain limits, then preregister an independent alternative (for example H57-2) before any new fit. Obtain authenticated official inputs if permitted.</li></ul>
<h2>Submission status</h2><p><strong>Safe to download for research: YES.</strong> <strong>Approved to submit: NO.</strong> Current note: <code>{esc(receipt['submission_note'])}</code>. The note is an identifier only; do not paste it into a portal while this run is unapproved.</p>'''
    return page("H57 real-data holdout and research TIFF", "H57 registered spatial holdout, corrected views, fail-closed co-training decision, and bounded TIFF gates", body)


def build_guide(receipt: dict, holdout: dict) -> str:
    file = esc(receipt["file"])
    name = esc(receipt["submission_name"])
    note = esc(receipt["submission_note"])
    score = float(holdout["primary"]["mean_dti"])
    hist = float(holdout["comparisons"]["historical_best_comparable_mean_dti"])
    status = "This candidate is NOT APPROVED. Do not use the submission steps below for this H57 file." if not receipt["approved_to_submit"] else "This candidate passed registered local gates; organizer acceptance and available slots remain the submitter's responsibility."
    h56 = "gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif"
    body = f'''{h57_bar(receipt, holdout)}
<div class="eyebrow">Executive summary · exact file identification · future submission steps</div>
<h1>One audited TIFF.<br>No unearned slot.</h1>
<div class="status"><strong>Safe to download for research: YES. Approved to submit: NO. Do not upload.</strong>{esc(status)} H57's OOF independence gate failed closed because one fold's false-positive-rate errors were constant, and the corrected View-B fallback mean {score:.6f} is below the historical comparable local mean {hist:.6f}. Zero competition slots were used.</div>
<section class="card"><h2>Identify the file</h2><p>Filename: <code>{file}</code></p><p>Unique submission identifier: <code>{name}</code> ({int(receipt['submission_name_chars'])} characters)</p>
<label for="submission-note">Short identifying note ({int(receipt['submission_note_chars'])} characters; do not submit this run)</label>
<textarea id="submission-note" readonly>{note}</textarea><button data-copy="submission-note">Copy note</button>
<p>TIFF SHA-256: <code>{esc(receipt['sha256'])}</code></p><p>Decoded-pixel SHA-256: <code>{esc(receipt['decoded_pixels_sha256'])}</code></p>
<p><a class="button" href="downloads/{file}" download>Download the exact H57 TIFF</a> <a class="button" href="downloads/{esc(receipt['zip'])}" download>Download the single-TIFF ZIP</a></p></section>
<h2>Why the reported [0,1] error is addressed</h2>
<p>The TIFF was re-opened after writing: one float32 band, 3730×3292, EPSG:32611, exact 100 m sample transform/bounds, all raw values finite in [0,1], and 37,654 nonzero cells. Zeros are written outside the feature footprint; there is no NaN or negative nodata sentinel. The local check is not an organizer upload-acceptance receipt.</p>
<h2>Exact submission steps — only after a future artifact is approved</h2>
<ol><li><strong>For this H57 file, stop here: do not upload it and do not spend a weekly slot.</strong> The receipt says <code>approved_to_submit: false</code>.</li>
<li>For a future candidate, confirm its audit receipt says <code>approved_to_submit: true</code>, then verify the exact SHA-256 of the TIFF download. Do not edit, reproject, recolor, or resave it in GIS software.</li>
<li>Sign in to the eligible team account on the official <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS competition</a>, open the new-submission form, and choose the one-band <code>.tif</code> or the ZIP containing exactly one TIFF.</li>
<li>Use the artifact's own submission identifier as the unique name when the portal offers a name field. Paste that artifact's ≤200-character note into <strong>Note (optional)</strong>.</li>
<li>Only when the local promotion gate is open and a weekly slot is available, submit. Save the organizer's receipt/ID/timestamp/returned score; do not infer a score from the local holdout.</li></ol>
<p>Official review links: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem and file-format rules</a> · <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official prize rules</a>.</p>
<h2>Older H56 synthetic method demo</h2><p>The H56 co-training TIFF remains in the archive and <code>submission/LATEST.txt</code> is intentionally unchanged, but H56 used synthetic methodology data and is not approved for a real upload. It is not the H57 output. <a href="h56-cotrain.html">Read the H56 warning</a> or <a href="downloads/{esc(h56)}" download>download the earlier demo</a>.</p>
<p>For H57's result, hypotheses, fold table, independence diagnostics, exact sources and limitations, see <a href="h57.html">the full H57 audit</a>.</p>'''
    return page("Executive summary and submission guide", "H57 research TIFF, exact identification, file validation and safe future submission steps", body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", help="explicit H57 submission receipt JSON; defaults to newest evidence receipt")
    args = parser.parse_args()
    receipt_path = Path(args.receipt) if args.receipt else None
    if receipt_path is None:
        candidates = sorted(EVIDENCE.glob("submission_gems52-h57-*.json"))
        if not candidates:
            raise SystemExit("no H57 artifact receipt exists; nothing to publish")
        receipt_path = candidates[-1]
    if not receipt_path.is_absolute():
        receipt_path = ROOT / receipt_path
    receipt = load_json(receipt_path)
    holdout = load_json(EVIDENCE / "h57_holdout.json")
    independence_path = EVIDENCE / "h57_independence.json"
    independence = load_json(independence_path)
    exchange = load_json(EVIDENCE / "h57_pseudo_exchange.json")
    feature_manifest = load_json(EVIDENCE / "h57_feature_manifest.json")
    run_integrity = load_json(EVIDENCE / "h57_run_integrity.json")
    prefit_path = EVIDENCE / "h57_prefit_lock.json"
    prefit = load_json(prefit_path)
    registration_sha = hashlib.sha256(REG_PATH.read_bytes()).hexdigest()
    hypothesis_sha = hashlib.sha256(HYP_PATH.read_bytes()).hexdigest()
    prefit_sha = hashlib.sha256(prefit_path.read_bytes()).hexdigest()
    independence_sha = hashlib.sha256(independence_path.read_bytes()).hexdigest()
    if (registration_sha != receipt.get("registration_sha256")
            or hypothesis_sha != receipt.get("hypothesis_sha256")
            or prefit_sha != receipt.get("prefit_lock_sha256")
            or prefit.get("registration_sha256") != registration_sha
            or prefit.get("hypothesis_sha256") != hypothesis_sha
            or prefit.get("model_fit_started") is not False):
        raise SystemExit("H57 preregistration, hypothesis or pre-fit lock hashes/state do not match")
    if holdout.get("registration_sha256") != receipt.get("registration_sha256"):
        raise SystemExit("holdout and artifact receipts use different registrations")
    run_signature = receipt.get("run_signature")
    if holdout.get("run_signature") != run_signature:
        raise SystemExit("holdout and artifact receipts use different code/input/feature signatures")
    if (independence.get("run_signature") != run_signature
            or feature_manifest.get("run_signature") != run_signature
            or run_integrity.get("run_signature") != run_signature
            or holdout.get("feature_manifest_sha256") != receipt.get("provenance", {}).get("feature_manifest_sha256")
            or exchange.get("independence_sha256") != independence_sha
            or holdout.get("independence_file") != "evidence/h57_independence.json"
            or holdout.get("pseudo_exchange_file") != "evidence/h57_pseudo_exchange.json"):
        raise SystemExit("H57 holdout, feature, OOF, exchange and run-integrity receipts do not cross-match")
    if (receipt.get("candidate_arm") != "view_B_corrected_fallback"
            or receipt.get("candidate_arm_is_cotrain") is not False
            or receipt.get("approved_to_submit") is not False
            or receipt.get("approved_for_weekly_slot") is not False
            or receipt.get("portal_upload_performed") is not False
            or receipt.get("slots_used") != 0
            or holdout.get("exchange", {}).get("enabled") is not False
            or exchange.get("enabled") is not False
            or exchange.get("used_in_primary") is not False
            or independence.get("allow_exchange") is not False
            or holdout.get("slot_gate", {}).get("approved_for_weekly_slot") is not False
            or holdout.get("submission_slots_used") != 0
            or run_integrity.get("submission_slots_used") != 0
            or run_integrity.get("portal_upload_performed") is not False):
        raise SystemExit("H57 failed-gate fallback, zero-slot and no-upload safety state is inconsistent")
    if (not receipt.get("format_gate", {}).get("ok")
            or not receipt.get("uniqueness", {}).get("canonical_pattern_unique")
            or not receipt.get("uniqueness", {}).get("research_publication_ok")
            or receipt.get("uniqueness", {}).get("equals_literal_prior_union") is not False):
        raise SystemExit("H57 format or bounded decoded-pattern uniqueness gates are not all passed")
    if float(holdout["primary"]["mean_dti"]) >= float(
            holdout["comparisons"]["historical_best_comparable_mean_dti"]):
        raise SystemExit("H57 fallback has not been shown below the comparable holdout reference")
    if not receipt.get("safe_to_download_for_research"):
        raise SystemExit("H57 failed local format/decoded-pattern gates; refusing to publish")
    if not receipt.get("approved_to_submit") and (ROOT / "submission/LATEST.txt").read_text().strip() != H56_CURRENT_FILE:
        raise SystemExit("failed-gate H57 must not replace the protected LATEST pointer")
    tif = ROOT / "submission" / receipt["file"]
    zip_path = ROOT / "submission" / receipt["zip"]
    if not tif.is_file() or not zip_path.is_file():
        raise SystemExit("canonical H57 TIFF/ZIP is missing")
    if hashlib.sha256(tif.read_bytes()).hexdigest() != receipt["sha256"]:
        raise SystemExit("canonical H57 TIFF does not match its receipt")
    if hashlib.sha256(zip_path.read_bytes()).hexdigest() != receipt["zip_sha256"]:
        raise SystemExit("canonical H57 ZIP does not match its receipt")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    for src, dst in ((tif, DOWNLOADS / tif.name), (zip_path, DOWNLOADS / zip_path.name)):
        shutil.copy2(src, dst)
        if hashlib.sha256(dst.read_bytes()).hexdigest() != hashlib.sha256(src.read_bytes()).hexdigest():
            raise SystemExit(f"site download copy differs from canonical bytes: {dst}")
    publications = [
        (receipt_path, DATA / "h57_submission.json"),
        (EVIDENCE / "h57_holdout.json", DATA / "h57_holdout.json"),
        (EVIDENCE / "h57_independence.json", DATA / "h57_independence.json"),
        (EVIDENCE / "h57_pseudo_exchange.json", DATA / "h57_pseudo_exchange.json"),
        (EVIDENCE / "h57_feature_manifest.json", DATA / "h57_feature_manifest.json"),
        (EVIDENCE / "h57_run_integrity.json", DATA / "h57_run_integrity.json"),
        (EVIDENCE / "h57_prefit_lock.json", DATA / "h57_prefit_lock.json"),
        (EVIDENCE / "h57_band6_identity.json", DATA / "h57_band6_identity.json"),
        (REG_PATH, DATA / "h57_preregistration.json"),
        (HYP_PATH, DOCS / "h57-hypotheses.md"),
    ]
    for src, dst in publications:
        shutil.copy2(src, dst)
    # Keep the frozen preregistration bytes untouched at knowledge/17...; normalize only the
    # human-facing docs copy so standard diff checks do not treat Markdown hard-break spaces as bugs.
    hypothesis_lines = []
    for line in HYP_PATH.read_text().splitlines():
        if line.endswith("  "):
            line = line.rstrip()
            if line.startswith("**"):
                line += "<br>"
        hypothesis_lines.append(line)
    (DOCS / "h57-hypotheses.md").write_text("\n".join(hypothesis_lines) + "\n")

    index_path = DOCS / "index.html"
    if not index_path.is_file():
        raise SystemExit("docs/index.html missing")
    bar = h57_bar(receipt, holdout)
    insert_marker(index_path, "<!--H57-BAR-->", "<!--/H57-BAR-->", bar,
                  before="<!--H56BAR-->")
    index_html = index_path.read_text()
    h57_nav = '<a href="h57.html">H57 real-data test</a>'
    if h57_nav not in index_html:
        anchor = '<a class="brand" href="index.html">GEMS / DOE 52</a>'
        if anchor not in index_html:
            raise SystemExit("index navigation anchor missing")
        index_path.write_text(index_html.replace(anchor, anchor + h57_nav, 1))
    index_html = index_path.read_text()
    index_html = index_html.replace(
        'content="New fault-prediction research TIFF, spatial validation and auditable source evidence. No unsupported leaderboard forecast."',
        'content="H57 real-data research GeoTIFF with a fail-closed spatial holdout; safe to download for review, not approved to submit."',
        1)
    index_html = index_html.replace(
        '★ H56 Co-training (NEW) — synthetic demo of View A vs View B disagreement ★',
        'H56 Co-training — earlier synthetic methodology demo (archive, not the real-data H57 output)', 1)
    index_html = index_html.replace(
        'A-only = buried fault beneath cover (372 neighborhoods, each with geological reasoning)',
        'A-only is a buried-fault hypothesis from synthetic demo scores, not verified geology (372 neighborhoods)', 1)
    index_path.write_text(index_html)

    (DOCS / "h57.html").write_text(build_audit_page(receipt, holdout, independence, prefit))
    (DOCS / "executive-summary.html").write_text(build_guide(receipt, holdout))

    downloads_index = DOCS / "downloads/index.html"
    if downloads_index.is_file():
        section = f'''<!--H57-DOWNLOADS--><section class="card" id="h57-research-download"><h2>H57 real-data research artifact — safe to download, not approved to submit</h2>
<p><a href="{esc(receipt['file'])}" download>Download the one-click H57 TIFF</a> · <a href="{esc(receipt['zip'])}" download>single-TIFF ZIP</a> · <a href="../h57.html">holdout and audit</a></p>
<p>Format/range PASS; exact decoded-pattern unique against {int(receipt['uniqueness']['n_priors_checked'])} supplied accessible priors. Co-training disabled by a degenerate OOF FPR fold; View-B fallback mean {float(holdout['primary']['mean_dti']):.6f}; do not upload or use a weekly slot.</p></section><!--/H57-DOWNLOADS-->'''
        insert_marker(downloads_index, "<!--H57-DOWNLOADS-->", "<!--/H57-DOWNLOADS-->", section,
                      before="<!--H55EDGE-ARCHIVE-->")

    # Preserve the full current user prompt already in README; only add a dated status block at the top.
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    old_heading = "## H56 Co-training — NEW unique TIF, downloadable now (synthetic demo)"
    if old_heading in readme:
        readme = readme.replace(old_heading, "## H56 Co-training — historical synthetic methodology demo (not the real-data H57 candidate)", 1)
    old_next_session = ("**Next-session start:** read this README and the full current task prompt below. The H55-PROFILE follow-up failed its promotion gate; "
                        "the main H55 file is historical and superseded by current H56; H55-PROFILE remains a separate failed-gate record. "
                        "A download link is not approval to spend a contest slot.")
    new_next_session = ("**Next-session start:** read this README, `AGENTS.md`, the H57 top status and the full preserved brief below. "
                        "H57 is the latest real-data research result, but its OOF gate failed closed and its fallback is not approved to submit; "
                        "keep `submission/LATEST.txt` unchanged unless a newly preregistered candidate beats the comparable spatial holdout gate. "
                        "A download link is not approval to spend a contest slot.")
    readme = readme.replace(old_next_session, new_next_session, 1)
    readme = readme.replace(
        "H55 is superseded. Current H56 is a **synthetic methodology demo**; neither H55's local gate nor H56's downloadable TIFF authorizes a weekly submission.",
        "H55 is superseded. H56 is an **earlier synthetic methodology demo**; neither H55's local gate nor H56's downloadable TIFF authorizes a weekly submission.",
        1)
    top = f'''<!--H57-STATUS-->
## H57 real-data research candidate — one-click download; NOT approved to submit

**[Download the unique H57 GeoTIFF](docs/downloads/{receipt['file']})** · [single-TIFF ZIP](docs/downloads/{receipt['zip']}) · [full H57 holdout, source review, four hypotheses and submission guide](docs/h57.html) · [executive summary / future submission steps](docs/executive-summary.html) · [artifact receipt](docs/data/h57_submission.json)

- **Safe to download for research review? YES.** Local on-disk format/range check passed; one-band float32, 3730×3292, EPSG:32611, 100 m, all values finite in [0,1], 37,654 positive pixels. Exact decoded-pixel pattern is unique against all {int(receipt['uniqueness']['n_priors_checked'])} supplied aligned accessible prior rasters; literal prior-union equality is false. This is bounded to the inventory, not a global uniqueness guarantee.
- **Approved to submit? NO. Do not upload or spend a weekly slot.** Registered OOF independence failed closed because fold 1's block-level false-positive-rate errors were constant/undefined. No pseudo labels or round-1 model were fit. The corrected View-B research fallback mean is {float(holdout['primary']['mean_dti']):.6f}; the historical comparable local mean is {float(holdout['comparisons']['historical_best_comparable_mean_dti']):.6f} (difference {float(holdout['comparisons']['mean_lift_vs_historical_best']):+.6f}). No public-score forecast is made.
- **Submission identifier:** `{receipt['submission_name']}` · **note ({int(receipt['submission_note_chars'])} chars):** `{receipt['submission_note']}`. These identify a research file; the note explicitly says not approved.
- **No A-only candidate exists for this H57 artifact:** the frozen independence gate disabled co-training, so the exported field is single-view B. A-only reasoning is therefore not applicable and the promotion gate remains closed.
- **`submission/LATEST.txt` remains unchanged** at the earlier synthetic H56 pointer. No organizer upload or slot use occurred. See official-source links and limitations on the H57 audit page.

### Continuing brief and review gates (2026-10-07)

Keep a unique, one-click downloadable GeoTIFF and a unique short competition name/note, but state download safety separately from submit approval. Ground geology and competition claims in official sources; distinguish organizer-authenticated facts from owner-reported filenames/scores and catalogue-zero proxies from verified fault absence. Maintain 3–5 ranked, layer-specific geological hypotheses with physical signature, missing-catalogue mechanism, novelty, expected gain and implementation cost. Validate a leading idea on spatially blocked holdout before any competition slot; discuss the reported 0.2778 result and dated leaderboard without inventing file attribution. Preserve the full historical prompt below, document limitations and remaining work, and complete implementation/review/re-check passes. Create and merge a PR to main only if the fixed Arena branch, checks and repository state permit.

<!--/H57-STATUS-->

'''
    if "<!--H57-STATUS-->" in readme and "<!--/H57-STATUS-->" in readme:
        a = readme.index("<!--H57-STATUS-->")
        b = readme.index("<!--/H57-STATUS-->", a) + len("<!--/H57-STATUS-->")
        readme = readme[:a] + top.rstrip() + readme[b:]
    else:
        title = "# GEMSDOE52"
        if not readme.startswith(title):
            raise SystemExit("README project title is missing; refusing to replace the prompt")
        end = readme.index("\n", len(title)) + 1
        readme = readme[:end] + "\n" + top + readme[end:].lstrip("\n")
    readme_path.write_text(readme)
    print(f"Published {receipt['file']} to docs/index.html, docs/executive-summary.html, docs/h57.html and README.md")
    print("Safe to download for research: YES; approved to submit: NO; LATEST pointer unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
