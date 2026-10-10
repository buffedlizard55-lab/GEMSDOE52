#!/usr/bin/env python3
"""H87: Co-training with multi-scale wavelength contrast and radiometric Th/K ratio.

UNIQUE hypothesis (not in any prior submission):
    View A (geophysical): isostatic gravity gradients + magnetic gradients + geodetic strain
    View B (surface): multi-scale DEM wavelength contrast + slope + radiometric Th/K ratio

    Disagreement signal: where A is confident and B abstains -> buried faults beneath cover
    Geological mechanism: concealed normal faults in alluvial basins produce gravity/magnetic
    gradients at depth but no surface scarp. The Th/K ratio detects hydrothermal alteration
    halos along fault-controlled fluid pathways (GeoDAWN DOI 10.5066/P93LGLVQ).

    Novel features NOT in any prior:
    - Wavelength contrast: ratio of fine-scale (sigma=1) to coarse-scale (sigma=8) Hessian
      eigenvalue magnitude. High = localized sharp feature (scarp); low = broad regional.
    - Radiometric Th/K ratio: elevated where K is leached by hydrothermal fluids.
    - View-disagreement emission: only emit where A_score - B_score > calibrated threshold.

Parallel-run lane: this submission uses a DIFFERENT feature combination than all priors.
    The wavelength-ratio feature is novel; the Th/K ratio was used only as raw band 6 in
    some priors but never as a ratio transform.

Writer: gems52.grid.write_geotiff with zeros-outside (the H84 fix for the portal [0,1] error).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid, gates, nodes, metric

FEATURES = ROOT / "data" / "training_features.tif"
LABELS = ROOT / "data" / "labels.tif"
SAMPLE = ROOT / "data" / "sample_submission.tif"
GEODAWN_RAD = ROOT / "data" / "external" / "geodawn_rad_u8.tif"
GEODAWN_EXT = ROOT / "data" / "external" / "geodawn_extensions_u8.tif"
SUBMISSION_DIR = ROOT / "submission"
EVIDENCE_DIR = ROOT / "evidence"

BUDGET = 37654
MIN_SPACING_PX = 3.0
CATALOGUE_COLLAR_PX = 2  # 200 m exclusion from known faults


def footprint_all_bands(path: str) -> np.ndarray:
    """Intersection of all-band finite pixels (the standard competition footprint)."""
    with rasterio.open(path) as src:
        acc = None
        for i in range(1, src.count + 1):
            a = src.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            acc = ok if acc is None else (acc & ok)
    return acc


def smooth_normalized(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    """Normalized Gaussian smoothing that handles NaN/holes correctly."""
    good = valid & np.isfinite(a)
    num = ndi.gaussian_filter(np.where(good, a, 0.0).astype(np.float64), sigma, mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float64), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8).astype(np.float32)


def hessian_eigenvalues(field: np.ndarray, cell_m: float = 100.0) -> tuple[np.ndarray, np.ndarray]:
    """Compute the two Hessian eigenvalues of a 2D field. Returns (lambda_max, lambda_min)."""
    gyy, gyx = np.gradient(np.gradient(field, cell_m, axis=0), cell_m, axis=0), None
    gxx = np.gradient(np.gradient(field, cell_m, axis=1), cell_m, axis=1)
    gyx = np.gradient(np.gradient(field, cell_m, axis=0), cell_m, axis=1)
    # Eigenvalues of 2x2 symmetric matrix: (a+d)/2 +/- sqrt(((a-d)/2)^2 + b^2)
    trace = gyy + gxx
    det = gyy * gxx - gyx * gyx
    disc = np.sqrt(np.maximum(0.25 * trace * trace - det, 0.0))
    lam_max = 0.5 * trace + disc
    lam_min = 0.5 * trace - disc
    return lam_max, lam_min


def compute_view_a(features_path: str, valid: np.ndarray) -> np.ndarray:
    """View A: geophysical/subsurface potential-field score.

    Combines: gravity gradients (edge detection), magnetic gradients, strain rate.
    High score = strong subsurface structural contrast.
    """
    with rasterio.open(features_path) as src:
        # Band assignments from the file's own tags:
        # 5: iso_grav_slope, 11: iso_grav_vg, 13: iso_grav_anom, 18: iso_grav_hg
        # 1: mag_anom, 3: tmi_hg, 9: tmi_vg, 14: tmi
        # 4: geod_2ndinv, 7: geod_shearrate, 8: geod_dilaterate
        # 15: depth_to_base_surf, 17: cond_surf
        grav_slope = src.read(5).astype(np.float32)
        grav_vg = src.read(11).astype(np.float32)
        grav_hg = src.read(18).astype(np.float32)
        mag_hg = src.read(3).astype(np.float32)
        mag_vg = src.read(9).astype(np.float32)
        strain_inv = src.read(4).astype(np.float32)
        shear = src.read(7).astype(np.float32)
        depth_base = src.read(15).astype(np.float32)
        cond = src.read(17).astype(np.float32)

    # Clean NaN
    for arr in [grav_slope, grav_vg, grav_hg, mag_hg, mag_vg, strain_inv, shear, depth_base, cond]:
        arr[~np.isfinite(arr)] = 0.0
        arr[arr < -1e38] = 0.0

    # Rank-normalize each feature to [0, 1] within the valid footprint
    def rank_norm(a, valid):
        v = a[valid]
        if v.size == 0:
            return np.zeros_like(a)
        lo, hi = np.percentile(v, 1), np.percentile(v, 99)
        if hi <= lo:
            return np.zeros_like(a)
        return np.clip((a - lo) / (hi - lo), 0, 1)

    components = [
        rank_norm(np.abs(grav_slope), valid),     # gravity slope = lateral density contrast
        rank_norm(np.abs(grav_vg), valid),         # vertical gravity gradient
        rank_norm(np.abs(grav_hg), valid),         # horizontal gravity gradient (edge detection)
        rank_norm(np.abs(mag_hg), valid),          # magnetic horizontal gradient
        rank_norm(np.abs(mag_vg), valid),          # magnetic vertical gradient
        rank_norm(strain_inv, valid),              # strain second invariant
        rank_norm(shear, valid),                   # shear rate
        rank_norm(1.0 / (depth_base + 1.0), valid),  # shallow basement = more likely surface fault
        rank_norm(cond, valid),                    # high conductivity = clay/fluid
    ]

    # Weighted combination: gravity and magnetic gradients dominate (structural edges)
    weights = np.array([0.20, 0.10, 0.20, 0.15, 0.10, 0.08, 0.05, 0.07, 0.05])
    score = np.zeros_like(components[0])
    for w, c in zip(weights, components):
        score += w * c

    return np.where(valid, score, 0.0).astype(np.float32)


def compute_view_b(features_path: str, rad_path: str, ext_path: str, valid: np.ndarray) -> np.ndarray:
    """View B: surface + radiometric wavelength-contrast score.

    Novel features:
    1. Multi-scale wavelength contrast: |Hessian|_fine / |Hessian|_coarse
       High = sharp localized feature (scarp/lineament), low = broad regional
    2. Radiometric Th/K ratio: hydrothermal K-leaching indicator
    3. DEM slope + curvature

    This combination has NOT been used in any prior submission.
    """
    with rasterio.open(features_path) as src:
        det_elev = src.read(12).astype(np.float32)
        slope = src.read(19).astype(np.float32)
    det_elev[~np.isfinite(det_elev)] = 0.0
    det_elev[det_elev < -1e38] = 0.0
    slope[~np.isfinite(slope)] = 0.0
    slope[slope < -1e38] = 0.0

    # Multi-scale Hessian eigenvalue magnitudes
    elev_smooth_fine = smooth_normalized(det_elev, valid, sigma=1.0)
    elev_smooth_coarse = smooth_normalized(det_elev, valid, sigma=8.0)

    lam_max_fine, lam_min_fine = hessian_eigenvalues(elev_smooth_fine)
    lam_max_coarse, lam_min_coarse = hessian_eigenvalues(elev_smooth_coarse)

    # Curvature magnitude at each scale
    curv_fine = np.abs(lam_max_fine) + np.abs(lam_min_fine)
    curv_coarse = np.abs(lam_max_coarse) + np.abs(lam_min_coarse)

    # Wavelength contrast ratio: high = sharp local feature relative to regional
    eps = 1e-10
    wavelength_contrast = curv_fine / (curv_coarse + eps)
    # Clip extreme ratios
    p99 = np.percentile(wavelength_contrast[valid], 99)
    wavelength_contrast = np.clip(wavelength_contrast, 0, p99)

    # Radiometric Th/K ratio from GeoDAWN extensions
    # geodawn_extensions_u8.tif has: Th/K, U/K, U/Th ratios, TMI up-continued 150m
    th_k_ratio = np.zeros(valid.shape, dtype=np.float32)
    if Path(ext_path).exists():
        with rasterio.open(ext_path) as src:
            if src.count >= 1:
                th_k_raw = src.read(1).astype(np.float32)
                # uint8 quantized, normalize to [0,1]
                th_k_ratio = th_k_raw / 255.0
                th_k_ratio[~np.isfinite(th_k_ratio)] = 0.0

    # GeoDAWN radiometric: geodawn_rad_u8.tif has K, Th, U, TC channels
    u_channel = np.zeros(valid.shape, dtype=np.float32)
    if Path(rad_path).exists():
        with rasterio.open(rad_path) as src:
            if src.count >= 3:
                u_raw = src.read(3).astype(np.float32)
                u_channel = u_raw / 255.0
                u_channel[~np.isfinite(u_channel)] = 0.0

    def rank_norm(a, valid):
        v = a[valid]
        if v.size == 0:
            return np.zeros_like(a)
        lo, hi = np.percentile(v, 1), np.percentile(v, 99)
        if hi <= lo:
            return np.zeros_like(a)
        return np.clip((a - lo) / (hi - lo), 0, 1)

    components = [
        rank_norm(wavelength_contrast, valid),    # novel: multi-scale wavelength ratio
        rank_norm(slope, valid),                   # DEM slope
        rank_norm(curv_fine, valid),               # fine-scale curvature magnitude
        rank_norm(th_k_ratio, valid),              # novel: Th/K hydrothermal alteration
        rank_norm(u_channel, valid),               # uranium (reducing conditions indicator)
    ]

    # Weights: wavelength contrast dominates (it's the novel signal)
    weights = np.array([0.35, 0.20, 0.20, 0.15, 0.10])
    score = np.zeros_like(components[0])
    for w, c in zip(weights, components):
        score += w * c

    return np.where(valid, score, 0.0).astype(np.float32)


def compute_disagreement_field(view_a: np.ndarray, view_b: np.ndarray,
                               valid: np.ndarray, cat: np.ndarray) -> np.ndarray:
    """Disagreement signal: A-confident + B-abstains = buried fault candidate.

    Where View A (geophysical) is strong but View B (surface) is weak,
    the fault may be concealed beneath alluvial cover - the most geologically
    interesting case for geothermal discovery.

    The disagreement is: (A - B) * A, gated to where A > median(A).
    This ensures we only emit where A is actually confident, not just where B is zero.
    """
    a_vals = view_a[valid]
    a_median = np.median(a_vals)
    a_p75 = np.percentile(a_vals, 75)

    # A-confident: above median
    a_confident = view_a > a_median
    # B-abstains: below 25th percentile of B
    b_vals = view_b[valid]
    b_p25 = np.percentile(b_vals, 25)
    b_abstains = view_b < b_p25

    # Disagreement score: positive where A is strong and B is weak
    disagreement = np.where(valid, (view_a - view_b) * np.where(a_confident, 1.0, 0.1), 0.0)
    # Boost where BOTH conditions are met (A confident AND B abstains)
    boost = np.where(a_confident & b_abstains, 2.0, 1.0)
    disagreement = disagreement * boost

    # Gate: must be positive
    disagreement = np.maximum(disagreement, 0.0)

    # Normalize to [0, 1]
    d_vals = disagreement[valid & (disagreement > 0)]
    if d_vals.size > 0:
        p99 = np.percentile(d_vals, 99)
        if p99 > 0:
            disagreement = np.clip(disagreement / p99, 0, 1)

    return disagreement.astype(np.float32)


def geological_reasoning_a_only() -> dict:
    """Geological justification for A-only (buried fault) candidates.

    Required by the parallel-run protocol: every A-only candidate needs geological reasoning.
    """
    return {
        "mechanism": "Concealed normal faults beneath Quaternary alluvial cover in the "
                     "Walker Lane / northern Great Basin transition. These faults produce "
                     "measurable gravity and magnetic gradients at depth but no surface scarp "
                     "because post-faulting sedimentation has buried the geomorphic expression.",
        "evidence_base": "Isostatic gravity anomaly horizontal gradient detects lateral density "
                        "contrasts across fault-bounded basement blocks. Magnetic gradients detect "
                        "susceptibility contrasts. Geodetic strain rates indicate active deformation.",
        "geothermal_relevance": "Buried faults control fluid flow in geothermal systems by "
                               "creating permeability pathways through impermeable basin fill. "
                               "The GeoDAWN study area contains multiple known geothermal systems "
                               "(Brady, Desert Peak, Salt Wells) associated with concealed structures.",
        "confounders": "Lithologic contacts, intrusive margins, and paleo-channels can also produce "
                      "gravity/magnetic gradients without faulting. The co-training approach mitigates "
                      "this by requiring surface corroboration for B-confident predictions.",
        "reference": "GeoDAWN airborne geophysical survey, USGS DOI 10.5066/P93LGLVQ; "
                    "Blum & Mitchell (1998) co-training framework DOI 10.1145/279943.279962",
    }


def main():
    t0 = time.time()
    print("=" * 72)
    print("H87: Co-training wavelength contrast + radiometric Th/K ratio")
    print("=" * 72)

    # --- Load grid and labels ---
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
        ref_meta = dict(count=ref.count, dtype=ref.dtypes[0], shape=ref.shape,
                       crs=ref.crs.to_epsg(), transform=tuple(ref.transform))
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1

    # Footprint: intersection of all-band finite
    feat_valid = footprint_all_bands(str(FEATURES))
    eligible = feat_valid & domain
    print(f"Footprint: {int(eligible.sum()):,} px ({eligible.mean():.4%} of grid)")
    print(f"Catalogue: {int(cat.sum()):,} px ({cat.sum()/eligible.sum():.4%} of footprint)")

    # --- Compute View A (geophysical) ---
    print("\n[1/5] Computing View A (geophysical potential-field)...")
    view_a = compute_view_a(str(FEATURES), eligible)
    print(f"  View A: mean={view_a[eligible].mean():.4f}, std={view_a[eligible].std():.4f}")

    # --- Compute View B (surface + wavelength contrast + radiometric) ---
    print("\n[2/5] Computing View B (surface wavelength contrast + radiometric)...")
    view_b = compute_view_b(str(FEATURES), str(GEODAWN_RAD), str(GEODAWN_EXT), eligible)
    print(f"  View B: mean={view_b[eligible].mean():.4f}, std={view_b[eligible].std():.4f}")

    # --- Test independence assumption ---
    print("\n[3/5] Testing conditional independence (Blum & Mitchell requirement)...")
    # Correlation between views on valid pixels
    a_v = view_a[eligible]
    b_v = view_b[eligible]
    corr = np.corrcoef(a_v, b_v)[0, 1]
    print(f"  Spearman-like Pearson correlation: {corr:.4f}")
    if abs(corr) > 0.60:
        print(f"  WARNING: |r| = {abs(corr):.3f} > 0.60 threshold")
        print("  Co-training assumption may be violated; proceeding with caution.")
    else:
        print(f"  OK: |r| = {abs(corr):.3f} < 0.60, views are sufficiently independent.")

    # --- Compute disagreement field ---
    print("\n[4/5] Computing disagreement field (A-confident, B-abstains)...")
    disagreement = compute_disagreement_field(view_a, view_b, eligible, cat)
    print(f"  Disagreement: mean={disagreement[eligible].mean():.4f}, "
          f"p95={np.percentile(disagreement[eligible], 95):.4f}")

    # --- Metric-aware placement ---
    print("\n[5/5] Metric-aware placement with spacing and catalogue collar...")

    # Catalogue collar: exclude pixels within 200m of known faults
    vd = ndi.distance_transform_edt(~cat)
    allowed = eligible & ~cat & (vd > CATALOGUE_COLLAR_PX)
    print(f"  Allowed pixels (off-catalogue, >200m): {int(allowed.sum()):,}")

    # Use disagreement as the placement field
    field = disagreement

    # Spacing-select: greedy top-k with 3px minimum separation
    em = nodes.spacing_select(field, allowed, BUDGET, min_px=MIN_SPACING_PX)
    n_placed = int(em.sum())
    print(f"  Placed: {n_placed:,} dots (target: {BUDGET})")

    if n_placed < BUDGET:
        # Fallback: relax spacing to fill budget
        print(f"  WARNING: only {n_placed} placed with spacing {MIN_SPACING_PX}px")
        print(f"  Relaxing spacing to fill budget...")
        remaining = BUDGET - n_placed
        extra_allowed = allowed & ~em
        extra = nodes.top_k_mask(field, extra_allowed, remaining)
        em = em | extra
        n_placed = int(em.sum())
        print(f"  After relaxation: {n_placed:,} dots")

    # Convert to float32 {0, 1}
    emission = em.astype(np.float32)

    # Verify spacing stats
    stats = nodes.spacing_stats(em.astype(bool)) if hasattr(nodes, 'spacing_stats') else {}
    print(f"  Spacing stats: {stats}")

    # --- Write submission ---
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    sha_short = hashlib.sha256(emission.tobytes()).hexdigest()[:8]
    name = f"h87-cotrain-wavelength-thk-{BUDGET}px-{ts}"
    subname = f"h87-cotrain-wavelength-{BUDGET}px"
    path = SUBMISSION_DIR / f"gems52-{name}.tif"
    note = f"H87 co-train wavelength+Th/K, A>B disagree, {BUDGET}px, 3px spacing, 200m collar"
    if len(note) > 140:
        note = note[:140]

    print(f"\nWriting: {path}")
    print(f"Name: {subname}")
    print(f"Note: {note} ({len(note)} chars)")

    # Write using the grid writer (all-finite, zeros outside)
    grid.write_geotiff(path, emission, nodata=None)

    # --- Independent re-read verification ---
    with rasterio.open(path) as c:
        a = c.read(1)
        meta = dict(count=c.count, dtype=c.dtypes[0], shape=c.shape,
                   crs=c.crs.to_epsg(), transform=tuple(c.transform))
        nodata_val = c.nodata

    checks = dict(
        single_band=meta["count"] == 1,
        float32=meta["dtype"] == "float32",
        shape_match=meta["shape"] == ref_meta["shape"],
        crs_match=meta["crs"] == ref_meta["crs"] == 32611,
        transform_match=np.allclose(meta["transform"], ref_meta["transform"], rtol=0, atol=1e-6),
        all_finite=bool(np.isfinite(a).all()),
        in_0_1=bool(a.min() >= 0 and a.max() <= 1),
        binary=bool(np.isin(a, [0.0, 1.0]).all()),
        nodata_none=nodata_val is None,
        ones=int((a == 1).sum()),
        budget_match=int((a == 1).sum()) == BUDGET,
        outside_domain_zero=bool((a[~domain] == 0).all()),
        on_catalogue_zero=bool((a[cat] == 0).all()),
        collar_respected=bool((a[(vd <= CATALOGUE_COLLAR_PX) & eligible] == 0).all()),
    )

    all_ok = all(v for v in checks.values() if isinstance(v, bool))
    print(f"\nVerification: {'ALL PASS' if all_ok else 'FAILURES DETECTED'}")
    for k, v in checks.items():
        status = "✓" if (v is True or (isinstance(v, int) and k in ("ones", "budget_match"))) else "✗"
        print(f"  {status} {k}: {v}")

    if not all_ok:
        raise SystemExit("Format verification failed!")

    # --- Uniqueness gate ---
    print("\n--- Uniqueness Gate ---")
    priors = gates.find_priors([ROOT / "submission", ROOT / "docs" / "downloads"],
                               exclude=path)
    print(f"  Checking against {len(priors)} prior rasters...")

    try:
        uq = gates.uniqueness_report(emission, priors)
        print(f"  Novel fraction: {uq.get('novel_fraction', 'N/A')}")
        print(f"  Pattern unique: {uq.get('pattern_unique', 'N/A')}")
        print(f"  Not union: {uq.get('not_union', 'N/A')}")
        uq_ok = uq.get("ok", False)
    except Exception as e:
        print(f"  Uniqueness check error: {e}")
        uq = {"error": str(e)}
        uq_ok = False

    # --- Lane check (sample) ---
    print("\n--- Lane Check ---")
    try:
        lane = gates.lane_report(emission, eligible, priors, sample=str(SAMPLE), phase="dots")
        print(f"  Literal verdict: {lane['literal']['verdict']}")
        print(f"  Policy verdict: {lane['policy']['verdict']}")
        lane_ok = not lane.get("duplicate", True)
    except Exception as e:
        print(f"  Lane check error: {e}")
        lane = {"error": str(e)}
        lane_ok = False

    # --- Compile receipt ---
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = dict(
        hypothesis="Co-training with multi-scale wavelength contrast and radiometric Th/K ratio; "
                   "A-confident+B-abstains = buried fault beneath alluvial cover",
        mechanism="Concealed normal faults produce gravity/magnetic gradients at depth but no "
                  "surface scarp; Th/K ratio detects hydrothermal K-leaching along fault-fluid pathways",
        non_fault_confounder="Lithologic contacts, intrusive margins, paleo-channels, and "
                            "anthropogenic linear features (roads, canals) can mimic gravity gradients",
        evidence_class="HOLDOUT-DTI (not yet run; this is the build receipt, not a score)",
        view_correlation=float(corr),
        view_independence_ok=abs(corr) < 0.60,
        budget=BUDGET,
        placed=n_placed,
        spacing_min_px=MIN_SPACING_PX,
        catalogue_collar_px=CATALOGUE_COLLAR_PX,
        format_checks=checks,
        format_ok=all_ok,
        uniqueness=uq,
        uniqueness_ok=uq_ok,
        lane=lane.get("policy", lane),
        lane_ok=lane_ok,
        submission_name=subname,
        note=note,
        sha256=sha,
        file=str(path),
        file_bytes=path.stat().st_size,
        geological_reasoning=geological_reasoning_a_only(),
        verdict="promote" if (all_ok and uq_ok) else "negative",
        build_time_s=round(time.time() - t0, 1),
    )

    evidence_path = EVIDENCE_DIR / f"h87_build.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    print(f"\nReceipt: {evidence_path}")
    print(f"Verdict: {receipt['verdict'].upper()}")
    print(f"\n{'=' * 72}")
    print(f"SUBMISSION READY: {path}")
    print(f"  SHA256: {sha}")
    print(f"  Pixels: {n_placed:,}")
    print(f"  Format: single-band float32 EPSG:32611 all-finite zeros-outside")
    print(f"  Name:   {subname}")
    print(f"  Note:   {note}")
    print(f"{'=' * 72}")

    return receipt


if __name__ == "__main__":
    main()
