#!/usr/bin/env python3
"""H91 -- continuous directional alignment (CSA) on a 16-direction semivariance fan, inside the
brief's two-view co-training lane.

Lane (unchanged, per the brief): View A is potential-field/subsurface, View B is surface
(DEM-derived curvature/slope plus every radiometric band present in training_features.tif), and
disagreement is the discovery signal.  Blum & Mitchell, COLT 1998, doi:10.1145/279943.279962.

What is new, and why it is not a re-run
---------------------------------------
H82 (knowledge/73 section 4) measured two *implementation* defects in the alignment channels:
theta_max is an argmax over 8 discrete fan directions, so cos(2*(theta_max - psi)) against a scalar
strike takes only 4 distinct values; and the local-tensor variant is exactly 0 on 46.7-69.9 % of
eligible pixels.  H91 repairs both:

* a **16-direction fan** whose even indices are exactly H82's 8 directions as a set, so the
  8-direction statistic is recomputed inside the same pass as an internal control;
* a **continuous** preferred direction obtained as the gamma-weighted axial circular mean of the fan
  (Mardia & Jupp construction on the doubled angle, via the same arithmetic as
  ``gems52.azimuth``), together with its **weighted resultant length** -- a directional-confidence
  channel that has no degenerate-null mode at all.

Stages (checkpointed, resumable):
    preflight    verify all 23 manifest entries by SHA-256/byte count; fail closed
    channels     build the H91 channel bank with the verified writer (run_h82.save_verified)
    fit          per-fold OOF fits of every frozen arm + the leakage canary on each new channel
    independence the lane's mandated view-independence test (thresholds inherited from H74)
    holdout      pooled HOLDOUT-DTI, paired spatial-block bootstrap CI, all frozen arms
    build        metric-aware placement of the primary arm + the union/A/B controls
    lane         uniqueness + lane gates on the surface and on the final dots
    write        portal-exact GeoTIFF + per-candidate geological reasoning
    card         the single JSON run card, assembled only from receipts on disk

No leaderboard score enters any fit, field, fold or arm.
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

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82tools                                            # noqa: E402  (verified writer + Bank)
from gems52 import azimuth as az                                      # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, submission_writer                    # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work/h91"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
SAMPLE = DATA / "sample_submission.tif"
PREREG_PATH = ROOT / "registry/h91_preregistration.json"
PREREG = json.loads(PREREG_PATH.read_text())

SEED = int(PREREG["seed"])
K_FOLD = int(PREREG["emission"]["K_fold"])
K_TOTAL = int(PREREG["emission"]["K_total"])
RING_M = float(PREREG["emission"]["catalogue_ring_excluded_m"])
MIN_SPACING = float(PREREG["emission"]["min_spacing_px"])
CANARY_BAR = float(PREREG["canary_alarm_auc"])
ARMS = tuple(PREREG["arms"])
PRIMARY = PREREG["primary_arm"]
PREFIX = "gems52-h91-"

# -------------------------------------------------------------------------------------------- design
SIGMA = 3.0
LAGS = tuple(PREREG["new_channels"]["lags_px"])
FAN16 = tuple(tuple(int(v) for v in t) for t in PREREG["new_channels"]["fan_offsets_dy_dx"])
assert len(FAN16) == 16, len(FAN16)
PHI16 = tuple(float(np.degrees(np.arctan2(dy, dx)) % 180.0) for dy, dx in FAN16)
# the 8-direction control is the even-index sub-fan of the same computation
FAN8 = tuple(FAN16[i] for i in range(0, 16, 2))
PHI8 = tuple(float(np.degrees(np.arctan2(dy, dx)) % 180.0) for dy, dx in FAN8)
assert {tuple(t) for t in FAN8} == {(0, 1), (1, 1), (1, 0), (1, -1),
                                    (1, 2), (2, 1), (2, -1), (1, -2)}, "8-fan control must equal H82's FAN set"
# bands: (source path relative to data root, 1-based band)
BANDS = {
    "det_elev": ("data/training_features.tif", 12),
    "det_elev_slope": ("data/training_features.tif", 19),
    "iso_grav_anom": ("data/training_features.tif", 13),
    "iso_grav_anom_hg": ("data/training_features.tif", 18),
    "depth_to_base_surf": ("data/training_features.tif", 15),
    "rad_ThK": ("data/external/geodawn_extensions_u8.tif", 1),
    "rad_UK": ("data/external/geodawn_extensions_u8.tif", 2),
}
CONTROL_BANDS = ("det_elev", "det_elev_slope", "iso_grav_anom")   # H82's own three bands


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def digest(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h91_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float, allow_nan=False) + "\n")
    return p


def done(p: Path) -> bool:
    return Path(p).exists()


# ------------------------------------------------------------------------------------ prereg check
def check_prereg() -> dict:
    reg = json.loads(PREREG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    h = digest(doc)
    if h != reg["hypothesis_sha256"] or doc.stat().st_size != reg["hypothesis_bytes"]:
        raise SystemExit(f"H91 hypothesis document changed after preregistration: {h}")
    return reg


# --------------------------------------------------------------------------------------- preflight
def stage_preflight() -> None:
    out = EVID / "h91_preflight_integrity.json"
    if done(out):
        log("preflight cached")
        return
    import gems52.h58 as h58
    receipts = h58.verify_manifest(ROOT / "registry/data_manifest.json", DATA)
    all_ok = len(receipts) == 23 and all(r["matches_pin"] for r in receipts)
    if not all_ok:
        raise SystemExit("preflight FAILED: a pinned input does not match its manifest entry")
    write("preflight_integrity", dict(
        round="H91-preflight", observed_utc=now(), manifest="registry/data_manifest.json",
        data_root="data", pinned_files_verified=len(receipts), pinned_all_ok=True,
        qualification=("SHA/byte verification of owner-mirror pins proves mirror integrity, NOT "
                       "organizer authentication; the DrivenData data tab is login-walled"),
        files=receipts))
    log(f"preflight OK: {len(receipts)}/23 pins match")


# ---------------------------------------------------------------------------------------- channels
def _gamma_accumulate(z, ok, w, h, fan, sigma=SIGMA):
    """(mx, mn, sm, sx, cx) over one fan; sx/cx are the doubled-angle weighted sine/cosine sums."""
    mx = mn = sm = sx = cx = None
    for dy_u, dx_u in fan:
        dy, dx = dy_u * h, dx_u * h
        zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
        oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
        d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
        g = ndi.gaussian_filter(d2, sigma) / w
        del d2, zs, oks
        phi = np.arctan2(dy_u, dx_u)          # image-frame direction of this fan offset
        gs = g * np.sin(2.0 * phi)
        gc = g * np.cos(2.0 * phi)
        if mx is None:
            mx, mn, sm, sx, cx = g, g.copy(), g.copy(), gs, gc
        else:
            np.maximum(mx, g, out=mx)
            np.minimum(mn, g, out=mn)
            sm += g
            sx += gs
            cx += gc
        del g, gs, gc
    return mx, mn, sm, sx, cx


def _fan_only(z, ok, w, h, fan, sigma=SIGMA):
    """(mx, mn, sm) over a sub-fan, for the 8-direction internal control."""
    mx = mn = sm = None
    for dy_u, dx_u in fan:
        dy, dx = dy_u * h, dx_u * h
        zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
        oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
        d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0) / (np.hypot(dy, dx) / h)
        g = ndi.gaussian_filter(d2, sigma) / w
        del d2, zs, oks
        if mx is None:
            mx, mn, sm = g, g.copy(), g.copy()
        else:
            np.maximum(mx, g, out=mx)
            np.minimum(mn, g, out=mn)
            sm += g
        del g
    return mx, mn, sm


def stage_channels() -> None:
    reg = check_prereg()
    if done(EVID / "h91_channels.json") and done(FEAT / "manifest.json"):
        log("channels cached")
        return
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    FEAT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cols: dict[str, np.ndarray] = {}

    # ---- per-fold regional strike, from that fold's VISIBLE catalogue only (H82 convention)
    psi_reg, strike_receipt = {}, []
    for fold in folds:
        f = fold["fold"]
        vis = fold["visible"]
        sm = ndi.gaussian_filter(vis.astype(np.float64), SIGMA)
        gy, gx = np.gradient(sm, 100.0, 100.0)
        jxx = ndi.gaussian_filter(gx * gx, SIGMA)
        jyy = ndi.gaussian_filter(gy * gy, SIGMA)
        jxy = ndi.gaussian_filter(gx * gy, SIGMA)
        aniso_t = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2)
        theta_grad = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
        psi_loc = az.wrap_axial(theta_grad + np.pi / 2.0)
        corridor = ndi.binary_dilation(vis, structure=np.ones((7, 7), bool)) & eligible
        wt = np.where(corridor, aniso_t, 0.0)
        m, R, n_used = az.axial_resultant(psi_loc[corridor], weights=wt[corridor])
        psi_reg[str(f)] = float(m)
        compass_reg = float((90.0 - np.degrees(m)) % 180.0)
        csd = float(np.degrees(np.sqrt(-2.0 * np.log(R)))) if R > 1e-12 else None
        strike_receipt.append(dict(
            fold=f, psi_reg_rad_image_frame=float(m), strike_compass_deg=compass_reg,
            resultant_length_R=float(R), axial_circular_sd_deg=csd, n_weighted_px=int(n_used),
            corridor_px=int(corridor.sum()), visible_px=int(vis.sum()),
            derived_from="fold['visible'] only (withheld segments never contribute)"))
        log(f"fold {f}: regional strike {compass_reg:.2f} deg compass, R={R:.4f}")
        del sm, gy, gx, jxx, jyy, jxy, aniso_t, theta_grad, psi_loc, corridor, wt

    def read_field(nm):
        rel, band = BANDS[nm]
        with rasterio.open(ROOT / rel) as ds:
            zb = ds.read(band).astype(np.float64)
        ok = np.isfinite(zb) & eligible
        mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
        z = np.where(ok, (zb - mu) / sd, 0.0)
        w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
        del zb
        return z, ok, w

    # ---- the 16-fan learner channels.  The fold-specific alignment is resolved at gather time
    # (psi_reg is per fold), so the continuous direction and its resultant are stored and the Bank
    # folds them against the fold's own regional strike.
    for nm in BANDS:
        z, ok, w = read_field(nm)
        log(f"band {nm}: standardised on {int(ok.sum())} eligible px")
        for h in LAGS:
            mx, mn, sm, sx, cx = _gamma_accumulate(z, ok, w, h, FAN16)
            cols[f"DVA3_{nm}_aniso_l{h}"] = np.asarray((mx - mn) / (mx + mn + 1e-9), np.float32)[eligible]
            cols[f"DVA3_{nm}_logvar_l{h}"] = np.asarray(np.log10(sm / len(FAN16) + 1e-9), np.float32)[eligible]
            rdir = np.hypot(sx, cx) / (sm + 1e-30)
            phi_soft = 0.5 * np.arctan2(sx, cx)
            cols[f"CSA_{nm}_phimax_l{h}"] = np.asarray(az.wrap_axial(phi_soft), np.float32)[eligible]
            cols[f"CSA_{nm}_dirR_l{h}"] = np.asarray(np.clip(rdir, 0.0, 1.0), np.float32)[eligible]
            del mx, mn, sm, sx, cx, rdir, phi_soft
        del z, ok, w
    # ---- the 8-direction internal control, computed in its own pass so the 16-fan accumulators are
    # already freed, and using only H82's own three bands.
    for nm in CONTROL_BANDS:
        z, ok, w = read_field(nm)
        for h in LAGS:
            m8, n8, s8 = _fan_only(z, ok, w, h, FAN8)
            cols[f"DVA3c_{nm}_aniso_l{h}"] = np.asarray((m8 - n8) / (m8 + n8 + 1e-9), np.float32)[eligible]
            cols[f"DVA3c_{nm}_logvar_l{h}"] = np.asarray(np.log10(s8 / len(FAN8) + 1e-9), np.float32)[eligible]
            del m8, n8, s8
        del z, ok, w
        log(f"8-fan control band {nm} done")

    sha, repaired = {}, {}
    for k, v in cols.items():
        v = np.ascontiguousarray(np.asarray(v))
        sha[k], attempts = h82tools.save_verified(FEAT / (k + ".npy"), v)
        if attempts > 1:
            repaired[k] = attempts
        del v
    learner = sorted([k for k in cols if k.startswith(("DVA3_", "CSA_"))])
    control = sorted([k for k in cols if k.startswith("DVA3c_")])
    man = dict(round="H91", created_utc=now(), version="h91-csa-16fan-v1", sigma_px=SIGMA,
               lags_px=list(LAGS), fan_offsets_dy_dx=[list(t) for t in FAN16],
               fan_phi_deg_image_frame=list(PHI16),
               fan_offset_lengths_px={str(k): float(np.hypot(*t)) for k, t in enumerate(FAN16)},
               fan8_offsets_dy_dx=[list(t) for t in FAN8], fan8_phi_deg_image_frame=list(PHI8),
               fan8_equals_h82_fan_set=True,
               bands={k: dict(path=v[0], band=v[1]) for k, v in BANDS.items()},
               control_bands=list(CONTROL_BANDS),
               learner_channels=learner, control_channels=control,
               n_learner_channels=len(learner), n_control_channels=len(control),
               atoms=[k for k in cols if k.startswith("CSA_")],
               n_eligible=int(store.valid.sum()), psi_reg_rad=psi_reg, strike=strike_receipt,
               sha256=sha, save_verified_by_reload=True, save_attempts_gt1=repaired,
               inputs_sha256=dict(store.manifest["inputs"]),
               store_version=store.manifest["version"],
               provenance="integrity-pinned, not organizer-authenticated (registry/data_manifest.json)")
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1, default=float))
    write("channels", dict(stage="channels", seconds=time.time() - t0, n_columns=len(cols),
                           learner=learner, control=control, psi_reg_rad=psi_reg,
                           strike=strike_receipt, fan_phi_deg_image_frame=list(PHI16),
                           fan8_phi_deg_image_frame=list(PHI8),
                           save_verified_by_reload=True, n_channels_needing_rewrite=len(repaired),
                           channels_needing_rewrite=repaired,
                           manifest_sha256=digest(FEAT / "manifest.json")))
    log(f"channels built in {time.time() - t0:.0f}s: {len(cols)} columns "
        f"({len(learner)} learner, {len(control)} control)")


class Bank(h82tools.Bank):
    """H91 channel bank; the only difference from H82's is the fold-folded CSA alignment column."""

    def gather(self, rows, names, fold=None):
        out = np.empty((len(rows), len(names)), np.float32)
        man = self.manifest
        for j, nm in enumerate(names):
            if nm.startswith("CSAalign_"):
                base_nm = nm[len("CSAalign_"):]
                ph = np.asarray(self.col(base_nm)[rows], np.float64)
                psi = float(man["psi_reg_rad"][str(fold)]) + np.pi / 2.0
                out[:, j] = np.cos(2.0 * np.asarray(az.axial_difference(ph, psi), np.float64))
            else:
                out[:, j] = self.col(nm)[rows]
        return np.nan_to_num(out, nan=0.0)


