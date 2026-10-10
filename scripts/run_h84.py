#!/usr/bin/env python3
"""H84 -- harmonic (elliptical) variogram anisotropy (HVA) on top of DVA-2, inside the co-training lane.

Preregistered in ``knowledge/74_hypotheses_H84_preregistered.md`` (frozen before any fit) and pinned by
``registry/h84_preregistration.json``; this runner refuses to start if the document's hash has moved.

Shared tools are reused, never forked: ``run_h61.setup / sample_for_fit / learner_for / to_grid /
pct_rank`` (cached feature stack, label-blind folds), ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1),
``gems52.nodes.spacing_select``, ``gems52.spatial.negative_block_errors / independence``,
``gems52.gates`` (lane, uniqueness, format), ``gems52.submission_writer``, ``run_h73.place_lane``, and
from ``run_h82``: ``Bank``, ``save_verified``, ``stitch``, ``restricted_registry``,
``restricted_supports`` and the exact DVA-2 design constants (bands, lags, fan, sigma).

Stages (checkpointed to work/h84 and evidence/h84_*.json):
    channels      50 DVA2 (control) + 25 HVA + 5 COH learner channels + 1 orientation diagnostic
    fit           leakage canary per channel per fold, then 5 arms x 4 folds (region-only prediction)
    holdout       matched-budget hide-and-recover pooled DTI with paired 95% CIs
    independence  the lane's spatial-block error-correlation test on single_A vs single_B
    build         stitched fields; A-only / B-only disagreement strata
    lane          surface lane gate (before placement), quota placement (E3), dot lane gate (after)
    write         GeoTIFF (0.0 outside footprint, no NaN), validator, uniqueness, not-the-union,
                  A-only reasoning CSV
    card          the single JSON run card, assembled only from receipts on disk

Usage: python scripts/run_h84.py [channels|fit|holdout|independence|build|lane|write|card|all]
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial                              # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h84_preregistration.json"
WORK = ROOT / "work/h84"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
K_FOLD = 9400
K_TOTAL = 37654
RING_M = 200.0
PREFIX = "gems52-h84-"

# design constants are imported, not retyped, so DVA2 here is H82's DVA2 by construction
BANDS, LAGS, FAN, SIGMA, PHI_DEG = h82.BANDS, h82.LAGS, h82.FAN, h82.SIGMA, h82.PHI_DEG
ARMS = ("single_B", "B_DVA2", "B_DVA2_HVA", "B_DVA2_HVA_COH", "single_A")
PRIMARY = "B_DVA2_HVA"
BEST = "B_DVA2"
CONTROL_TARGETS = {"single_B": 0.174517, "B_DVA2": 0.189200}
CONTROL_TOL = 1e-3

# h82.stitch reads its predictions from h82.WORK; point it at this round's checkpoints
h82.WORK = WORK

save_verified = h82.save_verified
Bank = h82.Bank


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h84_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H84 preregistration changed after freezing; re-pin registry/h84_preregistration.json")
    return reg


DVA2 = h82.DVA2
HVA = sorted(f"HVA_{nm}_h2amp_l{h}" for nm in BANDS.values() for h in LAGS)
COH = sorted(f"COH_{nm}" for nm in BANDS.values())
ARM_CHANNELS = {"single_B": [], "B_DVA2": DVA2, "B_DVA2_HVA": DVA2 + HVA,
                "B_DVA2_HVA_COH": DVA2 + HVA + COH, "single_A": []}


# --------------------------------------------------------------------------------------- harmonic operator
def harmonic_operator(phi_deg=PHI_DEG):
    """Fixed 3 x n least-squares operator M with [a, b, c] = M @ gamma for gamma(phi)=a+b cos2phi+c sin2phi."""
    ph = np.radians(np.asarray(phi_deg, np.float64))
    D = np.stack([np.ones_like(ph), np.cos(2 * ph), np.sin(2 * ph)], axis=1)
    M = np.linalg.solve(D.T @ D, D.T)
    return M, float(np.linalg.cond(D.T @ D))


def harmonic_stats(gammas, phi_deg=PHI_DEG):
    """Reference (non-streaming) implementation used by the unit test: returns a, b, c, h2amp."""
    M, _ = harmonic_operator(phi_deg)
    g = np.asarray(gammas, np.float64)
    a, b, c = (np.tensordot(M[i], g, axes=(0, 0)) for i in range(3))
    amp = np.where(a > 0, np.hypot(b, c) / np.maximum(a, 1e-300), 0.0)
    return a, b, c, amp


# --------------------------------------------------------------------------------------- stage: channels
def _band_names(nm):
    out = [f"{st}_{nm}_{k}_l{h}" for h in LAGS for st, k in (("DVA2", "aniso"), ("DVA2", "logvar"), ("HVA", "h2amp"))]
    out.append(f"COH_{nm}")
    if nm == "det_elev":
        out.append("THETA_det_elev_l2")
    return out


def _disk_digest(p):
    """SHA-256 read from disk: the file's cached pages are dropped first (IR-H84-003)."""
    fd = os.open(p, os.O_RDONLY)
    try:
        os.fsync(fd)
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)
    return digest(p)


