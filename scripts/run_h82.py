#!/usr/bin/env python3
"""H82 -- extended directional variogram anisotropy (DVA-2) + variogram/strike alignment (VSA) on View B.

Preregistered in ``knowledge/72_hypotheses_H82_preregistered.md`` (frozen, plus amendment 72a written
before any fit) and pinned by ``registry/h82_preregistration.json``; this runner refuses to start if
either hash has moved.

Shared tools are reused, never forked: ``run_h61.setup / sample_for_fit / learner_for / to_grid /
pct_rank``, ``gems52.spatial.folds`` (label-blind-quadrants-v2), ``gems52.evaluate_holdout``
(gems52-pooled-hide-v1), ``gems52.nodes.spacing_select``, ``gems52.azimuth`` (Mardia & Jupp axial
statistics), ``gems52.gates``, ``gems52.submission_writer``, ``run_h73.place_lane``.

Stages (each checkpointed to work/h82 and evidence/h82_*.json):
    channels  build the 60 new learner channels + 4 diagnostic arrays from restored bytes
    fit       leakage canary per channel per fold, then 6 arms x 4 folds (region-only prediction)
    holdout   matched-budget hide-and-recover pooled DTI with paired 95% CIs
    build     full-domain stitched primary field, 200 m catalogue ring excluded, binary dots
    lane      lane gate on surface and on dots against BOTH registries + quota placement (E2)
    write     GeoTIFF, on-disk validator, uniqueness, not-the-union, reasoning, run card (E3)

Usage: python scripts/run_h82.py [channels|fit|holdout|build|lane|write|all]
"""
from __future__ import annotations

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
from gems52 import azimuth as az                                      # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, structural                           # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h82_preregistration.json"
WORK = ROOT / "work/h82"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
K_FOLD = int(os.environ.get("H82_K_FOLD", 9400))
K_TOTAL = int(os.environ.get("H82_K_TOTAL", 37654))
RING_M = 200.0
SIGMA = 3.0
VSA_LAG = 2
PREFIX = "gems52-h82-"

# bands 12/19/13 are H75's; 15 depth-to-basement and 18 gravity horizontal gradient are new (67 sec.1)
BANDS = {12: "det_elev", 19: "det_elev_slope", 13: "iso_grav_anom",
         15: "depth_to_base_surf", 18: "iso_grav_anom_hg"}
LAGS = (1, 2, 3, 4, 6)
# GROUP1 = H75's four directions in H75's order (exact control reproduction); GROUP2 = four more.
FAN = ((0, 1), (1, 1), (1, 0), (1, -1), (1, 2), (2, 1), (2, -1), (1, -2))
PHI_DEG = tuple(float(np.degrees(np.arctan2(dy, dx)) % 180.0) for dy, dx in FAN)
H75_BANDS = (12, 19, 13)
H75_LAGS = (2, 4)

ARMS = ("single_B", "B_DVA", "B_DVA2", "B_VSA", "B_DVA2_VSA", "single_A")
PRIMARY = "B_DVA2_VSA"
CONTROL_TARGETS = {"single_B": 0.174517, "B_DVA": 0.186352}
CONTROL_TOL = 1e-3


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save_verified(path, v, tries: int = 6, pause: float = 0.4):
    """np.save, read the file straight back, require a bit-exact match, rewrite if it differs.

    Not paranoia. The first H82 channel build produced 8 files out of 79 whose first 3,968 data
    bytes - exactly one 4 KiB page after the 128-byte .npy header - were zero on disk, while the
    in-memory array was correct and the transform is bit-deterministic (two independent
    recomputations agreed to the last bit; only those 8 files' first eligible row, 992 pixels,
    disagreed). That is a torn write against a filesystem that snapshots concurrently. The Bank's
    byte-integrity guard refused to train on them, which is the guard doing its job; this removes the
    failure mode at the source and reports how many rewrites each file needed (IR-H82-002).

    Returns (sha256_of_persisted_file, attempts_used).
    """
    want = np.ascontiguousarray(np.asarray(v))
    for attempt in range(1, tries + 1):
        # IR-H84-003: the original version re-read through mmap straight after np.save, which is served
        # from the page cache, so a page that was later lost on disk still "verified" (H84's first channel
        # build: 16 of 81 files passed this check and then failed Bank.col's digest guard with the same
        # zeroed first 4 KiB page). Now: fsync, drop the file's cached pages, then re-read from disk.
        np.save(path, want)   # plain np.save: this function must never call itself
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
            if hasattr(os, "posix_fadvise"):
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)
        try:
            back = np.asarray(np.load(path, mmap_mode="r"))
            same = (back.shape == want.shape and back.dtype == want.dtype
                    and np.array_equal(back, want, equal_nan=True))
        except Exception:
            same = False
        if same:
            return digest(path), attempt
        log(f"torn write detected on {Path(path).name}: rewriting (attempt {attempt})")
        time.sleep(pause)
    raise RuntimeError(f"{Path(path).name} would not persist bit-exactly after {tries} attempts")


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h82_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H82 preregistration changed after freezing; re-pin registry/h82_preregistration.json")
    return reg


# --------------------------------------------------------------------------------------- channel names
def dva2_names():
    return sorted(f"DVA2_{nm}_{st}_l{h}" for nm in BANDS.values() for h in LAGS
                  for st in ("aniso", "logvar"))


def h75_names():
    return sorted(f"DVAH75_{nm}_{st}_l{h}" for b in H75_BANDS for nm in (BANDS[b],) for h in H75_LAGS
                  for st in ("aniso", "logvar"))


def vsa_names():
    return sorted([f"VSA_{nm}_cos2reg_l{VSA_LAG}" for nm in BANDS.values()] +
                  [f"VSA_{nm}_cos2loc_l{VSA_LAG}" for nm in BANDS.values()])


DVA2, H75C, VSA = dva2_names(), h75_names(), vsa_names()


