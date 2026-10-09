#!/usr/bin/env python3
"""H72-v2 — Spring-Proximity Structural Coherence (SPSC) submission.

Hypothesis: Hot springs in the Great Basin are the surface expression of deep
geothermal circulation along fault planes. A kernel density of hot spring
locations, combined with DEM-derived structural gradients, identifies fault
zones including unmapped ones. The 200m catalogue ring mask removes pure false
positive tax. The wider emission (60k-80k pixels) exploits the decreasing
required-ρ with budget (knowledge/49).

Layers:
- GDR Well and Spring Temperature and Chemistry (27,092 points, DOI
  10.15121/1881483, CC BY 4.0) — hot spring density kernel
- training_features.tif band 12 (detrended elevation slope), band 13 (isostatic
  gravity anomaly), band 19 (detrended elevation slope)
- External lidar_scarp_features_u8

Physical signature: Clustered hot springs along a structural trend indicate a
fault-controlled geothermal system. The spring density kernel captures this at
~300m scale, and the DEM structural gradient corroborates the surface expression.

Named non-fault mimics: Non-structural hot springs (volcanic, regional
groundwater), spring clusters along lithological contacts, artesian springs
unrelated to faulting.

Why it can find uncatalogued faults: The USGS/INGENIOUS catalogue maps faults
from geomorphic expression. Hot springs indicate active fault-controlled fluid
circulation even where no scarp exists. A spring cluster off the mapped fault
network is positive evidence for an unmapped fault.

Difference from all previous work: No submission in this family used spring
density as a ranking signal. Spring data was considered in H52-5 but blocked on
provenance; it is now SHA-256 verified in the data manifest. The spring kernel
provides an independent, hydrologically-motivated signal distinct from all
geophysical and topographic features.

Author: AI assistant. No geologist verified any structure.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = ROOT / "evidence"
SUBMISSION = ROOT / "submission"
EVIDENCE.mkdir(exist_ok=True)
SUBMISSION.mkdir(exist_ok=True)

import sys
sys.path.insert(0, str(ROOT / "src"))

import rasterio
from gems52 import grid, gates, metric, nodes


def load_band(path: str, band: int = 1) -> np.ndarray:
    """Load a single band as float32 with NaN for nodata."""
    with rasterio.open(path) as src:
        a = src.read(band).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < -1e30] = np.nan
    return a


def sobel_magnitude(a: np.ndarray) -> np.ndarray:
    """Compute Sobel edge magnitude."""
    valid = np.isfinite(a)
    a_filled = np.where(valid, a, 0.0).astype(np.float64)
    gx = ndimage.sobel(a_filled, axis=1)
    gy = ndimage.sobel(a_filled, axis=0)
    mag = np.sqrt(gx**2 + gy**2).astype(np.float32)
    mag[~valid] = np.nan
    return mag


def percentile_rank(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank within valid pixels."""
    vals = a[valid]
    if vals.size == 0:
        return np.zeros_like(a, dtype=np.float32)
    sorted_idx = np.argsort(vals)
    ranks = np.empty_like(sorted_idx, dtype=np.float64)
    ranks[sorted_idx] = np.arange(vals.size, dtype=np.float64) / max(1, vals.size - 1)
    result = np.zeros_like(a, dtype=np.float32)
    result[valid] = ranks.astype(np.float32)
    return result


