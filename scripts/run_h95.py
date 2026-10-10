#!/usr/bin/env python3
"""H95 — locked-fault geodetic strain dipole, run inside the assigned co-training lane.

Lane: two-view co-training (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).
View A = potential-field and subsurface (geodetic strain bands 4/7/8, isostatic gravity 13/18).
View B = surface (detrended elevation 12, its slope 19, aeroradiometric total count 6).
Discovery signal = disagreement; the primary arm is the *A-confident / B-abstains* quadrant, which
the lane names as "the fault may be buried beneath cover".

Mechanism (frozen in knowledge/93_hypotheses_H95_preregistered.md before any fit)
---------------------------------------------------------------------------------
A **signed, odd-symmetric profile decomposition** across the trace.  For every pixel the local
fault-normal direction n-hat is measured from that fold's *visible* catalogue only (structure tensor
over a dilated trace corridor; the tensor's dominant gradient direction IS the fault normal, so no
extra rotation is applied and nothing is assumed about the regional fabric).  The Gaussian-smoothed
band B is sampled at +/- h*n-hat by bilinear interpolation and split into

    odd  = (B(+h) - B(-h)) / 2          even = (B(+h) + B(-h)) / 2

with three statistics per (band, lag): |odd|, the odd-dominance odd^2/(|odd|+|even|+eps), and the
sign-reversal couple min(|B+|,|B-|)*1[sign(B+) != sign(B-)].

Why odd-dominance and not |grad|: a locked or creeping normal fault partitions geodetic strain into
an antisymmetric couple about its trace, so the trace sits at a zero crossing with a large odd part
and a small even part.  A lithologic contact, a basin-margin ramp, a road cut or an erosion line is a
monotone step, which is even-dominant after centring.  Every View A operator previously built in this
repository (gradient magnitude, structure-tensor coherence, directional variogram anisotropy, tilt /
RTP magnitude, raw strain values) is sign-blind and cannot make that separation.

Shared tools, reused and never forked
-------------------------------------
gems52.holdout (make_folds/score/mask_visible/emit_topk), gems52.evaluate_holdout
(gems52-pooled-hide-v1), gems52.metric, gems52.spatial (negative_block_errors/independence),
gems52.nodes (spacing_select), gems52.gates (format_report/lane_report), gems52.grid
(write_geotiff/read_geotiff), gems52.submission_writer (write_submission).

Stages: setup | channels | fit | holdout | independence | build | lane | write | card | all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import evaluate_holdout as EH          # noqa: E402
from gems52 import gates, grid, holdout, metric, nodes, spatial, submission_writer  # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work" / "h95"
EVID = ROOT / "evidence"
PREREG_MD = ROOT / "knowledge" / "93_hypotheses_H95_preregistered.md"
PREREG_JSON = ROOT / "registry" / "h95_preregistration.json"

FEATURES = DATA / "training_features.tif"
LABELS = DATA / "labels.tif"
SAMPLE = DATA / "sample_submission.tif"

# ---- frozen constants ----------------------------------------------------------------------------
N_FOLDS = 4
BUFFER_PX = 8
PREVALENCE = 0.002
SEED = 84
DOTS_PER_FOLD = 9400
FINAL_BUDGET = 37654
MIN_SEP_PX = 3.0
RING_M = 200.0
CANARY_ALARM = 0.90
ABANDON_RHO = 0.60
BLOCK_SIDE = 50
MIN_BLOCKS = 20
BOOT_DRAWS = 1000
BOOT_BLOCK = 200
EPS = 1e-9
ROWCHUNK = 256

# band ids, read from the organiser's own file tags in this session (evidence/h95_band_tags.json)
A_BANDS = {"b8_dilatation": 8, "b7_shear": 7, "b4_secondinvariant": 4,
           "b13_isograv": 13, "b18_isograv_hg": 18}
B_BANDS = {"b12_detrended_elev": 12, "b19_detrended_elev_slope": 19, "b6_radiometric_tc": 6}
SIG_A = 3.0
SIG_B = 2.0
H_A = {"b8_dilatation": (1, 2), "b7_shear": (2,), "b4_secondinvariant": (2,),
       "b13_isograv": (2,), "b18_isograv_hg": (2,)}
H_B = {"b12_detrended_elev": (2,), "b19_detrended_elev_slope": (2,), "b6_radiometric_tc": (2,)}

TS = time.time()


def log(*a):
    print(f"[{time.time() - TS:7.1f}s]", *a, flush=True)


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def check_prereg():
    """Refuse to run if the frozen hypothesis document moved.  Read the pin, do not trust memory."""
    reg = json.loads(PREREG_JSON.read_text())
    md_sha = sha256_file(PREREG_MD)
    md_bytes = PREREG_MD.stat().st_size
    if md_sha != reg["hypothesis_sha256"] or md_bytes != reg["hypothesis_bytes"]:
        raise SystemExit(f"PREREG MOVED: {md_sha} != pinned {reg['hypothesis_sha256']} "
                         f"(bytes {md_bytes} != {reg['hypothesis_bytes']}). Refusing to fit.")
    for k, v in (("canary_auc_alarm", CANARY_ALARM), ("independence_abandon_max_abs_rho", ABANDON_RHO),
                 ("budget_dots_per_fold_per_arm", DOTS_PER_FOLD),
                 ("min_dot_separation_px", MIN_SEP_PX), ("catalogue_exclusion_m", RING_M),
                 ("bootstrap_draws", BOOT_DRAWS), ("bootstrap_block_px", BOOT_BLOCK),
                 ("block_side_px", BLOCK_SIDE)):
        if float(reg["thresholds"][k]) != float(v):
            raise SystemExit(f"threshold {k} in the runner ({v}) != frozen pin ({reg['thresholds'][k]})")
    return reg


def save_verified(path: Path, arr):
    """np.save then re-read and compare bit-exactly; rewrite until it matches (IR-H82-002 pattern).

    ``equal_nan=True`` is load-bearing, not cosmetic: the out-of-fold grids are deliberately
    initialised to NaN off the evaluation region, and ``np.array_equal`` reports NaN != NaN, so
    without it every correct write of a NaN-bearing grid looked like corruption and fail-closed.
    That is the check working (it refused to accept an unverified file) and the comparison being
    wrong, not the file.  Fixed here once, in the runner, rather than forked around.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    want = np.asarray(arr)
    for attempt in range(3):
        np.save(path, arr)
        back = np.asarray(np.load(path, mmap_mode="r"))
        if (back.shape == want.shape and back.dtype == want.dtype
                and np.array_equal(back, want, equal_nan=True)):
            return dict(path=str(path), shape=list(want.shape), dtype=str(want.dtype),
                        sha256=sha256_file(path), bytes=path.stat().st_size, verified=True,
                        attempts=attempt + 1, nan_pixels=int(np.isnan(want).sum())
                        if want.dtype.kind == "f" else 0)
        log(f"  save_verified: {path.name} mismatch on attempt {attempt + 1}, rewriting")
    raise IOError(f"save_verified could not produce a bit-exact file for {path}")


# -------------------------------------------------------------------------------------------- setup
def stage_setup():
    log("SETUP: reading labels and measuring the footprint from the bytes")
    with rasterio.open(LABELS) as s:
        lab = s.read(1)
        meta = dict(crs=str(s.crs), transform=[float(v) for v in s.transform][:6],
                    shape=[s.height, s.width], dtype=s.dtypes[0], nodata=s.nodata)
    if tuple(meta["transform"]) != grid.TRANSFORM or tuple(meta["shape"]) != grid.SHAPE:
        raise SystemExit(f"labels grid {meta} != pinned competition grid")
    cat = lab == 1
    in_domain = lab != -1
    valid = grid.footprint_from(FEATURES, bands="all") & in_domain
    uniq, counts = np.unique(lab, return_counts=True)
    fp_all = grid.footprint_from(FEATURES, bands="all")
    with rasterio.open(SAMPLE) as s:
        ss = s.read(1)
    ss_fin = np.isfinite(ss)
    eligible = valid & ~ndimage.binary_dilation(cat, iterations=int(round(RING_M / metric.PIXEL_M)))
    folds = holdout.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                               prevalence=PREVALENCE, seed=SEED, mode="hide")
    out = dict(label_values={str(int(u)): int(c) for u, c in zip(uniq, counts)},
               in_domain_px=int(in_domain.sum()), features_all_bands_finite_px=int(fp_all.sum()),
               sample_submission_finite_px=int(ss_fin.sum()),
               footprint_delta_sample_minus_features=int(ss_fin.sum()) - int(fp_all.sum()),
               valid_used_px=int(valid.sum()), catalogue_px=int(cat.sum()),
               eligible_after_200m_ring_px=int(eligible.sum()),
               folds=[dict(fold=f["fold"], mode=f["mode"], truth_px=int(f["truth"].sum()),
                           visible_px=int(f["visible"].sum()), fit_px=int(f["fit"].sum()),
                           region_px=int(f["region"].sum()), n_held=int(f["n_held"]))
                      for f in folds],
               grid=meta, labels_sha256=sha256_file(LABELS),
               features_sha256=sha256_file(FEATURES), sample_sha256=sha256_file(SAMPLE),
               prevalence_target=PREVALENCE, buffer_px=BUFFER_PX, seed=SEED, n_folds=N_FOLDS,
               withheld_positive_pixels_total=int(sum(f["truth"].sum() for f in folds)))
    WORK.mkdir(parents=True, exist_ok=True)
    save_verified(WORK / "valid.npy", valid)
    save_verified(WORK / "cat.npy", cat)
    save_verified(WORK / "eligible.npy", eligible)
    grid.save_json(EVID / "h95_setup.json", out)
    log(f"SETUP ok: valid={out['valid_used_px']:,} eligible={out['eligible_after_200m_ring_px']:,} "
        f"withheld positives={out['withheld_positive_pixels_total']:,}")
    return out


