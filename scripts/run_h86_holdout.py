#!/usr/bin/env python3
"""H86: hide-and-recover HOLDOUT-DTI for the H83 structural-concordance + geothermal method.

Why this exists
---------------
H83 shipped a GeoTIFF (``submission/gems52-h83-structcon-geotherm-*.tif``) whose only "validation"
was an in-sample distance check against the full catalogue, and whose README claimed SUBMIT YES
without a holdout run. The repo's own rule (AGENTS.md) forbids a slot until a candidate beats the
comparable holdout best. This runner measures the H83 method under the shared hide-and-recover
protocol. It does not fork the method: it imports the H83 functions (structural concordance,
geothermal density, combiner, top-k emitter) from ``scripts/run_h83_structural_concordance.py``
and scores them with the shared ``gems52.evaluate_holdout`` / ``gems52.spatial`` modules.

Protocol (identical to H82's holdout stage)
-------------------------------------------
* Folds: ``gems52.spatial.folds(catalogue, footprint, buffer_px=80)`` (registry/h61 thresholds),
  whole catalogue components hidden per quadrant, label-blind quadrants.
* Per fold the catalogue fed to the method is the VISIBLE catalogue only (``fold['visible']``), and
  the 200 m collar is taken from the visible catalogue only. Held-out traces are never used.
* Emission: K = 9,400 dots per fold per arm (registry ``budget_dots_per_fold_per_arm``), pixels
  outside the fold region, on visible catalogue, or within 200 m of visible catalogue are not allowed.
* Scoring: ``gems52.evaluate_holdout.evaluate`` (pooled DTI, alpha 0.2, beta 0.8, 300 m triangular
  kernel) and ``pooled_summary`` (paired physical 20 km spatial-cluster bootstrap, 1000 draws).

Arms
----
* ``h83_topk``            H83 as built: combiner + unconstrained top-k (no 3 px spacing).
* ``h86_spaced``          H83 combiner + the repo's metric-aware 3 px spacing (``nodes.spacing_select``).
* ``concordance_only``    single-view baseline: structural concordance rank alone, no geothermal term,
                          same spacing. Tests whether the geothermal prior adds anything.
* ``random``              uniform random over the allowed set (floor).

Leakage canary: each feature's own AUC on the held-out truth inside the allowed set, alarm > 0.90.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rasterio  # noqa: E402

import run_h83_structural_concordance as H83  # noqa: E402  (shared H83 functions, not a copy)
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import nodes, spatial  # noqa: E402

SEED = 84001
K_FOLD = 9400
RING_PX = 2          # 200 m / 100 m pixels (registry catalogue_exclusion_m)
BUFFER_PX = 80       # registry buffer_px, label-blind quadrant split
CANARY_ALARM = 0.90
PRIMARY = "h86_spaced"
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
WELLS = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
OUT = ROOT / "evidence/h86_holdout.json"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def allowed_for(fold, valid):
    """Region, not visible, and outside the 200 m collar of the VISIBLE catalogue only."""
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (vd > RING_PX)


def rank01(a, mask):
    out = np.zeros(a.shape, np.float32)
    v = a[mask]
    out[mask] = (np.argsort(np.argsort(v)).astype(np.float32) / max(len(v) - 1, 1))
    return out


def main():
    t0 = time.time()
    with rasterio.open(LABELS) as ds, rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid != sample grid")
        labels = ds.read(1)
    cat = labels == 1
    # Eligible = all-19-band finite footprint AND the organiser domain (sample finite mask).
    # The two differ by 1,540 px (features valid, outside domain) and 3,073 px (domain, a band NaN);
    # registry/irregularities IR-52-002 documents this. We emit only where both hold.
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        domain = np.isfinite(ref.read(1))
    feat_valid = H83.footprint_all_bands(str(FEATURES))
    valid = feat_valid & domain
    log(f"eligible {int(valid.sum()):,} px (features {int(feat_valid.sum()):,}; domain {int(domain.sum()):,};"
        f" features-not-domain {int((feat_valid & ~domain).sum()):,}; domain-not-features {int((domain & ~feat_valid).sum()):,})")
    log(f"catalogue {int(cat.sum()):,} px")

    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positive px {withheld:,}")

    # ---- catalogue-free H83 ingredients: computed ONCE, no catalogue involved -------------
    conc, grav_rank, mag_rank, dem_rank, conc_count = H83.compute_structural_concordance(str(FEATURES), valid)
    log("structural concordance done")
    wells = H83.load_well_spring_data(str(WELLS))
    geo = H83.compute_geothermal_density(wells, valid, sigma_px=15.0)
    log(f"geothermal density done ({len(wells)} wells/springs)")
    cc_rank = rank01(conc, valid)
    gt_rank = rank01(geo, valid)

    terms = {a: None for a in ("h83_topk", "h86_spaced", "concordance_only", "random")}
    per_fold = []
    canary = {"concordance_rank": [], "geothermal_rank": [], "concordance_count": []}
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_for(fold, valid)
        # H83 combiner fed the VISIBLE catalogue only (labels==1 means visible here)
        vis_labels = fold["visible"].astype(np.int32)
        field = H83.combine_signals(conc, conc_count, grav_rank, mag_rank, dem_rank, geo, valid, vis_labels)
        cc_only = np.where(valid & (conc_count >= 1.0) & allowed, cc_rank, 0.0).astype(np.float32)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)

        emissions = {
            "h83_topk": H83.topk_emit(field, allowed, K_FOLD),
            "h86_spaced": nodes.spacing_select(field, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "concordance_only": nodes.spacing_select(cc_only, allowed, K_FOLD, min_px=3.0).astype(np.float32),
            "random": nodes.spacing_select(rnd, allowed, K_FOLD, min_px=3.0).astype(np.float32),
        }
        rec = dict(fold=f, withheld_positive_px=int((fold["truth"] & fold["region"]).sum()),
                   allowed_px=int(allowed.sum()), arms={})
        for arm, em in emissions.items():
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=res["dti"], placed=int(em.sum()), tpw=res["tpw"], fpw=res["fpw"], fnw=res["fnw"])
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        # leakage canary: each feature alone against the held-out truth inside the allowed set
        truth_in = (fold["truth"] & fold["region"])[allowed]
        if truth_in.any() and (~truth_in).any():
            for name, arr in (("concordance_rank", cc_rank), ("geothermal_rank", gt_rank),
                              ("concordance_count", conc_count.astype(np.float32))):
                auc = float(roc_auc_score(truth_in.astype(int), arr[allowed]))
                canary[name].append(dict(fold=f, auc=auc))
        rec["canary_done"] = True
        per_fold.append(rec)
        del field, cc_only, rnd, emissions

    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    canary_max = {k: max(x["auc"] for x in v) for k, v in canary.items()}
    canary_alarm = {k: v > CANARY_ALARM for k, v in canary_max.items()}

    reference = {  # HOLDOUT-DTI receipts from registry/evidence, same evaluator family (NOT re-run here)
        "H82 B_DVA2 (best prior holdout, evaluator gems52-pooled-hide-v1)": dict(dti=0.189200, ci95=[0.1679, 0.2091],
                                                                              source="evidence/h82_holdout.json"),
        "H82 single_B (single-view control)": dict(dti=0.174910, ci95=[0.1529, 0.1960], source="evidence/h82_holdout.json"),
    }
    out = dict(
        round="H86", stage="holdout", evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
        candidate=PRIMARY, budget_per_fold=K_FOLD, folds=len(folds), buffer_px=BUFFER_PX, ring_px=RING_PX,
        withheld_positive_px=withheld, eligible_px=int(valid.sum()),
        footprint_note="IR-52-002: eligible = 19-band finite AND organiser domain (sample finite)",
        pooled=summary, per_fold=per_fold,
        canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max, alarm=canary_alarm, per_fold=canary),
        reference_not_rerun=reference,
        inputs=dict(features_sha256=sha256(FEATURES), labels_sha256=sha256(LABELS), wells_sha256=sha256(WELLS),
                    wells_count=len(wells)),
        implementation_hashes=evaluator.implementation_hashes(),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a: round(summary["scores"][a]["dti"], 6) for a in terms}))
    log("CI: " + json.dumps({a: summary["scores"][a]["ci95"] for a in terms}))
    log("paired (candidate - arm): " + json.dumps({k: [round(v["delta"], 6), v["ci95"]] for k, v in summary["paired_differences"].items()}))
    log("canary max AUC: " + json.dumps(canary_max))
    log(f"wrote {OUT}")


if __name__ == "__main__":
    main()
