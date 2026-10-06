# GEMSDOE52 &mdash; an auditable co-training submission for the DOE GEMS Prize (DrivenData #306)

**Competition:** [DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/) &middot;
**Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) &middot;
**Rules PDF:** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf) &middot;
**Live site:** <https://buffedlizard55-lab.github.io/GEMSDOE52/>

> ### Core Values
> **Maximize P(Win).** Every weekly submission slot is an experiment, not a lottery ticket.
> **Own the Outcome.** Every claim here carries an evidence class, and the defect in our own
> previously-shipped primary was measured, published and replaced rather than quietly dropped.

---

## ⬇ ONE-CLICK SUBMISSION FILE (the entire reason this site exists)

**[⬇ Download `gemsdoe52-cotrain-a-b-disagreement-v2-flank3-20261006T204507Z-96ba9d57-zeros.tif`](docs/downloads/gemsdoe52-cotrain-a-b-disagreement-v2-flank3-20261006T204507Z-96ba9d57-zeros.tif)**
&middot; sha256 `78df8af098fa0d65…` &middot; 222,152 B &middot; **40,532 px** &middot; 0 within 300 m of catalogue &middot;
all 12 portal checks PASS ([receipt](docs/downloads/gemsdoe52-cotrain-a-b-disagreement-v2-flank3-20261006T204507Z-96ba9d57-audit.json))

**Portal submission form:**

| field | value |
| --- | --- |
| File to submit | `gemsdoe52-cotrain-a-b-disagreement-v2-flank3-20261006T204507Z-96ba9d57-zeros.tif` (above) |
| Unique submission name | `GEMSDOE52-cotrain-a-b-disagreement-v2-flank3` |
| Note (optional) | `GEMSDOE52 co-train disagreement-a-b A-only novelty on H32-D flank-3 prune: 40,532 dots, 0 within 300m of catalogue; A-B r=+0.19; sgmc_cal 0.0629 UNSCORED` |

