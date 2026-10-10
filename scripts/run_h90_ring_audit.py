#!/usr/bin/env python3
"""H87-R: instrument audit of the legal-pool ring on the shared H60D holdout (no refit).

Frozen in ``registry/h87_ring_preregistration.json`` before any number here was computed.

Shipped rule (run_h60d_cotrain.stage_validate): ``permitted = valid & ~dilate(FULL catalogue, 2)``,
so the held-out truth itself sets holes in the emission pool. Variant: ``valid & ~dilate(VISIBLE
catalogue, 2)``, which is what a competitor can actually see. Same OOF fields, same folds, same
scorer, same budget. Only the pool changes.

Outputs ``evidence/h90_ring_audit.json``.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h60d_cotrain as R  # noqa: E402
from gems52 import grid as G  # noqa: E402
from gems52 import h57  # noqa: E402
from gems52 import h60d  # noqa: E402
from gems52 import holdout as HO  # noqa: E402
from gems52 import metric as M  # noqa: E402

OUT = ROOT / "evidence/h90_ring_audit.json"
K = 37654


def log(m: str) -> None:
    print(f"[h90-R {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from(R.DATA / "training_features.tif", bands="all")
    with rasterio.open(R.DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=R.SEED,
                          mode="hide")
    corridor_full = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    pa = np.nan_to_num(np.load(R.WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(R.WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    fields = {"view_A": pa, "view_B": pb, "clf_union": np.maximum(pa, pb),
              "dis_contrast": h60d.dis_contrast(pa, pb)}

    rows = {"shipped": {}, "visible_ring": {}}
    for f in folds:
        reg, vis, fold = f["region"], f["visible"] & valid, f["fold"]
        truth_full = f["truth"] & reg & valid
        corridor_vis = ndimage.binary_dilation(vis, iterations=h57.CORRIDOR_PX)
        blocked = ndimage.binary_dilation(vis, iterations=h57.CORRIDOR_PX)
        legal_ship = reg & (valid & ~corridor_full) & ~blocked
        legal_vis = reg & valid & ~corridor_vis
        rng = np.random.default_rng(R.SEED + fold)
        for tag, legal in (("shipped", legal_ship), ("visible_ring", legal_vis)):
            truth = truth_full
            n_truth_in_legal = int((truth & legal).sum())
            rec_key = f"fold{fold}"
            rows[tag].setdefault("n_truth_in_legal", {})[rec_key] = n_truth_in_legal
            rows[tag].setdefault("legal_px", {})[rec_key] = int(legal.sum())
            flat = np.flatnonzero(legal.ravel())
            take = rng.choice(flat, min(K, flat.size), replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = HO.mask_visible(np.where(reg, rnd.astype(np.float32), 0.0), vis)
            rr = M.dti(p, truth)
            rows[tag].setdefault("random", []).append(dict(fold=fold, tpw=float(rr["tpw"]),
                                                             fpw=float(rr["fpw"]),
                                                             fnw=float(rr["fnw"]),
                                                             n_truth=int(rr["n_truth"]),
                                                             dti=float(rr["dti"])))
            for name, fld in fields.items():
                r = R.score_cell(fld, legal, truth, reg, valid, vis, K)
                rows[tag].setdefault(name, []).append(dict(fold=fold, tpw=float(r["tpw"]),
                                                            fpw=float(r["fpw"]),
                                                            fnw=float(r["fnw"]),
                                                            n_truth=int(r["n_truth"]),
                                                            dti=float(r["dti"])))
        log(f"fold {fold}: legal shipped {int(legal_ship.sum())} px, visible-ring "
            f"{int(legal_vis.sum())} px; truth in legal shipped={rows['shipped']['n_truth_in_legal'][f'fold{fold}']}, "
            f"visible-ring={rows['visible_ring']['n_truth_in_legal'][f'fold{fold}']}")

    names = ("random", "view_A", "view_B", "clf_union", "dis_contrast")
    summary = {tag: {} for tag in rows}
    for tag in rows:
        for name in names:
            pooled = h60d.pooled_dti(rows[tag][name])
            summary[tag][name] = dict(pooled_dti=pooled["dti"], n_truth=pooled["n_truth"],
                                      fold_dti=[round(x["dti"], 6) for x in rows[tag][name]])
    ratio = {n: (summary["visible_ring"][n]["pooled_dti"] / summary["shipped"][n]["pooled_dti"]
                 if summary["shipped"][n]["pooled_dti"] > 0 else None) for n in names}
    material = {n: (r is not None and abs(r - 1.0) > 0.10) for n, r in ratio.items()}
    order_ship = sorted(names, key=lambda n: -summary["shipped"][n]["pooled_dti"])
    order_vis = sorted(names, key=lambda n: -summary["visible_ring"][n]["pooled_dti"])
    receipt = dict(
        round="H87-R", preregistration="registry/h87_ring_preregistration.json",
        seed=R.SEED, budget=K, runtime_s=round(time.time() - t0, 1),
        pooled=summary, ratio_visible_over_shipped=ratio,
        material_change_over_10pct=material,
        arm_order_shipped=order_ship, arm_order_visible_ring=order_vis,
        arm_order_unchanged=(order_ship == order_vis),
        truth_in_legal_shipped_is_zero=bool(all(v == 0 for v in rows["shipped"]["n_truth_in_legal"].values())),
        holdout_label="HOLDOUT-DTI (H60D instrument; evaluator gems52.metric.dti alpha 0.2 beta 0.8 R 300 m; "
                      "4 hide folds; per-fold 37,654 px; not a leaderboard estimate)",
        slots_used=0,
    )
    h60d.write_json(OUT, receipt)
    log(f"ratios visible/shipped: {ratio}")
    log(f"arm order shipped {order_ship} | visible {order_vis}")
    log(f"truth inside shipped legal pool: {rows['shipped']['n_truth_in_legal']}")
    log(f"wrote {OUT.name} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
