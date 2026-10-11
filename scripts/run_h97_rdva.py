#!/usr/bin/env python3
"""H97: strict A/B directional-anisotropy co-training with radiometric DVA.

Frozen before H97 channel construction/model fitting in
``knowledge/97_hypotheses_H97_preregistered.md`` and
``registry/h97_rdva_preregistration.json``.  This runner imports H82's DVA operator and H61's learner/
sampling/ranking hooks; folds, exchange, evaluator, placement, gates and writer are shared modules.

Stages: channels | canary | fit | exchange | holdout | build | write | all
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
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
from scipy.stats import spearmanr                                    # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

ROUND_DATE = "2026-10-10"            # session-supplied UTC date; host clock crossed midnight
REG_PATH = ROOT / "registry/h97_rdva_preregistration.json"
REG_SHA = "0631745794bfb6a582bfe2bc2f7d3f32ed9e066b1855469606d2ff89a8993db8"
DOC_SHA = "f35c14e130af1ae00e6ed47a5a08a185125e81db8289ce30228ba7acfafc57e9"
DATA = ROOT / "data"
SAMPLE = DATA / "sample_submission.tif"
FEATURES = DATA / "training_features.tif"
LABELS = DATA / "labels.tif"
RAD = DATA / "external/geodawn_rad_u8.tif"
# Large raw arrays live under the snapshot-excluded runtime cache.  Persisting ~1.7 GB of .npy
# pages in work/ exceeded Arena's best-effort patch snapshot and reproduced IR-H82-002 despite
# atomic writes (IR-H97-RDVA-001).  Evidence and final artifacts remain in tracked/published paths.
WORK = ROOT / ".cache/h97"
BANK_DIR = WORK / "directional_features"
PRIOR_DIR = ROOT / "work/h97/priors"
EVID = ROOT / "evidence"
SUBDIR = ROOT / "submission"
DLDIR = ROOT / "docs/downloads"

SEED = 97001
PRIMARY = "cotrain_B_RDVA"
BAR = 0.19282907051926573
K_FOLD = 9400
K_SHIP = 25400
RING_PX = 2.0
BUFFER_PX = 80
CANARY_ALARM = 0.90
INDEP_ABANDON = 0.60
DONOR = 0.95
RECEIVER = (0.35, 0.65)
PSEUDO_WEIGHT = 0.25
PSEUDO_CAP = 2000
PSEUDO_MIN = 5
BLOCK_SIDE = 50
MIN_PX = 3.0
# The workspace storage layer has repeatedly zeroed exactly the first 3,968 payload bytes of large
# .npy files after a successful fsync/reload (IR-H82-002, IR-H97-RDVA-001).  A 1,024-value sacrificial
# zero prefix spans that page.  Every runtime vector is content-pinned and readers remove the prefix.
RUNTIME_PAD_VALUES = 1024

COMP_SOURCES = {12: "det_elev", 19: "det_elev_slope", 13: "iso_grav_anom",
                15: "depth_to_base_surf", 18: "iso_grav_anom_hg"}
RAD_SOURCES = {1: "K", 2: "Th", 3: "U", 4: "TC"}
LAGS = tuple(h82.LAGS)
FAN = tuple(h82.FAN)
A_SOURCE_NAMES = ("iso_grav_anom", "depth_to_base_surf", "iso_grav_anom_hg")
B_SOURCE_NAMES = ("det_elev", "det_elev_slope")


def log(*args):
    print(f"[{time.strftime('%H:%M:%S')}]", *args, flush=True)


def now():
    return ROUND_DATE + "T" + datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def portable(obj):
    """Keep published receipts independent of the checkout's absolute sandbox path."""
    if isinstance(obj, dict):
        return {k: portable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [portable(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(str(ROOT) + "/", "")
    return obj


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(portable(obj), indent=2, allow_nan=False, default=float) + "\n")
    return path


def _sidecar(path: Path) -> Path:
    return Path(str(path) + ".sha256")


def save_runtime_vector(path: Path, values):
    """Persist a large vector behind a sacrificial zero page and pin its exact container bytes."""
    path = Path(path)
    v = np.ascontiguousarray(np.asarray(values).ravel())
    padded = np.empty(len(v) + RUNTIME_PAD_VALUES, dtype=v.dtype)
    padded[:RUNTIME_PAD_VALUES] = 0
    padded[RUNTIME_PAD_VALUES:] = v
    digest, attempts = h82.save_verified(path, padded)
    _sidecar(path).write_text(digest + "\n")
    return digest, attempts


def load_runtime_vector(path: Path, *, expected_length=None):
    """Fail closed on bytes, then return the logical vector after its storage guard page."""
    path = Path(path)
    side = _sidecar(path)
    if not path.is_file() or not side.is_file():
        raise FileNotFoundError(path)
    expected = side.read_text().strip()
    got = sha(path)
    if got != expected:
        raise ValueError(f"runtime vector digest mismatch: {path.name} {got} != {expected}")
    raw = np.load(path, mmap_mode="r", allow_pickle=False)
    if len(raw) < RUNTIME_PAD_VALUES or np.any(raw[:RUNTIME_PAD_VALUES] != 0):
        raise ValueError(f"runtime guard page changed: {path.name}")
    logical = raw[RUNTIME_PAD_VALUES:]
    if expected_length is not None and len(logical) != expected_length:
        raise ValueError(f"runtime vector length mismatch: {path.name}")
    return logical


def check_prereg():
    got = sha(REG_PATH)
    if got != REG_SHA:
        raise SystemExit(f"H97 preregistration bytes moved ({got}); refusing to run")
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != DOC_SHA or sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H97 hypothesis document moved after freezing; refusing to run")
    return reg


def names_for(prefix: str, sources):
    return sorted(f"{prefix}_{src}_{stat}_l{lag}" for src in sources for lag in LAGS
                  for stat in ("aniso", "logvar"))


A_DVA = names_for("DVA2", A_SOURCE_NAMES)
B_DVA = names_for("DVA2", B_SOURCE_NAMES)
B_RDVA = names_for("RDVA2", tuple(RAD_SOURCES.values()))


class DirectionalBank:
    """Integrity-checked eligible-flat columns built with H82's DVA operator."""

    def __init__(self, directory=BANK_DIR):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self._cols = {}

    def col(self, name):
        if name not in self._cols:
            path = self.directory / f"{name}.npy"
            if sha(path) != self.manifest["sha256"][name]:
                raise ValueError(f"directional channel digest mismatch: {name}")
            raw = np.load(path, mmap_mode="r", allow_pickle=False)
            pad = int(self.manifest.get("runtime_padding_values", 0))
            if pad and np.any(raw[:pad] != 0):
                raise ValueError(f"directional channel guard page changed: {name}")
            self._cols[name] = raw[pad:]
            if len(self._cols[name]) != int(self.manifest["eligible_px"]):
                raise ValueError(f"directional channel logical length mismatch: {name}")
        return self._cols[name]

    def gather(self, eligible_rows, names):
        X = np.empty((len(eligible_rows), len(names)), np.float32)
        for j, name in enumerate(names):
            X[:, j] = self.col(name)[eligible_rows]
        return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def view_spec(va, vb):
    A = (list(va), list(A_DVA))
    B = (list(vb), list(B_DVA + B_RDVA))
    labels_A = [f"store::{x}" for x in A[0]] + [f"bank::{x}" for x in A[1]]
    labels_B = [f"store::{x}" for x in B[0]] + [f"bank::{x}" for x in B[1]]
    overlap = sorted(set(labels_A) & set(labels_B))
    if overlap:
        raise AssertionError(f"views overlap: {overlap}")
    return {"A": A, "B": B}, labels_A, labels_B


def gather(store, bank, rows_grid, view, specs):
    store_names, bank_names = specs[view]
    Xs = store.gather(rows_grid, store_names) if store_names else np.empty((len(rows_grid), 0), np.float32)
    Xb = bank.gather(store.inverse[rows_grid], bank_names) if bank_names else np.empty((len(rows_grid), 0), np.float32)
    return np.hstack([Xs, Xb])


def predict_all(store, bank, model, view, specs, chunk=120_000):
    flat = store.flat_idx
    out = np.empty(len(flat), np.float32)
    for i in range(0, len(flat), chunk):
        rows = flat[i:i + chunk]
        out[i:i + chunk] = model.predict_proba(gather(store, bank, rows, view, specs))[:, 1]
    return out


def allowed_of(fold, ring_px=RING_PX):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def rank_on(values, mask):
    out = np.full(mask.shape, np.nan, np.float32)
    idx = np.flatnonzero(mask.ravel())
    out.ravel()[idx] = base.pct_rank(values.ravel()[idx])
    return out


def to_grid(store, values):
    return base.to_grid(store.flat_idx, values, store.valid.shape)


# ----------------------------------------------------------------------------------- channels

def _source_channels(source_grid, ok, eligible, prefix, source_name):
    """H82's exact semivariance fan; return ten eligible-flat channels for one source."""
    z0 = np.asarray(source_grid, np.float64)
    mu, sd = float(z0[ok].mean()), float(z0[ok].std()) + 1e-12
    z = np.where(ok, (z0 - mu) / sd, 0.0)
    w = ndi.gaussian_filter(ok.astype(np.float64), h82.SIGMA) + 1e-9
    out = {}
    for lag in LAGS:
        mx, mn, mean = h82._gamma_stats(z, ok, w, lag, FAN, None)
        out[f"{prefix}_{source_name}_aniso_l{lag}"] = np.asarray(
            ((mx - mn) / (mx + mn + 1e-9))[eligible], np.float32)
        out[f"{prefix}_{source_name}_logvar_l{lag}"] = np.asarray(
            np.log10(mean + 1e-9)[eligible], np.float32)
        del mx, mn, mean
    return out, dict(mean=mu, sd=sd, finite_eligible_px=int(ok.sum()))


def stage_channels():
    reg = check_prereg()
    _r, store, _cat, eligible, _folds, va, vb, _ring = base.setup()
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cols, moments = {}, {}
    with rasterio.open(FEATURES) as ds:
        for band, name in COMP_SOURCES.items():
            a = ds.read(band).astype(np.float64)
            ok = eligible & np.isfinite(a) & (a > -1e38)
            got, moments[f"competition_band_{band}_{name}"] = _source_channels(
                a, ok, eligible, "DVA2", name)
            cols.update(got)
            log(f"DVA2 band {band} {name}: {len(got)} channels")
            del a, got
    with rasterio.open(RAD) as ds:
        for band, name in RAD_SOURCES.items():
            a = ds.read(band).astype(np.float64)
            ok = eligible & np.isfinite(a) & (a > 0)
            got, moments[f"GeoDAWN_band_{band}_{name}"] = _source_channels(
                a, ok, eligible, "RDVA2", name)
            cols.update(got)
            log(f"RDVA2 GeoDAWN band {band} {name}: {len(got)} channels")
            del a, got
    expected = sorted(A_DVA + B_DVA + B_RDVA)
    if sorted(cols) != expected:
        raise AssertionError(f"channel inventory mismatch: got {len(cols)}, expected {len(expected)}")
    digests, rewrites = {}, {}
    for name in expected:
        values = cols[name]
        padded = np.empty(len(values) + RUNTIME_PAD_VALUES, np.float32)
        padded[:RUNTIME_PAD_VALUES] = 0.0
        padded[RUNTIME_PAD_VALUES:] = values
        digests[name], attempts = h82.save_verified(BANK_DIR / f"{name}.npy", padded)
        if attempts > 1:
            rewrites[name] = attempts
        del cols[name], values, padded
    manifest = dict(round="H97", version="h97-view-pure-rdva-v1", created_utc=now(),
                    implementation="scripts/run_h82.py::_gamma_stats imported, not copied",
                    implementation_sha256=sha(ROOT / "scripts/run_h82.py"),
                    sigma_px=h82.SIGMA, lags_px=list(LAGS),
                    fan_offsets_dy_dx=[list(x) for x in FAN],
                    sources=dict(A_competition_bands={str(k): v for k, v in COMP_SOURCES.items()
                                                     if v in A_SOURCE_NAMES},
                                 B_competition_bands={str(k): v for k, v in COMP_SOURCES.items()
                                                     if v in B_SOURCE_NAMES},
                                 B_GeoDAWN_bands={str(k): v for k, v in RAD_SOURCES.items()}),
                    view_A=A_DVA, view_B=B_DVA + B_RDVA, overlap=[], moments=moments,
                    eligible_px=int(eligible.sum()), n_channels=len(expected), sha256=digests,
                    runtime_padding_values=RUNTIME_PAD_VALUES,
                    runtime_padding_reason="IR-H97-RDVA-001 sacrificial zero page; excluded from learner input",
                    save_rewrites=rewrites, store_version=store.manifest["version"],
                    store_view_A=va, store_view_B=vb,
                    input_sha256=dict(training_features=sha(FEATURES), radiometrics=sha(RAD)),
                    registration_sha256=REG_SHA)
    dump(BANK_DIR / "manifest.json", manifest)
    receipt = dict(stage="channels", generated_utc=now(), seconds=time.time() - t0,
                   n_channels=len(expected), n_A=len(A_DVA), n_B=len(B_DVA + B_RDVA),
                   manifest_sha256=sha(BANK_DIR / "manifest.json"),
                   all_columns_digest_verified=True, n_save_rewrites=len(rewrites),
                   registration_sha256=REG_SHA, hypothesis_sha256=DOC_SHA)
    dump(EVID / "h97_rdva_channels.json", receipt)
    log(f"channels done: {len(expected)} columns in {time.time()-t0:.0f}s")
    return receipt


# ------------------------------------------------------------------------------------- canary

def stage_canary():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, _ring = base.setup()
    bank = DirectionalBank()
    specs, labels_A, labels_B = view_spec(va, vb)
    catd = ndi.distance_transform_edt(~cat)
    rng = np.random.default_rng(SEED)
    out = dict(stage="canary", evidence_class="LEAKAGE-CANARY AUC (diagnostic; not DTI)",
               alarm_rule="direction-insensitive raw AUC > 0.90 is leakage until proven otherwise",
               alarm_threshold=CANARY_ALARM, feature_inventory=dict(A=labels_A, B=labels_B), folds=[])
    all_worst = []
    for fold in folds:
        f = int(fold["fold"])
        pos = np.flatnonzero((fold["truth"] & fold["region"] & eligible).ravel())
        neg = np.flatnonzero((fold["region"] & eligible & ~cat & (catd > 5)).ravel())
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        rows = np.r_[pos, neg]
        y = np.r_[np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)]
        recs = {}
        for view, (store_names, bank_names) in specs.items():
            for name in store_names:
                x = store.gather(rows, [name])[:, 0]
                auc = float(roc_auc_score(y, x)) if np.ptp(x) > 0 else 0.5
                recs[f"store::{name}"] = dict(view=view, auc=auc,
                    direction_insensitive=max(auc, 1 - auc), source="shared structural store")
            erows = store.inverse[rows]
            for name in bank_names:
                x = np.asarray(bank.col(name)[erows], np.float32)
                auc = float(roc_auc_score(y, x)) if np.ptp(x) > 0 else 0.5
                recs[f"bank::{name}"] = dict(view=view, auc=auc,
                    direction_insensitive=max(auc, 1 - auc), source="H97 directional bank")
        ranked = sorted(recs.items(), key=lambda kv: -kv[1]["direction_insensitive"])
        tr_rows, tr_y, _ = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + 900 + f))
        fitted = {}
        for label, meta in ranked[:5]:
            kind, name = label.split("::", 1)
            Xtr = store.gather(tr_rows, [name]) if kind == "store" else bank.gather(store.inverse[tr_rows], [name])
            Xte = store.gather(rows, [name]) if kind == "store" else bank.gather(store.inverse[rows], [name])
            model = base.learner_for(meta["view"], SEED + 91 + f)
            model.fit(Xtr, tr_y)
            fitted[label] = float(roc_auc_score(y, model.predict_proba(Xte)[:, 1]))
        alarms = [name for name, rec in recs.items() if rec["direction_insensitive"] > CANARY_ALARM]
        out["folds"].append(dict(fold=f, n_pos=len(pos), n_neg=len(neg), per_feature=recs,
                                 top5=[[n, r["direction_insensitive"]] for n, r in ranked[:5]],
                                 max_direction_insensitive_auc=ranked[0][1]["direction_insensitive"],
                                 fitted_top5_heldout_auc=fitted, alarms=alarms))
        all_worst.append(ranked[0][1]["direction_insensitive"])
        log(f"fold {f} canary max {all_worst[-1]:.4f} ({ranked[0][0]}); alarms={len(alarms)}")
    out.update(max_auc=float(max(all_worst)), any_alarm=bool(any(x["alarms"] for x in out["folds"])),
               finished_utc=now())
    dump(EVID / "h97_rdva_canary.json", out)
    return out


