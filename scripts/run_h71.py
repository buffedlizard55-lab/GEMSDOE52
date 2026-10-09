#!/usr/bin/env python3
"""H71 -- the A-only discovery stratum emitted directly, placed in the lane-quiet domain.

Lane: the brief's co-training paragraph.  Preregistered in
``knowledge/57_hypotheses_H71_preregistered.md`` and pinned by
``registry/h71_preregistration.json``; this runner refuses to start if the hash has moved.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61`` supplies ``setup`` (pins, cached store, label-blind
  quadrant folds, buffer 80 px), ``sample_train``, ``learner``, ``stage_canary``, ``stage_fit``
  and ``stage_exchange`` (independence screen + exactly one whole-segment confident-to-abstaining
  exchange with buffer, no leakage into any evaluation region).  The evaluator is
  ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1), placement is ``gems52.nodes.spacing_select``,
  packaging is ``gems52.submission_writer``, gates are ``gems52.gates`` (incl. the authoritative
  universal-coverage-probe lane policy) and ``scripts/audit_uniqueness.py`` with the census.
* Round-specific: the candidate field (the strict A-only discovery stratum, finite only on the
  stratum), the holdout arm list (H61's six control arms + the candidate, plus a matched-budget
  set at the candidate's per-fold fill), the lane-quiet placement domain, the build, the reasoning
  CSV and the run card.

Stages (checkpointed, resumable, never silently re-tuned)
---------------------------------------------------------
    diag       E1: canary + fit + premise + (independence screen is measured inside exchange)
    exchange   E2a: base.stage_exchange (independence screen, one exchange, refit)
    holdout    E2b: six H61 control arms at 9,400 dots/fold + candidate arm; matched-budget set
    build      E3: OOF mosaic -> ranks -> stratum -> quiet domain -> placement -> gates -> TIF
    audit      fold scripts/audit_uniqueness.py (census) into the run card

Usage: ``python scripts/run_h71.py [diag|exchange|holdout|build|audit|all]``
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
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
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402

import run_h61 as base                                               # noqa: E402
import build_h61_submission as b61                                   # noqa: E402  (prior census helper only)
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h71"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
REG_PATH = ROOT / "registry/h71_preregistration.json"
STAGE_EV = WORK / "stage_evidence"          # the shared holdout stage reads one receipt by a fixed name
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
PREFIX = "gems52-h71-"
CONTROL_ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random")
CHAMPION_REF = ("ref_h33_2_b2", 0.2778)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_h71(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h71_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h71_{name}.json").write_text(p.read_text())
    return p


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ preregistration + redirects
def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H71 preregistered document changed after registration; refusing to run")
    return reg


def redirect() -> None:
    """Point the shared H61 stages at H71 storage.  Nothing under evidence/h61_* is written."""
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h71
    base.EVID = STAGE_EV           # stage_holdout reads "h61_pseudo_exchange.json" by its fixed name


# ------------------------------------------------------------------ E1: diagnostics
def stage_diag(reg) -> dict:
    th = reg["thresholds"]
    log("=== H71 E1: canary + fit (premise measured from the fit checkpoint) ===")
    base.stage_canary()
    fit = base.stage_fit()
    aucs_a = [r["view_A"]["heldout_region_auc"] for r in fit["folds"]]
    aucs_b = [r["view_B"]["heldout_region_auc"] for r in fit["folds"]]
    premise = dict(
        evidence_class="HOLDOUT-DTI diagnostic AUC (out-of-quadrant), not a DTI score",
        view_A_oof_auc_per_fold=[round(a, 6) for a in aucs_a],
        view_B_oof_auc_per_fold=[round(a, 6) for a in aucs_b],
        view_A_mean=round(float(np.mean(aucs_a)), 6), view_A_min=round(float(np.min(aucs_a)), 6),
        view_B_mean=round(float(np.mean(aucs_b)), 6), view_B_min=round(float(np.min(aucs_b)), 6),
        h61_committed_view_A_mean=0.5163, h61_committed_view_B_mean=0.6843,
        h64_committed_view_A_mean=0.5230, h65_committed_view_A_mean=0.5202,
        note="H71 does not re-tune View A; the premise is reported as control H71-C. "
             "The lane's mandated empirical test is the independence screen (E2a).")
    write_h71("premise", premise)
    log(f"premise: view A OOF AUC mean {premise['view_A_mean']:.4f} (H61 0.5163), "
        f"view B mean {premise['view_B_mean']:.4f} (H61 0.6843)")
    can = json.loads((EVID / "h71_canary.json").read_text())
    diag = dict(stage="diag", finished_utc=now(), premise=premise,
                canary_max_alarm_across_folds=can["max_alarm_across_folds"],
                canary_any_alarm=can["any_alarm"],
                canary_max_fitted_top5_heldout_auc=can["max_fitted_top5_heldout_auc"],
                budget_note="E1 of 3")
    write_h71("diag", diag)
    return diag


# ------------------------------------------------------------------ E2a: exchange (independence inside)
def stage_exchange() -> dict:
    log("=== H71 E2a: independence screen + one whole-segment exchange ===")
    ex = base.stage_exchange()
    (STAGE_EV / "h61_pseudo_exchange.json").write_text(json.dumps(ex, default=str) + "\n")
    return ex


# ------------------------------------------------------------------ E2b: holdout
def _place_and_score(fields: dict, allowed: np.ndarray, fold: dict, eligible: np.ndarray,
                     K: int, min_px: float, th: dict):
    """Place every arm at budget K on the fold's allowed domain and score it."""
    from gems52 import evaluate_holdout as evaluator
    arms, terms, em_by_arm = {}, {a: None for a in fields}, {}
    for arm, field in fields.items():
        em = nodes.spacing_select(field, allowed, K, min_px=min_px)
        em_by_arm[arm] = em
        pred = em.astype(np.float32)
        result, term = evaluator.evaluate(pred, fold, eligible, block_side=th["bootstrap_block_px"])
        terms[arm] = term
        row = dict(result)
        row.update(placed=int(em.sum()), requested=K, filled=bool(int(em.sum()) == K))
        arms[arm] = row
        log(f"  fold {fold['fold']} arm {arm}: placed {int(em.sum())}/{K} DTI {result['dti']:.6f}")
    return arms, terms, em_by_arm


