#!/usr/bin/env python3
"""H87-L: negative-clearance leakage audit of the co-training lane (shared H60D instrument).

Frozen in ``registry/h87_negclear_preregistration.json`` before this file was run.

Question: the shipped path (``run_h60d_cotrain.fit_and_predict`` -> ``gems52.h57.labelled_pixels``)
draws training negatives from the WHOLE footprint and clears them by 5 px from the FULL catalogue,
which includes the held-out fold's truth. Held-out fault neighbourhoods are therefore never sampled
as negatives, and held-out region labels shape training. This runner refits View A and View B per
fold with a clean sampler (fit region only, catalogue = fit catalogue only) and compares holdout
DTI on the same folds, the same scorer and the same budgets.

Nothing is copied: every function is imported from ``run_h60d_cotrain`` / ``gems52``. The only
difference between arms is the ``cat``/``valid`` arguments handed to ``fit_and_predict``.

Outputs: ``evidence/h90_negclear_audit.json`` (receipt) and stdout log.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h60d_cotrain as R  # noqa: E402  (shared fit / score functions, not a copy)
from gems52 import grid as G  # noqa: E402
from gems52 import h57  # noqa: E402
from gems52 import h60d  # noqa: E402
from gems52 import holdout as HO  # noqa: E402
from gems52 import metric as M  # noqa: E402

OUT = ROOT / "evidence/h90_negclear_audit.json"
BUDGETS = (37654, 15000)
PRIMARY_K = 37654


def log(m: str) -> None:
    print(f"[h90-L {time.strftime('%H:%M:%S')}] {m}", flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from(R.DATA / "training_features.tif", bands="all")
    with rasterio.open(R.DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    layers = h57.Layers(str(R.WORK))
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=R.SEED,
                          mode="hide")
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    # Shipped OOF fields come from the H60D run in the same work directory (identical code path).
    pa_sh = np.nan_to_num(np.load(R.WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb_sh = np.nan_to_num(np.load(R.WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    log(f"loaded shipped OOF fields; {len(folds)} folds; footprint {int(valid.sum())} px")

    per_fold = []
    for f in folds:
        fit, reg = f["fit"], f["region"]
        fold = f["fold"]
        visible = f["visible"]
        blocked = ndimage.binary_dilation(visible & valid, iterations=h57.CORRIDOR_PX)
        legal = reg & permitted & ~blocked
        truth = f["truth"] & reg & valid

        # CLEAN arm: positives and negatives both from the fit region; clearance from fit catalogue.
        cat_fit = cat & fit
        _, pa_cl = R.fit_and_predict(layers, idx_a, cat_fit, valid & fit, fit, R.SEED + fold,
                                     f"A-clean/f{fold}")
        _, pb_cl = R.fit_and_predict(layers, idx_b, cat_fit, valid & fit, fit, R.SEED + fold,
                                     f"B-clean/f{fold}")
        pa_cl = np.where(reg, pa_cl, 0.0).astype(np.float32)
        pb_cl = np.where(reg, pb_cl, 0.0).astype(np.float32)

        # SHIPPED arm restricted to this fold's region (OOF fields hold each fold's own region).
        pa_s = np.where(reg, pa_sh, 0.0).astype(np.float32)
        pb_s = np.where(reg, pb_sh, 0.0).astype(np.float32)

        arms = {
            "shipped": dict(view_A=pa_s, view_B=pb_s, clf_union=np.maximum(pa_s, pb_s),
                            dis_contrast=h60d.dis_contrast(pa_s, pb_s)),
            "clean": dict(view_A=pa_cl, view_B=pb_cl, clf_union=np.maximum(pa_cl, pb_cl),
                          dis_contrast=h60d.dis_contrast(pa_cl, pb_cl)),
        }

        rec = dict(fold=int(fold), n_truth=int(f["n_truth"]), legal_px=int(legal.sum()),
                   fit_px=int(fit.sum()), cat_in_fit=int(cat_fit.sum()),
                   negatives_clean=int((valid & fit & ~ndimage.binary_dilation(cat_fit, iterations=h57.NEG_CLEAR_PX)).sum()),
                   negatives_shipped=int((valid & ~ndimage.binary_dilation(cat, iterations=h57.NEG_CLEAR_PX)).sum()),
                   arms={})
        rng = np.random.default_rng(R.SEED + fold)
        for k in BUDGETS:
            take = rng.choice(np.flatnonzero(legal.ravel()), min(k, int(legal.sum())), replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = np.where(reg, rnd.astype(np.float32), 0.0)
            p = HO.mask_visible(p, visible & valid)
            rr = M.dti(p, truth)
            rec["arms"].setdefault("random", {})[str(k)] = dict(
                dti=float(rr["dti"]), tpw=float(rr["tpw"]), fpw=float(rr["fpw"]),
                fnw=float(rr["fnw"]), n_truth=int(rr["n_truth"]))
        for arm, fields in arms.items():
            for name, fld in fields.items():
                # canary: the field alone against held-out truth over the fold region, exactly as
                # run_h60d_cotrain.canary_report does. (The prereg text said "legal set"; the legal
                # set excludes every catalogue pixel by construction, so truth is never inside it and
                # the AUC is undefined there. Deviation recorded in the receipt, IR-H90-004.)
                auc = h60d.layer_auc_canary(fld, truth, reg)
                for k in BUDGETS:
                    r = R.score_cell(fld, legal, truth, reg, valid, visible, k)
                    rec["arms"].setdefault(f"{arm}:{name}", {})[str(k)] = dict(
                        dti=float(r["dti"]), tpw=float(r["tpw"]), fpw=float(r["fpw"]),
                        fnw=float(r["fnw"]), n_truth=int(r["n_truth"]), emitted=int(r["emitted"]),
                        canary_auc=float(auc) if k == PRIMARY_K else None)
        per_fold.append(rec)
        log(f"fold {fold}: " + ", ".join(
            f"{a}:{n}={rec['arms'][f'{a}:{n}'][str(PRIMARY_K)]['dti']:.4f}"
            for a in arms for n in arms[a]))

    # ---- pooled read + paired fold bootstrap ------------------------------------------------
    names = [f"{a}:{n}" for a in ("shipped", "clean") for n in ("view_A", "view_B", "clf_union",
                                                                  "dis_contrast")] + ["random"]
    pooled, ci = {}, {}
    for nm in names:
        for k in BUDGETS:
            terms = [pf["arms"][nm][str(k)] for pf in per_fold]
            pooled.setdefault(nm, {})[str(k)] = h60d.pooled_dti(terms)
            ci.setdefault(nm, {})[str(k)] = h60d.bootstrap_ci([t["dti"] for t in terms])
    paired = {}
    for n in ("view_A", "view_B", "clf_union", "dis_contrast"):
        for k in BUDGETS:
            d = [pf["arms"][f"clean:{n}"][str(k)]["dti"] - pf["arms"][f"shipped:{n}"][str(k)]["dti"]
                 for pf in per_fold]
            paired[f"clean_minus_shipped:{n}:{k}"] = dict(per_fold=[round(x, 6) for x in d],
                                                          **h60d.bootstrap_ci(d))
    for k in BUDGETS:
        d = [pf["arms"]["clean:view_B"][str(k)]["dti"] - pf["arms"]["random"][str(k)]["dti"]
             for pf in per_fold]
        paired[f"clean_view_B_minus_random:{k}"] = dict(per_fold=[round(x, 6) for x in d],
                                                        **h60d.bootstrap_ci(d))

    primary = {n: paired[f"clean_minus_shipped:{n}:{PRIMARY_K}"] for n in ("view_A", "view_B")}
    leak_confirmed = all(v["ci_hi"] is not None and v["ci_hi"] < 0 for v in primary.values())
    no_leak = all(v["ci_lo"] is not None and v["ci_hi"] is not None and v["ci_lo"] <= 0 <= v["ci_hi"]
                  for v in primary.values())
    verdict = ("LEAK CONFIRMED: clean sampler lowers holdout DTI for both views"
               if leak_confirmed else
               "NO LEAK DETECTED: CI spans zero for both views" if no_leak else
               "MIXED: see paired CIs (not a clean leak call; no promotion either way)")

    receipt = dict(
        round="H87-L", preregistration="registry/h87_negclear_preregistration.json",
        preregistration_sha256=sha256(ROOT / "registry/h87_negclear_preregistration.json"),
        seed=R.SEED, runtime_s=round(time.time() - t0, 1),
        instrument=dict(folds="HO.make_folds hide n=4 buffer 4 prevalence 0.002",
                        scorer="gems52.metric.dti via run_h60d_cotrain.score_cell",
                        budgets=list(BUDGETS), alpha=0.2, beta=0.8, kernel_m=300),
        withheld_positives=int(sum(pf["n_truth"] for pf in per_fold)),
        per_fold=[dict(fold=pf["fold"], n_truth=pf["n_truth"], legal_px=pf["legal_px"],
                       fit_px=pf["fit_px"], cat_in_fit=pf["cat_in_fit"],
                       negatives_clean=pf["negatives_clean"],
                       negatives_shipped=pf["negatives_shipped"]) for pf in per_fold],
        pooled_dti=pooled, fold_bootstrap_ci=ci, paired=paired,
        primary_contrast=f"clean minus shipped at {PRIMARY_K} px",
        verdict=verdict,
        canary_bar=0.90,
        canary_max_auc=max(pf["arms"][f"{a}:{n}"][str(PRIMARY_K)]["canary_auc"]
                           for pf in per_fold for a in ("shipped", "clean")
                           for n in ("view_A", "view_B", "clf_union", "dis_contrast")),
        slots_used=0,
        hashes=dict(h60d_py=sha256(ROOT / "src/gems52/h60d.py"),
                    h57_py=sha256(ROOT / "src/gems52/h57.py"),
                    run_h60d_py=sha256(ROOT / "scripts/run_h60d_cotrain.py")),
        caveat=("Fold-bootstrap CIs over 4 folds are coarse. Shipped OOF fields are read from the "
                "H60D reproduction in work/h60; the clean arm is the only refit."),
        deviations=["canary region = fold region (not the legal set): the legal set holds no truth pixel "
                    "by construction (permitted = valid & ~dilate(full catalogue, 2 px)), so the prereg "
                    "wording gave an undefined AUC (IR-H90-004)."],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nan_paths = []

    def _clean(o, path=""):
        # JSON cannot hold NaN/inf; a NaN here means an undefined statistic, recorded as null
        # and listed, never silently replaced by a number.
        if isinstance(o, dict):
            return {k: _clean(v, f"{path}/{k}") for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(v, f"{path}[{i}]") for i, v in enumerate(o)]
        if isinstance(o, float) and not np.isfinite(o):
            nan_paths.append(path)
            return None
        return o

    receipt = _clean(receipt)
    receipt["undefined_statistics_set_to_null"] = nan_paths
    h60d.write_json(OUT, receipt)
    log(f"verdict: {verdict}")
    for kk, v in primary.items():
        log(f"primary {kk}: clean-shipped = {v.get('mean', float('nan')):+.6f} "
            f"[{v['ci_lo']:+.6f}, {v['ci_hi']:+.6f}]")
    log(f"wrote {OUT.name} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