# ----------------------------------------------------------------------------------------- fit

def stage_fit():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, _ring = base.setup()
    bank = DirectionalBank()
    specs, labels_A, labels_B = view_spec(va, vb)
    WORK.mkdir(parents=True, exist_ok=True)
    out = dict(stage="fit", generated_utc=now(), view_A_features=labels_A,
               view_B_features=labels_B, n_A=len(labels_A), n_B=len(labels_B), folds=[])
    for fold in folds:
        f = int(fold["fold"])
        rows, y, w = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + f))
        rec = dict(fold=f, n_train=len(rows), n_pos=int(y.sum()), views={})
        for view in ("A", "B"):
            path = WORK / f"pred_pre_{view}_f{f}.npy"
            t0 = time.time()
            in_auc = None
            if path.exists() and _sidecar(path).exists():
                pred = load_runtime_vector(path, expected_length=len(store.flat_idx))
                log(f"fold {f} pre-{view}: checkpoint reused")
            else:
                path.unlink(missing_ok=True)
                _sidecar(path).unlink(missing_ok=True)
                X = gather(store, bank, rows, view, specs)
                model = base.learner_for(view, SEED + f)
                if w is None:
                    model.fit(X, y)
                else:
                    model.fit(X, y, sample_weight=w)
                in_auc = float(roc_auc_score(y, model.predict_proba(X)[:, 1]))
                del X
                pred = predict_all(store, bank, model, view, specs)
                save_runtime_vector(path, pred)
                del model
                log(f"fold {f} pre-{view}: fit/predict checkpoint written")
            p = np.asarray(load_runtime_vector(path, expected_length=len(store.flat_idx)), np.float32)
            pos = store.inverse[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            catd = ndi.distance_transform_edt(~cat)
            neg = store.inverse[np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())]
            oof = float(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))],
                                      np.r_[p[pos], p[neg]]))
            rec["views"][view] = dict(heldout_region_auc=oof, fit_predict_seconds=time.time() - t0,
                                      n_region_pos=len(pos), n_region_neg=len(neg),
                                      prediction_sha256=sha(path), in_sample_auc=in_auc)
            log(f"fold {f} pre-{view}: OOF AUC {oof:.4f}")
        out["folds"].append(rec)
    out["finished_utc"] = now()
    dump(EVID / "h97_rdva_fit.json", out)
    return out


