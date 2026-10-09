# 48 · H67 results and limits (rendered from the receipts by `scripts/publish_h67_site.py`)

**Verdict: `NEGATIVE` — download for research, DO NOT SUBMIT, no weekly slot used.**

Artefact `gems52-h67-thermal-upflow-corridor-24907px-20261009T050704Z.tif`, SHA-256 `14644198f1031e8250a284c86775c55b57d60d55195e815eac6f4d17b01395c6`, 76,217 bytes,
24,907 emitted cells, values exactly {0, 1}, decoded-pixel SHA-256 `969bb11b7403d9c7506ad609084bcdfe6690993cd6dac459cf8de19a913d6d11`.
Reproduced bit-identically by a second independent run.
Pre-registration: `knowledge/45_hypotheses_H67_preregistered.md`, protocol SHA-256 `9fa87ab6ca463693…`,
thresholds and declared deviations frozen in `registry/h67_preregistration.json`.

## 1 · Preflight and footprint integrity

* 23 manifest pins checked, 0 mismatched.
* Labels/features/sample transforms and CRS all match the pinned sample.
* cells: 12,279,160 total, 7,111,787 outside the organiser's domain,
  5,167,373 in domain, **5,164,300 eligible** after excluding
  3,073 in-domain cells that carry the float32 nodata sentinel in at
  least one band (**IR-H67-002**, see §7).
* Three defensible footprints still coexist (IR-H67-003): `labels >= 0` gives 5,167,373,
  band-12-non-sentinel 5,165,840, all-19-band intersection 5,164,300.
  This round uses the intersection.

## 2 · The two lane gates, measured

**S1 two-view sufficiency — FAIL.** View A out-of-quadrant OOF AUC by fold
[0.605, 0.5858, 0.5462, 0.635], mean **0.5930**, minimum
**0.5462**; frozen bar mean ≥ 0.60 and min ≥ 0.55. View B
[0.5873, 0.6644, 0.5792, 0.6489], mean 0.6200.

This is the **highest View A measurement in the repository's history** (H61 0.5163, H63 0.5362,
H64 0.5230, all committed in their own receipts), and it still fails. The gap to View B narrowed from 0.148 (H61) to
0.027 here, which says part of View A's
historical failure was learner/parameterisation, not the layers — but the bar is the bar: **no
pseudo-label exchange was performed**, and the brief's co-training premise is not met in round four.

**S2 conditional independence — did not fire.** 2,283 spatial blocks;
block mean-squared-error Spearman 0.2951
(Pearson 0.2004), block false-positive-rate
Spearman 0.0078. Maximum |correlation|
**0.2951** against the abandonment threshold 0.60.

That contradicts N-19 (0.7625 hide / 0.7107 tip, same data) and agrees with H62 (0.1757). **IR-H67-005:
the S2 statistic is not a stable property of "the two views"** — it spans 0.0078 to 0.7625 across five
rounds depending on feature set, learner and block size. An ABANDON rule keyed to it can be made to
fire or not fire at will, so it cannot serve as a go/no-go gate until all three are frozen together.
Recorded, not smoothed over.

**Leakage canary — CLEAN.** Worst single-channel holdout AUC
**0.6228** (`downface_max`, fold 2) against
the 0.90 alarm. No channel is suspiciously good.

## 3 · HOLDOUT-DTI (evaluator `gems52-pooled-hide-v1`)

60,894 withheld positive pixels, 4 whole-segment hide-and-recover folds,
catalogue-derived quantities recomputed per fold from the VISIBLE catalogue only, visible faults masked
pixel-exactly, α 0.2 / β 0.8, 300 m triangular kernel, 95 % paired physical-cluster bootstrap
(1000 draws). Arms matched on budget within each fold.

| arm | HOLDOUT-DTI | 95 % CI | TPw | FPw | FNw |
|---|---:|---|---:|---:|---:|
| tuc | 0.015432 | [0.010756, 0.021313] | 839.6 | 27,625.1 | 60,054.4 |
| single_A | 0.017751 | [0.008472, 0.029061] | 964.1 | 27,036.4 | 59,929.9 |
| single_B | 0.051302 | [0.038758, 0.064892] | 2,790.6 | 25,611.9 | 58,103.4 |
| union_max | 0.038296 | [0.026750, 0.050117] | 2,082.5 | 26,244.1 | 58,811.5 |
| disagreement | 0.016527 | [0.007150, 0.028052] | 899.5 | 27,645.1 | 59,994.5 |
| random | 0.056623 | [0.051414, 0.061894] | 3,113.1 | 28,206.8 | 57,780.9 |

