#!/usr/bin/env python3
"""H97 E4 (diagnostic) -- is the score bought by the RANKING or by the EMISSION GEOMETRY?

knowledge/98 shows, with the repository's own metric, that the organiser's DTI is a *coverage*
metric: a swath covering a fault trace scores 0.88 where a sparse sampling of the same trace scores
far less, and the marginal rule admits any cell within ~283 m of an uncovered truth pixel. Every
round in this family, including H97's own artifact, emits dots at 3 px minimum spacing -- a *sampled*
trace. E4 asks the question the family has never asked, on the shared hide-and-recover instrument:

    at the SAME emitted mass, does connecting neighbouring confident cells along the field
    ("bridging") recover more weighted truth than spending the same mass on more dots?

Arms, per fold, all on the identical primary field and the identical allowed set:
    dots@K          the H97 convention: spacing_select(field, K=9400, min_px=3)
    dots@S_bridge   mass-matched control: spacing_select(field, S_bridge, min_px=3)
    bridged         dots@K plus every cell on a segment between two dots closer than R_bridge px,
                    kept only where the cell is inside the allowed set and its field rank clears a
                    pre-set floor
    random@S        floor at the same mass

If `bridged` beats `dots@S_bridge`, the family has been losing score to its emission geometry, which is
the cheapest unspent lever in the project (knowledge/98 sec.6). If it does not, the lever is dead and
that is a deliverable too.

This is a DIAGNOSTIC. It does not re-tune H97's frozen arm, budget or promotion rule.

Usage: python scripts/run_h97_e4_coverage.py
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
from scipy.spatial import cKDTree                                      # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h97 as h97                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import nodes                                              # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h97"
EVID = ROOT / "evidence"
K_FOLD = int(os.environ.get("H97E4_K_FOLD", 9400))
R_BRIDGE_PX = float(os.environ.get("H97E4_R_BRIDGE", 12.0))     # 1 200 m maximum gap to bridge
Q_FLOOR = float(os.environ.get("H97E4_Q_FLOOR", 0.60))          # field-rank floor for a bridged cell


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bridge(dots: np.ndarray, field: np.ndarray, allowed: np.ndarray, q_floor: float,
           r_px: float, step: float = 1.5) -> tuple[np.ndarray, dict]:
    """Add cells along the segment between dot pairs closer than r_px where the field rank clears q_floor."""
    idx = np.argwhere(dots)
    if len(idx) < 2:
        return dots.copy(), dict(pairs=0, added=0)
    tree = cKDTree(idx)
    pairs = np.asarray(sorted(tree.query_pairs(r_px)), dtype=np.int64)
    vals = field[allowed]
    thr = float(np.quantile(vals, q_floor))
    out = dots.copy()
    added = 0
    h, w = dots.shape
    for i, j in pairs:
        a, b = idx[i].astype(np.float64), idx[j].astype(np.float64)
        n = max(int(np.hypot(*(b - a)) / step), 1)
        t = np.linspace(0.0, 1.0, n + 2)[1:-1]
        ys = np.rint(a[0] + t * (b[0] - a[0])).astype(np.int64)
        xs = np.rint(a[1] + t * (b[1] - a[1])).astype(np.int64)
        okc = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
        ys, xs = ys[okc], xs[okc]
        if ys.size == 0:
            continue
        good = allowed[ys, xs] & (field[ys, xs] >= thr) & ~out[ys, xs]
        if good.any():
            out[ys[good], xs[good]] = True
            added += int(good.sum())
    return out, dict(pairs=int(len(pairs)), added=added, field_rank_floor=thr, q_floor=q_floor,
                     max_gap_px=r_px, step_px=step)


FIELDS = ("cotrain_disagree", "single_B2")


def main() -> int:
    t0 = time.time()
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    arms = ("dots@K", "dots@S_bridge", "bridged", "random@S")
    terms = {(fld, a): None for fld in FIELDS for a in arms}
    out = dict(stage="e4_coverage", started_utc=now(), evaluator=evaluator.VERSION, budget_per_fold=K_FOLD,
               r_bridge_px=R_BRIDGE_PX, q_floor=Q_FLOOR, seed=SEED, fields=list(FIELDS),
               implementation_hashes=evaluator.implementation_hashes(),
               question=("at the same emitted mass, does bridging neighbouring confident cells along the field "
                         "recover more weighted truth than the same mass spent on more dots?"),
               falsifier="bridged DTI <= dots@S_bridge DTI, i.e. the geometry adds nothing at matched mass",
               note=("run on two fields: the H97 primary disagreement field and the surface-anisotropy field "
                     "single_B2, because the geometry question is best posed on the strongest available field"),
               folds=[])
    for fold in folds:
        f = fold["fold"]
        allowed = h97.allowed_of(fold, ring_px)
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A2_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B2_f{f}.npy"), eligible.shape)
        ra, rb = h97.rank_in(pa, allowed), h97.rank_in(pb, allowed)
        rec = dict(fold=f, allowed_px=int(allowed.sum()), arms={})
        for fld in FIELDS:
            if fld == "cotrain_disagree":
                field = np.where(allowed, np.nan_to_num(h97.arm_field(h97.PRIMARY, ra, rb, eligible.shape), nan=-1.0),
                                 -1.0).astype(np.float32)
            else:
                field = np.where(allowed, np.nan_to_num(rb, nan=-1.0), -1.0).astype(np.float32)
            dots = nodes.spacing_select(field, allowed, K_FOLD, min_px=3.0)
            bridged, brec = bridge(dots, field, allowed, Q_FLOOR, R_BRIDGE_PX)
            s_bridge = int(bridged.sum())
            dots_matched = nodes.spacing_select(field, allowed, s_bridge, min_px=3.0)
            ai = np.flatnonzero(allowed.ravel())
            rnd = np.zeros(eligible.shape, bool)
            pick = np.random.default_rng(SEED + 900 + f).choice(ai, size=min(s_bridge, ai.size), replace=False)
            rnd.ravel()[pick] = True
            rec["arms"][fld] = {"bridge": brec, "arms": {}}
            for arm, em in (("dots@K", dots), ("dots@S_bridge", dots_matched), ("bridged", bridged), ("random@S", rnd)):
                res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
                key = (fld, arm)
                terms[key] = term if terms[key] is None else terms[key] + term
                rec["arms"][fld]["arms"][arm] = dict(res, placed=int(em.sum()))
                log(f"fold {f} {fld} {arm}: DTI {res['dti']:.6f} mass {int(em.sum())}")
            del field, dots, bridged, dots_matched, rnd
        del pa, pb, ra, rb
        out["folds"].append(rec)
    out["pooled"] = {fld: evaluator.pooled_summary({a: terms[(fld, a)] for a in arms}, draws=1000,
                                                   seed=SEED, candidate="bridged") for fld in FIELDS}
    out["geometry_vs_mass"] = {}
    for fld in FIELDS:
        pd = out["pooled"][fld]["paired_differences"]
        g = dict(
            bridged_dti=float(out["pooled"][fld]["scores"]["bridged"]["dti"]),
            dots_matched_mass_dti=float(out["pooled"][fld]["scores"]["dots@S_bridge"]["dti"]),
            delta_matched_mass=float(pd["dots@S_bridge"]["delta"]),
            ci95_matched_mass=[float(x) for x in pd["dots@S_bridge"]["ci95"]],
            bridged_mass=int(sum(r["arms"][fld]["arms"]["bridged"]["placed"] for r in out["folds"])),
            dots_K_mass=int(sum(r["arms"][fld]["arms"]["dots@K"]["placed"] for r in out["folds"])),
            random_same_mass_dti=float(out["pooled"][fld]["scores"]["random@S"]["dti"]),
            bridged_vs_random_delta=float(pd["random@S"]["delta"]),
            ci95_bridged_vs_random=[float(x) for x in pd["random@S"]["ci95"]])
        g["GEOMETRY_BEATS_MASS_AT_MATCHED_MASS"] = bool(g["delta_matched_mass"] > 0 and g["ci95_matched_mass"][0] > 0)
        g["verdict"] = ("geometry helps at matched mass" if g["GEOMETRY_BEATS_MASS_AT_MATCHED_MASS"]
                        else "no measured geometry gain at matched mass (negative)")
        out["geometry_vs_mass"][fld] = g
    out["seconds"] = round(time.time() - t0, 1)
    (EVID / "h97_e4_coverage.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    for fld in FIELDS:
        log(fld + ": " + json.dumps({a: round(out["pooled"][fld]["scores"][a]["dti"], 6) for a in arms}))
        log(fld + ": " + json.dumps(out["geometry_vs_mass"][fld], default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
