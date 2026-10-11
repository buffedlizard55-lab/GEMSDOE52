#!/usr/bin/env python3
"""H88 extra arm: score the *currently advertised candidate's own field* on the lane's instrument.

``evidence/h87_build.json`` admits ``evidence_class = "HOLDOUT-DTI (not yet run; this is the build
receipt, not a score)"`` — the artefact the site offers for download has no holdout number at all.
This script supplies that missing number on the *same* folds, the *same* 200 m collar, the *same*
per-fold budget and the *same* evaluator the H88 lane uses, so the incumbent field and the H88
primary arm can be compared on one instrument instead of argued about.

Reuse, not fork
---------------
The view fields are imported from ``scripts/build_h87_cotrain_wavelength.py``; there is exactly one
implementation of the H87 field in the repository.  Folds, evaluator, pooler and placer are the
shared tools (``gems52.spatial.folds``, ``gems52.evaluate_holdout``, ``gems52.nodes``).

Why the field may be scored but the shipped raster may not
----------------------------------------------------------
``compute_view_a``/``compute_view_b``/``compute_disagreement_field`` never read ``labels.tif``; the
catalogue enters the H87 build only as a 200 m collar, and each fold's ``allowed`` mask rebuilds
that collar from *visible* faults only.  The field is therefore fold-blind and may be scored.  The
shipped 37,654-px raster may not: it was collared against the full catalogue, so a dot sitting on a
component that this fold hides would earn credit the fold never offered.  Under the lane's leakage
rule the raster is not scored here; only its field is.

Output: ``evidence/h88_h87field_holdout.json`` (HOLDOUT-DTI), same schema as ``h88_holdout.json``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import build_h87_cotrain_wavelength as H87                                     # noqa: E402
from gems52 import evaluate_holdout as evaluator                                # noqa: E402
from gems52 import nodes, spatial                                              # noqa: E402

SEED = 61052
K_FOLD = 9400
BUDGET_CURVE = (4700, 6250, 9400)
BUFFER_PX = 80
RING_PX = 2
EVID = ROOT / "evidence"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _rank01(vals: np.ndarray) -> np.ndarray:
    from scipy.stats import rankdata
    if vals.size == 0:
        return np.zeros(vals.shape, np.float32)
    return ((rankdata(vals, method="average") - 0.5) / float(vals.size)).astype(np.float32)


def main() -> int:
    t0 = time.time()
    with rasterio.open(H87.SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
    with rasterio.open(H87.LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    eligible = H87.footprint_all_bands(str(H87.FEATURES)) & domain
    log(f"footprint {int(eligible.sum()):,} px; catalogue {int(cat.sum()):,} px")

    view_a = H87.compute_view_a(str(H87.FEATURES), eligible)
    log("view A built")
    view_b = H87.compute_view_b(str(H87.FEATURES), str(H87.GEODAWN_RAD), str(H87.GEODAWN_EXT), eligible)
    log("view B built")
    dis = H87.compute_disagreement_field(view_a, view_b, eligible, cat)
    pixel_r = float(np.corrcoef(view_a[eligible], view_b[eligible])[0, 1])
    log(f"H87 disagreement field built; pixel Pearson r(A, B) over the footprint = {pixel_r:.4f}")
    # the build's own placement is a rank of the clipped disagreement field; reproduce that ranking
    # on the positive support only, exactly as H87's nodes.spacing_select(field, allowed, ...) saw it.
    dis_pos = np.where(dis > 0, dis, 0.0).astype(np.float32)
    del view_a, view_b

    terms, rand_terms, per_fold = None, None, []
    curve_terms = {f'h87_field@k{k}': None for k in BUDGET_CURVE}
    for fold in spatial.folds(cat, eligible, buffer_px=BUFFER_PX):
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        visd = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & eligible & ~fold["visible"] & (visd > RING_PX)
        ai = np.flatnonzero(allowed.ravel())
        grid = np.zeros(dis.shape, np.float32)
        grid.ravel()[ai] = _rank01(dis_pos.ravel()[ai])
        rec = dict(fold=f, allowed_px=int(ai.size),
                   truth_px=int((fold["truth"] & fold["region"]).sum()), arms={})
        em = nodes.spacing_select(grid, allowed & (grid > 0), K_FOLD, min_px=3.0).astype(np.float32)
        res, term = evaluator.evaluate(em, fold, eligible, block_side=200)
        terms = term if terms is None else terms + term
        rec["arms"]["h87_field"] = dict(dti=round(res["dti"], 6), placed=int(em.sum()),
                                        tpw=round(res["tpw"], 3), fpw=round(res["fpw"], 3),
                                        fnw=round(res["fnw"], 3))
        log(f"fold {f} h87_field: DTI {res['dti']:.6f} placed {int(em.sum())} "
            f"TPw {res['tpw']:.0f} FPw {res['fpw']:.0f}")
        # same-folds random control, so the pooled pairing has a comparator (mirrors the lane's arm)
        rnd = np.zeros(dis.shape, np.float32)
        rnd.ravel()[ai] = rng.random(ai.size, dtype=np.float32)
        er = nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0).astype(np.float32)
        resr, termr = evaluator.evaluate(er, fold, eligible, block_side=200)
        rand_terms = termr if rand_terms is None else rand_terms + termr
        rec["arms"]["random"] = dict(dti=round(resr["dti"], 6), placed=int(er.sum()),
                                     tpw=round(resr["tpw"], 3), fpw=round(resr["fpw"], 3))
        log(f"fold {f} random: DTI {resr['dti']:.6f} placed {int(er.sum())} "
            f"TPw {resr['tpw']:.0f} FPw {resr['fpw']:.0f}")
        del er
        for k in BUDGET_CURVE:
            emk = nodes.spacing_select(grid, allowed & (grid > 0), k, min_px=3.0).astype(np.float32)
            resk, termk = evaluator.evaluate(emk, fold, eligible, block_side=200)
            ck = f"h87_field@k{k}"
            curve_terms[ck] = termk if curve_terms[ck] is None else curve_terms[ck] + termk
            rec["arms"][f"h87_field@k{k}"] = dict(dti=round(resk["dti"], 6), placed=int(emk.sum()),
                                                  tpw=round(resk["tpw"], 3), fpw=round(resk["fpw"], 3))
            log(f"fold {f} h87_field@k{k}: DTI {resk['dti']:.6f} placed {int(emk.sum())} "
                f"TPw {resk['tpw']:.0f} FPw {resk['fpw']:.0f}")
        per_fold.append(rec)
        del grid, em, emk, rnd

    pooled = evaluator.pooled_summary(dict(h87_field=terms, random=rand_terms), draws=1000,
                                      seed=SEED, candidate="h87_field")
    curve = evaluator.pooled_summary(dict(curve_terms), draws=1000, seed=SEED, candidate="h87_field@k4700")
    out = dict(stage="h87_incumbent_field_holdout",
               started_utc=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
               evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
               purpose=("score the advertised H87 candidate's own ranking field on the H88 folds so the "
                        "incumbent and the H88 primary arm are compared on one instrument"),
               arm_definition=dict(
                   h87_field=("H87 disagreement field (A-confident x B-abstains boost, clipped at zero), "
                              "rank-normalised inside the fold's allowed set, emitted as a 3 px-spaced "
                              "dot set at the lane's per-fold budget")),
               note=("The field is catalogue-free; only the placement collar uses the catalogue, and the "
                     "per-fold allowed mask rebuilds it from visible faults. The shipped raster itself is "
                     "not scored (it was collared against the full catalogue)."),
               seeds=dict(fit=SEED), buffer_px=BUFFER_PX, ring_px=RING_PX,
               budget_per_fold=K_FOLD, budget_curve=list(BUDGET_CURVE),
               pixel_pearson_r_views=pixel_r, pooled=pooled, budget_curve_pooled=curve,
               per_fold=per_fold, seconds=round(time.time() - t0, 1))
    (EVID / "h88_h87field_holdout.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a: round(pooled["scores"][a]["dti"], 6) for a in pooled["scores"]}))
    log("curve: " + json.dumps({f"k{k}": round(v["dti"], 6) for k, v in curve["scores"].items()}))
    log(f"wrote {EVID/'h88_h87field_holdout.json'} in {out['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
