# 98 · H97 results and limits — thermal-gap co-training

Round H97 · session `arena/86f85e87-gemsdoe52` · 2026-10-10/11 UTC.
Preregistration: `registry/h97_preregistration.json`
(SHA-256 `8cd93f2290d002c82b9770887f79a220352aeb42a94c238b713abaaf5f6bad1f`, frozen before any fit),
prose twin `knowledge/97_hypotheses_H97_preregistered.md`. Brief: `knowledge/99`.

**Verdict: NEGATIVE — download YES (research artifact), submit NO. Experiments 3 of 3, submission
slots used 0.**

Run card: `evidence/h97_run_card.json`. Artifact:
`submission/gems52-h97-thermal-gap-cotrain-25400px-20261011T003946Z-44f30af5-zeros.tif`
(108,930 bytes, SHA-256 `939d69ac3357ba7d69058c8163667830a4f79fcb8d1c30be1a8a1b0ddf80912d`).

---

## 1. What was asked and what was measured

The round's mechanism: a hot spring, or a well whose geothermometry indicates a high reservoir
temperature, that the **visible** fault catalogue cannot explain (> 3 px ≈ 300 m from the nearest
mapped fault) is surface evidence of a fault that is **absent from that catalogue**. Co-training
gates the emission: View A confident + View B abstains ⇒ buried candidate (emit); View B confident +
View A abstains ⇒ surface artefact (veto).

**HOLDOUT-DTI** (`gems52-pooled-hide-v1`, 60,894 withheld positive pixels, 4 whole-component
label-blind quadrant folds, 9,400 dots per fold per arm, α 0.2 / β 0.8 / R 300 m, paired 20 km
spatial-cluster bootstrap):

| arm | HOLDOUT-DTI [95 % CI] | dots/fold |
|---|---|---|
| `single_A` | **0.076401** [0.064559, 0.089127] | 9,400 |
| `random_gap_full` | 0.075335 [0.066538, 0.084143] | 9,400 |
| `thermal_gap_cotrain` **(PRIMARY)** | 0.074709 [0.062414, 0.088008] | 9,400 (867 gap + fill on fold 0) |
| `random_uniform` | 0.074972 [0.066432, 0.083875] | 9,400 |
| `cotrain_bi` | 0.074035 [0.061951, 0.087453] | 9,400 |
| `single_B` | 0.054311 [0.043245, 0.066025] | 9,400 |
| `thermal_gap` | 0.003977 [0.002581, 0.005748] | 867/291/81/85 = 1,324 total |
| `thermal_gap_line` | 0.003977 [0.002581, 0.005748] | 1,324 total |
| `random_gap` | 0.003237 [0.002443, 0.004115] | 1,324 total |

Paired differences against the primary:

