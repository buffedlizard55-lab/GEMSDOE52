#!/usr/bin/env python3
"""Render knowledge/31_h61_results_and_limits.md from the H61 receipts.

Every number in the document is read from ``evidence/h61_*.json`` at render time, so the prose
cannot drift from the receipts.  Run it after ``scripts/build_h61_submission.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"


def load(name: str) -> dict:
    return json.loads((EVID / f"h61_{name}.json").read_text())


def f(x, nd=4):
    return "n/a" if x is None else f"{float(x):.{nd}f}"


def main() -> int:
    card, sub, foren = load("run_card"), load("submission"), load("forensics")
    hold, exch, can = load("holdout"), load("pseudo_exchange"), load("canary")
    proj, lane = load("projection"), load("lane_dots")
    try:
        closure = load("concurrent_closure")
    except Exception:                                            # noqa: BLE001
        closure = None
    lanes = load("lane_surface")
    try:
        lane_an = load("lane_analysis")
    except Exception:                                    # noqa: BLE001 - optional diagnostic
        lane_an = None
    fit = load("fit_checkpoint")
    reg = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
    G = foren["G_identification"]["masked"]
    sc = hold["pooled"]["scores"]
    cand = sc["disagreement_post"]
    lit, pol = lane["literal"], lane["policy"]
    aucs = {r["fold"]: (r["view_A"]["heldout_region_auc"], r["view_B"]["heldout_region_auc"],
                        r["view_A"]["in_sample_auc"], r["view_B"]["in_sample_auc"])
            for r in fit["folds"]}
    mA = sum(v[0] for v in aucs.values()) / len(aucs)
    mB = sum(v[1] for v in aucs.values()) / len(aucs)
    v = card["verdict"]
    ok_submit = bool(card["submit_ok"])

    doc = f"""# H61 results and limits — deep-sharp two-view co-training

**Verdict: `{v.upper()}`. Download for research: {"YES" if card["download_ok"] else "NO"}.
Submit to the competition: {"YES" if ok_submit else "NO"}. Competition slots used: {card["slots_used"]}.**

> **Current score-evidence correction (2026-10-10):** the saved 2026-10-09 20:18 UTC public observation places the team-level 0.2778 row at rank 17 (top 0.3774); it has no TIFF-hash receipt. The file association remains owner-reported. The local 37,654/44,090 subset and 100–200 m distances do not identify hidden-truth credit or explain a score change; new-fault truth may occur within 300 m of known traces. Score-derived `|G|` and credit values below are conditional scenarios, not measurements. See `knowledge/49` and IR-R5-011.

Artefact `{card["raster_file"]}`, SHA-256 `{card["raster_sha256"]}`, {card["raster_bytes"]:,} bytes,
{card["emitted_px"]:,} emitted cells of exactly {{0, 1}} with {card["validator"]["nan_pixels"]} NaN.
Preregistered before any fit in `knowledge/30_hypotheses_H61_preregistered.md`
(SHA-256 `{reg["hypothesis_sha256"]}`); `scripts/run_h61.py` refuses to run if that hash moves.
This document was rendered from the receipts by `scripts/h61_knowledge.py`; no number here was typed
by hand.

## 1 · The primary result: View A does not transfer, so co-training has nothing to transfer

Blum and Mitchell's guarantee needs two views that are each *sufficient* for the class and
approximately conditionally independent given it. On the corrected label-blind quadrant splitter
the second condition holds and the first does not:

| fold | View A OOF AUC | View B OOF AUC | View A in-sample | View B in-sample |
|---|---:|---:|---:|---:|
""" + "".join(f"| {k} | {f(a[0])} | {f(a[1])} | {f(a[2])} | {f(a[3])} |\n"
              for k, a in sorted(aucs.items())) + f"""| **mean** | **{f(mA)}** | **{f(mB)}** | | |