Best comparable control: **random**. Paired differences (candidate − control):

* tuc − single_A: **-0.002319**, 95 % CI [-0.014365, 0.008834]
* tuc − single_B: **-0.035871**, 95 % CI [-0.049674, -0.023605]
* tuc − union_max: **-0.022864**, 95 % CI [-0.034292, -0.011448]
* tuc − disagreement: **-0.001095**, 95 % CI [-0.013179, 0.010170]
* tuc − random: **-0.041191**, 95 % CI [-0.047743, -0.034102]

Per fold (budget-matched within the fold):

| fold | matched budget | legal seeds | corridor pool | withheld truth px | tuc | single_B | random |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 19,975 | 1,064 | 19,975 | 29,297 | 0.01938 | 0.05667 | 0.07814 |
| 1 | 5,157 | 1,023 | 5,157 | 12,579 | 0.01785 | 0.04742 | 0.03506 |
| 2 | 2,134 | 957 | 2,134 | 9,433 | 0.00483 | 0.04979 | 0.04208 |
| 3 | 2,148 | 960 | 2,148 | 9,585 | 0.00926 | 0.03993 | 0.02721 |

**NEGATIVE, and negative in the strongest available sense: below uniform random.** Two things must be
said together, because either one alone would mislead:

1. The measurement is what it is. The frozen promotion bar was "candidate minus best comparable
   control > 0 with the 95 % CI excluding 0"; it is -0.041191
   with CI [-0.047743, -0.034102]. Not promoted.
2. The instrument cannot score this hypothesis class in either direction. Its truth class *is* the
   mapped catalogue, while H67-A is constructed to lie ≥ 200 m away from every mapped trace; and the
   same instrument ranks the organiser-scored 0.2778 champion at 0.00479, below a random placeholder
   (IR-H60-003; Spearman(board, instrument) = −0.099, n = 13, p = 0.748). Random beating single_B in
   this very table is the same fact seen from inside the round.

So: **do not submit** (the only defensible action given a significantly-negative measurement and no
instrument that can overturn it), and **do not read the negative as evidence that buried thermal
corridors are absent** — this round cannot tell us that either. That is the honest state of knowledge.

## 4 · Gates on the surface and on the final dots

| gate | result |
|---|---|
| Manifest integrity (23 pinned mirrors, SHA-256) | PASS · 23 checked, 0 mismatched |
| Pre-registered protocol hash matches at run time | PASS |
| Format gate: 1 band, float32, EPSG:32611, shape and transform identical to the pinned sample | PASS |
| Finite values in [0, 1] — measured range 0.0…1.0, 0 NaN, 0 infinite | PASS |
| Emitted mass outside the eligible footprint | 0 px |
| Leakage canary: worst single channel AUC on holdout, alarm at 0.90 | 0.6228 (downface_max) — CLEAN |
| S1 two-view sufficiency (mean ≥ 0.60 and min fold ≥ 0.55) | FAIL · View A mean 0.5930, min 0.5462 |
| S2 conditional independence (abandon above 0.60) | exchange allowed · max |Spearman| 0.2951 over 2,283 blocks |
| Lane gate, literal rule, surface / final dots | PASS / DUPLICATE/STOP |
| Lane gate, universal-coverage-probe policy, surface / final dots | PASS / DUPLICATE/STOP |
| Decoded-pattern uniqueness against the prior census | FAIL (identical to a prior) |
| Exact novelty: share of emitted cells positive in none of the informative registry rasters | 0.0000 |
| Not merely the union of the two views (0.0061 of the emission inside the union of matched view top-K fields, bar 0.90) | PASS |
| HOLDOUT-DTI beats the best comparable control (random) | FAIL · 0.015432 vs 0.056623 |
| Bit-identical reproduction by a second independent run | PASS |

Prior corpus: 568 aligned rasters
(372 distinct decoded patterns),
2 read errors, of which
551 are informative and
15 are measured universal-coverage probes
(3 px halo ≥ 95 % of the eligible footprint). Both verdicts are reported; neither replaces the other.
Scope: the supplied aligned immutable public inventory only — private, release-only or unlinked
artefacts are **not proven absent**.

## 5 · Expected score, as a projection and never as a score