# ------------------------------------------------------------------------------- exchange once

def stage_exchange():
    check_prereg()
    _r, store, cat, eligible, folds, va, vb, _ring = base.setup()
    bank = DirectionalBank()
    specs, _la, _lb = view_spec(va, vb)
    flat, inv = store.flat_idx, store.inverse
    catd_all = ndi.distance_transform_edt(~cat)
    block_rows, indep_folds = [], []
    for fold in folds:
        f = int(fold["fold"])
        pa = to_grid(store, load_runtime_vector(WORK / f"pred_pre_A_f{f}.npy", expected_length=len(flat)))
        pb = to_grid(store, load_runtime_vector(WORK / f"pred_pre_B_f{f}.npy", expected_length=len(flat)))
        neg = fold["region"] & eligible & ~cat & (catd_all > 4) & np.isfinite(pa) & np.isfinite(pb)
        thresholds = (float(np.quantile(pa[neg], DONOR)), float(np.quantile(pb[neg], DONOR)))
        rows = spatial.negative_block_errors(np.nan_to_num(pa), np.nan_to_num(pb), neg, f, thresholds,
                                             side=BLOCK_SIDE, minimum=32)
        block_rows.extend(rows)
        indep_folds.append(dict(fold=f, labelled_negative_px=int(neg.sum()), n_blocks=len(rows),
                                raw_probability_thresholds=list(thresholds)))
        del pa, pb
    indep = spatial.independence(block_rows, threshold=INDEP_ABANDON, min_blocks=20)
    indep.pop("blocks", None)
    allow = bool(indep["allow_exchange"] and
                 (indep.get("max_abs_correlation") is None or indep["max_abs_correlation"] < INDEP_ABANDON))
    log(f"independence max|rho|={indep['max_abs_correlation']} allow_exchange={allow}")
    out = dict(stage="exchange", generated_utc=now(), independence=dict(result=indep, folds=indep_folds,
               abandon_at_max_abs_correlation_gte=INDEP_ABANDON), allowed_exchange=allow,
               one_round_only=True, donor_rank_min=DONOR, receiver_rank_interval=list(RECEIVER),
               sample_weight=PSEUDO_WEIGHT, cap_per_direction_per_fold=PSEUDO_CAP,
               min_segment_px=PSEUDO_MIN, block_side_px=BLOCK_SIDE, folds=[])
    for fold in folds:
        f = int(fold["fold"])
        pre = {v: np.asarray(load_runtime_vector(WORK / f"pred_pre_{v}_f{f}.npy",
                                                 expected_length=len(flat)), np.float32)
               for v in ("A", "B")}
        train_grid = fold["train"] & eligible
        train_erows = inv[np.flatnonzero(train_grid.ravel())]
        rank_flat = {v: np.full(len(flat), -1.0, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            rank_flat[v][train_erows] = base.pct_rank(pre[v][train_erows])
        rank_grid = {v: to_grid(store, rank_flat[v]) for v in ("A", "B")}
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        forbidden = fold["region"] | fold["held_all"] | cat | (vis_dist <= 4)
        rec = dict(fold=f, train_domain_px=int(train_grid.sum()), forbidden_px=int(forbidden.sum()),
                   directions={})
        pseudo = {}
        for donor, receiver in (("A", "B"), ("B", "A")):
            if allow:
                idx, segments = spatial.whole_pseudo_segments(
                    rank_grid[donor], rank_grid[receiver], train_grid, forbidden,
                    DONOR, RECEIVER[0], RECEIVER[1], side=BLOCK_SIDE,
                    min_pixels=PSEUDO_MIN, cap=PSEUDO_CAP)
            else:
                idx, segments = np.empty(0, np.int64), []
            if len(idx):
                yy, xx = np.unravel_index(idx, eligible.shape)
                assert train_grid[yy, xx].all() and not forbidden[yy, xx].any()
                assert not fold["region"][yy, xx].any() and not fold["held_all"][yy, xx].any()
                assert not cat[yy, xx].any()
            pseudo[receiver] = idx
            np.save(WORK / f"pseudo_{donor}_to_{receiver}_f{f}.npy", idx)
            rec["directions"][f"{donor}->{receiver}"] = dict(n_pixels=len(idx), n_segments=len(segments),
                segments=segments, whole_segments_only=True,
                mean_donor_rank=float(np.mean([x["mean_donor"] for x in segments])) if segments else None,
                mean_receiver_rank=float(np.mean([x["mean_receiver"] for x in segments])) if segments else None)
            log(f"fold {f} {donor}->{receiver}: {len(idx)} px / {len(segments)} whole segments")
        for view in ("A", "B"):
            post_path = WORK / f"pred_post_{view}_f{f}.npy"
            extra = pseudo.get(view, np.empty(0, np.int64))
            if not allow:
                p = pre[view]
                save_runtime_vector(post_path, p)
            else:
                rows, y, _w = base.sample_for_fit(fold, cat, np.random.default_rng(SEED + 100 + f))
                extra = extra[inv[extra] >= 0]
                rows2 = np.r_[rows, extra]
                y2 = np.r_[y, np.ones(len(extra), np.int8)]
                weights = np.r_[np.ones(len(rows), np.float32),
                                np.full(len(extra), PSEUDO_WEIGHT, np.float32)]
                X = gather(store, bank, rows2, view, specs)
                model = base.learner_for(view, SEED + 7 + f)
                model.fit(X, y2, sample_weight=weights)
                del X
                p = predict_all(store, bank, model, view, specs)
                save_runtime_vector(post_path, p)
                del model
            pos = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            neg = inv[np.flatnonzero((fold["region"] & ~cat & (catd_all > 5)).ravel())]
            auc = float(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))],
                                      np.r_[p[pos], p[neg]]))
            rec["directions"][f"refit_{view}"] = dict(n_pseudo_added=len(extra) if allow else 0,
                                                        pseudo_sample_weight=PSEUDO_WEIGHT,
                                                        heldout_region_auc=auc,
                                                        prediction_sha256=sha(post_path))
            log(f"fold {f} post-{view}: OOF AUC {auc:.4f}")
        out["folds"].append(rec)
    out.update(total_pseudo_pixels=sum(d.get("n_pixels", 0) for r in out["folds"]
                                       for d in r["directions"].values()), finished_utc=now(),
               negative_class_caveat="catalogue-zero proxies are not verified fault absence")
    dump(EVID / "h97_rdva_exchange.json", out)
    return out


