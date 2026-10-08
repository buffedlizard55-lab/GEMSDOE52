# H60C session (2026-10-08) — three genuinely-new hypotheses, ranked and validated

This session's lane is the **two-view co-training / disagreement** method (View A geophysical,
View B surface). That lane was already executed (CTD5) and is **negative** — re-verified on the
freshly restored 2026-10-08 bytes by `scripts/verify_lane_h60c.py`:

* The lane artifact `gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif`
  (SHA-256 `a6e6e44aebaf057989e254bd5ce3729e5a94836c0e5687a95e91e3fc8a40c686`) is **format-valid**
  (EPSG:32611, 3,730×3,292, exact sample transform, all-finite `{0,1}`, zero mass outside the
  footprint) and **decoded-pattern-unique** (max tie-aware Spearman 0.00048 vs the 13
  manifest-pinned registry rasters; 0 exact matches; not a literal prior union).
* It **fails the parallel-lane uniqueness gate**: maximum directed ≤3px dot proximity to one
  registry raster is **1.0** (> 0.70). The cause is a **registry-saturation** fact, not a property
  of our dots: the 13GEMSDOE spacing-5 lattice covers **99.87 %** of the eligible footprint within
  3px, so *no non-empty raster on this frozen footprint can pass the >70% rule*. → **DUPLICATE/STOP,
  research-only, 0 slots used.** Receipt: `work/h60c_lane_verification.json`.

Because the disagreement field is not promotable, this session also did what the brief asks for:
**three hypotheses not yet implemented in this repository**, each naming its layers, physical
signature, why it should catch a catalogue-missing fault, and how it differs from the repo. They are
ranked by expected DTI / implementation cost, and the **top one was validated on the shared
spatially-blocked holdout**.

> Instrument caveat (carried through from R4 + `knowledge/10` §5): the local hide-and-recover
> simulator does **not** predict the organiser's board (Spearman ≈ −0.10; uniform random beat the
> champion). The organiser-tied instrument is the set algebra in `scripts/h60_forensics.py` /
> `scripts/h60_identify.py`, re-run this session on the restored bytes (below). A holdout win is a
> **necessary-but-not-sufficient** gate; it does not authorise a slot.

## 0 · The organiser-tied anchor, re-derived on the 2026-10-08 bytes

Recomputed by `scripts/h60_forensics.py` (never copied): **|G| = 14,088.7 px**; the champion
`A = h33-2-b2` (owner-reported 0.2778) splits into the atom **ABCDE = A∩B∩C∩D∩E = 25,517 px** that
carries **all** of its credit (NNLS density **0.20469**, credit 5,223.1) plus **AB--E = A\C =
12,137 px** of **zero** density. `scripts/h60_identify.py` gives the identified DTI intervals:

| candidate | px | DTI_lo | DTI_hi |
|---|---:|---:|---:|
| `A` champion | 37,654 | 0.2772 | 0.2784 |
| **`P1 = A∩C`** (the dense core) | 25,517 | 0.2524 | **0.3196** |
| `P2 = A\C` | 12,137 | 0.0000 | 0.0788 |
| `E∩I\A` (novel, off the champion) | 14,073 | 0.0000 | 0.1153 |
| `I\E` (off-catalogue mass) | 147,632 | 0.0495 | 0.2179 |

The user's "0.3195 current best" is the **identified upper bound of the dense core P1** (0.3196).
The structural tension that governs every candidate below: **the pixels with the highest measured
credit density (0.205, P1) are exactly the pixels where 4–5 independent prior submissions already
agree — i.e. the maximally *non-unique* pixels** — while the pixels that are novel to every prior
have an identified credit ceiling of ≤ 0.218 (`I\E`) and usually 0. A submission that is both
unique-per-the-lane-gate **and** above 0.32 is therefore not supported by any measurement in this
repository.

## 1 · H60C-N1 — pixel-level, orientation-consistent DEM-edge × radiometric-edge coincidence

* **Layers.** Band 12 `det_elev` (DEM) and band 6 (GeoDAWN total-count radiometric).
* **Physical signature.** A per-pixel **edge in both fields of co-aligned strike**: score =
  `min(rank(|∇DEM|), rank(|∇rad|)) × (1 + cos 2Δθ)/2`, where `Δθ` is the difference of the two
  fields' edge orientations (axial, mod 180°). High only where a *strong* topographic edge and a
  *strong* radiometric edge coincide **and** share strike. This is a 2-way independent-edge
  coincidence, a precision-raising operation in the same family as the measured density climb from
  a single field (0.056) to 4-way (0.138) to 5-way (0.205) agreement.
* **Why it catches a catalogue-missing fault.** A fault that offsets a radiometric unit
  (hydrothermal alteration, a lithologic contact) *and* has a small topographic offset produces two
  coincident, co-oriented edges. The orientation gate rejects the documented false-positive mode —
  canyon rims, stream banks, alluvial-fan margins, roads — which are single-field edges.
* **How it differs from this repository.** The repo's "agreement" is (a) **view-OOF-probability
  product** `p_A·p_B` (H59 `field_product`) or (b) **cross-team** corroboration of whole priors
  (H60-A). Neither is a **raw-edge, orientation-consistent, pixel-level** coincidence of two
  physical edge types. It is *not* co-training disagreement (which requires one view to *abstain* —
  CTD5/H56/H59).
* **Expected DTI / cost.** Medium / Low. **VALIDATED below → negative.**

**Validation (HOLDOUT-DTI), evaluator `gems52-pooled-hide-v1`, 4 hide folds, 36,439 withheld
positive pixels, 15,000-dot budget, `scripts/n2_holdout.py`:**