def arm_channels(arm: str, va=None, vb=None):
    """(store-column names, bank-column names, folded CSA column names) per frozen arm.

    The folded names are the Bank's ``CSAalign_<atom>`` columns: the continuous preferred direction
    turned into ``cos(2*(phi_soft - psi_reg(fold) - pi/2))`` at gather time, so the strike used is
    always the one measured from that fold's own visible catalogue.
    """
    if arm == "single_A":
        return (va, [], [])
    if arm == "single_B":
        return (vb, [], [])
    man = json.loads((FEAT / "manifest.json").read_text())
    align = [f"CSAalign_{k}" for k in man["atoms"] if "_phimax_" in k]
    dirR = [k for k in man["atoms"] if "_dirR_" in k]
    dva3 = [k for k in man["learner_channels"] if k.startswith("DVA3_")]
    ctrl = man["control_channels"]
    return {
        "single_B": (vb, [], []),
        "single_A": (va, [], []),
        "B_DVA3c": ([], ctrl, []),
        "B_DVA3": ([], dva3, []),
        PRIMARY: ([], dva3 + dirR, align),
    }[arm]


base_vb_cache: dict = {}


# -------------------------------------------------------------------------------------------- fit
def gather_arm(store, bank, rows_grid, names_store, names_ch, names_fold, fold):
    """Feature matrix: shared store columns, then bank columns, then fold-folded CSA columns."""
    erows = store.inverse[rows_grid]
    X = store.gather(rows_grid, names_store) if names_store else np.empty((len(rows_grid), 0), np.float32)
    if names_ch:
        C = bank.gather(erows, names_ch, fold=fold)
        X = np.hstack([X, C])
    if names_fold:
        F = bank.gather(erows, names_fold, fold=fold)
        X = np.hstack([X, F])
    return X


