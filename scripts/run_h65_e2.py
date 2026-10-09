#!/usr/bin/env python3
"""H65 E2 -- R5-H2a: the band-10 seismicity valley-line detector on the shared holdout.

Frozen in ``knowledge/41_hypotheses_H65_preregistered.md`` §5 (amendment written after E1's
FAIL, before any E2 number; SHA-256 pinned in ``registry/h65_preregistration.json``).

Hypothesis R5-H2a: recent seismicity clusters on active structures, so a fault trace is a
valley line of the distance-to-earthquake field ``deq_n100a15`` (features band 10) -- the one
organiser band no script in this repository had ever read (verified against
``gems52_r5.layers``/``cotrain_r5`` view lists this session).  Convention-free form: the
directional-sector variant of knowledge/33 R5-H2 needs the sector azimuth, which is only
documented in an INGENIOUS docx this sandbox cannot fetch (knowledge/39 §1.3).

Instrument: exactly ``scripts/n2_holdout.py``'s shared harness -- holdout.make_folds
(mode "hide", 4 folds, buffer 4 px, prevalence 0.002, seed 0), pooled DTI (alpha 0.2,
beta 0.8, R 300 m triangular), 15,000-dot budget (the family credit-curve optimum
S* = 4|G|beta/(1-beta) ~ 16.7k at |G| ~ 14.1k, beta = 0.2284).  Arms: candidate field,
single_B (logistic on DEM/slope/radiometric ranks -- the committed comparable control),
uniform random.  Leakage canary: fold-level AUC of the candidate field alone at fit pixels
(alarm 0.90 -- a higher AUC is treated as leakage until proven otherwise, per the brief).

Every number printed/written is HOLDOUT-DTI (evaluator version, withheld positives, 95% CI).
Known caveat carried: knowledge/10 section 5 -- this instrument cannot rank novel fields.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import holdout, evaluate_holdout as evaluate, transform as T  # noqa: E402

DATA = ROOT / "data"
B_DEM, B_SLOPE, B_RAD, B_EQD = 12, 19, 6, 10
N_FOLDS, BUFFER, PREVALENCE, SEED = 4, 4, 0.002, 0
BUDGET, BLOCK, DRAWS = 15000, 200, 1000
SIGMA_PX = 1.0          # frozen smoothing of the valley field
PCT_KEEP = 90.0         # frozen ridge threshold percentile


def log(*a, **k):
    print(*a, flush=True, **k)


def load_band(b: int) -> np.ndarray:
    with rasterio.open(DATA / "training_features.tif") as s:
        a = s.read(b).astype(np.float64)
    a = np.where((a < -1e30) | ~np.isfinite(a), 0.0, a)
    return a


def valley_field(valid: np.ndarray) -> tuple[np.ndarray, dict]:
    """R5-H2a: v = 1 - exact-rank(band10); sigma-1 smooth; NMS along the gradient; p90 threshold.

    Amendment 2 (knowledge/41 §5): the template's ``rank01`` is an equal-width-bin CDF; band 10
    spans 0..4.96e6 m in-footprint and 66.6 % of the footprint falls in its first bin (measured),
    which empties the ridge field.  This round therefore ranks with an exact tie-aware rank; the
    shared tool is left untouched because committed receipts depend on it (deviation recorded).
    """
    from scipy.stats import rankdata

    b10 = load_band(B_EQD)
    r = np.full(valid.shape, np.nan, np.float32)
    r[valid] = (rankdata(b10[valid]) / float(valid.sum())).astype(np.float32)
    v = (1.0 - r).astype(np.float32)
    v[~valid] = 0.0
    vs = ndimage.gaussian_filter(v, sigma=SIGMA_PX).astype(np.float32)
    vs[~valid] = 0.0
    gy, gx = np.gradient(vs, T.PIXEL_M, T.PIXEL_M, edge_order=2)
    gmag = np.hypot(gy, gx)
    sy = np.divide(gy, gmag, out=np.zeros_like(gy), where=gmag > 0)
    sx = np.divide(gx, gmag, out=np.zeros_like(gx), where=gmag > 0)
    h, w = vs.shape
    rr, cc = np.rint(sy).astype(np.int64), np.rint(sx).astype(np.int64)
    r0, c0 = np.arange(h)[:, None], np.arange(w)[None, :]
    r1 = np.clip(r0 + rr, 0, h - 1)
    c1 = np.clip(c0 + cc, 0, w - 1)
    r2 = np.clip(r0 - rr, 0, h - 1)
    c2 = np.clip(c0 - cc, 0, w - 1)
    center = vs
    up = vs[r1, c1]
    dn = vs[r2, c2]
    ridge = (center >= up) & (center >= dn)
    thr = np.percentile(vs[valid], PCT_KEEP)
    field = np.where(ridge & (vs > thr) & valid, vs, np.float32(0.0))
    meta = dict(band=B_EQD, band_name="deq_n100a15", rank="exact tie-aware rankdata/footprint (amendment 2)", sigma_px=SIGMA_PX,
                threshold_percentile=PCT_KEEP, threshold_value=float(thr),
                ridge_px=int(((field > 0) & valid).sum()))
    return field.astype(np.float32), meta


def fit_predict_b(features_by_name, fit, pos_idx, neg_idx, region, valid, seed):
    """Logistic regression on the View-B ranks; the committed comparable control."""
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


def main() -> int:
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    valid = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    cat = np.zeros(tpl.shape, bool)
    cat[valid] = np.isfinite(lb[valid]) & (lb[valid] > 0.5)

    log("loading bands and building the R5-H2a field...")
    dem, slope, rad = load_band(B_DEM), load_band(B_SLOPE), load_band(B_RAD)
    rdem, rslope, rrad = (T.rank01(x, valid) for x in (dem, slope, rad))
    del dem, slope, rad
    b_features = {"dem": rdem, "slope": rslope, "rad": rrad}
    cand, meta = valley_field(valid)
    log(f"field meta: {meta}  footprint={int(valid.sum())} catalogue={int(cat.sum())}")

    folds = holdout.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER,
                               prevalence=PREVALENCE, seed=SEED, mode="hide")
    for f in folds:
        log(f"  fold {f['fold']}: n_truth={f['n_truth']} n_held={f['n_held']}")

    terms = None
    canary = []
    per_fold = []
    rng_arm = np.random.default_rng(20261009)
    random_field = rng_arm.random(valid.shape).astype(np.float32)
    for fold in folds:
        allowed = valid & ~fold["visible"] & fold["region"]
        fitm = fold["fit"]
        pos = np.flatnonzero(cat & fitm)
        negpool = np.flatnonzero(~cat & fitm)
        rng = np.random.default_rng(SEED + fold["fold"])
        neg = rng.choice(negpool, size=min(len(negpool), 40 * max(len(pos), 1)), replace=False)

        # leakage canary: the candidate field ALONE at the fold's fit pixels
        vals = cand.ravel()
        canary.append(float(roc_auc_score(
            np.concatenate([np.ones(pos.size), np.zeros(neg.size)]),
            np.concatenate([vals[pos], vals[neg]]))))

        fb = fit_predict_b(b_features, fitm, pos, neg, fold["region"], valid, SEED + fold["fold"])
        em_c = holdout.emit_topk(cand, allowed, BUDGET)
        em_b = holdout.emit_topk(fb, allowed, BUDGET)
        em_r = holdout.emit_topk(random_field, allowed, BUDGET)

        _, tc = evaluate.evaluate(em_c, fold, valid, block_side=BLOCK)
        _, tb = evaluate.evaluate(em_b, fold, valid, block_side=BLOCK)
        _, tr = evaluate.evaluate(em_r, fold, valid, block_side=BLOCK)
        if terms is None:
            terms = {"candidate": np.zeros_like(tc), "singleB": np.zeros_like(tb),
                     "random": np.zeros_like(tr)}
        terms["candidate"] += tc
        terms["singleB"] += tb
        terms["random"] += tr
        for nm, em, t in (("candidate", em_c, tc), ("singleB", em_b, tb), ("random", em_r, tr)):
            sc = holdout.score(em, fold, valid, extra=False)
            per_fold.append(dict(fold=fold["fold"], arm=nm, dti=round(sc["dti"], 5),
                                 emitted=int(sc["emitted"])))
        log(f"  fold {fold['fold']} done; canary AUC={canary[-1]:.4f}")

    pooled = evaluate.pooled_summary(terms, draws=DRAWS, seed=520810, candidate="candidate")
    canary_alarm = bool(max(canary) > 0.90)
    out = dict(
        round="H65", stage="E2-holdout", finished_utc=None,
        evidence_class="HOLDOUT-DTI (defective board predictor; necessary-not-sufficient gate)",
        evaluator_version=pooled.get("evaluator_version", "gems52-pooled-hide-v1"),
        hypothesis="R5-H2a: valley lines of the band-10 distance-to-earthquake rank field "
                   "(sigma-1 smooth, gradient NMS, p90 threshold)",
        control="singleB: logistic regression on View-B ranks (DEM, slope, radiometric)",
        random_arm="uniform random field, matched budget",
        budget=int(BUDGET), block_side=BLOCK, n_folds=N_FOLDS, prevalence=PREVALENCE,
        mode="hide", field_meta=meta,
        leakage_canary=dict(per_fold_auc=[round(a, 5) for a in canary],
                            max_auc=round(max(canary), 5), alarm_090=canary_alarm,
                            rule="AUC > 0.90 means leakage until proven otherwise"),
        reference_bar=dict(arm="single_B committed (H61/H64 receipt)",
                           value=0.174517,
                           label="HOLDOUT-DTI, evaluator gems52-pooled-hide-v1, "
                                 "53,186 withheld positives"),
        pooled=pooled, per_fold=per_fold,
        caveats=["knowledge/10 section 5: this instrument cannot rank novel fields",
                 "holdout withholds ~1.04% of the footprint vs ~0.12-0.25% true prevalence"],
    )
    (ROOT / "work/h65").mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/h65_e2_holdout.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    log("\n=== POOLED HOLDOUT-DTI (evaluator gems52-pooled-hide-v1) ===")
    for name, s in pooled["scores"].items():
        log(f"  {name:10s} DTI={s['dti']:.5f}  95%CI=[{s['ci95'][0]:.5f},{s['ci95'][1]:.5f}]  "
            f"withheld={s['withheld_positive_pixels']}")
    bd = pooled["paired_differences"].get("singleB")
    if bd:
        log(f"  paired delta candidate-singleB = {bd['delta']:.5f}  "
            f"95%CI=[{bd['ci95'][0]:.5f},{bd['ci95'][1]:.5f}]")
    log(f"  canary max AUC = {max(canary):.4f} (alarm at 0.90: {canary_alarm})")
    log("wrote evidence/h65_e2_holdout.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
