"""Unsupervised multi-family lineament detection with one-pixel thinning.

Why a detector and not a classifier
-----------------------------------
A classifier trained on the organiser's 60,988 catalogue pixels learns *habitat*: where faults
are mapped.  The scored evidence in this repository says habitat is not credit -- the champion
file's dots are strongly habitat-selected (AUC up to 0.7023 against uniform random,
``knowledge/10`` §6) yet its realised credit density is 0.139, and within the file the habitat
signature does not separate the credited core from the uncredited tail (best of 63 point features
AUC 0.5453, best of 108 structure-tensor features 0.5122).  What the metric pays for is
positional accuracy against a *trace*, because the kernel is worth up to 3.0 truth-pixel-credits
to a dot sitting on a straight trace and 0 to the same dot 3 px away
(:func:`ribbon_credit`, pinned against :mod:`gems52.metric` by ``tests/test_r5.py``).

So the detector here is a transform, not a fit: gradient ridges and Hessian line response per
layer, local strike from the structure tensor, one-pixel thinning by non-maximum suppression
*perpendicular to that strike*, then a count of how many physically independent data families put
a trace through the same pixel.  No labels enter it, which is also why the localisation assay in
:mod:`gems52_r5.localize` cannot leak: there is nothing to leak from.

Orientation convention
----------------------
Arrays are (row, col) = (north-south, east-west) with row increasing southward.  All angles in
this module are *array-convention* radians measured from the +col axis toward the +row axis, so
an array-convention angle of ``pi/2`` is a north-south line.  To convert to a geological azimuth
(clockwise from north): ``azimuth = 90 - degrees(theta_array)``, normalised to [0, 180) for an
axial quantity.  ``to_azimuth_deg`` does that and is tested against the Basin-and-Range fabric
recovered independently in ``knowledge/10`` §7 (dominant strike 010-020 degrees).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from gems52_r5 import layers as L

# --------------------------------------------------------------------------------------
# metric arithmetic: what a dot is worth as a function of how well it is localised
# --------------------------------------------------------------------------------------

R_PX = 3.0          # 300 m kernel radius on a 100 m grid, exact


def _kernel(d_px: np.ndarray) -> np.ndarray:
    return np.maximum(1.0 - np.asarray(d_px, dtype=np.float64) / R_PX, 0.0)


def ribbon_credit(lateral_px: float, spacing_px: float = 3.0, n_sub: int = 41) -> dict:
    """Credit a *straight, infinite* trace pays to a row of dots offset ``lateral_px`` from it.

    Dots sit along the trace direction every ``spacing_px`` pixels, at perpendicular offset
    ``lateral_px``.  Two numbers come out, both in the metric's own units:

    ``credit_per_dot``  TPw earned per emitted dot.  ``TPw = sum_g max_x k(d(x,g))``, so a truth
        pixel is credited once at its best covering weight; integrating that along the trace and
        dividing by the number of dots per unit length gives credit per dot.  It reaches 3.0 for a
        perfectly localised, 3-px-spaced dot row and falls to 0 at 3 px of lateral error.
    ``cover_per_dot``   ``max_g k(d(x,g))`` for one dot -- the term that decides whether the dot
        pays false-positive tax.  A dot on the trace pays none; a dot 3 px off pays all of itself.

    ``n_sub`` sub-samples the along-trace offset so the integral is not a lattice artefact.
    """
    if lateral_px < 0 or spacing_px <= 0:
        raise ValueError("lateral_px must be >= 0 and spacing_px > 0")
    a = np.linspace(-spacing_px / 2.0, spacing_px / 2.0, int(n_sub))
    # truth pixels are one per px of trace length; each is covered by the nearest dots
    d = np.hypot(np.asarray(lateral_px, float), a)
    k = _kernel(d)
    # per truth pixel: best cover from either neighbouring dot -> take the max over the two
    # nearest dots, which for a uniform row equals the max over a in [-s/2, s/2]
    per_truth = float(k.max() if k.size else 0.0)
    # integrate k along the trace for one dot's own contribution window of length spacing_px
    credit_per_dot = float(np.trapezoid(k, a) if hasattr(np, "trapezoid") else np.trapz(k, a))
    return dict(lateral_px=float(lateral_px), spacing_px=float(spacing_px),
                credit_per_dot=credit_per_dot,
                per_truth_pixel=per_truth,
                cover_per_dot=float(_kernel(np.asarray([lateral_px]))[0]),
                tax_per_dot=float(1.0 - _kernel(np.asarray([lateral_px]))[0]))


def ribbon_credit_table(spacing_px: float = 3.0) -> list[dict]:
    """The whole lateral-error curve at one spacing, for receipts and for the site's table."""
    return [ribbon_credit(e / 4.0, spacing_px) for e in range(0, 13)]   # 0.00 .. 3.00 px