def _compute_band(ds, b, nm, eligible, M, persist, stats, t0):
    zb = ds.read(b).astype(np.float64)
    ok = np.isfinite(zb) & eligible
    mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
    z = np.where(ok, (zb - mu) / sd, 0.0)
    w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
    del zb
    Sb = np.zeros(z.shape); Sc = np.zeros(z.shape); Sw = np.zeros(z.shape)
    for h in LAGS:
        mx = mn = sm = None
        A = np.zeros(z.shape); B = np.zeros(z.shape); C = np.zeros(z.shape)
        for k, (dy_u, dx_u) in enumerate(FAN):
            # identical to run_h82._gamma_stats (same roll, mask, normalisation and smoothing)
            dy, dx = dy_u * h, dx_u * h
            zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
            oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
            d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
            g = ndi.gaussian_filter(d2, SIGMA) / w
            del d2, zs, oks
            if mx is None:
                mx, mn, sm = g.copy(), g.copy(), g.copy()
            else:
                np.maximum(mx, g, out=mx); np.minimum(mn, g, out=mn); sm += g
            A += M[0, k] * g; B += M[1, k] * g; C += M[2, k] * g
            del g
        mean = sm / float(len(FAN))
        persist(f"DVA2_{nm}_aniso_l{h}", (mx - mn) / (mx + mn + 1e-9))
        persist(f"DVA2_{nm}_logvar_l{h}", np.log10(mean + 1e-9))
        pos = A > 1e-12
        amp = np.where(pos, np.hypot(B, C) / np.where(pos, A, 1.0), 0.0)
        persist(f"HVA_{nm}_h2amp_l{h}", amp)
        stats[f"HVA_{nm}_h2amp_l{h}"] = dict(
            a_nonpositive_px_eligible=int((~pos & eligible).sum()),
            amp_p50=float(np.median(amp[eligible])), amp_p99=float(np.quantile(amp[eligible], 0.99)))
        inv = np.where(pos, 1.0 / np.where(pos, A, 1.0), 0.0)
        Sb += B * inv; Sc += C * inv; Sw += np.hypot(B, C) * inv
        if nm == "det_elev" and h == 2:
            # orientation of maximum semivariance (image frame, radians, axial) -> diagnostic only,
            # used by the B-only road/section-line audit; never a learner channel
            persist("THETA_det_elev_l2", 0.5 * np.arctan2(C, B))
        del mx, mn, sm, mean, A, B, C, amp, inv, pos
        log(f"band {b} {nm} lag {h}: done ({time.time()-t0:.0f}s)")
    coh = np.where(Sw > 1e-12, np.hypot(Sb, Sc) / np.where(Sw > 1e-12, Sw, 1.0), 0.0)
    persist(f"COH_{nm}", coh)
    stats[f"COH_{nm}"] = dict(p50=float(np.median(coh[eligible])), p99=float(np.quantile(coh[eligible], 0.99)))
    del z, ok, w, Sb, Sc, Sw, coh


def stage_channels(max_passes: int = 4):
    """Build every channel, then audit every file from disk and recompute any band whose file moved.

    IR-H84-003: under this stage's write+memory load, files that had passed a disk-level verified write
    were later found with bytes 128-4095 (the rest of the header's first 4 KiB page) zeroed - 16/81 files
    in the first build, 65/81 in the second. Not reproducible on a quiet system (8/8 intact after 100 s,
    both np.save and structural.save_array). The stage therefore writes through the shared store's atomic
    writer and re-audits; it only returns when every file's on-disk digest equals its in-memory digest.
    """
    from gems52.structural import save_array
    check_prereg()
    FEAT.mkdir(parents=True, exist_ok=True)
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    M, cond = harmonic_operator()
    t0 = time.time()
    sha, stats, history = {}, {}, []

    def persist(name, grid):
        v = np.ascontiguousarray(np.asarray(grid, np.float32)[eligible])
        save_array(FEAT / (name + ".npy"), v)
        sha[name] = digest(FEAT / (name + ".npy"))
        # the file digest of a correct write is reproducible from the array alone: keep that as the pin
        sha[name + "#array"] = hashlib.sha256(v.tobytes()).hexdigest()

    todo = dict(BANDS)
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for npass in range(1, max_passes + 1):
            for b, nm in todo.items():
                _compute_band(ds, b, nm, eligible, M, persist, stats, t0)
            time.sleep(5.0)
            moved = {}
            for b, nm in BANDS.items():
                for n in _band_names(nm):
                    p = FEAT / (n + ".npy")
                    a = np.load(p, mmap_mode="r")
                    ok_arr = hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest() == sha[n + "#array"]
                    if not ok_arr or _disk_digest(p) != sha[n]:
                        moved.setdefault(b, []).append(n)
            history.append(dict(pass_=npass, recomputed_bands=sorted(int(k) for k in todo),
                                files_moved_after_write=sum(len(v) for v in moved.values()),
                                moved=moved))
            log(f"audit pass {npass}: {sum(len(v) for v in moved.values())} files moved after write")
            if not moved:
                break
            todo = {b: BANDS[b] for b in moved}
        else:
            raise SystemExit(f"IR-H84-003: channel files still moving after {max_passes} passes: {history[-1]}")
    pins = {k: v for k, v in sha.items() if not k.endswith("#array")}
    man = dict(round="H84", created_utc=now(), version="h84-dva2-hva-coh-v1", sigma_px=SIGMA,
               lags_px=list(LAGS), fan_offsets_dy_dx=[list(t) for t in FAN], fan_phi_deg_image_frame=list(PHI_DEG),
               harmonic_operator=M.tolist(), normal_matrix_condition_number=cond,
               bands={str(k): v for k, v in BANDS.items()},
               learner_channels=dict(dva2=DVA2, hva=HVA, coh=COH), diagnostics_not_learner=["THETA_det_elev_l2"],
               n_eligible=int(store.valid.sum()), sha256=pins,
               array_sha256={k[:-6]: v for k, v in sha.items() if k.endswith("#array")},
               writer="gems52.structural.save_array (atomic tmp+fsync+rename) + disk-level audit loop",
               audit_history=history, stats=stats, inputs_sha256=dict(store.manifest["inputs"]))
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    write("channels", dict(stage="channels", n_columns=len(pins), learner_new=HVA + COH, dva2_control=len(DVA2),
                           condition_number=cond, stats=stats, audit_history=history,
                           file_sha256=pins, array_sha256=man["array_sha256"],
                           seconds=time.time() - t0, finished_utc=now()))
    log(f"channels: {len(pins)} columns in {time.time()-t0:.0f}s; cond(DtD)={cond:.3f}")


