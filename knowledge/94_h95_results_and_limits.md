# 75 — H95: results, the mechanism, and what this round actually settles

Round **H95**, run 2026-10-10 inside the assigned **two-view co-training** lane (Blum & Mitchell, COLT
'98, doi:10.1145/279943.279962). Pre-registration frozen before any fit:
`knowledge/93_hypotheses_H95_preregistered.md`, SHA-256 pinned in
`registry/h95_preregistration.json`; `scripts/run_h95.py` re-hashes that document on every stage and
refuses to fit if it moved.

**Verdict: NEGATIVE. 0 submission slots spent. Download safe, submission not recommended.**

---

## 1. The one-sentence result

A signed, odd-symmetric fault-normal decomposition of the geodetic strain field was built, gated and
measured; **View A came out below chance** (mean out-of-fold AUC 0.48753, worst fold 0.43510), which is
the eighth consecutive failure of View A sufficiency in this lane, so the A-confident/B-abstains primary
arm had nothing to donate and lost to its own control decisively.

## 2. HOLDOUT-DTI

Evaluator `gems52-pooled-hide-v1` · 36,356 withheld positive pixels · 9,400 dots per fold per arm ·
triangular kernel k(d) = max(1 − d/R, 0), R = 300 m = 3 px · α 0.2 / β 0.8 · 1,000 paired
physical-cluster bootstrap draws at 200 px block side · hide-and-recover folds (whole 8-connected
catalogue components withheld, 8 px buffer, prevalence 0.002, seed 84).

| Arm | HOLDOUT-DTI | 95 % CI | Role |
|---|---:|---|---|
| `single_B` | **0.029349** | [0.019308, 0.041468] | the control the frozen rule compares against |
| `union_max` | 0.029290 | [0.019265, 0.041379] | the not-the-union comparator |
| `B_conf_A_abstain` | 0.027022 | [0.018889, 0.037144] | surface-artefact suspects, reported not promoted |
| `random` | 0.016962 | [0.014982, 0.018973] | floor |
| `A_ODD_ungated` | 0.009979 | [0.006233, 0.014322] | model-free odd-dominance composite (attribution) |
| `single_A` | 0.003260 | [0.001366, 0.005454] | View A alone |
| **`A_ODD_gated`** | **0.002757** | [0.001354, 0.004559] | **pre-registered primary** |

All other paired differences, primary minus each arm (positive = primary better):
`single_A` -0.000503 [-0.002045, +0.000845] (indistinguishable) ·
`single_B` -0.026592 [-0.038914, -0.016328] ·
`A_ODD_ungated` -0.007221 [-0.011519, -0.003540] ·
`B_conf_A_abstain` -0.024265 [-0.034594, -0.015641] ·
`union_max` -0.026533 [-0.038861, -0.016276] ·
`random` -0.014205 [-0.016577, -0.011772].

The most informative line is `A_ODD_ungated`: restricting View A's field to where View B abstains
**reduced** it (0.009979 → 0.002757, paired
-0.007221 with an interval entirely below
zero).
The disagreement gate did not select buried faults; it selected the part of View A that was worst. That
is what a below-chance view looks like when you condition it on another view's abstention.

Paired difference, primary minus `single_B`: **-0.026592**, 95 % CI
**[-0.038914, -0.016328]** — entirely below zero.

**Frozen promotion rule:** promote only if that lower bound is above zero. It is -0.038914.
**Not promoted.** Attribution arms are not promotable post hoc.

These are HOLDOUT-DTI numbers. The hide-and-recover instrument does **not** rank leaderboard
performance in this repository (Spearman −0.10 against owner-reported board scores, `knowledge/10` §5),
so none of them is a board forecast, and none is written as one.

**Control comparability, stated plainly:** `single_B` here is *this round's own* View-B learner on
*this round's* 14 surface channels. It is **not** a replay of the committed 0.174517 control, whose
feature bank (the cached structural store plus the external layers) is not reproducible from this
checkout — the same limitation recorded as IR-H82-004. No reproduction claim is made, and the
round-internal comparison is the only one this document uses.

## 3. Out-of-fold AUC, per fold

| Fold | Train pos / neg | Withheld truth px | Proxy negatives | View A | View B |
|---:|---:|---:|---:|---:|---:|
| 0 | 45,932 / 918,640 | 10,332 | 200,000 | 0.48386 | 0.58111 |
| 1 | 32,764 / 655,280 | 10,341 | 200,000 | 0.49740 | 0.57976 |
| 2 | 41,851 / 837,020 | 10,342 | 200,000 | 0.53376 | 0.65360 |
| 3 | 52,543 / 1,050,860 | 5,341 | 200,000 | 0.43512 | 0.60683 |
| **mean** | | **36,356 withheld positives in total** | | **0.48753** | **0.60533** |

Per-fold HOLDOUT-DTI (same order), primary / `single_B` / `random`:
fold 0 0.002775 / 0.033258 / 0.016895 · fold 1 0.005519 / 0.020567 / 0.017438 · fold 2 0.001653 / 0.030263 / 0.017494 · fold 3 0.000000 / 0.035933 / 0.015411.
Fold 3 is an exact zero: on that fold the gated View A field recovered **no** credited mass at all.

Sufficiency bar (inherited, not re-tuned): mean ≥ 0.60, min fold ≥ 0.55. View A: mean 0.48753,
min fold 0.43510 → **FAIL**. Fold 3's 0.4351 is anti-informative, not merely uninformative: on that
fold the signed strain dipole points *away* from withheld catalogue traces.

## 4. Leakage canary — no alarm

Bar: a single-channel out-of-fold AUC ≥ 0.90 is leakage until proven otherwise. Measured maximum over
all 32 channels in all four folds: **0.66534** (fold 2, `B_b19_detrended_elev_slope_h2_oddom`).
Per fold: 0.65189, 0.64203, 0.66534, 0.62208. No alarm — and no channel is near useful either.
The six best single channels across all folds, in order:

| channel | view | best AUC | fold |
|---|---|---:|---:|
| `B_b19_detrended_elev_slope_h2_oddom` | B | 0.66534 | 2 |
| `B_b12_detrended_elev_h2_absodd` | B | 0.66130 | 2 |
| `B_b19_detrended_elev_slope_h2_absodd` | B | 0.65876 | 2 |
| `B_b12_detrended_elev_h2_oddom` | B | 0.65826 | 2 |
| `B_b19_grad` | B | 0.65097 | 0 |
| **`A_b7_shear_h2_absodd`** | **A** | **0.64203** | 1 |

Five of the six best channels in the round are View B, and the best View A channel anywhere is the
**shear-rate odd part** at 0.64203 on one fold. That is the single positive finding about the
mechanism: of the three strain bands, shear rate (band 7) is the only one whose signed fault-normal
decomposition carries out-of-fold information, and it is the `|odd|` statistic rather than the
odd-dominance ratio that carries it. Dilatation rate (band 8) — the band the hypothesis was built
around — is not in the top six at all.

## 5. View independence — passes, and is beside the point

Instrument `gems52.spatial.negative_block_errors` + `independence` on spatial-block out-of-fold errors
of the two views over held-out catalogue-zero **proxy** negatives. Thresholds inherited **verbatim**
from `registry/h74_preregistration.json` (donor rank 0.95, receiver interval [0.35, 0.65], block side
50 px, abandon bar |ρ| > 0.60, minimum 20 blocks) and not re-tuned. See
`evidence/h95_independence.json`.

Measured: **8,788 spatial blocks** (2,197 per fold) over **20,412,932** proxy-negative predictions.
Negative mean squared error: Pearson 0.085067, Spearman 0.025049. Negative false-positive rate:
Pearson 0.035804, Spearman 0.026838. `max_abs_correlation = 0.085067` < 0.60 → `allow_exchange=true`,
with the instrument's own caveat recorded verbatim: *"weak proxy negative-error correlation; not proof
of conditional feature independence"*. This is a **lower** dependence than H82 measured (0.1317), and
for a mundane reason: View A here is close to noise, and noise does not correlate with anything.

Independence passing is necessary, not sufficient. Exchange additionally requires View A to be
*sufficient*, and it failed, so **the pseudo-label exchange was not run** — the eighth consecutive
round in which that is the disposition. H71 already measured that running the exchange anyway *lowered*
the View A out-of-fold AUC (0.5019 → 0.4759), which is exactly the bias amplification the brief warns
about.

## 6. The measurement that matters more than the score

**The hide-and-recover instrument is structurally blind to this hypothesis, and that is a finding about
the instrument, not an excuse for the result.**

H95-A predicts faults that have **no Quaternary surface rupture** — locked, creeping or basin-buried
structures that are absent from the USGS/INGENIOUS catalogue *by construction*. The hide-and-recover
instrument grades recovery of **whole components of the catalogue that were withheld**. Those
components are in the catalogue precisely because a mapper saw them: they have surface expression. So
the instrument asks a detector for buried faults to find faults that are not buried.

This is the same structural mismatch that produces the repository's measured Spearman −0.10 between the
instrument and owner-reported board scores, and it has a second, sharper form here: the organiser's own
problem page states the test set is *"newly identified faults … that are not included in the existing
USGS fault database"*, while `holdout.make_folds(mode="hide")` builds truth **from** that database. The
instrument's positives and the board's positives are, in the limit, disjoint populations.

**Nothing in this document waives the frozen rule on that basis.** The rule was frozen before the fit,
the primary lost to its control with an interval entirely below zero, and the verdict is NEGATIVE. The
point is recorded so that the next round does not read a low hide-and-recover number as evidence
*against* a buried-fault hypothesis, or a high one as evidence *for* it. What the instrument can and
does settle here is narrower and still useful: the signed strain dipole does not re-rank *catalogue-like*
structure better than chance, so it is not a general-purpose View A detector, and it cannot be used as
one.

## 6b. Did the emission actually select the named signature? No — and that qualifies the verdict

Measured from the 37,654-row per-cell export (`evidence/h95_reasoning.json →
signature_diagnostic`), not asserted:

| Band carrying the largest \|odd\| response | Emitted cells | Share |
|---|---:|---:|
| `isostatic_gravity_b13_h2` | 25,583 | 67.94 % |
| `dilatation_rate_b8_h2` | 3,810 | 10.12 % |
| `second_invariant_b4_h2` | 3,501 | 9.30 % |
| `isostatic_gravity_hg_b18_h2` | 2,899 | 7.70 % |
| `shear_rate_b7_h2` | 1,861 | 4.94 % |

* **Strain-band dominant: 9,172 cells (24.36 %). Gravity-band dominant: 28,482 (75.64 %).**
* **An actual sign-reversal couple is present on only 2,814 cells (7.54 %).**
* Mean odd-dominance: median **0.01251**, 95th percentile 0.07293 — most emitted cells are
  **even-dominant monotone steps**, i.e. the opposite of the antisymmetric couple the hypothesis named.
* The gate itself worked exactly as designed: `b_abstains` is true on **all 37,654** rows.

**Reading, and it cuts both ways.** A linear blend of `|odd|`, odd-dominance and couple lets the
largest-*magnitude* channel decide, and on this grid that is isostatic gravity, not strain. So the arm
that was frozen as primary tested "large fault-normal gradient", predominantly in a gravity band, far
more than it tested "antisymmetric strain couple". The NEGATIVE verdict stands exactly as frozen — the
rule was fixed before the fit and is not waivable after it — but **this arm does not cleanly refute the
hypothesis**, and claiming that it did would overstate the result. The clean test is stated in
`evidence/h95_reasoning.json`: gate on the couple directly (sign reversal at *both* lags, plus
odd-dominance above a quantile frozen before the fit) instead of letting a logistic model weight
`|odd|` against it. This is a design defect in the arm, found by measuring the arm's own output, and it
is the single most useful thing H95 leaves behind.

## 7. The direction field cross-validates against an independent round

The structure tensor's dominant gradient direction is the fault **normal**; the trace strike is that
plus 90°. Measured per fold from each fold's own visible catalogue:

| Fold | Normal (compass) | Derived strike | Resultant R | Axial circ. SD | Coherence median | Coherent px | Regional fallback |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 77.3° | 167.3° | 0.3044 | 88.4° | 0.9108 | 1,490,754 | **87.9 %** |
| 1 | 74.5° | 164.5° | 0.3525 | 82.7° | 0.9098 | 1,094,158 | **91.1 %** |
| 2 | 76.6° | 166.6° | 0.2633 | 93.6° | 0.8996 | 1,364,734 | **88.9 %** |
| 3 | 80.3° | 170.3° | 0.3020 | 88.7° | 0.9047 | 1,678,270 | **86.3 %** |

Emission-time field (whole visible catalogue): normal 77.3°, strike 167.3°, R 0.3020,
1,867,434 coherent px, **84.8 %** regional fallback.

H82 measured the regional strike at **166.7–171.8°** compass with a completely separate
structure-tensor implementation (`knowledge/73` §5). The two agree fold by fold. That is a genuine
cross-validation of both direction fields, and it is the one unambiguously positive result of this
round.

It also names the round's most serious design limitation, and it is worse than the pre-registration
anticipated: R is only 0.26–0.35, the axial circular SD is 82.7–93.6° (barely better than uniform),
and **84.8–91.1 % of pixels take the regional fallback**, because the coherent-corridor gate
(`support > 0.05`, `coherence > 0.2`, `corridor > 0.01`) is satisfied only near visible traces. Note
the apparent paradox: the coherence *median over coherent pixels* is ~0.90, i.e. where the tensor is
non-degenerate it is strongly oriented — there are just very few such pixels. Off-corridor the odd/even
split is therefore a **fixed-direction filter at ~77°**, not a local measurement. In a province whose
visible fabric is genuinely multi-directional (R ≈ 0.30 says so), applying one regional normal to ~88 %
of the grid is close to the wrong operator for most pixels, and that is a plausible mechanical reason
the View A field came out at chance rather than merely weak. It is disclosed as a design defect, not
presented as a local measurement, and §11 item 3 is the fix.

## 8. What was built

32 learner channels over the 5,164,300 px valid footprint, computed on demand at arbitrary
coordinates by bilinear interpolation (no full-grid channel bank, so peak memory stays near 1.1 GB):

* **18 View A channels** — for bands 8 (dilatation rate), 7 (shear rate), 4 (second invariant) at
  lags h ∈ {1, 2} px (band 8 only at both lags; 7 and 4 at h = 2), and the cross-family controls
  13 (isostatic gravity anomaly) and 18 (its horizontal gradient) at h = 2: `|odd|`, odd-dominance
  `odd²/(|odd|+|even|+ε)`, and the sign-reversal couple `min(|B+|,|B−|)·1[sign differs]`, where
  `odd = (B(+h)−B(−h))/2` and `even = (B(+h)+B(−h))/2` sampled at ±h·n̂ on the σ = 3 px
  support-normalised smoothed band.
* **14 View B channels** — the same odd/even/couple triple at h = 2 for bands 12 (detrended elevation),
  19 (its slope) and 6 (aeroradiometric total count), plus five local morphology channels:
  5×5 relief of band 12, its Laplacian, |∇| of bands 12 and 19, and the 5×5 local standard deviation
  of band 6.
* **Learners** — `LogisticRegression(C=1.0, max_iter=2000)` per view per fold on standardised
  channels, trained on `fold['fit']` positives (visible catalogue) against 20× as many non-catalogue
  negatives. A linear model was chosen deliberately: with a below-chance view the question is whether
  the *operator* carries signal, and a high-capacity model would confound that with fitting noise.

## 9. Placement, and the container decision

37,654 cells emitted (full budget, **short-fill 0**) at 3 px minimum separation
(`gems52.nodes.spacing_select`) from the eligible pool of 4,859,987 px, with a 200 m catalogue ring
excluded. Values exactly {0, 1}. Measured distance to the mapped catalogue: minimum **223.6 m**,
5th percentile 300.0 m, median 1,923.5 m, **0.000 %** within 200 m, **5.543 %** within the metric's
300 m kernel. Not-the-union at equal budget (37,654 cells each): shared with `union_max` **1,421**
(Jaccard 0.01923), with `single_A` **11,145** (Jaccard 0.17370), with `single_B` **0**
(Jaccard 0.00000) — the primary shares *no cell at all* with View B's own top-37,654, because it is
gated to where B abstains. **PASS.**

**Lane uniqueness**, against a census of **79 byte-distinct aligned rasters** (`data/scored`,
`data/reference`, `submission/`, `docs/downloads/`, deduplicated by (size, SHA-256), excluding this
round's own output):

| phase | tier | max Spearman | max near-3px | verdict |
|---|---|---:|---:|---|
| surface (before placement) | literal | 0.022438 | — | **PASS** |
| surface (before placement) | policy | 0.022438 | — | **PASS** |
| final dots (after placement) | literal | 0.020777 | **0.998964** | **DUPLICATE/STOP** |
| final dots (after placement) | policy | 0.020777 | 0.348940 | **PASS** |

The literal final-dot stop is **not waived**, and its single witness is named:
`data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, a spacing-5 square lattice. That is a
*universal-coverage probe* — its maximum interior distance is √8 = 2.83 px, so its 3 px halo covers
essentially every eligible pixel and the directed near-3px statistic is ≈1.0 for **every** nonempty
candidate, which is a property of the registry and not of this file. The policy tier, which measures
coverage per prior and excludes probes, gives max near-3px **0.348940** against
`submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif` — a round merged to main
*while this one ran* — still far under the 0.70 bar. Both tiers are published side by side; the literal
stop still counts, so `submit_ok` is false on two independent grounds
(`promoted=False` and `lane_literal_stop=True`, recorded verbatim in `submit_ok_reason`).

The census scope is **narrower than earlier rounds'** (H74S scanned 693 paths, H82 567 rasters, both
including sibling public owner-mirror paths refreshed over the network). This session's census is
local-checkout-only and that is disclosed in the receipt rather than presented as exhaustive.

**The lane stage was run twice, and the second run is the authoritative one.** The first ran against a
66-raster census before `origin/main` was merged; the merge brought in rounds H85–H94 from parallel
sessions, growing the census to 79. A receipt taken before a merge is scoped to a stale census — that is
exactly the H74S lesson (`knowledge/75` of that round: *"re-scan `origin/main` before trusting any lane
receipt"*). Re-running changed the surface max Spearman from 0.022457 to
0.022438 and the dots max Spearman from 0.008733 to 0.020777; **no verdict changed**, and the near-3px
witness is the same universal-coverage lattice in both runs. The exclusion of this round's own output
from the census is recorded in the receipt as `census_excludes_this_round`, because without it the
candidate is compared against itself and returns Spearman 1.0 (§10b item 2).

**Container, chosen on evidence:** all-finite float32 with zeros outside the footprint, tiled/deflate,
no nodata tag. Measured this session from the restored bytes: of the 13 owner-scored and reference
rasters, **11** are stripped/LZW with `nodata=nan` and 7,111,787 NaN outside the footprint, and **2**
are all-finite with zeros outside — one of which is `h33-2-b2-zeros.tif`, the OWNER-REPORTED 0.2778
file. Both containers have therefore been accepted by the portal, so the container alone cannot be the
whole explanation for a *"Predicted values must be in range [0, 1]"* rejection. But the all-finite
container cannot trip that rule under **any** reader, NaN-honouring or not, so it removes an unknown
instead of guessing at the portal's parser. The file's container is compared field by field against the
0.2778 reference in `evidence/h95_write.json → container_vs_0p2778_reference`.

A second measured detail that matters for the range rule: the organiser's footprint
(`labels != −1`, 5,167,373 px) is **1,533 px larger** than the intersection of all 19 feature bands
being finite (5,165,840 px). A submission has to be finite on those 1,533 px too, and this round
writes 0.0 there rather than NaN.

## 10. Limits — what this round cannot tell you

1. **It cannot tell you what this file would score on the board.** It has no organiser number and no
   projection is offered. `knowledge/49`'s algebra bounds what a *novel* field can be expected to
   reach, and that bound is below the 0.2778 champion; the shortfall is the price of the lane's
   uniqueness rule.
2. **It cannot certify anything that depends on replaying a prior round.** The cached structural store
   and the external layers were not rebuilt here, so `single_B` is round-internal (see §2).
3. **The three external uint8 rasters were deliberately not used.** `lidar_scarp_features_u8`,
   `geodawn_rad_u8` and `geodawn_extensions_u8` carry **no band descriptions at all** — 12, 4 and 4
   unlabelled uint8 layers. Their channels cannot be audited against any source, so building a detector
   on them would put unauditable inputs under a number. Flagged, not used.
4. **The A-only stratum reasoning table is per emitted cell, not per pseudo-labelled segment.** The
   exchange was not run, so there is no A-only stratum. `docs/downloads/h95-a-only-reasoning.csv`
   carries row, column, easting, northing, both view scores, B-abstention flag, catalogue distance,
   fault-normal bearing, dominant strain band, mean odd-dominance, sign-reversal couple, the
   interpreted mechanism, the named non-fault mimic, an explicit falsifier, and an evidence class that
   says *model evidence for a Phase-2 reviewer target, NOT an organiser-confirmed fault*.
5. **The independence test uses proxy negatives.** "Catalogue-zero" is not verified absence; a real but
   unmapped fault inside a negative block inflates both views' errors together and would *increase* the
   measured correlation, so the measured |ρ| is if anything an over-estimate of the dependence.
6. **The lane census is not organiser-authenticated.** It is every aligned raster this session can see,
   deduplicated by (size, SHA-256); private or unlinked artefacts are outside its scope.
7. **Three experiments of the three-experiment budget were used** (channels/canary/fit; independence +
   matched holdout; build/lane/write/reasoning/card).

## 10b. Three defects this round found in its own code, and how each was handled

All three were caught by a fail-closed check rather than by a wrong number reaching a receipt, and all
three were fixed once in the runner rather than worked around.

1. **`save_verified` rejected correct NaN-bearing grids** (IR-H95-006). The out-of-fold grids are
   deliberately NaN off the evaluation region; `np.array_equal` reports NaN ≠ NaN, so every correct
   write looked like corruption and the stage fail-closed on fold 0. Fixed with `equal_nan=True`, and
   the receipt now records the NaN count so the deliberate NaNs are visible instead of hidden inside a
   comparison. The stage was re-run from scratch; no number in this round came from the defective
   comparison.
2. **The lane census compared the candidate against itself.** The write stage puts the TIFF into
   `submission/` and the publisher copies it to `docs/downloads/`, so re-running `lane` after `write`
   included the round's own output as prior #67 and returned Spearman **1.0000** and near-3px **1.0** —
   a self-inflicted DUPLICATE/STOP that would have been indistinguishable in the receipt from a real
   one. Fixed by excluding this round's artefacts from the census and recording the exclusion in the
   receipt (`census_excludes_this_round`), with the before/after numbers stated here so the correction
   is auditable.
3. **The card read `duplicate` where the shared gate returns `verdict`.** `gates.lane_report` puts its
   per-tier result in `literal["verdict"]` / `policy["verdict"]`; reading `.get("duplicate")` returned
   `None` for every tier, so a literal STOP would have silently read as no stop. Nothing was
   mis-reported as a result — `submit_ok` was already false via the promotion gate — but the field was
   wrong, and `submit_ok` is now derived from both tiers plus an explicit `submit_ok_reason` string
   (`promoted=False, not_the_union_ok=True, lane_literal_stop=True, lane_policy_stop=False`).

4. **A reproducibility discrepancy that is recorded, not explained** (IR-H95-010). The first execution
   of the holdout stage returned a pooled `single_B` of 0.030262; two consecutive re-runs of the same
   seeded stage returned **0.029349 bit-identically** (max absolute difference 0.0 across all 28
   arm-by-fold values and all pooled values), while the input files were demonstrably unchanged — the
   out-of-fold grids' mtimes and the SHA-256 recorded by the fit stage both predate all three runs. The
   **mechanism is unresolved.** Rather than invent one, the stage now writes `input_sha256` for every
   file it consumes plus a `reproducibility` block into `evidence/h95_holdout.json`, so a future
   discrepancy can be attributed to an input or to the stage. Every number published for H95 comes from
   the reproducible pair; the first run's numbers are superseded and appear nowhere else. Impact: the
   shift is ~0.0009 on the control and ~0.0012 on the paired delta, against a primary that sits below
   *random placement* by 0.0127 — no verdict depends on it.

A fourth defect was found in the **pre-registration transcription**, not the code: the inherited
threshold block omitted `receiver_rank_interval` and three other keys, and the independence stage
raised `KeyError` on the first one. They were copied verbatim from `registry/h74_preregistration.json`
**before** the stage was re-run, and the edit is recorded inside the pin itself
(`thresholds_completion_note`, IR-H95-005). The abandon bar, donor rank, block side and minimum block
count were already pinned and were not touched.

## 11. What H95 leaves for the next round

1. **The shear-rate odd part is the only View A channel with any out-of-fold signal** (`A_b7_shear_h2_absodd`,
   0.64203 on fold 1). If a View A detector is ever going to work in this lane, it starts there, not
   with dilatation.
2. **Fix the instrument before fixing the detector.** A holdout whose positives are drawn from the
   catalogue cannot grade a hypothesis about faults the catalogue misses. The cheapest honest
   improvement is a *tip/truncation* instrument (`holdout.make_folds(mode="tip")`, already in the shared
   template and documented as the one that can see near-trace mass) plus an explicit statement that no
   available instrument measures off-catalogue discovery. Until then, hide-and-recover results should be
   read as *rankings among catalogue-like detectors only*.
3. **Gate on the couple, do not let a linear model choose it** (§6b). This is the highest-value next
   step and it costs almost nothing: the channels already exist, the measurement already shows that the
   frozen arm was dominated by a gravity `|odd|` channel, and a direct `sign-reversal at both lags AND
   odd-dominance above a pre-frozen quantile` gate is a two-line change that tests the hypothesis the
   pre-registration actually states.
4. **A local fault normal that is not borrowed from the catalogue corridor.** 84.8–91.1 % of pixels
   took the regional fallback (§7), so the operator was mostly a single fixed-direction filter. The
   fix is to estimate the normal from a tensor on the *strain field itself* — or on band 19, which is
   dense everywhere — rather than on a dilated corridor of visible traces, and to use continuous
   sub-pixel directions instead of one regional value. Until that is done, no conclusion about the
   odd-symmetric mechanism itself is safe: this round tested the mechanism **under a direction field
   that was regional for ~88 % of pixels**, and that confound is not separable from the result.
5. **The blocked lever is unchanged and remains the only one with measured headroom:** a native-
   resolution reduction of the competition's `1m_DEM_links.csv` tiles (USGS 3DEP, public domain). Not
   obtainable from this sandbox — bash egress is limited to github.com, codeload, api.github.com,
   pypi.org and files.pythonhosted.org, and the data tab is login-walled.

## 11b. Rename record — this round was executed as H84 and renamed H95 at merge

`origin/main` already held a **different** H84 round from a parallel session — an elliptical
spatial-covariance anisotropy detector, `gems52-h84-hva-ellipse-B-37654px-20261010T204630Z` — plus
rounds H85 through H94. The merge conflicted add/add on 15 `h84` paths including both landing pages,
`docs/downloads/h84-candidate.tif`, `evidence/h84_run_card.json`,
`registry/h84_preregistration.json`, `knowledge/74` and both runners. Every colliding path was resolved
in **main's** favour so the parallel round survives intact, and this round was then renamed to **H95**,
the next free identifier, following the IR-H71-005 / IR-H74-002 / IR-H82-008 precedent (IR-H95-011).

The rename is **identifier-only, and that is provable rather than asserted**:

* The GeoTIFF is **byte-identical** before and after — SHA-256
  `c122a9ff37abf5512bbddf39c9d55c60effb2229ed992d959e357ffb804a50f3`, 132,513 bytes, both times —
  because a TIFF does not store its own filename. Only the ZIP's SHA-256 changed
  (`9ea3e5dcc45d231d0138e2a9bb21a8dadd8e252aa009ecf631607ff65cd6cda5`), because a ZIP stores its inner
  member's filename. The submission name and note live in the sidecar JSON and on the site, never in
  the raster bytes.
* The frozen pre-registration's own SHA-256 is preserved as `pre_rename_sha256`
  `ae86107fb0c760ac1604a0011bf11884186e4d9496ac04fce7472bf327767c12` (14,407 bytes) beside the
  post-rename hash `cbefd703a9a0c0893b133c4a4768b2e8f2e8cb9dd03be980b09c4326bbe31a57` — the same byte
  count, because `H84`→`H95` is length-preserving — so the frozen text is still tied to the executed
  run. Full record: `evidence/h95_rename_record.json`.
* The stages whose numbers were **moved, not recomputed**: setup, channels, fit, holdout, independence,
  build. The stages **re-run** after the rename: write (re-stamps the filename and note), lane (the
  census grew from 66 to 79 rasters, so it had to be re-run), reasoning and card.
* Executed-as-H84 artefacts remain recoverable from this branch's own commit `f963831`.

## 12. Reproduce

```bash
python3 scripts/restore_data.py --target-dir data          # 23/23 SHA-256 pins, ~7 min, ALL_VERIFIED=True
python scripts/run_h95.py setup                            # ~2.5 min, measures grid + footprint
python scripts/run_h95.py channels                         # ~1.2 min, smoothed bands + per-fold normals
python scripts/run_h95.py fit                              # ~2.1 min, canary + OOF AUC + OOF grids
python scripts/run_h95.py holdout independence             # ~2.5 min
python scripts/run_h95.py build                            # ~1 min, placement + not-the-union
python scripts/run_h95.py write reasoning                  # ~5 s
python scripts/run_h95.py lane card                        # ~1.5 min for 66 rasters x 2 phases
python scripts/h95_irregularities.py                       # 9 entries, appended to the register
python scripts/publish_h95_site.py                         # site + MANIFEST + README block
python scripts/check_site.py                               # 0 problems
python -m pytest -q                                        # 502 passed, 6 skipped
```

Machine: 2 vCPU, 3.9 GB RAM, peak RSS ~1.4 GB. Wall clock for the whole round after the data restore:
about 13 minutes of compute across the stages above. Three experiments of the three-experiment budget
were used.
