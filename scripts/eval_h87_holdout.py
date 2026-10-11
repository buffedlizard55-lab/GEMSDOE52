#!/usr/bin/env python3
"""IR-H88-003: evaluate the shipped H87 field on the shared instruments.

Reuses the template's shared machinery only -- ``gems52.evaluate_holdout`` (pooled hide-and-recover),
``gems52.nodes.spacing_select`` (metric-aware placement), ``gems52.gates.lane_report`` -- together
with ``run_h83.setup()`` and ``run_h88.make_pm_folds`` so the numbers are directly comparable with the
published bars of this repository:

    gems52-pooled-hide-v1 @ 9,400 dots/fold   single_B 0.174571 | B_DVA2 0.192829 (repo best)
                                              B_DVA2_HVA 0.190147 | random 0.080426

Writes ``evidence/h87_holdout.json`` and ``evidence/h87_lane_full_registry.json``.

The H87 score surface is rebuilt with the very functions that produced the shipped file
(``build_h87_cotrain_wavelength.compute_view_a`` / ``compute_view_b`` /
``compute_disagreement_field``), then placed per fold inside the instrument's own pool, so the
placement never sees a hidden component.  The shipped raster is additionally scored verbatim (the
"file" arm) so the owner can see what the actual artefact would have done on the instrument.
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
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h83 as h83                                                                  # noqa: E402
import run_h88 as h88                                                                  # noqa: E402
import build_h87_cotrain_wavelength as b87                                             # noqa: E402
from gems52 import evaluate_holdout as evaluator, gates, nodes                           # noqa: E402

EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
H87_FILE = ROOT / "submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif"
PREFIX = "gems52-h87-"
SEED = h88.SEED
ARMS = ("single_A", "single_B", "h87", "A_only", "B_only", "concordant", "random")
BARS = dict(single_B=0.17457135886487102, B_DVA2=0.19282907051926573,
            B_DVA2_HVA=0.19014733655411672, random=0.08042564781050282)


def log(*a):
    print(*a, flush=True)


def write(name, obj):
    p = EVID / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    return p


def main():
    t0 = time.time()
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = h83.setup()
    th = reg["thresholds"]
    min_px = float(th["min_dot_separation_px"])
    shape = eligible.shape

    # ---- rebuild the H87 surface with the shipped builder's own functions -------------------
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
    h87_valid = b87.footprint_all_bands(str(b87.FEATURES)) & domain
    same_mask = bool(np.array_equal(h87_valid, eligible))
    log(f"footprint: h87 {int(h87_valid.sum())} px, instrument {int(eligible.sum())} px, "
        f"identical={same_mask}")
    view_a = b87.compute_view_a(str(b87.FEATURES), h87_valid)
    view_b = b87.compute_view_b(str(b87.FEATURES), str(b87.GEODAWN_RAD), str(b87.GEODAWN_EXT),
                                h87_valid)
    dis = b87.compute_disagreement_field(view_a, view_b, h87_valid, cat)
    a_v, b_v = view_a[eligible], view_b[eligible]
    corr = float(np.corrcoef(a_v, b_v)[0, 1])
    log(f"view correlation on eligible pixels: {corr:+.4f}")

    with rasterio.open(H87_FILE) as ds:
        file_dots = ds.read(1) > 0
    log(f"shipped H87 file dots: {int(file_dots.sum())}")

    # ---- instruments (identical pools to run_h88.stage_holdout) ------------------------------
    pm = json.loads((EVID / "h88_pm_budget.json").read_text())
    k_pm = int(pm["chosen_budget_per_fold"])
    k_ref = int(th["budget_dots_per_fold_per_arm"])
    pm_folds = h88.make_pm_folds(folds, eligible, cat)
    cat_dist_all = ndi.distance_transform_edt(~cat)
    pool1, pool2 = {}, {}
    for fold in pm_folds:
        vis = ndi.distance_transform_edt(~fold["visible"])
        pool1[fold["fold"]] = fold["region"] & ~fold["visible"] & (vis > ring_px)
        pool2[fold["fold"]] = fold["region"] & ~cat & (cat_dist_all > ring_px)
        del vis
    del cat_dist_all

    def rank01(a, mask):
        out = np.zeros(shape, np.float32)
        idx = np.flatnonzero(mask.ravel())
        vals = np.asarray(a).ravel()[idx]
        out.ravel()[idx] = h88.base.pct_rank(vals)
        return out

    def fields_for(fold):
        f = fold["fold"]
        dom = pool1[f] | pool2[f]
        rA, rB = rank01(view_a, dom), rank01(view_b, dom)
        return dict(single_A=rA, single_B=rB, h87=rank01(dis, dom),
                    A_only=np.where(dom, rA - rB, -1.0).astype(np.float32),
                    B_only=np.where(dom, rB - rA, -1.0).astype(np.float32),
                    concordant=np.where(dom, np.minimum(rA, rB), -1.0).astype(np.float32))

    def place(arm, fields, pool, k, rng):
        if arm == "random":
            rnd = np.full(shape, -1.0, np.float32)
            idx = np.flatnonzero(pool.ravel())
            rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
            return nodes.spacing_select(rnd, pool, k, min_px=min_px)
        return nodes.spacing_select(fields[arm], pool, k, min_px=min_px)

    def score(name, truth_key, pool_for_fold, k, evidence_class):
        terms = {a: None for a in ARMS + ("file",)}
        recs = []
        for fold in pm_folds:
            f = fold["fold"]
            fields = fields_for(fold)
            pool = pool_for_fold(fold)
            ifold = dict(fold=f, region=fold["region"], truth=fold[truth_key],
                         visible=fold["visible"])
            rec = dict(fold=f, truth_px=int(fold[truth_key].sum()), allowed_px=int(pool.sum()),
                       arms={})
            rng = np.random.default_rng(SEED + 700 + f)
            for arm in ARMS:
                t1 = time.time()
                em = place(arm, fields, pool, k, rng)
                res, term = evaluator.evaluate(em.astype(np.float32), ifold, eligible, block_side=200)
                terms[arm] = term if terms[arm] is None else terms[arm] + term
                rec["arms"][arm] = dict(dti=float(res["dti"]), placed=int(em.sum()),
                                        filled=bool(int(em.sum()) == k),
                                        seconds=round(time.time() - t1, 1))
                log(f"  [{name}] fold {f} {arm}: {int(em.sum())}/{k} DTI {res['dti']:.6f}")
            res, term = evaluator.evaluate(file_dots.astype(np.float32), ifold, eligible,
                                           block_side=200)
            terms["file"] = term if terms["file"] is None else terms["file"] + term
            rec["arms"]["file"] = dict(dti=float(res["dti"]),
                                       placed=int((file_dots & fold["region"]).sum()),
                                       filled=None, seconds=None)
            log(f"  [{name}] fold {f} file: DTI {res['dti']:.6f}")
            recs.append(rec)
        pooled = evaluator.pooled_summary(terms, draws=200, seed=SEED, candidate="h87",
                                          evidence_class=evidence_class)
        return dict(instrument=name, evidence_class=evidence_class, budget_per_fold=k,
                    folds=recs, pooled=pooled)

    res = dict(stage="holdout", round="H87", started_utc=h88.now(),
               evaluator=evaluator.VERSION,
               implementation_hashes=evaluator.implementation_hashes(),
               purpose="IR-H88-003: a held-out number for the already-built H87 artefact",
               field="H87 disagreement field (A-confident x B-abstains), rebuilt with the shipped "
                     "builder's functions; values re-ranked inside each fold's own pool",
               view_correlation_on_eligible=corr,
               budget_reference_per_fold=k_ref, budget_pm_per_fold=k_pm,
               min_separation_px=min_px, bars=BARS,
               caveat="HOLDOUT-DTI screens procedures and does not rank the leaderboard "
                      "(Spearman -0.10, knowledge/10); the prevalence-matched instruments are "
                      "diagnostic and can demote but never promote.")
    res["pooled_hide_9400"] = score("gems52-pooled-hide-v1 @ 9400", "truth",
                                    lambda f: pool1[f["fold"]], k_ref, "HOLDOUT-DTI")
    res["pm_hide"] = score("gems52-pm-hide-v1", "pm_truth", lambda f: pool1[f["fold"]], k_pm,
                           "HOLDOUT-DTI")
    res["pm_offcatalogue"] = score("gems52-pm-offcatalogue-v1", "pm_offcat_truth",
                                   lambda f: pool2[f["fold"]], k_pm, "OFFCAT-DTI")

    # ---- full-registry lane check on the shipped raster ---------------------------------------
    priors = sorted((ROOT / "data/scored").glob("*.tif"))
    ref_champ = ROOT / "data/reference/h33-2-b2-zeros.tif"
    if ref_champ.exists():
        priors.append(ref_champ)
    priors += [q for q in sorted((ROOT / "submission").glob("*.tif")) if not q.name.startswith(PREFIX)]
    priors += [q for q in sorted((ROOT / "docs/downloads").glob("*.tif")) if not q.name.startswith(PREFIX)]
    t1 = time.time()
    # drop this round's own copies (canonical name, publisher alias, docs copy): an artefact must
    # never be compared with its own bytes -- the pinned identical-decode STOP is for real copies
    cand_sha = hashlib.sha256(H87_FILE.read_bytes()).hexdigest()
    cand_size = H87_FILE.stat().st_size
    priors = [q for q in priors
              if not (q.stat().st_size == cand_size
                      and hashlib.sha256(q.read_bytes()).hexdigest() == cand_sha)]
    lane_dots = gates.lane_report(file_dots.astype(np.float32), eligible, priors,
                                  sample=str(SAMPLE), phase="dots")
    log(f"lane dots done in {time.time()-t1:.1f}s: literal {lane_dots['literal']['verdict']} "
        f"policy {lane_dots['policy']['verdict']} "
        f"max_near {lane_dots['literal']['max_near_3px_fraction']}")
    t1 = time.time()
    lane_surf = gates.lane_report(file_dots.astype(np.float32), eligible, priors,
                                  sample=str(SAMPLE), phase="surface")
    log(f"lane surface done in {time.time()-t1:.1f}s: literal {lane_surf['literal']['verdict']} "
        f"policy {lane_surf['policy']['verdict']}")
    lane = dict(stage="lane_full_registry", round="H87", started_utc=h88.now(),
                instrument=lane_dots["instrument"], registry_size=len(priors),
                dots=lane_dots, surface=lane_surf, finished_utc=h88.now())
    write("h87_lane_full_registry", lane)

    s = res["pooled_hide_9400"]["pooled"]["scores"]
    p = res["pooled_hide_9400"]["pooled"]["paired_differences"]
    gate = dict(
        beats_random=bool(s["h87"]["dti"] > s["random"]["dti"]),
        beats_single_B=bool(s["h87"]["dti"] > s["single_B"]["dti"]),
        beats_current_holdout_best_B_DVA2=bool(s["h87"]["dti"] > BARS["B_DVA2"]),
        paired_h87_minus_single_B=p.get("single_B"),
        paired_h87_minus_random=p.get("random"),
        file_beats_random=bool(s["file"]["dti"] > s["random"]["dti"]),
        file_dti=s["file"]["dti"],
        lane_dots_policy=lane_dots["policy"]["verdict"],
        lane_surface_policy=lane_surf["policy"]["verdict"],
        lane_dots_literal=lane_dots["literal"]["verdict"])
    gate["submit_recommendation"] = (
        "YES" if (gate["beats_current_holdout_best_B_DVA2"] and gate["beats_random"]
                  and gate["lane_dots_policy"] == "PASS") else "NO")
    res["gate"] = gate
    res.update(finished_utc=h88.now())
    write("h87_holdout", res)
    log(f"gate: {json.dumps(gate, default=str)}")
    log(f"H87 holdout+full-registry lane done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