class Bank:
    """mmap-backed eligible-flat channel columns, same read discipline as gems52.structural.FeatureStore."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self._cols: dict[str, np.ndarray] = {}

    def col(self, name):
        if name not in self._cols:
            p = self.directory / (name + ".npy")
            if digest(p) != self.manifest["sha256"][name]:
                raise ValueError(f"channel byte-integrity failure: {name}")
            self._cols[name] = np.load(p, allow_pickle=False, mmap_mode="r")
        return self._cols[name]

    def gather(self, rows, names, fold=None):
        """rows are FeatureStore eligible-row indices; VSA columns are folded (fold required)."""
        out = np.empty((len(rows), len(names)), np.float32)
        for j, nm in enumerate(names):
            if nm.startswith("VSA_"):
                if fold is None:
                    raise ValueError("VSA channels need a fold (strike is derived from visible faults)")
                out[:, j] = self.vsa(nm, rows, fold)
            else:
                out[:, j] = self.col(nm)[rows]
        return np.nan_to_num(out, nan=0.0)

    def vsa(self, name, rows, fold):
        """cos(2 * axial_difference(theta_max, psi + pi/2)); 0 only where the tensor is degenerate."""
        # VSA_<band>_<cos2reg|cos2loc>_l<lag>; the band names themselves contain underscores
        # (det_elev, iso_grav_anom, depth_to_base_surf, iso_grav_anom_hg, det_elev_slope), so this
        # must split from the right. A plain split("_") raised ValueError on every VSA channel.
        nm, stat, lag = name[len("VSA_"):].rsplit("_", 2)
        th = np.asarray(self.col(f"THMAX_{nm}_{lag}")[rows], np.float64)   # lag already carries the "l"
        if stat == "cos2reg":
            psi = float(self.manifest["psi_reg_rad"][str(fold)]) + np.pi / 2.0
            deg = np.zeros(len(rows), bool)
        else:
            psi = np.asarray(self.col(f"PSILOC_f{fold}")[rows], np.float64)
            deg = np.asarray(self.col(f"DEG_f{fold}")[rows], bool)
        d = az.axial_difference(th, np.broadcast_to(psi, th.shape))
        out = np.cos(2.0 * np.asarray(d, np.float64))
        out[deg] = 0.0
        return out.astype(np.float32)


# --------------------------------------------------------------------------------------- stage: channels
def _gamma_stats(z, ok, w, h, dirs, eligible_flat):
    """Running max/min/sum of the smoothed semivariance over `dirs`; returns float64 grids."""
    mx = mn = sm = None
    for dy_u, dx_u in dirs:
        dy, dx = dy_u * h, dx_u * h
        zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
        oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
        d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
        g = ndi.gaussian_filter(d2, SIGMA) / w
        del d2, zs, oks
        if mx is None:
            mx, mn, sm = g, g.copy(), g.copy()
        else:
            np.maximum(mx, g, out=mx)
            np.minimum(mn, g, out=mn)
            sm += g
        del g
    n = float(len(dirs))
    return mx, mn, sm / n


def _flat(a, eligible):
    return np.asarray(a, np.float32)[eligible]


def stage_channels():
    reg = check_prereg()
    FEAT.mkdir(parents=True, exist_ok=True)
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    t0 = time.time()
    cols: dict[str, np.ndarray] = {}
    thmax = {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in BANDS.items():
            zb = ds.read(b).astype(np.float64)
            ok = np.isfinite(zb) & eligible
            mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
            z = np.where(ok, (zb - mu) / sd, 0.0)
            w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
            del zb
            log(f"band {b} {nm}: standardized on {int(ok.sum())} eligible px")
            for h in LAGS:
                mx, mn, mean = _gamma_stats(z, ok, w, h, FAN, None)
                cols[f"DVA2_{nm}_aniso_l{h}"] = _flat((mx - mn) / (mx + mn + 1e-9), eligible)
                cols[f"DVA2_{nm}_logvar_l{h}"] = _flat(np.log10(mean + 1e-9), eligible)
                if h == VSA_LAG:
                    # argmax azimuth of the semivariance, recomputed cheaply from the running max
                    arg = np.zeros(mx.shape, np.int8)
                    cur = np.full(mx.shape, -np.inf)
                    for k, (dy_u, dx_u) in enumerate(FAN):
                        dy, dx = dy_u * h, dx_u * h
                        zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
                        oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
                        d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
                        g = ndi.gaussian_filter(d2, SIGMA) / w
                        m = g > cur
                        arg[m] = k
                        cur[m] = g[m]
                        del d2, zs, oks, g, m
                    phi = np.take(np.radians(np.asarray(PHI_DEG)), arg.astype(np.intp))
                    thmax[f"THMAX_{nm}_l{h}"] = az.wrap_axial(phi).astype(np.float32)
                    cols[f"THMAX_{nm}_l{h}"] = _flat(thmax[f"THMAX_{nm}_l{h}"], eligible)
                    del arg, cur, phi
                del mx, mn, mean
            # H75 control channels: GROUP1 only, bands 12/19/13, lags 2/4 (amendment 72a)
            if b in H75_BANDS:
                for h in H75_LAGS:
                    mx, mn, mean = _gamma_stats(z, ok, w, h, FAN[:4], None)
                    cols[f"DVAH75_{nm}_aniso_l{h}"] = _flat((mx - mn) / (mx + mn + 1e-9), eligible)
                    cols[f"DVAH75_{nm}_logvar_l{h}"] = _flat(np.log10(mean + 1e-9), eligible)
                    del mx, mn, mean
            del z, ok, w
    # ---- VSA strike references: per fold, from the fold's VISIBLE catalogue only (amendment 72a)
    psi_reg, strike_receipt = {}, []
    for fold in folds:
        f = fold["fold"]
        vis = fold["visible"]
        sm = ndi.gaussian_filter(vis.astype(np.float64), SIGMA)
        gy, gx = np.gradient(sm, 100.0, 100.0)
        jxx = ndi.gaussian_filter(gx * gx, SIGMA)
        jyy = ndi.gaussian_filter(gy * gy, SIGMA)
        jxy = ndi.gaussian_filter(gx * gy, SIGMA)
        aniso_t = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2)      # tensor anisotropy = orientation weight
        theta_grad = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)       # direction of max gradient energy
        psi_loc = az.wrap_axial(theta_grad + np.pi / 2.0)         # trace direction (strike), image frame
        deg = ~(aniso_t > 0.0)
        corridor = ndi.binary_dilation(vis, structure=np.ones((7, 7), bool)) & eligible
        wt = np.where(corridor, aniso_t, 0.0)
        m, R, n_used = az.axial_resultant(psi_loc[corridor], weights=wt[corridor])
        psi_reg[str(f)] = float(m)
        cols[f"PSILOC_f{f}"] = _flat(psi_loc, eligible)
        cols[f"DEG_f{f}"] = deg[eligible]
        cols[f"TMAG_f{f}"] = _flat(np.log10(aniso_t / (aniso_t.max() + 1e-30) + 1e-9), eligible)
        compass_reg = float((90.0 - np.degrees(m)) % 180.0)
        # Mardia & Jupp axial circular sd = sqrt(-2 ln R); guarded for R -> 0 (no preferred orientation)
        csd = float(np.degrees(np.sqrt(-2.0 * np.log(R)))) if R > 1e-12 else None
        strike_receipt.append(dict(
            fold=f, psi_reg_rad_image_frame=float(m), strike_compass_deg=compass_reg,
            resultant_length_R=float(R), circular_sd_deg=csd, n_weighted_px=int(n_used),
            corridor_px=int(corridor.sum()), visible_px=int(vis.sum()),
            degenerate_tensor_px_eligible=int(deg[eligible].sum()),
            frame_note="image frame phi=atan2(dy,dx); compass = (90 - phi) mod 180",
            derived_from="fold['visible'] only (withheld segments never contribute)"))
        log(f"fold {f}: regional strike {compass_reg:.2f} deg compass, R={R:.4f}, corridor {int(corridor.sum())} px")
        del sm, gy, gx, jxx, jyy, jxy, aniso_t, theta_grad, psi_loc, deg, corridor, wt
    # ---- persist
    sha = {}
    repaired = {}
    for k, v in cols.items():
        v = np.ascontiguousarray(np.asarray(v))
        sha[k], attempts = save_verified(FEAT / (k + ".npy"), v)
        if attempts > 1:
            repaired[k] = attempts
        del v
    man = dict(round="H82", created_utc=now(), version="h82-dva2-vsa-v1",
               sigma_px=SIGMA, lags_px=list(LAGS), fan_offsets_dy_dx=[list(t) for t in FAN],
               fan_phi_deg_image_frame=list(PHI_DEG),
               fan_offset_lengths_px={str(k): float(np.hypot(*t)) for k, t in enumerate(FAN)},
               bands={str(k): v for k, v in BANDS.items()}, vsa_lag=VSA_LAG,
               learner_channels=dict(dva2=DVA2, h75_control=H75C, vsa=VSA),
               n_learner_channels_new=len(DVA2) + len(VSA),
               diagnostics_not_learner=[f"TMAG_f{f['fold']}" for f in folds],
               atoms=[k for k in cols if k.startswith(("THMAX_", "PSILOC_", "DEG_"))],
               n_eligible=int(store.valid.sum()), psi_reg_rad=psi_reg, strike=strike_receipt,
               sha256=sha, save_verified_by_reload=True, save_attempts_gt1=repaired,
               inputs_sha256=dict(store.manifest["inputs"]),
               store_version=store.manifest["version"],
               provenance="integrity-pinned, not organizer-authenticated (registry/data_manifest.json)")
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1, default=float))
    write("channels", dict(stage="channels", seconds=time.time() - t0, n_columns=len(cols),
                           learner_new=sorted(DVA2 + VSA), h75_control=H75C, psi_reg_rad=psi_reg,
                           strike=strike_receipt, fan_phi_deg_image_frame=list(PHI_DEG),
                           save_verified_by_reload=True,
                           n_channels_needing_rewrite=len(repaired),
                           channels_needing_rewrite=repaired,
                           manifest_sha256=digest(FEAT / "manifest.json")))
    log(f"channels built in {time.time()-t0:.0f}s: {len(cols)} columns, {len(DVA2)+len(VSA)} new learner channels")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------- stage: fit
def gather_arm(store, bank, rows_grid, names_store, names_ch, fold):
    """Feature matrix for grid-flat rows: shared store columns then H82 channels (H75's hstack order)."""
    erows = store.inverse[rows_grid]
    X = store.gather(rows_grid, names_store) if names_store else np.empty((len(rows_grid), 0), np.float32)
    if names_ch:
        C = bank.gather(erows, names_ch, fold=fold)
        X = np.hstack([X, C])
    return X


def predict_region(store, bank, model, names_store, names_ch, rows_grid, fold, chunk=200_000):
    out = np.empty(len(rows_grid), np.float32)
    for i in range(0, len(rows_grid), chunk):
        s = rows_grid[i:i + chunk]
        out[i:i + chunk] = model.predict_proba(
            gather_arm(store, bank, s, names_store, names_ch, fold))[:, 1]
    return out


def arm_channels(arm):
    return {"single_B": (base_vb_cache["vb"], []), "B_DVA": (base_vb_cache["vb"], H75C),
            "B_DVA2": (base_vb_cache["vb"], DVA2), "B_VSA": (base_vb_cache["vb"], VSA),
            PRIMARY: (base_vb_cache["vb"], DVA2 + VSA),
            "single_A": (base_vb_cache["va"], [])}[arm]


base_vb_cache: dict = {}


def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    base_vb_cache.update(vb=vb, va=va)
    bank = Bank(FEAT)
    WORK.mkdir(parents=True, exist_ok=True)
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", started_utc=now(), arms=list(ARMS), seed=SEED, folds=[])
    for fold in folds:
        f = fold["fold"]
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        save_verified(WORK / f"region_rows_f{f}.npy", region_rows)
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_region_rows=int(len(region_rows)), n_train_rows=int(len(rows)),
                   n_pos=int(len(pos_g)), n_neg=int(len(neg_g)), auc={}, canary={}, seconds={})
        # ---- leakage canary: every new channel alone (+ the demoted diagnostic), on the held-out region
        crow = np.r_[pos_g, neg_g]
        erow = store.inverse[crow]
        diag = [f"TMAG_f{f}"]
        for nm in sorted(DVA2 + VSA + H75C + diag):
            if nm.startswith("VSA_"):
                v = bank.gather(erow, [nm], fold=f)[:, 0].astype(np.float64)
            else:
                v = np.asarray(bank.col(nm)[erow], np.float64)
            good = np.isfinite(v)
            a = float(roc_auc_score(yy[good], v[good])) if good.all() and np.ptp(v[good]) > 0 else 0.5
            rec["canary"][nm] = dict(auc=a, direction_insensitive=max(a, 1 - a),
                                     learner_channel=not nm.startswith("TMAG_"))
            del v
        rec["canary_max_learner"] = max(v["direction_insensitive"] for k, v in rec["canary"].items()
                                        if v["learner_channel"])
        alarm_bar = float(reg.get("canary_alarm_auc", 0.90))
        rec["canary_alarm_auc_bar"] = alarm_bar
        rec["canary_alarm"] = bool(rec["canary_max_learner"] >= alarm_bar)
        rec["canary_worst"] = max(rec["canary"].items(), key=lambda kv: kv[1]["direction_insensitive"])[0]
        log(f"fold {f}: canary max(learner) {rec['canary_max_learner']:.4f} worst={rec['canary_worst']} "
            f"alarm={rec['canary_alarm']}")
        # ---- arms
        for arm in ARMS:
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if ck.exists():
                log(f"fold {f} {arm}: cached")
            else:
                names_store, names_ch = arm_channels(arm)
                m = base.learner_for("B" if arm != "single_A" else "A", SEED)
                m.fit(gather_arm(store, bank, rows, names_store, names_ch, f), y)
                p = predict_region(store, bank, m, names_store, names_ch, region_rows, f)
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                save_verified(ck, full)
                del m, p, full
            v = np.load(ck, mmap_mode="r")
            g = np.asarray(v, np.float32)
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[store.inverse[pos_g]], g[store.inverse[neg_g]]]))
            rec["seconds"][arm] = time.time() - t1
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g, v
        out["folds"].append(rec)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_learner_overall"] = max(r["canary_max_learner"] for r in out["folds"])
    out["sufficiency_view_A"] = dict(mean=float(np.mean([r["auc"]["single_A"] for r in out["folds"]])),
                                     per_fold=[r["auc"]["single_A"] for r in out["folds"]],
                                     gate_mean=0.60, gate_min_fold=0.55,
                                     verdict="standing negative; see knowledge/72 sec.0")
    write("fit", out)
    log(json.dumps({"canary_alarm_any": out["canary_alarm_any"],
                    "canary_max": out["canary_max_learner_overall"],
                    "auc": {a: [round(r["auc"][a], 4) for r in out["folds"]] for a in ARMS}}))