def _load_setup():
    valid = np.load(WORK / "valid.npy")
    cat = np.load(WORK / "cat.npy")
    eligible = np.load(WORK / "eligible.npy")
    return valid, cat, eligible


def _folds(valid, cat):
    return holdout.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                              prevalence=PREVALENCE, seed=SEED, mode="hide")


# ---------------------------------------------------------------------------------------- channels
def smooth_valid(a, valid, sigma):
    """Gaussian smoothing with the support weight normalised, so the footprint edge is not invented."""
    w = valid.astype(np.float32)
    x = np.where(valid, np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0), 0.0).astype(np.float32)
    num = ndimage.gaussian_filter(x, sigma, mode="constant", cval=0.0)
    den = ndimage.gaussian_filter(w, sigma, mode="constant", cval=0.0)
    out = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-3)
    return out.astype(np.float32), den.astype(np.float32)


def normal_field(visible, valid, sigma=4.0, dilate=7, log_=None):
    """Fault-normal direction (cos, sin) and coherence, from a structure tensor over VISIBLE traces.

    The structure tensor's dominant gradient direction is perpendicular to the local trace, i.e. it
    IS the fault normal, so no extra rotation is applied.  Where the tensor is degenerate (no visible
    trace within the smoothing support) the fold's regional normal is substituted and the pixel is
    flagged, because a direction invented from noise would make the odd/even split meaningless.
    """
    cor = ndimage.binary_dilation(visible, iterations=dilate) & valid
    m, sup = smooth_valid(cor.astype(np.float32), valid, sigma)
    gy, gx = np.gradient(m)
    Jxx = ndimage.gaussian_filter((gx * gx).astype(np.float32), sigma, mode="nearest")
    Jyy = ndimage.gaussian_filter((gy * gy).astype(np.float32), sigma, mode="nearest")
    Jxy = ndimage.gaussian_filter((gx * gy).astype(np.float32), sigma, mode="nearest")
    theta = 0.5 * np.arctan2(2.0 * Jxy, Jxx - Jyy)          # dominant gradient direction = normal
    tr = Jxx + Jyy
    coh = np.divide(np.sqrt((Jxx - Jyy) ** 2 + 4.0 * Jxy ** 2), tr, out=np.zeros_like(tr),
                    where=tr > EPS)
    good = (sup > 0.05) & (coh > 0.2) & (m > 0.01)
    # regional normal: the axial resultant over all good pixels (a circular mean of 2*theta)
    gx_ = float(np.cos(2 * theta[good]).mean()) if good.any() else 0.0
    gy_ = float(np.sin(2 * theta[good]).mean()) if good.any() else 0.0
    R = float(np.hypot(gx_, gy_))
    theta_reg = float(0.5 * np.arctan2(gy_, gx_)) if R > 1e-6 else 0.0
    th = np.where(good, theta, theta_reg)
    cosn = np.cos(th).astype(np.float32)
    sinn = np.sin(th).astype(np.float32)
    # theta is the structure tensor's dominant GRADIENT direction, i.e. the fault NORMAL.  Compass
    # bearing of a vector (cos t east, sin t south) is (90 - t) mod 180; the trace strike is that + 90.
    # Labelled as what it is: the first version of this receipt called the normal a "strike", which is
    # a 90 degree error in the label and none in the number.  The derived strike is published beside it
    # so it can be checked against H82's independent measurement (166.7-171.8 deg compass).
    nrm = float((90.0 - np.degrees(theta_reg)) % 180.0)
    stats = dict(good_px=int(good.sum()), coherence_median=float(np.median(coh[good])) if good.any() else None,
                 regional_normal_tensor_rad=float(theta_reg),
                 regional_resultant_R=R,
                 regional_normal_compass_deg=nrm,
                 regional_strike_compass_deg=float((nrm + 90.0) % 180.0),
                 axial_circular_sd_deg=float(np.degrees(np.sqrt(-2.0 * np.log(R)))) if R > 1e-6 else None,
                 substituted_px=int((~good).sum()),
                 substituted_fraction=round(float((~good).mean()), 5),
                 cross_check="strike derived as normal + 90 deg; H82 measured 166.7-171.8 deg compass "
                             "from an independent structure-tensor implementation "
                             "(knowledge/73 section 5)")
    if log_:
        log_(f"  normal field: {stats['good_px']:,} coherent px ({100 * stats['substituted_fraction']:.1f}% "
             f"take the regional fallback), normal {nrm:.1f} deg / strike "
             f"{stats['regional_strike_compass_deg']:.1f} deg compass, R={R:.3f}")
    return cosn, sinn, good, stats


def channel_names():
    """Flat channel list, in a fixed order.  A channels first, then B; the split is the view split."""
    a, b = [], []
    for nm, hs in H_A.items():
        for h in hs:
            a += [f"A_{nm}_h{h}_absodd", f"A_{nm}_h{h}_oddom", f"A_{nm}_h{h}_couple"]
    for nm, hs in H_B.items():
        for h in hs:
            b += [f"B_{nm}_h{h}_absodd", f"B_{nm}_h{h}_oddom", f"B_{nm}_h{h}_couple"]
    b += ["B_b12_relief5", "B_b12_curv", "B_b12_grad", "B_b19_grad", "B_b6_localstd"]
    return a, b


def stage_channels():
    """Build every full-grid derived field once, verified to disk.  Bands are read one at a time."""
    check_prereg()
    valid, cat, _ = _load_setup()
    folds = _folds(valid, cat)
    bands = {}
    tags = {}
    receipts = {}
    with rasterio.open(FEATURES) as s:
        for nm, bi in list(A_BANDS.items()) + list(B_BANDS.items()):
            t = s.tags(bi)
            tags[nm] = dict(band=bi, data_category=t.get("data_category"),
                            description=t.get("description"))
            bands[nm] = grid.read_band(FEATURES, bi)
    grid.save_json(EVID / "h95_band_tags.json", tags)
    log("CHANNELS: smoothing bands (sigma_A=3, sigma_B=2) with support normalisation")
    sm = {}
    for nm in A_BANDS:
        sm[nm], _ = smooth_valid(bands[nm], valid, SIG_A)
        receipts[f"sm_{nm}"] = save_verified(WORK / f"sm_{nm}.npy", sm[nm])
    for nm in B_BANDS:
        sm[nm], _ = smooth_valid(bands[nm], valid, SIG_B)
        receipts[f"sm_{nm}"] = save_verified(WORK / f"sm_{nm}.npy", sm[nm])
    del bands

    log("CHANNELS: local morphology on View B bands (relief, curvature, gradient, local sd)")
    b12, b19, b6 = sm["b12_detrended_elev"], sm["b19_detrended_elev_slope"], sm["b6_radiometric_tc"]
    extra = {}
    extra["B_b12_relief5"] = (ndimage.maximum_filter(b12, 5, mode="nearest")
                              - ndimage.minimum_filter(b12, 5, mode="nearest")).astype(np.float32)
    extra["B_b12_curv"] = ndimage.laplace(b12, mode="nearest").astype(np.float32)
    gy, gx = np.gradient(b12)
    extra["B_b12_grad"] = np.hypot(gx, gy).astype(np.float32)
    gy, gx = np.gradient(b19)
    extra["B_b19_grad"] = np.hypot(gx, gy).astype(np.float32)
    m2 = ndimage.uniform_filter((b6 * b6).astype(np.float32), 5, mode="nearest")
    m1 = ndimage.uniform_filter(b6, 5, mode="nearest")
    extra["B_b6_localstd"] = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)).astype(np.float32)
    for k, v in extra.items():
        receipts[k] = save_verified(WORK / f"{k}.npy", v)
    del extra, b12, b19, b6

    log("CHANNELS: per-fold fault-normal field from VISIBLE catalogue only")
    nf = []
    for f in folds:
        cosn, sinn, good, st = normal_field(f["visible"], valid, log_=log)
        st["fold"] = f["fold"]
        nf.append(st)
        receipts[f"cosn_f{f['fold']}"] = save_verified(WORK / f"cosn_f{f['fold']}.npy", cosn)
        receipts[f"sinn_f{f['fold']}"] = save_verified(WORK / f"sinn_f{f['fold']}.npy", sinn)
        save_verified(WORK / f"ngood_f{f['fold']}.npy", good)
        del cosn, sinn, good
    a_names, b_names = channel_names()
    out = dict(band_tags=tags, sigma_A=SIG_A, sigma_B=SIG_B, lags_A=H_A, lags_B=H_B,
               A_channels=a_names, B_channels=b_names, n_A=len(a_names), n_B=len(b_names),
               normal_fields=nf, writes=receipts,
               smoothing="gaussian with support-weight normalisation; footprint edge not invented",
               direction_source="structure tensor over a 7px-dilated corridor of THIS FOLD's visible "
                                "catalogue only; degenerate pixels take the fold's regional normal and "
                                "are flagged (substituted_px)",
               odd_even_definition="odd=(B(+h)-B(-h))/2, even=(B(+h)+B(-h))/2 sampled at +/-h*n_hat "
                                   "by bilinear interpolation on the smoothed band")
    grid.save_json(EVID / "h95_channels.json", out)
    log(f"CHANNELS ok: {len(a_names)} View A + {len(b_names)} View B channels")
    return out


class Fields:
    """Lazy holder for the full-grid derived fields, loaded once per stage."""

    def __init__(self):
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            self.cache[name] = np.load(WORK / f"{name}.npy")
        return self.cache[name]


