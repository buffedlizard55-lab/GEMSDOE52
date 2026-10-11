# 97 — H103 results and limits (2026-10-11)

Verdict: **NEGATIVE**. OK TO DOWNLOAD: yes (format audit only). OK TO SUBMIT: **NO**. Experiments used 2 of 3 (experiment 2 is a labelled post-hoc diagnostic, not promotable). Slots used: 0.

Preregistration: `knowledge/108_hypotheses_H97_preregistered.md`, `registry/h103_preregistration.json`. Run card: `evidence/h103_run_card.json`. Receipts: `evidence/h103_*.json`.

## 1. Holdout (pre-registered arms, HOLDOUT-DTI, gems52-pooled-hide-v1, 53,186 withheld positive px)

| arm | DTI | 95 % CI |
|---|---|---|
| B_DVA2_HVA (control, promotable bar) | 0.190147 | — |
| graft_primary (H103 candidate) | 0.047183 | [0.034716, 0.060419] |
| consensus_only | 0.132823 | — |
| single_A | 0.071954 | — |
| random | 0.080426 | — |

Paired graft − B_DVA2_HVA: −0.142964 [−0.164118, −0.121119]. The graft is below the bar and below its own control. Source: `evidence/h103_holdout.json`.

Control check: B_DVA2_HVA reproduces at 0.19014734 against the committed 0.190147 (absolute delta 3.4e-7, PASS).

## 2. Post-hoc diagnostic (experiment 2, not promotable)

`evidence/h103_posthoc_diagnostic.json`: veto_only 0.095002 [0.079507, 0.110836]; graft_no_veto 0.061309 [0.046613, 0.077939]. The veto is not the main cause: removing it does not recover the control. The A-only term drives the failure. This was a post-hoc decomposition, not a second preregistered attempt, and it does not change the verdict.

## 3. Lane (non-adjacent registry checks)

- Surface field: literal PASS (max Spearman 0.2562 against the 0.90 limit); policy PASS (0.0931); scored-only PASS.
- Dots, full census (611 rasters): literal DUPLICATE/STOP. The max 3 px share is 1.0, from universal-coverage probes, which the policy excludes by design.
- Dots, policy: DUPLICATE/STOP. The max 3 px share is 0.8773 against `15GEMSDOE/…/gems-cleanup-a-20260928T195952Z-curv_scarp.tif`, whose dots cover 89.8 % of the eligible footprint (below the preregistered probe threshold of 0.95, so it counts as informative). Other informative offenders: 0.8493, 0.8236, 0.7600.
- Chance control (`scripts/h103_lane_chance_control.py`, `evidence/h103_lane_chance_control.json`): random dots of the same count score **0.8959** on the same raster, above H103's 0.8773. The dot-lane 3 px rule trips on high-coverage rasters for any placement. This is a gate-sensitivity finding (IR-H103-006). The verdict is not waived and the threshold is not retuned.

## 4. Candidate file

- `submission/gems52-h103-graft-B_DVA2_HVA-37654px-20261011T010835Z.tif`, SHA-256 `588d0db7af4e818d90d84ecb983ab1bb842a327f49f9a047dfb04528625f9419`, 128,840 bytes.
- Validator PASS: single-band float32, EPSG:32611, 3730×3292, values exactly {0, 1}, 37,654 ones, no NaN, no nodata.
- Not the union: Jaccard with the union 0.0649; with single_A 0.1430; with B_DVA2_HVA 0.0010.
- A-only reasoning CSV: `docs/downloads/…-a-only-reasoning.csv`, 37,654 rows, every dot with A rank > B rank.
- Uniqueness: canonical (decoded) pattern unique over 611 census priors; no identical prior. Support-novelty gate (≥ 20 %) FAILED with novel fraction 0.0. Recorded as a failed diagnostic, not waived. The `uniqueness_pass` check is the decoded-pattern criterion only.
- Name `h103-graft-B_DVA2_HVA-37654px-20261011T010835Z` (45 chars). Note 139/140 chars.

## 5. Limits

- The holdout is the only promotion evidence. The H84 receipt's B_DVA2 control does not reproduce its own committed value (IR-H103-001), so B_DVA2_HVA is the control only through its own reproduced number.
- The A-only term puts the entire emission budget on A-confident / B-abstaining cells (all 37,654 dots are A-only). The single_A arm (A alone) scores 0.071954, below random 0.080426, so the A-view signal is weaker than random placement on this holdout. Do not re-run this graft with changed weights (measured dead end).
- A 0.0 fill outside the footprint is used in place of the NaN the official page permits (IR-H103-004); scoring is identical, but the portal behaviour for NaN is unverified.
- The rank domain is stitched per fold (IR-H103-002).

## 6. Irregularities

IR-H103-001 to IR-H103-007 in `registry/irregularities.json`.

## 7. Label history (disclosure)

- This round was built and first recorded under the label H97. On `main`, the label H97 had already been taken by parallel rounds (H97 co-training sparse, H97b, H98 to H101, with their own IR-H97-* and IR-H98-* ids). This round is therefore registered as **H103**. Its IR ids are IR-H103-001..007.
- The preregistration **document is unchanged**: `knowledge/108_hypotheses_H97_preregistered.md`, SHA-256 `11b40c7f6340381d5e37ce45dc4ea9e89f0eb2d6d9678cf7d71c6d0dc4dafb29`, which matches the pinned value in `registry/h103_preregistration.json`. Only its path changed. Its text still says H97, because it was frozen under that name before the collision.
- Labels in this round's receipts and scripts were changed from H97 to H103 (file names, round fields, and text). The numbers were not changed.
- The census was widened on merge with `main`: the local submission folder now includes main's submissions, so the lane was re-run against the merged census (evidence/h103_lane.json registry_full: 524 present census priors, 75 local artefacts including main's new submissions, 13 extra scored references; n_full 611 after de-duplication). The earlier 601-raster census is superseded.