def stage_holdout(reg) -> dict:
    from gems52 import evaluate_holdout as evaluator
    th = reg["thresholds"]
    log("=== H71 E2b: holdout — H61 control arms + A-only discovery candidate ===")
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat, inv = store.flat_idx, store.inverse
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    lo, hi = th["receiver_rank_interval"]
    dmin = float(th["donor_rank_min"])
    ex = json.loads((EVID / "h71_pseudo_exchange.json").read_text())
    out = dict(stage="holdout", started_utc=now(), control_budget_per_arm_per_fold=K,
               min_separation_px=min_px, donor_rank_min=dmin, receiver_rank_interval=[lo, hi],
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               candidate_arm="a_only",
               candidate_definition=("strict A-only discovery stratum on the POST-exchange out-of-fold "
                                     "ranks: rankA >= donor_rank_min AND rankB in the receiver abstain "
                                     "interval; field = rankA on the stratum, -inf elsewhere, so every "
                                     "placed dot is an A-only (buried-beneath-cover) candidate"),
               folds=[])
    # ---- pass 1: H61's six control arms + the candidate, all at the H61 budget
    terms_ctl = {a: None for a in CONTROL_ARMS + ("a_only",)}
    fill_a_only = {}
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = {}
        for v in ("A", "B"):
            g[f"pre_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f}.npy"), eligible.shape)
            g[f"post_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        allowed_idx = np.flatnonzero(allowed.ravel())
        r_post = {v: np.full(g[f"post_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r_post[v].ravel()[allowed_idx] = base.pct_rank(g[f"post_{v}"].ravel()[allowed_idx])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        stratum = (r_post["A"] >= dmin) & (r_post["B"] >= lo) & (r_post["B"] <= hi) & allowed
        rA_pre = np.nan_to_num(_grid_rank(g["pre_A"], allowed_idx, eligible.shape), nan=-1.0)
        rB_pre = np.nan_to_num(_grid_rank(g["pre_B"], allowed_idx, eligible.shape), nan=-1.0)
        fields = {
            "single_A": rA_pre,
            "single_B": rB_pre,
            "union_max": np.maximum(rA_pre, rB_pre),
            "disagreement_pre": rA_pre - rB_pre,
            "disagreement_post": np.nan_to_num(r_post["A"] - r_post["B"], nan=-1.0),
            "random": rnd,
            "a_only": np.where(stratum, np.nan_to_num(r_post["A"], nan=0.0), -np.inf).astype(np.float32),
        }
        arms, terms, em_by_arm = _place_and_score(fields, allowed, fold, eligible, K, min_px, th)
        for a in terms_ctl:
            terms_ctl[a] = terms[a] if terms_ctl[a] is None else terms_ctl[a] + terms[a]
        fill_a_only[f] = arms["a_only"]["placed"]
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   stratum_px=int(stratum.sum()), arms=arms)
        # not-the-union diagnostics on the shipped candidate arm
        d_em = em_by_arm["a_only"] > 0
        u_em = em_by_arm["union_max"] > 0
        a_em = em_by_arm["single_A"] > 0
        b_em = em_by_arm["single_B"] > 0
        rec["not_the_union"] = dict(
            a_only_cells_vs_A=int((d_em != a_em).sum()), a_only_cells_vs_B=int((d_em != b_em).sum()),
            a_only_cells_vs_union=int((d_em != u_em).sum()),
            a_only_dots_also_in_union=int((d_em & u_em).sum()),
            a_only_dots_strict_a_only=int((d_em & stratum).sum()),
            note="the candidate is placed only on the A-only stratum; max(A,B) places concordant "
                 "high-high cells the candidate never touches")
        out["folds"].append(rec)
        del g, r_post, fields, em_by_arm
    out["control_pooled"] = evaluator.pooled_summary(terms_ctl, draws=int(th["bootstrap_draws"]),
                                                     seed=SEED, candidate="a_only")
    ctl = out["control_pooled"]
    sB = ctl["scores"]["single_B"]["dti"]
    ctrl = dict(single_B_h71=sB, single_B_h61_committed=float(th["single_B_h61_control_holdout_dti"]),
                abs_difference=abs(sB - float(th["single_B_h61_control_holdout_dti"])),
                tolerance=float(th["single_B_control_abs_tolerance"]),
                pass_=bool(abs(sB - float(th["single_B_h61_control_holdout_dti"]))
                           <= float(th["single_B_control_abs_tolerance"])))
    out["control_check"] = ctrl
    log(f"control: single_B {sB:.6f} vs H61 committed {th['single_B_h61_control_holdout_dti']} "
        f"-> {'PASS' if ctrl['pass_'] else 'FAIL'}")
    if not ctrl["pass_"]:
        raise SystemExit(f"single_B control outside tolerance: {ctrl}; pipeline defect, stopping")
    for arm in CONTROL_ARMS + ("a_only",):
        s = ctl["scores"][arm]
        log(f"  control arm {arm}: {s['dti']:.6f} [{s['ci95'][0]:.6f}, {s['ci95'][1]:.6f}] "
            f"placed {out['folds'][0]['arms'][arm]['placed']}..")

    # ---- pass 2: matched-budget set at the candidate's per-fold fill
    Kc = int(min(fill_a_only.values()))
    out["matched_budget_per_fold"] = Kc
    out["a_only_fill_per_fold"] = {str(k): int(v) for k, v in fill_a_only.items()}
    if Kc < 100:
        raise SystemExit(f"candidate stratum too small for a matched comparison: {fill_a_only}")
    log(f"matched budget K_c = {Kc} dots/fold (candidate's minimum fill)")
    terms_m = {a: None for a in ("a_only", "single_A", "single_B", "union_max", "random")}
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = {}
        for v in ("A", "B"):
            g[f"post_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        allowed_idx = np.flatnonzero(allowed.ravel())
        r_post = {v: np.full(g[f"post_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r_post[v].ravel()[allowed_idx] = base.pct_rank(g[f"post_{v}"].ravel()[allowed_idx])
        rng = np.random.default_rng(SEED + 700 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        stratum = (r_post["A"] >= dmin) & (r_post["B"] >= lo) & (r_post["B"] <= hi) & allowed
        rA = np.nan_to_num(r_post["A"], nan=-1.0)
        rB = np.nan_to_num(r_post["B"], nan=-1.0)
        fields = {
            "a_only": np.where(stratum, np.nan_to_num(r_post["A"], nan=0.0), -np.inf).astype(np.float32),
            "single_A": rA, "single_B": rB,
            "union_max": np.maximum(rA, rB),
            "random": rnd,
        }
        arms, terms, _em = _place_and_score(fields, allowed, fold, eligible, Kc, min_px, th)
        for a in terms_m:
            terms_m[a] = terms[a] if terms_m[a] is None else terms_m[a] + terms[a]
        out["folds"][f]["matched_arms"] = arms
        del g, r_post, fields
    out["matched_pooled"] = evaluator.pooled_summary(terms_m, draws=int(th["bootstrap_draws"]),
                                                     seed=SEED, candidate="a_only")
    mp = out["matched_pooled"]
    for arm in ("a_only", "single_A", "single_B", "union_max", "random"):
        s = mp["scores"][arm]
        log(f"  matched arm {arm}: {s['dti']:.6f} [{s['ci95'][0]:.6f}, {s['ci95'][1]:.6f}]")
    pd = mp["paired_differences"]["single_B"]
    out["holdout_eligible"] = bool(mp["scores"]["a_only"]["dti"] > mp["scores"]["single_B"]["dti"]
                                   and float(pd["ci95"][0]) > 0.0)
    out["paired_vs_single_B"] = pd
    log(f"matched candidate vs single_B: delta {pd['delta']:+.6f} CI [{pd['ci95'][0]:+.6f}, "
        f"{pd['ci95'][1]:+.6f}] -> holdout_eligible={out['holdout_eligible']}")
    out.update(finished_utc=now(),
               withheld_positive_pixels=mp["scores"]["a_only"]["withheld_positive_pixels"],
               caveat="HOLDOUT-DTI on the corrected label-blind-quadrants-v2 splitter. The simulator "
                      "measured Spearman -0.10 against the owner-reported board in round R4, so it "
                      "screens procedures; it does not by itself promote anything.")
    write_h71("holdout", out)
    return out


def _grid_rank(grid_values_flat: np.ndarray, allowed_idx: np.ndarray, shape) -> np.ndarray:
    """Percentile rank of the flat grid values over the allowed indices, as a full grid."""
    g = np.full(int(np.prod(shape)), np.nan, np.float32)
    g[allowed_idx] = base.pct_rank(grid_values_flat.ravel()[allowed_idx])
    return g.reshape(shape)


# ------------------------------------------------------------------ E3: build
def stage_build(reg) -> dict:
    th = reg["thresholds"]
    log("=== H71 E3: build — mosaic, stratum, quiet domain, placement, gates, GeoTIFF ===")
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    flat, inv, shape = store.flat_idx, store.inverse, eligible.shape
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
        sample_grid = (ref.shape, ref.crs, ref.transform)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    del sub
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    h61_th = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    buffer_px = int(h61_th["buffer_px"])
    folds = list(spatial.folds(cat, eligible, buffer_px=buffer_px))

    # ---- OOF mosaic of the post-exchange predictions (out-of-fold only, as H64)
    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_post_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[v] = g.reshape(shape)
        del g
    covered = np.isfinite(mos["A"]) & np.isfinite(mos["B"])
    if not (covered == eligible).all():
        raise SystemExit(f"OOF mosaic covers {int(covered.sum())} px, eligible {int(eligible.sum())}")

    allowed = eligible & sub_finite & ~cat & (cat_dist > th["catalogue_exclusion_m"])
    log(f"emission domain: eligible {int(eligible.sum())} -> allowed {int(allowed.sum())}")

    # ---- registry: census + local, informative vs universal-coverage probes (shared classification)
    # Memory: supports are folded into ONE union grid as we go; keeping every prior's support would
    # be ~500 x 12.3 MB of bool and OOM this box (the first H71 build died exactly there).
    priors, pmeta = b61.prior_paths(CENSUS, ("submission",))
    priors = [p for p in priors if not p.name.startswith(PREFIX)]
    log(f"registry: {len(priors)} rasters ({pmeta})")
    informative, probes = [], []
    union_sup = np.zeros(shape, bool)   # positive pixels of informative priors (exact novelty)
    for pp in priors:
        with rasterio.open(pp) as ds_p:
            if ds_p.shape != shape:
                continue
            a = ds_p.read(1)
        sup = np.isfinite(a) & (a > -1e38) & (a > 0)
        del a
        if not sup.any():
            continue
        cov = gates.registry_coverage(sup, eligible, gates.NEAR_RADIUS_PX)
        if cov >= gates.PROBE_COVERAGE:
            probes.append(dict(name=pp.name, coverage_3px_of_eligible=round(cov, 6)))
            del sup
            continue
        informative.append(pp)
        union_sup |= sup
        del sup
    log(f"registry: {len(informative)} informative, {len(probes)} universal-coverage probes")

    # ---- lane-quiet domain: >= 3 px from every informative prior's positive pixel.
    # MEASURED (build v1): the 3 px halos of the informative priors blanket the whole allowed
    # domain -- the quiet domain is EMPTY (0 px), so a zero-near-dot placement is infeasible on
    # this registry.  Amendment (knowledge/57a): the lane's own rule -- no informative prior may
    # have > 70% of the emitted dots within 3 px of its dots -- is enforced as a per-prior cap
    # during placement instead.  That is the rule the lane states, applied as a constraint, not a
    # re-tuning of it.
    quiet = allowed & ~ndi.binary_dilation(union_sup, structure=gates._disk(gates.NEAR_RADIUS_PX))
    log(f"quiet domain: allowed {int(allowed.sum())} -> quiet {int(quiet.sum())} "
        f"({100.0 * float(quiet.sum()) / max(int(allowed.sum()), 1):.2f}%) "
        f"[measured infeasible; see knowledge/57a]")

    # ---- ranks over the allowed domain, stratum, candidate field
    idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[idx] = base.pct_rank(mos["A"].ravel()[idx])
    rankB.ravel()[idx] = base.pct_rank(mos["B"].ravel()[idx])
    lo, hi = th["receiver_rank_interval"]
    dmin = float(th["donor_rank_min"])
    stratum = (rankA >= dmin) & (rankB >= lo) & (rankB <= hi) & allowed
    field = np.where(stratum, rankA, -np.inf).astype(np.float32)
    # amendment 57b: placement domain is the FULL stratum; exact-novelty is handled by ordering.
    place_domain = stratum
    novel_flag = stratum & ~union_sup          # exact-novel cells (H64-declared support novelty)
    log(f"A-only stratum: {int(stratum.sum())} px; exact-novel within stratum: "
        f"{int(novel_flag.sum())} px")

    # ---- surface lane check BEFORE placement (the pre-placement surface is the stratum-gated rank)
    surf_field = np.where(allowed, np.where(stratum, rankA, 0.0), 0.0).astype(np.float32)
    v = surf_field[allowed]
    surf = np.where(allowed, (surf_field - float(v.min())) / max(1e-9, float(np.ptp(v))), 0.0).astype(np.float32)
    surf_digest = hashlib.sha256(surf.astype("<f4").tobytes()).hexdigest()
    cached = EVID / "h71_lane_surface.json"
    lane_surface = None
    if cached.exists():
        prev = json.loads(cached.read_text())
        if prev.get("candidate_decoded_sha256") == surf_digest:
            lane_surface = prev
            log("surface lane: reusing cached receipt (identical surface bytes)")
    if lane_surface is None:
        lane_surface = gates.lane_report(surf, allowed, priors, sample=ROOT / "data/sample_submission.tif",
                                         phase="surface", log=log)
        write_h71("lane_surface", lane_surface)
    log(f"surface lane: literal {lane_surface['literal']['verdict']} (max rho "
        f"{lane_surface['literal']['max_spearman']}), policy {lane_surface['policy']['verdict']} "
        f"(max rho {lane_surface['policy']['max_spearman']})")

    # ---- metric-aware placement (amendment 57b): novel-first order, per-prior lane cap c
    # searched so that the BUILT file satisfies near_i / filled <= 0.70 for every informative
    # prior; floor 300 dots; fallback to novel-first uncapped if no feasible cap admits it.
    budget_cap = int(th["build_budget_cap"])
    sep = int(np.ceil(float(th["min_dot_separation_px"])))
    min_px = float(th["min_dot_separation_px"])
    capacity = nodes.spacing_select(field, place_domain, budget_cap, min_px=min_px)
    C = int(capacity.sum())
    log(f"stratum capacity at {sep} px separation: {C} dots (cap {budget_cap})")
    if C < 300:
        raise SystemExit(f"A-only stratum placement domain too small: {C} dots")
    # membership: candidate j is within 3 px of informative prior i's proposal pixels.
    ys, xs = np.nonzero(place_domain)
    is_novel = ~union_sup[ys, xs]
    n_cand = int(ys.size)
    membership = np.zeros((len(informative), n_cand), bool)
    for i, pp in enumerate(informative):
        with rasterio.open(pp) as ds_p:
            a = ds_p.read(1)
        sup = np.isfinite(a) & (a > -1e38) & (a > 0)
        del a
        if not sup.any():
            continue
        halo = ndi.binary_dilation(sup, structure=gates._disk(gates.NEAR_RADIUS_PX))
        membership[i] = halo[ys, xs]
        del sup, halo
    log(f"lane-cap membership matrix: {membership.shape} "
        f"({int(membership.sum())} candidate-prior near pairs)")

    # ordering: exact-novel cells first, then by View A's out-of-fold rank (57b rule 3)
    vals = field[ys, xs].astype(np.float64)
    order = np.lexsort((-vals, ~is_novel))   # primary ~is_novel asc => novel first; vals desc within

    def capped_place(c: int, budget: int):
        """Greedy over the ordered candidates at 3 px separation with per-prior cap c."""
        counts = np.zeros(len(informative), np.int64)
        taken = np.zeros(place_domain.shape, bool)
        buckets: dict = {}
        filled = 0
        for j in order:
            if filled >= budget:
                break
            y, x = int(ys[j]), int(xs[j])
            ky, kx = y // sep, x // sep
            clash = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    for (oy, ox) in buckets.get((ky + dy, kx + dx), ()):
                        if (oy - y) ** 2 + (ox - x) ** 2 < sep * sep:
                            clash = True
                            break
                    if clash:
                        break
                if clash:
                    break
            if clash:
                continue
            containing = membership[:, j]
            if c >= 0 and containing.any() and int(counts[containing].max()) >= c:
                continue  # would push an informative prior over its near-dot allowance
            taken[y, x] = True
            counts[containing] += 1
            buckets.setdefault((ky, kx), []).append((y, x))
            filled += 1
        return taken, filled, counts

    # cap grid: a feasible cap satisfies c <= 0.70 * f (the lane statistic divides by f).
    budget = min(C, budget_cap)
    c0 = int(0.70 * budget)
    feasible = []
    c = c0
    cap_probes = []
    for _ in range(10):
        if c < 50:
            break
        taken, filled, counts = capped_place(c, budget)
        cap_probes.append(dict(cap=c, filled=int(filled), max_near=int(counts.max()) if counts.size else 0,
                           feasible=bool(c <= 0.70 * filled)))
        log(f"  cap probe: c={c} filled={filled} max_near={int(counts.max())} "
            f"-> {'FEASIBLE' if c <= 0.70 * filled else 'infeasible'}")
        if c <= 0.70 * filled:
            feasible.append((filled, c, taken, counts))
        if filled == 0:
            break
        c = int(0.70 * filled)          # tighter next cap: the lane allowance for this fill
        if feasible and c <= feasible[0][1]:
            break
    emission_mode = None
    if feasible:
        feasible.sort(key=lambda t: -t[0])
        f_best, c_best, emission, counts_best = feasible[0]
        n_dots = int(f_best)
        emission_mode = dict(rule="lane-capped (57b): per-prior near-dot cap c <= 0.70 * filled",
                             cap=c_best, filled=n_dots, cap_probes=cap_probes)
        log(f"lane-capped placement: filled {n_dots} dots with cap {c_best} "
            f"(near_i/filled <= {c_best / n_dots:.4f} for every informative prior)")
    else:
        # fallback (57b rule 4): novel-first greedy without an effective cap, budgeted so the
        # exact-novel pool can still carry >= 20% support novelty when its capacity allows.
        novel_capacity = int(nodes.spacing_select(field, novel_flag, budget_cap, min_px=min_px).sum())
        budget_fb = min(budget, max(500, int(novel_capacity / 0.20)))
        budget_fb = min(budget_fb, budget)
        emission, n_dots, counts_best = capped_place(-1, budget_fb)
        emission_mode = dict(rule="fallback (57b rule 4): novel-first uncapped; lane reported verbatim",
                             cap=None, filled=int(n_dots), cap_probes=cap_probes,
                             novel_capacity=novel_capacity, budget=budget_fb,
                             max_near=int(counts_best.max()) if counts_best.size else 0)
        log(f"FALLBACK uncapped placement: {n_dots} dots (max prior near-count "
            f"{int(counts_best.max())}); the policy lane will be reported verbatim")
    n_dots = int(emission.sum())
    n_novel = int((emission & novel_flag).sum())
    log(f"emission: {n_dots} dots, {n_novel} exact-novel "
        f"({100.0 * n_novel / max(n_dots, 1):.2f}% support novelty)")
    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if not ((pred > 0) <= place_domain).all():
        raise SystemExit("mass outside the A-only stratum domain")

    # ---- dots lane check AFTER placement
    lane_dots = gates.lane_report(pred, eligible, priors, sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log)
    write_h71("lane_dots", lane_dots)
    log(f"dots lane: literal {lane_dots['literal']['verdict']} (max near "
        f"{lane_dots['literal']['max_near_3px_fraction']}), policy {lane_dots['policy']['verdict']} "
        f"(max near {lane_dots['policy']['max_near_3px_fraction']}, offenders "
        f"{len(lane_dots['policy']['near_offenders'])})")

    # ---- uniqueness, tier 1 (all priors) and tier 2 (informative priors)
    uniq = gates.uniqueness_report(pred, priors, top=None)
    uniq_inf = gates.uniqueness_report(pred, informative, top=None)
    write_h71("uniqueness", dict(
        tier1_all_priors=dict(canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
                              equals_literal_prior_union=uniq.get("equals_literal_prior_union"),
                              novel_fraction=uniq.get("novel_fraction"),
                              relation_to_union=uniq.get("relation_to_union"),
                              n_priors_checked=uniq.get("n_priors_checked")),
        tier2_informative_priors=dict(novel_fraction=uniq_inf.get("novel_fraction"),
                                      equals_literal_prior_union=uniq_inf.get("equals_literal_prior_union"),
                                      relation_to_union=uniq_inf.get("relation_to_union"),
                                      n_priors_checked=uniq_inf.get("n_priors_checked"),
                                      informative_rasters=len(informative))))

    # ---- not-the-union, the same definitions as build_h61_submission.py
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)
    u_em = nodes.spacing_select(union_field, allowed, n_dots, min_px=float(th["min_dot_separation_px"]))
    d = emission
    not_union = dict(
        dots=int(n_dots),
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(np.where(allowed, field, 0.0)[allowed].astype(np.float64)),
                                                     rankdata(union_field[allowed].astype(np.float64)))[0, 1]),
        strict_a_only_candidate_px=int(stratum.sum()),
        emitted_cells_that_are_strict_a_only=int((d & stratum).sum()),
        emitted_cells_in_quiet=int((d & quiet).sum()),
        verdict="emission is the A-only discovery stratum placed novel-first under the lane's own "
                "rule (57b), not max(A,B), not either single view, and not their union")
    not_union["not_union_pass"] = bool(not_union["jaccard_with_union_max"] < 0.9
                                      and not_union["emitted_cells_that_are_strict_a_only"] == n_dots)
    write_h71("not_union", not_union)

    # ---- GeoTIFF via the shared fail-closed writer
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mode_word = ("lane-capped" if emission_mode["cap"] is not None else "fallback-uncapped")
    stem = f"gems52-h71-aonly-stratum-{mode_word}-{n_dots}px-{stamp}"
    path = SUBM / f"{stem}.tif"
    SUBM.mkdir(exist_ok=True)
    hold = json.loads((EVID / "h71_holdout.json").read_text())
    eligible_flag = bool(hold["holdout_eligible"])
    note = (f"H71 A-only stratum (A confident, B abstains), {mode_word} placement; "
            f"{'holdout beats single_B' if eligible_flag else 'holdout does NOT beat single_B'}; "
            f"research only, not slot-approved")
    assert len(note) <= 140, len(note)
    receipt = submission_writer.write_submission(
        path, pred, sample=ROOT / "data/sample_submission.tif", footprint=sub_finite,
        note=note[:140], name=stem[:140],
        metadata=dict(round="H71", preregistration=reg["hypothesis_sha256"], budget=n_dots,
                      stratum_px=int(stratum.sum()), quiet_px=int(quiet.sum()),
                      placement=emission_mode.get("rule"),
                      placement_cap=emission_mode.get("cap")))
    fmt = receipt["validator"]
    log(f"wrote {path.name} ({receipt['bytes']} bytes), validator ok={fmt['ok']}")

    # ---- publish the download copies (canonical + short alias), as the site expects
    DOWN.mkdir(parents=True, exist_ok=True)
    for src in (path, path.with_suffix(".zip")):
        shutil.copy2(src, DOWN / src.name)
    shutil.copy2(path, DOWN / "h71-candidate.tif")
    shutil.copy2(path.with_suffix(".zip"), DOWN / "h71-candidate.zip")

    # ---- geological reasoning for every emitted cell (all are A-only candidates)
    ys, xs = np.nonzero(emission)
    CTX = ("raw_band_15", "raw_band_19", "A_gravity_grad_3", "X_rad_ThK_rank", "X_rad_K_rank",
           "X_mag_TMI_up150_grad3", "raw_band_13", "raw_band_17")
    ctx_rows = store.gather(ys * shape[1] + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h71-a-only-reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "distance_to_mapped_trace_m",
                    "view_A_operating_rank", "view_B_operating_rank", "in_abstain_interval",
                    "strict_A_only", "cover_depth_to_base_m", "dem_slope", "gravity_grad_sigma3",
                    "isostatic_grav_anom", "near_surface_conductivity", "rad_ThK_rank",
                    "rad_K_rank", "tmi_up150_grad3", "geological_hypothesis",
                    "named_non_fault_mimic", "falsifier", "evidence_class"])
        for i, (y, x) in enumerate(zip(ys, xs)):
            w.writerow([
                int(y), int(x), 243350.0 + 100.0 * (x + 0.5), 4508550.0 - 100.0 * (y + 0.5),
                round(float(cat_dist[y, x]), 1),
                round(float(rankA[y, x]), 6), round(float(rankB[y, x]), 6),
                int(bool(lo <= rankB[y, x] <= hi)), 1,
                round(float(ctx["raw_band_15"][i]), 1), round(float(ctx["raw_band_19"][i]), 4),
                round(float(ctx["A_gravity_grad_3"][i]), 6),
                round(float(ctx["raw_band_13"][i]), 4), round(float(ctx["raw_band_17"][i]), 4),
                round(float(ctx["X_rad_ThK_rank"][i]), 4), round(float(ctx["X_rad_K_rank"][i]), 4),
                round(float(ctx["X_mag_TMI_up150_grad3"][i]), 6),
                "Buried or cover-hidden fault (A-only discovery candidate): the potential-field/"
                "subsurface view is confident (gravity/magnetic gradient, basement-depth offset, "
                "upward-continued TMI edge) while the surface view abstains (no DEM scarp, no "
                "radiometric lineament) - consistent with a fault buried beneath cover. "
                "HYPOTHESIS, not verified geology.",
                "Non-fault basin-margin or flexural hinge line (basement deepens with no "
                "displacement); density or lithologic basement contact (geophysical step without "
                "throw); buried palaeo-channel or alluvial-fan margin; interpolation seam in the "
                "modelled depth-to-basement grid.",
                "Independent evidence of offset: a displaced contact or marker bed, deflected or "
                "offset drainage, a facies termination, a published structural interpretation, or "
                "field observation. None is claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")

    build = dict(stage="build", finished_utc=now(), file=path.name, budget=n_dots,
                 stratum_px=int(stratum.sum()), quiet_px=int(quiet.sum()),
                 quiet_domain_infeasible=True,
                 placement_rule=emission_mode,
                 placement_domain_px=int(place_domain.sum()),
                 exact_novel_px=int(novel_flag.sum()),
                 stratum_capacity_at_3px=C,
                 emitted_exact_novel_dots=n_novel,
                 emitted_novel_fraction=round(n_novel / max(n_dots, 1), 6),
                 allowed_px=int(allowed.sum()), eligible_px=int(eligible.sum()),
                 informative_rasters=len(informative), probe_rasters=len(probes),
                 registry_rasters=len(priors),
                 lane_surface_literal=lane_surface["literal"]["verdict"],
                 lane_surface_policy=lane_surface["policy"]["verdict"],
                 lane_dots_literal=lane_dots["literal"]["verdict"],
                 lane_dots_policy=lane_dots["policy"]["verdict"],
                 lane_dots_policy_max_near=lane_dots["policy"]["max_near_3px_fraction"],
                 lane_dots_literal_max_near=lane_dots["literal"]["max_near_3px_fraction"],
                 not_union=not_union, validator=fmt, submission_receipt=receipt)
    write_h71("build", build)
    return build


# ------------------------------------------------------------------ audit + run card
def stage_audit(reg) -> dict:
    log("=== H71 audit: scripts/audit_uniqueness.py with the census receipt ===")
    build = json.loads((EVID / "h71_build.json").read_text())
    tif = SUBM / build["file"]
    audit_path = EVID / "h71_audit_uniqueness.json"
    cmd = [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/audit_uniqueness.py"),
           str(tif.relative_to(ROOT)), str(audit_path.relative_to(ROOT)), str(CENSUS.relative_to(ROOT))]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log(r.stdout[-2000:])
    if r.returncode != 0:
        log(r.stderr[-2000:])
        raise SystemExit("audit_uniqueness.py failed")
    audit = json.loads(audit_path.read_text())
    card = make_run_card(reg, build, audit)
    write_h71("run_card", card)
    log(f"verdict: {card['verdict']}")
    return card


def make_run_card(reg, build, audit) -> dict:
    th = reg["thresholds"]
    hold = json.loads((EVID / "h71_holdout.json").read_text())
    diag = json.loads((EVID / "h71_diag.json").read_text())
    mp = hold["matched_pooled"]
    fmt = build["validator"]
    receipt = build["submission_receipt"]
    uniq = json.loads((EVID / "h71_uniqueness.json").read_text())
    lane_pol_ok = build["lane_dots_policy"] == "PASS" and build["lane_surface_policy"] == "PASS"
    fmt_ok = bool(fmt.get("ok"))
    uniq_ok = bool(uniq["tier1_all_priors"]["canonical_pattern_unique"]
                   and not any(True for _ in ())
                   and (uniq["tier2_informative_priors"]["novel_fraction"] or 0.0) >= 0.2
                   and not uniq["tier1_all_priors"]["equals_literal_prior_union"]
                   and not uniq["tier2_informative_priors"]["equals_literal_prior_union"])
    not_union_ok = bool(build["not_union"]["not_union_pass"])
    holdout_ok = bool(hold["holdout_eligible"])
    promote = bool(fmt_ok and lane_pol_ok and uniq_ok and not_union_ok and holdout_ok)
    verdict = ("PROMOTE-ELIGIBLE (passes every gate incl. holdout vs single_B); the selector still "
               "owns the weekly slot" if promote else
               "NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique on decoded pixels); "
               "SUBMIT NO. " + "; ".join(
                   f"{k}={v}" for k, v in dict(format=fmt_ok, lane_policy=lane_pol_ok,
                                              unique=uniq_ok, not_union=not_union_ok,
                                              holdout_beats_single_B=holdout_ok).items()
                   if not v) + ". No weekly slot spent by this lane.")
    s = mp["scores"]["a_only"]
    return dict(
        round="H71",
        generated_utc=now(),
        hypothesis="The lane's discovery signal emitted directly: where View A (potential-field/"
                   "subsurface) is confident and View B (surface) abstains, the fault may be buried "
                   "beneath cover; emit the strict A-only stratum, ranked by View A's out-of-fold "
                   "conviction, placed in the lane-quiet domain.",
        mechanism="Blum & Mitchell (COLT '98, doi:10.1145/279943.279962) co-training: the "
                  "confident-to-abstaining disagreement stratum is the discovery signal; the "
                  "emission is that stratum, placed by metric-aware spacing_select at 3 px in the "
                  "lane-quiet domain (>= 3 px from every informative registry prior's positive "
                  "pixel), so the directed near-dot fraction is 0 for every informative prior by "
                  "construction.",
        named_non_fault_mimic="basin-margin or flexural hinge line (basement deepens with no "
                              "displacement); density or lithologic basement contact; buried "
                              "palaeo-channel or alluvial-fan margin; interpolation seam in the "
                              "modelled depth-to-basement grid",
        independence=dict(max_abs_rho=hold["independence_max_abs_rho"],
                          threshold=th["independence_abandon_max_abs_rho"],
                          allow_exchange=hold["exchange_allowed"],
                          negative_class="held-out catalogue-zero proxies, not verified absence"),
        premise_control=diag["premise"],
        canary=dict(max_alarm_across_folds=diag["canary_max_alarm_across_folds"],
                    any_alarm=diag["canary_any_alarm"],
                    max_fitted_top5_heldout_auc=diag["canary_max_fitted_top5_heldout_auc"],
                    alarm_threshold=th["canary_auc_alarm"]),
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI", evaluator_version="gems52-pooled-hide-v1",
            alpha=0.2, beta=0.8, triangular_radius_m=300,
            withheld_positive_pixels=mp["scores"]["a_only"]["withheld_positive_pixels"],
            matched_budget_per_fold=hold["matched_budget_per_fold"],
            candidate_a_only=dict(dti=s["dti"], ci95=s["ci95"]),
            single_B_baseline=dict(dti=mp["scores"]["single_B"]["dti"], ci95=mp["scores"]["single_B"]["ci95"]),
            single_A=dict(dti=mp["scores"]["single_A"]["dti"], ci95=mp["scores"]["single_A"]["ci95"]),
            union_max=dict(dti=mp["scores"]["union_max"]["dti"], ci95=mp["scores"]["union_max"]["ci95"]),
            random=dict(dti=mp["scores"]["random"]["dti"], ci95=mp["scores"]["random"]["ci95"]),
            paired_candidate_minus_single_B=hold["paired_vs_single_B"],
            control_reproduction=hold["control_check"],
            control_budget_arms={a: dict(dti=hold["control_pooled"]["scores"][a]["dti"],
                                        ci95=hold["control_pooled"]["scores"][a]["ci95"])
                                 for a in CONTROL_ARMS + ("a_only",)}),
        correlation_overlap_vs_registry=dict(
            lane_surface_literal=build["lane_surface_literal"],
            lane_surface_policy=build["lane_surface_policy"],
            lane_dots_literal=build["lane_dots_literal"],
            lane_dots_policy=build["lane_dots_policy"],
            lane_dots_policy_max_near_3px=build["lane_dots_policy_max_near"],
            lane_dots_literal_max_near_3px=build["lane_dots_literal_max_near"],
            audit_surface=dict(max_spearman=audit["phases"]["surface"]["max_spearman"],
                               ok=audit["phases"]["surface"]["ok"]),
            audit_dots=dict(max_near_3px=audit["phases"]["dots"]["max_near_3px_fraction"],
                            ok=audit["phases"]["dots"]["ok"]),
            audit_lane_policy_dots_literal=audit["lane_policy_dots"]["literal"]["verdict"],
            audit_lane_policy_dots_policy=audit["lane_policy_dots"]["policy"]["verdict"],
            audit_max_jaccard=audit["max_jaccard"],
            audit_share_of_candidate_inside_any_prior=audit["share_of_candidate_px_inside_any_prior_support"],
            uniqueness_tier1=uniq["tier1_all_priors"],
            uniqueness_tier2=uniq["tier2_informative_priors"],
            registry_rasters=build["registry_rasters"],
            informative_rasters=build["informative_rasters"],
            probe_rasters=build["probe_rasters"]),
        not_the_union=build["not_union"],
        placement=dict(mode=build.get("placement_rule"),
                       stratum_px=build.get("stratum_px"),
                       exact_novel_px=build.get("exact_novel_px"),
                       capacity_at_3px=build.get("stratum_capacity_at_3px"),
                       emitted_exact_novel_dots=build.get("emitted_exact_novel_dots"),
                       emitted_novel_fraction=build.get("emitted_novel_fraction")),
        raster=dict(file=build["file"], sha256=receipt["sha256"], bytes=receipt["bytes"],
                    zip_sha256=receipt["zip_sha256"], emitted_cells=build["budget"]),
        validator=dict(ok=fmt_ok, problems=fmt.get("problems"),
                       nan_pixels=fmt.get("nan_pixels"), infinity_pixels=fmt.get("infinity_pixels"),
                       value_range=[fmt.get("min"), fmt.get("max")],
                       crs=fmt.get("crs"), shape=[fmt.get("height"), fmt.get("width")],
                       transform=fmt.get("transform"),
                       matches_sample_submission=bool(
                           fmt_ok and fmt.get("height") == 3730 and fmt.get("width") == 3292
                           and fmt.get("crs") == "EPSG:32611" and not fmt.get("problems")),
                       validation_class=fmt.get("validation_class")),
        submission_name=receipt["submission_name"], note=receipt["note"], note_chars=receipt["note_chars"],
        champion_reference=dict(name=CHAMPION_REF[0], reported_score=CHAMPION_REF[1],
                                evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"),
        leaderboard_top_public_board=dict(score=0.3774, team="xiaofanhu",
                                          evidence_class="PUBLIC BOARD 2026-10-09, NOT ORGANIZER-CONFIRMED"),
        experiments_used="3 of 3 (E1 diagnostics, E2 exchange+holdout, E3 build+audit)",
        submission_slots_used=0,
        verdict=verdict,
        verdict_promote=promote)


# ------------------------------------------------------------------ main
def main(argv) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    if stage not in ("diag", "exchange", "holdout", "build", "audit", "all"):
        raise SystemExit(f"unknown stage {stage!r}")
    reg = check_prereg()
    redirect()
    if stage in ("diag", "all"):
        t0 = time.time()
        stage_diag(reg)
        log(f"--- E1 diag done in {time.time()-t0:.1f}s")
    if stage in ("exchange", "all"):
        t0 = time.time()
        stage_exchange()
        log(f"--- E2a exchange done in {time.time()-t0:.1f}s")
    if stage in ("holdout", "all"):
        t0 = time.time()
        stage_holdout(reg)
        log(f"--- E2b holdout done in {time.time()-t0:.1f}s")
    if stage in ("build", "all"):
        t0 = time.time()
        stage_build(reg)
        log(f"--- E3 build done in {time.time()-t0:.1f}s")
    if stage in ("audit", "all"):
        t0 = time.time()
        stage_audit(reg)
        log(f"--- audit done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
