# GEMSDOE52 — Co-Training Wavelength Contrast for the DOE GEMS Prize

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