# -------------------------------------------------------------------------------------- holdout

def stage_holdout():
    reg = check_prereg()
    _r, store, cat, eligible, folds, _va, _vb, _ring = base.setup()
    canary = json.loads((EVID / "h97_rdva_canary.json").read_text())
    exchange = json.loads((EVID / "h97_rdva_exchange.json").read_text())
    terms = {a: None for a in ("single_A_RDVA", "single_B_RDVA", PRIMARY,
                                "union_pre", "Aonly_pre", "random")}
    per_fold = []
    for fold in folds:
        f = int(fold["fold"])
        allowed = allowed_of(fold)
        ai = np.flatnonzero(allowed.ravel())
        grids = {key: to_grid(store, load_runtime_vector(WORK / f"pred_{key}_f{f}.npy",
                                                       expected_length=len(store.flat_idx)))
                 for key in ("pre_A", "pre_B", "post_B")}
        ranks = {key: rank_on(value, allowed) for key, value in grids.items()}
        a_only_mask = allowed & (ranks["pre_A"] >= DONOR) & (ranks["pre_B"] >= RECEIVER[0]) \
                      & (ranks["pre_B"] <= RECEIVER[1])
        aonly_field = np.where(a_only_mask, ranks["pre_A"], -1.0).astype(np.float32)
        rnd = np.full(eligible.shape, -1.0, np.float32)
        rnd.ravel()[ai] = np.random.default_rng(SEED + 500 + f).random(len(ai), dtype=np.float32)
        fields = {"single_A_RDVA": np.nan_to_num(ranks["pre_A"], nan=-1.0),
                  "single_B_RDVA": np.nan_to_num(ranks["pre_B"], nan=-1.0),
                  PRIMARY: np.nan_to_num(ranks["post_B"], nan=-1.0),
                  "union_pre": np.nan_to_num(np.maximum(ranks["pre_A"], ranks["pre_B"]), nan=-1.0),
                  "Aonly_pre": aonly_field, "random": rnd}
        rec = dict(fold=f, allowed_px=int(allowed.sum()), withheld_positive_px=int(fold["truth"].sum()),
                   Aonly_eligible_px=int(a_only_mask.sum()), arms={})
        emitted = {}
        for arm, field in fields.items():
            em = nodes.spacing_select(field, allowed if arm != "Aonly_pre" else a_only_mask,
                                      K_FOLD, min_px=MIN_PX)
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(result, placed=int(em.sum()), requested=K_FOLD,
                                    filled=int(em.sum()) == K_FOLD)
            emitted[arm] = em
            log(f"fold {f} {arm}: HOLDOUT-DTI {result['dti']:.6f}, {int(em.sum())}/{K_FOLD}")
        d, a, b, u = emitted[PRIMARY], emitted["single_A_RDVA"], emitted["single_B_RDVA"], emitted["union_pre"]
        rec["not_union"] = dict(equals_single_A=bool(np.array_equal(d, a)),
                                equals_single_B=bool(np.array_equal(d, b)),
                                equals_union_field=bool(np.array_equal(d, u)),
                                cells_different_from_union=int((d != u).sum()))
        per_fold.append(rec)
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    primary = summary["scores"][PRIMARY]
    paired = summary["paired_differences"]["single_B_RDVA"]
    promotion = bool(primary["dti"] > BAR and paired["ci95"][0] > 0 and
                     not canary["any_alarm"] and exchange["allowed_exchange"])
    out = dict(round="H97", stage="holdout", evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION,
               evaluator_implementation_hashes=evaluator.implementation_hashes(),
               primary=PRIMARY, budget_per_arm_per_fold=K_FOLD, min_spacing_px=MIN_PX,
               withheld_positive_pixels=int(sum(f["truth"].sum() for f in folds)),
               pooled=summary, per_fold=per_fold, independence=exchange["independence"],
               exchange_allowed=exchange["allowed_exchange"],
               pseudo_pixels_total=exchange["total_pseudo_pixels"],
               canary=dict(any_alarm=canary["any_alarm"], max_auc=canary["max_auc"],
                           alarm_rule=canary["alarm_rule"]),
               bar_to_beat=BAR, bar_source="evidence/h84_holdout.json pooled.scores.B_DVA2",
               bar_caveat="H84 B_DVA2 reproduction control failed tolerance; larger observed value retained conservatively",
               promotion=dict(primary_above_bar=primary["dti"] > BAR,
                              paired_vs_single_B=paired,
                              paired_ci_lower_gt_zero=paired["ci95"][0] > 0,
                              pre_artifact_gate_pass=promotion),
               verdict="promotable pending artifact gates" if promotion else "negative",
               registration_sha256=REG_SHA, finished_utc=now())
    dump(EVID / "h97_rdva_holdout.json", out)
    log("pooled " + json.dumps({k: round(v["dti"], 6) for k, v in summary["scores"].items()}))
    log(f"holdout verdict: {out['verdict']}")
    return out


