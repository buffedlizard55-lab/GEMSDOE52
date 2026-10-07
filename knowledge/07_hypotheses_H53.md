# 07 · H53: five hypotheses not yet tried, each with its layers, its signature, and its cost

Written **before** the H53 holdout sweep was scored. Ranking rule stated up front and not moved
afterwards: **expected DTI improvement divided by implementation cost**, where "expected" means
either measured in this repository on a spatially-blocked fold or bounded by the metric algebra —
never asserted.

Two standing constraints from the brief are honoured in every entry below:

* a hypothesis must explain why it finds a fault that is **absent** from the USGS Quaternary fault
  and INGENIOUS compilations, not one that is present in them. The metric pays nothing for
  re-finding a mapped trace: `labels.tif` is masked pixel-exactly, and the family measured that
  deleting 6.3 % of its own mass that sat on catalogue pixels **raised** its score 2.6 %
  (`knowledge/01`).
* if a hypothesis needs data the repository does not have, the specific free official source is
  named and its obtainability is confirmed before the hypothesis is called viable.

---

## The correction that unlocks four of the five

**Band 6 of the official `training_features.tif` is the GeoDAWN aeroradiometric total-count grid,
not a magnetic derivative.** The file's own TIFF tag says
`data_category = magnetic_data`, `description = "Tilt angle or total curvature - magnetic field
derivative for edge detection"`. Measured on the bytes this session, 150,000-pixel sample,
`evidence/h53_band6_identity.json`:

| test | Spearman ρ |
|---|---|
| band 6 vs the independently reduced GeoDAWN **TC** grid (`data/external/geodawn_rad_u8.tif` band 4, from DOI 10.5066/P93LGLVQ) | **+1.0000** |
| band 6 vs **K + Th + U** from the same release | **+0.9914** |
| band 6 vs TMI (band 14) | −0.0250 |
| band 6 vs TMI upward-continued 150 m (external band 4) | +0.0079 |
| band 6 vs TMI horizontal gradient (band 3) | −0.1489 |
| band 6 vs TMI vertical gradient (band 9) | +0.0214 |
| band 6 vs RTP (band 2) | −0.0914 |

Total count *is* the sum of the potassium, thorium and uranium windows — that is what a
total-count channel means — so ρ = 0.9914 against K+Th+U is the physical signature, and ρ = 1.0000
against the independently reduced TC grid is the identification. A magnetic-field derivative cannot
be uncorrelated with the magnetic field; |ρ| ≤ 0.149 against all five magnetic bands in the file.
Also decisive: band 6 is strictly positive (min 2.953, max 88.573, mean 18.46) while a tilt angle is
bounded by ±π/2.

**Consequences.** `src/gems52/features.py` filed this band inside **View A** as `A_mag_tilt_abs`,
i.e. a radiometric surface-geochemistry band was being used as potential-field evidence. That
corrupts the two-view split the whole brief is built on and the conditional-independence test that
is supposed to police it: any correlation between "View A" and "View B" that runs through band 6 is
an artefact of the mis-filing. And the brief's clause *"View B is DEM-derived curvature and slope,
plus any radiometric bands present in `training_features.tif`"* therefore resolves to **one band**,
not to none as `knowledge/04` and `docs/irregularities.html` recorded. `src/gems53/radlayers.py`
moves it and adds the six radiometric products the official USGS release carries but the
competition did not ship.

---

## H53-1 · Radiometric total-count step: the range front that has no scarp

**Layers.** `R_tc_step900` (two-sided across-strike step of band 6, 900 m half-width, 1,900 m
along-strike persistence), `R_tc_edge` (|∇TC| in units per metre), `R_tc_line` (300 m Hessian line
response on TC), `R_tc_rank`. All from the official competition file, band 6.

**Physical signature targeted.** A *laterally persistent two-sided step* in total gamma-ray count.
Basin fill and range bedrock differ in bulk K/Th/U by a factor of two to five in the northwestern
Great Basin; the survey measures the top 30–50 cm, so the contrast is a property of **material**,
not of relief. The transform is deliberately not curvature: `T.scarp_step` requires both flanks to
move and the offset to continue for ~2 km, which is what removes canyon rims, stream banks and
alluvial-fan apices — the documented false-positive mode of fault mappers in this province
(Hermant et al. 2025, 50th Stanford Geothermal Workshop).

