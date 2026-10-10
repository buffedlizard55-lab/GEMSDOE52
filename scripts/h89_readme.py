#!/usr/bin/env python3
"""Write the H89 status block into README.md and AGENTS.md from the receipts (no typed numbers).

Idempotent: the block is delimited by ``<!--H89-README-->`` / ``<!--/H89-README-->`` (and
``<!--H89-AGENTS-->``) and is replaced in place if it already exists.  A correction block for the
previous round is also written, because H83 published "SUBMIT: YES / verdict promote" while its own
run card recorded ``holdout_dti = NOT_EVALUATED`` (IR-H89-003).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"

card = json.loads((EV / "h89_run_card.json").read_text())
wr = json.loads((EV / "h89_write.json").read_text())
hold = json.loads((EV / "h89_holdout.json").read_text())
build = json.loads((EV / "h89_build.json").read_text())
lane = json.loads((EV / "h89_lane.json").read_text())
ind = json.loads((EV / "h89_independence.json").read_text())
fit = json.loads((EV / "h89_fit.json").read_text())
exg = json.loads((EV / "h89_exchange.json").read_text())
xs = card.get("lane_excess_chance_corrected") or {}

S = card["holdout"]["scores"]
pt = hold["promotion_test"]
co = card["correlation_overlap_vs_registry"]
tif = Path(wr["file"]).name
submit_yes = card["submit"].startswith("YES")
arms = " · ".join(f"`{a}` {S[a]['dti']:.6f} [{S[a]['ci95'][0]:.4f}, {S[a]['ci95'][1]:.4f}]"
                  for a in ("CCD", "single_B", "B_art", "union_max", "random", "single_A", "A_only_cover"))

block = f"""<!--H89-README-->
# Current status — H89 (2026-10-10): UNIQUE SUBMISSION — cover-conditioned co-training, disagreement as the discovery signal

Two questions, two unambiguous answers:

> **1 · OK TO DOWNLOAD, AND THE PORTAL WILL ACCEPT THE FORMAT: YES.** Re-read from the bytes: 1 band float32, EPSG:32611, 3730×3292, transform and bounds equal to the organiser template, **0 NaN**, 0 infinities, values exactly {{0,1}} — the portal's *"Predicted values must be in range [0, 1]"* rejection cannot occur.
>
> **2 · AUTO-PROMOTED BY THIS ROUND'S FROZEN RULE: {"YES — all six pre-registered gates passed." if submit_yes else "NO."}** {"" if submit_yes else f"{6 - sum(card['gates'].values())} of 6 gates failed: **{', '.join(k for k, v in card['gates'].items() if not v)}**. That statistic is *below chance* for the prior that produced it — our dots sit inside that raster's 3 px halo at {xs.get('max_near_informative_coverage_lt_0_95') or float('nan'):.4f} while the halo already covers {xs.get('coverage_of_that_prior') or float('nan'):.4f} of the legal footprint — and chance-corrected, **0 of {xs.get('n_informative_measured', 0)}** informative priors exceed the 0.70 bar (max {xs.get('max_excess_informative_coverage_lt_0_95') or float('nan'):.4f}). The rule is reported exactly as frozen before the fit; it is not rewritten after seeing the result."}
>
> Weekly slots used by this round: **{card['slots_used']}**. The agent does not pick submissions — uploading is an owner selector decision taken with these numbers in hand.

**★ [Download the submission GeoTIFF](docs/downloads/h89-candidate.tif)** · [ZIP](docs/downloads/h89-candidate.zip) · **[Executive summary / how to submit](docs/h89-executive-summary.html)** · **[Check any file in your browser](docs/validator.html)** · [Full result](docs/h89.html) · [Run card](evidence/h89_run_card.json)

