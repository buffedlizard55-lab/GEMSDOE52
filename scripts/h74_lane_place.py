#!/usr/bin/env python3
"""H74 experiment 2 (amendment 63a): run_h73.place_lane on the B_DVA field; full domain then per-fold holdout."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
from scipy import ndimage as ndi
import run_h73 as h73, run_h74 as h74, run_h61 as base
from gems52 import evaluate_holdout as evaluator, nodes
h73.H73 = json.loads((ROOT / "registry/h73_preregistration.json").read_text())
stage = sys.argv[1] if len(sys.argv) > 1 else "full"
reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
sups = h73.informative_supports(eligible, None)
h74.log(f"informative supports {len(sups)}")
if stage == "full":
    surf = np.load(ROOT / "work/h74/surface.npy")
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & (catd * 100.0 > 200.0)
    dots, rec = h73.place_lane(np.where(pool, surf, -1.0).astype(np.float32), pool, h74.K_TOTAL, sups,
                               eligible.shape, limit=0.70, rounds=8)
    np.save(ROOT / f"work/h74/dots_lane_{h74.K_TOTAL}.npy", dots)
    (ROOT / f"evidence/h74_lane_place_{h74.K_TOTAL}.json").write_text(json.dumps(rec, indent=1, default=float))
    print(json.dumps({k: rec[k] for k in ("ok", "worst", "quota_priors", "spacing_ok")}), int(dots.sum()))
else:   # per-fold holdout of the lane-placed arm vs single_B, same evaluator
    K = h74.K_FOLD
    arms = ("single_B", "B_DVA", "B_DVA_lane")
    terms = {a: None for a in arms}; rows = []
    for fold in folds:
        f = fold["fold"]; allowed = h74.allowed_of(fold, ring_px); ai = np.flatnonzero(allowed.ravel())
        for arm in arms:
            src = "B_DVA" if arm == "B_DVA_lane" else arm
            g = base.to_grid(store.flat_idx, np.load(ROOT / f"work/h74/pred_{src}_f{f}.npy"), eligible.shape)
            fld = np.full(eligible.shape, -1.0, np.float32)
            fld.ravel()[ai] = np.nan_to_num(base.pct_rank(g.ravel()[ai]), nan=-1.0)
            if arm == "B_DVA_lane":
                em, rc = h73.place_lane(fld, allowed, K, sups, eligible.shape, limit=0.70, rounds=8)
            else:
                em, rc = nodes.spacing_select(fld, allowed, K, min_px=3.0), {}
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rows.append(dict(fold=f, arm=arm, dti=res["dti"], placed=int(em.sum()), lane_ok=rc.get("ok"), worst=rc.get("worst")))
            h74.log(rows[-1])
    pooled = evaluator.pooled_summary(terms, draws=1000, seed=base.SEED, candidate="B_DVA_lane")
    (ROOT / f"evidence/h74_lane_holdout_{h74.K_FOLD}.json").write_text(json.dumps(dict(folds=rows, pooled=pooled), indent=1, default=float))
    print(json.dumps({a: pooled["scores"][a]["dti"] for a in arms}), json.dumps(pooled["paired_differences"], default=float)[:600])
