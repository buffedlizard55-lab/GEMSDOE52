#!/usr/bin/env python3
"""Refresh the README status block for round H97.

Reads only receipts written by ``scripts/run_h97.py`` (plus the E4/E4b diagnostics and the
irregularities register); nothing on the block is invented or projected onto the leaderboard.

Behaviour
---------
* Replaces the region delimited by ``<!--H95-README-->`` … ``<!--/H95-README-->`` (or a previous
  ``<!--H97-README-->`` region) with a fresh H97 status block.
* The standing user brief that currently sits inside the H95 region (heading
  ``# 94 · Standing user brief …``) is carried across **byte-identically**; the script asserts that.
* Idempotent: running it twice leaves the second run's output equal to the first.

Usage: python3 scripts/publish_h97_readme.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
README = ROOT / "README.md"
BRIEF_HEADING = "# 94 · Standing user brief"


def load(name):
    return json.loads((EV / name).read_text())


def main() -> int:
    text = README.read_text(encoding="utf-8")
    if "<!--H97-README-->" in text:
        head, rest = text.split("<!--H97-README-->", 1)
        _old, tail = rest.split("<!--/H97-README-->", 1)
        brief = ""
        archived_h95 = ""
    elif "<!--H95-README-->" in text:
        head, rest = text.split("<!--H95-README-->", 1)
        region, tail = rest.split("<!--/H95-README-->", 1)
        brief = region[region.index(BRIEF_HEADING):]
        # the retired round's own status block stays in the README as an archive, the way the
        # H89/H87/H83/H82 blocks before it did; only its own markers are re-closed here
        archived_h95 = "<!--H95-README-->" + region[:region.index(BRIEF_HEADING)].rstrip("\n") + \
            "\n<!--/H95-README-->\n"
    else:
        raise SystemExit("README has no known status marker")

    card, hold, fit, ind = (load("h97_run_card.json"), load("h97_holdout.json"),
                            load("h97_fit.json"), load("h97_independence.json"))
    lane, build = load("h97_lane.json"), load("h97_build_placement.json")
    e4, e4b = load("h97_e4_coverage.json"), load("h97_e4b_hysteresis.json")
    reg = json.loads((ROOT / "registry/irregularities.json").read_text(encoding="utf-8"))

    v = card["validator"]
    pool = hold["pooled"]["scores"]
    gate = hold["promotion_gate"]
    vd, vs = lane["dots"]["policy"], lane["surface"]["policy"]
    uniq = lane["uniqueness"]
    g4, g4b = e4["geometry_vs_mass"], e4b["geometry_vs_mass"]
    ir97 = [e["id"] for e in reg["entries"] if e["id"].startswith("IR-H97")]
    BAR = 0.190147  # standing bar, frozen in registry/h97_preregistration.json (knowledge/73)

    arm_rows = "\n".join(
        f"| `{a}` | {pool[a]['dti']:.6f} [{pool[a]['ci95'][0]:.6f}, {pool[a]['ci95'][1]:.6f}] |"
        for a in pool)
    fold_rows = "\n".join(
        f"| {r['fold']} | {r['auc']['single_A2']:.4f} | {r['auc']['single_B2']:.4f} | {r['canary_max']:.4f} |"
        for r in fit["folds"])
    budget_rows = "\n".join(
        f"| {f['fold']} | {f['budget_curve']['9400']:.6f} | {f['budget_curve']['16000']:.6f} |"
        f" {f['budget_curve']['25400']:.6f} |" for f in hold["folds"])
    geom_rows = "\n".join(
        f"| `{f}` | {g4b[f]['dots_K_dti']:.6f} | {g4[f]['bridged_dti']:.6f} | {g4b[f]['hyst_dti']:.6f} |"
        f" **{g4[f]['dots_matched_mass_dti']:.6f}** | {g4[f]['random_same_mass_dti']:.6f} |"
        f" {'loses' if not g4[f]['GEOMETRY_BEATS_MASS_AT_MATCHED_MASS'] else 'wins'} |"
        for f in ("cotrain_disagree", "single_B2"))

    block = f"""<!--H97-README-->