def expected_credit(p_lateral: np.ndarray, spacing_px: float = 3.0) -> float:
    """Credit per dot for a distribution of lateral errors ``p_lateral`` over 0..3 px bins."""
    p = np.asarray(p_lateral, float)
    if p.shape != (13,):
        raise ValueError("p_lateral must have 13 bins (0.00,0.25,...,3.00 px)")
    if p.min() < 0 or abs(p.sum() - 1.0) > 1e-6:
        raise ValueError("p_lateral must be a nonnegative distribution summing to 1")
    tbl = ribbon_credit_table(spacing_px)
    return float(sum(pi * t["credit_per_dot"] for pi, t in zip(p, tbl)))


def expected_cover(p_lateral: np.ndarray) -> float:
    p = np.asarray(p_lateral, float)
    tbl = ribbon_credit_table()
    return float(sum(pi * t["cover_per_dot"] for pi, t in zip(p, tbl)))


def to_azimuth_deg(theta_array_rad) -> np.ndarray:
    """Array-convention axial angle -> geological azimuth in [0, 180) degrees."""
    az = 90.0 - np.degrees(np.asarray(theta_array_rad, float))
    az = np.mod(az, 180.0)
    return az


# --------------------------------------------------------------------------------------
# per-layer responses
# --------------------------------------------------------------------------------------

