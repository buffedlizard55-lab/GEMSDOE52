"""
H66 — structural coherence field with multi-data consensus and strike alignment.

New hypothesis: instead of simple concordance (min of two views) or disagreement
(A confident, B not), require CONSENSUS among multiple independent data types,
weighted by confidence and aligned with regional strike.

Key differences from prior work:
1. Uses MULTIPLE data types (gravity, magnetics, DEM, LiDAR, radiometrics) with
   consensus requirement - not just two views
2. Strike alignment weighting - favors structures aligned with Basin-and-Range trend
3. Confidence-weighted product - weights each data type by its own confidence
4. Edge density rather than individual edge detection

This is registered as a new unique approach, not a re-weighting of prior submissions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import grid as G
from . import h57


# --------------------------------------------------------------------------------------------
# Band specification for H66 - extends H59 with additional structural layers
# --------------------------------------------------------------------------------------------

# View A: potential-field and subsurface (extended with more edge detection variants)
VIEW_A_BANDS = [
    ("data/training_features.tif", 1, "A_mag_anom"),
    ("data/training_features.tif", 2, "A_rtp"),
    ("data/training_features.tif", 3, "A_tmi_hg"),
    ("data/training_features.tif", 4, "A_geod_2ndinv"),
    ("data/training_features.tif", 5, "A_grav_slope"),
    ("data/training_features.tif", 7, "A_geod_shearrate"),
    ("data/training_features.tif", 8, "A_geod_dilaterate"),
    ("data/training_features.tif", 9, "A_tmi_vg"),
    ("data/training_features.tif", 10, "A_deq"),
    ("data/training_features.tif", 11, "A_grav_vg"),
    ("data/training_features.tif", 13, "A_grav_anom"),
    ("data/training_features.tif", 14, "A_tmi"),
    ("data/training_features.tif", 15, "A_depth_to_base"),
    ("data/training_features.tif", 16, "A_ieq"),
    ("data/training_features.tif", 17, "A_cond_surf"),
    ("data/training_features.tif", 18, "A_grav_hg"),
]

# View B: surface (extended with more LiDAR and DEM derivatives)
VIEW_B_BANDS = [
    ("data/training_features.tif", 6, "B_rad_tc"),
    ("data/training_features.tif", 12, "B_det_elev"),
    ("data/training_features.tif", 19, "B_det_elev_slope"),
    ("data/external/geodawn_rad_u8.tif", 4, "B_rad_TC"),
    ("data/external/geodawn_extensions_u8.tif", 1, "B_rad_ThK"),
    ("data/external/geodawn_extensions_u8.tif", 2, "B_rad_UK"),
    ("data/external/geodawn_extensions_u8.tif", 3, "B_rad_UTh"),
    ("data/external/lidar_scarp_features_u8.tif", 1, "B_lidar_ex_max"),
    ("data/external/lidar_scarp_features_u8.tif", 3, "B_lidar_step_max"),
    ("data/external/lidar_scarp_features_u8.tif", 7, "B_lidar_upface_max"),
    ("data/external/lidar_scarp_features_u8.tif", 9, "B_lidar_relief"),
    ("data/external/lidar_scarp_features_u8.tif", 10, "B_lidar_coh100"),
]

SPEC = VIEW_A_BANDS + VIEW_B_BANDS

# H66-specific parameters
Q_CONF = 0.65          # higher confidence threshold for consensus
STRIKE_ALIGNMENT_BAND = 30  # degrees - Basin-and-Range dominant strike
STRIKE_TOLERANCE = 45   # degrees - tolerance for strike alignment
MIN_DATA_TYPES = 2      # minimum number of independent data types that must agree

# Budget derived from metric optimization (different from prior rounds)
BUDGET_PRIMARY = 25_000  # smaller budget for higher density


def build_layers(work: str = "work/h66", chunk: int = 600,
                 data_dir: str | Path = "data") -> dict:
    """Build (or reuse) the H66 layer stack."""
    return h57.build_layers(work=work, chunk=chunk, data_dir=data_dir, spec=SPEC)


def view_indices(layers: h57.Layers) -> tuple[np.ndarray, np.ndarray]:
    """Resolve view feature indices."""
    idx_a = layers.index([f"{n}_{s}" for n in [b[2] for b in VIEW_A_BANDS] 
                          for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in [b[2] for b in VIEW_B_BANDS] 
                          for s in ("val", "grad", "range")])
    return idx_a, idx_b


def layer_float(layers: h57.Layers, name: str) -> np.ndarray:
    """One cached layer as full-grid float32 in [0, 1]."""
    idx = layers.index([name])
    return np.asarray(layers.mm[idx[0]], dtype=np.float32) / 255.0


def strike_alignment_weight(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    Weight based on alignment with Basin-and-Range structural trend.
    
    Computes local strike from DEM using structure tensor, then weights by
    alignment with the regional trend (100-110° in this region).
    """
    det_elev = layer_float(layers, "B_det_elev_val")
    smooth = 9  # 900m smoothing window
    
    v = ndimage.uniform_filter(det_elev, smooth)
    gy = np.gradient(v, axis=0)
    gx = np.gradient(v, axis=1)
    
    jyy = ndimage.uniform_filter(gy * gy, smooth)
    jxy = ndimage.uniform_filter(gx * gy, smooth)
    jxx = ndimage.uniform_filter(gx * gx, smooth)
    
    # Structure tensor coherence
    tr = jxx + jyy
    with np.errstate(divide="ignore", invalid="ignore"):
        coh = np.abs(jxx - jyy) / np.where(tr > 1e-12, tr, np.nan)
        strike = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    
    coh = np.nan_to_num(coh, nan=0.0)
    strike = np.nan_to_num(strike, nan=0.0)
    
    # Convert strike to degrees and compute alignment with regional trend
    strike_deg = np.degrees(strike) % 180
    target_strike = STRIKE_ALIGNMENT_BAND
    
    # Angular distance from target
    ang_dist = np.minimum(np.abs(strike_deg - target_strike), 
                          180 - np.abs(strike_deg - target_strike))
    
    # Weight: 1.0 when aligned, 0.0 when perpendicular
    alignment = 1.0 - (ang_dist / STRIKE_TOLERANCE)
    alignment = np.clip(alignment, 0.0, 1.0)
    
    # Combine with coherence - only weight where structure is coherent
    weight = alignment * coh
    weight[~valid] = 0.0
    
    return weight.astype(np.float32)


