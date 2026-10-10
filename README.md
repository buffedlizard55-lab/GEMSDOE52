# GEMSDOE52 — Co-Training Wavelength Contrast for the DOE GEMS Prize

**Competition:** [DOE GEMS Prize (DrivenData #306)](https://www.drivendata.org/competitions/306/competition-doe-gems/)
**Working branch:** `arena/f7adbaaa-gemsdoe52`
**Status (2026-10-10, after round H88):** no file in this repository currently passes the registered
promotion bar. **Download anything here for review; do not spend a weekly slot yet.**

## Submission status board

| file | round | HOLDOUT-DTI (53,186 withheld positives) | lane gate | OK to submit? |
|---|---|---|---|---|
| `docs/downloads/h88-candidate.tif` | H88 | **0.0632** at 75.2k dots (random 0.1346; `single_B` 0.2228; paired −0.1596 [−0.1821, −0.1374]) | **DUPLICATE/STOP** (0.969 ≤3 px to our own H61 candidate; 1.000 to the scored lattice probe) | **NO — research only** |
| `docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif` | H87 | **not run** — the build receipt says `HOLDOUT-DTI (not yet run)` | PASS (0.413) | **NO — validation incomplete** |
| `docs/downloads/h75-candidate.tif` | H75 | 0.1864 vs `single_B` 0.1745, paired +0.0118 [0.0068, 0.0174] → **promotes** | **DUPLICATE/STOP** (0.922) | **NO — research only per protocol** (owner may override the lane rule) |
| older rounds in `docs/downloads/` | H52–H86 | mixed / negative | mixed | **NO** unless its own run card says otherwise |

Every row above is a label read off that round's run card in `evidence/`; nothing is inferred from
the leaderboard. The board itself is not measurable from this sandbox (no portal credentials).

## ⬇️ Latest artefact — H88 (DOWNLOAD YES, SUBMIT NO)

**File:** [`docs/downloads/h88-candidate.tif`](docs/downloads/h88-candidate.tif) (93,751 bytes,
17,707 set pixels, single band float32, EPSG:32611, values exactly {0,1})
**ZIP:** [`docs/downloads/h88-candidate.zip`](docs/downloads/h88-candidate.zip) (50,631 bytes, holds exactly one TIFF)
**Canonical name:** `submission/gems52-h88-cotrain-disagree-supportcal-17707px-20261010T222145Z.tif`
**SHA-256:** `ddf09d89003eacb8a9df8896a9783e078a6fca5500445b24f3375d3db4d79d4f`
**Submission name / note for the portal:**
`h88-cotrain-disagreement-support-cal-17707px-20261010` /
`H88 co-train disagreement disagreement_post, prevalence-calibrated 17707px, 3px spacing, 200m collar`
**Reasoning dossier:** [`docs/downloads/h88-a-only-reasoning.csv`](docs/downloads/h88-a-only-reasoning.csv)
(17,707 rows: interpretation + named non-fault mimic + falsifier per dot)
**Full card:** [`evidence/h88_run_card.json`](evidence/h88_run_card.json) · **write-up:** [`knowledge/81_h88_results_and_limits.md`](knowledge/81_h88_results_and_limits.md)

Why it is **not** submittable, in one line each: the mandated disagreement field measures 0.0632
pooled HOLDOUT-DTI at 75.2k dots, **below the 0.1346 random arm** and 0.1596 below the single-view
control with a paired CI excluding zero; and the directed ≤3 px dot-proximity gate stops at 0.969
against our own H61-family candidate. Both facts are recomputed from the shipped bytes by
`scripts/h88_run_card.py`, which also proves the emission still reproduces from the current code.

### How to submit (only after a row above says SUBMIT YES)
1. Download the `.tif` (or the ZIP, which holds the same bytes).
2. Open the [DrivenData submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/).
3. Upload the file, paste the row's submission name and note, click Submit.
4. The portal has previously rejected files with `Predicted values must be in range [0, 1]`; every
   file here is written by `gems52.submission_writer.write_submission`, the zero-outside variant
   (IR-H85-004), and the run card records `min = 0.0, max = 1.0, n_nan = 0`.

## What this work is

Finds **buried faults** beneath alluvial cover in the GeoDAWN study area (NW Nevada) by
co-training two views:

- **View A (subsurface):** gravity gradients, magnetic gradients, geodetic strain, basement depth.
- **View B (surface):** DEM curvature/slope and the radiometric bands of `training_features.tif`.

Where A is confident while B abstains is treated as a buried-fault candidate (the brief's
disagreement signal). Round H88 tested the *support size* question for that signal: the shared
hide-and-recover instrument runs at 1.1579 % positive density while the board's truth is 0.27265 %
of the footprint, so the mandated field was re-placed at the prevalence-corrected budget of
17,707 dots (instrument optimum 75.2k ÷ 4.247). The result is a **negative calibration**: the
signal itself fails the holdout (see the table), and its rank-difference operationalisation is
dominated by surface-view abstention (only 499 of 17,707 dots are strict A-only).

Derived board algebra (from two owner-reported scores, reproduced from the restored bytes):
implied board truth **|G| ≈ 14,088.75 px**, credit **T = 5,223.1 px** for the 0.2778 file; beating
0.3195 needs T ≥ 6,007.2 at 37,654 pixels, or T ≥ 4,240.1 if the same credit were carried by only
10,000 pixels. Reconstructions, not measurements.

## Verified properties (from disk, this round)

- H88 format: single-band float32, shape/CRS/transform match the sample, all finite, values {0,1},
  17,707 dots, zero within the 200 m catalogue collar.
- H88 decoded-pattern uniqueness: novel fraction 0.229, not identical to and not a subset of any of
  the 146 aligned priors still on disk, not the literal union of the registry.
- H88 not-the-union check: Jaccard vs `max(A,B)` = 0.0121; rank correlation of the field with
  `max(A,B)` = 0.0321; 0 dots shared with the single-view B placement.
- H88 reproducibility: `scripts/h88_run_card.py` rebuilds the emission and asserts it equals the
  shipped mask.
- H88 holdout: evaluator `gems52-pooled-hide-v1`, 53,186 withheld positives, 1000 paired draws,
  200 px blocks; `single_B` at 37k6 reproduces the committed 0.174517.

## Project structure

```
GEMSDOE52/
├── docs/                        # GitHub Pages site (downloads + evidence pages)
├── src/gems52/                  # core library: grid, gates, metric, holdout, spatial,
│                                #   cotrain, nodes, emit, submission_writer, structural, external
├── scripts/
│   ├── run_h88.py               # H88 runner: audit | fit | ladder | emit (+ the shared helpers)
│   ├── h88_run_card.py          # rebuilds the emission, recomputes every gate, writes the card
│   ├── h88_reasoning.py         # per-dot reasoning CSV for the shipped file
│   ├── run_h61.py               # shared co-training template (folds, fits, exchange, holdout)
│   ├── restore_data.py          # SHA-256 pinned data restoration
│   └── check_site.py            # asserts the Pages site still carries its historical claims
├── data/                        # competition data + GeoDAWN externals (restored, 23/23 verified)
├── submission/                  # built artefacts + receipts
├── evidence/                    # machine-readable receipts for every round
├── knowledge/                   # research notes (80 = H88 hypotheses, 81 = H88 results/limits)
└── registry/                    # data manifest, preregistrations, irregularities
```

## Data sources

| Source | Data | License | Reachable from this sandbox |
|--------|------|---------|------------|
| [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) | competition data & rules | competition rules | data tab is login-walled |
| [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) | airborne magnetics, radiometrics | public domain | mirrored in `data/external/` |
| [USGS GeoDAWN release](https://doi.org/10.5066/P93LGLVQ) | data release DOI | public domain | recorded |
| [GDR 1391 INGENIOUS](https://gdr.openei.org/submissions/1391) | fault traces, wells, springs | CC BY 4.0 | **no — `gdr.openei.org` unreachable (IR-H85 block)** |

## Core values

**Maximize P(Win):** every decision is measured against the board algebra above; the lever this
round identified is support size (over-emission is a pure 0.2-per-pixel tax), not new geology.

**Own the Outcome:** every number carries an evidence class — `HOLDOUT-DTI` with the evaluator
version, withheld-positive count and 95 % CI, or `reconstruction from owner-reported scores`. No
claim is transferred between the two.

## Limitations

1. The hide-and-recover instrument hides *catalogue* faults and the board scores *uncatalogued*
   ones; R4 measured Spearman ≈ −0.10 between them. Nothing here predicts the board.
2. The instrument runs at 1.1579 % positive density; the board's is 0.27265 % (bracket
   0.112–0.294 %). The prevalence correction is a proportionality argument, not a measurement.
3. No geologist verified any emitted structure; the reasoning CSV is a template, not an
   interpretation. No field observation was collected.
4. H87's build receipt carries `HOLDOUT-DTI (not yet run)`; an earlier revision of this README
   claimed it was "built and validated ✓". That claim was unsupported and is corrected here.
5. The lane/uniqueness registry is the 146 aligned rasters still on disk; the 545-raster
   `work/h61/priors` inventory used by the H61/H75 cards is no longer in the workspace.

## Next steps

1. Re-run the budget ladder on a **prevalence-thinned** instrument and re-select the support size
   on the corrected prevalence (needs no new data).
2. Re-run the ladder on the strict A-only stratum (the better of the two operationalisations) and
   require it to clear `random` **and** `single_B` before promotion.
3. Tilt-depth / theta-map on the GeoDAWN magnetics already in `data/external/` — top-ranked untried
   hypothesis in `knowledge/80`.
4. Give H87 a real holdout score or retire it from the status board.

## Standing prompt (re-read this first each session)

> Review the repo, then **generate a unique TIF submission** for the competition — never copy a
> prior submission (copying allowed only for learning). It must be instantly obvious whether the
> generated TIF is OK to download and OK to submit. There must be an easy one-click download plus a
> name and a ≤140-character note for the portal. Avoid the portal error
> `Predicted values must be in range [0, 1]`. Keep a clean GitHub Pages site with an
> executive-summary subpage explaining exactly how to make a submission and official verified
> source links. Deep-research the geology from official free sources, store the knowledge in-repo,
> and design a strategy to beat the current leaderboard top. Follow the parallel-run protocol: stay
> in lane, reuse shared tools (never fork privately), label every number `HOLDOUT-DTI` (evaluator,
> withheld positives, 95 % CI) or `ORGANIZER-CONFIRMED`, run a leakage canary per feature
> (AUC > 0.90 = leakage), end with a JSON run card, budget 3 experiments / 2 hours, never pick
> submissions (promotion is a separate selector step). No hallucinations — verify line by line and
> cite official sources. Work autonomously; no manual input from the user.
