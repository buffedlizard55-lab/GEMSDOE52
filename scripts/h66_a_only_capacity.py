#!/usr/bin/env python3
"""H66 diagnostic: capacity and PURE measurement of the strict A-only stratum.

Two facts the pooled holdout number alone would hide:

1. The holdout's ``a_only`` arm is the top-K of the gated field with -1 outside the gate.
   ``nodes.spacing_select`` fills K from the -1 cells once the stratum's 3 px-thinned cells are
   exhausted, so most of that arm's dots are NOT in the strict stratum (measured per fold below).
2. The pure stratum -- the brief's literal discovery signal -- cannot fill the matched budget on
   any fold. Per the preregistered capacity note it is therefore reported at its ACHIEVED budget,
   not rescued to K.

This script measures both: the top-K arm's inside/outside split, and the pure stratum's emission
scored per fold and pooled with the same evaluator (gems52-pooled-hide-v1), alongside the
single_B control and a random control at the same achieved placement rule. The pure-stratum number
is a labelled diagnostic at an UNMATCHED budget; it is not eligible to beat the control.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                   # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402

import run_h61 as base                                               # noqa: E402
from gems52 import evaluate_holdout as evaluator                    # noqa: E402
from gems52 import nodes                                            # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h66"


def main() -> int:
    reg = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    ring_px = int(round(reg["catalogue_exclusion_m"] / 100.0))
    lo, hi = reg["receiver_rank_interval"]
    donor = float(reg["donor_rank_min"])
    K = int(reg["budget_dots_per_fold_per_arm"])
    min_px = float(reg["min_dot_separation_px"])
    _, store, cat, eligible, folds, va, vb, _ = base.setup()
    flat = store.flat_idx
    terms = {"a_only_pure": None, "single_B": None, "random": None}
    out = dict(stage="a_only_capacity", matched_budget_per_fold=K,
               evidence_class="HOLDOUT-DTI diagnostic at an UNMATCHED (achieved) budget; not a "
                              "matched-budget comparison and not a leaderboard score",
               folds=[])
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = {v: base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
             for v in ("A", "B")}
        allowed_idx = np.flatnonzero(allowed.ravel())
        r = {v: np.full(eligible.shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r[v].ravel()[allowed_idx] = base.pct_rank(g[v].ravel()[allowed_idx])
        gate = (r["A"] >= donor) & (r["B"] >= lo) & (r["B"] <= hi) & allowed
        # the holdout arm's field (finite everywhere) and the pure field (-inf outside the gate)
        field_topk = np.nan_to_num(np.where(gate, r["A"] - r["B"], -1.0), nan=-1.0)
        field_pure = np.where(gate, r["A"] - r["B"], -np.inf)
        em_topk = nodes.spacing_select(field_topk, allowed, K, min_px=min_px)
        em_pure = nodes.spacing_select(field_pure, allowed, K, min_px=min_px)
        n_topk, n_pure = int(em_topk.sum()), int(em_pure.sum())
        inside = int((em_topk & gate).sum())
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        em_b = nodes.spacing_select(np.nan_to_num(r["B"], nan=-1.0), allowed, K, min_px=min_px)
        em_r = nodes.spacing_select(rnd, allowed, K, min_px=min_px)
        row = dict(fold=f, allowed_px=int(allowed.sum()),
                   strict_a_only_cells=int(gate.sum()),
                   topk_arm=dict(placed=n_topk, requested=K, inside_stratum=inside,
                                 outside_stratum=n_topk - inside),
                   pure_stratum=dict(placed=n_pure, requested=K, filled=bool(n_pure == K)))
        for name, em in (("a_only_pure", em_pure), ("single_B", em_b), ("random", em_r)):
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[name] = term if terms[name] is None else terms[name] + term
            row[name] = dict(dti=result["dti"], tpw=result["tpw"], emitted=int(em.sum()))
        out["folds"].append(row)
        print(f"fold {f}: stratum {int(gate.sum())} cells | top-K arm placed {n_topk} "
              f"(inside {inside}, outside {n_topk - inside}) | pure placed {n_pure} "
              f"pure DTI {row['a_only_pure']['dti']:.6f} vs single_B {row['single_B']['dti']:.6f}",
              flush=True)
        del g, r, gate, field_topk, field_pure, em_topk, em_pure, em_b, em_r
    pooled = evaluator.pooled_summary(terms, draws=int(reg["bootstrap_draws"]), seed=SEED,
                                      candidate="a_only_pure")
    out["pooled_unmatched_budget"] = pooled
    out["interpretation"] = (
        "the pure strict A-only stratum (the brief's literal discovery signal) is placed at its "
        "achieved budget because it cannot fill the matched 9,400 dots per fold; its pooled "
        "HOLDOUT-DTI is a diagnostic at an unmatched budget, not a matched-budget comparison. "
        "The holdout's top-K a_only arm is additionally reported with its inside/outside split: "
        "most of its dots sit at field=-1 outside the stratum, so its pooled number is a mix, "
        "not the pure stratum.")
    (ROOT / "evidence/h66_a_only_capacity.json").write_text(
        json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    (ROOT / "docs/data/h66_a_only_capacity.json").write_text(
        json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
