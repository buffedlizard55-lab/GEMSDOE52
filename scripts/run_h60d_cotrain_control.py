#!/usr/bin/env python3
"""H60 co-training control: same-seed refit WITHOUT pseudo-labels, on the treated fold.

The round-1 refits in ``run_h60d_cotrain.py`` used ``SEED + 7`` while the round-0 fits used
``SEED + fold``; a DTI difference between round 0 and round 1 on the treated fold is
therefore confounded with the seed change.  This control refits both views on the fold-0
fit region with the SAME seed as the round-1 refits (``SEED + 7``) and NO pseudo-labels,
and scores the identical cells.  Exchange effect = round1 − control; seed effect =
control − round0.  Registered in ``registry/h60d_preregistration.json`` (H60-3 readout).
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

from gems52 import grid as G                       # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h60d                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402

DATA = ROOT / "work/pinned"
WORK = ROOT / "work/h60"
EV = ROOT / "evidence"
PREREG = json.loads((ROOT / "registry/h60d_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
N_NEG_TRAIN = int(PREREG["protocol"]["thresholds"]["neg_train"])
BUDGET = 37654


def log(m: str) -> None:
    print(f"[h60d-ctrl {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _gather(layers, idx, flat_idx, width):
    flat_idx = np.asarray(flat_idx, np.int64)
    rows = flat_idx // width
    order = np.argsort(rows, kind="stable")
    rows_sorted = rows[order]
    out = np.empty((flat_idx.size, len(idx)), np.float32)
    mm = layers.mm
    uniq = np.unique(rows_sorted)
    for r, s0, e0 in zip(uniq, np.searchsorted(rows_sorted, uniq, side="left"),
                         np.searchsorted(rows_sorted, uniq, side="right")):
        sel = order[s0:e0]
        cols = flat_idx[sel] - int(r) * width
        block = np.asarray(mm[idx, int(r), :], dtype=np.uint8)
        out[sel] = block[:, cols].T.astype(np.float32) / 255.0
    return out


def fit_and_predict(layers, idx, cat, valid, fit, seed, tag):
    pos, neg = h57.labelled_pixels(cat, valid, fit, seed=seed, n_neg=N_NEG_TRAIN)
    w = cat.shape[1]
    X = np.vstack([_gather(layers, idx, pos, w), _gather(layers, idx, neg, w)])
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
    clf = h57.fit_view(X, y)
    grid = h57.predict_grid(clf, layers, idx)
    log(f"{tag}: {pos.size} pos / {neg.size} neg, {X.shape[1]} features")
    del X, y
    return grid


def score_cell(field, legal, truth, region, valid, visible, k):
    score = np.where(legal, field, 0.0).astype(np.float32)
    nodes = h57.iso_select(score, legal, k, min_px=3.0, nms_px=5)
    p = np.where(region, nodes.astype(np.float32), 0.0)
    p = HO.mask_visible(p, visible & valid)
    r = M.dti(p, truth & region & valid)
    return r


def main() -> int:
    out = EV / "h60d_cotrain_control.json"
    if out.exists():
        log("control cached")
        return 0
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    layers = h57.Layers(str(WORK))
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    pa0 = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb0 = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    pa_ct = np.load(WORK / "pa_cotrain.npy").astype(np.float32)
    pb_ct = np.load(WORK / "pb_cotrain.npy").astype(np.float32)

    # same-seed (SEED+7), no-pseudo refits on the fold-0 fit region
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="hide")
    f0 = folds[0]
    pa_ctrl = fit_and_predict(layers, idx_a, cat, valid, f0["fit"], SEED + 7, "A-control")
    pb_ctrl = fit_and_predict(layers, idx_b, cat, valid, f0["fit"], SEED + 7, "B-control")
    np.save(WORK / "pa_control.npy", pa_ctrl)
    np.save(WORK / "pb_control.npy", pb_ctrl)

    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    rows = []
    for mode in ("hide", "tip"):
        mf = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                           seed=SEED, mode=mode)
        f = mf[0]
        blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
        legal = f["region"] & permitted & ~blocked
        truth = f["truth"] & f["region"] & valid
        fields = {
            "view_A_round0": pa0, "view_B_round0": pb0,
            "clf_union_round0": np.maximum(pa0, pb0),
            "view_A_control": pa_ctrl, "view_B_control": pb_ctrl,
            "clf_union_control": np.maximum(pa_ctrl, pb_ctrl),
            "cotrain_A_round1": pa_ct, "cotrain_B_round1": pb_ct,
            "cotrain_union_round1": np.maximum(pa_ct, pb_ct),
        }
        for name, fld in fields.items():
            r = score_cell(fld, legal, truth, f["region"], valid, f["visible"], BUDGET)
            rows.append(dict(mode=mode, fold=0, budget=BUDGET, arm=name,
                             dti=round(float(r["dti"]), 6), n_truth=int(r["n_truth"])))
        log(f"{mode} f0: " + ", ".join(f"{a['arm']}={a['dti']:.4f}" for a in rows
                                       if a["mode"] == mode))

    def d(mode, arm):
        return next(r["dti"] for r in rows if r["mode"] == mode and r["arm"] == arm)

    readout = {}
    for mode in ("hide", "tip"):
        readout[mode] = dict(
            seed_effect_union=round(d(mode, "clf_union_control") - d(mode, "clf_union_round0"), 6),
            exchange_effect_union=round(d(mode, "cotrain_union_round1") - d(mode, "clf_union_control"), 6),
            seed_effect_A=round(d(mode, "view_A_control") - d(mode, "view_A_round0"), 6),
            exchange_effect_A=round(d(mode, "cotrain_A_round1") - d(mode, "view_A_control"), 6),
            seed_effect_B=round(d(mode, "view_B_control") - d(mode, "view_B_round0"), 6),
            exchange_effect_B=round(d(mode, "cotrain_B_round1") - d(mode, "view_B_control"), 6),
            round0_union=d(mode, "clf_union_round0"),
            control_union=d(mode, "clf_union_control"),
            round1_union=d(mode, "cotrain_union_round1"))
    rep = dict(round="H60D-cotrain-control-v1", seed=SEED,
               runtime_s=round(time.time() - t0, 1),
               purpose=("isolate the seed effect from the exchange effect on the treated "
                        "fold: control = same-seed (SEED+7) refit with NO pseudo-labels"),
               rows=rows, readout=readout,
               interpretation=("exchange effect = round1 - control; seed effect = control - "
                               "round0. A positive exchange effect that survives the control "
                               "is the only co-training gain this round can claim; the AUC "
                               "readout in evidence/h60d_cotrain.json remains the registered "
                               "primary and is null-to-negative."))
    h60d.write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
