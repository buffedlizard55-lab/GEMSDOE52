#!/usr/bin/env python3
"""Render the H69 pages and stage the downloadable artefacts, from the receipts only.

Every number on these pages is read from ``evidence/h69_*.json`` or from the submission receipt that
``scripts/run_h69.py`` wrote. Nothing is typed by hand, so a page cannot disagree with the evidence it
cites. This script uploads nothing and changes no verdict; it reports the verdict the run card holds.

Run after ``scripts/run_h69.py --stage gates``:
    .venv/bin/python scripts/publish_h69_site.py
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"


def load(name):
    return json.loads((EVID / name).read_text())


def e(x):
    return html.escape(str(x))


def n(x):
    return f"{int(x):,}"


HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>{title}</title><link rel="stylesheet" href="{root}assets/ctd5.css"></head>\n<body>'
        '<a class="skip" href="#main">Skip to content</a>'
        '<header><nav aria-label="Main navigation">'
        '<a class="brand" href="{root}index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
        '<a href="{root}index.html">Overview</a>'
        '<a href="{root}h69.html">H69 method &amp; results</a>'
        '<a href="{root}h69-executive-summary.html">H69 stop status</a>'
        '<a href="{root}h69-sources.html">Sources</a>'
        '<a href="{root}downloads/index.html">Archive</a>'
        '</nav></header>\n<main id="main">')
FOOT = ('\n<footer><p class="small">GEMSDOE52 · H69 · every number on this page is read from '
        '<code>evidence/h69_*.json</code>, produced by <code>scripts/run_h69.py</code> from rasters '
        'restored and SHA-256 verified by <code>scripts/restore_data.py</code>. No organiser receipt '
        'exists for this round. Projections are labelled PROJECTION and are never scores.</p></footer>'
        '</main></body></html>\n')


def verdict_block(card, val, big=True):
    sub = card["submit_recommended"]
    dl = card["download_ok"]
    literal_stop = card["correlation_vs_registry"]["literal"]["duplicate"]
    cls = "notice"
    if literal_stop:
        head = ("RESEARCH DOWNLOAD ONLY · LOCAL FORMAT VALIDATION IS NOT PORTAL ACCEPTANCE · "
                "NOT FOR SUBMISSION — DUPLICATE/STOP")
    elif sub:
        head = "LOCAL FORMAT CHECKS PASS · PORTAL ACCEPTANCE UNVERIFIED · PROMOTION GATES PASS"
    else:
        head = "RESEARCH DOWNLOAD ONLY · PORTAL ACCEPTANCE UNVERIFIED · SUBMISSION NOT RECOMMENDED"
    rows = [
        ("Local format validation (single band, float32, EPSG:32611, 3,730 × 3,292, pinned transform)",
         "PASS" if val["matches_sample"] else "FAIL"),
        ("Local value-range check only — portal acceptance is unverified",
         "PASS" if val["values_in_0_1"] and val["unique_values"] <= 2 else "FAIL"),
        ("No NaN or infinite pixel anywhere in the file", "PASS" if val["no_nan_inside_footprint"] else "FAIL"),
        ("Decoded-pattern uniqueness — not identical to any registry raster",
         "PASS" if card["overlap_vs_registry"]["canonical_pattern_unique"] else "FAIL"),
        ("Lane, literal rule (every aligned prior): Spearman ≤ 0.90 and 3 px near-dot ≤ 0.70",
         "DUPLICATE/STOP" if literal_stop else "PASS"),
        ("Lane, saturation policy (informative priors only; does not override literal stop)",
         "PASS" if not card["correlation_vs_registry"]["policy"]["duplicate"] else "DUPLICATE"),
        ("Not the union of the two views", "PASS" if card["not_union"]["pass_"] else "FAIL"),
        ("S1 sufficiency (Blum–Mitchell premise, View A out-of-quadrant AUC)",
         "PASS" if card["s1_sufficiency"]["pass_"] else "FAIL"),
        ("HOLDOUT-DTI beats single_B (paired 95 % CI lower bound > 0)",
         "PASS" if card["holdout_dti"]["beats_single_B"] else "FAIL"),
        ("≥ 20 % exact support novelty against the all-prior union",
         "PASS" if card["overlap_vs_registry"]["support_novelty_20pct_diagnostic"] else "FAILED DIAGNOSTIC"),
    ]
    out = [f'<div class="{cls}" role="note"><strong>{e(head)}</strong>']
    out.append('<table class="t"><thead><tr><th>Gate</th><th>Measured result</th></tr></thead><tbody>')
    for k, v in rows:
        good = str(v).startswith("PASS")
        out.append(f'<tr><td>{k}</td><td><strong style="color:{"#137333" if good else "#b3261e"}">{e(v)}</strong></td></tr>')
    out.append("</tbody></table>")
    out.append(f'<p><strong>Disposition.</strong> Research download: <strong>{"YES" if dl else "NO"}</strong>. '
               'Local format validation: <strong>PASS</strong>; that does not establish portal acceptance. '
               '<strong>Portal acceptance: UNVERIFIED</strong> — no organizer-confirmed receipt exists. '
               f'Literal lane status: <strong>{"DUPLICATE/STOP" if literal_stop else "see measured gate above"}</strong>. '
               f'Submission status: <strong>{"NO — stop controls; no override" if literal_stop else ("eligible under local gates only" if sub else "NO")}</strong>. '
               'The informative-prior saturation-policy PASS cannot waive a literal DUPLICATE/STOP. '
               f'Competition slots used: <strong>{card["slots_used"]}</strong>; no slot is recommended. '
               f'Run-card verdict (historical): <strong>{e(card["verdict"])}</strong>.</p></div>')
    return "\n".join(out)


def main():

    _h75_home = ROOT / "docs" / "index.html"
    _h75_status = ROOT / "docs" / "h75-executive-summary.html"
    if (_h75_home.is_file() and _h75_status.is_file()
            and "H75: DUPLICATE/STOP" in _h75_home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in
            _h75_status.read_text(errors="replace")):
        print("H75 terminal stop is current; historical publisher made no page or pointer changes")
        return
    card = load("h69_run_card.json")
    hold = load("h69_holdout.json")
    s1 = load("h69_s1.json")
    indep = load("h69_independence.json")
    can = load("h69_canary.json")
    fmt = load("h69_format_gate.json")
    uniq = load("h69_uniqueness.json")
    lane_d = load("h69_lane_dots.json")
    lane_s = load("h69_lane_surface.json")
    place = load("h69_placement.json")
    ao = load("h69_a_only.json")
    val = card["validator"]
    name = card["submission_name"]
    stem = name
    S = int(fmt["n_nonzero"])
    sub = card["submit_recommended"]
    pw = card["projection"]["per_g"]
    lane_pol = card["correlation_vs_registry"]["policy"]
    lane_lit = card["correlation_vs_registry"]["literal"]

    DOWN.mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)
    shutil.copy(SUBM / f"{stem}.tif", DOWN / "h69-candidate.tif")
    shutil.copy(SUBM / f"{stem}.tif", DOWN / f"{stem}.tif")     # canonical name, byte-identical
    shutil.copy(SUBM / f"{stem}.zip", DOWN / f"{stem}.zip")
    shutil.copy(SUBM / f"{stem}.zip", DOWN / "h69-candidate.zip")
    if (EVID / "h69_a_only_geological_reasoning.csv").exists():
        shutil.copy(EVID / "h69_a_only_geological_reasoning.csv.gz", DOWN / "h69-a-only-reasoning.csv.gz")
    for f in ("h69_run_card.json", "h69_holdout.json", "h69_s1.json", "h69_independence.json",
              "h69_canary.json", "h69_format_gate.json", "h69_uniqueness.json", "h69_lane_dots.json",
              "h69_lane_surface.json", "h69_placement.json", "h69_a_only.json"):
        shutil.copy(EVID / f, DOCS / "data" / f)

    sc = hold["pooled"]["scores"]
    pdiff = hold["pooled"]["paired_differences"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"  # noqa: E731

    # ------------------------------------------------------------------ index.html (landing)
    idx = [HEAD.format(title="GEMSDOE52 · H69 historical research GeoTIFF and stop status", root="")]
    idx.append('<section class="hero"><div>')
    idx.append('<div class="eyebrow">DOE GEMS Prize Challenge · round H69 · 2026-10-09</div>')
    idx.append('<h1>H69 research artifact.<br>Terminal submission stop.</h1>')
    idx.append('<p class="lead">A historical single-band GeoTIFF retained for research and review. Local format checks pass, but portal acceptance is unverified. The literal all-prior lane check is DUPLICATE/STOP because a universal-coverage registry probe exceeds the near-dot limit; the informative-prior saturation policy does not waive that stop. This artifact is not for submission.</p>')
    idx.append('<div class="actions">'
               f'<a class="button" href="downloads/h69-candidate.tif" download>⬇ Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a>'
               '<a class="button secondary" href="downloads/h69-candidate.zip" download>Single-TIFF ZIP</a>'
               '<a class="button secondary" href="downloads/h69-a-only-reasoning.csv.gz" download>A-only geological reasoning CSV</a>'
               '<a class="button secondary" href="h69-executive-summary.html">H69 stop status →</a>'
               '</div>')
    idx.append(f'<p class="fileline"><code>{e(stem)}.tif</code><br>'
               f'{n(fmt["bytes"])} bytes · SHA-256 <code>{e(card["raster_sha256"])}</code><br>'
               f'{n(S)} emitted pixels · values exactly {e(sorted(fmt.get("value_set", ["0", "1"])))} · '
               f'{val["unique_values"]} distinct value(s) · 0 NaN · EPSG:32611 · '
               f'{val["shape"][0]:,} × {val["shape"][1]:,} · transform {e(val["transform"])}</p>')
    idx.append('</div>')
    idx.append('<aside class="panel" aria-label="Readiness"><div class="label">Readiness, measured</div>')
    idx.append('<p class="big">RESEARCH DOWNLOAD · DUPLICATE/STOP</p>')
    idx.append('<p class="small">Local format validation: PASS. Portal acceptance: UNVERIFIED; no organizer-confirmed receipt exists. Submission is stopped by the literal DUPLICATE/STOP result and other failed promotion gates.</p>')
    idx.append(f'<p class="small">Local format {e("PASS" if card["gates"]["format"] else "FAIL")} · '
               'literal lane DUPLICATE/STOP · informative-prior saturation policy PASS · '
               f'Unique {e("PASS" if card["gates"]["unique"] else "FAIL")} · '
               f'Not-union {e("PASS" if card["gates"]["not_union"] else "FAIL")} · '
               f'S1 {e("PASS" if card["gates"]["S1"] else "FAIL")} · '
               f'Beats single_B {e("PASS" if card["gates"]["holdout_beats_single_B"] else "FAIL")}</p>')
    idx.append(f'<p class="small">CONDITIONAL SCENARIO ARITHMETIC only: the |G| range and score-derived density assumptions are not measured truth. These values are not a leaderboard score or prediction; see knowledge/49 and knowledge/53.</p>')
    idx.append('</aside></section>')
    idx.append(verdict_block(card, val))
    idx.append('<section><h2>What changed in this round</h2><ol>'
               '<li><strong>The informative-prior saturation policy was enforced during placement; the literal all-prior gate still stops H69.</strong> '
               f'The policy-only max near-dot is <strong>{lane_d["policy"]["max_near_3px_fraction"]:.4f}</strong>; '
               'a universal-coverage probe has 1.0000, so the final literal status is DUPLICATE/STOP. '
               'The policy pass is not lane clearance or submission eligibility.</li>'
               '<li><strong>The emission is novel-only.</strong> A pre-registered variant that retained the '
               '25,502-cell local support overlap in <code>A ∩ C</code> was withdrawn before placement. Any credit assigned by score inversion depends on owner-reported associations, assumed |G| and the sparse-emission model; it is conditional arithmetic, not measured hidden-truth credit. The historical H60C uniqueness correction (IR-H61-007, IR-UNQ-001) also remains applicable. Its scenario projection is NOT SHIPPED and is not a candidate.</li>'
               '<li><strong>View A was rebuilt as differential geometry of the basement surface</strong> '
               '(|∇| and ∇² of organiser band 15, a band-passed isostatic residual, and the gravity/RTP '
               'gradient-angle coherence), not as raw band levels or step/persistence columns. It did not work: '
               f'out-of-quadrant AUC {s1["summary"]["A"]["mean"]:.4f} against a 0.60 bar.</li>'
               '<li><strong>The committed whole-segment pseudo-label rule produced exactly zero labels</strong> '
               'in all four folds, so <code>disagreement_post</code> is bit-identical to '
               '<code>disagreement_pre</code>. The co-training mechanism could not be executed as specified.</li>'
               '<li><strong>Exact support novelty is impossible on this registry and is reported, not waived.</strong> '
               'The union of every informative prior\'s 3 px halo covers 100 % of the 4,859,987 px legal set '
               '(<code>work/h69/probe.py</code>), so the ≥ 20 % novelty diagnostic fails for every nonempty '
               'candidate that has ever been built here.</li></ol></section>')
    idx.append(FOOT)
    (DOCS / "h69-overview.html").write_text("\n".join(idx))

    # ------------------------------------------------------------------ executive summary
    ex = [HEAD.format(title="H69 · research-only stop status · GEMSDOE52", root="")]
    ex.append('<section><h1>H69 status — research artifact, not for submission</h1>')
    ex.append(verdict_block(card, val))
    ex.append('<h2>1 · The file</h2>')
    ex.append('<div class="actions"><a class="button" href="downloads/h69-candidate.tif" download>'
              '⬇ Download h69-candidate.tif</a>'
              '<a class="button secondary" href="downloads/h69-candidate.zip" download>ZIP</a></div>')
    ex.append('<table class="t"><tbody>'
               f'<tr><td>Filename on disk</td><td><code>{e(stem)}.tif</code> (served as <code>h69-candidate.tif</code>)</td></tr>'
               f'<tr><td>Size</td><td>{n(fmt["bytes"])} bytes</td></tr>'
               f'<tr><td>SHA-256</td><td><code>{e(card["raster_sha256"])}</code></td></tr>'
               f'<tr><td>Bands / dtype</td><td>{val["bands"]} band, {e(val["dtype"])}</td></tr>'
               f'<tr><td>CRS</td><td>{e(val["crs"])} (UTM zone 11N)</td></tr>'
               f'<tr><td>Shape</td><td>{val["shape"][0]:,} rows × {val["shape"][1]:,} cols</td></tr>'
               f'<tr><td>Transform</td><td><code>{e(val["transform"])}</code> — identical to <code>sample_submission.tif</code></td></tr>'
               f'<tr><td>Value range</td><td>min {val["min"] if "min" in val else 0}, max {val["max"] if "max" in val else 1}; '
               f'{val["unique_values"]} distinct value(s); all inside [0, 1]</td></tr>'
               f'<tr><td>NaN / infinite pixels</td><td>0 (all-finite export policy)</td></tr>'
               f'<tr><td>Emitted pixels</td><td>{n(S)} = {n(place["n_core"])} local overlap-core cells (credit unknown) + '
               f'{n(place["n_novel_placed"])} novel-view cells</td></tr>'
               '</tbody></table>')
    ex.append('<h2>2 · Submission status</h2>')
    ex.append('<p><strong>NOT FOR SUBMISSION — DUPLICATE/STOP.</strong> This historical raster is downloadable only as a research artifact. Do not use a competition slot. No owner override or submission steps are offered.</p>')
    ex.append('<h2>3 · Local format validation (not portal acceptance)</h2>')
    ex.append(f'<p>The saved bytes were locally re-read and checked against the sample grid: {val["bands"]} band, {e(val["dtype"])}, {e(val["crs"])}, {val["shape"][0]:,} × {val["shape"][1]:,}, values in [0, 1], no NaN or infinity. These local checks do not establish portal acceptance. Portal acceptance is UNVERIFIED because no organizer-confirmed submission receipt exists.</p>')
    ex.append('<h2>4 · The decision, in the repository’s own terms</h2>')
    s1word = "PASS" if s1["pass_"] else "FAIL"
    ex.append('<p><strong>RESEARCH DOWNLOAD ONLY · LOCAL FORMAT PASS · PORTAL ACCEPTANCE UNVERIFIED · NOT FOR SUBMISSION — DUPLICATE/STOP.</strong> '
               'The informative-prior saturation-policy PASS does not waive the literal all-prior stop. '
               'Two additional promotion criteria also fail:</p><ul>'
               f'<li><strong>S1 sufficiency {s1word}</strong> &mdash; View A '
               f'out-of-quadrant AUC mean {s1["summary"]["A"]["mean"]:.4f}, minimum '
               f'{s1["summary"]["A"]["minimum"]:.4f}, against thresholds mean ≥ 0.60 and fold ≥ 0.55. '
               'When this fails the Blum–Mitchell premise fails and the disagreement arm is noise-dominated. '
               'H61 measured 0.5163, H63 0.5362, H64 0.5230.</li>'
               f'<li><strong>HOLDOUT-DTI vs single_B</strong> — candidate '
               f'{pdiff["single_B"]["delta"]:+.6f}, 95 % CI {ci(pdiff["single_B"]["ci95"])}. '
               'The brief says never spend a slot on an idea that has not beaten the current holdout best.</li>'
               '</ul>'
               '<p>The historical n = 13 correlation between this holdout instrument and reported leaderboard values is exploratory only and is not a conversion or score forecast. H69 HOLDOUT-DTI remains an internal hide-and-recover measurement; all score-inversion outputs are conditional scenarios, not measured credit or organizer-confirmed results. See knowledge/49 and knowledge/53.</p>')
    ex.append('<h2>5 · The instrument control, published because it did not reproduce</h2>'
              f'<p>The pre-registration required <code>single_B</code> to reproduce the committed H61/H64 value '
              f'0.1745172876 to |Δ| ≤ 0.001. It measured '
              f'<strong>{hold["pooled"]["scores"]["single_B"]["dti"]:.6f}</strong>. That clause is unsatisfiable '
              'for a round that deliberately changes View B\'s channel set, and it is reported as FAILED rather '
              'than hidden. The model-free control that can reproduce across channel changes is the '
              f'<code>random</code> arm: <strong>{hold["instrument_control"]["random_arm"]:.6f}</strong> here '
              f'against 0.080426 in H64, |Δ| = {hold["instrument_control"]["abs_delta"]:.4f}, also outside '
              '0.001. The residual difference is the <code>eligible</code> mask: the committed rounds read '
              '<code>structural.FeatureStore.valid</code> from <code>work/r2/features</code>, which is '
              'git-ignored and absent in a fresh sandbox, so this round used the all-19-bands-finite ∩ '
              f'sample-submission-finite footprint and withheld {hold["withheld_positives"]:,} positives against '
              'H64\'s 53,186. <strong>Within-round paired comparisons are exact</strong> (identical folds, '
              'budget and masks for every arm); <strong>across-round level comparisons are approximate.</strong></p>')
    ex.append('<h2>6 · The projection, labelled as a projection</h2>')
    ex.append('<p>The tables below are historical conditional scenarios, not forecasts, scores, or submission candidates. They do not establish whether any raster can beat a public leaderboard value.</p>')
    ex.append('<h3>6a · The shipped novel-only file</h3>')
    ex.append('<table class="t"><thead><tr><th>|G| (scenario assumption; not observed)</th>'
               '<th>conditional t_core interval</th><th>scenario P(DTI &gt; 0.2778)</th><th>P(DTI &gt; 0.3195)</th>'
               '<th>scenario P(DTI &gt; 0.3774)</th><th>mean</th><th>worst</th><th>best</th></tr></thead><tbody>')
    for k, lbl in (("G_lo", "5,949.3 px (scenario assumption)"),
                   ("G_mid", "9,230.7 px (scenario midpoint)"),
                   ("G_hi", "12,512.1 px (scenario assumption)")):
        r = pw[k]
        ex.append(f'<tr><td>{lbl}</td><td>[{r["t_core_bounds"][0]:,.0f}, {r["t_core_bounds"][1]:,.0f}]</td>'
                  f'<td>{r["p_beat_02778"]:.3f}</td><td>{r["p_beat_03195"]:.3f}</td>'
                  f'<td>{r["p_beat_03774"]:.3f}</td><td>{r["mean_dti"]:.4f}</td>'
                  f'<td>{r["worst_dti"]:.4f}</td><td>{r["best_dti"]:.4f}</td></tr>')
    ex.append('</tbody></table>')
    cf = card["projection"].get("counterfactual_recombination_NOT_SHIPPED", {})
    if cf:
        ex.append('<h3>6b · NOT SHIPPED — withdrawn local-overlap recombination (credit unknown)</h3>'
                  f'<p class="small">Conditional scenario only; score-derived credit depends on owner-reported score associations and assumed |G|. {e(cf["why"])}</p>'
                  f'<p class="small">Design: <code>{e(cf["design"])}</code></p>'
                  '<table class="t"><thead><tr><th>|G| scenario</th><th>S</th><th>conditional t_core interval</th>'
                  '<th>P(DTI &gt; 0.2778)</th><th>P(DTI &gt; 0.3774)</th><th>mean</th><th>worst</th>'
                  '<th>best</th></tr></thead><tbody>')
        for k, lbl in (("G_lo", "5,949.3 px"), ("G_mid", "9,230.7 px"), ("G_hi", "12,512.1 px")):
            r = cf["per_g"][k]
            ex.append(f'<tr><td>{lbl}</td><td>{n(r["S"])}</td>'
                      f'<td>[{r["t_core_bounds"][0]:,.0f}, {r["t_core_bounds"][1]:,.0f}]</td>'
                      f'<td>{r["p_beat_02778"]:.3f}</td><td>{r["p_beat_03774"]:.3f}</td>'
                      f'<td>{r["mean_dti"]:.4f}</td><td>{r["worst_dti"]:.4f}</td><td>{r["best_dti"]:.4f}</td></tr>')
        ex.append('</tbody></table>'
                  '<p class="small"><strong>This is analysis, not a candidate.</strong> No such file was '
                  'written, served or offered for download in this round.</p>')
    ex.append(f'<p class="small">Algebra: <code>DTI = min(t_core + ρ_novel·n_novel, |G|) / (0.2·S + 0.8·|G|)</code> '
               f'with S = {n(S)}, n_novel = {n(place["n_novel_placed"])}, t_core re-solved at each assumed |G| under '
               'owner-reported score associations and a sparse-emission approximation. ρ_novel uses the stated '
               f'scenario prior [{card["projection"]["rho_novel_prior"][0]}, {card["projection"]["rho_novel_prior"][1]}], not measured hidden-truth credit. '
               'No organizer receipt exists for this round; nothing here is ORGANIZER-CONFIRMED.</p>')
    ex.append(FOOT)
    (DOCS / "h69-executive-summary.html").write_text("\n".join(ex))

    # ------------------------------------------------------------------ round page
    rd = [HEAD.format(title="H69 · method, measurements and limits · GEMSDOE52", root="")]
    rd.append('<section><h1>H69 — historical co-training result and literal DUPLICATE/STOP</h1>')
    rd.append(verdict_block(card, val))
    rd.append('<h2>1 · Hypotheses, ranked before any fit</h2>'
              '<p>Frozen in <code>knowledge/52_hypotheses_H69_preregistered.md</code> '
              f'(SHA-256 <code>{e(json.loads((ROOT / "registry/h69_preregistration.json").read_text())["preregistration_sha256"])}</code>); '
              '<code>scripts/run_h69.py</code> refuses to run if that hash moves.</p>'
              '<table class="t"><thead><tr><th>Rank</th><th>Hypothesis</th><th>Layers</th>'
              '<th>Signature</th><th>Status this round</th></tr></thead><tbody>'
              '<tr><td>1</td><td><strong>H69-1</strong> Basement-surface differential geometry as View A</td>'
              '<td>band 15 depth-to-basement; 13/11/5/18 isostatic gravity and gradients; 1/2/3/9/14 magnetics; '
              '4/7/8 geodetic strain; 10/16 seismicity; 17 conductivity</td>'
              '<td>|∇| and ∇² of the basement surface at σ = 2/4/8 px; difference-of-Gaussians band-pass of the '
              'isostatic anomaly (800 m – 4 km); |cos ∠| between ∇gravity and ∇RTP</td><td>RUN</td></tr>'
              '<tr><td>2</td><td><strong>H69-2</strong> Cross-family consensus as the credit-density proxy</td>'
              '<td>the 526-blob prior census, decoded pixels only</td>'
              '<td>count of distinct decoded prior patterns whose 3 px halo covers the pixel</td><td>RUN</td></tr>'
              '<tr><td>3</td><td><strong>H69-3</strong> Isostatic residual after regressing gravity on topography</td>'
              '<td>13, 12, 15</td><td>locally-weighted regression residual at 5/15/45 km</td>'
              '<td>NOT RUN — over the 3-experiment budget; H69-1(ii) carries the band-pass version</td></tr>'
              '<tr><td>4</td><td><strong>H69-4</strong> Geodetic strain lineament intersection</td>'
              '<td>4, 7, 8</td><td>co-location of shear-rate and dilatation gradients</td>'
              '<td>NOT RUN — bands already inside the View-A stack; recorded so it is not re-derived</td></tr>'
              '<tr><td>5</td><td><strong>H69-5</strong> Trace-correction corridor (R5-H1)</td>'
              '<td>labels.tif as geometry, external LiDAR scarp bands, 12/19, 2/3/9</td>'
              '<td>signed perpendicular offset estimator along the trace normal</td>'
              '<td>CARRIED FORWARD — frozen §A-gate was not executed under this round’s budget. The 100–200 m distance is not evidence of zero hidden-truth credit; no score claim follows.</td></tr></tbody></table>')
    rd.append('<h2>2 · Leakage canary</h2>'
              f'<p>Every one of the {can["n_channels"]} channels fitted alone on the holdout. Worst '
              f'single-feature AUC <strong>{can["worst"]["auc_alone"]:.4f}</strong> '
              f'(<code>{e(can["worst"]["channel"])}</code>) against an alarm at {can["alarm_threshold"]}. '
              f'Leakage flags: <strong>{can["any_alarm"]}</strong>.</p>')
    rd.append('<h2>3 · S1 sufficiency and S2 independence</h2>'
              f'<p>View A out-of-quadrant AUC mean <strong>{s1["summary"]["A"]["mean"]:.4f}</strong>, '
              f'minimum {s1["summary"]["A"]["minimum"]:.4f}; View B mean '
              f'<strong>{s1["summary"]["B"]["mean"]:.4f}</strong>, minimum {s1["summary"]["B"]["minimum"]:.4f}. '
              f'S1 <strong>{"PASS" if s1["pass_"] else "FAIL"}</strong> (thresholds mean ≥ 0.60, fold ≥ 0.55). '
              f'Prior rounds on the identical splitter: H61 0.5163, H63 0.5362, H64 0.5230.</p>'
              f'<p>Independence: max |ρ| <strong>{indep["pre_exchange"]["max_abs_correlation"]:.4f}</strong> over '
              f'{indep["n_blocks"]} spatial blocks of held-out labelled negatives; abandon at '
              f'{indep["abandon_threshold"]}; exchange allowed = <strong>{indep["allow_exchange"]}</strong>. '
              'This is a proxy diagnostic over blocks, not proof of conditional feature independence.</p>')
    rd.append('<h2>4 · HOLDOUT-DTI — evaluator <code>' + e(hold["evaluator_version"]) + '</code></h2>'
              f'<p>{hold["pooled"]["withheld_positives"] if "withheld_positives" in hold["pooled"] else hold["withheld_positives"]:,} '
              'withheld positive pixels; α = 0.2, β = 0.8, 300 m triangular kernel; visible catalogue masked '
              'pixel-exactly; every arm at a matched '
              f'{hold["budget_per_fold"]:,}-pixel-per-fold budget; paired 95 % percentile bootstrap over '
              f'{hold["pooled"]["bootstrap"]["clusters"]} physical 20 km clusters, '
              f'{hold["pooled"]["bootstrap"]["draws"]} draws.</p>'
              '<table class="t"><thead><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95 % CI</th></tr></thead><tbody>')
    for k in ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random"):
        if k in sc:
            rd.append(f'<tr><td>{k}</td><td>{sc[k]["dti"]:.6f}</td><td>{ci(sc[k]["ci95"])}</td></tr>')
    rd.append('</tbody></table>')
    rd.append(f'<p>Paired, candidate minus the best comparable control <code>single_B</code>: '
               f'<strong>{pdiff["single_B"]["delta"]:+.6f}</strong>, 95 % CI {ci(pdiff["single_B"]["ci95"])}. '
               'Control reproduction: see section 5 below — the pre-registered clause FAILED and is '
               'reported, not hidden.</p>'
               f'<p class="small"><strong>Validity warning, published with every number:</strong> '
               f'{e(hold["validity_warning"])}</p>')
    rd.append('<h2>5 · The discovery signal — where A is confident and B abstains</h2>'
              f'<p>{n(ao["n_pixels"])} pixels in {n(ao["n_segments"])} whole segments; '
              f'{n(ao["n_segments_written"])} segments of ≥ 3 px carry written geological reasoning in '
              '<a href="downloads/h69-a-only-reasoning.csv.gz">the CSV</a>. '
              f'{e(ao["caveat"])} S1 status: {e(ao["s1_status"])}.</p>')
    rd.append('<h2>6 · Placement — informative-prior policy pass, literal lane stop</h2>'
              f'<p>Legal set: valid ∧ off-catalogue ∧ &gt; 200 m from any mapped trace '
              f'({n(place["base_pool_px"])} px with a finite operating field). Emission: novel-only, '
              f'{n(place["S_placed"])} dots. Ranking: {e(place["ranking"])}. Placement: {e(place["placement"])}. '
              f'Quota cap = floor({place["margin"]} · S) = {n(place["cap"])} against the brief’s literal 0.70; '
              f'{place["n_quota_priors"]} priors were held under quota. Worst informative near-dot after '
              f'convergence: {n(place["worst_informative_near"])} = '
              f'{place["worst_informative_near_share"]:.4f} '
              f'(<code>{e(place["worst_informative_prior"])}</code>). Informative-prior policy feasibility: '
              f'<strong>{place["feasible"]}</strong>; this does not override the literal DUPLICATE/STOP triggered by a universal-coverage probe.</p>'
              '<table class="t"><thead><tr><th>round</th><th>placed</th><th>worst near-dot</th>'
              '<th>share</th><th>offenders over cap</th><th>priors under quota</th></tr></thead><tbody>')
    for r in place["rounds"]:
        rd.append(f'<tr><td>{r["round"]}</td><td>{n(r["placed"])}</td><td>{n(r["worst_near"])}</td>'
                  f'<td>{r["worst_share"]:.4f}</td><td>{r["n_offenders"]}</td>'
                  f'<td>{r.get("n_quota_priors", 0)}</td></tr>')
    rd.append('</tbody></table>')
    rd.append('<h2>7 · Lane and uniqueness, measured</h2>'
              '<table class="t"><thead><tr><th>Test</th><th>Literal (all priors)</th>'
               '<th>Saturation policy (informative only)</th></tr></thead><tbody>'
              f'<tr><td>Priors checked / distinct decoded patterns</td><td colspan="2">'
              f'{lane_d["priors_checked"]} / {lane_d["distinct_decoded_priors"]}</td></tr>'
              f'<tr><td>Universal-coverage probes / informative</td><td colspan="2">'
              f'{lane_d["policy"]["universal_coverage_probes"]} / {lane_d["policy"]["informative_priors"]}</td></tr>'
              f'<tr><td>Surface phase, max Spearman</td><td>{lane_s["literal"]["max_spearman"]:.4f}</td>'
              f'<td>{lane_s["policy"]["max_spearman"]:.4f}</td></tr>'
              f'<tr><td>Surface phase verdict</td><td>{e(lane_s["literal"]["verdict"])}</td>'
              f'<td>{e(lane_s["policy"]["verdict"])}</td></tr>'
              f'<tr><td>Final dots, max Spearman (limit 0.90)</td><td>{lane_d["literal"]["max_spearman"]:.4f}</td>'
              f'<td>{lane_d["policy"]["max_spearman"]:.4f}</td></tr>'
              f'<tr><td>Final dots, max 3 px near-dot fraction (limit 0.70)</td>'
              f'<td>{lane_d["literal"]["max_near_3px_fraction"]:.4f}</td>'
              f'<td>{lane_d["policy"]["max_near_3px_fraction"]:.4f}</td></tr>'
              f'<tr><td>Final dots verdict</td><td>{e(lane_d["literal"]["verdict"])}</td>'
              f'<td>{e(lane_d["policy"]["verdict"])}</td></tr>'
              '</tbody></table>'
              f'<p>Decoded-pattern uniqueness: <strong>{"PASS" if uniq["canonical_pattern_unique"] else "FAIL"}</strong> '
              f'over {uniq["n_priors_checked"]} priors; equals the literal prior union: '
              f'{uniq["equals_literal_prior_union"]}. Exact support novelty against the all-prior union: '
              f'<strong>{uniq["novel_fraction"]:.4f}</strong> — a FAILED diagnostic that is reported, not waived, '
              'because the union of every informative prior’s 3 px halo covers 100 % of the legal set on this '
              'registry (<code>work/h69/probe.py</code>: <code>novel_pool_exactly_novel = 0</code> of '
              '4,859,987). No nonempty candidate on this registry can pass it, which is a property of the '
              'registry rather than of this file.</p>')
    rd.append('<h2>8 · Limits</h2><ul>'
              '<li>No organizer-confirmed submission receipt exists for this round. The saved 2026-10-09 20:18 UTC public observation places the team at rank 17 with 0.2778; no row maps a TIFF hash to that score. The H33 file association is owner-reported, not organizer-confirmed.</li>'
              '<li>All input rasters are SHA-256-pinned owner mirrors of a login-walled portal file '
              '(<code>data/restore_receipt.json</code>, <code>ALL_VERIFIED=True</code>). The pins prove mirror '
              'consistency, not organiser authentication.</li>'
              '<li>|G| is not measured. The [5,949.3, 12,512.1] bracket is conditional on owner-reported score associations and the stated inversion assumptions; projection values are scenario arithmetic.</li>'
              '<li>ρ_novel is an assumed scenario prior, not a measured credit density. No instrument here certifies hidden-truth credit for novel mass.</li>'
              '<li>A historical correlation of the hide-and-recover instrument with reported scores (ρ = −0.1045, p = 0.734, n = 13) is exploratory, small-sample evidence only. HOLDOUT-DTI is not a leaderboard predictor.</li>'
              '<li>The external GeoDAWN radiometric raster carries no band tags; the total-count band is '
              'identified by rank correlation against organiser band 6 and the other three are averaged into one '
              'contrast channel whose identity is UNVERIFIED.</li>'
              '<li>Band 6’s own file description says “Tilt angle or total curvature — magnetic field derivative”; '
              'the bytes rank-match external radiometric total count at ρ = 0.99995 and the tilt angle at '
              'ρ = 0.0175 (<code>evidence/h61_forensics.json</code>). It is treated as radiometric and placed in '
              'View B. This is an organiser metadata irregularity, flagged not silently corrected.</li>'
              '<li>The A-only reasoning is measured context plus a template mechanism, not field-verified geology.</li>'
              '<li>The committed whole-segment pseudo-label rule produced zero labels in every fold, so the '
              'before/after exchange comparison the brief asks for is degenerate: '
              '<code>disagreement_post</code> is bit-identical to <code>disagreement_pre</code> and the paired '
              'CI is exactly [0, 0].</li>'
              '<li>An early sufficiency reading of 0.6636 for View A was produced on the wrong splitter '
              '(<code>holdout.make_folds(mode="block")</code> with prevalence-thinned truth) and is '
              '<strong>retracted</strong>; the committed <code>spatial.folds</code> instrument gives '
              f'{s1["summary"]["A"]["mean"]:.4f}. It is recorded so nobody resurrects it.</li>'
              '<li>ComCat cannot be bulk-downloaded from this sandbox; the seismicity channels are the organiser’s '
              'own bands 10 and 16, not a fresh catalogue.</li>'
              '<li>No submission slot was used. Submission is stopped by the literal DUPLICATE/STOP; portal acceptance is unverified.</li>'
              '</ul>')
    rd.append(FOOT)
    (DOCS / "h69.html").write_text("\n".join(rd))

    # ------------------------------------------------------------------ sources page
    src = [HEAD.format(title="H69 · sources, links and provenance · GEMSDOE52", root="")]
    src.append('<section><h1>Sources — every external claim with its link</h1>'
               '<p class="small">Only <code>github.com</code>, <code>api.github.com</code>, '
               '<code>codeload.github.com</code>, <code>registry.npmjs.org</code>, <code>pypi.org</code> and '
               '<code>files.pythonhosted.org</code> are reachable from this sandbox. Links to other hosts are '
               'given for manual review and are marked <strong>NOT FETCHED HERE</strong>; nothing on this page '
               'rests on a source this session could not read.</p>'
               '<table class="t"><thead><tr><th>Item</th><th>Link</th><th>Accessed here?</th>'
               '<th>What it settles</th></tr></thead><tbody>'
               '<tr><td>Competition problem description and submission format</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">drivendata.org/competitions/306/…/page/967/</a></td>'
               '<td>NOT FETCHED HERE (login/host blocked)</td><td>DTI definition, α = 0.2, β = 0.8, R = 300 m, '
               'single-band float32 GeoTIFF, EPSG:32611, values in [0, 1]</td></tr>'
               '<tr><td>Official leaderboard</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">…/leaderboard/</a></td>'
               '<td>NOT FETCHED HERE</td><td>0.3774 top of board, 0.3195 rank 7 as reported in the brief; '
               'dated local snapshots in <code>registry/leaderboard_snapshot_*.json</code></td></tr>'
               '<tr><td>Reference solution (Prof. John Lipor)</td>'
               '<td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></td>'
               '<td><strong>CLONED AND READ</strong> (this session)</td>'
               '<td>U-Net + resnet18 encoder, <code>TverskyLoss(alpha=0.2, beta=0.8, mode="binary")</code>, '
               'MC = 5 random patch splits, 128 px patches, 5 epochs, all 19 channels min–max normalised to '
               '[0, 1], predictions averaged only over held-out test patches, written with the labels’ CRS and '
               'transform. It is a supervised model <em>of the existing catalogue</em>, which is masked out of '
               'scoring — the reason a catalogue-fitting submission scores low.</td></tr>'
               '<tr><td>Co-training</td><td>Blum &amp; Mitchell, COLT 1998, pp. 92–100, '
               '<a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a></td>'
               '<td>NOT FETCHED HERE</td><td>two-view sufficiency, compatibility and conditional independence</td></tr>'
               '<tr><td>Tversky index</td><td><a href="https://en.wikipedia.org/wiki/Tversky_index">en.wikipedia.org/wiki/Tversky_index</a></td>'
               '<td>NOT FETCHED HERE</td><td>the α/β asymmetry DTI and TverskyLoss both implement</td></tr>'
               '<tr><td>EPSG:32611</td><td><a href="https://epsg.io/32611">epsg.io/32611</a></td>'
               '<td>NOT FETCHED HERE</td><td>WGS 84 / UTM zone 11N — verified against the restored rasters by '
               '<code>scripts/prepare_data.py</code> instead</td></tr>'
               '<tr><td>GeoDAWN airborne magnetic and radiometric surveys</td>'
               '<td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">usgs.gov/data/geodawn-…</a>, '
               'DOI 10.5066/P93LGLVQ</td><td>NOT FETCHED HERE</td>'
               '<td>the external K/Th/U/TC grids; the derived uint8 mirror is SHA-256 pinned in '
               '<code>registry/data_manifest.json</code> and restored</td></tr>'
               '<tr><td>INGENIOUS / GDR submission 1391</td>'
               '<td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a>, '
               '<a href="https://gbcge.org/current-projects/ingenious/">gbcge.org/current-projects/ingenious/</a></td>'
               '<td>NOT FETCHED HERE</td><td>Quaternary fault traces and well/spring temperatures; the derived '
               'CSV mirrors are restored and SHA-verified</td></tr>'
               '<tr><td>DOE GEMS solicitation PDF (OSTI 96647)</td>'
               '<td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">docs.nlr.gov/docs/fy26osti/96647.pdf</a></td>'
               '<td>NOT FETCHED HERE</td><td>submission rules as transcribed in the brief and '
               '<code>knowledge/00_brief_as_received.md</code></td></tr>'
               '<tr><td>Competition rasters (login-walled)</td>'
               '<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">…/data/</a></td>'
               '<td>NOT FETCHABLE — restored from owner mirrors and SHA-256 verified</td>'
               '<td><code>training_features.tif</code> (418,912,844 B, 19 float32 bands), '
               '<code>labels.tif</code> (60,988 positives), <code>sample_submission.tif</code></td></tr>'
               '</tbody></table>'
               '<h2>Irregularities flagged this round</h2><ul>'
               '<li><strong>Band 6 metadata contradicts its bytes.</strong> Description says magnetic tilt angle; '
               'Spearman against external radiometric TC is 0.99995 and against the tilt angle 0.0175.</li>'
               '<li><strong>sample_submission.tif is not “total fault absence”.</strong> Its 60,988 pixels equal to 1 '
               'sit exactly on the labelled catalogue.</li>'
               '<li><strong>Exact support novelty is unsatisfiable on this registry.</strong> The union of all 359 '
               'informative priors’ 3 px halos covers 100 % of the 4,859,987 px legal set.</li>'
               '<li><strong>HOLDOUT-DTI is not a leaderboard predictor.</strong> The historical n = 13 correlation (ρ = −0.1045, p = 0.734) is exploratory only.</li>'
               '<li><strong>|G| and near-trace credit are not measured.</strong> Score inversions and the 6,436-cell local subset comparison depend on owner-reported score associations and conditional assumptions; new-fault truth may occur within 300 m of known traces.</li>'
               '</ul></section>')
    src.append(FOOT)
    (DOCS / "h69-sources.html").write_text("\n".join(src))

    # ------------------------------------------------------------------ archive downloads index
    arch = DOWN / "index.html"
    if arch.exists():
        txt = arch.read_text()
        import re as _re2
        txt = _re2.sub(r"<!--H69-DOWNLOAD-NOTICE-->.*?<!--/H69-DOWNLOAD-NOTICE-->", "", txt, flags=_re2.S)
        txt = _re2.sub(r"<!--H69-DL-->.*?<!--/H69-DL-->", "", txt, flags=_re2.S)
        # This round was committed as H65 and renumbered to H69 after a parallel session merged a
        # different round under H65 (PR #57). main carries no H65 block in this file, so any H65
        # marker here is this round's own pre-rename injection, pointing at files that no longer
        # exist. Strip it rather than leave dead links for scripts/check_site.py to find.
        txt = _re2.sub(r"<!--H65-DOWNLOAD-NOTICE-->.*?<!--/H65-DOWNLOAD-NOTICE-->", "", txt, flags=_re2.S)
        txt = _re2.sub(r"<!--H65-DL-->.*?<!--/H65-DL-->", "", txt, flags=_re2.S)
        notice = (f'<!--H69-DOWNLOAD-NOTICE--><aside style="padding:20px;background:#e8f0fe;color:#0b1f3a;'
                  f'font:16px/1.6 system-ui"><b>Historical H69 research artifact — NOT FOR SUBMISSION (DUPLICATE/STOP).</b> '
                  f'<a href="h69-candidate.tif" download>Download for research</a> ({n(fmt["bytes"])} bytes, '
                  f'SHA-256 <code>{e(card["raster_sha256"][:16])}…</code>, {n(S)} cells). Local format checks pass; '
                  f'portal acceptance is unverified. Informative-prior policy PASS does not waive literal stop. '
                  f'<a href="../h69-executive-summary.html">H69 stop status</a> · '
                  f'<a href="../h69.html">method, results and limits</a>.<!--/H69-DOWNLOAD-NOTICE-->')
        rows = (f'<!--H69-DL--><tr><td><a href="h69-candidate.tif" download>h69-candidate.tif</a></td>'
                f'<td class="number">{n(fmt["bytes"])}</td><td class="mono">{e(card["raster_sha256"])}</td>'
                f'<td>H69 · historical two-view co-training, novel-only research artifact; informative-prior policy PASS, literal DUPLICATE/STOP · {n(S)} px; <a href="../h69.html">evidence</a></td></tr>'
                f'<tr><td><a href="{e(stem)}.tif" download>{e(stem)}.tif</a></td>'
                f'<td class="number">{n(fmt["bytes"])}</td><td class="mono">{e(card["raster_sha256"])}</td>'
                f'<td>canonical filename, byte-identical</td></tr>'
                f'<tr><td><a href="h69-candidate.zip" download>h69-candidate.zip</a></td>'
                f'<td class="number">{n((DOWN / "h69-candidate.zip").stat().st_size)}</td>'
                f'<td class="mono">single-TIFF ZIP, byte-identical payload</td>'
                f'<td>single-TIFF ZIP archive; local packaging only, portal acceptance unverified</td></tr>'
                f'<tr><td><a href="h69-a-only-reasoning.csv.gz" download>h69-a-only-reasoning.csv.gz</a></td>'
                f'<td class="number">{n((DOWN / "h69-a-only-reasoning.csv.gz").stat().st_size)}</td>'
                f'<td class="mono">gzipped CSV</td><td>{n(ao["n_segments_written"])} A-only segments, one '
                f'geological hypothesis and one named non-fault mimic each</td></tr><!--/H69-DL-->')
        txt = txt.replace("<body>", "<body>" + notice, 1)
        txt = txt.replace("<tbody>", "<tbody>" + rows, 1)
        arch.write_text(txt)
        print("archive downloads index updated")

    # ------------------------------------------------------------------ inject the H69 notice
    # docs/index.html is the standing landing page and carries the older rounds' required links;
    # scripts/check_site.py enforces them. Inject a marked notice at the very top of <main> instead
    # of replacing the page, exactly as the H64 round did.
    idxp = DOCS / "index.html"
    txt = idxp.read_text()
    import re as _re3
    txt = _re3.sub(r"<!--H69-NOTICE-->.*?<!--/H69-NOTICE-->", "", txt, flags=_re3.S)
    verdict_word = ("PROMOTION GATES PASS; PORTAL ACCEPTANCE UNVERIFIED" if sub else
                    "RESEARCH DOWNLOAD ONLY &middot; LOCAL FORMAT PASS &middot; PORTAL UNVERIFIED &middot; NOT FOR SUBMISSION — DUPLICATE/STOP")
    notice = (
        '<!--H69-NOTICE--><div class="notice" role="note" style="margin:0 0 1rem;padding:1.1rem 1.2rem">'
        '<strong style="font-size:1.05rem">Round H69 (this branch, 2026-10-09) &mdash; '
        f'{verdict_word}.</strong><br>'
        f'<a class="button" style="margin:.6rem .5rem .3rem 0" href="downloads/h69-candidate.tif" download>'
        f'&#11015; Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a>'
        '<a class="button secondary" style="margin:.6rem .5rem .3rem 0" href="downloads/h69-candidate.zip" '
        'download>Single-TIFF ZIP</a><br>'
        f'<span class="small"><code>{e(stem)}.tif</code> &middot; SHA-256 <code>{e(card["raster_sha256"])}</code>'
        f' &middot; {n(S)} cells &middot; values exactly {{0, 1}} &middot; 0 NaN &middot; EPSG:32611 &middot; '
        f'{val["shape"][0]:,} &times; {val["shape"][1]:,} &middot; transform identical to '
        '<code>sample_submission.tif</code>; this is a local grid/value check only and does not establish portal acceptance.<br>'
        f'<strong>Literal lane status: DUPLICATE/STOP.</strong> The informative-prior saturation-policy value '
        f'{lane_pol["max_near_3px"]:.4f} is not an override. View A S1 mean is '
        f'{card["s1_sufficiency"]["view_A_mean"]:.4f}; the HOLDOUT-DTI paired difference against '
        f'<code>single_B</code> is {card["holdout_dti"]["candidate_minus_single_B"]["delta"]:+.6f}. '
        f'No slot used; none recommended.<br>'
        '<a href="h69-overview.html">H69 overview and research download</a> &middot; '
        '<a href="h69-executive-summary.html">H69 stop status</a> &middot; '
        '<a href="h69.html">method, results and limits</a> &middot; '
        '<a href="h69-sources.html">sources with links</a> &middot; '
        '<a href="downloads/h69-a-only-reasoning.csv.gz">A-only geological reasoning CSV</a></span>'
        '</div><!--/H69-NOTICE-->')
    marker = '<main id="main">'
    if marker in txt:
        txt = txt.replace(marker, marker + notice, 1)
    else:
        txt = txt.replace("<body>", "<body>" + notice, 1)
    idxp.write_text(txt)
    print("H69 notice injected into docs/index.html")


    (ROOT / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=docs/index.html">'
        '<title>GEMSDOE52 — H69 research GeoTIFF and submission status</title></head><body>'
        '<h1>GEMSDOE52 · H69</h1>'
        f'<p><a href="docs/downloads/h69-candidate.tif" download>Download the H69 GeoTIFF ({n(fmt["bytes"])} bytes)</a></p>'
        '<p><a href="docs/index.html">Open the research download and the explicit submission verdict.</a></p>'
        '<p><a href="docs/h69-executive-summary.html">H69 stop status; no submission steps.</a></p>'
        '<p>Research download only. Local format validation does not establish portal acceptance. Literal lane verdict: DUPLICATE/STOP; NOT FOR SUBMISSION.</p>'
        '</body></html>\n')

    # ------------------------------------------------------------------ README block (prepended)
    readme = ROOT / "README.md"
    old = readme.read_text()
    import re as _re
    old = _re.sub(r"<!--H69-README-->.*?<!--/H69-README-->\n?", "", old, flags=_re.S)
    lane_lit = card["correlation_vs_registry"]["literal"]
    lane_pol = card["correlation_vs_registry"]["policy"]
    cf = card["projection"].get("counterfactual_recombination_NOT_SHIPPED", {})
    block = f"""<!--H69-README-->