| arm | HOLDOUT-DTI | 95% CI (paired spatial-cluster, 1,000 draws) |
|---|---:|---:|
| `singleB` control (logistic on DEM, slope, radiometric) | 0.01890 | [0.01211, 0.02703] |
| **H60C-N1** candidate | **0.00857** | [0.00614, 0.01131] |

Paired delta (N1 − singleB) = **−0.01033**, 95% CI **[−0.01848, −0.00347]** — a significant loss to
the surface control at identical folds/budget, and far below the CTD5 single-B reference of
0.106749 (different, richer feature stack). **Verdict: NEGATIVE for promotion; not promotable.
No slot used.** The learned logistic control already subsumes the coincidence the raw transform
adds. Receipt: `evidence/h60c_n2_holdout.json`.

## 2 · H60C-N2 — seismicity local-excess (point-process) anomaly, off-catalogue

* **Layers.** Band 16 `ieq_n100a15` (epicentral seismicity) treated as a spatial point process.
* **Physical signature.** A per-pixel **local-excess** statistic: observed event count in a 500 m
  disc minus the expected count under the background intensity — a Poisson / K-function
  *relative-rate* test, giving P(fault | seismicity clustering above chance). This is the standard
  estimator for clustering on hidden linear structures.
* **Why it catches a catalogue-missing fault.** Active and buried faults concentrate quakes. The
  USGS/INGENIOUS catalogue is a **surface Quaternary-expression** inventory and is structurally
  blind to a buried fault that still nucleates earthquakes. A local-excess (not a smoothed
  intensity) is more fault-specific because it discounts the regional background rate.
* **How it differs from this repository.** H59 `field_seismicity` = `rank(band16) × rank(∇band16)`,
  a **smoothed, gradient-weighted field**. N2 is a **point-process local-excess test** (relative
  rate), a different estimator with a null model, not a field smoothing.
* **Expected DTI / cost.** Medium-Low / Low-Medium. **Not validated this session** (experiment
  budget). Caveats to disclose: the input is the *gridded* band (an approximation to the true point
  process), and the study region is weakly seismic, so the excess signal may be sparse; the
  holdout truth is catalogue (surface) faults, which a buried-fault seismicity signature is not
  matched to.

## 3 · H60C-N3 — short-fault step detector (reduced-persistence signed step + sign-consistency)

* **Layers.** Band 12 `det_elev` (DEM).
* **Physical signature.** For each of the four Basin-and-Range strike families, the **signed**
  across-strike difference `f(x + k v) − f(x − k v)` at a **short** half-width, taken **without**
  the kilometre-scale along-strike persistence that `scarp_step` applies, plus a **sign-consistency**
  gate over a 3-px along-strike window (a monotone **step**, not an oscillating **bump**).
* **Why it catches a catalogue-missing fault.** INGENIOUS/USGS Quaternary mapping preferentially
  maps faults with clear, laterally-continuous expression; **short, young faults are under-mapped**.
  A short-persistence, step-confirmed detector is tuned to exactly those.
* **How it differs from this repository.** `scarp_step` (`transform.py`) *deliberately* applies
  km-scale along-strike persistence **to remove** short features as false positives (documented
  against Hermant et al. 2025's canyon/stream/stream-bank firing). N3 *deliberately lowers* the
  persistence and adds a **sign-consistency** gate to **recover** short faults — the opposite
  design intent. This is a genuine methodological change, not a retune of the same rule.
* **Expected DTI / cost.** Medium-Low / Low. **Not validated this session** (experiment budget).
  Caveat: the holdout truth is whole (long) catalogue components, so a short-fault detector can
  under-perform *on this holdout* even if it is the right tool for the real off-catalogue truth —
  an important instrument/construct mismatch to state, not hide.

## 4 · Synthesis and honest reading

The transform/feature space is **saturated**: the repository already implements `scarp_step`
(persistent two-sided step), `hessian_line`, multi-scale `oriented_energy`, structure-tensor strike
coherence, strike-projected basement steps (NNE/NW), signed-log-edge, co-training disagreement
(H56/H59/CTD5), cross-provenance corroboration (H60-A), and `field_product`. The two **binding**
constraints on beating 0.3195 on this frozen footprint are, in order:

1. **The registry-saturated uniqueness gate** — the 13GEMSDOE spacing-5 lattice covers ~100 % of the
   footprint within 3 px, so the >70% directed-proximity lane gate is mathematically impassable for
   any non-empty raster (measured this session, `work/h60c_lane_verification.json`).
2. **The defective holdout simulator** — Spearman ≈ −0.10 with the board, so a holdout win does not
   predict a board win, and the set algebra is the only organiser-tied instrument.

Neither a better raw transform (N1, tested) nor a new geophysical estimator (N2, N3, not tested) is
expected to beat 0.3195 while also being lane-unique. Beating the board more likely requires either
(a) a detector that finds genuinely new off-catalogue faults missed by all twelve priors — whose
identified credit ceiling (≤ 0.218 for `I\E`) is *below* the dense core's 0.32 — or (b) emitting the
dense corroboration core P1 (score ≤ 0.3196) which is **maximally non-unique**. The honest
recommendation is unchanged from CTD5: **resolve the registry-saturation policy in the shared
selector prospectively, and obtain organizer-authenticated receipts**, before another experiment.

## 5 · Sources (official / verified)

* Metric, submission format, dataset — https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* Blum & Mitchell, COLT '98 pp. 92–100 — https://doi.org/10.1145/279943.279962
* GeoDAWN airborne magnetic & radiometric survey (USGS) — https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* INGENIOUS (GBCEG) — https://gbcge.org/current-projects/ingenious/
* EPSG:32611 — https://epsg.io/32611 · Tversky index — https://en.wikipedia.org/wiki/Tversky_index
* Reference solution — https://github.com/drivendataorg/gems-prize-reference-solution
