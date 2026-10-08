# H60 — preregistered hypotheses, written before any model was fitted

Frozen by `registry/h60_preregistration.json` (SHA-256 of this file). The round's rule is
the repository's standing one: **do not spend a weekly submission slot on an idea that has
not beaten the current holdout best on a spatially-blocked holdout.** Every hypothesis
below names its layers, its physical target, why the target should be a fault the
USGS/INGENIOUS catalogue does not already contain, and how it differs from anything this
repository has already implemented and measured.

## What is already dead, so these do not repeat it

Read from `knowledge/03_negative_results_and_what_they_killed.md`, not from memory:

| dead | measured |
|---|---|
| pseudo-label co-training as a *training* signal | mean AUC Δ −0.0159, 1/4 fold support (N-1) |
| isotropic potential-field second derivatives | transform AUC ≈ 0.52 at a 300 m cell (N-6) |
| structure-tensor coherence as a *band* layer | best AUC 0.5122 of 108 features (N-11) |
| radiometric channels as *values* (depletion) | rad_K AUC 0.3506, ratios 0.4959–0.5723 (N-12) |
| external fault catalogues as positive priors | QFaults 1 px, INGENIOUS 0 px in footprint (N-6) |
| ranking a whole-footprint field and taking the top | top of a rank field is a regional anomaly (N-2) |
| 1 m 3DEP LiDAR scarp bands | not enriched under the credited dots: 76.4 % vs 75.4 % (H57-5) |

Every hypothesis below is **oriented**, **strike-specific**, or **metric-algebraic**, which
is the axis none of the dead entries used: they were all isotropic or value-based.

---

## H60-1 · Metric-algebra-optimal emission budget — RANK 1

**Layers.** None. This is the published metric's own algebra, applied to our own ranking.

**Target.** The `0.2·(S − M)` tax term of the distance-weighted Tversky index. With
`FNw = |G| − TPw` the score is exactly

```
DTI = T / (0.2·T + 0.2·(S − M) + 0.8·|G|)
```

so at fixed credited mass `T` every emitted pixel that is not within 300 m of a truth
pixel costs `0.2` in the denominator, and the marginal rule
`c·(1 − 0.2·DTI) > 0.2·DTI·(1 − m_x)` has a bar of only 0.0556 at DTI = 0.2778.

**Why it should catch something the catalogue does not contain.** It does not need to.
The 0.2778 file emitted 37,654 px whose implied hit-mass was ≈5,223, i.e. ~32,400 px of
pure tax; the same credit at zero tax scores 0.42. Budget is the one lever whose size is
known from algebra rather than from a model.

**How it differs from this repository.** Every round from H52 to H59 emitted at *the
champion's* budget (37,654 px) by analogy. No round has ever measured DTI as a function of
budget for its own ranking on a spatially-blocked holdout. `scripts/run_h60.py` stage 7
does that at 10 k / 20 k / 37,654 / 60 k / 100 k.

**Expected DTI improvement / cost.** Large if our precision decays with rank, zero if it
does not — and the measurement is the point. Cost: one extra loop in the holdout stage.

**Falsifier.** If mean holdout DTI is monotone increasing in budget across all four folds,
the hypothesis is refuted and the budget stays at the largest value tested.

---

## H60-2 · Strike-oriented ridge energy in the aeroradiometric total-count channel — RANK 2

**Layers.** `b06_ridge_nne`, `b06_ridge_nw`, `b06_gradmag`, `b02_ridge_nne`, `b14_ridge_nne`,
`b05_ridge_nne`, `b17_ridge_nne`, `b19_ridge_nne`, `b12_ridge_nne`, `b12_ridge_nw`.

**Physical signature.** Directional derivative taken along the *normal* to a lineament of
compass azimuth 15° or 315°, maximised over Gaussian scales 1/2/4 px, then regionally
centred. A fault is a one-dimensional object; an isotropic gradient magnitude spends most
of its energy on the two-dimensional regional trend, which is exactly why N-6 found
isotropic transforms at AUC ≈ 0.52.

**Why it should catch a fault the catalogue does not contain.** GeoDAWN is an *airborne*
magnetic and radiometric survey (USGS, DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ))
gridded to 100 m. Radiometric total count resolves lithologic contacts and hydrothermal
clay alteration at a scale finer than the grid; a contact-parallel fault shows up as a
straight, kilometre-long total-count gradient ridge long before it shows up as a scarp.
The USGS Quaternary Fault and Fold Database is a *Quaternary* compilation — it does not
contain pre-Quaternary or buried contacts at all.

**How it differs.** Band 6 has only ever entered this repository as a raw value inside a
view (and, before IR-52-019, mis-filed in View A). N-12 tested radiometric *channels as
values* and found depletion; this tests them as *oriented detectors*, which is a different
statistic on the same bytes. No prior round computed a directional derivative at all.