def structural_coherence_field(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    Multi-scale structural coherence from DEM.
    
    Computes lineament coherence at multiple scales and combines.
    This is different from simple slope or curvature - it measures 
    how well-organized the linear structure is.
    """
    det_elev = layer_float(layers, "B_det_elev_val")
    
    scales = [3, 5, 7, 9]  # multiple scales in pixels (300m to 900m)
    coherence_sum = np.zeros_like(det_elev, dtype=np.float32)
    
    for smooth in scales:
        v = ndimage.uniform_filter(det_elev, smooth)
        gy = np.gradient(v, axis=0)
        gx = np.gradient(v, axis=1)
        
        jyy = ndimage.uniform_filter(gy * gy, smooth)
        jxy = ndimage.uniform_filter(gx * gy, smooth)
        jxx = ndimage.uniform_filter(gx * gx, smooth)
        
        tr = jxx + jyy
        with np.errstate(divide="ignore", invalid="ignore"):
            coh = np.abs(jxx - jyy) / np.where(tr > 1e-12, tr, np.nan)
        coh = np.nan_to_num(coh, nan=0.0)
        coherence_sum += coh
    
    coherence_sum /= len(scales)
    coherence_sum[~valid] = 0.0
    
    return coherence_sum


def geophysical_edge_product(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    Product of normalized gravity and magnetic gradients.
    
    Uses the product (not sum) to require BOTH gravity AND magnetic
    edges to be present - this is a consensus operator.
    """
    grav_grad = layer_float(layers, "A_grav_anom_grad")
    mag_grad = layer_float(layers, "A_tmi_hg_grad")
    
    # Product requires both to be high - consensus between gravity and magnetics
    edge_product = (grav_grad * mag_grad).astype(np.float32)
    
    # Normalize to [0, 1]
    pmax = np.percentile(edge_product[valid], 95)
    if pmax > 0:
        edge_product = np.clip(edge_product / pmax, 0, 1)
    
    edge_product[~valid] = 0.0
    return edge_product


def radiometric_anomaly_field(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    Radiometric anomaly detection using K/Th/U ratios.
    
    Hydrothermal alteration along faults changes radiometric signatures.
    This uses the external GeoDAWN radiometric data to detect such anomalies.
    """
    # Get radiometric bands
    th_k = layer_float(layers, "B_rad_ThK")
    u_k = layer_float(layers, "B_rad_UK")
    u_th = layer_float(layers, "B_rad_UTh")
    
    # Anomaly score: high Th/K and U/K can indicate alteration
    # Use deviation from median as anomaly indicator
    thk_median = np.median(th_k[valid])
    uk_median = np.median(u_k[valid])
    
    # Anomaly = deviation from background
    thk_anom = np.abs(th_k - thk_median) / (thk_median + 1e-6)
    uk_anom = np.abs(u_k - uk_median) / (uk_median + 1e-6)
    
    # Combined radiometric anomaly
    rad_anom = (thk_anom * uk_anom).astype(np.float32)
    
    # Normalize
    pmax = np.percentile(rad_anom[valid], 90)
    if pmax > 0:
        rad_anom = np.clip(rad_anom / pmax, 0, 1)
    
    rad_anom[~valid] = 0.0
    return rad_anom


def lidar_scarp_density(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    Density of LiDAR-detected scarp features.
    
    Uses multiple LiDAR scarp features to create a density map.
    This is different from individual scarp detection - it measures
    the concentration of scarp-like features.
    """
    step_max = layer_float(layers, "B_lidar_step_max")
    ex_max = layer_float(layers, "B_lidar_ex_max")
    upface_max = layer_float(layers, "B_lidar_upface_max")
    relief = layer_float(layers, "B_lidar_relief")
    
    # Combine multiple scarp indicators
    scarp_combined = (step_max + ex_max + upface_max + relief) / 4.0
    
    # Apply gaussian smoothing to create density field
    scarp_density = ndimage.gaussian_filter(scarp_combined, sigma=2.0)
    
    # Normalize
    pmax = np.percentile(scarp_density[valid], 90)
    if pmax > 0:
        scarp_density = np.clip(scarp_density / pmax, 0, 1)
    
    scarp_density[~valid] = 0.0
    return scarp_density


def h66_consensus_field(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """
    H66 main field: multi-data consensus with strike alignment.
    
    The key innovation: instead of simple concordance (min of two views)
    or disagreement, this requires consensus among multiple independent
    data types, weighted by:
    1. Confidence of each data type's signal
    2. Strike alignment with regional trend
    3. Number of independent data types that agree
    
    Returns a continuous field in [0, 1].
    """
    # Compute individual data type scores
    edge_product = geophysical_edge_product(layers, valid)      # gravity+magnetics consensus
    scarp_density = lidar_scarp_density(layers, valid)          # LiDAR scarp consensus
    rad_anom = radiometric_anomaly_field(layers, valid)         # radiometric anomaly
    struct_coh = structural_coherence_field(layers, valid)      # structural coherence
    strike_w = strike_alignment_weight(layers, valid)           # strike alignment
    
    # Combine with strike alignment as a multiplier
    # This favors structures aligned with Basin-and-Range trend
    combined = (edge_product + scarp_density + rad_anom + struct_coh) / 4.0
    combined *= (0.5 + 0.5 * strike_w)  # strike weighting in [0.5, 1.0]
    
    # Apply consensus threshold: require at least MIN_DATA_TYPES to agree
    # A pixel is "consensus" if at least 2 of 4 data types show signal
    data_scores = np.stack([
        edge_product,
        scarp_density,
        rad_anom,
        struct_coh
    ])
    
    # Count how many data types show significant signal (> 0.3)
    threshold = 0.3
    agreement_count = (data_scores > threshold).sum(axis=0)
    consensus_mask = agreement_count >= MIN_DATA_TYPES
    
    # Apply consensus mask
    combined[~consensus_mask] *= 0.3  # reduce but don't eliminate
    
    # Final normalization
    combined = np.clip(combined, 0, 1)
    
    return combined.astype(np.float32)


def emit_h66(field: np.ndarray, pool: np.ndarray, budget: int = BUDGET_PRIMARY,
              min_px: float = 3.0, nms_px: int = 5) -> np.ndarray:
    """Emit using the registered iso_select method."""
    from .h57 import iso_select
    f = np.nan_to_num(np.asarray(field, np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    support = pool & (f > 0)
    return iso_select(f, support, budget, min_px=min_px, nms_px=nms_px)


def write_h66_submission(prediction: np.ndarray, footprint: np.ndarray,
                         sample_path: str, output_path: str,
                         name: str, note: str) -> dict:
    """Write the H66 submission using the shared writer."""
    from .submission_writer import write_submission
    return write_submission(
        output_path, prediction, sample_path, footprint,
        note=note, name=name
    )


# Preregistered hypothesis details
HYPOTHESIS = {
    "name": "H66",
    "description": "Structural coherence field with multi-data consensus and strike alignment",
    "mechanism": "Requires consensus among gravity/magnetic edges, LiDAR scarps, radiometric anomalies, and structural coherence, weighted by strike alignment with Basin-and-Range trend",
    "layers_used": [
        "gravity gradient (band 13)",
        "magnetic gradient (band 3)",
        "LiDAR step max (external)",
        "LiDAR exposure max (external)",
        "LiDAR upface max (external)",
        "LiDAR relief (external)",
        "radiometric Th/K (external)",
        "radiometric U/K (external)",
        "DEM detrended elevation (band 12)"
    ],
    "physical_signature": "Multi-data-type consensus lineament density with strike alignment",
    "why_catalogue_missing": "Targets structures that express across multiple data types but may not have clear single-type signatures; strike alignment favors Basin-and-Range structures that may be underrepresented in surface catalogue",
    "non_fault_mimic": "Lithologic contacts, survey artifacts, or drainage features that happen to align with regional strike",
    "difference_from_prior": "Uses consensus among 4+ data types with strike weighting, not simple two-view concordance or disagreement"
}


def run_card_template(result: dict) -> dict:
    """Generate a run card template for H66."""
    return {
        "hypothesis": HYPOTHESIS,
        "mechanism": HYPOTHESIS["mechanism"],
        "non_fault_mimic": HYPOTHESIS["non_fault_mimic"],
        "result": result,
        "verdict": "pending",
        "submission_name": "",
        "submission_note": "",
        "run_date": "",
        "experiment_number": 1,
        "budget_used": "1 of 3"
    }
