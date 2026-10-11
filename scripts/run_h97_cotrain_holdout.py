#!/usr/bin/env python3
"""H97 experiment 1+2: co-training views on two instruments, plus the mass-lever sweep.

Why this exists
---------------
``knowledge/76`` names the next step explicitly: the H83 off-catalogue instrument over-rewards
recall (55,562 px of truth against an incumbent |G| bracket of 14,089 px), so it *cannot* be used to
choose the emitted budget, and no instrument in this repository could test the **mass lever** — the
measured monotone decrease of board score with emitted mass (Spearman(mass, score) = -0.928 over the
twelve restored owner-reported scores).  This runner builds the prevalence-matched instrument
(``gems52.h97.offcatalogue_truth``) and measures DTI as a function of the budget K for the lane's
disagreement field, with a matched random control at every K.

Protocol (frozen in ``registry/h97_preregistration.json`` before any fit)
------------------------------------------------------------------------
* Instrument 1 (hide-and-recover, catalogue truth): ``gems52.spatial.folds`` label-blind quadrants v2,
  buffer 80 px, whole components hidden, 200 m collar taken from the VISIBLE catalogue only,
  K = 9,400 dots/fold/arm, ``gems52.evaluate_holdout`` pooled, paired 20 km block bootstrap.
  Arms: ``h97_disagree`` (the lane's field), ``single_A``, ``single_B`` (single-view baselines the
  brief requires), ``random``.
* Instrument 2 (prevalence-matched off-catalogue): truth = SGMC fault pixels >= 300 m from
  ``labels.tif``, thinned with a fixed seed to 14,089 px.  Emission = the SAME field placed on the
  full footprint with ``nodes.spacing_select`` (3 px) outside the 200 m catalogue ring, at
  K in {8000, 15000, 25517, 30000, 37654}; matched random control at every K.  The field reads no
  label, so no fold structure is needed here; the reference files are scored as-is for context only.
* Independence (Blum & Mitchell premise, brief-mandated): 50x50 px block Spearman of each view's
  error on catalogue-zero proxies inside each fold's TRAIN domain.
* Leakage canary: per-arm AUC against the held-out truth inside the allowed set, alarm 0.90.

Preregistered budget rule for the builder
-----------------------------------------
``K*`` = the K with the highest instrument-2 DTI **provided** that value is at least 0.001 above the
instrument-2 DTI at K = 37,654 and strictly greater than the matched random control at the same K.
If no K < 37,654 satisfies that, K* = 37,654 and the round reports the mass lever as unmeasured.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import evaluate_holdout as evaluator   # noqa: E402
from gems52 import grid, h97, metric, nodes, spatial  # noqa: E402

SEED = 88001
K_FOLD = 9400
BUFFER_PX = 80
CANARY_ALARM = 0.90
OC_BUDGETS = (8000, 15000, 25517, 30000, 37654)
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
SGMC = ROOT / "data/external/derived_sgmc_faults_100m_u8.tif"
RAD = ROOT / "data/external/geodawn_rad_u8.tif"
REFERENCE = ROOT / "data/reference/h33-2-b2-zeros.tif"
OUT = ROOT / "evidence/h97_holdout.json"


def log(m: str) -> None:
    print(f"[h97 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def allowed_for(fold, valid):
    """Fold region, not visible, outside the 200 m collar of the VISIBLE catalogue only."""
    from scipy import ndimage as ndi
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (vd > h97.RING_PX)


def main() -> int:
    t0 = time.time()
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    with rasterio.open(SAMPLE) as ds:
        domain = np.isfinite(ds.read(1))
    feat_valid = grid.footprint_from(FEATURES, "all")
    valid = feat_valid & domain
    cat = labels == 1
    log(f"eligible {int(valid.sum()):,} px; catalogue {int(cat.sum()):,} px")

    # ---- views (catalogue-free) ------------------------------------------------------------
    a_rank = h97.view_a(str(FEATURES), valid)
    b_rank = h97.view_b(str(FEATURES), valid)
    field = h97.disagreement(a_rank, b_rank, valid)
    comp = h97.composition(a_rank, b_rank, valid)
    log(f"view A mean {a_rank[valid].mean():.4f}, view B mean {b_rank[valid].mean():.4f}, "
        f"composition {comp}")
    band6 = h97.band6_is_radiometric_total_count(str(FEATURES), str(RAD))
    log(f"band-6 vs GeoDAWN TC Spearman {band6['band6_vs_geodawn_tc_spearman']:.4f} "
        f"(n={band6['n']:,})")

    # ---- instrument 2: prevalence-matched off-catalogue ------------------------------------
    with rasterio.open(SGMC) as ds:
        sgmc = ds.read(1) > 0
    truth_oc, oc_receipt = h97.offcatalogue_truth(labels, sgmc, valid)
    log(f"off-catalogue truth {int(truth_oc.sum()):,} px (raw candidate "
        f"{oc_receipt['raw_candidate_px']:,})")
    from scipy import ndimage as ndi
    ed_cat = ndi.distance_transform_edt(~cat)
    allowed_full = valid & ~cat & (ed_cat > h97.RING_PX)
    rng = np.random.default_rng(SEED)
    noise = rng.random(valid.shape).astype(np.float32)

    mass_lever = {}
    for K in OC_BUDGETS:
        em = nodes.spacing_select(field, allowed_full, K, min_px=3.0).astype(np.float32)
        rnd = nodes.spacing_select(noise, allowed_full, K, min_px=3.0).astype(np.float32)
        r_em = metric.dti(em, truth_oc)
        r_rnd = metric.dti(rnd, truth_oc)
        mass_lever[int(K)] = dict(
            placement="spacing_select 3 px, 200 m catalogue ring removed, full footprint",
            expected_mass=int(em.sum()), random_expected_mass=int(rnd.sum()),
            dti=float(r_em["dti"]), tpw=float(r_em["tpw"]), fpw=float(r_em["fpw"]),
            n_truth=int(r_em["n_truth"]), credit_per_dot=float(r_em["tpw"] / max(em.sum(), 1)),
            random_dti=float(r_rnd["dti"]), random_credit_per_dot=float(r_rnd["tpw"] / max(rnd.sum(), 1)))
        log(f"instrument2 K={K}: DTI {r_em['dti']:.6f} (random {r_rnd['dti']:.6f}), "
            f"credit/dot {mass_lever[int(K)]['credit_per_dot']:.5f}")
        del em, rnd
    # reference file scored as-is on the same instrument (context only; NOT our submission)
    with rasterio.open(REFERENCE) as ds:
        ref = ds.read(1)
    ref = np.where(np.isfinite(ref) & (ref > 0), 1.0, 0.0).astype(np.float32)
    ref_dti = metric.dti(ref, truth_oc)
    log(f"instrument2 champion h33-2-b2 as-is: DTI {ref_dti['dti']:.6f} "
        f"(mass {int(ref.sum()):,})")

    # ---- instrument 1: hide-and-recover ----------------------------------------------------
    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"hide folds {len(folds)}; withheld positive px {withheld:,}")
    arms = ("h97_disagree", "single_A", "single_B", "random")
    terms = {a: None for a in arms}
    per_fold, canary, neg_rows = [], {a: [] for a in arms}, []
    for fold in folds:
        allowed = allowed_for(fold, valid)
        r = np.random.default_rng(SEED + fold["fold"])
        noise_f = np.full(valid.shape, -1.0, np.float32)
        flat = np.flatnonzero(allowed.ravel())
        noise_f.ravel()[flat] = r.random(len(flat), dtype=np.float32)
        fields = dict(h97_disagree=field, single_A=a_rank, single_B=b_rank, random=noise_f)
        rec = dict(fold=fold["fold"], allowed_px=int(allowed.sum()),
                   withheld_positive_px=int((fold["truth"] & fold["region"]).sum()), arms={})
        emissions = {}
        for arm, fl in fields.items():
            em = nodes.spacing_select(fl, allowed, K_FOLD, min_px=3.0)
            emissions[arm] = em
            res, term = evaluator.evaluate(em.astype(np.float32), fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=float(res["dti"]), placed=int(em.sum()),
                                    tpw=float(res["tpw"]), fpw=float(res["fpw"]))
            truth_in = (fold["truth"] & fold["region"])[allowed]
            if truth_in.any() and (~truth_in).any():
                canary[arm].append(dict(fold=fold["fold"],
                                        auc=float(roc_auc_score(truth_in.astype(int), fl[allowed]))))
            log(f"fold {fold['fold']} {arm}: DTI {res['dti']:.6f} placed {int(em.sum()):,}")
        # independence: block errors on catalogue-zero proxies inside this fold's TRAIN domain
        neg = fold["train"] & valid & ~fold["visible"]
        rows = spatial.negative_block_errors(a_rank, b_rank, neg, fold["fold"], (0.75, 0.40),
                                             side=50, minimum=32)
        neg_rows.extend(rows)
        rec["independence_blocks"] = len(rows)
        per_fold.append(rec)
        del fields, emissions
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="h97_disagree")
    indep = spatial.independence(neg_rows, threshold=0.6, min_blocks=20)
    canary_max = {a: max(x["auc"] for x in v) for a, v in canary.items()}
    log("pooled: " + json.dumps({a: round(summary["scores"][a]["dti"], 6) for a in arms}))
    log("paired: " + json.dumps({k: [round(v["delta"], 6), [round(c, 6) for c in v["ci95"]]]
                                 for k, v in summary["paired_differences"].items()}))
    log(f"independence {json.dumps(indep['tests'])[:400]}")
    log(f"canary max AUC {json.dumps({k: round(v, 4) for k, v in canary_max.items()})}")

    # ---- preregistered K* rule -------------------------------------------------------------
    full = mass_lever[int(OC_BUDGETS[-1])]
    best_K, best = None, -1.0
    for K in OC_BUDGETS:
        row = mass_lever[int(K)]
        if row["dti"] > best and row["dti"] > row["random_dti"]:
            best, best_K = row["dti"], int(K)
    k_star = int(OC_BUDGETS[-1])
    if best_K is not None and best_K < int(OC_BUDGETS[-1]) and best - full["dti"] >= 0.001:
        k_star = best_K
    rule = dict(k_star=k_star, best_K_measuring=best_K, best_dti=best,
                dti_at_full_budget=full["dti"], minimum_gain_required=0.001,
                rule="K* = argmax instrument-2 DTI iff it is < 37654 AND >= full-budget DTI + 0.001 "
                     "AND > the matched random control; otherwise K* = 37654")
    log(f"K* rule -> {json.dumps(rule)}")

    out = dict(
        round="H97", stage="holdout+mass_lever", evidence_class="HOLDOUT-DTI / PROXY-INSTRUMENT",
        evaluator_version=evaluator.VERSION, lane="co-training disagreement (brief paragraph 1)",
        hypothesis_document="knowledge/97_h97_hypotheses_preregistered.md",
        preregistration="registry/h97_preregistration.json",
        views=dict(A="potential-field edge family bands 18,11,5,3,9,2 (gradient magnitude sigma 2)",
                   B="DEM band 12 curvature sigma 2 and 6, band 12 gradient, band 19 curvature, "
                     "band 6 in-stack radiometric"),
        band6_recheck=band6, composition=comp,
        instrument1=dict(folds=len(folds), buffer_px=BUFFER_PX, budget_per_fold=K_FOLD,
                         withheld_positive_px=withheld, pooled=summary,
                         canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max,
                                     alarm={k: v > CANARY_ALARM for k, v in canary_max.items()},
                                     per_fold=canary),
                         per_fold=per_fold),
        independence=dict(receipt=indep, threshold=0.6,
                          negative_class="catalogue-zero proxies inside fold TRAIN domains only",
                          blocks=len(neg_rows)),
        instrument2=dict(receipt=oc_receipt, mass_lever=mass_lever,
                         reference_champion_as_is=dict(path=str(REFERENCE),
                                                       sha256=sha256(REFERENCE),
                                                       mass=int(ref.sum()), dti=float(ref_dti["dti"]),
                                                       note="scored as-is for context; it is a prior "
                                                            "submission used for learning only"),
                         prevalence_note="truth thinned to 14,089 px to match the incumbent |G| "
                                         "bracket; the unthinned H83 instrument over-rewards recall "
                                         "(knowledge/76 §6) and its budget choice was invalid"),
        k_star_rule=rule,
        inputs=dict(features_sha256=sha256(FEATURES), labels_sha256=sha256(LABELS),
                    sgmc_sha256=sha256(SGMC), sample_sha256=sha256(SAMPLE)),
        implementation_hashes=evaluator.implementation_hashes(),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
