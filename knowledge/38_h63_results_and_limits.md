# H63 — results and limits (2026-10-09)

**Verdict: NEGATIVE.** The step-normalised View A does **not** regain transferable skill: its mean
out-of-fold AUC inside a held-out quadrant is **0.5362** against the preregistered sufficiency bar
of 0.60 (H61's raw-value View A measured 0.5163 on the identical splitter — the step
parameterisation bought +0.0199). The disagreement arm is significantly **worse than every control
including uniform random**, and the single pseudo-label exchange transferred nothing. A negative
result is a deliverable: this document records it, and the artefact is published research-only
(DOWNLOAD YES · SUBMIT NO · slots used 0).

Preregistration: [knowledge/37_hypotheses_H63_preregistered.md](34_hypotheses_H63_preregistered.md),
pinned by `registry/h63_preregistration.json` (SHA-256
`41dabafd63235695759c731b3daacb33b54790f7f54a96a8414efdcdd39f411e`) before the first fit.
Receipts: `evidence/h63_{canary,fit_checkpoint,independence,pseudo_exchange,holdout,projection,lane_surface,lane_dots,submission,run_card}.json`.

---

## 1 · The question H63 was built to answer

H61 §8 item 1: *change what View A is.* H61 measured a View A built from raw potential-field band
values at mean out-of-fold AUC **0.5163** (in-sample 0.948) — chance out of quadrant — against
View B's **0.6843**. Blum–Mitchell sufficiency failed, so the A→B pseudo-label transfer handed over
noise and the disagreement arm scored below every control. H63 rebuilt View A as a physically
parameterised view: matched step/persistence columns of the three subsurface fields (band 13
`iso_grav_anom`, band 15 `depth_to_base_surf`, band 2 `rtp`) at σ = 3, offsets 200 m / 400 m, plus
the template's local-contrast channels and the upward-continued TMI — **38 channels, no raw band
values** — and measured the sufficiency screen **before** any exchange.

## 2 · Measured results

