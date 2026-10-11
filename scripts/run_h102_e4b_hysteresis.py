#!/usr/bin/env python3
"""H102 E4b -- second geometry for the same question: hysteresis traces instead of naive bridging.

E4a (``run_h102_e4_coverage.py``) showed that *bridging every nearby pair* of dots along a weak field is
worse than spending the same mass on more dots, on both fields tested.  That is a negative for the
bridging operator, not necessarily for the coverage thesis: bridging fills the segment between two cells
regardless of what the field does in between, so on a field whose ranking is poor it concentrates mass
where the field is *confident*, which is exactly where it is wrong.

E4b tests the classical alternative: **hysteresis** (geodesic growth under a rank floor) --
    seeds  := field rank >= q_seed
    grow   := repeat  dilate(mask) & (field rank >= q_grow)
This produces connected traces down the ridge, stops where the evidence dies, and cannot leave the
high-rank region.  Compared, at the same emitted mass, against
    dots@S   the family convention at that mass, and
    random@S the floor at that mass.

Same shared instrument, same folds, same evaluator, same frozen field.  Diagnostic only.

Usage: python scripts/run_h102_e4b_hysteresis.py
"""
from __future__ import annotations

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
from scipy import ndimage as ndi                                      # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h102 as h102                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import nodes                                              # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h102"
EVID = ROOT / "evidence"
Q_SEED = float(os.environ.get("H102E4B_Q_SEED", 0.98))
Q_GROW = float(os.environ.get("H102E4B_Q_GROW", 0.85))
MAX_STEPS = int(os.environ.get("H102E4B_MAX_STEPS", 12))
FIELDS = ("single_B2", "cotrain_disagree")


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def hysteresis(field: np.ndarray, allowed: np.ndarray, q_seed: float, q_grow: float, max_steps: int):
    """Geodesic growth of the top-rank seeds under a rank floor; returns the mask and its receipt."""
    vals = field[allowed]
    thr_seed, thr_grow = float(np.quantile(vals, q_seed)), float(np.quantile(vals, q_grow))
    mask = allowed & (field >= thr_seed)
    n_seed = int(mask.sum())
    steps, growable = 0, allowed & (field >= thr_grow)
    for _ in range(max_steps):
        grown = ndi.binary_dilation(mask, structure=np.ones((3, 3), bool)) & growable
        if not (grown & ~mask).any():
            break
        mask = grown
        steps += 1
    return mask, dict(q_seed=q_seed, q_grow=q_grow, seed_threshold=thr_seed, grow_threshold=thr_grow,
                      seeds=int(n_seed), cells=int(mask.sum()), growth_steps=steps,
                      components=int(ndi.label(mask, structure=np.ones((3, 3), bool))[1]) if mask.any() else 0)


def main() -> int:
    t0 = time.time()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    arms = ("dots@K", "hyst@S", "dots@S", "random@S")
    terms = {(fld, a): None for fld in FIELDS for a in arms}
    out = dict(stage="e4b_hysteresis", started_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               evaluator=evaluator.VERSION, q_seed=Q_SEED, q_grow=Q_GROW, max_steps=MAX_STEPS,
               implementation_hashes=evaluator.implementation_hashes(),
               question=("at the same emitted mass, does a hysteresis (geodesic-growth) trace beat the same "
                         "mass spent on more dots, where naive pairwise bridging did not?"),
               falsifier="hyst@S DTI <= dots@S DTI at the same mass",
               folds=[])
    for fold in folds:
        f = fold["fold"]
        allowed = h102.allowed_of(fold, ring_px)
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A2_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B2_f{f}.npy"), eligible.shape)
        ra, rb = h102.rank_in(pa, allowed), h102.rank_in(pb, allowed)
        rec = dict(fold=f, allowed_px=int(allowed.sum()), fields={})
        for fld in FIELDS:
            if fld == "cotrain_disagree":
                field = np.where(allowed, np.nan_to_num(h102.arm_field(h102.PRIMARY, ra, rb, eligible.shape), nan=-1.0),
                                 -1.0).astype(np.float32)
                field[allowed] = ra[allowed] - rb[allowed] + 1.0        # keep it non-negative on the allowed set
            else:
                field = np.where(allowed, np.nan_to_num(rb, nan=-1.0), -1.0).astype(np.float32)
            dots = nodes.spacing_select(field, allowed, h102.K_FOLD, min_px=3.0)
            hyst, hrec = hysteresis(field, allowed, Q_SEED, Q_GROW, MAX_STEPS)
            s_hyst = int(hyst.sum())
            dots_s = nodes.spacing_select(field, allowed, s_hyst, min_px=3.0)
            ai = np.flatnonzero(allowed.ravel())
            rnd = np.zeros(eligible.shape, bool)
            pick = np.random.default_rng(SEED + 1100 + f).choice(ai, size=min(s_hyst, ai.size), replace=False)
            rnd.ravel()[pick] = True
            rec["fields"][fld] = dict(hysteresis=hrec, arms={})
            for arm, em in (("dots@K", dots), ("hyst@S", hyst), ("dots@S", dots_s), ("random@S", rnd)):
                res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
                key = (fld, arm)
                terms[key] = term if terms[key] is None else terms[key] + term
                rec["fields"][fld]["arms"][arm] = dict(res, placed=int(em.sum()))
                log(f"fold {f} {fld} {arm}: DTI {res['dti']:.6f} mass {int(em.sum())}")
            del field, dots, hyst, dots_s, rnd
        del pa, pb, ra, rb
        out["folds"].append(rec)
    out["pooled"] = {fld: evaluator.pooled_summary({a: terms[(fld, a)] for a in arms}, draws=1000,
                                                   seed=SEED, candidate="hyst@S") for fld in FIELDS}
    out["geometry_vs_mass"] = {}
    for fld in FIELDS:
        pd = out["pooled"][fld]["paired_differences"]
        g = dict(hyst_dti=float(out["pooled"][fld]["scores"]["hyst@S"]["dti"]),
                 dots_K_dti=float(out["pooled"][fld]["scores"]["dots@K"]["dti"]),
                 dots_matched_mass_dti=float(out["pooled"][fld]["scores"]["dots@S"]["dti"]),
                 random_same_mass_dti=float(out["pooled"][fld]["scores"]["random@S"]["dti"]),
                 delta_vs_dots_matched=float(pd["dots@S"]["delta"]),
                 ci95_vs_dots_matched=[float(x) for x in pd["dots@S"]["ci95"]],
                 delta_vs_random=float(pd["random@S"]["delta"]),
                 ci95_vs_random=[float(x) for x in pd["random@S"]["ci95"]],
                 hyst_mass=int(sum(r["fields"][fld]["arms"]["hyst@S"]["placed"] for r in out["folds"])))
        g["HYSTERESIS_BEATS_MATCHED_MASS"] = bool(g["delta_vs_dots_matched"] > 0 and g["ci95_vs_dots_matched"][0] > 0)
        g["verdict"] = ("hysteresis helps at matched mass" if g["HYSTERESIS_BEATS_MATCHED_MASS"]
                        else "no measured hysteresis gain at matched mass (negative)")
        out["geometry_vs_mass"][fld] = g
    out["seconds"] = round(time.time() - t0, 1)
    (EVID / "h102_e4b_hysteresis.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    for fld in FIELDS:
        log(fld + ": " + json.dumps({a: round(out["pooled"][fld]["scores"][a]["dti"], 6) for a in arms}))
        log(fld + ": " + json.dumps(out["geometry_vs_mass"][fld], default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