# -------------------------------------------------------------------------------- build field

def stitch(store, folds, key):
    field = np.full(store.valid.shape, np.nan, np.float32)
    for fold in folds:
        f = int(fold["fold"])
        g = to_grid(store, load_runtime_vector(WORK / f"pred_{key}_f{f}.npy",
                                               expected_length=len(store.flat_idx)))
        q = fold["quadrant"] & store.valid
        field[q] = rank_on(g, q)[q]
    return field


def prior_inventory(exclude=None):
    paths = gates.find_priors([DATA / "scored", DATA / "reference", SUBDIR, DLDIR, PRIOR_DIR],
                              exclude=exclude)
    # Eliminate candidate aliases/checkpoints by naming convention as a second fail-safe.
    return [p for p in paths if "h97-rdva-candidate" not in p.name and "gems52-h97-rdva-cotrain" not in p.name]


def small_lane(report):
    out = {k: v for k, v in report.items() if k != "per_prior"}
    rows = [x for x in report.get("per_prior", []) if not x.get("error")]
    out["top_rank"] = sorted(((x.get("spearman") or 0.0, x["path"]) for x in rows), reverse=True)[:5]
    out["top_near"] = sorted(((x.get("near_3px_fraction") or 0.0, x["path"],
                               x.get("universal_coverage_probe")) for x in rows), reverse=True)[:5]
    return out