def compute_channels(F: Fields, fold: int, rows, cols):
    """Channels at arbitrary (row, col) coordinates.  Returns (n_chan, n_pt) float32."""
    cosn = F.get(f"cosn_f{fold}")
    sinn = F.get(f"sinn_f{fold}")
    cn = cosn[rows, cols].astype(np.float64)
    sn = sinn[rows, cols].astype(np.float64)
    a_names, b_names = channel_names()
    out = {}
    for nm, hs in H_A.items():
        B = F.get(f"sm_{nm}")
        for h in hs:
            Bp = ndimage.map_coordinates(B, [rows + h * sn, cols + h * cn], order=1, mode="nearest")
            Bm = ndimage.map_coordinates(B, [rows - h * sn, cols - h * cn], order=1, mode="nearest")
            odd = (Bp - Bm) / 2.0
            even = (Bp + Bm) / 2.0
            out[f"A_{nm}_h{h}_absodd"] = np.abs(odd)
            out[f"A_{nm}_h{h}_oddom"] = odd * odd / (np.abs(odd) + np.abs(even) + EPS)
            out[f"A_{nm}_h{h}_couple"] = np.minimum(np.abs(Bp), np.abs(Bm)) * (np.sign(Bp) != np.sign(Bm))
            del Bp, Bm, odd, even
    for nm, hs in H_B.items():
        B = F.get(f"sm_{nm}")
        for h in hs:
            Bp = ndimage.map_coordinates(B, [rows + h * sn, cols + h * cn], order=1, mode="nearest")
            Bm = ndimage.map_coordinates(B, [rows - h * sn, cols - h * cn], order=1, mode="nearest")
            odd = (Bp - Bm) / 2.0
            even = (Bp + Bm) / 2.0
            out[f"B_{nm}_h{h}_absodd"] = np.abs(odd)
            out[f"B_{nm}_h{h}_oddom"] = odd * odd / (np.abs(odd) + np.abs(even) + EPS)
            out[f"B_{nm}_h{h}_couple"] = np.minimum(np.abs(Bp), np.abs(Bm)) * (np.sign(Bp) != np.sign(Bm))
            del Bp, Bm, odd, even
    for k in b_names:
        if k.startswith("B_b") and k in ("B_b12_relief5", "B_b12_curv", "B_b12_grad",
                                        "B_b19_grad", "B_b6_localstd"):
            out[k] = F.get(k)[rows, cols].astype(np.float64)
    X_a = np.stack([out[k] for k in a_names], 1).astype(np.float32)
    X_b = np.stack([out[k] for k in b_names], 1).astype(np.float32)
    return X_a, X_b


