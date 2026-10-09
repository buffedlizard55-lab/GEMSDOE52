#!/usr/bin/env python3
"""H74 -- deformation-only View A2 (the deferred H70-E variant) in the two-view co-training lane.

Preregistered in ``knowledge/63_hypotheses_H74_preregistered.md`` and pinned by
``registry/h74_preregistration.json``; this runner refuses to start if the hash has moved.

Lane: the brief's co-training paragraph.  View A2 is DEFORMATION-ONLY (geodetic strain bands
4/7/8 + seismicity bands 10/16, with gradient/coherence transforms), View B is surface (DEM
curvature and slope plus the radiometric channels), unchanged, and disagreement is the discovery
signal.  H74 attributes the lane's five consecutive View A sufficiency failures: every previous
View A mixed potential-field and deformation channels; none tested the deformation half alone.

What is shared and what is not
------------------------------
* Shared, not forked: ``src/gems52/h74.py::extend_store`` adds the 17 deformation columns to the
  shared store ONCE, idempotently (version tag ``+h74-deformation-v1``; the canonical
  ``view_A_with_external`` / ``view_B_with_external`` are untouched).  ``run_h61`` supplies
  ``setup`` (pins, cached store, label-blind-quadrant folds, buffer 80 px), ``sample_train``,
  ``learner``, ``stage_canary``, ``stage_fit`` and ``stage_exchange`` (independence screen +
  exactly one whole-segment confident-to-abstaining exchange with buffer, no leakage into any
  evaluation region) -- all run UNCHANGED, with the View A list substituted by a setup wrapper
  (``redirect`` below).  The evaluator is ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1),
  placement is ``gems52.nodes.spacing_select``, packaging is ``gems52.submission_writer``, gates
  are ``gems52.gates`` (incl. the authoritative universal-coverage-probe lane policy) and
  ``scripts/audit_uniqueness.py`` with the census.  The prior census helper is
  ``build_h61_submission.prior_paths``; the lane-valid greedy is ``run_h70.lane_valid_greedy``.
* Round-specific: the nine-arm holdout (H70's arms with View A2 in place of View A), the S1
  sufficiency screen on View A2, the strict-A2-only build field, the H70 section-3 lane-valid
  constrained placement, the reasoning CSV and the run card.

Stages (checkpointed, resumable, never silently re-tuned)
---------------------------------------------------------
    features    E1: extend the shared store with the H74 deformation columns (once)
    canary      E1: base.stage_canary (leakage canary, alarm 0.90, on the A2+B features)
    fit         E1: base.stage_fit (both views, every fold; H61 learner unchanged)
    sufficiency E1: S1 screen on View A2 out-of-quadrant AUC (reported for the verdict rule)
    exchange    E2: base.stage_exchange (independence screen first; one round per direction)
    holdout     E2: nine arms, matched budget, pooled HOLDOUT-DTI + paired 95% CI
    build       E3: strict A2-only candidate, lane-valid placement, gates, GeoTIFF, reasoning CSV
    audit       E3: scripts/audit_uniqueness.py (census) folded into the run card

Nothing here uploads or spends a competition slot; promotion is the separate selector step.

Usage: ``python scripts/run_h74.py [features|canary|fit|sufficiency|exchange|holdout|build|audit|all]``
"""
from __future__ import annotations

import csv
import gzip
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
import scipy.sparse as sp                                            # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
import run_h70 as h70                                                # noqa: E402  (lane_valid_greedy only)
import build_h61_submission as b61                                   # noqa: E402  (prior census helper only)
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402
from gems52 import h74 as h74_ext                                   # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h74"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
REG_PATH = ROOT / "registry/h74_preregistration.json"
STAGE_EV = WORK / "stage_evidence"          # the shared exchange stage reads one receipt by a fixed name
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
PREFIX = "gems52-h74-"
ARMS = ("single_A2", "single_B", "union_max", "disagreement_pre", "disagreement_post",
        "a_only", "single_B_veto_Bonly", "concordant", "random")