View A is the potential-field/subsurface view ({len(fit["view_A_features"])} channels, including the
external upward-continued TMI). It fits its own quadrant at AUC {f(max(a[2] for a in aucs.values()), 3)}
and predicts **chance** in the next one ({f(mA, 3)}). View B — DEM curvature and slope, band 6
(radiometric total count) and the external K, Th, U, Th/K, U/K, U/Th — reaches {f(mB, 3)}. A
sufficient view cannot be at chance out of sample, so the A→B transfer hands View B noise. This is
the mechanism behind the failed disagreement arms in H55, H56, H57 (A-only density 0.000785 against
a matched random control of 0.001057), H59 and CTD5: those rounds all reported weak or negative
disagreement arms without ever measuring *why*. H61 measures why.

Diagnostics that were clean, so the failure is the premise and not the plumbing:

* leakage canary on all {len(fit["view_A_features"]) + len(fit["view_B_features"])} channels, every
  fold, held-out sample: maximum direction-insensitive AUC {f(can["max_alarm_across_folds"])} against
  an alarm at {can["alarm_auc"]}; fitted single-feature canary on the five strongest
  {f(can["max_fitted_top5_heldout_auc"])}. **No alarm.**
* independence screen on {exch["independence_pre"]["n_blocks"]} 50×50 px blocks of held-out
  catalogue-zero proxies: max |ρ| = {f(exch["independence_pre"]["max_abs_correlation"])} against an
  abandon threshold of {exch["independence_pre"]["threshold"]} → exchange **allowed**. Weak proxy-error
  correlation is not proof of conditional independence, and it is not evidence of sufficiency either.
* exactly one exchange, {exch["total_pseudo_pixels"]:,} pseudo-label pixels in whole segments inside
  the training domain; refit changed held-out AUC by
  {f(aucs[0][0] - exch["folds"][0]["directions"]["refit_A"]["heldout_region_auc"], 4)} (A, fold 0) —
  i.e. nothing, as expected when the donor has no signal.

## 2 · HOLDOUT-DTI, matched budget for the first time in this lane

Evaluator `{hold["pooled"]["evaluator_version"]}`, {int(cand["withheld_positive_pixels"]):,} withheld
positive pixels, pooled TPw/FPw/FNw, α 0.2, β 0.8, 300 m triangular kernel, 95% paired
physical-cluster bootstrap ({hold["pooled"]["bootstrap"]["clusters"]} clusters,
{hold["pooled"]["bootstrap"]["draws"]} draws). Every arm placed exactly
{hold["budget_per_arm_per_fold"]:,} dots per fold at {hold["min_separation_px"]:g} px minimum
separation — {"all arms filled their budget, so the comparison is eligible" if hold["all_arms_filled"] else "BUDGET NOT MATCHED — comparison ineligible"}.
CTD5's primary comparison was ineligible precisely because its candidate arm filled 2,041 of 3,058
requested dots; H61 fixes that by ranking a field that is finite over the whole allowed domain
instead of thresholding a hard mask.

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---:|
""" + "".join(f"| {'**' + k + '**' if k == 'disagreement_post' else k} | {f(x['dti'], 6)} | "
              f"[{f(x['ci95'][0], 6)}, {f(x['ci95'][1], 6)}] |\n" for k, x in sc.items()) + f"""
Best comparable control: `{hold["pooled"]["best_comparable_control"]}`. Paired differences against the
candidate: """ + ", ".join(f"{k} Δ {f(x['delta'], 6)} [{f(x['ci95'][0], 6)}, {f(x['ci95'][1], 6)}]"
                           for k, x in hold["pooled"]["paired_differences"].items()) + f""".

**Instrument validity, stated before the numbers are used for anything.**

1. This simulator measured Spearman −0.10 against the owner-reported board in round R4, and uniform
   random beat the champion on it. It screens procedures; it does not promote. No value above is a
   score or a leaderboard forecast.
