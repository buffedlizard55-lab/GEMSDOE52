# 41 · H65 pre-registration — frozen before any fit (2026-10-09)

Round **H65**. Written before `scripts/run_h65.py` fitted anything; the runner refuses to execute if the
SHA-256 of this file moves (the same discipline as `knowledge/30_hypotheses_H61_preregistered.md`).
Per `AGENTS.md`, every failed experiment below was read first: `knowledge/03` (N-1 … N-21),
`knowledge/31` (H61), `knowledge/33`/`35` (H62), `knowledge/38` (H63), `knowledge/40` + `39c` (H64),
`knowledge/27`/`28` (CTD5).

## 0. Measured starting state, re-derived from the restored bytes in this session

Nothing below is copied from a previous session's prose. Each line was recomputed by
`work/h65/probe.py` and `scripts/h65_forensics.py` from the SHA-256-verified rasters in `data/`
(`data/restore_receipt.json`, `ALL_VERIFIED=True`) and the 526-blob prior census re-materialised into
`work/h65/priors/` (`work/h65/prior_fetch_receipt.json`, `errors=0`).

| quantity | value | source |
|---|---:|---|
| catalogue pixels (`labels.tif` > 0) | 60,988 | `evidence/grid.json` |
| sample-submission finite footprint | 5,167,373 | `evidence/grid.json` |
| valid = all 19 bands finite ∩ sample finite | 5,164,300 | `work/h65/probe.json` |
| eligible = valid ∧ off-catalogue | 5,103,406 | `work/h65/probe.json` (equals `evidence/h61_forensics.json`) |
| legal = eligible ∧ > 200 m from any mapped trace | measured | `work/h65/probe.json` |
| \|G\| (organiser's hidden positive count) | **interval [5,949.3, 12,512.1] px** | `evidence/h61_forensics.json` `G_identification.masked` |
| \|G\| point under "the deleted ring earns exactly 0" | 14,088.7 px (non-binding upper bound) | same, `G_point_under_zero_ring_credit` |
| champion A = `h33-2-b2` (reported 0.2778) | 37,654 px, min distance to catalogue 223.6 m | `data/reference/h33-2-b2-zeros.tif` |
| core P1 = A ∩ C (`d1-5`, reported 0.2477) | 25,517 px, of which **25,502 inside `legal`** | `work/h65/probe.py` |
| marginal acceptance bar at DTI 0.2778 | 0.0588 credit per emitted pixel | `evidence/h61_forensics.json` `marginal_bar` |
| uniform-random credit density over the legal set | 0.0279 | `revealed.calibrate().reference_densities` |
| band 6 identity | radiometric **total count**, Spearman 0.99995 vs the external GeoDAWN TC grid, 0.0175 vs the magnetic tilt angle its own tag claims | `evidence/h61_forensics.json` `band6_identity` |

Metric (official, page 967; implemented in `src/gems52/metric.py`, pinned by `tests/test_metric.py`):

```
DTI = TPw / (alpha*FPw + beta*FNw + eps),  alpha = 0.2, beta = 0.8, R = 300 m = 3 px
k(d) = max(1 - d/R, 0);  TPw = sum_g max_x p(x) k(|x-g|);  FNw = |G| - TPw
```

For a binary emission whose dots are separated by more than the kernel support, `M = TPw` and

```
DTI = T / (0.2*S + 0.8*|G|)          S = off-catalogue emitted mass, T = credited mass
```

so **{0,1} is optimal** (the metric is not scale invariant) and the only two levers are `T` and `S`.

## 1. The five candidate hypotheses, ranked

Ranked by expected DTI improvement first, implementation cost second. "New" means new against the
written record in `knowledge/03`, `31`, `33`, `35`, `38`, `40`, not against memory.

### H65-1 · Basement-surface differential geometry as View A (RANK 1 — the round that is run)

* **Expected DTI improvement:** the largest available inside the lane, because it replaces the View-A
  channel set that failed sufficiency three times running (0.5163 / 0.5362 / 0.5230 out-of-quadrant
  AUC) with channels that are *derivatives of the one band whose physical meaning is a fault offset*.
* **Implementation cost:** medium. No new external data; all 19 organiser bands are already restored.
* **Layers.** View A: band 15 `Depth to basement surface - thickness of sedimentary cover` (the only
  organiser band that is a *surface*, not a field, and a buried normal fault is a step in it);
  bands 13/11/5/18 isostatic gravity anomaly and its vertical, slope and horizontal gradients;
  bands 1/2/3/9/14 magnetics; bands 4/7/8 geodetic second invariant, shear rate, dilatation rate;
  bands 10/16 distance-to and density-of earthquakes; band 17 conductivity surface.
  View B: bands 12/19 detrended elevation and its slope, band 6 (radiometric total count, identity
  measured above), and the external GeoDAWN K/Th/U/TC grids in `data/external/geodawn_rad_u8.tif`.
* **Physical signature targeted.** Three transforms, none of which is a raw band level:
  (i) `|∇ depth-to-basement|` and `∇² depth-to-basement` at σ = 2, 4, 8 px — the edge and the
  crest-of-step operators for a buried normal fault;
  (ii) a **band-passed isostatic residual**, band 13 minus its local mean at 5 km and 15 km, which
  removes the regional basin-fill trend that dominates the raw gravity field and leaves local
  basement relief;
  (iii) **cross-instrument gradient coherence**: the absolute cosine of the angle between
  ∇(isostatic gravity) and ∇(RTP magnetics). A fault that cuts both the density and the
  magnetisation surface produces two gradients that are *parallel*; a lithologic contact or a
  basin axis generally does not.
* **Why it should catch a fault missing from the catalogue rather than one already in it.** The
  catalogue is a geomorphic product: it maps traces that survive as scarps. A fault buried under
  basin fill has no scarp, so it is absent from `labels.tif` by construction, but it still offsets the
  basement surface, which is what band 15 measures. The A-confident / B-abstaining class is exactly
  that population, and it is the class the lane calls "the fault may be buried beneath cover".
* **How it differs from anything implemented here.** H61 used raw band values; H63 used
  step/persistence columns of bands 13/15/2; H64 was a capacity cut of H61. None computed the
  basement-surface Laplacian, none band-passed gravity against its own regional trend, and none used
  the gravity/magnetics gradient-angle coherence channel. `knowledge/03` N-19 records that R4's
  74-layer stack broke conditional independence at ρ = 0.7051; the channel count here is capped at 24
  and independence is re-tested (S2) rather than assumed.

### H65-2 · Cross-family consensus as the credit-density proxy for novel mass (RANK 2 — also run)

* **Expected DTI improvement:** second, and it is the only ranking for *novel* mass that rests on a
  measured credit effect rather than on an unvalidated detector.
* **Implementation cost:** low. The 526-blob census is already on disk.
* **Layers.** No geophysics. The decoded positive support of every informative prior raster.
* **Physical signature.** Per-pixel count of *distinct decoded prior patterns* whose 3 px halo covers
  the pixel, i.e. how many independently-built fields agreed that this pixel is fault-like.
* **Why it should catch a missing fault.** `knowledge/10` §3 measured that mass selected by two
  independent thinnings of one field carries credit density 0.163–0.205 while mass selected by one
  carries 0.000–0.087 — an order of magnitude. Corroboration is therefore the only sub-ranking inside
  a scored file that the organiser's own numbers can see. Extending it *across* families rather than
  within one is the untested direction.
* **How it differs.** H56's "consensus core" was a consensus of this repository's own arms inside one
  round. No round has ranked novel mass by the number of distinct published decoded patterns covering
  it. It is also not a submission-copy: consensus is used only where the lane caps allow it, and the
  binding families' halos are excluded from the novel pool by construction (§4).

### H65-3 · Isostatic residual after regressing gravity on topography (RANK 3 — not run this round)

* **Expected DTI improvement:** medium. **Implementation cost:** medium.
* **Layers.** 13 (isostatic gravity anomaly), 12 (detrended elevation), 15 (depth to basement).
* **Signature.** Locally-weighted regression residual of gravity on elevation at 5/15/45 km scales —
  the part of the gravity field that topography does not explain, which is cover thickness and
  basement relief.
* **Why it differs from H65-1(ii).** H65-1(ii) band-passes gravity against *itself*; H65-3 removes the
  *topography-predicted* component, which is a different null. CTD5 used a cover-disagreement lattice
  and was killed by the >70 % near-dot gate (`knowledge/27`), not by this transform.
* **Not run this round** because the brief's budget is three experiments and H65-1(ii) already carries
  the band-pass version of the same idea.

### H65-4 · Geodetic strain lineament intersection (RANK 4 — not run this round)

* **Expected DTI improvement:** small alone, larger as a genuinely third view. **Cost:** low.
* **Layers.** 4 (second invariant), 7 (shear rate), 8 (dilatation rate) — the only organiser bands
  that are neither topographic nor potential-field.
* **Signature.** Intersection of high-shear and high-dilatation-gradient lineaments; blind faults load
  strain without rupturing the surface.
* **Why not run.** Bands 4/7/8 are already inside the H65-1 View-A stack, so testing them separately
  would be a fourth experiment, over budget. Recorded so the next session does not re-derive it.

### H65-5 · Trace-correction corridor (R5-H1) — carried forward, still gated, still not run

* The organiser has confirmed the population exists (staff, forum topic 11516, quoted in
  `knowledge/33` R5-H1). The frozen §A-gate in `knowledge/33` has never been executed. This round's
  emission **excludes** the ≤ 200 m ring because its credit is measured at exactly 0.0 for the family
  whose bytes we hold (`evidence/h61_forensics.json` `catalogue_rings`, `revealed.corridor_credit`).
* Named free official source needed and obtainability: USGS 3DEP 1 m DEM (`lidar_scarp_features_u8.tif`
  is already restored from the owner mirror, derived from 706 of 716 tiles). No new download is
  required to run the §A-gate, so it is viable and remains the highest-upside un-run idea in the repo.

## 2. Frozen gates and instruments

* **Evaluator.** `gems52-pooled-hide-v1`: `holdout.make_folds(mode="hide", n_folds=4, buffer_px=4)`,
  whole 8-connected catalogue components per fold, prevalence thinned into the measured bracket,
  visible catalogue masked pixel-exactly (`holdout.mask_visible`), pooled DTI with α = 0.2, β = 0.8
  and the 300 m triangular kernel, 95 % cluster bootstrap over 20 km clusters.
* **S1 sufficiency (Blum–Mitchell premise).** View A out-of-quadrant (`mode="block"`) AUC against the
  hidden catalogue: PASS at mean ≥ 0.60 and every fold ≥ 0.55. H61 0.5163, H63 0.5362, H64 0.5230 all
  FAILED. If S1 fails again the co-training mechanism is reported as refuted a fourth time and the
  disagreement arm is **not** promoted, whatever it scores.
* **S2 independence.** Pearson *and* Spearman of the two views' per-block out-of-fold error on labelled
  negatives; ABANDON at |r| ≥ 0.60 (`cotrain.ABANDON_R`).
* **Leakage canary.** Every feature fitted alone on the holdout; AUC > 0.90 is treated as leakage until
  proven otherwise.
* **Buffered whole-segment blocks.** `grid.buffer_from_block_ids`, buffer 4 px = 400 m > the 300 m
  kernel, so no fold can be scored on mass its own fit region could see.
* **Arms, all at matched budgets.** `single_A`, `single_B`, `union_max`, `disagreement_pre`,
  `disagreement_post`, `random`.
* **Control.** `single_B` must reproduce the committed H61/H64 value 0.1745172876 to |Δ| ≤ 0.001
  (`knowledge/39b` amended tolerance).

## 3. Frozen verdict rule

`promote` requires **all** of: format gate PASS · decoded-pattern uniqueness PASS · lane gate
(literal and saturation policy) PASS on the surface **and** on the final dots · not-the-union PASS ·
S1 PASS · holdout paired CI lower bound above `single_B` > 0. Anything else is `negative`, and a
negative result is published with its numbers.

Because `knowledge/10` §5 measured that the hide-and-recover instrument **anti-ranks** the board
(Spearman ρ = −0.1045, p = 0.734, n = 13; the champion ranks 13th of 13 on the instrument and 1st on
the board), the holdout is reported as HOLDOUT-DTI and **never** as a forecast. The forecast column is
the projection from the measured credit algebra, labelled PROJECTION.

## 4. Frozen placement rule — the lane-feasible constrained placer (new this round)

No previous round enforced the lane during placement; H63 and H64 both shipped files labelled
DUPLICATE (`knowledge/38`, `39c`). H65 places under the constraint instead of checking it afterwards.

1. **Legal set.** `valid ∧ ¬catalogue ∧ distance-to-catalogue > 200 m`. Nothing is emitted on a
   catalogue pixel (the organiser masks them, so such mass is pure tax) and nothing inside the ring
   whose credit is measured at exactly zero.
2. **Core.** The measured double-corroborated credited core `P1 = A ∩ C` restricted to the legal set
   (25,502 px). It is inherited mass whose credit is bounded *exactly* by the organiser's own reported
   scores: `t(P1) ∈ [T(A)+T(C)−T(E), T(A)]`. It is used as evidence, learned from two prior scored
   rasters; it is not a copy of either (A ∩ C is neither A nor C).
3. **Novel mass.** Ranked by H65-1's two-view field multiplied by H65-2's cross-family consensus, and
   drawn **only** from legal pixels that lie outside the 3 px halo of every *binding* prior (a prior
   whose core-near count already reaches the cap) and outside the 3 px halo of the core itself.
4. **Caps, enforced during placement.** For target size `S` and margin `m`, every informative prior
   `p` must satisfy `|{my dots within 3 px of p}| ≤ m·S`. `m = 0.67`, i.e. a 3-point buffer below the
   brief's literal 0.70, because the brief's rule is "more than 70 %". Universal-coverage probes
   (3 px halo covering ≥ 95 % of the legal set, `gates.PROBE_COVERAGE`) cannot localise a lane; their
   literal statistic is measured and reported but they are not enforced, per `AGENTS.md`.
5. **Budget.** `S = n_core + n_novel` with `n_novel = ceil(n_core·(1/m − 1))` rounded up to the
   placer's feasible count, i.e. the *smallest* novel mass that satisfies the lane. This is deliberate:
   the marginal acceptance bar at DTI 0.2778 is 0.0588 credit/px and uniform random is 0.0279, so
   novel mass bought only to satisfy the lane is expected to be dilutive and must be minimised, not
   maximised. `revealed.budget_rule` is reported alongside for the alternative reading.
6. **Spacing.** Novel dots are kept ≥ 3 px from every other emitted dot so that `M = T` stays a good
   approximation and novel mass is not paying tax for credit the core already collects.
7. **Output.** Single band, float32, values exactly {0, 1} ⊂ [0, 1], EPSG:32611, 3,730 × 3,292,
   transform `(100, 0, 243350, 0, -100, 4508550)`, all finite (no NaN anywhere), verified by re-reading
   the written file against `data/sample_submission.tif`.

## 5. Frozen projection algebra (labelled PROJECTION, never a score)

For each `|G|` in the measured bracket `[5,949.3, 12,512.1]`:

```
T(X) = s_X * (0.2*S_X + 0.8*|G|)          for each reported file X
t_core(|G|) in [T(A)+T(C)-T(E), T(A)]     exact, from disjoint-atom additivity
DTI(candidate) = min(t_core + rho_novel*n_novel, |G|) / (0.2*S + 0.8*|G|)
```

with `rho_novel` given a uniform prior over `[0.0279, 0.1387]` — "no better than uniform random over
the legal set" to "as good as the champion file's own average", the two densities that are actually
measured. `P(DTI > 0.2778)` and `P(DTI > 0.3774)` are reported over that joint prior. **The
`rho_novel` prior is a prior, not a measurement; nothing in this repository can certify a novel
field's credit density, and this file does not claim otherwise.**

## 6. What would make this round negative, stated in advance

* S1 fails again (expected on the evidence of three prior rounds) → the co-training *mechanism* is
  reported refuted a fourth time. The emission is then carried by the core and the ranking field, not
  by pseudo-label exchange, and the run card says so.
* The placer cannot reach `n_novel` inside the binding-halo exclusion → the budget falls back to the
  largest feasible `n_novel`, `m` is reported as measured (not as targeted), and the file is labelled
  with its true near-dot share.
* Any gate in §3 fails → verdict `negative`, file published as research-only with an explicit
  DO-NOT-SUBMIT line.

## 7. Budget

Three experiments, two hours, per the brief. Experiment 1 = H65-1 two-view fit + S1/S2/canary.
Experiment 2 = H65-2 consensus ranking and the constrained placement. Experiment 3 = the gate battery
and the projection. No submission slot is spent by this session: the portal is login-walled and this
sandbox has no DrivenData credentials.