class RamBank:
    """Verified channels held in RAM for the fit, so later on-disk page loss cannot reach a model."""

    def __init__(self, directory: Path, names):
        man = json.loads((Path(directory) / "manifest.json").read_text())
        self.cols = {}
        for n in names:
            a = np.load(Path(directory) / (n + ".npy"))
            if hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest() != man["array_sha256"][n]:
                raise ValueError(f"channel byte-integrity failure (IR-H84-003): {n}")
            self.cols[n] = a

    def col(self, name):
        return self.cols[name]

    def gather(self, rows, names, fold=None):
        out = np.empty((len(rows), len(names)), np.float32)
        for j, nm in enumerate(names):
            out[:, j] = self.cols[nm][rows]
        return np.nan_to_num(out, nan=0.0)


# --------------------------------------------------------------------------------------- stage: fit
def gather_arm(store, bank, rows_grid, names_store, names_ch):
    X = store.gather(rows_grid, names_store)
    if names_ch:
        X = np.hstack([X, bank.gather(store.inverse[rows_grid], names_ch)])
    return X


def predict_region(store, bank, model, names_store, names_ch, rows_grid, chunk=200_000):
    out = np.empty(len(rows_grid), np.float32)
    for i in range(0, len(rows_grid), chunk):
        s = rows_grid[i:i + chunk]
        out[i:i + chunk] = model.predict_proba(gather_arm(store, bank, s, names_store, names_ch))[:, 1]
    return out


def stage_fit():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    bank = RamBank(FEAT, sorted(DVA2 + HVA + COH))
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", started_utc=now(), arms=list(ARMS), seed=SEED, folds=[])
    for fold in folds:
        f = fold["fold"]
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_region_rows=int(len(region_rows)), n_train_rows=int(len(rows)),
                   n_pos=int(len(pos_g)), n_neg=int(len(neg_g)), auc={}, canary={}, seconds={})
        erow = store.inverse[np.r_[pos_g, neg_g]]
        for nm in sorted(DVA2 + HVA + COH):
            v = np.asarray(bank.col(nm)[erow], np.float64)
            a = float(roc_auc_score(yy, v)) if np.isfinite(v).all() and np.ptp(v) > 0 else 0.5
            rec["canary"][nm] = dict(auc=a, direction_insensitive=max(a, 1 - a), new_this_round=nm not in DVA2)
            del v
        rec["canary_max_learner"] = max(v["direction_insensitive"] for v in rec["canary"].values())
        rec["canary_max_new"] = max(v["direction_insensitive"] for v in rec["canary"].values() if v["new_this_round"])
        rec["canary_worst"] = max(rec["canary"].items(), key=lambda kv: kv[1]["direction_insensitive"])[0]
        rec["canary_alarm"] = bool(rec["canary_max_learner"] >= reg["canary_alarm_auc"])
        log(f"fold {f}: canary max {rec['canary_max_learner']:.4f} ({rec['canary_worst']}) new max "
            f"{rec['canary_max_new']:.4f} alarm={rec['canary_alarm']}")
        for arm in ARMS:
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if not ck.exists():
                names_store = va if arm == "single_A" else vb
                m = base.learner_for("A" if arm == "single_A" else "B", SEED)
                m.fit(gather_arm(store, bank, rows, names_store, ARM_CHANNELS[arm]), y)
                p = predict_region(store, bank, m, names_store, ARM_CHANNELS[arm], region_rows)
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                save_verified(ck, full)
                del m, p, full
            g = np.asarray(np.load(ck, mmap_mode="r"), np.float32)
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[store.inverse[pos_g]], g[store.inverse[neg_g]]]))
            rec["seconds"][arm] = time.time() - t1
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g
        out["folds"].append(rec)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_learner_overall"] = max(r["canary_max_learner"] for r in out["folds"])
    out["canary_max_new_overall"] = max(r["canary_max_new"] for r in out["folds"])
    out["canary_alarm_auc_bar"] = reg["canary_alarm_auc"]
    sa = [r["auc"]["single_A"] for r in out["folds"]]
    out["sufficiency_view_A"] = dict(mean=float(np.mean(sa)), min_fold=float(np.min(sa)), per_fold=sa,
                                     gate_mean=0.60, gate_min_fold=0.55,
                                     passes=bool(np.mean(sa) >= 0.60 and np.min(sa) >= 0.55))
    out["finished_utc"] = now()
    write("fit", out)
    log(json.dumps({"canary_max": out["canary_max_learner_overall"], "sufficiency_A": out["sufficiency_view_A"],
                    "auc": {a: [round(r["auc"][a], 4) for r in out["folds"]] for a in ARMS}}))