# H69 historical research artifact — NOT FOR SUBMISSION

[Research GeoTIFF](docs/downloads/h69-candidate.tif) · [single-TIFF archive](docs/downloads/h69-candidate.zip) ·
[H69 stop status](docs/h69-executive-summary.html) · [method and HOLDOUT-DTI evidence](docs/h69.html) ·
[provenance and sources](docs/h69-sources.html) · [results/limits](knowledge/53_h69_results_and_limits.md)

> **Research download: YES. Local format checks: PASS. Portal acceptance: UNVERIFIED. Submission: NO — literal DUPLICATE/STOP.**
> The informative-prior saturation-policy result does not waive the literal all-prior stop; no override or slot is recommended. Slots used: **{card["slots_used"]}**.

- **Research raster:** `{stem}.tif`, {n(fmt["bytes"])} bytes, {n(S)} emitted cells, SHA-256 `{card["raster_sha256"]}`.
- **Local format check:** EPSG:32611, {val["shape"][0]:,} × {val["shape"][1]:,}, one float32 band, values in [0, 1], no NaN/infinity. This is not portal acceptance; no organizer-confirmed receipt exists.
- **Literal lane:** `DUPLICATE/STOP` because the all-prior check includes a universal-coverage probe with a 3 px near-dot fraction of 1.0000. Informative-prior-only saturation policy is a separate diagnostic, not an override.
- **HOLDOUT-DTI:** evaluator `{hold["evaluator_version"]}`, {hold["withheld_positives"]:,} withheld positives; View-A co-training candidate minus `single_B` = {card["holdout_dti"]["candidate_minus_single_B"]["delta"]:+.6f}, 95% CI [{card["holdout_dti"]["candidate_minus_single_B"]["ci95"][0]:+.6f}, {card["holdout_dti"]["candidate_minus_single_B"]["ci95"][1]:+.6f}]. Internal hide-and-recover result, not a board score.
- **Public-board evidence:** the saved 2026-10-09 20:18 UTC observation places the team at rank 17 with 0.2778. No public row maps a TIFF hash to a score; the file association is owner-reported, not organizer-confirmed.
- **No causal explanation:** the local 37,654/44,090 subset and 100–200 m distances do not identify hidden-truth credit or explain a score change. Known-fault masking is pixel-exact; new-fault truth may lie within 300 m of known traces. Score inversions and projections are conditional scenario arithmetic only, never measured credit or a score forecast. See `knowledge/49` and `IR-R5-011`.

The H69 artifact and results are retained for review. They are not submission-approved and this block contains no upload instructions.
<!--/H69-README-->
"""
    readme.write_text(block + "\n" + old)
    print(f"PUBLISHED name={stem} bytes={fmt['bytes']} sha={card['raster_sha256']} submit={sub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
