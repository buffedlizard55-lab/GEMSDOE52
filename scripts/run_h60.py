#!/usr/bin/env python3
"""H60 round: two-view co-training, independence test, hide-and-recover, budget selection.

Stages (each writes a receipt under ``evidence/``; nothing downstream quotes a number
this script did not measure):

  1. folds          whole-catalogue-component folds with a 4 px buffer
  2. views          View A / View B out-of-fold fields, blocked AUC
  3. independence   per-block OOF error correlation on labelled negatives (abandon > 0.60)
  4. pseudo         Blum-Mitchell exchange, confident-to-abstain, whole segments; AUC delta
  5. strata         A-only / B-only / concordant populations and their physical context
  6. holdout        hide-and-recover DTI for every arm at matched budget, vs random
  7. budget         DTI as a function of budget for the selected ranking  <-- the new test
  8. select         the preregistered promotion rule

Run:  python3 scripts/run_h60.py            (needs /tmp/gemswork/layers from h60.build_stack)
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G                                    # noqa: E402
from gems52.h60 import Stack                                    # noqa: E402
from gems52.metric import dti                                   # noqa: E402

EV = ROOT / "evidence"
EV.mkdir(exist_ok=True)
WORK = Path("/tmp/gemswork/layers")
SEED = 20261009
N_FOLDS = 4
BUFFER_PX = 4
RING_M = 200.0                 # measured: the 100-200 m catalogue ring carried no credit
ABANDON_R = 0.60               # the brief's conditional-independence threshold
MIN_FOLD_WINS = 3


def log(*a):
    print(*a, flush=True)


def save(name, obj):
    (EV / name).write_text(json.dumps(obj, indent=1, default=_fb) + "\n")


def _fb(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


# --------------------------------------------------------------------------- geometry
def spatial_block_folds(cat: np.ndarray, foot: np.ndarray, n_folds=N_FOLDS, seed=SEED,
                        n_blocks: int = 8):
    """Whole contiguous rectangular blocks, dealt to folds.

    The brief asks for "whole-segment spatial blocks and a buffer".  Contiguous rectangles
    are used rather than a random pixel split because a 300 m kernel forgives a trace that
    crosses the split, and rather than catalogue components because the independence test
    the brief names needs held-out *labelled negatives*, which only exist if the held-out
    region contains off-catalogue footprint.  Blocks are dealt largest-catalogue-first so
    the folds are balanced in positive pixels.
    """
    lab = G.block_labels(cat.shape, foot, n=n_blocks)
    ids = np.unique(lab[lab >= 0])
    pos = np.array([int((cat & (lab == i)).sum()) for i in ids])
    rng = np.random.default_rng(seed)
    order = ids[np.argsort(-pos, kind="stable")]
    fold_of = {}
    load = np.zeros(n_folds)
    for b in order:
        f = int(np.argmin(load))
        fold_of[int(b)] = f
        load[f] += pos[list(ids).index(b)]
    fmap = np.full(cat.shape, -1, np.int16)
    m = lab >= 0
    fmap[m] = np.array([fold_of[int(v)] for v in lab[m]], np.int16)
    buf = G.buffer_from_block_ids(lab, BUFFER_PX)
    return fmap, buf, int(ids.size), load.tolist(), [int(x) for x in pos]


def main() -> int:
    t0 = time.time()
    st = Stack(WORK)
    lab = rasterio.open(ROOT / "data/labels.tif").read(1)
    cat = lab == 1
    foot = lab != -1
    with rasterio.open(ROOT / "data/sample_submission.tif") as s:
        sub_ok = np.isfinite(s.read(1))
    H, W = lab.shape
    log(f"[grid] {H}x{W} footprint={int(foot.sum())} catalogue={int(cat.sum())} "
        f"submission-finite={int(sub_ok.sum())}")

    fmap, block_buf, nblk, load, blk_pos = spatial_block_folds(cat, foot)
    log(f"[folds] {nblk} contiguous blocks -> {N_FOLDS} folds, catalogue px per fold {load}")
    save("h60_folds.json", dict(n_blocks=nblk, fold_catalogue_px=load,
                                catalogue_px_per_block=blk_pos, buffer_px=BUFFER_PX,
                                seed=SEED, unit="whole contiguous 466x411 px block",
                                boundary_buffer_px=int(block_buf.sum())))

    # ------------------------------------------------------------------ 2. views OOF
    names_A, names_B = st.view_names("A"), st.view_names("B")
    log(f"[views] A={len(names_A)} layers  B={len(names_B)} layers")
    pA = np.full((H, W), np.nan, np.float32)
    pB = np.full((H, W), np.nan, np.float32)
    oof_rows = []            # (row, col, pA, pB, fold) for the independence test
    fold_auc, fit_px = [], []
    cached = (EV / "h60_views.json").exists() and (ROOT / "work/h60_pA.npy").exists() \
        and "--refit" not in sys.argv
    if cached:
        pA = np.load(ROOT / "work/h60_pA.npy"); pB = np.load(ROOT / "work/h60_pB.npy")
        fold_auc = json.loads((EV / "h60_views.json").read_text())["folds"]
        log("[views] reusing the cached out-of-fold fields (pass --refit to recompute)")

    for f in ([] if cached else range(N_FOLDS)):
        held = fmap == f
        vis_cat = cat & ~held
        # training exclusion: the held-out blocks and the block-boundary buffer
        bnd = ndimage.binary_dilation(held, np.ones((3, 3), bool), iterations=BUFFER_PX) | block_buf
        fit_ok = foot & ~bnd
        pos = fit_ok & vis_cat
        neg_pool = fit_ok & ~vis_cat
        ys, xs = np.nonzero(pos)
        rng = np.random.default_rng(SEED + f)
        nn, npool = ys.size, int(neg_pool.sum())
        k = min(3 * nn, npool)
        sel = rng.choice(npool, size=k, replace=False)
        ny, nx = np.nonzero(neg_pool)
        ny, nx = ny[sel], nx[sel]
        ty = np.concatenate([ys, ny]); tx = np.concatenate([xs, nx])
        yy = np.concatenate([np.ones(ys.size, np.int8), np.zeros(ny.size, np.int8)])
        row = dict(fold=f, n_pos=int(ys.size), n_neg=int(ny.size))
        for view, out in (("A", pA), ("B", pB)):
            X = st.rows(view, ty, tx)
            m = HistGradientBoostingClassifier(
                max_iter=160, learning_rate=0.09, max_leaf_nodes=31, min_samples_leaf=60,
                l2_regularization=1.0, early_stopping=False, random_state=SEED + f)
            m.fit(X, yy)
            # predict over the whole grid in row blocks.  st.block returns (L, h, w);
            # the learner needs (h*w, L), so the axes have to be *transposed* before the
            # reshape -- reshaping (L, h, w) straight to (-1, L) interleaves bands and
            # silently produces garbage features.
            blk = 256
            nl = len(st.view_names(view))
            for b0 in range(0, H, blk):
                b1 = min(H, b0 + blk)
                Xb = np.transpose(st.block(view, b0, b1), (1, 2, 0)).reshape(-1, nl)
                pb = m.predict_proba(Xb)[:, 1].astype(np.float32)
                out[b0:b1] = pb.reshape(b1 - b0, W)
            row[f"view_{view}_layers"] = len(st.view_names(view))
        # blocked AUC on held-out pixels
        hpos = held & cat
        hneg = held & ~cat & foot
        from sklearn.metrics import roc_auc_score
        for view, out in (("A", pA), ("B", pB)):
            y = np.concatenate([np.ones(int(hpos.sum()), np.int8), np.zeros(int(hneg.sum()), np.int8)])
            s = np.concatenate([out[hpos], out[hneg]])
            row[f"auc_{view}_heldout"] = float(roc_auc_score(y, s))
        fold_auc.append(row)
        fit_px.append(int(fit_ok.sum()))
        log(f"  fold {f}: pos={row['n_pos']} neg={row['n_neg']} "
            f"AUC_A={row['auc_A_heldout']:.4f} AUC_B={row['auc_B_heldout']:.4f}")
        # collect labelled NEGATIVES for the independence test: a stratified subsample that
        # keeps enough pixels per 100 px block for a per-block rate to mean anything
        sy, sx = np.nonzero(hneg)
        keep = min(sy.size, 400000)
        if sy.size > keep:
            s2 = rng.choice(sy.size, keep, replace=False)
            sy, sx = sy[s2], sx[s2]
        oof_rows.append(np.column_stack([sy, sx, pA[sy, sx], pB[sy, sx],
                                         np.full(sy.size, f)]).astype(np.float64))
    if not cached:
        save("h60_views.json", dict(folds=fold_auc, fit_px=fit_px,
                                mean_auc_A=float(np.mean([r["auc_A_heldout"] for r in fold_auc])),
                                mean_auc_B=float(np.mean([r["auc_B_heldout"] for r in fold_auc])),
                                layers_A=names_A, layers_B=names_B))
        np.save(ROOT / "work/h60_pA.npy", pA)
        np.save(ROOT / "work/h60_pB.npy", pB)

    # ---------------------------------------------------------- 3. independence test
    # Built from the fields themselves, not accumulated inside the fit loop, so the cached
    # path and the refit path produce the identical statistic.
    rng = np.random.default_rng(SEED + 7)
    oof_rows = []
    for f in range(N_FOLDS):
        hneg = (fmap == f) & ~cat & foot
        sy, sx = np.nonzero(hneg)
        keep = min(sy.size, 400000)
        if sy.size > keep:
            s2 = rng.choice(sy.size, keep, replace=False)
            sy, sx = sy[s2], sx[s2]
        oof_rows.append(np.column_stack([sy, sx, pA[sy, sx], pB[sy, sx],
                                         np.full(sy.size, f)]).astype(np.float64))
    oof = np.vstack(oof_rows)
    BS = 100
    by = (oof[:, 0] // BS).astype(np.int64); bx = (oof[:, 1] // BS).astype(np.int64)
    bid = by * 100000 + bx
    uniq, inv = np.unique(bid, return_inverse=True)
    cnt = np.bincount(inv)
    FAR = 0.01                       # matched global false-alarm rate for both views
    thr_a = float(np.quantile(oof[:, 2], 1 - FAR))
    thr_b = float(np.quantile(oof[:, 3], 1 - FAR))
    hits_a = np.bincount(inv, weights=(oof[:, 2] >= thr_a).astype(float), minlength=uniq.size)
    hits_b = np.bincount(inv, weights=(oof[:, 3] >= thr_b).astype(float), minlength=uniq.size)
    use = cnt >= 200
    fa_a, fa_b = hits_a[use] / cnt[use], hits_b[use] / cnt[use]
    mean_a = np.bincount(inv, weights=oof[:, 2], minlength=uniq.size)[use] / cnt[use]
    mean_b = np.bincount(inv, weights=oof[:, 3], minlength=uniq.size)[use] / cnt[use]
    r_far = float(spearmanr(fa_a, fa_b).statistic) if fa_a.std() > 0 and fa_b.std() > 0 else None
    r_mean = float(spearmanr(mean_a, mean_b).statistic) if mean_a.std() > 0 else None
    r_pix = float(spearmanr(oof[:, 2], oof[:, 3]).statistic)
    indep = dict(
        statistic_named_by_the_brief="per-block false-alarm rate at a matched global rate of "
                                     f"{FAR}, out-of-fold, labelled negatives only, {BS}x{BS} px blocks",
        threshold_view_A=thr_a, threshold_view_B=thr_b,
        n_blocks_used=int(use.sum()), n_blocks_rejected_small=int((~use).sum()),
        min_block_pixels=200,
        spearman_false_alarm=r_far, spearman_mean_score_on_negatives=r_mean,
        spearman_pixel_score=r_pix, abandon_threshold=ABANDON_R,
        abandoned=bool((r_far is not None and abs(r_far) > ABANDON_R)
                       or (r_mean is not None and abs(r_mean) > ABANDON_R)),
        reading="the premise is judged on the statistic the brief names (per-block false-alarm "
                "rate); the mean-score-on-negatives and pixel-level correlations are reported "
                "beside it, not instead of it",
        n_negative_pixels=int(oof.shape[0]))
    log(f"[independence] blocks={indep['n_blocks_used']} r_FAR={r_far} r_mean={r_mean} "
        f"r_pixel={r_pix:.4f} -> abandon={indep['abandoned']}")
    save("h60_independence.json", indep)

    # ------------------------------------------------------- 4. pseudo-label exchange
    # Adaptive, not absolute: on this layer plan neither view ever reaches p=0.995, so a
    # fixed 0.995 confidence threshold produced zero pseudo-labels and the exchange was a
    # no-op that reported itself as a result.  Confidence = the view's own top 0.5 %;
    # abstain = below its own 60th percentile.  The *rule* is unchanged: confident in one
    # view, abstaining in the other.
    qA = float(np.nanquantile(pA[foot], 0.995)); qB = float(np.nanquantile(pB[foot], 0.995))
    lA = float(np.nanquantile(pA[foot], 0.60)); lB = float(np.nanquantile(pB[foot], 0.60))
    confA, abstB = pA >= qA, pB <= lB
    confB, abstA = pB >= qB, pA <= lA
    # whole 50x50 segments only, and never inside the 300 m kernel of a labelled pixel
    seg = np.zeros((H, W), bool)
    for by_ in range(0, H, 50):
        for bx_ in range(0, W, 50):
            sl = (slice(by_, by_ + 50), slice(bx_, bx_ + 50))
            if (confA & abstB)[sl].mean() >= 0.02 or (confB & abstA)[sl].mean() >= 0.02:
                seg[sl] = True
    near_lab = ndimage.binary_dilation(cat, np.ones((3, 3), bool), iterations=3)
    pl_pos = seg & confA & abstB & ~near_lab
    pl_neg = seg & confB & abstA & ~near_lab
    pseudo = dict(pseudo_positive_px=int(pl_pos.sum()), pseudo_negative_px=int(pl_neg.sum()),
                  segment_px=int(seg.sum()),
                  thresholds=dict(confident_A=qA, confident_B=qB, abstain_A=lA, abstain_B=lB),
                  rule="top-0.5% in one view & below-60th-percentile in the other, "
                       "whole 50x50 segments, outside 300 m of any labelled pixel")
    log(f"[pseudo] +{pseudo['pseudo_positive_px']} / -{pseudo['pseudo_negative_px']} "
        f"in {pseudo['segment_px']} px of segments")

    # one exchange round, fold 0 only (the pre-registered cheap test)
    held = fmap == 0
    bnd = ndimage.binary_dilation(held, np.ones((3, 3), bool), iterations=BUFFER_PX) | block_buf
    fit_ok = foot & ~bnd
    vis_cat = cat & ~held
    pos = fit_ok & vis_cat
    neg_pool = fit_ok & ~vis_cat & ~pl_pos & ~pl_neg
    ys, xs = np.nonzero(pos)
    rng = np.random.default_rng(SEED)
    ny_a, nx_a = np.nonzero(neg_pool)
    sel = rng.choice(ny_a.size, size=min(3 * ys.size, ny_a.size), replace=False)
    ny_a, nx_a = ny_a[sel], nx_a[sel]
    py, px_ = np.nonzero(pl_pos & fit_ok)
    qy, qx = np.nonzero(pl_neg & fit_ok)
    from sklearn.metrics import roc_auc_score
    exchange = {}
    for tag, extra_y, extra_x, extra_lab in (
            ("base", np.array([], int), np.array([], int), np.array([], int)),
            ("with_pseudo", np.concatenate([py, qy]), np.concatenate([px_, qx]),
             np.concatenate([np.ones(py.size, np.int8), np.zeros(qy.size, np.int8)]))):
        ty = np.concatenate([ys, ny_a, extra_y]); tx = np.concatenate([xs, nx_a, extra_x])
        yy = np.concatenate([np.ones(ys.size, np.int8), np.zeros(ny_a.size, np.int8), extra_lab])
        X = st.rows("B", ty, tx)
        m = HistGradientBoostingClassifier(max_iter=160, learning_rate=0.09, max_leaf_nodes=31,
                                           min_samples_leaf=60, l2_regularization=1.0,
                                           early_stopping=False, random_state=SEED)
        m.fit(X, yy)
        hp, hn = held & cat, held & ~cat & foot
        hy, hx = np.nonzero(hp | hn)
        Xh = st.rows("B", hy, hx)
        pr = m.predict_proba(Xh)[:, 1]
        # the label vector must follow the SAME pixel order as Xh.  np.nonzero returns
        # raster order; concatenating ones-then-zeros scores a shuffled label vector and
        # produced AUC 0.5186 where the identical model scores 0.6512.
        yh = hp[hy, hx].astype(np.int8)
        exchange[tag] = float(roc_auc_score(yh, pr))
        log(f"[pseudo] View B fold-0 held-out AUC {tag}: {exchange[tag]:.4f}")
    pseudo["fold0_viewB_auc"] = exchange
    pseudo["auc_delta"] = exchange["with_pseudo"] - exchange["base"]
    pseudo["verdict"] = "adopted" if pseudo["auc_delta"] > 0.002 else \
        "refuted: the exchange did not move held-out AUC by more than +0.002"
    save("h60_pseudo.json", pseudo)

    # ------------------------------------------------------------------- 5. strata
    b15 = rasterio.open(ROOT / "data/training_features.tif").read(15).astype(np.float32)
    b15[~np.isfinite(b15)] = np.nan
    # Quantile thresholds, not absolute ones: on this layer plan neither view ever reaches
    # p=0.90, so absolute 0.90/0.50 cut points left ONE pixel in the A-only stratum and the
    # stratum table described nothing.  "Confident" = the view's own top decile, "abstains"
    # = below its own 60th percentile.
    cA = float(np.nanquantile(pA[foot], 0.90)); cB = float(np.nanquantile(pB[foot], 0.90))
    aA = float(np.nanquantile(pA[foot], 0.60)); aB = float(np.nanquantile(pB[foot], 0.60))
    a_only = foot & (pA >= cA) & (pB <= aB)
    b_only = foot & (pB >= cB) & (pA <= aA)
    conc = foot & (pA >= cA) & (pB >= cB)
    strata = dict(thresholds=dict(confident_A=cA, confident_B=cB, abstain_A=aA, abstain_B=aB),
                  definition="confident = the view's own top decile; abstains = below its own "
                             "60th percentile; both computed over the footprint")
    for nm, m in (("A_only", a_only), ("B_only", b_only), ("concordant", conc)):
        v = b15[m]
        strata[nm] = dict(px=int(m.sum()),
                          median_depth_to_basement=float(np.nanmedian(v)) if np.isfinite(v).any() else None,
                          mean_depth_to_basement=float(np.nanmean(v)) if np.isfinite(v).any() else None)
    save("h60_strata.json", strata)
    log(f"[strata] A_only={strata['A_only']['px']} (median basement depth "
        f"{strata['A_only']['median_depth_to_basement']}) B_only={strata['B_only']['px']} "
        f"({strata['B_only']['median_depth_to_basement']})")

    # ------------------------------------------- 6/7. hide-and-recover + budget curve
    ed_vis_list = []
    arms = ["A_only", "B_only", "union_max", "A_where_B_abstains", "B_where_A_abstains",
            "disagreement_sum", "random"]
    BUDGETS = [10000, 20000, 37654, 60000, 100000]
    res = {a: {b: [] for b in BUDGETS} for a in arms}
    capture = {a: [] for a in arms}
    for f in range(N_FOLDS):
        held = fmap == f
        vis_cat = cat & ~held
        ed_vis = ndimage.distance_transform_edt(~vis_cat, sampling=100.0)
        # The emission-allowed mask and the training-exclusion mask are DIFFERENT objects.
        # AND-ing ~held into the allowed set makes the held-out truth unplaceable and
        # measured survival 0.000 -- the same defect knowledge/24 item 5 records.
        allow = foot & sub_ok & (ed_vis > RING_M)
        truth = held & cat
        surv = float((truth & allow).sum() / max(int(truth.sum()), 1))
        if surv < 0.9:
            raise SystemExit(f"fold {f}: held-out truth survival {surv:.3f} < 0.9 (mask bug)")
        log(f"  fold {f}: allowed={int(allow.sum())} truth={int(truth.sum())} survival={surv:.4f}")
        rng = np.random.default_rng(SEED + 1000 + f)
        fields = {
            "A_only": pA, "B_only": pB,
            "union_max": np.maximum(np.nan_to_num(pA, nan=-1), np.nan_to_num(pB, nan=-1)),
            "A_where_B_abstains": np.where(pB <= 0.5, np.nan_to_num(pA, nan=-1), -1.0),
            "B_where_A_abstains": np.where(pA <= 0.5, np.nan_to_num(pB, nan=-1), -1.0),
            "disagreement_sum": np.abs(np.nan_to_num(pA, nan=0) - np.nan_to_num(pB, nan=0)),
            "random": rng.random((H, W)).astype(np.float32),
        }
        for a, fld in fields.items():
            v = np.where(allow, np.nan_to_num(fld, nan=-1.0), -2.0).ravel()
            order = np.argsort(-v, kind="stable")
            for b in BUDGETS:
                sel = order[:b]
                pr = np.zeros(H * W, np.float32); pr[sel] = 1.0
                d = dti(pr.reshape(H, W).astype(np.float64), truth)
                res[a][b].append(float(d["dti"]))
            sel = order[:37654]
            pr = np.zeros(H * W, np.float32); pr[sel] = 1.0
            capture[a].append(float(dti(pr.reshape(H, W).astype(np.float64), truth)["tpw"]
                                / max(int(truth.sum()), 1)))
        ed_vis_list.append(dict(fold=f, allowed=int(allow.sum()), truth=int(truth.sum()),
                                survival=surv))
    holdout = dict(ring_m=RING_M, budgets=BUDGETS, folds=ed_vis_list,
                   dti={a: {str(b): res[a][b] for b in BUDGETS} for a in arms},
                   mean_dti={a: {str(b): float(np.mean(res[a][b])) for b in BUDGETS} for a in arms},
                   capture_at_37654={a: float(np.mean(capture[a])) for a in arms})
    wins = {}
    for a in arms:
        if a == "random":
            continue
        for b in BUDGETS:
            wins[f"{a}@{b}"] = int(sum(1 for i in range(N_FOLDS)
                                       if res[a][b][i] > res["random"][b][i]))
    holdout["fold_wins_vs_random"] = wins
    save("h60_holdout.json", holdout)
    log("[holdout] mean DTI")
    for a in arms:
        log("   " + " ".join(f"{b}:{holdout['mean_dti'][a][str(b)]:.5f}" for b in BUDGETS) + f"  <- {a}")

    # ------------------------------------------------------------------ 8. selection
    best = None
    for a in arms:
        if a == "random":
            continue
        for b in BUDGETS:
            key = f"{a}@{b}"
            if wins[key] >= MIN_FOLD_WINS:
                m = holdout["mean_dti"][a][str(b)]
                if best is None or m > best["mean_dti"]:
                    best = dict(arm=a, budget=b, mean_dti=m, fold_wins=wins[key])
    sel = dict(promotion_rule=f"arm must beat the matched-budget random control in >= {MIN_FOLD_WINS}"
                              f" of {N_FOLDS} hide-and-recover folds; among those, highest mean DTI",
               selected=best,
               random_mean_at_each_budget={str(b): holdout["mean_dti"]["random"][str(b)] for b in BUDGETS},
               note="hide-and-recover measures recovery of held-out CATALOGUE segments; the "
                    "competition truth is expert-labelled faults that are NOT in the catalogue, "
                    "so this is an instrument, not a score forecast")
    save("h60_selection.json", sel)
    log(f"[select] {json.dumps(best)}")
    np.savez(ROOT / "work/h60_fields.npz", pA=pA, pB=pB)
    log(f"[done] {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
