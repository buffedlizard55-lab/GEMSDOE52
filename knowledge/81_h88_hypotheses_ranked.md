# 81 · H88 — candidate hypotheses, ranked (written before this round's fits were read)

Scope: the brief asks for **3–5 candidate geological hypotheses this repository has not tried**, each
naming the specific layers, the physical signature, why it should catch a fault missing from the
USGS/INGENIOUS catalogue *rather than one already in it*, and how it differs from what is implemented
here; ranked by expected DTI gain and implementation cost; the top one validated on the
spatially-blocked holdout before any slot decision (a slot decision is the owner's, and is separate).

Honest prior, stated first: this repository's own record (`knowledge/03`, `knowledge/76`) is that every
potential-field transform tested at the 100 m cell sits at chance on the holdout, and that the holdout
does **not** rank the public board (Spearman −0.10). So the ranking below is by (evidence that the
mechanism addresses a *measured* board effect) × (data already in hand) ÷ (cost) — never by a projected
score. **A projection is not written as a score.**

| rank | id | layers (band tag in `training_features.tif`; external layers as named) | physical signature targeted | why it should catch a catalogue-missing fault | how it differs from everything already here | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **H88-A · prevalence-matched budget calibration + disagreement-stratified emission** | all — uses the two views' out-of-fold scores (View A 36 ch; View B 37 ch incl. `raw_band_06` TC and the GeoDAWN `X_rad_*`) | none new: it targets the *budget/placement* term, which the board's own history says dominates (Spearman(mass, score) = −0.94, 13 rasters, `knowledge/80`) | the scored population is off-catalogue by definition; a sparser, better-placed emission converts the same credit into a higher DTI (`DTI = T/(0.2(T+S−M)+0.8\|G\|)`) | no prior round built a **prevalence-matched** instrument (every instrument here scores a truth set ~4× denser than the organiser-implied 0.112–0.294 %), and no prior round allocated the budget across disagreement strata by a frozen rule | medium (reuses the cached out-of-fold fits) | **validated this round** on `gems52-pooled-hide-v1` and both prevalence-matched instruments |
| 2 | **H88-B · de-trended K/Th alteration residual** | external GeoDAWN K, Th (`data/external/geodawn_rad_u8.tif`, USGS DOI 10.5066/P93LGLVQ) | hydrothermal K enrichment and Th depletion *relative to a 5 km local trend* — removes the lithological background that dominates the raw ratio | fault-controlled fluid pathways leach K and precipitate clays along the fault; many INGENIOUS traces were mapped geomorphologically, so geochemical halos can mark faults the catalogue lacks | H87 used the raw `Th/K` band; no round here has used a **de-trended residual**, which is the classic alteration index rather than a lithology map | low | untested (not reachable inside this round's 3-experiment budget) |
| 3 | **H88-C · seismicity lineation (directional gradient of the 100 km-kernel seismicity density)** | bands 10 `deq_n100a15`, 16 `ieq_n100a15` | anisotropic spatial gradient of earthquake density along strike | faults that are seismically active but unmapped produce lineated activity, independent of surface geomorphology | these bands have only ever been covariates inside View A; no standalone directional holdout test exists in this repo (`knowledge/78` §4 rank 3 is "untested standalone") | low | untested |
| 4 | **H88-D · theta map on the RTP magnetic field (Wijns et al. 2005 normalised horizontal-derivative-of-tilt)** | band 2 `rtp` (plus band 3/9 for the derivatives) | an equal-amplitude magnetic edge map; avoids the saturation of strong sources | equalisation can expose weak, short-wavelength contacts where the catalogue is sparse | the repo implements tilt/`tc` everywhere (29 files) but never the theta normalisation; the *information* overlaps tilt, so expected gain is small | low | untested; ranked below because it is a re-normalisation of a signal already used |
| 5 | **H88-E · Euler deconvolution, structural index 1, on the upward-continued TMI** | band 2 `rtp`, band 9 `tmi_vg`, external `X_mag_TMI_up150` | depth-resolved thin-sheet edges | adds a depth axis the 2-D transforms lack | H86 tested **SI 0** and measured it at random (0.0777 vs 0.0754); SI 1 and the upward-continued field are explicitly listed as untested in `knowledge/79` §Result | medium | untested; the family is already measured near-random, so it ranks last |
| — | **H88-F · external ASTER/Landsat alteration indices or the INGENIOUS 2-m temperature survey** | external products (ASTER L1T/SWIR; GDR 1391 "2m Temperature Probes", DOI 10.15121/1881483) | surface alteration mineralogy / shallow thermal anomaly | alteration and shallow heat flow can mark fault-fed systems | bytes are not in this repository | high | **not viable in this sandbox**: the egress allowlist is `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. `gdr.openei.org` and USGS bulk scene servers are **not reachable** (verified by `scripts/restore_data.py`'s transport notes and this round's restore, which succeeded only through `api.github.com` mirrors). A user-side download with SHA pins, or an allowlist entry, is required before this can be proposed as viable. |

## Why H88-A is first, and what "validated" means here

1. **It attacks the measured dominant term.** Over the 13 restore-able scored rasters,
   Spearman(emitted mass, owner-reported score) = **−0.9436**; the champion lineage
   `d1-5 → d2-8 → h33-2-b2` earned +0.030 DTI (0.2477 → 0.2778) by shipping *fewer, better-placed* dots
   with no detector change (`knowledge/80` §3). No detector swap in this repository has ever produced a
   board effect of that size.
2. **It is the prerequisite the other candidates lack.** Until the instrument's prevalence matches the
   organiser-implied prevalence, every candidate is ranked by an instrument that over-rewards recall,
   so detector work cannot be judged. Fixing prevalence is therefore *cheaper than any detector* and
   unlocks the rest.
3. **Validation protocol (frozen before the fits were read):** the two pm instruments keep whole
   8-connected components (seeded permutation until the target count), the budget ladder is
   `[1200, 1800, 2445, 3600, 5000, 7000, 9413]` dots per fold, the budget rule is "maximise the average
   rank of the candidate's pooled DTI across both pm instruments, ties to the smaller budget", the
   A-only quota is `F_A_QUOTA = 0.15`, and the emission is finally guarded to
   `[14,000, 27,000]` whole-grid dots. Arms are matched-budget throughout.
4. **Honest failure modes, named:** (a) whole-component thinning reduces the pm truth to a few hundred
   components per fold, so CIs are wide; (b) if the pm instruments still prefer large budgets, the
   board's mass lever is *not* reproduced inside the instrument and the emitted budget falls back to
   the arithmetic target of `knowledge/80` — in that case the round reports a conflict rather than a
   win; (c) the A-only stratum is measured anti-informative on the catalogue instrument
   (`knowledge/03` N-1), so its 15 % is a **brief-mandated** reservation carrying written reasoning,
   not a measured gain, and is labelled as such in the run card.

## What is explicitly *not* re-proposed

Co-training pseudo-label exchange as the *detector* (refuted, `knowledge/03` N-1); whole-footprint
top-k (N-2); the geo-concordance field (H85 negative); further reduction operators on the directional
variogram family (H84 NEGATIVE); plain agreement/consensus emissions (H86 measured −0.006 vs random).
Structure-tensor and geothermal-channel variants are measured at or near random and are not re-proposed
without a new mechanism.

## Sources checked this round

* Competition metric and format: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* Leaderboard (2026-10-10): https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* GeoDAWN release cited by the organiser: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and (DOI 10.5066/P93LGLVQ)
* INGENIOUS GDR 1391 (access-blocked from this sandbox): https://gdr.openei.org/submissions/1391 · https://gbcge.org/current-projects/ingenious/
* Blum & Mitchell, COLT '98: https://doi.org/10.1145/279943.279962
* EPSG:32611: https://epsg.io/32611
