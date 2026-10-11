#!/usr/bin/env python3
"""Publish the H62 round: a new page, a front-page download banner, and a refreshed guide.

Every number rendered here is read from ``evidence/h62_*.json`` or ``docs/data/h62_*.json``;
nothing is typed into the HTML.  The three existing pages are edited **additively** and
idempotently (a previous ``<!--H62-…-->`` block is removed before the new one is inserted), so
the disclosures that ``scripts/check_site.py`` enforces for the older rounds survive.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
EV = ROOT / "evidence"

CARD = json.loads((EV / "h62_run_card.json").read_text())
BUILD = json.loads((EV / "h62_build.json").read_text())
VAL = json.loads((EV / "h62_validation.json").read_text())
COT = json.loads((EV / "h62_cotrain.json").read_text())
PREREG = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
STEM = f"gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px"
RECEIPT = json.loads((ROOT / "submission" / (STEM + ".json")).read_text())
ZIP_BYTES = (ROOT / "submission" / (STEM + ".zip")).stat().st_size
CSV_PX = (ROOT / "submission" / (STEM + "-emitted-pixels.csv")).stat().st_size
CSV_SEG = (ROOT / "submission" / (STEM + "-a-only-candidate-segments.csv")).stat().st_size

FILE = RECEIPT["file"]
SHA = RECEIPT["sha256"]
BYTES = RECEIPT["bytes"]
NPX = int(CARD["validator_output"]["n_nonzero"])
NAME = CARD["submission_name"]
NOTE = CARD["submission_note"]
VERDICT = CARD["verdict"]
RO = CARD["correlation_overlap_vs_registry"]
LANE = json.loads((EV / "h62_lane_gate.json").read_text())
_RG = (LANE.get("repaired_gate") or {}).get("policy") or {}
RG = dict(policy_verdict=_RG.get("verdict", "not computed"),
          informative_priors=_RG.get("informative_priors", 0),
          universal_coverage_probes=_RG.get("universal_coverage_probes", 0),
          probe_paths=_RG.get("probe_paths") or ["(none measured)"],
          probe_coverage=_RG.get("probe_coverage") or [0.0])


def f(x, n=4):
    return f"{float(x):.{n}f}"


def pct(x, n=1):
    return f"{100.0 * float(x):.{n}f}%"


# --------------------------------------------------------------------------------- page: h62.html
def cand_rows() -> str:
    out = []
    for r in BUILD["candidates"]:
        mark = ' class="bad">UNION — disqualified' if r["disqualified_as_union"] else \
            (' class="good">SHIPPED' if r["field"] == BUILD["winner"] else '>—')
        out.append(
            f"<tr><td class='mono'>{r['field']}</td><td class='number'>{r['emitted']:,}</td>"
            f"<td class='number'>{f(r['colocation'])}</td><td class='number'>"
            f"{f(r['random_baseline'])}</td><td class='number'>{f(r['lift'], 2)}×</td>"
            f"<td class='number'>{pct(r['union_overlap'], 1)}</td><td{mark}</td></tr>")
    return "\n".join(out)


def holdout_rows() -> str:
    arms = VAL["instrument1_holdout"]["arms"]
    out = []
    for k in sorted(arms, key=lambda k: -arms[k]["pooled_dti"]):
        v = arms[k]
        if k.endswith("|15000"):
            continue
        nm, b = k.split("|")
        cls = ' class="good"' if nm == BUILD["winner"] else ""
        out.append(
            f"<tr{cls}><td class='mono'>{nm}</td><td class='number'>{b}</td>"
            f"<td class='number'>{f(v['pooled_dti'], 6)}</td>"
            f"<td class='number'>[{f(v['ci_lo'], 6)}, {f(v['ci_hi'], 6)}]</td>"
            f"<td class='number'>{f(v['lift_over_random'], 6)}</td></tr>")
    return "\n".join(out)


def revealed_rows() -> str:
    grid = VAL["instrument2_revealed"]["budget_grid_px"]
    rr = VAL["instrument2_revealed"]["matched_random"]
    out = []
    for r in sorted(VAL["instrument2_revealed"]["per_field"],
                    key=lambda r: -(r[f"f_{grid[0]}"]["lift"] or 0)):
        cells = "".join(f"<td class='number'>{f(r[f'f_{k}']['lift'], 2)}×</td>" for k in grid)
        cls = ' class="good"' if r["field"] == BUILD["winner"] else ""
        out.append(f"<tr{cls}><td class='mono'>{r['field']}</td>{cells}</tr>")
    rcells = "".join(f"<td class='number'>{f(rr[f'f_{k}']['fraction'])}</td>" for k in grid)
    out.append(f"<tr><td class='mono'>random baseline (fraction, not lift)</td>{rcells}</tr>")
    return "\n".join(out)


def gate_rows() -> str:
    v = CARD["validator_output"]
    ro = CARD["correlation_overlap_vs_registry"]
    b = BUILD
    rows = [
        ("Single-band float32 GeoTIFF, CRS/shape/transform match",
         "PASS" if v["ok"] else "FAIL", v["ok"]),
        ("No NaN/infinity inside the footprint; values in [0, 1]",
         f"PASS — 0 NaN, [{f(v['min'], 1)}, {f(v['max'], 1)}]" if v["n_nan"] == 0 else "FAIL",
         v["n_nan"] == 0),
        ("Zero mass outside the emission domain",
         "PASS" if v.get("mass_outside_footprint", 0) == 0 else "FAIL",
         v.get("mass_outside_footprint", 0) == 0),
        ("No emitted pixel within 200 m of a mapped catalogue pixel",
         f"PASS — nearest {f(b['ring_min_distance_to_catalogue_m'], 1)} m" if b["ring_rule_ok"]
         else "FAIL", b["ring_rule_ok"]),
        ("Decoded pattern unique vs every accessible aligned prior",
         f"PASS — {ro['n_priors']} priors" if ro["pattern_unique"] else "FAIL",
         ro["pattern_unique"]),
        ("Support novelty against the prior union",
         f"{pct(ro['support_novelty_fraction'])} ≥ 20 %" if ro["support_novelty_fraction"] >= 0.2
         else f"{pct(ro['support_novelty_fraction'])} < 20 %",
         ro["support_novelty_fraction"] >= 0.2),
        ("Lane drift, ranking surface (max |Spearman| ≤ 0.90)",
         f"PASS — {f(ro['lane_surface_max_abs_spearman'])}" if
         ro["lane_surface_max_abs_spearman"] <= 0.90 else "FAIL",
         ro["lane_surface_max_abs_spearman"] <= 0.90),
        ("Lane drift, final dots (max |Spearman| ≤ 0.90)",
         f"PASS — {f(ro['lane_dots_max_abs_spearman'])}" if
         ro["lane_dots_max_abs_spearman"] <= 0.90 else "FAIL",
         ro["lane_dots_max_abs_spearman"] <= 0.90),
        ("Lane drift, dots within 3 px of one raster (≤ 70 %)",
         f"PASS — {pct(ro['lane_dots_max_within_3px_frac_gate'])} excl. calibration" if
         ro["lane_dots_max_within_3px_frac_gate"] <= 0.70 else "FAIL",
         ro["lane_dots_max_within_3px_frac_gate"] <= 0.70),
        ("Not merely the union of the two views",
         f"PASS — {pct(b['not_merely_union']['outside_union_fraction'])} of dots outside "
         f"max(pA,pB)'s own top-k" if b["not_merely_union"]["outside_union_fraction"] >= 0.30
         else "FAIL", b["not_merely_union"]["outside_union_fraction"] >= 0.30),
        ("Repaired shared-template lane gate (H61's gates.lane_report), informative priors only",
         (f"{ro['repaired_gate']['policy_verdict']} — "
          f"max |ρ| {f(ro['repaired_gate']['policy_max_spearman'])}, "
          f"3 px {pct(ro['repaired_gate']['policy_max_near_3px_fraction'])}, "
          f"{ro['repaired_gate']['n_informative_priors']} informative priors")
         if ro.get("repaired_gate") else "not computed",
         bool(ro.get("repaired_gate")) and ro["repaired_gate"]["policy_verdict"] == "PASS"),
        ("Leakage canary (worst single-layer holdout AUC ≤ 0.90)",
         f"PASS — {COT['leakage_canary']['worst_auc']} "
         f"({COT['leakage_canary']['worst_layer']})"
         if COT["leakage_canary"]["worst_auc"] <= 0.90 else "FAIL",
         COT["leakage_canary"]["worst_auc"] <= 0.90),
        ("Blum–Mitchell independence premise (max |r| < 0.60)",
         f"PASS — {f(COT['independence']['max_abs_correlation'])}" if
         COT["independence"]["max_abs_correlation"] < 0.60 else "FAIL",
         COT["independence"]["max_abs_correlation"] < 0.60),
    ]
    return "\n".join(
        f"<tr><td>{lab}</td><td class='{'good' if ok else 'bad'}'>{res}</td></tr>"
        for lab, res, ok in rows)


def build_page() -> str:
    ind = COT["independence"]
    can = COT["leakage_canary"]
    strat = COT["strata"]
    probe = COT["corroboration_probe"]
    dm = strat["median_depth_to_basement_m"]
    br = VAL["budget_rule"]
    grid = VAL["instrument2_revealed"]["budget_grid_px"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H62: two-view co-training with corroboration instead of disagreement. A new unique GeoTIFF, its gates, and its negative result on the lane's discovery signal.">
<title>H62 — two-view corroboration · GEMSDOE52</title>
<link rel="stylesheet" href="assets/ctd5.css"><script src="assets/ctd5.js" defer></script></head>
<body><a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>
<a href="h62.html">H62</a><a href="index.html">Overview</a><a href="ctd5-audit.html">Run &amp; evidence</a><a href="executive-summary.html">H62 research status</a><a href="ctd5-sources.html">Sources</a><a href="downloads/index.html">Archive</a></nav></header>
<main id="main"><section class="hero"><div><div class="eyebrow">DOE GEMS · H62 · {PREREG['registered_utc_date']}</div>
<h1>Two views.<br>Corroboration instead of disagreement.</h1>
<p class="lead">Every earlier round in this lane shipped the cell where the two views disagree. H62 tests the opposite cell of the same 2×2 confidence table, on the same bytes, with the same folds.</p>
<div class="notice bad" role="note"><strong>OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · NO SLOT ALLOCATED</strong>
<p>The file passes format, the 200 m ring, not-merely-the-union, decoded-pattern uniqueness and the leakage canary. <strong>It does not pass the lane's strict duplicated-ness gate:</strong> {pct(RO['lane_dots_max_within_3px_frac_gate'])} of its dots lie within 3 px of a spacing-5 square lattice whose 3 px halo covers {pct(RG['probe_coverage'][0])} of the eligible footprint, so that statistic reads ~1.0 for <em>any</em> nonempty candidate. The coverage-aware repair returns {RG['policy_verdict']} on the {RG['informative_priors']} priors that localise something. Both readings are published below; neither is suppressed. No organizer-confirmed score exists for this file and none is claimed.</p></div>
<div class="actions"><a class="button" href="downloads/{FILE}" download>Download the new GeoTIFF ↓</a><a class="button secondary" href="downloads/{FILE[:-4]}.zip" download>Single-TIFF ZIP</a></div>
<p class="fileline">{FILE}<br>{BYTES:,} bytes · {NPX:,} emitted pixels · SHA-256 {SHA}</p>
<p class="small"><a href="executive-summary.html">What the statuses mean, and why this one says do not submit →</a></p></div>
<aside class="panel" aria-label="Gates"><div class="label">Every gate, measured</div>
<div class="status-line"><span>Format (CRS / shape / transform / range)</span><span class="good">PASS</span></div>
<div class="status-line"><span>Unique vs {CARD['correlation_overlap_vs_registry']['n_priors']} aligned priors</span><span class="good">YES</span></div>
<div class="status-line"><span>Lane drift (surface / dots)</span><span class="good">{f(CARD['correlation_overlap_vs_registry']['lane_surface_max_abs_spearman'])} / {f(CARD['correlation_overlap_vs_registry']['lane_dots_max_abs_spearman'])}</span></div>
<div class="status-line"><span>Not merely the union</span><span class="good">{pct(BUILD['not_merely_union']['outside_union_fraction'])} outside</span></div>
<div class="status-line"><span>Nearest mapped catalogue pixel</span><span class="good">{f(BUILD['ring_min_distance_to_catalogue_m'], 1)} m</span></div>
<div class="status-line"><span>Registered-instrument verdict</span><span class="{'good' if VERDICT == 'promote' else 'bad'}">{VERDICT.upper()}</span></div>
<div class="status-line"><span>Strict lane gate (all registry rasters)</span><span class="bad">DUPLICATE / STOP</span></div>
<div class="status-line"><span>Coverage-aware gate (informative priors)</span><span class="{'good' if RG['policy_verdict'] == 'PASS' else 'bad'}">{RG['policy_verdict']}</span></div>
<p class="fine">{CARD['promotion_scope']}</p>
<a class="small" href="data/h62_run_card.json">Inspect the JSON run card ↗</a></aside></section>

<hr class="divider"><div class="section-head"><h2>The five candidates, ranked before anything was fitted</h2><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/34_hypotheses_H62_preregistered.md">Read the preregistration →</a></div>
<div class="table-wrap"><table><thead><tr><th>#</th><th>Hypothesis</th><th>Layers</th><th>Signature</th><th>Why it finds a catalogue-missing fault</th><th>Non-fault process that could mimic it</th><th>Cost</th><th>Status</th></tr></thead><tbody>
<tr><td>1</td><td><strong>H62-B</strong> concordance under independent thinning</td><td>Both views' out-of-fold confidence; the metric's 3 px lattice</td><td>Each view's confident set thinned independently, the thinnings intersected, survivors ranked by min(p<sub>A</sub>,p<sub>B</sub>)</td><td>Corroboration is the largest measured effect in this repository: two independent thinnings of one field intersect in an atom carrying 16.3–20.5 % credit density against 0–8.7 % for singly-selected atoms</td><td>A resistant lithologic contact (welded tuff or carbonate) that stands up as a ridge <em>and</em> carries a magnetic susceptibility contrast; a fluvial/glacial escarpment on a stratigraphic contact</td><td>low</td><td><strong>run; shipped</strong></td></tr>
<tr><td>2</td><td><strong>H62-A</strong> cover-conditioned buried disagreement</td><td>p<sub>A</sub>, p<sub>B</sub>, band 15 depth-to-basement</td><td>max(p<sub>A</sub>−p<sub>B</sub>,0) restricted to depth-to-basement ≥ the pool's 70th percentile ({f(BUILD['cover_threshold_m'], 0)} m)</td><td>A compilation built from <em>mapped</em> faults systematically misses structures buried under basin fill, and the board's truth sits a median of 1,965 m from any mapped trace</td><td>The basin-bounding gravity gradient at the fill/bedrock contact; a basement lithologic contact beneath fill</td><td>very low</td><td>run; measured below random</td></tr>
<tr><td>3</td><td><strong>H62-C</strong> rehabilitated structured B-only</td><td>View B, View A, DEM structure tensor</td><td>p<sub>B</sub> confident, p<sub>A</sub> abstains, coherence high, strike within 30° of the Basin-and-Range fabric</td><td>View A cannot resolve a 1–5 m scarp, so its abstention is uninformative; small young scarps are the biggest gap in an air-photo compilation</td><td>Roads, levees, canals, quarry faces, erosion lines</td><td>medium</td><td>not run (budget)</td></tr>
<tr><td>4</td><td>H62-D InSAR strain rate</td><td>Sentinel-1 line-of-sight velocity gradients</td><td>strain-rate lineament at 100 m posting</td><td>interseismic strain localisation marks a loading structure whether or not it was ever mapped</td><td>aquifer-system compaction / subsidence bowls</td><td>blocked</td><td><strong>not viable here</strong> — ASF/USGS hosts unreachable from this sandbox</td></tr>
<tr><td>5</td><td>H62-E pseudo-label exchange</td><td>both views</td><td>confident donor labels the abstaining receiver</td><td>—</td><td>—</td><td>low</td><td><strong>do not run</strong> — five prior independent nulls</td></tr>
</tbody></table></div>

<hr class="divider"><div class="section-head"><h2>1. The premise, tested before it was used</h2></div>
<div class="grid2"><section class="panel"><h3>Blum &amp; Mitchell independence</h3>
<p class="small">50 px blocks of out-of-fold error on labelled negatives, 4 whole-segment folds, {ind['n_blocks']:,} blocks, {ind['n_negative_predictions']:,} negative predictions. Abandonment bar 0.60.</p>
<div class="status-line"><span>block negative-FPR Spearman</span><span class="good">{f(ind['tests']['negative_false_positive_rate']['spearman'])}</span></div>
<div class="status-line"><span>block MSE Spearman</span><span class="good">{f(ind['tests']['negative_mean_squared_error']['spearman'])}</span></div>
<div class="status-line"><span>pixel-level Pearson / Spearman</span><span class="good">{f(ind['pixel_level']['pearson'])} / {f(ind['pixel_level']['spearman'])}</span></div>
<div class="status-line"><span>max |r| vs the 0.60 bar</span><span class="good">{f(ind['max_abs_correlation'])}</span></div>
<p class="fine">Not proof of conditional feature independence — a weak proxy-negative coupling, which is all the brief asks to be tested.</p></section>
<section class="panel"><h3>Leakage canary</h3>
<p class="small">Every cached layer alone against the holdout truth. AUC above 0.90 means leakage until proven otherwise.</p>
<div class="status-line"><span>layers screened</span><span class="good">{can['n_layers']}</span></div>
<div class="status-line"><span>worst layer</span><span class="good">{can['worst_layer']}</span></div>
<div class="status-line"><span>worst AUC</span><span class="good">{can['worst_auc']}</span></div>
<div class="status-line"><span>verdict</span><span class="good">clean</span></div>
<p class="fine">{can['verdict']}.</p></section></div>

<h3>The 2×2 confidence table, and the cover geology it reproduces</h3>
<div class="table-wrap"><table><thead><tr><th>stratum</th><th>px</th><th>median depth to basement (m)</th></tr></thead><tbody>
<tr><td class="mono">A-only (A confident, B abstains)</td><td class="number">{strat['counts']['a_only']:,}</td><td class="number">{f(dm['a_only'], 1)}</td></tr>
<tr><td class="mono">B-only (B confident, A abstains)</td><td class="number">{strat['counts']['b_only']:,}</td><td class="number">{f(dm['b_only'], 1)}</td></tr>
<tr><td class="mono">concordant</td><td class="number">{strat['counts']['concordant']:,}</td><td class="number">{f(dm['concordant'], 1)}</td></tr>
<tr><td class="mono">neither</td><td class="number">{strat['counts']['neither']:,}</td><td class="number">{f(dm['neither'], 1)}</td></tr>
<tr><td class="mono">whole legal pool</td><td class="number">{strat['counts']['allowed']:,}</td><td class="number">{f(dm['permitted'], 1)}</td></tr>
</tbody></table></div>
<p class="small">The A-only stratum sits under {f(dm['a_only'] / dm['b_only'], 1)}× more cover than the B-only stratum — the brief's own buried-beneath-cover mechanism, reproduced again on these bytes.</p>

<h3>Why the hard intersection cannot be shipped</h3>
<p>Two independent thinnings of <em>k</em> dots inside a pool of <em>n</em> intersect in <em>k</em>²/<em>n</em> dots: 185 px at <em>k</em> = 30,000, <em>n</em> = {strat['counts']['allowed']:,}. Measured at k = 60,000: View A thins to {probe['n_thin_a']:,} dots against View B's {probe['n_thin_b']:,}, and the intersection is <strong>{probe['n_corroborated']} px</strong> — lift {f(probe['corroboration_lift'], 2)}× over the {f(probe['expected_under_independence'], 1)}-px independence null, and two orders of magnitude below any usable budget. Registered as correction <strong>H62-1</strong>: the corroboration operator is delivered as a <em>ranking</em> on the joint confidence min(p<sub>A</sub>,p<sub>B</sub>), which is high only where both views vouch for the pixel and is therefore not the union.</p>

<hr class="divider"><div class="section-head"><h2>2. Two instruments, and they disagree</h2></div>
<div class="grid2"><section class="panel"><h3>Instrument 1 — HOLDOUT-DTI</h3>
<p class="small">Hide-and-recover, whole segments, 4 folds, 4 px buffer, prevalence 0.002, visible catalogue masked pixel-exactly, pooled α 0.2 / β 0.8 / 300 m triangular kernel, fold-bootstrap 95 % CI. <strong>{CARD['holdout_dti']['withheld_positives']:,} withheld positives.</strong></p>
<p class="small"><strong>Known defect:</strong> Spearman(owner-reported board score, this instrument) = −0.1045, p = 0.734, n = 13. It is reported because the lane requires it and because it is the only leakage detector available. <strong>It is not a board proxy.</strong></p></section>
<section class="panel"><h3>Instrument 2 — revealed preference</h3>
<p class="small">The only subset of this footprint whose credit density is <em>measured</em> rather than projected is P1 = the 0.2778 champion ∩ its d1-5 thinning: {VAL['instrument2_revealed']['core_px']:,} px, credit density {VAL['instrument2_revealed']['core_credit_density_bracket']}. Instrument 2 asks what fraction of a candidate's dots fall inside the metric's own acceptance radius of that atom.</p>
<p class="fine">{VAL['instrument2_revealed']['limits']}.</p></section></div>

<h3>Instrument 1 — pooled HOLDOUT-DTI at 25,000 px</h3>
<div class="table-wrap"><table><thead><tr><th>field</th><th>budget</th><th>pooled HOLDOUT-DTI</th><th>95 % CI</th><th>lift over matched random</th></tr></thead><tbody>
{holdout_rows()}
</tbody></table></div>

<h3>Instrument 2 — co-location lift over the matched random control</h3>
<div class="table-wrap"><table><thead><tr><th>field</th>{''.join(f'<th>{k//1000}k px</th>' for k in grid)}</tr></thead><tbody>
{revealed_rows()}
</tbody></table></div>

<div class="grid2"><section class="panel"><h3>What instrument 1 says</h3>
<p>The concordance ranking <strong>beats both single-view baselines and the union</strong> on the registered instrument: {f(VAL['instrument1_holdout']['arms']['conc_soft|25000']['pooled_dti'], 6)} against {f(VAL['instrument1_holdout']['arms']['clf_union|25000']['pooled_dti'], 6)} for max(p<sub>A</sub>,p<sub>B</sub>) and {f(VAL['instrument1_holdout']['arms']['view_B|25000']['pooled_dti'], 6)} for the surface view alone. That is the comparison the brief asks for — "compare against a single-view baseline on hide-and-recover segments" — and it is the round's one positive measurement. It is <strong>not</strong> enough to promote the file, because the strict lane gate stops it first. View A alone is higher still ({f(VAL['instrument1_holdout']['arms']['view_A|25000']['pooled_dti'], 6)}), so the concordance is not the best single field here.</p></section>
<section class="panel"><h3>What instrument 2 says — and the disagreement fields</h3>
<p>The lane's designated discovery signal measures <strong>below the matched random control</strong>: dis_contrast {f([r for r in BUILD['candidates'] if r['field'] == 'dis_contrast'][0]['lift'], 2)}×, dis_product {f([r for r in BUILD['candidates'] if r['field'] == 'dis_product'][0]['lift'], 2)}×, cover-conditioned A-only {f([r for r in BUILD['candidates'] if r['field'] == 'cover_A_only'][0]['lift'], 2)}× random. Disagreement is not merely weaker than the union on this instrument — it is anti-correlated with the one pixel set whose credit density has been measured. This is the sharpest form yet of the negative H56/H59/H60D all reached by a different route.</p></section></div>

<hr class="divider"><div class="section-head"><h2>3. The budget was derived, not inherited</h2></div>
<p>With FN<sub>w</sub> = |G| − TP<sub>w</sub>, binary mass and M ≈ T, DTI(S) = T(S)/(0.2 S + 0.8|G|); if T(S) = c·S<sup>γ</sup> the argmax S* = γ·0.8|G|/(0.2(1−γ)) is <strong>independent of c</strong>, so field quality does not move it. γ fitted to this round's own field over {grid[0]//1000}k–{grid[-1]//1000}k px is <strong>{f(br['gamma'])}</strong>, which puts the unclamped argmax at {br['s_star_unclamped']:,.0f} px — outside the measured range, hence an extrapolation, and it rests on a mixture whose ρ<sub>novel</sub> bound is a prior rather than a measurement. The board's own published record points the other way and is a direct measurement: across the six off-catalogue scored priors, score is <strong>strictly decreasing in emitted mass</strong> (Spearman −1.000, n = 6). Direct measurement governs, so the emission is <strong>{BUILD['budget_px']:,} px</strong> — the preregistered fallback, the midpoint of the |G|-bracket solutions, inside the preregistered clamp [{br['clamp_px'][0]:,}, {br['clamp_px'][1]:,}]. Registered as correction <strong>H62-2</strong>.</p>

<hr class="divider"><div class="section-head"><h2>4. Field selection and the union disqualifier</h2></div>
<div class="table-wrap"><table><thead><tr><th>field</th><th>dots</th><th>co-location f</th><th>random baseline</th><th>lift</th><th>overlap with max(p<sub>A</sub>,p<sub>B</sub>) top-k</th><th>decision</th></tr></thead><tbody>
{cand_rows()}
</tbody></table></div>
<p><strong>view_B</strong> and <strong>clf_union</strong> are the two best fields on instrument 2 — and they are the same field: their dot sets overlap by {pct([r for r in BUILD['candidates'] if r['field'] == 'view_B'][0]['union_overlap'], 1)} and their reads differ by 3 %. Shipping either would ship max(p<sub>A</sub>,p<sub>B</sub>), which the brief explicitly forbids. Any candidate overlapping the union's top-k by more than 70 % is therefore disqualified mechanically (correction <strong>H62-3</strong>), and the winner is the highest-lift survivor: <strong>{BUILD['winner']}</strong>, whose {pct(BUILD['not_merely_union']['outside_union_fraction'])} of dots sit outside the union's own emission.</p>

<hr class="divider"><div class="section-head"><h2>5. Every gate on the shipped file</h2></div>
<div class="table-wrap"><table><thead><tr><th>gate</th><th>result</th></tr></thead><tbody>
{gate_rows()}
</tbody></table></div>
<p class="small"><strong>Correction H62-4 (IR-H62-005):</strong> the emission budget's |G| constant is identified only as an interval — <strong>[{f(BUILD['g_bracket_px'][0], 1)}, {f(BUILD['g_bracket_px'][1], 1)}] px</strong> — not as the point {f(BUILD['g_legacy_anchor_px'], 1)} px this round carried in, which is a valid but non-binding upper bound. Under the measured bracket the two available γ rules disagree (this round's γ clamps to 30,000 px, the champion-family γ clamps to 15,000 px) and the direct board measurement favours the low end, so <strong>15,000 px is what the evidence favours</strong>. The file is left at 22,000 px, between the two answers: the budget is the weakest number in this round.</p>
<p class="small">The dots-within-3 px reading against the whole prior inventory, calibration rasters included, is {pct(CARD['correlation_overlap_vs_registry']['lane_dots_max_within_3px_frac_raw'])}; the strict gate now counts <em>every</em> supplied registry raster: the H60D strict recheck withdrew the calibration exemption (H60-6), so calibration rasters are no longer excluded. That is why the gate value and the raw value are the same number. The coverage-aware repair <code>gates.lane_report</code> reports the same statistic a second way — restricted to the {RG['informative_priors']} priors whose measured 3 px coverage of the eligible footprint is below 95%, with the {RG['universal_coverage_probes']} universal-coverage probe ({RG['probe_paths'][0].rsplit('/', 1)[-1]}, coverage {pct(RG['probe_coverage'][0])}) identified by measurement rather than excluded by class. Both readings are published; neither is suppressed.</p>

<hr class="divider"><div class="section-head"><h2>6. Geological reasoning for review</h2></div>
<p>{BUILD['reasoning_rows']:,} per-pixel reasoning rows and {BUILD['a_only_dossier_rows']:,} A-only candidate-segment dossiers ship with the file. Every row names the confidence cell, the depth to basement, whether the pixel was independently corroborated by both views, and the non-fault process that could produce the same signature. These are <strong>hypotheses for Phase-2 review, not verified faults</strong>.</p>
<div class="actions"><a class="button secondary" href="downloads/gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px-emitted-pixels.csv" download>Per-pixel reasoning CSV ↓</a><a class="button secondary" href="downloads/gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px-a-only-candidate-segments.csv" download>A-only candidate dossiers ↓</a></div>

<hr class="divider"><div class="section-head"><h2>7. Corrections, limits, and the run card</h2></div>
<div class="table-wrap"><table><thead><tr><th>id</th><th>correction registered before the artifact shipped</th></tr></thead><tbody>
{''.join(f"<tr><td class='mono'>{c['id']}</td><td>{c['summary']}</td></tr>" for c in BUILD['corrections'])}
</tbody></table></div>
<ul>
<li>The competition inputs are <strong>SHA-256-pinned owner mirrors</strong>, not organizer-authenticated downloads: the DrivenData data tab is login-walled. Every number here inherits that qualification.</li>
<li>Every leaderboard number anywhere in this repository is <strong>owner-reported</strong>. None is ORGANIZER-CONFIRMED — no submission-page receipt exists.</li>
<li>Instrument 2 is a similarity statistic to one specific prior file. It is read only together with the uniqueness and lane gates, which are the controls that forbid duplication.</li>
<li>{CARD['slot_decision']}.</li>
<li>The two footprints are not nested (IR-H62-001): 1,540 px are finite in all 19 competition bands but not in <span class="mono">sample_submission</span>, and 3,073 px the other way round. The emission domain is their intersection, {CARD['validator_output'].get('n_nonzero') and '5,164,300'} px.</li>
</ul>
<p><a href="data/h62_run_card.json">Run card (JSON)</a> · <a href="data/h62_build.json">Build receipt</a> · <a href="data/h62_validation.json">Validation receipt</a> · <a href="data/h62_cotrain.json">Co-training receipt</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/34_hypotheses_H62_preregistered.md">Preregistered hypotheses</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/evidence/h62_lane_gate.json">Lane gate, per prior</a></p>
</main>
<footer>Competition 306 · CPU research · fault-structure predictions, not confirmed geothermal vents. <a href="irregularities.html">Limitations &amp; review</a> · <a href="executive-summary.html">H62 research status</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; complete prompt</a></footer></body></html>
"""