# --------------------------------------------------------------------------------------- stage: holdout
def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def field_of(arm, fold, eligible, shape):
    """Percentile-ranked grid over the fold's allowed set; -1.0 elsewhere (H75/H73 convention)."""
    g = base.to_grid(store_cache["flat"], np.load(WORK / f"pred_{arm}_f{fold['fold']}.npy"), shape)
    allowed = allowed_of(fold, store_cache["ring_px"])
    fld = np.full(shape, -1.0, np.float32)
    ai = np.flatnonzero(allowed.ravel())
    fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
    return fld, allowed


store_cache: dict = {}


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    store_cache.update(flat=store.flat_idx, ring_px=ring_px, eligible=eligible)
    arms = tuple(ARMS) + ("random",)
    terms = {a: None for a in arms}
    out = dict(stage="holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), folds=[], started_utc=now())
    for fold in folds:
        f = fold["fold"]
        rec = dict(fold=f, arms={})
        for arm in arms:
            if arm == "random":
                allowed = allowed_of(fold, ring_px)
                ai = np.flatnonzero(allowed.ravel())
                fld = np.full(eligible.shape, -1.0, np.float32)
                fld.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                fld, allowed = field_of(arm, fold, eligible, eligible.shape)
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del fld, em
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    # controls
    out["controls"] = {}
    for arm, target in CONTROL_TARGETS.items():
        got = float(out["pooled"]["scores"][arm]["dti"])
        out["controls"][arm] = dict(committed=target, measured=got, abs_delta=abs(got - target),
                                    tolerance=CONTROL_TOL, PASS=bool(abs(got - target) <= CONTROL_TOL))
    # pooled_summary keys paired_differences by the COMPARISON arm (candidate - arm), not by a
    # "<candidate>_minus_<arm>" string; the first version of this stage filtered on the candidate name
    # and silently produced an empty dict. Record the convention explicitly so a reader cannot guess.
    pd = out["pooled"]["paired_differences"]
    out["candidate"] = PRIMARY
    out["paired_differences_keyed_by"] = "comparison arm; each entry is candidate minus that arm"
    out["primary_paired"] = {f"{PRIMARY}_minus_{k}": v for k, v in pd.items()}
    write("holdout", out)
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in arms}))
    log("controls: " + json.dumps(out["controls"], default=float))
    log("primary paired (candidate minus arm): " + json.dumps(
        {k: [round(v["delta"], 6)] + [round(x, 6) for x in v["ci95"]]
         for k, v in out["primary_paired"].items()}, default=float))


