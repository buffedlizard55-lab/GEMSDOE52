#!/usr/bin/env python3
"""H66 runner: local-scale, low-capacity View A inside the H61 co-training template.

Reuses (does not fork) ``scripts/run_h61.py`` for folds, sampling, fit, exchange, holdout and the
canary, and ``scripts/build_h61_submission.py::prior_paths`` for the registry. Only three hooks change:

* the output directories (module globals ``WORK``, ``EVID``, ``DOCS``) point at ``work/h66`` so H61's
  receipts are never overwritten;
* ``setup()`` returns the View A feature list restricted to the pre-registered local channels (H66-A);
* ``learner_for('A')`` is a logistic pipeline; ``learner_for('B')`` is H61's learner unchanged.

Frozen rules live in ``knowledge/43_hypotheses_H66_preregistered.md`` (SHA-256 pinned in
``registry/h66_preregistration.json``). The runner refuses to run if either hash moves.

Stages:  canary -> fit -> diagnostic -> (premise gate printed) -> exchange -> holdout -> build.
The build step always runs after the holdout because the pre-registration allows a research-only
artefact on a premise FAIL; it never sets a slot-eligible verdict unless every condition in §2.10 holds.
Nothing here uploads anything or consumes a weekly slot.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h61 as h61                                   # noqa: E402  shared H61 template
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_h61_submission",
                                               ROOT / "scripts" / "build_h61_submission.py")
build_h61 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_h61)                     # for prior_paths() only; no main() call

REG_PATH = ROOT / "registry/h66_preregistration.json"
DOC_PATH = ROOT / "knowledge/43_hypotheses_H66_preregistered.md"
WORK = ROOT / "work/h66"
EVID_OUT = ROOT / "evidence"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
SEED = h61.SEED
BUDGET = 37600
MIN_PX = 3.0
OWN_PREFIX = "gems52-h66-"
EXPECTED_A_LOCAL = [
    "A_RTP_grad_1", "A_RTP_grad_3", "A_gravity_grad_1", "A_gravity_grad_3",
    "A_cover_grad_1", "A_cover_grad_3", "A_gravity_cover_signed_1", "A_gravity_cover_signed_3",
    "A_gravity_persistence_1_3", "A_cover_persistence_1_3", "A_gravity_coherence",
    "A_cover_coherence", "X_mag_TMI_up150_grad1", "X_mag_TMI_up150_grad3",
]
ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random")


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ pre-registration guard
def guard() -> dict:
    reg = json.loads(REG_PATH.read_text())
    if sha256_file(DOC_PATH) != reg["hypothesis_sha256"]:
        raise SystemExit("H66 pre-registration document changed after registration; refusing to run")
    if sha256_file(ROOT / reg["inherited_thresholds_from"]["path"]) != reg["inherited_thresholds_from"]["sha256"]:
        raise SystemExit("inherited H61 registry changed; refusing to run")
    return reg


# ------------------------------------------------------------------ hooks into the H61 template
def local_view_A(va: list[str]) -> list[str]:
    sel = [n for n in va
           if n.endswith(("_1", "_3", "_1_3", "grad1", "grad3", "_coherence"))
           and not n.startswith("raw_band_") and "rank" not in n]
    if sorted(sel) != sorted(EXPECTED_A_LOCAL):
        raise SystemExit(f"H66-A feature rule drifted: got {sorted(sel)}")
    return sel


_orig_setup = h61.setup


def setup_h66():
    reg, store, cat, eligible, folds, va, vb, ring_px = _orig_setup()
    return reg, store, cat, eligible, folds, local_view_A(va), vb, ring_px


def learner_for_h66(view: str, seed: int = SEED):
    if view == "A":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=1.0, max_iter=2000))
    return h61.learner(seed)


def install_hooks(stage_setup: bool):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "evid").mkdir(parents=True, exist_ok=True)
    (WORK / "docs").mkdir(parents=True, exist_ok=True)
    h61.WORK = WORK
    h61.EVID = WORK / "evid"
    h61.DOCS = WORK / "docs"
    h61.learner_for = learner_for_h66
    if stage_setup:
        h61.setup = setup_h66


# ------------------------------------------------------------------ diagnostic (non-gating)
def stage_diagnostic():
    reg, store, cat, eligible, folds, va, vb, ring_px = h61.setup()   # patched: local A
    inv = store.inverse
    out = dict(stage="diagnostic", started_utc=now(), gating=False,
               learner="HistGradientBoostingClassifier(max_depth=3,max_iter=150,lr=0.05,min_samples_leaf=200,l2=1.0)",
               view_A_features=va, folds=[])
    for fold in folds:
        rng = np.random.default_rng(SEED + 1000 + fold["fold"])
        rows, y = h61.sample_train(fold, cat, rng)
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05,
                                           min_samples_leaf=200, l2_regularization=1.0,
                                           early_stopping=False, random_state=SEED + 1000)
        m.fit(store.gather(rows, va), y)
        # store.gather takes GRID-FLAT indices (as in run_h61.stage_fit), not store rows
        pos_flat = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        catd = ndi.distance_transform_edt(~cat)
        neg_flat = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        del catd
        Xe = store.gather(np.concatenate([pos_flat, neg_flat]), va)
        ye = np.r_[np.ones(len(pos_flat)), np.zeros(len(neg_flat))]
        auc = float(roc_auc_score(ye, m.predict_proba(Xe)[:, 1]))
        out["folds"].append(dict(fold=fold["fold"], heldout_region_auc_hgb_local=auc,
                                 n_region_pos=int(len(pos_flat)), n_region_neg=int(len(neg_flat))))
        log(f"diagnostic fold {fold['fold']}: HGB-local region AUC {auc:.4f}")
    vals = [r["heldout_region_auc_hgb_local"] for r in out["folds"]]
    out.update(finished_utc=now(), mean=float(np.mean(vals)), min=float(np.min(vals)))
    (WORK / "evid" / "h66_diagnostic_hgb_local.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def premise_summary() -> dict:
    ck = json.loads((WORK / "evid" / "h61_fit_checkpoint.json").read_text())
    aucs = [f["view_A"]["heldout_region_auc"] for f in ck["folds"]]
    bucs = [f["view_B"]["heldout_region_auc"] for f in ck["folds"]]
    m, lo = float(np.mean(aucs)), float(np.min(aucs))
    verdict = "PASS" if (m >= 0.60 and lo >= 0.55) else "FAIL"
    return dict(view_A_local_oof_auc_per_fold=aucs, view_A_mean=m, view_A_min=lo,
                view_B_oof_auc_per_fold=bucs, view_B_mean=float(np.mean(bucs)),
                premise_gate="mean>=0.60 and min>=0.55 (H65 section 3, inherited)", verdict=verdict)


# ------------------------------------------------------------------ build: emission + gates
def build() -> dict:
    reg = json.loads(REG_PATH.read_text())
    th = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    store = structural.FeatureStore(ROOT / h61.STORE)
    eligible = store.valid
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
        sample_grid = (ref.shape, ref.crs, ref.transform)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        if (ds.shape, ds.crs, ds.transform) != sample_grid:
            raise SystemExit("labels grid mismatch")
        cat = ds.read(1) == 1
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    folds = list(spatial.folds(cat, eligible, buffer_px=th["buffer_px"]))
    inv = store.inverse
    shape = eligible.shape
    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_post_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[v] = g.reshape(shape)
        del g
    covered = np.isfinite(mos["A"]) & np.isfinite(mos["B"])
    if not (covered == eligible).all():
        raise SystemExit(f"OOF mosaic covers {int(covered.sum())} px, eligible {int(eligible.sum())}")
    allowed = eligible & sub_finite & ~cat & (cat_dist > th["catalogue_exclusion_m"])
    allowed_idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[allowed_idx] = h61.pct_rank(mos["A"].ravel()[allowed_idx])
    rankB.ravel()[allowed_idx] = h61.pct_rank(mos["B"].ravel()[allowed_idx])
    field = np.where(allowed, rankA - rankB, -1.0).astype(np.float32)
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)
    surface_field = np.where(allowed, (field - field[allowed].min()) /
                             max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    log(f"emission domain {int(allowed.sum())} px; placing {BUDGET} dots")

    census = json.loads(CENSUS.read_text())
    if census.get("n_errors") != 0 or len(census.get("files", {})) != census.get("n_entries"):
        raise SystemExit("census incomplete or has errors; the lane gate refuses a partial registry")
    priors, pmeta = build_h61.prior_paths(CENSUS, ("submission",))
    priors = [p for p in priors if not p.name.startswith(OWN_PREFIX)]
    pmeta["excluded_own_round_prefix"] = OWN_PREFIX
    log(f"registry: {len(priors)} rasters ({pmeta})")

    lane_surface = gates.lane_report(surface_field, allowed, priors,
                                     sample=ROOT / "data/sample_submission.tif", phase="surface", log=log)
    emission = nodes.spacing_select(field, allowed, BUDGET, min_px=MIN_PX, log=log)
    n_dots = int(emission.sum())
    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if n_dots and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    stem = f"{OWN_PREFIX}localA-cotrain-{n_dots}px"
    sub_name = f"{stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"[:140]
    note = ("H66 local View-A co-training: 14 local-scale potential-field channels vs DEM+radiometric "
            "B; one exchange; 3px dots; >200m off catalogue; research-only")
    if len(note) > 140:
        note = "H66 local-A cotrain: 3px dots, >200m off catalogue, research-only"
    outdir = ROOT / "submission"
    outdir.mkdir(exist_ok=True)
    path = outdir / f"{stem}.tif"
    receipt = submission_writer.write_submission(
        path, pred, ROOT / "data/sample_submission.tif", sub_finite, note=note, name=sub_name,
        metadata=dict(round="H66", seed=SEED, budget=BUDGET, placed=n_dots, min_separation_px=MIN_PX,
                      field="post-exchange rank difference, local View A", views=dict(A=EXPECTED_A_LOCAL),
                      catalogue_exclusion_m=th["catalogue_exclusion_m"]))
    log(f"wrote {path} sha256 {receipt['sha256']} dots {n_dots}")

    lane_dots = gates.lane_report(pred, eligible, priors, sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log)
    # uniqueness through the shared audit tool, census receipt as third argument (never a fork)
    audit_out = EVID_OUT / "h66_uniqueness_audit.json"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/audit_uniqueness.py"), str(path),
                           str(audit_out), str(CENSUS)], cwd=ROOT, capture_output=True, text=True)
    audit = json.loads(audit_out.read_text()) if audit_out.exists() else dict(error=proc.stderr[-800:])
    return dict(emission=dict(path=str(path.relative_to(ROOT)), sha256=receipt["sha256"],
                              bytes=receipt["bytes"], dots=n_dots, note=note, name=sub_name),
                writer_receipt={k: v for k, v in receipt.items() if k != "per_prior"},
                registry=pmeta, lane_surface=lane_surface, lane_dots=lane_dots,
                uniqueness_audit_rc=proc.returncode,
                uniqueness_audit=dict(verdict=audit.get("verdict"), summary=audit.get("summary"))
                if isinstance(audit, dict) else audit)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["canary", "fit", "diagnostic", "exchange", "holdout", "build", "all"])
    args = ap.parse_args()
    reg = guard()
    stages = ["canary", "fit", "diagnostic", "exchange", "holdout", "build"] if args.stage == "all" else [args.stage]
    t0 = time.time()
    summary = {}
    for st in stages:
        log(f"=== H66 stage {st} ({now()}) ===")
        if st == "canary":
            install_hooks(stage_setup=False)          # all 73 features, H61 canary unchanged
            h61.stage_canary()
        elif st == "fit":
            install_hooks(stage_setup=True)
            h61.stage_fit()
            summary["premise"] = premise_summary()
            log(f"PREMISE {summary['premise']['verdict']}: A_local mean {summary['premise']['view_A_mean']:.4f} "
                f"min {summary['premise']['view_A_min']:.4f} (B mean {summary['premise']['view_B_mean']:.4f})")
        elif st == "diagnostic":
            install_hooks(stage_setup=True)
            d = stage_diagnostic()
            summary["diagnostic_hgb_local"] = dict(mean=d["mean"], min=d["min"])
        elif st == "exchange":
            install_hooks(stage_setup=True)
            ex = h61.stage_exchange()
            summary["exchange_allowed"] = ex.get("allowed_exchange")
            summary["exchange_pixels"] = ex.get("total_pseudo_pixels")
        elif st == "holdout":
            install_hooks(stage_setup=True)
            ho = h61.stage_holdout()
            scores = ho["pooled"]["scores"]
            summary["holdout_scores"] = {a: {k: scores[a][k] for k in scores[a] if k in
                                             ("dti", "ci95", "ci_low", "ci_high", "tpw", "withheld_positive_pixels")}
                                         for a in scores}
            single_b = scores["single_B"].get("dti")
            summary["reproduction_single_B_vs_H61"] = dict(h66=single_b, h61_receipt=0.174517,
                                                           match=bool(single_b is not None and abs(single_b - 0.174517) < 1e-6))
        elif st == "build":
            summary["build"] = build()
    summary["elapsed_seconds"] = round(time.time() - t0, 1)
    (WORK / "evid" / "h66_stage_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    log(json.dumps(summary, indent=1, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
