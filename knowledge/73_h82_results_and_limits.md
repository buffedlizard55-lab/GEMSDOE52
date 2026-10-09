# 68 — H82: results, attribution, and limits

Round **H82** — extended directional variogram anisotropy (DVA-2) plus variogram/strike alignment (VSA),
run inside the assigned **co-training lane** (View A subsurface/geophysical vs View B surface, Blum &
Mitchell 1998, doi:10.1145/279943.279962).

Frozen before any fit: `knowledge/72_hypotheses_H82_preregistered.md`
(SHA-256 `fe7050eb40ecf23ff717514ac5067cbc7d45cfa1f844c6d12fa0ee85d6b3b571`, pinned in
`registry/h82_preregistration.json`, amendment 72a included).

**Verdict: NEGATIVE. 0 submission slots spent. Download safe, submission not recommended.**

---

## 1. The one-sentence result

The pre-registered primary arm lost to its own control with a 95% CI entirely below zero; the attribution
arms show the 8-direction fan extension **helps** and the strike-alignment channels **hurt**, so the
combination that was frozen as primary was the wrong combination.

## 2. HOLDOUT-DTI (the only score this repository can compute for itself)

Evaluator `gems52-pooled-hide-v1` · 53,186 withheld positive pixels · 9,400 dots per fold per arm ·
triangular kernel k(d) = max(1 − d/R, 0), R = 300 m = 3 px · α = 0.2, β = 0.8 · 1,000 paired
physical-cluster bootstrap draws (block side 200 px) · label-blind quadrant folds
(`label-blind-quadrants-v2`), 80 px buffer, zero shared components between training domain and evaluation
region.

| Arm | HOLDOUT-DTI | 95% CI | Role |
|---|---|---|---|
| `B_DVA2` | **0.189200** | [0.167891, 0.209115] | attribution — best number this repository has measured |
| `B_DVA` | 0.187587 | [0.166508, 0.209203] | H75 control (re-implemented here) |
| `single_B` | 0.174910 | [0.152922, 0.196038] | control the promotion rule compares against |
| `B_DVA2_VSA` | 0.150591 | [0.131262, 0.169201] | **pre-registered primary** |
| `B_VSA` | 0.142148 | [0.124400, 0.159982] | attribution |
| `random` | 0.080426 | [0.070223, 0.090973] | floor |
| `single_A` | 0.073062 | [0.057798, 0.088877] | View A alone — below random |

Paired differences, primary minus each arm (positive = primary better):

| Comparison | Δ | 95% CI | Reads as |
|---|---|---|---|
| − `single_B` | **−0.024319** | [−0.039025, −0.006869] | significantly **worse** than the control |
| − `B_DVA` | −0.036996 | [−0.050647, −0.022254] | significantly worse than the H75 control |
| − `B_DVA2` | −0.038609 | [−0.050793, −0.024754] | significantly worse than its own fan-only variant |
| − `B_VSA` | +0.008443 | [−0.001972, +0.021122] | indistinguishable from VSA alone |
| − `single_A` | +0.077529 | [+0.057553, +0.095452] | far better than View A alone |
| − `random` | +0.070165 | [+0.054822, +0.085891] | far better than random placement |

**Frozen promotion rule:** promote only if the primary's paired CI lower bound against `single_B` is above
zero. It is −0.039025. **Not promoted. No attribution arm may be promoted post hoc**
(`registry/h82_preregistration.json → attribution_arms_not_promotable`), so `B_DVA2`'s 0.189200 is
recorded as a *finding*, not as a submission.

These are HOLDOUT-DTI numbers. In this repository the hide-and-recover instrument does **not** rank
leaderboard performance (Spearman −0.10 over R4, `knowledge/10` §5), so none of them is a board forecast.

## 3. Out-of-quadrant AUC — the same ordering in all four folds

