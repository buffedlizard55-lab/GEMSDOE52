#!/usr/bin/env python3
"""R5 stage 2 -- ask the organiser's own scores whether corroborated traces carry more credit.

Thirteen rasters this family shipped were scored on the public leaderboard and are restored here
with pinned SHA-256.  Their credit is an exact linear function of any disjoint stratification of the
footprint, so the credit density of "pixels the R5 detector marks as a multi-family trace" is
*solvable* from those scores rather than hoped for.

Designs compared, all leave-one-file-out on the reported DTI:

  size      one stratum per file-size decile            (the leaderboard curve-fit control)
  cons      ring + prior-consensus count (1, 2, 3+)     (knowledge/10 §3's corroboration)
  trace     ring + R5 detector corroboration (0,1,2,3+) (this round's hypothesis)
  cons_x_trace  ring + consensus x detector corroboration (both, crossed)
  dist      ring + distance band x detector corroboration

If ``trace`` does not beat ``cons`` out of sample, the detector adds nothing to what the family
already knew, and the emission must not claim otherwise.

Usage:  python scripts/run_r5_revealed.py [--tau 0.99]
Writes: evidence/r5_revealed_inversion.json (+ a printed summary; the receipt is the record).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52_r5 import revealed_r5 as R          # noqa: E402
from gems52_r5 import traces as T               # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"


def consensus_count(supp: dict[str, np.ndarray]) -> np.ndarray:
    """How many of the thirteen scored rasters emitted each pixel (evaluated support)."""
    cnt = np.zeros(next(iter(supp.values())).shape, np.int8)
    for m in supp.values():
        cnt += m.astype(np.int8)
    return cnt


def designs(data_dir: Path, supp, corr: np.ndarray, cat: np.ndarray, valid: np.ndarray):
    edt = ndimage.distance_transform_edt(~cat, sampling=100.0)
    ring = edt <= 200.0
    off = ~ring
    cons = consensus_count(supp)
    cb = np.clip(corr, 0, 3)                    # 0, 1, 2, 3+ detector families
    nb = np.clip(cons, 0, 3)                    # 0, 1, 2, 3+ prior rasters
    out = {}
    out["size_only"] = [("all_evaluated", off)]
    out["trace"] = [("ring_le200m", ring)] + \
        [(f"traceC{c}", off & (cb == c)) for c in (0, 1, 2, 3)]
    out["cons"] = [("ring_le200m", ring)] + \
        [(f"cons{n}", off & (nb == n) & (cons > 0)) for n in (1, 2, 3)] + \
        [("never_emitted", off & (cons == 0))]
    out["cons_x_trace"] = [("ring_le200m", ring)] + \
        [(f"cons{n}_C{c}", off & (nb == n) & (cb == c)) for n in (1, 2, 3) for c in (0, 1, 2, 3)]
    db = np.digitize(edt, [200.0, 500.0, 1000.0, 2000.0])
    out["dist"] = [("ring_le200m", ring)] + \
        [(f"d{d}_C{c}", (db == d) & (cb == c)) for d in (1, 2, 3, 4) for c in (0, 2)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tau", type=float, default=0.99)
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(m, flush=True)          # noqa: E731
    data_dir = Path(args.data_dir)
    supp = R.load_supports(data_dir)
    cat = rasterio.open(data_dir / "labels.tif").read(1) == 1
    valid = np.load(WORK / "valid.npy")
    corr = np.load(WORK / f"corrobor_{args.tau:g}.npy")
    log(f"[inputs] {len(supp)} scored rasters, footprint {int(valid.sum())} px, "
        f"detector corroboration at tau={args.tau:g}")

    ident = R.nested_pair_identity(supp)
    ring_geo = R.ring_check(data_dir, supp)
    log(f"[identity] A\\B={ident['a_minus_b_px']} px, B\\A={ident['b_minus_a_px']} px, "
        f"|G| solved from the nested pair = {ident['G_solved_from_identity']:.1f} px "
        f"(assumed {R.G_PX})")
    log(f"[ring] B\\A max distance to catalogue {ring_geo['b_minus_a_max_dist_m']:.0f} m, "
        f"A min distance {ring_geo['a_min_dist_to_catalogue_m']:.1f} m")

    ds = designs(data_dir, supp, corr, cat, valid)
    receipt = dict(tau=args.tau, g_px=R.G_PX, seconds=None,
                   nested_identity=ident, ring_geometry=ring_geo,
                   detector_corroboration_px_by_count=[int(x) for x in np.bincount(
                       np.clip(corr[valid], 0, 6), minlength=7)],
                   designs={})
    for name, strata in ds.items():
        fixed = tuple(i for i, (n, _) in enumerate(strata) if n == "ring_le200m")
        mono = None
        if name == "trace":
            mono = 1                                 # densities nondecreasing in corroboration
        rep = R.report(data_dir, strata_fn=lambda d, s, strata=strata: strata,
                       fixed_zero=fixed, monotone_from=mono)
        rep.pop("nested_identity", None)
        rep.pop("ring_geometry", None)
        receipt["designs"][name] = rep
        log(f"\n[design {name}] {len(strata)} strata, in-sample RMSE(T)={rep['in_sample_rmse_T']:.1f}, "
            f"LOO mean|dDTI|={rep['loo']['mean_abs_dti_err']:.4f} "
            f"max={rep['loo']['max_abs_dti_err']:.4f} "
            f"mean rel={rep['loo']['mean_rel_err']:.3f}")
        for s, n, rho in zip(rep["strata"], rep["strata_px"], rep["rho"]):
            log(f"    {s:22s} px={n:9d} rho={rho:.4f} ({100 * rho:.2f}%)")
    receipt["seconds"] = time.time() - t0
    receipt["random_baseline_density"] = dict(
        note="uniform-random mass over the permitted (off-ring, in-footprint) set",
        px=int((valid & (ndimage.distance_transform_edt(~cat, sampling=100.0) > 200)).sum()))
    R.save(EVID / "r5_revealed_inversion.json", receipt)
    R.save(ROOT / "docs" / "data" / "r5_revealed_inversion.json", receipt)
    log(f"\n[receipt] evidence/r5_revealed_inversion.json  ({receipt['seconds']:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
