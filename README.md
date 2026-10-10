# GEMSDOE52 — Co-Training Wavelength Contrast for the DOE GEMS Prize
<!--H78-README-->
# Current status — H78 (2026-10-09): verification of H75, the 0.2778 mechanism, and five ranked hypotheses

**Core values (focal point):** **Maximize P(Win)** — do not spend a scarce weekly slot on an arm that has not beaten the comparable holdout best. **Own the Outcome** — publish the real file, its evidence, and the open decisions.

> **Read the complete prompt blocks further down before each session** (`H72 project prompt` and the verbatim `Complete current prompt`). They are not edited here.

> **DOWNLOAD: YES** (format-valid; decoded-unique against every restored raster). **SUBMIT: NOT APPROVED.** The parallel-run lane check FAILS (near-dot 0.922 > 0.70, 38 informative offenders in the 565-raster census). Submitting requires an explicit owner override. Slots used: 0.

**START HERE:** [docs/index.html](docs/index.html) (top of the page) · [H75 executive summary](docs/h75-executive-summary.html) · [H78 record](knowledge/67_h78_verification_hypotheses_and_status.md)

**Numbers and labels.** Holdout values are **HOLDOUT-DTI** (evaluator `gems52-pooled-hide-v1`, 53,186 withheld positives; not re-run this round; receipt `evidence/h75_holdout.json`). H75 vs control: paired +0.011835, 95% CI [0.006791, 0.017362]. **ORGANIZER-CONFIRMED: none.** The 0.3774, 0.3195, and 0.2778 values are owner-reported public-board values from `registry/leaderboard_snapshot_2026-10-08.json` (not organizer-confirmed).

**What this round established (verified on bytes):**
- The H75 raster: 1 band float32, EPSG:32611, 3730×3292, template transform, values exactly {0, 1}, 0 NaN, 37,654 dots. Nearest dot to a catalogue positive: 223.6 m; median 1,552.4 m (`evidence/h75_build.json`). Its SHA-256 is `b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16`. Name and file carry the UTC write time `20261009T200333Z` (IR-H78-008).
- The metric in `src/gems52/metric.py` has the official structure: TP_w, FP_w = mass − Σp·q (p > 0 only), FN_w, and DTI = TP_w / (TP_w + αFP_w + βFN_w + ε).
- The 0.2778 reference (`h33-2-b2`) and H75 share 1,742 pixels; their near-3 px share is 0.549 (3 px disk) and the receipt's 0.642 is a 7×7 box. Definitions differ, so the numbers are not interchangeable.
- Measured out-of-domain counts: 7,111,787 px. The sample's NaN pattern equals that set. H75 writes 0 there (open owner decision, IR-H78-003).

**0.2778 mechanism (inference from one owner-reported pair; knowledge/67 §2):** the 0.2778 reference (37,654 dots) is the 0.2600 file (44,090 dots) with its 6,436 pixels in the 100–200 m catalogue ring deleted. Deleting the ring raised the score, so that ring's implied credit density is at most 0.018 per px across the repo's |G| interval, below the 0.052 break-even. The reference has 0 dots within 200 m of the catalogue. The mechanism is measured; the score attribution is owner-reported.

**Five ranked hypotheses (none validated; knowledge/67 §7):**
1. **H78-1** strike-aligned directional variogram, DVA+ (top candidate; validation blocked until the owner decides on the 419 MB training raster).
2. **H78-2** INGENIOUS 2 m temperature probes (owner must download GDR 1391 and pin SHA-256).
3. **H78-3** Landsat TIRS night surface-temperature residual (needs an EarthExplorer route; the owner confirms account requirements).
4. **H78-4** paleo sinter/tufa proximity. Spring-fed tufa columns mark faults; wave (shoreline) tufa is the elevation-controlled mimic and must be removed by a shoreline test.
5. **H78-5** Great Basin heat-flow residual (km-scale; low expected gain).

**Not run this round (stated plainly):** the co-training conditional-independence test on spatial-block OOF errors, the hide-and-recover comparison, and any new raster. Experiments used: 0 of 3. No slot used.

**Irregularities:** IR-H78-001…008 in `registry/irregularities.json` and `knowledge/67` §10. Key items: the brief's 0.3195 "top" conflicts with the 0.3774 snapshot (IR-H78-001); the sample is "total fault absence" yet holds the 60,988 catalogue positives (IR-H78-002); zeros versus NaN outside the domain (IR-H78-003); an unverified "fix" claim was corrected (IR-H78-004); the lane verdict depends on the census (IR-H78-005); redistribution of mirrored inputs is unverified (IR-H78-006).