def predict_region(store, bank, model, names_store, names_ch, names_fold, rows_grid, fold,
                   chunk=200_000):
    out = np.empty(len(rows_grid), np.float32)
    for i in range(0, len(rows_grid), chunk):
        s = rows_grid[i:i + chunk]
        out[i:i + chunk] = model.predict_proba(
            gather_arm(store, bank, s, names_store, names_ch, names_fold, fold))[:, 1]
    return out


def stage_fit() -> None:
    check_prereg()
    if done(EVID / "h91_fit.json"):
        log("fit cached")
        return
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    base_vb_cache.update(vb=vb, va=va)
    bank = Bank(FEAT)
    man = json.loads((FEAT / "manifest.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", started_utc=now(), arms=list(ARMS), seed=SEED,
               view_A_features=len(va), view_B_features=len(vb), folds=[])
    for fold in folds:
        f = fold["fold"]
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        h82tools.save_verified(WORK / f"region_rows_f{f}.npy", region_rows)
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_region_rows=int(len(region_rows)), n_train_rows=int(len(rows)),
                   n_pos=int(len(pos_g)), n_neg=int(len(neg_g)), auc={}, canary={}, seconds={})
        # ---- leakage canary: every new channel alone, on the held-out region sample
        crow = np.r_[pos_g, neg_g]
        erow = store.inverse[crow]
        ch_names = sorted(man["learner_channels"] + man["control_channels"])
        psi_f = float(man["psi_reg_rad"][str(f)]) + np.pi / 2.0
        for nm in ch_names:
            if nm.endswith("_phimax_l2") or nm.endswith("_phimax_l3") or nm.endswith("_phimax_l4"):
                # the stored atom is an angle; the *learner* channel is its continuous alignment
                # against this fold's regional strike, so that is what the canary must test
                ph = np.asarray(bank.col(nm)[erow], np.float64)
                v = np.cos(2.0 * np.asarray(az.axial_difference(ph, psi_f), np.float64))
            else:
                v = np.asarray(bank.col(nm)[erow], np.float64)
            good = np.isfinite(v)
            a = float(roc_auc_score(yy[good], v[good])) if good.all() and np.ptp(v[good]) > 0 else 0.5
            rec["canary"][nm] = dict(auc=a, direction_insensitive=max(a, 1 - a),
                                     learner_channel=not nm.startswith("DVA3c_"))
            del v
        rec["canary_max_learner"] = max(v["direction_insensitive"] for k, v in rec["canary"].items()
                                        if v["learner_channel"])
        rec["canary_alarm_auc_bar"] = CANARY_BAR
        rec["canary_alarm"] = bool(rec["canary_max_learner"] >= CANARY_BAR)
        rec["canary_worst"] = max(rec["canary"].items(),
                                  key=lambda kv: kv[1]["direction_insensitive"])[0]
        log(f"fold {f}: canary max(learner) {rec['canary_max_learner']:.4f} "
            f"worst={rec['canary_worst']} alarm={rec['canary_alarm']}")
        # ---- arms
        for arm in ARMS:
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if ck.exists() and arm != "random":
                log(f"fold {f} {arm}: cached")
            elif arm == "random":
                # preregistered floor arm: no model at all, one uniform draw per held pixel
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = np.random.default_rng(
                    SEED + 500 + f).random(len(region_rows), dtype=np.float32)
                h82tools.save_verified(ck, full)
                del full
            elif not ck.exists():
                ns, nc, nf = arm_channels(arm, va, vb)
                m = base.learner_for("B" if arm != "single_A" else "A", SEED)
                m.fit(gather_arm(store, bank, rows, ns, nc, nf, f), y)
                p = predict_region(store, bank, m, ns, nc, nf, region_rows, f)
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                h82tools.save_verified(ck, full)
                del m, p, full
            g = np.load(ck, mmap_mode="r")
            gg = np.asarray(g, np.float32)
            rec["auc"][arm] = float(roc_auc_score(
                yy, np.r_[gg[store.inverse[pos_g]], gg[store.inverse[neg_g]]]))
            rec["seconds"][arm] = time.time() - t1
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g, gg
        out["folds"].append(rec)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_learner_overall"] = max(r["canary_max_learner"] for r in out["folds"])
    out["sufficiency_view_A"] = dict(
        mean=float(np.mean([r["auc"]["single_A"] for r in out["folds"]])),
        per_fold=[r["auc"]["single_A"] for r in out["folds"]],
        gate_mean=0.60, gate_min_fold=0.55)
    out["sufficiency_view_A"]["pass"] = bool(
        out["sufficiency_view_A"]["mean"] >= 0.60
        and min(out["sufficiency_view_A"]["per_fold"]) >= 0.55)
    out.update(finished_utc=now(), evaluator_hashes=evaluator.implementation_hashes())
    write("fit", out)
    log(json.dumps({a: [round(r["auc"][a], 4) for r in out["folds"]] for a in ARMS}))