# --------------------------------------------------------------------------------------- stage: holdout
def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def stage_holdout():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    arms = tuple(ARMS) + ("random",)
    terms = {a: None for a in arms}
    out = dict(stage="holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), folds=[], started_utc=now())
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        rec = dict(fold=f, arms={})
        for arm in arms:
            fld = np.full(eligible.shape, -1.0, np.float32)
            if arm == "random":
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                g = base.to_grid(store.flat_idx, np.load(WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
                fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
                del g
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del fld, em
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    out["controls"] = {}
    for arm, target in CONTROL_TARGETS.items():
        got = float(out["pooled"]["scores"][arm]["dti"])
        out["controls"][arm] = dict(committed=target, measured=got, abs_delta=abs(got - target),
                                    tolerance=CONTROL_TOL, PASS=bool(abs(got - target) <= CONTROL_TOL))
    # the attribution arm's own paired comparison against the primary, same draws/seed
    out["attribution_pooled"] = evaluator.pooled_summary(
        {k: terms[k] for k in ("B_DVA2_HVA_COH", "B_DVA2", "single_B", PRIMARY)},
        draws=1000, seed=SEED, candidate="B_DVA2_HVA_COH")
    out["paired_differences_keyed_by"] = "comparison arm; each entry is candidate minus that arm"
    out["finished_utc"] = now()
    write("holdout", out)
    pdiff = out["pooled"]["paired_differences"]
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in arms}))
    log("controls: " + json.dumps(out["controls"], default=float))
    log("primary paired: " + json.dumps({k: [round(v["delta"], 6)] + [round(x, 6) for x in v["ci95"]]
                                          for k, v in pdiff.items()}, default=float))


# ---------------------------------------------------------------------------------- stage: independence
def stage_independence():
    """The brief's test: correlate each view's spatial-block OOF errors on labelled negatives."""
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th_src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    blocks_all, per_fold = [], []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        thr = (float(np.quantile(pa[neg], th["donor_rank_min"])), float(np.quantile(pb[neg], th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        blocks_all += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr), n_blocks=len(blocks)))
        log(f"fold {f}: {len(blocks)} blocks over {int(neg.sum())} labelled negatives")
        del pa, pb
    res = spatial.independence(blocks_all, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    out = dict(stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
               thresholds_inherited_from=str(th_src.relative_to(ROOT)), thresholds_inherited_sha256=digest(th_src),
               thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"], min_blocks=20,
                               negative_ring_px=4),
               view_A="single_A (store view_A_with_external)", view_B="single_B (store view_B_with_external)",
               per_fold=per_fold, result=res,
               caveat=("negatives are catalogue-zero proxies, not verified absence; weak error correlation is "
                       "necessary for co-training, not proof of conditional independence"))
    write("independence", out)
    log(json.dumps({k: res[k] for k in res if not isinstance(res[k], (list, dict))}, default=float))


# --------------------------------------------------------------------------------------- stage: build
def stage_build():
    check_prereg()
    reg = json.loads(PREREG.read_text())
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fP = h82.stitch(PRIMARY, folds, eligible, flat)
    fA = h82.stitch("single_A", folds, eligible, flat)
    fB = h82.stitch("single_B", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fP) & (catd * 100.0 > RING_M)
    save_verified(WORK / "surface.npy", np.where(eligible & np.isfinite(fP), fP, 0.0).astype(np.float32))
    save_verified(WORK / "field_primary.npy", fP)
    save_verified(WORK / "field_A.npy", fA)
    save_verified(WORK / "field_B.npy", fB)
    save_verified(WORK / "pool.npy", pool)
    # disagreement strata (the lane's discovery signal), on the emission pool
    sA = reg["a_only_stratum"]
    lo, hi = sA["primary_rank_band"]
    a_only = pool & np.isfinite(fA) & (fA >= sA["A_rank_min"]) & (fP >= lo) & (fP <= hi)
    b_only = pool & np.isfinite(fA) & (fP >= sA["A_rank_min"]) & (fA >= lo) & (fA <= hi)
    a_cand = nodes.spacing_select(np.where(a_only, fA, -1.0).astype(np.float32), a_only,
                                  int(a_only.sum()), min_px=sA["spacing_px"])
    b_cand = nodes.spacing_select(np.where(b_only, fP, -1.0).astype(np.float32), b_only,
                                  int(b_only.sum()), min_px=sA["spacing_px"])
    save_verified(WORK / "a_only_candidates.npy", a_cand)
    save_verified(WORK / "b_only_candidates.npy", b_cand)
    # road / section-line audit of B-only candidates: strike = axis of MIN semivariance = theta_max + 90 deg
    bank = RamBank(FEAT, ["THETA_det_elev_l2"])
    ys, xs = np.nonzero(b_cand)
    th = np.asarray(bank.col("THETA_det_elev_l2")[store.inverse[ys * eligible.shape[1] + xs]], np.float64)
    strike = np.degrees(th + np.pi / 2.0) % 180.0
    dcard = np.minimum.reduce([np.abs(strike - 0.0), np.abs(strike - 90.0), np.abs(strike - 180.0)])
    cardinal = float((dcard <= 5.0).mean()) if len(dcard) else None
    rec = dict(stage="build", pool_px=int(pool.sum()), eligible_px=int(eligible.sum()), ring_excluded_m=RING_M,
               a_only_stratum_px=int(a_only.sum()), a_only_candidates=int(a_cand.sum()),
               b_only_stratum_px=int(b_only.sum()), b_only_candidates=int(b_cand.sum()),
               b_only_cardinal_strike_within_5deg_fraction=cardinal,
               b_only_cardinal_null_fraction=20.0 / 180.0,
               b_only_audit_note=("Nevada section-line roads and fences run N-S/E-W; a B-only population strongly "
                                  "enriched above the isotropic null 20/180 = 0.111 would support the brief's "
                                  "road/erosion-line reading. Image frame: x east, y south; the cardinal set is "
                                  "frame-invariant."),
               stratum_rule=sA, started_utc=now())
    write("build_placement", rec)
    log(json.dumps(rec, default=float))


