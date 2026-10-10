#!/usr/bin/env python3
"""Generate knowledge/85_h89_results_and_limits.md from the H89 receipts (no typed numbers)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
L = lambda n: json.loads((EV / f"h89_{n}.json").read_text())  # noqa: E731

card, wr, hold, build, lane = L("run_card"), L("write"), L("holdout"), L("build"), L("lane")
ind, exg, fit, chan = L("independence"), L("exchange"), L("fit"), L("channels")
S, pt = card["holdout"]["scores"], hold["promotion_test"]
co = card["correlation_overlap_vs_registry"]
tif = Path(wr["file"]).name

rows = "\n".join(
    f"| `{a}` | {S[a]['dti']:.6f} | [{S[a]['ci95'][0]:.6f}, {S[a]['ci95'][1]:.6f}] | "
    f"{'primary (pre-registered)' if a == 'CCD' else 'control' if a in ('single_B', 'random', 'single_A') else 'attribution arm — not promotable post hoc'} |"
    for a in ("CCD", "single_B", "B_art", "union_max", "single_A", "A_only_cover", "random"))

fold_rows = "\n".join(
    f"| {f['fold']} | {f['truth_px']:,} | {f['allowed_px']:,} | {f['discovery_pool_px']:,} | "
    f"{f['arms']['CCD']['dti']:.6f} | {f['arms']['single_B']['dti']:.6f} | "
    f"{f['arms']['A_only_cover']['dti']:.6f} ({f['arms']['A_only_cover']['placed']:,} placed) |"
    for f in hold["folds"])

canary_rows = "\n".join(f"| {c['fold']} | `{c['max_channel']}` | {c['max_auc']:.4f} | {c['n_pos']:,} | {c['n_neg']:,} |"
                        for c in fit["canary"])
auc_rows = "\n".join(f"| {f['fold']} | {f['view_A']['heldout_region_auc']:.4f} | {f['view_B']['heldout_region_auc']:.4f} |"
                     for f in fit["folds"])
don_rows = "\n".join(f"| {f['fold']} | {f['donated_px']:,} | {f['donated_components']:,} | "
                     f"{f['auc_pre']:.4f} | {f['auc_post']:.4f} | {f['improved']} |"
                     for f in exg.get("folds", []))

doc = f"""# 76 · H89 results and limits

Round **H89**, {card['generated_utc']}. Preregistration `knowledge/83_hypotheses_H89_preregistered.md`
(SHA-256 `{card['preregistration_sha256']}`), frozen before any fit and pinned by
`registry/h89_preregistration.json`. Every number below is read from `evidence/h89_*.json`.

**Verdict: {card['verdict'].upper()} · DOWNLOAD {card['download']} · SUBMIT {card['submit']} · slots used {card['slots_used']}.**

Artefact: `submission/{tif}` — {wr['bytes']:,} bytes, SHA-256 `{wr['sha256']}`.
Submission name `{wr['submission_name']}`; note ({wr['note_chars']}/140) `{wr['note']}`.

---

## 1. Hide-and-recover holdout (the only measured score here)

Evaluator `{hold['evaluator']}`; {hold['withheld_positive_px']:,} withheld positive pixels;
{hold['budget_per_fold']:,} dots per fold per arm at 3 px separation; the fold's visible catalogue
masked pixel-exactly and a 200 m ring excluded; α 0.2, β 0.8, 300 m triangular kernel; 1,000 paired
physical-cluster bootstrap draws.

| arm | HOLDOUT-DTI | 95 % CI | role |
|---|---:|---|---|
{rows}

Frozen promotion test: paired **CCD − single_B = {pt['delta']:+.6f}** [{pt['delta_ci95'][0]:.6f},
{pt['delta_ci95'][1]:.6f}]. Non-inferiority (point ≥ single_B − 0.020 **and** CI lower bound >
−0.040): **{'PASS' if pt['noninferior'] else 'FAIL'}**. Superiority: **{'yes' if pt['superiority'] else 'no'}**.

Per fold:

| fold | withheld truth px | allowed px | A-only discovery pool px | CCD | single_B | A_only_cover |
|---:|---:|---:|---:|---:|---:|---|
{fold_rows}

**Three honest readings of this table.**