def stage_build():
    check_prereg()
    _r, store, cat, eligible, folds, _va, _vb, _ring = base.setup()
    preA, preB, postB = (stitch(store, folds, k) for k in ("pre_A", "pre_B", "post_B"))
    field = np.nan_to_num(postB, nan=0.0).astype(np.float32)
    priors = prior_inventory()
    log(f"surface lane against {len(priors)} accessible registry rasters")
    lane_s = gates.lane_report(field, eligible, priors, sample=SAMPLE, phase="surface", log=log)
    dump(EVID / "h97_rdva_lane_surface.json", small_lane(lane_s))
    literal_rank_fail = bool((lane_s["literal"]["max_spearman"] or 0.0) > 0.90)
    if literal_rank_fail:
        dump(EVID / "h97_rdva_build_stop.json", dict(stage="build", verdict="DUPLICATE/STOP",
             reason="surface Spearman >0.90 with an accessible registry raster",
             lane_surface=small_lane(lane_s), generated_utc=now()))
        raise SystemExit("H97 surface is duplicate by frozen literal rank rule; stopping before placement")
    with rasterio.open(SAMPLE) as src:
        sample_domain = np.isfinite(src.read(1))
    catd = ndi.distance_transform_edt(~cat)
    allowed = eligible & sample_domain & ~cat & (catd > RING_PX)
    dots = nodes.spacing_select(np.where(allowed, field, -1.0).astype(np.float32), allowed,
                                K_SHIP, min_px=MIN_PX)
    if int(dots.sum()) != K_SHIP:
        raise RuntimeError(f"final budget shortfall: {int(dots.sum())}/{K_SHIP}")
    pred = dots.astype(np.float32)
    # Equal-budget constituent/union-field placements.
    ea = nodes.spacing_select(np.nan_to_num(preA, nan=-1.0), allowed, K_SHIP, min_px=MIN_PX)
    eb = nodes.spacing_select(np.nan_to_num(preB, nan=-1.0), allowed, K_SHIP, min_px=MIN_PX)
    eu = nodes.spacing_select(np.nan_to_num(np.maximum(preA, preB), nan=-1.0), allowed,
                              K_SHIP, min_px=MIN_PX)
    set_union = ea | eb
    def jac(x, y):
        return float((x & y).sum() / max(int((x | y).sum()), 1))
    not_union = dict(equals_single_A=bool(np.array_equal(dots, ea)),
                     equals_single_B=bool(np.array_equal(dots, eb)),
                     equals_equal_budget_union_field=bool(np.array_equal(dots, eu)),
                     equals_literal_set_union=bool(np.array_equal(dots, set_union)),
                     jaccard_single_A=jac(dots, ea), jaccard_single_B=jac(dots, eb),
                     jaccard_union_field=jac(dots, eu), jaccard_set_union=jac(dots, set_union),
                     dots_outside_union_field=int((dots & ~eu).sum()),
                     dots_outside_set_union=int((dots & ~set_union).sum()),
                     gate=bool(jac(dots, eu) < 0.99 and not np.array_equal(dots, set_union)))
    save_runtime_vector(WORK / "field_pre_A.npy", np.nan_to_num(preA, nan=0.0).astype(np.float32))
    save_runtime_vector(WORK / "field_pre_B.npy", np.nan_to_num(preB, nan=0.0).astype(np.float32))
    save_runtime_vector(WORK / "field_post_B.npy", field)
    save_runtime_vector(WORK / "final_pred_idx.npy", np.flatnonzero(dots.ravel()).astype(np.int64))
    out = dict(stage="build", generated_utc=now(), target_px=K_SHIP, emitted_px=int(dots.sum()),
               allowed_px=int(allowed.sum()), min_catalogue_distance_m=float(catd[dots].min() * 100.0),
               within_300m_of_catalogue_px=int((catd[dots] <= 3).sum()), spacing_px=MIN_PX,
               field_decoded_sha256=hashlib.sha256(field.astype("<f4").tobytes()).hexdigest(),
               prediction_decoded_sha256=hashlib.sha256(pred.astype("<f4").tobytes()).hexdigest(),
               surface_lane=small_lane(lane_s), not_the_union=not_union,
               surface_literal_rank_gate_pass=not literal_rank_fail)
    dump(EVID / "h97_rdva_build.json", out)
    log(f"placed {int(dots.sum())}; not-union J={not_union['jaccard_union_field']:.4f}")
    return out


# ------------------------------------------------------------------------------ reasoning/write

def write_reasoning(stem, pred, preA, preB, cat, eligible, exchange):
    """Every final A-confident/B-abstaining dot plus every donated A->B whole segment."""
    idx = np.flatnonzero(pred.ravel() > 0)
    yy, xx = np.unravel_index(idx, pred.shape)
    aonly = (preA[yy, xx] >= DONOR) & (preB[yy, xx] >= RECEIVER[0]) & (preB[yy, xx] <= RECEIVER[1])
    with rasterio.open(FEATURES) as src:
        cover, grav, gh, slope = (src.read(i) for i in (15, 13, 18, 19))
        T = src.transform
    q = lambda a, p: float(np.nanpercentile(np.where((a > -1e38) & eligible, a, np.nan), p))
    cov50, grav25, grav75, gh75, slope50 = q(cover, 50), q(grav, 25), q(grav, 75), q(gh, 75), q(slope, 50)
    path = SUBDIR / f"{stem}-a-only-reasoning.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "utm_x_m", "utm_y_m", "rank_A", "rank_B", "depth_to_basement_band15",
                    "gravity_anomaly_band13", "gravity_hg_band18", "surface_slope_band19",
                    "geological_reasoning", "named_non_fault_mimics", "verification_status"])
        for j in np.flatnonzero(aonly):
            r, c = int(yy[j]), int(xx[j]); x, y = T * (c + 0.5, r + 0.5)
            signatures = []
            signatures.append("greater-than-median sedimentary cover" if cover[r, c] > cov50 else "thin/moderate cover")
            signatures.append("strong gravity gradient" if gh[r, c] > gh75 else "moderate gravity gradient")
            signatures.append("gravity low/high tail" if grav[r, c] < grav25 or grav[r, c] > grav75 else "mid-range gravity")
            signatures.append("low slope/no clear scarp" if slope[r, c] < slope50 else "moderate/high slope")
            reason = (f"A-only disagreement: View A rank {preA[r,c]:.3f}, View B rank {preB[r,c]:.3f}; "
                      f"{', '.join(signatures)}. A persistent gravity/basement directional step without a "
                      "surface/radiometric response is consistent with a concealed fault offset beneath basin fill.")
            mimics = "lithologic contact; intrusive margin; basin-margin facies change; differential compaction"
            status = "Phase-2 candidate only; not an independently mapped or field-verified fault"
            w.writerow([r, c, f"{x:.1f}", f"{y:.1f}", f"{preA[r,c]:.6f}", f"{preB[r,c]:.6f}",
                        f"{cover[r,c]:.7g}", f"{grav[r,c]:.7g}", f"{gh[r,c]:.7g}", f"{slope[r,c]:.7g}",
                        reason, mimics, status])
    # One row per whole donated A->B segment; receipts are already complete (not truncated).
    seg_path = SUBDIR / f"{stem}-pseudo-segments.csv"
    with seg_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fold", "direction", "component", "block_row", "block_col", "pixels", "mean_donor_rank",
                    "mean_receiver_rank", "geological_interpretation", "named_non_fault_mimics",
                    "leakage_guards"])
        nseg = 0
        for fr in exchange["folds"]:
            direction = "A->B"
            for s in fr["directions"].get(direction, {}).get("segments", []):
                w.writerow([fr["fold"], direction, s.get("component"), s.get("block_row"), s.get("block_col"),
                            s.get("pixels"), s.get("mean_donor"), s.get("mean_receiver"),
                            "whole A-confident/B-abstaining segment: candidate buried basement/potential-field fault",
                            "lithologic contact; intrusive margin; basin facies boundary; interpolation edge",
                            "one 50px block; training domain only; outside held/eval/catalogue/400m-visible collar"])
                nseg += 1
    return dict(a_only_path=str(path.relative_to(ROOT)), a_only_rows=int(aonly.sum()),
                pseudo_segments_path=str(seg_path.relative_to(ROOT)), pseudo_A_to_B_segments=nseg,
                one_reason_per_final_A_only_candidate=True)


