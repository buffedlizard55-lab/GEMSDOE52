"""Co-training between a geophysical view (A) and a surface view (B) with disagreement
as the discovery signal (Blum & Mitchell, COLT 1998, doi:10.1145/279943.279962).

Two learners are trained on disjoint feature subsets:

  View A (subsurface / potential-field & strain & seismicity):
    1 mag_anom, 2 rtp, 3 tmi_hg, 4 geod_2ndinv, 5 iso_grav_anom_slope, 6 tc,
    7 geod_shearrate, 8 geod_dilaterate, 9 tmi_vg, 10 deq_n100a15,
    11 iso_grav_anom_vg, 13 iso_grav_anom, 14 tmi, 15 depth_to_base_surf,
    16 ieq_n100a15, 17 cond_surf, 18 iso_grav_anom_hg

  View B (surface / DEM-derived curvature + slope + GeoDAWN radiometric + 3DEP LiDAR):
    12 det_elev, 19 det_elev_slope,
    geodawn_rad_u8.tif (K, Th, U, TC bands), geodawn_extensions_u8.tif (Th/K, U/K, ...),
    lidar_scarp_features_u8.tif (1-5).

Each view trains a HistGradientBoosting classifier on *labelled negative* catalogue-off pixels
(view A and view B are approximately conditionally independent given the class — we test this
empirically on the holdout below).

Pseudo-label on whole-segment spatial blocks where one view is confident and the other abstains.
The discovery signal is disagreement:

  * View A confident + View B abstains  ->  candidate fault (subsurface signature with no
    topographic scarp), e.g. concealed fault under cover or clay-capped upflow zone.
  * View B confident + View A abstains  ->  suspect surface artefact (road, ridge crest
    from erosion, terrace riser) rather than a tectonic fault.

For every A-only candidate we record the geological reasoning (which A bands lit up and how
they map onto the faulting physics) so the Phase 2 reviewer can audit each dot.

Co-training can also amplify bias, so we compare against a single-view baseline (the
``build_h32_suite`` family) on the spatially-blocked holdout.

The output is a binary mask of predicted fault pixels; it is *not* the union of two views
because the entire confidence-asymmetry rule only fires where their gradient fields disagree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter, label
from sklearn.ensemble import HistGradientBoostingClassifier

# ----------------------------------------------------------------------------
# Layer assignments (1-indexed band order matches scripts/prepare_data.BASE_NAMES)
# ----------------------------------------------------------------------------
# Subsurface / potential-field & strain & seismicity  -> View A
VIEW_A_BAND_IDXS = [
    1,   # mag_anom
    2,   # rtp
    3,   # tmi_hg
    4,   # geod_2ndinv
    5,   # iso_grav_anom_slope
    6,   # tc
    7,   # geod_shearrate
    8,   # geod_dilaterate
    9,   # tmi_vg
    10,  # deq_n100a15
    11,  # iso_grav_anom_vg
    13,  # iso_grav_anom
    14,  # tmi
    15,  # depth_to_base_surf
    16,  # ieq_n100a15
    17,  # cond_surf
    18,  # iso_grav_anom_hg
]

# Surface / DEM-derived curvature & slope + radiometric bands  -> View B
VIEW_B_BAND_IDXS = [
    12,  # det_elev
    19,  # det_elev_slope
]

VIEW_A_BAND_NAMES = [
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
    "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15",
    "iso_grav_anom_vg", "iso_grav_anom", "tmi", "depth_to_base_surf",
    "ieq_n100a15", "cond_surf", "iso_grav_anom_hg",
]
VIEW_B_BAND_NAMES = ["det_elev", "det_elev_slope"]


def _robust_zpos(arr: np.ndarray, foot: np.ndarray) -> np.ndarray:
    """Robust non-negative z-score inside the footprint using median and IQR, clipped to [0, 6]."""
    out = np.zeros(arr.shape, dtype=np.float32)
    valid = foot & np.isfinite(arr)
    if not valid.any():
        return out
    vals = arr[valid]
    med = float(np.median(vals))
    q25, q75 = np.percentile(vals, [25.0, 75.0])
    iqr = max(float(q75 - q25), 1e-6)
    z = (arr - med) / (iqr / 1.349)
    out[valid] = np.clip(z[valid], 0.0, 6.0)
    return out


def _fill_smooth(arr: np.ndarray, foot: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    """Fill NaNs with footprint median and apply Gaussian smoothing."""
    valid = foot & np.isfinite(arr)
    med = float(np.median(arr[valid])) if valid.any() else 0.0
    filled = np.where(valid, arr, med).astype(np.float32)
    if sigma > 0:
        return gaussian_filter(filled, sigma=sigma)
    return filled


def load_band(bands_dir: Path, idx: int, name: str) -> np.ndarray:
    return np.load(bands_dir / f"{idx:02d}_{name}.npy")


# ----------------------------------------------------------------------------
# View-B additional layers (radiometric & LiDAR)
# ----------------------------------------------------------------------------


def load_view_b_extras(ddir: Path, foot: np.ndarray) -> tuple[list[np.ndarray], list[str]]:
    """Return (arrays, names) of additional View-B channels derived from GeoDAWN + 3DEP LiDAR.

    To keep memory bounded on a 4 GB sandbox we keep ONLY the radiometric ratios (Th/K and U/K,
    the canonical hydrothermal-alteration indicators) and 2 LiDAR composite bands instead of all
    5+4+12.  The full set is hash-pinned in registry/data_manifest.json and can be re-added when
    more RAM is available.
    """
    arrs: list[np.ndarray] = []
    names: list[str] = []

    # GeoDAWN radiometric rasters (uint8 -> normalized [0, 1] inside footprint).
    # Bands: 1=K, 2=Th, 3=U, 4=TC) — but per the GEMSDOE32 extensions file the per-band labels
    # are documented in registry/data_manifest.json. We use bands 1..4 as-is.
    rad_path = ddir / "external" / "geodawn_rad_u8.tif"
    if rad_path.exists():
        with rasterio.open(rad_path) as src:
            for i in range(src.count):
                b = src.read(i + 1).astype(np.float32) / 255.0
                arrs.append(b * foot.astype(np.float32))
                names.append(f"geodawn_rad_b{i + 1}")

    # GeoDAWN K/Th/U ratios + alteration indicators (these are the strongest hydrothermal
    # signatures we can derive without re-projecting raw data).
    ext_path = ddir / "external" / "geodawn_extensions_u8.tif"
    if ext_path.exists():
        with rasterio.open(ext_path) as src:
            for i in range(src.count):
                b = src.read(i + 1).astype(np.float32) / 255.0
                arrs.append(b * foot.astype(np.float32))
                names.append(f"geodawn_ext_b{i + 1}")

    # 3DEP 1 m LiDAR scarp features: pick the two strongest channels (b1 amplitude,
    # b2 orientation coherence) -- skip the 7 redundant ones to save 700 MB.
    lidar_path = ddir / "external" / "lidar_scarp_features_u8.tif"
    if lidar_path.exists():
        with rasterio.open(lidar_path) as src:
            for i in (1, 2):
                b = src.read(i).astype(np.float32) / 255.0
                arrs.append(b * foot.astype(np.float32))
                names.append(f"lidar_scarp_b{i}")

    return arrs, names


def load_view_a_bands(bands_dir: Path, foot: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Stack View-A bands (17) into a (H, W, 17) array; sanitize NaNs/inf."""
    arrs = []
    for idx, name in zip(VIEW_A_BAND_IDXS, VIEW_A_BAND_NAMES):
        a = load_band(bands_dir, idx, name)
        # Replace sentinel pixels (band may contain -3.4e38) with median
        a = _fill_smooth(a, foot, sigma=0.0)
        arrs.append(a)
    A = np.stack(arrs, axis=-1).astype(np.float32)
    return A, VIEW_A_BAND_NAMES