| comparison | paired Δ | 95 % CI | reading |
|---|---|---|---|
| `random_gap` (count-matched control, frozen claim) | **+0.071471** | [+0.058852, +0.085253] | CI excludes 0 → **frozen claim satisfied** |
| `random_gap_full` (mass-matched control) | **−0.000627** | [−0.013423, +0.012889] | CI includes 0 → **indistinguishable from random** |
| `random_uniform` | −0.000264 | [−0.012854, +0.012160] | includes 0 |
| `single_B` (the brief's single-view yardstick) | +0.020398 | [+0.004170, +0.037294] | composition > View B alone |
| `single_A` | −0.001692 | [−0.004436, +0.000684] | includes 0 |
| `cotrain_bi` (field alone, no thermal gating) | +0.000674 | [−0.000662, +0.001901] | includes 0 → **the gap dots add nothing beyond the field** |

**Promotion bar 0.192829** (`evidence/h82_holdout.json`, H82 `B_DVA2`) → **FAIL** by a factor of 2.6.

Gates: independence **PASS** (max |r| 0.070877 over 2,283 spatial blocks, abandon at 0.60 — so the
Blum & Mitchell premise is not the reason this round failed); leakage canary **PASS** (max
single-feature out-of-quadrant AUC 0.597283, `topo_edge`; alarm 0.90); format **PASS**; uniqueness
**PASS** in exact-pixel terms (193 priors, novel fraction 0.357717, identical to none);
lane-surface **PASS** (max Spearman 0.114786); **lane-dots DUPLICATE/STOP**;
not-the-union **PASS** (Jaccard 0.110322 against the views' spaced top-k union, 17,848 dots outside
it, buried-dominant fraction 0.386969).

## 2. Why the round is negative — three separate readings, all in the same direction

1. **The frozen claim is satisfied and is not evidence.** `random_gap` emits only the gap-dot count
   (1,324 dots over four folds) while the primary fills to 9,400. DTI's denominator carries
   `0.2·S`, so the count-matched comparison is dominated by mass, not by skill. Against the
   mass-matched control the difference is −0.000627 [−0.013423, +0.012889]. The "+0.071" is a
   denominator artefact (IR-H97-002).
2. **The gap dots alone are worse than random at the same count.** `thermal_gap` 0.003977 vs
   `random_gap` 0.003237 — i.e. within noise of each other, and both ~20× below the arms that fill
   the full budget. The gap population is 1,106 sites, ~0.09 % of the dots at the 9,400-dot budget,
   so it cannot move a pooled number by itself; what it *can* do is fail to be better than chance,
   and it does fail.
3. **On the prevalence-matched off-catalogue instrument the composition is *worse* than random.**
   `gems52-offcat-prevalence-h97`: SGMC fault pixels > 3 px from `labels.tif`, thinned by whole
   8-connected components (seed 9700) to 14,101 px, i.e. matched to the `|G|` bracket of the metric
   inversion. Credit density `T/S` at the 9,400-dot budget: `single_B` 0.0361, `random_matched`
   0.0157, `single_A` 0.0134, `thermal_gap` 0.0131, `cotrain_bi` 0.0097, `thermal_gap_cotrain`
   0.0073, `shipped_composition` 0.0097. The composition is at half of random. (Ranking evidence
   only — this instrument never chooses a budget; IR-H95-003.)

Two further diagnostics worth keeping:

* **The mass curve of the shipped ranking is flat** (credit density by budget 2,000 → 0.0104,
  5,000 → 0.0107, 9,400 → 0.0097, 15,000 → 0.0104, 25,000 → 0.0103, 40,000 → 0.0099,
  60,000 → 0.0089, 90,000 → 0.0086). A rising off-catalogue DTI with budget is therefore mechanical
  (`S` approaching the truth footprint), not ranking skill. This is the cleanest available
  demonstration that a budget sweep on this instrument cannot certify a detector.
* **`thermal_gap_line` placed exactly the same dots as `thermal_gap`** on all four folds (1,324
  dots), so the strike-line projection added nothing — a negative on that sub-mechanism.

## 3. The lane-dots failure, and why it is structural (IR-H97-003)

`gates.lane_report(..., phase="dots")` returns **DUPLICATE/STOP** twice:

* literal: 0.9889 of the H97 dots lie within 3 px of
  `data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`. That file is a **regular 5 px
  lattice** (746 unique rows × 659 unique columns, exactly 5 px apart, 206,895 cells) whose 3 px
  dilation covers 99.90 % of the eligible footprint; the shared tool itself classifies it as a
  `universal_coverage_probes` entry. The literal line is uninformative against any dense emission
  (IR-H97-001).
* policy (probe excluded): 0.8749 within 3 px of **this repository's own H96 file**
  `gems52-h96-bidir-cotrain-coverstep-25400px-…-zeros.tif`. This one is real. The round registered
  "Views/field = H96 spec (reused, not forked)" and `gems52.nodes.spacing_select` is a deterministic
  greedy, so the same field at the same or a smaller budget re-emits a **prefix** of the H96 dots.
  The composition is therefore a lane near-duplicate of the H96 artifact **by construction**, while
  its exact-pixel novelty (0.3577) is real.

Consequence: this artifact may be downloaded and studied but not submitted. The fix is a
registration-time constraint, not a placement tweak: the next round must register either a **quota
placement** or a **sub-halo budget** for any field that has already been shipped, before the fit.

## 4. What this round changes about the bigger picture

* The thermal-gap population is real (1,106 evidence sites unexplained by the visible catalogue) but
  **it is not a detector**: it is 1.5 orders of magnitude too small to carry a submission, and where
  it does place dots it does no better than chance.
* **View A alone is not a detector either**: `single_A` 0.076401 is inside the noise band of
  `random_uniform` 0.074972 and `random_gap_full` 0.075335, on this instrument, for the third round
  running. The standing hypothesis that the buried population is what View A should win is *not*
  supported by this instrument.
* **View B remains the only arm with any off-catalogue credit density above random**
  (0.0361 vs 0.0157 = 2.3×), and it is still far below what the mass lever needs
  (`knowledge/76`: 0.3195 needs credit density 15.95 % at 37,654 dots).
* The honest gap to the board is unchanged: nothing measured in H97 (or H95/H96 before it) supplies
  the ×1.15–1.36 enrichment that beating 0.3195 / 0.3774 requires.

## 5. Limits

1. **Neither instrument is the organiser's set.** The holdout measures *withheld catalogue* faults;
   the off-catalogue instrument measures *SGMC-mapped* faults far from the catalogue. The
   organisers score newly discovered faults reviewed by an expert panel. A detector can be
   negative on both and still be valuable on the third, and vice versa; no number here is
   ORGANIZER-CONFIRMED.
2. **The gap population is small** (1,106 sites; 1,324 dots over four folds), so the arm's confidence
   interval is wide and its per-fold counts are lumpy (867 / 291 / 81 / 85). The negative is a
   *no-signal* statement, not a precise null estimate.
3. **The 0.192829 bar comes from a different fold set** (53,186 withheld positives in H82; 60,894
   here), so the comparison is directional, not exact (IR-H94-002, carried).
4. **Placement is a heuristic.** `spacing_select` at 3 px is not a proven optimum; the H85 ablation
   is the only evidence in this repository (knowledge/78 §2).
5. **The shipped file is unusable as a submission** for two independent reasons (bar, lane), so this
   round advances the *research* state and not the *leaderboard* state.

## 6. Remaining work (ranked, with the constraint that each must beat the bar or show a
board-anchored gain before a slot is spent)