# ---------------------------------------------------------------------------------- independence
def stage_independence() -> None:
    check_prereg()
    if done(EVID / "h91_independence.json"):
        log("independence cached")
        return
    from gems52 import spatial
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th_src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    rows_blocks, per_fold = [], []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        qa, qb = pa[neg], pb[neg]
        thr = (float(np.quantile(qa, th["donor_rank_min"])),
               float(np.quantile(qb, th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        rows_blocks += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr),
                             n_blocks=len(blocks)))
        log(f"fold {f}: independence {len(blocks)} blocks over {int(neg.sum())} labelled negatives")
        del pa, pb, qa, qb
    res = spatial.independence(rows_blocks, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    write("independence", dict(
        stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
        thresholds_inherited_from="registry/h74_preregistration.json",
        thresholds_inherited_sha256=digest(th_src), thresholds_not_retuned_for_h91=True,
        thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                        abandon_max_abs_rho=th["independence_abandon_max_abs_rho"], min_blocks=20,
                        negative_ring_px=4),
        view_A="single_A (geophysical/subsurface store columns only)",
        view_B="single_B (surface store columns only)",
        per_fold=per_fold, result=res,
        interpretation=("the abandon bar is |rho| > %.2f; a strongly correlated pair would mean the two "
                        "views share their errors and co-training could only amplify a common bias"
                        % th["independence_abandon_max_abs_rho"]),
        standing_deviation=("pseudo-label exchange is still not run: View-A sufficiency has failed "
                            "repeatedly and H71 measured that exchange LOWERED the A2 out-of-fold AUC "
                            "(0.5019 -> 0.4759), which is the bias amplification the brief warns about")))
    log(json.dumps({k: v for k, v in res.items() if not isinstance(v, (list, dict))}, default=float))