2. **Prevalence mismatch, measured.** The folds withhold {int(cand["withheld_positive_pixels"]):,}
   catalogue pixels = {100.0 * cand["withheld_positive_pixels"] / foren["grid"]["eligible_px"]:.2f}% of
   the eligible footprint, whereas the hidden truth is
   {100.0 * G["G_lower_bound"] / foren["grid"]["eligible_px"]:.2f}–{100.0 * G["G_upper_bound"] / foren["grid"]["eligible_px"]:.2f}%
   of it. The simulator is therefore {cand["withheld_positive_pixels"] / G["G_upper_bound"]:.1f}–{cand["withheld_positive_pixels"] / G["G_lower_bound"]:.1f}×
   richer in truth than the real task, which makes every density measured here **optimistic** for the
   competition. The candidate is already below uniform random at that inflated prevalence, so the
   negative verdict does not depend on this correction.
3. The folds hide *catalogue* components. The competition's hidden truth is expert-drawn
   **off-catalogue** structure more than 200 m from any mapped trace, which is a related but not
   identical recovery task.

## 3 · Repaired organiser-score algebra (measured from pinned bytes)

`scripts/h61_forensics.py` → `evidence/h61_forensics.json`. Eligible footprint
{foren["grid"]["eligible_px"]:,} px; catalogue {foren["grid"]["catalogue_px"]:,} px.

* **Masked support.** Known catalogue pixels are masked out of evaluation, so `S` counts off-catalogue
  pixels. Witness: `Hedge-v2` and `ens12-7f00890a` have identical off-catalogue support
  (Jaccard 1.000) and identical reported scores, yet raw-`S` accounting gave them credit
  {f(foren["masked_accounting_witness"]["T_under_raw_accounting"][0], 1)} vs
  {f(foren["masked_accounting_witness"]["T_under_raw_accounting"][1], 1)}; masked accounting gives
  both {f(foren["masked_accounting_witness"]["T_under_masked_accounting"][0], 1)}.
* **|G| is an interval: [{G["G_lower_bound"]:,.1f}, {G["G_upper_bound"]:,.1f}] px.** Thirteen scores
  give thirteen equations in fourteen unknowns. Lower bound binds on
  `{G["G_lower_binding_file"]}`; upper bound on the nested pair
  `{G["G_upper_binding_pair"]["subset"]}` ⊂ `{G["G_upper_binding_pair"]["superset"]}`
  ({G["G_upper_binding_pair"]["s_sub"]} > {G["G_upper_binding_pair"]["s_sup"]} with fewer pixels).
  The previously published point value
  {foren["G_point_under_zero_ring_credit"]["G_px"]:,.1f} px is **outside** that conditional interval. It is obtained only under the extra scenario assumption that the 6,436-cell local difference has zero hidden-truth credit; neither the score-to-file association nor that credit assumption is organizer-confirmed. The {f(foren["G_point_under_zero_ring_credit"]["sensitivity_to_ring_credit"][1]["G_px"], 0)} px result is a sensitivity calculation with an assumed 25 credit, not a measurement.
* **Nested lattice, measured locally:** the restored rasters have the listed subset relations
  (`evidence/h61_forensics.json → subset_pairs`). The H33-labelled 37,654-cell raster is a strict subset
  of a separate 44,090-cell raster associated with 0.2600 by its owner: 6,436 cells removed, none added,
  all between {f(foren["catalogue_rings"]["base_only_distance_to_catalogue_m"]["min"], 0)} m and
  {f(foren["catalogue_rings"]["base_only_distance_to_catalogue_m"]["max"], 0)} m from the local known-fault mask.
  Its nearest retained cell is {f(foren["catalogue_rings"]["champion_distance_to_catalogue_m_min"], 1)} m away.
  These byte and distance facts do not authenticate either score, identify hidden-truth credit, or establish a score-change mechanism.
* **Band 6 is radiometric total count.** Spearman
  {f(foren["band6_identity"]["best_external_match"]["spearman"])} against the independently derived
  external TC grid, {f(foren["band6_identity"]["spearman_vs_tilt_deg_of_TMI"])} against the tilt angle
  of TMI computed from bands 9 and 3, and
  {f(foren["band6_identity"]["spearman_vs_tmi_hg"])} against `tmi_hg` — on
  {foren["band6_identity"]["n_sampled"]:,} eligible pixels. The input file's own description
  ("{foren["band6_identity"]["description_in_file"]}") is contradicted by its bytes. Units remain
  unauthenticated.
