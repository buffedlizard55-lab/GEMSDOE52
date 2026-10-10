# 74 · H84 preregistration — continuous directional alignment (CSA) on a 16-direction semivariance fan, inside the two-view co-training lane

**Frozen before any H84 fit, canary, holdout or placement read.** Pinned by
`registry/h84_preregistration.json` (which carries this document's SHA-256 and byte count);
`scripts/run_h84.py` refuses to start if either moves.

Labels used throughout this round, and nowhere relaxed:

* **HOLDOUT-DTI** — `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel), with the number of
  withheld positive pixels and a 95 % paired spatial-block CI. A holdout number is **never** a board
  forecast (measured Spearman −0.10 against owner-reported board scores, `knowledge/10` §5).
* **ORGANIZER-CONFIRMED** — only ever with a copied organizer portal receipt. This repository holds
  **no** organizer receipt for any file; every score quoted from the brief or a sibling site is
  **OWNER-REPORTED / PUBLIC**.
* Inputs are **integrity-pinned, not organizer-authenticated** (`registry/data_manifest.json`,
  23/23 SHA-256 pins).

---

## 0. Lane

The brief's single method paragraph: two views, Blum & Mitchell COLT 1998
(<https://doi.org/10.1145/279943.279962>), disagreement as the discovery signal.

* **View A** — potential-field and subsurface: gravity (5, 11, 13, 15, 18), magnetics (1, 2, 3, 9, 14),
  geodetic strain (4, 7, 8), seismicity (10, 16), conductivity (17), plus the external upward-continued
  TMI `X_mag_TMI_up150`.
* **View B** — surface: detrended elevation (12) and its slope (19), DEM-derived curvature/slope
  transforms from the shared store, plus every radiometric band present in `training_features.tif`
  (band 6 = total count, identity resolved on the bytes, `evidence/h53_band6_identity.json`) and the
  external GeoDAWN K/Th/U and ratio grids.

H84 stays inside that lane: it changes **only the View-B channel family** and re-runs the lane's
mandated machinery (independence test, single-view baselines, hide-and-recover comparison, A-only
geological reasoning, not-the-union test, lane-uniqueness gate).

## 1. The measured defect this round is written to repair

`knowledge/73` §4 measured, on H82's own channels, two implementation defects — not geological
refutations:

1. `θ_max` is an **argmax over 8 discrete fan directions**, so `cos 2(θ_max − ψ)` against a scalar
   strike takes only **4 distinct values** (the middle histogram bin is exactly empty). The channel is
   a categorical recoding of "which fan direction won", not a continuous alignment.
2. The local-tensor variant `cos2loc` is **exactly 0** on 46.7–69.9 % of eligible pixels where the
   tensor is degenerate, so most of that channel is a null indicator pooled with 50 informative floats.

`knowledge/73` §4 names the fixes explicitly: *"a 16- or 32-direction fan, and a continuous sub-pixel
θ_max … so the alignment channel is continuous rather than 4-valued."* H84 implements the 16-direction
fan and a continuous alignment that has **no degenerate-null mode at all**.

**Amendment 74a (2026-10-10T21:10Z, still before any fit, canary or holdout read):** the channel count
in the rank-1 row was written as 60; the executed design is **84** learner channels (7 fields × 3 lags ×
4 statistics: 16-fan anisotropy, 16-fan log-variance, continuous preferred direction, directional
resultant length) plus **18** 8-direction control channels. No hypothesis, threshold, arm, seed,
budget, promotion rule or lane rule changed — only the arithmetic of a count that the design table
below already implied.

## 2. Ranked hypotheses (all new to this repository; each grep-checked)

| Rank | Hypothesis | Layers | Physical signature | Why it should catch a fault the USGS/INGENIOUS catalogue lacks | How it differs from anything implemented here | Cost |
|---|---|---|---|---|---|---|
| **1** | **H84-A · continuous directional alignment + 16-fan anisotropy** | 12, 19, 13, 18, 15 | γ-weighted mean direction of the directional semivariance over a 16-direction fan, and its weighted resultant length *R_dir*; alignment `cos 2(φ_soft − ψ_reg(fold))` derived from the **visible catalogue only** | A damage zone is a property of the *continuous* field, so it is visible where mapping stopped; the discrete argmax discarded exactly the sub-direction information that locates an oblique fault | No round has used a 16-direction fan (`grep -rn "FAN = " scripts/ → only run_h82.py, 8 entries`), no round has used a soft/weighted mean direction (`grep -rn "parabolic\|sub-pixel\|subpixel" scripts/ src/ → 0 hits`), and no round has published a directional resultant of the semivariance fan | medium — 84 new channels (7 fields × 3 lags × 4 statistics) + an 18-channel 8-direction internal control, reuses `run_h82`'s verified writer |
| **2** | **H84-B · radiometric-alteration directional anisotropy** | external `geodawn_extensions_u8.tif` bands 1–2 (Th/K, U/K) | same 16-fan statistics on gamma-ray-spectrometry **ratio** fields | hydrothermal alteration along a conduit is *directional*; the catalogue maps the fault, not the alteration halo, and alteration halos persist where the trace is unmapped | the ratio grids are in View B only as rank/gradient columns (`X_rad_ThK_*`, `X_rad_UK_*`); no variogram statistic has ever been computed on them (`grep -rln "semivari\|variogram" scripts/ → run_h75, run_h82, run_h83 only`) | low once H84-A's machinery exists |
| **3** | **H84-C · B-only disagreement as a *suppression* set** | none new (uses both views' OOF fields) | remove candidate dots where View B is confident **and** View A abstains | the brief's own reading — that cell is where roads, erosion lines and levee crests live; suppressing it should raise the credit density of what remains | H62/H70 scored the B-only cell as a *candidate* set; no round has used it as a **veto** on the emission (`grep -rn "b_only\|B-only" scripts/ → only as scored arms`) | very low — one boolean mask over an existing field |
| **4** | **H84-D · magnetic-gradient directional anisotropy as the View-A donor** | 3 `tmi_hg` (and 6 as a variant) | 16-fan anisotropy of the magnetic horizontal gradient | dike swarms and basement-lineament corridors are not catalogued as faults | `knowledge/69` rank 3 proposed it and it was **never run**; the named mimic (GeoDAWN flight-line direction) is checked first by the leakage canary | low, but expected gain is small: View-A sufficiency has now failed **seven** consecutive rounds |
| **5** | **H84-E · cover-conditioned A-only disagreement, re-tested on the repaired alignment** | 15 + both views | H62-A's cover test with a *continuous* alignment channel instead of the 4-valued one | buried continuation beneath thick cover | H62-A measured 0.93× random with the broken channel; retesting it on the repaired channel is new, and the honest prior is that it stays ≈ random | very low |

Only rank 1 (with rank 2 folded into the same channel build) is executed this round; ranks 3–5 are
recorded as proposals with their own preconditions. **Budget: 3 experiments, 2 hours, 0 submission
slots.**

## 3. Frozen protocol

* Seed `SEED = 84024` (H84's own; the H61/H82 seed is *not* reused so the fold draw is independent).
* Folds: `gems52.spatial.folds` label-blind-quadrants-v2, whole 8-connected catalogue components,
  80 px buffer, 4 folds — the shared instrument, not a fork.
* Negatives for training: catalogue-zero pixels ≥ 500 m from any mapped trace. **Catalogue-zero is not
  verified fault absence.**
* Views fitted per fold on that fold's own visible catalogue only; predictions are made on the fold's
  evaluation region only.
* Leakage canary: every new channel alone, direction-insensitive AUC on the held-out region; alarm
  bar **0.90**. A channel above the bar is dropped from the learner *before any fit* and reported.
* Independence (the lane's mandated premise test): `gems52.spatial.negative_block_errors` +
  `gems52.spatial.independence`, thresholds inherited **verbatim** from
  `registry/h74_preregistration.json` (abandon bar |ρ| > 0.60, block 50 px, donor rank 0.90, min 32
  negatives/block). Not re-tuned for H84.
* Sufficiency gate for View A: mean out-of-quadrant AUC ≥ 0.60 and min fold ≥ 0.55. This is the
  standing Blum–Mitchell premise; it has failed seven times and is re-measured, not assumed.
* Emission: binary {0,1}, 37,654 dots total / 9,400 per fold per arm, 3 px minimum spacing
  (`gems52.nodes.spacing_select`), 200 m catalogue ring excluded, written with
  `gems52.grid.write_geotiff_portal_exact` through `gems52.submission_writer`.
* Holdout: pooled DTI, 1,000 paired physical-block bootstrap draws, block side 200 px.

### Arms (frozen)

| arm | channels | role |
|---|---|---|
| `single_A` | View A store columns | sufficiency + disagreement donor |
| `single_B` | View B store columns | **control the promotion rule compares against** |
| `B_DVA3c` | View B + 8-direction sub-fan aniso/logvar (the even indices of the 16-fan) | attributes the fan-resolution effect; **not promotable** |
| `B_DVA3` | View B + 16-fan aniso/logvar | attributes the finer fan alone |
| `B_CSA` | View B + 16-fan aniso/logvar + continuous alignment + `R_dir` | **primary** |
| `random` | none | floor |

### Promotion rule (frozen)

Promote only if the paired 95 % CI lower bound of (`B_CSA` − `single_B`) is **> 0** on
`gems52-pooled-hide-v1` at 9,400 dots/fold, **and** `single_B` reproduces its committed control
0.174517 within 1e−3 (instrument-integrity check), **and** the leakage canary is clean, **and** the
not-the-union test passes, **and** the lane gate passes. `B_DVA3` and `B_DVA3c` are attribution arms and
are **not promotable post hoc** — the same rule that made H82's best number a finding rather than a
submission.

### Lane registries (frozen)

* **Literal full census**: every grid-aligned raster in `submission/` plus the prior inventory receipt,
  excluding this round's own `gems52-h84-*` artefacts.
* **Restricted scored-only**: `data/scored/*.tif` + `data/reference/h33-2-b2-zeros.tif` (13 files,
  membership rule in `registry/h82_scored_registry.json`).
* Doctrine: a restricted or policy PASS **never** waives a literal full-census DUPLICATE/STOP. Both
  verdicts are reported verbatim.

## 4. Honest expectation, written before the holdout is read

`knowledge/49` §4: at 37,654 emitted px the credit density needed for 0.3195 is ρ ≈ 0.1595 against the
0.2778 champion's measured ρ ≈ 0.1387, and the binding constraint on this family is the ranker's ρ(S)
decay, not the budget. H84's channel family is a *ranker* repair, so the honest bracket is: if the
paired CI clears zero, expect a single-digit-percent relative improvement over `single_B` on the
holdout — the same order as H82's `B_DVA2` (+0.0143 absolute) — and **no** expectation of reaching
0.3195, which needs a detector this repository has measured seven times that it does not have. A
negative result is a deliverable.

## 5. What is *not* claimed

No organizer leaderboard page, portal receipt or private-set information was accessed in this session;
the DrivenData data tab remains login-walled and every raster is an owner-mirror copy verified only
against its own SHA-256 pin. Nothing here is a guaranteed score.