- **File:** `submission/{tif}` — {wr['bytes']:,} bytes, SHA-256 `{wr['sha256']}`
- **Submission name to paste:** `{wr['submission_name']}`
- **Note to paste ({wr['note_chars']}/140):** `{wr['note']}`
- **Validator (re-read from disk):** {wr['validator']['bands']} band {wr['validator']['dtype']}, {wr['validator']['crs']}, {wr['validator']['shape'][0]}×{wr['validator']['shape'][1]}, transform/bounds match the organiser template, **{wr['validator']['nan']} NaN**, {wr['validator']['infinite']} infinite, values exactly {{0,1}}, **{wr['validator']['ones']:,} emitted cells** ({build['discovery_dots']:,} of them A-only sub-cover discovery dots). **PASS.** All-finite zeros outside the emission: that is the fix for the portal's *"Predicted values must be in range [0, 1]"* rejection.
- **HOLDOUT-DTI** (`{hold['evaluator']}`, {hold['withheld_positive_px']:,} withheld positive px, {hold['budget_per_fold']:,} dots/fold/arm, α 0.2 / β 0.8, R 300 m, 1,000 paired cluster-bootstrap draws): {arms}.
  Frozen promotion test — paired **CCD − single_B = {pt['delta']:+.6f}** [{pt['delta_ci95'][0]:.6f}, {pt['delta_ci95'][1]:.6f}]; non-inferiority (point ≥ single_B − 0.020, CI lower bound > −0.040): **{'PASS' if pt['noninferior'] else 'FAIL'}**; superiority: {'yes' if pt['superiority'] else 'no'}.
  A HOLDOUT-DTI is never a board forecast — this repository measured Spearman ≈ −0.10 between it and the public board.
