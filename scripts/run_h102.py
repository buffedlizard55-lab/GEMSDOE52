#!/usr/bin/env python3
"""H102 -- potential-field directional anisotropy (PAF-DVA) as View A, disagreement as the discovery signal.

Preregistered (frozen before any fit) in ``knowledge/108_hypotheses_H102_preregistered.md`` and pinned by
``registry/h102_preregistration.json`` (amendment h102a included); this runner refuses to start if either
hash has moved.

Lane: the standing brief's co-training paragraph (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).

Reuse, don't rebuild
--------------------
* evaluator          ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1) -- unmodified
* folds              ``gems52.spatial.folds`` (label-blind-quadrants-v2) via ``run_h61.setup`` -- unmodified
* independence       ``gems52.spatial.negative_block_errors`` + ``spatial.independence``, thresholds
                     inherited verbatim from ``registry/h74_preregistration.json``
* placement          ``gems52.nodes.spacing_select`` -- unmodified
* writer/validator   ``gems52.submission_writer`` -> ``gems52.gates.format_report`` -- unmodified
* DVA operator       ``run_h82._gamma_stats`` + the frozen fan/sigma/lags -- imported, never forked
* learner, sampling, view columns, percentile rank: ``run_h61`` -- imported

Stages (each checkpointed under work/h102 and evidence/h102_*.json):
    channels     40 PAF-DVA channels (View A) + 20 surface-DVA channels (View B) from the pinned raster
    fit          leakage canary per channel, then single_A2 and single_B2 per fold (region-only predict)
    holdout      matched-budget hide-and-recover pooled DTI for 7 arms + paired 95 % CIs
    independence the lane's mandated view-independence test on labelled negatives
    build        stitched A2/B2 fields, disagreement field, frozen 37 600-dot placement
    lane         lane gate (surface and dots) against every locally available registry raster
    write        GeoTIFF + on-disk validator + uniqueness + not-the-union + reasoning + run card

Usage: python scripts/run_h102.py [channels|fit|holdout|independence|build|lane|write|all]
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
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer           # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h102_preregistration.json"
WORK = ROOT / "work/h102"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
K_FOLD = int(os.environ.get("H102_K_FOLD", 9400))
K_TOTAL = int(os.environ.get("H102_K_TOTAL", 37600))          # amendment h102a: frozen = 4 x K_FOLD
RING_M = 200.0
SIGMA = h82.SIGMA
LAGS = h82.LAGS
FAN = h82.FAN
PREFIX = "gems52-h102-"

# View A: potential field and subsurface.  View B: surface only.  Disjoint by construction.
A_BANDS = {13: "iso_grav_anom", 18: "iso_grav_anom_hg", 2: "rtp", 15: "depth_to_base_surf"}
B_BANDS = {12: "det_elev", 19: "det_elev_slope"}
ARMS = ("single_A2", "single_B2", "cotrain_disagree", "consensus", "buried_only", "union_max")
PRIMARY = "cotrain_disagree"
STANDING_BAR = 0.190147          # knowledge/73 (B_DVA2 attribution arm is a finding, not promotable)


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h102_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


def check_prereg():
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if digest(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H102 preregistration document changed after freezing; re-pin registry/h102_preregistration.json")
    if reg.get("frozen_before_any_fit") is not True:
        raise SystemExit("H102 preregistration is not marked frozen before any fit")
    return reg


def dva_names(bands):
    return sorted(f"DVA2_{nm}_{st}_l{h}" for nm in bands.values() for h in LAGS for st in ("aniso", "logvar"))


A_NAMES, B_NAMES = dva_names(A_BANDS), dva_names(B_BANDS)


# --------------------------------------------------------------------------------------- stage: channels
def stage_channels():
    reg = check_prereg()
    FEAT.mkdir(parents=True, exist_ok=True)
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    both = {**A_BANDS, **B_BANDS}
    t0 = time.time()
    cols, per_band = {}, {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b, nm in both.items():
            t1 = time.time()
            zb = ds.read(b).astype(np.float64)
            ok = np.isfinite(zb) & eligible
            mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
            z = np.where(ok, (zb - mu) / sd, 0.0)
            w = ndi.gaussian_filter(ok.astype(np.float64), SIGMA) + 1e-9
            del zb
            for h in LAGS:
                mx, mn, mean = h82._gamma_stats(z, ok, w, h, FAN, None)
                cols[f"DVA2_{nm}_aniso_l{h}"] = h82._flat((mx - mn) / (mx + mn + 1e-9), eligible)
                cols[f"DVA2_{nm}_logvar_l{h}"] = h82._flat(np.log10(mean + 1e-9), eligible)
                del mx, mn, mean
            per_band[nm] = dict(band=b, seconds=round(time.time() - t1, 1), eligible_px=int(ok.sum()),
                                standardized_mean=mu, standardized_sd=sd,
                                view="A" if b in A_BANDS else "B")
            log(f"band {b} {nm}: {2 * len(LAGS)} channels in {time.time() - t1:.0f}s")
            del z, ok, w
    sha, repaired = {}, {}
    for k, v in cols.items():
        v = np.ascontiguousarray(np.asarray(v))
        sha[k], attempts = h82.save_verified(FEAT / (k + ".npy"), v)
        if attempts > 1:
            repaired[k] = attempts
        del v
    man = dict(round="H102", created_utc=now(), version="h102-pafdva-v1", sigma_px=SIGMA, lags_px=list(LAGS),
               fan_offsets_dy_dx=[list(t) for t in FAN], view_A_bands={str(k): v for k, v in A_BANDS.items()},
               view_B_bands={str(k): v for k, v in B_BANDS.items()},
               operator="run_h82._gamma_stats (imported, not forked)", channels_A=A_NAMES, channels_B=B_NAMES,
               n_channels=len(cols), per_band=per_band, sha256=sha, save_verified_by_reload=True,
               store_version=store.manifest["version"], inputs_sha256=dict(store.manifest["inputs"]),
               provenance="integrity-pinned, not organizer-authenticated (registry/data_manifest.json)")
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1, default=float))
    write("channels", dict(stage="channels", seconds=round(time.time() - t0, 1), n_columns=len(cols),
                           channels_A=A_NAMES, channels_B=B_NAMES, per_band=per_band,
                           n_channels_needing_rewrite=len(repaired), channels_needing_rewrite=repaired,
                           manifest_sha256=digest(FEAT / "manifest.json")))
    log(f"channels built in {time.time() - t0:.0f}s: {len(cols)} columns")


class Bank:
    """mmap-backed channel columns with the same byte-integrity discipline as h82.Bank (verified on load)."""

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

    def gather(self, rows, names):
        out = np.empty((len(rows), len(names)), np.float32)
        for j, nm in enumerate(names):
            out[:, j] = self.col(nm)[rows]
        return np.nan_to_num(out, nan=0.0)


def gather_arm(store, bank, rows_grid, names_store, names_ch):
    X = store.gather(rows_grid, names_store) if names_store else np.empty((len(rows_grid), 0), np.float32)
    if names_ch:
        X = np.hstack([X, bank.gather(store.inverse[rows_grid], names_ch)])
    return X


def predict_region(store, bank, model, names_store, names_ch, rows_grid, chunk=200_000):
    out = np.empty(len(rows_grid), np.float32)
    for i in range(0, len(rows_grid), chunk):
        s = rows_grid[i:i + chunk]
        out[i:i + chunk] = model.predict_proba(gather_arm(store, bank, s, names_store, names_ch))[:, 1]
    return out


# --------------------------------------------------------------------------------------- stage: fit
def stage_fit():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    for name in A_NAMES + B_NAMES:
        if name not in bank_manifest():
            raise SystemExit(f"channel {name} missing; run the channels stage first")
    bank = Bank(FEAT)
    WORK.mkdir(parents=True, exist_ok=True)
    out = dict(stage="fit", started_utc=now(), arms=["single_A2", "single_B2"], seed=SEED, folds=[],
               view_A_store_columns=len(va), view_B_store_columns=len(vb),
               channels_A=len(A_NAMES), channels_B=len(B_NAMES))
    for fold in folds:
        f = fold["fold"]
        t0 = time.time()
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        catd = ndi.distance_transform_edt(~cat)
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_region_rows=int(len(region_rows)), n_train_rows=int(len(rows)),
                   n_pos=int(len(pos_g)), n_neg=int(len(neg_g)), auc={}, canary={}, seconds={})
        crow = np.r_[pos_g, neg_g]
        erow = store.inverse[crow]
        for nm in sorted(A_NAMES + B_NAMES):
            v = np.asarray(bank.col(nm)[erow], np.float64)
            good = np.isfinite(v)
            a = float(roc_auc_score(yy[good], v[good])) if good.all() and np.ptp(v[good]) > 0 else 0.5
            rec["canary"][nm] = dict(auc=a, direction_insensitive=max(a, 1 - a),
                                     view="A" if nm in A_NAMES else "B")
        rec["canary_max"] = max(v["direction_insensitive"] for v in rec["canary"].values())
        rec["canary_worst"] = max(rec["canary"].items(), key=lambda kv: kv[1]["direction_insensitive"])[0]
        rec["canary_alarm_auc_bar"] = 0.90
        rec["canary_alarm"] = bool(rec["canary_max"] >= 0.90)
        log(f"fold {f}: canary max {rec['canary_max']:.4f} worst={rec['canary_worst']} alarm={rec['canary_alarm']}")
        for arm, (names_store, names_ch) in (("single_A2", (va, A_NAMES)), ("single_B2", (vb, B_NAMES))):
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if ck.exists():
                log(f"fold {f} {arm}: cached")
            else:
                m = base.learner_for("A" if arm == "single_A2" else "B", SEED)
                m.fit(gather_arm(store, bank, rows, names_store, names_ch), y)
                p = predict_region(store, bank, m, names_store, names_ch, region_rows)
                full = np.full(store.flat_idx.size, np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                h82.save_verified(ck, full)
                del m, p, full
            v = np.load(ck, mmap_mode="r")
            g = np.asarray(v, np.float32)
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[store.inverse[pos_g]], g[store.inverse[neg_g]]]))
            rec["seconds"][arm] = round(time.time() - t1, 1)
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g, v
        rec["seconds"]["total"] = round(time.time() - t0, 1)
        out["folds"].append(rec)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_overall"] = max(r["canary_max"] for r in out["folds"])
    out["sufficiency"] = {arm: dict(mean=float(np.mean([r["auc"][arm] for r in out["folds"]])),
                                    per_fold=[r["auc"][arm] for r in out["folds"]],
                                    gate_mean=0.60, gate_min_fold=0.55)
                          for arm in ("single_A2", "single_B2")}
    write("fit", out)
    log(json.dumps({"canary_alarm_any": out["canary_alarm_any"], "canary_max": out["canary_max_overall"],
                    "auc": {a: [round(r["auc"][a], 4) for r in out["folds"]] for a in ("single_A2", "single_B2")}}))


def bank_manifest():
    p = FEAT / "manifest.json"
    return json.loads(p.read_text())["sha256"] if p.exists() else {}


# --------------------------------------------------------------------------------------- stage: holdout
def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def rank_in(grid, mask):
    """Percentile rank of a fold's prediction grid restricted to `mask`; NaN outside."""
    out = np.full(grid.shape, np.nan, np.float32)
    ai = np.flatnonzero(mask.ravel())
    out.ravel()[ai] = np.nan_to_num(base.pct_rank(grid.ravel()[ai]), nan=0.0)
    return out


