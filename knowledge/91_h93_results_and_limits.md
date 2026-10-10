> **Label note.** This round is **H93** in this repository. `main` already holds an H88 round from another session (basement-step coherence), so the round label was changed. The frozen protocol (`knowledge/90`, bytes unchanged, pin verified) and the receipts under `evidence/h93_*` still carry the internal label **H88**. Every reference to "H88" in this document means this round.

# 81 · H93 results and limits — co-training with a disagreement-gated A-only stratum

**Verdict: NEGATIVE.** Download yes (format-valid, audit only). **Submit: NO.** Slots used: **0**. Experiments: **1 of 3**.
Protocol: `knowledge/90_h93_protocol_frozen_bytes_from_h88.md` (SHA-256 `50db10583392…`, pinned in `registry/h93_preregistration.json`).
Every number below is **HOLDOUT-DTI** unless stated, evaluator `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel),
**60,894 withheld positive pixels** over 4 label-blind quadrant folds, K = 9,400 dots per fold, 3 px spacing, 1,000-draw paired
physical 20 km cluster bootstrap (`evidence/h93_holdout.json`, produced by `scripts/run_h88_holdout.py`, 225 s on 2 CPUs).

## 1 · Results (the frozen arms)

| arm | HOLDOUT-DTI | 95 % CI |
|---|---:|---|
| single_A (View A alone) | **0.074611** | [0.059380, 0.091743] |
| random (floor, same allowed set) | **0.076551** | [0.068175, 0.084557] |
| **P_strict_cotrain (PRIMARY, pre-registered)** | **0.063055** | [0.049134, 0.078135] |
| h87_asbuilt (the H87 rule, first measurement) | 0.056889 | [0.043563, 0.071325] |
| single_B (View B alone) | 0.054771 | [0.042546, 0.066783] |
| S_BA_control (B-confident, A-abstain) | 0.054520 | [0.042458, 0.066336] |

Paired differences, primary minus arm (95 % CI):

| comparison | Δ | 95 % CI | reading |
|---|---:|---|---|
| P − single_A | **−0.011556** | [−0.019032, −0.004848] | co-training is **significantly worse** than View A alone |
| P − random | −0.013496 | [−0.026299, +0.001016] | below the floor, CI touches 0 |
| P − single_B | +0.008284 | [−0.009246, +0.029358] | not distinguishable from View B alone |
| P − h87_asbuilt | +0.006166 | [+0.001185, +0.011410] | the pre-registered rule beats the shipped H87 rule |
| P − S_BA_control | +0.008535 | [−0.009468, +0.030574] | not distinguishable |

Per-fold DTI (fold: withheld positives): fold 0 (29,297): P 0.02686, single_A 0.03778, random 0.04447. Fold 1 (12,579):
P 0.07249, single_A 0.08522, random 0.06277. Fold 2 (9,433): P 0.10455, single_A 0.12999, single_B 0.14199, random 0.14843.
Fold 3 (9,585): P 0.10553, single_A 0.10357, random 0.10674. P is below single_A in folds 0–2 and above it in fold 3; P is below random in folds 0, 2 and 3, and above random in fold 1 (0.07249 vs 0.06277).

## 2 · Gates (all run before the verdict)

* **Decision rule (protocol §5):** POSITIVE requires P ≥ 0.192829, P − single_B lower CI > 0, and P − random lower CI > 0.
  Measured: bar **fail**; single_B **fail** (−0.009246); random **fail** (−0.026299). Verdict NEGATIVE.
* **Leakage canary (alarm > 0.90):** max single-feature AUC on held-out truth inside the allowed set: rank_A 0.5565,
  rank_B 0.5933, P 0.5578, H87 field 0.5255. **No alarm.** A pure-catalogue leak would have shown AUC near 1.0.
* **Independence proxy (abandon at |ρ| ≥ 0.60):** 2,283 negative blocks; max |ρ| **0.229** (negative-block MSE and FPR
  correlations of the two unsupervised scores). **Passes**, with the protocol's caveat: these scores are unsupervised, so
  this is a proxy for conditional independence, not the fitted OOF test used in earlier rounds.
* **View A sufficiency proxy:** unsupervised canary AUC of rank_A on held-out truth is 0.5565 (max over folds), i.e.
  View A alone is near chance (0.56) on this instrument. This matches the eight earlier sufficiency failures in the
  repository (AGENTS.md). Independence without sufficiency gives co-training nothing to donate.
* **Stratum sizes:** S_AB (A-confident, B-abstaining) 411,799 px; S_BA 407,695 px; eligible footprint 5,164,300 px.
  View correlation over the eligible footprint: Pearson −0.139819 (matches H87's receipt, −0.13981911).

## 3 · What the measurement says (plain)

1. **Co-training as specified loses signal.** Every S_AB pixel outranks every non-S_AB pixel (P > 1 versus P ≤ 1), so the
   9,400 dots per fold are the highest-A pixels whose View B rank is at or below the 25th percentile. Highest-A pixels whose
   View B rank is above that cut are excluded. The loss is measured, not assumed: P is 0.011556 below View A alone.
2. **The H87 rule was not validated.** Its docstring claims "A confident, B abstains", but its emission is a continuous
   `(A − B)·gate` ranking. On this instrument it scores 0.056889 (below random). H93 shows the protocol rule does
   better than the H87 rule, but still below random.
3. **Nothing in this lane beats random here.** The repository's best arm on the older 53,186-withheld instrument is
   H84 `B_DVA2` 0.192829 (see §4). The lane's own arms do not reach random on this instrument.

## 4 · Instrument caveat (IR-H93-002) — read before comparing to older rounds

H82 and H84 receipts withhold **53,186** positives; H86 and H93 withhold **60,894** (H86 and H93 share one runner
logic, eligible = 19-band finite AND organiser domain, IR-52-002). **The cause of the H82/H84 difference was not traced in this
session** (they went through the H61 setup path). Random agrees across the two families (0.080426 vs 0.075429 for H86,
0.076551 for H93), so the random control is stable across the two families. That does **not** establish the cause of the bar gap. The **0.192829 bar is a
different-instrument number, and the H84 single_B (0.174571) is a different View-B method**, so the bar is a reference,
not a like-for-like threshold. The verdict does not depend on it: P is below random on the same instrument as H93.

## 5 · What was checked from the bytes (no hallucinated facts)

* Training-feature band tags were read from the GeoTIFF (19 bands). View A (`compute_view_a`) uses bands 5, 11, 18, 3, 9, 4, 7,
  15 and 17 (band 8 is not used). View B (`compute_view_b`) uses band 12 (Hessian wavelength contrast) and band 19 (slope). The GeoDAWN `ThK` label (external `geodawn_extensions_u8` band 1) and `U` (external
  `geodawn_rad_u8` band 3) were read from the external files' own labels.
* **Band 6** is tagged `tc` (tilt angle / total curvature, magnetic) in the training features. Its content is radiometric:
  Pearson **0.99569** and Spearman **0.99912** against GeoDAWN `TC` (`geodawn_rad_u8` band 4), over the 5,165,840 cells
  that are not the declared nodata sentinel (−3.4028e38; it covers 7,113,320 cells of band 6). Restricted to the 5,164,300
  GeoDAWN-footprint cells: Pearson **0.99714**, Spearman **0.99995**. Without the sentinel mask, Pearson is about 0.886 on the
  full grid and near 0 on the footprint, so the masking must be stated with any Pearson value. Re-read from disk this session.
  H93 does **not** use band 6 in View B. That is a declared deviation from the lane brief, which asks for "any radiometric
  bands present in training_features.tif". See IR-H93-001 and the next-round item in `knowledge/82`.

## 6 · The shipped file (download for audit, not for submission)

| field | value |
|---|---|
| file | `docs/downloads/gems52-h88-cotrain-strict-AB-37654px-20261010T220328Z.tif` (also in `submission/`) |
| ZIP | `docs/downloads/gems52-h88-cotrain-strict-AB-37654px-20261010T220328Z.zip` |
| SHA-256 (TIF) | `794b3814b63cdcd880395f5a632cfe0f3b28642b3fdb337ca0315a4722c0ccdd` |
| SHA-256 (ZIP) | see `evidence/h93_build.json` `zip_sha256` |
| name (≤140 chars) | `h88-cotrain-strict-AB-37654px` |
| note (≤140 chars) | `H93 cotrain A-conf/B-abstain stratum, 3px spacing, 200m collar, zeros outside` |
| dots / values | 37,654 ones, all other pixels 0.0; no NaN; float32; EPSG:32611; 3730 × 3292 |
| validator | `scripts/verify_h88_file.py` → `evidence/h93_validator.json`: **12 of 12 checks PASS** (single band, float32, CRS, shape, transform, all finite, footprint NaN-free, values in [0,1], binary, no mass outside footprint, count = budget, ZIP identical) |
| spacing | placed by `gems52.nodes.spacing_select` at 3 px; 0 fallback dots |
| collar | 0 dots within 2 px (200 m) of the FULL catalogue; minimum distance to a mapped trace 223.6 m (`evidence/h93_union_check.json`, review table) |

### 6a · Uniqueness and lane (protocol §1)

* **Surface, pre-placement** (`gems52.gates.lane_uniqueness_report`, phase surface, over 562 priors = census + local
  globs, byte-deduplicated, 397 distinct decoded): max Spearman **0.2999** (limit 0.90), **0 offenders**. PASS.
* **Dots, final** (`scripts/audit_uniqueness.py` with the census receipt): **DUPLICATE/STOP** (§6b).
* **Not-the-union** (`scripts/h88_review_tables.py`): **93.7 %** of the shipped dots lie outside the union of the
  top-37,654 dots of View A and of View B; 100 % lie in S_AB; Jaccard vs the union 0.0215. The output is not
  the union of the two views.

### 6b · Final-dot lane result — DUPLICATE/STOP (`evidence/h93_uniqueness.json`)

* Decoded-pixel uniqueness is **clean**: 0 identical priors, maximum Jaccard **0.128193** (against the H87 file), 562 priors after
  byte deduplication. The H93 file is not a copy of anything in the registry.
* The **dot-proximity** rule fails. The H93 dots are within 3 px of the H87 raster's dots for **97.46 %** of their positions
  (`lane_policy_dots.policy.max_near_3px_fraction` = 0.974637). Seven further informative census rasters exceed the 70 %
  limit (`informative_near_offenders_over_70pct`). The literal rule, which also counts 14 universal-coverage probes, returns
  DUPLICATE/STOP as well (`literal.verdict`).
* Measured: H87 and H93 both place dots with `nodes.spacing_select` at 3 px and the same budget (37,654)
  (`scripts/build_h87_cotrain_wavelength.py` l.357; `scripts/build_h88_cotrain_strict.py` l.108). They are the same placement
  family. **Inference, not measured this round:** both fields rank View A highly, which is the likely source of the coincidence.
  The H93 placement ablation (spaced vs clumped on H93's own field) was **not run** this round. The H85 instrument ablation is
  in `knowledge/78` §2 (0.072384 spaced vs 0.017201 clumped).
* **Protocol §1 says: log the drift as a duplicate and stop.** The lane was not retuned to clear the gate. A quota or
  alternative placement would be a new experiment with its own pre-registration, and the holdout is negative regardless.

## 7 · A-only geological reasoning (required by the brief, with its limits)

`docs/downloads/h93-a-only-reasoning.csv`: **1,352 clusters** (dots dilated 3 px, 8-connected). Each row has measured ranks
(View A, View B, and the gravity / magnetic / strain group ranks), distance to the nearest mapped trace, distance to the
nearest GDR well or spring, median raw depth to basement, a dominant-channel mechanism, and a named non-fault mimic.
Dominant channel counts (after the View A band fix, from `evidence/h93_review_tables.log`): gravity 370, magnetic 460, strain 522. Every row is marked **UNREVIEWED**. The mechanism text is
a template chosen from the dominant channel. It is not a per-site geological finding and must not be reported as one.
Per-dot prose was not produced (37,654 dots); cluster-level review is the honest unit.

## 8 · Limits

1. One holdout experiment; the verdict is measured, not projected. No organiser receipt exists for this file.
2. The independence test is a proxy (unsupervised scores), not the fitted OOF test. View sufficiency was not refitted.
3. The fold set differs from H82/H84 (60,894 vs 53,186). The bar is a different-instrument reference (IR-H93-002).
4. Band 6 is radiometric by content but is excluded from View B (IR-H93-001). The lane brief asks for it.
5. The external GeoDAWN rasters are USGS/GeoDAWN products restored from owner mirrors under SHA-256 pins; they are not
   re-downloaded from usgs.gov (egress returns 000 from this sandbox).
6. The A-only table is templated. It needs a geologist before any reviewer sees it as an interpretation.
7. The 524-blob prior census was restored through the Git Data API and byte-verified (524/524 file SHA-256 match).
   The fetch log's `decoded_sha_ok=0` is a labelling artefact: the census column stores file bytes, not decoded
   pixels, so decoded comparison is not expected to match (IR-H93-004).

## 9 · Why 0.2778 scored highest, and what this round adds to that answer

The full reading is in `knowledge/78` §1 and `knowledge/76`. **This round did not re-derive `knowledge/78` §1.4.** That arithmetic
is repo-derived and labelled assumption-dependent there. The DTI formula it relies on is repeated from `knowledge/78` §1.2 and
is **not verified** against an official source here: the reference-solution README (the only official page reachable this
session) does not state it. The board attribution of 0.2778 to `h33-2-b2` is owner-reported (IR-H93-006).

What H93 adds: a 3-px thinned lattice is necessary but not sufficient. The H93 field is below random on its own holdout, and
its placement is the same family as H87 (97.46 % of dots within 3 px of H87's dots). Placement alone does not rescue a field
that the holdout already scores below random (`knowledge/78` §2 shows that, for one field on one instrument, spacing moves the
holdout from 0.017201 (clumped top-k) to 0.072384 (spaced).)

## 10 · Sources for manual review (status as observed this session)

Sandbox check, run this session: `curl` returned HTTP 200 for `github.com` and `api.github.com`, and HTTP 000 (no route) for every other host listed below.

* Competition page and data tab: https://www.drivendata.org/competitions/306/competition-doe-gems/ · **000, not fetched**; link from the brief.
* Leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ · **000, not fetched**; repo snapshot `registry/leaderboard_snapshot_2026-10-10.json` is a one-off read.
* GeoDAWN airborne magnetic and radiometric release: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and · **000, not fetched**; DOI 10.5066/P93LGLVQ from the brief.
* INGENIOUS / GDR submission 1391: https://gdr.openei.org/submissions/1391 · **000, not fetched**; CC BY 4.0 per the repository's source notes.
* Blum & Mitchell (1998), co-training: https://doi.org/10.1145/279943.279962 · **000, not fetched**; from the brief.
* EPSG:32611: https://epsg.io/32611 · **000, not fetched**.
* Tversky index: https://en.wikipedia.org/wiki/Tversky_index · **000, not fetched**.
* Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution · **HTTP 200, fetched via `api.github.com/repos/.../readme`** (2,359 characters). It is a setup guide by John Lipor for a U-Net notebook with Monte-Carlo cross-validation (`unet-mc-cv-reference-solution.ipynb`). It contains **no** DTI formula, no submission-format text and no range rule, so it does not verify the metric. The repository's DTI statement (knowledge/78 §1.2) stays unverified against an official source.