def _fill(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """NaN -> the footprint median so filters do not smear holes across a trace."""
    out = np.array(a, np.float32, copy=True)
    if np.isnan(out).any():
        med = float(np.nanmedian(out[valid])) if valid.any() else 0.0
        out[~np.isfinite(out)] = med
    return out


def _shift(a: np.ndarray, dy: int, dx: int, fill: float = -np.inf) -> np.ndarray:
    """Zero-padded (never wrapped) integer shift: out[y, x] = a[y + dy, x + dx]."""
    h, w = a.shape
    out = np.full((h, w), fill, a.dtype)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    if ys1 > ys0 and xs1 > xs0:
        out[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    return out


def structure_tensor(a: np.ndarray, sigma_grad: float = 1.0, sigma_tensor: float = 3.0):
    """Local orientation and coherence of a field, from the smoothed outer product of its gradient.

    Returns ``(theta_perp, coherence)`` where ``theta_perp`` is the array-convention angle of the
    direction of *maximum variation* -- i.e. perpendicular to a linear feature -- and
    ``coherence`` in [0, 1] is ``((l1 - l2) / (l1 + l2))**2``, 1 for a perfectly one-dimensional
    fabric and 0 for isotropic noise.
    """
    gy, gx = np.gradient(a.astype(np.float32))
    s = (sigma_grad, sigma_tensor)
    jxx = ndimage.gaussian_filter(gx * gx, sigma_tensor)
    jyy = ndimage.gaussian_filter(gy * gy, sigma_tensor)
    jxy = ndimage.gaussian_filter(gx * gy, sigma_tensor)
    trace = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(trace * trace / 4.0 - det, 0.0))
    l1 = trace / 2.0 + disc
    l2 = np.maximum(trace / 2.0 - disc, 0.0)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    coh = np.where(trace > 0, ((l1 - l2) / np.maximum(trace, 1e-12)) ** 2, 0.0)
    del gy, gx, jxx, jyy, jxy, trace, det, disc, l1, l2
    return theta.astype(np.float32), coh.astype(np.float32)


def gradient_ridge(a: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """|grad| of a Gaussian-smoothed field: peaks on a step, which is what a scarp or a
    potential-field offset actually is."""
    s = ndimage.gaussian_filter(a.astype(np.float32), sigma)
    gy, gx = np.gradient(s)
    out = np.sqrt(gx * gx + gy * gy)
    del s, gy, gx
    return out.astype(np.float32)


def hessian_line(a: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Largest-magnitude Hessian eigenvalue of a smoothed field, and its eigenvector angle.

    A linear anomaly (a crest over a buried intrusive ridge, a trough over a graben) has one large
    eigenvalue across the line and a near-zero one along it, so ``|lambda_max|`` is a line-energy
    measure and its eigenvector is the across-line direction.  Steps also produce a large
    eigenvalue (bipolar), which is why :func:`gradient_ridge` is computed alongside it and the two
    are combined by rank -- a detector that only had one of the two would systematically sit
    half a pixel off whichever feature type it could not see.
    """
    f = a.astype(np.float32)
    hxx = ndimage.gaussian_filter(f, sigma, order=(0, 2))
    hyy = ndimage.gaussian_filter(f, sigma, order=(2, 0))
    hxy = ndimage.gaussian_filter(f, sigma, order=(1, 1))
    half = 0.5 * (hxx + hyy)
    disc = np.sqrt(np.maximum((0.5 * (hxx - hyy)) ** 2 + hxy * hxy, 0.0))
    lp, lm = half + disc, half - disc
    pick_plus = np.abs(lp) >= np.abs(lm)
    lam = np.where(pick_plus, lp, lm)
    # eigenvector of lam in (x=col, y=row): v = (lam - hyy, hxy), fallback (hxy, lam - hxx)
    vx = np.where(pick_plus, lp - hyy, lm - hyy)
    vy = hxy
    degenerate = (np.abs(vx) + np.abs(vy)) < 1e-12
    vx = np.where(degenerate, hxy, vx)
    vy = np.where(degenerate, np.where(pick_plus, lp - hxx, lm - hxx), vy)
    theta = np.arctan2(vy, vx)         # across-line direction, array convention
    del hxx, hyy, hxy, half, disc, lp, lm, vx, vy, degenerate
    return np.abs(lam).astype(np.float32), theta.astype(np.float32)


# --------------------------------------------------------------------------------------
# thinning
# --------------------------------------------------------------------------------------

# eight compass offsets; the perpendicular direction is quantised onto these for the NMS shift
_DIRS = [(0, 1), (1, 1), (1, 0), (1, -1)]          # the other four are their negatives


def nms_perpendicular(resp: np.ndarray, theta_perp: np.ndarray, tol_deg: float = 22.5):
    """One-pixel thinning by non-maximum suppression along the local across-line direction.

    For every pixel the across-line direction is quantised to one of four axis pairs; the pixel is
    kept only if its response is >= both neighbours along that pair.  Ties are broken by a fixed
    parity rule so the output is deterministic and so a flat plateau cannot survive as a two-pixel
    wide ridge (which would put two dots one pixel apart on the same trace and make them compete
    for the same truth pixels -- the single most expensive mistake this metric allows).
    """
    h, w = resp.shape
    ang = np.mod(np.degrees(theta_perp.astype(np.float64)), 180.0)
    keep = np.zeros((h, w), bool)
    # quantise: direction index d covers [d*45 - tol, d*45 + tol) around 0/45/90/135
    for d, (dy, dx) in enumerate(_DIRS):
        centre = d * 45.0
        lo, hi = centre - tol_deg, centre + tol_deg
        if d == 0:
            sel = (ang < hi) | (ang >= 180.0 + lo)
        else:
            sel = (ang >= lo) & (ang < hi)
        if not sel.any():
            continue
        fwd = _shift(resp, dy, dx)
        bwd = _shift(resp, -dy, -dx)
        r = resp.astype(np.float64)
        ok = sel & (r >= fwd) & (r >= bwd)
        # plateau tie-break: keep only even (row+col) parity among exact equals
        eq = sel & (r == fwd) & (r == bwd)
        if eq.any():
            yy, xx = np.mgrid[0:h, 0:w]
            ok &= ~eq | (((yy + xx) % 2) == 0)
        keep |= ok
    return keep


def local_maxima_radius(resp: np.ndarray, radius_px: int) -> np.ndarray:
    """Strict local maxima in a disc of ``radius_px`` (used to enforce dot spacing)."""
    if radius_px <= 0:
        return resp > -np.inf
    mx = ndimage.maximum_filter(resp, size=2 * radius_px + 1, mode="nearest")
    return resp >= mx


# --------------------------------------------------------------------------------------
# family assembly
# --------------------------------------------------------------------------------------

def layer_response(source: str, band: int, valid: np.ndarray, *, sigma_grad: float = 1.0,
                   sigma_line: float = 2.0, sigma_tensor: float = 3.0,
                   ranks: bool = True) -> dict:
    """Gradient-ridge and Hessian-line response of one raw layer, plus its across-line angle."""
    raw = L.read(source, band, valid=valid)
    f = _fill(raw, valid)
    del raw
    g = gradient_ridge(f, sigma_grad)
    hl, theta_h = hessian_line(f, sigma_line)
    theta_t, coh = structure_tensor(f, sigma_grad, sigma_tensor)
    if ranks:
        g = L.rank_within(g, valid)
        hl = L.rank_within(hl, valid)
    resp = np.maximum(np.nan_to_num(g, nan=0.0), np.nan_to_num(hl, nan=0.0)).astype(np.float32)
    # orientation: prefer the structure tensor (it averages over a neighbourhood, so it is the
    # stable one); where it is incoherent fall back to the Hessian eigenvector
    use_t = coh > 0.25
    theta = np.where(use_t, theta_t, theta_h).astype(np.float32)
    del f, g, hl, theta_t, theta_h, coh, use_t
    return dict(name=f"{source}:{L.band_name(source, band)}", resp=resp, theta=theta)


def family_response(family: str, valid: np.ndarray, cache: dict | None = None,
                    log=print, **kw) -> dict:
    """Max-over-layers response and the winning layer's orientation, for one data family."""
    if family not in L.FAMILIES:
        raise KeyError(f"unknown family {family!r}; have {sorted(L.FAMILIES)}")
    best = np.zeros(valid.shape, np.float32)
    best_theta = np.zeros(valid.shape, np.float32)
    agree = np.zeros(valid.shape, np.int8)
    names = []
    for source, band in L.FAMILIES[family]:
        key = (source, band)
        lr = cache.get(key) if cache is not None else None
        if lr is None:
            lr = layer_response(source, band, valid, **kw)
            if cache is not None:
                cache[key] = lr
        names.append(lr["name"])
        r = np.nan_to_num(lr["resp"], nan=0.0)
        upd = r > best
        best = np.where(upd, r, best)
        best_theta = np.where(upd, lr["theta"], best_theta)
        agree += (r >= 0.98).astype(np.int8)
        log(f"    {family:6s} {lr['name']:24s} done")
    return dict(family=family, resp=best, theta=best_theta, agree=agree, layers=names)


def thinned_trace(fam: dict, valid: np.ndarray, tau: float = 0.90,
                  min_agree: int = 1) -> np.ndarray:
    """One-pixel trace mask for a family: strong response, locally maximal across its own strike,
    and seen by at least ``min_agree`` of the family's own layers."""
    resp = np.where(valid, fam["resp"], -1.0)
    strong = resp >= tau
    if min_agree > 1:
        strong &= fam["agree"] >= min_agree
    if not strong.any():
        return np.zeros(resp.shape, bool)
    keep = nms_perpendicular(resp, fam["theta"])
    return strong & keep


def corroboration(traces: dict[str, np.ndarray], tol_px: int = 1) -> np.ndarray:
    """How many families put a trace within ``tol_px`` of each pixel (0..len(traces))."""
    out = None
    st = np.ones((2 * tol_px + 1, 2 * tol_px + 1), bool) if tol_px > 0 else None
    for name, t in traces.items():
        d = ndimage.binary_dilation(t, structure=st) if tol_px > 0 else t
        out = d.astype(np.int8) if out is None else (out + d.astype(np.int8))
    return out


def strike_map(fams: dict[str, dict], traces: dict[str, np.ndarray]) -> np.ndarray:
    """Array-convention strike (radians, [0, pi)) of the highest-response family at each trace px."""
    shape = next(iter(traces.values())).shape
    best = np.zeros(shape, np.float32)
    out = np.zeros(shape, np.float32)
    for name, t in traces.items():
        r = fams[name]["resp"]
        upd = t & (r > best)
        best = np.where(upd, r, best)
        out = np.where(upd, fams[name]["theta"] + np.pi / 2.0, out)
    return np.mod(out, np.pi).astype(np.float32)
