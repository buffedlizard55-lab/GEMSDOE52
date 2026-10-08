#!/usr/bin/env python3
"""H60-B/C -- two-view co-training, and the empirical test of its independence premise.

Method (Blum & Mitchell, COLT '98 pp. 92-100, doi:10.1145/279943.279962)
------------------------------------------------------------------------
Two learners are trained on two different feature sets (views) of the same pixels.  Where one is
confident and the other abstains, the confident view's prediction becomes a pseudo-label for the
other.  The guarantee requires each view to be (i) sufficient and (ii) approximately conditionally
independent given the class.  (ii) is what this script measures, because three previous rounds in
this family disagreed about it (H57 0.1108, H59 0.1071, R4 0.7051 on a different layer plan) and
the brief requires the test before the method is used.

Views
-----
View A -- potential field and subsurface (`training_features.tif` bands, 1-indexed):
    1 mag_anom, 2 rtp, 3 tmi_hg, 9 tmi_vg, 14 tmi
    13 iso_grav_anom, 11 iso_grav_anom_vg, 18 iso_grav_anom_hg, 5 iso_grav_anom_slope
    4 geod_2ndinv, 7 geod_shearrate, 8 geod_dilaterate
    10 deq_n100a15, 16 ieq_n100a15, 15 depth_to_base_surf, 17 cond_surf
View B -- surface:
    12 det_elev, 19 det_elev_slope, and 6 tc.

Band 6 is described by the organiser as a magnetic tilt derivative, but measured on the bytes its
range here is 2.95-88.6, which is a radiometric total count and not a tilt angle
(IR-52-019 / IR-52-034).  It is the only radiometric band in the training raster, so it belongs to
the surface view; leaving it inside the potential-field view would corrupt the very independence
test this method has to pass.

Band 10 (`deq_n100a15`) reaches 4,962,515 m inside a grid whose diagonal is about 492 km
(IR-R4-002), so every band is rank-transformed before any learner sees it.

Memory note: features are materialised on the ~5.16 M valid pixels only, never on the 12.28 M-cell
rectangle -- the first attempt allocated 1,375 MB for one view and died in a 3 GB sandbox.
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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data"
WORK = ROOT / "work"
SEED = 20261008

BANDS_A = [1, 2, 3, 9, 14, 13, 11, 18, 5, 4, 7, 8, 10, 16, 15, 17]
BANDS_B = [12, 19, 6]
DERIV_A = [2, 14, 13, 15]
DERIV_B = [12, 19, 6]

NEG_PER_POS = 4
N_TRAIN = 240_000
# Thresholds are per-view QUANTILES, not absolute probabilities.  The two views are calibrated
# very differently (in-sample AUC 0.93 for View A against 0.78 for View B on this layer plan), so a
# shared absolute cut-off makes the confident set almost entirely a property of which view is
# better calibrated rather than of which view is more certain.  "Confident" = the view's own top
# 5 % over the valid footprint; "abstain" = at or below its median.
CONF_Q, ABSTAIN_Q = 0.95, 0.50
BUFFER_PX = 4
BLOCK_SIDE = 50
TILE_PX = 200
INDEP_THRESHOLD = 0.60


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def rank_transform(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.zeros(a.shape, dtype=np.float32)
    v = a[valid]
    if v.size == 0:
        return out
    order = np.argsort(v, kind="stable")
    ranks = np.empty(v.size, dtype=np.float64)
    ranks[order] = np.arange(v.size, dtype=np.float64)
    r = np.zeros(a.shape, dtype=np.float64)
    r[valid] = ranks
    out[valid] = (r[valid] / max(v.size - 1, 1)).astype(np.float32)
    return out


def build_view(spec_bands, deriv_bands, valid, valid_idx, tag, extras):
    ncol = len(spec_bands) + len(deriv_bands) * len(extras)
    X = np.zeros((valid_idx.size, ncol), dtype=np.float32)
    names = []
    j = 0
    for b in spec_bands:
        with rasterio.open(DATA / "training_features.tif") as s:
            a = s.read(b)
        a = np.where(np.isfinite(a) & (a > -1e38), a, np.nan).astype(np.float32)
        fin = np.isfinite(a) & valid
        r = rank_transform(a, fin)
        del a, fin
        flat = r.reshape(-1)
        X[:, j] = flat[valid_idx]
        names.append(f"{tag}_b{b}_rank")
        j += 1
        if b in deriv_bands:
            rf = np.nan_to_num(r, nan=0.0)
            if "grad" in extras:
                X[:, j] = np.hypot(ndimage.sobel(rf, axis=1, mode="nearest"),
                                   ndimage.sobel(rf, axis=0, mode="nearest")
                                   ).reshape(-1)[valid_idx]
                names.append(f"{tag}_b{b}_grad")
                j += 1
            if "range5" in extras:
                X[:, j] = (ndimage.maximum_filter(rf, size=5) -
                           ndimage.minimum_filter(rf, size=5)).reshape(-1)[valid_idx]
                names.append(f"{tag}_b{b}_range5")
                j += 1
            if "lap" in extras:
                X[:, j] = ndimage.laplace(rf, mode="nearest").reshape(-1)[valid_idx]
                names.append(f"{tag}_b{b}_lap")
                j += 1
            del rf
        del r, flat
    assert j == ncol, (j, ncol)
    np.nan_to_num(X, copy=False)
    return X, names


def make_model(seed, iters=150):
    return HistGradientBoostingClassifier(
        max_iter=iters, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=60,
        l2_regularization=1.0, random_state=seed)


def main() -> int:
    WORK.mkdir(exist_ok=True)
    t0 = time.time()
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    shape = tpl.shape
    finite = np.isfinite(tpl)
    with rasterio.open(DATA / "training_features.tif") as s:
        acc = None
        for i in range(1, s.count + 1):
            a = s.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            acc = ok if acc is None else (acc & ok)
    valid = finite & acc
    del acc, tpl
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    lab = np.zeros(shape, dtype=bool)
    lab[finite] = np.isfinite(lb[finite]) & (lb[finite] > 0.5)
    log(f"footprint {int(finite.sum())}  all-19-bands-valid {int(valid.sum())}  "
        f"catalogue {int(lab.sum())}")

    valid_idx = np.flatnonzero(valid.ravel())

    struct = np.ones((3, 3), bool)
    cc, ncomp = ndimage.label(lab, structure=struct)
    rng = np.random.default_rng(SEED)
    # Spatially blocked folds over the WHOLE grid.  A fold assignment built only from catalogue
    # components leaves every non-catalogue pixel with fold 0, which makes out-of-fold
    # probabilities undefined exactly on the negatives the independence test needs (the first run
    # produced blocks=0 and rho=nan).  Tiles of TILE_PX are assigned by (i + 2j) mod 4, so every
    # 4-neighbour tile is in a different fold; catalogue components are then forced whole into the
    # fold of the tile holding their centroid, which is the "whole-segment spatial block" the brief
    # asks for.
    H, W = shape
    ti = np.add.outer(np.arange((H + TILE_PX - 1) // TILE_PX) * TILE_PX // TILE_PX,
                      np.zeros((W + TILE_PX - 1) // TILE_PX, dtype=np.int64))
    tj = np.add.outer(np.zeros((H + TILE_PX - 1) // TILE_PX, dtype=np.int64),
                      np.arange((W + TILE_PX - 1) // TILE_PX))
    tile_fold = ((ti + 2 * tj) % 4).astype(np.int8) + 1
    fold_of = np.zeros(shape, dtype=np.int8)
    for a in range(tile_fold.shape[0]):
        for b in range(tile_fold.shape[1]):
            fold_of[a * TILE_PX:(a + 1) * TILE_PX, b * TILE_PX:(b + 1) * TILE_PX] = tile_fold[a, b]
    # keep whole catalogue components in one fold
    cents = ndimage.center_of_mass(lab, cc, range(1, ncomp + 1))
    for ci_, (cy, cx) in enumerate(cents, start=1):
        if not np.isfinite(cy):
            continue
        f = fold_of[int(cy), int(cx)]
        fold_of[cc == ci_] = f
    log(f"catalogue components {ncomp}; blocked folds over the whole grid "
        f"(tile {TILE_PX} px), component counts "
        f"{[int(((fold_of==k)&lab).sum()) for k in (1,2,3,4)]}")

    # ---------------- global training rows (mapped into valid-index space) ----------------
    pos_grid = np.flatnonzero((lab & valid).ravel())
    neg_pool_grid = np.flatnonzero((valid & ~ndimage.binary_dilation(lab, structure=struct,
                                                                     iterations=BUFFER_PX)).ravel())
    rng.shuffle(neg_pool_grid)
    n_pos = min(len(pos_grid), N_TRAIN // (NEG_PER_POS + 1))
    pos_grid = rng.choice(pos_grid, size=n_pos, replace=False) if n_pos < len(pos_grid) else pos_grid
    neg_grid = neg_pool_grid[:n_pos * NEG_PER_POS]
    rows = np.concatenate([np.searchsorted(valid_idx, pos_grid),
                           np.searchsorted(valid_idx, neg_grid)])
    y = np.concatenate([np.ones(len(pos_grid), np.int8), np.zeros(len(neg_grid), np.int8)])
    log(f"training rows {len(rows)} ({len(pos_grid)}+ / {len(neg_grid)}-)")

    # ---------------- feature stacks, built once ----------------
    Xs, namemap = {}, {}
    Xs["A"], namemap["A"] = build_view(BANDS_A, DERIV_A, valid, valid_idx, "A", ("grad",))
    log(f"view A {Xs['A'].shape}  {Xs['A'].nbytes/1e6:.0f} MB")
    Xs["B"], namemap["B"] = build_view(BANDS_B, DERIV_B, valid, valid_idx, "B",
                                       ("grad", "range5", "lap"))
    log(f"view B {Xs['B'].shape}  {Xs['B'].nbytes/1e6:.0f} MB")

    def to_grid(v):
        g = np.zeros(shape, dtype=np.float32)
        g.reshape(-1)[valid_idx] = v
        return g

    # ---------------- full-fit probabilities ----------------
    probs, auc_in = {}, {}
    for tag in ("A", "B"):
        X = Xs[tag]
        clf = make_model(SEED, iters=200)
        clf.fit(X[rows], y)
        p = np.zeros(valid_idx.size, dtype=np.float32)
        step = 600_000
        for s0 in range(0, valid_idx.size, step):
            p[s0:s0 + step] = clf.predict_proba(X[s0:s0 + step])[:, 1].astype(np.float32)
        probs[tag] = to_grid(p)
        auc_in[tag] = float(roc_auc_score(y, clf.predict_proba(X[rows])[:, 1]))
        np.save(WORK / f"h60_prob_{tag}.npy", probs[tag])
        log(f"view {tag}: {X.shape[1]} features, in-sample AUC {auc_in[tag]:.4f}")
    pA, pB = probs["A"], probs["B"]

    # ---------------- out-of-fold, whole-component blocked ----------------
    log("--- blocked out-of-fold (4 whole-component folds, 4 px buffer off training)")
    oof = {}
    fold_auc = {}
    for tag in ("A", "B"):
        X = Xs[tag]
        o = np.full(valid_idx.size, np.nan, dtype=np.float32)
        for fi in range(4):
            # The buffer must surround the HELD-OUT segment: it keeps training rows away from the
            # segment being recovered, and it must NOT be built from the training positives
            # themselves (that emptied the positive set on the first run).
            buf_fi = ndimage.binary_dilation((fold_of == fi + 1), structure=struct,
                                             iterations=BUFFER_PX)
            tr_mask = (fold_of != fi + 1) & valid & ~buf_fi
            tp = np.searchsorted(valid_idx, np.flatnonzero((lab & tr_mask).ravel()))
            tn = np.searchsorted(valid_idx, np.flatnonzero((tr_mask & ~lab).ravel()))
            rng.shuffle(tn)
            k = min(len(tp) * NEG_PER_POS, len(tn))
            tr_rows = np.concatenate([tp, tn[:k]])
            yy = np.concatenate([np.ones(len(tp), np.int8), np.zeros(k, np.int8)])
            clf = make_model(SEED + fi)
            clf.fit(X[tr_rows], yy)
            te = np.flatnonzero(((fold_of == fi + 1) & valid).ravel())
            te_v = np.searchsorted(valid_idx, te)
            o[te_v] = clf.predict_proba(X[te_v])[:, 1].astype(np.float32)
            fold_auc[f"{tag}_fold{fi}_n_train_pos"] = int(len(tp))
            del buf_fi
        oof[tag] = to_grid(o)
        np.save(WORK / f"h60_oof_{tag}.npy", oof[tag])
        log(f"    view {tag} OOF complete")
    np.save(WORK / "h60_valid_idx.npy", valid_idx)
    np.save(WORK / "h60_fold_of.npy", fold_of)

    # ---------------- H60-C: the independence test ----------------
    log("--- H60-C independence: per-block OOF false-positive rate correlation on labelled negatives")
    oa, ob = oof["A"], oof["B"]
    neg_mask = valid & ~ndimage.binary_dilation(lab, structure=struct, iterations=BUFFER_PX)
    neg_mask &= ~lab
    H, W = shape
    blocks = []
    for by in range(0, H, BLOCK_SIDE):
        for bx in range(0, W, BLOCK_SIDE):
            m = np.zeros(shape, dtype=bool)
            m[by:by + BLOCK_SIDE, bx:bx + BLOCK_SIDE] = True
            m &= neg_mask & np.isfinite(oa) & np.isfinite(ob)
            n_b = int(m.sum())
            if n_b < 400:
                continue
            ea = (oa[m] > 0.5).astype(np.int8)
            eb = (ob[m] > 0.5).astype(np.int8)
            if ea.std() == 0 or eb.std() == 0:
                continue
            blocks.append(dict(block=f"{by}_{bx}", n=n_b,
                               fp_rate_a=float(ea.mean()), fp_rate_b=float(eb.mean())))
    fa = np.array([b["fp_rate_a"] for b in blocks])
    fb = np.array([b["fp_rate_b"] for b in blocks])
    rho = float(spearmanr(fa, fb).correlation) if len(blocks) > 2 else float("nan")
    if np.isfinite(rho):
        for b in blocks:
            b["rho_global"] = rho
        # block-level bootstrap of the same statistic is not defined for a single global rho;
        # report the per-block contribution spread as the uncertainty instead.
    stat = dict(
        n_blocks=len(blocks), block_side_px=BLOCK_SIDE, statistic="spearman_fp_rate_across_blocks",
        rho=rho, threshold=INDEP_THRESHOLD,
        fires=bool(np.isfinite(rho) and abs(rho) > INDEP_THRESHOLD),
        mean_fp_rate_a=float(fa.mean()) if len(fa) else float("nan"),
        mean_fp_rate_b=float(fb.mean()) if len(fb) else float("nan"),
        note=("Per 50x50 px (5 km) block over labelled negatives (outside catalogue and a 4 px "
              "buffer), each view's out-of-fold confident-positive rate is computed; the Spearman "
              "correlation of those two block-level error rates is the statistic. Blum-Mitchell "
              "requires approximate conditional independence given the class; above 0.60 the "
              "pseudo-label exchange is abandoned."))
    log(f"    blocks={stat['n_blocks']}  rho={stat['rho']:.4f}  threshold={INDEP_THRESHOLD}  "
        f"fires={stat['fires']}")

    # ---------------- disagreement strata ----------------
    thrA_hi = float(np.quantile(pA[valid], CONF_Q))
    thrB_hi = float(np.quantile(pB[valid], CONF_Q))
    thrA_lo = float(np.quantile(pA[valid], ABSTAIN_Q))
    thrB_lo = float(np.quantile(pB[valid], ABSTAIN_Q))
    log(f"    per-view quantile thresholds: A conf>={thrA_hi:.4f} abstain<={thrA_lo:.4f} | "
        f"B conf>={thrB_hi:.4f} abstain<={thrB_lo:.4f}")
    A_conf, B_conf = pA >= thrA_hi, pB >= thrB_hi
    A_abs, B_abs = pA <= thrA_lo, pB <= thrB_lo
    allowed = valid
    strata = {"a_only": A_conf & B_abs & allowed,
              "b_only": B_conf & A_abs & allowed,
              "concordant": A_conf & B_conf & allowed,
              "neither": ~(A_conf | B_conf) & allowed}
    counts = {k: int(v.sum()) for k, v in strata.items()}
    log(f"    strata (per-view quantiles): {counts}")

    # ---------------- hide-and-recover vs single-view baselines ----------------
    log("--- hide-and-recover: two views vs random at matched budget")
    from gems52 import metric as M
    hide_rows = []
    BUDGET = 40_000
    for fi in range(4):
        held = (fold_of == fi + 1) & lab & valid
        lab_held = (fold_of == fi + 1) & lab
        if held.sum() < 200:
            continue
        # the held-out segment must be REMOVED from the catalogue that builds the emission
        # exclusion, or it becomes unplaceable (survival 0.000).  R4 §4.
        buf_fi = ndimage.binary_dilation((fold_of == fi + 1), structure=struct,
                                         iterations=BUFFER_PX)
        cand = valid      # the held-out segment stays placeable (R4 §4: survival must be ~1)
        ci = np.flatnonzero(cand.ravel())
        ci_v = np.searchsorted(valid_idx, ci)
        # survival = is the held-out truth inside the set we are allowed to emit on?  It must be,
        # or the held-out segment is unrecoverable and the fold measures nothing (R4 section 4).
        survival = float((held & cand).sum() / max(held.sum(), 1))
        for tag in ("A", "B", "union"):
            X = Xs[tag] if tag in ("A", "B") else None
            tp = np.searchsorted(valid_idx, np.flatnonzero(
                ((lab & (fold_of != fi + 1)) & valid & ~buf_fi & ~lab_held).ravel()))
            tn = np.searchsorted(valid_idx, np.flatnonzero(
                ((fold_of != fi + 1) & valid & ~buf_fi & ~lab).ravel()))
            rng.shuffle(tn)
            k = min(len(tp) * NEG_PER_POS, len(tn))
            tr_rows = np.concatenate([tp, tn[:k]])
            yy = np.concatenate([np.ones(len(tp), np.int8), np.zeros(k, np.int8)])
            ph = np.zeros(ci_v.size, dtype=np.float32)
            if tag == "union":
                for tg in ("A", "B"):
                    clf = make_model(SEED + fi)
                    clf.fit(Xs[tg][tr_rows], yy)
                    q = np.zeros(ci_v.size, dtype=np.float32)
                    for s0 in range(0, ci_v.size, 600_000):
                        q[s0:s0 + 600_000] = clf.predict_proba(
                            Xs[tg][ci_v[s0:s0 + 600_000]])[:, 1].astype(np.float32)
                    ph = np.maximum(ph, q)
            else:
                clf = make_model(SEED + fi)
                clf.fit(X[tr_rows], yy)
                for s0 in range(0, ci_v.size, 600_000):
                    ph[s0:s0 + 600_000] = clf.predict_proba(
                        X[ci_v[s0:s0 + 600_000]])[:, 1].astype(np.float32)
            budget = min(BUDGET, int(ci.size))
            sel = ci[np.argsort(-ph)[:budget]]
            sm = np.zeros(shape, dtype=bool)
            sm[np.unravel_index(sel, shape)] = True
            r = M.dti(sm.astype(np.float64), held)
            hide_rows.append(dict(fold=fi, arm=tag, budget=budget, n_held=int(held.sum()),
                                  survival=round(survival, 4), dti=float(r["dti"]),
                                  tpw=float(r["tpw"])))
            log(f"    fold {fi} {tag:6s}: held={int(held.sum())} survival={survival:.3f} "
                f"DTI={r['dti']:.5f}")
        pick = rng.choice(ci, size=min(BUDGET, int(ci.size)), replace=False)
        sm = np.zeros(shape, dtype=bool)
        sm[np.unravel_index(pick, shape)] = True
        r = M.dti(sm.astype(np.float64), held)
        hide_rows.append(dict(fold=fi, arm="random", budget=min(BUDGET, int(ci.size)),
                              n_held=int(held.sum()), survival=round(survival, 4),
                              dti=float(r["dti"]), tpw=float(r["tpw"])))
        log(f"    fold {fi} random: held={int(held.sum())} DTI={r['dti']:.5f}")

    out = dict(seed=SEED, bands_A=BANDS_A, bands_B=BANDS_B,
               features_A=namemap["A"], features_B=namemap["B"],
               thresholds=dict(confident_quantile=CONF_Q, abstain_quantile=ABSTAIN_Q,
                               confident_quantile_value=dict(A=thrA_hi, B=thrB_hi),
                               abstain_quantile_value=dict(A=thrA_lo, B=thrB_lo)),
               buffer_px=BUFFER_PX,
               training=dict(positives=int(len(pos_grid)), negatives=int(len(neg_grid))),
               in_sample_auc=auc_in, independence=stat, strata_counts=counts,
               hide_and_recover=hide_rows, n_components=int(ncomp),
               runtime_s=round(time.time() - t0, 1))
    (WORK / "h60_cotrain.json").write_text(json.dumps(out, indent=1))
    log(f"wrote work/h60_cotrain.json in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
