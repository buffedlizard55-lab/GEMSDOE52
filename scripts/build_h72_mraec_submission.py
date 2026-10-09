#!/usr/bin/env python3
"""H72 — Multi-Band Radiometric Alteration Edge Coherence (MRAEC) submission.

Hypothesis: Geothermal faults create hydrothermal alteration halos detectable as
linear edges in GeoDAWN K/Th/U ratio maps. Multi-band edge coherence — where
gravity, magnetic, radiometric, and conductivity gradients all agree on edge
direction — provides a physically distinct ranker that is wider and more robust
than any single feature, enabling a higher-budget emission at the moderate ρ
(≥0.10) needed to reach 0.3195+ on the board.

Layers used:
- GeoDAWN K, Th, U individual bands (geodawn_rad_u8, bands 1-3)
- GeoDAWN Th/K ratio (geodawn_extensions_u8, band 1) — alteration index
- Training features: isostatic gravity anomaly (band 13), RTP magnetics (band 2),
  surface conductivity (band 17), detrended elevation slope (band 19)
- External: LiDAR scarp features (lidar_scarp_features_u8)

Physical signature: A linear zone of coincident edge responses across multiple
geophysical and radiometric domains, indicating a structural discontinuity
(fault) with associated hydrothermal alteration.

Named non-fault mimics: lithological contacts (different rock types have
different K/Th/U), drainage/alluvial boundaries, vegetation-soil moisture
patterns, model artefacts in the depth-to-basement grid.

Why it can find uncatalogued faults: The USGS/INGENIOUS catalogue is based on
geomorphic/LiDAR expression. A fault beneath alluvial cover has no scarp but
retains its gravity, magnetic, and alteration signatures at depth.

Difference from previous work: No prior submission used directional edge
coherence across multiple physics domains. Previous approaches used magnitude
thresholds or rank transforms. Edge coherence is a geometric property of the
gradient field, not a scalar transform — it measures structural alignment, not
anomaly strength.

Author: AI assistant. No geologist verified any structure. No field observation
was collected. No organizer score is claimed.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

# ---- paths ----
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
    """Compute Sobel edge magnitude. NaN-in, NaN-out."""
    valid = np.isfinite(a)
    a_filled = np.where(valid, a, 0.0).astype(np.float64)
    gx = ndimage.sobel(a_filled, axis=1)
    gy = ndimage.sobel(a_filled, axis=0)
    mag = np.sqrt(gx**2 + gy**2).astype(np.float32)
    mag[~valid] = np.nan
    return mag


def sobel_direction(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute Sobel gradient x and y components. NaN-in, NaN-out."""
    valid = np.isfinite(a)
    a_filled = np.where(valid, a, 0.0).astype(np.float64)
    gx = ndimage.sobel(a_filled, axis=1).astype(np.float32)
    gy = ndimage.sobel(a_filled, axis=0).astype(np.float32)
    gx[~valid] = np.nan
    gy[~valid] = np.nan
    return gx, gy


def edge_coherence_2d(gx1, gy1, gx2, gy2) -> np.ndarray:
    """Coherence between two gradient fields: |cos(angle)| between gradient vectors.

    Returns values in [0, 1]: 1 = parallel gradients, 0 = perpendicular.
    """
    dot = gx1 * gx2 + gy1 * gy2
    mag1 = np.sqrt(gx1**2 + gy1**2)
    mag2 = np.sqrt(gx2**2 + gy2**2)
    denom = mag1 * mag2
    # Avoid division by zero
    coherence = np.where(denom > 1e-10, np.abs(dot) / denom, 0.0)
    # Handle NaN
    invalid = ~np.isfinite(gx1) | ~np.isfinite(gx2) | ~np.isfinite(gy1) | ~np.isfinite(gy2)
    coherence[invalid] = np.nan
    return np.clip(coherence, 0.0, 1.0).astype(np.float32)