# --------------------------------------------------------------------------------------- stage: lane
def full_registry():
    from build_h61_submission import prior_paths
    full, meta = prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    extra = sorted((ROOT / "data/scored").glob("*.tif")) + sorted((ROOT / "data/reference").glob("*.tif"))
    seen, out = set(), []
    for p in full + extra:
        if p.exists() and PREFIX not in p.name and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    meta["extra_scored_reference"] = len(extra)
    return out, meta


def stage_lane():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    import run_h73 as h73
    h73.H73 = json.loads((ROOT / "registry/h73_preregistration.json").read_text())
    surf = np.load(WORK / "surface.npy")
    pool = np.load(WORK / "pool.npy")
    full, meta = full_registry()
    restr, scored = h82.restricted_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full), n_restricted=len(restr),
               doctrine=("both registries reported verbatim; a restricted-registry PASS never waives a literal "
                         "full-census DUPLICATE/STOP (AGENTS.md, knowledge/62 IR-H73-011)"))
    log(f"lane: full census {len(full)} rasters, scored-only {len(restr)} rasters")
    # 1) surface BEFORE placement
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface", log=log)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface")
    write("lane", out)
    if out["full_surface"]["literal"]["verdict"].upper().startswith("DUPLICATE"):
        out["stopped"] = "surface literal DUPLICATE -> logged as duplicate, stopped before placement"
        write("lane", out)
        log(out["stopped"])
        return
    # 2) E3 quota placement against the scored-only informative supports
    sups, suprows = h82.restricted_supports(restr, eligible)
    out["restricted_supports"] = suprows
    fld = np.where(pool, surf, -1.0).astype(np.float32)
    lane_dots, lrec = h73.place_lane(fld, pool, K_TOTAL, sups, eligible.shape, limit=0.70, rounds=8)
    out["quota_placement"] = lrec
    if int(lane_dots.sum()) == K_TOTAL:
        dots, out["emitted_placement"] = lane_dots, "quota (run_h73.place_lane, scored-only supports)"
    else:
        dots = nodes.spacing_select(fld, pool, K_TOTAL, min_px=3.0)
        out["emitted_placement"] = f"fallback spacing_select (quota short-filled at {int(lane_dots.sum())})"
    save_verified(WORK / "dots.npy", dots)
    out["dots"] = int(dots.sum())
    # 3) dots AFTER placement, on the emitted dots
    df = dots.astype(np.float32)
    out["full_dots"] = gates.lane_report(df, eligible, full, sample=SAMPLE, phase="dots", log=log)
    out["restricted_dots"] = gates.lane_report(df, eligible, restr, sample=SAMPLE, phase="dots")
    out["uniqueness_full"] = gates.uniqueness_report(df, full)
    out["finished_utc"] = now()
    write("lane", out)
    for k in ("full_surface", "restricted_surface", "full_dots", "restricted_dots"):
        r = out[k]
        log(f"{k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, max near "
            f"{r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']}")


# --------------------------------------------------------------------------------------- stage: write
A_BANDS = {13: "iso_grav_anom", 18: "iso_grav_anom_hg", 15: "depth_to_base_surf", 1: "mag_anom",
           4: "geod_2ndinv", 16: "ieq_n100a15", 17: "cond_surf"}
A_MECH = {
    "iso_grav_anom": ("isostatic gravity anomaly is extreme here while the surface view is undecided: a "
                      "density step consistent with a buried basin-bounding normal fault under alluvium",
                      "lithologic density contrast at a buried depositional contact or basin-fill facies change"),
    "iso_grav_anom_hg": ("steep isostatic-gravity horizontal gradient under subdued topography: the classic "
                         "signature of a concealed range-front or intra-basin normal fault",
                         "gradient along a buried erosional basement slope or intrusive contact, no offset"),
    "depth_to_base_surf": ("depth-to-basement is anomalous relative to its surroundings: a basement step "
                           "beneath cover consistent with a fault-bounded half-graben margin",
                           "inversion artefact of the gravity-derived basement model; buried paleotopography"),
    "mag_anom": ("magnetic anomaly is extreme under quiet topography: a truncated magnetic body consistent "
                 "with a fault offsetting buried volcanic or basement rocks",
                 "buried volcanic flow margin, dyke, or remanent-magnetised body without fault offset"),
    "geod_2ndinv": ("geodetic strain-rate second invariant is elevated: active distributed deformation "
                    "that may localise on an unmapped structure",
                    "smoothing/interpolation gradient of the GNSS strain-rate grid (tens of km wavelength)"),
    "ieq_n100a15": ("earthquake density is elevated: microseismicity that may outline a blind fault",
                    "swarm or aftershock cloud not tied to one plane; catalogue-completeness artefact"),
    "cond_surf": ("subsurface conductivity anomaly: fluid-filled damage zone or hydrothermal alteration "
                  "along a buried fault",
                  "conductive clay-rich basin fill or saline groundwater without a fault"),
}