| Arm | fold 0 | fold 1 | fold 2 | fold 3 | mean |
|---|---|---|---|---|---|
| `B_DVA2` | 0.6849 | 0.7855 | 0.6493 | 0.7297 | **0.7124** |
| `B_DVA` | 0.6820 | 0.7820 | 0.6443 | 0.7118 | 0.7050 |
| `single_B` | 0.6607 | 0.7682 | 0.6143 | 0.6962 | 0.6849 |
| `B_DVA2_VSA` | 0.6462 | 0.7287 | 0.6295 | 0.6836 | 0.6720 |
| `B_VSA` | 0.6362 | 0.7374 | 0.6061 | 0.6248 | 0.6511 |
| `single_A` | 0.5062 | 0.6072 | 0.4309 | 0.5008 | **0.5113** |

`B_DVA2` beats `B_DVA` in 4/4 folds and `single_B` in 4/4 folds. `single_A` fails the sufficiency gate
(mean ≥ 0.60, min fold ≥ 0.55) for the **seventh** consecutive time; fold 2's 0.4309 is anti-informative.

## 4. Why VSA hurt — two measured mechanisms, not a guess

1. **θ_max is quantised by the fan.** θ_max is an argmax over 8 discrete integer directions, so
   cos(2·(θ_max − ψ_reg − π/2)) against a *scalar* regional strike takes only **4 distinct values**.
   Measured on a 1-in-37 subsample of `VSA_det_elev_cos2reg_l2`: histogram over [−1,1] in 5 bins is
   [0.1919, 0.2116, **0.0000**, 0.2746, 0.3218] — the middle bin is empty, i.e. four spikes. The channel
   is a categorical recoding of "which fan direction won", not a continuous alignment, and it carries far
   less entropy than the 50 float channels it is pooled with.
2. **The local variant is mostly a null indicator.** `VSA_*_cos2loc` is exactly 0 wherever the local
   structure tensor is degenerate, which is **69.9% / 53.6% / 46.7% / 47.8%** of eligible pixels by fold
   (`degenerate_tensor_px_eligible` in `evidence/h82_channels.json`). On a 1-in-37 subsample of
   `VSA_det_elev_cos2loc_l2`, 69.85% of values are exactly 0.

Both were frozen design consequences, discovered by measurement after the fit. Neither was visible from
the hypothesis text. **H77 candidates that follow directly:** a 16- or 32-direction fan, and a continuous
sub-pixel θ_max (parabolic interpolation across the fan, or a proper structure tensor on the γ field) so
the alignment channel is continuous rather than 4-valued.

## 5. The measured strike field — the assumption the hypothesis got wrong

The frozen text said "regional Basin-and-Range fabric". Measured from each fold's **own visible** catalogue
(structure-tensor axial resultant over a 7×7-dilated corridor):

| Fold | Regional strike (compass) | Resultant R | Axial circular SD | Corridor px |
|---|---|---|---|---|
| 0 | 169.73° | 0.3708 | 80.7° | 241,871 |
| 1 | 171.82° | 0.3669 | 81.1° | 392,124 |
| 2 | 166.72° | 0.4529 | 72.1° | 434,494 |
| 3 | 167.19° | 0.3782 | 79.9° | 425,661 |

The fabric here is **N10°W–SSE (≈167–172° compass)**, not the classic NNE trend of the central Basin and
Range, and R is only 0.37–0.45 with a circular SD of 72–81° — the visible catalogue is genuinely
multi-directional, so a *scalar* regional strike is a weak summary. That is a second reason the regional
alignment channel under-delivers, and it is why the local strike field was a separate channel. Circular SD
is the Mardia–Jupp axial form √(−2 ln R); it is undefined as R → 0, and the receipt records `null` in that
case rather than printing a number.

## 6. Leakage canary — no alarm

Bar: a single-channel direction-insensitive AUC ≥ 0.90 on the held-out region is treated as leakage until
proven otherwise. Measured maximum over all **60 new learner channels** in all four folds: **0.6235**
(fold 2, `DVAH75_det_elev_slope_logvar_l4`). Per fold: 0.5666, 0.6235, 0.6235, 0.6010. No alarm.

