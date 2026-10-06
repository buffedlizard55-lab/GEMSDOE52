#!/usr/bin/env python3
"""Final paired check of the shipped bytes against the incumbent layout, on the catalogue-aware
truth model, with the official metric.

Model: the hidden round-1 set excludes mapped faults, so truth is drawn from the field surface
*away* from the given catalogue, scattered with the group's inferred 1.85 px scale and sized at
their inferred 12,691 px.  Candidates: the shipped file (read from disk), the incumbent file
(pinned sha256), and the surface-coverage greedy of the same mass.
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
from gems52 import emission as E, metric as M  # noqa: E402

DATA = Path("/tmp/gems52/data")


def load_mask(p: Path) -> np.ndarray:
    with rasterio.open(p) as s:
        return np.nan_to_num(s.read(1), nan=0.0) > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shipped", default="docs/downloads/gems52-h19-5-smoothmaxcov-44090.tif")
    ap.add_argument("--draws", type=int, default=12)
    ap.add_argument("--truth-px", type=int, default=12_691)
    ap.add_argument("--sigma", type=float, default=1.85)
    ap.add_argument("--out", default="evidence/shipped_vs_incumbent_mc.json")
    a = ap.parse_args()

    t0 = time.time()
    with rasterio.open(DATA / "h19_5.tif") as s:
        surface = np.nan_to_num(s.read(1), nan=0.0) > 0
    with rasterio.open(DATA / "sample_submission.tif") as s:
        footprint = np.isfinite(s.read(1))
    labels = load_mask(DATA / "labels.tif")
    surface &= footprint
    pool = surface & ~ndimage.binary_dilation(labels, iterations=1)

    shipped = load_mask(ROOT / a.shipped) & footprint
    inc = load_mask(DATA / "incumbent_d28.tif") & footprint
    surf_greedy, _ = E.greedy_cover_fast(surface.astype(np.float32), surface & ~labels,
                                         int(shipped.sum()), headroom=8)
    cands = {"shipped": shipped, "incumbent": inc, "surface_greedy": surf_greedy & footprint}

    ys, xs = np.nonzero(pool)
    h, w = surface.shape
    rng = np.random.default_rng(20261006)
    scores = {k: [] for k in cands}
    tp = {k: [] for k in cands}
    for d in range(a.draws):
        pick = rng.choice(ys.size, min(a.truth_px, ys.size), replace=False)
        ty = ys[pick] + np.rint(rng.normal(0, a.sigma, pick.size)).astype(int)
        tx = xs[pick] + np.rint(rng.normal(0, a.sigma, pick.size)).astype(int)
        ok = (ty >= 0) & (ty < h) & (tx >= 0) & (tx < w)
        truth = np.zeros_like(surface)
        truth[ty[ok], tx[ok]] = True
        truth &= footprint & ~ndimage.binary_dilation(labels, iterations=1)
        for k, m in cands.items():
            c = M.components(m.astype(np.float32), truth)
            scores[k].append(float(M.dti(c["TP_w"], c["FP_w"], c["FN_w"])))
            tp[k].append(float(c["TP_w"]))
        print(f"  draw {d+1}/{a.draws}", flush=True)

    summary = {}
    for k, v in scores.items():
        arr = np.asarray(v)
        summary[k] = {"mean": float(arr.mean()), "sem": float(arr.std(ddof=1) / np.sqrt(arr.size)),
                      "px": int(cands[k].sum()), "mean_TP_w": float(np.mean(tp[k]))}
    for k in ("shipped", "surface_greedy"):
        d = np.asarray(scores[k]) - np.asarray(scores["incumbent"])
        summary[f"paired_{k}_minus_incumbent"] = {
            "mean": float(d.mean()), "sem": float(d.std(ddof=1) / np.sqrt(d.size)),
            "draws_positive": int((d > 0).sum()), "n_draws": int(d.size),
            "per_draw": [round(float(x), 6) for x in d]}
    out = {"instrument": "catalogue-aware generative truth model + official metric, paired draws",
           "truth_model": {"truth_px": a.truth_px, "sigma_px": a.sigma,
                           "pool": "field surface at least 1 px from the given catalogue",
                           "source": "GEMSDOE25 H28 inference (owner-report-derived prior)"},
           "draws": a.draws, "summary": summary, "seconds": round(time.time() - t0, 1),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ROOT / a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_draw"}
                      for k, v in summary.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
