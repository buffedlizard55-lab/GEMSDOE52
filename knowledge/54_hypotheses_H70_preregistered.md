# H70 — hypotheses and protocol, preregistered 2026-10-09 **before** any H70 fit, score or artefact

Frozen file. Its SHA-256 is recorded in `registry/h70_preregistration.json` before the first model
is fitted, and `scripts/run_h70.py` refuses to run if the hash has moved. Nothing below was written
after seeing an H70 result. Lane: the brief's two-view co-training paragraph (Blum & Mitchell, COLT
'98, pp. 92–100, doi:10.1145/279943.279962; View A potential-field/subsurface, View B surface;
disagreement as the discovery signal).

Scope of this round: it isolates the one lane element no previous round ever tested standalone —
**the strict A-only discovery stratum as an emission arm** — validates three cheap lane variants in
one matched-budget holdout, and then builds the round's GeoTIFF with a **lane-valid constrained
placement** (the property the H61 and H64 files lacked). It is a submission round: one file is
built, gated and published with an explicit download/submit verdict. No competition slot is spent by
this document.

---

## 0 · Why this, and what it must not repeat

Four independent rebuilds of View A all failed the Blum–Mitchell sufficiency screen out of
quadrant, and every disagreement arm scored below the single-view control:

| round | View A definition | View A OOF AUC | View B OOF AUC | disagreement arm HOLDOUT-DTI | single_B HOLDOUT-DTI |
|---|---|---:|---:|---:|---:|
| H61 | 36 raw/transformed potential-field channels | 0.5163 | 0.6843 | (pooled with B-only) | 0.1742–0.1745 |
| H63 | step-normalised gravity/basement/RTP, 38 channels | 0.5362 | 0.6862 | 0.040257 | 0.174193 |
| H64 | lower-capacity learner, same features | 0.5230 | — | 0.031233 | 0.174517 |
| H65 | cross-strike detrended offsets, bands 15/13 | 0.5202 | — | not run (premise gate) | — |