For a fully novel field at S = 24,907 with credit density ρ ~ U[0.0279, 0.1387] and |G| = 14,088.7:
DTI = ρS/(0.2S + 0.8|G|) ∈ **[0.0428, 0.2126]**. At |G| = 18,000 → [0.0359, 0.1782]; at |G| = 27,400
→ [0.0258, 0.1284]. Even the optimistic end is below the 0.2778 champion. This was stated **before**
the holdout ran, in `knowledge/45` §1, and the measured holdout is worse than the projection.

## 6 · Why the lane cannot reach 0.3195 — the arithmetic, not the mood

`knowledge/49` derives it from bytes re-measured this session (`scripts/h67_board_algebra.py`):

* `h33-2-b2` (0.2778, 37,654 px) is a **strict subset** of the 0.2600 file (44,090 px); the 6,436
  deleted pixels all lie 100–200 m from a mapped trace, and deleting them raised the score 6.8 %.
* Its credit density is ρ = 0.1387 — 5.0× uniform random. That is the whole content of 0.2778.
* Spearman(mass, board) = −1.0000 over the five owner-reported off-catalogue files (n = 5, p < 1e-4),
  and every step past 37,654 px fails the metric's own marginal rule ΔT/ΔS > 0.2·DTI.
* Required ρ to reach 0.3195: 0.1595 at 37,654 px, 0.0999 at 100,000 px.
  Required ρ to reach 0.3774: 0.1884 at 37,654 px, 0.1180 at 100,000 px.
* The only sub-field with a measured ρ in that range is the 25,517 px credited core P1, exact interval
  ρ ∈ [0.163, 0.205] ⇒ DTI ∈ [0.2546, 0.3190] — **its upper bound is below 0.3195** — and any subset
  of P1 has 100 % of its dots within 3 px of an existing registry raster, so the lane rule forbids it.

**Conclusion for the selector step, stated plainly: within this lane's uniqueness rule no candidate can
be shown to beat 0.2778, let alone 0.3195.** The binding constraint is a ranker whose marginal credit
density stays above ~0.06 out to 60,000–150,000 px; that is a better detector, and seven separate
measurements in this repository say it is not available at 100 m.

## 7 · Irregularities found this round

* **IR-H67-002 (severe, caught before publication).** 3,073
  in-domain cells carry the nodata sentinel −3.4028234663852886e+38 in at least one band (3,061 cells
  across 18 of 19 bands; 3,073 in band 6). `transform.rank01` bins against `lo = −3.4e38`, which
  collapses every rank channel to a near-constant and would have silently produced a
  garbage-but-format-valid submission. Fixed with the template's own
  `grid.footprint_from(bands='all')`.
* **IR-H67-003.** Three defensible footprints coexist (5,167,373 / 5,165,840 /
  5,164,300). Every number in this round is stated against the intersection.
* **IR-H67-004.** Two channels are legitimately zero-inflated (`rank_b10`, `grad_b17`: more than half
  the footprint ties at the physical minimum). A blunt "collapsed channel" guard reports them as
  failures; replaced with a degenerate test (< 10 distinct rank levels, or raw |value| > 1e30 inside
  the eligible set) plus an informational zero-inflation list.
* **IR-H67-005.** The S2 independence statistic spans 0.0078–0.7625 across five rounds on the same
  data (§2). It cannot gate anything until feature set, learner and block size are frozen together.
* **IR-H67-006.** `sample_submission.tif` declares a **NaN** nodata value, so any receipt writer that
  serialises it verbatim produces invalid JSON. Handled by an explicit sanitizer and a
  `nodata_declared_is_nan` field; worth fixing once in the shared template.

## 8 · Limits

* The holdout withholds ≈ 1.18 % of the footprint as truth; the competition truth is ≈ 0.12–0.25 %.
  Prevalence mismatch inflates every arm's denominator effect and is the reason absolute values are
  not comparable across rounds.
* The lane reports are computed against the registry census available on disk at build time.
* No organiser receipt exists for any H67 number. Nothing here is ORGANIZER-CONFIRMED.
* The declared learner is `LogisticRegression(max_iter=800, C=1.0, lbfgs)` on rank channels; the
  splitter is `label-blind-quadrants-v2` with an 80 px buffer. H67's `single_B` is therefore **not**
  comparable to H64's stored 0.174517 — a declared difference, not a control failure (H64's cached
  fold predictions no longer exist in this checkout, so its runner cannot be re-executed).
