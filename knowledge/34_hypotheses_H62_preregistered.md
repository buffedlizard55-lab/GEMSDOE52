# 32 — H62: five candidate hypotheses, ranked; the top one preregistered

Session 2026-10-08/09. Lane: *co-training between a geophysical view and a surface view, with
disagreement as the discovery signal* (Blum & Mitchell, COLT '98, pp. 92–100,
doi:10.1145/279943.279962). Everything below is written **before** any H62 fit ran.

Standing facts inherited from earlier rounds, all measured on the manifest-pinned bytes and all
labelled as such:

| fact | value | source |
|---|---|---|
| the board's truth is **not** near the mapped catalogue | champion `h33-2-b2` has 0 px within 200 m of a catalogue pixel; median distance 1,965 m | `knowledge/27` §2 |
| the hide-and-recover instrument is **anti-informative** about the board | Spearman(reported, simulated DTI) = −0.1045, p = 0.734, n = 13; the champion ranks 13/13 on it | `knowledge/10` §5, `knowledge/27` §5 |
| board score is **strictly decreasing in emitted mass** across the six off-catalogue scored priors | Spearman −1.000 | `knowledge/27` §6 |
| **corroboration** is worth ~an order of magnitude in credit density | `P1 = h33-2-b2 ∩ d1-5` (two independent thinnings of one field), 25,517 px, credit density **16.3–20.5 %**, vs 0–8.7 % for the singly-selected atoms | `knowledge/10` §3 |
| the two views' block out-of-fold errors on labelled negatives are weakly coupled | max |block r| ≤ 0.176, abandonment at 0.60 | `knowledge/31` §1 |
| the A-only stratum is deep cover | median depth to basement 341.7 m (A-only) vs 106.5 m (B-only) | `knowledge/31` §1 |

The last two rows are the two premises this round exploits, and both were left unused as
*design variables* by the rounds that measured them.

---

## The five candidates

Each names the layers, the physical signature, why it should find a **catalogue-missing** fault
rather than one already in the USGS/INGENIOUS compilation, and how it differs from everything
already implemented here.

### H62-A — cover-thickness-conditioned buried disagreement  *(rank 2)*

* **Layers.** View-A out-of-fold confidence `pA`, View-B out-of-fold confidence `pB`, and
  `training_features.tif` band 15 *depth to basement surface*.