**Why it finds a fault the catalogue lacks.** USGS Quaternary fault and INGENIOUS traces are
compiled from geomorphic expression: a scarp, a lineament, a deflected drainage. Where a range-front
fault has been buried by Holocene fan alluvium the geomorphology is erased but the two materials
still sit either side of the plane, and the gamma-ray contrast survives. This is precisely the
population the competition asks for — new faults, not re-found ones — and it is the population
`knowledge/03` N-2 showed the surface view alone cannot reach (only 0.5 % of a *hidden whole
component*'s pixels lie within 5 px of a still-visible trace).

**How it differs from anything in the repo.** Nothing in `gems52.features` touches band 6 except to
take its absolute value as a magnetic tilt. `knowledge/03` N-7 killed *second-derivative
potential-field* transforms (Laplacian of strain ≈ 0.50, basement signed step 0.511, magnetic
transforms ≈ 0.52) — this is a *first-order two-sided step on a surface-geochemical field*, in View
B, never screened.

**Expected gain / cost.** Gain: unmeasured until the sweep; the corrected View B is what produced
the fold-0 winner (see H53-5), so the gain is already partly realised. Cost: **zero new data, 37 s
of compute** (`python3 scripts/run_h53.py --stage layers`). **Rank 2** — enabling, and free.

---

## H53-2 · Th/K and U/K ratio steps: alteration and cover, separated from topography

**Layers.** `R_thk_step900`, `R_uk_step900`, `R_thk_edge`, `R_uk_edge`, built from
`data/external/geodawn_extensions_u8.tif` bands 1–3 (Th/K, U/K, U/Th). Source: the official USGS
GeoDAWN release, Glen & Earney 2024, https://doi.org/10.5066/P93LGLVQ, public domain.

**Physical signature targeted.** The same two-sided persistent step, but on an **elemental ratio**
rather than on total count. Ratios remove the three things that make total count noisy — soil
moisture, radon escape and flight-height residual — so a ratio step is a lithological or alteration
boundary, not a weather boundary. Th/K rises across bedrock→alluvium (alluvium is Th-enriched in
detrital heavy minerals, K-feldspar is winnowed); U/K rises over silicification and iron staining.

**Why it finds a fault the catalogue lacks.** Two independent reasons. (i) A buried contact has no
geomorphology to map. (ii) A hydrothermal alteration zone is *not a geomorphic feature at all*: it
is a chemical deposit left by fluid that used the fault as a conduit, and it can sit hundreds of
metres from the plane. No Quaternary-fault mapping campaign records either.

**How it differs.** Measured this session: Spearman(U/K, detrended elevation) = **+0.007**,
Spearman(U/K, K) = −0.580, Spearman(Th/K, detrended elevation) = +0.208. The U/K field is
essentially orthogonal to relief, which makes it the only layer in this repository that can see a
fault with no topographic expression. The repo's View B is 100 % DEM-derived; it is structurally
blind to that case.

**Expected gain / cost.** Gain: small-to-moderate, unmeasured. Cost: **zero new data** (the rasters
are already restored and SHA-256-verified), 37 s of compute. **Rank 4.**

---

## H53-3 · Thermal-fluid points extended along a measured structural strike

**Layers.** `Th_point` and `Th_lineament`, built from
`data/external/gdr_wellspring_in_footprint.csv` (27,092 rows).

**Source, and the blocker discharged.** Great Basin Center for Geothermal Energy, *INGENIOUS –
Great Basin Regional Dataset Compilation*, Geothermal Data Repository submission 1391,
DOI **10.15121/1881483**, licence **CC-BY 4.0**,
https://gdr.openei.org/submissions/1391, file
https://gdr.openei.org/files/1391/wellspringdata.gdb.zip. `knowledge/02` H52-5 recorded this source
as **blocked** because the GDR host could not be re-resolved and an unverifiable file may not move
emitted mass. Both the submission page and the file URL were read this session (2026-10-06), the DOI
resolves, and CC-BY satisfies the competition's external-data rule. The blocker is discharged. The
one column *not* trusted is `dist_known_fault_px`: it is derived, so distance to the visible
catalogue is recomputed from `data/labels.tif` on the pinned grid.

**Physical signature targeted.** The silica **geothermometer**, not the point count. A quartz
geothermometer temperature of ≥ 100 °C at discharge means the water equilibrated with rock at that
temperature, i.e. circulated to roughly 2–4 km on a normal Great Basin gradient, and returned fast
enough not to lose its heat. Deep, fast, buoyant circulation in extensional terrain requires a
fault: the damage zone is the only structure with both the fracture permeability and the throw.
Measured on the grid this session: **12,570** distinct 100 m cells carry a well or spring;
**11,258** are more than 300 m from any mapped catalogue fault; **8,958** are more than 1 km away;
only **194** lie *on* a catalogue pixel; **991** cells record a discharge temperature ≥ 30 °C,
**362** ≥ 70 °C, and **147** carry a quartz geothermometer ≥ 100 °C.

**Why it finds a fault the catalogue lacks.** The thermal population and the mapped-trace
population barely intersect — 194 of 12,570 cells, 1.5 %. A hot discharge 3 km from the nearest
mapped trace is either an unmapped fault or a mapped fault whose trace is wrong or truncated, and
both are the competition's target. Staff confirmed in forum thread 11516 post #4 that truth may lie
within 300 m of a known trace and that those corrections are part of the goal.

**The step nobody has taken.** A spring is a *point*; under a 300 m kernel one point earns at most
1.0 and costs 0.2, which is a good trade but not a trace. So the point is extended along a **strike
measured from a 2 km structure tensor** of the radiometric field, and the walk is gated by that
tensor's coherence and truncated when coherence drops below 0.30 or the footprint ends. No layer
anywhere in this family converts a point observation into a linear hypothesis; every existing
point-derived layer (GDR spring density, volcanic vents, QFaults centroids) is a kernel-density
blob.

**Expected gain / cost.** Gain: moderate and *orthogonal* — the evidence is not a function of any
band in `training_features.tif`, so it cannot be reproduced by the other views. Cost: low; the data
is on disk, ~1 min of compute. **Rank 3.**

---

## H53-4 · Calibrated |G| and the credit bar, replacing the inherited budget

**Layers.** None — this is a calibration, and it changes every other hypothesis's placement.

**Signature.** The competition publishes DTI but not |G|. Inverting the metric on this laboratory's
own 13 scored rasters does. For a sparse emission (every emitted pixel 8-isolated, so no two
compete for the same truth pixel and `M = T`) the published form collapses to

    DTI = T / (0.2·S + 0.8·|G|)          ⇒     |G| ≥ 0.2·DTI·S / (1 − 0.8·DTI)

per submission; `scripts/calibrate_g.py` computes `S`, `A` (kernel-weighted coverage) and the
sparsity test for all 13, then picks the |G| that makes the implied per-covered-pixel truth density
`ρ_A = T/A` as close to constant as possible across the sparse rows — the only cross-submission
prediction the model actually makes. Output: `evidence/h53_g_calibration.json`.

**Why it matters.** `knowledge/05` fixed `K = 37654` "to match the 0.2778 file's footprint mass" —
i.e. the budget was inherited from an unrelated submission. The metric's own marginal rule says the
budget is an *output*: add a pixel while its expected credit exceeds `bar·(1 − C)`, with
`bar = 0.2·DTI/(1 − 0.2·DTI)`, and `bar` is a function of |G| through DTI. Getting |G| wrong moves
the bar and therefore the file size, in the wrong direction, silently.

**Caveat carried, not hidden.** Every score in the family's history is owner-reported; the board
publishes a number and a username, never a filename, hash or receipt (IR-52-011). Raster bytes are
SHA-256-verified, so `S`, `A` and the geometry are exact; only DTI is second-hand.

**Expected gain / cost.** Gain: bounded — it cannot create signal, it stops throwing it away.
Cost: ~2 min. **Rank 5** (necessary infrastructure, no signal of its own).

---

## H53-5 · Placement is worth more than prediction: the 600 m hard-core rule

**Layers.** None — an emitter, applied to whatever field wins.

**Signature.** The kernel `k(d) = max(1 − d/300 m, 0)` has a disc weight sum of exactly
**9.380298** (25 cells with k > 0, 29 with k ≥ 0; enumerated, never approximated). One isolated
emitted pixel can therefore contribute at most 9.380 of kernel-weighted coverage `A`, and the ratio
`A/S` — coverage per unit of budget — is bounded by that number. For a *straight trace* sampled
every `s` pixels the credited mass per emitted pixel is measured
(`evidence/h53_spacing_curve.json`):

| spacing s (px) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| mean kernel weight per truth px | 1.000 | 0.836 | 0.772 | 0.673 | 0.608 | 0.509 | 0.439 | 0.386 |
| **T / S** | 1.000 | 1.644 | 2.316 | 2.556 | **2.889** | **2.900** | 2.778 | 2.750 |
| A / S | 3.112 | 5.376 | 7.567 | 8.487 | 9.380 | 9.380 | 9.380 | 9.380 |

**The optimum is 500–600 m, not 100 m and not 200–300 m.** Measured on the family's real scored
rasters, `A/S` is 3.81 for a contiguous file (`h19-5`, 41 % of the ceiling), 6.56 for `d1-5`
(spacing ~1.5 px), 7.95 for `d2-8`, and **8.04 for the 0.2778 file** (86 %). So the best submission
this group ever made leaves 14 % of its placement efficiency on the table, and its contiguous
ancestor leaves 59 %.

**Measured, on a real fold, with everything else held identical.** `hide` fold 0, `n_truth = 10,336`,
same fitted field, same permitted set (footprint minus visible catalogue minus held-out components
grown by the buffer), same budget 37,654 px, same pixel-exact mask, same tested metric:

| emitter | DTI | A/S | % of ceiling |
|---|---|---|---|
| top-K (rank order — what the family shipped) | 0.03196 | 2.233 | 23.8 % |
| hard-core 200 m | 0.05130 | 6.184 | 65.9 % |
| hard-core 300 m | 0.06334 | 8.010 | 85.4 % |
| **hard-core 500 m** | **0.07151** | **9.303** | **99.2 %** |
| matched random control | 0.04387 | ≈9.38 | 100 % |

**+124 % over top-K at identical budget, and +63 % over the matched random control.** This is the
largest single effect measured in this repository, and it is a *placement* effect: it creates no
signal, it stops spending budget on pixels inside a 300 m disc that another emitted pixel already
covers.

**Why this is an emitter and not a tuning knob.** `gems52.emit.greedy_emit` maximises ρ̂-weighted
coverage and should find the same spacing on its own. The first version of
`gems53.emit_opt.coverage_greedy` reported `A/S` = 1.8–2.1 — *worse than top-K* — which looked like
evidence that a greedy packs into the peak of a peaked belief field. It was a bug: the running cover
was updated with `np.maximum(cf[nbi], kk, out=cf[nbi])`, and fancy indexing copies, so `out=` wrote
into a throwaway and no pixel ever learned that its disc was already covered. One test
(`sum of marginal gains == Σ ρ̂·K_E`, the telescoping identity) caught it at 107.7 vs 66.6. Fixed,
the greedy reaches `A/S` = 9.27 (98.8 % of the ceiling) and banks **20 % more** ρ̂-weighted coverage
than a hard-core thinning of the same field and **33 % more** than top-K, on both a flat and a
clustered belief (`tests/test_h53_emit.py`). So the claim "the greedy under-spreads when ρ̂ is
peaked" is **withdrawn**; IR-52-025 records the correction. Both emitters are measured on both
instruments and the winner ships — see §Measured below.

**Expected gain / cost.** Gain: measured, +0.040 absolute on `hide` fold 0; the algebra says the
same 14 % → 99 % move on the 0.2778 file is worth roughly +0.03 DTI on the board at unchanged
geology. Cost: **already implemented**, ~5 s per emission. **Rank 1.**

---

## Ranking, as written before scoring

| rank | id | hypothesis | expected DTI gain | implementation cost | new external data needed |
|---|---|---|---|---|---|
| 1 | H53-5 | 500–600 m hard-core placement, budget from the metric | **+0.040 measured on `hide` fold 0** (+124 % rel.) | done | none |
| 2 | H53-1 | band 6 is radiometric TC → corrected View B, TC step/edge/line | enabling; realised inside the fold-0 winner | 37 s | none |
| 3 | H53-3 | thermal points extended along a structure-tensor strike | moderate, and orthogonal to every band | ~1 min | INGENIOUS/GDR 1391, DOI 10.15121/1881483, CC-BY — **verified reachable** |
| 4 | H53-2 | Th/K and U/K ratio steps (buried contact + alteration) | small–moderate | 37 s | USGS GeoDAWN, DOI 10.5066/P93LGLVQ — already on disk |
| 5 | H53-4 | |G| calibrated from our own scored history | bounded; stops waste | ~2 min | none |

**Promotion rule (pre-registered, not moved later).** A hypothesis may touch a weekly submission
slot only if, on **both** instruments (`hide` and `tip`), it beats the matched-budget random
control in **≥ 3 of 4** folds *and* beats the best H52 arm recorded in `evidence/holdout_*.json`.
Never pool the two instruments: `union_cor|37654` is the best `tip` arm (0.0320) and the worst
`hide` arm (0.0001), and each is structurally blind to what the other can see (`knowledge/05` §4).
