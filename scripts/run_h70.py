#!/usr/bin/env python3
"""H70 -- strict A-only isolation in the two-view co-training lane, with a lane-valid build.

Preregistered in ``knowledge/54_hypotheses_H70_preregistered.md`` and pinned by
``registry/h70_preregistration.json``; this runner refuses to start if the hash has moved.

Lane: the brief's co-training paragraph.  View A is potential-field/subsurface, View B is surface
(DEM curvature and slope plus the radiometric channels), and disagreement is the discovery signal.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61`` supplies ``setup`` (folds, feature store, pin checks), the canary,
  fit and exchange stages (identical sampler, learner, thresholds and assertions), and the evaluator
  ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1).  The prior census helper is
  ``build_h61_submission.prior_paths``.  Nothing under ``evidence/h61_*`` is written.
* Round-specific: the nine-arm holdout (H61's six arms plus the three preregistered H70 arms
  ``a_only``, ``single_B_veto_Bonly``, ``concordant``), the sufficiency screen S1 (reported, not
  gating the exchange -- the brief's abandonment clause is the independence correlation only), the
  strict-A-only build field, and the lane-valid constrained placement of prereg §3.

Stages
------
    canary      base.stage_canary (leakage canary, alarm 0.90)
    fit         base.stage_fit (both views, every fold; H61 learner unchanged)
    sufficiency S1 screen on View A out-of-quadrant AUC (reported for the verdict rule)
    exchange    base.stage_exchange (independence screen first; one whole-segment round per direction)
    holdout     nine arms, matched budget, pooled HOLDOUT-DTI + paired 95% CI
    build       strict A-only candidate, lane-valid placement, gates, GeoTIFF, reasoning CSV, run card

Nothing here uploads or spends a competition slot; promotion is the separate selector step.

Usage: ``python scripts/run_h70.py [canary|fit|sufficiency|exchange|holdout|build|all]``
"""
from __future__ import annotations

import csv
import gzip
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
import rasterio                                                      # noqa: E402
import scipy.sparse as sp                                            # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
import build_h61_submission as b61                                   # noqa: E402  (prior census helper only)
from gems52 import evaluate_holdout as evaluator                    # noqa: E402
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h70"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
REG_PATH = ROOT / "registry/h70_preregistration.json"
STAGE_EV = WORK / "stage_evidence"          # the holdout stage reads one receipt by a fixed name
CENSUS = ROOT / "work/h70/prior_fetch_receipt.json"
ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post",
        "a_only", "single_B_veto_Bonly", "concordant", "random")
