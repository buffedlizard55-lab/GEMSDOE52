#!/usr/bin/env python3
"""H97 post-hoc diagnostic (experiment 2 of 3).  NOT preregistered, NOT promotable, NOT a slot candidate.

Purpose: explain the negative H97 holdout (graft_primary 0.047183 vs B_DVA2_HVA 0.190147) by decomposing the graft into
its terms on the same folds, same budget, same instrument (gems52-pooled-hide-v1).  Labelled post-hoc in the receipt.

Arms:
  B_DVA2_HVA      control (must reproduce 0.190147)
  graft_primary   the preregistered formula (must reproduce the H97 holdout receipt)
  graft_no_veto   (0.45*a*b + 0.55*a*clip(a-b,0,1))            -- the veto removed
  veto_only       b*(1 - 0.70*veto)                              -- the A-prior and buried term removed
Plus a top-K overlap measure between the graft's and B's placed dots on each fold.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

import run_h61 as base  # noqa: E402
import run_h84 as h84  # noqa: E402
import run_h97 as h97  # noqa: E402
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import nodes  # noqa: E402

ARMS = ("B_DVA2_HVA", "graft_primary", "graft_no_veto", "veto_only")
PRIMARY = "graft_primary"


def main():
    h97.check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    h97.require_h84_arms(folds)
    terms = {a: None for a in ARMS}
    per_fold = []
    for fold in folds:
        f = fold["fold"]
        allowed = h84.allowed_of(fold, ring_px)
        ai = np.flatnonzero(allowed.ravel())
        gA = base.to_grid(store.flat_idx, np.load(h84.WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        gB = base.to_grid(store.flat_idx, np.load(h84.WORK / f"pred_B_DVA2_HVA_f{f}.npy"), eligible.shape)
        a_full = np.zeros(eligible.shape, np.float32)
        b_full = np.zeros(eligible.shape, np.float32)
        a_full.ravel()[ai] = np.nan_to_num(base.pct_rank(gA.ravel()[ai]), nan=0.0)
        b_full.ravel()[ai] = np.nan_to_num(base.pct_rank(gB.ravel()[ai]), nan=0.0)
        m = allowed.astype(bool)
        a, b = a_full, b_full
        veto = h97.rank01(np.clip(b - a, 0.0, 1.0), m)
        buried = a * np.clip(a - b, 0.0, 1.0)
        fields = {
            "B_DVA2_HVA": np.where(m, b, -1.0).astype(np.float32),
            "graft_primary": h97.graft(a, b, m),
            "graft_no_veto": np.where(m, h97.W_CONS * a * b + h97.W_BURIED * buried, -1.0).astype(np.float32),
            "veto_only": np.where(m, b * (1.0 - h97.W_VETO * veto), -1.0).astype(np.float32),
        }
        rec = dict(fold=f, arms={})
        dots = {}
        for arm in ARMS:
            em = nodes.spacing_select(fields[arm], allowed, h97.K_FOLD, min_px=3.0)
            dots[arm] = em
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(res, placed=int(em.sum()))
            print(f"fold {f} {arm}: DTI {res['dti']:.6f}", flush=True)
        # overlap: graft vs B on the same fold budget
        dg, db = dots[PRIMARY], dots["B_DVA2_HVA"]
        near = ndi.binary_dilation(db, structure=np.ones((7, 7), bool))
        rec["overlap"] = dict(graft_dots=int(dg.sum()), B_dots=int(db.sum()),
                              shared_exact=int((dg & db).sum()),
                              graft_dots_within_3px_of_B=int((dg & near).sum()),
                              graft_dots_with_a_gt_b=int((dg & (a > b)).sum()),
                              graft_dots_with_veto_gt_0_5=int((dg & (veto > 0.5)).sum()))
        per_fold.append(rec)
        del gA, gB, a_full, b_full, fields, dots
    pooled = evaluator.pooled_summary(terms, draws=1000, seed=h97.SEED, candidate=PRIMARY)
    out = dict(stage="h97_posthoc_diagnostic", post_hoc=True, not_preregistered=True, not_promotable=True,
               submission_slot=0, note=("Explains the H97 negative. Arms veto_only and graft_no_veto were not in the "
                                        "preregistration; they are reported as diagnostics only."),
               evaluator=evaluator.VERSION, folds=per_fold,
               pooled={a: dict(dti=float(pooled["scores"][a]["dti"]), ci95=pooled["scores"][a]["ci95"])
                       for a in ARMS},
               paired={k: dict(delta=float(v["delta"]), ci95=[float(x) for x in v["ci95"]])
                       for k, v in pooled["paired_differences"].items()})
    h97.write("posthoc_diagnostic", out)
    print(json.dumps(out["pooled"], indent=1))


if __name__ == "__main__":
    main()
