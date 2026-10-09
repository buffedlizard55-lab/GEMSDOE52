# H74 — hypotheses and protocol, preregistered 2026-10-09 **before** any H74 fit, score or artefact

Frozen file. Its SHA-256 is recorded in `registry/h74_preregistration.json` before the first model
is fitted, and `scripts/run_h74.py` refuses to run if the hash has moved. Nothing below was written
after seeing an H74 result. Lane: the brief's two-view co-training paragraph (Blum & Mitchell, COLT
'98, pp. 92–100, doi:10.1145/279943.279962; View A potential-field/subsurface, View B surface;
disagreement as the discovery signal).

Scope of this round: it executes **H70-E**, the one lane variant the H70 preregistration deferred as
"needs its own round and its own store build" — a **deformation-only View A2** built from the
geodetic strain and seismicity bands alone (bands 4/7/8/10/16), with View B unchanged. Five
consecutive View A rebuilds that mixed potential-field and deformation channels all failed the
Blum–Mitchell sufficiency screen out of quadrant (H61 0.5163 · H63 0.5362 · H64 0.5230 · H65 0.5202 ·
H70 0.5166, all PREMISE-AUC diagnostics, not DTI scores), so the failure cannot be attributed to
either half of View A. H74 attributes it. It then re-runs the lane's full mandated protocol on the
A2/B pair — independence screen, one whole-segment confident-to-abstaining exchange per direction,
matched-budget hide-and-recover holdout against the single-view baseline — and builds the round's
GeoTIFF from the lane's discovery signal with the lane-valid constrained placement. It is a
submission round: one file is built, gated and published with an explicit download/submit verdict.
No competition slot is spent by this document.

---

## 0 · Why this, and what it must not repeat

Measured lane history (all HOLDOUT-DTI on evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m
triangular kernel, 53,186 withheld positives, 95 % paired 20 km-cluster bootstrap, 1,000 draws;
all AUCs are out-of-quadrant diagnostics on `label-blind-quadrants-v2`, not DTI scores):

| round | View A definition | View A OOF AUC | a_only arm HOLDOUT-DTI | single_B HOLDOUT-DTI |
|---|---|---:|---:|---:|
| H61 | 36 raw/transformed potential-field + deformation channels | 0.5163 | (pooled disagreement) | 0.1742–0.1745 |
| H63 | step-normalised gravity/basement/RTP, 38 channels | 0.5362 | — | 0.174193 |
| H64 | lower-capacity learner, same features | 0.5230 | — | 0.174517 |
| H65 | cross-strike detrended offsets, bands 15/13 | 0.5202 | not run (premise gate) | — |
| H70 | H61 View A unchanged (control) | 0.5166 | 0.046023 (matched) / 0.017351 (pure stratum) | 0.174571 |
| H71 | H61 View A unchanged (control) | 0.5163 | 0.009532 (matched 1,264/fold) | 0.059676 (matched) |

Facts that bound this round:

* **The conditional-independence premise held every round** (H63 max |ρ| 0.1817 · H70 0.1337 over
  2,089 spatial blocks of held-out catalogue-zero negatives; abandon bar 0.60), so the brief's
  abandonment clause does not fire on this stack; the method fails on *sufficiency* and on the
  *discovery signal*, not on dependence.
* **The exchange transferred nothing** (H63 post − pre = −0.000364 [−0.0039, +0.0028]; H70 −0.0004).
  Co-training as a *lift* mechanism is falsified on this stack; H74 re-tests it once on the A2/B pair
  because the pair is different physics, not because lift is expected.
* **The strict A-only stratum was anti-informative with the potential-field View A** (H70 pure
  stratum 0.0174, significantly below uniform random 0.0804, paired Δ −0.0631 [−0.0739, −0.0521]).
  Whether that inversion is a property of the *potential-field* half of View A or of the *stratum*
  itself is exactly what H74 separates.