CANDIDATES = ("a_only", "single_B_veto_Bonly", "concordant", "disagreement_post")
PREFIX = "gems52-h70-"
CHAMPION_REF = ("ref_h33_2_b2", 0.2778)
# budget discovery for the lane-valid constrained placement (prereg §3): descending probes
BUDGET_PROBES = [40000, 36000, 32000, 29000, 26000, 23000, 20000, 18000, 16000,
                 14000, 12000, 10000, 8000, 6000, 4000, 2000]


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_h70(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h70_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h70_{name}.json").write_text(p.read_text())
    return p


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ preregistration + redirects
def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H70 preregistered document changed after registration; refusing to run")
    return reg


def redirect() -> None:
    """Point the shared H61 stages at H70 storage.  Nothing under evidence/h61_* is written."""
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h70
    base.EVID = STAGE_EV
    # H70 changes no learner: the default hook (H61 learner for both views) stays.


# ------------------------------------------------------------------ stage: sufficiency (S1, reported)
def stage_sufficiency() -> dict:
    _, store, cat, eligible, folds, va, vb, _ = base.setup()
    flat = store.flat_idx
    th = json.loads(REG_PATH.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    rec = dict(stage="sufficiency", started_utc=now(), folds=[],
               evidence_class="HOLDOUT-DTI diagnostic AUC (View A out-of-quadrant), not a DTI score")
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + 500 + f)
        region = fold["region"]
        pos = np.flatnonzero((fold["truth"] & region).ravel())
        neg = np.flatnonzero((region & ~cat & (catd > 5)).ravel())
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        pa = base.to_grid(flat, np.load(WORK / f"pred_pre_A_f{f}.npy"), eligible.shape)
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        s = np.r_[pa.ravel()[pos], pa.ravel()[neg]]
        auc = float(roc_auc_score(y, s))
        rec["folds"].append(dict(fold=f, n_pos=int(len(pos)), n_neg=int(len(neg)), view_A_oof_auc=auc))
        log(f"fold {f} view A out-of-quadrant AUC {auc:.4f} (pos {len(pos)}, neg {len(neg)})")
    aucs = [r["view_A_oof_auc"] for r in rec["folds"]]
    rec["mean_view_A_oof_auc"] = float(np.mean(aucs))
    rec["min_fold_view_A_oof_auc"] = float(np.min(aucs))
    rec["S1_thresholds"] = dict(mean_min=th["S1_sufficiency_mean_oof_auc_min"],
                                fold_min=th["S1_sufficiency_min_fold_oof_auc"])
    rec["S1_pass"] = bool(rec["mean_view_A_oof_auc"] >= th["S1_sufficiency_mean_oof_auc_min"]
                          and rec["min_fold_view_A_oof_auc"] >= th["S1_sufficiency_min_fold_oof_auc"])
    rec["finished_utc"] = now()
    rec["H61_reference_view_A_mean_oof_auc"] = 0.5163
    rec["H63_reference_view_A_mean_oof_auc"] = 0.5362
    rec["H64_reference_view_A_mean_oof_auc"] = 0.5230
    rec["H65_reference_view_A_mean_oof_auc"] = 0.5202
    write_h70("sufficiency", rec)
    log(f"S1 sufficiency: mean {rec['mean_view_A_oof_auc']:.4f} min {rec['min_fold_view_A_oof_auc']:.4f} "
        f"-> {'PASS' if rec['S1_pass'] else 'FAIL'}")
    return rec


# ------------------------------------------------------------------ stage: holdout (nine arms)
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
               arms=list(ARMS), folds=[],
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               new_arms={
                   "a_only": f"rankA_post - rankB_post gated to rankA_post >= {donor} & rankB_post in [{lo}, {hi}] "
                             "(H70-A: the brief's literal discovery stratum, isolated)",
                   "single_B_veto_Bonly": f"rankB_pre gated to NOT(rankB_pre >= {donor} & rankA_pre in [{lo}, {hi}]) "
                                          "(H70-B: the brief's artifact clause as a veto)",
                   "concordant": "min(rankA_pre, rankB_pre) over the allowed domain (H70-C: the concordant "
                                 "ranking; the strict 0.95/0.95 stratum size is reported as a diagnostic)"},
               capacity_note=("every arm is placed by nodes.spacing_select on a field that is finite over the whole "
                              "allowed domain; an arm that cannot fill K is reported with its achieved budget "
                              "and is not eligible to beat the control at matched budget"))
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
        # H70-A: strict A-only stratum on the post-exchange (co-trained) operating ranks
        gate_a = (r_post["A"] >= donor) & (r_post["B"] >= lo) & (r_post["B"] <= hi) & allowed
        f_a = np.where(gate_a, r_post["A"] - r_post["B"], -1.0)
        # H70-B: single_B minus the B-only stratum (artifact veto)
        veto = (r_pre["B"] >= donor) & (r_pre["A"] >= lo) & (r_pre["A"] <= hi)
        f_bv = np.where(allowed & ~veto, r_pre["B"], -1.0)
        # H70-C: concordant ranking (soft min), strict stratum size as a diagnostic
        f_cc = np.where(allowed, np.minimum(r_pre["A"], r_pre["B"]), -1.0)
        strict_cc = int(((r_pre["A"] >= donor) & (r_pre["B"] >= donor) & allowed).sum())
        fields = {
            "single_A": np.nan_to_num(r_pre["A"], nan=-1.0),
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
                   strict_a_only_candidate_px=int(gate_a.sum()), strict_concordant_px=strict_cc,
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
        a_em, b_em, u_em = (em_by_arm["single_A"], em_by_arm["single_B"], em_by_arm["union_max"])
        dis_allowed = np.asarray(fields["a_only"][allowed], dtype=np.float64)
        union_field = fields["union_max"]
        rec["not_the_union"] = dict(
            a_only_cells_vs_A=int((d_em != a_em).sum()), a_only_cells_vs_B=int((d_em != b_em).sum()),
            a_only_cells_vs_union=int((d_em != u_em).sum()),
            a_only_dots_also_in_A=int((d_em & a_em).sum()), a_only_dots_also_in_B=int((d_em & b_em).sum()),
            spearman_a_only_vs_unionmax=float(np.corrcoef(
                rankdata(dis_allowed), rankdata(union_field[allowed]))[0, 1]),
            note="the strict A-only stratum is gated on the post-exchange operating ranks; it is not a "
                 "rescaling of max(A,B), of either single view, or of their union")
        out["folds"].append(rec)
        del g, r_pre, r_post, fields
    pooled = {}
    for cand in CANDIDATES:
        pooled[cand] = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                                candidate=cand)
    out["pooled"] = pooled
    sB = pooled["a_only"]["scores"]["single_B"]["dti"]
    committed = float(reg["single_B_control_holdout_dti"])
    tol = float(reg["single_B_control_abs_tolerance"])
    out["control"] = dict(single_B_h70=sB, single_B_committed=committed, abs_difference=abs(sB - committed),
                          tolerance=tol, pass_=bool(abs(sB - committed) <= tol),
                          note="H61/H63/H64 measured 0.1742-0.1745 on the identical splitter and sampler")
    out.update(finished_utc=now(),
               withheld_positive_pixels=pooled["a_only"]["scores"]["a_only"]["withheld_positive_pixels"],
               all_standard_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"]
                                                for arm in ARMS if arm not in
                                                ("a_only", "concordant"))),
               caveat="HOLDOUT-DTI on the corrected label-blind-quadrants-v2 splitter. This simulator "
                      "measured Spearman -0.10 against the owner-reported board in round R4, so it "
                      "screens procedures; it does not by itself promote anything.")
    write_h70("holdout", out)
    if not out["control"]["pass_"]:
        raise SystemExit(f"single_B control outside tolerance: {out['control']}; pipeline defect, stopping")
    return out