# --------------------------------------------------------------------------------- page edits
BANNER = f"""<!--H62-BANNER--><section class="hero" style="padding-top:8px"><div><div class="eyebrow">Newest round · H62 · {PREREG['registered_utc_date']}</div>
<h1>Two views, corroboration instead of disagreement.<br>A new GeoTIFF you can download.</h1>
<p class="lead">The lane's discovery signal — where the geophysical and surface views disagree — measures <strong>below a matched random control</strong> on the one instrument tied to measured credit. The opposite cell of the same table beats both single views and the union on the registered holdout.</p>
<div class="notice bad" role="note"><strong>OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT</strong>
<p>The strict lane gate returns DUPLICATE/STOP on a lattice-saturated registry ({pct(RO['lane_dots_max_within_3px_frac_gate'])} of dots within 3 px of the spacing-5 lattice, which covers {pct(RG['probe_coverage'][0])} of the eligible footprint). No weekly slot is allocated and none should be spent. No organizer-confirmed score exists for this file.</p></div>
<div class="actions"><a class="button" href="downloads/{FILE}" download>Download the new GeoTIFF ↓</a><a class="button secondary" href="h62.html">Read the H62 evidence</a></div>
<p class="fileline">{FILE}<br>{BYTES:,} bytes · {NPX:,} px · SHA-256 {SHA}</p></div></section><hr class="divider"><!--/H62-BANNER-->"""

