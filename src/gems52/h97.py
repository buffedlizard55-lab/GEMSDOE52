"""H97: co-training views, the disagreement field, and the prevalence-matched off-catalogue instrument.

Lane (from the current brief, verbatim): "Co-training between a geophysical view and a surface view,
with disagreement as the discovery signal ... View A is potential-field and subsurface (gravity,
magnetics, strain, seismicity). View B is surface (DEM-derived curvature and slope, plus any
radiometric bands present in training_features.tif)."

What is *new* in H97 relative to this repository's record
--------------------------------------------------------
1. View B uses the **in-stack** radiometric band (band 6) rather than the external GeoDAWN ratio
   files H87 used.  Band 6 carries a magnetic tag but its bytes are the GeoDAWN total count
   (IR-H85-005; re-measured by ``band6_is_radiometric_total_count`` below, not asserted).
2. The round does **not** re-test a physical gate on the disagreement field.  H62 measured
   cover/edge/persistence gating and it subtracted ranking quality (``knowledge/33``); re-running it
   would be re-litigating a closed experiment.
3. The round tests the *mass lever* named as the next step in ``knowledge/76`` §6: it builds a
   **prevalence-matched** off-catalogue instrument (the H83 instrument's truth thinned to the
   incumbent |G| bracket, 14,089 px) and measures DTI as a function of the emitted budget K.  The
   H83 instrument over-rewarded recall (55,562 px of truth against ≈14,000 real), which is why it
   contradicted the board's measured monotone decrease of score with mass.

Nothing in this module reads ``labels.tif``.  The catalogue is only ever passed in by a caller that
has already restricted it to a fold's visible pixels.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

RING_PX = 2                    # 200 m catalogue ring removed from emission (knowledge/49 §1)
TARGET_TRUTH_PX = 14089        # incumbent |G| bracket, knowledge/76 §3
SIGMA_FINE = 2.0
SIGMA_COARSE = 6.0

# ---------------------------------------------------------------- helpers

def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank of ``a`` inside ``mask`` mapped to [0, 1]; zero elsewhere.

    Ties are impossible on continuous geophysical rasters except on flat regions, where the ordering
    is still deterministic (argsort on the flat index), so the field is reproducible.
    """
    out = np.zeros(a.shape, np.float32)
    v = np.asarray(a, np.float64)[mask]
    if v.size == 0:
        return out
    if v.size == 1 or np.ptp(v) == 0:
        out[mask] = 0.0
        return out
    order = np.argsort(np.argsort(v, kind="stable"), kind="stable")
    out[mask] = (order.astype(np.float32) / max(v.size - 1, 1))
    return out


def smooth_norm(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    """NaN-aware Gaussian smoothing: numerator and support smoothed with the same kernel."""
    good = valid & np.isfinite(a)
    num = ndi.gaussian_filter(np.where(good, a, 0.0).astype(np.float64), sigma,
                              mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float64), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8).astype(np.float32)