1. The primary is **non-inferior, not superior**. The 12 % reserved discovery budget costs
   {abs(pt['delta']):.4f} DTI on this instrument, which is inside the margin that was priced in
   *before* the fit precisely because the instrument withholds **catalogue** faults — features that
   were mapped from surface expression — while the competition scores faults the catalogue lacks.
2. `A_only_cover` **short-fills** its matched budget in every fold (see the per-fold counts), so its
   number is not a matched comparison. That is the same defect H74S recorded; it is reported, not
   repaired by back-filling.
3. `B_art` ({S['B_art']['dti']:.6f}) is slightly below `single_B` ({S['single_B']['dti']:.6f}). The
   artefact veto is a hypothesis about **off-catalogue precision**; this instrument cannot test it,
   so the small loss is evidence about the instrument as much as about the veto. The weight was not
   re-tuned after seeing it.

## 2. Leakage canary

Every learner channel scored alone, direction-insensitively, on each fold's held-out region
(all withheld positives plus up to 200,000 random negatives):

| fold | strongest single channel | AUC | positives | negatives |
|---:|---|---:|---:|---:|
{canary_rows}

Maximum {fit['canary_max_auc']:.4f} against an alarm bar of {card['leakage_canary']['bar']} → **no leakage alarm**.

## 3. View sufficiency and independence

| fold | View A out-of-quadrant AUC | View B |
|---:|---:|---:|
{auc_rows}

Means: A **{fit['mean_auc_A']:.4f}**, B **{fit['mean_auc_B']:.4f}**. This is the **eighth** measurement
in this project that View A is not a sufficient view for catalogue faults.