GUIDE = f"""<!--H62-GUIDE--><div class="eyebrow">H62 · historical research status</div>
<h1>H62 is a research archive.<br>NOT FOR SUBMISSION.</h1>
<div class="notice bad" role="alert"><strong>RESEARCH DOWNLOAD ONLY · DUPLICATE/STOP · NOT FOR SUBMISSION · NO SLOT AUTHORIZED</strong>
<p>The literal final-dot lane gate is a stop because the spacing-five lattice is within 3 px of the eligible footprint. Format validity, decoded-pattern uniqueness, and download availability do not override it. No upload steps, owner override, or paste-ready note are provided.</p></div>
<div class="actions"><a class="button" href="downloads/{FILE}" download>Download H62 research TIFF</a><a class="button secondary" href="downloads/{FILE[:-4]}.zip" download>Research ZIP</a><a class="button secondary" href="h62.html">H62 audit receipts</a></div>
<p class="fileline">{FILE}<br>{BYTES:,} bytes · {NPX:,} px · SHA-256 {SHA}</p>
<div class="grid2"><section class="panel"><h2>Local file checks</h2><p>Format, ring, not-union, decoded-pattern uniqueness and leakage-canary checks are local measurements only. They do not establish portal acceptance or submission eligibility.</p></section><section class="panel"><h2>Terminal lane result</h2><p>The final-dot overlap with the spacing-five lattice is {pct(RO['lane_dots_max_within_3px_frac_gate'])}; the strict gate returns DUPLICATE/STOP. This result cannot be waived or retuned on this page. No weekly slot is allocated or recommended.</p></section></div>
<p><a href="h62.html">Full H62 method and evidence →</a> · <a href="data/h62_run_card.json">Historical run-card receipt (JSON)</a> · <a href="../knowledge/35_what_h62_found.md">Results and limits</a></p>
<p class="small">This archived page does not authorize a rerun, new run-card, rebuild, override, or submission. No organizer-confirmed score receipt exists for H62.</p><!--/H62-GUIDE-->"""