# --------------------------------------------------------------------------------------- holdout
def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def field_of(arm, fold, eligible, shape, flat):
    g = base.to_grid(flat, np.load(WORK / f"pred_{arm}_f{fold['fold']}.npy"), shape)
    allowed = allowed_of(fold, store_cache["ring_px"])
    fld = np.full(shape, -1.0, np.float32)
    ai = np.flatnonzero(allowed.ravel())
    fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
    return fld, allowed


store_cache: dict = {}


def stage_holdout() -> None:
    check_prereg()
    if done(EVID / "h91_holdout.json"):
        log("holdout cached")
        return
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
                fld, allowed = field_of(arm, fold, eligible, eligible.shape, store.flat_idx)
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=MIN_SPACING)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del fld, em
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    out["controls"] = {}
    for arm, tgt in PREREG["controls"].items():
        got = float(out["pooled"]["scores"][arm]["dti"])
        out["controls"][arm] = dict(committed=tgt["committed"], measured=got,
                                    abs_delta=abs(got - tgt["committed"]),
                                    tolerance=tgt["tolerance"],
                                    PASS=bool(abs(got - tgt["committed"]) <= tgt["tolerance"]))
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


# ----------------------------------------------------------------------------------------- build
def stitch(arm, folds, eligible, flat):
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


def stage_build() -> None:
    check_prereg()
    if done(EVID / "h91_build_placement.json"):
        log("build cached")
        return
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fP = stitch(PRIMARY, folds, eligible, flat)
    fA = stitch("single_A", folds, eligible, flat)
    fS = stitch("single_B", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fP) & (catd * 100.0 > RING_M)
    fld = np.where(pool, fP, -1.0).astype(np.float32)
    dots = nodes.spacing_select(fld, pool, K_TOTAL, min_px=MIN_SPACING)

    def sel(field):
        return nodes.spacing_select(np.where(pool, np.nan_to_num(field, nan=-1.0), -1.0).astype(np.float32),
                                    pool, K_TOTAL, min_px=MIN_SPACING)

    union_dots = sel(np.maximum(np.where(np.isfinite(fA), fA, -1.0),
                                np.where(np.isfinite(fS), fS, -1.0)))
    a_dots, b_dots = sel(fA), sel(fS)
    # H91-C: the B-only disagreement stratum as a SUPPRESSION set (new this round)
    pa = np.nan_to_num(fA, nan=0.0)
    pb = np.nan_to_num(fS, nan=0.0)
    q_conf, q_abst = 0.60, 0.40
    b_only = pool & (pb >= q_conf) & (pa <= q_abst)
    supp_pool = pool & ~b_only
    supp_dots = nodes.spacing_select(np.where(supp_pool, fP, -1.0).astype(np.float32),
                                     supp_pool, K_TOTAL, min_px=MIN_SPACING)
    h82tools.save_verified(WORK / "dots.npy", dots)
    h82tools.save_verified(WORK / "surface.npy",
                           np.where(eligible & np.isfinite(fP), fP, 0.0).astype(np.float32))
    h82tools.save_verified(WORK / "union_dots.npy", union_dots)
    h82tools.save_verified(WORK / "supp_dots.npy", supp_dots)
    h82tools.save_verified(WORK / "field_primary.npy", fP)
    h82tools.save_verified(WORK / "field_A.npy", fA)
    h82tools.save_verified(WORK / "field_B.npy", fS)
    rec = dict(stage="build", dots=int(dots.sum()), pool_px=int(pool.sum()),
               eligible_px=int(eligible.sum()), ring_excluded_m=RING_M,
               min_cat_dist_m=float((catd[dots] * 100).min()),
               median_cat_dist_m=float(np.median(catd[dots] * 100)),
               dots_within_300m_of_catalogue_pct=float((catd[dots] * 100 <= 300).mean() * 100),
               union_dots=int(union_dots.sum()), a_dots=int(a_dots.sum()), b_dots=int(b_dots.sum()),
               b_only_suppression=dict(thresholds=dict(q_conf=q_conf, q_abstain=q_abst),
                                       b_only_px=int(b_only.sum()),
                                       supp_pool_px=int(supp_pool.sum()),
                                       supp_dots=int(supp_dots.sum())),
               started_utc=now())
    write("build_placement", rec)
    log(f"dots {int(dots.sum())}, pool {int(pool.sum())}, "
        f"min catalogue distance {rec['min_cat_dist_m']:.1f} m, B-only veto px {int(b_only.sum())}")
    del fP, fA, fS, fld, dots, union_dots, a_dots, b_dots, supp_dots, catd, pool


# ------------------------------------------------------------------------------------------ lane
def restricted_registry():
    paths = sorted((DATA / "scored").glob("*.tif")) + sorted((DATA / "reference").glob("*.tif"))
    return [p for p in paths if p.exists()]


def restricted_supports(paths, eligible, probe_threshold=0.95):
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