def arm_field(arm, ra, rb, shape):
    if arm == "single_A2":
        return ra
    if arm == "single_B2":
        return rb
    f = np.full(shape, -1.0, np.float32)
    good = np.isfinite(ra) & np.isfinite(rb)
    if arm == "cotrain_disagree":
        f[good] = (ra[good] - rb[good]).astype(np.float32)
    elif arm == "consensus":
        f[good] = np.minimum(ra[good], rb[good]).astype(np.float32)
    elif arm == "buried_only":
        sel = good & (rb <= 0.5)
        f[sel] = ra[sel].astype(np.float32)
    elif arm == "union_max":
        f[good] = np.maximum(ra[good], rb[good]).astype(np.float32)
    else:
        raise ValueError(arm)
    # percentile-rank the composed field inside its own support so budgets are comparable across arms
    out = np.full(shape, np.nan, np.float32)
    out[sel_ok(f)] = np.nan_to_num(base.pct_rank(f[sel_ok(f)]), nan=0.0)
    return out


def sel_ok(f):
    return np.isfinite(f) & (f >= 0)


def stage_holdout():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    arms = tuple(ARMS) + ("random",)
    terms = {a: None for a in arms}
    budget_terms = {}
    out = dict(stage="holdout", evaluator=evaluator.VERSION, budget_per_fold=K_FOLD, spacing_px=3.0,
               withheld_positive_px=int(sum(int(f["truth"].sum()) for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(), folds=[], started_utc=now())
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A2_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B2_f{f}.npy"), eligible.shape)
        ra, rb = rank_in(pa, allowed), rank_in(pb, allowed)
        rec = dict(fold=f, arms={})
        for arm in arms:
            if arm == "random":
                ai = np.flatnonzero(allowed.ravel())
                fld = np.full(eligible.shape, -1.0, np.float32)
                fld.ravel()[ai] = np.random.default_rng(SEED + 700 + f).random(len(ai), dtype=np.float32)
            else:
                fld = np.where(allowed, np.nan_to_num(arm_field(arm, ra, rb, eligible.shape), nan=-1.0), -1.0)
            em = nodes.spacing_select(fld.astype(np.float32), allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
            del fld, em
        # pre-registered diagnostic: primary-arm DTI vs per-fold budget (does NOT select the budget)
        fld = np.where(allowed, np.nan_to_num(arm_field(PRIMARY, ra, rb, eligible.shape), nan=-1.0), -1.0).astype(np.float32)
        rec["budget_curve"] = {}
        for k in (K_FOLD, 16000, 25400):
            em = nodes.spacing_select(fld, allowed, k, min_px=3.0)
            res, _ = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            rec["budget_curve"][str(k)] = float(res["dti"])
            del em
        log(f"fold {f} budget curve {json.dumps(rec['budget_curve'])}")
        del fld, pa, pb, ra, rb
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    pd = out["pooled"]["paired_differences"]
    out["candidate"] = PRIMARY
    out["paired_differences_keyed_by"] = "comparison arm; each entry is primary minus that arm"
    out["primary_paired"] = {f"{PRIMARY}_minus_{k}": v for k, v in pd.items()}
    best_control = out["pooled"]["best_comparable_control"]
    d = pd[best_control]["ci95"]
    out["promotion_rule"] = ("pooled candidate minus best comparable control: paired 95 %% CI lower bound > 0 "
                             "AND pooled DTI >= %.6f (standing bar, knowledge/73)" % STANDING_BAR)
    out["promotion_gate"] = dict(best_comparable_control=best_control,
                                 candidate_dti=float(out["pooled"]["scores"][PRIMARY]["dti"]),
                                 control_dti=float(out["pooled"]["scores"][best_control]["dti"]),
                                 delta=float(pd[best_control]["delta"]), ci95=[float(x) for x in d],
                                 ci_lower_above_zero=bool(d[0] > 0),
                                 above_standing_bar=bool(out["pooled"]["scores"][PRIMARY]["dti"] >= STANDING_BAR))
    out["promotion_gate"]["PROMOTE"] = bool(out["promotion_gate"]["ci_lower_above_zero"]
                                            and out["promotion_gate"]["above_standing_bar"])
    write("holdout", out)
    log(json.dumps({a: round(out["pooled"]["scores"][a]["dti"], 6) for a in arms}))
    log("PROMOTE=" + str(out["promotion_gate"]["PROMOTE"]) + " gate=" + json.dumps(out["promotion_gate"]))


# ---------------------------------------------------------------------------------- stage: independence
def stage_independence():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th_src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    rows_blocks, per_fold = [], []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A2_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B2_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        qa, qb = pa[neg], pb[neg]
        thr = (float(np.quantile(qa, th["donor_rank_min"])), float(np.quantile(qb, th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        rows_blocks += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr), n_blocks=len(blocks)))
        log(f"fold {f}: independence blocks {len(blocks)} over {int(neg.sum())} labelled negatives")
        del pa, pb, qa, qb
    res = spatial.independence(rows_blocks, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    out = dict(stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
               thresholds_inherited_from=str(th_src.relative_to(ROOT)),
               thresholds_inherited_sha256=digest(th_src),
               thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"],
                               min_blocks=20, negative_ring_px=4),
               thresholds_not_retuned_for_h102=True,
               view_A="single_A2 (store view_A_with_external + 40 PAF-DVA channels)",
               view_B="single_B2 (store view_B_with_external + 20 surface-DVA channels)",
               per_fold=per_fold, result=res,
               interpretation=("abandon bar |rho| > %.2f: a strongly correlated pair would mean the two views share "
                               "their errors, so co-training could only amplify a common bias"
                               % th["independence_abandon_max_abs_rho"]))
    write("independence", out)
    log(json.dumps({k: res[k] for k in res if not isinstance(res[k], (list, dict))}, default=float))
    return out


# --------------------------------------------------------------------------------------- stage: build
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


def stage_build():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fA, fB = stitch("single_A2", folds, eligible, flat), stitch("single_B2", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fA) & np.isfinite(fB) & (catd * 100.0 > RING_M)
    ra, rb = np.full(eligible.shape, np.nan, np.float32), np.full(eligible.shape, np.nan, np.float32)
    ai = np.flatnonzero(pool.ravel())
    ra.ravel()[ai] = base.pct_rank(fA.ravel()[ai])
    rb.ravel()[ai] = base.pct_rank(fB.ravel()[ai])
    dis = np.full(eligible.shape, np.nan, np.float32)
    dis.ravel()[ai] = base.pct_rank((ra.ravel()[ai] - rb.ravel()[ai]).astype(np.float64))
    field = np.where(pool, np.nan_to_num(dis, nan=-1.0), -1.0).astype(np.float32)
    dots = nodes.spacing_select(field, pool, K_TOTAL, min_px=3.0)
    a_field = np.where(pool, np.nan_to_num(ra, nan=-1.0), -1.0).astype(np.float32)
    b_field = np.where(pool, np.nan_to_num(rb, nan=-1.0), -1.0).astype(np.float32)
    a_dots = nodes.spacing_select(a_field, pool, K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(b_field, pool, K_TOTAL, min_px=3.0)
    umax = np.full(eligible.shape, np.nan, np.float32)
    umax.ravel()[ai] = base.pct_rank(np.maximum(ra.ravel()[ai], rb.ravel()[ai]).astype(np.float64))
    union_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(umax, nan=-1.0), -1.0).astype(np.float32),
                                      pool, K_TOTAL, min_px=3.0)
    h82.save_verified(WORK / "dots.npy", dots)
    h82.save_verified(WORK / "surface.npy", np.where(np.isfinite(dis), np.nan_to_num(dis, nan=0.0), 0.0).astype(np.float32))
    h82.save_verified(WORK / "field_A.npy", fA)
    h82.save_verified(WORK / "field_B.npy", fB)
    h82.save_verified(WORK / "union_dots.npy", union_dots)
    rec = dict(stage="build", dots=int(dots.sum()), target_dots=K_TOTAL, pool_px=int(pool.sum()),
               eligible_px=int(eligible.sum()), ring_excluded_m=RING_M,
               min_cat_dist_m=float((catd[dots] * 100).min()), median_cat_dist_m=float(np.median(catd[dots] * 100)),
               dots_within_300m_of_catalogue_pct=float((catd[dots] * 100 <= 300).mean() * 100),
               union_dots=int(union_dots.sum()), a_dots=int(a_dots.sum()), b_dots=int(b_dots.sum()),
               budget_rule="amendment h102a: frozen 37600 = 4 x 9400/fold", started_utc=now())
    write("build_placement", rec)
    log(f"dots {int(dots.sum())}, pool {int(pool.sum())}, min catalogue distance {rec['min_cat_dist_m']:.1f} m")
    del fA, fB, ra, rb, dis, field, dots, a_field, b_field, a_dots, b_dots, umax, union_dots, catd, pool


# --------------------------------------------------------------------------------------- stage: lane
def local_registry():
    """Every locally available prior raster, de-duplicated by raw bytes.

    The full cross-repository census (526 blobs) lives in a git-ignored receipt and is re-fetched only by
    scripts/fetch_prior_inventory.py, which reads sibling repositories over the GitHub API.  That fetch was
    not run inside this round's time box, so the lane gate is run against the restricted scored registry
    (data/scored + data/reference), this repository's own submission/ artefacts and every GeoTIFF published
    under docs/downloads/.  The limitation is recorded in the run card, not hidden.
    """
    seen, paths = set(), []
    cands = sorted((ROOT / "data/scored").glob("*.tif")) + sorted((ROOT / "data/reference").glob("*.tif")) \
        + sorted((ROOT / "submission").glob("*.tif")) + sorted((ROOT / "docs/downloads").glob("*.tif"))
    for p in cands:
        if PREFIX in p.name:
            continue
        try:
            h = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if h in seen:
            continue
        seen.add(h)
        paths.append(p)
    return paths


def stage_lane():
    check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy").astype(np.float32)
    surf = np.load(WORK / "surface.npy")
    reg = local_registry()
    out = dict(stage="lane", started_utc=now(), n_local_registry=len(reg),
               registry_paths=[str(p.relative_to(ROOT)) for p in reg],
               registry_scope=("locally available de-duplicated rasters: restricted scored registry "
                               "(data/scored, data/reference), this repository's submission/ artefacts and "
                               "docs/downloads/*.tif. The 526-blob cross-repository census was NOT re-fetched "
                               "inside this round's time box (IR-H102-003)."),
               doctrine="a restricted-registry PASS never waives the full-census result; here both are the same set")
    out["surface"] = gates.lane_report(surf, eligible, reg, sample=SAMPLE, phase="surface", log=log)
    out["dots"] = gates.lane_report(dots, eligible, reg, sample=SAMPLE, phase="dots", log=log)
    out["uniqueness"] = gates.uniqueness_report(dots, reg)
    write("lane", out)
    for k in ("surface", "dots"):
        r = out[k]
        log(f"lane {k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, "
            f"max near {r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']} "
            f"(informative {r['policy']['informative_priors']}, probes {r['policy']['universal_coverage_probes']}, "
            f"max near {r['policy']['max_near_3px_fraction']})")


# --------------------------------------------------------------------------------------- stage: write
def stage_write():
    reg = check_prereg()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    dots = np.load(WORK / "dots.npy")
    union_dots = np.load(WORK / "union_dots.npy")
    pred = dots.astype(np.float32)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h102-pafdva-disagree-{int(dots.sum())}px-{stamp}"
    note = ("H102 co-training: View-A potential-field directional anisotropy (gravity/RTP/cover) x View-B DEM "
            "anisotropy; disagreement field, 200m catalogue ring excluded, binary")
    if len(note) > 140:
        note = ("H102 co-training: View-A potential-field anisotropy x View-B DEM anisotropy; disagreement field, "
                f"200m ring excluded, binary {int(dots.sum())} dots")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    rec = submission_writer.write_submission(out, pred, SAMPLE, eligible, note=note, name=name,
                                             metadata=dict(round="H102", primary_arm=PRIMARY,
                                                           preregistration_sha256=digest(PREREG)))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()), mass=float(np.nansum(v)))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"]
                       and val["shape_match"] and val["transform_match"] and val["range_ok"])
    val["range_rule_source"] = ("official: single layer float32 with values between 0 and 1, EPSG:32611, 100 m, "
                                "same bounds as the training data "
                                "(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)")
    hold = json.loads((EVID / "h102_holdout.json").read_text())
    lane = json.loads((EVID / "h102_lane.json").read_text())
    fA, fB = np.load(WORK / "field_A.npy"), np.load(WORK / "field_B.npy")
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fA) & np.isfinite(fB) & (catd * 100.0 > RING_M)
    a_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fA, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)
    b_dots = nodes.spacing_select(np.where(pool, np.nan_to_num(fB, nan=-1.0), -1.0).astype(np.float32),
                                  pool, K_TOTAL, min_px=3.0)

    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    not_union = dict(dots_emitted=int(dots.sum()), union_max_dots=int(union_dots.sum()),
                     dots_equal_union=bool(np.array_equal(dots, union_dots)),
                     dots_equal_single_A=bool(np.array_equal(dots, a_dots)),
                     dots_equal_single_B=bool(np.array_equal(dots, b_dots)),
                     dots_subset_of_union=bool((dots & ~union_dots).sum() == 0),
                     shared_with_union=int((dots & union_dots).sum()), jaccard_with_union=jac(dots, union_dots),
                     shared_with_single_A=int((dots & a_dots).sum()), jaccard_with_single_A=jac(dots, a_dots),
                     shared_with_single_B=int((dots & b_dots).sum()), jaccard_with_single_B=jac(dots, b_dots))
    y = np.flatnonzero(dots.ravel()) // dots.shape[1]
    x = np.flatnonzero(dots.ravel()) % dots.shape[1]
    import csv
    with (out.with_suffix("").with_name(out.stem + "-a-only-reasoning.csv")).open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "utm_e_m", "utm_n_m", "dist_to_mapped_catalogue_m",
                    "view_A_pafdva_rank", "view_B_surface_rank", "disagreement_score",
                    "fired_components", "alternative_non_fault_processes", "falsifier"])
        fA_r, fB_r, dis = fA, np.load(WORK / "field_B.npy"), np.load(WORK / "surface.npy")
        for i in range(len(y)):
            w.writerow([int(y[i]), int(x[i]), 243350.0 + 100.0 * (x[i] + 0.5), 4508550.0 - 100.0 * (y[i] + 0.5),
                        round(float(catd[y[i], x[i]] * 100), 1),
                        round(float(fA_r[y[i], x[i]]), 4), round(float(fB_r[y[i], x[i]]), 4),
                        round(float(dis[y[i], x[i]]), 4),
                        "View A (potential-field / subsurface directional anisotropy) confident while View B "
                        "(detrended-elevation anisotropy) abstains: buried-fault hypothesis",
                        "lithologic or intrusive contact; basin-margin facies step; airborne/gravity survey "
                        "flight-line or terrain-correction striping; paleochannel scour at the basement surface",
                        "a Phase-2 reviewer finds the candidate coincides with a mapped lithologic contact or a "
                        "survey flight line and has no independent surface or seismicity expression"])
    run_card = dict(round="H102", generated_utc=now(),
                    hypothesis=("directional semivariance anisotropy on the potential-field/subsurface bands is a "
                                "subsurface texture that is not a copy of the surface texture; where View A is "
                                "confident and View B abstains the fault may be buried beneath cover and absent "
                                "from the surface-expression catalogue"),
                    mechanism=("fault damage zones lower density and destroy magnetite along strike, imprinting a "
                               "preferred direction on the gravity and RTP-magnetic semivariance while alluvial "
                               "cover removes the DEM expression"),
                    named_non_fault_mimic=("lithologic/intrusive contacts; basin-margin facies steps; survey "
                                           "flight-line and terrain-correction striping; paleochannel scour; "
                                           "isostatic/terrain-correction artefacts at block margins"),
                    preregistration_sha256=digest(PREREG),
                    holdout_dti={a: hold["pooled"]["scores"][a] for a in hold["pooled"]["scores"]},
                    holdout_promotion_gate=hold["promotion_gate"],
                    lane_surface=lane["surface"]["policy"], lane_dots=lane["dots"]["policy"],
                    lane_registry_scope=lane["registry_scope"], len_registry=lane["n_local_registry"],
                    uniqueness=lane["uniqueness"]["summary"] if "summary" in lane["uniqueness"] else
                    {k: v for k, v in lane["uniqueness"].items() if k != "per_prior"},
                    raster_sha256=val and rec["sha256"], raster_bytes=rec["bytes"],
                    validator=val, not_the_union=not_union, submission_name=name, note=note, note_chars=len(note),
                    slotted=False, submission_slots_used=0)
    run_card["verdict"] = "promote" if hold["promotion_gate"]["PROMOTE"] else "negative"
    run_card["submit_ok"] = bool(hold["promotion_gate"]["PROMOTE"] and val["PASS"])
    write("run_card", run_card)
    write("not_union", not_union)
    log(json.dumps({k: v for k, v in not_union.items()}, default=float))
    log("verdict " + run_card["verdict"] + " submit_ok=" + str(run_card["submit_ok"]))


STAGES = dict(channels=stage_channels, fit=stage_fit, holdout=stage_holdout,
              independence=stage_independence, build=stage_build, lane=stage_lane, write=stage_write)


def main(argv):
    todo = argv[1:] or ["all"]
    order = ["channels", "fit", "holdout", "independence", "build", "lane", "write"]
    for s in (order if todo == ["all"] else todo):
        if s not in STAGES:
            raise SystemExit(f"unknown stage {s}; choose from {', '.join(order)}")
        t0 = time.time()
        log(f"=== stage {s} ===")
        STAGES[s]()
        log(f"=== stage {s} done in {time.time() - t0:.0f}s ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