1. **Register placement that cannot reproduce a shipped file**, then re-test the strongest existing
   field: quota placement or sub-halo budget, registered *before* the fit (IR-H97-003).
2. **Mass lever on the champion family** — the only lever with board-sign evidence
   (Spearman(mass, score) = −0.928). It is currently blocked by the lane rule because any subset of
   the champion's field lies within 3 px of the champion's own dots; it needs an explicit owner
   decision on the 70 % rule or a genuinely displaced placement, not a re-emission.
3. **Tilt-depth / wavelet multi-scale edge of the RTP magnetics** (H92-A, H89-W): the top-ranked
   untried ranking ideas in `knowledge/92`, and the only ones with a physical mechanism for
   *buried* structures that the surface view cannot see. Register them with the placement constraint
   above.
4. **Road/drainage artefact screen** for B-only dots (the brief's named mimics), and the
   cardinal-azimuth/fall-line test, still not run.
5. **Do not re-litigate**: co-training as a discovery mechanism (four measured negatives: H87-era,
   H95, H96, H97), View A as a learner (failing sufficiency since H88), the count-matched control
   design (IR-H97-002), and thermal-gap emission (this round).

## 7. Reproduction

```
python3 scripts/prepare_data.py                    # audit restored bytes -> evidence/grid.json
python3 scripts/restore_data.py --target-dir data  # 23 pinned rasters (needs gh auth)
python3 scripts/run_h97_thermal_gap.py views       # 144 s
python3 scripts/run_h97_thermal_gap.py holdout     # 188 s
python3 scripts/run_h97_thermal_gap.py offcat      #  56 s
python3 scripts/run_h97_thermal_gap.py build       #  79 s
python3 scripts/run_h97_thermal_gap.py write 25400 # ~330 s
python3 scripts/h97_irregularities.py && python3 scripts/h97_supplemental_closure.py
python3 scripts/publish_h97_site.py && python3 scripts/check_site.py
```

Runner SHA-256 is recorded in `evidence/h97_gates.json` (see `h97_supplemental_closure.py`) so a
receipt can be matched to the code that produced it (IR-H97-004).

## 8. The three required passes, and what each one caught

**Pass 1 — implement.** Views, holdout, off-catalogue instrument, build, write and the site receipts
were produced by `scripts/run_h97_thermal_gap.py` against the frozen registration
(SHA-256 `8cd93f22…`, hash-gated: the runner refuses to run if the registration changed).

**Pass 2 — bug and edge-case review.** Three defects were found and fixed *before* anything was
published (all recorded in `registry/irregularities.json`):

1. **A stale receipt** (IR-H97-004): the first `holdout` JSON was written by a process launched
   *before* the arm redesign, so the receipt described arms the file no longer contained. Caught by
   comparing `json.load(...)['arms']` with the script; fixed by re-running and by recording the
   runner's SHA-256 in `evidence/h97_gates.json`.
2. **Spacing inconsistency** (IR-H97-005): two call sites used `min_px=1.0` while the registration
   fixes the placement minimum at 3.0 px, so the measured primary was not the registered
   composition. Fixed in both places before the reported run.
3. **A control that was not a control** (IR-H97-002): the frozen count-matched comparison is
   satisfied by construction at these budgets. Fixed by adding a mass-matched control and reporting
   both, which converts an apparent +0.071 into a −0.0006.

**Pass 3 — full re-check against the original request.** Every numbered item of the standing brief:

| # | requirement | where it stands |
|---|---|---|
| 1 | review the repo; explain 0.2778 at PhD level; say whether a higher-scoring unique submission is producible | `knowledge/76` + README §"Why `h33-2-b2` scored 0.2778" + this document §2/§4: the derivation is reproduced and the answer is **not yet demonstrated**, with the two live levers named |
| 2 | MUST generate a unique TIF; obvious on the site whether OK to download/submit; single-band, matching CRS/shape/transform, values in [0,1], unique name, ≤140-char note | artifact written (`939d69ac…`, 25,400 cells, 1 band float32, EPSG:32611, 3730×3292, 0 NaN, 0 inf, note 136 chars); `docs/index.html` and `docs/h97.html` open with **OK TO DOWNLOAD: YES / OK TO SUBMIT: NO**; exact-pixel novelty 0.3577 over 193 priors and not identical to any of the 526 censused sibling blobs |
| 3 | co-training lane; conditional independence tested on labelled negatives; abandon if correlated; pseudo-label only on one-confident/other-abstains; A-only reasoning written; compare to single-view baseline; not merely the union | independence max \|r\| 0.070877 (< 0.60) → exchange allowed; single-view baseline `single_B` 0.054311 vs primary 0.074709 (+0.020398 [+0.004170, +0.037294]); every one of the 25,400 emitted cells has a row in `docs/downloads/h97-a-only-reasoning.csv`; not-the-union Jaccard 0.110322 with 17,848 dots outside the views' union |
| 4 | lane-drift check on the surface **and** on the final dots; reuse the shared tools; label every number HOLDOUT-DTI or ORGANIZER-CONFIRMED; leakage canary | surface PASS (max Spearman 0.114786); dots **DUPLICATE/STOP** and reported as such rather than hidden (IR-H97-003); no private forks — the round only *used* `spatial`, `evaluate_holdout`, `nodes`, `gates`, `submission_writer`; canary max AUC 0.597283; nothing in this round is ORGANIZER-CONFIRMED |
| 5 | beat 0.3195 / 0.3774 with something new | not achieved; H97 is the fourth measured negative on co-training and the first on thermal gating, and the remaining levers are ranked in §6 |
| 6 | autonomous; official sources only; no hallucinations; ≥3 passes; PR to `main`; limitations and remaining work | every number in this document is read from a receipt in `evidence/`; the two external sources used are the organisers' own problem description and the COLT '98 paper; §8 (this table) is the third pass; the PR and the merge are recorded in the repository history |

## 9. Post-publication closure: the full 526-blob sibling census, and a repair to the lane rule

After the round's own gates ran, the frozen sibling census (`evidence/ctd5_prior_inventory.json`,
526 aligned single-band prediction blobs published across the owner's sibling repositories,
generated 2026-10-08) was **materialised in this sandbox** with the shared tool
`scripts/fetch_prior_inventory.py`: 526/526 blobs present, **0 errors**, 524 eligible blobs verified
against the census' own SHA-256 column (the 2 unverified entries are the census' own
`eligible: false` rows). The shared `gates.uniqueness_report` and `gates.lane_report` were then run
against all of them by `scripts/h97_supplemental_closure.py` (`evidence/h97_gates.json`).