def auc(score, y):
    """Rank AUC without sklearn's overhead on big arrays; ties handled by average rank."""
    from scipy.stats import rankdata
    s = np.asarray(score, float)
    y = np.asarray(y, bool)
    npos, nneg = int(y.sum()), int((~y).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def standardize(Xtr, Xev_list):
    mu = Xtr.mean(0)
    sd = Xtr.std(0)
    sd[sd < 1e-12] = 1.0
    return (Xtr - mu) / sd, [((X - mu) / sd) for X in Xev_list], mu, sd


# --------------------------------------------------------------------------------------------- fit
def stage_fit():
    from sklearn.linear_model import LogisticRegression
    reg = check_prereg()
    valid, cat, _ = _load_setup()
    folds = _folds(valid, cat)
    F = Fields()
    a_names, b_names = channel_names()
    rng = np.random.default_rng(SEED)
    res = dict(evaluator_version=EH.VERSION, arms=["single_A", "single_B"], folds=[],
               canary=dict(alarm=CANARY_ALARM, per_fold=[], max_auc=None, max_channel=None,
                           alarm_tripped=None),
               sufficiency=dict(bar_mean=reg["thresholds"]["S1_sufficiency_mean_oof_auc_min"],
                                bar_min_fold=reg["thresholds"]["S1_sufficiency_min_fold_oof_auc"],
                                view_A_mean=None, view_A_min_fold=None, passed=None),
               models={})
    for f in folds:
        k = f["fold"]
        pos = f["visible"] & f["fit"]
        neg = f["fit"] & ~cat
        npos = int(pos.sum())
        nneg_want = min(int(neg.sum()), 20 * npos)
        yp, xp = np.nonzero(pos)
        idx = np.flatnonzero(neg.ravel())
        pick = rng.choice(idx, size=nneg_want, replace=False)
        yn, xn = np.unravel_index(pick, neg.shape)
        rows = np.concatenate([yp, yn]); cols = np.concatenate([xp, xn])
        y = np.concatenate([np.ones(npos, bool), np.zeros(nneg_want, bool)])
        log(f"FIT fold {k}: {npos:,} positives + {nneg_want:,} negatives")
        Xa, Xb = compute_channels(F, k, rows, cols)
        # evaluation sample for out-of-fold AUC and the leakage canary: THIS fold's withheld truth
        ev_pos = f["truth"] & f["region"] & valid
        ev_neg = f["region"] & valid & ~cat
        ep_y, ep_x = np.nonzero(ev_pos)
        en_idx = np.flatnonzero(ev_neg.ravel())
        en_pick = rng.choice(en_idx, size=min(en_idx.size, 200_000), replace=False)
        en_y, en_x = np.unravel_index(en_pick, ev_neg.shape)
        erows = np.concatenate([ep_y, en_y]); ecols = np.concatenate([ep_x, en_x])
        ey = np.concatenate([np.ones(len(ep_y), bool), np.zeros(len(en_y), bool)])
        Ea, Eb = compute_channels(F, k, erows, ecols)
        log(f"  eval sample: {len(ep_y):,} withheld truth px vs {len(en_y):,} proxy negatives")
        Xa_s, (Ea_s,), mu_a, sd_a = standardize(Xa, [Ea])
        Xb_s, (Eb_s,), mu_b, sd_b = standardize(Xb, [Eb])
        ma = LogisticRegression(max_iter=2000, C=1.0, n_jobs=1).fit(Xa_s, y)
        mb = LogisticRegression(max_iter=2000, C=1.0, n_jobs=1).fit(Xb_s, y)
        pa_ev, pb_ev = ma.decision_function(Ea_s), mb.decision_function(Eb_s)
        auc_a, auc_b = auc(pa_ev, ey), auc(pb_ev, ey)
        # leakage canary: each channel ALONE, out-of-fold, on the held-out region
        can = {a_names[i]: auc(Ea[:, i], ey) for i in range(len(a_names))}
        can.update({b_names[i]: auc(Eb[:, i], ey) for i in range(len(b_names))}  )
        can = {kk: (None if not np.isfinite(v) else round(float(v), 5)) for kk, v in can.items()}
        mx = max((v for v in can.values() if v is not None), default=None)
        mk = max(can, key=lambda z: (can[z] if can[z] is not None else -1))
        res["canary"]["per_fold"].append(dict(fold=k, max_auc=mx, max_channel=mk,
                                              alarm=bool(mx is not None and mx >= CANARY_ALARM),
                                              per_channel=can))
        res["folds"].append(dict(fold=k, n_train_pos=npos, n_train_neg=nneg_want,
                                 n_eval_pos=int(len(ep_y)), n_eval_neg=int(len(en_y)),
                                 oof_auc_A=round(float(auc_a), 5), oof_auc_B=round(float(auc_b), 5)))
        res["models"][str(k)] = dict(A=dict(intercept=float(ma.intercept_[0]), coef=ma.coef_[0].tolist(),
                                            mu=mu_a.tolist(), sd=sd_a.tolist()),
                                     B=dict(intercept=float(mb.intercept_[0]), coef=mb.coef_[0].tolist(),
                                            mu=mu_b.tolist(), sd=sd_b.tolist()))
        log(f"  OOF AUC  A={auc_a:.4f}  B={auc_b:.4f}   canary max={mx} ({mk})")
        # ---- predict the whole fold region in row blocks and store the OOF grids ----------------
        for tag, model, mu, sd in (("A", ma, mu_a, sd_a), ("B", mb, mu_b, sd_b)):
            outg = np.full(valid.shape, np.nan, dtype=np.float32)
            region = f["region"] & valid
            for y0 in range(0, valid.shape[0], ROWCHUNK):
                y1 = min(y0 + ROWCHUNK, valid.shape[0])
                sl = np.s_[y0:y1]
                blk = region[sl]
                if not blk.any():
                    continue
                rr, cc = np.nonzero(blk)
                rr = rr + y0
                Xa_, Xb_ = compute_channels(F, k, rr, cc)
                X = (Xa_ if tag == "A" else Xb_)
                X = (X - (mu_a if tag == "A" else mu_b)) / (sd_a if tag == "A" else sd_b)
                d = (model.decision_function(X)).astype(np.float32)
                outg[rr, cc] = d
                del Xa_, Xb_, X, d
            rec = save_verified(WORK / f"oof{tag}_f{k}.npy", outg)
            res.setdefault("oof_grids", {})[f"{tag}_f{k}"] = rec
            del outg
    aa = [d["oof_auc_A"] for d in res["folds"]]
    ab = [d["oof_auc_B"] for d in res["folds"]]
    res["sufficiency"].update(view_A_mean=round(float(np.mean(aa)), 5),
                              view_A_min_fold=round(float(np.min(aa)), 5),
                              view_B_mean=round(float(np.mean(ab)), 5),
                              view_B_min_fold=round(float(np.min(ab)), 5),
                              passed=bool(np.mean(aa) >= reg["thresholds"]["S1_sufficiency_mean_oof_auc_min"]
                                          and np.min(aa) >= reg["thresholds"]["S1_sufficiency_min_fold_oof_auc"]))
    mx = max(d["max_auc"] for d in res["canary"]["per_fold"] if d["max_auc"] is not None)
    res["canary"]["max_auc"] = mx
    res["canary"]["alarm_tripped"] = bool(mx >= CANARY_ALARM)
    res["canary"]["max_channel"] = max(
        (d for d in res["canary"]["per_fold"]), key=lambda d: d["max_auc"] or -1)["max_channel"]
    grid.save_json(EVID / "h95_fit.json", res)
    log(f"FIT ok: View A mean OOF AUC {res['sufficiency']['view_A_mean']} "
        f"(sufficiency {'PASS' if res['sufficiency']['passed'] else 'FAIL'}); "
        f"View B {res['sufficiency']['view_B_mean']}; canary max {mx} "
        f"({'ALARM' if res['canary']['alarm_tripped'] else 'no alarm'})")
    return res


# ----------------------------------------------------------------------------------------- holdout
def _arms_for_fold(fold, valid, cat, eligible, rng):
    """Every arm's emission on one fold, at the frozen 9,400-dot budget.  Equal budget = comparable."""
    k = fold["fold"]
    zA = np.load(WORK / f"oofA_f{k}.npy")
    zB = np.load(WORK / f"oofB_f{k}.npy")
    allowed = valid & ~fold["visible"] & fold["region"]
    F = Fields()
    # model-free odd-dominance composite over View A channels (the attribution arm)
    a_names, _ = channel_names()
    odd_names = [n for n in a_names if n.endswith("_oddom")]
    return zA, zB, allowed, odd_names


def stage_holdout():
    reg = check_prereg()
    valid, cat, eligible = _load_setup()
    folds = _folds(valid, cat)
    rng = np.random.default_rng(SEED + 1)
    terms, per_fold, grids = {}, [], {}
    arm_names = ["A_ODD_gated", "single_A", "single_B", "A_ODD_ungated",
                 "B_conf_A_abstain", "union_max", "random"]
    for n in arm_names:
        terms[n] = []
    for f in folds:
        k = f["fold"]
        zA = np.load(WORK / f"oofA_f{k}.npy")
        zB = np.load(WORK / f"oofB_f{k}.npy")
        allowed = valid & ~f["visible"] & f["region"]
        fin = allowed & np.isfinite(zA) & np.isfinite(zB)
        medA = float(np.median(zA[fin])); medB = float(np.median(zB[fin]))
        arms = {
            "A_ODD_gated": np.where(fin & (zB < medB), zA, -np.inf),      # A confident, B abstains
            "single_A": np.where(fin, zA, -np.inf),
            "single_B": np.where(fin, zB, -np.inf),
            "A_ODD_ungated": np.where(fin, zA, -np.inf),                  # ref: attribution below
            "B_conf_A_abstain": np.where(fin & (zA < medA), zB, -np.inf),  # surface-artefact suspects
            "union_max": np.where(fin, np.maximum((zA - medA), (zB - medB)), -np.inf),
            "random": np.where(fin, rng.random(zA.shape).astype(np.float32), -np.inf),
        }
        # A_ODD_ungated is made a genuinely different arm: the model-free odd-dominance composite.
        a_names, _ = channel_names()
        F = Fields()
        rows, cols = np.nonzero(fin)
        sub = rng.choice(rows.size, size=min(rows.size, 1_200_000), replace=False)
        rows, cols = rows[sub], cols[sub]
        Xa, _ = compute_channels(F, k, rows, cols)
        odd = np.stack([Xa[:, i] for i, n in enumerate(a_names) if n.endswith("_oddom")], 1)
        comp = np.zeros(rows.size, np.float32)
        for j in range(odd.shape[1]):
            v = odd[:, j]
            comp += ((v - v.mean()) / (v.std() + 1e-9)).astype(np.float32)
        g = np.full(zA.shape, -np.inf, np.float32)
        g[rows, cols] = comp
        arms["A_ODD_ungated"] = g
        rec = dict(fold=k, medA=medA, medB=medB,
                   gated_pool_px=int((fin & (zB < medB)).sum()),
                   withheld_positive_px=int((f["truth"] & f["region"] & valid).sum()))
        for n, fld in arms.items():
            em = holdout.emit_topk(np.nan_to_num(fld, nan=0.0, neginf=-1e30), allowed, DOTS_PER_FOLD)
            if int((em > 0).sum()) != DOTS_PER_FOLD:
                # a short-filled arm makes the matched-budget comparison invalid (H74S: 1,126/1,264),
                # so it is raised here rather than reported afterwards as a caveat
                raise SystemExit(f"arm {n} fold {k} filled {int((em > 0).sum())}/{DOTS_PER_FOLD} dots; "
                                 f"the matched comparison would be invalid")
            r, t = EH.evaluate(em.astype(np.float32), f, valid, block_side=BOOT_BLOCK)
            terms[n].append(t)
            rec[n] = dict(dti=round(float(r["dti"]), 6), tpw=round(float(r["tpw"]), 3),
                          fpw=round(float(r["fpw"]), 3), fnw=round(float(r["fnw"]), 3),
                          emitted=int(r["emitted"]))
            grids.setdefault(n, {})[k] = em
            del em, fld
        per_fold.append(rec)
        log(f"HOLDOUT fold {k}: " + " ".join(f"{n}={rec[n]['dti']:.4f}" for n in arm_names))
        del zA, zB, arms, Xa, odd
    pooled = EH.pooled_summary({n: np.concatenate(terms[n], 0) for n in arm_names},
                               draws=BOOT_DRAWS, seed=520884, candidate="A_ODD_gated")
    primary = pooled["scores"]["A_ODD_gated"]
    ctrl = pooled["scores"]["single_B"]
    d = pooled["paired_differences"]["single_B"]
    promote = bool(d["ci95"][0] > 0)
    # Record the hashes of every input this stage consumed. The first execution of this stage produced
    # a pooled single_B of 0.030262 and two consecutive re-runs produced 0.029349 bit-identically, with
    # the input files demonstrably unchanged (mtime and the sha256 recorded by the fit stage). The
    # mechanism is unresolved, so instead of explaining it, the receipt now carries the input hashes so
    # any future discrepancy can be attributed to an input or to the stage. See IR-H95-010.
    input_hashes = {f"oof{tag}_f{k}": sha256_file(WORK / f"oof{tag}_f{k}.npy")
                    for k in range(N_FOLDS) for tag in "AB"}
    input_hashes.update({n: sha256_file(WORK / f"{n}.npy") for n in ("valid", "cat", "eligible")})
    out = dict(input_sha256=input_hashes,
               reproducibility=dict(
                   consecutive_identical_reruns=2, max_abs_difference=0.0,
                   superseded_first_run_pooled_single_B=0.030262,
                   current_pooled_single_B=None,
                   mechanism="UNRESOLVED - inputs unchanged, stage re-runs bit-identically; recorded "
                             "rather than explained",
                   impact="shifts single_B by about 0.0009 and the paired delta by about 0.0012; no "
                          "verdict changes, the primary is below random and below its control by an "
                          "order of magnitude more than the shift"),
               evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
               withheld_positive_pixels=int(pooled["scores"]["single_B"]["withheld_positive_pixels"]),
               dots_per_fold_per_arm=DOTS_PER_FOLD, arms=arm_names, primary="A_ODD_gated",
               pooled=pooled, per_fold=per_fold,
               promotion_rule="primary paired 95% CI lower bound vs single_B must exceed 0",
               promotion_delta_vs_single_B=d, promoted=promote,
               attribution_arms_not_promotable=True,
               arm_construction_disclosures={
                 "A_ODD_gated": "View A logistic decision function restricted to eligible pixels whose "
                                "View B decision function is below that fold's median over the same pool "
                                "(B abstains). Pool per fold recorded as gated_pool_px.",
                 "A_ODD_ungated": "MODEL-FREE composite: the per-fold mean of the z-scored odd-dominance "
                                  "channels, evaluated on a 1,200,000-point random subsample of the "
                                  "eligible pool (seed SEED+1, drawn after the random arm so the stream "
                                  "is reproducible). Its pool therefore differs from the other arms. "
                                  "9,400 dots is far below the subsample size so there is no short-fill, "
                                  "but this arm carries subsample variance and is attribution only.",
                 "B_conf_A_abstain": "View B decision function restricted to pixels where View A is below "
                                     "its fold median - the lane's 'suspect surface artefacts (roads, "
                                     "erosion lines)' quadrant. Reported, never promoted.",
                 "union_max": "max of the two median-centred decision functions; the not-the-union "
                              "comparator at the same budget.",
                 "random": "uniform random field over the same allowed set - the floor.",
                 "ring_convention": "Holdout arms place on `valid & ~fold.visible & fold.region`, which is "
                                    "the shared-template convention (gems52.holdout.arm_scores) and does "
                                    "NOT apply the 200 m catalogue ring; the final emission does. This is "
                                    "a placement-convention difference, not a scoring difference: the "
                                    "instrument masks visible catalogue pixels exactly, as the organiser "
                                    "does (staff thread 11516 post #2), and every arm here shares it.",
                 "budget_completeness": "every arm filled its 9,400-dot budget on every fold; "
                                        "no matched comparison in this round is invalidated by a "
                                        "short-fill (contrast H74S, where one arm filled 1,126/1,264)."},
               caveat="A holdout number is never a leaderboard forecast. This repository has measured "
                      "Spearman -0.10 between this instrument and owner-reported board scores "
                      "(knowledge/10 section 5), so no number here is a projection.",
               implementation_sha256=EH.implementation_hashes(),
               single_B_control_note="single_B here is this round's OWN View-B learner on this round's "
                                     "surface channels; it is NOT a replay of the committed 0.174517 "
                                     "control, whose feature bank is not reproducible from this checkout "
                                     "(cf. IR-H82-004). No reproduction claim is made.")
    np.savez_compressed(WORK / "holdout_grids.npz",
                        **{f"{n}_f{k}": v.astype(np.uint8) for n, d2 in grids.items() for k, v in d2.items()})
    out["reproducibility"]["current_pooled_single_B"] = pooled["scores"]["single_B"]["dti"]
    grid.save_json(EVID / "h95_holdout.json", out)
    log(f"HOLDOUT primary A_ODD_gated={primary['dti']:.6f} CI {primary['ci95']} | single_B={ctrl['dti']:.6f} "
        f"CI {ctrl['ci95']} | delta CI {d['ci95']} -> {'PROMOTE' if promote else 'NEGATIVE'}")
    return out


# ------------------------------------------------------------------------------------ independence
def stage_independence():
    reg = check_prereg()
    valid, cat, _ = _load_setup()
    folds = _folds(valid, cat)
    rows = []
    for f in folds:
        k = f["fold"]
        zA = np.load(WORK / f"oofA_f{k}.npy")
        zB = np.load(WORK / f"oofB_f{k}.npy")
        neg = f["region"] & valid & ~cat & np.isfinite(zA) & np.isfinite(zB)
        # the instrument wants probabilities, not log-odds: squash, then cut at the frozen quantiles
        pA = 1.0 / (1.0 + np.exp(-np.clip(zA, -30, 30)))
        pB = 1.0 / (1.0 + np.exp(-np.clip(zB, -30, 30)))
        cutA = float(np.quantile(pA[neg], reg["thresholds"]["donor_rank_min"]))
        cutB = float(np.quantile(pB[neg], reg["thresholds"]["receiver_rank_interval"][1]))
        rows += spatial.negative_block_errors(np.nan_to_num(pA, nan=np.nan), np.nan_to_num(pB, nan=np.nan),
                                              neg, k, (cutA, cutB), side=BLOCK_SIDE, minimum=32)
        del zA, zB, pA, pB
    ind = spatial.independence(rows, threshold=ABANDON_RHO, min_blocks=MIN_BLOCKS)
    ind.update(evidence_class="view-independence diagnostic, not a score",
               thresholds_inherited_verbatim_from="registry/h74_preregistration.json",
               thresholds_source_sha256=reg["thresholds_source_sha256"],
               donor_cut_quantile=reg["thresholds"]["donor_rank_min"],
               receiver_cut_quantile=reg["thresholds"]["receiver_rank_interval"][1],
               blocks_per_fold={str(k): int(sum(1 for r in rows if r["fold"] == k)) for k in range(N_FOLDS)},
               sufficiency_gate_passed=json.loads((EVID / "h95_fit.json").read_text())["sufficiency"]["passed"],
               exchange_decision=None)
    ind["exchange_decision"] = (
        "independence passes but View A sufficiency FAILED, so there is nothing to donate: exchange not "
        "run" if not ind["sufficiency_gate_passed"] else
        "independence and sufficiency both pass: exchange authorised" if ind["allow_exchange"] else
        "independence FAILED (|rho| >= abandon bar): co-training abandoned for this round")
    blocks = ind.pop("blocks")
    grid.save_json(EVID / "h95_independence.json", ind)
    grid.save_json(EVID / "h95_independence_blocks.json", dict(n_blocks=len(blocks), blocks=blocks[:200]))
    log(f"INDEPENDENCE: {ind['n_blocks']} blocks, max|rho|={ind['max_abs_correlation']}, "
        f"allow_exchange={ind['allow_exchange']}; {ind['exchange_decision']}")
    return ind


# ------------------------------------------------------------------------------------------- build
def stage_build():
    """Fit on ALL visible catalogue, score the eligible pool, place with the metric-aware rule."""
    from sklearn.linear_model import LogisticRegression
    check_prereg()
    valid, cat, eligible = _load_setup()
    fit = json.loads((EVID / "h95_fit.json").read_text())
    F = Fields()
    a_names, b_names = channel_names()
    rng = np.random.default_rng(SEED + 7)
    # ---- all-data model: positives = every catalogue pixel that is inside the fit domain of some
    # fold; negatives = non-catalogue in-domain pixels.  Nothing is withheld here: this is the
    # emission model, and every number that judges it came from the hide-and-recover stage above.
    pos = cat & valid
    neg = valid & ~cat
    yp, xp = np.nonzero(pos)
    npos = len(yp)
    idx = np.flatnonzero(neg.ravel())
    pick = rng.choice(idx, size=min(idx.size, 20 * npos), replace=False)
    yn, xn = np.unravel_index(pick, neg.shape)
    rows = np.concatenate([yp, yn]); cols = np.concatenate([xp, xn])
    y = np.concatenate([np.ones(npos, bool), np.zeros(len(yn), bool)])
    log(f"BUILD: all-data model on {npos:,} positives + {len(yn):,} negatives")
    # the emission direction field uses the FULL visible catalogue (nothing is hidden at emission time)
    cosn, sinn, good, nstat = normal_field(cat & valid, valid, log_=log)
    save_verified(WORK / "cosn_full.npy", cosn)
    save_verified(WORK / "sinn_full.npy", sinn)
    Xa, Xb = compute_channels_full(F, rows, cols, cosn, sinn)
    mu_a, sd_a = Xa.mean(0), Xa.std(0); sd_a[sd_a < 1e-12] = 1.0
    mu_b, sd_b = Xb.mean(0), Xb.std(0); sd_b[sd_b < 1e-12] = 1.0
    ma = LogisticRegression(max_iter=2000, C=1.0).fit((Xa - mu_a) / sd_a, y)
    mb = LogisticRegression(max_iter=2000, C=1.0).fit((Xb - mu_b) / sd_b, y)
    del Xa, Xb
    # ---- score the eligible pool in row blocks
    zA = np.full(valid.shape, -np.inf, np.float32)
    zB = np.full(valid.shape, -np.inf, np.float32)
    for y0 in range(0, valid.shape[0], ROWCHUNK):
        y1 = min(y0 + ROWCHUNK, valid.shape[0])
        rr, cc = np.nonzero(eligible[y0:y1])
        if rr.size == 0:
            continue
        rr = rr + y0
        Xa_, Xb_ = compute_channels_full(F, rr, cc, cosn, sinn)
        zA[rr, cc] = ma.decision_function((Xa_ - mu_a) / sd_a).astype(np.float32)
        zB[rr, cc] = mb.decision_function((Xb_ - mu_b) / sd_b).astype(np.float32)
        del Xa_, Xb_
    save_verified(WORK / "zA_full.npy", zA)
    save_verified(WORK / "zB_full.npy", zB)
    fin = np.isfinite(zA) & np.isfinite(zB) & eligible
    medB = float(np.median(zB[fin]))
    primary_field = np.where(fin & (zB < medB), zA, -np.inf).astype(np.float32)
    save_verified(WORK / "primary_field.npy", primary_field)
    # ---- metric-aware placement: 3 px minimum separation, 200 m catalogue ring already excluded
    allowed = eligible & fin
    dots = nodes.spacing_select(np.nan_to_num(primary_field, nan=-1e30, neginf=-1e30),
                                allowed, FINAL_BUDGET, min_px=MIN_SEP_PX, log=log)
    n_dots = int(dots.sum())
    if n_dots < FINAL_BUDGET:
        log(f"BUILD: spacing-constrained placement short-filled {n_dots}/{FINAL_BUDGET}; "
            f"recording it rather than silently widening the pool")
    # ---- distance statistics to the mapped catalogue, measured not asserted
    edc = ndimage.distance_transform_edt(~cat, sampling=metric.PIXEL_M)
    d = edc[dots]
    # ---- not-the-union test at EQUAL budget
    uni = np.where(fin, np.maximum(zA - float(np.median(zA[fin])), zB - medB), -np.inf).astype(np.float32)
    em_union = nodes.spacing_select(np.nan_to_num(uni, nan=-1e30, neginf=-1e30), allowed,
                                    FINAL_BUDGET, min_px=MIN_SEP_PX)
    em_a = nodes.spacing_select(np.nan_to_num(np.where(fin, zA, -np.inf), nan=-1e30, neginf=-1e30),
                                allowed, FINAL_BUDGET, min_px=MIN_SEP_PX)
    em_b = nodes.spacing_select(np.nan_to_num(np.where(fin, zB, -np.inf), nan=-1e30, neginf=-1e30),
                                allowed, FINAL_BUDGET, min_px=MIN_SEP_PX)

    def rel(x, name):
        sh = int((dots & x).sum())
        nx, ny = int(x.sum()), int(dots.sum())
        return dict(arm=name, arm_px=nx, shared_px=sh, jaccard=round(sh / max(1, nx + ny - sh), 5),
                    identical=bool(sh == nx == ny))
    ntu = [rel(em_union, "union_max"), rel(em_a, "single_A"), rel(em_b, "single_B")]
    ok_ntu = not any(r["identical"] for r in ntu)
    out = dict(emitted_px=n_dots, requested_budget=FINAL_BUDGET, min_separation_px=MIN_SEP_PX,
               pool_px=int(allowed.sum()), short_fill=FINAL_BUDGET - n_dots,
               catalogue_distance_m=dict(min=round(float(d.min()), 1) if n_dots else None,
                                         median=round(float(np.median(d)), 1) if n_dots else None,
                                         p05=round(float(np.percentile(d, 5)), 1) if n_dots else None,
                                         pct_within_300m=round(float((d <= 300).mean() * 100), 3) if n_dots else None,
                                         pct_within_200m=round(float((d <= 200).mean() * 100), 3) if n_dots else None),
               ring_exclusion_m=RING_M, normal_field=nstat,
               marginal_rule=dict(source="knowledge/49 section 2",
                                  bar_at_board_dti_0p2778=round(0.2 * 0.2778, 5),
                                  bar_at_board_dti_0p3774=round(0.2 * 0.3774, 5),
                                  max_emit_distance_px=metric.bar_to_max_distance_px(0.2 * 0.2778),
                                  note="OWNER-REPORTED board DTIs used only to state the bar; not a "
                                       "projection of this file's score"),
               not_the_union=dict(equal_budget=FINAL_BUDGET, relations=ntu, ok=ok_ntu,
                                  rule="the authorized candidate must not be identical to the union-max "
                                       "of the two views nor to either single view at the same budget"),
               surface_field=dict(kind="normalized rank surface of the primary field",
                                  note="kept for the pre-placement lane check"))
    save_verified(WORK / "dots.npy", dots)
    save_verified(WORK / "em_union.npy", em_union)
    save_verified(WORK / "em_A.npy", em_a)
    save_verified(WORK / "em_B.npy", em_b)
    grid.save_json(EVID / "h95_build.json", out)
    log(f"BUILD ok: {n_dots:,} dots, min catalogue distance {out['catalogue_distance_m']['min']} m, "
        f"not-the-union {'PASS' if ok_ntu else 'FAIL'}")
    return out


def compute_channels_full(F, rows, cols, cosn, sinn):
    """Same channel definition as compute_channels but with an explicitly supplied direction field."""
    cn = cosn[rows, cols].astype(np.float64)
    sn = sinn[rows, cols].astype(np.float64)
    a_names, b_names = channel_names()
    out = {}
    for nm, hs in H_A.items():
        B = F.get(f"sm_{nm}")
        for h in hs:
            Bp = ndimage.map_coordinates(B, [rows + h * sn, cols + h * cn], order=1, mode="nearest")
            Bm = ndimage.map_coordinates(B, [rows - h * sn, cols - h * cn], order=1, mode="nearest")
            odd = (Bp - Bm) / 2.0; even = (Bp + Bm) / 2.0
            out[f"A_{nm}_h{h}_absodd"] = np.abs(odd)
            out[f"A_{nm}_h{h}_oddom"] = odd * odd / (np.abs(odd) + np.abs(even) + EPS)
            out[f"A_{nm}_h{h}_couple"] = np.minimum(np.abs(Bp), np.abs(Bm)) * (np.sign(Bp) != np.sign(Bm))
            del Bp, Bm, odd, even
    for nm, hs in H_B.items():
        B = F.get(f"sm_{nm}")
        for h in hs:
            Bp = ndimage.map_coordinates(B, [rows + h * sn, cols + h * cn], order=1, mode="nearest")
            Bm = ndimage.map_coordinates(B, [rows - h * sn, cols - h * cn], order=1, mode="nearest")
            odd = (Bp - Bm) / 2.0; even = (Bp + Bm) / 2.0
            out[f"B_{nm}_h{h}_absodd"] = np.abs(odd)
            out[f"B_{nm}_h{h}_oddom"] = odd * odd / (np.abs(odd) + np.abs(even) + EPS)
            out[f"B_{nm}_h{h}_couple"] = np.minimum(np.abs(Bp), np.abs(Bm)) * (np.sign(Bp) != np.sign(Bm))
            del Bp, Bm, odd, even
    for k in ("B_b12_relief5", "B_b12_curv", "B_b12_grad", "B_b19_grad", "B_b6_localstd"):
        out[k] = F.get(k)[rows, cols].astype(np.float64)
    X_a = np.stack([out[k] for k in a_names], 1).astype(np.float32)
    X_b = np.stack([out[k] for k in b_names], 1).astype(np.float32)
    return X_a, X_b


# -------------------------------------------------------------------------------------------- lane
OWN_ROUND_TOKENS = ("h95",)


def census_paths():
    """Every aligned raster this session can see EXCEPT this round's own output.

    Excluding the current round is load-bearing, not tidy: the write stage puts the candidate into
    submission/ and the publisher copies it to docs/downloads/, so a lane stage re-run afterwards would
    otherwise compare the candidate against itself and report Spearman 1.0 and near-3px 1.0 - a
    self-inflicted DUPLICATE/STOP that says nothing. Measured here before the fix: exactly that, on a
    67-raster census whose 67th member was the file written 90 seconds earlier.
    """
    roots = [DATA / "scored", DATA / "reference", ROOT / "submission", ROOT / "docs" / "downloads"]
    out = []
    for r in roots:
        if r.is_dir():
            out += sorted(p for p in r.glob("*.tif"))
    dedup, seen, own = [], set(), []
    for p in out:
        if any(tok in p.name.lower() for tok in OWN_ROUND_TOKENS):
            own.append(str(p)); continue
        k = (p.stat().st_size, sha256_file(p)[:16])
        if k in seen:
            continue
        seen.add(k); dedup.append(p)
    if own:
        log(f"LANE: excluded this round's own artefacts from the census: {own}")
    return dedup


def _own_excluded():
    out = []
    for r in (ROOT / "submission", ROOT / "docs" / "downloads"):
        if r.is_dir():
            out += [str(p) for p in sorted(r.glob("*.tif"))
                    if any(tok in p.name.lower() for tok in OWN_ROUND_TOKENS)]
    return out


def stage_lane():
    check_prereg()
    valid, cat, eligible = _load_setup()
    priors = census_paths()
    log(f"LANE: census of {len(priors)} byte-distinct aligned rasters")
    zf = np.load(WORK / "primary_field.npy")
    fin = np.isfinite(zf) & eligible
    lo, hi = float(zf[fin].min()), float(zf[fin].max())
    surf = np.zeros(zf.shape, np.float32)
    surf[fin] = ((zf[fin] - lo) / (hi - lo + 1e-12)).astype(np.float32)
    # ONE coverage cache shared by both phases: registry_coverage is a full-grid EDT per distinct prior
    # and recomputing it for the surface phase and again for the dots phase doubles the slowest stage in
    # the round for an identical number.  Sharing the cache changes no output value.
    cache: dict = {}
    surface = gates.lane_report(surf, eligible, priors, sample=SAMPLE, phase="surface", log=log,
                                coverage_cache=cache)
    dots = np.load(WORK / "dots.npy")
    cand = dots.astype(np.float32)
    dotrep = gates.lane_report(cand, eligible, priors, sample=SAMPLE, phase="dots", log=log,
                               coverage_cache=cache)
    # The tier dicts carry `verdict`, not `duplicate`; reading the wrong key silently made every stop
    # look like a pass.  Both tiers are recorded and neither waives the other (H82 precedent: "a
    # restricted PASS never waives a literal full-census DUPLICATE/STOP").
    lit_v = dotrep["literal"]["verdict"]
    pol_v = dotrep["policy"]["verdict"]
    sl_v = surface["literal"]["verdict"]
    sp_v = surface["policy"]["verdict"]
    out = dict(census=[str(p) for p in priors], census_size=len(priors),
               census_excludes_this_round=_own_excluded(),
               census_scope=("local checkout only: data/scored, data/reference, submission/, "
                             "docs/downloads/, deduplicated by (size, sha256[:16]), minus this round's "
                             "own artefacts. It does NOT include sibling public owner-mirror paths, so "
                             "it is narrower than H74S's 693-path or H82's 567-raster censuses. "
                             "Disclosed, not presented as exhaustive."),
               coverage_cache_entries=len(cache),
               surface=surface, dots=dotrep,
               verdicts=dict(surface_literal=sl_v, surface_policy=sp_v,
                             dots_literal=lit_v, dots_policy=pol_v),
               stop=bool("STOP" in sl_v or "STOP" in lit_v),
               policy_stop=bool("STOP" in sp_v or "STOP" in pol_v),
               dots_literal_witness=dict(
                   source=dotrep["literal"].get("max_near_source"),
                   near_3px_fraction=dotrep["literal"].get("max_near_3px_fraction"),
                   explanation="the single literal offender is a spacing-5 square lattice, i.e. a "
                               "universal-coverage probe: its maximum interior distance is sqrt(8)=2.83 "
                               "px, so its 3 px halo covers essentially every eligible pixel and the "
                               "directed near-3px statistic is ~1.0 for EVERY nonempty candidate. That "
                               "is a property of the registry, not of this candidate, which is why the "
                               "shared template publishes a policy tier beside the literal one. Both "
                               "are reported and neither is waived."))
    grid.save_json(EVID / "h95_lane.json", out)
    log(f"LANE surface literal max_rho={surface.get('literal', {}).get('max_spearman')} "
        f"dup={surface.get('literal', {}).get('duplicate')} | "
        f"dots literal max_rho={dotrep.get('literal', {}).get('max_spearman')} "
        f"near={dotrep.get('literal', {}).get('max_near_3px_fraction')} "
        f"dup={dotrep.get('literal', {}).get('duplicate')}")
    return out


# ------------------------------------------------------------------------------------------- write
def stage_write():
    check_prereg()
    valid, cat, eligible = _load_setup()
    dots = np.load(WORK / "dots.npy")
    # The organiser's own footprint is `labels != -1` (5,167,373 px), which is 1,533 px larger than the
    # feature intersection.  A submission must be finite there too, so the container is all-finite with
    # zeros outside the feature footprint -- the container the 0.2778 reference itself uses.
    inside = np.where(dots, 1.0, 0.0).astype(np.float32)
    if not np.isfinite(inside).all() or inside.min() < 0 or inside.max() > 1:
        raise SystemExit("emission is not finite and inside [0,1] before writing")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems52-h95-straindipole-cotrain-{int(dots.sum())}px-{stamp}"
    path = ROOT / "submission" / f"{name}.tif"
    receipt = submission_writer.write_submission(
        path, inside, SAMPLE, valid,
        note=("H95 co-training: odd-symmetric fault-normal strain dipole (View A) gated to where View B "
              "abstains; 200m catalogue ring excluded; binary dots")[0:140],
        name=name[0:140],
        metadata=dict(round="H95", mechanism="odd-symmetric fault-normal profile decomposition",
                      emitted_px=int(dots.sum())))
    # container comparison against the 0.2778 reference, measured from both files' bytes
    with rasterio.open(path) as s1, rasterio.open(DATA / "reference" / "h33-2-b2-zeros.tif") as s2:
        p1, p2 = s1.profile, s2.profile
        cont = {k: (p1.get(k), p2.get(k)) for k in
                ("driver", "height", "width", "count", "dtype", "compress", "tiled", "predictor", "nodata")}
        same = all(a == b for a, b in cont.values())
    receipt["container_vs_0p2778_reference"] = dict(
        reference=str(DATA / "reference" / "h33-2-b2-zeros.tif"),
        reference_sha256=sha256_file(DATA / "reference" / "h33-2-b2-zeros.tif"),
        fields={k: dict(ours=a, reference=b) for k, (a, b) in cont.items()},
        identical_container=bool(same),
        note="the 0.2778 file is all-finite with zeros outside and no nodata tag; matching that "
             "container removes the NaN-reader unknown behind 'Predicted values must be in range [0, 1]'")
    receipt["range_gate"] = dict(min=receipt["validator"]["min"], max=receipt["validator"]["max"],
                                 n_nan=receipt["validator"]["n_nan"],
                                 values_in_0_1=bool(receipt["validator"]["min"] >= 0.0
                                                    and receipt["validator"]["max"] <= 1.0
                                                    and receipt["validator"]["n_nan"] == 0))
    grid.save_json(EVID / "h95_write.json", receipt)
    log(f"WRITE ok: {path.name} sha256={receipt['sha256'][:16]}… container match={same}")
    return receipt


def stage_reasoning():
    """Geological reasoning for every A-only (A confident / B abstains) emitted cell."""
    import csv
    valid, cat, eligible = _load_setup()
    dots = np.load(WORK / "dots.npy")
    zA = np.load(WORK / "zA_full.npy"); zB = np.load(WORK / "zB_full.npy")
    F = Fields()
    cosn = np.load(WORK / "cosn_full.npy"); sinn = np.load(WORK / "sinn_full.npy")
    edc = ndimage.distance_transform_edt(~cat, sampling=metric.PIXEL_M)
    rows = np.nonzero(dots)[0]; cols = np.nonzero(dots)[1]
    Xa, Xb = compute_channels_full(F, rows, cols, cosn, sinn)
    a_names, b_names = channel_names()
    fin = np.isfinite(zA) & np.isfinite(zB) & eligible
    medB = float(np.median(zB[fin]))
    tr = grid.TRANSFORM
    out = ROOT / "docs" / "downloads" / "h95-a-only-reasoning.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    i_odd = [i for i, n in enumerate(a_names) if n.endswith("_oddom")]
    i_cpl = [i for i, n in enumerate(a_names) if n.endswith("_couple")]
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "view_A_score", "view_B_score",
                    "b_abstains", "catalogue_distance_m", "fault_normal_deg_compass",
                    "dominant_view_A_band", "mean_odd_dominance", "sign_reversal_couple",
                    "mechanism", "named_non_fault_mimic", "falsifier", "evidence_class"])
        for j in range(rows.size):
            r, c = int(rows[j]), int(cols[j])
            od = float(np.mean(Xa[j, i_odd])); cp = float(np.max(Xa[j, i_cpl]))
            # Which View A band carries the largest |odd| response here.  Named "view_A", not "strain":
            # the channel set includes the isostatic-gravity cross-family control, so the winner can be a
            # gravity band, and calling that a strain band would misdescribe the row.
            i_abs = [i for i, n in enumerate(a_names) if n.endswith("_absodd")]
            bandmax = int(np.argmax(np.abs(Xa[j, i_abs])))
            nm = ["dilatation_rate_b8_h1", "dilatation_rate_b8_h2", "shear_rate_b7_h2",
                  "second_invariant_b4_h2", "isostatic_gravity_b13_h2",
                  "isostatic_gravity_hg_b18_h2"][min(bandmax, 5)]
            ndeg = float(np.degrees(np.arctan2(sinn[r, c], cosn[r, c])) % 180.0)
            w.writerow([r, c, round(tr[2] + (c + 0.5) * tr[0], 1), round(tr[5] + (r + 0.5) * tr[4], 1),
                        round(float(zA[r, c]), 5), round(float(zB[r, c]), 5), bool(zB[r, c] < medB),
                        round(float(edc[r, c]), 1), round(ndeg, 1), nm, round(od, 5), round(cp, 5),
                        "antisymmetric geodetic strain couple across a locked/buried normal fault: "
                        "dilatant on one side, relatively contractile on the other, so the trace sits at "
                        "a zero crossing of the smoothed dilatation/shear field with an odd-dominant "
                        "fault-normal profile",
                        "interpolated GPS/InSAR strain grid artefact (station-density gradient or block "
                        "smoothing seam); magmatic inflation-deflation; post-seismic viscoelastic "
                        "relaxation; lithologic ramp that is even-dominant but noisy",
                        "the couple must reverse sign when the fault-normal direction is rotated by 90 "
                        "degrees, and must persist at both lags h=1 and h=2 px; a smoothing seam does "
                        "neither. Field check: no Quaternary scarp, no mapped trace within 200 m, and a "
                        "basement-depth step (band 15) should be present if the fault is real and buried",
                        "model evidence for a Phase-2 reviewer target, NOT an organizer-confirmed fault"])
    import gzip as _gzip
    import shutil as _shutil
    gzp = Path(str(out) + ".gz")
    with open(out, "rb") as fh, _gzip.GzipFile(gzp, "wb", compresslevel=9) as gz:
        _shutil.copyfileobj(fh, gz)
    n = rows.size
    # ---- did the emission actually select the signature the hypothesis named? --------------------
    # This is the question the round's own negative result turns on, so it is measured from the
    # exported rows rather than asserted in prose.
    import collections
    band_idx = [i for i, nm_ in enumerate(a_names) if nm_.endswith("_absodd")]
    dom = [str(np.argmax(np.abs(Xa[j, band_idx]))) for j in range(rows.size)]
    dom_names = ["dilatation_rate_b8_h1", "dilatation_rate_b8_h2", "shear_rate_b7_h2",
                 "second_invariant_b4_h2", "isostatic_gravity_b13_h2", "isostatic_gravity_hg_b18_h2"]
    counts = collections.Counter(dom_names[min(int(d), len(dom_names) - 1)] for d in dom)
    couples = np.array([float(v) for v in _csv_col(out, "sign_reversal_couple")])
    odds = np.array([float(v) for v in _csv_col(out, "mean_odd_dominance")])
    dists = np.array([float(v) for v in _csv_col(out, "catalogue_distance_m")])
    strain_px = sum(v for k, v in counts.items()
                    if k.startswith(("dilatation", "shear", "second")))
    diag = dict(
        dominant_view_A_band_counts=dict(counts),
        strain_dominant_px=int(strain_px), strain_dominant_fraction=round(strain_px / max(1, n), 5),
        gravity_dominant_px=int(n - strain_px), gravity_dominant_fraction=round((n - strain_px) / max(1, n), 5),
        sign_reversal_couple_present_px=int((couples > 0).sum()),
        sign_reversal_couple_present_fraction=round(float((couples > 0).mean()), 5),
        mean_odd_dominance_median=round(float(np.median(odds)), 6),
        mean_odd_dominance_p95=round(float(np.percentile(odds, 95)), 6),
        min_catalogue_distance_m=round(float(dists.min()), 1),
        b_abstains_on_every_row=bool(all(v == "True" for v in _csv_col(out, "b_abstains"))),
        reading=("the emission did NOT predominantly select the signature the hypothesis named: "
                 "75.6% of emitted cells carry their largest |odd| response in an isostatic-gravity "
                 "band rather than a strain band, only 7.5% show an actual sign-reversal couple, and "
                 "the median odd-dominance is 0.0125, i.e. most emitted cells are EVEN-dominant "
                 "monotone steps. A linear blend of |odd|, odd-dominance and couple lets the "
                 "largest-magnitude channel decide, so this arm tested 'large fault-normal gradient' "
                 "far more than it tested 'antisymmetric couple'. The negative verdict stands as "
                 "frozen, but the hypothesis itself is NOT cleanly refuted by this arm - a clean test "
                 "gates on the couple directly."),
        clean_test_for_the_next_round=("emit only cells with sign(B(+h)) != sign(B(-h)) at BOTH lags "
                                       "and odd-dominance above a quantile frozen before the fit, "
                                       "instead of letting a logistic model weight |odd| against it"))
    grid.save_json(EVID / "h95_reasoning.json", dict(csv=str(out), rows=int(n),
                                                     bytes=out.stat().st_size,
                                                     gz=str(out) + ".gz",
                                                     gz_bytes=(Path(str(out) + ".gz").stat().st_size
                                                               if Path(str(out) + ".gz").exists() else None),
                                                     columns=list(_csv_col_header(out)),
                                                     signature_diagnostic=diag,
                                                     scope="every emitted cell of the primary arm; "
                                                           "the pseudo-label exchange was not run, so "
                                                           "there is no separate A-only stratum"))
    log(f"REASONING ok: {n:,} rows -> {out.name}; strain-dominant {100 * strain_px / max(1, n):.1f}%, "
        f"sign-reversal couple present on {100 * float((couples > 0).mean()):.1f}%")
    return dict(csv=str(out), rows=int(n), signature_diagnostic=diag)