* **The lane's literal dot rule is saturated on this registry** (the 13GEMSDOE spacing-5 lattice
  probe's 3 px halo covers ≥ 95 % of the eligible footprint, so its near-dot statistic is 1.0 for
  every nonempty candidate; measured `evidence/ctd5_registry_saturation.json`). The repository's
  authoritative lane is therefore `gems52.gates.lane_report`'s **policy** verdict (universal-coverage
  probes classified by measured coverage ≥ 0.95 and excluded as non-localising); the literal verdict
  is reported verbatim alongside, never silently replaced.
* **Control reproduction is mandatory**: single_B must reproduce the committed H61 value 0.174517
  within ± 0.001 on the identical splitter/sampler/learner before any H74 number is trusted. The
  shared store is rebuilt from SHA-256-pinned bytes, so the reproduction is exact up to float noise.

What no round has ever measured: a View A built **only** from the deformation bands. H70-E
preregistered it as RANK 5, deferred: "Every View A so far mixed potential-field and deformation
channels; none tested the deformation half alone, so the four sufficiency failures cannot attribute
the failure to either half."

---

## 1 · Hypotheses (the brief's 3–5 candidates, ranked; status)

Ranking criterion: expected HOLDOUT-DTI improvement against the current comparable control
(single_B ≈ 0.1742–0.1746), divided by implementation cost. Arms A, B and C share the fitted A2/B
views, so their marginal cost inside the holdout stage is one placement + one evaluation each.

### H74-A — deformation-only View A2, the full lane protocol on the A2/B pair — RANK 1, tested in E1+E2, built in E3

* **Layers.** View A2 = the five deformation bands of `training_features.tif` — band 4 geodetic
  second invariant (strain-rate tensor magnitude), band 7 geodetic shear rate, band 8 geodetic
  dilatation rate, band 10 distance to earthquake (100 km radius kernel), band 16 earthquake
  intensity/density (100 km radius kernel) — plus derived transforms built once on the shared
  feature-store footprint: gradient magnitude of each band at the shared scales σ ∈ {1, 3, 8} px
  (15 channels, `H74_def_grad_{band}_{sigma}`) and structure coherence of the second-invariant and
  shear-rate gradients at σ = 3 px (2 channels, `H74_def_coherence_{4,7}`). 22 channels total.
  View B = the shared `view_B_with_external`, 37 channels, **unchanged** (detrended elevation and
  slope transforms, curvature, scarp/profile geometry, radiometric total count `raw_band_06`,
  external GeoDAWN K/Th/U and alteration ratios).
* **Physical signature.** An active or recently active fault in a sedimentary basin accumulates
  geodetic strain (shear/dilatation/second invariant) and concentrates micro-seismicity along its
  plane, while its surface expression can be absent (blind fault) — so a deformation-only view can
  be sufficient where a potential-field view is not, and the A2-confident ∧ B-abstaining stratum is
  the "buried beneath cover" candidate set with a *different* physics basis than H70's.
* **Why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already
  in it.** The catalogue is a surface-mapped product; a young blind fault strains and micro-seismics
  without a mappable trace. Strain and seismicity are *rate* fields: they respond to the fault's
  present activity, not to its erosional expression, so they are exactly the channels a
  surface-mapped catalogue cannot contain.
* **How it differs from anything implemented.** Every View A so far (H61 36 ch, H63 38 ch, H64/H70
  controls) mixed potential-field channels (gravity, magnetics, basement depth, conductivity) with
  the deformation bands; H65 tested cross-strike offsets of bands 15/13 only. No round isolated the
  deformation half, so the five sufficiency failures are unattributed between the two halves. H74
  attributes them: if A2 passes S1 where the mixed View A failed, the potential-field half was the
  noise source; if A2 also fails, the lane's sufficiency premise is dead on this stack as a whole.