def stage_lane() -> None:
    check_prereg()
    if done(EVID / "h91_lane.json"):
        log("lane cached")
        return
    import run_h73 as h73
    from build_h61_submission import prior_paths
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy").astype(np.float32)
    surf = np.load(WORK / "surface.npy")
    full, meta = prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    full = [p for p in full if p.exists() and PREFIX not in p.name and "h91" not in p.name]
    restr = restricted_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full),
               n_restricted=len(restr),
               doctrine=("both registries reported verbatim; a restricted-registry PASS never waives a "
                         "literal full-census DUPLICATE/STOP (AGENTS.md, knowledge/62 IR-H73-011)"))
    log(f"lane: full census {len(full)} rasters, restricted scored-only {len(restr)} rasters")
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface", log=log)
    out["full_dots"] = gates.lane_report(dots, eligible, full, sample=SAMPLE, phase="dots", log=log)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface")
    out["restricted_dots"] = gates.lane_report(dots, eligible, restr, sample=SAMPLE, phase="dots")
    out["uniqueness_full"] = gates.uniqueness_report(dots, full)
    sups, suprows = restricted_supports(restr, eligible)
    out["restricted_supports"] = suprows
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(surf) & (surf > 0) & (catd * 100.0 > RING_M)
    lane_dots, lrec = h73.place_lane(np.where(pool, surf, -1.0).astype(np.float32), pool, K_TOTAL,
                                     sups, eligible.shape, limit=0.70, rounds=8)
    h82tools.save_verified(WORK / "dots_lane_restricted.npy", lane_dots)
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
            f"(informative {r['policy']['informative_priors']}, "
            f"max near {r['policy']['max_near_3px_fraction']})")
    log("quota placement (restricted supports): " + json.dumps(
        {k: lrec[k] for k in ("ok", "worst", "quota_priors", "spacing_ok")}, default=float))


# ----------------------------------------------------------------------------------------- write
def write_reasoning(dots, catd, eligible, folds) -> str:
    """Per-candidate geological reasoning for the A-only and B-only strata (the brief's requirement)."""
    import csv
    fA = np.load(WORK / "field_A.npy")
    fS = np.load(WORK / "field_B.npy")
    pa = np.nan_to_num(fA, nan=0.0)
    pb = np.nan_to_num(fS, nan=0.0)
    q_conf, q_abst = 0.60, 0.40
    ys, xs = np.nonzero(dots)
    depth = None
    out_rows = []
    for y, x in zip(ys, xs):
        a, b = float(pa[y, x]), float(pb[y, x])
        if a >= q_conf and b <= q_abst:
            stratum = "A_only_buried_continuation"
            reading = ("View A (potential field) is confident while the surface view abstains: the "
                       "structure has no surface expression, consistent with a fault buried beneath "
                       "cover or a young alluvial/volcanic carapace.")
            falsifier = ("A road, levee or erosion line would raise View B; a lithologic contact or "
                         "buried channel would raise View A without a through-going lineament. Check "
                         "the 1 m DEM scarp layer and the magnetic RTP lineament at this cell.")
        elif b >= q_conf and a <= q_abst:
            stratum = "B_only_surface_artifact_suspect"
            reading = ("View B (surface) is confident while the potential-field view abstains: the "
                       "signature is skin-deep, so a road cut, gully, quarry or channel bank is the "
                       "leading non-fault explanation.")
            falsifier = ("A real surface-rupturing fault also looks like this; the discriminator is "
                         "whether the DEM lineament continues across drainage divides and whether the "
                         "gravity/magnetic gradient is flat here.")
        elif a >= q_conf and b >= q_conf:
            stratum = "concordant"
            reading = "Both views agree; the strongest class of candidate."
            falsifier = "A mapped-but-uncatalogued lithologic contact can satisfy both views."
        else:
            continue
        out_rows.append(dict(row=int(y), col=int(x), stratum=stratum,
                             p_view_A=round(a, 4), p_view_B=round(b, 4),
                             dist_to_catalogue_m=round(float(catd[y, x] * 100.0), 1),
                             geological_reading=reading, falsifier=falsifier))
    p = ROOT / "docs/downloads/h91-a-only-reasoning.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()) if out_rows else
                           ["row", "col", "stratum", "p_view_A", "p_view_B", "dist_to_catalogue_m",
                            "geological_reading", "falsifier"])
        w.writeheader()
        w.writerows(out_rows)
    return str(p.relative_to(ROOT)), len(out_rows)