All DTI numbers are **HOLDOUT-DTI**, evaluator `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m
triangular kernel, 53,186 withheld positives, 95 % paired 20 km-cluster bootstrap). All AUCs are
out-of-quadrant diagnostics on `label-blind-quadrants-v2`, not DTI scores. Sources:
`evidence/h61_fit_checkpoint.json`, `evidence/h63_{fit_checkpoint,holdout}.json`,
`evidence/h64_{sufficiency,holdout}.json`, `evidence/h65_premise.json`.

Two further measured facts bound this round:

* **The conditional-independence premise held** (H63: max |ρ| = 0.1817 over 2,089 spatial blocks of
  held-out catalogue-zero negatives, abandon bar 0.60), so the brief's abandonment clause does not
  fire; the method fails on *sufficiency*, not on dependence.
* **The exchange transferred nothing** (H63: disagreement_post − disagreement_pre = −0.000364,
  95 % CI [−0.0039, +0.0028]; refit AUCs moved by ≤ 0.01). Co-training as a *lift* mechanism is
  falsified on this stack.

What no round has ever measured: the **strict A-only stratum alone** as an emission. Every
"disagreement" arm so far ranked the soft field `rankA − rankB` over the whole eligible domain,
which pools A-only pixels with B-only pixels and with the concordant tail. The brief's discovery
signal is specifically *"where A is confident and B is not, the fault may be buried beneath cover"*
— a strict, quantile-gated stratum. That stratum has never been isolated, scored, or emitted from.

The H64 build also left a second gap: its file is unique on decoded pixels (0 of 548 identical;
novel_fraction 1.0 against the 511 informative priors) but **lane-DUPLICATE** — 9 informative
priors have > 70 % of its dots within 3 px (largest 0.888), and the constrained re-placement that
enforces the per-raster 70 % cap placed only 31,487 of 37,600 dots before the time limit. No file
in this repository currently passes the lane's policy gate. H70 closes that gap with a placement
that is lane-valid *by construction* (§3).

---

## 1 · Hypotheses (the brief's 3–5 candidates, ranked; status)

Ranking criterion: expected HOLDOUT-DTI improvement against the current comparable control
(single_B ≈ 0.1742–0.1745), divided by implementation cost. Arms A, B and C share the already-fitted
views, so their marginal cost inside the holdout stage is one placement + one evaluation each;
the ranking therefore orders interpretation priority, and all three are measured in E2.

### H70-A — strict A-only isolation (the brief's literal discovery stratum) — RANK 1, tested in E2, built in E3

* **Layers.** The shared store's `view_A_with_external` (36 channels: isostatic gravity anomaly and
  its slope/vertical/horizontal gradients, magnetics — anomaly, RTP, TMI, TMI horizontal/vertical
  gradient, upward-continued TMI and its gradients — geodetic strain second invariant / shear /
  dilatation, earthquake density and distance, depth to basement, surface conductivity) and
  `view_B_with_external` (37 channels: detrended elevation and slope transforms, scarp steps,
  Hessian line response, radiometric total count `raw_band_06`, external GeoDAWN radiometrics).
* **Physical signature.** A fault buried beneath cover offsets the potential field and basement but
  produces no DEM scarp, no slope lineament and no radiometric lineament. Operationalised with the
  H61 exchange gate, now used as an **emission** gate: operating rank `rankA ≥ 0.95` (donor
  confidence) ∧ `rankB ∈ [0.35, 0.65]` (receiver abstention), evaluated on the post-exchange
  (co-trained) operating ranks, restricted to the allowed domain.
* **Why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already
  in it.** The catalogue is a surface-mapped product: a fault whose surface expression is absent
  (buried under basin fill or volcanic cover) cannot be in it, yet it still offsets basement depth
  and the gravity/magnetic field. The A-only stratum is precisely the set of pixels with
  subsurface signal and no surface signal.
* **How it differs from anything implemented.** H61/H63/H64's disagreement arms rank the soft field
  `rankA − rankB` over the whole eligible domain — a pool of A-only, B-only and concordant-tail
  pixels whose top-k is dominated by wherever A's noise tail happens to sit. The strict stratum
  (quantile-gated, whole-segment, buffered) has never been isolated as an arm or emitted from. The
  gate thresholds themselves are H61's frozen exchange thresholds, reused unchanged.
* **Expected DTI improvement.** Low, and stated honestly before the run: with View A's out-of-quadrant
  AUC measured at 0.5163 / 0.5362 / 0.5230 / 0.5202 across four rebuilds, the stratum's expected
  HOLDOUT-DTI is at or below the random control (0.078). The value of the test is **falsification of
  the brief's literal discovery signal** — every previous disagreement number pooled this stratum
  with others, so no previous number actually measured it.
* **Implementation cost.** One extra arm in the existing holdout stage (~10 min); the E3 build emits
  from it directly.

### H70-B — B-only veto on the strongest arm (single_B minus the B-only stratum) — RANK 2, tested in E2

* **Layers.** View B operating ranks plus the disagreement stratum mask (no new physics).
* **Physical signature.** The brief's own reading: *"where B is confident and A is not, suspect
  surface artifacts such as roads or erosion lines."* A DEM/radiometric lineament with no
  potential-field support is more likely anthropogenic or erosional than tectonic.
* **Why it should catch a fault missing from the catalogue.** Roads, fence lines, erosion rills and
  lithologic strips are not faults and are by construction absent from a fault catalogue — so
  vetoing them removes off-catalogue false-positive mass that the surface view otherwise emits.
* **How it differs.** The disagreement signal was only ever used as a *positive* emission field
  (`rankA − rankB`); no round used it as a *negative filter* on the strongest arm. H70-B places
  single_B's top-k after deleting the B-only stratum (`rankB ≥ 0.95` ∧ `rankA ∈ [0.35, 0.65]`).
* **Expected DTI improvement.** Small and possibly negative: A's abstention carries little
  information (OOF AUC ≈ 0.52), so the veto is near-random with respect to truth; the expected
  delta vs single_B is within the bootstrap noise. Cheap to measure, and it directly tests the
  brief's artifact clause.
* **Implementation cost.** One extra arm (~10 min).

### H70-C — concordant-only emission (both views confident) — RANK 3, tested in E2

* **Layers.** Both views' operating ranks.
* **Physical signature.** Two physically independent sensor families — potential field/subsurface
  versus surface/radiometrics — agreeing at one pixel is the strongest corroboration available in
  this stack. A genuine fault should be visible to both unless it is buried (A-only) or
  anthropogenic (B-only); concordant pixels are the residual candidate set.
* **Why it should catch a fault missing from the catalogue.** Independent-sensor agreement
  suppresses both catalogue-adjacent artefacts and single-view noise, so the surviving ranking is
  more likely to sit on real, uncatalogued structure than either view alone.
* **How it differs.** `union_max` ranks `max(rankA, rankB)` over the whole domain (measured
  0.1497–0.1513, below single_B because A's noise tail dilutes the ranking at fixed budget). The
  strict concordant stratum (`rankA ≥ 0.95` ∧ `rankB ≥ 0.95`) has never been isolated; H70-C places
  its top-k by `min(rankA, rankB)`.
* **Expected DTI improvement.** Between single_B and union_max; small. If View A contributes any
  independent signal at all, concordant ranking should edge single_B; if A is pure noise out of
  quadrant (the four sufficiency measurements), it should land slightly below.
* **Implementation cost.** One extra arm (~10 min).

### H70-D — radiometric-cover gating of the A-only stratum — RANK 4, deferred (budget)

* **Layers.** H70-A's stratum intersected with radiometric quiet (band 6 total count and `X_rad_*`
  line responses below their local background), sharpening "buried beneath cover" to "no surface
  expression in *any* surface view".
* **Physical signature.** A covered fault shows no lineament in DEM *or* radiometrics; radiometric
  alteration halos, by contrast, mark fluid pathways and can corroborate a hidden fault's position.
* **Why catalogue-missing.** Same mechanism as H70-A, with a second independent surface family
  required to be silent.
* **Differs.** No round has gated an emission stratum by radiometric context; radiometrics entered
  only as View B learner features.
* **Expected / cost.** Small second-order effect on a stratum already expected at random; medium
  cost (per-cell radiometric transforms). **Deferred**: not authorised in this round's 3-experiment
  budget.

### H70-E — deformation-only View A2 — RANK 5, deferred (needs its own round)

* **Layers.** A View A built only from the deformation bands: geodetic second invariant, shear rate,
  dilatation rate (bands 4/7/8), earthquake density and distance (bands 10/16).
* **Physical signature.** Active or recently active faulting expressed as strain transients and
  seismicity, independent of the potential-field response that dominates View A.
* **Why catalogue-missing.** A young, blind fault in a sedimentary basin can strain and micro-seismic
  without a mappable surface trace.
* **Differs.** Every View A so far mixed potential-field and deformation channels; none tested the
  deformation half alone, so the four sufficiency failures cannot attribute the failure to either
  half.
* **Expected / cost.** Unknown; high cost (new store build + refit of every fold). **Deferred**.

---

## 2 · Experiments (budget: 3, per the brief's §6)

**E1 — canary + independence (mandated by the brief).** Rebuild nothing: use the template's cached
feature stack (`work/r2/features`, version `structural-core-v2-band6-B+external-geodawn-v1`,
78 features, 4,593,171 eligible px, input pins verified by `run_h61.setup`). Run the H61 canary
stage unchanged (raw single-feature AUC of every feature on every fold's held-out sample, alarm
0.90; fitted single-feature canary on the five strongest) and the H61 independence screen
(`spatial.negative_block_errors` on 50×50 px blocks of held-out catalogue-zero negatives, then
`spatial.independence`, abandon at |ρ| ≥ 0.60). The brief's clause — *correlate each view's
spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are strongly
correlated* — is measured here, before any exchange.

**E2 — fit + exchange + matched-budget holdout (validates H70-A/B/C).** H61's fit stage unchanged
(same sampler, same learner, same label-blind-quadrants-v2 folds, buffer 80 px), then exactly one
confident-to-abstaining whole-segment pseudo-label round per direction per fold (H61 thresholds:
donor rank ≥ 0.95, receiver rank ∈ [0.35, 0.65], ≥ 5 px segments, ≤ 2,000 px per fold per
direction, wholly inside the training domain and disjoint from the evaluation region, hidden
components, visible catalogue + 4 px collar and sampled labels — the assertions in
`run_h61.stage_exchange` are kept). Then the matched-budget hide-and-recover holdout with **nine**
arms at exactly 9,400 dots per fold per arm, 3 px minimum separation, pooled HOLDOUT-DTI with the
95 % paired 20 km-cluster bootstrap (1,000 draws):

| arm | field (post-exchange ranks unless noted) |
|---|---|
| `single_A` | `rankA_pre` |
| `single_B` | `rankB_pre` (current comparable control) |
| `union_max` | `max(rankA_pre, rankB_pre)` |
| `disagreement_pre` | `rankA_pre − rankB_pre` |
| `disagreement_post` | `rankA_post − rankB_post` |
| **`a_only` (H70-A, new)** | `rankA_post − rankB_post` gated to `rankA_post ≥ 0.95` ∧ `rankB_post ∈ [0.35, 0.65]` |
| **`single_B_veto_Bonly` (H70-B, new)** | `rankB_pre` gated to NOT(`rankB_pre ≥ 0.95` ∧ `rankA_pre ∈ [0.35, 0.65]`) |
| **`concordant` (H70-C, new)** | `min(rankA_pre, rankB_pre)` gated to `rankA_pre ≥ 0.95` ∧ `rankB_pre ≥ 0.95` |
| `random` | uniform over the allowed domain |

An arm that cannot fill 9,400 dots invalidates the comparison and is reported, not rescued. The
verdict comparison is the paired bootstrap delta of each new arm against `single_B`.

**E3 — build, gate, publish.** Build the round's GeoTIFF from the **H70-A strict A-only post-exchange
field** (the lane's literal candidate), with the placement of §3, the not-the-union check, the
A-only geological-reasoning CSV for every emitted cell (the brief: *write the geological reasoning
for every A-only candidate*), the uniqueness gates (tier 1 exact vs every prior; tier 2 novelty vs
informative priors), the lane gates (surface before placement, dots after), the on-disk validator,
and the run card. Publish to `docs/downloads/` and the site with an explicit verdict. **No
competition slot is spent; promotion is the separate selector step.**

---

## 3 · Lane-valid constrained placement (the H70 build change)

The lane rule: STOP if more than 70 % of the candidate's dots fall within 3 px of **one** registry
raster's dots (or rank correlation > 0.90). On this registry the *literal* rule is saturated — the
13GEMSDOE spacing-5 lattice probe's 3 px halo covers ≥ 95 % of the eligible footprint, so its
near-dot statistic is 1.0 for every nonempty candidate (measured, `evidence/ctd5_registry_saturation.json`;
`knowledge/31`). The repository policy therefore classifies universal-coverage probes (measured
3 px coverage ≥ 0.95) as non-localising and applies the rule to **informative** priors only
(`gems52.gates.lane_report`, the H61 shared-template repair — not forked).

H64 enforced the per-raster cap lazily (constrain only current offenders, re-place, repeat) and
could not fill its budget (31,487 of 37,600). H70 enforces it **by construction**:

1. Constrain **every** informative prior from the first placement (halo = its 3 px dilation).
2. Discover the largest feasible budget `n` by feasibility probes (coarse-to-fine over
   [16,000, 40,000] dots; a probe places greedily in field-score order with 3 px minimum separation,
   skipping any dot that would push an informative raster's near-dot count over
   `cap = floor(0.70 × n)`, and reports how many dots it placed).
3. Adopt the largest feasible `n`; the emission is the first `n` placed dots. Because the greedy
   respects every cap at `cap = floor(0.70 × n)` and the emission is a prefix of the placement, every
   informative raster's near-dot share of the emission is ≤ 0.70 **by construction**, whatever the
   halos' geometry. The literal gate is still reported verbatim (it will read DUPLICATE against the
   lattice probe for any nonempty candidate — a measured property of the registry, not of this file).

This is a uniqueness constraint, not a holdout-driven choice: it is applied identically to any
candidate built from here, and it does not use one label pixel.

---

## 4 · Thresholds (H61's frozen values, unchanged; nothing is re-tuned)

canary alarm 0.90 · independence abandon |ρ| ≥ 0.60 · donor rank ≥ 0.95 · receiver rank interval
[0.35, 0.65] · fold buffer 80 px · block side 50 px · min pseudo segment 5 px · pseudo cap 2,000 px
per fold per direction · holdout budget 9,400 dots per fold per arm · min dot separation 3.0 px ·
catalogue exclusion 200 m · bootstrap 1,000 draws over 200 px (20 km) clusters · lane rank limit 0.90
· lane near-dot limit 0.70 at 3 px · probe coverage threshold 0.95.

## 5 · Verdict rule (frozen; mirrors knowledge/39 §4)

The file is **eligible for the selector** only if ALL of: format gate PASS · lane gate PASS ·
decoded-pattern uniqueness PASS (no identical prior, novel_fraction ≥ 1.0 against informative
priors, not the literal prior union) · not-the-union PASS · S1 sufficiency PASS (View A mean OOF AUC
≥ 0.60 and min fold ≥ 0.55) · holdout: the candidate arm beats `single_B` with the paired 95 % CI
of the delta above 0. Even then nothing is promoted and no slot is used — promotion is the separate
selector step, within the weekly cap. Otherwise the verdict is **negative / research-only**:
DOWNLOAD yes (format-valid and unique), SUBMIT no. Negative results are deliverables.

## 6 · Labels used in every H70 number

* **HOLDOUT-DTI** — evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel,
  withheld-positive count, 95 % paired cluster-bootstrap CI. A simulator number, never a leaderboard
  score.
* **PREMISE-AUC / diagnostic AUC** — out-of-quadrant AUC on `label-blind-quadrants-v2`; not a DTI
  score.
* **ORGANIZER-CONFIRMED** — only a score copied from a submission-page receipt. None exists in this
  repository; every board number here is PUBLIC BOARD or OWNER-REPORTED.
* **SYNTHETIC** — operator checks on generated grids.

## 7 · The 0.2778 question (answered at PhD level; full algebra in `knowledge/01` and `knowledge/27`)

Measured from the restored bytes (`data/reference/h33-2-b2-zeros.tif`, SHA-256 pinned in
`registry/data_manifest.json`): the owner-reported 0.2778 file is a **strict subset** of the
owner-reported 0.2600 file (37,654 ⊂ 44,090 off-catalogue px), itself a strict subset of the
0.1922 parent field. The champion added **no** pixel and deleted 6,436 — every one between 100 m and
200 m of a mapped trace (measured); its own nearest dot is 223.6 m from the catalogue. Under
`DTI = TPw / (0.2·FPw + 0.8·FNw)` with `FNw = |G| − TPw` exactly, mass on a masked or near-masked
pixel can never earn credit but always pays the false-positive tax; deleting it is free precision
(+2.6 %). The metric is not scale-invariant and binary mass {0,1} is optimal at fixed support
(pinned in `tests/test_metric.py`). Two counterfactuals bound the field: an identical-mass scatter
control scores 0.0778 (placement is worth more than detector recall), and a perfect-precision
counterfactual at this budget ceilings at 0.464. The live public board's top is 0.3774 (xiaofanhu),
so the leader is nearly maxed on placement and must be *finding* structure, not tidying mass. **Can
we beat 0.2778?** Only by ranking pixels by "probability an uncatalogued fault pixel lies within
224 m", which is exactly what the A-only/B-only analysis attacks; our own detector measurements say
the honest expectation is a small gain, not a doubling. The attribution itself is OWNER-REPORTED,
NOT ORGANIZER-CONFIRMED: the champion's token `e5eb6e7e` matches no hash convention of the held
bytes, and the public board attributes 0.2778 to team extradr19 (rank 13, live fetch 2026-10-09).