Amendment 72a was applied **before any fit**: `XVSA_visible_tensor_mag` was demoted from a learner channel
to a diagnostic because it is monotone in distance-to-visible-catalogue and would have tripped the canary
by construction rather than by discovery. It never entered a model.

## 7. View independence — the lane's mandated test, measured

Instrument `gems52.spatial.independence` on spatial-block out-of-fold errors of the two views over
held-out catalogue-zero proxies. Thresholds inherited **verbatim** from
`registry/h74_preregistration.json` (donor rank 0.95, block side 50 px, abandon bar |ρ| > 0.60, minimum 20
blocks, negative ring 4 px) and **not re-tuned for H82**; the H82 pin was not edited after the fact, and the
inheritance is recorded with the source file's own SHA-256.

| Statistic | n | Pearson | Spearman |
|---|---|---|---|
| Negative mean squared error | 2,089 blocks | 0.061386 | 0.068150 |
| Negative false-positive rate | 2,089 blocks | 0.094542 | **0.131671** |

2,089 blocks over 4,095,103 negative predictions; per fold 978 / 559 / 221 / 331 blocks.
`max_abs_correlation = 0.1317` < 0.60 → `allow_exchange = true`, with the instrument's own caveat recorded:
*"weak proxy negative-error correlation; not proof of conditional feature independence"*, and the negative
class is *"held-out catalogue-zero proxies, not verified absence"*.

**Pseudo-label exchange was still not run.** Independence passing is necessary, not sufficient: View A must
also be *sufficient* for exchange to have anything to donate, and it failed again (§3). H71 already measured
that exchange **lowered** the A2 out-of-fold AUC (0.5019 → 0.4759), which is precisely the bias
amplification the brief warns about. This is the documented standing deviation, re-measured rather than
cited.

## 8. Placement

37,654 emitted cells at 3 px minimum separation from a pool of 4,325,298 px (eligible 4,593,171 minus a
200 m catalogue ring). Minimum distance from any emitted cell to the mapped catalogue **223.6 m**, median
**1,562.0 m**, and **10.80%** of emitted cells lie within the metric's 300 m kernel radius of a mapped
trace. Values are exactly {0, 1}: the distance-weighted Tversky metric is linear in p, so the optimum is a
corner. Marginal rule at a board DTI of 0.2778 (OWNER-REPORTED): emit only within **2.24 px = 224 m**
(`knowledge/49` §2) — the measured minimum of 223.6 m sits essentially on that boundary, which is the ring
cut doing its job.

## 9. Not-the-union test (the brief's explicit requirement)

The emission is compared against the union-max of the two single-view fields and against each single view
at the same budget. Results are in `evidence/h82_build.json → not_the_union`, and the run card carries the
Jaccard and shared-cell counts. Equal-budget comparison is the point: all four placements emit 37,654
cells, so a shared-cell count is directly interpretable as an overlap fraction rather than a budget
artefact.

## 10. What was built

79 flat eligible-indexed columns (4,593,171 float32 each, 1.4 GB total in `work/h82/features`, git-ignored):

* **50 DVA-2 learner channels** — `aniso = (max γ − min γ)/(max γ + min γ + 1e−9)` and
  `logvar = log10(mean γ + 1e−9)` over 8 integer directions (GROUP1 `(0,h)(h,h)(h,0)(h,−h)` = H75's fan,
  GROUP2 `(h,2h)(2h,h)(2h,−h)(h,−2h)`) at lags h ∈ {1,2,3,4,6} px (100–600 m), on bands 12 `det_elev`,
  19 `det_elev_slope`, 13 `iso_grav_anom`, 15 `depth_to_base_surf`, 18 `iso_grav_anom_hg`. γ is divided by
  the exact offset length `hypot(dy,dx)/h`, which is what makes H75's 12 channels recoverable as a subset
  and `B_DVA` a genuine control. Gaussian smoothing σ = 3 px, edge weight normalised by the smoothed
  support mask.
