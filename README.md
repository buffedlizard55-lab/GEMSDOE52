# GEMSDOE52

> **H59 — Unique TIF submission generated 2026-10-08 UTC**
>
> **Download the submission TIF**: [`docs/downloads/gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif`](docs/downloads/gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif)
>
> **How to submit**: See [`docs/executive-summary.html`](docs/executive-summary.html) or the [GitHub Pages site](https://buffedlizard55-lab.github.io/GEMSDOE52/)
>
> **File**: 130,768 bytes · single-band float32 · EPSG:32611 · 3,292 × 3,730 · values {0, 1} · 37,654 emitted pixels
> **SHA-256**: `4a60f9410405c7a4df12c004736e57596fa8c6d4877d667d694b002740f635f6`
> **Format gate**: PASS (all checks) · **Novelty vs H33**: 98.8% (only 466 pixels overlap)

## Quick Start

```bash
# 1. Restore competition data (requires access to sibling repos)
python3 scripts/restore_data.py --force

# 2. Build the H59 submission
PYTHONPATH=src python3 scripts/build_h59_submission.py

# 3. Download the TIF from docs/downloads/ or submission/
# 4. Submit at https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/
```

## What is this project?

This repository generates GeoTIFF submissions for the [DOE GEMS competition](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) on DrivenData. The competition asks participants to discover previously unknown geothermal faults in the northwestern Great Basin, Nevada, using airborne geophysical data.

### The metric: Distance-weighted Tversky Index (DTI)

```
DTI = TPw / (TPw + α·FPw + β·FNw + ε)
k(d) = max(1 - d/R, 0)    where R = 300m, α = 0.2, β = 0.8
```

Key insight: at DTI ≈ 0.28, the acceptance rule is: *emit a pixel iff it is within 224m of an uncatalogued fault pixel*. The only lever that moves the score is the **ranking** of candidates.

## H59: Multi-scale geophysical edge coherence + co-training disagreement

### Method

1. **View A (Geophysical)**: Multi-scale gradient edges from gravity anomaly (band 13), RTP magnetic (band 2), gravity vertical gradient (band 11), TMI horizontal gradient (band 3), and geodetic strain (band 4) at Gaussian scales σ=1,2,3 (100-300m).

2. **View B (Surface)**: Radiometric total count edges (band 6), DEM slope (band 19), surface conductivity (band 17).

3. **Co-training disagreement** ([Blum & Mitchell, COLT '98](https://doi.org/10.1145/279943.279962)): Where View A is confident (high geophysical edge response) but View B abstains (low surface signal) → buried fault beneath cover. 532,408 A-only candidate pixels identified.

4. **Fault-tip continuation**: Exponential proximity boost (2km decay) near 55,045 identified catalogue fault tips.

5. **Metric-aware greedy placement**: 37,654 pixels placed by `greedy_emit` with the triangular kernel k(d) = max(1−d/300m, 0).

6. **Catalogue exclusion**: No emission within 200m of any mapped catalogue pixel (min distance: 300m).

### Why this is unique

| Approach | Method | Score | Pixels | Novel vs H33 |
|----------|--------|-------|--------|--------------|
| H33 (GEMSDOE32) | Dotted ridge minus catalogue ring | 0.2778 | 37,654 | — (reference) |
| H25-1 D2.8 | Dotted with H19-5 powerlaw | 0.2600 | 44,090 | Different |
| H27 topo-gap | Topographic gap closure | 0.2449 | 61,328 | Different |
| **H59 (this)** | **Multi-scale edge + co-training** | **Pending** | **37,654** | **98.8%** |

### Ranking field composition

```
ranking = 0.35 × geophysical_edges     (multi-scale gravity + magnetic)
        + 0.15 × surface_score         (radiometric + slope + conductivity)
        + 0.15 × tip_proximity         (exponential decay from fault tips)
        + 0.15 × external_score        (LiDAR scarp + GeoDAWN extensions)
        + 0.20 × A_only_indicator      (co-training disagreement)
```

## Data sources

| Source | Description | URL |
|--------|-------------|-----|
| USGS GeoDAWN | Airborne magnetic and radiometric surveys | [usgs.gov](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) |
| INGENIOUS | Great Basin geothermal field mapping | [gbcge.org](https://gbcge.org/current-projects/ingenious/) |
| GDR OpenEI | Geothermal wells, springs, temperature | [gdr.openei.org](https://gdr.openei.org/submissions/1391) |
| DrivenData | Competition data and rules | [drivendata.org](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |

## Competition context

- **Leaderboard top**: 0.3774 (xiaofanhu, as of 2026-10-07)
- **Best in family**: 0.2778 (H33, GEMSDOE32)
- **Target**: Beat 0.3195 (DARD)
- **Submissions per week**: 3

## Project structure

```
scripts/              # Pipeline scripts
  build_h59_submission.py  # H59 TIF generator
  restore_data.py          # Data restoration from sibling repos
src/gems52/           # Core library
  metric.py           # DTI metric (literal transcription)
  emit.py             # Metric-aware greedy placement
  grid.py             # Grid constants and footprint
  gates.py            # Format and uniqueness gates
  cotrain.py          # Two-view co-training
  holdout.py          # Spatially-blocked validation
docs/                 # GitHub Pages site
  index.html          # Overview + download
  executive-summary.html  # Submission instructions
  h59-method.html     # Method details
  h59-evidence.html   # Validation evidence
  downloads/          # Downloadable TIF files
data/                 # Competition data (gitignored)
evidence/             # Machine-readable evidence
knowledge/            # Research notes and hypotheses
registry/             # Manifests and preregistrations
submission/           # Current submission pointer
```

## Core Values

### Maximize P(Win)
"Maximize the Probability of Winning": our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win).

### Own the Outcome
We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve.

## Full project prompt

<details>
<summary>Click to expand the complete project prompt</summary>

Co-training between a geophysical view and a surface view, with disagreement as the discovery signal. Blum and Mitchell (COLT '98, pp. 92–100, doi:10.1145/279943.279962) show that when each example has two views, each sufficient and approximately conditionally independent given the class, two learners trained on separate views can use each other's confident predictions on unlabeled data. View A is potential-field and subsurface (gravity, magnetics, strain, seismicity). View B is surface (DEM-derived curvature and slope, plus any radiometric bands present in training_features.tif). Test the independence assumption empirically: correlate each view's spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are strongly correlated. Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and B is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface artifacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare against a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the GeoTIFF, apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output isn't merely the union of the two views.

The goal is to generate a unique TIF submission for the DOE GEMS competition that scores higher than 0.2778 (the best family result) and ideally beats 0.3195 (DARD on the leaderboard). The submission must be:
- A single-band float32 GeoTIFF
- EPSG:32611, 3730×3292, 100m resolution
- Values in [0,1]
- Matching the sample_submission.tif grid exactly
- Unique (not a copy of any prior submission)

</details>

## Limitations

1. **No organizer-authenticated score**: The data files are SHA-pinned owner mirrors, not authenticated downloads from DrivenData. The bytes match the manifest but the provenance chain to the organizer is not independently verified.
2. **Local holdout is not a leaderboard forecast**: The spatial-blocked validation measures relative performance, not absolute DTI.
3. **No ground truth for new faults**: The competition's hidden truth set is unknown; all claims about discovering new faults are hypotheses pending Phase 2 verification.
4. **Co-training independence assumption**: The conditional independence of View A and View B errors is tested but not proven. The measured correlation is low but not zero.

## Reproducibility

```bash
# Full pipeline
python3 scripts/restore_data.py --force
PYTHONPATH=src python3 scripts/build_h59_submission.py

# Verify the output
PYTHONPATH=src python3 -c "
import rasterio, numpy as np
with rasterio.open('submission/$(cat submission/LATEST.txt)') as ds:
    arr = ds.read(1)
    print(f'Shape: {ds.shape}, CRS: {ds.crs}')
    print(f'Values: [{arr.min()}, {arr.max()}]')
    print(f'Positive: {(arr > 0).sum()}')
"
```

## Links

- [Competition page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [GitHub Pages site](https://buffedlizard55-lab.github.io/GEMSDOE52/)
- [Submission guide](https://buffedlizard55-lab.github.io/GEMSDOE52/executive-summary.html)
- [USGS GeoDAWN data](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [INGENIOUS project](https://gbcge.org/current-projects/ingenious/)
- [GDR OpenEI](https://gdr.openei.org/submissions/1391)
- [Blum & Mitchell (1998)](https://doi.org/10.1145/279943.279962)