# ------------------------------------------------------------------ lane-valid greedy (module level)
def lane_valid_greedy(cand: np.ndarray, indptr, indices, n_priors: int, width: int, n: int,
                      near_limit: float = gates.NEAR_LIMIT, min_px: float = 3.0):
    """Place up to ``n`` dots in field order, ``min_px`` apart, honouring per-prior near-dot caps.

    ``cand`` are candidate flat cells in field-score order; ``(indptr, indices)`` is the CSR of
    halo hits over the candidates (row j = the informative priors whose 3 px halo contains
    candidate j).  The cap per prior is ``floor(near_limit * n)``; a candidate that would push any
    halo it sits in over its cap is skipped.  Because the emission is a score-order prefix of the
    placement, every prior's near-dot share of the first ``n`` placed dots is <= ``near_limit``
    by construction.
    """
    cap = int(np.floor(near_limit * n))
    counts = np.zeros(n_priors, dtype=np.int64)
    keep: list[int] = []
    buckets: dict[tuple[int, int], list[tuple[int, int]]] = {}
    cellpx = float(min_px)
    d2 = cellpx * cellpx
    for j in range(cand.size):
        flatc = int(cand[j])
        y, x = divmod(flatc, width)
        cy, cx = int(y // cellpx), int(x // cellpx)
        ok = True
        for gy in range(cy - 1, cy + 2):
            for gx in range(cx - 1, cx + 2):
                for (py, px) in buckets.get((gy, gx), ()):
                    if (py - y) ** 2 + (px - x) ** 2 < d2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            continue
        s, e = int(indptr[j]), int(indptr[j + 1])
        if e > s:
            hit = indices[s:e]
            if int((counts[hit] + 1 > cap).sum()):
                continue
            counts[hit] += 1
        keep.append(j)
        buckets.setdefault((cy, cx), []).append((y, x))
        if len(keep) >= n:
            break
    return keep, counts


# ------------------------------------------------------------------ stage: build (lane-valid placement)
def stage_build(reg, s1: dict, exch: dict) -> dict:
    th = reg["thresholds"]
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    flat, inv, shape = store.flat_idx, store.inverse, eligible.shape
    H_, W_ = shape
    N = int(np.prod(shape))
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
        sample_grid = (ref.shape, ref.crs, ref.transform)
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

    # ---- the H70-A candidate field: strict A-only on the post-exchange operating ranks --------
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
    cand = np.flatnonzero((field > -1.0).ravel())           # the strict A-only candidate cells
    cval = field.ravel()[cand]
    order = np.lexsort((cand, -cval))
    cand = cand[order]
    log(f"strict A-only candidate cells: {cand.size} (gate rankA >= {donor}, rankB in [{lo}, {hi}])")
    if cand.size == 0:
        raise SystemExit("the strict A-only stratum is empty; nothing to build")

    # ---- lane-valid constrained placement (prereg §3): every informative prior constrained ----
    # CSR of halo hits over the candidate cells; one 3 px dilation per informative prior, the same
    # disk gates.lane_report uses.
    halo_rows = []
    for pp in informative:
        sup2 = np.zeros(N, bool)
        sup2[supports[pp.name]] = True
        halo_rows.append(ndi.binary_dilation(sup2.reshape(shape), structure=disk).ravel()[cand])
        del sup2
    HITS = sp.csr_matrix(np.stack(halo_rows).T) if halo_rows else sp.csr_matrix((cand.size, 0))
    indptr, indices = HITS.indptr, HITS.indices
    n_inf = len(informative)
    log(f"lane constraints: {n_inf} informative halos stacked over {cand.size} candidates")

    def greedy(n: int):
        return lane_valid_greedy(cand, indptr, indices, n_inf, W_, n)

    def near_counts(em_flat: np.ndarray) -> dict:
        out = {}
        for k, pp in enumerate(informative):
            sup2 = np.zeros(N, bool)
            sup2[supports[pp.name]] = True
            halo = ndi.binary_dilation(sup2.reshape(shape), structure=disk)
            out[pp.name] = int(halo.ravel()[em_flat].sum())
            del sup2, halo
        return out

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
            counts = near_counts(em_flat)
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
        counts = near_counts(em_flat)
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
                                  note=("no budget probe was feasible: the strict A-only candidate "
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
        dots_shared_with_single_A=int((d & a_em).sum()), dots_shared_with_single_B=int((d & b_em).sum()),
        jaccard_with_single_A=float((d & a_em).sum() / max(1, int((d | a_em).sum()))),
        jaccard_with_single_B=float((d & b_em).sum() / max(1, int((d | b_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(field[allowed]),
                                                     rankdata(union_field[allowed]))[0, 1]),
        verdict="the strict A-only emission is not max(A,B), not either single view, and not their union")
    not_union["not_union_pass"] = bool(not_union["jaccard_with_union_max"] < 0.9
                                       and not_union["jaccard_with_single_A"] < 0.9
                                       and not_union["jaccard_with_single_B"] < 0.9)

    # ---- surface lane gate before the dots gate (the brief: check on the surface AND on the dots)
    priors = priors_all
    surf = np.where(allowed, (field - field[allowed].min()) /
                    max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    lane_surface = gates.lane_report(surf, allowed, priors, sample=ROOT / "data/sample_submission.tif",
                                     phase="surface", log=log)
    write_h70("lane_surface", lane_surface)

    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if (pred > 0).sum() and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    # ---- the TIF, the single-TIFF ZIP and the on-disk validator ------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gems52-h70-aonly-cotrain-{n_dots}px-{stamp}"
    path = SUBM / f"{stem}.tif"
    SUBM.mkdir(exist_ok=True)
    hold = json.loads((EVID / "h70_holdout.json").read_text())
    cand_dti = hold["pooled"]["a_only"]["scores"]["a_only"]["dti"]
    cand_ci = hold["pooled"]["a_only"]["scores"]["a_only"]["ci95"]
    sB = hold["pooled"]["a_only"]["scores"]["single_B"]["dti"]
    beats = bool(cand_dti > sB and hold["pooled"]["a_only"]["paired_differences"]["single_B"]["ci95"][0] > 0.0)
    note = (f"H70 strict A-only co-training discovery stratum; constrained placement at {n_dots} dots, "
            f"lane-DUPLICATE; research only, not slot-approved")
    assert len(note) <= 140, len(note)
    name = stem
    receipt = submission_writer.write_submission(
        path, pred, sample=ROOT / "data/sample_submission.tif", footprint=sub_finite,
        note=note[:140], name=name[:140],
        metadata=dict(round="H70", preregistration=reg["hypothesis_sha256"], budget=n_dots,
                      candidate_arm="a_only"))
    fmt = receipt["validator"]
    lane_dots = gates.lane_report(pred, eligible, priors, sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log)
    uniq = gates.uniqueness_report(pred, [p for p in priors if p != path], top=None)   # tier 1: exact, all priors
    uniq_inf = gates.uniqueness_report(pred, [p for p in informative if p != path], top=None)  # tier 2: novelty
    write_h70("lane_dots", lane_dots)

    # ---- geological reasoning for every emitted (A-only) cell --------------------------------
    ys, xs = np.nonzero(emission)
    CTX = ("raw_band_15", "raw_band_19", "A_gravity_grad_3", "X_rad_ThK_rank", "X_rad_K_rank",
           "X_mag_TMI_up150_grad3", "raw_band_13", "raw_band_17")
    ctx_rows = store.gather(ys * W_ + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h70-a-only-reasoning.csv"
    DOWN.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "distance_to_mapped_trace_m",
                    "view_A_operating_rank", "view_B_operating_rank", "disagreement_rank_diff",
                    "strict_A_only", "cover_depth_to_base_m", "dem_slope", "gravity_grad_sigma3",
                    "isostatic_grav_anom", "near_surface_conductivity", "rad_ThK_rank",
                    "rad_K_rank", "tmi_up150_grad3", "geological_hypothesis",
                    "named_non_fault_mimic", "falsifier", "evidence_class"])
        for i, (y, x) in enumerate(zip(ys, xs)):
            strict = bool(gate[y, x])
            w.writerow([
                int(y), int(x), 243350.0 + 100.0 * (x + 0.5), 4508550.0 - 100.0 * (y + 0.5),
                round(float(cat_dist[y, x]), 1),
                round(float(rankA[y, x]), 6), round(float(rankB[y, x]), 6),
                round(float(rankA[y, x] - rankB[y, x]), 6), int(strict),
                round(float(ctx["raw_band_15"][i]), 1), round(float(ctx["raw_band_19"][i]), 4),
                round(float(ctx["A_gravity_grad_3"][i]), 6),
                round(float(ctx["raw_band_13"][i]), 4), round(float(ctx["raw_band_17"][i]), 4),
                round(float(ctx["X_rad_ThK_rank"][i]), 4), round(float(ctx["X_rad_K_rank"][i]), 4),
                round(float(ctx["X_mag_TMI_up150_grad3"][i]), 6),
                "Buried or cover-hidden fault (H70-A): a deep potential-field fabric step (upward-continued "
                "TMI and isostatic gravity gradient, basement-depth contrast) with no DEM scarp, no slope "
                "lineament and no radiometric lineament -- View A confident, View B abstaining. "
                "HYPOTHESIS, not verified geology.",
                "Non-fault basin-fill density boundary or volcanic lithologic contact; buried "
                "palaeo-channel or alluvial-fan margin; upward-continued flight-line artefact; "
                "basement high without a discrete fault.",
                "Independent evidence of offset: a displaced contact or marker bed, deflected or "
                "offset drainage, a facies termination, a published structural interpretation, or "
                "field observation. None is claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")
    with csv_path.open("rb") as fh_in, gzip.open(str(csv_path) + ".gz", "wb") as fh_out:
        fh_out.write(fh_in.read())

    # ---- publish the download set -------------------------------------------------------------
    import shutil
    shutil.copyfile(path, DOWN / "h70-candidate.tif")
    shutil.copyfile(path.with_suffix(".zip"), DOWN / "h70-candidate.zip")
    shutil.copyfile(path.with_suffix(".json"), DOWN / "h70-candidate-receipt.json")
    for src_p, dst in ((path, DOWN / "h70-candidate.tif"),
                       (path.with_suffix(".zip"), DOWN / "h70-candidate.zip")):
        if sha(src_p) != sha(dst):
            raise IOError(f"published copy mismatch: {dst}")

    # ---- run card -----------------------------------------------------------------------------
    card = dict(
        round="H70",
        generated_utc=now(),
        hypothesis="H70-A: the brief's literal discovery stratum -- strict A-only (View A confident at "
                   "operating rank >= 0.95, View B abstaining in [0.35, 0.65]) -- isolated as a standalone "
                   "emission arm and built as the candidate, after the co-training exchange.",
        mechanism="Blum & Mitchell co-training (doi:10.1145/279943.279962): one whole-segment "
                  "confident-to-abstaining pseudo-label round per direction per fold, then the disagreement "
                  "stratum A-confident & B-abstaining is emitted as buried-cover fault candidates.",
        named_non_fault_mimic="basin-margin or basement-high gravity/magnetic gradient, volcanic lithologic "
                              "contact, buried palaeo-channel or alluvial-fan margin, upward-continued "
                              "flight-line artefact",
        sufficiency_S1=dict(mean_view_A_oof_auc=s1["mean_view_A_oof_auc"],
                            min_fold=s1["min_fold_view_A_oof_auc"], S1_pass=s1["S1_pass"]),
        exchange=dict(total_pseudo_pixels=exch.get("total_pseudo_pixels"),
                      allowed_exchange=exch.get("allowed_exchange")),
        holdout_dti=hold["pooled"],
        holdout_candidate=dict(arm="a_only", dti=cand_dti, ci95=cand_ci,
                               beats_single_B=beats,
                               paired_delta_vs_single_B=hold["pooled"]["a_only"]["paired_differences"]["single_B"]),
        correlation_overlap_vs_registry=dict(
            lane_dots_literal=lane_dots["literal"]["verdict"],
            lane_dots_policy=lane_dots["policy"]["verdict"],
            lane_dots_policy_max_near_3px_fraction=lane_dots["policy"]["max_near_3px_fraction"],
            lane_surface_literal=lane_surface["literal"]["verdict"],
            lane_surface_policy=lane_surface["policy"]["verdict"],
            lane_valid_emission_exists=lane_valid_exists,
            uniqueness_canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
            novel_fraction=uniq.get("novel_fraction"),
            equals_literal_prior_union=uniq.get("equals_literal_prior_union")),
        not_the_union=not_union,
        raster=dict(file=path.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
                    zip_sha256=receipt["zip_sha256"]),
        validator=dict(ok=fmt.get("ok"), problems=fmt.get("problems"),
                       nan_pixels=fmt.get("nan_pixels"), infinity_pixels=fmt.get("infinity_pixels"),
                       value_range=[fmt.get("min"), fmt.get("max")],
                       crs=fmt.get("crs"), shape=[fmt.get("height"), fmt.get("width")],
                       transform=fmt.get("transform"),
                       mass_outside_footprint=fmt.get("mass_outside_footprint")),
        submission_name=name, note=note, note_chars=len(note),
        counts=dict(budget=adopted, placed=n_dots, prior_rasters=len(priors),
                    informative_rasters=len(informative), probe_rasters=len(probes)),
        novelty_rule=novelty,
        uniqueness=dict(tier1_exact_all_priors=dict(canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
                                                   identical_to_any_prior=any(r.get("identical")
                                                                              for r in uniq.get("per_prior", []))),
                        tier2_novelty_informative_priors=dict(novel_fraction=uniq_inf.get("novel_fraction"),
                                                              equals_literal_prior_union=uniq_inf.get("equals_literal_prior_union"),
                                                              informative_rasters=len(informative))),
        champion_reference=dict(name=CHAMPION_REF[0], reported_score=CHAMPION_REF[1],
                                evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"),
        submission_slots_used=0,
        verdict=verdict_text(fmt_ok=bool(fmt.get("ok")),
                             lane_ok=(lane_dots["literal"]["verdict"] == "PASS"),   # literal = authority
                             lane_policy_ok=(lane_dots["policy"]["verdict"] == "PASS"),
                             uniq_ok=bool(uniq.get("canonical_pattern_unique")
                                          and not any(r.get("identical") for r in uniq.get("per_prior", []))
                                          and not uniq_inf.get("equals_literal_prior_union")
                                          and (uniq_inf.get("novel_fraction") or 0.0) >= 1.0),
                             not_union_ok=not_union["not_union_pass"],
                             s1=s1["S1_pass"],
                             holdout_ok=beats))
    write_h70("run_card", card)
    return card


def verdict_text(*, fmt_ok, lane_ok, lane_policy_ok, uniq_ok, not_union_ok, s1, holdout_ok) -> str:
    """Frozen rule (knowledge/54 §5): eligible for the selector only if every gate passes AND the
    candidate arm beats single_B with the paired 95% CI above 0.  Even then nothing is promoted and
    no slot is used.  The literal lane is authority; the policy lane is reported alongside."""
    if fmt_ok and lane_ok and uniq_ok and not_union_ok and s1 and holdout_ok:
        return "ELIGIBLE FOR SELECTOR, NOT PROMOTED (no slot used; holdout is not board evidence)"
    download = "YES" if (fmt_ok and uniq_ok) else "NO"
    return (f"NEGATIVE, research-only. DOWNLOAD {download} (format-valid and unique); SUBMIT NO "
            "(holdout does not beat single_B and/or literal lane not PASS). "
            f"gates: format={fmt_ok} lane_literal={lane_ok} lane_policy={lane_policy_ok} "
            f"unique={uniq_ok} not_union={not_union_ok} S1={s1} holdout_beats_single_B={holdout_ok}")


# ------------------------------------------------------------------ main
def main(argv) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    if stage not in ("canary", "fit", "sufficiency", "exchange", "holdout", "build", "all"):
        raise SystemExit(f"unknown stage {stage!r}")
    reg = check_prereg()
    redirect()
    load = lambda name: json.loads((EVID / f"h70_{name}.json").read_text())   # noqa: E731
    if stage in ("canary", "all"):
        log("=== H70 stage canary (shared H61 stage) ===")
        base.stage_canary()
    if stage in ("fit", "all"):
        log("=== H70 stage fit (shared H61 stage; learners unchanged) ===")
        base.stage_fit()
    if stage in ("sufficiency", "all"):
        stage_sufficiency()
    if stage in ("exchange", "all"):
        log("=== H70 stage exchange (shared H61 stage: independence screen + one round per direction) ===")
        ex = base.stage_exchange()
        # the shared holdout stage reads this exact file name from base.EVID (= STAGE_EV)
        (STAGE_EV / "h61_pseudo_exchange.json").write_text(json.dumps(ex, default=str) + "\n")
    if stage in ("holdout", "all"):
        log("=== H70 stage holdout (nine arms) ===")
        stage_holdout(reg)
    if stage in ("build", "all"):
        log("=== H70 stage build (strict A-only, lane-valid placement) ===")
        s1 = load("sufficiency")
        exch = json.loads((STAGE_EV / "h61_pseudo_exchange.json").read_text())
        card = stage_build(reg, s1, exch)
        log(f"verdict: {card['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