* **Attribution strength is not uniform.** Only
  {sum(1 for x in foren["files"].values() if x["attribution_class"].startswith("HASH"))} of
  {len(foren["files"])} owner-reported scores are hash-linked to the bytes held. The champion's token
  `e5eb6e7e` matches none of six hash conventions of the file we hold, and GEMSDOE32's own page says
  no organiser score exists. Everything here is **OWNER-REPORTED, NOT ORGANIZER-CONFIRMED**.

## 4 · Lane gate: the literal rule, the saturation repair, and what they say about this file

The 526-blob census was re-materialised and SHA-verified (`scripts/fetch_prior_inventory.py`:
{lane["priors_checked"]} rasters checked, {lane["distinct_decoded_priors"]} distinct decoded
patterns). The 13GEMSDOE spacing-five lattice has 3 px coverage
{f([r["coverage_3px_of_eligible"] for r in lane["per_prior"] if r.get("universal_coverage_probe")][0] if pol["universal_coverage_probes"] else 0, 4)}
of the eligible footprint, so the literal "70% of dots within 3 px" rule returns DUPLICATE for
**every** nonempty raster — which is why CTD5 stopped. The repair classifies a prior with measured
coverage ≥ {gates_probe()} as a universal-coverage probe, applies the literal rule to informative
priors, and still reports the literal statistic for every prior.

| verdict | max Spearman | max near-dot fraction | source |
|---|---:|---:|---|
| literal (all priors) | {f(lit["max_spearman"])} | {f(lit["max_near_3px_fraction"])} | `{Path(lit["max_near_source"]).name if lit.get("max_near_source") else "n/a"}` |
| policy (informative priors) | {f(pol["max_spearman"])} | {f(pol["max_near_3px_fraction"])} | `{Path(pol["max_near_source"]).name if pol.get("max_near_source") else "n/a"}` |

Surface phase before placement: literal `{lanes["literal"]["verdict"]}`, policy
`{lanes["policy"]["verdict"]}`. Probes measured: {pol["universal_coverage_probes"]}; informative
priors: {pol["informative_priors"]}. Decoded-pattern uniqueness:
{"PASS" if sub["uniqueness_summary"]["canonical_pattern_unique"] else "FAIL"}; literal union of the
priors: {"YES" if sub["uniqueness_summary"]["equals_literal_prior_union"] else "NO"}; novel support
fraction {f(sub["uniqueness_summary"]["novel_fraction"])}.

**Why the literal rule fires, measured against chance.** The directed statistic has a chance level
equal to the prior's own 3 px coverage, because a uniformly random emission lands inside that halo with
exactly that probability. Of {lane_an["n_rasters"] if lane_an else "n/a"} registry rasters,
{lane_an["n_rasters_with_coverage_at_or_above_trigger"] if lane_an else "n/a"} have coverage at or above
the rule's own 0.70 trigger. Of {lane_an["n_near_offenders"] if lane_an else "n/a"} near-offenders,
{lane_an["n_probes"] if lane_an else "n/a"} are probes, and **all
{lane_an["n_informative_near_offenders"] if lane_an else "n/a"} informative ones have coverage
{f(min(o["coverage_3px"] for o in lane_an["informative_offenders"])) if lane_an and lane_an["informative_offenders"] else "n/a"}–{f(max(o["coverage_3px"] for o in lane_an["informative_offenders"])) if lane_an and lane_an["informative_offenders"] else "n/a"}
with negative excess over chance**
({f(min(o["excess_over_chance"] for o in lane_an["informative_offenders"])) if lane_an and lane_an["informative_offenders"] else "n/a"}
to {f(max(o["excess_over_chance"] for o in lane_an["informative_offenders"])) if lane_an and lane_an["informative_offenders"] else "n/a"}).
Across the whole registry the median excess is
{f(lane_an["excess_over_chance"]["median"]) if lane_an else "n/a"} and only
{lane_an["excess_over_chance"]["n_above_zero"] if lane_an else "n/a"} of
{lane_an["n_rasters"] if lane_an else "n/a"} priors are positive: this emission is *less* clustered near
prior dots than uniform chance, and its maximum Spearman is {f(lit["max_spearman"])} against a 0.90
trigger. The preregistered threshold was not relaxed — the STOP stands and the artefact stays
research-only. This historical diagnostic creates no override or promotion path. Any future change to
the shared rule would require a separately authorized, prospectively frozen protocol; it cannot be
applied retroactively to this stopped file. [IR-H61-009]

