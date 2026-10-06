#!/usr/bin/env python3
"""Which layout of the *same* 44 090 pixels is best, judged on the instrument that is anchored to the
live scoring distribution rather than to the catalogue?

Two instruments disagree about the incumbent's raster-order dotting versus surface-coverage greedy
packing.  This script tests a third rule that follows from the truth model itself: if the hidden
faults are scattered around the field surface with a 1.85 px scale (the group's own inference), then
the quantity to cover is not the surface but the *scattered truth density* -- i.e. the surface
smoothed by that scatter.  Emitting the greedy maximum-coverage packing of the smoothed surface is
the matched filter for the model's own credit.

Everything is scored with the official metric on paired draws, so the comparison is a paired
difference with a standard error, not a point estimate.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import emission as E, metric as M  # noqa: E402

DATA = Path("/tmp/gems52/data")


def load_mask(p: Path) -> np.ndarray:
    with rasterio.open(p) as s:
        return np.nan_to_num(s.read(1), nan=0.0) > 0


def mc_score(cands: dict[str, np.ndarray], surface: np.ndarray, footprint: np.ndarray,
             draws: int, truth_px: int, sigma: float, rng) -> dict:
    ys, xs = np.nonzero(surface)
    h, w = surface.shape
    res = {k: [] for k in cands}
    for _ in range(draws):
        pick = rng.choice(ys.size, min(truth_px, ys.size), replace=False)
        ty = ys[pick] + np.rint(rng.normal(0, sigma, pick.size)).astype(int)
        tx = xs[pick] + np.rint(rng.normal(0, sigma, pick.size)).astype(int)
        ok = (ty >= 0) & (ty < h) & (tx >= 0) & (tx < w)
        truth = np.zeros_like(surface)
        truth[ty[ok], tx[ok]] = True
        truth &= footprint
        for k, m in cands.items():
            c = M.components(m.astype(np.float32), truth)
            res[k].append(float(M.dti(c["TP_w"], c["FP_w"], c["FN_w"])))
    return res


def main() -> int:
    t0 = time.time()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=44_090)
    ap.add_argument("--draws", type=int, default=16)
    ap.add_argument("--truth-px", type=int, default=12_691)
    ap.add_argument("--sigma", type=float, default=1.85)
    ap.add_argument("--out", default="evidence/emission_models_mc.json")
    a = ap.parse_args()

    with rasterio.open(DATA / "h19_5.tif") as s:
        surface = np.nan_to_num(s.read(1), nan=0.0) > 0
    with rasterio.open(DATA / "sample_submission.tif") as s:
        footprint = np.isfinite(s.read(1))
    surface &= footprint

    # the model's own objective: the surface blurred by the truth scatter
    dens = ndimage.gaussian_filter(surface.astype(np.float32), a.sigma, mode="constant")
    near = ndimage.binary_dilation(surface, iterations=int(np.ceil(2 * a.sigma)))

    cands: dict[str, np.ndarray] = {}
    cands["incumbent_dot_thin_44090"] = load_mask(DATA / "incumbent_d28.tif") & footprint
    m1, _ = E.greedy_cover_fast((surface * 1.0).astype(np.float32), surface, a.budget, headroom=8)
    cands["greedy_surface_44090"] = m1 & footprint
    m2, tr2 = E.greedy_cover_fast(dens.astype(np.float32), near, a.budget, headroom=8)
    cands["greedy_smoothfield_44090"] = m2 & footprint
    ref = "incumbent_dot_thin_44090"

    rng = np.random.default_rng(20261005)
    res = mc_score(cands, surface, footprint, a.draws, a.truth_px, a.sigma, rng)
    summary = {}
    for k, v in res.items():
        arr = np.asarray(v)
        summary[k] = {"mean": float(arr.mean()), "sd": float(arr.std(ddof=1)),
                      "sem": float(arr.std(ddof=1) / np.sqrt(arr.size)), "px": int(cands[k].sum())}
    for k in cands:
        if k == ref:
            continue
        d = np.asarray(res[k]) - np.asarray(res[ref])
        summary[f"paired_{k}_minus_{ref}"] = {
            "mean": float(d.mean()), "sem": float(d.std(ddof=1) / np.sqrt(d.size)),
            "draws_positive": int((d > 0).sum()), "n_draws": int(d.size),
            "per_draw": [round(float(x), 6) for x in d]}
    best = max((k for k in cands if not k.startswith("incumbent")), key=lambda k: summary[k]["mean"])
    out = {"question": "which layout of the same mass is best under the live-anchored truth model?",
           "budget_px": a.budget, "draws": a.draws,
           "truth_model": {"truth_px": a.truth_px, "sigma_px": a.sigma,
                           "source": "GEMSDOE25 H28 (owner-report-derived prior)"},
           "reference": ref, "summary": summary, "best_arm": best,
           "verdict": (f"{best} has the highest mean official DTI on paired draws from the truth "
                       f"model ({summary[best]['mean']:.4f} vs incumbent "
                       f"{summary[ref]['mean']:.4f}); paired difference "
                       f"{summary[f'paired_{best}_minus_{ref}']['mean']:+.4f} ± "
                       f"{summary[f'paired_{best}_minus_{ref}']['sem']:.4f} with "
                       f"{summary[f'paired_{best}_minus_{ref}']['draws_positive']}/"
                       f"{summary[f'paired_{best}_minus_{ref}']['n_draws']} draws positive."),
           "seconds": round(time.time() - t0, 1),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ROOT / a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_draw" or True}, indent=1)[:2000])
    print("verdict:", out["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
