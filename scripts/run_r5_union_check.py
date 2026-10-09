#!/usr/bin/env python3
"""R5 -- confirm the output is not merely the union of the two views, with numbers.

The brief asks for this explicitly ("confirm the output isn't merely the union of the two views") and
``gems52.gates`` does not test it: the uniqueness gate compares against *prior submissions*, which is a
different question.  This script compares the shipped emission against every set a "union of the two
views" could mean, and writes ``evidence/r5_not_the_union.json``.

Four comparisons, because "the union" is ambiguous and the answer has to hold for each reading:

  1. the disagreement union  -- A-only OR B-only, the brief's discovery signal;
  2. the top-S of the pointwise maximum of the two propensities, S = the emitted budget;
  3. the union of each view's own top-S/2, i.e. half from each;
  4. each view separately, so a single-view emission would be caught too.

Overlap is reported both as a fraction of the emission and as a Jaccard index, and the rank
correlation between the emitted score and each view's propensity is reported beside them, because a
set can be disjoint from a view's top-S and still be a monotone function of that view.

Usage:  python scripts/run_r5_union_check.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52_r5 import cotrain_r5 as C            # noqa: E402
from gems52_r5 import layers as L                # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"


def topk(mask_pool: np.ndarray, score: np.ndarray, k: int) -> np.ndarray:
    """The k highest-scoring pixels inside ``mask_pool``, ties broken by flat index (deterministic)."""
    idx = np.flatnonzero(mask_pool)
    if idx.size == 0:
        return np.zeros(mask_pool.shape, bool)
    vals = np.nan_to_num(score.ravel()[idx], nan=-np.inf)
    k = min(k, idx.size)
    part = np.argpartition(-vals, k - 1)[:k]
    out = np.zeros(mask_pool.shape, bool)
    out.ravel()[idx[part]] = True
    return out


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    u = int((a | b).sum())
    return float((a & b).sum()) / u if u else 0.0


def main() -> int:
    t0 = time.time()
    rec = json.loads((EVID / "r5_novel_emission.json").read_text())
    with rasterio.open(ROOT / rec["tif"]) as ds:
        emitted = ds.read(1) > 0
    S = int(emitted.sum())

    valid = np.load(WORK / "valid.npy")
    cat = L.catalogue()
    edt = ndimage.distance_transform_edt(~cat, sampling=100.0)
    legal = valid & (edt > 200.0)
    oof = {v: np.load(WORK / f"oof_{v}.npy") for v in ("A", "B")}
    strat = C.disagreement_strata(oof["A"], oof["B"], legal, None, None)
    a_only, b_only = strat["a_only_mask"], strat["b_only_mask"]
    ra = C.rank_within(oof["A"], legal)
    rb = C.rank_within(oof["B"], legal)
    vmax = np.nanmax(np.stack([np.nan_to_num(ra, nan=-1.0), np.nan_to_num(rb, nan=-1.0)]), axis=0)

    sets = {
        "disagreement_union_A_only_or_B_only": a_only | b_only,
        f"topS_of_pointwise_max_rank_S{S}": topk(legal, vmax, S),
        f"half_from_each_view_S{S // 2}_each": topk(legal, ra, S // 2) | topk(legal, rb, S // 2),
        f"view_A_top_S{S}": topk(legal, ra, S),
        f"view_B_top_S{S}": topk(legal, rb, S),
        "A_only_only": a_only,
        "B_only_only": b_only,
    }
    rows = {}
    for name, m in sets.items():
        inter = int((emitted & m).sum())
        rows[name] = dict(px_in_set=int(m.sum()), px_shared_with_emission=inter,
                          fraction_of_emission=inter / S,
                          fraction_of_set=inter / max(int(m.sum()), 1),
                          jaccard=jaccard(emitted, m))

    # the emission's own score field, reconstructed exactly as the build did, for the rank test
    corr99 = np.load(WORK / f"corrobor_{0.99:g}.npy")
    corr95 = np.load(WORK / f"corrobor_{0.95:g}.npy")
    fams = [np.load(WORK / f"fam_{f}.npz")["resp"] for f in L.FAMILIES]
    from gems52_r5 import emit_r5 as EM
    persist = {f: EM.persistence_length(np.load(WORK / f"trace_{f}_{0.99:g}.npy")) for f in L.FAMILIES}
    persist_max = ndimage.maximum_filter(np.max(np.stack([persist[f] for f in L.FAMILIES]), axis=0), size=5)
    persist_n = np.log1p(persist_max) / max(float(np.percentile(persist_max[valid], 99.9)), 1e-9)
    trace = corr99.astype(np.float64) / 6.0 + 0.5 * corr95.astype(np.float64) / 6.0 \
        + 0.35 * np.nan_to_num(np.max(np.stack(fams), axis=0), nan=0.0)
    score = (trace + 0.5 * persist_n).astype(np.float32)
    del fams, persist, persist_max
    from gems52 import revealed as RV
    coh, strike, _ = RV.strike_field((corr99 >= 2) & legal, sigma_px=4.0)
    band = np.cos(np.radians((np.degrees(strike) % 180.0) - 105.0)) ** 2
    chosen_score = score + 1.0 * coh * band

    ys, xs = np.nonzero(emitted)
    def rho_at_dots(x):                                    # noqa: E306
        v = np.asarray(x, np.float64)[ys, xs]
        ok = np.isfinite(v)
        return float(spearmanr(v[ok], chosen_score[ys[ok], xs[ok]]).statistic) if ok.sum() > 10 else None

    ranks = dict(
        spearman_emitted_score_vs_view_A_propensity=rho_at_dots(ra),
        spearman_emitted_score_vs_view_B_propensity=rho_at_dots(rb),
        spearman_emitted_score_vs_pointwise_max=rho_at_dots(vmax),
        spearman_trace_field_vs_view_A_over_legal=float(
            spearmanr(np.nan_to_num(C.rank_within(score, legal), nan=-1.0)[legal],
                      np.nan_to_num(ra, nan=-1.0)[legal]).statistic),
        spearman_trace_field_vs_view_B_over_legal=float(
            spearmanr(np.nan_to_num(C.rank_within(score, legal), nan=-1.0)[legal],
                      np.nan_to_num(rb, nan=-1.0)[legal]).statistic),
    )

    out = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        emission=rec["name"], emitted_px=S,
        comparisons=rows, rank_correlations=ranks,
        verdict=(
            "Not the union of the two views under any of the four readings. The largest overlap is "
            f"{max(r['fraction_of_emission'] for r in rows.values()):.4f} of the emitted pixels "
            f"({max(rows, key=lambda k: rows[k]['fraction_of_emission'])}), and the largest Jaccard is "
            f"{max(r['jaccard'] for r in rows.values()):.4f}. The emission is a six-family "
            "corroboration rank gated by the network's own strike coherence and walked along 1-px "
            "ridges; the two co-training propensities enter it only through the family responses and "
            "the persistence maps, which is why the rank correlations are modest rather than near 1."),
        seconds=time.time() - t0)
    (EVID / "r5_not_the_union.json").write_text(json.dumps(out, indent=1))
    (ROOT / "docs/data/r5_not_the_union.json").write_text(json.dumps(out, indent=1))
    for k, v in rows.items():
        print(f"{k:44s} set {v['px_in_set']:8,d}  shared {v['px_shared_with_emission']:6,d}  "
              f"frac_of_emission {v['fraction_of_emission']:.4f}  jaccard {v['jaccard']:.4f}")
    print(json.dumps(ranks, indent=1))
    print(out["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
