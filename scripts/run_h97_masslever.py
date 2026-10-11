#!/usr/bin/env python3
"""H97 -- two questions the eight previous co-training rounds never asked.

Lane (standing brief, single method paragraph): two-view co-training between a geophysical view
(A) and a surface view (B) with disagreement as the discovery signal (Blum & Mitchell, COLT '98,
pp. 92-100, doi:10.1145/279943.279962).

    instrument  E1: is our holdout instrument rank-correlated with the board's own scored files?
    holdout     E2: co-training at the metric-implied mass lever, with View B at full channel width
    build/write E3: the unique GeoTIFF, every gate re-read from the written bytes

Frozen before any fit in ``registry/h97_masslever_preregistration.json`` (sha256 of
``knowledge/105_h97_masslever_hypotheses_preregistered.md``); the runner refuses to start if the hash moves.

Shared tools are reused, never forked: ``gems52.spatial`` (whole-component label-blind-quadrant
folds, negative_block_errors, independence, whole_pseudo_segments), ``gems52.evaluate_holdout``
(``gems52-pooled-hide-v1``), ``gems52.nodes.spacing_select`` (metric-aware placement),
``gems52.gates`` (format/uniqueness/lane), ``gems52.submission_writer``.

Usage: python scripts/run_h97_masslever.py [folds|instrument|views|holdout|build|write|card|all]
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from scipy.stats import spearmanr, pearsonr                           # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer           # noqa: E402

PREREG = ROOT / "registry/h97_masslever_preregistration.json"
WORK = ROOT / "work/h97"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DLDIR = ROOT / "docs/downloads"
SUBDIR = ROOT / "submission"

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
RAD = ROOT / "data/external/geodawn_rad_u8.tif"
EXT = ROOT / "data/external/geodawn_extensions_u8.tif"
LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
SCORED = ROOT / "data/scored"
REFERENCE = ROOT / "data/reference"

SEED = 97001
BUFFER_PX = 80            # registry/h84_preregistration.json thresholds
RING_PX = 2               # catalogue_exclusion_m 200 / 100 m cells
K_FOLD = 9400             # matched budget (4 x 9,400 = 37,654)
K_FOLD_MASS = 6350        # metric-implied mass lever (4 x 6,350 = 25,400), knowledge/76 section 3
S_SHIP = 25400
PRIMARY = "cotrain_dis"
BAR = 0.190147            # H84 primary B_DVA2_HVA (evidence/h84_holdout.json)
CANARY_ALARM = 0.90
INDEP_ABANDON = 0.60
SPACING_PX = 3.0

# frozen component weights (rank-01-normalised inside the eligible footprint before weighting)
A_W = {"grav_hg": 0.22, "mag_hg": 0.18, "cover_step": 0.22, "seis_line": 0.13,
       "strain_step": 0.10, "mag_vg": 0.10, "cond": 0.05}
# H96's five channels, plus the LiDAR-scarp and radiometric-ratio channels the certified-best
# FITTED View B instrument uses (H61/H84 View B feature list) -- the only change from H96.
B_W = {"slope": 0.14, "ridge_curv": 0.18, "topo_edge": 0.12, "K_over_Th": 0.08, "tc": 0.06,
       "scarp_ex_max": 0.10, "scarp_step_max": 0.10, "scarp_upface_max": 0.08,
       "scarp_relief": 0.05, "scarp_coh100": 0.04,
       "rad_ThK": 0.02, "rad_UK": 0.02, "rad_UTh": 0.01}
LIDAR_BANDS = {"scarp_ex_max": 1, "scarp_step_max": 3, "scarp_upface_max": 7,
               "scarp_relief": 9, "scarp_coh100": 10}
EXT_BANDS = {"rad_ThK": 1, "rad_UK": 2, "rad_UTh": 3}

# OWNER-REPORTED board scores (the owner's submission-page receipts, knowledge/75).  Not
# ORGANIZER-CONFIRMED: no submission-page receipt is quoted in this repository.
BOARD_SCORES = {
    "gems52-h56-consensus-core-continuation": None,
}
BOARD_FILES = {
    "h33-2-b2-zeros": 0.2778,
    "d2-8": 0.2600,
    "d1-5": 0.2477,
    "tgc_v2_d1_5": 0.2449,
    "h19-5": 0.1922,
    "h19-4": 0.1894,
    "h16-1": 0.1855,
    "h28-dotted-ridge": 0.1839,
    "ens12-adopted": 0.1563,
    "Hedge-v2": 0.1563,
    "h25-ctx-ridge": 0.1280,
    "r13-lattice-s5": 0.0904,
    "2314b599": 0.0107,
}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_prereg():
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    got = sha256_file(doc)
    if got != reg["hypothesis_sha256"]:
        raise SystemExit(f"preregistration hash moved: {got} != {reg['hypothesis_sha256']}; "
                         "refusing to run (frozen before any fit)")
    return {"preregistration_sha256": got, "hypothesis_bytes": int(doc.stat().st_size),
            "frozen_before_any_fit": True}


def write_ev(name: str, obj):
    EVID.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    p = EVID / f"{name}.json"
    txt = json.dumps(obj, indent=2, allow_nan=False, default=float) + "\n"
    p.write_text(txt)
    (DOCS / f"{name}.json").write_text(txt)
    return p


# ---------------------------------------------------------------------------------------------
# shared loaders
# ---------------------------------------------------------------------------------------------
def clean_band(v: np.ndarray) -> np.ndarray:
    b = np.asarray(v, np.float32).copy()
    b[~np.isfinite(b)] = 0.0
    b[b < -1e38] = 0.0
    return b


def band(src, i):
    return clean_band(src.read(i))


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros(a.shape, np.float32)
    v = a[mask]
    if v.size == 0:
        return out
    out[mask] = np.argsort(np.argsort(v)).astype(np.float32) / max(v.size - 1, 1)
    return out


def smooth_normalized(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    good = valid & np.isfinite(a)
    num = ndi.gaussian_filter(np.where(good, a, 0.0).astype(np.float64), sigma,
                              mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float64), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8).astype(np.float32)


def gradmag(a, valid, sigma, cell_m=100.0):
    s = smooth_normalized(a, valid, sigma)
    gy, gx = np.gradient(s, cell_m)
    return np.sqrt(gx * gx + gy * gy).astype(np.float32)


def hessian_min_abs(a, valid, sigma, cell_m=100.0):
    s = smooth_normalized(a, valid, sigma)
    gyy = np.gradient(np.gradient(s, cell_m, axis=0), cell_m, axis=0)
    gxx = np.gradient(np.gradient(s, cell_m, axis=1), cell_m, axis=1)
    gyx = np.gradient(np.gradient(s, cell_m, axis=0), cell_m, axis=1)
    trace, det = gyy + gxx, gyy * gxx - gyx * gyx
    disc = np.sqrt(np.maximum(0.25 * trace * trace - det, 0.0))
    return np.abs(0.5 * trace - disc).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# stage: folds
# ---------------------------------------------------------------------------------------------
def stage_folds():
    reg = check_prereg()
    with rasterio.open(LABELS) as ds, rasterio.open(SAMPLE) as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid != sample grid")
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
    cat = labels == 1
    with rasterio.open(FEATURES) as src:
        valid = np.ones(cat.shape, bool)
        for i in range(1, src.count + 1):
            arr = src.read(i)
            valid &= np.isfinite(arr) & (arr > -1e38)
            del arr
    valid &= domain
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    WORK.mkdir(parents=True, exist_ok=True)
    np.save(WORK / "valid.npy", valid)
    np.save(WORK / "cat.npy", cat)
    out = dict(stage="folds", registration=reg, eligible_px=int(valid.sum()),
               catalogue_px=int(cat.sum()), withheld_positive_px=withheld,
               buffer_px=BUFFER_PX, ring_px=RING_PX, folds=len(folds),
               fold_receipts=[f["receipt"] for f in folds],
               split_version="label-blind-quadrants-v2", generated_utc=now())
    write_ev("h97_folds", out)
    log(f"eligible {int(valid.sum()):,} px; catalogue {int(cat.sum()):,} px; "
        f"withheld positives {withheld:,} px over {len(folds)} folds")
    return out


def load_folds():
    valid = np.load(WORK / "valid.npy")
    cat = np.load(WORK / "cat.npy")
    return valid, cat, list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))


def allowed_for(fold, valid):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (vd > RING_PX)


# ---------------------------------------------------------------------------------------------
# stage: instrument (E1)
# ---------------------------------------------------------------------------------------------
def read_prior_binary(path: Path, valid: np.ndarray):
    """A previously written submission as it stands: >0 is a prediction.  NaN becomes 0.

    The organiser's own worked examples and eleven of the twelve scored priors declare nodata as
    NaN outside the footprint; the portal nevertheless rejected a file whose reader saw values
    outside [0,1] (owner report, this session's brief).  NaN outside the footprint is therefore
    treated as "no prediction", and the count of NaN *inside* the footprint is reported, never
    silently absorbed.
    """
    with rasterio.open(str(path)) as src:
        a = src.read(1).astype(np.float32)
    nan_in = int((~np.isfinite(a) & valid).sum())
    nan_out = int((~np.isfinite(a) & ~valid).sum())
    p = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    out_of_range = int(((p < 0) | (p > 1)).sum())
    p = np.clip(p, 0.0, 1.0)
    return (p > 0).astype(np.float32), dict(nan_inside_footprint=nan_in, nan_outside_footprint=nan_out,
                                            values_out_of_range=out_of_range)



def prior_list(roots, own_names: set[str]):
    """gates.find_priors with this round's OWN artifact copies removed by name.

    ``find_priors`` already refuses to compare a candidate against itself (IR-52-026), including a
    staged copy with the *same* basename.  This round stages a second, shorter alias
    (``h97-masslever-candidate.tif``) for the site, whose basename differs, so the tool cannot know it is the
    same bytes; without this filter the candidate is compared against its own copy and the gate
    reports "identical to a prior, novel = 0" -- the one verdict that would wrongly stop a
    legitimate submission.  Only this round's own names are removed; every other prior is kept.
    """
    found = gates.find_priors(roots)
    keep = [p for p in found if p.name not in own_names]
    dropped = [str(p) for p in found if p.name in own_names]
    return keep, dropped

INSTRUMENT_ARMS = [
    ("champion_h33_2_b2", REFERENCE / "h33-2-b2-zeros.tif", "h33-2-b2-zeros"),
    ("d2_8", SCORED / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif", "d2-8"),
    ("d1_5", SCORED / "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif", "d1-5"),
    ("tgc_v2_d1_5", SCORED / "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
     "tgc_v2_d1_5"),
    ("h19_5", SCORED / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
     "h19-5"),
    ("h19_4", SCORED / "gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
     "h19-4"),
    ("h16_1", SCORED / "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif", "h16-1"),
    ("h28_dotted_ridge", SCORED / "gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
     "h28-dotted-ridge"),
    ("ens12_adopted", SCORED / "gemsdoe-ens12-adopted-7f00890a.tif", "ens12-adopted"),
    ("hedge_v2", SCORED / "8GEMSDOE_Hedge-v2_submission.tif", "Hedge-v2"),
    ("h25_ctx_ridge", SCORED / "gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
     "h25-ctx-ridge"),
    ("r13_lattice_s5", SCORED / "13gems_20261001_r13-lattice-s5_v2_nan-outside.tif", "r13-lattice-s5"),
    ("nan_2314b599", SCORED / "gemsdoe9-PLACEHOLDER-2314b599.tif", "2314b599"),
]


def stage_instrument():
    reg = check_prereg()
    reg_doc = json.loads(PREREG.read_text())
    valid, cat, folds = load_folds()
    arms = {}
    notes = {}
    for key, path, board_key in INSTRUMENT_ARMS:
        if not path.exists():
            raise SystemExit(f"missing restored prior {path}")
        p, note = read_prior_binary(path, valid)
        arms[key] = p
        note["board_score_owner_reported"] = BOARD_FILES.get(board_key)
        note["path"] = str(path.relative_to(ROOT))
        notes[key] = note
        log(f"loaded {key:20s} mass {int(p.sum()):8,}  {note}")
    # random controls under the same placement rule
    for k in (K_FOLD * 4, S_SHIP):
        rnd = np.zeros(valid.shape, np.float32)
        for fold in folds:
            allowed = allowed_for(fold, valid)
            rng = np.random.default_rng(SEED + int(fold["fold"]) + k)
            idx = np.flatnonzero(allowed.ravel())
            vals = rng.random(len(idx), dtype=np.float32)
            rnd.ravel()[idx] = np.maximum(rnd.ravel()[idx], vals)
        arms[f"random_{k}"] = nodes.spacing_select(rnd, valid, k, min_px=SPACING_PX).astype(np.float32)
        notes[f"random_{k}"] = dict(board_score_owner_reported=None, mass=int(arms[f"random_{k}"].sum()))
    terms = {k: None for k in arms}
    per_fold = []
    for fold in folds:
        f = int(fold["fold"])
        rec = dict(fold=f, withheld_positive_px=int((fold["truth"] & fold["region"]).sum()), arms={})
        for k, em in arms.items():
            res, term = evaluator.evaluate(np.where(valid, em, 0.0).astype(np.float32), fold, valid,
                                           block_side=200)
            terms[k] = term if terms[k] is None else terms[k] + term
            rec["arms"][k] = dict(dti=float(res["dti"]), emitted=int(res["emitted"]))
            log(f"  fold {f} {k:20s} DTI {res['dti']:.6f} emitted {res['emitted']:,}")
        per_fold.append(rec)
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="champion_h33_2_b2")
    # correlation of the instrument with the board
    rows = []
    for key, path, board_key in INSTRUMENT_ARMS:
        bs = BOARD_FILES.get(board_key)
        if bs is None:
            continue
        rows.append(dict(arm=key, board_score=bs, holdout_dti=summary["scores"][key]["dti"],
                         holdout_ci95=summary["scores"][key]["ci95"],
                         emitted=int(arms[key].sum())))
    mass = np.array([r["emitted"] for r in rows], float)
    dti = np.array([r["holdout_dti"] for r in rows], float)
    board = np.array([r["board_score"] for r in rows], float)

    def _corr(a, b):
        if len(a) < 3 or np.ptp(a) <= 0 or np.ptp(b) <= 0:
            return dict(n=int(len(a)), spearman=None, pearson=None)
        return dict(n=int(len(a)), spearman=float(spearmanr(a, b).statistic),
                    pearson=float(pearsonr(a, b).statistic))

    raw = _corr(board, dti)
    board_mass = _corr(board, mass)
    # partial correlation of board and DTI controlling for log mass (residualise both on log mass)
    lm = np.log(mass)
    def _resid(y):
        x = np.column_stack([np.ones_like(lm), lm])
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        return y - x @ beta
    r_b = _resid(board)
    r_d = _resid(dti)
    partial = _corr(r_b, r_d)
    hyp = reg_doc["experiments"]["E1_instrument_fidelity"]
    falsified = raw["spearman"] is not None and raw["spearman"] >= 0.5
    out = dict(stage="instrument", registration=reg, evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, withheld_positive_px=summary["scores"]
               ["champion_h33_2_b2"]["withheld_positive_pixels"],
               folds=len(folds), buffer_px=BUFFER_PX, ring_px=RING_PX,
               hypothesis=hyp["hypothesis"], falsifier=hyp["falsifier"],
               spearman_board_vs_holdout=raw, spearman_board_vs_mass=board_mass,
               partial_board_vs_holdout_given_log_mass=partial,
               falsified=falsified,
               verdict=("instrument TRACKS the board (falsifier hit)" if falsified else
                        "instrument does NOT track the board (hypothesis not falsified)"),
               rows=rows, prior_notes=notes, pooled=summary, per_fold=per_fold,
               board_score_provenance="OWNER-REPORTED (knowledge/75 owner receipts) -- NOT organizer-confirmed",
               implementation_hashes=evaluator.implementation_hashes(), generated_utc=now())
    write_ev("h97_instrument", out)
    log(f"Spearman(board, HOLDOUT-DTI) = {raw['spearman']}; partial | log-mass = {partial['spearman']}; "
        f"Spearman(board, mass) = {board_mass['spearman']}")
    log(f"E1 verdict: {out['verdict']}")
    return out


# ---------------------------------------------------------------------------------------------
# stage: views
# ---------------------------------------------------------------------------------------------
def build_views(valid: np.ndarray, want: dict | None = None):
    comps = {}
    with rasterio.open(FEATURES) as src:
        comps["grav_hg"] = np.abs(band(src, 18))
        comps["mag_hg"] = np.abs(band(src, 3))
        b15 = band(src, 15)
        comps["cover_step"] = gradmag(b15, valid, 2.0)
        del b15
        b10 = band(src, 10)
        comps["seis_line"] = gradmag(b10, valid, 2.0)
        del b10
        b7 = band(src, 7)
        comps["strain_step"] = gradmag(b7, valid, 2.0)
        del b7
        comps["mag_vg"] = np.abs(band(src, 9))
        comps["cond"] = band(src, 17)
        comps["slope"] = band(src, 19)
        b12 = band(src, 12)
        comps["ridge_curv"] = hessian_min_abs(b12, valid, 1.5)
        comps["topo_edge"] = gradmag(b12, valid, 1.5)
        del b12
        comps["tc"] = band(src, 6)
        log("A+B base components done")
    with rasterio.open(RAD) as src:
        k = src.read(1).astype(np.float32) / 255.0
        th = src.read(2).astype(np.float32) / 255.0
    k[~np.isfinite(k)] = 0.0
    th[~np.isfinite(th)] = 0.0
    comps["K_over_Th"] = (k / (th + 1e-3)).astype(np.float32)
    del k, th
    # the channels the certified-best FITTED View B uses, absent from H96's unfitted composite
    cov = {}
    with rasterio.open(LIDAR) as src:
        if (src.height, src.width) != valid.shape:
            raise SystemExit(f"lidar layer shape {src.height}x{src.width} != grid")
        for name, b in LIDAR_BANDS.items():
            a = src.read(b).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            comps[name] = a
            cov[name] = float((a > 0).mean())
    with rasterio.open(EXT) as src:
        if (src.height, src.width) != valid.shape:
            raise SystemExit(f"extension layer shape {src.height}x{src.width} != grid")
        for name, b in EXT_BANDS.items():
            a = src.read(b).astype(np.float32)
            a[~np.isfinite(a)] = 0.0
            comps[name] = a
            cov[name] = float((a > 0).mean())
    log("B extended components done: " + json.dumps(cov))
    if want:
        return {n: comps[n] for n in want}
    a = np.zeros(valid.shape, np.float32)
    for n, w in A_W.items():
        a += np.float32(w) * rank01(comps[n], valid)
        del comps[n]
    b = np.zeros(valid.shape, np.float32)
    for n, w in B_W.items():
        b += np.float32(w) * rank01(comps[n], valid)
        del comps[n]
    return rank01(a, valid), rank01(b, valid), cov


def stage_views():
    reg = check_prereg()
    valid = np.load(WORK / "valid.npy")
    a, b, cov = build_views(valid)
    np.savez_compressed(WORK / "views.npz", a=a, b=b)
    out = dict(stage="views", registration=reg, eligible_px=int(valid.sum()),
               weights_A=A_W, weights_B=B_W, lidar_ext_coverage=cov,
               view_correlation=float(np.corrcoef(a[valid], b[valid])[0, 1]),
               features_sha256=sha256_file(FEATURES), labels_sha256=sha256_file(LABELS),
               rad_sha256=sha256_file(RAD), extensions_sha256=sha256_file(EXT),
               lidar_sha256=sha256_file(LIDAR),
               difference_from_H96="View B adds lidar scarp bands 1,3,7,9,10 and geodawn_extensions bands 1,2,3",
               generated_utc=now())
    write_ev("h97_views", out)
    log(f"view correlation {out['view_correlation']:.4f}")
    return out


# ---------------------------------------------------------------------------------------------
# stage: holdout (E2)
# ---------------------------------------------------------------------------------------------
def make_field(a, b, valid):
    cons = a * b
    buried = a * np.clip(a - b, 0.0, 1.0)
    art = np.clip(b - a, 0.0, 1.0)
    veto = np.zeros(valid.shape, np.float32)
    pos = valid & (art > 0)
    if pos.any():
        veto[pos] = rank01(art, pos)[pos]
    field = (0.45 * cons + 0.55 * buried) * (1.0 - 0.70 * veto)
    return (np.where(valid, field, 0.0).astype(np.float32), cons, buried, art, veto)


def stage_holdout():
    reg = check_prereg()
    valid, cat, folds = load_folds()
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    field, cons, buried, art, veto = make_field(a, b, valid)
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positives {withheld:,}")

    # ---- independence gate: spatial-block OOF errors of the two views on labelled negatives ----
    rows = []
    for fold in folds:
        neg = allowed_for(fold, valid) & ~fold["truth"]
        if not neg.any():
            continue
        ta = float(np.quantile(a[neg], 0.9))
        tb = float(np.quantile(b[neg], 0.9))
        rows += spatial.negative_block_errors(a, b, neg, int(fold["fold"]), (ta, tb),
                                             side=50, minimum=32)
    indep = spatial.independence(rows, threshold=INDEP_ABANDON, min_blocks=20)
    log(f"independence max |rho| {indep['max_abs_correlation']:.4f} allow {indep['allow_exchange']}")
    if indep.get("max_abs_correlation") is not None and \
            indep["max_abs_correlation"] >= INDEP_ABANDON:
        out = dict(stage="holdout", registration=reg, independence=indep,
                   verdict="ABANDONED: view errors strongly correlated; co-training abandoned",
                   generated_utc=now())
        write_ev("h97_holdout", out)
        raise SystemExit("independence gate failed")

    # ---- pseudo-label diagnostic: whole segments, buffered, counted not used -------------------
    forbidden = cat.copy()
    vd_all = ndi.distance_transform_edt(~cat)
    train = valid & ~cat & (vd_all > RING_PX)
    _idx, receipts = spatial.whole_pseudo_segments(
        a, b, train, forbidden, donor_threshold=0.90, receiver_lo=0.20, receiver_hi=0.60,
        side=50, min_pixels=5, cap=2000)
    n_segs, n_seg_px = len(receipts), int(_idx.size)
    log(f"whole-segment A-confident/B-abstain candidates: {n_segs} segments, {n_seg_px} px")

    arms = (PRIMARY, "cons_only", "buried_only", "single_B", "single_A", "random")
    terms = {k: None for k in arms}
    terms_mass = {k: None for k in (PRIMARY, "single_B", "random")}
    per_fold = []
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_for(fold, valid)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        fields = {PRIMARY: field, "cons_only": cons, "buried_only": buried,
                  "single_B": b, "single_A": a, "random": rnd}
        rec = dict(fold=f, withheld_positive_px=int((fold["truth"] & fold["region"]).sum()),
                   allowed_px=int(allowed.sum()), arms={}, mass_arms={})
        for k in arms:
            fl = np.where(allowed, fields[k], 0.0).astype(np.float32)
            em = nodes.spacing_select(fl, allowed, K_FOLD, min_px=SPACING_PX).astype(np.float32)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[k] = term if terms[k] is None else terms[k] + term
            rec["arms"][k] = dict(dti=float(res["dti"]), placed=int(em.sum()))
            log(f"fold {f} {k:13s} DTI {res['dti']:.6f} placed {int(em.sum()):,}")
            del em
        for k in terms_mass:
            fl = np.where(allowed, fields[k], 0.0).astype(np.float32)
            em = nodes.spacing_select(fl, allowed, K_FOLD_MASS, min_px=SPACING_PX).astype(np.float32)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms_mass[k] = term if terms_mass[k] is None else terms_mass[k] + term
            rec["mass_arms"][k] = dict(dti=float(res["dti"]), placed=int(em.sum()))
            log(f"fold {f} {k:13s} MASS-LEVER DTI {res['dti']:.6f} placed {int(em.sum()):,}")
            del em
        per_fold.append(rec)
        del rnd

    # ---- canary: every single channel and both composites against held-out truth --------------
    canary = {}
    comps = build_views(valid, want=list(A_W) + list(B_W))
    for fold in folds:
        allowed = allowed_for(fold, valid)
        t = (fold["truth"] & fold["region"])[allowed]
        if not (t.any() and (~t).any()):
            continue
        for n, arr in comps.items():
            canary.setdefault(n, []).append(dict(fold=int(fold["fold"]),
                                                 auc=float(roc_auc_score(t.astype(int), arr[allowed]))))
        for n, arr in (("view_A", a), ("view_B", b), (PRIMARY, field)):
            canary.setdefault(n, []).append(dict(fold=int(fold["fold"]),
                                                 auc=float(roc_auc_score(t.astype(int), arr[allowed]))))
    canary_max = {k: float(max(x["auc"] for x in v)) for k, v in canary.items()}
    canary_alarm = {k: bool(v > CANARY_ALARM) for k, v in canary_max.items()}

    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    summary_mass = evaluator.pooled_summary(terms_mass, draws=1000, seed=SEED, candidate=PRIMARY)
    pri = summary["scores"][PRIMARY]["dti"]
    pri_lo = summary["paired_differences"][summary["best_comparable_control"]]["ci95"][0]
    pri_mass = summary_mass["scores"][PRIMARY]["dti"]
    pri_mass_lo = summary_mass["paired_differences"][summary_mass["best_comparable_control"]]["ci95"][0]
    promote = bool(pri >= BAR and pri_lo > 0 and indep["allow_exchange"] and not any(canary_alarm.values()))
    out = dict(stage="holdout", registration=reg, evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, candidate=PRIMARY,
               budget_per_fold=K_FOLD, mass_lever_budget_per_fold=K_FOLD_MASS,
               folds=len(folds), buffer_px=BUFFER_PX, ring_px=RING_PX,
               withheld_positive_px=withheld, eligible_px=int(valid.sum()),
               independence=indep,
               pseudo_label_diagnostic=dict(whole_segments=n_segs, whole_segment_px=n_seg_px,
                                            used_for_training=False,
                                            note="iterative pseudo-label exchange is a closed negative; count only"),
               pooled=summary, pooled_mass_lever=summary_mass,
               bar_to_beat=BAR, bar_source="evidence/h84_holdout.json primary B_DVA2_HVA",
               primary_dti=pri, primary_paired_ci_low=float(pri_lo),
               primary_mass_lever_dti=pri_mass, primary_mass_lever_paired_ci_low=float(pri_mass_lo),
               verdict_for_slot="promote" if promote else "negative",
               per_fold=per_fold, canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max,
                                              alarm=canary_alarm),
               implementation_hashes=evaluator.implementation_hashes(), generated_utc=now())
    write_ev("h97_holdout", out)
    log("pooled " + json.dumps({k: round(summary["scores"][k]["dti"], 6) for k in arms}))
    log("pooled mass-lever " + json.dumps({k: round(summary_mass["scores"][k]["dti"], 6)
                                           for k in terms_mass}))
    log(f"verdict for slot (bar {BAR}): {out['verdict_for_slot']}")
    return out


# ---------------------------------------------------------------------------------------------
# stage: build
# ---------------------------------------------------------------------------------------------
def stage_build():
    reg = check_prereg()
    valid, cat, _folds = load_folds()
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    field, cons, buried, art, veto = make_field(a, b, valid)
    priors, own_dropped = prior_list([SUBDIR, DLDIR, ROOT / "data/scored", ROOT / "data/reference"],
                                     {"h97-masslever-candidate.tif"})
    log(f"registry priors found: {len(priors)} (own alias copies dropped: {own_dropped})")
    surface = gates.lane_report(field, valid, priors, sample=str(SAMPLE), phase="surface", log=log)
    log(f"surface lane: literal {surface['literal']['verdict']} "
        f"(max Spearman {surface['literal']['max_spearman']}); policy {surface['policy']['verdict']}")
    if surface["policy"]["verdict"] != "PASS":
        raise SystemExit("lane drift on the surface: DUPLICATE/STOP")
    vd = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd > RING_PX)
    dots = nodes.spacing_select(np.where(allowed, field, 0.0).astype(np.float32), allowed,
                                S_SHIP, min_px=SPACING_PX)
    n = int(dots.sum())
    log(f"placed {n:,} dots (target {S_SHIP:,}); allowed {int(allowed.sum()):,} px")
    raster = np.where(dots, 1.0, 0.0).astype(np.float32)
    np.savez_compressed(WORK / "ship.npz", raster=raster, dots=dots, field=field, cons=cons,
                        buried=buried, artifact=art, veto=veto, a=a, b=b)
    y, x = np.nonzero(dots)
    buried_dom = int((buried[y, x] > cons[y, x]).sum())
    comp = dict(emitted=n, target=S_SHIP, buried_dominant_dots=buried_dom,
                consensus_dominant_dots=n - buried_dom,
                buried_dominant_fraction=buried_dom / max(n, 1))
    ua = nodes.spacing_select(np.where(allowed, a, 0.0).astype(np.float32), allowed, S_SHIP,
                              min_px=SPACING_PX)
    ub = nodes.spacing_select(np.where(allowed, b, 0.0).astype(np.float32), allowed, S_SHIP,
                              min_px=SPACING_PX)
    union = ua | ub
    inter = int((dots & union).sum())
    comp["jaccard_vs_viewA_viewB_spaced_topk_union"] = float(inter / max(int((dots | union).sum()), 1))
    comp["intersection_with_view_union"] = inter
    comp["dots_outside_view_union"] = int((dots & ~union).sum())
    comp["is_merely_the_view_union"] = bool(comp["jaccard_vs_viewA_viewB_spaced_topk_union"] >= 0.99
                                            and comp["dots_outside_view_union"] == 0)
    del ua, ub, union
    out = dict(stage="build", registration=reg, composition=comp, allowed_px=int(allowed.sum()),
               catalogue_px=int(cat.sum()), collar_px=RING_PX, spacing_px=SPACING_PX,
               target_mass=S_SHIP, mass_rule="knowledge/76 section 3: DTI 0.3195 at the champion's "
               "credit needs S ~ 25,384 px",
               surface_lane=surface, generated_utc=now())
    write_ev("h97_build", out)
    log("composition " + json.dumps(comp))
    return out


# ---------------------------------------------------------------------------------------------
# stage: write
# ---------------------------------------------------------------------------------------------
def stage_write():
    reg = check_prereg()
    valid, cat, _folds = load_folds()
    z = np.load(WORK / "ship.npz")
    raster, dots = z["raster"], z["dots"]
    a, b, cons, buried, art = z["a"], z["b"], z["cons"], z["buried"], z["artifact"]
    # An earlier run of THIS round leaves byte-identical rasters with an older stamp; left in the
    # scanned roots they are compared against the new file and reported as "identical to a prior"
    # (the one verdict that would stop a legitimate submission).  Superseded artifacts of this round
    # are therefore removed before writing; other rounds' artifacts are never touched.
    removed = []
    for d in (SUBDIR, DLDIR):
        if d.exists():
            for old in sorted(d.glob("gems52-h97-*")):
                removed.append(str(old.relative_to(ROOT)))
                old.unlink()
    log(f"superseded H97 artifacts removed: {removed}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(raster.tobytes()).hexdigest()[:12]
    name = f"gems52-h97-cotrain-disagree-masslever-{int(raster.sum())}px-{stamp}-{digest}-zeros"
    note = ("H97 co-training A(geophys)xB(surface incl. LiDAR scarp + radiometric ratios); "
            "disagreement mass lever 25,400 dots; 3px spacing; 200m collar")
    out_tif = SUBDIR / f"{name}.tif"
    meta = submission_writer.write_submission(out_tif, raster, sample=str(SAMPLE), footprint=valid,
                                             note=note, name=name)
    log(f"wrote {out_tif} ({out_tif.stat().st_size:,} bytes)")
    # copies for the site
    DLDIR.mkdir(parents=True, exist_ok=True)
    for dst in (DLDIR / f"{name}.tif", DLDIR / "h97-masslever-candidate.tif"):
        dst.write_bytes(out_tif.read_bytes())
    with zipfile.ZipFile(DLDIR / "h97-masslever-candidate.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_tif, arcname=f"{name}.tif")

    fm = gates.format_report(out_tif, str(SAMPLE), footprint=valid)
    log("format: " + json.dumps({k: fm[k] for k in list(fm)[:8]}, default=str)[:400])
    own = {out_tif.name, "h97-masslever-candidate.tif"}
    priors, own_dropped = prior_list([SUBDIR, DLDIR, ROOT / "data/scored", ROOT / "data/reference"], own)
    log(f"uniqueness/lane priors: {len(priors)} (own copies dropped by name: {own_dropped})")
    uni = gates.uniqueness_report(dots, priors)
    lane = gates.lane_report(dots, valid, priors, sample=str(SAMPLE), phase="dots", log=log)
    mx_j = max([r.get("jaccard", 0.0) for r in uni["per_prior"] if "jaccard" in r] or [0.0])
    log(f"uniqueness: {uni['n_priors_checked']} checked, {uni['n_priors_compared']} comparable, "
        f"identical_to_a_prior={uni['identical_to_a_prior']}, max_jaccard={mx_j:.4f}, "
        f"incomparable={len(uni['incomparable_priors'])}")
    log(f"dots lane: literal {lane['literal']['verdict']} policy {lane['policy']['verdict']} "
        f"(max Spearman {lane['literal']['max_spearman']}, max near-3px {lane['literal']['max_near_3px_fraction']})")
    gates.write_report(EVID / "h97_format_gate.json", fm)
    gates.write_report(EVID / "h97_uniqueness.json", uni)
    gates.write_report(EVID / "h97_masslever_lane_dots.json", lane)

    # A-only geological reasoning (the brief's Phase-2 duty): every dot whose buried score
    # dominates its consensus score, with the named non-fault mimic and a falsifier.
    y, x = np.nonzero(dots)
    with rasterio.open(str(SAMPLE)) as ref:
        tr = ref.transform
    rows = []
    for i in range(len(y)):
        yy, xx = int(y[i]), int(x[i])
        r = 0.0
        if np.isfinite(buried[yy, xx]) and np.isfinite(cons[yy, xx]):
            r = float(buried[yy, xx]) - float(cons[yy, xx])
        if r <= 0:
            continue
        X, Y = tr * (xx + 0.5, yy + 0.5)
        rows.append(dict(row=yy, col=xx, easting_m=round(X, 1), northing_m=round(Y, 1),
                         buried_score=round(float(buried[yy, xx]), 4),
                         consensus_score=round(float(cons[yy, xx]), 4),
                         view_A_rank=round(float(a[yy, xx]), 4), view_B_rank=round(float(b[yy, xx]), 4),
                         b_only_artifact_score=round(float(art[yy, xx]), 4),
                         hypothesis="buried fault beneath cover: potential-field edge / cover-thickness"
                                    " step / strain step / seismicity lineation without a surface scarp",
                         named_mimic="lithologic contact or intrusive margin; basin-margin facies step;"
                                     " paleochannel; aftershock cluster",
                         falsifier="a mapped lithologic contact or a spring line at the same location"
                                   " with no offset in the potential-field edge",
                         phase2_action="field-check the trace continuation for offset geomorphology"))
    csv_path = SUBDIR / f"{name}-a-only-reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                           ["row", "col", "easting_m", "northing_m"])
        w.writeheader()
        w.writerows(rows)
    (DLDIR / f"{name}-a-only-reasoning.csv").write_bytes(csv_path.read_bytes())
    (SUBDIR / f"{name}-note.txt").write_text(f"name: {name}\nnote ({len(note)}/140): {note}\n")
    (DLDIR / f"{name}-note.txt").write_text((SUBDIR / f"{name}-note.txt").read_text())
    log(f"A-only reasoning rows: {len(rows):,} (buried-dominant dots {len(y):,} total)")
    out = dict(stage="write", registration=reg, submission_name=name, note=note,
               note_chars=len(note), tif=str(out_tif.relative_to(ROOT)),
               tif_bytes=int(out_tif.stat().st_size), sha256=sha256_file(out_tif),
               raster_pixel_sha256=hashlib.sha256(raster.tobytes()).hexdigest(),
               validator=fm, uniqueness=uni, lane_dots=lane,
               priors_checked=len(priors), own_copies_dropped_by_name=own_dropped,
               superseded_removed=removed,
               a_only_reasoning_rows=len(rows),
               a_only_reasoning_csv=str(csv_path.relative_to(ROOT)),
               writer_metadata=meta, generated_utc=now())
    write_ev("h97_write", out)
    return out


# ---------------------------------------------------------------------------------------------
# stage: card
# ---------------------------------------------------------------------------------------------
def stage_card():
    reg = check_prereg()
    ho = json.loads((EVID / "h97_masslever_holdout.json").read_text())
    inst = json.loads((EVID / "h97_masslever_instrument.json").read_text())
    build = json.loads((EVID / "h97_masslever_build.json").read_text())
    wr = json.loads((EVID / "h97_masslever_write.json").read_text())
    uni = wr["uniqueness"]
    lane = wr["lane_dots"]
    fm = wr["validator"]
    s = ho["pooled"]["scores"]
    sm = ho["pooled_mass_lever"]["scores"]
    gates_tbl = {
        "control_reproduction": dict(result="n/a", measured="no shared control re-run this round"),
        "leakage_canary": dict(result="PASS" if not any(ho["canary"]["alarm"].values()) else "FAIL",
                               measured=f"max single-channel out-of-quadrant AUC "
                                        f"{max(ho['canary']['max_auc'].values()):.4f}; alarm 0.90"),
        "independence": dict(result="PASS" if ho["independence"]["allow_exchange"] else "FAIL",
                             measured=f"max |rho| {ho['independence']['max_abs_correlation']:.4f} over "
                                      f"{ho['independence']['n_blocks']} blocks; abandon >= 0.60"),
        "holdout_promotion": dict(result="PASS" if ho["verdict_for_slot"] == "promote" else "FAIL",
                                  measured=f"primary {ho['primary_dti']:.6f} vs bar {ho['bar_to_beat']}; "
                                           f"paired CI low {ho['primary_paired_ci_low']:.6f}"),
        "format": dict(result=("PASS" if fm.get("ok") else "FAIL"),
                       measured=f"{fm.get('bands')} band {fm.get('dtype')}, {fm.get('crs')}, "
                                f"{fm.get('height')}x{fm.get('width')}, nan {fm.get('nan_pixels')}, "
                                f"inf {fm.get('infinity_pixels')}, range [{fm.get('min')}, {fm.get('max')}], "
                                f"emitted {fm.get('n_nonzero')}, nodata {fm.get('nodata')}; "
                                f"problems {fm.get('problems')}"),
        "uniqueness": dict(result=("PASS" if (uni.get("distinct_from_every_comparable_prior")
                                              and uni.get("audit_complete")) else "FAIL"),
                           measured=f"{uni.get('n_priors_checked')} priors checked, "
                                    f"{uni.get('n_priors_compared')} comparable, identical to a prior "
                                    f"{uni.get('identical_to_a_prior')}, max Jaccard "
                                    f"{max([r.get('jaccard', 0.0) for r in uni.get('per_prior', []) if 'jaccard' in r] or [0.0])}, "
                                    f"incomparable {len(uni.get('incomparable_priors', []))}"),
        "lane_surface": dict(result=build["surface_lane"]["policy"]["verdict"],
                             measured=f"max Spearman {build['surface_lane']['policy']['max_spearman']} "
                                      f"(bar 0.90)"),
        "lane_dots": dict(result=lane["policy"]["verdict"],
                          measured=f"max Spearman {lane['literal']['max_spearman']}, max near-3px "
                                   f"{lane['literal']['max_near_3px_fraction']}"),
        "not_the_union": dict(result="PASS" if not build["composition"]["is_merely_the_view_union"] else "FAIL",
                              measured=f"Jaccard vs spaced A/B union "
                                       f"{build['composition']['jaccard_vs_viewA_viewB_spaced_topk_union']:.4f}"),
    }
    # Any verdict that is not PASS is a failure: the lane gate returns DUPLICATE/STOP, not FAIL,
    # and treating that as a pass would let a duplicate be shipped with a clean gate table.
    failed = [k for k, v in gates_tbl.items() if v["result"] not in ("PASS", "n/a")]
    verdict = "promote" if not failed else "negative"
    card = dict(round="H97", generated_utc=now(), registration=reg,
                hypothesis="Two-view co-training (A geophysical, B surface incl. LiDAR scarp and "
                           "radiometric ratios) with disagreement as the discovery signal, emitted at "
                           "the metric-implied 25,400-dot mass lever; plus the first direct test of "
                           "whether the repository's holdout instrument ranks the board's own files.",
                mechanism="Concealed faults offset basement beneath cover: potential-field edges, "
                          "cover-thickness steps, strain steps and seismicity lineations register in "
                          "View A while DEM curvature and slope see no scarp; the radiometric ratios and "
                          "LiDAR scarp layers are the surface channels that answer a buried trace.",
                named_non_fault_mimic="lithologic contacts and intrusive margins; basin-margin facies "
                                      "steps; paleochannels; aftershock clusters; road cuts and erosion "
                                      "lines (the vetoed B-only population); DEM/radiometric acquisition seams",
                experiment_1_instrument=dict(
                    spearman_board_vs_holdout=inst["spearman_board_vs_holdout"],
                    partial_given_log_mass=inst["partial_board_vs_holdout_given_log_mass"],
                    spearman_board_vs_mass=inst["spearman_board_vs_mass"],
                    verdict=inst["verdict"], falsified=inst["falsified"],
                    withheld_positive_px=inst["withheld_positive_px"]),
                experiment_2_holdout=dict(
                    withheld_positive_px=ho["withheld_positive_px"],
                    matched_budget={k: dict(dti=s[k]["dti"], ci95=s[k]["ci95"]) for k in s},
                    mass_lever={k: dict(dti=sm[k]["dti"], ci95=sm[k]["ci95"]) for k in sm},
                    paired_vs_best_control=ho["pooled"]["paired_differences"]
                    [ho["pooled"]["best_comparable_control"]],
                    bar=ho["bar_to_beat"], verdict=ho["verdict_for_slot"]),
                experiment_3_gates=gates_tbl, failed_gates=failed, verdict=verdict,
                raster=dict(name=wr["submission_name"], sha256=wr["sha256"], bytes=wr["tif_bytes"],
                            note=wr["note"], note_chars=wr["note_chars"]),
                download_ok=True, submit_ok=bool(verdict == "promote"),
                slots_used=0,
                honesty=dict(bounded_by="the instrument and the restored bytes are integrity-pinned, "
                                        "not organizer-authenticated",
                             not_a_score="no leaderboard score is predicted anywhere in this card"))
    write_ev("h97_run_card", card)
    log("failed gates: " + json.dumps(failed))
    log(f"VERDICT {verdict}; download yes; submit {'YES' if verdict == 'promote' else 'NO'}")
    return card


STAGES = {"folds": stage_folds, "instrument": stage_instrument, "views": stage_views,
          "holdout": stage_holdout, "build": stage_build, "write": stage_write, "card": stage_card}


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    t0 = time.time()
    todo = list(STAGES) if which == "all" else [which]
    for name in todo:
        if name not in STAGES:
            raise SystemExit(f"unknown stage {name}; choose from {list(STAGES)}")
        log(f"=== {name} ===")
        STAGES[name]()
    log(f"done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