def write_a_only_reasoning(store, cand, fA, fP, catd, eligible, name):
    ys, xs = np.nonzero(cand)
    p = ROOT / "docs/downloads" / f"gems52-{name}-a-only-reasoning.csv"
    with rasterio.open(SAMPLE) as s:
        tr = s.transform
    z = {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in A_BANDS.items():
            a = ds.read(b).astype(np.float64)
            ok = np.isfinite(a) & eligible
            mu, sd = float(a[ok].mean()), float(a[ok].std()) + 1e-12
            z[nm] = (a[ys, xs] - mu) / sd
            del a, ok
    Z = np.stack([np.abs(z[nm]) for nm in A_BANDS.values()])
    names = list(A_BANDS.values())
    dom = [names[i] for i in Z.argmax(0)]
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "view_A_rank", "primary_view_B_rank",
                    "dist_to_mapped_catalogue_m", "dominant_view_A_band"] + [f"z_{nm}" for nm in names] +
                   ["geological_reasoning", "named_non_fault_process_that_could_mimic_it", "falsifier",
                    "confidence_note", "evidence_class"])
        for i in range(len(ys)):
            mech, mimic = A_MECH[dom[i]]
            w.writerow([int(ys[i]), int(xs[i]), round(float(tr.c + (xs[i] + 0.5) * tr.a), 1),
                        round(float(tr.f + (ys[i] + 0.5) * tr.e), 1), round(float(fA[ys[i], xs[i]]), 5),
                        round(float(fP[ys[i], xs[i]]), 5), round(float(catd[ys[i], xs[i]] * 100.0), 1), dom[i]] +
                       [round(float(z[nm][i]), 3) for nm in names] +
                       [f"A-only (buried-fault reading): {mech}", mimic,
                        "a seismic-reflection, gravity or MT profile across the cell shows no basement offset, "
                        "or 1-m LiDAR / field mapping shows unfaulted Quaternary cover with no buried step",
                        "LOW: View A failed sufficiency in H84 (see run card) and H77cond measured View A to be "
                        "least informative where View B is blind; treat as a reviewer lead, not a detection",
                        "model evidence for a Phase-2 reviewer target; NOT an organizer-confirmed fault"])
    return str(p.relative_to(ROOT)), int(len(ys))


def _spearman_sub(a, b, eligible, step=7):
    from scipy.stats import spearmanr
    m = eligible.ravel()[::step]
    return float(spearmanr(a.ravel()[::step][m], b.ravel()[::step][m]).statistic)


