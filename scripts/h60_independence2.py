#!/usr/bin/env python3
"""H60-C (second form) — a more powerful version of the independence statistic.

The first form thresholds each view's out-of-fold probability at 0.5 and correlates the two
per-block confident-positive rates.  On labelled negatives almost every block has a rate of
exactly zero, so its variance is zero and the block is dropped: only 60 of ~4,950 blocks survived.
That is a real statistic but a weak one, and a weak test of the Blum-Mitchell premise is not what
the brief asks for.

This second form uses each view's **mean out-of-fold probability** on labelled negatives as the
block error rate.  It is continuous, defined on every block, and strictly more powerful.  Both
forms are reported; the preregistered abandonment rule (max |rho| > 0.60) is applied to both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data"
WORK = ROOT / "work"
BLOCK_SIDE = 50
MIN_N = 400
BUFFER_PX = 4
THRESHOLD = 0.60


def main() -> int:
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    shape = tpl.shape
    finite = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    lab = np.zeros(shape, dtype=bool)
    lab[finite] = np.isfinite(lb[finite]) & (lb[finite] > 0.5)

    oa = np.load(WORK / "h60_oof_A.npy")
    ob = np.load(WORK / "h60_oof_B.npy")
    neg = finite & ~lab & ~ndimage.binary_dilation(lab, structure=np.ones((3, 3), bool),
                                                   iterations=BUFFER_PX)
    neg &= np.isfinite(oa) & np.isfinite(ob)
    H, W = shape
    ma, mb, fa, fb, nn = [], [], [], [], []
    for by in range(0, H, BLOCK_SIDE):
        for bx in range(0, W, BLOCK_SIDE):
            m = np.zeros(shape, dtype=bool)
            m[by:by + BLOCK_SIDE, bx:bx + BLOCK_SIDE] = True
            m &= neg
            n = int(m.sum())
            if n < MIN_N:
                continue
            a, b = oa[m], ob[m]
            ma.append(float(a.mean()))
            mb.append(float(b.mean()))
            fa.append(float((a > 0.5).mean()))
            fb.append(float((b > 0.5).mean()))
            nn.append(n)
    ma, mb = np.array(ma), np.array(mb)
    fa, fb = np.array(fa), np.array(fb)
    rho_mean = float(spearmanr(ma, mb).correlation)
    rho_rate = float(spearmanr(fa, fb).correlation) if fa.std() > 0 and fb.std() > 0 else float("nan")
    # variance-filtered variant of the thresholded form, for comparability with the first run
    keep = (fa > 0) | (fb > 0)
    rho_rate_f = (float(spearmanr(fa[keep], fb[keep]).correlation)
                  if keep.sum() > 3 and fa[keep].std() > 0 and fb[keep].std() > 0 else float("nan"))
    stat = dict(
        n_blocks=len(ma), block_side_px=BLOCK_SIDE, min_n_per_block=MIN_N, threshold=THRESHOLD,
        rho_block_mean_oof_probability=rho_mean,
        rho_block_fp_rate_all_blocks=rho_rate,
        rho_block_fp_rate_nonzero_blocks=rho_rate_f,
        n_nonzero_fp_blocks=int(keep.sum()),
        fires=bool(max(abs(x) for x in (rho_mean, rho_rate, rho_rate_f) if np.isfinite(x))
                   > THRESHOLD),
        mean_oof_a=float(ma.mean()), mean_oof_b=float(mb.mean()),
        note=("Primary statistic: Spearman correlation, across 50x50 px blocks, of the two views' "
              "mean out-of-fold probability on labelled negatives (outside the catalogue and a 4 px "
              "buffer). It is continuous and defined on every block, unlike the thresholded "
              "confident-positive rate, which is zero on most blocks and therefore discards them."))
    print(json.dumps({k: v for k, v in stat.items() if k != "note"}, indent=1))

    p = WORK / "h60_cotrain.json"
    d = json.loads(p.read_text())
    d["independence_primary"] = stat
    d["independence"] = stat
    p.write_text(json.dumps(d, indent=1))
    print("wrote work/h60_cotrain.json (independence replaced with the more powerful form)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
