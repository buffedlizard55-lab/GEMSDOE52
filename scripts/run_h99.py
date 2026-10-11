#!/usr/bin/env python3
"""H99 -- texture View A: does directional variogram anisotropy make the failing view sufficient?

Lane
----
The brief's co-training paragraph.  View A is potential-field and subsurface; View B is surface
(DEM curvature/slope plus the radiometric bands present in ``training_features.tif``); the discovery
signal is disagreement.

Why this round exists
---------------------
The repository has measured its View A (H61's *raw* potential-field channels) below chance eight
times (mean spatial-block OOF AUC 0.5163, min fold 0.4309) while its View B sits at 0.684.  Every
DVA (directional variogram anisotropy) channel ever computed here used bands 12, 19, 13, 15, 18
(``scripts/run_h82.py`` ``BANDS``).  Bands 2 (``rtp``), 9 (``tmi_vg``) and 6 (radiometric total
count by bytes, IR-H85-005) have never carried a variogram anisotropy channel.  H99 replaces the
*failing view's representation* -- amplitude -> boundary texture -- and leaves the working view's
machinery alone.

Shared tools, never forked
--------------------------
``run_h61.setup`` (store, folds, thresholds), ``gems52.spatial.folds`` (label-blind quadrants),
``gems52.evaluate_holdout`` (``gems52-pooled-hide-v1``), ``gems52.nodes.spacing_select``,
``gems52.azimuth`` (axial statistics for the regional strike receipt).

Stages (each checkpointed under ``work/h99`` and ``evidence/h99_*.json``)
------------------------------------------------------------------------
    channels  36 new DVA channels (6 bands x 3 lags x {aniso, logvar}) + regional-strike receipt
    fit       per-fold, per-view learner + leakage canary + sufficiency AUC; VSA-style independence
              screen on labelled negatives in 200 px blocks (the brief's own test)
    holdout   matched-budget hide-and-recover DTI for 5 arms with paired 95% CIs

Usage: python3 scripts/run_h99.py [channels|fit|holdout|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
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
from scipy.stats import rankdata                                      # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import nodes                                              # noqa: E402

SEED = base.SEED
# The runner is registry-driven, not round-specific: one implementation serves every texture
# co-training round, so there is never a private fork of the science.  ``H99_PREREG`` selects the
# frozen registry; everything below (bands, lags, sigma, round name, evidence prefix) is read from it.
PREREG = Path(os.environ.get("H99_PREREG", ROOT / "registry/h99_preregistration.json"))
FEATURES = ROOT / "data/training_features.tif"
CANARY_ALARM = 0.90
FAN = ((0, 1), (1, 1), (1, 0), (1, -1), (1, 2), (2, 1), (2, -1), (1, -2))

BAND_TAGS = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_anom_slope",
    6: "tc_radiometric", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg",
    10: "deq_n100a15", 11: "iso_grav_anom_vg", 12: "det_elev", 13: "iso_grav_anom",
    14: "tmi", 15: "depth_to_base_surf", 16: "ieq_n100a15", 17: "cond_surf",
    18: "iso_grav_anom_hg", 19: "det_elev_slope",
}


def _load_config():
    reg = json.loads(PREREG.read_text())
    rnd = reg["round"]
    cfg = dict(reg=reg, round=rnd, work=ROOT / f"work/{rnd.lower()}",
               evidence_prefix=f"{rnd.lower()}_",
               view_a={int(k): BAND_TAGS[int(k)] for k in reg["view_a_bands"]},
               view_b={int(k): BAND_TAGS[int(k)] for k in reg["view_b_bands"]},
               lags=tuple(reg["lags_px"]), sigma=float(reg["sigma_px"]),
               arms=tuple(reg["arms"]), primary=reg["primary_arm"],
               ring_px=int(round(reg["thresholds"]["catalogue_exclusion_m"] / 100.0)),
               k_fold=int(reg["thresholds"]["budget_dots_per_fold_per_arm"]))
    return cfg


CFG = _load_config()
ROUND = CFG["round"]
WORK = CFG["work"]
FEAT = WORK / "features"
EVID = ROOT / "evidence"
EVID_PREFIX = CFG["evidence_prefix"]
K_FOLD = CFG["k_fold"]
RING_PX = CFG["ring_px"]
SIGMA = CFG["sigma"]
LAGS = CFG["lags"]
VIEW_A_BANDS = CFG["view_a"]
VIEW_B_BANDS = CFG["view_b"]
ARMS = CFG["arms"]
PRIMARY = CFG["primary"]


def log(*a):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"{EVID_PREFIX}{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    log(f"wrote {p}")
    return p


def save_verified(path, v, tries=8, pause=0.25):
    """Persist bit-exactly: write, fsync, then compare the RAW FILE BYTES with the in-memory image.

    IR-H99-001 (this round): the array-compare version used in H99's first channels build passed
    while a whole 4 KiB page of the file was zero.  A byte-for-byte comparison against
    ``hdr + want.tobytes()`` catches exactly that failure (992 float32 = 3,968 bytes = one page).
    Detection at write time is necessary but not sufficient -- this sandbox also loses pages
    *after* a verified write, so every consumer must verify at read time (``Bank.col``) and
    ``heal_channels`` rewrites whatever fails.
    """
    import io
    want = np.ascontiguousarray(np.asarray(v))
    buf = io.BytesIO()
    np.save(buf, want)
    exp = buf.getvalue()
    for attempt in range(1, tries + 1):
        with open(path, "wb") as fh:
            fh.write(exp)
            fh.flush()
            os.fsync(fh.fileno())
        os.sync()
        raw = Path(path).read_bytes()
        if raw == exp:
            return hashlib.sha256(raw).hexdigest(), attempt
        log(f"torn write on {Path(path).name} (attempt {attempt}): "
            f"{sum(1 for a, b in zip(raw, exp) if a != b)} differing bytes")
        time.sleep(pause)
    raise RuntimeError(f"{Path(path).name} would not persist bit-exactly after {tries} attempts")


def heal_channels(bank=None, log_fn=None):
    """Recompute any channel whose on-disk bytes no longer match its pin (IR-H99-001).

    Reuses the SAME source bands and the SAME frozen parameters as the channels stage, so a healed
    channel is bit-identical to a freshly computed one.  Returns a receipt of what was rewritten.
    """
    say = log_fn or log
    man_path = FEAT / "manifest.json"
    man = json.loads(man_path.read_text())
    bands = {**VIEW_A_BANDS, **VIEW_B_BANDS}
    bad_bands, fixed = [], {}
    for b, nm in bands.items():
        names = [n for n in ALL_DVA if f"_{nm}_" in n]
        broken = [n for n in names
                  if not (FEAT / (n + ".npy")).exists()
                  or digest(FEAT / (n + ".npy")) != man["sha256"][n]]
        if broken:
            bad_bands.append((b, nm, broken))
    if not bad_bands:
        say("heal: all channel digests match their pins")
        return dict(healed={}, bad_bands=0)
    say(f"heal: {len(bad_bands)} band(s) need recomputation: "
        + ", ".join(f"{nm}({len(bl)})" for _b, nm, bl in bad_bands))
    eligible = np.load(ROOT / "work/r2/features/valid.npy")
    for b, nm, broken in bad_bands:
        with rasterio.open(FEATURES) as ds:
            zb = ds.read(b).astype(np.float64)
        ok = np.isfinite(zb) & eligible
        mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
        z = np.where(ok, (zb - mu) / sd, 0.0)
        w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
        del zb
        for h in LAGS:
            mx, mn, mean = _gamma_stats(z, ok, w, h, FAN)
            for st, arr in (("aniso", (mx - mn) / (mx + mn + 1e-9)),
                            ("logvar", np.log10(mean + 1e-9))):
                name = f"DVA_{nm}_{st}_l{h}"
                if name in broken:
                    sha, attempts = save_verified(FEAT / (name + ".npy"),
                                                  np.asarray(arr, np.float32)[eligible])
                    man["sha256"][name] = sha
                    fixed[name] = attempts
            del mx, mn, mean
        del z, ok, w
        say(f"heal: band {b} {nm} rewritten ({len(broken)} channels)")
    man["healed_utc"] = now()
    man["healed_channels"] = fixed
    man_path.write_text(json.dumps(man, indent=1) + "\n")
    say(f"heal: rewrote {len(fixed)} channel(s)")
    return dict(healed=fixed, bad_bands=len(bad_bands))


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit(f"{reg['round']} preregistration changed after freezing; re-pin the file")
    return reg


def dva_names(bands):
    return sorted(f"DVA_{nm}_{st}_l{h}" for nm in bands.values() for h in LAGS
                  for st in ("aniso", "logvar"))


DVA_A = dva_names(VIEW_A_BANDS)
DVA_B = dva_names(VIEW_B_BANDS)
ALL_DVA = DVA_A + DVA_B


# -------------------------------------------------------------------------- stage: channels
def _gamma_stats(z, ok, w, h, dirs):
    mx = mn = sm = None
    for dy_u, dx_u in dirs:
        dy, dx = dy_u * h, dx_u * h
        zs = np.roll(np.roll(z, -dy, 0), -dx, 1)
        oks = np.roll(np.roll(ok, -dy, 0), -dx, 1) & ok
        d2 = np.where(oks, 0.5 * (zs - z) ** 2, 0.0)
        g = ndi.gaussian_filter(d2, SIGMA) / w
        del d2, zs, oks
        if mx is None:
            mx, mn, sm = g, g.copy(), g.copy()
        else:
            np.maximum(mx, g, out=mx)
            np.minimum(mn, g, out=mn)
            sm += g
        del g
    return mx, mn, sm / float(len(dirs))


def stage_channels():
    reg = check_prereg()
    FEAT.mkdir(parents=True, exist_ok=True)
    _r, store, cat, eligible, folds, _va, _vb, _ring = base.setup()
    t0 = time.time()
    cols = {}
    band_receipt = []
    with rasterio.open(FEATURES) as ds:
        for b, nm in {**VIEW_A_BANDS, **VIEW_B_BANDS}.items():
            zb = ds.read(b).astype(np.float64)
            ok = np.isfinite(zb) & eligible
            mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
            z = np.where(ok, (zb - mu) / sd, 0.0)
            w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
            del zb
            for h in LAGS:
                mx, mn, mean = _gamma_stats(z, ok, w, h, FAN)
                cols[f"DVA_{nm}_aniso_l{h}"] = np.asarray((mx - mn) / (mx + mn + 1e-9),
                                                          np.float32)[eligible]
                cols[f"DVA_{nm}_logvar_l{h}"] = np.asarray(np.log10(mean + 1e-9),
                                                           np.float32)[eligible]
                del mx, mn, mean
            band_receipt.append(dict(band=b, tag=nm, eligible_px=int(ok.sum())))
            log(f"band {b} {nm}: DVA done ({time.time()-t0:.0f}s elapsed)")
            del z, ok, w
    sha, repaired = {}, {}
    for k, v in cols.items():
        sha[k], attempts = save_verified(FEAT / (k + ".npy"), v)
        if attempts > 1:
            repaired[k] = attempts
        del v
    man = dict(round=ROUND, created_utc=now(), stage="channels",
               sigma_px=SIGMA, lags_px=list(LAGS),
               fan_offsets_dy_dx=[list(t) for t in FAN],
               view_a_bands={str(k): v for k, v in VIEW_A_BANDS.items()},
               view_b_bands={str(k): v for k, v in VIEW_B_BANDS.items()},
               learner_channels=ALL_DVA, n_channels=len(ALL_DVA),
               band_receipt=band_receipt, sha256=sha, torn_writes_repaired=repaired,
               note="DVA never previously computed on bands 2, 9, 6 (run_h82.BANDS = 12,19,13,15,18)")
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    write("channels", {k: v for k, v in man.items() if k != "sha256"})
    log(f"channels stage done: {len(ALL_DVA)} channels in {time.time()-t0:.0f}s")
    return man


class Bank:
    """mmap-backed eligible-flat channel columns with a byte-integrity guard (H82 pattern).

    ``gather`` takes FLAT GRID indices and maps them through ``store.inverse`` exactly as
    ``gems52.structural.FeatureStore.gather`` does, so a caller can be swapped between the two
    without changing indexing semantics.
    """

    def __init__(self, directory=FEAT, inverse=None):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self._cols = {}
        if inverse is None:
            valid = np.load(ROOT / "work/r2/features/valid.npy")
            flat_idx = np.load(ROOT / "work/r2/features/flat_idx.npy")
            inverse = np.full(valid.size, -1, dtype=np.int32)
            inverse[flat_idx] = np.arange(flat_idx.size)
        self.inverse = inverse

    def col(self, name):
        if name not in self._cols:
            p = self.directory / (name + ".npy")
            if digest(p) != self.manifest["sha256"][name]:
                raise ValueError(f"channel byte-integrity failure: {name} (run heal_channels)")
            self._cols[name] = np.load(p, allow_pickle=False, mmap_mode="r")
        return self._cols[name]

    def refresh(self):
        """Drop cached columns so the next request re-reads and re-verifies from disk."""
        self._cols.clear()

    def gather(self, flat_rows, names):
        rows = self.inverse[np.asarray(flat_rows)]
        if (rows < 0).any():
            raise ValueError("requested row outside eligible feature footprint")
        out = np.empty((len(rows), len(names)), np.float32)
        for j, nm in enumerate(names):
            out[:, j] = self.col(nm)[rows]
        return np.nan_to_num(out, nan=0.0)


# -------------------------------------------------------------------------- stage: fit
def stage_fit():
    reg = check_prereg()
    _r, store, cat, eligible, folds, _va, _vb, ring_px = base.setup()
    heal_channels()
    bank = Bank(inverse=store.inverse)
    if list(bank.manifest["learner_channels"]) != ALL_DVA:
        raise SystemExit("channel manifest does not match the frozen channel list")
    if bank.manifest.get("round") != ROUND:
        raise SystemExit("channel directory belongs to a different round")
    flat, inv = store.flat_idx, store.inverse
    rng_global = np.random.default_rng(SEED)
    canary = {}
    out = dict(round=ROUND, stage="fit", started_utc=now(), evaluator_version=evaluator.VERSION,
               view_a_features=DVA_A, view_b_features=DVA_B, seed=SEED, folds=[])
    catd = ndi.distance_transform_edt(~cat)
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        rows, y = base.sample_train(fold, cat, rng)
        # ---- leakage canary: each channel alone against withheld truth inside the allowed set.
        # A 200k-pixel subsample of the allowed set keeps this cheap; the alarm bar is 0.90 so a
        # 4 % standard error is irrelevant to the decision.
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        truth_in = (fold["truth"] & fold["region"])[allowed]
        n_allow = int(allowed.sum())
        sub = np.flatnonzero(allowed.ravel())
        if sub.size > 200_000:
            sub = np.sort(np.random.default_rng(SEED + 900 + f).choice(sub, 200_000, replace=False))
        tsub = (fold["truth"] & fold["region"]).ravel()[sub]
        can_fold = {}
        if tsub.any() and (~tsub).any():
            inv_all = store.inverse
            srows = inv_all[sub]
            for nm in ALL_DVA:
                v = np.asarray(bank.col(nm)[srows], np.float64)
                if np.isfinite(v).all() and v.std() > 0:
                    can_fold[nm] = float(roc_auc_score(tsub.astype(int), v))
        canary[f"f{f}"] = can_fold
        rec = dict(fold=f, n_train=int(len(rows)), n_pos=int(y.sum()),
                   truth_px=int((fold["truth"] & fold["region"]).sum()),
                   allowed_px=n_allow, canary_max_auc=(max(can_fold.values()) if can_fold else None),
                   canary_argmax=(max(can_fold, key=can_fold.get) if can_fold else None),
                   views={})
        if can_fold:
            log(f"fold {f} canary max AUC {max(can_fold.values()):.4f} "
                f"({max(can_fold, key=can_fold.get)})")
        for view, names in (("Atex", DVA_A), ("Btex", DVA_B)):
            t0 = time.time()
            X = bank.gather(rows, names)
            m = base.learner(SEED)
            m.fit(X, y)
            in_auc = float(roc_auc_score(y, m.predict_proba(X)[:, 1]))
            del X
            p = np.empty(len(flat), np.float32)
            for i in range(0, len(flat), 250_000):
                sel = flat[i:i + 250_000]
                p[i:i + 250_000] = m.predict_proba(bank.gather(sel, names))[:, 1].astype(np.float32)
            psha, _a = save_verified(WORK / f"pred_{view}_f{f}.npy", p)
            rec.setdefault("pred_sha256", {})[view] = psha
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            neg_rows = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
            neg_idx = inv[neg_rows]
            oof = float(roc_auc_score(np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                                      np.r_[p[pos_idx], p[neg_idx]]))
            rec["views"][view] = dict(fit_seconds=round(time.time() - t0, 1), in_sample_auc=in_auc,
                                      heldout_region_auc=oof, n_region_pos=int(len(pos_idx)),
                                      n_region_neg=int(len(neg_idx)), n_features=len(names))
            log(f"fold {f} view {view}: in-AUC {in_auc:.4f} held-out-region AUC {oof:.4f} "
                f"({time.time()-t0:.0f}s)")
            del p
        out["folds"].append(rec)
    # ---- independence screen: spatial-block mean errors on labelled negatives (the brief's test)
    ind = dict(bar_brief=reg["thresholds"]["independence_bar_brief"],
               bar_repo=reg["thresholds"]["independence_bar_repo"], folds=[])
    fresh_pred_sha = {r["fold"]: r["pred_sha256"] for r in out["folds"]}
    for fold in folds:
        f = fold["fold"]
        pa = np.full(eligible.shape, np.nan, np.float32)
        pb = np.full(eligible.shape, np.nan, np.float32)
        pa.ravel()[flat] = load_pred("Atex", f, fresh_pred_sha[f]["Atex"])
        pb.ravel()[flat] = load_pred("Btex", f, fresh_pred_sha[f]["Btex"])
        neg = fold["region"] & ~cat & (catd > 5) & np.isfinite(pa) & np.isfinite(pb)
        block = 200
        h, w = neg.shape
        ncols = (w + block - 1) // block
        yv, xv = np.nonzero(neg)
        ids = (yv // block) * ncols + (xv // block)
        nblk = ncols * ((h + block - 1) // block)
        sa = np.bincount(ids, weights=pa[yv, xv], minlength=nblk)
        sb = np.bincount(ids, weights=pb[yv, xv], minlength=nblk)
        n = np.bincount(ids, minlength=nblk)
        keep = n > 0
        ma, mb = sa[keep] / n[keep], sb[keep] / n[keep]
        rho = float(np.corrcoef(ma, mb)[0, 1]) if keep.sum() > 2 else float("nan")
        ind["folds"].append(dict(fold=f, n_blocks=int(keep.sum()), pearson_rho=rho,
                                 mean_abs_error_A=float(np.abs(ma).mean()),
                                 mean_abs_error_B=float(np.abs(mb).mean())))
        log(f"fold {f} independence: rho {rho:.4f} over {int(keep.sum())} blocks")
    ind["max_abs_correlation"] = float(np.nanmax([abs(x["pearson_rho"]) for x in ind["folds"]]))
    ind["abandon_required"] = bool(ind["max_abs_correlation"] > ind["bar_brief"])
    ind["independence_ok_repo_bar"] = bool(ind["max_abs_correlation"] <= ind["bar_repo"])
    out["independence"] = ind
    can_flat = [v for d in canary.values() for v in d.values()]
    out["leakage_canary"] = dict(threshold_auc=CANARY_ALARM, per_fold=canary,
                                 max_auc=(max(can_flat) if can_flat else None),
                                 alarm=(bool(max(can_flat) > CANARY_ALARM) if can_flat else None),
                                 subsample_px=200_000)
    out["finished_utc"] = now()
    out["evaluator_hashes"] = evaluator.implementation_hashes()
    write("fit", out)
    log(f"independence max |rho| {ind['max_abs_correlation']:.4f} "
        f"abandon_required={ind['abandon_required']}")
    return out


# -------------------------------------------------------------------------- stage: holdout
def load_pred(view, f, expected):
    """Read a fold prediction and refuse it unless its bytes still hash to what the fit wrote."""
    p = WORK / f"pred_{view}_f{f}.npy"
    got = digest(p)
    if got != expected:
        raise SystemExit(f"{p.name} failed its integrity check after the fit "
                         f"({got[:12]} != {expected[:12]}); re-run the fit stage")
    return np.load(p, mmap_mode="r")


def pct_rank(values):
    v = np.asarray(values, np.float64)
    good = np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if good.any():
        out[good] = (rankdata(v[good], method="average") - 0.5) / float(good.sum())
    return out.astype(np.float32)


def stage_holdout():
    reg = check_prereg()
    _r, store, cat, eligible, folds, _va, _vb, ring_px = base.setup()
    flat = store.flat_idx
    fitrec_preds = {x["fold"]: x["pred_sha256"]
                    for x in json.loads((EVID / f"{EVID_PREFIX}fit.json").read_text())["folds"]}
    K = K_FOLD
    min_px = float(reg["thresholds"]["min_dot_separation_px"])
    terms = {a: None for a in ARMS}
    out = dict(round=ROUND, stage="holdout", started_utc=now(), evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, arms=list(ARMS), primary=PRIMARY,
               budget_per_fold=K, min_separation_px=min_px, folds=[])
    catd = ndi.distance_transform_edt(~cat)
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        pa = np.full(eligible.shape, np.nan, np.float32)
        pb = np.full(eligible.shape, np.nan, np.float32)
        pa.ravel()[flat] = load_pred("Atex", f, fitrec_preds[f]["Atex"])
        pb.ravel()[flat] = load_pred("Btex", f, fitrec_preds[f]["Btex"])
        ai = np.flatnonzero(allowed.ravel())
        ra = np.full(pa.size, np.nan, np.float32)
        rb = np.full(pb.size, np.nan, np.float32)
        ra[ai] = pct_rank(pa.ravel()[ai])
        rb[ai] = pct_rank(pb.ravel()[ai])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(pa.size, np.float32)
        rnd[ai] = rng.random(len(ai), dtype=np.float32)
        ra_g, rb_g = ra.reshape(eligible.shape), rb.reshape(eligible.shape)
        fields = {
            "xtex_dis": np.nan_to_num(ra_g - rb_g, nan=-1.0),
            "xtex_agree": np.nan_to_num(np.minimum(ra_g, rb_g), nan=-1.0),
            "single_Atex": np.nan_to_num(ra_g, nan=-1.0),
            "single_Btex": np.nan_to_num(rb_g, nan=-1.0),
            "random": rnd.reshape(eligible.shape),
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()),
                   truth_px=int((fold["truth"] & fold["region"]).sum()), arms={})
        em_by = {}
        for arm, field in fields.items():
            t0 = time.time()
            em = nodes.spacing_select(field, allowed, K, min_px=min_px)
            em_by[arm] = em
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"], fnw=res["fnw"],
                                    placed=int(em.sum()), seconds=round(time.time() - t0, 1))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        d_em = em_by[PRIMARY] > 0
        a_em, b_em, u_em = em_by["single_Atex"], em_by["single_Btex"], em_by["xtex_agree"]
        rec["not_the_union"] = dict(
            disagreement_dots=int(d_em.sum()),
            also_high_in_A=int((d_em & (a_em > 0)).sum()),
            also_high_in_B=int((d_em & (b_em > 0)).sum()),
            consensus_dots=int((u_em > 0).sum()),
            symmetric_difference_vs_consensus=int((d_em != (u_em > 0)).sum()))
        out["folds"].append(rec)
        del pa, pb, ra, rb, rnd, fields, em_by
    out["pooled"] = evaluator.pooled_summary(terms, draws=int(reg["thresholds"]["bootstrap_draws"]),
                                             seed=SEED, candidate=PRIMARY)
    out["withheld_positive_px"] = out["pooled"]["scores"][PRIMARY]["withheld_positive_pixels"]
    # per-view sufficiency, pooled over folds (the brief's sufficiency half)
    fitrec = json.loads((EVID / f"{EVID_PREFIX}fit.json").read_text())
    out["sufficiency"] = dict(
        view_A_AUC=[x["views"]["Atex"]["heldout_region_auc"] for x in fitrec["folds"]],
        view_B_AUC=[x["views"]["Btex"]["heldout_region_auc"] for x in fitrec["folds"]],
        note="positives = the fold's withheld catalogue truth inside its region; "
             "negatives = region and not-catalogue and >500 m from any catalogue pixel")
    out["independence"] = fitrec["independence"]
    out["finished_utc"] = now()
    out["caveat"] = ("HOLDOUT-DTI hides catalogue components; the competition scores faults the "
                     "catalogue lacks. This instrument screens procedures and is not a leaderboard "
                     "forecast (cross-round Spearman -0.10, IR-H77-005).")
    out["evaluator_hashes"] = evaluator.implementation_hashes()
    write("holdout", out)
    log("pooled: " + json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in ARMS}))
    log("paired vs random: " + json.dumps(
        {k: [round(v["delta"], 6), [round(x, 6) for x in v["ci95"]]]
         for k, v in out["pooled"]["paired_differences"].items()}))
    return out


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("channels", "all"):
        stage_channels()
    if stage in ("fit", "all"):
        stage_fit()
    if stage in ("holdout", "all"):
        stage_holdout()


if __name__ == "__main__":
    main()