def stage_write():
    check_prereg()
    from gems52 import submission_writer
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    ln = json.loads((EVID / "h84_lane.json").read_text())
    if "stopped" in ln:
        raise SystemExit("lane stopped before placement; no raster is written (duplicate logged)")
    dots = np.load(WORK / "dots.npy").astype(bool)
    pool = np.load(WORK / "pool.npy")
    fP, fA, fB = (np.load(WORK / f"field_{k}.npy") for k in ("primary", "A", "B"))
    catd = ndi.distance_transform_edt(~cat)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h84-hva-ellipse-B-{int(dots.sum())}px-{stamp}"
    note = ("H84: View-B + DVA2 + harmonic variogram-ellipse anisotropy (8-dir LS fit, lags 100-600m); "
            "200m ring cut; binary dots; research")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    pred = dots.astype(np.float32)          # exactly {0,1}; 0.0 outside the footprint; no NaN anywhere
    rec = submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                             metadata=dict(round="H84", primary_arm=PRIMARY))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nodata=a.nodata, nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   nan_inside_footprint=int(np.isnan(v[eligible]).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()),
                   ones_outside_footprint=int(((v == 1) & ~eligible).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"] and val["shape_match"]
                       and val["transform_match"] and val["bounds_match"] and val["range_ok"]
                       and val["ones_outside_footprint"] == 0)
    val["rule_source"] = ("https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ (single band "
                          "float32, EPSG:32611, 100 m, values in [0,1]); portal message 'Predicted values must be in "
                          "range [0, 1]' -> no NaN written (knowledge/03 N-5)")
    # not-the-union, at equal budget on the same pool
    a_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fA, nan=-1.0), -1.0).astype(np.float32), pool,
                                  K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fB, nan=-1.0), -1.0).astype(np.float32), pool,
                                  K_TOTAL, min_px=3.0)
    union_field = np.where(pool, np.maximum(np.nan_to_num(fA, nan=-1.0), np.nan_to_num(fB, nan=-1.0)), -1.0)
    u_dots = nodes.spacing_select(union_field.astype(np.float32), pool, K_TOTAL, min_px=3.0)

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    nu = dict(dots_emitted=int(dots.sum()), union_max_dots=int(u_dots.sum()),
              dots_equal_union=bool(np.array_equal(dots, u_dots)),
              dots_subset_of_union=bool(not (dots & ~u_dots).any()),
              dots_equal_single_A=bool(np.array_equal(dots, a_dots)),
              dots_equal_single_B=bool(np.array_equal(dots, b_dots)),
              shared_with_union=int((dots & u_dots).sum()), jaccard_with_union=jac(dots, u_dots),
              shared_with_single_A=int((dots & a_dots).sum()), jaccard_with_single_A=jac(dots, a_dots),
              shared_with_single_B=int((dots & b_dots).sum()), jaccard_with_single_B=jac(dots, b_dots),
              spearman_primary_field_vs_unionmax_field=_spearman_sub(np.nan_to_num(fP, nan=0.0),
                                                                     np.nan_to_num(union_field, nan=0.0), eligible))
    nu["not_union_pass"] = bool(not nu["dots_equal_union"] and not nu["dots_subset_of_union"]
                                and not nu["dots_equal_single_A"] and not nu["dots_equal_single_B"])
    cmp = {}
    for key, p in (("ref_h33_2_b2_owner_reported_0.2778", "data/reference/h33-2-b2-zeros.tif"),
                   ("h82_candidate", "docs/downloads/h82-candidate.tif")):
        pp = ROOT / p
        if pp.exists():
            with rasterio.open(pp) as d:
                r = np.nan_to_num(d.read(1)) > 0
            near = ndi.binary_dilation(r, structure=gates._disk(3.0))
            cmp[key] = dict(shared_px=int((r & dots).sum()), prior_px=int(r.sum()),
                            near_3px_share_of_my_dots=float(near[dots].mean()), jaccard=jac(dots, r))
    a_cand = np.load(WORK / "a_only_candidates.npy").astype(bool)
    a_csv, n_a = write_a_only_reasoning(store, a_cand, fA, fP, catd, eligible, name)
    res = dict(stage="write", file=str(out.relative_to(ROOT)), bytes=out.stat().st_size, sha256=digest(out),
               name=name, note=note, note_chars=len(note), validator=val, writer_receipt=rec,
               not_the_union=nu, vs_named_priors=cmp,
               catalogue=dict(min_dist_m=float((catd[dots] * 100).min()),
                              median_dist_m=float(np.median(catd[dots] * 100)),
                              within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100)),
               a_only_reasoning_csv=a_csv, a_only_rows=n_a, started_utc=now())
    dl = ROOT / "docs/downloads"
    shutil.copy(out, dl / "h84-candidate.tif")
    with zipfile.ZipFile(dl / "h84-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, out.name)
    with zipfile.ZipFile(dl / "h84-candidate.zip") as z:
        assert z.namelist() == [out.name] and z.read(out.name) == out.read_bytes()
    res["download_staged"] = dict(tif="docs/downloads/h84-candidate.tif", zip="docs/downloads/h84-candidate.zip",
                                  tif_sha256=digest(dl / "h84-candidate.tif"),
                                  zip_sha256=digest(dl / "h84-candidate.zip"))
    write("build", res)
    log(json.dumps({k: res[k] for k in ("file", "bytes", "sha256", "name", "note")}, indent=1))
    log("validator: " + json.dumps({k: val[k] for k in ("PASS", "nan", "min", "max", "ones")}))
    log("not_union: " + json.dumps(nu, default=float))


# --------------------------------------------------------------------------------------- stage: card
def stage_card():
    reg = check_prereg()
    ch = json.loads((EVID / "h84_channels.json").read_text())
    fit = json.loads((EVID / "h84_fit.json").read_text())
    ho = json.loads((EVID / "h84_holdout.json").read_text())
    ind = json.loads((EVID / "h84_independence.json").read_text())
    bp = json.loads((EVID / "h84_build_placement.json").read_text())
    ln = json.loads((EVID / "h84_lane.json").read_text())
    bu = json.loads((EVID / "h84_build.json").read_text()) if (EVID / "h84_build.json").exists() else None
    sc = ho["pooled"]["scores"]
    pdf = ho["pooled"]["paired_differences"]
    vs_best, vs_b = pdf[BEST], pdf["single_B"]
    controls_ok = all(ho["controls"][a]["PASS"] for a in CONTROL_TARGETS)
    lit_s = ln["full_surface"]["literal"]["verdict"]
    lit_d = ln.get("full_dots", {}).get("literal", {}).get("verdict", "NOT RUN")
    reasons = dict(
        beats_current_holdout_best_B_DVA2=bool(vs_best["ci95"][0] > 0),
        beats_single_B=bool(vs_b["ci95"][0] > 0), controls_reproduce=controls_ok,
        canary_no_alarm=not fit["canary_alarm_any"],
        lane_surface_literal_pass=not lit_s.upper().startswith("DUPLICATE"),
        lane_dots_literal_full_census_pass=not str(lit_d).upper().startswith(("DUPLICATE", "NOT")),
        format_validator_pass=bool(bu and bu["validator"]["PASS"]),
        not_the_union_pass=bool(bu and bu["not_the_union"]["not_union_pass"]))
    promote = all(reasons.values())
    S = lambda a: dict(dti=sc[a]["dti"], ci95=sc[a]["ci95"], label="HOLDOUT-DTI")  # noqa: E731
    card = dict(
        round="H84", generated_utc=now(),
        hypothesis=("A fault zone makes the spatial covariance of elevation, slope, gravity and basement-depth "
                    "fields elliptical with its long axis along strike; the eccentricity of that ellipse, "
                    "fitted continuously from 8 directional semivariances at 100-600 m lags, ranks unmapped "
                    "fault cells better than the quantised (max-min)/(max+min) DVA-2 statistic."),
        mechanism=("Damage zones, juxtaposed blocks and cover-thickness steps leave low semivariance along strike "
                   "and high semivariance across it. Under geometric anisotropy gamma(h,theta) = a + b cos2theta "
                   "+ c sin2theta at fixed lag, so sqrt(b^2+c^2)/a is the ellipse eccentricity; a fixed 3x8 "
                   "least-squares operator estimates it from all 8 directions rather than 2 order statistics."),
        mimic=("Named non-fault processes with the same signature: linear drainage incision and road cuts "
               "(anisotropic elevation texture), alluvial-fan margins and lithologic contacts (anisotropic "
               "gravity/basement fields with no offset). B-only road audit result is in disagreement below."),
        preregistration=dict(document=reg["hypothesis_document"], sha256=reg["hypothesis_sha256"],
                             frozen_utc=reg["preregistered_utc"], frozen_before_any_fit=True),
        channels=dict(new_learner=len(ch["learner_new"]), hva=len(HVA), coh=len(COH), dva2_control=len(DVA2),
                      normal_matrix_condition_number=ch["condition_number"]),
        canary=dict(label="LEAKAGE CANARY (single-channel AUC on held-out region; bar 0.90)",
                    max_all_learner=fit["canary_max_learner_overall"], max_new=fit["canary_max_new_overall"],
                    alarm=fit["canary_alarm_any"]),
        out_of_quadrant_auc={a: [r["auc"][a] for r in fit["folds"]] for a in ARMS},
        holdout=dict(label="HOLDOUT-DTI", evaluator=ho["evaluator"],
                     withheld_positive_pixels=ho["withheld_positive_px"], dots_per_fold_per_arm=ho["budget_per_fold"],
                     ci="95% paired cluster bootstrap, 1000 draws", scores={a: S(a) for a in sc},
                     primary_minus_each_arm={k: dict(delta=v["delta"], ci95=v["ci95"]) for k, v in pdf.items()},
                     attribution_COH_minus_each_arm={k: dict(delta=v["delta"], ci95=v["ci95"])
                                                     for k, v in ho["attribution_pooled"]["paired_differences"].items()},
                     controls=ho["controls"],
                     never_a_board_forecast="holdout DTI does not rank board scores here (Spearman -0.10, knowledge/10)"),
        cotraining=dict(independence=dict(max_abs_rho=ind["result"].get("max_abs_correlation"),
                                          allow_exchange=ind["result"].get("allow_exchange"),
                                          n_blocks=sum(r["n_blocks"] for r in ind["per_fold"]),
                                          abandon_bar=ind["thresholds"]["abandon_max_abs_rho"], caveat=ind["caveat"]),
                        sufficiency_view_A=fit["sufficiency_view_A"],
                        exchange_run=False,
                        exchange_not_run_reason=("no sufficient donor view: View A's out-of-quadrant AUC fails the "
                                                 "0.60 mean / 0.55 min-fold gate (re-measured above); H71/H74 measured "
                                                 "that exchange lowered the receiving view's AUC")),
        disagreement=dict(a_only_stratum_px=bp["a_only_stratum_px"], a_only_candidates=bp["a_only_candidates"],
                          a_only_reasoning_csv=(bu or {}).get("a_only_reasoning_csv"),
                          b_only_candidates=bp["b_only_candidates"],
                          b_only_cardinal_fraction=bp["b_only_cardinal_strike_within_5deg_fraction"],
                          b_only_cardinal_null=bp["b_only_cardinal_null_fraction"]),
        lane=dict(full_census_rasters=ln["n_full"], scored_only_rasters=ln["n_restricted"],
                  surface_literal=lit_s, surface_max_spearman=ln["full_surface"]["literal"]["max_spearman"],
                  surface_scored_only=ln["restricted_surface"]["literal"]["verdict"],
                  emitted_placement=ln.get("emitted_placement"),
                  quota_worst_share=(ln.get("quota_placement") or {}).get("worst"),
                  dots_literal=lit_d,
                  dots_max_spearman=ln.get("full_dots", {}).get("literal", {}).get("max_spearman"),
                  dots_max_near_3px=ln.get("full_dots", {}).get("literal", {}).get("max_near_3px_fraction"),
                  dots_policy=ln.get("full_dots", {}).get("policy", {}).get("verdict"),
                  dots_policy_max_near_3px=ln.get("full_dots", {}).get("policy", {}).get("max_near_3px_fraction"),
                  dots_scored_only=ln.get("restricted_dots", {}).get("literal", {}).get("verdict"),
                  dots_scored_only_max_near_3px=ln.get("restricted_dots", {}).get("literal", {}).get("max_near_3px_fraction"),
                  doctrine=ln["doctrine"]),
        uniqueness={k: ln.get("uniqueness_full", {}).get(k) for k in (
            "n_priors_compared", "audit_complete", "distinct_from_every_comparable_prior", "identical_to_a_prior",
            "candidate_decoded_sha256", "support_novelty_gate_ok", "novel_fraction", "relation_to_union",
            "research_publication_ok", "gate_correction")},
        not_the_union=(bu or {}).get("not_the_union"),
        raster=None if bu is None else dict(file=bu["file"], bytes=bu["bytes"], sha256=bu["sha256"],
                                            download=bu["download_staged"]),
        validator=None if bu is None else bu["validator"],
        submission_name=None if bu is None else bu["name"],
        submission_note=None if bu is None else bu["note"],
        verdict="promote" if promote else "negative",
        verdict_reasons=reasons,
        download_ok=bool(bu and bu["validator"]["PASS"]), submit_ok=promote,
        slots_used=0, budget=dict(experiments_used=1, experiments_allowed=3))
    write("run_card", card)
    log(f"verdict={card['verdict']} reasons={json.dumps(reasons)}")
    return card


def main():
    check_prereg()
    stages = (("channels", stage_channels), ("fit", stage_fit), ("holdout", stage_holdout),
              ("independence", stage_independence), ("build", stage_build), ("lane", stage_lane),
              ("write", stage_write), ("card", stage_card))
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in stages:
        if st in (name, "all"):
            fn()


if __name__ == "__main__":
    main()