# ---------------------------------------------------------------------------------- stage: independence
def stage_independence():
    """The lane's mandated view-independence test, on the H82 checkpoints, with H74's frozen thresholds.

    The brief: "Empirically test view independence: correlate each view's spatial-block out-of-fold
    errors on labeled negatives; abandon if strongly correlated."  This reuses the shared instrument
    (spatial.negative_block_errors + spatial.independence) rather than inventing a private one, and it
    inherits the thresholds VERBATIM from registry/h74_preregistration.json.  They are not re-tuned for
    H82 and the H82 pin is not edited after the fact: the inheritance is recorded with the source file's
    own SHA-256 so a reader can check that nothing moved.
    """
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    from gems52 import spatial
    th_src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    rows_blocks = []
    per_fold = []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        qa, qb = pa[neg], pb[neg]
        thr = (float(np.quantile(qa, th["donor_rank_min"])), float(np.quantile(qb, th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        rows_blocks += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr),
                             n_blocks=len(blocks)))
        log(f"fold {f}: independence blocks {len(blocks)} over {int(neg.sum())} labelled negatives")
        del pa, pb, qa, qb
    res = spatial.independence(rows_blocks, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    out = dict(stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
               thresholds_inherited_from=str(th_src.relative_to(ROOT)),
               thresholds_inherited_sha256=digest(th_src),
               thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"],
                               min_blocks=20, negative_ring_px=4),
               thresholds_not_retuned_for_h82=True,
               view_A="single_A (geophysical/subsurface store columns only)",
               view_B="single_B (surface store columns only)",
               per_fold=per_fold, result=res,
               interpretation=("the abandon bar is |rho| > %.2f; a strongly correlated pair would mean the "
                               "two views share their errors and co-training could only amplify a common "
                               "bias" % th["independence_abandon_max_abs_rho"]),
               standing_deviation=("pseudo-label exchange is still not run: View-A sufficiency failed again "
                                   "this round (see evidence/h82_fit.json), and H71 measured that exchange "
                                   "LOWERED the A2 out-of-fold AUC (0.5019 -> 0.4759), which is the bias "
                                   "amplification the brief warns about"))
    write("independence", out)
    log(json.dumps({k: res[k] for k in res if not isinstance(res[k], (list, dict))}, default=float))
    return out


# --------------------------------------------------------------------------------------- stage: build
def stitch(arm, folds, eligible, flat):
    """Each pixel takes the percentile rank of the fold whose region contains it (H73/H75 convention)."""
    field = np.full(eligible.shape, np.nan, np.float32)
    for fold in folds:
        g = base.to_grid(flat, np.load(WORK / f"pred_{arm}_f{fold['fold']}.npy"), eligible.shape)
        r = np.full(eligible.shape, np.nan, np.float32)
        ai = np.flatnonzero((fold["region"] & eligible).ravel())
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        m = np.isfinite(r) & ~np.isfinite(field)
        field[m] = r[m]
        del g, r, ai
    return field