**What the census changes.**

| measurement | against the 193 rasters on disk | against the 526-blob census |
|---|---|---|
| identical to any prior (file bytes or decoded band) | no | **no** |
| novel fraction (dots outside the union of supports) | 0.3577 | **0.0000** |
| max Jaccard against any single prior | small | 0.0173 (`2e8651d8…`) |
| lane-dots verdict | DUPLICATE/STOP | **DUPLICATE/STOP** |

The novel fraction collapsing to **0.0000** is not a new failure of this candidate: the census
contains dense lattice probes (e.g. `13gems … r13-lattice-s5`, whose own 3 px halo covers 0.9985 of
the eligible footprint), and the *union* of 526 sibling rasters covers the field. The lesson is that
"novel fraction" is a statement about the **prior set**, not about the candidate, and must always be
quoted with the set it was measured against.

**The repair (shared tool, additive; IR-H97-006).** The brief's dot-proximity arm is a fixed 0.70 on
the raw near-3 px fraction, which is only informative if the prior localises anything. Measured on
this round's raster:

| prior | prior px | its own 3 px coverage | our near-3 px fraction | **lift** | raw rule |
|---|---|---|---|---|---|
| this repository's **H96 file** | 25,400 | 0.0756 | 0.8632 | **11.42×** | STOP (correct) |
| `13gems` 5 px lattice (probe) | 206,895 | 0.9985 | 0.9863 | 0.988× | STOP (artefact) |
| `13gems-composite` (13GEMSDOE) | 507,776 | 0.8133 | 0.7783 | 0.957× | STOP (artefact) |
| champion `h33-2-b2` | 37,654 | 0.1369 | 0.1824 | 1.332× | pass |
| `d2-8` family (0.2600) | 44,090 | 0.1568 | 0.1868 | 1.191× | pass |
| H95 file | 37,654 | 0.1304 | 0.1426 | 1.093× | pass |

