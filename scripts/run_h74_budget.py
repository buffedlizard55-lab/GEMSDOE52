#!/usr/bin/env python3
"""H74-E3a: budget sweep of the one field that survives E2, on the SHARED holdout.

The board algebra (measured on organiser-scored bytes, evidence/h74_board_forensics.json) says
DTI = T/(0.2*S + 0.8*|G|) with |G| pinned at 14,088.7, so the emission budget is a real decision
variable, not a tradition.  This measures where the shared instrument's DTI peaks for the
single_B ranking, so the shipped budget is chosen by a measurement rather than copied from the
family's 37,654.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import run_h61 as base                                              # noqa: E402
from gems52 import nodes, evaluate_holdout as evaluator              # noqa: E402

EVID = ROOT / "evidence"; SEED = 520810; MIN_PX = 3.0
BUDGETS = (4000, 8000, 9400, 12000, 16000, 20000, 25517, 37654)


def log(*a): print(*a, flush=True)


def main() -> int:
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx; shape = eligible.shape; npix = int(eligible.size)
    out = dict(stage="budget_sweep", min_separation_px=MIN_PX, budgets=list(BUDGETS),
               field="single_B (H61/H71 View-B surface model, out-of-fold)", folds=[])
    terms = {b: None for b in BUDGETS}
    for fold in folds:
        f = fold["fold"]
        vd = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vd > ring_px)
        del vd
        ai = np.flatnonzero(allowed.ravel())
        preB = np.zeros(npix, np.float32); preB[flat] = np.load(
            ROOT / "work/h61" / f"pred_pre_B_f{f}.npy").astype(np.float32)
        x = preB.ravel()[ai]
        rB = np.zeros(npix, np.float32)
        rB[ai] = (rankdata(x) / float(len(x))).astype(np.float32)
        del preB, x
        rec = dict(fold=f, allowed_px=int(allowed.sum()), budgets={})
        for k in BUDGETS:
            em = nodes.spacing_select(rB.reshape(shape), allowed, int(k), min_px=MIN_PX)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[k] = term if terms[k] is None else terms[k] + term
            rec["budgets"][str(k)] = dict(dti=res["dti"], emitted=res["emitted"])
            log(f"  fold {f} K={k:6d} emitted {res['emitted']:6d} DTI {res['dti']:.6f}")
            del em
        del rB, ai; out["folds"].append(rec)
    summ = evaluator.pooled_summary({str(b): t for b, t in terms.items()}, draws=1000,
                                    seed=SEED, candidate=str(BUDGETS[0]))
    out["pooled"] = json.loads(json.dumps(summ, default=str))
    log("\n=== POOLED HOLDOUT-DTI by budget (evaluator %s) ===" % evaluator.VERSION)
    for k, row in sorted(summ["scores"].items(), key=lambda kv: -kv[1]["dti"]):
        log(f"  K={int(k):6d}  DTI {row['dti']:.6f}  95% CI [{row['ci95'][0]:.6f}, {row['ci95'][1]:.6f}]")
    best = max(summ["scores"].items(), key=lambda kv: kv[1]["dti"])[0]
    log(f"\n  best pooled budget: K={int(best)}")
    out["best_budget"] = int(best)
    (EVID / "h74_budget_sweep.json").write_text(json.dumps(out, indent=1, default=str))
    log(f"wrote {EVID/'h74_budget_sweep.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