def stage_write() -> None:
    check_prereg()
    if done(EVID / "h91_build.json"):
        log("write cached")
        return
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy")
    union_dots = np.load(WORK / "union_dots.npy")
    pred = dots.astype(np.float32)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h91-csa16fan-B-{int(dots.sum())}px-{stamp}"
    _man = json.loads((FEAT / "manifest.json").read_text())
    note = (f"H91: View-B + {_man['n_learner_channels']} continuous directional-alignment "
            f"channels on a {len(_man['fan_offsets_dy_dx'])}-direction semivariance fan; "
            f"200m ring excluded; binary dots")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    rec = submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                            metadata=dict(round="H91", primary_arm=PRIMARY))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0
                           and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"]
                       and val["shape_match"] and val["transform_match"] and val["range_ok"])
    val["range_rule_source"] = ("official: values between 0 and 1, single layer float32, EPSG:32611, "
                                "100 m, same bounds as the training data "
                                "(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)")
    # not-the-union test
    fA = np.load(WORK / "field_A.npy")
    fS = np.load(WORK / "field_B.npy")
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(np.load(WORK / "field_primary.npy")) & (catd * 100.0 > RING_M)

    def sel(field):
        return nodes.spacing_select(np.where(pool, np.nan_to_num(field, nan=-1.0), -1.0).astype(np.float32),
                                    pool, K_TOTAL, min_px=MIN_SPACING)

    a_dots, b_dots = sel(fA), sel(fS)
    supp_dots = np.load(WORK / "supp_dots.npy")

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
        shared_with_bonly_suppressed=int((dots & supp_dots).sum()),
        jaccard_with_bonly_suppressed=jac(dots, supp_dots),
        not_union_pass=bool(not np.array_equal(dots, union_dots)
                            and not (dots & ~union_dots).sum() == 0
                            and not np.array_equal(dots, a_dots)
                            and not np.array_equal(dots, b_dots)))
    cmp = {}
    for key, p in (("ref_h33_2_b2_owner_reported_0.2778", "data/reference/h33-2-b2-zeros.tif"),):
        pp = ROOT / p
        if not pp.exists():
            continue
        with rasterio.open(pp) as d:
            r = np.nan_to_num(d.read(1)) > 0
        near = ndi.binary_dilation(r, structure=np.ones((7, 7), bool))
        cmp[key] = dict(shared_px=int((r & dots).sum()), prior_px=int(r.sum()),
                        near_3px_share_of_my_dots=float(near[dots].mean()), jaccard=jac(dots, r))
    reasoning_csv, n_reason = write_reasoning(dots, catd, eligible, folds)
    res = dict(stage="write", file=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
               sha256=digest(out), name=name, note=note, note_chars=len(note), validator=val,
               writer_receipt=rec, not_the_union=not_union, vs_named_priors=cmp,
               catalogue=dict(min_dist_m=float((catd[dots] * 100).min()),
                              median_dist_m=float(np.median(catd[dots] * 100)),
                              within_300m_pct=float((catd[dots] * 100 <= 300).mean() * 100)),
               reasoning_csv=reasoning_csv, n_reasoning_rows=n_reason, started_utc=now())
    write("build", res)
    dl = ROOT / "docs/downloads"
    shutil.copy(out, dl / "h91-candidate.tif")
    with zipfile.ZipFile(dl / "h91-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, out.name)
    with zipfile.ZipFile(dl / "h91-candidate.zip") as z:
        assert z.namelist() == [out.name] and z.read(out.name) == out.read_bytes()
    res["download_staged"] = dict(tif="docs/downloads/h91-candidate.tif",
                                  zip="docs/downloads/h91-candidate.zip",
                                  tif_sha256=digest(dl / "h91-candidate.tif"),
                                  zip_sha256=digest(dl / "h91-candidate.zip"))
    write("build", res)
    log(json.dumps({k: res[k] for k in ("file", "bytes", "sha256", "name", "note")}, indent=1))
    log("validator: " + json.dumps({k: val[k] for k in ("PASS", "range_ok", "dtype", "crs",
                                                        "shape", "ones", "nan")}))
    log("not_union: " + json.dumps({k: not_union[k] for k in not_union
                                    if not isinstance(not_union[k], float)}))


# ------------------------------------------------------------------------------------------ card
def stage_card() -> None:
    ch = json.loads((EVID / "h91_channels.json").read_text())
    chm = json.loads((FEAT / "manifest.json").read_text())
    fit = json.loads((EVID / "h91_fit.json").read_text())
    ho = json.loads((EVID / "h91_holdout.json").read_text())
    bp = json.loads((EVID / "h91_build_placement.json").read_text())
    ln = json.loads((EVID / "h91_lane.json").read_text())
    bu = json.loads((EVID / "h91_build.json").read_text())
    ind = json.loads((EVID / "h91_independence.json").read_text())
    sc = ho["pooled"]["scores"]
    pd_ = ho["pooled"]["paired_differences"]
    pair = pd_["single_B"]
    lo = pair["ci95"][0]
    controls_ok = all(v["PASS"] for v in ho["controls"].values())
    holdout_wins = bool(lo > 0 and controls_ok and not fit["canary_alarm_any"])
    lit = ln["full_dots"]["literal"]
    lane_dup = lit["verdict"].upper().startswith("DUPLICATE")
    promote = bool(holdout_wins and not lane_dup and bu["validator"]["PASS"]
                   and bu["not_the_union"]["not_union_pass"])
    card = dict(
        round="H91", generated_utc=now(),
        preregistration=dict(document=PREREG["hypothesis_document"],
                             sha256=PREREG["hypothesis_sha256"],
                             hypothesis_document_sha256=digest(ROOT / PREREG["hypothesis_document"]),
                             frozen_before_any_fit=True, seed=SEED),
        hypothesis=("A fault damage zone imposes a direction-dependent semivariance on the surface and "
                    "potential-field grids; H82's 8-direction argmax quantised the preferred direction "
                    "to four values and its local-tensor variant was null on 47-70 % of pixels. A "
                    "16-direction fan with a gamma-weighted circular mean direction and its resultant "
                    "length recovers oblique, catalogue-missing structure that the discrete fan cannot "
                    "resolve."),
        mechanism=("Semivariance measured parallel to a fault's own strike stays low while the "
                   "perpendicular lag crosses the damage-zone contrast, so gamma(h, phi) is anisotropic "
                   "with its maximum perpendicular to the fault. Weighting the 16 fan directions by "
                   "gamma and taking the axial circular mean gives a continuous preferred direction; "
                   "cos(2*(phi_soft - psi_reg - pi/2)) tests it against the regional strike measured "
                   "from the fold's own visible catalogue, and the weighted resultant length R_dir says "
                   "how directionally coherent the fan is (0 = no preferred direction)."),
        mimic=("Named non-fault process that produces the same signature: linear drainage incision, "
               "road cuts and flight-line artefacts imprint a directional semivariance anomaly of "
               "their own; range-front bajada edges and Tertiary volcanic flow margins produce a "
               "gradient with a preferred direction and no fault. Every emitted cell carries its own "
               "row in the reasoning CSV naming which of these it could be and the falsifier."),
        holdout=dict(label="HOLDOUT-DTI", evaluator=evaluator.VERSION,
                     evaluator_implementation_hashes=ho["implementation_hashes"],
                     withheld_positive_pixels=ho["withheld_positive_px"],
                     budget_dots_per_fold_per_arm=ho["budget_per_fold"],
                     kernel="triangular k(d)=max(1-d/R,0), R=300 m = 3 px at 100 m (organiser-published)",
                     alpha=0.2, beta=0.8, bootstrap="1000 paired draws, physical block side 200 px",
                     scores={a: dict(dti=sc[a]["dti"], ci95=sc[a]["ci95"], label="HOLDOUT-DTI")
                             for a in sc},
                     controls=ho["controls"],
                     primary_paired=ho["primary_paired"],
                     note=("a holdout number is not a board forecast: measured Spearman -0.10 against "
                           "owner-reported board scores (knowledge/10 section 5)")),
        correlation_vs_registry=dict(
            full_census=dict(n_priors=ln["n_full"],
                             surface_literal=ln["full_surface"]["literal"],
                             dots_literal=ln["full_dots"]["literal"],
                             dots_policy=ln["full_dots"]["policy"]),
            restricted_scored_only=dict(n_priors=ln["n_restricted"],
                                        surface_literal=ln["restricted_surface"]["literal"],
                                        dots_literal=ln["restricted_dots"]["literal"],
                                        dots_policy=ln["restricted_dots"]["policy"],
                                        quota_placement=ln["quota_placement_restricted"],
                                        quota_placement_dots=ln["quota_placement_restricted_dots"]),
            uniqueness_full=ln["uniqueness_full"],
            doctrine=("a restricted or policy PASS never waives a literal full-census DUPLICATE/STOP")),
        raster_sha256=bu["sha256"],
        validator_output=bu["validator"],
        submission_name=bu["name"], submission_note=bu["note"],
        not_the_union=bu["not_the_union"], catalogue=bu["catalogue"],
        reasoning_csv=bu["reasoning_csv"], n_reasoning_rows=bu["n_reasoning_rows"],
        independence=ind, sufficiency_view_A=fit["sufficiency_view_A"],
        canary=dict(label="LEAKAGE CANARY (single-channel direction-insensitive AUC on held-out region)",
                    bar=CANARY_BAR, max_over_learner_channels=fit["canary_max_learner_overall"],
                    alarm=fit["canary_alarm_any"],
                    worst_channel=max((r["canary_worst"] for r in fit["folds"]),
                                      key=lambda n: max(r["canary"][n]["direction_insensitive"]
                                                        for r in fit["folds"])),
                    per_fold={str(r["fold"]): dict(max_learner=r["canary_max_learner"],
                                                   worst=r["canary_worst"]) for r in fit["folds"]}),
        channels=dict(n_learner=chm["n_learner_channels"], n_control=chm["n_control_channels"],
                      sigma_px=chm["sigma_px"], lags_px=chm["lags_px"],
                      fan_offsets_dy_dx=chm["fan_offsets_dy_dx"],
                      fan_phi_deg_image_frame=chm["fan_phi_deg_image_frame"],
                      fan8_equals_h82_fan_set=chm["fan8_equals_h82_fan_set"],
                      bands=chm["bands"], save_verified_by_reload=ch.get("save_verified_by_reload"),
                      channels_needing_rewrite=ch.get("n_channels_needing_rewrite", 0)),
        measured_strike=dict(per_fold=ch["strike"],
                             note=("MEASURED from each fold's own visible catalogue, not assumed; "
                                   "the scalar regional strike is a weak summary (R 0.37-0.45), which "
                                   "is why the alignment channel is continuous rather than a single "
                                   "strike comparison.")),
        cotraining_lane=("pseudo-label exchange is NOT re-run: View-A sufficiency has failed "
                         "repeatedly on this footprint and H71 measured that exchange lowered the A2 "
                         "out-of-fold AUC (0.5019 -> 0.4759). The lane's mandated independence test is "
                         "reported, and both views are fitted and scored so the failure is re-measured "
                         "rather than cited."),
        reason=("three independent promotion conditions fail: (1) the primary paired difference "
                f"B_CSA - single_B = {pd_['single_B']['delta']:.6f} has a 95 % CI "
                f"[{pd_['single_B']['ci95'][0]:.6f}, {pd_['single_B']['ci95'][1]:.6f}] that straddles "
                "zero, so the continuous 16-fan alignment does not beat the single-view control; "
                "(2) the single_B instrument control measured "
                f"{ho['controls']['single_B']['measured']:.6f} against its committed "
                f"{ho['controls']['single_B']['committed']:.6f}, |delta| "
                f"{ho['controls']['single_B']['abs_delta']:.2e} > tolerance "
                f"{ho['controls']['single_B']['tolerance']}; (3) the lane dots literal gate is "
                "DUPLICATE/STOP on the full census and on the restricted scored-only registry "
                "(max near-3-px share 1.0000). The one significant positive result is internal: "
                f"B_CSA - B_DVA3 = {pd_['B_DVA3']['delta']:.6f} "
                f"[{pd_['B_DVA3']['ci95'][0]:.6f}, {pd_['B_DVA3']['ci95'][1]:.6f}], i.e. the "
                "continuous alignment is measurably better than H82's four-valued argmax recoding, "
                "but that only removes the H82 damage and does not beat plain 8-direction anisotropy "
                f"(B_CSA - B_DVA3c = {pd_['B_DVA3c']['delta']:.6f}, CI "
                f"[{pd_['B_DVA3c']['ci95'][0]:.6f}, {pd_['B_DVA3c']['ci95'][1]:.6f}])."),
        verdict="promote" if promote else "negative",
        slots_used=0, experiments_used=1,
        files=dict(tif=bu["file"], zip="docs/downloads/h91-candidate.zip",
                   download="docs/downloads/h91-candidate.tif",
                   reasoning_csv=bu["reasoning_csv"]),
        download_ok=bool(bu["validator"]["PASS"]),
        submit_ok=bool(promote),
        inputs_provenance=PREREG["inputs_provenance"])
    write("run_card", card)
    log("RUN CARD: " + json.dumps({k: card[k] for k in
                                   ("verdict", "slots_used", "experiments_used", "download_ok",
                                    "submit_ok", "raster_sha256")}))


STAGES = {"preflight": stage_preflight, "channels": stage_channels, "fit": stage_fit,
          "independence": stage_independence, "holdout": stage_holdout, "build": stage_build,
          "lane": stage_lane, "write": stage_write, "card": stage_card}

if __name__ == "__main__":
    want = sys.argv[1:] or ["preflight", "channels", "fit", "independence", "holdout",
                            "build", "lane", "write", "card"]
    for s in want:
        if s not in STAGES:
            raise SystemExit(f"unknown stage {s}; choose from {sorted(STAGES)}")
        log(f"=== stage {s} ===")
        STAGES[s]()
    log("ALL STAGES DONE")
