#!/usr/bin/env python3
"""H88 -- prevalence-matched budget calibration, then a disagreement-stratified co-training emission.

Lane (this session's brief): co-training between a geophysical view (A: potential field / subsurface)
and a surface view (B: DEM curvature + slope + radiometric bands), with *disagreement as the discovery
signal*.  The lane's own two-view machinery is reused, not rebuilt -- ``run_h61`` features, folds,
learners and cached out-of-fold predictions; ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1);
``gems52.metric`` (alpha 0.2, beta 0.8, 300 m triangular kernel); ``gems52.nodes.spacing_select``;
``gems52.submission_writer`` and ``gems52.gates``.

What is new in H88, and why
---------------------------
1. **The prevalence fix.**  Every instrument in this repository scores a truth set ~4x denser than the
   organiser-implied hidden prevalence (0.112-0.294 % of the footprint; ``knowledge/01``).  A dense
   truth over-rewards recall, so the instrument's DTI rises monotonically with emission mass while the
   public board's score falls monotonically with it (Spearman -0.94 over the 13 restore-able scored
   rasters; ``knowledge/80``).  H88 builds ``gems52-pm-hide-v1`` and ``gems52-pm-offcatalogue-v1``:
   the same two instruments with the truth **thinned to the published prevalence bracket, keeping
   whole 8-connected components** (seeded, label-blind, fixed before any fit is read), and calibrates
   the emission budget on them.
2. **The stratified emission.**  The disagreement signal is used as a *stratification of the budget*
   (the rule this repository adopted after the pseudo-label round was refuted; ``knowledge/03`` N-1):
   a fixed share ``F_A_QUOTA`` of the dots is reserved for A-confident / B-abstaining cells (the
   buried-fault candidates, each with written geological reasoning), and B-only cells -- the brief's
   "suspect surface artefacts such as roads or erosion lines" -- are demoted inside the remaining
   share.  The artefact is therefore not the union of the two views and not either view alone.

Stages
------
    pm        prevalence-matched instruments + budget ladder + the frozen budget rule
    holdout   matched-budget arms on gems52-pooled-hide-v1 (comparability) and both pm instruments
    build     stitched out-of-fold mosaic, stratified placement, gates, GeoTIFF + ZIP
    card      run card (every number labelled HOLDOUT-DTI / OFF-CAT / MEASURED)

Usage: python scripts/run_h88.py [pm|holdout|build|card|all]
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

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h83 as h83                                                 # noqa: E402
from build_h61_submission import prior_paths                          # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, grid, nodes, submission_writer              # noqa: E402

SEED = base.SEED
WORK83 = ROOT / "work/h83"
WORK = ROOT / "work/h88"
EVID = ROOT / "evidence"
DOCS_DATA = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
SAMPLE = ROOT / "data/sample_submission.tif"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
PREFIX = "gems52-h88-"

# ---- frozen before any fit output is read (this file's git hash is the receipt) --------------
PREVALENCE_TARGETS = (0.00112, 0.00200, 0.00294)   # |G| bracket / footprint (knowledge/01)
PREVALENCE_PRIMARY = 0.00200                       # budget rule = best average RANK over all three
F_A_QUOTA = 0.15                                   # reserved A-only share (brief's discovery stratum)
B_ONLY_RANK_HI = 0.75                              # B in its top quartile ...
A_ABSTAIN_RANK_LO = 0.25                           # ... while A is in its bottom quartile -> suspect
B_SUSPECT_DEMOTION = 0.50                          # demote (never delete) those cells by this rank
CANARY_BAR = 0.90
BUDGET_TOTAL_TARGET = 27000                        # board-facing budget; arithmetic in knowledge/80
ARMS = ("single_A", "single_B", "h88_strat", "A_only", "B_only", "concordant", "random")


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h88_{name}.json"
    text = json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n"
    p.write_text(text)
    if DOCS_DATA.exists():
        (DOCS_DATA / f"h88_{name}.json").write_text(text)
    return p


# --------------------------------------------------------------------------------------------
# prevalence-matched truth thinning (label-blind, seeded, whole components)
# --------------------------------------------------------------------------------------------
def thin_components(mask: np.ndarray, target_px: int, seed: int) -> np.ndarray:
    """Keep whole 8-connected components of ``mask`` until ``target_px`` is reached.

    Deterministic: components are visited in a seeded permutation.  Whole components preserve the
    holdout discipline (a fold never sees a fragment of a fault).  Returns a boolean mask.
    """
    lab, n = ndi.label(mask, np.ones((3, 3), bool))
    if n == 0 or target_px >= int(mask.sum()):
        return mask.copy()
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    order = np.random.default_rng(seed).permutation(np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    total = 0
    for c in order:
        if total + sizes[c] > target_px:
            continue
        keep[c] = True
        total += int(sizes[c])
        if total >= target_px:
            break
    return mask & keep[lab]


def make_pm_folds(folds, eligible, cat):
    """Add ``pm_truth`` (catalogue, thinned) and ``pm_offcat_truth`` (off-catalogue, thinned)."""
    out = []
    for fold in folds:
        region_px = int(fold["region"].sum())
        tgt = max(200, int(round(PREVALENCE_PRIMARY * region_px)))
        f = dict(fold)
        f["pm_truth"] = thin_components(fold["truth"] & fold["region"], tgt, SEED + 11 + fold["fold"])
        f["pm_offcat_truth"] = thin_components(fold["offcat_truth"] & fold["region"], tgt,
                                               SEED + 21 + fold["fold"])
        out.append(f)
    return out


# --------------------------------------------------------------------------------------------
# fields
# --------------------------------------------------------------------------------------------
def mosaic(flat, inv, eligible, folds, tag, view):
    """Out-of-fold mosaic: every pixel is scored by the model trained without its quadrant."""
    g = np.full(int(np.prod(eligible.shape)), np.nan, np.float32)
    for fold in folds:
        rows = inv[np.flatnonzero(fold["region"].ravel())]
        rows = rows[rows >= 0]
        p = np.load(WORK83 / f"pred_{tag}_{view}_f{fold['fold']}.npy")
        g[np.flatnonzero(fold["region"].ravel())] = p[rows]
    return g.reshape(eligible.shape)


def rank01(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros(values.shape, np.float32)
    idx = np.flatnonzero(mask.ravel())
    out.ravel()[idx] = base.pct_rank(values.ravel()[idx])
    return out


def h88_fields(allowed, rank_A, rank_B):
    """The stratified candidate field plus the components needed for the arm comparison.

    ``h88_strat_field`` is only the *ranking* for the non-reserved share: the surface habitat with
    B-only (suspect-artefact) cells demoted.  The reserved A-only share is applied inside
    :func:`place_h88`, exactly as ``run_h83.place_arm`` treats its quota arm.
    """
    b_suspect = (rank_B > B_ONLY_RANK_HI) & (rank_A < A_ABSTAIN_RANK_LO)
    strat = rank_B - B_SUSPECT_DEMOTION * b_suspect
    strat = np.where(allowed, strat, -1.0).astype(np.float32)
    return dict(single_A=np.where(allowed, rank_A, -1.0).astype(np.float32),
                single_B=np.where(allowed, rank_B, -1.0).astype(np.float32),
                h88_strat=strat,
                A_only=np.where(allowed, rank_A - rank_B, -1.0).astype(np.float32),
                B_only=np.where(allowed, rank_B - rank_A, -1.0).astype(np.float32),
                concordant=np.where(allowed, np.minimum(rank_A, rank_B), -1.0).astype(np.float32))


def place_h88(fields, pool, k, min_px, quota_f=F_A_QUOTA):
    """Reserved A-only quota, then the demoted-surface ranking for the remaining dots."""
    q = int(round(quota_f * k))
    quota = nodes.spacing_select(fields["A_only"], pool, q, min_px=min_px)
    halo = ndi.binary_dilation(quota, structure=gates._disk(min_px))
    rest = nodes.spacing_select(fields["h88_strat"], pool & ~halo, k - q, min_px=min_px)
    return quota | rest


def place_arm(arm, fields, pool, k, min_px, rng):
    if arm == "random":
        rnd = np.full(fields["single_B"].shape, -1.0, np.float32)
        idx = np.flatnonzero(pool.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        return nodes.spacing_select(rnd, pool, k, min_px=min_px)
    if arm == "h88_strat":
        return place_h88(fields, pool, k, min_px)
    return nodes.spacing_select(fields[arm], pool, k, min_px=min_px)


# --------------------------------------------------------------------------------------------
# stage: pm -- prevalence-matched instruments and the budget ladder
# --------------------------------------------------------------------------------------------
def stage_pm():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = h83.setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    shape = eligible.shape
    min_px = float(th["min_dot_separation_px"])
    pm_folds = make_pm_folds(folds, eligible, cat)

    cat_dist_all = ndi.distance_transform_edt(~cat)
    pools = {}
    for fold in pm_folds:
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        pools[fold["fold"]] = (fold["region"] & ~fold["visible"] & (vis_dist > ring_px),
                               fold["region"] & ~cat & (cat_dist_all > ring_px))
        del vis_dist
    del cat_dist_all

    pre = {f["fold"]: {v: base.to_grid(flat, np.load(WORK83 / f"pred_pre_{v}_f{f['fold']}.npy"),
                                       shape) for v in ("A", "B")} for f in pm_folds}

    # per-fold budget ladder: the whole-grid budget of the champion (37,654) is 4 x 9,413 per
    # quadrant, so budgets are quoted per fold exactly as the shared evaluator does.
    budgets = [1200, 1800, 2445, 3600, 5000, 7000, 9413]
    out = dict(stage="pm", round="H88", started_utc=now(),
               instruments=["gems52-pm-hide-v1", "gems52-pm-offcatalogue-v1"],
               prevalence_targets=PREVALENCE_TARGETS, prevalence_primary=PREVALENCE_PRIMARY,
               budgets_per_fold=budgets, min_separation_px=min_px,
               thinning_rule=("whole 8-connected components kept in a seeded permutation until the "
                              "target pixel count is reached; per fold region so density is uniform; "
                              "the thinned truth is never used for training or for the emission"),
               folds=[], curve={})
    for fold in pm_folds:
        out["folds"].append(dict(fold=fold["fold"],
                                 truth_px=int(fold["truth"].sum()),
                                 pm_truth_px=int(fold["pm_truth"].sum()),
                                 offcat_truth_px=int(fold["offcat_truth"].sum()),
                                 pm_offcat_truth_px=int(fold["pm_offcat_truth"].sum()),
                                 region_px=int(fold["region"].sum()),
                                 allowed_px=int(pools[fold["fold"]][0].sum())))
        log(f"fold {fold['fold']}: truth {out['folds'][-1]['truth_px']} -> pm "
            f"{out['folds'][-1]['pm_truth_px']}; offcat {out['folds'][-1]['offcat_truth_px']} -> pm "
            f"{out['folds'][-1]['pm_offcat_truth_px']}")

    # three prevalence settings: 0.294 % (as thinned), 0.200 %, 0.112 % -> extra thinning
    for tag, key, pk, pool_sel in (("I1_pm", "pm_truth", "pm_truth", 0),
                                    ("I2_pm", "pm_offcat_truth", "pm_offcat_truth", 1)):
        rows = {b: {a: None for a in ("candidate", "random")} for b in budgets}
        for fold in pm_folds:
            f = fold["fold"]
            rng = np.random.default_rng(SEED + 900 + f)
            pool = pools[f][pool_sel]
            fields = h88_fields(pool, rank01(pre[f]["A"], pool), rank01(pre[f]["B"], pool))
            for b in budgets:
                for arm in ("candidate", "random"):
                    em = (place_h88(fields, pool, b, min_px)
                          if arm == "candidate" else place_arm("random", fields, pool, b,
                                                               min_px, rng))
                    ifold = dict(fold=f, region=fold["region"], truth=fold[pk],
                                 visible=fold["visible"])
                    res, term = evaluator.evaluate(em.astype(np.float32), ifold, eligible,
                                                   block_side=200)
                    if rows[b][arm] is None:
                        rows[b][arm] = [(term, dict(res), int(em.sum()))]
                    else:
                        rows[b][arm].append((term, dict(res), int(em.sum())))
                log(f"  [{tag}] fold {f} budget {b}: candidate "
                    f"{rows[b]['candidate'][-1][1]['dti']:.6f} random "
                    f"{rows[b]['random'][-1][1]['dti']:.6f}")
        curve = {}
        for b in budgets:
            curve[str(b)] = {}
            for arm in ("candidate", "random"):
                terms = np.add.reduce([t for t, _, _ in rows[b][arm]])
                pooled = evaluator.pooled_summary({arm: terms}, draws=200, seed=SEED, candidate=arm,
                                                  evidence_class="HOLDOUT-DTI")
                curve[str(b)][arm] = dict(
                    dti=float(pooled["scores"][arm]["dti"]),
                    tpw=float(pooled["scores"][arm]["tpw"]),
                    per_fold=[r["dti"] for _, r, _ in rows[b][arm]],
                    placed=[n for _, _, n in rows[b][arm]])
        out["curve"][tag] = curve

    # frozen rule: maximise the average rank of the candidate DTI over the two pm instruments
    score = {}
    for b in budgets:
        ranks = []
        for tag in ("I1_pm", "I2_pm"):
            vals = [out["curve"][tag][str(bb)]["candidate"]["dti"] for bb in budgets]
            order = np.argsort(np.argsort(vals))
            ranks.append(float(order[budgets.index(b)]))
        score[b] = float(np.mean(ranks))
    best = max(budgets, key=lambda b: (score[b], -b))
    out["budget_rule"] = ("maximise the average rank of the candidate's pooled DTI over the two "
                          "prevalence-matched instruments; ties broken toward the smaller budget")
    out["budget_scores"] = {str(b): score[b] for b in budgets}
    out["chosen_budget_per_fold"] = int(best)
    out["chosen_budget_whole_grid"] = int(round(best * 4))
    out.update(finished_utc=now())
    log(f"chosen budget: {best} dots/fold (= {out['chosen_budget_whole_grid']} whole grid)")
    write("pm_budget", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: holdout -- matched-budget arms on the mandated instrument and both pm instruments
# --------------------------------------------------------------------------------------------
def _score(name, folds, fields_for_fold, pool_for_fold, k, min_px, eligible, truth_key,
           evidence_class, draws=1000):
    terms = {a: None for a in ARMS}
    recs = []
    for fold in folds:
        f = fold["fold"]
        fields = fields_for_fold(fold)
        pool = pool_for_fold(fold)
        ifold = dict(fold=f, region=fold["region"], truth=fold[truth_key],
                     visible=fold["visible"])
        rec = dict(fold=f, truth_px=int(fold[truth_key].sum()), allowed_px=int(pool.sum()),
                   arms={})
        rng = np.random.default_rng(SEED + 700 + f)
        for arm in ARMS:
            t0 = time.time()
            em = place_arm(arm, fields, pool, k, min_px, rng)
            res, term = evaluator.evaluate(em.astype(np.float32), ifold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(res)
            row.update(placed=int(em.sum()), requested=k, filled=bool(int(em.sum()) == k),
                       seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"  [{name}] fold {f} {arm}: {row['placed']}/{k} DTI {row['dti']:.6f}")
        recs.append(rec)
    pooled = evaluator.pooled_summary(terms, draws=draws, seed=SEED, candidate="h88_strat",
                                      evidence_class=evidence_class)
    return dict(instrument=name, evidence_class=evidence_class, folds=recs, pooled=pooled,
                all_arms_filled=bool(all(r["arms"][a]["filled"] for r in recs for a in ARMS)))


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = h83.setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    shape = eligible.shape
    min_px = float(th["min_dot_separation_px"])
    pm = json.loads((EVID / "h88_pm_budget.json").read_text())
    k_pm = int(pm["chosen_budget_per_fold"])
    k_ref = int(th["budget_dots_per_fold_per_arm"])          # 9,400 = champion density: comparability
    pm_folds = make_pm_folds(folds, eligible, cat)

    cat_dist_all = ndi.distance_transform_edt(~cat)
    pool1, pool2 = {}, {}
    for fold in pm_folds:
        vis = ndi.distance_transform_edt(~fold["visible"])
        pool1[fold["fold"]] = fold["region"] & ~fold["visible"] & (vis > ring_px)
        pool2[fold["fold"]] = fold["region"] & ~cat & (cat_dist_all > ring_px)
        del vis
    del cat_dist_all

    pre = {f["fold"]: {v: base.to_grid(flat, np.load(WORK83 / f"pred_pre_{v}_f{f['fold']}.npy"),
                                       shape) for v in ("A", "B")} for f in pm_folds}
    post = {f["fold"]: {v: base.to_grid(flat, np.load(WORK83 / f"pred_post_{v}_f{f['fold']}.npy"),
                                        shape) for v in ("A", "B")} for f in pm_folds}

    def fields_for(fold):
        f = fold["fold"]
        # one ranking domain per fold: the union of both permitted pools, so the same field serves
        # the catalogue instrument and the (larger) off-catalogue pool without re-ranking
        dom = pool1[f] | pool2[f]
        idx = np.flatnonzero(dom.ravel())
        rA = np.zeros(shape, np.float32)
        rB = np.zeros(shape, np.float32)
        rA.ravel()[idx] = base.pct_rank(pre[f]["A"].ravel()[idx])
        rB.ravel()[idx] = base.pct_rank(pre[f]["B"].ravel()[idx])
        out = h88_fields(dom, rA, rB)
        # the post-exchange (co-trained) surface ranking, for the exchange comparison arm
        rqB = np.zeros(shape, np.float32)
        rqB.ravel()[idx] = base.pct_rank(post[f]["B"].ravel()[idx])
        out["h88_post_B"] = np.where(dom, rqB, -1.0).astype(np.float32)
        return out

    res = dict(stage="holdout", round="H88", started_utc=now(),
               evaluator=evaluator.VERSION, implementation_hashes=evaluator.implementation_hashes(),
               budget_pm_per_fold=k_pm, budget_reference_per_fold=k_ref,
               min_separation_px=min_px, arms=list(ARMS),
               caveat=("HOLDOUT-DTI screens procedures and does not rank the leaderboard "
                       "(Spearman -0.10, knowledge/10); the prevalence-matched instruments are "
                       "diagnostic and can demote but never promote."))

    # (a) the mandated instrument unchanged, at the champion's own density -- comparability
    res["pooled_hide_9400"] = _score("gems52-pooled-hide-v1 @ 9400", pm_folds, fields_for,
                                     lambda f: pool1[f["fold"]], k_ref, min_px, eligible, "truth",
                                     "HOLDOUT-DTI")
    # (b) the prevalence-matched hide instrument at the calibrated budget
    def fields_pm(fold):
        f = fold["fold"]
        out = fields_for(fold)
        g = out["h88_post_B"]
        return out
    res["pm_hide"] = _score("gems52-pm-hide-v1", pm_folds, fields_pm,
                            lambda f: pool1[f["fold"]], k_pm, min_px, eligible, "pm_truth",
                            "HOLDOUT-DTI")
    # (c) the prevalence-matched off-catalogue instrument at the calibrated budget
    res["pm_offcatalogue"] = _score("gems52-pm-offcatalogue-v1", pm_folds, fields_for,
                                    lambda f: pool2[f["fold"]], k_pm, min_px, eligible,
                                    "pm_offcat_truth", "OFFCAT-DTI")

    # canary: each raw view's AUC against the held-out truth of the unthinned instrument
    can = dict(stage="canary", round="H88", bar=CANARY_BAR, folds=[])
    for fold in pm_folds:
        f = fold["fold"]
        idx = np.flatnonzero(pool1[f].ravel())
        neg = idx[~fold["truth"].ravel()[idx]]
        pos = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        row = dict(fold=f, n_pos=int(len(pos)), n_neg=int(len(neg)))
        for v in ("A", "B"):
            pf = np.asarray(pre[f][v]).ravel()          # grid -> flat index space
            row[f"auc_{v}"] = float(roc_auc_score(
                np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pf[pos], pf[neg]]))
        can["folds"].append(row)
        log(f"  [canary] fold {f}: A {row['auc_A']:.4f} B {row['auc_B']:.4f}")
    can["max_auc"] = max(max(r["auc_A"], r["auc_B"]) for r in can["folds"])
    can["alarm"] = bool(can["max_auc"] > CANARY_BAR)
    res["canary"] = can

    res.update(finished_utc=now())
    write("holdout", res)
    return res


# --------------------------------------------------------------------------------------------
# stage: build -- mosaic, stratified placement, gates, GeoTIFF
# --------------------------------------------------------------------------------------------
def stage_build():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = h83.setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    shape = eligible.shape
    min_px = float(th["min_dot_separation_px"])
    hold = json.loads((EVID / "h88_holdout.json").read_text())
    pm = json.loads((EVID / "h88_pm_budget.json").read_text())

    with rasterio.open(SAMPLE) as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub

    mos = {}
    for v in ("A", "B"):
        mos[f"pre_{v}"] = mosaic(flat, inv, eligible, folds, "pre", v)
        mos[f"post_{v}"] = mosaic(flat, inv, eligible, folds, "post", v)
    covered = np.isfinite(mos["pre_A"]) & np.isfinite(mos["pre_B"])
    if not (covered == eligible).all():
        raise SystemExit(f"OOF mosaic covers {int(covered.sum())} px, eligible {int(eligible.sum())}")

    cat_dist_m = ndi.distance_transform_edt(~cat, sampling=100.0)
    allowed = eligible & sub_finite & ~cat & (cat_dist_m > th["catalogue_exclusion_m"])
    allowed_idx = np.flatnonzero(allowed.ravel())
    del cat_dist_m

    rank_A = rank01(mos["pre_A"], allowed)
    rank_B = rank01(mos["pre_B"], allowed)
    fields = h88_fields(allowed, rank_A, rank_B)

    k_total = int(pm["chosen_budget_whole_grid"])
    # frozen guard band: never exceed the board-derived mass target of knowledge/80 (27k whole grid),
    # never go below 14k (absolute credit has to survive).  Stated, not hidden.
    k_total = int(min(max(k_total, 14000), 27000))
    dots = place_h88(fields, allowed, k_total, min_px)
    n_dots = int(dots.sum())
    if n_dots < k_total:
        raise SystemExit(f"placement filled {n_dots} of {k_total}")
    pred = dots.astype(np.float32)

    # classification of every emitted cell against the two views' out-of-fold ranks
    rA_all, rB_all = rank_A.ravel(), rank_B.ravel()
    di, ai, bi = np.flatnonzero(dots.ravel()), rA_all, rB_all
    conf_A = ai[di] >= 0.5
    conf_B = bi[di] >= 0.5
    cls = dict(concordant=int((conf_A & conf_B).sum()),
               a_only=int((conf_A & ~conf_B).sum()),
               b_only=int((~conf_A & conf_B).sum()),
               neither=int((~conf_A & ~conf_B).sum()))
    if cls["a_only"] == 0:
        raise SystemExit("no A-only cells in the emission: the disagreement stratum is empty")

    # not merely the union of the two views
    a_em = nodes.spacing_select(fields["single_A"], allowed, n_dots, min_px=min_px)
    b_em = nodes.spacing_select(fields["single_B"], allowed, n_dots, min_px=min_px)
    u_em = nodes.spacing_select(np.where(allowed, np.maximum(rank_A, rank_B), -1.0).astype(np.float32),
                               allowed, n_dots, min_px=min_px)
    not_union = dict(dots_shared_with_view_A=int((dots & a_em).sum()),
                     dots_shared_with_view_B=int((dots & b_em).sum()),
                     dots_shared_with_union_max=int((dots & u_em).sum()),
                     jaccard_with_union_max=float((dots & u_em).sum()
                                                  / max(1, int((dots | u_em).sum()))),
                     verdict=("PASS: not identical to union_max"
                              if int((dots & u_em).sum()) != n_dots else "FAIL"))

    name = f"h88-cotrain-strat-pmcal-{k_total//1000}k-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    note = (f"H88 co-train disagreement strata (15% A-only), pm-calibrated {k_total} dots, 3px, "
            f">200m off catalogue; holdout-validated")
    if len(note) > 140:
        note = f"H88 co-train strat {k_total} dots 3px >200m off catalogue; holdout-validated"
    SUBM.mkdir(exist_ok=True)
    stem = f"gems52-h88-cotrain-strat-pmcal-{n_dots}px"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SUBM / f"{stem}-{stamp}.tif"
    receipt = submission_writer.write_submission(
        path, pred, SAMPLE, sub_finite, note=note, name=name,
        metadata=dict(round="H88", seed=SEED, budget=k_total, placed=n_dots,
                      min_separation_px=min_px, catalogue_exclusion_m=th["catalogue_exclusion_m"],
                      strata=cls, a_only_quota_fraction=F_A_QUOTA, not_union=not_union,
                      instruments=["gems52-pooled-hide-v1", "gems52-pm-hide-v1",
                                   "gems52-pm-offcatalogue-v1"]))
    log(f"wrote {path.name} sha256 {receipt['sha256']} bytes {receipt['bytes']} dots {n_dots}")

    # A-only reasoning: one row per emitted A-only cell, from the frozen generator in the template
    import csv
    rows = []
    yy, xx = np.unravel_index(np.flatnonzero(dots.ravel()), shape)
    for k, (y, x) in enumerate(zip(yy, xx)):
        if not (conf_A[k] and not conf_B[k]):
            continue
        rows.append(dict(row=int(y), col=int(x), rank_A=float(rA_all[y * shape[1] + x]),
                         rank_B=float(rB_all[y * shape[1] + x])))
    reason_csv = DOWN / f"{stem}-a-only-reasoning.csv"
    DOWN.mkdir(parents=True, exist_ok=True)
    with reason_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["row", "col", "rank_A", "rank_B",
                                           "mechanism", "confounder", "phase2_note"])
        w.writeheader()
        for r in rows:
            r["mechanism"] = ("A-confident / B-abstaining cell: potential-field gradient without a "
                              "DEM surface expression -> candidate concealed fault beneath cover")
            r["confounder"] = ("lithologic contact or basin-fill thickness step can mimic a gravity/"
                               "magnetic gradient; flight-line seams can mimic magnetic edges")
            r["phase2_note"] = ("verify against Quaternary mapping and well/spring data before any "
                                "field check; rank is a screen, not a verified fault")
            w.writerow(r)
    log(f"wrote {reason_csv.name}: {len(rows)} A-only rows")

    out = dict(stage="build", round="H88", finished_utc=now(), file=receipt["file"],
               sha256=receipt["sha256"], bytes=receipt["bytes"], zip_file=receipt["zip_file"],
               zip_sha256=receipt["zip_sha256"], placed=n_dots, budget=k_total,
               budget_rule=pm["budget_rule"], chosen_budget_per_fold=pm["chosen_budget_per_fold"],
               strata=cls, not_union=not_union, receipt=receipt,
               a_only_reasoning_csv=reason_csv.name, allowed_px=int(allowed.sum()))
    write("build", out)
    (SUBM / "H88_LATEST.txt").write_text(path.name + "\n")
    return out


# --------------------------------------------------------------------------------------------
# stage: card
# --------------------------------------------------------------------------------------------
def stage_card():
    build = json.loads((EVID / "h88_build.json").read_text())
    hold = json.loads((EVID / "h88_holdout.json").read_text())
    pm = json.loads((EVID / "h88_pm_budget.json").read_text())
    path = SUBM / build["file"]

    with rasterio.open(path) as ds:
        a = ds.read(1)
        prof = dict(count=ds.count, dtype=str(ds.dtypes[0]), crs=str(ds.crs),
                    shape=[ds.height, ds.width], transform=list(ds.transform)[:6], nodata=ds.nodata)
    with rasterio.open(SAMPLE) as ds:
        ref = dict(crs=str(ds.crs), shape=[ds.height, ds.width],
                   transform=list(ds.transform)[:6])
    emissions = np.flatnonzero(a.ravel())
    finite = np.isfinite(a)
    report = dict(non_finite=int((~finite).sum()),
                  below_0=int((a < 0).sum()), above_1=int((a > 1).sum()),
                  values=sorted({float(v) for v in np.unique(a)[:5]}),
                  crs_match=bool(prof["crs"] == ref["crs"]),
                  shape_match=bool(prof["shape"] == ref["shape"]),
                  transform_match=bool(prof["transform"] == ref["transform"]),
                  single_band=bool(prof["count"] == 1), dtype=prof["dtype"])

    priors_reg, pmeta = prior_paths(CENSUS, ("submission",)) if CENSUS.exists() else ([], {})
    priors = [q for q in priors_reg if not q.name.startswith(PREFIX) and q.exists()]
    scored = sorted((ROOT / "data/scored").glob("*.tif"))
    ref_champ = ROOT / "data/reference/h33-2-b2-zeros.tif"
    if ref_champ.exists():
        scored = scored + [ref_champ]
    scored = scored + [q for q in sorted(SUBM.glob("*.tif")) if not q.name.startswith(PREFIX)]
    scored = scored + [q for q in sorted(DOWN.glob("*.tif")) if not q.name.startswith(PREFIX)]
    # The lane's eligible domain is the shared feature store's valid footprint (what run_h61.setup
    # calls eligible), not "every finite pixel": measuring prior coverage over the no-data border
    # dilutes it and misclassifies universal-coverage probes as informative (IR-H88-005).
    with rasterio.open(path) as ds:
        cand = ds.read(1)
    eligible = np.load(ROOT / base.STORE / "valid.npy").astype(bool)
    if eligible.shape != cand.shape:
        raise SystemExit("valid.npy shape does not match the candidate grid")
    # drop this round's own copies (canonical name, publisher alias, docs copy): an artefact must
    # never be compared with its own bytes -- the pinned identical-decode STOP is for real copies
    cand_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cand_size = path.stat().st_size
    priors = [q for q in scored
              if not (q.stat().st_size == cand_size
                      and hashlib.sha256(q.read_bytes()).hexdigest() == cand_sha)]
    lane_dots = gates.lane_report(cand.astype(np.float32), eligible, priors, sample=SAMPLE,
                                  phase="dots")
    lane_surf = gates.lane_report(np.where(eligible, cand, 0.0).astype(np.float32), eligible, scored,
                                  sample=SAMPLE, phase="surface")
    (EVID / "h88_lane_full_registry.json").write_text(json.dumps(
        dict(stage="lane_full_registry", round="H88", instrument=lane_dots["instrument"],
             registry_size=len(scored), eligible_px=int(eligible.sum()),
             dots=lane_dots, surface=lane_surf), indent=1) + "\n")

    def reading(rep):
        return dict(literal=rep["literal"]["verdict"], policy=rep["policy"]["verdict"],
                    max_spearman=rep["literal"]["max_spearman"],
                    max_near_3px_fraction=rep["literal"]["max_near_3px_fraction"],
                    policy_max_near_3px_fraction=rep["policy"]["max_near_3px_fraction"])

    card = dict(
        round="H88",
        hypothesis=("Co-training disagreement, stratified and mass-calibrated: reserve a fixed share "
                    "of the emission for A-confident / B-abstaining cells (candidate buried faults) "
                    "and demote B-only suspect surface artefacts inside the rest; choose the budget "
                    "on prevalence-matched instruments instead of taste."),
        mechanism=("Concealed normal faults in the Walker Lane / northern Great Basin produce "
                   "potential-field gradients with no DEM scarp (A-confident, B-abstains), while "
                   "roads, canals and erosion lines produce the reverse (B-only)."),
        named_non_fault_mimic=("Lithologic contacts and basin-fill thickness steps mimic gravity/"
                               "conductivity gradients (A branch); roads, canals and erosion lines "
                               "mimic DEM linearity (B branch). Both are named in the reasoning CSV."),
        holdout=dict(
            evidence_class="HOLDOUT-DTI", evaluator=hold["evaluator"],
            budget_per_fold_reference=hold["budget_reference_per_fold"],
            budget_per_fold_pm=hold["budget_pm_per_fold"],
            withheld_positive_px={k: hold[k]["pooled"]["scores"]["h88_strat"]
                                  ["withheld_positive_pixels"]
                                  for k in ("pooled_hide_9400", "pm_hide", "pm_offcatalogue")},
            arms={k: {a: hold[k]["pooled"]["scores"][a]["dti"] for a in ARMS}
                  for k in ("pooled_hide_9400", "pm_hide", "pm_offcatalogue")},
            ci95={k: {a: hold[k]["pooled"]["scores"][a].get("ci95") for a in ARMS}
                 for k in ("pooled_hide_9400", "pm_hide", "pm_offcatalogue")},
            paired_vs={k: {a: hold[k]["pooled"]["paired_differences"].get(a)
                           for a in ARMS} for k in ("pooled_hide_9400", "pm_hide",
                                                    "pm_offcatalogue")},
            canary=hold["canary"]),
        budget_calibration=dict(rule=pm["budget_rule"], per_fold=pm["chosen_budget_per_fold"],
                                whole_grid=pm["chosen_budget_whole_grid"],
                                curve={k: {b: v["candidate"]["dti"] for b, v in
                                           pm["curve"][k].items()}
                                       for k in pm["curve"]}),
        raster=dict(file=build["file"], sha256=build["sha256"], bytes=build["bytes"],
                    zip_file=build["zip_file"], zip_sha256=build["zip_sha256"],
                    placed=build["placed"], strata=build["strata"],
                    a_only_reasoning_csv=build["a_only_reasoning_csv"]),
        not_union=build["not_union"],
        validator=report,
        lane=dict(dots=reading(lane_dots), surface=reading(lane_surf),
                  registry=f"{len(scored)} scored/calibration rasters (data/scored + reference)",
                  note=("the literal full-census dots rule is unsatisfiable for every nonempty "
                        "raster because universal-coverage probes exist; both readings published")),
        submission_name=build["receipt"]["submission_name"],
        note=build["receipt"]["note"],
        note_chars=build["receipt"]["note_chars"],
        organiser_confirmed_scores="none in this repository; all board numbers are owner-reported",
        evidence_class_note=("HOLDOUT-DTI = evaluator gems52-pooled-hide-v1 with the fold count and "
                             "withheld positives above; OFFCAT-DTI = prevalence-matched "
                             "off-catalogue proxy, diagnostic only; MEASURED = read from bytes."),
        receipts=["evidence/h88_pm_budget.json", "evidence/h88_holdout.json",
                  "evidence/h88_build.json", "docs/downloads/" + build["a_only_reasoning_csv"]],
        verdict=None)
    h = card["holdout"]["arms"]
    beats_random = float(h["pm_hide"]["h88_strat"]) > float(h["pm_hide"]["random"])
    beats_single_b = float(h["pm_hide"]["h88_strat"]) > float(h["pm_hide"]["single_B"])
    # repository promotion rule: format + not-union + beats random + does not lose to the
    # single-view baseline on either hide instrument (the rule that has governed every round here)
    beats_single_b_ref = (float(h["pooled_hide_9400"]["h88_strat"])
                          > float(h["pooled_hide_9400"]["single_B"]))
    card["verdict"] = ("promote" if (report["below_0"] == 0 and report["above_1"] == 0
                                     and not report["non_finite"]
                                     and build["not_union"]["verdict"].startswith("PASS")
                                     and beats_random and beats_single_b and beats_single_b_ref)
                       else "negative")
    card["verdict_reason"] = (
        f"promotion requires format + not-union + beats_random + does not lose to single_B on "
        f"either hide instrument. pm-hide: h88_strat {h['pm_hide']['h88_strat']:.6f} vs random "
        f"{h['pm_hide']['random']:.6f} (beats_random={beats_random}) vs single_B "
        f"{h['pm_hide']['single_B']:.6f} (beats_single_b={beats_single_b}); reference-density hide: "
        f"h88_strat {h['pooled_hide_9400']['h88_strat']:.6f} vs single_B "
        f"{h['pooled_hide_9400']['single_B']:.6f} (beats_single_b_ref={beats_single_b_ref}); "
        f"off-catalogue: {h['pm_offcatalogue']['h88_strat']:.6f} vs random "
        f"{h['pm_offcatalogue']['random']:.6f} (indistinguishable). The A-only reservation is a real "
        f"cost: the A_only arm is below random on both hide instruments.")
    write("run_card", card)
    return card


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pm", "holdout", "build", "card", "all"])
    a = ap.parse_args()
    t0 = time.time()
    if a.stage in ("pm", "all"):
        stage_pm()
    if a.stage in ("holdout", "all"):
        stage_holdout()
    if a.stage in ("build", "all"):
        stage_build()
    if a.stage in ("card", "all"):
        stage_card()
    log(f"H88 {a.stage} done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