CANDIDATES = ("a_only", "single_B_veto_Bonly", "concordant", "disagreement_post")
CHAMPION_REF = ("ref_h33_2_b2", 0.2778)
# budget discovery for the lane-valid constrained placement (prereg section 3): descending probes
BUDGET_PROBES = [40000, 36000, 32000, 29000, 26000, 23000, 20000, 18000, 16000,
                 14000, 12000, 10000, 8000, 6000, 4000, 2000]


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_h74(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h74_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h74_{name}.json").write_text(p.read_text())
    return p


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ preregistration + redirects
def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H74 preregistered document changed after registration; refusing to run")
    return reg


def redirect() -> None:
    """Point the shared H61 stages at H74 storage and substitute the View A2 list.  Nothing under
    ``evidence/h61_*`` is written and no shared stage is forked: ``base.setup`` is wrapped so the
    canonical setup checks (pins, store, cross-view overlap on the canonical lists) still run,
    and only the returned View A list is replaced by ``manifest["view_A2_deformation"]``."""
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h74
    base.EVID = STAGE_EV
    orig_setup = base.setup

    def setup_a2():
        reg, store, cat, eligible, folds, va, vb, ring_px = orig_setup()
        va2 = list(store.manifest["view_A2_deformation"])
        if set(va2) & set(vb):
            raise SystemExit(f"H74 cross-view feature overlap: {sorted(set(va2) & set(vb))}")
        missing = [n for n in va2 if n not in store.manifest["feature_sha256"]]
        if missing:
            raise SystemExit(f"H74 View A2 columns missing from the store: {missing}; "
                             "run the features stage (gems52.h74.extend_store)")
        return reg, store, cat, eligible, folds, va2, vb, ring_px

    base.setup = setup_a2


# ------------------------------------------------------------------ E1: features
def stage_features(reg) -> dict:
    log("=== H74 E1: shared-store extension with the deformation columns (once, idempotent) ===")
    t0 = time.time()
    summary = h74_ext.extend_store(ROOT / "work/r2/features",
                                   ROOT / "data/training_features.tif", log=log)
    rec = dict(stage="features", finished_utc=now(), seconds=round(time.time() - t0, 1), **summary)
    store = structural.FeatureStore(ROOT / "work/r2/features")
    rec["store_version"] = store.manifest["version"]
    rec["store_features"] = len(store.manifest["feature_names"])
    rec["view_A2_deformation"] = store.manifest["view_A2_deformation"]
    rec["view_A2_channel_count"] = len(store.manifest["view_A2_deformation"])
    rec["view_B_with_external_count"] = len(store.manifest["view_B_with_external"])
    rec["canonical_views_unchanged"] = bool(
        len(store.manifest["view_A_with_external"]) == 36
        and len(store.manifest["view_B_with_external"]) == 37)
    write_h74("features", rec)
    log(f"store {rec['store_version']}: {rec['store_features']} features; "
        f"View A2 = {rec['view_A2_channel_count']} deformation channels; "
        f"canonical views unchanged: {rec['canonical_views_unchanged']}")
    return rec


# ------------------------------------------------------------------ E1: sufficiency (S1, reported)
def stage_sufficiency(reg) -> dict:
    _, store, cat, eligible, folds, va, vb, _ = base.setup()
    th = reg["thresholds"]
    fit = json.loads((EVID / "h74_fit_checkpoint.json").read_text())
    aucs = [r["view_A"]["heldout_region_auc"] for r in fit["folds"]]
    aucs_b = [r["view_B"]["heldout_region_auc"] for r in fit["folds"]]
    rec = dict(stage="sufficiency", started_utc=now(),
               evidence_class="PREMISE-AUC (View A2 out-of-quadrant diagnostic), not a DTI score",
               view_A2_oof_auc_per_fold=[round(a, 6) for a in aucs],
               view_B_oof_auc_per_fold=[round(a, 6) for a in aucs_b],
               mean_view_A2_oof_auc=round(float(np.mean(aucs)), 6),
               min_fold_view_A2_oof_auc=round(float(np.min(aucs)), 6),
               mean_view_B_oof_auc=round(float(np.mean(aucs_b)), 6),
               S1_thresholds=dict(mean_min=th["S1_sufficiency_mean_oof_auc_min"],
                                  fold_min=th["S1_sufficiency_min_fold_oof_auc"]),
               prior_view_A_mean_oof_auc=dict(H61=0.5163, H63=0.5362, H64=0.5230, H65=0.5202,
                                              H70=0.5166, H71=0.5163))
    rec["S1_pass"] = bool(rec["mean_view_A2_oof_auc"] >= th["S1_sufficiency_mean_oof_auc_min"]
                          and rec["min_fold_view_A2_oof_auc"] >= th["S1_sufficiency_min_fold_oof_auc"])
    rec["finished_utc"] = now()
    write_h74("sufficiency", rec)
    log(f"S1 sufficiency (View A2 deformation-only): mean {rec['mean_view_A2_oof_auc']:.4f} "
        f"min {rec['min_fold_view_A2_oof_auc']:.4f} -> {'PASS' if rec['S1_pass'] else 'FAIL'} "
        f"(View B mean {rec['mean_view_B_oof_auc']:.4f})")
    return rec


# ------------------------------------------------------------------ E2: holdout (nine arms)
def stage_holdout(reg) -> dict:
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    lo, hi = th["receiver_rank_interval"]
    donor = float(th["donor_rank_min"])
    ex = json.loads((STAGE_EV / "h61_pseudo_exchange.json").read_text())
    if not ex.get("allowed_exchange", False):
        log("NOTE: the independence screen fired; post-exchange arms are refits without transfer")
    out = dict(stage="holdout", started_utc=now(), budget_per_arm_per_fold=K, min_separation_px=min_px,
               arms=list(ARMS), folds=[], view_A="A2 deformation-only (bands 4/7/8/10/16 + transforms)",
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               new_arms={
                   "a_only": f"rankA2_post - rankB_post gated to rankA2_post >= {donor} & rankB_post in "
                             f"[{lo}, {hi}] (H74-A: the brief's literal discovery stratum on the "
                             "deformation pair, isolated)",
                   "single_B_veto_Bonly": f"rankB_pre gated to NOT(rankB_pre >= {donor} & rankA2_pre in "
                                          f"[{lo}, {hi}]) (H74-B: the brief's artifact clause as a veto, "
                                          "with View A2's abstention)",
                   "concordant": "min(rankA2_pre, rankB_pre) gated to rankA2_pre >= 0.95 & rankB_pre >= 0.95 "
                                 "(H74-C: the concordant ranking on the deformation pair)"},
               capacity_note=("every arm is placed by nodes.spacing_select on a field that is finite over "
                              "the whole allowed domain; an arm that cannot fill K is reported with its "
                              "achieved budget and is not eligible to beat the control at matched budget"))
    terms = {a: None for a in ARMS}
    for fold in folds:
        f = fold["fold"]
        # LABEL-BLIND emission domain: the 200 m exclusion ring is built from the fold's VISIBLE
        # catalogue only (the CTD5 defect is not repeated).
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = {}
        for v in ("A", "B"):
            g[f"pre_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f}.npy"), eligible.shape)
            g[f"post_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        allowed_idx = np.flatnonzero(allowed.ravel())
        r_pre = {v: np.full(g[f"pre_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        r_post = {v: np.full(g[f"post_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r_pre[v].ravel()[allowed_idx] = base.pct_rank(g[f"pre_{v}"].ravel()[allowed_idx])
            r_post[v].ravel()[allowed_idx] = base.pct_rank(g[f"post_{v}"].ravel()[allowed_idx])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        # H74-A: strict A2-only stratum on the post-exchange (co-trained) operating ranks
        gate_a = (r_post["A"] >= donor) & (r_post["B"] >= lo) & (r_post["B"] <= hi) & allowed
        f_a = np.where(gate_a, r_post["A"] - r_post["B"], -1.0)
        # H74-B: single_B minus the B-only stratum (artifact veto, View A2's abstention)
        veto = (r_pre["B"] >= donor) & (r_pre["A"] >= lo) & (r_pre["A"] <= hi)
        f_bv = np.where(allowed & ~veto, r_pre["B"], -1.0)
        # H74-C: concordant ranking (soft min), strict stratum size as a diagnostic
        f_cc = np.where(allowed, np.minimum(r_pre["A"], r_pre["B"]), -1.0)
        strict_cc = int(((r_pre["A"] >= donor) & (r_pre["B"] >= donor) & allowed).sum())
        fields = {
            "single_A2": np.nan_to_num(r_pre["A"], nan=-1.0),
            "single_B": np.nan_to_num(r_pre["B"], nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(r_pre["A"], r_pre["B"]), nan=-1.0),
            "disagreement_pre": np.nan_to_num(r_pre["A"] - r_pre["B"], nan=-1.0),
            "disagreement_post": np.nan_to_num(r_post["A"] - r_post["B"], nan=-1.0),
            "a_only": np.nan_to_num(f_a, nan=-1.0),
            "single_B_veto_Bonly": np.nan_to_num(f_bv, nan=-1.0),
            "concordant": np.nan_to_num(f_cc, nan=-1.0),
            "random": rnd,
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(fold["region"].sum()),
                   strict_a2_only_candidate_px=int(gate_a.sum()), strict_concordant_px=strict_cc,
                   arms={})
        em_by_arm = {}
        for arm, field in fields.items():
            t0 = time.time()
            em = nodes.spacing_select(field, allowed, K, min_px=min_px)
            em_by_arm[arm] = em
            n = int(em.sum())
            pred = em.astype(np.float32)
            result, term = evaluator.evaluate(pred, fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=n, requested=K, filled=bool(n == K),
                       seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {f} arm {arm}: emitted {n}/{K} DTI {result['dti']:.6f} tpw {result['tpw']:.1f}")
        # not-the-union diagnostics on the shipped fields, reusing the already-placed arms
        d_em = em_by_arm["a_only"] > 0
        a_em, b_em, u_em = (em_by_arm["single_A2"], em_by_arm["single_B"], em_by_arm["union_max"])
        dis_allowed = np.asarray(fields["a_only"][allowed], dtype=np.float64)
        union_field = fields["union_max"]
        rec["not_the_union"] = dict(
            a_only_cells_vs_A2=int((d_em != a_em).sum()), a_only_cells_vs_B=int((d_em != b_em).sum()),
            a_only_cells_vs_union=int((d_em != u_em).sum()),
            a_only_dots_also_in_A2=int((d_em & a_em).sum()), a_only_dots_also_in_B=int((d_em & b_em).sum()),
            spearman_a_only_vs_unionmax=float(np.corrcoef(
                rankdata(dis_allowed), rankdata(union_field[allowed]))[0, 1]),
            note="the strict A2-only stratum is gated on the post-exchange operating ranks; it is not a "
                 "rescaling of max(A2,B), of either single view, or of their union")
        out["folds"].append(rec)
        del g, r_pre, r_post, fields
    pooled = {}
    for cand in CANDIDATES:
        pooled[cand] = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                                candidate=cand)
    out["pooled"] = pooled
    sB = pooled["a_only"]["scores"]["single_B"]["dti"]
    committed = float(reg["thresholds"]["single_B_control_holdout_dti"])
    tol = float(reg["thresholds"]["single_B_control_abs_tolerance"])
    out["control"] = dict(single_B_h74=sB, single_B_committed=committed, abs_difference=abs(sB - committed),
                          tolerance=tol, pass_=bool(abs(sB - committed) <= tol),
                          note="H61/H63/H64/H70 measured 0.1742-0.1746 on the identical splitter, "
                               "sampler and learner; View B and its columns are byte-identical")
    out.update(finished_utc=now(),
               withheld_positive_pixels=pooled["a_only"]["scores"]["a_only"]["withheld_positive_pixels"],
               all_standard_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"]
                                                for arm in ARMS if arm not in
                                                ("a_only", "concordant"))),
               caveat="HOLDOUT-DTI on the corrected label-blind-quadrants-v2 splitter. This simulator "
                      "measured Spearman -0.10 against the owner-reported board in round R4, so it "
                      "screens procedures; it does not by itself promote anything.")
    write_h74("holdout", out)
    if not out["control"]["pass_"]:
        raise SystemExit(f"single_B control outside tolerance: {out['control']}; pipeline defect, stopping")
    for arm in ARMS:
        s = pooled["a_only"]["scores"][arm]
        log(f"  arm {arm}: {s['dti']:.6f} [{s['ci95'][0]:.6f}, {s['ci95'][1]:.6f}]")
    pd = pooled["a_only"]["paired_differences"]["single_B"]
    out["holdout_eligible"] = bool(pooled["a_only"]["scores"]["a_only"]["dti"]
                                   > pooled["a_only"]["scores"]["single_B"]["dti"]
                                   and float(pd["ci95"][0]) > 0.0)
    write_h74("holdout", out)
    log(f"candidate a_only vs single_B: delta {pd['delta']:+.6f} CI [{pd['ci95'][0]:+.6f}, "
        f"{pd['ci95'][1]:+.6f}] -> holdout_eligible={out['holdout_eligible']}")
    return out


# ------------------------------------------------------------------ E3: build (lane-valid placement)
def stage_build(reg, s1: dict, exch: dict) -> dict:
    th = reg["thresholds"]
    log("=== H74 E3: build — OOF mosaic, strict A2-only stratum, lane-valid placement, gates, GeoTIFF ===")
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    flat, inv, shape = store.flat_idx, store.inverse, eligible.shape
    H_, W_ = shape
    N = int(np.prod(shape))
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    del sub
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    folds = list(spatial.folds(cat, eligible, buffer_px=int(th["buffer_px"])))

    # out-of-fold mosaic of the post-exchange (co-trained) operating scores
    mos = {}
    for v in ("A", "B"):
        g = np.full(N, np.nan, np.float32)
        for fold in folds:       # OUT-OF-FOLD only
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
    n_allowed_pre_novelty = int(allowed.sum())
    log(f"emission domain: eligible {int(eligible.sum())} -> allowed {n_allowed_pre_novelty}")

    # ---- registry: census + local artefacts; informative vs universal-coverage probes --------
    priors_all, pmeta = b61.prior_paths(CENSUS, ("submission",))
    priors_all = [p for p in priors_all if not p.name.startswith(PREFIX)]
    disk = gates._disk(gates.NEAR_RADIUS_PX)
    informative, probes, supports = [], [], {}
    for pp in priors_all:
        with rasterio.open(pp) as ds_p:
            if ds_p.shape != shape:
                continue
            a = ds_p.read(1)
        sup = np.isfinite(a) & (a > 0)
        if not sup.any():
            continue
        cov = gates.registry_coverage(sup, eligible, gates.NEAR_RADIUS_PX)
        if cov >= gates.PROBE_COVERAGE:           # universal-coverage probe: localises nothing
            probes.append(dict(name=pp.name, coverage_3px_of_eligible=round(cov, 6)))
            continue
        informative.append(pp)
        supports[pp.name] = np.flatnonzero(sup.ravel()).astype(np.int32)
    log(f"registry: {len(priors_all)} rasters -> {len(informative)} informative, {len(probes)} probes")

    # NOVELTY RULE (declared post hoc in knowledge/39c; unchanged): no emitted cell is a positive
    # pixel of any informative registry raster.
    exact_union = np.zeros(N, bool)
    for nm in supports:
        exact_union[supports[nm]] = True
    allowed = allowed & ~exact_union.reshape(shape)
    novelty = dict(rule=("no emitted cell is a positive pixel of an informative registry raster; universal-"
                         "coverage probes (3 px coverage >= 0.95) are excluded as in gates.lane_report policy"),
                   radius_px=gates.NEAR_RADIUS_PX, informative_rasters=len(informative),
                   probe_rasters=len(probes), probes=probes,
                   exact_union_px=int(exact_union.sum()),
                   allowed_before=n_allowed_pre_novelty, allowed_after_exact=int(allowed.sum()),
                   declared="post hoc, after the H64 first build failed uniqueness (novel_fraction 0.0); "
                            "see knowledge/39c")
    log(f"novelty exact: allowed {n_allowed_pre_novelty} -> {int(allowed.sum())}")

    # ---- the H74-A candidate field: strict A2-only on the post-exchange operating ranks -------
    lo, hi = th["receiver_rank_interval"]
    donor = float(th["donor_rank_min"])
    idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[idx] = base.pct_rank(mos["A"].ravel()[idx])
    rankB.ravel()[idx] = base.pct_rank(mos["B"].ravel()[idx])
    gate = (rankA >= donor) & (rankB >= lo) & (rankB <= hi) & allowed
    field = np.where(gate, rankA - rankB, -1.0).astype(np.float32)
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)
    cand = np.flatnonzero((field > -1.0).ravel())           # the strict A2-only candidate cells
    cval = field.ravel()[cand]
    order = np.lexsort((cand, -cval))
    cand = cand[order]
    log(f"strict A2-only candidate cells: {cand.size} (gate rankA2 >= {donor}, rankB in [{lo}, {hi}])")
    if cand.size == 0:
        raise SystemExit("the strict A2-only stratum is empty; nothing to build")

    # ---- lane-valid constrained placement (prereg section 3): every informative prior constrained
    # CSR of halo hits over the candidate cells; one 3 px dilation per informative prior, the same
    # disk gates.lane_report uses.  Built row-sparse to bound memory on a 3 GB box.
    rows_sp = []
    for pp in informative:
        sup2 = np.zeros(N, bool)
        sup2[supports[pp.name]] = True
        rows_sp.append(sp.csr_matrix(ndi.binary_dilation(sup2.reshape(shape), structure=disk)
                                     .ravel()[cand].astype(np.float32)))
        del sup2
    # HITS is (candidates x priors): row j lists the informative priors whose 3 px halo contains
    # candidate j — the orientation run_h70.lane_valid_greedy expects (H70 stacks priors x
    # candidates and transposes).
    HITS = sp.vstack(rows_sp, format="csr").T.tocsr() if rows_sp else sp.csr_matrix((cand.size, 0))
    del rows_sp
    indptr, indices = HITS.indptr, HITS.indices
    n_inf = len(informative)
    log(f"lane constraints: {n_inf} informative halos stacked over {cand.size} candidates "
        f"({int(HITS.nnz)} near pairs)")

    def greedy(n: int):
        return h70.lane_valid_greedy(cand, indptr, indices, n_inf, W_, n)

    def near_counts(positions: np.ndarray) -> dict:
        """Exact per-prior near-dot counts from the CSR membership (no re-dilation of 523 grids).

        ``positions`` are indices into the score-ordered candidate array (the greedy's keep list),
        not flat grid cells."""
        v = np.zeros(cand.size, np.float32)
        v[np.asarray(positions, dtype=np.int64)] = 1.0
        counts = np.asarray(HITS.T @ v, dtype=np.int64).ravel()
        return {informative[i].name: int(counts[i]) for i in range(n_inf)}

    placement_log = []
    emission_flat = None
    adopted = None
    lane_valid_exists = False
    best_probe = None            # (probe n, keep list) with the largest placement
    for n in BUDGET_PROBES:
        keep, _ = greedy(n)
        placement_log.append(dict(probe=n, placed=len(keep)))
        log(f"lane-valid probe n={n}: placed {len(keep)}")
        if best_probe is None or len(keep) > len(best_probe[1]):
            best_probe = (n, keep)
        if len(keep) >= n:
            em_flat = cand[np.asarray(keep[:n], dtype=np.int64)]
            counts = near_counts(np.asarray(keep[:n], dtype=np.int64))
            worst_nm, worst_c = max(counts.items(), key=lambda kv: kv[1])
            share = worst_c / n
            placement_log[-1].update(adopted=True, worst_raster=worst_nm, worst_near_dots=worst_c,
                                     worst_share=round(share, 6), verified=bool(share <= gates.NEAR_LIMIT))
            if share <= gates.NEAR_LIMIT:
                emission_flat = em_flat
                adopted = n
                lane_valid_exists = True
                log(f"lane-valid budget adopted: {n} dots; worst informative near-dot share "
                    f"{share:.4f} ({worst_nm})")
                break
    if emission_flat is None:
        # No probe was feasible.  The candidate set cannot host a lane-valid emission at any
        # budget: adopt the largest placement any probe achieved (candidate exhaustion), verify
        # its shares with the TRUE emission size as the denominator, and report honestly.  A
        # share above the limit is a measured DUPLICATE, not a rescued placement.
        if best_probe is None or len(best_probe[1]) == 0:
            raise SystemExit("lane-valid placement placed 0 dots; no file can be built")
        n_probe, keep = best_probe
        em_flat = cand[np.asarray(keep, dtype=np.int64)]
        m = int(em_flat.size)
        counts = near_counts(np.asarray(keep, dtype=np.int64))
        worst_nm, worst_c = max(counts.items(), key=lambda kv: kv[1])
        share = worst_c / m
        emission_flat = em_flat
        adopted = m
        lane_valid_exists = bool(share <= gates.NEAR_LIMIT)
        placement_log.append(dict(fallback=True, largest_probe=dict(probe=n_probe, placed=m),
                                  adopted=m, worst_raster=worst_nm, worst_near_dots=worst_c,
                                  worst_share=round(share, 6),
                                  verified=lane_valid_exists,
                                  lane_valid_emission_exists=lane_valid_exists,
                                  note=("no budget probe was feasible: the strict A2-only candidate "
                                        "set cannot host a lane-valid emission at any budget; the "
                                        "file is published with the measured DUPLICATE label")))
        log(f"FALLBACK: largest placement {m} dots; TRUE worst informative near-dot share "
            f"{share:.4f} ({worst_nm}) -> lane-valid emission exists: {lane_valid_exists}")
    n_dots = int(emission_flat.size)
    emission = np.zeros(N, bool)
    emission[emission_flat] = True
    emission = emission.reshape(shape)
    novelty.update(lane_valid_placement=dict(
        rule=("every informative prior constrained from the first placement; cap = floor(0.70 x n) per "
              "prior; budget n discovered by descending feasibility probes; the emission is a score-order "
              "prefix of the placement, so every informative prior's near-dot share is <= 0.70 by construction"),
        probes=placement_log, adopted_budget=adopted, placed=n_dots,
        min_separation_px=3.0, lane_valid_emission_exists=lane_valid_exists,
        verified_by_construction=lane_valid_exists,
        measured_worst_informative_near_dot_share=(
            placement_log[-1].get("worst_share")
            if isinstance(placement_log[-1], dict) else None)))

    # ---- not-the-union check at the adopted budget -------------------------------------------
    u_em = nodes.spacing_select(union_field, allowed, n_dots, min_px=3.0)
    a_em = nodes.spacing_select(np.where(allowed, rankA, -1.0).astype(np.float32), allowed, n_dots, min_px=3.0)
    b_em = nodes.spacing_select(np.where(allowed, rankB, -1.0).astype(np.float32), allowed, n_dots, min_px=3.0)
    d = emission
    not_union = dict(
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        dots_shared_with_single_A2=int((d & a_em).sum()), dots_shared_with_single_B=int((d & b_em).sum()),
        jaccard_with_single_A2=float((d & a_em).sum() / max(1, int((d | a_em).sum()))),
        jaccard_with_single_B=float((d & b_em).sum() / max(1, int((d | b_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(field[allowed]),
                                                     rankdata(union_field[allowed]))[0, 1]),
        emitted_cells_that_are_strict_a2_only=int((d & gate).sum()),
        verdict="the strict A2-only emission is not max(A2,B), not either single view, and not their union")
    not_union["not_union_pass"] = bool(not_union["jaccard_with_union_max"] < 0.9
                                       and not_union["jaccard_with_single_A2"] < 0.9
                                       and not_union["jaccard_with_single_B"] < 0.9
                                       and not_union["emitted_cells_that_are_strict_a2_only"] == n_dots)
    write_h74("not_union", not_union)

    # ---- surface lane gate before the dots gate (the brief: check on the surface AND on the dots)
    priors = priors_all
    cov_cache: dict = {}
    surf = np.where(allowed, (field - field[allowed].min()) /
                    max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    surf_digest = hashlib.sha256(surf.astype("<f4").tobytes()).hexdigest()
    lane_surface = None
    cached_path = EVID / "h74_lane_surface.json"
    if cached_path.exists():
        prev = json.loads(cached_path.read_text())
        if prev.get("candidate_decoded_sha256") == surf_digest:
            lane_surface = prev
            log("surface lane: reusing cached receipt (identical surface bytes)")
    if lane_surface is None:
        lane_surface = gates.lane_report(surf, allowed, priors,
                                         sample=ROOT / "data/sample_submission.tif",
                                         phase="surface", log=log, coverage_cache=cov_cache)
        write_h74("lane_surface", lane_surface)
    # seed the coverage cache from the surface report so the dots phase does not re-dilate
    # every prior's support a second time
    for r in lane_surface.get("per_prior", []):
        if "decoded_sha256" in r and r.get("coverage_3px_of_eligible") is not None:
            cov_cache.setdefault(r["decoded_sha256"], r["coverage_3px_of_eligible"])
    log(f"surface lane: literal {lane_surface['literal']['verdict']} "
        f"(max rho {lane_surface['literal']['max_spearman']}), policy "
        f"{lane_surface['policy']['verdict']} (max rho {lane_surface['policy']['max_spearman']})")

    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if (pred > 0).sum() and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    # ---- the TIF, the single-TIFF ZIP and the on-disk validator ------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mode_word = "lanevalid" if lane_valid_exists else "fallback-duplicate"
    stem = f"gems52-h74-a2deform-cotrain-{n_dots}px-{stamp}"
    path = SUBM / f"{stem}.tif"
    SUBM.mkdir(exist_ok=True)
    hold = json.loads((EVID / "h74_holdout.json").read_text())
    cand_dti = hold["pooled"]["a_only"]["scores"]["a_only"]["dti"]
    cand_ci = hold["pooled"]["a_only"]["scores"]["a_only"]["ci95"]
    sB = hold["pooled"]["a_only"]["scores"]["single_B"]["dti"]
    beats = bool(hold.get("holdout_eligible", False))
    mode_note = "lane-valid" if lane_valid_exists else "lane-DUPLICATE"
    beat_word = "beats" if beats else "does NOT beat"
    note = (f"H74 deformation-only View A2; A2-only stratum, {n_dots} dots, {mode_note}; "
            f"holdout {beat_word} single_B; research only, not slot-approved")
    assert len(note) <= 140, len(note)
    name = stem
    receipt = submission_writer.write_submission(
        path, pred, sample=ROOT / "data/sample_submission.tif", footprint=sub_finite,
        note=note[:140], name=name[:140],
        metadata=dict(round="H74", preregistration=reg["hypothesis_sha256"], budget=n_dots,
                      candidate_arm="a_only", view_A="deformation-only A2",
                      placement=mode_word))
    fmt = receipt["validator"]
    lane_dots = gates.lane_report(pred, eligible, priors, sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log, coverage_cache=cov_cache)
    uniq = gates.uniqueness_report(pred, [p for p in priors if p != path], top=None)   # tier 1: exact, all priors
    uniq_inf = gates.uniqueness_report(pred, [p for p in informative if p != path], top=None)  # tier 2: novelty
    write_h74("lane_dots", lane_dots)
    log(f"dots lane: literal {lane_dots['literal']['verdict']} (max near "
        f"{lane_dots['literal']['max_near_3px_fraction']}), policy {lane_dots['policy']['verdict']} "
        f"(max near {lane_dots['policy']['max_near_3px_fraction']})")

    # ---- geological reasoning for every emitted (A2-only) cell -------------------------------
    ys, xs = np.nonzero(emission)
    CTX = ("raw_band_04", "raw_band_07", "raw_band_08", "raw_band_10", "raw_band_16",
           "raw_band_15", "raw_band_19", "raw_band_13", "X_rad_ThK_rank", "X_rad_K_rank")
    ctx_rows = store.gather(ys * W_ + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h74-a-only-reasoning.csv"
    DOWN.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "distance_to_mapped_trace_m",
                    "view_A2_operating_rank", "view_B_operating_rank", "disagreement_rank_diff",
                    "strict_A2_only", "strain_second_invariant", "strain_shear_rate",
                    "strain_dilatation_rate", "eq_distance_kernel", "eq_density_kernel",
                    "cover_depth_to_base_m", "dem_slope", "isostatic_grav_anom", "rad_ThK_rank",
                    "rad_K_rank", "geological_hypothesis",
                    "named_non_fault_mimic", "falsifier", "evidence_class"])
        for i, (y, x) in enumerate(zip(ys, xs)):
            strict = bool(gate[y, x])
            w.writerow([
                int(y), int(x), 243350.0 + 100.0 * (x + 0.5), 4508550.0 - 100.0 * (y + 0.5),
                round(float(cat_dist[y, x]), 1),
                round(float(rankA[y, x]), 6), round(float(rankB[y, x]), 6),
                round(float(rankA[y, x] - rankB[y, x]), 6), int(strict),
                round(float(ctx["raw_band_04"][i]), 4), round(float(ctx["raw_band_07"][i]), 4),
                round(float(ctx["raw_band_08"][i]), 4), round(float(ctx["raw_band_10"][i]), 4),
                round(float(ctx["raw_band_16"][i]), 4),
                round(float(ctx["raw_band_15"][i]), 1), round(float(ctx["raw_band_19"][i]), 4),
                round(float(ctx["raw_band_13"][i]), 4),
                round(float(ctx["X_rad_ThK_rank"][i]), 4), round(float(ctx["X_rad_K_rank"][i]), 4),
                "Buried or cover-hidden ACTIVE fault (H74-A): the deformation-only view is confident "
                "(geodetic second invariant / shear / dilatation gradients and their coherence, "
                "earthquake-density kernel edge) while the surface view abstains (no DEM scarp, no "
                "slope lineament, no radiometric lineament) -- consistent with a young blind fault "
                "straining and micro-seismic beneath cover. HYPOTHESIS, not verified geology.",
                "Anthropogenic subsidence from groundwater withdrawal; irrigation-related aquifer "
                "compaction; volcanic inflation or deflation (magma movement without discrete "
                "faulting); post-seismic afterslip or viscoelastic relaxation; seasonal hydrological "
                "loading; a strain transient on a creeping (aseismic) fault segment.",
                "Independent evidence of discrete offset: a displaced contact or marker bed, deflected "
                "or offset drainage, a facies termination, a fault-plane solution aligned with the "
                "lineament, a published structural interpretation, or field observation. None is "
                "claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")
    with csv_path.open("rb") as fh_in, gzip.open(str(csv_path) + ".gz", "wb") as fh_out:
        fh_out.write(fh_in.read())

    # ---- publish the download set -------------------------------------------------------------
    shutil.copyfile(path, DOWN / "h74-candidate.tif")
    shutil.copyfile(path.with_suffix(".zip"), DOWN / "h74-candidate.zip")
    shutil.copyfile(path.with_suffix(".json"), DOWN / "h74-candidate-receipt.json")
    for src_p, dst in ((path, DOWN / "h74-candidate.tif"),
                       (path.with_suffix(".zip"), DOWN / "h74-candidate.zip")):
        if sha(src_p) != sha(dst):
            raise IOError(f"published copy mismatch: {dst}")

    # ---- build receipt -------------------------------------------------------------------------
    card = dict(
        stage="build", finished_utc=now(), file=path.name, budget=n_dots,
        placement_mode=mode_word, lane_valid_emission_exists=lane_valid_exists,
        stratum_px=int(gate.sum()), allowed_px=int(allowed.sum()), eligible_px=int(eligible.sum()),
        informative_rasters=len(informative), probe_rasters=len(probes), registry_rasters=len(priors),
        lane_surface_literal=lane_surface["literal"]["verdict"],
        lane_surface_policy=lane_surface["policy"]["verdict"],
        lane_dots_literal=lane_dots["literal"]["verdict"],
        lane_dots_policy=lane_dots["policy"]["verdict"],
        lane_dots_policy_max_near_3px=lane_dots["policy"]["max_near_3px_fraction"],
        lane_dots_literal_max_near_3px=lane_dots["literal"]["max_near_3px_fraction"],
        lane_dots_policy_max_spearman=lane_dots["policy"]["max_spearman"],
        not_union=not_union, validator=fmt, submission_receipt=receipt,
        uniqueness_tier1=dict(canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
                              equals_literal_prior_union=uniq.get("equals_literal_prior_union"),
                              novel_fraction=uniq.get("novel_fraction"),
                              n_priors_checked=uniq.get("n_priors_checked")),
        uniqueness_tier2=dict(novel_fraction=uniq_inf.get("novel_fraction"),
                              equals_literal_prior_union=uniq_inf.get("equals_literal_prior_union"),
                              n_priors_checked=uniq_inf.get("n_priors_checked"),
                              informative_rasters=len(informative)),
        novelty_rule=novelty,
        holdout_candidate=dict(arm="a_only", dti=cand_dti, ci95=cand_ci, beats_single_B=beats),
        sufficiency_S1=dict(mean_view_A2_oof_auc=s1["mean_view_A2_oof_auc"],
                            min_fold=s1["min_fold_view_A2_oof_auc"], S1_pass=s1["S1_pass"]),
        exchange=dict(total_pseudo_pixels=exch.get("total_pseudo_pixels"),
                      allowed_exchange=exch.get("allowed_exchange"),
                      independence_max_abs_rho=(exch.get("independence_pre") or {}).get("max_abs_correlation")))
    write_h74("build", card)
    return card


# ------------------------------------------------------------------ E3: audit + run card
def stage_audit(reg) -> dict:
    log("=== H74 audit: scripts/audit_uniqueness.py with the census receipt ===")
    build = json.loads((EVID / "h74_build.json").read_text())
    tif = SUBM / build["file"]
    audit_path = EVID / "h74_audit_uniqueness.json"
    cmd = [sys.executable, str(ROOT / "scripts/audit_uniqueness.py"),
           str(tif.relative_to(ROOT)), str(audit_path.relative_to(ROOT)), str(CENSUS.relative_to(ROOT))]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log(r.stdout[-2000:])
    if r.returncode != 0:
        log(r.stderr[-2000:])
        raise SystemExit("audit_uniqueness.py failed")
    audit = json.loads(audit_path.read_text())
    (DOCS / "h74_audit_uniqueness.json").write_text(audit_path.read_text())
    card = make_run_card(reg, build, audit)
    write_h74("run_card", card)
    log(f"verdict: {card['verdict']}")
    return card


def make_run_card(reg, build, audit) -> dict:
    th = reg["thresholds"]
    hold = json.loads((EVID / "h74_holdout.json").read_text())
    s1 = json.loads((EVID / "h74_sufficiency.json").read_text())
    can = json.loads((EVID / "h74_canary.json").read_text())
    pooled = hold["pooled"]["a_only"]
    fmt = build["validator"]
    receipt = build["submission_receipt"]
    lane_pol_ok = (build["lane_dots_policy"] == "PASS" and build["lane_surface_policy"] == "PASS"
                   and build["lane_valid_emission_exists"])
    fmt_ok = bool(fmt.get("ok"))
    uniq_ok = bool(build["uniqueness_tier1"]["canonical_pattern_unique"]
                   and not build["uniqueness_tier1"]["equals_literal_prior_union"]
                   and (build["uniqueness_tier2"]["novel_fraction"] or 0.0) >= 1.0
                   and not build["uniqueness_tier2"]["equals_literal_prior_union"])
    not_union_ok = bool(build["not_union"]["not_union_pass"])
    holdout_ok = bool(hold.get("holdout_eligible", False))
    promote = bool(fmt_ok and lane_pol_ok and uniq_ok and not_union_ok and s1["S1_pass"] and holdout_ok)
    if promote:
        verdict = ("PROMOTE-ELIGIBLE (passes every gate incl. S1 sufficiency and holdout vs single_B); "
                   "the selector still owns the weekly slot; nothing uploaded by this lane")
    else:
        failed = [k for k, v in dict(format=fmt_ok, lane_policy=lane_pol_ok, unique=uniq_ok,
                                     not_union=not_union_ok, S1=s1["S1_pass"],
                                     holdout_beats_single_B=holdout_ok).items() if not v]
        download = "YES" if (fmt_ok and uniq_ok) else "NO"
        verdict = (f"NEGATIVE, research-only. DOWNLOAD {download} (format-valid and unique on decoded "
                   f"pixels); SUBMIT NO. Failed gates: {', '.join(failed)}. "
                   f"No weekly slot spent by this lane.")
    s = pooled["scores"]["a_only"]
    return dict(
        round="H74",
        generated_utc=now(),
        hypothesis="H74-A (the deferred H70-E variant): a DEFORMATION-ONLY View A2 (geodetic strain "
                   "bands 4/7/8 + seismicity bands 10/16, with gradient/coherence transforms) is a "
                   "sufficient, transferable view where every mixed potential-field+deformation View A "
                   "failed (five consecutive OOF AUC ~0.52); the brief's literal discovery stratum -- "
                   "strict A2-only (A2 confident at operating rank >= 0.95, View B abstaining in "
                   "[0.35, 0.65]) -- is isolated as a standalone emission arm and built as the "
                   "candidate, after the co-training exchange.",
        mechanism="Blum & Mitchell co-training (doi:10.1145/279943.279962) on the A2/B pair: one "
                  "whole-segment confident-to-abstaining pseudo-label round per direction per fold, "
                  "then the disagreement stratum A2-confident & B-abstaining is emitted as "
                  "buried-beneath-cover active-fault candidates.",
        named_non_fault_mimic="anthropogenic subsidence from groundwater withdrawal; irrigation-related "
                              "aquifer compaction; volcanic inflation/deflation (magma movement without "
                              "discrete faulting); post-seismic afterslip or viscoelastic relaxation; "
                              "seasonal hydrological loading; a strain transient on a creeping aseismic "
                              "fault segment",
        independence=dict(max_abs_rho=build["exchange"]["independence_max_abs_rho"],
                          threshold=th["independence_abandon_max_abs_rho"],
                          allow_exchange=build["exchange"]["allowed_exchange"],
                          negative_class="held-out catalogue-zero proxies, not verified absence"),
        canary=dict(max_alarm_across_folds=can["max_alarm_across_folds"],
                    any_alarm=can["any_alarm"],
                    max_fitted_top5_heldout_auc=can["max_fitted_top5_heldout_auc"],
                    alarm_threshold=th["canary_auc_alarm"]),
        sufficiency_S1=s1,
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI", evaluator_version="gems52-pooled-hide-v1",
            alpha=0.2, beta=0.8, triangular_radius_m=300,
            withheld_positive_pixels=pooled["scores"]["a_only"]["withheld_positive_pixels"],
            matched_budget_per_fold_per_arm=hold["budget_per_arm_per_fold"],
            candidate_a_only=dict(dti=s["dti"], ci95=s["ci95"]),
            single_B_baseline=dict(dti=pooled["scores"]["single_B"]["dti"],
                                   ci95=pooled["scores"]["single_B"]["ci95"]),
            single_A2=dict(dti=pooled["scores"]["single_A2"]["dti"],
                           ci95=pooled["scores"]["single_A2"]["ci95"]),
            union_max=dict(dti=pooled["scores"]["union_max"]["dti"],
                           ci95=pooled["scores"]["union_max"]["ci95"]),
            disagreement_pre=dict(dti=pooled["scores"]["disagreement_pre"]["dti"],
                                  ci95=pooled["scores"]["disagreement_pre"]["ci95"]),
            disagreement_post=dict(dti=pooled["scores"]["disagreement_post"]["dti"],
                                   ci95=pooled["scores"]["disagreement_post"]["ci95"]),
            single_B_veto_Bonly=dict(dti=pooled["scores"]["single_B_veto_Bonly"]["dti"],
                                     ci95=pooled["scores"]["single_B_veto_Bonly"]["ci95"]),
            concordant=dict(dti=pooled["scores"]["concordant"]["dti"],
                            ci95=pooled["scores"]["concordant"]["ci95"]),
            random=dict(dti=pooled["scores"]["random"]["dti"], ci95=pooled["scores"]["random"]["ci95"]),
            paired_candidate_minus_single_B=pooled["paired_differences"]["single_B"],
            control_reproduction=hold["control"]),
        correlation_overlap_vs_registry=dict(
            lane_surface_literal=build["lane_surface_literal"],
            lane_surface_policy=build["lane_surface_policy"],
            lane_dots_literal=build["lane_dots_literal"],
            lane_dots_policy=build["lane_dots_policy"],
            lane_dots_policy_max_near_3px=build["lane_dots_policy_max_near_3px"],
            lane_dots_literal_max_near_3px=build["lane_dots_literal_max_near_3px"],
            lane_dots_policy_max_spearman=build["lane_dots_policy_max_spearman"],
            lane_valid_emission_exists=build["lane_valid_emission_exists"],
            audit_surface=dict(max_spearman=audit["phases"]["surface"]["max_spearman"],
                               ok=audit["phases"]["surface"]["ok"]),
            audit_dots=dict(max_near_3px=audit["phases"]["dots"]["max_near_3px_fraction"],
                            ok=audit["phases"]["dots"]["ok"]),
            audit_max_jaccard=audit["max_jaccard"],
            audit_share_of_candidate_inside_any_prior=audit["share_of_candidate_px_inside_any_prior_support"],
            uniqueness_tier1=build["uniqueness_tier1"],
            uniqueness_tier2=build["uniqueness_tier2"],
            registry_rasters=build["registry_rasters"],
            informative_rasters=build["informative_rasters"],
            probe_rasters=build["probe_rasters"]),
        not_the_union=build["not_union"],
        placement=dict(mode=build["placement_mode"], stratum_px=build["stratum_px"],
                       budget=build["budget"], lane_valid_emission_exists=build["lane_valid_emission_exists"]),
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
                       mass_outside_footprint=fmt.get("mass_outside_footprint"),
                       validation_class=fmt.get("validation_class")),
        submission_name=receipt["submission_name"], note=receipt["note"], note_chars=receipt["note_chars"],
        champion_reference=dict(name=CHAMPION_REF[0], reported_score=CHAMPION_REF[1],
                                evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"),
        leaderboard_top_public_board=dict(score=0.3774, team="xiaofanhu",
                                          evidence_class="PUBLIC BOARD 2026-10-09, NOT ORGANIZER-CONFIRMED"),
        experiments_used="3 of 3 (E1 features+canary+fit+sufficiency, E2 exchange+holdout, E3 build+audit)",
        submission_slots_used=0,
        verdict=verdict,
        verdict_promote=promote)


# ------------------------------------------------------------------ main
def main(argv) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    if stage not in ("features", "canary", "fit", "sufficiency", "exchange", "holdout", "build",
                     "audit", "all"):
        raise SystemExit(f"unknown stage {stage!r}")
    reg = check_prereg()
    redirect()
    load = lambda name: json.loads((EVID / f"h74_{name}.json").read_text())   # noqa: E731
    if stage in ("features", "all"):
        stage_features(reg)
    if stage in ("canary", "all"):
        log("=== H74 E1: canary (shared H61 stage, View A2 list substituted; not forked) ===")
        base.stage_canary()
    if stage in ("fit", "all"):
        log("=== H74 E1: fit (shared H61 stage; sampler and learner unchanged) ===")
        base.stage_fit()
    if stage in ("sufficiency", "all"):
        stage_sufficiency(reg)
    if stage in ("exchange", "all"):
        log("=== H74 E2: exchange (shared H61 stage: independence screen + one round per direction) ===")
        ex = base.stage_exchange()
        # the round holdout stage reads this exact file name from STAGE_EV
        (STAGE_EV / "h61_pseudo_exchange.json").write_text(json.dumps(ex, default=str) + "\n")
    if stage in ("holdout", "all"):
        log("=== H74 E2: holdout (nine arms, matched budget) ===")
        stage_holdout(reg)
    if stage in ("build", "all"):
        log("=== H74 E3: build (strict A2-only, lane-valid placement) ===")
        s1 = load("sufficiency")
        exch = json.loads((STAGE_EV / "h61_pseudo_exchange.json").read_text())
        stage_build(reg, s1, exch)
    if stage in ("audit", "all"):
        log("=== H74 E3: audit (census uniqueness) + run card ===")
        stage_audit(reg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
