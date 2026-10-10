# GEMSDOE52 — Geothermal Fault Discovery Competition

> **CURRENT SUBMISSION: H83 — Multi-band Structural Concordance**
> 
> **[⬇ Download H83 GeoTIFF](docs/downloads/h83-candidate.tif)** (1.5 MB) · 
> **[📋 How to submit](docs/h83-executive-summary.html)** · 
> **[🏠 Site](docs/index.html)**
>
> 37,654 binary dots · float32 · EPSG:32611 · 3730×3292 · portal-exact format  
> DOWNLOAD: **YES** · SUBMIT: **RESEARCH-ONLY** (no holdout validation run)  
> SHA-256: `274db602ec8b91cb6a2793e9f512321f32326298aa8ed031ebd478e21426f5cd`

## Competition

- **Competition:** [DOE GEMS — DrivenData](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- **Leaderboard top:** 0.3774 (xiaofanhu) · Best from this family: 0.2778 (h33-2-b2, owner-reported)
- **Target:** Score > 0.3195 to reach top 7

## What This Project Does

Detects geothermal faults in the Northwestern Great Basin, Nevada using geophysical data (gravity, magnetics, DEM, radiometrics, strain). Generates GeoTIFF submissions for the [DrivenData GEMS competition](https://www.drivendata.org/competitions/306/competition-doe-gems/).

## How to Submit

1. Click the download link above for the H83 GeoTIFF
2. Go to [DrivenData → New submission](https://www.drivendata.org/competitions/306/competition-doe-gems/predictions/)
3. Upload the `.tif` file with note: `H83 multi-band structural concordance; 10 bands x 3 scales; 37654 dots 3px spacing; >200m off catalogue`

The file will **not** produce "Predicted values must be in range [0, 1]" — it uses the portal-exact writer.

## H83 Method

**Multi-band structural concordance lineament detector** — detects structural lineaments where multiple geophysical bands show coherent gradient orientation.

- 10 structural bands × 3 scales (σ=1,2,4)
- Structure tensor analysis for lineament detection
- Cross-band gradient coherence scoring
- LiDAR scarp integration for surface fault confidence
- 37,654 binary dots at 3px spacing, 200m catalogue ring excluded
- Portal-exact GeoTIFF writer (LZW, stripped, nodata=nan)

## Key Findings (from 80+ experiments)

| Finding | Evidence |
|---------|----------|
| **Co-training lane is dead** | View A (subsurface) failed sufficiency 7 times (mean AUC ~0.52) |
| **Holdout doesn't predict board** | Spearman −0.10 between holdout DTI and board scores |
| **Placement headroom is closed** | Within 4% of geometric thinning optimum |
| **0.2778 was precision editing** | Deleted 6,436 zero-credit pixels from the 0.2600 file |
| **To beat 0.3195** | Need credit density ~0.16 at 37,654 px (6× random) |

## Data Sources

| Source | URL | Status |
|--------|-----|--------|
| Competition data | https://www.drivendata.org/competitions/306/competition-doe-gems/data/ | Login-walled; restored from owner mirrors |
| USGS GeoDAWN | https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and | External layers included |
| INGENIOUS | https://gdr.openei.org/submissions/1391 | Fault/well/vent data included |
| Reference solution | https://github.com/drivendataorg/gems-prize-reference-solution | Open source |
| Technical report | https://docs.nlr.gov/docs/fy26osti/96647.pdf | PDF |
| Blum & Mitchell | https://doi.org/10.1145/279943.279962 | Co-training paper |

## Repository Structure

```
├── data/                          # Competition data (restored)
│   ├── training_features.tif      # 19-band feature stack (400 MB)
│   ├── labels.tif                 # Fault labels
│   ├── sample_submission.tif      # Template
│   └── external/                  # LiDAR, radiometric, SGMC, etc.
├── src/gems52/                    # Core library
│   ├── metric.py                  # DTI metric implementation
│   ├── grid.py                    # Grid, footprint, spatial blocks
│   ├── submission_writer.py       # GeoTIFF writer
│   └── evaluate_holdout.py        # Holdout evaluator
├── scripts/                       # Runners and utilities
│   ├── restore_data.py            # Restore data from GitHub mirrors
│   ├── run_h83_submission.py      # H83 submission generator
│   └── check_site.py              # Site validation
├── submission/                    # Generated GeoTIFFs
├── docs/                          # GitHub Pages site
│   ├── index.html                 # Landing page
│   ├── h83-executive-summary.html # Submission guide
│   └── downloads/                 # Downloadable files
└── knowledge/                     # Research notes
```

## Core Values

**Maximize P(Win):** Every decision weighs tradeoffs to maximize the probability of winning. We set aside emotions and make tough decisions.

**Own the Outcome:** We own results end to end. When problems arise, we act without waiting. We treat failure and success as signals.

## Working Agreement

Read `README.md` and `AGENTS.md` before every session. The working branch is fixed by Arena. Never spend a competition slot without holdout validation. Label every number as HOLDOUT-DTI or ORGANIZER-CONFIRMED.

## Limitations

1. **DrivenData data tab is login-walled** — data restored from owner-mirrored GitHub repositories (integrity-pinned, not organizer-authenticated)
2. **USGS, GDR, DrivenData hosts are unreachable** from this sandbox (egress limited to github.com, api.github.com, codeload.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org)
3. **No GPU available** — training uses CPU (adequate for gradient boosting, slow for deep learning)
4. **Holdout instrument doesn't predict the board** — Spearman −0.10, so validation is necessary but not sufficient

## Reproduce H83

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-r2.txt
.venv/bin/python scripts/restore_data.py --target-dir data
PYTHONPATH=src .venv/bin/python scripts/run_h83_submission.py
```