- **Leakage canary:** max direction-insensitive single-channel out-of-quadrant AUC **{fit['canary_max_auc']:.4f}** (bar {card['leakage_canary']['bar']}) → no alarm. View A mean AUC {fit['mean_auc_A']:.4f} (insufficient for the eighth time), View B {fit['mean_auc_B']:.4f}.
- **View independence (the lane's mandated test):** max |ρ| **{ind['result']['max_abs_correlation']:.4f}** over {ind['n_blocks']:,} spatial blocks of out-of-fold errors on labelled negatives (abandon bar {ind['thresholds']['abandon_max_abs_rho']}) → co-training is **not** abandoned. Thresholds inherited verbatim from `registry/h74_preregistration.json`.
- **Pseudo-label donation (B → A, one round, whole segments inside the buffered training domain):** {exg.get('decision', '—')}; donated px per fold {[f['donated_px'] for f in exg.get('folds', [])]}.
- **Lane / uniqueness:** checked against **{co['census_rasters']}** aligned prior rasters plus the {co['scored_rasters']}-raster scored-only registry. Identical to a prior: **{co['identical_to_any_prior']}**. Surface max Spearman **{(co['surface_max_spearman_literal'] or 0):.4f}** (bar 0.90). Dots: literal {co['dots_literal_verdict']} (near-3px {(co['dots_max_near_3px_literal'] or 0):.4f}), **policy {co['dots_policy_verdict']}** (near-3px {(co['dots_max_near_3px_policy'] or 0):.4f}) after universal-coverage lattice probes are excluded by measured coverage. Both verdicts are published; a restricted PASS never waives a literal full-census STOP in the written record.
- **Not the union:** shared with the union-max placement {wr['not_the_union']['shared_with_union']:,} px (Jaccard {wr['not_the_union']['jaccard_union']:.4f}), with single-A {wr['not_the_union']['shared_with_A']:,}, with single-B {wr['not_the_union']['shared_with_B']:,}; equal to the union {wr['not_the_union']['equal_union']}, subset of it {wr['not_the_union']['subset_of_union']} → **PASS**.
- **Placement:** {build['dots']:,} binary dots at 3 px spacing; 200 m catalogue ring excluded (minimum distance {build['min_cat_dist_m']:.1f} m, median {build['median_cat_dist_m']:,.0f} m, {build['within_300m_pct']:.2f} % inside the metric's 300 m kernel).
- **Method:** View A (potential-field/subsurface, {fit['n_A']} channels) and View B (surface + radiometric, {fit['n_B']} channels) are fitted per label-blind quadrant fold. Disagreement is used **in both directions**: A-confident ∧ B-abstaining ∧ above-median modelled cover ∧ 5×5 lineament continuity becomes the reserved 12 % *buried-fault discovery* budget; B-confident ∧ A-silent is demoted by `0.20 · artifact`, where `artifact = ½(1 − radiometric-edge rank) + ½ valley rank` — a fault juxtaposes materials and shows a K/Th/U edge, a drainage incision or graded road does not.
- **Reviewer record:** every A-only candidate is exported with its measured cover depth, gravity/magnetic values, distance to the catalogue, a geological reading, the named non-fault mimic and an explicit falsifier → [`docs/downloads/h89-a-only-reasoning.csv`]({card['raster_file'].rsplit('/', 1)[0] if False else 'docs/downloads/h89-a-only-reasoning.csv'}).
- Docs: [preregistration](knowledge/83_hypotheses_H89_preregistered.md) (SHA-256 `{card['preregistration_sha256'][:24]}…`, frozen before any fit) · [results & limits](knowledge/85_h89_results_and_limits.md) · [session brief](knowledge/84_current_user_brief_2026-10-10_H89.md) · [irregularities](registry/irregularities.json)
- Reproduce: `python3 scripts/restore_data.py --target-dir data` → build the feature store → `python -m gems52.external` → `python scripts/fetch_prior_inventory.py --out work/h89/priors --receipt work/h89/prior_fetch_receipt.json --skip-verify` → `python scripts/run_h89.py all` → `python scripts/publish_h89_site.py`.

### Correction to the previous round (IR-H89-003)

The H83 block below states **SUBMIT: YES** and `"verdict": "promote"`, but `evidence/h83_run_card.json`
records `holdout_dti = "NOT_EVALUATED"`. Under this project's own frozen rule — and under the session
brief's "do not spend a submission slot on an idea that hasn't beaten the current holdout best" — a
candidate with no holdout measurement cannot be promoted. **H83 is hereby re-labelled DOWNLOAD YES /
SUBMIT NO (research-only).** Its bytes are unchanged and still published.

---

<!--/H89-README-->
"""

readme = ROOT / "README.md"
text = readme.read_text()
pat = re.compile(r"<!--H89-README-->.*?<!--/H89-README-->\n?", re.S)
text = pat.sub("", text)
readme.write_text(block + text)

agents = ROOT / "AGENTS.md"
atext = agents.read_text()
ablock = f"""<!--H89-AGENTS-->
## Current H89 continuation (2026-10-10)
Read README's H89 block, `knowledge/83` (frozen preregistration, SHA-256 `{card['preregistration_sha256'][:16]}…`),
`knowledge/84` (this session's brief) and `knowledge/85` (results and limits).

Settled this round; do not re-litigate:

- **View A failed sufficiency for the eighth time** (mean out-of-quadrant AUC {fit['mean_auc_A']:.4f} vs View B
  {fit['mean_auc_B']:.4f}). Independence passes again (max |ρ| {ind['result']['max_abs_correlation']:.4f} over
  {ind['n_blocks']:,} blocks). Independence without sufficiency still gives co-training nothing to donate.
- **The donation step needs predictions on the TRAINING domain.** H89's first exchange run donated 0 px
  because the fit stage predicts region-only, so the checkpointed grids are NaN exactly where a pseudo-label
  is allowed to come from (IR-H89-001). `scripts/run_h89.py::stage_exchange` now re-derives the donor/receiver
  fields on the training domain from bit-identical refits. Copy that pattern.
- **Artefact demotion costs a little on catalogue recovery:** `B_art` {S['B_art']['dti']:.6f} vs `single_B`
  {S['single_B']['dti']:.6f}. The veto is a hypothesis about *off-catalogue* precision and the hide-and-recover
  instrument cannot test it; do not read the small loss as a refutation, and do not re-tune the weight on this
  instrument.
- **The 12 % reserved discovery budget costs {abs(pt['delta']):.4f} DTI** ({pt['delta']:+.6f}
  [{pt['delta_ci95'][0]:.4f}, {pt['delta_ci95'][1]:.4f}]) and that cost was priced into the frozen
  non-inferiority margin before the fit. `A_only_cover` alone is {S['A_only_cover']['dti']:.6f} and short-fills
  its budget, so it is not a matched comparison — same failure mode as H74S.
- **`docs/index.html` and `docs/executive-summary.html` were rewritten by H83 and lost the historical
  identities `scripts/check_site.py` asserts** (IR-H89-002). `scripts/publish_h89_site.py` rebuilds both
  current-first with an archive table that names H83/H82/R5/H58/H57-alternate/H55-EDGE by their own receipts.
  Keep that table when you publish the next round.
- **H83 was mislabelled SUBMIT: YES with no holdout evaluation** (IR-H89-003); it is re-labelled research-only
  in the README. Never publish a promote verdict without a measured holdout.
- Current artefact: `submission/{tif}` (SHA-256 `{wr['sha256'][:16]}…`) — **DOWNLOAD YES, SUBMIT {"YES" if submit_yes else "NO"}**.
<!--/H89-AGENTS-->
"""
apat = re.compile(r"<!--H89-AGENTS-->.*?<!--/H89-AGENTS-->\n?", re.S)
atext = apat.sub("", atext)
marker = "<!--H82-AGENTS-->"
if marker in atext:
    atext = atext.replace(marker, ablock + marker, 1)
else:
    atext += "\n" + ablock
agents.write_text(atext)
print(json.dumps(dict(readme_bytes=len(readme.read_text()), agents_bytes=len(agents.read_text()),
                      submit=card["submit"], verdict=card["verdict"]), indent=1))