* **Signature.** `A-only ∧ (depth-to-basement ≥ d*)`, with `d*` preregistered at the
  **70th percentile of depth-to-basement inside the legal pool** (a quantile, so it is measured on
  the run's own bytes and cannot be tuned to a result).
* **Physics.** A Quaternary normal fault that offsets basement beneath thick basin fill produces a
  potential-field lineament (isostatic-gravity and reduced-to-pole magnetic gradient) but no
  detectable scarp, because the rupture tip is blunted by the fill and the free surface is a
  depositional plain. Where cover is thin, the *absence* of a scarp falsifies the fault: the
  A-side lineament there is a lithologic contact, a dike, or the basin-margin gravity gradient.
  So the brief's "A confident, B abstains ⇒ buried beneath cover" cell is only licensed **inside
  the thick-cover regime**, and the round that measured the depth contrast never used it as a
  restriction.
* **Why catalogue-missing.** The USGS/INGENIOUS compilation used for the labels is built from
  *mapped* — overwhelmingly surface-visible — Quaternary faults. Buried structures under basin
  fill are the systematically under-mapped population, and the board's own truth sits a median of
  1,965 m from any mapped trace.
* **Difference from the repo.** H60D measured the depth contrast and stopped (`dis_contrast`,
  shipped, negative). H56/H59 emitted A-only with no cover conditioning. No round has ever
  intersected the disagreement cell with a cover-thickness regime.
* **Named non-fault mimic.** The **basin-bounding gravity gradient** itself: a strong, laterally
  persistent isostatic-gravity lineament at the fill–bedrock contact with no scarp anywhere near
  it, and it is exactly where depth-to-basement is large. Second: basement lithologic contacts
  beneath fill.
* **Cost.** One mask. **Expected DTI change:** small but positive; a precision filter, not a new
  detector.

### H62-B — two-view concordance under independent thinning (co-training corroboration)  *(rank 1)*

* **Layers.** Both views' out-of-fold confidence surfaces, plus the metric's own 3 px lattice.
* **Signature.** `concordance = min(pA, pB)` restricted to `pA ≥ q_conf ∧ pB ≥ q_conf`, then
  thinned to the metric's lattice **independently within each view** and intersected.
* **Mechanism.** `knowledge/10` §3 measures a corroboration law: two *independent thinnings of one
  field* (`d1-5`, `d2-8`) intersect in an atom carrying 16.3–20.5 % credit density, an order of
  magnitude above the atoms selected by only one thinning. Corroboration is the only sub-ranking
  inside the champion file that the published scores can see, and it is the single largest
  measured effect in this repository's history after the 200 m ring. Blum & Mitchell's premise is
  that two views are *conditionally independent given the class* — which is a strictly stronger
  independence than two random thinnings of one detector, and it is empirically supported here
  (block OOF negative-error correlation ≤ 0.176 against an abandonment bar of 0.60). Two views
  that err independently corroborate more than two thinnings of one view that share every
  systematic error.
* **Why catalogue-missing.** Concordance is a *precision* operator: it removes the pixels where
  either view's confidence is an artefact of its own instrument, which is precisely the failure
  mode that keeps a detector's dots off the real, unmapped structures.
* **Difference from the repo.** Every prior round in this lane shipped a **disagreement** field
  (`pA(1−pB)`, `max(pA−pB,0)`). This is the opposite cell of the same 2×2 confidence table, it is
  not the union `max(pA,pB)` (which is large wherever *either* view fires), and it applies the
  metric's own lattice as an *independent thinning per view* before intersecting — the step that
  converts agreement into corroboration.
* **Named non-fault mimic.** A **resistant lithologic contact**: a welded-tuff or carbonate unit
  that both stands up as a ridge (View B lineament) and carries a magnetic susceptibility contrast
  (View A lineament). It is a straight, laterally persistent, geologically real structure that is
  not a fault. Second: a fluvial/glacial erosional escarpment along a stratigraphic contact.
* **Cost.** Low (no new data). **Expected DTI change:** the largest of the five, because it acts
  on credit density, which is the only quantity the metric rewards.

### H62-C — B-only rehabilitated: structured surface lineaments the geophysics cannot resolve *(rank 3)*

* **Layers.** View B (LiDAR scarp products, detrended-elevation slope, radiometric), View A, and a
  structure-tensor coherence/strike field on the DEM.
* **Signature.** `pB ≥ q_conf ∧ pA ≤ q_abstain ∧ coherence ≥ c* ∧ strike within ±30° of the
  footprint's Basin-and-Range fabric ∧ not on flat/playa ground`.
* **Mechanism.** Sufficiency, not independence, is the assumption that fails. View A's inputs are
  regional potential-field and geodetic grids: a 1–5 m Quaternary scarp is below their
  resolution, and `knowledge/01` §5 records that the strain bands are smoothed below
  fault-resolution at 100 m. A's abstention is therefore *uninformative*, and reading the B-only
  cell as an artefact population (the brief's own warning, and H59-B's blanket veto at λ = 0.5)
  misreads the asymmetry. The rehabilitation is a **structure** test, not a blanket un-veto.
* **Why catalogue-missing.** Small, young scarps on the flanks of unmapped range fronts are the
  single largest population missing from a compilation built from air-photo and field mapping.
* **Difference from the repo.** H59-B refuted a *blanket* B-veto (λ = 0.5 multiplicative
  suppression). No round has restricted B-only by lineament coherence, strike concordance and
  surface roughness.
* **Named non-fault mimic.** **Roads, levees, irrigation canals and quarry faces** — straight,
  coherent, high-contrast DEM lineaments with no geophysical expression, exactly as the brief
  warns. This is why the coherence restriction is paired with a strike test and a flat-ground
  veto, and why the round reports B-only as characterization if the mimic cannot be excluded.
* **Cost.** Medium (needs the coherence/strike field). **Expected DTI change:** high variance.

### H62-D — InSAR line-of-sight strain rate at 10× the geodetic resolution  *(rank 4 — NOT VIABLE HERE)*

* **Layers.** A free, official InSAR displacement time series (e.g. the ESA Sentinel-1-derived
  products distributed through ASF/NASA, or the USGS/Nevada Bureau wide-area products).
* **Signature.** A gradient in line-of-sight velocity, i.e. a strain-rate lineament, at 100 m
  posting instead of the ~10–25 km smoothing of `training_features.tif` bands 4/7/8.
* **Why it would be catalogue-missing.** Interseismic strain localisation marks an actively
  loading structure regardless of whether it has ever been mapped.
* **Named non-fault mimic.** **Aquifer-system compaction / subsidence bowls** — a sharp
  InSAR velocity gradient over a basin-fill thickness change with no fault at all.
* **Viability check, done this session:** the sandbox reaches only `github.com`,
  `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org` and
  `files.pythonhosted.org`. ASF (`asf.alaska.edu`, `api.daac.asf.alaska.edu`), the USGS
  `rockyweb`/`prd-tnm` hosts and the Nevada Bureau host are **not reachable**, so the download
  cannot be performed or hash-pinned here. **Not proposed as viable this session**; the specific
  free official source is named so a later session on an unrestricted machine can fetch it.

### H62-E — a further pseudo-label exchange round  *(rank 5 — DO NOT RUN)*

Already null in **five** independent reproductions (H56, H57, H59, H60D ×2 directions), each with a
whole-segment buffered exchange. Re-running it would consume the round's budget on a
measured null. Recorded here only so it is not re-proposed.

---

## Ranking by expected DTI improvement per unit cost

| rank | candidate | expected effect | cost | verdict |
|---|---|---|---|---|
| 1 | **H62-B** concordance under independent thinning | acts on credit density; corroboration is the largest measured effect in this repo | low | **preregistered, run** |
| 2 | **H62-A** cover-conditioned buried disagreement | precision filter on the lane's own discovery cell | very low | **preregistered, run** |
| 3 | **H62-C** rehabilitated structured B-only | high variance; the brief's own warning applies | medium | run as a characterization arm if budget allows |
| 4 | H62-D InSAR strain rate | would be large | blocked | not viable: hosts unreachable |
| 5 | H62-E pseudo-label exchange | null ×5 | low | do not run |

---

## Instruments

**Instrument 1 (required by the lane).** Hide-and-recover, whole-segment, 4 folds, 4 px buffer,
prevalence 0.002, visible catalogue masked pixel-exactly, pooled DTI α 0.2 / β 0.8 / 300 m
triangular kernel, fold-bootstrap 95 % CI. Every number is a **HOLDOUT-DTI** number. It is
reported because the lane requires it and because it is the only instrument that can detect
leakage — **not** because it predicts the board (Spearman −0.1045, `knowledge/10` §5).

**Instrument 2 (new this round, revealed-preference).** The one subset of this footprint whose
credit density is *measured* rather than projected is `P1 = h33-2-b2 ∩ d1-5`, 25,517 px, credit
density bounded to **[16.3 %, 20.5 %]** by the exact nested-pair algebra on owner-reported scores
(`knowledge/10` §3). For a candidate dot set `X` in the legal pool define

```
f(X) = | X ∩ dilate(P1, 3 px) | / |X|
```

the fraction of the candidate's dots inside the metric's own acceptance radius of a pixel of
measured credit. Against a matched random baseline `f_random = |dilate(P1,3px)| / |pool|`. Under a
two-component mixture the implied credit density is
`ρ(X) ≈ f·ρ_P1 + (1−f)·ρ_novel`, `ρ_novel ∈ [0.0279, 0.1387]` (measured uniform-random and
champion-average densities).

Three disclosures, non-negotiable: (a) `f` rewards co-location with **one specific prior file**, so
it is a similarity statistic, not an independent measurement of truth, and it is read **together
with** the uniqueness gate; (b) `ρ_P1` itself rests on owner-reported scores, none of which is
ORGANIZER-CONFIRMED; (c) a field can maximize `f` by reproducing the champion, which the lane's
3-px-proximity and pattern-uniqueness gates exist to forbid.

**Instrument 3 (leakage canary).** Every cached layer alone against the holdout truth; AUC > 0.90
on any layer is leakage until proven otherwise.

---

## The budget rule (derived, not inherited)

Prior rounds emitted 37,654 px because that is the champion's mass. It is not derived. With
`FNw = |G| − TPw`, binary mass and `M ≈ T`,

```
DTI(S) = T(S) / (0.2 S + 0.8 |G|),    T(S) = c S^γ
```

The argmax in `S` is independent of `c` — field quality does not move it:

```
S* = γ · 0.8 |G| / (0.2 (1 − γ))
```

`knowledge/10` §4 fits `γ = 0.2284` to the champion family. With the repo's registered
`|G| = 14,088.7` this gives **S\* ≈ 16,700 px**; with the wider bracket `|G| = 18,000–19,300`
(`knowledge/27` §3, which drops the `M = T` coincidence assumption) it gives **21,300–22,900 px**.
Both are far below 37,654, and both agree with the measured Spearman −1.000 between emitted mass
and board score.

`γ` is therefore **measured on this round's own field**, by regressing `log f(S)` on `log S` at
`S ∈ {8k, 12k, 17k, 25k, 38k}` under Instrument 2 (`f(S) ∝ ρ(S)` under the mixture model), and
`S*` is taken from that fit with `|G| = 14,088.7`, clamped to **[15,000, 30,000]**. The clamp is
preregistered so that a wild `γ` cannot produce an absurd emission, and both unclamped and
clamped values are reported.

---

## Decision rules

1. **Leakage.** Any layer with holdout AUC > 0.90: stop, report, trust nothing built on it.
2. **Independence.** `spatial.independence` on 50 px block OOF negative-error rows; abandon the
   co-training exchange at max |r| ≥ 0.60. The exchange is **not** re-run this round (H62-E); the
   test is still run because the concordance hypothesis *depends* on the same premise.
3. **Promotion.** The concordance field promotes iff, at the derived budget, its
   `f` (Instrument 2) exceeds `f` of `view_A`, `view_B`, `clf_union` and `dis_contrast`, **and**
   it is not beaten by them on the hide instrument by more than the registered lift bar
   (+0.005 pooled), **and** it passes uniqueness and the lane gate. Otherwise the round ships the
   best measured field with verdict **negative**. A negative result is a deliverable.
4. **Artifact.** Values exactly `{0,1}` float32, all finite, EPSG:32611, 3730×3292, pinned
   transform, ZIP containing only that TIFF.
5. **Ring.** No emitted pixel within 200 m of a mapped catalogue pixel. Re-measured on the output.
6. **Lane drift.** Spearman with every registry raster ≤ 0.90 on the ranking surface **and** on the
   final dots; ≤ 70 % of final dots within 3 px of any one registry raster's dots (calibration
   rasters excluded from the proximity component only, per registered correction H60-6).
   Exceeding either: log as a duplicate lane and stop.
7. **Not merely the union.** The emitted set must not be the top-k of `max(pA,pB)` under an
   identical pool and emitter; reported as a count and a fraction.
8. **Reasoning.** One written geological reasoning row per emitted pixel, plus a dossier row for
   every A-only candidate segment in the legal pool (capped, with the cap disclosed).
9. **Reporting.** Every holdout number labelled HOLDOUT-DTI (evaluator version, withheld
   positives, 95 % CI). Every leaderboard number anywhere is owner-reported; none is
   ORGANIZER-CONFIRMED. A projection is never written as a score. Promotion to a real weekly slot
   is a separate selector step and is not decided here.