All AUCs are **HOLDOUT-DTI diagnostics (not DTI scores)** on `label-blind-quadrants-v2` (whole
8-connected catalogue components hidden, 80 px buffer). All DTI numbers are **HOLDOUT-DTI**,
evaluator `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel, pooled TPw/FPw/FNw,
95 % paired 20 km-cluster bootstrap, 1,000 draws), **53,186 withheld positive pixels**, every arm
placed at exactly **9,400 dots per fold** at 3 px minimum separation (matched budget — the
comparison is eligible).

### 2.1 Sufficiency screen (measured before any exchange)

| fold | View A in-sample AUC | View A OOF AUC | View B in-sample AUC | View B OOF AUC |
|---:|---:|---:|---:|---:|
| 0 | 0.8317 | 0.5270 | 0.8762 | 0.6623 |
| 1 | 0.7859 | 0.5803 | 0.8346 | 0.7646 |
| 2 | 0.7926 | 0.5096 | 0.8523 | 0.6186 |
| 3 | 0.7850 | 0.5280 | 0.8479 | 0.6994 |
| **mean** | 0.8013 | **0.5362** | 0.8544 | **0.6862** |

View A (H63 step-normalised) **0.5362** vs the 0.60 bar: **sufficiency premise not met.**
H61's raw-value View A: 0.5163 (per-fold 0.4668–0.6011). The step parameterisation moved View A by
+0.0199 and did not cross the bar. View B is unchanged (0.6862 vs H61's 0.6843 — same view, same
splitter, so the protocol is exactly comparable).

### 2.2 Canary (leakage)

Raw single-feature AUC of all 75 channels on every fold's held-out sample (held-out positives +
catalogue-zero proxies ≥ 5 px from any visible trace): maximum **0.6679** (`B_slope_grad_3`, fold 1)
against the 0.90 alarm. Fitted single-feature canary on the five strongest: maximum **0.6648**.
**No alarm fired.** Catalogue-zero pixels are proxies, not verified fault absence.

### 2.3 Independence and the exchange

`spatial.negative_block_errors` on 50×50 px blocks (min 32 negatives) of held-out catalogue-zero
proxies, then `spatial.independence`: max |ρ| = **0.1817** over **2,089 blocks** (abandon at 0.60) —
the conditional-independence premise **held**, so the exchange was allowed and executed: exactly one
confident-to-abstaining whole-segment round per direction per fold, **15,989 pseudo pixels** total
(2,000 / 1,998 / 1,999 / 1,999 / 1,996 / 1,997 / 2,000 / 2,000 across the eight directions), each
segment ≥ 5 px, wholly inside the training domain and one 50×50 block, disjoint from the evaluation
region, hidden components, visible catalogue + 4 px collar, and sampled labels.

### 2.4 Holdout — matched-budget six-arm comparison

| arm | HOLDOUT-DTI | 95 % CI |
|---|---:|---:|
| single_A | 0.084788 | [0.070929, 0.098329] |
| single_B | 0.174193 | [0.151520, 0.193642] |
| union_max | 0.151308 | [0.132069, 0.169142] |
| disagreement_pre | 0.040620 | [0.032044, 0.050132] |
| **disagreement_post (candidate)** | **0.040257** | **[0.032106, 0.048664]** |
| random | 0.078257 | [0.068163, 0.087930] |

Paired differences against the candidate (95 % CI):

| comparison | Δ DTI | 95 % CI |
|---|---:|---:|
| disagreement_post − single_B | **−0.133937** | [−0.155362, −0.110948] |
| disagreement_post − union_max | −0.111051 | [−0.128694, −0.091269] |
| disagreement_post − single_A | −0.044531 | [−0.054732, −0.034262] |
| disagreement_post − random | **−0.038000** | [−0.045197, −0.029797] |
| disagreement_post − disagreement_pre | −0.000364 | [−0.003877, +0.002754] |

**Reading.** (1) The candidate is significantly worse than the best single-view control
(`single_B`, 0.1742), worse than the union (0.1513), worse than `single_A` (0.0848), and — decisively
— **worse than uniform random** (0.0783): the disagreement field actively selects pixels that do not
recover withheld structure. (2) The exchange transferred nothing: post vs pre differs by −0.0004
with a CI spanning zero, i.e. the pseudo-labels changed no ranking that mattered. (3) This is the
second consecutive negative co-training round with the same signature: when View A is at chance out
of quadrant, "A confident, B abstaining" is a selector for *A's errors*, and the emitted mass lands
where View B (the view that actually transfers) is ambivalent.

### 2.5 Not-the-union check

The shipped field is `rank(A) − rank(B)` of the post-exchange mosaic, placed by `spacing_select`
at 3 px. Against separately emitted controls at the same budget (per fold, cells differing):

| fold | vs single_A emission | vs single_B emission | vs union_max emission | Spearman(field, union) |
|---:|---:|---:|---:|---:|
| 0 | 18,266 | 18,800 | 18,446 | −0.034 |
| 1 | 18,154 | 18,800 | 18,406 | −0.084 |
| 2 | 17,922 | 18,794 | 18,278 | −0.097 |
| 3 | 18,106 | 18,800 | 18,366 | −0.052 |

The emission is not `max(A, B)`, not either single view, and not their union: a high-A/middle-B pixel
and a high-A/high-B pixel share a union score but differ in disagreement score. **PASS.**

### 2.6 Artefact, gates and projection

Filled in from the build receipts (`evidence/h63_submission.json`, `evidence/h63_lane_*.json`,
`evidence/h63_projection.json`, `evidence/h63_run_card.json`) — see the site audit page
(`docs/h63-audit.html`) for the rendered tables. Headline: format gate PASS (single-band float32,
values exactly {0,1}, 0 NaN/Inf, EPSG:32611, 3,730 × 3,292, transform identical to the pinned
sample, all mass > 200 m from any mapped trace inside the sample footprint); decoded-pattern
uniqueness PASS against the 548-raster registry (526-blob census re-materialised and SHA-verified,
plus this repository's own artefacts, own round excluded); not-the-union PASS. **Projection, never a
score:** at 37,600 dots the break-even credit density to match the owner-reported champion 0.2778 is
0.0907–0.1295 per pixel; the candidate's only empirical density estimate comes from a simulator that
measured Spearman −0.10 against the owner-reported board in R4, and its holdout density (≈ 0.040 DTI
at matched budget) projects far below the champion at both ends of the measured |G| interval
[5,949.3, 12,512.1] px. **Verdict: negative — DOWNLOAD YES · SUBMIT NO.**

## 3 · What H63 establishes (and what it does not)

**Established, measured:**
1. The template's matched step filter transfers to the subsurface fields mechanically (finite,
   zero outside the footprint, plane-detrended, sign-invariant — pinned by `tests/test_h63.py`).
2. As a *view*, the step-normalised potential-field channels still do not transfer between
   quadrants: mean OOF AUC 0.5362, statistically indistinguishable from H61's raw-value View A
   (0.5163) and far below View B (0.6862). Two different parameterisations of View A — raw values and
   step/persistence transforms — both fail sufficiency on this data.
3. The Blum–Mitchell conditional-independence premise holds (max |ρ| 0.18), so the negative verdict
   is **not** an independence failure: it is a sufficiency failure. Co-training cannot rescue a view
   that carries no out-of-quadrant signal, however the view is parameterised.
4. The disagreement direction "A confident, B abstaining" is, on this data, an *anti*-signal: it
   scores below uniform random. Any future round that emits A-only mass on this evidence would be
   spending a slot on measured negative density.
5. The pipeline, gates and publication path work end to end on the repaired instruments: canary →
   fit → sufficiency screen → independence → one exchange → matched-budget holdout → placement →
   surface and dots lane gates → uniqueness → not-union → projection → verdict → site, with the
   incumbent pointer untouched (`submission/LATEST.txt` stays on H60; H63 publishes
   `submission/H63_LATEST.txt` and `docs/data/submission_h63.json`).

**Not established:** whether *any* potential-field view can be made sufficient on this data (two
parameterisations failed; a third is not ruled out). Whether buried faults exist that neither view
senses. Whether the champion's 0.2778 exists as an organiser-confirmed score (attribution remains
FILENAME-ONLY-OWNER-REPORTED).

## 4 · Limitations, stated plainly

- The sufficiency screen is a quadrant-transfer test, not a physics test: a view could be
  physically meaningful and still fail it if the catalogue's hidden components are not spatially
  representative of the hidden truth (selection bias in the hide-and-recover protocol).
- The holdout simulator measured Spearman −0.10 against the owner-reported board in R4. It screens
  procedures; it cannot promote or certify anything.
- Inputs are SHA-256-pinned owner mirrors of a login-walled portal file; pins prove mirror
  consistency, not organiser authentication. No organiser receipt, weekly allowance or leaderboard
  observation was available in this sandbox.
- External radiometrics are uint8 percentile quantisations derived by the owner's CI from the USGS
  GeoDAWN release; USGS, GDR and DrivenData hosts are unreachable from this sandbox.
- The step/persistence transform is a contrast-and-continuity feature, not a fault detector: it
  fires on any localised cross-strike contrast (measured: an isolated blob responds as strongly as
  a step edge), and its persistence term discriminates weakly between short segments and long edges
  at the scales tested (ratios 0.99 vs 1.00). Flight-line artefacts in the airborne survey remain a
  named mimic.
- Fault candidates are not geothermal vents, and neither establishes permeability or a reservoir.
  No geologist reviewed any emitted structure; the reasoning CSV is measured context plus a template
  hypothesis and a named non-fault mimic.
- Memory/time: the whole round ran on 2 cores / 3 GB in well under the 2-hour budget.

## 5 · Next, in priority order

1. **Stop spending the co-training lane on View A parameterisations.** Two measured failures
   (raw 0.5163, step 0.5362) say the potential-field channels as compiled do not carry
   quadrant-transferable fault signal at 100 m. The lane's own falsification condition has fired
   twice.
2. **Run the B-only direction (H63-B, preregistered rank 2).** Where B is confident and A abstains,
   the brief names roads/erosion lines — but a subset may be real scarps in homogeneous alluvium
   that geophysics cannot see. `single_B` is the only view that transfers (0.6862 OOF AUC; 0.1742
   HOLDOUT-DTI, the best measured arm in either round). This is the cheapest untried *emission*
   direction in the lane and it needs the optional H2/H55 profile store plus its own preregistered
   holdout.
3. **Run H61-D / H63-E: cross-file credit localisation by terrain stratum.** Cross the LP atoms
   with slope, modelled cover thickness and radiometric alteration strata so the organiser's own
   scores say *where* hidden truth sits. No new data; it converts owner-reported scores into a
   placement prior without emitting a duplicate.
4. **Acquire sub-100 m topography (H63-D) when egress allows.** USGS 3DEP 1 m DEM over the GeoDAWN
   footprint (https://www.usgs.gov/3d-elevation-program) is the specific free official source; it
   was unobtainable this session (usgs.gov unreachable).
5. **Authenticate one receipt.** A single submission-page receipt tying a file SHA-256 to a score
   would settle whether 0.2778 exists at all (IR-H61-004). No credentials may be requested or
   stored in chat.
6. **Give the selector a priced option.** The only mass measured above the break-even density is
   inside the champion family, and emitting it is a duplicate by construction. That trade belongs
   to the selector with the weekly cap in front of it.

## 6 · AI-use disclosure

An AI assistant wrote the code, this protocol, the results document and the candidate-review
templates. No geologist verified any emitted structure, no field observation was collected, and no
organiser score, acceptance or leaderboard gain is claimed for any H63 artefact.