def gaussian_smooth(a: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussian smooth, NaN-aware: fill NaN with 0, smooth, mask back."""
    valid = np.isfinite(a)
    filled = np.where(valid, a, 0.0).astype(np.float64)
    smoothed = ndimage.gaussian_filter(filled, sigma=sigma_px)
    # Also smooth the mask to get the normalization
    mask_smoothed = ndimage.gaussian_filter(valid.astype(np.float64), sigma=sigma_px)
    mask_smoothed = np.maximum(mask_smoothed, 1e-10)
    result = (smoothed / mask_smoothed).astype(np.float32)
    result[~valid] = np.nan
    return result


def percentile_rank(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank within valid pixels. Returns [0,1]."""
    vals = a[valid]
    if vals.size == 0:
        return np.zeros_like(a, dtype=np.float32)
    # Use argsort for ranking
    sorted_idx = np.argsort(vals)
    ranks = np.empty_like(sorted_idx, dtype=np.float64)
    ranks[sorted_idx] = np.arange(vals.size, dtype=np.float64) / max(1, vals.size - 1)
    result = np.zeros_like(a, dtype=np.float32)
    result[valid] = ranks.astype(np.float32)
    return result


def main():
    t0 = time.time()
    print("=" * 70)
    print("H72 — Multi-Band Radiometric Alteration Edge Coherence (MRAEC)")
    print("=" * 70)

    # ---- 1. Load all bands ----
    print("\n[1] Loading bands...")
    # GeoDAWN radiometric individual bands (uint8, need float)
    geodawn_k = load_band(str(DATA / "external" / "geodawn_rad_u8.tif"), 1).astype(np.float32)
    geodawn_th = load_band(str(DATA / "external" / "geodawn_rad_u8.tif"), 2).astype(np.float32)
    geodawn_u = load_band(str(DATA / "external" / "geodawn_rad_u8.tif"), 3).astype(np.float32)
    geodawn_tc = load_band(str(DATA / "external" / "geodawn_rad_u8.tif"), 4).astype(np.float32)

    # GeoDAWN ratio bands
    geodawn_th_k = load_band(str(DATA / "external" / "geodawn_extensions_u8.tif"), 1).astype(np.float32)
    geodawn_u_k = load_band(str(DATA / "external" / "geodawn_extensions_u8.tif"), 2).astype(np.float32)

    # Training features
    mag_rtp = load_band(str(DATA / "training_features.tif"), 2)  # RTP magnetics
    grav_anom = load_band(str(DATA / "training_features.tif"), 13)  # Isostatic gravity anomaly
    cond_surf = load_band(str(DATA / "training_features.tif"), 17)  # Surface conductivity
    det_slope = load_band(str(DATA / "training_features.tif"), 19)  # Detrended elevation slope
    depth_base = load_band(str(DATA / "training_features.tif"), 15)  # Depth to basement

    # LiDAR scarp features
    lidar_scarp = load_band(str(DATA / "external" / "lidar_scarp_features_u8.tif"), 1).astype(np.float32)

    # Labels and footprint
    with rasterio.open(str(DATA / "labels.tif")) as src:
        labels = src.read(1)
    valid = np.isfinite(mag_rtp) & np.isfinite(grav_anom)
    catalogue = (labels == 1)
    nodata_domain = (labels == -1)

    print(f"  Footprint: {valid.sum()} valid pixels, {catalogue.sum()} catalogue, {nodata_domain.sum()} nodata")

    # ---- 2. Compute edge magnitude for each feature ----
    print("\n[2] Computing edge magnitudes...")
    edge_features = {}

    # Gravity edge
    edge_features['grav'] = sobel_magnitude(grav_anom)
    print("  gravity edge: done")

    # Magnetic edge
    edge_features['mag'] = sobel_magnitude(mag_rtp)
    print("  magnetics edge: done")

    # GeoDAWN Th/K ratio edge (alteration index)
    edge_features['th_k'] = sobel_magnitude(geodawn_th_k)
    print("  Th/K ratio edge: done")

    # GeoDAWN K edge
    edge_features['k'] = sobel_magnitude(geodawn_k)
    print("  K edge: done")

    # GeoDAWN Th edge
    edge_features['th'] = sobel_magnitude(geodawn_th)
    print("  Th edge: done")

    # Conductivity edge
    edge_features['cond'] = sobel_magnitude(cond_surf)
    print("  conductivity edge: done")

    # Total count edge
    edge_features['tc'] = sobel_magnitude(geodawn_tc)
    print("  total count edge: done")

    # LiDAR scarp edge
    edge_features['lidar'] = sobel_magnitude(lidar_scarp)
    print("  LiDAR scarp edge: done")

    # ---- 3. Compute multi-band edge coherence ----
    print("\n[3] Computing multi-band edge coherence...")

    # Pairwise coherence between key bands
    # First compute gradient directions
    grad = {}
    for name, band_data in [
        ('grav', grav_anom), ('mag', mag_rtp), ('th_k', geodawn_th_k),
        ('k', geodawn_k), ('cond', cond_surf), ('tc', geodawn_tc),
    ]:
        gx, gy = sobel_direction(band_data)
        grad[name] = (gx, gy)
    print("  gradients computed for 6 bands")

    # Compute coherence for key pairs that should agree along faults:
    # gravity-magnetic (both image density contrasts)
    # gravity-Th/K (alteration along structural zones)
    # magnetic-Th/K (magnetic + radiometric structural correlation)
    # gravity-conductivity (fluid pathways along faults)
    # tc-conductivity (radiometric + hydrologic)
    pairs = [
        ('grav', 'mag', 'grav_mag'),
        ('grav', 'th_k', 'grav_thk'),
        ('mag', 'th_k', 'mag_thk'),
        ('grav', 'cond', 'grav_cond'),
        ('tc', 'cond', 'tc_cond'),
        ('k', 'th_k', 'k_thk'),
        ('mag', 'cond', 'mag_cond'),
    ]

    coherence_sum = np.zeros(valid.shape, dtype=np.float64)
    coherence_count = np.zeros(valid.shape, dtype=np.float64)

    for name1, name2, label in pairs:
        coh = edge_coherence_2d(
            grad[name1][0], grad[name1][1],
            grad[name2][0], grad[name2][1]
        )
        mask = np.isfinite(coh) & valid
        coherence_sum[mask] += coh[mask]
        coherence_count[mask] += 1.0
        mean_coh = float(np.nanmean(coh[valid & np.isfinite(coh)]))
        print(f"  {label}: mean coherence = {mean_coh:.4f}")

    # Average coherence
    coherence_count = np.maximum(coherence_count, 1.0)
    mean_coherence = (coherence_sum / coherence_count).astype(np.float32)
    mean_coherence[~valid] = np.nan

    print(f"  Mean multi-band coherence: {float(np.nanmean(mean_coherence)):.4f}")

    # ---- 4. Build the MRAEC ranking field ----
    print("\n[4] Building MRAEC ranking field...")

    # Component 1: Multi-band edge coherence (the novel signal)
    coh_rank = percentile_rank(mean_coherence, valid & np.isfinite(mean_coherence))
    print(f"  Coherence rank: min={float(np.nanmin(coh_rank)):.4f} max={float(np.nanmax(coh_rank)):.4f}")

    # Component 2: Average edge magnitude across all features (strength signal)
    all_edges = np.zeros(valid.shape, dtype=np.float64)
    edge_count = np.zeros(valid.shape, dtype=np.float64)
    for name, edge in edge_features.items():
        mask = np.isfinite(edge) & valid
        all_edges[mask] += edge[mask]
        edge_count[mask] += 1.0
    edge_count = np.maximum(edge_count, 1.0)
    mean_edge = (all_edges / edge_count).astype(np.float32)
    mean_edge[~valid] = np.nan
    edge_rank = percentile_rank(mean_edge, valid & np.isfinite(mean_edge))
    print(f"  Edge rank: min={float(np.nanmin(edge_rank)):.4f} max={float(np.nanmax(edge_rank)):.4f}")

    # Component 3: LiDAR scarp evidence (direct surface expression)
    lidar_rank = percentile_rank(lidar_scarp, valid & np.isfinite(lidar_scarp))
    print(f"  LiDAR rank: min={float(np.nanmin(lidar_rank)):.4f} max={float(np.nanmax(lidar_rank)):.4f}")

    # Component 4: Depth to basement (prefer shallow cover — faults more likely to be expressed)
    depth_rank = percentile_rank(-depth_base, valid & np.isfinite(depth_base))  # negate: shallow = high rank
    print(f"  Depth rank (shallow preferred): min={float(np.nanmin(depth_rank)):.4f} max={float(np.nanmax(depth_rank)):.4f}")

    # Combine: weighted blend favoring coherence and edge strength
    # Weights based on geological motivation:
    # - coherence (0.35): multi-physics agreement is the strongest signal
    # - edge strength (0.30): any strong edge in any domain matters
    # - lidar (0.20): direct surface expression of faults
    # - depth (0.15): prefer areas where faults are expressible
    mraec_field = (
        0.35 * coh_rank +
        0.30 * edge_rank +
        0.20 * lidar_rank +
        0.15 * depth_rank
    ).astype(np.float32)
    mraec_field[~valid] = np.nan

    print(f"  MRAEC field: min={float(np.nanmin(mraec_field)):.4f} max={float(np.nanmax(mraec_field)):.4f}")

    # ---- 5. Apply catalogue mask ----
    print("\n[5] Applying masks...")

    # Mask: valid footprint, not on catalogue, not on nodata domain
    allowed = valid & ~catalogue & ~nodata_domain
    print(f"  Allowed pixels: {allowed.sum()}")

    # ---- 6. Apply 200m ring mask from catalogue ----
    print("  Building 200m catalogue ring mask...")
    cat_dilated = ndimage.binary_dilation(catalogue, iterations=2)  # 200m = 2 pixels at 100m
    ring_mask = cat_dilated & ~catalogue
    allowed_no_ring = allowed & ~ring_mask
    print(f"  Allowed after 200m ring removal: {allowed_no_ring.sum()}")

    # ---- 7. Smooth the field at structural scale (300m = 3px) ----
    print("\n[6] Smoothing at structural scale (sigma=1.5 px = 150m)...")
    field_smooth = gaussian_smooth(mraec_field, sigma_px=1.5)
    field_smooth[~valid] = np.nan

    # ---- 8. Determine budget ----
    # Strategy: wider emission than champion's 37k, targeting ~60k pixels
    # At S=60,000 with ρ ≈ 0.10, DTI ≈ 0.3195 (from knowledge/49 table)
    n_allowed = int(allowed_no_ring.sum())
    budget = min(60_000, n_allowed)
    print(f"\n[7] Budget: {budget} (allowed: {n_allowed})")

    # ---- 9. Emit with metric-aware spacing ----
    print("\n[8] Emitting with metric-aware spacing (min 3px)...")
    emission = nodes.emit_nodes(
        field_smooth, allowed_no_ring, budget, min_px=3.0,
        log=lambda *a: print(f"    {' '.join(str(x) for x in a)}")
    )
    n_emitted = int(emission.sum())
    print(f"  Emitted: {n_emitted} pixels")

    # ---- 10. Convert to float32 for submission ----
    submission = emission.astype(np.float32)

    # Verify values in [0, 1]
    assert submission.min() >= 0.0 and submission.max() <= 1.0, \
        f"Out of range: min={submission.min()}, max={submission.max()}"

    # ---- 11. Write submission ----
    print("\n[9] Writing submission TIF...")
    import time as _time
    ts = _time.strftime("%Y%m%dT%H%M%SZ", _time.gmtime())
    sha_id = hashlib.sha256(f"h72-mraec-{ts}".encode()).hexdigest()[:12]
    name = f"h72-mraec-multiband-edge-coherence-{budget}px-{ts}-{sha_id}"
    note = ("H72 MRAEC: multi-band radiometric alteration edge coherence across gravity,"
            " magnetics, K/Th/U ratios, conductivity; wider emission at 60k budget")

    tif_path = SUBMISSION / f"gems52-{name}.tif"
    receipt = gates.write_submission if hasattr(gates, 'write_submission') else None
    # Use the grid writer directly
    grid.write_geotiff(tif_path, submission, nodata=None)

    # Validate
    report = gates.format_report(str(tif_path), str(DATA / "sample_submission.tif"),
                                  footprint=valid)
    print(f"  Written: {tif_path.name}")
    print(f"  SHA-256: {report['sha256']}")
    print(f"  Bytes: {report['bytes']}")
    print(f"  Problems: {report.get('problems', [])}")

    if report.get('problems'):
        print("  ⚠️  FORMAT PROBLEMS DETECTED — see above")
    else:
        print("  ✅ Format gate PASSED")

    # ---- 12. Write submission JSON ----
    receipt_data = {
        "hypothesis": "H72-MRAEC: multi-band radiometric alteration edge coherence detects "
                      "fault-controlled alteration halos invisible to single-feature ranking",
        "mechanism": "Edge coherence across gravity, magnetic, K/Th/U radiometric, and conductivity "
                     "gradients identifies structural discontinuities with associated hydrothermal alteration",
        "named_mimic": "Lithological contacts, drainage/alluvial boundaries, vegetation-soil moisture patterns",
        "budget": budget,
        "n_emitted": n_emitted,
        "field_weights": {"coherence": 0.35, "edge_strength": 0.30, "lidar": 0.20, "depth": 0.15},
        "catalogue_ring_m": 200,
        "smoothing_sigma_px": 1.5,
        "binary_mass": True,
        "sha256": report["sha256"],
        "bytes": report["bytes"],
        "format_ok": not bool(report.get("problems")),
        "submission_name": name,
        "note": note[:140],
        "verdict": "PENDING_HOLDOUT" if not report.get("problems") else "NEGATIVE",
        "status": "research-only; local format validation only, not organizer acceptance",
        "experiments_used": "1_of_3",
    }
    receipt_path = SUBMISSION / f"gems52-{name}.json"
    receipt_path.write_text(json.dumps(receipt_data, indent=2) + "\n")

    # Also write the submission note and name files
    (SUBMISSION / f"gems52-{name}-submission-name.txt").write_text(name + "\n")
    (SUBMISSION / f"gems52-{name}-submission-note.txt").write_text(note[:140] + "\n")

    print(f"\n  Receipt: {receipt_path.name}")
    print(f"  Name: {name}")
    print(f"  Note: {note[:140]}")

    # ---- 13. Quick validation: uniqueness check ----
    print("\n[10] Running uniqueness check...")
    # Check vs existing submissions in submission/
    existing_tifs = list(SUBMISSION.glob("gems52-*.tif"))
    n_existing = len(existing_tifs)
    print(f"  Existing submissions in submission/: {n_existing}")

    # Check decoded pattern uniqueness
    my_pattern = hashlib.sha256(submission.tobytes()).hexdigest()
    print(f"  Decoded pattern SHA-256: {my_pattern[:32]}...")

    is_unique = True
    for existing in existing_tifs:
        if existing == tif_path:
            continue
        try:
            with rasterio.open(str(existing)) as src:
                other = src.read(1)
            if np.array_equal(submission, other):
                print(f"  ⚠️  IDENTICAL to {existing.name}")
                is_unique = False
        except Exception:
            pass

    if is_unique:
        print("  ✅ Decoded pattern is UNIQUE vs all existing submissions")

    # ---- 14. Summary ----
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"H72 MRAEC submission complete in {elapsed:.1f}s")
    print(f"  File: {tif_path}")
    print(f"  Budget: {budget} px, emitted: {n_emitted} px")
    print(f"  Binary: yes, values exactly {{0.0, 1.0}}")
    print(f"  Catalogue ring: 200m removed")
    print(f"  Verdict: {receipt_data['verdict']}")
    print(f"{'=' * 70}")

    return tif_path, receipt_data


if __name__ == "__main__":
    main()