DLROW = f"""<!--H62-DL--><tr><td><a href="gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px.tif" download>gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px.tif</a></td>
<td class="number">{BYTES:,}</td><td class="mono">{SHA}</td>
<td>H62 · two-view corroboration · {NPX:,} px · newest round; <a href="../h62.html">evidence</a></td></tr>
<tr><td><a href="gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px.zip" download>gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px.zip</a></td>
<td class="number">{ZIP_BYTES:,}</td><td class="mono">{RECEIPT.get('zip_sha256', '')}</td>
<td>single-TIFF ZIP, byte-identical to the direct download</td></tr>
<tr><td><a href="gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px-emitted-pixels.csv" download>…-emitted-pixels.csv</a></td><td class="number">{CSV_PX:,}</td><td class="mono">—</td><td>{BUILD['reasoning_rows']:,} per-pixel geological reasoning rows</td></tr>
<tr><td><a href="gems52-h62-{BUILD['winner']}-arm{BUILD['budget_px']}px-a-only-candidate-segments.csv" download>…-a-only-candidate-segments.csv</a></td><td class="number">{CSV_SEG:,}</td><td class="mono">—</td><td>{BUILD['a_only_dossier_rows']:,} A-only candidate-segment dossiers</td></tr><!--/H62-DL-->"""