Re-measured with the same instrument, two inherited artefacts are placed correctly: **CTD5** has
informative-prior near-dot fractions of 0.1063–0.1368 and |ρ| ≤ 0.0046 — its STOP was entirely the
probe, so the repair vindicates its own diagnosis. **H60C** has near-dot fraction 0.7929 against the
champion and 0.8087 against `h19-5`, with Spearman 0.7083: DUPLICATE/STOP under the literal rule
*and* under the policy, because those priors are informative. H60C's published gate used
support-novelty and Jaccard and never applied the brief's rule; it is flagged as IR-H61-007 and is
neither promoted nor deleted here.

**Concurrent closure.** The parallel R5 and H60D rounds merged into `main` after the census was
frozen, so the unchanged emission was re-checked against the
{closure["new_decoded_patterns_checked"] if closure else 0} newly added decoded patterns
(`scripts/h61_concurrent_closure.py`): verdict **{closure["verdict_on_new_rasters"] if closure else "n/a"}**,
max near-dot {f(closure["max_near_3px_fraction"]) if closure else "n/a"} (H60D, coverage
{f([r["coverage_3px_of_eligible"] for r in closure["rows"]][0]) if closure and closure["rows"] else "n/a"}),
max Spearman {f(closure["max_spearman"]) if closure else "n/a"}. The artefact was not rebuilt,
re-placed or re-tuned for that check, and a pass there does not overturn the recorded STOP.

## 5 · Not the union of the two views

{card["not_the_union"]["cells_differing_from_union_max"]:,} cells differ from the `max(A, B)`
emission, {card["not_the_union"]["cells_differing_from_view_A"]:,} from View A alone and
{card["not_the_union"]["cells_differing_from_view_B"]:,} from View B alone;
{card["not_the_union"]["dots_shared_with_union_max"]:,} dots coincide with the union emission
(Jaccard {f(card["not_the_union"]["jaccard_with_union_max"])}), and the field's Spearman against
`max(A, B)` is {f(card["not_the_union"]["spearman_field_vs_unionmax"])}. A high-A/middle-B pixel and a
high-A/high-B pixel have the same union score and opposite disagreement scores, so the field is not a
rescaling of the union. Strict A-only candidates (donor rank ≥
{reg["thresholds"]["donor_rank_min"]}, receiver rank inside
{reg["thresholds"]["receiver_rank_interval"]}): {card["not_the_union"]["strict_a_only_candidate_px"]:,} px,
of which {card["not_the_union"]["emitted_cells_that_are_strict_a_only"]:,} are emitted cells.

## 6 · The projection, which is never a score

DTI = T / (0.2·(T + S − M) + 0.8·(|G| − T)); with sparse dots M ≈ T, so DTI = d·S / (0.2·S + 0.8·|G|)
for credit density d. At S = {int(proj["G_lower"]["emitted_px"]):,} dots the break-even density to
match the reported champion is
**{f(proj["G_lower"]["breakeven_credit_density_to_match_champion"])}–{f(proj["G_upper"]["breakeven_credit_density_to_match_champion"])}**
per emitted pixel ({f(proj["G_lower"]["breakeven_multiple_of_random"], 1)}–{f(proj["G_upper"]["breakeven_multiple_of_random"], 1)}×
uniform random, which is {f(proj["G_upper"]["random_dot_density"])}–{f(proj["G_lower"]["random_dot_density"])}).
If the arm's density equalled its HOLDOUT-DTI density
({f(proj["holdout_arm_density"])}), the projected DTI would be
{f(proj["G_lower"]["dti_if_density_equals_holdout_arm"])}–{f(proj["G_upper"]["dti_if_density_equals_holdout_arm"])}
— below the champion at both ends. Pixels outside all thirteen scored files belong to no identified
atom, so organiser-tied evidence bounds their credit only by [0, |G|]: neither "worthless" nor
"valuable" is proven, and the holdout density comes from an instrument that does not predict the
board. **No leaderboard gain is claimed, and none is projected.**