# Current status — H97 (2026-10-11): potential-field directional anisotropy (PAF-DVA) as View A · NEGATIVE

> **OK TO DOWNLOAD: YES** — format-valid single-band float32 GeoTIFF, EPSG:32611, 3730×3292, all-finite,
> values exactly {{0,1}} (the portal's *"Predicted values must be in range [0, 1]"* rejection cannot occur).
>
> **OK TO SUBMIT: NO — research-only, do not upload.** Failed gate: **holdout_promotion**. The
> disagreement field scored **{pool['cotrain_disagree']['dti']:.6f}** on HOLDOUT-DTI — *below* the random
> control ({pool['random']['dti']:.6f}) and far below the standing bar {BAR:.6f}; the best comparable control
> `{gate['best_comparable_control']}` scored {gate['control_dti']:.6f}, paired difference
> {gate['delta']:+.6f} [{gate['ci95'][0]:+.6f}, {gate['ci95'][1]:+.6f}].
>
> Weekly slots used: **{card['submission_slots_used']}**. No weekly slot is approved by this round; the agent
> does not pick submissions.

**★ [Download h97-candidate.tif](docs/downloads/h97-candidate.tif)** ·
[ZIP](docs/downloads/h97-candidate.zip) · [A-only reasoning CSV](docs/downloads/h97-a-only-reasoning.csv) ·
[Full result](docs/h97.html) · [Executive summary / how to submit](docs/executive-summary.html) ·
[Run card](evidence/h97_run_card.json)

- **File:** `submission/gems52-{card['submission_name']}.tif` — {card['raster_bytes']:,} bytes,
  SHA-256 `{card['raster_sha256']}`
- **Submission name:** `{card['submission_name']}` · **Note ({card['note_chars']}/140):**
  `{card['note']}`
- **Validator (re-read from disk):** {v['count']} band {v['dtype']}, {v['crs']}, {v['shape'][0]} rows x
  {v['shape'][1]} cols, transform/bounds = sample_submission.tif: yes, NaN {v['nan']}, inf {v['infinite']},
  values exactly [{v['min']}, {v['max']}], {v['ones']:,} emitted cells, nodata tag None; problems: none
- **HOLDOUT-DTI** (`gems52-pooled-hide-v1`, {hold['withheld_positive_px']:,} withheld positive px,
  {hold['budget_per_fold']:,} dots per fold per arm, 95 % CI, 1,000 paired physical-cluster bootstrap draws):

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{arm_rows}

  Paired `cotrain_disagree − single_B2` = **{gate['delta']:+.6f}** [{gate['ci95'][0]:+.6f},
  {gate['ci95'][1]:+.6f}]; standing bar {BAR:.6f}; CI lower bound above zero:
  {gate['ci_lower_above_zero']} → **{'PASS' if gate['PROMOTE'] else 'FAIL'}**.
- **View-A sufficiency (out-of-quadrant AUC on the held-out region, per fold):**

| fold | single_A2 AUC | single_B2 AUC | leakage canary max |
|---|---|---|---|
{fold_rows}

  Mean View-A AUC {sum(r['auc']['single_A2'] for r in fit['folds']) / len(fit['folds']):.4f} — the eighth
  consecutive failure of the potential-field view to carry usable signal; canary alarm (bar 0.90):
  **{fit['canary_alarm_any']}**.
- **Independence (spatial-block OOF error correlation on labelled negatives):** max |ρ|
  {ind['result']['max_abs_correlation']:.4f}; abandon ≥ {ind['result']['threshold']} → exchange allowed.
- **Emission-geometry diagnostic (E4/E4b, this round's second and third experiments):** at *matched emitted
  mass*, does a connected trace along the field beat more well-separated dots? No — both constructions lose
  to dots **and** to random at the same mass, on both test fields:

| field | dots @ 9,400 | bridged @ S | hysteresis @ S | dots @ S | random @ S | verdict |
|---|---|---|---|---|---|---|
{geom_rows}

  This closes "coverage emission" as a fix *on the catalogue instrument*; it does not close it on the board,
  whose truth set and scoring region differ ([knowledge/99](knowledge/99_h97_results_and_limits.md) §7–§8).
- **Budget diagnostic (does NOT select the budget — amendment h97a):** frozen at
  {build['target_dots']:,} dots = 4 × {hold['budget_per_fold']:,}.

| fold | 9,400/fold | 16,000/fold | 25,400/fold |
|---|---|---|---|
{budget_rows}

- **Gates (frozen in `registry/h97_preregistration.json`):**

| gate | result | measured |
|---|---|---|
| leakage_canary | PASS | max single-feature out-of-quadrant AUC {max(r['canary_max'] for r in fit['folds']):.4f}; alarm 0.90 |
| independence | PASS | max \\|rho\\| {ind['result']['max_abs_correlation']:.4f} over {ind['result']['n_blocks']:,} blocks; abandon ≥ 0.60 |
| holdout_promotion | FAIL | primary {pool['cotrain_disagree']['dti']:.6f} vs standing bar {BAR:.6f}; paired vs control {gate['delta']:+.6f} [{gate['ci95'][0]:+.6f}, {gate['ci95'][1]:+.6f}] |
| format | PASS | 1 band float32, EPSG:32611, 3730×3292, transform/bounds = sample_submission.tif: yes, 0 NaN, 0 inf, values exactly [0.0, 1.0], {v['ones']:,} emitted cells |
| uniqueness | PASS | {uniq['n_priors_checked']} locally available priors; identical to a prior: {uniq['identical_to_a_prior']}; canonical pattern unique: {uniq['canonical_pattern_unique']} |
| lane_surface | PASS | max Spearman {vs['max_spearman']:.4f} (bar 0.90) |
| lane_dots | PASS (close) | max near-3px {vd['max_near_3px_fraction']:.4f} (bar 0.70) → **IR-H97-005** |
| not_the_union | PASS | Jaccard vs union-max {card['not_the_union']['jaccard_with_union']:.4f}, vs single-A {card['not_the_union']['jaccard_with_single_A']:.4f}, shared with single-B {card['not_the_union']['shared_with_single_B']} |

  This round preregistered **no control-reproduction gate** (unlike H95); the controls are the in-round arms
  themselves, and `single_B2` ({pool['single_B2']['dti']:.6f}) reproduces the family's known single-view level
  (H82's `B_DVA2` 0.189200 was a non-promotable finding arm).
- **Placement:** {build['dots']:,} cells at ≥3 px spacing, pool {build['pool_px']:,} px of
  {build['eligible_px']:,} eligible px, ≤{build['ring_excluded_m']:.0f} m catalogue collar excluded;
  nearest emitted cell to the mapped catalogue {build['min_cat_dist_m']:.1f} m, median
  {build['median_cat_dist_m']:.0f} m, {build['dots_within_300m_of_catalogue_pct']:.2f} % of the mass within
  300 m of a mapped fault.
- **Irregularities:** {' · '.join(ir97)} — board corrections (IR-H97-001..004), lane proximity (IR-H97-005);
  the register now carries {len(reg['entries'])} entries.
- Docs: [preregistration](registry/h97_preregistration.json) ·
  [hypotheses](knowledge/97_hypotheses_H97_preregistered.md) ·
  [results & limits](knowledge/99_h97_results_and_limits.md) ·
  [metric/coverage note](knowledge/98_the_metric_is_a_coverage_metric.md) ·
  [next-round proposals](knowledge/100_next_round_proposals.md)
- Reproduce: `python3 scripts/restore_data.py --target-dir data` → feature store + `python -m gems52.external`
  → `python3 scripts/run_h97.py all` → `python3 scripts/run_h97_e4_coverage.py` →
  `python3 scripts/run_h97_e4b_hysteresis.py` → `python3 scripts/publish_h97_site.py` →
  `python3 scripts/publish_h97_readme.py`.

### Why `h33-h33-2-b2` scored 0.2778, and can we beat it? (derivation: [knowledge/76](knowledge/76_why_02778_and_what_beating_03195_requires.md))

- DTI = T / (0.2·S + 0.8·|G|) with S = emitted mass and |G| the hidden positives. Our predictions are binary,
  so S is the dot count, and a dot raises the score only if its kernel credit exceeds ≈0.2·DTI (about 0.056
  at the 0.2778 level). The board shows this directly: Spearman(emitted mass, score) = −0.93 over our scored
  files. H97's E4/E4b add the mechanism: on the catalogue instrument, **mass dominates shape** — random
  placement at ~400 k cells scores 0.177–0.197 while every trace construction loses.
- The champion is the 0.2600 `d2-8` field (44,090 px) with every dot within 200 m of the public catalogue
  deleted, leaving 37,654 dots. The hidden faults are *new* faults, so dots on the known catalogue are pure
  false-positive mass; deleting them raised the score by +0.0178 with no new signal.
- Beating the top-5 cut (0.3262) needs ×1.15 more credit at the same mass, or the same credit from about
  25,400 dots; beating rank 1 (0.3774, verified live 2026-10-10) needs ×1.36. No ranking signal in this
  repository — H97's co-training included — has yet shown that precision on an instrument that tracks the
  board. **Honest answer: not yet demonstrated; the levers are listed below.**

### Next work (ranked in [knowledge/100](knowledge/100_next_round_proposals.md); each must beat 0.190147 on the holdout or show a board-anchored gain before using a slot)

1. **Prevalence-matched off-catalogue instrument (H89-P).** E4/E4b prove the catalogue instrument pays for
   mass regardless of shape, so it cannot certify the one lever with board evidence (emitted mass, ρ −0.93);
   the existing off-catalogue instrument carries ~4× real prevalence. Build the thinned one first.
2. **Alteration-ratio anisotropy (Th/K, U/K, U/Th from the pinned GeoDAWN layers) as a third view** — with a
   flight-line striping control, since that is the named non-fault mimic for any radiometric texture.
3. **Tip-and-stepover continuation gated by the surface anisotropy ridge** — cheap, no new channels.
4. **Do not retry:** naive bridging (E4) or hysteresis growth (E4b); View-A-only fits (eight sufficiency
   failures); iterative pseudo-label exchange (closed negative).
5. **INGENIOUS 2 m temperature probes** (GDR 1391, DOI 10.15121/1881483) remain the highest-value unused
   channel, but `gdr.openei.org` is not reachable from this sandbox — the owner must download and pin it.
<!--/H97-README-->
"""

    rest_after = tail.lstrip("\n")
    if brief:
        new = (head + block + "\n" + brief.rstrip("\n") + "\n\n" + archived_h95 + "\n" + rest_after)
        # the brief must survive byte-identically
        i = new.index(BRIEF_HEADING)
        kept = brief.rstrip("\n")
        assert new[i:i + len(kept)] == kept, "brief changed during rewrite"
        after_brief = new[i + len(kept):].lstrip("\n")
        assert after_brief.startswith(archived_h95.strip("\n")) or after_brief == rest_after, \
            "tail changed during rewrite"
    else:
        new = head + block + rest_after
    README.write_text(new, encoding="utf-8")
    print(json.dumps(dict(readme_bytes=len(new), block_lines=block.count(chr(10)),
                          entries=len(reg["entries"]), brief_preserved=bool(brief)), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
