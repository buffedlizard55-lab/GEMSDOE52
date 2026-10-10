# H83 — co-training on two instruments: the mandated hide-and-recover, and a new
# off-catalogue recovery instrument built from a fault compilation the competition
# catalogue does not contain

**Round:** H83 · **Lane:** co-training between a geophysical view (A) and a surface view (B),
disagreement as the discovery signal (Blum & Mitchell, COLT '98, pp. 92–100,
doi:10.1145/279943.279962).
**Status:** frozen before any H83 fit, holdout score or emission.
**Session branch:** `arena/e3e0264a-gemsdoe52` (fixed by Arena; do not change).

---

## 1. Why this round exists — the measurement gap, stated as a measurement

Every instrument this repository has (`gems52-pooled-hide-v1`, evaluator in
`src/gems52/evaluate_holdout.py`) withholds **catalogue** faults — components of `labels.tif`,
the USGS/INGENIOUS compilation — and scores how well a field recovers them. The competition's
truth `G` is the set of faults that compilation **lacks** (DrivenData page 967; staff thread
11516 post #4: the new-fault truth includes corrections and extensions of mapped traces).
Those are two different populations of pixels.

The mismatch has already been measured, not guessed:

* `knowledge/10_revealed_preference_inverse.md` §5 — Spearman **−0.10** between holdout DTI and
  owner-reported board score, over the R4 arm set.
* `knowledge/66_h75_results_and_limits.md` — the derived SGMC fault compilation is **95 %
  disjoint** from `labels.tif` (79,615 off-catalogue pixels), so a *second, independent* fault
  compilation exists inside the footprint.
* H77 closeout — "An off-catalogue instrument is the highest-value unbuilt tool in this
  repository."

H83 builds that instrument and runs the lane's arms through **both** instruments. It does not
replace `gems52-pooled-hide-v1`; the hide-and-recover run remains the primary, comparable
number, and it is the comparison the brief asks for against the single-view baseline.

## 2. Instruments

### I1 — `gems52-pooled-hide-v1` (mandated, unchanged, shared)

`gems52.spatial.folds(cat, eligible, buffer_px=80)`, label-blind-quadrants-v2. Whole
8-connected catalogue components are held; a component crossing quadrants is excluded from
training in every quadrant it touches and scored only in its fixed quadrant. Pooled DTI,
α = 0.2, β = 0.8, triangular kernel k(d) = max(1 − d/R, 0), R = 300 m = 3 px; 200 px physical
cluster blocks; 1,000 paired cluster-bootstrap draws; the visible catalogue is deleted
pixel-exactly from the emission pool and from the score.

### I2 — `gems52-offcatalogue-v1` (new this round; added to the shared template)

* **Truth.** Pixels of `data/external/derived_sgmc_faults_100m_u8.tif` (a rasterised fault
  compilation derived from the USGS **State Geologic Map Compilation**, SGMC — restored and
  SHA-256-pinned in `registry/data_manifest.json`, integrity-pinned not organiser-authenticated)
  whose Euclidean distance to the nearest `labels.tif` pixel is **≥ 300 m = 3 px**. The 300 m cut
  is the metric kernel radius: it removes SGMC pixels that merely duplicate the competition
  catalogue, leaving faults a *different* compilation mapped that this one did not.
  Truth is grouped into whole 8-connected components and assigned to the quadrant owning most
  of its pixels, so I2 is segment-wise, not pixel-wise.
* **Training positives.** `labels.tif` pixels from the **other three quadrants only**, minus an
  80 px buffer at the quadrant boundary. Nothing from an I2 truth component is ever a training
  positive: that is the train/test asymmetry of the competition itself (you get the catalogue,
  you are graded on what it missed).
* **Emission pool / mask.** `labels.tif` dilated by 2 px (200 m) is deleted from the pool and
  from the score, pixel-exactly, in every quadrant — the organiser's mask is the whole
  catalogue, not a fold's subset.
* **Scoring.** Identical to I1: `gems52.metric.dti`, α 0.2, β 0.8, R 300 m, 200 px physical
  blocks, 1,000 paired draws, one pooled CI per arm.
* **Reported as** `OFFCAT-DTI`, never as `HOLDOUT-DTI` and never as a board forecast. It is a
  second, differently-biased proxy for the same unknown quantity.

**Known limitations of I2, stated in advance.** (a) The 300 m cut removes the *extension*
population by construction, so I2 cannot see whether a field finds extensions of mapped traces.
(b) SGMC traces are compiled from state geologic maps at 1:100 k–1:500 k; they are themselves
incomplete and may include non-fault lineaments. (c) Off-catalogue SGMC pixels may sit in
different terrain than the faults the competition will actually verify. I2 is a proxy, not the
hidden set.

## 3. Views (inherited, not re-tuned)

* **View A — potential-field / subsurface** (`view_A_with_external`, 36 channels): isostatic
  gravity anomaly and its slope/vertical/horizontal gradients, magnetics (anomaly, RTP, TMI,
  TMI up-continued 150 m, horizontal and vertical gradients), geodetic strain (second
  invariant, shear, dilatation), seismicity (density, distance to earthquake), depth to
  basement-surface, surface conductivity, plus the cover-coherence and gravity-persistence
  transforms of `gems52.structural`.
* **View B — surface** (`view_B_with_external`, 37 channels): detrended elevation, its slope,
  DEM curvature (plus/minus/trace) at σ = 1, 3 px, the paired-flank profile transform, **band 6
  = radiometric total count** (moved here by IR-52-019 / IR-52-034; the file's own tag says
  "magnetic tilt" but measured Spearman with the GeoDAWN total-count grid is +1.0000 and the
  range 2.95–88.6 is not a tilt angle), and the external GeoDAWN radiometric and LiDAR scarp
  channels.
* The two sets are disjoint by construction; `run_h61.setup` refuses to start if they overlap.

## 4. Arms (identical on both instruments, identical budget, identical rows and seeds)

`nodes.spacing_select(field, allowed, K, min_px=3.0)`, K = 9,400 dots per fold per arm,
K_TOTAL = 37,654 across the four stitched folds.

| arm | field | meaning |
|---|---|---|
| `single_A` | pct-rank of pre-exchange View A | subsurface alone |
| `single_B` | pct-rank of pre-exchange View B | surface alone — the control every promotion rule compares against |
| `union_max` | max(rank A, rank B) | plain two-view agreement |
| `A_only` | rank A − rank B | **A confident, B abstains → candidate buried structure** |
| `B_only` | rank B − rank A | **B confident, A abstains → suspect surface artefact (road, erosion line)** |
| `disagreement_post` | rank A_post − rank B_post | the lane's discovery signal after one exchange round |
| `random` | uniform | floor |

## 5. Frozen decision rules

1. **Independence first, before any transfer.** `gems52.spatial.independence` on 50 px blocks of
   held-out catalogue-zero proxy negatives; abandon the exchange if max |ρ| ≥ 0.60 or if the
   statistic is undefined/under-powered (< 20 blocks).
2. **One exchange round only, whole segments, buffered.** `gems52.spatial.whole_pseudo_segments`
   with donor rank ≥ 0.98, receiver rank in [0.35, 0.65] (abstention, not confident negation),
   min 5 px per segment, cap 2,000 px per fold per direction, confined to a single 50 px block
   and never touching an evaluation pixel, a held component or a catalogue pixel. No second
   round, no post-result hyper-parameter search.
3. **Leakage canary.** Any single channel with direction-insensitive AUC ≥ 0.90 on a held-out
   region sample is leakage until proven otherwise and is dropped before the fit.
4. **Promotion rule.** Ship-promote only if the selected candidate's paired 95 % CI lower bound
   against `single_B` on **I1** is above zero. (I2 is diagnostic; it can demote a candidate that
   I1 would promote, but it cannot by itself promote.)
5. **Shipment selection, frozen before any fit.** Two candidate emissions are pre-registered:
   * **E1** — `disagreement_post` (the lane's literal discovery field).
   * **E2** — `union_post` = max(rank A_post, rank B_post) over the allowed domain, with
     **25 % of the budget reserved, before ranking, for the highest `A_only` pixels that are not
     in the union field's own top-k**. Rationale: at a fixed budget the pure-disagreement pixels
     are otherwise always outranked by consensus pixels, so a reserved quota is the only way the
     discovery signal can appear in an emission at all.
   Ship **whichever of E1/E2 has the higher pooled I1 DTI**. Verdict is **negative** unless rule
   4 is met. Slots used this round: **0** — promotion to a real weekly slot is a separate
   selector step.
6. **Emission domain.** 3 px minimum separation, 200 m (2 px) ring around the whole `labels.tif`
   catalogue excluded, footprint = the all-19-band finite intersection, values exactly {0, 1},
   NaN outside the footprint on the organiser template's own container profile
   (`gems52.grid.write_geotiff_portal_exact`).
7. **Not-merely-the-union.** The written raster is checked against `A_only`, `B_only` and
   `union_max` placements at the same budget; Jaccard and the Spearman of the fields over the
   allowed pool are reported either way.
8. **Lane drift check.** Spearman of the output surface against every census raster (bar 0.90)
   and the fraction of emitted dots within 3 px of any one census raster's dots (bar 0.70);
   full-census literal and scored-only-restricted readings are both reported, because the
   full census contains universal-coverage lattice probes for which the literal dots rule
   returns DUPLICATE for *every* non-empty raster.

## 6. Candidate geological hypotheses considered for this round (ranked before the run)

Ranked by expected DTI improvement against implementation cost. None of these is a claim of
scoring; they are the three candidate mechanisms H83 could have spent its budget on.

1. **H83-1 (chosen) — buried-structure discovery under thin cover, measured off-catalogue.**
   *Layers*: View A gravity/RTP/TMI-up150 edge and step channels + depth-to-basement-surface
   (band 15) + surface conductivity (band 17), against View B curvature/slope abstention.
   *Signature*: A confident, B abstaining, **restricted to where band 15 (depth to basement
   surface) is small-to-moderate**, i.e. where a bedrock fault could be buried beneath a thin
   veneer rather than beneath a thick basin fill.
   *Why it should catch a fault the catalogue lacks*: a fault with no scarp is invisible to every
   surface detector, and this repository's best-scoring family is entirely surface-morphological,
   so the buried population is the one place marginal credit can still come from.
   *Why it differs from anything already implemented*: previous rounds tested A-only
   disagreement **unconditioned** on cover thickness; the cover conditioning and the off-catalogue
   instrument are both new.
   *Named non-fault process that could mimic it*: a **lithologic contact or a basin-fill
   thickness change** — both produce gravity and conductivity steps and basement-depth
   gradients with no fault at all. Second mimic: the **flight-line / grid seam** artefact in the
   airborne magnetic and radiometric grids.
   *Cost*: low — every channel is already in the cached store.
2. **H83-2 (not run) — artefact suppression on the B-only branch.**
   *Layers*: View B curvature vs the GeoDAWN radiometric K/Th/U and the LiDAR scarp layers.
   *Signature*: B confident, A abstaining **and** radiometric total count anomalous → road,
   canal or fence line rather than a scarp.
   *Named mimic*: **anthropogenic linear features** (roads, powerline corridors, irrigation
   canals) which are the dominant false-positive source for scarp detectors in this basin.
   *Cost*: low, but it can only *remove* pixels; its upside is bounded by the FP tax, ~small.
   *Ranked below H83-1 because* at α = 0.2 the false-positive weight is 5× cheaper than the
   false-negative weight (β = 0.8), so precision work pays less than recall work.
3. **H83-3 (not run, needs external data — availability checked, see §7) — spring and vent
   proximity as a geothermal prior.**
   *Layers*: GDR well/spring records restored at `data/external/gdr_wellspring_in_footprint.csv`
   and `data/external/gdr_volcanic_vents_in_footprint.csv`, distance-decayed.
   *Signature*: distance to a documented warm spring oryoung volcanic vent, interacted with
   View-A permeability proxies.
   *Named mimic*: **springs locate on any permeable fault or on a stratigraphic aquifer**, so
   they are a geothermal indicator, not a fault indicator; using them as a positive label would
   import exactly the bias the brief warns about.
   *Cost*: low — the CSVs are already restored. Deferred because the competition scores
   *structure*, and a spring prior would need a labelled geothermal set to calibrate that does
   not exist here.

## 7. External data availability check (done before proposing H83-3 as viable)

| Source | URL | Status in this sandbox |
|---|---|---|
| GDR submission 1391 (well/spring + vent tables) | https://gdr.openei.org/submissions/1391 | **already restored** as `data/external/gdr_wellspring_in_footprint.csv` and `data/external/gdr_volcanic_vents_in_footprint.csv`, SHA-256 pinned in `registry/data_manifest.json` |
| GeoDAWN airborne magnetic & radiometric surveys, NW Great Basin | https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and | **already restored** as `data/external/geodawn_rad_u8.tif`, `geodawn_extensions_u8.tif`; inaccessible live (host outside the egress allowlist), used through the pinned mirror |
| USGS SGMC (state geologic map compilation) | https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc | **already restored** in derived form as `data/external/derived_sgmc_faults_100m_u8.tif` |
| USGS Quaternary fault and fold database | https://www.usgs.gov/programs/earthquake-hazards/faults | **already restored** as `data/external/gdr_qfaults_traces.csv` (not used this round: it is a USGS product and overlaps the competition catalogue, so it is not off-catalogue) |
| USGS 3DEP 1 m DEM | https://www.usgs.gov/3d-elevation-program | **not obtainable** from this sandbox; the tile-index host is outside the egress allowlist. Earlier rounds (H55) recorded the same TLS failure. Named here only so no later round spends time rediscovering it. |

No new external data is required by the chosen hypothesis (H83-1).

## 8. Reproduce

```
python3 scripts/restore_data.py --target-dir data
PYTHONPATH=src python3 -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False)"
PYTHONPATH=src python3 -m gems52.external
python3 scripts/fetch_prior_inventory.py
python3 scripts/run_h83.py {canary|fit|exchange|holdout|build|lane|write|card|all}
```

---

*Frozen: this document's SHA-256 is pinned in `registry/h83_preregistration.json`, and
`scripts/run_h83.py` refuses to start if either has moved.*

---

## 9. Amendment 74a (registered 2026-10-10, before the E3 measurement and before any build)

Two additions, both registered **before** the measurement they govern.

**A. A third candidate emission, E3.** The frozen rule in §5.5 ranked only E1 and E2, neither of
which is the single-view baseline the brief requires as the comparison. E3 is therefore added:

* **E3** — `single_B` field (pre-exchange View-B rank) with the **same 25 % reserved A-only quota**
  as E2, i.e. `q = 0.25·K` dots placed first on `A_only = rankA − rankB`, then the remaining `K − q`
  dots placed on the `single_B` field excluding the 3 px halo of the quota dots.

E3 is scored as an eighth holdout arm, `E3_single_B_quota`, on both instruments, and the shipment
rule becomes "ship whichever of E1 / E2 / E3 has the highest **measured** pooled I1 DTI".

**Honesty statement, recorded deliberately.** The E1/E2 arm results were read before this amendment
was written, and they show `single_B` (0.174571) above `union_max` (0.149009). The choice of
`single_B` as E3's base field is therefore **informed by results already in hand**, even though E3's
own measurement is prospective. E3 is consequently registered as an **attribution arm**: under
`registry/h83_preregistration.json → attribution_arms_not_promotable` it may be **shipped** (it is
the better artefact) but it can never by itself turn the verdict positive. The verdict is decided by
the pre-registered candidate `disagreement_post` and by the frozen CI rule in §5.4, exactly as
before.

**B. A second off-catalogue variant, I2b.** I2 excludes SGMC pixels within 300 m of `labels.tif`,
which removes the *extension* population by construction — and the organiser has stated that the
new-fault truth includes corrections and extensions of mapped traces. I2b repeats I2 with the cut at
**0 px** (every SGMC pixel that is not itself a `labels.tif` pixel), so the two bracket the extension
question. I2b is diagnostic in the same way as I2.