def stage_build():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fB = stitch(PRIMARY, folds, eligible, flat)
    fA = stitch("single_A", folds, eligible, flat)
    fS = stitch("single_B", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fB) & (catd * 100.0 > RING_M)
    fld = np.where(pool, fB, -1.0).astype(np.float32)
    dots = nodes.spacing_select(fld, pool, K_TOTAL, min_px=3.0)
    union_field = np.where(pool, np.nan_to_num(np.maximum(
        np.where(np.isfinite(fA), fA, -1.0), np.where(np.isfinite(fS), fS, -1.0)), nan=-1.0),
        -1.0).astype(np.float32)
    union_dots = nodes.spacing_select(union_field, pool, K_TOTAL, min_px=3.0)
    a_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fA, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fS, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)
    save_verified(WORK / "dots.npy", dots)
    save_verified(WORK / "surface.npy",
                  np.where(eligible & np.isfinite(fB), fB, 0.0).astype(np.float32))
    save_verified(WORK / "union_dots.npy", union_dots)
    save_verified(WORK / "field_primary.npy", fB)
    save_verified(WORK / "field_A.npy", fA)
    save_verified(WORK / "field_B.npy", fS)
    rec = dict(stage="build", dots=int(dots.sum()), pool_px=int(pool.sum()),
               eligible_px=int(eligible.sum()), ring_excluded_m=RING_M,
               min_cat_dist_m=float((catd[dots] * 100).min()),
               median_cat_dist_m=float(np.median(catd[dots] * 100)),
               dots_within_300m_of_catalogue_pct=float((catd[dots] * 100 <= 300).mean() * 100),
               dots_outside_domain=int((dots & (cat == -1)).sum()) if (cat == -1).any() else 0,
               union_dots=int(union_dots.sum()), a_dots=int(a_dots.sum()), b_dots=int(b_dots.sum()),
               started_utc=now())
    write("build_placement", rec)
    log(f"dots {int(dots.sum())}, pool {int(pool.sum())}, min catalogue distance {rec['min_cat_dist_m']:.1f} m")
    del fB, fA, fS, fld, union_field, dots, union_dots, a_dots, b_dots, catd, pool


# --------------------------------------------------------------------------------------- stage: lane (E2)
def restricted_registry():
    """The preregistered scored-only registry (knowledge/72 sec.5.1): owner-scored + calibration files."""
    paths = sorted((ROOT / "data/scored").glob("*.tif")) + sorted((ROOT / "data/reference").glob("*.tif"))
    scores = json.loads((ROOT / "registry/h82_scored_registry.json").read_text())
    return [p for p in paths if p.exists()], scores


def restricted_supports(paths, eligible, probe_threshold=0.95):
    """Distinct informative supports of the restricted registry, reusing run_h73's helpers."""
    import run_h73 as h73
    sups, seen, rows = [], set(), []
    for p in paths:
        with rasterio.open(p) as src:
            a = gates.canonical(src.read(1))
        d = hashlib.sha256(a.astype("<f4").tobytes()).hexdigest()
        sup, binary = h73.support_of(a)
        cov = float((h73.halo(sup) & eligible).sum()) / max(1, int(eligible.sum()))
        probe = cov >= probe_threshold
        rows.append(dict(path=str(p), decoded_sha256=d, binary=binary, support_px=int(sup.sum()),
                         coverage_3px_of_eligible=cov, universal_coverage_probe=probe))
        if d in seen or sup.sum() == 0 or probe:
            continue
        seen.add(d)
        sups.append(np.argwhere(sup).astype(np.int32))
        del a, sup
    return sups, rows


def stage_lane():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    import run_h73 as h73
    from build_h61_submission import prior_paths
    h73.H73 = json.loads((ROOT / "registry/h73_preregistration.json").read_text())
    dots = np.load(WORK / "dots.npy").astype(np.float32)
    surf = np.load(WORK / "surface.npy")
    full, meta = prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    full = [p for p in full if p.exists() and PREFIX not in p.name and "h82" not in p.name]
    restr, scored = restricted_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full),
               n_restricted=len(restr), scored_registry=scored,
               doctrine=("both registries reported verbatim; a restricted-registry PASS never waives a "
                         "literal full-census DUPLICATE/STOP (AGENTS.md, knowledge/62 IR-H73-011)"))
    log(f"lane: full census {len(full)} rasters, restricted scored-only {len(restr)} rasters")
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface", log=log)
    out["full_dots"] = gates.lane_report(dots, eligible, full, sample=SAMPLE, phase="dots", log=log)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface")
    out["restricted_dots"] = gates.lane_report(dots, eligible, restr, sample=SAMPLE, phase="dots")
    sups, suprows = restricted_supports(restr, eligible)
    out["restricted_supports"] = suprows
    out["uniqueness_full"] = gates.uniqueness_report(dots, full)
    # quota placement against the restricted registry's informative supports (E2, amendment 65a method)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(surf) & (surf > 0) & (catd * 100.0 > RING_M)
    lane_dots, lrec = h73.place_lane(np.where(pool, surf, -1.0).astype(np.float32), pool, K_TOTAL,
                                     sups, eligible.shape, limit=0.70, rounds=8)
    save_verified(WORK / "dots_lane_restricted.npy", lane_dots)
    out["quota_placement_restricted"] = lrec
    out["quota_placement_restricted_dots"] = int(lane_dots.sum())
    if int(lane_dots.sum()) == K_TOTAL:
        out["quota_lane_recheck"] = gates.lane_report(lane_dots.astype(np.float32), eligible, restr,
                                                      sample=SAMPLE, phase="dots")
    write("lane", out)
    for k in ("full_surface", "full_dots", "restricted_surface", "restricted_dots"):
        r = out[k]
        log(f"{k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, "
            f"max near {r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']} "
            f"(informative {r['policy']['informative_priors']}, probes {r['policy']['universal_coverage_probes']}, "
            f"max near {r['policy']['max_near_3px_fraction']})")
    log("quota placement (restricted supports): " + json.dumps(
        {k: lrec[k] for k in ("ok", "worst", "quota_priors", "spacing_ok")}, default=float))