* **10 VSA learner channels** — 5 bands × {`cos2reg`, `cos2loc`} at lag 2 px.
* **12 H75 control channels** — GROUP1 at H75's lags, so `B_DVA` reproduces the committed arm.
* **7 diagnostics/atoms** — `THMAX_*` (winning azimuth), `PSILOC_f*` (local strike field), `DEG_f*`
  (degenerate-tensor mask), `TMAG_f*` (demoted visible-tensor magnitude).

## 11. Limits — what this round cannot tell you

1. **It cannot tell you what `B_DVA2` would score on the board.** It is the best holdout number measured
   here, it was never pre-registered as a primary, and promoting it now would be exactly the post-hoc
   selection the protocol forbids. It must be pre-registered fresh, before any fit, in the next round.
2. **The H75 control did not reproduce inside tolerance.** `B_DVA` measured 0.187587 against a committed
   0.186352, |Δ| = 1.23e−3 against a 1e−3 tolerance → **FAIL** (IR-H82-004). `single_B` reproduced at
   3.93e−4 → PASS. Two candidate causes cannot be separated on this machine: installed library versions
   exceed the pins (cf. IR-H75-004, 5.4e−5), and `B_DVA` here is a *re-implementation* of H75's channels
   inside `run_h82.py`, not a replay of H75's arrays — H75's `work/` directory no longer exists, so no
   bit-for-bit comparison is possible. Any H82 claim that depends on reproducing H75 exactly is therefore
   **not certified**; claims that depend only on arms fitted inside this round are unaffected.
3. **No organiser number was produced.** This runner has no DrivenData credentials: it has never downloaded
   the competition data from the organiser and has never uploaded a file. Every score here is
   HOLDOUT-DTI, OWNER-REPORTED, or ORGANIZER-CONFIRMED-from-the-public-leaderboard, and is labelled as such.
4. **The drainage-deflection hypothesis was never tested.** `1m_DEM_links.csv` is login-walled and usgs.gov
   is outside this runner's egress allowlist (IR-H82-003). It remains the strongest untested idea in
   `knowledge/72` because offset drainage targets exactly the covered faults the catalogue misses.
5. **The A-only stratum reasoning table is not emitted.** The brief asks for geological reasoning for every
   A-only candidate; because the exchange was not run there is no A-only candidate set. Reasoning is instead
   written for **every emitted cell of the primary arm** (row, column, easting, northing, fold, rank
   percentile, distance to the mapped catalogue, dominant band at 200 m, per-band anisotropy and
   cos2reg, interpreted mechanism, the named non-fault mimic, the falsifier, and an evidence class that
   says *model evidence for a Phase-2 reviewer target, NOT an organiser-confirmed fault*).
6. **The independence test uses proxy negatives.** "Catalogue-zero" is not verified absence; a real but
   unmapped fault inside a negative block inflates both views' errors together and would *increase* the
   measured correlation, so 0.1317 is if anything an over-estimate of the dependence.
7. **One experiment of the three-experiment budget was used**, in about 50 minutes of compute. The budget
   was not exhausted; the round stopped because the frozen primary had a decisive answer.

## 12. Reproduce

```bash
python3 scripts/restore_data.py --target-dir data
PYTHONPATH=src python -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False)"
PYTHONPATH=src python -m gems52.external
python scripts/fetch_prior_inventory.py
python scripts/run_h82.py channels        # 180 s, 79 columns, verified writes
python scripts/run_h82.py fit             # ~7 min, 6 arms x 4 folds, checkpointed
python scripts/run_h82.py holdout         # ~2.5 min
python scripts/run_h82.py independence    # ~10 s
python scripts/run_h82.py build           # ~20 s
python scripts/run_h82.py lane            # ~20 min, 567-raster census x 2 phases
python scripts/run_h82.py write           # ~4 min, raster + validator + reasoning CSV
python scripts/run_h82.py card            # the single JSON run card
python scripts/publish_h82_site.py
python scripts/check_site.py && python -m pytest -q
```

Every `np.save` in the runner goes through `save_verified()`, which re-reads each file and rewrites until it
is bit-exact (IR-H82-002). `Bank.col` refuses to serve a column whose bytes do not match its manifest
digest, so a corrupted channel cannot reach a model silently.
