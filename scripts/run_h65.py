#!/usr/bin/env python3
"""H65 -- metric-kernel halo targets for both co-training views (one experiment).

Preregistered in ``knowledge/41_hypotheses_H65_preregistered.md`` and pinned by
``registry/h65_preregistration.json``; this runner refuses to start if either hash has moved.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61`` supplies ``setup`` (folds, feature store, thresholds), the
  canary, the fit stage, the exchange stage, the placement helper and the evaluator
  ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1).  ``run_h64`` supplies the S1 sufficiency gate
  and the exchange-or-skip rule, unchanged; this file only redirects where they write.
* The one change is the shared hook ``run_h61.sample_for_fit``.  This round overrides it with
  ``sample_soft_halo``: the H61 hard sample (identical draws) plus a halo of pixels at 0 < d < 300 m
  from the visible catalogue, each entered twice with weights ``t`` and ``1 - t`` (``t`` is the
  metric's triangular kernel).  The learners, feature sets, folds, budget and placement are H61's.
* Control: ``single_B_hard`` re-fits View B on H61's hard sample and must reproduce H61's
  ``single_B`` holdout DTI (0.174517) within the preregistered tolerance.  Otherwise the run stops.
* Holdout: the six H61 arms on the soft fields, plus ``single_B_hard``, evaluated by the shared
  evaluator.  Paired differences come from ``evaluate_holdout.pooled_summary``.

Stages (checkpointed; each writes ``evidence/h65_*.json``)
------
    canary       single-feature leakage canary on every fold (alarm 0.90)
    fit          soft-halo fit of both views on every fold, plus the hard B control
    sufficiency  S1 on View A (out-of-quadrant AUC, hard labels), via run_h64.stage_sufficiency
    exchange     run_h64.run_exchange_or_skip: exchange only if S1 passes, else post := pre
    holdout      six soft arms + hard control, pooled HOLDOUT-DTI, paired 95% CI
    all          the above in order

Nothing here uploads, promotes or spends a weekly slot.
Usage: ``python scripts/run_h65.py [canary|fit|sufficiency|exchange|holdout|all]``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                   # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
import run_h64 as h64                                                # noqa: E402  (S1 + exchange-or-skip only)
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import metric, nodes                                     # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h65"
STAGE_EV = WORK / "stage_evidence"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
REG_PATH = ROOT / "registry/h65_preregistration.json"
HALO_MAX = 30000                 # per fold; sampled from the halo pool with its own generator
HALO_SEED_OFFSET = 900           # rng = default_rng(SEED + 900 + fold)
ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random")
CONTROL = "single_B_hard"
CARD_TEXT = dict(
    hypothesis=("Metric-kernel halo targets: both co-training views learn the triangular 300 m coverage "
                "target (soft labels for 0 < d < 300 m from the visible catalogue) instead of pixel-exact "
                "masks; learners, folds, budget and placement unchanged."),
    mechanism=("The official distance-weighted Tversky credit is partial within 300 m; the hard-label learners "
               "never saw the 0-500 m halo, so the 200 m emission boundary sits in a blind zone."),
    named_non_fault_mimic=("basin-margin gravity gradient or lithologic contact running parallel to a mapped "
                           "trace within 300 m; flight-line or DEM artefact along a road or canal"),
    note_body="co-train, halo soft targets (metric kernel), 3px dots, >200m off catalogue",
    note_exact_only="exact-novel vs registry; lane DUPLICATE (70% rule)",
)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_h65(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h65_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h65_{name}.json").write_text(p.read_text())
    return p


def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H65 preregistered document changed after registration; refusing to run")
    h61 = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    reg["thresholds"] = {**h61, **reg["thresholds"]}
    return reg


def redirect() -> None:
    """Point every shared H61/H64 stage at H65 storage.  Nothing under evidence/h61_* or h64_* is written."""
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h65
    base.EVID = STAGE_EV             # stage_holdout reads "h61_pseudo_exchange.json" by its fixed name
    base.sample_for_fit = sample_soft_halo
    # one build implementation (run_h64.stage_build), with H65 names: TAG drives every receipt name
    h64.WORK = WORK
    h64.STAGE_EV = STAGE_EV
    h64.TAG = "h65"
    h64.PREFIX = "gems52-h65-"
    h64.ROUND_NAME = "H65"
    h64.CARD_TEXT = CARD_TEXT
    h64.BUDGET = int(os.environ.get("H65_BUDGET", "37600"))
    h64.FEASIBILITY_ONLY = os.environ.get("H65_FEASIBILITY_ONLY") == "1"
    h64.NOVELTY_MODE = os.environ.get("H65_NOVELTY_MODE", "exact_and_lane")
    h64.EXACT_ONLY = h64.NOVELTY_MODE == "exact_only"


# ------------------------------------------------------------------ the one change: soft halo targets
def sample_soft_halo(fold, cat, rng):
    """H61 hard sample (identical draws) plus the metric-kernel halo, duplicated with soft weights.

    Halo pool: fold.train & ~cat & 0 < d_vis < R (300 m).  ``cat`` is the full catalogue, but it is
    used only to EXCLUDE pixels from the halo, never as a label; the halo weight depends only on the
    visible catalogue, so no hidden truth enters training.
    """
    rows, y = base.sample_train(fold, cat, rng)
    d_m = ndi.distance_transform_edt(~fold["visible"]).ravel() * metric.PIXEL_M
    pool = np.flatnonzero((fold["train"] & ~cat & (d_m.reshape(fold["train"].shape) > 0)
                           & (d_m.reshape(fold["train"].shape) < metric.R_M)).ravel())
    hrng = np.random.default_rng(SEED + HALO_SEED_OFFSET + fold["fold"])
    take = min(HALO_MAX, len(pool))
    pick = hrng.choice(pool, take, replace=False)
    t = np.clip(1.0 - d_m[pick] / metric.R_M, 0.0, 1.0)
    rows2 = np.concatenate([rows, pick, pick])
    y2 = np.concatenate([y, np.ones(take, np.int8), np.zeros(take, np.int8)])
    w2 = np.concatenate([np.ones(len(rows)), t, 1.0 - t])
    # guard: every weight is a valid probability mass and no halo pixel is hidden truth
    assert np.isfinite(w2).all() and (w2 > 0).all()
    assert not cat.ravel()[pick].any()
    fold_rec = dict(halo_pool=int(len(pool)), halo_taken=int(take),
                    halo_mean_t=float(t.mean()) if take else None,
                    hard_rows=int(len(rows)), total_rows=int(len(rows2)))
    HALO_LOG.setdefault("folds", {})[str(fold["fold"])] = fold_rec
    return rows2, y2, w2


HALO_LOG: dict = {}


# ------------------------------------------------------------------ stage: fit (soft) + hard control
def stage_fit_soft() -> dict:
    out = base.stage_fit()
    out["halo"] = dict(sampler="sample_soft_halo", **HALO_LOG)
    write_h65("fit_soft_checkpoint", out)
    return out


def stage_fit_hard_control() -> dict:
    """View B on the H61 hard sample only: the pipeline control for single_B."""
    _, store, cat, eligible, folds, va, vb, _ = base.setup()
    flat = store.flat_idx
    rec = dict(stage="fit_hard_control", started_utc=now(), folds=[])
    for fold in folds:
        rng = np.random.default_rng(SEED + fold["fold"])
        rows, y = base.sample_train(fold, cat, rng)
        t0 = time.time()
        X = store.gather(rows, vb)
        m = base.learner_for("B", SEED)
        m.fit(X, y)
        del X
        p = base.predict_flat(store, m, vb, flat)
        np.save(WORK / f"pred_hard_B_f{fold['fold']}.npy", p)
        rec["folds"].append(dict(fold=fold["fold"], n_train=int(len(rows)), seconds=round(time.time() - t0, 1)))
        log(f"hard control fold {fold['fold']} view B fitted ({rec['folds'][-1]['seconds']}s)")
    rec["finished_utc"] = now()
    write_h65("fit_hard_control", rec)
    return rec


def stage_canary() -> dict:
    return base.stage_canary()


def stage_sufficiency(reg) -> dict:
    return h64.stage_sufficiency(reg)


def stage_exchange(reg, s1) -> dict:
    return h64.run_exchange_or_skip(reg, s1)


# ------------------------------------------------------------------ stage: holdout (six soft arms + hard control)
def stage_holdout(reg) -> dict:
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    ex = json.loads((STAGE_EV / "h61_pseudo_exchange.json").read_text())
    names = ARMS + (CONTROL,)
    terms = {a: None for a in names}
    out = dict(stage="holdout", started_utc=now(), budget_per_arm_per_fold=K, min_separation_px=min_px,
               arms=list(names), control=CONTROL, folds=[], exchange_allowed=ex.get("allowed_exchange"),
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               capacity_note=("every arm is placed by nodes.spacing_select on a field finite over the whole "
                              "allowed domain, so each arm fills exactly K dots; an arm that cannot fill K "
                              "invalidates the comparison and is reported, not rescued"))
    for fold in folds:
        f = fold["fold"]
        # LABEL-BLIND emission domain (as H61): the ring is built from the VISIBLE catalogue only
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        allowed_idx = np.flatnonzero(allowed.ravel())
        g = {}
        for v in ("A", "B"):
            g[f"pre_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f}.npy"), eligible.shape)
            g[f"post_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        g["hard_B"] = base.to_grid(flat, np.load(WORK / f"pred_hard_B_f{f}.npy"), eligible.shape)

        def rank(grid):
            r = np.full(grid.shape, np.nan, np.float32)
            r.ravel()[allowed_idx] = base.pct_rank(grid.ravel()[allowed_idx])
            return r

        r_pre = {v: rank(g[f"pre_{v}"]) for v in ("A", "B")}
        r_post = {v: rank(g[f"post_{v}"]) for v in ("A", "B")}
        r_hard_B = rank(g["hard_B"])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        fields = {
            "single_A": np.nan_to_num(r_pre["A"], nan=-1.0),
            "single_B": np.nan_to_num(r_pre["B"], nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(r_pre["A"], r_pre["B"]), nan=-1.0),
            "disagreement_pre": np.nan_to_num(r_pre["A"] - r_pre["B"], nan=-1.0),
            "disagreement_post": np.nan_to_num(r_post["A"] - r_post["B"], nan=-1.0),
            "random": rnd,
            CONTROL: np.nan_to_num(r_hard_B, nan=-1.0),
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(fold["region"].sum()), arms={})
        for arm in names:
            t0 = time.time()
            em = nodes.spacing_select(fields[arm], allowed, K, min_px=min_px)
            n = int(em.sum())
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=n, requested=K, filled=bool(n == K), seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {f} arm {arm}: emitted {n}/{K} DTI {result['dti']:.6f}")
        out["folds"].append(rec)
        del g, r_pre, r_post, fields
    draws = int(th["bootstrap_draws"])
    out["pooled_soft_candidate_single_B"] = evaluator.pooled_summary(terms, draws=draws, seed=SEED,
                                                                     candidate="single_B")
    out["pooled_soft_candidate_disagreement_post"] = evaluator.pooled_summary(
        terms, draws=draws, seed=SEED, candidate="disagreement_post")
    pooled = out["pooled_soft_candidate_single_B"]
    out["pooled"] = out["pooled_soft_candidate_disagreement_post"]     # candidate block, read by the build
    out.update(finished_utc=now(),
               withheld_positive_pixels=pooled["scores"]["single_B"]["withheld_positive_pixels"],
               all_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"] for arm in names)),
               caveat=("HOLDOUT-DTI on the label-blind-quadrants-v2 splitter; conditional on fitted folds, catalogue "
                       "labels and fixed budgets; not a leaderboard interval."))
    write_h65("holdout", out)
    return out


def stage_verdict(reg) -> dict:
    """Frozen verdict rule (knowledge/41 section 6).  Writes the receipt; never uploads."""
    hold = json.loads((EVID / "h65_holdout.json").read_text())
    sB = hold["pooled_soft_candidate_single_B"]
    sD = hold["pooled_soft_candidate_disagreement_post"]
    soft_vs_hard = sB["paired_differences"][CONTROL]
    cand_vs_B = sD["paired_differences"]["single_B"]
    control_dti = sB["scores"][CONTROL]["dti"]
    h61_ref = float(reg["thresholds"]["single_B_h61_control_holdout_dti"])
    tol = float(reg["thresholds"]["single_B_control_abs_tolerance"])
    s1 = json.loads((EVID / "h65_sufficiency.json").read_text())
    exch = json.loads((EVID / "h65_pseudo_exchange.json").read_text())
    out = dict(
        evidence_class="HOLDOUT-DTI",
        control=dict(single_B_hard_h65=control_dti, single_B_h61_committed=h61_ref,
                     abs_difference=abs(control_dti - h61_ref), tolerance=tol,
                     pass_=bool(abs(control_dti - h61_ref) <= tol)),
        mechanism_test=dict(comparison="single_B_soft minus single_B_hard (H61 control)",
                            delta=soft_vs_hard["delta"], ci95=soft_vs_hard["ci95"],
                            confirmed=bool(soft_vs_hard["ci95"][0] > 0.0)),
        single_B_soft_dti=sB["scores"]["single_B"]["dti"],
        candidate=dict(arm="disagreement_post", dti=sD["scores"]["disagreement_post"]["dti"],
                       delta_vs_single_B_soft=cand_vs_B["delta"], ci95=cand_vs_B["ci95"]),
        S1_pass=bool(s1["S1_pass"]), exchange_allowed=bool(exch.get("allowed_exchange", False)),
        note="lane, not-union, format and uniqueness are decided by the build step (not run in this receipt)",
    )
    out["eligible_for_selector_pending_build"] = bool(
        out["S1_pass"] and out["exchange_allowed"] and out["candidate"]["dti"] > out["single_B_soft_dti"]
        and cand_vs_B["ci95"][0] > 0.0 and out["control"]["pass_"])
    out["slot_used"] = 0
    out["upload"] = "none"
    write_h65("verdict", out)
    holdout_eligible = bool(out["control"]["pass_"] and cand_vs_B["delta"] > 0
                            and out["candidate"]["dti"] > out["single_B_soft_dti"] and cand_vs_B["ci95"][0] > 0.0)
    write_h65("control_and_verdict", dict(
        control=out["control"], candidate_arm="disagreement_post", candidate_dti=out["candidate"]["dti"],
        paired_delta_vs_single_B=cand_vs_B, holdout_eligible=holdout_eligible,
        note="holdout part of the frozen rule only; S1, lane, not-union, format and uniqueness are "
             "decided by the shared build and verdict_text"))
    return out


def stage_build(reg) -> dict:
    s1 = json.loads((EVID / "h65_sufficiency.json").read_text())
    exch = json.loads((EVID / "h65_pseudo_exchange.json").read_text())
    return h64.stage_build(reg, s1, exch)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["canary", "fit", "sufficiency", "exchange", "holdout", "verdict",
                                      "build", "all"])
    args = ap.parse_args()
    reg = check_prereg()
    redirect()
    stages = (["canary", "fit", "control", "sufficiency", "exchange", "holdout", "verdict"]
              if args.stage == "all" else [args.stage])
    if args.stage == "build":
        stages = ["build"]
    if args.stage == "fit":
        stages = ["fit", "control"]
    for s in stages:
        t0 = time.time()
        log(f"=== H65 stage {s} ===")
        if s == "canary":
            stage_canary()
        elif s == "fit":
            stage_fit_soft()
        elif s == "control":
            stage_fit_hard_control()
        elif s == "sufficiency":
            stage_sufficiency(reg)
        elif s == "exchange":
            stage_exchange(reg, json.loads((EVID / "h65_sufficiency.json").read_text()))
        elif s == "holdout":
            stage_holdout(reg)
        elif s == "verdict":
            stage_verdict(reg)
        elif s == "build":
            try:
                stage_build(reg)
            except SystemExit as e:           # the shared build stops with a message; record it
                write_h65("build_stop", dict(stopped=True, message=str(e), utc=now()))
                log(f"BUILD STOP: {e}")
                raise
        log(f"--- stage {s} done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