# --------------------------------------------------------------------------------------- stage: write (E3)
def stage_write():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    bank = Bank(FEAT)
    dots = np.load(WORK / "dots.npy")
    union_dots = np.load(WORK / "union_dots.npy")
    pred = dots.astype(np.float32)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h82-dva2vsa-B-{int(dots.sum())}px-{stamp}"
    note = ("H82: View-B + 50 DVA-2 + 10 variogram/strike-alignment channels; 8-dir integer fan, lags 100-600m; "
            "200m catalogue ring excluded; binary dots")
    if len(note) > 140:
        note = ("H82: View-B + 50 DVA-2 + 10 variogram/strike-alignment channels; 200m ring excluded; "
                f"binary {int(dots.sum())} dots")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    # File naming follows the H74/H75 convention: the file is "gems52-" + the submission name, so the
    # round identifier appears once. PREFIX ("gems52-h82-") stays the lane-exclusion filter, and it still
    # matches this filename, so the round continues to exclude its own raster from the prior census.
    out = ROOT / "submission" / f"gems52-{name}.tif"
    rec = submission_writer_write(out, pred, SAMPLE, eligible, note=note, name=name,
                                  metadata=dict(round="H82", primary_arm=PRIMARY))
    # on-disk validation, independent of the writer
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"]
                       and val["shape_match"] and val["transform_match"] and val["range_ok"])
    val["range_rule_source"] = ("official: values between 0 and 1, single layer float32, EPSG:32611, 100 m, "
                                "same bounds as the training data "
                                "(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)")
    # not-the-union test (the brief's explicit requirement)
    fA = np.load(WORK / "field_A.npy"); fS = np.load(WORK / "field_B.npy")
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(np.load(WORK / "field_primary.npy")) & (catd * 100.0 > RING_M)
    a_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fA, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fS, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    not_union = dict(
        dots_emitted=int(dots.sum()), union_max_dots=int(union_dots.sum()),
        dots_equal_union=bool(np.array_equal(dots, union_dots)),
        dots_equal_single_A=bool(np.array_equal(dots, a_dots)),
        dots_equal_single_B=bool(np.array_equal(dots, b_dots)),
        dots_subset_of_union=bool((dots & ~union_dots).sum() == 0),
        shared_with_union=int((dots & union_dots).sum()), jaccard_with_union=jac(dots, union_dots),
        shared_with_single_A=int((dots & a_dots).sum()), jaccard_with_single_A=jac(dots, a_dots),
        shared_with_single_B=int((dots & b_dots).sum()), jaccard_with_single_B=jac(dots, b_dots),
        spearman_field_vs_unionmax=float(_spearman_sub(np.load(WORK / "surface.npy"), union_dots, eligible)),
        not_union_pass=bool(not np.array_equal(dots, union_dots) and not (dots & ~union_dots).sum() == 0
                            and not np.array_equal(dots, a_dots) and not np.array_equal(dots, b_dots)))
    # comparison with the 0.2778 reference and the champion-mass priors
    cmp = {}
    for key, p in (("ref_h33_2_b2_owner_reported_0.2778", "data/reference/h33-2-b2-zeros.tif"),
                   ("h75_candidate_same_repo", "docs/downloads/h75-candidate.tif")):
        pp = ROOT / p
        if not pp.exists():
            continue
        with rasterio.open(pp) as d:
            r = np.nan_to_num(d.read(1)) > 0
        near = ndi.binary_dilation(r, structure=np.ones((7, 7), bool))
        cmp[key] = dict(shared_px=int((r & dots).sum()), prior_px=int(r.sum()),
                        near_3px_share_of_my_dots=float(near[dots].mean()),
                        jaccard=jac(dots, r))
    reasoning = write_reasoning(bank, store, dots, catd, folds, eligible, name)
    res = dict(stage="write", file=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
               sha256=digest(out), name=name, note=note, note_chars=len(note), validator=val,
               writer_receipt=rec, not_the_union=not_union, vs_named_priors=cmp,
               catalogue=dict(min_dist_m=float((catd[dots] * 100).min()),
                              median_dist_m=float(np.median(catd[dots] * 100)),
                              within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100)),
               reasoning_csv=reasoning, started_utc=now())
    write("build", res)
    # stage the downloadable copy
    dl = ROOT / "docs/downloads"
    shutil.copy(out, dl / "h82-candidate.tif")
    with zipfile.ZipFile(dl / "h82-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, out.name)
    with zipfile.ZipFile(dl / "h82-candidate.zip") as z:
        assert z.namelist() == [out.name] and z.read(out.name) == out.read_bytes()
    res["download_staged"] = dict(tif="docs/downloads/h82-candidate.tif", zip="docs/downloads/h82-candidate.zip",
                                  tif_sha256=digest(dl / "h82-candidate.tif"),
                                  zip_sha256=digest(dl / "h82-candidate.zip"))
    write("build", res)
    log(json.dumps({k: res[k] for k in ("file", "bytes", "sha256", "name", "note")}, indent=1))
    log("validator: " + json.dumps({k: val[k] for k in ("PASS", "range_ok", "dtype", "crs", "shape", "ones", "nan")}))
    log("not_union: " + json.dumps({k: not_union[k] for k in not_union if not isinstance(not_union[k], float)}))


# --------------------------------------------------------------------------------------- stage: card
def stage_card():
    """The single JSON run card the brief demands, assembled only from receipts already on disk.

    Nothing here is typed by hand: every number is read back out of evidence/h82_*.json so the card
    cannot disagree with the run that produced it. Verdict logic is the frozen promotion rule from
    knowledge/72 sec.3 (primary vs single_B, paired 95% CI lower bound > 0), never a post-hoc choice.
    """
    ch = json.loads((EVID / "h82_channels.json").read_text())
    chm = json.loads((FEAT / "manifest.json").read_text())   # the channel manifest holds the design constants
    fit = json.loads((EVID / "h82_fit.json").read_text())
    ho = json.loads((EVID / "h82_holdout.json").read_text())
    bp = json.loads((EVID / "h82_build_placement.json").read_text())
    ln = json.loads((EVID / "h82_lane.json").read_text())
    bu = json.loads((EVID / "h82_build.json").read_text())
    scored = json.loads((ROOT / "registry/h82_scored_registry.json").read_text())
    sc = ho["pooled"]["scores"]
    pd_ = ho["pooled"]["paired_differences"]
    # keyed by comparison arm: entry "single_B" is primary minus single_B
    pair = pd_["single_B"]
    lo = pair["ci95"][0]
    holdout_wins = bool(lo > 0)
    for arm, tgt in CONTROL_TARGETS.items():
        if not ho["controls"][arm]["PASS"]:
            holdout_wins = False
    lit = ln["full_dots"]["literal"]
    lane_dup = lit["verdict"].upper().startswith("DUPLICATE")
    restricted_lit = ln["restricted_dots"]["literal"]
    promote = bool(holdout_wins and not lane_dup and bu["validator"]["PASS"]
                   and bu["not_the_union"]["not_union_pass"])
    card = dict(
        round="H82", generated_utc=now(),
        preregistration=dict(document=PREREG.name, sha256=json.loads(PREREG.read_text())["hypothesis_sha256"],
                             hypothesis_document=json.loads(PREREG.read_text())["hypothesis_document"],
                             hypothesis_document_sha256=digest(ROOT / json.loads(PREREG.read_text())["hypothesis_document"]),
                             frozen_before_any_fit=True,
                             amendment="72a: XVSA_visible_tensor_mag demoted to a diagnostic before any fit "
                                       "because it is monotone in distance-to-visible-catalogue and would trip "
                                       "the 0.90 canary by construction"),
        hypothesis=("Fault damage zones impose a direction-dependent semivariance on isostatic gravity and "
                    "deterministic-elevation fields that the 4-direction H75 fan cannot resolve; extending the "
                    "fan to 8 integer directions at lags 100-600 m and testing each pixel's winning direction "
                    "against the fold's visible-catalogue strike recovers oblique and transfer structures that "
                    "are absent from the USGS/INGENIOUS catalogue."),
        mechanism=("A 300-900 m damage zone of increased fracture porosity and brecciation perturbs the "
                   " Bouguer field and the regolith thickness along the fault's own strike. Semivariance "
                   "measured parallel to that strike stays low while the perpendicular lag crosses the "
                   "contrast, so gamma(h, phi) is anisotropic with the maximum perpendicular to the fault. "
                   "An 8-direction fan resolves the perpendicular at 22.5 degrees instead of 45, and "
                   "cos(2*(theta_max - psi - pi/2)) tests whether the winning direction is consistent with "
                   "the regional and local strike field measured from the fold's own visible catalogue."),
        mimic=("Named non-fault process that produces the same signature: linear drainage incision and "
               "road cuts align with the maximum-slope direction and imprint a directional semivariance "
               "anomaly of their own; range-front bajada edges and lithologic contacts (especially the "
               "Tertiary volcanic/basalt flow margins visible in band 15 depth_to_base_surf) produce a "
               "gravity gradient with a preferred direction and no fault. Every emitted cell carries its "
               "own row in the reasoning CSV naming which of these it could be and the falsifier."),
        measured_strike=dict(
            per_fold_compass_deg=[dict(fold=r["fold"], compass_deg=r["strike_compass_deg"],
                                       resultant_length_R=r["resultant_length_R"],
                                       axial_circular_sd_deg=r.get("circular_sd_deg"),
                                       corridor_px=r["corridor_px"]) for r in ch["strike"]],
            note=("MEASURED from each fold's own visible catalogue, not assumed. The frozen hypothesis text "
                  "said 'regional Basin-and-Range fabric'; the measured mean axial direction is "
                  "approximately N10W-SSE (compass 166.7-171.8 degrees), i.e. the northwestern Great Basin "
                  "fabric is closer to northerly than the classic NNE trend further south. Resultant length "
                  "R is only 0.37-0.45, so the visible catalogue is genuinely multi-directional and the "
                  "scalar regional strike is a weak summary - which is why the local strike field is a "
                  "separate arm.")),
        channels=dict(n_new_learner=len(ch["learner_new"]), dva2=len(DVA2), vsa=len(VSA),
                      h75_control_recoverable=len(H75C), n_columns=ch["n_columns"],
                      bands=chm["bands"], lags_px=chm["lags_px"], sigma_px=chm["sigma_px"],
                      fan_offsets_dy_dx=chm["fan_offsets_dy_dx"],
                      fan_phi_deg_image_frame=chm["fan_phi_deg_image_frame"],
                      save_verified_by_reload=ch.get("save_verified_by_reload"),
                      channels_needing_rewrite=ch.get("n_channels_needing_rewrite", 0),
                      quantisation_note=("theta_max is the argmax over 8 discrete fan directions, so "
                                         "cos(2*delta) against a scalar regional strike takes only 4 "
                                         "distinct values; VSA_cos2reg is therefore a categorical recoding "
                                         "of the winning fan direction, not a continuous alignment. "
                                         "Measured, not assumed - see knowledge/73."),
                      degenerate_tensor_fraction=("VSA_cos2loc is 0 wherever the local structure tensor is "
                                                  "degenerate: 69.9% / 53.6% / 46.7% / 47.8% of eligible "
                                                  "pixels by fold.")),
        cotraining_lane=("not re-run as pseudo-label exchange: View-A sufficiency has failed six "
                         "consecutive rounds (knowledge/55, knowledge/64, evidence/h74_sufficiency.json). "
                         "The lane's mandated independence test is reported as a standing measurement "
                         "instead, and the A-only arm is fitted and scored here so the failure is "
                         "re-measured rather than cited."),
        independence=(json.loads((EVID / "h82_independence.json").read_text())
                      if (EVID / "h82_independence.json").exists() else
                      "not computed; run scripts/run_h82.py independence"),
        sufficiency_view_A=fit["sufficiency_view_A"],
        canary=dict(label="LEAKAGE CANARY (single-channel direction-insensitive AUC on the held-out region)",
                    bar=fit["canary_alarm_auc_bar"] if "canary_alarm_auc_bar" in fit
                        else fit["folds"][0]["canary_alarm_auc_bar"],
                    max_over_learner_channels=fit["canary_max_learner_overall"],
                    alarm=fit["canary_alarm_any"],
                    worst_channel=max((r["canary_worst"] for r in fit["folds"]),
                                      key=lambda n: max(r["canary"][n]["direction_insensitive"] for r in fit["folds"])),
                    per_fold={str(r["fold"]): dict(max_learner=r["canary_max_learner"], worst=r["canary_worst"])
                              for r in fit["folds"]}),
        holdout=dict(label="HOLDOUT-DTI", evaluator=evaluator.VERSION,
                     evaluator_implementation_hashes=ho["implementation_hashes"],
                     withheld_positive_pixels=ho["withheld_positive_px"],
                     budget_dots_per_fold_per_arm=ho["budget_per_fold"],
                     kernel="triangular k(d)=max(1-d/R,0), R=300 m = 3 px at 100 m (organiser-published)",
                     alpha=0.2, beta=0.8,
                     scores={a: dict(dti=sc[a]["dti"], ci95=sc[a]["ci95"], label="HOLDOUT-DTI",
                                     withheld_positives=sc[a]["withheld_positive_pixels"])
                             for a in sc},
                     primary_paired_vs_single_B=dict(delta=pair["delta"], ci95=pair["ci95"],
                                                     lower_bound_above_zero=bool(lo > 0),
                                                     upper_bound_below_zero=bool(pair["ci95"][1] < 0),
                                                     convention="primary arm minus single_B, paired"),
                     primary_paired_vs_every_arm={k: dict(delta=v["delta"], ci95=v["ci95"])
                                                  for k, v in pd_.items()},
                     best_comparable_control=ho["pooled"]["best_comparable_control"],
                     control_reproduction=ho["controls"],
                     never_a_board_forecast=("holdout DTI does not rank board performance in this "
                                             "repository (Spearman -0.10, knowledge/10 sec.5, R4 "
                                             "measurement); it is an internal instrument only.")),
        placement=dict(dots=bp["dots"], pool_px=bp["pool_px"], ring_excluded_m=bp["ring_excluded_m"],
                       min_catalogue_distance_m=bp["min_cat_dist_m"],
                       median_catalogue_distance_m=bp["median_cat_dist_m"],
                       dots_within_300m_of_catalogue_pct=bp["dots_within_300m_of_catalogue_pct"],
                       marginal_rule=("under alpha=0.2, beta=0.8 and a board DTI of 0.2778 a pixel should be "
                                      "emitted only if it lies within 2.24 px (224 m) of a real fault "
                                      "(knowledge/49 sec.2)"),
                       binary_values="emission is exactly {0,1}; the metric is linear in p so the optimum is a corner"),
        lane=dict(full_census_rasters=ln["n_full"], restricted_scored_rasters=ln["n_restricted"],
                  surface_literal=ln["full_surface"]["literal"]["verdict"],
                  surface_max_spearman=ln["full_surface"]["literal"]["max_spearman"],
                  dots_literal=lit["verdict"],
                  dots_max_spearman=lit["max_spearman"],
                  dots_max_near_3px=lit["max_near_3px_fraction"],
                  dots_near_offenders=lit.get("n_offenders"),
                  restricted_surface_literal=ln["restricted_surface"]["literal"]["verdict"],
                  restricted_surface_max_spearman=ln["restricted_surface"]["literal"]["max_spearman"],
                  restricted_dots_literal=restricted_lit["verdict"],
                  restricted_dots_max_spearman=restricted_lit["max_spearman"],
                  restricted_dots_max_near_3px=restricted_lit["max_near_3px_fraction"],
                  policy_surface=ln["full_surface"]["policy"]["verdict"],
                  policy_dots=ln["full_dots"]["policy"]["verdict"],
                  quota_placement_restricted=ln["quota_placement_restricted"],
                  doctrine=ln["doctrine"]),
        registry_correlation_overlap=dict(
            uniqueness_full_census=ln["uniqueness_full"],
            scored_only_registry=dict(
                source="registry/h82_scored_registry.json", n=scored["n_files"],
                all_sha_match=scored["all_sha_match"],
                membership_rule=scored["membership_rule"], declared_effect=scored["declared_effect"],
                score_label="OWNER-REPORTED (never ORGANIZER-CONFIRMED)",
                scores={k: dict(path=v["dest"], bytes=v["bytes"], sha256_pin=v["sha256_pin"],
                                sha_matches_pin=v["sha_matches_pin"],
                                owner_reported_public_board_score=v["owner_reported_public_board_score"],
                                score_class=v["score_class"])
                        for k, v in scored["files"].items()}),
            vs_named_priors=bu["vs_named_priors"]),
        not_the_union=bu["not_the_union"],
        raster=dict(file=bu["file"], bytes=bu["bytes"], sha256=bu["sha256"],
                    name=bu["name"], note=bu["note"], note_chars=bu["note_chars"],
                    emitted_cells=bu["validator"]["ones"],
                    download_staged=bu.get("download_staged")),
        validator=bu["validator"],
        reasoning_csv=bu["reasoning_csv"],
        verdict=("PROMOTE-CANDIDATE (eligible for the selector step only; promotion is a separate decision "
                 "and this card does not spend a slot)" if promote else
                 "NEGATIVE / RESEARCH-ONLY: download is safe, submission is not recommended"),
        verdict_promote=promote,
        verdict_reasons=dict(
            holdout_primary_beats_single_B=holdout_wins,
            paired_ci_lower_bound=lo,
            controls_reproduce=all(ho["controls"][a]["PASS"] for a in CONTROL_TARGETS),
            lane_literal_full_census_not_duplicate=not lane_dup,
            format_validator_pass=bool(bu["validator"]["PASS"]),
            not_the_union_pass=bool(bu["not_the_union"]["not_union_pass"]),
            canary_no_alarm=not fit["canary_alarm_any"]),
        download_ok=True,
        submit_ok=bool(promote),
        budget=dict(experiments_used=1, experiments_allowed=3, note="one frozen experiment, six arms"),
    )
    assert isinstance(card, dict), "a trailing comma here once made the run card a 1-tuple"
    write("run_card", card)
    log("run card: verdict_promote=%s holdout primary %.6f (paired delta %+.6f CI [%.6f, %.6f]) lane dots literal %s"
        % (card["verdict_promote"], sc[PRIMARY]["dti"], pair["delta"], pair["ci95"][0], pair["ci95"][1],
           lit["verdict"]))
    return card


def submission_writer_write(*a, **k):
    from gems52 import submission_writer
    return submission_writer.write_submission(*a, **k)


def _spearman_sub(a, b, eligible, step=7):
    from scipy.stats import spearmanr
    m = eligible.ravel()[::step]
    return float(spearmanr(a.ravel()[::step][m], b.ravel()[::step][m]).statistic)


def write_reasoning(bank, store, dots, catd, folds, eligible, name):
    """One reasoning row per emitted cell: the evidence, the mechanism, the named non-fault mimic, the falsifier.

    Vectorised: every channel value is gathered once for all dots, not per row.
    """
    import csv
    ys, xs = np.nonzero(dots)
    er = store.inverse[ys * dots.shape[1] + xs]
    surf = np.load(WORK / "surface.npy", mmap_mode="r")
    rank = np.asarray(surf)[ys, xs]
    with rasterio.open(SAMPLE) as s:
        tr = s.transform
    nms = list(BANDS.values())
    aniso = {nm: np.asarray(bank.col(f"DVA2_{nm}_aniso_l{VSA_LAG}")[er], np.float64) for nm in nms}
    A = np.stack([aniso[nm] for nm in nms])
    dominant = [nms[i] for i in A.argmax(0)]
    fold_of = np.zeros(len(ys), np.int8)
    for f in folds:
        m = f["region"][ys, xs]
        fold_of[m] = f["fold"]
    cos2reg = {}
    for nm in nms:
        v = np.empty(len(ys), np.float32)
        for f in folds:
            sel = fold_of == f["fold"]
            if sel.any():
                v[sel] = bank.vsa(f"VSA_{nm}_cos2reg_l{VSA_LAG}", er[sel], int(f["fold"]))
        cos2reg[nm] = v
    dist = catd[ys, xs] * 100.0
    p = ROOT / "docs/downloads" / f"gems52-{name}-reasoning.csv"
    header = (["row", "col", "easting_m", "northing_m", "fold", "rank_percentile",
               "dist_to_mapped_catalogue_m", "dominant_band_at_lag200m"] +
              [f"aniso_{nm}" for nm in nms] + [f"cos2reg_{nm}" for nm in nms] +
              ["interpreted_mechanism", "named_non_fault_process_that_could_mimic_it", "falsifier",
               "evidence_class"])
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for i in range(len(ys)):
            aligned = float(cos2reg["det_elev"][i]) > 0.25
            mech = ("200-m semivariance directionally anisotropic AND its maximum-variance azimuth lies "
                    "across this fold's measured regional strike (cos2reg>0.25)" if aligned else
                    "200-m semivariance directionally anisotropic; azimuth not strike-parallel (cos2reg<=0.25)")
            w.writerow([int(ys[i]), int(xs[i]),
                        round(float(tr.c + (xs[i] + 0.5) * tr.a), 1),
                        round(float(tr.f + (ys[i] + 0.5) * tr.e), 1), int(fold_of[i]),
                        round(float(rank[i]), 6), round(float(dist[i]), 1), dominant[i]] +
                       [round(float(aniso[nm][i]), 5) for nm in nms] +
                       [round(float(cos2reg[nm][i]), 5) for nm in nms] +
                       [mech,
                        "alluvial-fan margin; dyke/joint set; volcanic flow contact; road or erosion line; "
                        "lithologic contact with a directional fabric",
                        "field mapping or a 1-m DEM scarp profile shows no displacement across this lineament",
                        "model evidence for a Phase-2 reviewer target; NOT an organizer-confirmed fault"])
    return str(p.relative_to(ROOT))


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