* **Expected DTI improvement.** Unknown — stated honestly before the run: the deformation bands are
  among the weakest single features measured so far (H70 canary max alarm AUC 0.6687 across all 75
  features; the strain/EQ channels sit well below the surface channels in every round's feature
  ranking), so the prior is that A2's OOF AUC lands near the mixed View A's ≈ 0.52. The value of the
  test is *attribution* and the *falsification* of the lane on the deformation pair, not an expected
  lift. The holdout verdict rule below is what decides, not this expectation.
* **Implementation cost.** One store extension (17 new columns, idempotent) + the shared stages run
  unchanged with the A2 list substituted for View A (setup wrapper, no forked stage) + one
  round-specific holdout/build. Medium.

### H74-B — the brief's artifact clause as a veto, with A2 as the abstaining view — RANK 2, tested in E2

* **Layers.** View B operating ranks plus the A2/B disagreement stratum mask (no new physics).
* **Physical signature.** The brief's own reading: *"where B is confident and A is not, suspect
  surface artifacts such as roads or erosion lines."* With A2, "A is not confident" means no strain
  or seismicity support — a DEM/radiometric lineament with neither potential-field nor deformation
  support is more likely anthropogenic or erosional than tectonic.
* **Why catalogue-missing.** Roads, fence lines, erosion rills and lithologic strips are not faults
  and are absent from a fault catalogue by construction; vetoing them removes off-catalogue
  false-positive mass.
* **How it differs.** H70-B tested the same veto with the *potential-field* View A's abstention
  (measured negative: Δ −0.0074 [−0.0112, −0.0034], the veto removed real signal). H74-B re-tests it
  with the deformation view's abstention, a physically different abstention set.
* **Expected / cost.** Small, possibly negative, same as H70-B. One extra holdout arm (~10 min).

### H74-C — concordant ranking on the A2/B pair — RANK 3, tested in E2

* **Layers.** Both views' operating ranks.
* **Physical signature.** Strain/seismicity (A2) and DEM/radiometrics (B) are physically independent
  sensor families; agreement at one pixel is the strongest corroboration available on this pair.
* **Why catalogue-missing.** Independent-sensor agreement suppresses both catalogue-adjacent
  artefacts and single-view noise.
* **How it differs.** H70-C tested `min(rankA, rankB)` with the potential-field View A (measured
  0.1196, below single_B, Δ −0.0550). H74-C re-tests with A2; `union_max` on the A2/B pair is also
  measured as a control.
* **Expected / cost.** Between single_B and union_max; small. One extra holdout arm.

### H74-D — radiometric-cover gating of the A2-only stratum — RANK 4, deferred (budget)

* **Layers.** H74-A's stratum intersected with radiometric quiet (band 6 total count and `X_rad_*`
  line responses below local background), sharpening "buried beneath cover" to "no surface expression
  in any surface view".
* **Physical signature.** A covered, actively straining fault shows no lineament in DEM *or*
  radiometrics.
* **Why catalogue-missing.** Same mechanism as H74-A with a second independent surface family
  required to be silent.
* **Differs.** H70-D deferred this for the same reason; no round has gated an emission stratum by
  radiometric context.
* **Expected / cost.** Small second-order effect on a stratum already expected at random; medium
  cost. **Deferred**: not authorised in this round's 3-experiment budget.

### H74-E — cross-strike detrended strain offsets (H65 operator on bands 4/7/8) — RANK 5, deferred (needs its own feature build)

* **Layers.** The H65 operator (cross-strike symmetric difference, regionally detrended) applied to
  the strain bands 4/7/8 instead of bands 15/13.
* **Physical signature.** A fault's strain field is a step across strike; the H65 operator measures
  exactly that, on the deformation bands.
* **Why catalogue-missing.** Same blind-fault mechanism as H74-A, with strike-orthogonal
  sensitivity instead of gradient magnitude.
* **Differs.** H65 applied the operator to basement/gravity only; no round applied it to strain.
* **Expected / cost.** Unknown; high cost (new feature build + refit). **Deferred**.

---