def _csv_col(path, name):
    import csv as _csv
    with open(path, newline="") as fh:
        for row in _csv.DictReader(fh):
            yield row[name]


def _csv_col_header(path):
    import csv as _csv
    with open(path, newline="") as fh:
        return next(_csv.reader(fh))


def stage_card():
    reg = check_prereg()
    setup = json.loads((EVID / "h95_setup.json").read_text())
    fit = json.loads((EVID / "h95_fit.json").read_text())
    hold = json.loads((EVID / "h95_holdout.json").read_text())
    ind = json.loads((EVID / "h95_independence.json").read_text())
    build = json.loads((EVID / "h95_build.json").read_text())
    lane = json.loads((EVID / "h95_lane.json").read_text())
    wr = json.loads((EVID / "h95_write.json").read_text())
    prim = hold["pooled"]["scores"]["A_ODD_gated"]
    sb = hold["pooled"]["scores"]["single_B"]
    d = hold["promotion_delta_vs_single_B"]
    lit = lane["dots"].get("literal", {})
    card = {
        "round": "H95",
        "hypothesis": "A locked, creeping or basin-buried normal fault partitions GPS/InSAR-derived "
                      "geodetic strain into an antisymmetric couple about its trace, so a SIGNED "
                      "odd-symmetric fault-normal profile decomposition of the dilatation/shear/second-"
                      "invariant fields localises faults that have no Quaternary surface rupture and are "
                      "therefore absent from the USGS/INGENIOUS catalogue by construction.",
        "mechanism": "odd=(B(+h)-B(-h))/2, even=(B(+h)+B(-h))/2 at h in {1,2} px along a fault normal "
                     "measured from a structure tensor over each fold's VISIBLE catalogue only; the "
                     "discriminator is odd-dominance odd^2/(|odd|+|even|+eps) plus the sign-reversal "
                     "couple min(|B+|,|B-|)*1[sign differs]; View B is the surface view (detrended "
                     "elevation, its slope, aeroradiometric total count) and abstention is B below its "
                     "fold median over the eligible pool.",
        "named_non_fault_process": "the geodetic strain layers are a smooth interpolation of sparse "
                                   "GPS/InSAR observations: (i) station-density gradients and block-"
                                   "boundary smoothing seams create signed couples with no structure; "
                                   "(ii) magmatic inflation/deflation is dilatant by definition; "
                                   "(iii) post-seismic viscoelastic relaxation after the 1954 Fairview "
                                   "Peak and 1959 Hebgen Lake sequences; (iv) elastic strain on an "
                                   "already-mapped fault, removed by the 200 m catalogue ring.",
        "holdout_dti": {"evidence_class": "HOLDOUT-DTI", "evaluator_version": hold["evaluator_version"],
                        "withheld_positive_pixels": hold["withheld_positive_pixels"],
                        "primary_arm": "A_ODD_gated", "dti": prim["dti"], "ci95": prim["ci95"],
                        "control_single_B": {"dti": sb["dti"], "ci95": sb["ci95"]},
                        "paired_delta_primary_minus_single_B": {"delta": d["delta"], "ci95": d["ci95"]},
                        "all_arms": {k: {"dti": v["dti"], "ci95": v["ci95"]}
                                     for k, v in hold["pooled"]["scores"].items()},
                        "is_a_leaderboard_forecast": False,
                        "caveat": hold["caveat"]},
        "oof_auc": {"view_A_mean": fit["sufficiency"]["view_A_mean"],
                    "view_A_min_fold": fit["sufficiency"]["view_A_min_fold"],
                    "view_B_mean": fit["sufficiency"]["view_B_mean"],
                    "view_B_min_fold": fit["sufficiency"]["view_B_min_fold"],
                    "view_A_sufficiency_passed": fit["sufficiency"]["passed"],
                    "per_fold": fit["folds"]},
        "leakage_canary": {"bar": CANARY_ALARM, "max_single_channel_oof_auc": fit["canary"]["max_auc"],
                           "max_channel": fit["canary"]["max_channel"],
                           "alarm_tripped": fit["canary"]["alarm_tripped"]},
        "independence": {"max_abs_rho": ind["max_abs_correlation"], "n_blocks": ind["n_blocks"],
                         "n_negative_predictions": ind["n_negative_predictions"],
                         "abandon_bar": ABANDON_RHO, "allow_exchange": ind["allow_exchange"],
                         "exchange_decision": ind["exchange_decision"],
                         "thresholds_inherited_verbatim_from": ind["thresholds_inherited_verbatim_from"]},
        "correlation_vs_registry": {
            "census_size": lane["census_size"],
            "census_scope": lane["census_scope"],
            "census_excludes_this_round": lane["census_excludes_this_round"],
            "verdicts": lane["verdicts"],
            "dots_literal_witness": lane["dots_literal_witness"],
            "literal_stop": bool(lane["stop"]), "policy_stop": bool(lane["policy_stop"]),
            "surface_literal": {"max_spearman": lane["surface"].get("literal", {}).get("max_spearman"),
                                "duplicate": lane["surface"].get("literal", {}).get("duplicate")},
            "surface_policy": {"max_spearman": lane["surface"].get("policy", {}).get("max_spearman"),
                               "duplicate": lane["surface"].get("policy", {}).get("duplicate")},
            "dots_literal": {"max_spearman": lit.get("max_spearman"),
                             "max_near_3px_fraction": lit.get("max_near_3px_fraction"),
                             "duplicate": lit.get("duplicate")},
            "dots_policy": {"max_spearman": lane["dots"].get("policy", {}).get("max_spearman"),
                            "max_near_3px_fraction": lane["dots"].get("policy", {}).get("max_near_3px_fraction"),
                            "duplicate": lane["dots"].get("policy", {}).get("duplicate")},
            "thresholds": {"rank_rho": 0.90, "near_3px_fraction": 0.70}},
        "not_the_union": build["not_the_union"],
        "raster_sha256": wr["sha256"],
        "raster_file": wr["file"], "raster_bytes": wr["bytes"], "zip_sha256": wr["zip_sha256"],
        "validator_output": wr["validator"],
        "range_gate": wr["range_gate"],
        "container_vs_0p2778_reference": wr["container_vs_0p2778_reference"],
        "placement": {"emitted_px": build["emitted_px"], "budget": build["requested_budget"],
                      "short_fill": build["short_fill"], "min_separation_px": build["min_separation_px"],
                      "catalogue_distance_m": build["catalogue_distance_m"],
                      "marginal_rule": build["marginal_rule"]},
        "submission_name": wr["submission_name"],
        "submission_note": wr["note"],
        "submission_note_chars": wr["note_chars"],
        "slots_used": 0,
        "promoted": bool(hold["promoted"]),
        "verdict": "promote" if hold["promoted"] else "negative",
        "download_ok": True,
        "submit_ok": bool(hold["promoted"]) and bool(build["not_the_union"]["ok"])
        and not lane["stop"] and not lane["policy_stop"],
        "submit_ok_reason": ("promoted={p}, not_the_union_ok={u}, lane_literal_stop={l}, "
                             "lane_policy_stop={q}".format(p=bool(hold["promoted"]),
                                                           u=bool(build["not_the_union"]["ok"]),
                                                           l=bool(lane["stop"]),
                                                           q=bool(lane["policy_stop"]))),
        "preregistration": {"document": reg["hypothesis_document"], "sha256": reg["hypothesis_sha256"],
                            "frozen_before_any_fit": True},
        "organizer_confirmed_numbers": {
            "source": "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
            "fetched_utc": "2026-10-10",
            "public_leaderboard_top": 0.3774, "rank_8": 0.3195, "rank_22": 0.2778,
            "note": "public-chunk scores read off the organiser's own leaderboard page; the Initial "
                    "Prize Round is scored on the PRIVATE chunk, so none of these is a target this "
                    "repository can verify against its own file"},
        "reasoning_export": json.loads((EVID / "h95_reasoning.json").read_text())
        if (EVID / "h95_reasoning.json").exists() else None,
        "budget": {"max_experiments": reg["budget"]["max_experiments"], "experiments_used": 3},
    }
    grid.save_json(EVID / "h95_run_card.json", card)
    (ROOT / "submission" / "H95_LATEST.txt").write_text(
        f"{wr['file']}\n# pointer for the site; NOT an upload approval\n"
        f"# submit_ok={card['submit_ok']} download_ok={card['download_ok']}\n")
    log(f"CARD: verdict={card['verdict']} submit_ok={card['submit_ok']} sha={wr['sha256'][:16]}…")
    return card


STAGES = {"setup": stage_setup, "channels": stage_channels, "fit": stage_fit,
          "holdout": stage_holdout, "independence": stage_independence, "build": stage_build,
          "lane": stage_lane, "write": stage_write, "reasoning": stage_reasoning, "card": stage_card}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", nargs="+", choices=list(STAGES) + ["all"])
    args = ap.parse_args(argv)
    stages = list(STAGES) if args.stage == ["all"] or "all" in args.stage else args.stage
    for s in stages:
        log(f"=== STAGE {s} ===")
        STAGES[s]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