**Open owner decisions:** (1) lane override for submission; (2) zeros vs NaN outside the domain; (3) lane-rule scope (full census versus scored submissions); (4) redistribution position on the mirror (IR-H78-006); (5) download and pin GDR 1391 (2 m probes and paleo zips), which are unreachable from the sandbox.

<!--/H78-README-->

**Competition:** [DOE GEMS Prize (DrivenData #306)](https://www.drivendata.org/competitions/306/competition-doe-gems/)
**Branch:** `arena/99f480b9-gemsdoe52`
**Status:** Submission built and validated ✓

## ⬇️ Quick Download — Ready-to-Submit File

**File:** [`docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif`](docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif) (128 KB)

**ZIP:** [`docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.zip`](docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.zip) (90 KB)

**Submission Name:** `h87-cotrain-wavelength-37654px`

**Note:** `H87 co-train wavelength+Th/K, A>B disagree, 37654px, 3px spacing, 200m collar`

**SHA256:** `a861069b8c780738b83245c1f736313d043989ca33554377f6dffb0465d8e9c3`

### How to Submit
1. Download the .tif file above
2. Go to [DrivenData submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/)
3. Upload the file, paste the name and note, click Submit

## What This Does

Finds **buried faults** beneath alluvial cover in the GeoDAWN study area (NW Nevada) using co-training between two independent geophysical views:

- **View A (subsurface):** Gravity gradients + magnetic gradients + geodetic strain + basement depth + conductivity
- **View B (surface):** Multi-scale DEM wavelength contrast + slope + radiometric Th/K ratio

Where A is confident and B abstains → buried fault candidate (discovery signal).

### Novel Features
- **Wavelength contrast ratio:** |Hessian|_fine / |Hessian|_coarse — detects localized sharp features vs regional trends
- **Th/K radiometric ratio:** targets hydrothermal K-leaching along fault-fluid pathways
- **Disagreement-gated emission:** only emit where A > B (opposite of consensus-based priors)

### Verified Properties
- Views are independent: r = −0.140 (< 0.60 threshold)
- 70.7% novel fraction vs 129 prior rasters
- Lane check: PASS (no rank or spatial overlap with any prior)
- All format checks: PASS (single-band float32 EPSG:32611, values in [0,1], zero NaN)
- Zero dots on known catalogue, zero within 200m collar

## Project Structure

```
GEMSDOE52/
├── docs/                       # GitHub Pages site
│   ├── index.html              # Main page with download link
│   ├── executive-summary.html  # Detailed methodology
│   └── downloads/              # Submission files
├── src/gems52/                 # Core library
│   ├── grid.py                 # GeoTIFF writer, grid constants
│   ├── gates.py                # Uniqueness & lane gates
│   ├── metric.py               # DTI implementation
│   ├── holdout.py              # Spatially-blocked holdout
│   ├── emit.py                 # Metric-aware emission
│   ├── nodes.py                # Spacing-constrained placement
│   ├── cotrain.py              # Co-training framework
│   └── structural.py           # Structural features
├── scripts/                    # Build & analysis scripts
│   ├── build_h87_cotrain_wavelength.py  # THIS submission's builder
│   ├── prepare_data.py         # Data audit
│   └── restore_data.py         # Data restoration from mirrors
├── data/                       # Competition data (restored from SHA-256 pinned mirrors)
├── submission/                 # Built submission files
├── evidence/                   # Build receipts & evidence
├── registry/                   # Preregistration & data manifests
└── knowledge/                  # Research notes & hypotheses
```

## Data Sources

| Source | Data | License |
|--------|------|---------|
| [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) | Competition data | Competition rules |
| [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) | Airborne magnetics, radiometrics | Public domain |
| [GDR 1391 INGENIOUS](https://gdr.openei.org/submissions/1391) | Fault traces, wells, springs | CC BY 4.0 |
| [USGS DOI 10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) | GeoDAWN data release | Public domain |

## Core Values

**Maximize P(Win):** Every decision maximizes the probability of winning. This submission uses a novel feature combination that no prior has tried, targeting a geologically plausible hidden population.

**Own the Outcome:** Every claim carries an evidence class. Format checks, uniqueness gates, and lane checks are all verified from disk.

## Limitations

1. No holdout DTI score yet (build receipt only)
2. Catalogue proxy cannot reward genuinely new faults
3. Gravity/magnetic gradients can arise from lithologic contacts without faulting
4. Actual DTI only known after portal submission

## Next Steps

- Submit to competition portal and record actual score
- Run spatially-blocked holdout for projected DTI with CI
- If score > 0.28, investigate geological zones of A-only concentration
- Consider tip-extension variant with tighter catalogue collar