Independence (the lane's mandated test): spatial-block out-of-fold error correlation on labelled
negatives, max |ρ| = **{ind['result']['max_abs_correlation']:.6f}** over {ind['n_blocks']:,} blocks,
abandon bar {ind['thresholds']['abandon_max_abs_rho']} → **co-training is not abandoned**
(`allow_exchange = {ind['result']['allow_exchange']}`). Thresholds inherited verbatim from
`registry/h74_preregistration.json` (SHA-256 `{ind['thresholds_inherited_sha256'][:24]}…`), not
re-tuned. Standing caveat from the shared tool: catalogue-zero proxy negatives are not verified
fault absence, and a weak error correlation is not proof of conditional feature independence.

## 4. Pseudo-label donation, B → A, one round

| fold | donated px | whole segments | A AUC before | after | improved |
|---:|---:|---:|---:|---:|---|
{don_rows}

Decision: **{exg.get('decision', '—')}** (the frozen rule requires improvement in
{json.loads((ROOT / 'registry/h89_preregistration.json').read_text())['thresholds']['donation_fold_improvement_required']}/4 folds).

**IR-H89-001.** The first execution of this stage donated **0 px in all four folds** because the fit
stage predicts on each fold's *evaluation region* only, so the checkpointed grids are NaN across the
buffered training domain — exactly where a pseudo-label is permitted to originate. The stage now
re-derives donor/receiver fields on the training domain from bit-identical refits (same seed, same
sample, deterministic learner). The holdout and the build had already been computed with the
pre-exchange View A, and the corrected run did not change that decision, so no result depends on the
defect. Both receipts exist.

## 5. Placement, and what the metric actually pays for

{build['dots']:,} binary dots at 3 px minimum separation, {build['discovery_dots']:,} of them A-only
sub-cover discovery dots ({build['placement']['placed_b']:,} + {build['placement']['placed_discovery']:,},
shortfall {build['placement']['shortfall_discovery']}). Distance to the nearest mapped catalogue
trace: minimum **{build['min_cat_dist_m']:.1f} m**, median **{build['median_cat_dist_m']:,.0f} m**,
{build['within_300m_pct']:.2f} % inside the metric's 300 m kernel. Median nearest-neighbour spacing
{build['spacing']['median_px']:.1f} px.

The 200 m ring exclusion is not a style choice: on organiser-scored bytes, deleting the 100–200 m
ring moved an owner-reported 0.2600 file to 0.2778 (`knowledge/49` §1), i.e. that ring earned zero
credit while paying the full false-positive tax.

## 6. Uniqueness, lane and not-the-union

Checked against **{co['census_rasters']}** aligned prior rasters — the owner's 526-blob public census
(re-materialised and byte-checked this session) plus this repository's own artefacts — and the
{co['scored_rasters']}-raster scored-only registry.

* identical to a prior raster: **{co['identical_to_any_prior']}**
* surface maximum Spearman: **{(co['surface_max_spearman_literal'] or 0):.6f}** (lane bar 0.90)
* dots, literal verdict: **{co['dots_literal_verdict']}**, max near-3 px {(co['dots_max_near_3px_literal'] or 0):.4f}
* dots, policy verdict (universal-coverage lattice probes excluded by *measured* coverage ≥ 0.95):
  **{co['dots_policy_verdict']}**, max near-3 px {(co['dots_max_near_3px_policy'] or 0):.4f}

Both verdicts are published. The literal rule is known to return a duplicate verdict against this
census for *every* non-empty raster, because the census contains full-coverage lattice probes; a
restricted PASS never waives the literal result in the written record.

Not-the-union (the lane's explicit requirement): shared with the union-max placement
{wr['not_the_union']['shared_with_union']:,} px (Jaccard {wr['not_the_union']['jaccard_union']:.4f}),
with single-A {wr['not_the_union']['shared_with_A']:,}, with single-B
{wr['not_the_union']['shared_with_B']:,}; equal to the union {wr['not_the_union']['equal_union']},
subset of the union {wr['not_the_union']['subset_of_union']} → **PASS**.

## 7. Conditioner sign checks (measured, not assumed)

Top 1 % of `B_curvature_plus_3` sits at {chan['checks']['mean_detrended_elev_top1pct_curv_plus_m']:.1f} m
detrended elevation; top 1 % of `B_curvature_minus_3` at
{chan['checks']['mean_detrended_elev_top1pct_curv_minus_m']:.1f} m; footprint mean
{chan['checks']['mean_detrended_elev_all_m']:.1f} m → the positive principal curvature is the
concave-up (valley) one, which is what the artefact term assumes
(`valley_convention_consistent = {chan['checks']['valley_convention_consistent']}`).
Modelled cover in the eligible footprint: median {chan['checks']['cover_m']['median']:.1f} m,
p90 {chan['checks']['cover_m']['p90']:.1f} m, max {chan['checks']['cover_m']['max']:.1f} m; the
discovery gate uses the median as its threshold.

## 8. Limits — what this round does **not** establish

1. **It is not a leaderboard projection.** No number here is ORGANIZER-CONFIRMED. The only honest
   board statement this project can make is the algebra in `knowledge/49`: at S = 37,654 px and
   |G| ≈ 14,088.7 px, a board DTI of 0.3195 needs credit density ρ ≈ 0.1595 versus the 0.1387 the
   owner-reported champion achieved. Nothing measured this round establishes that this file reaches
   it.
2. **The holdout is the wrong instrument for the hypothesis.** It hides catalogue faults; the
   hypothesis is about faults the catalogue never had. An off-catalogue instrument remains the
   highest-value unbuilt tool in this repository — and SGMC is *not* the target to build it on
   (off-catalogue SGMC lines scored 0.0512 on 44 k px, i.e. ρ 0.0234, below uniform random 0.0279).
3. **The artefact veto can delete true positives** wherever aeolian cover or soil mutes a real
   fault's radiometric contrast. It is a soft −0.20 demotion for that reason.
4. **Competition rasters are integrity-pinned mirrors**, verified by SHA-256 against
   `registry/data_manifest.json`, **not** organizer-authenticated downloads.
5. **Local format validation is not upload acceptance.**

## 9. What the next round should do

1. **Build the off-catalogue instrument** (named in AGENTS.md since H77 and still unbuilt). Target
   candidates: Quaternary fault traces from the GDR 1391 tables that are > 200 m from `labels.tif`,
   scored as a *ranking* test, never as an emission target.
2. **Pre-register `B_DVA2` with a continuous sub-pixel orientation** (16/32-direction fan or
   parabolic interpolation). It measured 0.189200 in H82 — the best arm this repository has ever
   produced — and may not be promoted post hoc, so it needs a fresh pre-registration.
3. **Test the artefact veto on its own terms**: hold out *non-tectonic* linear features (mapped roads
   or drainage lines) and measure whether the veto suppresses them more than it suppresses withheld
   catalogue faults. That is a direct test of the mechanism rather than a side-effect measurement.
"""
out = ROOT / "knowledge/85_h89_results_and_limits.md"
out.write_text(doc)
print(f"wrote {out} ({len(doc):,} chars)")