**Cost.** ~40 s of the layer build. **Falsifier.** Blocked AUC below 0.55 against
held-out catalogue segments, and no fold win over the matched-budget random control.

---

## H60-3 · Strike-projected basement-depth steps = buried range-front faults — RANK 3

**Layers.** `b15_step_nne`, `b15_step_nw`, `b13_step_nne`.

**Physical signature.** Second difference of band 15 (depth to basement surface) taken
*along* the strike direction, not isotropically. A buried normal fault under basin fill
produces a monotonic offset in basement depth that is linear over kilometres; the regional
dip of the basin is a ramp, and a second difference *along strike* cancels a ramp while an
isotropic Laplacian does not.

**Why it should catch a fault the catalogue does not contain.** This is the only signature
in the supplied cube that is *definitionally* invisible at the surface. The 0.2778 file
sits a median 1,965 m from the published catalogue (measured this session on the restored
bytes), i.e. the scored truth is predominantly *not* a mapped range front — which is what
a basin-buried fault population looks like.

**How it differs.** N-6 lists "basement-depth signed step 0.5113": that was the isotropic
signed step. The strike-projected version is a new statistic.

**Cost.** ~15 s. **Falsifier.** Blocked AUC ≤ 0.53 and no contribution to the selected arm.

---

## H60-4 · Dilational intersection nodes of the two strike sets — RANK 4

**Layers.** `node_nne_x_nw` (surface ridge fields), `node_nne_x_nw_A` (potential-field
ridge fields).

**Physical signature.** Product of the two normalised, strike-specific lineament-density
fields, smoothed at 2 px. Maxima are where a NNE-striking normal fault is crossed by a
NW-striking transfer structure.

**Why it should catch a fault the catalogue does not contain.** Fault intersections are
where the dilatational strain — and therefore permeability and geothermal upflow — is
concentrated; this is the standard structural argument in play-fairway analysis for the
Great Basin. An intersection *node* is a point object, and point objects are precisely
what a line-compiled Quaternary fault database under-represents: the database records the
traces, not the crossings, and a crossing with no surface expression is not recorded at
all.

**How it differs.** The repository computed structure-tensor *coherence* (isotropic,
AUC 0.5122, N-11) and never crossed two independently extracted, strike-specific lineament
fields. H55's "paired shoulders" was a shoulder-pair statistic on one band, not an
intersection of two sets.

**Cost.** ~20 s. **Falsifier.** Blocked AUC ≤ 0.55; also refuted if the layer is not
selected into the winning arm.

---

## H60-5 · Seismicity-alignment locator, rank-encoded — RANK 5

**Layers.** `b10_rank`, `b16_rank` (already in the plan; this hypothesis is about *how*
they may be used, not a new layer).

**Physical signature.** Microseismicity aligns on active structures. Band 16 (earthquake
density) is high along active faults; band 10 (distance to nearest earthquake) is low
there. Both are used **rank-encoded only**.

**Why it should catch a fault the catalogue does not contain.** Instrumental seismicity is
compiled independently of any geologic map: an active structure that has never been mapped
still earthquakes.

**How it differs / and the irregularity that governs it.** **IR-R4-002: band 10 reaches
4,962,515 m inside a grid whose diagonal is ~492 km**, so 0.41 % of footprint pixels
report an impossible distance-to-nearest-earthquake. Any use of band 10 as metres is
therefore forbidden in this round; rank encoding is monotone and bounded and is the only
permitted transform.

**Cost.** Zero (layers already present). **Falsifier.** Removing both bands from View A
does not lower blocked AUC.

---

## Ranking, and what gets validated

| rank | id | expected DTI lever | implementation cost | validated by |
|---|---|---|---|---|
| 1 | H60-1 | removes ~32 k px of tax | trivial | holdout DTI-vs-budget curve, 4 folds |
| 2 | H60-2 | new detection signal, oriented | 40 s | blocked AUC + hide-and-recover |
| 3 | H60-3 | buried-fault population | 15 s | blocked AUC + hide-and-recover |
| 4 | H60-4 | geothermal-specific nodes | 20 s | blocked AUC + hide-and-recover |
| 5 | H60-5 | independent activity data | 0 s | ablation |

**No external data is required for any of the five.** Everything above is computed from
`data/training_features.tif`, whose SHA-256 is pinned in `registry/data_manifest.json` and
re-verified on restore this session (`4371c82e3b8339b8…`, 418,912,844 bytes). H60-2's
interpretation of band 6 rests on the repository's own measurement against the USGS
GeoDAWN total-count grid (DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ)), not on
the file's TIFF tag, which is wrong.

**The top candidate (H60-1) is validated on the spatially-blocked hide-and-recover
holdout before any submission slot is considered**, per the standing rule.