def main():
    t0 = time.time()
    print("=" * 70)
    print("H72-v2 — Spring-Proximity Structural Coherence (SPSC)")
    print("=" * 70)

    # ---- 1. Load data ----
    print("\n[1] Loading data...")
    with rasterio.open(str(DATA / "labels.tif")) as src:
        labels = src.read(1)
    with rasterio.open(str(DATA / "training_features.tif")) as src:
        feat = src.read(range(1, 20)).astype(np.float32)

    valid = np.isfinite(feat[0]) & (labels != -1)
    catalogue = (labels == 1)
    nodata_domain = (labels == -1)
    print(f"  Valid: {valid.sum()}, Catalogue: {catalogue.sum()}, Nodata: {nodata_domain.sum()}")

    # ---- 2. Load spring data ----
    print("\n[2] Loading spring data...")
    spring_points = []
    hot_spring_points = []
    with open(str(DATA / "external" / "gdr_wellspring_in_footprint.csv")) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                r = int(float(row['row']))
                c = int(float(row['col']))
                if 0 <= r < 3730 and 0 <= c < 3292:
                    spring_points.append((r, c))
                    if row.get('thermalclass', '').strip() == 'Hot':
                        hot_spring_points.append((r, c))
            except (ValueError, KeyError):
                pass
    print(f"  Total springs in grid: {len(spring_points)}")
    print(f"  Hot springs in grid: {len(hot_spring_points)}")

    # ---- 3. Compute spring kernel density ----
    print("\n[3] Computing spring kernel density...")
    # Create binary spring maps
    all_spring_map = np.zeros((3730, 3292), dtype=np.float32)
    for r, c in spring_points:
        all_spring_map[r, c] = 1.0

    hot_spring_map = np.zeros((3730, 3292), dtype=np.float32)
    for r, c in hot_spring_points:
        hot_spring_map[r, c] = 1.0

    # Kernel density at ~300m scale (3 pixels at 100m resolution)
    # Use Gaussian with sigma=1.5 (covers ~300m FWHM)
    spring_density = ndimage.gaussian_filter(all_spring_map.astype(np.float64), sigma=1.5).astype(np.float32)
    hot_spring_density = ndimage.gaussian_filter(hot_spring_map.astype(np.float64), sigma=1.5).astype(np.float32)

    print(f"  All spring density: min={spring_density.min():.6f}, max={spring_density.max():.6f}")
    print(f"  Hot spring density: min={hot_spring_density.min():.6f}, max={hot_spring_density.max():.6f}")

    # ---- 4. Compute structural features ----
    print("\n[4] Computing structural features...")
    # Isostatic gravity anomaly edges
    grav = feat[12]  # band 13 (0-indexed)
    edges_grav = sobel_magnitude(grav)

    # Detrended elevation slope
    slope = feat[18]  # band 19

    # LiDAR scarp features
    lidar = load_band(str(DATA / "external" / "lidar_scarp_features_u8.tif"), 1)

    # ---- 5. Build the SPSC ranking field ----
    print("\n[5] Building SPSC ranking field...")

    # Percentile ranks
    rk_spring = percentile_rank(spring_density, valid)
    rk_hot_spring = percentile_rank(hot_spring_density, valid)
    rk_grav_edge = percentile_rank(edges_grav, valid & np.isfinite(edges_grav))
    rk_slope = percentile_rank(slope, valid & np.isfinite(slope))
    rk_lidar = percentile_rank(lidar, valid & np.isfinite(lidar))

    # Weighted combination:
    # - Hot spring density (0.30): strongest independent signal for geothermal faults
    # - All spring density (0.20): broader hydrologic structural signal
    # - Gravity edge (0.20): subsurface structural discontinuity
    # - Slope (0.15): surface structural expression
    # - LiDAR scarp (0.15): high-resolution surface fault expression
    spsc_field = (
        0.30 * rk_hot_spring +
        0.20 * rk_spring +
        0.20 * rk_grav_edge +
        0.15 * rk_slope +
        0.15 * rk_lidar
    ).astype(np.float32)
    spsc_field[~valid] = 0.0

    # Smooth at structural scale (sigma=1.5px = 150m)
    spsc_smooth = ndimage.gaussian_filter(
        np.where(valid, spsc_field, 0.0).astype(np.float64), sigma=1.5
    ).astype(np.float32)
    spsc_smooth[~valid] = 0.0

    print(f"  SPSC field: min={spsc_smooth.min():.4f}, max={spsc_smooth.max():.4f}")

    # ---- 6. Apply masks ----
    print("\n[6] Applying masks...")
    allowed = valid & ~catalogue & ~nodata_domain

    # 200m catalogue ring removal (2 pixels at 100m)
    cat_dilated = ndimage.binary_dilation(catalogue, iterations=2)
    ring_mask = cat_dilated & ~catalogue
    allowed_no_ring = allowed & ~ring_mask
    print(f"  Allowed: {allowed.sum()}, After ring: {allowed_no_ring.sum()}")

    # ---- 7. Determine budget ----
    # Strategy: wider emission targeting ρ ≈ 0.10 at 60-80k pixels
    n_allowed = int(allowed_no_ring.sum())
    
    # Try multiple budgets and pick the one that fills
    for target_budget in [80_000, 70_000, 60_000, 50_000, 40_000]:
        if target_budget <= n_allowed:
            budget = target_budget
            break
    else:
        budget = min(37_654, n_allowed)
    
    print(f"\n[7] Budget: {budget} (allowed: {n_allowed})")

    # ---- 8. Emit with metric-aware spacing ----
    print("\n[8] Emitting with metric-aware spacing (min 3px)...")
    emission = nodes.emit_nodes(
        spsc_smooth, allowed_no_ring, budget, min_px=3.0,
        log=lambda *a: print(f"    {' '.join(str(x) for x in a)}")
    )
    n_emitted = int(emission.sum())
    print(f"  Emitted: {n_emitted} pixels")

    # ---- 9. Convert to submission format ----
    submission = emission.astype(np.float32)
    assert submission.min() >= 0.0 and submission.max() <= 1.0
    assert submission.shape == (3730, 3292)

    # ---- 10. Write GeoTIFF ----
    print("\n[9] Writing submission TIF...")
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    sha_id = hashlib.sha256(f"h72-spsc-{ts}".encode()).hexdigest()[:12]
    name = f"h72-spsc-spring-structural-{n_emitted}px-{ts}-{sha_id}"
    note = ("H72 SPSC: hot-spring density + gravity edge + slope + LiDAR scarp; "
            "wider emission for higher coverage of unmapped faults; 200m ring masked")

    tif_path = SUBMISSION / f"gems52-{name}.tif"
    grid.write_geotiff(tif_path, submission, nodata=None)

    # Validate
    report = gates.format_report(str(tif_path), str(DATA / "sample_submission.tif"),
                                  footprint=valid)
    print(f"  Written: {tif_path.name}")
    print(f"  SHA-256: {report['sha256']}")
    print(f"  Bytes: {report['bytes']}")
    print(f"  Problems: {report.get('problems', [])}")

    if report.get('problems'):
        print("  ⚠️  FORMAT PROBLEMS DETECTED")
    else:
        print("  ✅ Format gate PASSED")

    # ---- 11. Uniqueness check ----
    print("\n[10] Uniqueness check...")
    import glob
    existing_tifs = [f for f in glob.glob(str(SUBMISSION / "gems52-*.tif"))
                     if 'h72-spsc' not in f]
    my_pattern = hashlib.sha256(submission.tobytes()).hexdigest()
    print(f"  Decoded pattern SHA-256: {my_pattern[:32]}...")

    is_unique = True
    for existing in existing_tifs:
        try:
            with rasterio.open(existing) as src:
                other = src.read(1)
            if np.array_equal(submission, other):
                print(f"  ⚠️  IDENTICAL to {Path(existing).name}")
                is_unique = False
        except Exception:
            pass
    if is_unique:
        print("  ✅ Decoded pattern UNIQUE")

    # ---- 12. Rank correlation check ----
    print("\n[11] Rank correlation check...")
    from scipy import stats as sp_stats
    registry_tifs = glob.glob(str(DATA / "scored" / "*.tif"))
    max_corr = 0.0
    max_corr_name = ""
    for tif in registry_tifs:
        try:
            with rasterio.open(tif) as src:
                other = src.read(1)
            mask = valid & np.isfinite(other)
            if mask.sum() < 1000:
                continue
            rho, _ = sp_stats.spearmanr(spsc_smooth[mask], other[mask])
            if abs(rho) > max_corr:
                max_corr = abs(rho)
                max_corr_name = Path(tif).name
            if abs(rho) > 0.5:
                print(f"  ⚠️  {Path(tif).name}: |rho|={abs(rho):.4f}")
        except Exception:
            pass
    print(f"  Max |rho|: {max_corr:.4f} ({max_corr_name})")
    print(f"  Below 0.90: {max_corr < 0.90}")

    # ---- 13. Quick holdout check ----
    print("\n[12] Quick holdout check...")
    from gems52 import holdout as H
    folds = H.make_folds(catalogue, valid, n_folds=4, buffer_px=4,
                         prevalence=0.002, seed=42, mode='hide')
    fold_dtis = []
    for fold in folds:
        fld_allowed = valid & ~fold['visible'] & fold['region']
        em = nodes.emit_nodes(spsc_smooth, fld_allowed, 9400, min_px=3.0)
        em = H.mask_visible(em, fold['visible'])
        r = H.score(em, fold, valid)
        fold_dtis.append(r['dti'])
        print(f"    Fold {fold['fold']}: DTI={r['dti']:.5f}")
    pooled = np.mean(fold_dtis)
    print(f"    POOLED HOLDOUT-DTI: {pooled:.5f} (vs single_B 0.174571)")

    # ---- 14. Write receipt ----
    receipt_data = {
        "hypothesis": "H72-SPSC: hot spring density + structural gradients identify "
                      "fault-controlled geothermal systems including unmapped faults",
        "mechanism": "Spring kernel density at 300m scale captures fault-controlled "
                     "hydrothermal fluid pathways; corroborated by gravity edges and DEM slope",
        "named_mimic": "Non-structural hot springs, artesian springs, lithological contacts",
        "budget": budget,
        "n_emitted": n_emitted,
        "field_weights": {
            "hot_spring_density": 0.30,
            "all_spring_density": 0.20,
            "gravity_edge": 0.20,
            "slope": 0.15,
            "lidar_scarp": 0.15
        },
        "spring_data": {
            "source": "GDR 1391, DOI 10.15121/1881483, CC BY 4.0",
            "n_springs": len(spring_points),
            "n_hot_springs": len(hot_spring_points),
            "provenance": "SHA-256 verified in data_manifest.json"
        },
        "catalogue_ring_m": 200,
        "smoothing_sigma_px": 1.5,
        "binary_mass": True,
        "sha256": report["sha256"],
        "bytes": report["bytes"],
        "format_ok": not bool(report.get("problems")),
        "max_rank_corr": max_corr,
        "holdout_dti_pooled": pooled,
        "submission_name": name,
        "note": note[:140],
        "verdict": "PENDING_HOLDOUT" if not report.get("problems") else "NEGATIVE",
        "status": "research-only; local validation only, not organizer acceptance",
    }
    receipt_path = SUBMISSION / f"gems52-{name}.json"
    receipt_path.write_text(json.dumps(receipt_data, indent=2) + "\n")
    (SUBMISSION / f"gems52-{name}-submission-name.txt").write_text(name + "\n")
    (SUBMISSION / f"gems52-{name}-submission-note.txt").write_text(note[:140] + "\n")

    # ---- Summary ----
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"H72-v2 SPSC complete in {elapsed:.1f}s")
    print(f"  File: {tif_path}")
    print(f"  Budget: {budget}, Emitted: {n_emitted}")
    print(f"  Springs: {len(spring_points)} total, {len(hot_spring_points)} hot")
    print(f"  Format: {'PASS' if not report.get('problems') else 'FAIL'}")
    print(f"  Uniqueness: {'PASS' if is_unique else 'FAIL'}")
    print(f"  Rank corr: {max_corr:.4f} (bar 0.90)")
    print(f"  Holdout DTI: {pooled:.5f}")
    print(f"{'=' * 70}")

    return tif_path, receipt_data


if __name__ == "__main__":
    main()