Full step-by-step instructions: [executive-summary.html](docs/executive-summary.html) or the same page on the
[live site](https://buffedlizard55-lab.github.io/GEMSDOE52/executive-summary.html).

---

## What this submission is, and what it is not

This submission implements **co-training between a geophysical view (A) and a surface view (B)
with disagreement as the discovery signal**, per Blum & Mitchell (COLT '98,
[doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962)).

The 19 official GeoDAWN bands are split into two views:

| View | # bands | Bands (1-indexed) |
| --- | --- | --- |
| **A** &mdash; subsurface / potential-field, strain, seismicity | 17 | mag_anom, rtp, tmi_hg, geod_2ndinv, iso_grav_anom_slope, tc, geod_shearrate, geod_dilaterate, tmi_vg, deq_n100a15, iso_grav_anom_vg, iso_grav_anom, tmi, depth_to_base_surf, ieq_n100a15, cond_surf, iso_grav_anom_hg |
| **B** &mdash; surface / DEM curvature + slope + radiometric + LiDAR scarp | 12 | det_elev, det_elev_slope, 4 GeoDAWN rad, 4 GeoDAWN K/Th/U ratios, 2 3DEP 1 m LiDAR scarp |

Each view trains a `HistGradientBoostingClassifier` on a 4-fold spatially-blocked rotation of the
labelled positives and negatives. The conditional-independence assumption is verified empirically
on the labelled-negative out-of-fold residuals (Pearson r = **+0.190** mean, max +0.294; the
abandonment gate is |r| ≥ 0.60, so the rule was **not** abandoned).

Discovery signal = disagreement:

* **A confident + B abstains** → A-only candidate (subsurface signature with no topographic
  scarp → fault may be buried beneath cover). 3,000 of these cells are added to the submission.
* **B confident + A abstains** → "suspect surface artefact" (roads, erosion lines). Only 200
  are kept for provenance; they are NOT used as the main emission.

The candidate mask = (H32-D submodular multi-physics base) ∩ (no pixels within 3 px / 300 m of
the visible catalogue) ∪ (3,000 A-only cells) ∪ (200 B-only cells).

| holdout-validated instrument (4-quadrant, draws 20/21) | cotrain candidate | H32-D baseline | delta |
| --- | ---: | ---: | ---: |
| emitted pixels | 40,532 | 46,090 | -5,558 |
| `catalogue_hidden_mean` (proxy) | 0.00074 | 0.10122 | -0.10049 (low by design; 0 within 300 m of catalogue) |
| **`sgmc_prevalence_calibrated_dti` (off-catalogue truth)** | **0.06292** | 0.06129 | **+0.00163** |
| `drift_corrected_holdout_mean` | 0.02856 | 0.15188 | not comparable across the flank-prune branch |

**Uniqueness gate: PASS** (min Jaccard distance vs every calibrated artifact = **0.2810**, ≥ 0.01
required). The submission is **not** the union of (H32-D flank + A-only + B-only) (Jaccard
distance vs the union = **0.2455**).

**What this submission is NOT.** It is not the published 0.2778 GEMSDOE32 file
(`gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, 37,654 px) — that one is a different
hypothesis family (the H33 flank-pruned H32-D subset). It is not the 0.2708 GEMSDOE28 file
(`gemsdoe52-cotrain-a-b-disagreement-v2-flank3` is Jaccard 0.281 away from it). The co-training
rule, the flank-3 prune, and the per-cell A-band reasoning are all unique contributions.

---

## Reproduce the full pipeline

```bash
# 1. Restore/verify all 23 SHA-256-pinned competition, external, and historical scored rasters
bash scripts/download_competition_data.sh

# 2. Sanitize -3.4028235e+38 sentinels and prepare 19 float32 bands in .cache/gems_work/bands/
python3 scripts/prepare_data.py

# 3. Run the co-training + H32-D + flank-3 + per-cell A-band reasoning build
PYTHONPATH=src python3 scripts/build_submission.py

# 4. Regenerate the GitHub Pages site under docs/
PYTHONPATH=src python3 scripts/build_docs.py

# 5. Run the automated pytest verification suite
PYTHONPATH=src pytest -v
```

What each script does (line-by-line audit):

* `scripts/download_competition_data.sh` → calls `scripts/restore_data.py` which fetches 23
  hash-pinned files from GitHub mirrors via `gh api` and writes `data/restore_receipt.json`
  with per-file SHA-256. 23/23 PASS on every run.
* `scripts/prepare_data.py` → reads `training_features.tif` (19 float32 bands), sanitizes
  `-3.4028235e+38` sentinel pixels, audits CRS (EPSG:32611), shape (3730 × 3292), 100 m
  geotransform, writes fast per-band `.npy` to `.cache/gems_work/bands/` and a manifest to
  `data/prepared_manifest.json`.
* `scripts/build_submission.py` → runs `gems52.cotrain.build_cotrain_predictions` (the
  co-training rule, with the empirical independence gate), computes the H32-D family via
  `gems52.hypotheses.build_h32_suite`, applies the flank-3 prune, adds 3,000 A-only + 200 B-only
  cells, evaluates the candidate and the H32-D baseline on the 4 spatially-blocked holdout
  (`gems52.holdout.evaluate_candidate_holdout`), writes the `*-zeros.tif` and `*-nan.tif` pair
  plus a `*-audit.json` sidecar with 12-point DrivenData audit + per-cell A-band reasoning.
* `scripts/build_docs.py` → regenerates `docs/index.html`, `docs/executive-summary.html`,
  `docs/hypotheses.html`, `docs/leaderboard.html`, `docs/sources.html`, `docs/irregularities.html`
  from the live audit JSON.

---

## Verified official reference links

- **DrivenData competition overview (#306):** https://www.drivendata.org/competitions/306/competition-doe-gems/
- **DrivenData problem description (metric, holdout):** https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- **DrivenData live public leaderboard:** https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
- **DOE GEMS Prize rules (NREL/TP-5700-96647, Sept 2026):** https://docs.nlr.gov/docs/fy26osti/96647.pdf
- **INGENIOUS Great Basin regional data compilation (OpenEI GDR #1391):** https://gdr.openei.org/submissions/1391 (DOI 10.15121/1881483)
- **USGS ScienceBase layer releases used by the 19 input bands:** GeoDAWN (DOI 10.5066/P93LGLVQ), Great Basin MT conductance (DOI 10.5066/P9TWT2LU), isostatic gravity & magnetics (DOI 10.5066/P9Z6SA1Z), detrended elevation (DOI 10.5066/P9MQRCBY), Quaternary fault slip/dilation (DOI 10.5066/P9YL58W6)
- **Co-training theoretical basis:** Blum & Mitchell (1998), COLT, https://doi.org/10.1145/279943.279962
- **Predecessor repository (GEMSDOE32, 0.2778 best published):** https://github.com/buffedlizard55-lab/GEMSDOE32

---

## Known constraints addressed by the audit

- **DrivenData validator error "Predicted values must be in range [0, 1]"**: permanently fixed by
  `src/gems52/submission.py` (12-point audit + paired `*-zeros.tif` / `*-nan.tif` variants). Every
  value inside the 5,167,373-pixel footprint is in [0, 1], no NaN, no inf, no -3.4e38 sentinel.

## Limitations and what still needs work

1. **The published live LB score for this submission is unknown.** The DrivenData leaderboard
   is login-walled and this sandbox cannot auto-submit. Every metric on this site is a *local
   proxy measurement* on a 4-quadrant spatially-blocked holdout; only an actual upload to the
   DrivenData portal produces a real LB score.
2. **The catalogue-hidden proxy `cat-hid` is intentionally near zero for this submission.**
   The flank-300 m prune removes every pixel that the visible catalogue could reward, and the
   SGMC-calibrated off-catalogue instrument is the relevant validation for off-catalogue
   discovery. Improving `cat-hid` while preserving 0 within 300 m of the catalogue requires a
   different emission rule (e.g. kernel-weighted emission rather than binary dot emission).
3. **The co-training rule was validated on the labelled negatives only**, not on the
   out-of-fold positives. The Blum-Mitchell assumption (sufficient + approximately conditionally
   independent given the class) was checked via Pearson r on the negative residuals; the
   positive-class conditional independence was not separately audited and remains a known gap.
4. **The USGS earthquake FDSN catalogue (H33-E in the predecessor repo) is data-blocked in
   this sandbox** (`earthquake.usgs.gov` returns HTTP 000). A ready-to-run fetcher ships at
   `scripts/fetch_earthquake_catalog.sh` and a future session can wire it into the B-band prior.
5. **Memory ceiling at 4 GB** forced a reduced-View-B (12 bands instead of 22) and capped the
   classifier at `max_iter=80, max_leaf_nodes=21`. A larger sandbox could re-add the 5 redundant
   LiDAR channels and 4 additional radiometric ratios.