## 2 · Experiments (budget: 3, per the brief's §6)

**E1 — store extension + canary + fit + independence (the brief's mandated tests, measured first).**
Extend the shared store once, idempotently, with the 17 H74 deformation columns (version tag
`+h74-deformation-v1`, manifest key `view_A2_deformation`; the canonical `view_A_with_external` and
`view_B_with_external` are untouched, so the H61 setup checks still run on the canonical lists).
Then run the **shared** H61 stages unchanged, with the View A list substituted by a setup wrapper (no
forked stage): `stage_canary` (raw single-feature AUC of every A2 and B feature on every fold's
held-out sample, alarm 0.90, plus the fitted top-5 canary; the brief's leakage canary), `stage_fit`
(both views, every fold; H61 sampler and learner unchanged), and the independence screen inside
`stage_exchange` (`spatial.negative_block_errors` on 50×50 px blocks of held-out catalogue-zero
negatives, then `spatial.independence`, abandon at |ρ| ≥ 0.60 — the brief's clause: *correlate each
view's spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are
strongly correlated*). The independence screen is measured **before** any pseudo-label is exchanged.

**E2 — exchange + sufficiency + matched-budget holdout (validates H74-A/B/C).** The shared
`stage_exchange` (exactly one confident-to-abstaining whole-segment pseudo-label round per direction
per fold; donor rank ≥ 0.95, receiver rank ∈ [0.35, 0.65], ≥ 5 px segments, ≤ 2,000 px per fold per
direction, wholly inside the training domain and disjoint from the evaluation region, hidden
components, visible catalogue + 4 px collar and sampled labels — the assertions in
`run_h61.stage_exchange` are kept), then the S1 sufficiency screen on View A2 (out-of-quadrant AUC,
gate mean ≥ 0.60 and min fold ≥ 0.55, reported for the verdict rule), then the matched-budget
hide-and-recover holdout with **nine** arms at exactly 9,400 dots per fold per arm, 3 px minimum
separation, pooled HOLDOUT-DTI with the 95 % paired 20 km-cluster bootstrap (1,000 draws):

| arm | field (ranks over the fold's allowed domain) |
|---|---|
| `single_A2` | `rankA2_pre` |
| `single_B` | `rankB_pre` (current comparable control; must reproduce 0.174517 ± 0.001) |
| `union_max` | `max(rankA2_pre, rankB_pre)` |
| `disagreement_pre` | `rankA2_pre − rankB_pre` |
| `disagreement_post` | `rankA2_post − rankB_post` |
| **`a_only` (H74-A candidate)** | `rankA2_post − rankB_post` gated to `rankA2_post ≥ 0.95` ∧ `rankB_post ∈ [0.35, 0.65]` |
| **`single_B_veto_Bonly` (H74-B)** | `rankB_pre` gated to NOT(`rankB_pre ≥ 0.95` ∧ `rankA2_pre ∈ [0.35, 0.65]`) |
| **`concordant` (H74-C)** | `min(rankA2_pre, rankB_pre)` gated to `rankA2_pre ≥ 0.95` ∧ `rankB_pre ≥ 0.95` |
| `random` | uniform over the allowed domain |

The emission domain is label-blind per fold: the 200 m exclusion ring is built from the fold's
**visible** catalogue only. An arm that cannot fill 9,400 dots invalidates the comparison and is
reported, not rescued. The verdict comparison is the paired bootstrap delta of each new arm against
`single_B`.

**E3 — build, gate, publish.** Build the round's GeoTIFF from the **H74-A strict A2-only
post-exchange field** (the lane's literal discovery candidate on the deformation pair), with the
placement of §3, the not-the-union check, the A-only geological-reasoning CSV for every emitted cell
(the brief: *write the geological reasoning for every A-only candidate* — for the deformation pair
the reasoning names strain/seismicity context and the anthropogenic/volcanic mimics), the uniqueness
gates (tier 1 exact vs every prior; tier 2 novelty vs informative priors), the lane gates (surface
before placement, dots after; literal and policy both reported), the on-disk validator,
`scripts/audit_uniqueness.py` with the census, and the run card. Publish to `docs/downloads/` and
the site with an explicit verdict. **No competition slot is spent; promotion is the separate selector
step.**

---

## 3 · Lane-valid constrained placement (H70 §3, unchanged)

The lane rule: STOP if more than 70 % of the candidate's dots fall within 3 px of **one** registry
raster's dots (or rank correlation > 0.90), checked on the surface before placement AND on the final
dots. On this registry the *literal* rule is saturated (measured, §0), so the repository's
authoritative verdict is the **policy** lane (informative priors only; universal-coverage probes
classified by measured 3 px coverage ≥ 0.95). H74 enforces the policy rule **by construction**:

1. Constrain **every** informative prior from the first placement (halo = its 3 px dilation).
2. The exact-novelty rule (declared post hoc in knowledge/39c, unchanged): no emitted cell is a
   positive pixel of any informative registry raster; this shrinks the allowed domain first.
3. Discover the largest feasible budget `n` by descending feasibility probes (coarse-to-fine over
   [40,000 … 2,000] dots; a probe places greedily in field-score order with 3 px minimum separation,
   skipping any dot that would push an informative raster's near-dot count over
   `cap = floor(0.70 × n)`, and reports how many dots it placed).
4. Adopt the largest feasible `n`; the emission is the first `n` placed dots. Because the greedy
   respects every cap at `cap = floor(0.70 × n)` and the emission is a prefix of the placement,
   every informative raster's near-dot share of the emission is ≤ 0.70 **by construction**. If no
   probe is feasible, adopt the largest placement any probe achieved, verify its shares with the
   TRUE emission size as the denominator, and publish it with the measured DUPLICATE label — a
   measured duplicate is a deliverable, not a rescued placement.

This is a uniqueness constraint, not a holdout-driven choice: it is applied identically to any
candidate built from here, and it does not use one label pixel.

---

## 4 · Thresholds (H61/H70 frozen values, unchanged; nothing is re-tuned)

canary alarm 0.90 · independence abandon |ρ| ≥ 0.60 · donor rank ≥ 0.95 · receiver rank interval
[0.35, 0.65] · fold buffer 80 px · block side 50 px · min pseudo segment 5 px · pseudo cap 2,000 px
per fold per direction · holdout budget 9,400 dots per fold per arm · min dot separation 3.0 px ·
catalogue exclusion 200 m · bootstrap 1,000 draws over 200 px (20 km) clusters · lane rank limit 0.90
· lane near-dot limit 0.70 at 3 px · probe coverage threshold 0.95 · S1 sufficiency mean ≥ 0.60,
min fold ≥ 0.55 · single_B control 0.174517 ± 0.001.

## 5 · Verdict rule (frozen; mirrors knowledge/54 §5)

The file is **eligible for the selector** only if ALL of: format gate PASS · lane gate PASS
(policy verdict; literal reported verbatim) · decoded-pattern uniqueness PASS (no identical prior,
novel_fraction ≥ 1.0 against informative priors, not the literal prior union) · not-the-union PASS ·
S1 sufficiency PASS (View A2 mean OOF AUC ≥ 0.60 and min fold ≥ 0.55) · holdout: the candidate arm
beats `single_B` with the paired 95 % CI of the delta above 0. Even then nothing is promoted and no
slot is used — promotion is the separate selector step, within the weekly cap. Otherwise the verdict
is **negative / research-only**: DOWNLOAD yes (format-valid and unique), SUBMIT no. Negative results
are deliverables.

## 6 · Labels used in every H74 number

* **HOLDOUT-DTI** — evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel,
  withheld-positive count, 95 % paired cluster-bootstrap CI. A simulator number, never a leaderboard
  score.
* **PREMISE-AUC / diagnostic AUC** — out-of-quadrant AUC on `label-blind-quadrants-v2`; not a DTI
  score.
* **ORGANIZER-CONFIRMED** — only a score copied from a submission-page receipt. None exists in this
  repository; every board number here is PUBLIC BOARD or OWNER-REPORTED.
* **SYNTHETIC** — operator checks on generated grids.

## 7 · The 0.2778 question (answered at PhD level; full algebra in `knowledge/49`)

The owner-reported 0.2778 file (`data/reference/h33-2-b2-zeros.tif`, SHA-256 pinned) is a **strict
subset** of the owner-reported 0.2600 file with its 100–200 m catalogue ring deleted: 6,436 px
removed, all inside the ring, +6.8 % relative score. Under `DTI = TPw / (0.2·FPw + 0.8·FNw)` with
`FNw = |G| − TPw` exactly, mass within 200 m of a mapped trace earns no credit and pays the
false-positive tax; binary {0,1} mass is metric-optimal at fixed support; and the marginal rule
`ρ_marginal > α·DTI` puts the bar at 0.0556 — a *distance* (emit only within 224 m of an uncatalogued
fault pixel). The champion is the correct stopping point of its own field, not a better detector:
across the family's five scored files Spearman(mass, board) = −1.0000. Beating it needs sustained
ρ ≈ 0.16 at 37,654 px (0.3195) or ρ ≈ 0.19 (0.3774) — a better ranker, which this repository has
measured seven separate ways that it does not have (`knowledge/49` §4c). The Final Prize Round
($250k) instead rescores against an **expanded, expert-verified** label set, so a file whose every
emitted cluster carries written, falsifiable geological reasoning is worth more there than a
marginally better public-chunk DTI — which is why this round writes the A-only reasoning record even
if the verdict is negative. The attribution of 0.2778 to `h33-2-b2` is OWNER-REPORTED, NOT
ORGANIZER-CONFIRMED.

---

## 8 · Rename record (identifier-only; no measured number, threshold or conclusion changed)

This round was first frozen as **H72** in this session (2026-10-09, ~17:05Z; preregistration
`knowledge/59_hypotheses_H72_preregistered.md`, runner `scripts/run_h72.py`) and was completed in full
(three experiments, unique GeoTIFF built, gates measured) before the branch was pushed. At merge time,
parallel sessions' rounds had already merged to `main` and one of them had taken the number H72
(`knowledge/59_hypotheses_H72_preregistered.md` on `main` — a *strain-only* View A protocol: raw bands
4/7/8 alone, no derived transforms, no seismicity channels, **no file emitted**; merged via PR #67),
followed by an H73 round. This session's round was therefore renamed **H74** with identifier-only
edits: `h72→h74`, `H72→H74`, knowledge 59/60/60b → 63/64/64b, `evidence/` and `docs/data/` `h72_*` →
`h74_*`, `scripts/run_h72.py`/`publish_h72_site.py` → `run_h74.py`/`publish_h74_site.py`,
`tests/test_h72.py` → `test_h74.py`, `src/gems52/h72.py` → `h74.py`, submission prefix
`gems52-h72-` → `gems52-h74-`, `IR-H72-001` → `IR-H74-001` (IR-H74-002 records the collision). The
shared-store extension tag was `+h72-deformation-v1` at run time and is `+h74-deformation-v1` after
the rename; the git-ignored store was rebuilt cleanly (`structural.build` is deterministic, so the
columns are byte-identical) and the features-stage receipt regenerated. The two H72-labelled rounds
are **distinct protocols**: `main`'s H72 isolates the three raw strain bands and emitted no file;
H74 is the H70-E variant exactly as preregistered in `knowledge/54` — a deformation-only View A2 of
strain bands 4/7/8 **plus** seismicity bands 10/16 with gradient/coherence transforms (22 channels) —
and it built the round's GeoTIFF. No measured number, threshold, gate or conclusion changed.