def grad_mag(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    g = smooth_norm(a, valid, sigma)
    gy, gx = np.gradient(g)
    return np.hypot(gx, gy).astype(np.float32)


def curvature_mag(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    """|lambda_max| + |lambda_min| of the Hessian of the smoothed field (px units)."""
    g = smooth_norm(a, valid, sigma)
    gyy = np.gradient(np.gradient(g, axis=0), axis=0)
    gxx = np.gradient(np.gradient(g, axis=1), axis=1)
    gyx = np.gradient(np.gradient(g, axis=0), axis=1)
    tr = gyy + gxx
    det = gyy * gxx - gyx * gyx
    disc = np.sqrt(np.maximum(0.25 * tr * tr - det, 0.0))
    lam_max = 0.5 * tr + disc
    lam_min = 0.5 * tr - disc
    return (np.abs(lam_max) + np.abs(lam_min)).astype(np.float32)


def _clean(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, np.float32)
    out = np.where(np.isfinite(a) & (a > -1e38), a, np.nan).astype(np.float32)
    return out


def band6_is_radiometric_total_count(features_path, rad_path, sample: int = 200_000,
                                     seed: int = 8801) -> dict:
    """Re-measure IR-H85-005 instead of quoting it: band 6 bytes vs GeoDAWN total count.

    Returns the Spearman correlation over a fixed random subsample of co-finite pixels.  A high
    value is what licenses treating band 6 as the in-stack radiometric channel the brief asks for.
    """
    import rasterio
    from scipy.stats import spearmanr
    with rasterio.open(features_path) as ds:
        b6 = _clean(ds.read(6))
    with rasterio.open(rad_path) as ds:
        names = [str(x).lower() for x in ds.descriptions]
        rad_band = names.index("tc") + 1 if "tc" in names else ds.count
        tc = _clean(ds.read(rad_band))
    ok = np.isfinite(b6) & np.isfinite(tc)
    flat = np.flatnonzero(ok.ravel())
    rng = np.random.default_rng(seed)
    take = rng.choice(flat, size=min(sample, flat.size), replace=False)
    r = spearmanr(b6.ravel()[take], tc.ravel()[take])
    return dict(band6_vs_geodawn_tc_spearman=float(r.statistic), n=int(take.size),
                rad_band_used=int(rad_band),
                rad_descriptions=[str(x) for x in names])


# ---------------------------------------------------------------- views

A_BANDS = (18, 11, 5, 3, 9, 2)      # gravity HG/VG/slope, TMI HG/VG, RTP


def view_a(features_path: str, valid: np.ndarray) -> np.ndarray:
    """View A -- potential-field edge family (no depth, conductivity or strain: those are not edges)."""
    import rasterio
    with rasterio.open(features_path) as ds:
        raw = {b: _clean(ds.read(b)) for b in A_BANDS}
    comps = [rank01(grad_mag(raw[b], valid, SIGMA_FINE), valid) for b in A_BANDS]
    acc = np.zeros(valid.shape, np.float32)
    for c in comps:
        acc += c
    return (acc / len(comps)).astype(np.float32)


def view_b(features_path: str, valid: np.ndarray) -> np.ndarray:
    """View B -- surface family: DEM curvature and slope + the in-stack radiometric band."""
    import rasterio
    with rasterio.open(features_path) as ds:
        elev = _clean(ds.read(12))       # detrended elevation
        slope = _clean(ds.read(19))      # detrended elevation slope
        rad = _clean(ds.read(6))         # radiometric total count by bytes (IR-H85-005)
    comps = [
        rank01(curvature_mag(elev, valid, SIGMA_FINE), valid),
        rank01(curvature_mag(elev, valid, SIGMA_COARSE), valid),
        rank01(grad_mag(elev, valid, SIGMA_FINE), valid),
        rank01(curvature_mag(slope, valid, SIGMA_FINE), valid),
        rank01(smooth_norm(rad, valid, 4.0), valid),
    ]
    acc = np.zeros(valid.shape, np.float32)
    for c in comps:
        acc += c
    return (acc / len(comps)).astype(np.float32)


def disagreement(a_rank: np.ndarray, b_rank: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """A-confident, B-abstains: A * (1 - B), the discovery signal the brief names.

    No physical gate multiplies this (that is H62's closed experiment).  The hard conjunction
    A >= 0.75 and B <= 0.40 is reported as a *composition* diagnostic, never as the emission rule.
    """
    field = (a_rank * (1.0 - b_rank)).astype(np.float32)
    return np.where(valid, field, 0.0).astype(np.float32)


def composition(a_rank, b_rank, valid, q_conf=0.75, q_abstain=0.40) -> dict:
    return dict(
        a_confident_and_b_abstains_px=int((valid & (a_rank >= q_conf) & (b_rank <= q_abstain)).sum()),
        a_confident_px=int((valid & (a_rank >= q_conf)).sum()),
        b_abstains_px=int((valid & (b_rank <= q_abstain)).sum()),
        eligible_px=int(valid.sum()),
    )


# ---------------------------------------------------------------- instruments

def offcatalogue_truth(labels: np.ndarray, sgmc: np.ndarray, valid: np.ndarray,
                       cut_px: float = 3.0, target_px: int = TARGET_TRUTH_PX,
                       seed: int = 88052) -> tuple[np.ndarray, dict]:
    """Prevalence-matched off-catalogue truth: SGMC fault pixels >= ``cut_px`` from the catalogue.

    ``cut_px = 3`` is 300 m, the kernel radius, so a truth pixel here cannot be credited by any
    emission inside the 200 m ring of a catalogue fault.  The population is thinned to
    ``target_px`` (> the incumbent |G| bracket) with a fixed seed so that DTI is measured at a
    prevalence comparable to the board's, which is what H83's instrument lacked (knowledge/76 §6).
    """
    cat = labels == 1
    ed = ndi.distance_transform_edt(~cat)
    cand = np.asarray(sgmc, bool) & valid & (ed > cut_px)
    idx = np.flatnonzero(cand.ravel())
    rng = np.random.default_rng(seed)
    if idx.size > target_px:
        idx = np.sort(rng.choice(idx, size=int(target_px), replace=False))
    truth = np.zeros(cand.shape, bool)
    truth.ravel()[idx] = True
    receipt = dict(instrument="gems52-offcatalogue-prevalence-matched-v1",
                   raw_candidate_px=int(cand.sum()), truth_px=int(truth.sum()),
                   target_px=int(target_px), cut_m=float(cut_px * 100.0), seed=int(seed),
                   prevalence_note="thinned to the incumbent |G| bracket (knowledge/76 §3), which "
                                   "the unthinned H83 instrument lacked")
    return truth, receipt