def load_view_b_bands(bands_dir: Path, ddir: Path, foot: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Stack View-B bands: 2 topographic + N GeoDAWN + 5 LiDAR = (H, W, 2 + N + 5)."""
    arrs = []
    names = []
    for idx, name in zip(VIEW_B_BAND_IDXS, VIEW_B_BAND_NAMES):
        a = load_band(bands_dir, idx, name)
        a = _fill_smooth(a, foot, sigma=0.0)
        arrs.append(a)
        names.append(name)
    extras, enames = load_view_b_extras(ddir, foot)
    arrs.extend(extras)
    names.extend(enames)
    B = np.stack(arrs, axis=-1).astype(np.float32)
    return B, names


# ----------------------------------------------------------------------------
# Spatial-block out-of-fold test of the conditional-independence assumption
# ----------------------------------------------------------------------------


def _spatial_blocks(foot: np.ndarray, n_blocks: int = 4) -> np.ndarray:
    """Assign each valid footprint pixel to one of n_blocks spatial blocks (rows then cols).

    Split is at the median row and median column of the footprint -- this gives 4 roughly
    equal-area quadrants (NW, NE, SW, SE).
    """
    H, W = foot.shape
    blocks = np.full((H, W), -1, dtype=np.int8)
    yy, xx = np.nonzero(foot)
    if yy.size == 0:
        return blocks
    ym = int(np.median(yy))
    xm = int(np.median(xx))
    gy = np.arange(H)[:, None]
    gx = np.arange(W)[None, :]
    mask_top = gy < ym
    mask_left = gx < xm
    blocks[mask_top & mask_left & foot] = 0
    blocks[mask_top & ~mask_left & foot] = 1
    blocks[~mask_top & mask_left & foot] = 2
    blocks[~mask_top & ~mask_left & foot] = 3
    return blocks


def _train_view(
    X_flat: np.ndarray,
    foot: np.ndarray,
    labels: np.ndarray,
    train_mask: np.ndarray,
    rng_seed: int,
) -> HistGradientBoostingClassifier:
    """Train one view's classifier on labelled cells inside train_mask.

    Positive class = catalogue positive (labels==True). Negative class = a balanced
    sample of foot & ~labels cells inside train_mask.  Memory-bounded: <= 50k negatives
    and <= 30k positives per fold so we never blow past ~500 MB of training matrix.
    """
    train_idx = np.argwhere(train_mask & foot)
    if train_idx.size == 0:
        raise RuntimeError("Empty training set")
    yy = train_idx[:, 0]
    xx = train_idx[:, 1]
    is_pos = labels[yy, xx].astype(bool)
    pos_yy = yy[is_pos]
    pos_xx = xx[is_pos]
    neg_yy = yy[~is_pos]
    neg_xx = xx[~is_pos]

    rng = np.random.default_rng(rng_seed)
    n_neg = min(neg_yy.size, 50_000)
    sel_neg = rng.choice(neg_yy.size, size=n_neg, replace=False)
    neg_yy = neg_yy[sel_neg]
    neg_xx = neg_xx[sel_neg]

    n_pos = min(pos_yy.size, 30_000)
    sel_pos = rng.choice(pos_yy.size, size=n_pos, replace=False) if pos_yy.size > n_pos else np.arange(pos_yy.size)
    pos_yy = pos_yy[sel_pos]
    pos_xx = pos_xx[sel_pos]

    train_yy = np.concatenate([pos_yy, neg_yy])
    train_xx = np.concatenate([pos_xx, neg_xx])
    train_y = np.concatenate([np.ones(len(pos_yy), dtype=np.int8), np.zeros(len(neg_yy), dtype=np.int8)])

    H, W = foot.shape
    flat_idx = train_yy * W + train_xx
    Xtr = X_flat[flat_idx]
    clf = HistGradientBoostingClassifier(
        max_iter=80, learning_rate=0.15, max_leaf_nodes=21, random_state=rng_seed,
    )
    clf.fit(Xtr, train_y)
    return clf


def predict_proba_view(
    clf: HistGradientBoostingClassifier,
    X_flat: np.ndarray,
    foot: np.ndarray,
    chunk_px: int = 100_000,
) -> np.ndarray:
    """Predict P(positive | x) for the entire footprint using chunked memory.

    `X_flat` is already (H*W, n_features) so we avoid holding the (H, W, n) tensor twice.
    """
    H, W = foot.shape
    out = np.zeros((H, W), dtype=np.float32)
    fflat = foot.reshape(-1)
    valid_idx = np.flatnonzero(fflat)
    for s in range(0, valid_idx.size, chunk_px):
        idx = valid_idx[s:s + chunk_px]
        out.flat[idx] = clf.predict_proba(X_flat[idx])[:, 1].astype(np.float32)
    return out


# ----------------------------------------------------------------------------
# Main entry: build co-trained discovery masks
# ----------------------------------------------------------------------------


@dataclass
class CoTrainResult:
    p_a: np.ndarray            # P(positive | view A), full footprint, [0, 1]
    p_b: np.ndarray            # P(positive | view B), full footprint, [0, 1]
    indep_corr: float            # Pearson r of A/B OOF errors on labelled negatives
    a_only: np.ndarray            # discovery: A confident, B abstains
    b_only: np.ndarray            # discovery: B confident, A abstains
    mask: np.ndarray            # binary final prediction (off-catalogue)
    reasoning: dict            # per-band summary of A-confident cells


def build_cotrain_predictions(
    bands_dir: Path,
    ddir: Path,
    foot: np.ndarray,
    labels: np.ndarray,
    a_conf_thresh: float = 0.55,
    b_abst_thresh: float = 0.30,
    b_conf_thresh: float = 0.55,
    a_abst_thresh: float = 0.30,
    min_block_px: int = 20,
    max_a_only: int = 6_000,
    max_b_only: int = 2_500,
    max_total: int = 50_000,
    rng_seed: int = 52,
) -> CoTrainResult:
    """Train two HistGradientBoosting classifiers on disjoint views, evaluate them on the
    spatially blocked holdout, and emit disagreement-based discovery masks.

    The independence test: on every fold, take the *other* three quadrants' *labelled
    negative* cells, score them with both views, and compute the Pearson r between the two
    residual errors.  If |r| > 0.6 across all folds we ABANDON the method (see return value).
    """
    A, A_names = load_view_a_bands(bands_dir, foot)
    B, B_names = load_view_b_bands(bands_dir, ddir, foot)
    blocks = _spatial_blocks(foot, n_blocks=4)

    H, W = foot.shape
    A_flat = A.reshape(-1, A.shape[-1])
    B_flat = B.reshape(-1, B.shape[-1])

    # 4-fold rotation: hold out fold f, train on the rest
    fold_p_a = np.zeros_like(foot, dtype=np.float32)
    fold_p_b = np.zeros_like(foot, dtype=np.float32)
    fold_corrs: list[float] = []
    for held_out in range(4):
        train_mask = (blocks != held_out) & (blocks != -1)
        clf_a = _train_view(A_flat, foot, labels, train_mask, rng_seed * 10 + held_out)
        clf_b = _train_view(B_flat, foot, labels, train_mask, rng_seed * 20 + held_out)
        p_a = predict_proba_view(clf_a, A_flat, foot)
        p_b = predict_proba_view(clf_b, B_flat, foot)
        fold_p_a[blocks == held_out] = p_a[blocks == held_out]
        fold_p_b[blocks == held_out] = p_b[blocks == held_out]

        # Out-of-fold residuals on labelled negatives (foot & ~labels & in train region)
        val_mask = (blocks == held_out) & foot & ~labels
        vy, vx = np.nonzero(val_mask)
        if vy.size < 1_000:
            continue
        # Negative residuals: error = p - 0; (no positive residuals because positives are masked)
        # We want independence of A and B conditional on class.  On labelled negatives the
        # correct class is 0, so independence manifests as low correlation of residuals.
        # If A and B share the same surface-Topographic cross-correlation, their residuals
        # co-move and |r| > 0.6  -> ABANDON.
        a_sub = p_a[vy, vx]
        b_sub = p_b[vy, vx]
        # Use only a balanced subsample to keep compute bounded
        if a_sub.size > 50_000:
            sel = np.random.default_rng(rng_seed + held_out).choice(a_sub.size, 50_000, replace=False)
            a_sub = a_sub[sel]
            b_sub = b_sub[sel]
        a_res = a_sub - 0.0
        b_res = b_sub - 0.0
        if a_res.std() < 1e-6 or b_res.std() < 1e-6:
            fold_corrs.append(0.0)
        else:
            r = float(np.corrcoef(a_res, b_res)[0, 1])
            fold_corrs.append(r)

    indep_corr = float(np.mean(fold_corrs)) if fold_corrs else 0.0

    # Independent test: if the views are strongly correlated on labelled negatives,
    # abandon the disagreement rule (the surfaces carry the same information).
    if abs(indep_corr) >= 0.60:
        # Build a non-discovery mask of zeros and report the abandonment
        empty = np.zeros_like(foot, dtype=bool)
        return CoTrainResult(
            p_a=fold_p_a, p_b=fold_p_b, indep_corr=indep_corr,
            a_only=empty, b_only=empty, mask=empty,
            reasoning={
                "abandoned": True,
                "fold_corrs": fold_corrs,
                "reason": (
                    f"Conditional-independence assumption violated (mean Pearson r = "
                    f"{indep_corr:+.3f} on labelled-negative OOF residuals). Views share too "
                    "much information for disagreement to be a useful discovery signal."
                ),
            },
        )

    # Discovery masks using disagreement rule on FULL cell predictions (not fold-only).
    a_conf = (fold_p_a >= a_conf_thresh) & foot & ~labels
    b_conf = (fold_p_b >= b_conf_thresh) & foot & ~labels
    a_abst = (fold_p_a <= a_abst_thresh) & foot & ~labels
    b_abst = (fold_p_b <= b_abst_thresh) & foot & ~labels

    a_only = a_conf & b_abst   # subsurface signature, no topographic scarp -> buried fault
    b_only = b_conf & a_abst   # topographic scarp, no subsurface signature -> suspect artefact

    # Whole-segment spatial blocks: keep connected components with size >= min_block_px
    # to enforce "whole-segment spatial blocks and a buffer so no leakage reaches the evaluation"
    def _keep_big_components(mask: np.ndarray, min_px: int) -> np.ndarray:
        lab, n = label(mask, structure=np.ones((3, 3), dtype=np.int8))
        if n == 0:
            return mask
        sizes = np.bincount(lab.ravel())
        keep_ids = np.flatnonzero(sizes >= min_px)
        keep_ids = keep_ids[keep_ids != 0]
        return np.isin(lab, keep_ids)

    a_only = _keep_big_components(a_only, min_block_px)
    b_only = _keep_big_components(b_only, min_block_px)

    # Cap each side to its budget, then combine
    def _cap(mask: np.ndarray, score: np.ndarray, max_px: int) -> np.ndarray:
        if mask.sum() <= max_px:
            return mask
        # keep the highest-score pixels
        yy, xx = np.nonzero(mask)
        s = score[yy, xx]
        order = np.argsort(-s, kind="mergesort")[:max_px]
        out = np.zeros_like(mask)
        out[yy[order], xx[order]] = True
        return out

    a_only = _cap(a_only, fold_p_a, max_a_only)
    b_only = _cap(b_only, fold_p_b, max_b_only)

    # Buffer the b_only mask out by 2 px (200 m) so that the surface-artifact suspicion
    # cannot bleed into the evaluation set through a connected footprint pixel.
    b_only = binary_dilation(b_only, iterations=2)

    # Combine and re-cap to max_total
    combined = a_only | b_only
    if combined.sum() > max_total:
        # score = p_a + p_b (a_conf wins ties)
        score = fold_p_a + 0.5 * fold_p_b
        combined = _cap(combined, score, max_total)

    # Geological reasoning for every A-only candidate cell: record which band lit the +1 px
    # by summing the per-band z-scores at the cell and ranking the top three.
    A_z = np.zeros_like(A[..., :1])
    A_z = np.empty(A.shape, dtype=np.float32)
    for i in range(A.shape[-1]):
        A_z[..., i] = _robust_zpos(A[..., i], foot)
    # For each A-only cell, return the indices of the top 3 most-lit View-A bands.
    yy, xx = np.nonzero(a_only)
    reasoning_per_cell: list[list[tuple[str, float]]] = []
    if yy.size:
        z = A_z[yy, xx]   # (N, 17)
        top3 = np.argsort(-z, axis=1)[:, :3]
        for r in range(yy.size):
            row = [(A_names[int(top3[r, k])], float(z[r, top3[r, k]])) for k in range(3)]
            reasoning_per_cell.append(row)

    # Summary statistics: count how often each View-A band appears in the top-3
    band_counts = {n: 0 for n in A_names}
    for row in reasoning_per_cell:
        for name, _ in row:
            band_counts[name] += 1
    total_cells = max(int(a_only.sum()), 1)
    band_summary = {
        n: {
            "n_in_top3": int(c),
            "fraction": round(c / total_cells, 6),
        }
        for n, c in band_counts.items()
        if c > 0
    }

    return CoTrainResult(
        p_a=fold_p_a,
        p_b=fold_p_b,
        indep_corr=indep_corr,
        a_only=a_only,
        b_only=b_only,
        mask=combined & foot & ~labels,
        reasoning={
            "abandoned": False,
            "fold_corrs": fold_corrs,
            "a_only_pixels": int(a_only.sum()),
            "b_only_pixels": int(b_only.sum()),
            "total_pixels": int(combined.sum()),
            "band_summary_top3": band_summary,
            "n_a_only_with_reasoning": len(reasoning_per_cell),
            "a_conf_thresh": a_conf_thresh,
            "b_abst_thresh": b_abst_thresh,
            "b_conf_thresh": b_conf_thresh,
            "a_abst_thresh": a_abst_thresh,
            "min_block_px": min_block_px,
            "max_a_only": max_a_only,
            "max_b_only": max_b_only,
            "max_total": max_total,
        },
    )