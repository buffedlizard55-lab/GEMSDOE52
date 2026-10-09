# H66 Summary — Structural Coherence with Multi-Data Consensus

**Generated:** 2026-10-09  
**Status:** Research artifact, pending holdout validation

## Submission Details

| Property | Value |
|----------|-------|
| File | `gems52-h66-structural-coherence-25000px.tif` |
| SHA-256 | `23915c13d1b2f9b3f6c5628158cd2576030d356c465e5c385c7c2b95ff7ef664` |
| Size | 88,070 bytes |
| Submission name | `gems52-h66-structural-coherence-25000px-20261009T030000Z` |
| Note | `H66 structural coherence: multi-data consensus with strike alignment; 3px dots; >200m off catalogue; research-only` |
| Positive pixels | 25,000 |
| Values | Binary {0, 1}, 0 NaN |

## Gate Results

| Gate | Result | Details |
|------|--------|---------|
| Format | PASS | Single-band float32, EPSG:32611, 3730×3292, correct transform |
| Values | PASS | Exactly {0,1}, 0 NaN |
| Uniqueness (pattern) | PASS | Different decoded SHA-256 from all 48 priors |
| Novelty | PASS | 90.56% novel vs prior union |
| Not union | PASS | Not the literal union of any priors |
| Lane (Spearman) | PASS | Max 0.0033 (threshold 0.90) |
| Lane (near-3px) | PASS | Max 0.1194 (threshold 0.70) |
| Holdout | NOT YET | Pending validation |

## What Makes H66 Unique

H66 uses a **multi-data consensus** approach that is fundamentally different from all prior submissions:

1. **Geophysical edge product**: gravity gradient × magnetic gradient (requires BOTH)
2. **LiDAR scarp density**: combined step, exposure, upface, relief
3. **Radiometric anomaly**: K/Th, U/K deviations from background
4. **Structural coherence**: multi-scale structure tensor from DEM
5. **Strike alignment**: weighting for Basin-and-Range trend (~100°)

Prior submissions used:
- Two-view concordance (min of View A and View B)
- Two-view disagreement (A confident, B not)
- Single-view methods

H66 requires consensus among 4+ independent data types with strike alignment.

## Files Created

- `submission/gems52-h66-structural-coherence-25000px.tif` — The GeoTIFF
- `submission/gems52-h66-structural-coherence-25000px.zip` — Single-TIFF ZIP
- `submission/gems52-h66-structural-coherence-25000px.json` — Receipt
- `docs/downloads/h66-candidate.tif` — Download copy
- `docs/downloads/h66-candidate.zip` — Download ZIP
- `docs/h66-executive-summary.html` — Submission guide
- `docs/h66-audit.html` — Audit page
- `src/gems52/h66.py` — H66 hypothesis module
- `scripts/generate_h66_submission.py` — Generation script

## Next Steps

1. Run H66 on hide-and-recover holdout to measure HOLDOUT-DTI
2. Compare against single-view baselines (View A, View B) and union
3. If HOLDOUT-DTI exceeds best control, seek selector approval
4. Document geological reasoning for each emitted pixel

## Limitations

- Not validated on holdout yet
- Training data not available in this environment; prediction uses methodological framework
- External radiometric data provenance not independently verified
- No geologist review of specific structures
