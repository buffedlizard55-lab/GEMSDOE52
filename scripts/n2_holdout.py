#!/usr/bin/env python3
"""H60C session -- NEW-hypothesis holdout validation (top candidate = N2).

This validates ONE of the three genuinely-new hypotheses proposed in
knowledge/30_hypotheses_h60c_new.md on the shared spatially-blocked hide-and-recover
holdout, paired against the single-B (surface) control that is the current
comparable holdout best.  It reuses the template's folds/evaluator (holdout.make_folds,
holdout.emit_topk, evaluate.evaluate, evaluate.pooled_summary) -- no private fork.

Every number below is labelled HOLDOUT-DTI (evaluator version, withheld positive pixels,
95% CI).  The simulator is a known-defective board predictor (Spearman ~ -0.10 with the
organiser's scores, R4 + knowledge/10), so a holdout win is a NECESSARY-but-not-sufficient
gate; the organiser-tied instrument is the set algebra in scripts/h60_identify.py.

  Control  singleB : logistic regression on the three View-B bands (DEM, slope, radiometric).
  Candidate N2      : pixel-level, orientation-consistent EDGE-EDGE coincidence of the
                      DEM edge and the radiometric edge (magnitude min x axial orientation
                      agreement) -- a 2-way independent-edge coincidence, NOT view-level
                      disagreement (CTD5/H56/H59) and NOT cross-team corroboration (H60-A).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import holdout, evaluate_holdout as evaluate, transform as T  # noqa: E402

DATA = ROOT / "data"
B_DEM, B_SLOPE, B_RAD = 12, 19, 6          # View-B bands (H60C band plan)
N_FOLDS, BUFFER, PREVALENCE, SEED = 4, 4, 0.002, 0
BUDGET, BLOCK, DRAWS = 15000, 200, 1000


def load_band(b):
    with rasterio.open(DATA / "training_features.tif") as s:
        a = s.read(b).astype(np.float64)
    # the official sentinel is float32 min (-3.4e38), which is FINITE -- real band values are
    # >= 0, so anything below -1e30 (or non-finite) is the outside-footprint sentinel.
    a = np.where((a < -1e30) | ~np.isfinite(a), 0.0, a)
    return a


def grad(a, valid):
    f = T.fill_outside(a, valid)
    gy, gx = np.gradient(f.astype(np.float32), T.PIXEL_M, T.PIXEL_M, edge_order=2)
    out = np.sqrt(np.nan_to_num(gy ** 2 + gx ** 2)) .astype(np.float32)
    out[~valid] = 0.0
    ang = np.arctan2(np.nan_to_num(gy), np.nan_to_num(gx))
    return out, ang


def n2_field(dem, rad, valid):
    """Pixel-level DEM-edge x radiometric-edge coincidence, orientation-consistent.

    magnitude term = min(rank(DEM edge), rank(rad edge))      (both must be strong edges)
    agreement term = (1 + cos(2*(ang_dem - ang_rad))) / 2     (axial, 0..1; 1 when aligned)
    field = magnitude term * agreement term                    (edge-edge, consistent strike)
    """
    gm, am = grad(dem, valid)
    gr, ar = grad(rad, valid)
    rgm = T.rank01(gm, valid)
    rgr = T.rank01(gr, valid)
    mag = np.minimum(rgm, rgr)                                   # both must be an edge
    d2 = 2.0 * (am - ar)
    agree = 0.5 * (1.0 + np.cos(d2))                             # axial orientation agreement
    field = np.nan_to_num(mag * agree, nan=0.0)
    field[~valid] = 0.0
    return field


def fit_predict_b(features_by_name, fit, pos_idx, neg_idx, region, valid, seed):
    """Logistic regression on the View-B bands; return the probability field over `region`."""
    names = list(features_by_name)
    allidx = np.flatnonzero(region)
    X = np.column_stack([features_by_name[nm].ravel()[allidx] for nm in names])
    X = np.nan_to_num(X, nan=0.0)
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-6
    Z = (X - mu) / sd
    y = np.zeros(allidx.size, dtype=int)
    y[np.isin(allidx, pos_idx)] = 1
    sel = np.where((y == 1) | (np.isin(allidx, neg_idx)))[0]
    clf = LogisticRegression(C=1.0, max_iter=400, class_weight="balanced", random_state=seed)
    clf.fit(Z[sel], y[sel])
    prob = clf.predict_proba(Z)[:, 1]
    field = np.zeros(valid.size, dtype=np.float32)
    field[allidx] = prob
    return field.reshape(valid.shape)


def main():
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    valid = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    cat = np.zeros(tpl.shape, bool)
    cat[valid] = np.isfinite(lb[valid]) & (lb[valid] > 0.5)

    print("loading bands...")
    dem, slope, rad = load_band(B_DEM), load_band(B_SLOPE), load_band(B_RAD)
    rdem, rslope, rrad = (T.rank01(x, valid) for x in (dem, slope, rad))
    b_features = {"dem": rdem, "slope": rslope, "rad": rrad}
    n2 = n2_field(dem, rad, valid)
    print(f"footprint={int(valid.sum())} catalogue={int(cat.sum())}")

    folds = holdout.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER,
                               prevalence=PREVALENCE, seed=SEED, mode="hide")
    for f in folds:
        print(f"  fold {f['fold']}: n_truth={f['n_truth']} n_held={f['n_held']}")

    terms = None
    per_fold = []
    for fold in folds:
        allowed = valid & ~fold["visible"] & fold["region"]
        fitm = fold["fit"]
        pos = np.flatnonzero(cat & fitm)
        negpool = np.flatnonzero(~cat & fitm)
        rng = np.random.default_rng(SEED + fold["fold"])
        neg = rng.choice(negpool, size=min(len(negpool), 40 * max(len(pos), 1)), replace=False)

        fb = fit_predict_b(b_features, fitm, pos, neg, fold["region"], valid, SEED + fold["fold"])
        em_b = holdout.emit_topk(fb, allowed, BUDGET)
        em_n = holdout.emit_topk(n2, allowed, BUDGET)

        _, tb = evaluate.evaluate(em_b, fold, valid, block_side=BLOCK)
        _, tn = evaluate.evaluate(em_n, fold, valid, block_side=BLOCK)
        if terms is None:
            terms = {"singleB": np.zeros_like(tb), "N2": np.zeros_like(tn)}
        terms["singleB"] += tb
        terms["N2"] += tn
        rb = holdout.score(em_b, fold, valid, extra=False)
        rn = holdout.score(em_n, fold, valid, extra=False)
        per_fold.append(dict(fold=fold["fold"],
                             singleB=dict(dti=round(rb["dti"], 5), emitted=rb["emitted"]),
                             N2=dict(dti=round(rn["dti"], 5), emitted=rn["emitted"])))
        print(f"  fold {fold['fold']}: singleB dti={rb['dti']:.4f} (em {rb['emitted']}) "
              f"N2 dti={rn['dti']:.4f} (em {rn['emitted']})")

    pooled = evaluate.pooled_summary(terms, draws=DRAWS, seed=520810, candidate="N2")
    out = dict(
        evidence_class="HOLDOUT-DTI (defective board predictor; necessary-not-sufficient gate)",
        hypothesis="N2: pixel-level DEM-edge x radiometric-edge orientation-consistent coincidence",
        control="singleB: logistic regression on View-B bands (DEM, slope, radiometric)",
        budget=int(BUDGET), block_side=BLOCK, n_folds=N_FOLDS, prevalence=PREVALENCE,
        mode="hide",
        prior_ctd5_singleB_ref="0.106749 (CTD5, exploratory legacy-v1; different feature stack/folds)",
        pooled=pooled, per_fold=per_fold,
        verdict_note=("N2 must beat singleB AND the prior 0.1067 holdout best to be promotable; "
                      "even a holdout win does not authorise a slot (simulator defect + lane "
                      "uniqueness gate)."),
    )
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "h60c_n2_holdout.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print("\n=== POOLED HOLDOUT-DTI (evaluator", pooled["evaluator_version"], ") ===")
    for name, s in pooled["scores"].items():
        print(f"  {name:8s} DTI={s['dti']:.5f}  95%CI=[{s['ci95'][0]:.5f},{s['ci95'][1]:.5f}]  "
              f"withheld={s['withheld_positive_pixels']}  TPw={s['tpw']:.1f} FPw={s['fpw']:.1f} FNw={s['fnw']:.1f}")
    bd = pooled["paired_differences"].get("singleB")
    if bd:
        print(f"  paired delta N2-singleB = {bd['delta']:.5f}  95%CI=[{bd['ci95'][0]:.5f},{bd['ci95'][1]:.5f}]")
    print("wrote evidence/h60c_n2_holdout.json")


if __name__ == "__main__":
    main()