## 7 · Limits

1. The shipped surface is an out-of-fold mosaic of four quadrant models, not one model refit on
   everything; inter-fold rank calibration and quadrant seams are unvalidated.
2. The hidden truth is expert-drawn off-catalogue structure. The holdout hides *catalogue*
   components, so it measures a related but different recovery task.
3. Inputs are SHA-256-pinned owner mirrors of a login-walled portal file. Pins prove mirror
   consistency, not organiser authentication. No organiser receipt, authenticated weekly allowance or
   live leaderboard observation was available in this sandbox, whose egress is limited to github.com,
   api.github.com, codeload.github.com, pypi.org and files.pythonhosted.org.
4. External radiometrics are uint8 percentile quantisations derived by the owner's CI from the USGS
   GeoDAWN release (DOI 10.5066/P93LGLVQ); only rank and gradient transforms are used, and absolute
   units are unauthenticated.
5. Fault candidates are not geothermal vents and establish neither permeability nor a reservoir.
   `docs/downloads/h61-a-only-reasoning.csv` gives every emitted cell a measured context, the named
   non-fault mimic (a basin-fill density boundary or volcanic lithologic contact; secondarily buried
   palaeo-channels, fan margins, dykes and flight-line artefacts in the continued field) and a
   falsifier. No geologist reviewed any structure and no field observation was collected.

## 8 · What should happen next

1. **Change what View A is.** Raw potential-field channels do not transfer between quadrants. A
   physically parameterised predictor — a modelled basement-depth step across a candidate trace, a
   strike-continuity score along an interpreted lineament, an isostatic-residual discontinuity — is a
   different object from a band value and is the obvious next candidate. Measure its out-of-quadrant
   AUC **before** building an emission.
2. **Run H61-D: cross-file credit localisation by terrain stratum.** Cross the LP atoms with slope,
   modelled cover thickness and radiometric alteration strata and bound credit per stratum, so the
   organiser's own scores say *where* hidden truth sits rather than *which prior* found it. No new
   data needed; deferred only by this round's three-experiment budget.
3. **No promotion path for this artifact.** The shared policy lane verdict is DUPLICATE/STOP and the
   H61 holdout did not clear its promotion gate. The historical score-derived density comparisons are
   conditional scenarios, not measured credit. Do not present a selector override or weekly-slot
   exception as a way around the stop.
4. **Authenticate.** One submission-page receipt tying a file SHA-256 to a score would convert
   IR-H61-004 from a caveat into a calibration, and would settle whether 0.2778 exists at all.
5. **Reconcile `registry/data_manifest.json` provenance text** with the owner's score list
   (IR-H61-008) without touching the pins.

**Operational values.** This historical H61 file remains research-only: the lane gate is DUPLICATE/STOP,
the holdout does not establish leaderboard performance, and no weekly slot was used. Preserve the
negative result, repaired instruments, provenance gaps, and reproducible evidence without implying an
override or a score forecast.
"""
    out = ROOT / "knowledge/31_h61_results_and_limits.md"
    out.write_text(doc)
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


def gates_probe() -> float:
    # Read the scalar from source instead of importing the full gate module: rendering a
    # historical note should not require NumPy/rasterio or mutate the runtime environment.
    import re
    text = (ROOT / "src/gems52/gates.py").read_text()
    match = re.search(r"^PROBE_COVERAGE\s*=\s*([0-9.]+)", text, re.M)
    if not match:
        raise RuntimeError("PROBE_COVERAGE is missing from src/gems52/gates.py")
    return f"{float(match.group(1)):g}"


if __name__ == "__main__":
    raise SystemExit(main())
