# 64 · H76 results and limits (rendered from the receipts by `scripts/publish_h76_site.py`)

**Verdict: `NEGATIVE, research-only`** · download OK: **True** · spend a weekly slot: **False**

Artefact `gems76-line-support-B-cotrain-37654px-20261009T193810Z.tif`, SHA-256 `49ad60980f8bf768b94a2753581cae9ba572c75564d862089cec8093bcf317ad`, 137255 bytes, 37654 emitted cells.
Preregistration `knowledge/67_hypotheses_H76_preregistered.md`
(SHA-256 `d117b265d44aed769ec19e9a38f10ad5aa53793feca52be0e6a8579dfc8e3b55`, pinned in `registry/h76_preregistration.json`),
amendment `knowledge/67a_h76_amendment_shipped_arm_rule.md`.

## 1 · What H76 changed

Five rounds closed this lane on one gate: View A's out-of-quadrant AUC on *all* held-out truth is ~0.52, below the
0.60 sufficiency bar. H76's claim is that this gate is confounded: the catalogue's faults are surface-expressed by
selection, so "View A cannot predict mapped faults" and "View A is uninformative" are not the same statement. The
new test **S1′** restricts View A's AUC to held-out truth inside View B's blind band and requires it to beat both an
absolute bar and View A's own AUC on surface-expressed truth.

| measurement | value | bar |
|---|---:|---:|
| View A AUC, all held-out truth (old gate S1) | 0.5163 | 0.60 |
| View B AUC, all held-out truth | 0.6843 | — |
| View A AUC, truth in View B's blind band | 0.4893 | ≥ 0.60 |
| View A AUC, surface-expressed truth | 0.5436 | — |
| conditional margin | -0.0543 | ≥ +0.05 |

S1 global pass: **False**. S1′ conditional pass: **False**.
Conditional AUCs are label-selected diagnostics, not unbiased estimates.

### Per fold — the actual finding

| fold | truth px | A all | B all | A∣B-dark | A∣B-blind | A∣B-bright | margin |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 27,309 | 0.5062 | 0.6625 | 0.4554 | 0.4854 | 0.5339 | -0.0484 |
| 1 | 10,677 | 0.6011 | 0.7684 | 0.5685 | 0.5714 | 0.6139 | -0.0425 |
| 2 | 6,813 | 0.4668 | 0.6112 | 0.4250 | 0.4278 | 0.5108 | -0.0830 |
| 3 | 8,387 | 0.4910 | 0.6952 | 0.4251 | 0.4727 | 0.5158 | -0.0431 |

**In every fold, without exception, A∣B-dark < A∣B-blind < A∣B-bright.**
View A is least informative exactly where View B is blind and most informative where View B is already confident —
the reverse of the H76 hypothesis. This does not merely fail the bar, it forecloses the rescue argument that kept
the lane open for six rounds: View A's apparent skill is a shadow of the same surface-expressed structures View B
reads directly, not an independent subsurface channel that the catalogue under-samples. A buried-fault population
visible only to gravity and magnetics would have produced the reverse ordering.

Conditional **independence** is not what failed: max |ρ| 0.1331 over
2,089 blocks, well inside the 0.60 abandon bar. Co-training's independence
precondition holds on this data; its *sufficiency* precondition is refuted, now conditionally as well as globally.

## 2 · HOLDOUT-DTI (`gems52-pooled-hide-v1`, 53186 withheld positive px, 9400 dots/fold)

| arm | HOLDOUT-DTI | 95% CI | paired Δ vs single_B |
|---|---:|---:|---:|
| `disagreement_post` | 0.030584 | [0.020941, 0.042238] | -0.143933 [-0.167383, -0.121183] |
| `swap_050` | 0.152317 | [0.131466, 0.173735] | -0.022201 [-0.027505, -0.016355] |
| `disagreement_pre` | 0.033293 | [0.023815, 0.044556] | — |
| `union_max` | 0.148981 | [0.128084, 0.169418] | — |
| `random` | 0.080426 | [0.070223, 0.090973] | — |
| `swap_010` | 0.168343 | [0.146443, 0.190252] | -0.006175 [-0.009869, -0.002305] |
| `swap_025` | 0.160427 | [0.138964, 0.181651] | -0.014091 [-0.018133, -0.009855] |
| `single_B` | 0.174517 | [0.152316, 0.196299] | — |
| `line_support_B` **(shipped)** | 0.172426 | [0.150155, 0.195030] | -0.002091 [-0.005873, 0.001289] |
| `single_A` | 0.071954 | [0.056636, 0.088566] | — |

Control reproduction: single_B 0.174517 vs committed
0.174517, |Δ| 2.88e-07
(tolerance 0.001).

## 3 · The six frozen clauses

* 1 · Format: single-band float32 GeoTIFF, EPSG:32611, 3730×3292, transform of sample_submission.tif, every value in [0,1], no NaN → **PASS**
* 2 · Uniqueness: decoded pattern differs from every one of the 643 comparable registry rasters and is not the literal union of them → **PASS**
* 3 · Parallel-lane gate on the final dots (saturation policy: Spearman ≤ 0.90 and ≤ 70% of dots within 3 px of any informative prior) → **PASS**
* 4 · Not merely the union of the two views → **PASS**
* 5 · Conditional sufficiency S1′: View A's out-of-quadrant AUC on truth inside View B's blind band ≥ 0.60 and ≥ 0.05 above its AUC on surface-expressed truth → **FAIL**
* 6 · HOLDOUT-DTI: the shipped arm's paired 95% CI against single_B has a lower bound above zero → **FAIL**

## 4 · Placement

Shipped arm `line_support_B`; A-only stratum 29,669 px, 842
lane candidate cells, 431 of them emitted by the shipped raster of
37,654; legal pool 1942371 px at cross-family consensus ≤ 50;
per-prior near-dot quota 26301 over 262 packed informative priors;
3 px hard-core separation. Lane (dots, policy) max near-3px share
0.6985 against the 0.70 bar → **PASS**.

## 5 · Limits

* **The holdout measured the ranking RULE, not the shipped bytes.** `line_support_B` was scored on each
  fold's full allowed domain. The shipped raster applies the same rule inside a pool restricted to
  cross-family consensus ≤ 50, which is what makes it lane-feasible — and that
  restriction moves almost every dot (Jaccard against the `single_B` placement is only
  0.0060). No holdout number describes the shipped bytes. This
  limitation is shared with H69 and H73 and is the main reason the file is research-only.
* HOLDOUT-DTI does not rank the board (Spearman −0.10, `knowledge/10` §5). No number here is a projection.
* Holdout prevalence ≈ 1% vs competition ≈ 0.15%; absolute DTI values are not comparable to leaderboard values.
* The literal lane rule fails for every non-empty raster on this registry because the registry contains
  15 measured universal-coverage probes; the policy rule over
  627 informative priors is the repository's authoritative lane verdict.
* Conditional sufficiency is measured on a label-selected subset and is a diagnostic only.
* The reasoning CSV is measured context plus a templated hypothesis and a named mimic — not field-verified geology.
* Inputs are SHA-256-pinned owner mirrors of the competition data, not organiser-authenticated downloads.
* Registry scope: the supplied, aligned, publicly mirrored inventory only; private or unlinked artefacts are not
  proven absent.