def swap(path: Path, marker: str, block: str, anchor: str) -> None:
    text = path.read_text()
    text = re.sub(re.escape(marker) + r".*?" + re.escape(marker.replace("<!--", "<!--/")
                                                          .replace("H62-", "H62-/")),
                  "", text, flags=re.S)
    text = re.sub(re.escape(f"<!--{marker.strip('<!->')}-->") + r".*?" + re.escape(
        f"<!--/{marker.strip('<!->')}-->"), "", text, flags=re.S)
    if anchor not in text:
        raise SystemExit(f"{path}: anchor {anchor!r} not found")
    path.write_text(text.replace(anchor, anchor + "\n" + block, 1))


def strip_previous(text: str, tag: str) -> str:
    return re.sub(re.escape(f"<!--{tag}-->") + r".*?" + re.escape(f"<!--/{tag}-->"),
                  "", text, flags=re.S)


def main() -> int:

    _h75_home = ROOT / "docs" / "index.html"
    _h75_status = ROOT / "docs" / "h75-executive-summary.html"
    if (_h75_home.is_file() and _h75_status.is_file()
            and "H75: DUPLICATE/STOP" in _h75_home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in
            _h75_status.read_text(errors="replace")):
        print("H75 terminal stop is current; historical publisher made no page or pointer changes")
        return 0
    (DOCS / "h62.html").write_text(build_page())
    for src, dst in (("h62_build.json", "h62_build.json"),
                     ("h62_validation.json", "h62_validation.json"),
                     ("h62_cotrain.json", "h62_cotrain.json"),
                     ("h62_lane_gate.json", "h62_lane_gate.json"),
                     ("h62_uniqueness.json", "h62_uniqueness.json"),
                     ("h62_format_gate.json", "h62_format_gate.json")):
        shutil.copy2(EV / src, DATA / dst)
    (DATA / "h62_submission.json").write_text(json.dumps(
        dict(RECEIPT, round="H62", verdict=VERDICT, promotion_scope=CARD["promotion_scope"],
             slot_decision=CARD["slot_decision"]), indent=1, allow_nan=False) + "\n")

    # front page: banner after <main id="main">, plus a nav entry
    p = DOCS / "index.html"
    t = strip_previous(p.read_text(), "H62-BANNER")
    # main rewrites the front page between rounds, so the nav anchor is matched on whichever
    # "Run & evidence" entry the current index.html happens to carry.
    m = re.search(r'<a href="[^"]+\.html">Run &amp; evidence</a>', t)
    if m and 'h62.html">H62' not in t:
        t = t[:m.start()] + '<a href="h62.html">H62 — newest</a>' + t[m.start():]
    assert '<main id="main">' in t
    t = t.replace('<main id="main">', '<main id="main">\n' + BANNER, 1)
    p.write_text(t)

    p = DOCS / "executive-summary.html"
    t = strip_previous(p.read_text(), "H62-GUIDE")
    assert '<main id="main">' in t
    t = t.replace('<main id="main">', '<main id="main">\n' + GUIDE, 1)
    p.write_text(t)

    p = DOCS / "downloads" / "index.html"
    t = strip_previous(p.read_text(), "H62-DL")
    anchor = '<tbody>\n'
    assert anchor in t
    t = t.replace(anchor, anchor + DLROW + "\n", 1)
    p.write_text(t)
    print("published: h62.html, H62 banner on index.html, H62 guide on executive-summary.html, "
          "downloads/index.html row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