`gems52.gates.lane_report` now also returns `near_3px_lift` per prior,
`max_near_3px_lift`/`max_lift_source`/`max_lift_coverage`, `lift_offenders` (lift > 2.0) and a
`coverage_normalization` note. The **literal and policy verdicts are byte-for-byte unchanged**, so
every earlier round's recorded verdict still reproduces (73 gate/lane/uniqueness tests pass).

The normalised reading of this round: **one genuine concentration, 11.42×, against our own H96
file** — which is exactly IR-H97-003 — and two artefactual trips of the raw rule at lift < 1. The
verdict does not change (both rules stop), but the *reason* is now the right one.

## 10. Correction: a lift is only evidence when the raw rule also fires

The first version of the lift statistic maximised `near-fraction / coverage` over **all** priors and
reported 13.07× against a censused blob whose 3 px halo covers 0.00012 of the footprint — i.e. from
**41 of 25,400 dots**. That is a coincidence ratio, not a duplication signal, and publishing it would
have been a genuine error. The rule was therefore conditioned:

> an **offender** must trip the raw rule (`near-fraction > 0.70`) **and** survive normalisation
> (`lift > 2.0`).

`lane_report` now reports `lift_offenders` (both conditions), `coverage_explained_near` (raw rule
fires, lift ≤ 2 — the coverage artefacts) and `high_lift_low_overlap` (lift > 2 but the raw rule does
not fire — coincidence). Measured with that rule:

| prior set | priors | max lift *among priors that trip the raw rule* | genuine offenders |
|---|---|---|---|
| on disk (`submission/`, `docs/downloads/`, `data/scored/`, `data/reference/`) | 193 | **10.85×** against this repository's own H96 file (its own coverage 0.0806, near-fraction 0.8749) | **1 pattern** (the H96 raster, present under three file names) |
| the 526-blob sibling census | 526 | 1.0028× (`d8969518…`, its own coverage 0.9883) | **0** |

(Full counts from `evidence/h97_gates.json`: census — 25 priors trip the raw rule and are explained by
their own coverage, 31 show a lift > 2 from too few dots to matter, 0 are genuine; disk — the single
genuine offender pattern is the H96 raster, which the registry carries under three file names.)

So the final reading of the lane gate for H97 is narrow and honest: **the only genuine dot-proximity
duplication in either registry is against our own H96 artifact** — the raw 0.99/0.83 near-fractions
against the lattice and composite probes are their own coverage (lifts 0.990 and 0.957), and 24
priors show a large lift from too few dots to matter. The verdict is unchanged (STOP), the reason is
now correct, and the shared tool carries the repair.

**Sidenote for the next round.** The census set is *not* a source of near-duplicates for this
candidate: no sibling blob is identical to it, the largest Jaccard against any single censused blob is
0.0173, and no sibling blob's localisation is concentrated on our dots. The one number that collapsed
(novelty 0.3577 → 0.0000) is a property of *the union of 526 supports*, not of the candidate.