def stage_write():
    reg = check_prereg()
    hold = json.loads((EVID / "h97_rdva_holdout.json").read_text())
    build = json.loads((EVID / "h97_rdva_build.json").read_text())
    exchange = json.loads((EVID / "h97_rdva_exchange.json").read_text())
    _r, store, cat, eligible, _folds, _va, _vb, _ring = base.setup()
    idx = np.asarray(load_runtime_vector(WORK / "final_pred_idx.npy", expected_length=K_SHIP), np.int64)
    pred = np.zeros(eligible.shape, np.float32); pred.ravel()[idx] = 1.0
    n_grid = int(np.prod(eligible.shape))
    preA = load_runtime_vector(WORK / "field_pre_A.npy", expected_length=n_grid).reshape(eligible.shape)
    preB = load_runtime_vector(WORK / "field_pre_B.npy", expected_length=n_grid).reshape(eligible.shape)
    field = load_runtime_vector(WORK / "field_post_B.npy", expected_length=n_grid).reshape(eligible.shape)
    dhash = hashlib.sha256(pred.astype("<f4").tobytes()).hexdigest()
    stem = f"gems52-h97-rdva-cotrain-{len(idx)}px-{ROUND_DATE.replace('-', '')}-{dhash[:12]}-zeros"
    note = "H97 view-pure radiometric DVA co-training; 25,400 dots, 3px, 200m collar; research only, no slot approved"
    assert len(note) <= 140
    SUBDIR.mkdir(exist_ok=True); DLDIR.mkdir(parents=True, exist_ok=True)
    tif = SUBDIR / f"{stem}.tif"
    receipt = submission_writer.write_submission(tif, pred, SAMPLE, eligible, note=note, name=stem,
        metadata=dict(round="H97-RDVA", original_frozen_round="H97", primary=PRIMARY, preregistration_sha256=REG_SHA,
                      hypothesis_sha256=DOC_SHA, evidence_class="HOLDOUT-DTI"))
    fmt = gates.format_report(tif, SAMPLE, footprint=eligible)
    priors = prior_inventory(exclude=tif)
    log(f"final uniqueness/lane against {len(priors)} accessible registry rasters")
    uniq = gates.uniqueness_report(pred, priors)
    lane_d = gates.lane_report(pred, eligible, priors, sample=SAMPLE, phase="dots", log=log)
    # Recheck surface on the exact final registry inventory (no H97 copies staged yet).
    lane_s = gates.lane_report(np.asarray(field), eligible, priors, sample=SAMPLE, phase="surface", log=log)
    dump(EVID / "h97_rdva_lane_dots.json", small_lane(lane_d))
    dump(EVID / "h97_rdva_lane_surface.json", small_lane(lane_s))
    uniq_small = {k: v for k, v in uniq.items() if k != "per_prior"}
    rows = [x for x in uniq["per_prior"] if not x.get("error")]
    uniq_small["max_jaccard"] = max((x.get("jaccard", 0.0) for x in rows), default=0.0)
    uniq_small["max_jaccard_source"] = max(rows, key=lambda x: x.get("jaccard", 0.0))["path"] if rows else None
    # Exact file copying is ruled out cheaply and completely: unequal byte lengths cannot be
    # byte-identical, so only same-length priors need hashing. Decoded equality remains the stronger
    # prediction test above because different TIFF encodings can hold the same raster.
    same_size = [p for p in priors if p.stat().st_size == tif.stat().st_size]
    same_hash = [str(p) for p in same_size if sha(p) == fmt["sha256"]]
    uniq_small["file_byte_identity"] = dict(
        inventory_entries=len(priors), candidate_bytes=tif.stat().st_size,
        same_size_entries=len(same_size), same_sha256_entries=len(same_hash),
        identical_paths=same_hash, distinct_from_every_inventory_file=not same_hash,
        method="stat every entry; SHA-256 every entry with candidate byte length")
    errors = [x for x in uniq["per_prior"] if x.get("error")]
    uniq_small["distinct_by_decoded_values_or_shape"] = bool(
        uniq["distinct_from_every_comparable_prior"] and
        all("not aligned single-band prediction" in x["error"] for x in errors))
    dump(EVID / "h97_rdva_uniqueness.json", uniq_small)
    reasoning = write_reasoning(stem, pred, preA, preB, cat, eligible, exchange)

    literal_surface_pass = lane_s["literal"]["verdict"] == "PASS"
    literal_dots_pass = lane_d["literal"]["verdict"] == "PASS"
    gates_all = dict(holdout=hold["promotion"]["pre_artifact_gate_pass"],
                     canary=not hold["canary"]["any_alarm"], independence=hold["exchange_allowed"],
                     surface_literal_lane=literal_surface_pass, final_dot_literal_lane=literal_dots_pass,
                     decoded_pattern_unique=uniq["canonical_pattern_unique"],
                     not_literal_prior_union=not uniq["equals_literal_prior_union"],
                     not_view_union=build["not_the_union"]["gate"], format=fmt["ok"])
    promote = bool(all(gates_all.values()))
    primary = hold["pooled"]["scores"][PRIMARY]
    paired = hold["pooled"]["paired_differences"]["single_B_RDVA"]
    card = dict(round="H97-RDVA", original_frozen_round="H97", generated_utc=now(),
        integration_note="Executed and frozen under the H97 namespace on an isolated branch; main independently acquired H97 through H102 before integration. Published as H97-RDVA without changing frozen preregistration bytes.",
        hypothesis="View-pure directional semivariance in A (gravity/basement) and B (DEM/radiometrics), followed by exactly one weighted whole-segment disagreement exchange.",
        mechanism="A-only lineaments can be concealed basement faults; radiometric/DEM directional texture gives B an altered-surface response. Only confident-donor/abstaining-receiver whole segments cross views.",
        named_non_fault_mimic="lithologic or intrusive contact; radiometric flight-line/interpolation stripe; road; erosion rill; palaeochannel; basin facies boundary",
        holdout_dti=dict(label="HOLDOUT-DTI", evaluator_version=hold["evaluator_version"],
                         withheld_positive_pixels=hold["withheld_positive_pixels"],
                         primary_arm=PRIMARY, primary=primary, paired_vs_single_B_RDVA=paired,
                         all_scores=hold["pooled"]["scores"],
                         ci_method="95% paired 20 km spatial-cluster bootstrap, 1,000 draws"),
        bar_to_beat=BAR, bar_source=hold["bar_source"], bar_caveat=hold["bar_caveat"],
        independence=exchange["independence"], exchange_allowed=exchange["allowed_exchange"],
        pseudo_pixels=exchange["total_pseudo_pixels"], canary=hold["canary"],
        registry_correlation_overlap=dict(
            priors_checked=len(priors),
            surface_max_spearman=lane_s["literal"]["max_spearman"],
            surface_literal_verdict=lane_s["literal"]["verdict"],
            final_dot_max_near_3px_fraction=lane_d["literal"]["max_near_3px_fraction"],
            final_dot_near_source=lane_d["literal"]["max_near_source"],
            final_dot_literal_verdict=lane_d["literal"]["verdict"],
            policy_verdicts=dict(surface=lane_s["policy"]["verdict"], dots=lane_d["policy"]["verdict"])),
        uniqueness=uniq_small, not_the_union=build["not_the_union"],
        raster=dict(file=str(tif.relative_to(ROOT)), sha256=fmt["sha256"],
                    decoded_sha256=dhash, bytes=tif.stat().st_size, nonzero_px=len(idx)),
        validator=fmt, unique_submission_name=stem, note=note, note_chars=len(note),
        reasoning=reasoning, gates=gates_all,
        verdict="promotable" if promote else "negative",
        # Download safety is about readable, normalized, distinct research bytes.  One 32x48 census
        # thumbnail is incomparable and therefore makes the legacy fail-closed
        # `canonical_pattern_unique` key false, but it does not make this aligned 3730x3292 raster
        # unsafe to inspect/download.  Submission remains blocked by the literal lane + holdout.
        download_ok=bool(fmt["ok"] and uniq["distinct_from_every_comparable_prior"]
                         and not uniq["identical_to_a_prior"]),
        submit_ok=False, approved_for_weekly_slot=False, submission_slots_used=0,
        submission_decision="DO NOT SUBMIT: selector step was not run; no weekly slot is approved.",
        literal_lane_stop=not (literal_surface_pass and literal_dots_pass),
        registration=dict(path=str(REG_PATH.relative_to(ROOT)), sha256=REG_SHA,
                          hypothesis_sha256=DOC_SHA, frozen_before_fit=True),
        full_validator_result=fmt,
        evidence_class_note="No organizer upload occurred. A holdout number is not a board score; no H97 value is ORGANIZER-CONFIRMED.",
        download_safety_note="YES for research/audit: single-band float32, finite [0,1], template-aligned, and distinct from all 718 comparable priors. One 32x48 census thumbnail is incomparable; holdout/lane failures make submission NO.",
        irregularities=["IR-H97-RDVA-001", "IR-H97-RDVA-002", "IR-H97-RDVA-003", "IR-H97-RDVA-004", "IR-H97-RDVA-005", "IR-H97-RDVA-006"])

    dump(EVID / "h97_rdva_run_card.json", card)
    # Extend the writer receipt with the final safety facts, then stage exact downloads.
    receipt.update(round="H97-RDVA", original_frozen_round="H97", short_tif="h97-rdva-candidate.tif", short_zip="h97-rdva-candidate.zip",
                   nonzero_px=len(idx), note=note, note_chars=len(note),
                   approved_for_weekly_slot=False, promoted=False, submission_slots_used=0,
                   download_ok=card["download_ok"], submit_ok=False,
                   verdict=card["verdict"], run_card="evidence/h97_rdva_run_card.json")
    dump(EVID / f"submission_{stem}.json", receipt)
    dump(tif.with_suffix(".json"), receipt)
    for src, dest in ((tif, DLDIR / tif.name), (tif.with_suffix(".zip"), DLDIR / tif.with_suffix(".zip").name),
                      (tif.with_suffix(".json"), DLDIR / tif.with_suffix(".json").name),
                      (tif, DLDIR / "h97-rdva-candidate.tif"),
                      (tif.with_suffix(".zip"), DLDIR / "h97-rdva-candidate.zip")):
        shutil.copyfile(src, dest)
    for rpath in (SUBDIR / f"{stem}-a-only-reasoning.csv", SUBDIR / f"{stem}-pseudo-segments.csv"):
        shutil.copyfile(rpath, DLDIR / rpath.name)
    log(f"H97 artifact {tif.name} sha256={fmt['sha256']}")
    log(f"verdict={card['verdict']} DOWNLOAD={'YES' if card['download_ok'] else 'NO'} SUBMIT=NO")
    return card


def main(argv=None):
    argv = sys.argv if argv is None else argv
    stage = argv[1] if len(argv) > 1 else "all"
    names = ["channels", "canary", "fit", "exchange", "holdout", "build", "write"]
    if stage not in names + ["all"]:
        raise SystemExit(f"usage: {argv[0]} [{'|'.join(names)}|all]")
    chosen = names if stage == "all" else [stage]
    funcs = {"channels": stage_channels, "canary": stage_canary, "fit": stage_fit,
             "exchange": stage_exchange, "holdout": stage_holdout,
             "build": stage_build, "write": stage_write}
    t0 = time.time()
    for name in chosen:
        s = time.time(); log(f"=== H97 {name} ==="); funcs[name](); log(f"--- {name}: {time.time()-s:.1f}s")
    log(f"H97 selected stages complete in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
