#!/usr/bin/env python3
"""H76-1 -- DVA of band 18 (iso_grav_anom_hg) added to View B; one experiment; holdout only.

Preregistered in knowledge/68_h76_preregistered.md (pinned in registry/h76_preregistration.json).
Shared, not forked: run_h75 (setup via run_h61, DVA kernel, gather/predict, allowed_of, evaluator calls).
Reused arms: single_B, B_DVA and random predictions/terms from work/h75 (same rows, learner, seed, folds).
Only B_DVA18 is fitted here. No placement or emission file is written by this runner.

Usage: python scripts/run_h76.py [fit|holdout|all]
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import numpy as np                                                   # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
import run_h75 as h75                                                # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import nodes                                             # noqa: E402

PREREG = ROOT / "registry/h76_preregistration.json"
WORK = ROOT / "work/h76"
H75 = ROOT / "work/h75"
EVID = ROOT / "evidence"
K_FOLD = 9400
B18 = {18: "iso_grav_anom_hg"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H76 preregistration changed after freezing")
    return reg


def write(name, obj):
    p = EVID / f"h76_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float))
    return p


def band18_channels(eligible):
    """Same DVA kernel as H75, applied to band 18 only (run_h75.DVA_BANDS swapped for this call)."""
    saved = h75.DVA_BANDS
    h75.DVA_BANDS = B18
    try:
        return h75.dva_channels(eligible)
    finally:
        h75.DVA_BANDS = saved


def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    WORK.mkdir(parents=True, exist_ok=True)
    h75_dva = dict(np.load(H75 / "dva.npz"))
    new = band18_channels(eligible)
    np.savez_compressed(WORK / "dva18.npz", **new)
    dva = dict(h75_dva)
    dva.update(new)
    log(f"band-18 DVA channels: {sorted(new)}; total B_DVA18 channels {len(dva)}")
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", arm="B_DVA18", new_channels=sorted(new), folds=[])
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(base.SEED + f)
        rows, y, _ = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        m = base.learner_for("B", base.SEED)
        m.fit(h75.gather(store, rows, vb, dva), y)
        p = h75.predict(store, m, vb, dva, flat)
        np.save(WORK / f"pred_B_DVA18_f{f}.npy", p)
        g = base.to_grid(flat, p, eligible.shape).ravel()
        auc = float(roc_auc_score(yy, np.r_[g[pos_g], g[neg_g]]))
        canary = {}
        for k in sorted(new):
            v = new[k].ravel()[np.r_[pos_g, neg_g]]
            ok = np.isfinite(v)
            a = float(roc_auc_score(yy[ok], v[ok]))
            canary[k] = max(a, 1 - a)
        rec = dict(fold=f, auc_B_DVA18=auc, canary=canary, canary_max=max(canary.values()))
        log(f"fold {f}: AUC B_DVA18 {auc:.4f}; band-18 canary max {rec['canary_max']:.3f}")
        out["folds"].append(rec)
    out["canary_max"] = max(r["canary_max"] for r in out["folds"])
    out["canary_alarm"] = out["canary_max"] >= 0.90
    write("fit", out)


def allowed_of(fold, ring_px):
    return h75.allowed_of(fold, ring_px)


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    arms = ("single_B", "B_DVA", "B_DVA18", "random")
    terms = {a: None for a in arms}
    out = dict(stage="holdout", evaluator="gems52-pooled-hide-v1", budget_per_fold=K_FOLD,
               reused_from="work/h75 (single_B, B_DVA, random)", folds=[])
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        rec = dict(fold=f, arms={})
        for arm in arms:
            fld = np.full(eligible.shape, -1.0, np.float32)
            if arm == "random":
                fld.ravel()[ai] = np.random.default_rng(base.SEED + 500 + f).random(len(ai), dtype=np.float32)
            else:
                src = WORK if arm == "B_DVA18" else H75
                pred = np.load(src / f"pred_{arm}_f{f}.npy")
                g = base.to_grid(store.flat_idx, pred, eligible.shape)
                fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
            em = nodes.spacing_select(fld, allowed, K_FOLD, min_px=3.0)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f}")
        out["folds"].append(rec)
    summ = evaluator.pooled_summary(terms, draws=1000, seed=base.SEED, candidate="B_DVA18")
    out["pooled"] = summ
    # preregistered comparison: the evaluator's own paired block-bootstrap (candidate B_DVA18 vs B_DVA)
    d = summ["paired_differences"]["B_DVA"]
    out["paired_B_DVA18_minus_B_DVA"] = d
    canary_alarm = json.loads((EVID / "h76_fit.json").read_text())["canary_alarm"]
    out["canary_alarm"] = canary_alarm
    out["promote_rule_met"] = bool(d["ci95"][0] > 0 and not canary_alarm)
    write("holdout", out)
    log(json.dumps({k: summ["scores"][k]["dti"] for k in arms}))
    log("paired B_DVA18 - B_DVA", json.dumps(d))


def main():
    check_prereg()
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st in ("fit", "all"):
        stage_fit()
    if st in ("holdout", "all"):
        stage_holdout()


if __name__ == "__main__":
    main()
