#!/usr/bin/env python3
"""H64 -- sufficiency-gated two-view co-training: one pre-registered change to View A capacity.

Preregistered in ``knowledge/39_hypotheses_H64_preregistered.md`` and pinned by
``registry/h64_preregistration.json``; this runner refuses to start if either hash has moved.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61`` supplies ``setup`` (folds, feature store, thresholds), the
  View-B learner, the canary-free fit/exchange/holdout stages, and the evaluator
  ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1).  The only change to the shared runner is the
  ``learner_for(view, seed)`` hook, whose default is the H61 learner (H61 receipts are unchanged).
* Round-specific: ``learner_for`` for View A (the single pre-registered change), the sufficiency gate
  S1, the output names (``h64_*``), and the build (placement, not-union, A-only reasoning, gates),
  which mirrors ``scripts/build_h61_submission.py`` line for line and imports only its prior census.

Stages
------
    fit        base.stage_fit with the H64 View-A learner (both views, every fold)
    sufficiency  gate S1 on View A out-of-quadrant AUC (pre-registered thresholds)
    exchange   base.stage_exchange only if S1 passes (S2 is evaluated inside it); otherwise the
               post-arms are declared equal to the pre-arms and no pseudo-label is created
    holdout    base.stage_holdout, six arms, pooled HOLDOUT-DTI + paired 95% CI
    build      placement, gates, GeoTIFF, reasoning CSV, run card (nothing is uploaded)

Usage: ``python scripts/run_h64.py [fit|exchange|holdout|build|all]``
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
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
from sklearn.ensemble import HistGradientBoostingClassifier          # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
import build_h61_submission as b61                                   # noqa: E402  (prior census helper only)
from gems52 import gates, nodes, spatial, structural, submission_writer  # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h64"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
REG_PATH = ROOT / "registry/h64_preregistration.json"
STAGE_EV = WORK / "stage_evidence"          # the holdout stage reads one receipt by a fixed name
BUDGET = int(os.environ.get("H64_BUDGET", "37600"))   # default = template budget; see knowledge/34c
FEASIBILITY_ONLY = os.environ.get("H64_FEASIBILITY_ONLY") == "1"
# exact_and_lane (default): per-raster 70% cap enforced; exact_only: exact pixel novelty only, the
# per-raster cap is measured and reported but not enforced (used for the downloadable, lane-DUPLICATE build)
NOVELTY_MODE = os.environ.get("H64_NOVELTY_MODE", "exact_and_lane")
EXACT_ONLY = NOVELTY_MODE == "exact_only"
NOVELTY_RADIUS_PX = 3
MAX_NOVELTY_ITER = 12
NOVELTY_MIN_PX = 3.0
PREFIX = "gems52-h64-"
CHAMPION_REF = ("ref_h33_2_b2", 0.2778)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_h64(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h64_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h64_{name}.json").write_text(p.read_text())
    return p


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ preregistration + redirects
def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H64 preregistered document changed after registration; refusing to run")
    for am in reg.get("amendments", []):
        if sha(ROOT / am["document"]) != am["sha256"]:
            raise SystemExit(f"H64 amendment changed after registration: {am['document']}")
    # every threshold not restated here is H61's, unchanged (knowledge/39 §4: "identical to H61")
    h61 = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    reg["thresholds"] = {**h61, **reg["thresholds"]}
    return reg


def control_and_verdict(reg) -> dict:
    """Amended single_B control (|delta| <= tolerance) and the frozen verdict rule (knowledge/39 §4)."""
    rec = json.loads((EVID / "h64_holdout.json").read_text())
    pooled = rec["pooled"]
    sB = float(pooled["scores"]["single_B"]["dti"])
    ref = float(reg["thresholds"]["single_B_h61_control_holdout_dti"])
    tol = float(reg["thresholds"]["single_B_control_abs_tolerance"])
    control = dict(single_B_h64=sB, single_B_h61_committed=ref, abs_difference=abs(sB - ref),
                   tolerance=tol, pass_=bool(abs(sB - ref) <= tol))
    pd = pooled["paired_differences"]["single_B"]          # candidate minus single_B
    lo = float(pd["ci95"][0])
    cand = float(pooled["scores"]["disagreement_post"]["dti"])
    beats = bool(cand > sB and lo > 0.0)
    out = dict(control=control, candidate_arm="disagreement_post", candidate_dti=cand,
               paired_delta_vs_single_B=pd, holdout_eligible=beats)
    write_h64("control_and_verdict", out)
    if not control["pass_"]:
        raise SystemExit(f"single_B control outside tolerance: {control}; pipeline defect, stopping")
    return out


def view_a_learner(seed=SEED):
    """The one pre-registered change: View-A capacity (knowledge/39 §4)."""
    return HistGradientBoostingClassifier(max_iter=120, learning_rate=0.05, max_leaf_nodes=7,
                                          min_samples_leaf=400, l2_regularization=5.0,
                                          early_stopping=False, random_state=seed)


def learner_for(view: str, seed=SEED):
    return view_a_learner(seed) if view == "A" else base.learner(seed)


def redirect() -> None:
    """Point the shared H61 stages at H64 storage.  Nothing under evidence/h61_* is written."""
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h64
    base.learner_for = learner_for
    base.EVID = STAGE_EV           # stage_holdout reads "h61_pseudo_exchange.json" by its fixed name


# ------------------------------------------------------------------ stage: sufficiency (S1)
def stage_sufficiency(reg) -> dict:
    _, store, cat, eligible, folds, va, vb, _ = base.setup()
    flat = store.flat_idx
    th = reg["thresholds"]
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
    write_h64("sufficiency", rec)
    log(f"S1 sufficiency: mean {rec['mean_view_A_oof_auc']:.4f} min {rec['min_fold_view_A_oof_auc']:.4f} "
        f"-> {'PASS' if rec['S1_pass'] else 'FAIL'}")
    return rec


def mirror_pre_to_post(folds) -> None:
    for fold in folds:
        for v in ("A", "B"):
            src = WORK / f"pred_pre_{v}_f{fold['fold']}.npy"
            (WORK / f"pred_post_{v}_f{fold['fold']}.npy").write_bytes(src.read_bytes())


def run_exchange_or_skip(reg, s1: dict) -> dict:
    if s1["S1_pass"]:
        # S2 is evaluated inside the shared stage, which writes the full receipt itself
        # (h64_pseudo_exchange.json).  Mirror that receipt, unmodified, for the holdout stage.
        ex = base.stage_exchange()
        (STAGE_EV / "h61_pseudo_exchange.json").write_text(json.dumps(ex, default=str) + "\n")
        return ex
    else:
        _, _, _, _, folds, _, _, _ = base.setup()
        mirror_pre_to_post(folds)
        receipt = dict(stage="exchange_gate", skipped=True, allowed_exchange=False,
                       total_pseudo_pixels=0, allowed_exchange_note="",
                       reason=("S1 sufficiency failed: View A is not sufficient out of quadrant, so "
                               "Blum-Mitchell does not license an exchange. Post-arms := pre-arms."))
    receipt["finished_utc"] = now()
    write_h64("pseudo_exchange", receipt)
    # the shared holdout stage reads this exact file name from base.EVID (= STAGE_EV)
    (STAGE_EV / "h61_pseudo_exchange.json").write_text(json.dumps(receipt, default=str) + "\n")
    return receipt


# ------------------------------------------------------------------ stage: build (placement, gates)
def pct(v):
    return base.pct_rank(v)


def stage_build(reg, s1: dict, exch: dict) -> dict:
    th = reg["thresholds"]
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
    # buffer_px is not restated in the H64 prereg; the H64 folds were built with the H61 value (80 px),
    # read from the frozen H61 prereg so the build and the fit use identical fold geometry.
    h61_th = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    buffer_px = int(h61_th["buffer_px"])
    folds = list(spatial.folds(cat, eligible, buffer_px=buffer_px))

    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
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

    # NOVELTY RULE (declared post hoc in knowledge/34c; see README). The first H64 build was not
    # unique: every emitted cell already occurred in some registry raster (novel_fraction 0.0).
    # Rule: no emitted cell within NOVELTY_RADIUS_PX of any positive pixel of an informative registry
    # raster; the radius is the lane's own near-dot radius (3 px). A first attempt that used all 548
    # rasters left 0 cells, because 34 rasters are dense probes (e.g. one covers 42% of the grid). This is a uniqueness constraint,
    # not a holdout-driven choice, and it is applied identically to every candidate built from here.
    priors_all, pmeta = b61.prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    priors_all = [p for p in priors_all if not p.name.startswith(PREFIX)]
    N = int(np.prod(shape))
    informative, probes, supports, n_skip = [], [], {}, 0
    for pp in priors_all:
        with rasterio.open(pp) as ds_p:
            if ds_p.shape != shape:
                n_skip += 1
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
    # (1) exact novelty: no emitted cell may be a positive pixel of any informative raster
    exact_union = np.zeros(N, bool)
    for nm in supports:
        exact_union[supports[nm]] = True
    n_allowed_pre_novelty = int(allowed.sum())
    allowed = allowed & ~exact_union.reshape(shape)
    novelty = dict(rule=("(1) no emitted cell is a positive pixel of an informative registry raster; "
                         "(2) no emitted cell lies within 3 px of a positive pixel of an informative registry "
                         "raster whose near-dot share of the emission exceeds 0.70 (the lane's per-raster rule); "
                         f"universal-coverage probes (3 px coverage >= {gates.PROBE_COVERAGE}) are excluded as in "
                         "gates.lane_report policy"),
                   radius_px=NOVELTY_RADIUS_PX, near_limit=gates.NEAR_LIMIT,
                   informative_rasters=len(informative), probe_rasters=len(probes), probes=probes,
                   rasters_skipped_shape=n_skip, exact_union_px=int(exact_union.sum()),
                   allowed_before=n_allowed_pre_novelty, allowed_after_exact=int(allowed.sum()),
                   declared="post hoc, after build 1 failed uniqueness (novel_fraction 0.0); see knowledge/39c")
    log(f"novelty (1) exact: informative {len(informative)}, probes {len(probes)}; allowed "
        f"{n_allowed_pre_novelty} -> {int(allowed.sum())}")
    if int(allowed.sum()) < BUDGET:
        raise SystemExit("exact novelty leaves too few cells for the budget")

    idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[idx] = pct(mos["A"].ravel()[idx])
    rankB.ravel()[idx] = pct(mos["B"].ravel()[idx])
    field = np.where(allowed, rankA - rankB, -1.0).astype(np.float32)
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)

    # (2) per-raster 3 px rule (the lane's own "more than 70% of dots within 3 px of one raster").
    # Place greedily; for every informative raster whose near-dot count exceeds CAP, cap its
    # contribution to CAP = floor(0.70 * BUDGET) in a constrained greedy re-placement, which keeps
    # the same score order and 3 px spacing. A full budget must be placed or the build stops.
    disk = gates._disk(NOVELTY_RADIUS_PX)
    cap = int(np.floor(gates.NEAR_LIMIT * BUDGET))
    offs = [(dy, dx) for dy in range(-NOVELTY_RADIUS_PX, NOVELTY_RADIUS_PX + 1)
            for dx in range(-NOVELTY_RADIUS_PX, NOVELTY_RADIUS_PX + 1)
            if disk[dy + NOVELTY_RADIUS_PX, dx + NOVELTY_RADIUS_PX]]
    def _sup2d(nm):
        g = np.zeros(N, bool)
        g[supports[nm]] = True
        return g.reshape(shape)
    def _near_counts(em):
        ys, xs = np.nonzero(em)
        out = {}
        for nm in supports:
            sup2 = _sup2d(nm)
            near = np.zeros(len(ys), bool)
            for dy, dx in offs:
                rr, cc = ys + dy, xs + dx
                ok = (rr >= 0) & (rr < shape[0]) & (cc >= 0) & (cc < shape[1])
                near[ok] |= sup2[rr[ok], cc[ok]]
            out[nm] = int(near.sum())
        return out
    def _constrained_select(halos):
        idx = np.flatnonzero(allowed.ravel())
        val = np.nan_to_num(field.ravel()[idx], nan=-np.inf, neginf=-np.inf, posinf=np.inf)
        order = np.lexsort((idx, -val))
        cellpx = float(NOVELTY_MIN_PX)
        d2 = cellpx * cellpx
        keep = np.zeros(shape, bool)
        buckets = {}
        counts = {nm: 0 for nm in halos}
        taken = 0
        for pos in order:
            if val[pos] == -np.inf:
                break
            flat = int(idx[pos])
            y, x = divmod(flat, shape[1])
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
            hit = [nm for nm in halos if halos[nm][y, x]]
            if any(counts[nm] + 1 > cap for nm in hit):
                continue
            for nm in hit:
                counts[nm] += 1
            keep[y, x] = True
            buckets.setdefault((cy, cx), []).append((y, x))
            taken += 1
            if taken >= BUDGET:
                break
        return keep, taken

    em0 = nodes.spacing_select(field, allowed, BUDGET, min_px=3.0)
    counts0 = _near_counts(em0)
    offenders = {nm: c for nm, c in counts0.items() if c > cap}
    it_log = [dict(round=0, placed=int(em0.sum()), offenders=len(offenders), unconstrained=True)]
    log(f"novelty (2) unconstrained: placed {int(em0.sum())}; rasters over cap {cap}: {len(offenders)}")
    em = em0
    halos_all = {}
    for rnd in range(1, MAX_NOVELTY_ITER + 1):
        if not offenders or EXACT_ONLY:
            break
        for nm in offenders:
            if nm not in halos_all:
                halos_all[nm] = ndi.binary_dilation(_sup2d(nm), structure=disk)
        em, taken = _constrained_select(halos_all)
        if taken < BUDGET:
            msg = dict(feasible=False, budget=BUDGET, placed=taken, round=rnd, cap=cap)
            if FEASIBILITY_ONLY:
                print("FEASIBILITY", json.dumps(msg), flush=True)
                raise SystemExit(0)
            raise SystemExit(f"per-raster constrained placement placed {taken} of {BUDGET}; stopping")
        counts = _near_counts(em)
        offenders = {nm: c for nm, c in counts.items() if c > cap and nm not in halos_all}
        it_log.append(dict(round=rnd, placed=taken, constrained_rasters=len(halos_all),
                           new_offenders=len(offenders)))
        log(f"novelty (2) round {rnd}: placed {taken}, constrained {len(halos_all)} rasters, new offenders {len(offenders)}")
    else:
        raise SystemExit("per-raster rule did not converge")
    final_counts = _near_counts(em)
    worst = max(final_counts.items(), key=lambda kv: kv[1])
    if FEASIBILITY_ONLY:
        print("FEASIBILITY", json.dumps(dict(feasible=bool(int(em.sum()) == BUDGET and worst[1] <= cap),
                                            budget=BUDGET, placed=int(em.sum()), cap=cap,
                                            worst=worst, share=round(worst[1] / BUDGET, 6))), flush=True)
        raise SystemExit(0)
    if int(em.sum()) != BUDGET or (worst[1] > cap and not EXACT_ONLY):
        raise SystemExit("per-raster rule not satisfied after placement")
    emission_final = em
    novelty.update(mode=NOVELTY_MODE,
                   per_raster_rule=(("NOT ENFORCED (exact_only mode): unconstrained greedy placement; the cap is measured only"
                                     if EXACT_ONLY else
                                     f"greedy placement; any informative raster whose near-dot count would exceed "
                                     f"{cap} (= {gates.NEAR_LIMIT} x {BUDGET}) is capped")),
                   near_limit=gates.NEAR_LIMIT, cap_dots=cap, iterations=it_log,
                   constrained_rasters=sorted(halos_all), worst_raster_near_dots=dict(name=worst[0], count=worst[1],
                                                                                    share=round(worst[1] / BUDGET, 6)),
                   allowed_final=int(allowed.sum()), min_px=NOVELTY_MIN_PX)

    priors, pmeta = b61.prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    priors = [p for p in priors if not p.name.startswith(PREFIX)]
    pmeta["excluded_own_round_prefix"] = PREFIX
    informative_paths = informative
    log(f"registry: {len(priors)} rasters")

    surf = np.where(allowed, (field - field[allowed].min()) /
                    max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    lane_surface = gates.lane_report(surf, allowed, priors, sample=ROOT / "data/sample_submission.tif",
                                     phase="surface", log=log)
    write_h64("lane_surface", lane_surface)

    emission = emission_final
    n_dots = int(emission.sum())
    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if (pred > 0).sum() and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    # not-the-union, the same definitions as build_h61_submission.py lines 226-246
    lo, hi = th["receiver_rank_interval"]
    a_only = (rankA >= th["donor_rank_min"]) & allowed
    b_abstain = (rankB >= lo) & (rankB <= hi) & allowed
    u_em = nodes.spacing_select(union_field, allowed, n_dots, min_px=3.0)
    d = emission
    not_union = dict(
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(field[allowed]),
                                                     rankdata(union_field[allowed]))[0, 1]),
        strict_a_only_candidate_px=int((a_only & b_abstain).sum()),
        emitted_cells_that_are_strict_a_only=int((d & a_only & b_abstain).sum()),
        verdict="emission is not max(A,B), not either single view, and not their union")
    not_union["not_union_pass"] = bool(not_union["jaccard_with_union_max"] < 0.9)

    # the TIF and its single-band validator
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gems52-h64-sufgate-cotrain-{BUDGET}px-{stamp}"
    path = SUBM / f"{stem}.tif"
    SUBM.mkdir(exist_ok=True)
    s1_word = "S1 pass" if s1["S1_pass"] else "S1 fail"
    if EXACT_ONLY:
        note = (f"H64 {s1_word}; exact-novel vs registry; lane DUPLICATE (70% rule); "
                f"research only, do not submit")
    else:
        note = (f"H64 {s1_word}: co-train, A capacity cut, 3px dots, >200m off catalogue; "
                f"research only, not slot-approved")
    assert len(note) <= 140, len(note)
    name = stem
    receipt = submission_writer.write_submission(
        path, pred, sample=ROOT / "data/sample_submission.tif", footprint=sub_finite,
        note=note[:140], name=name[:140],
        metadata=dict(round="H64", preregistration=reg["hypothesis_sha256"], budget=BUDGET))
    fmt = receipt["validator"]
    lane_dots = gates.lane_report(pred, eligible, priors, sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log)
    uniq = gates.uniqueness_report(pred, [p for p in priors if p != path], top=None)   # tier 1: exact, all priors
    uniq_inf = gates.uniqueness_report(pred, [p for p in informative_paths if p != path], top=None)  # tier 2: novelty
    write_h64("lane_dots", lane_dots)

    # geological reasoning for every emitted cell, measured context + template hypothesis
    ys, xs = np.nonzero(emission)
    CTX = ("raw_band_15", "raw_band_19", "A_gravity_grad_3", "X_rad_ThK_rank", "X_rad_K_rank",
           "X_mag_TMI_up150_grad3", "raw_band_13", "raw_band_17")
    ctx_rows = store.gather(ys * shape[1] + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h64-a-only-reasoning.csv"
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
            strict = bool(a_only[y, x] and b_abstain[y, x])
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
                "Buried or cover-hidden fault: a deep potential-field fabric step (upward-continued "
                "TMI and isostatic gravity gradient) with no DEM scarp and no radiometric lineament. "
                "HYPOTHESIS, not verified geology.",
                "Non-fault basin-fill density boundary or volcanic lithologic contact; buried "
                "palaeo-channel or alluvial-fan margin; upward-continued flight-line artefact.",
                "Independent evidence of offset: a displaced contact or marker bed, deflected or "
                "offset drainage, a facies termination, a published structural interpretation, or "
                "field observation. None is claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")

    # the H61 run card records these; H64 keeps the same fields
    hold = json.loads((EVID / "h64_holdout.json").read_text()) if (EVID / "h64_holdout.json").exists() else None
    card = dict(
        round="H64",
        generated_utc=now(),
        hypothesis="Sufficiency-gated co-training: a lower-capacity View A that generalises out of "
                   "quadrant makes the exchange licensed; then disagreement ranks buried-cover candidates.",
        mechanism="Blum-Mitchell needs sufficient views. View A capacity is the single change (knowledge/39 §4).",
        named_non_fault_mimic="basin-margin or basement-high gravity/magnetic gradient, lithologic contact, "
                              "volcanic or basin-fill density boundary, upward-continued flight-line artefact",
        sufficiency_S1=dict(mean_view_A_oof_auc=s1["mean_view_A_oof_auc"],
                            min_fold=s1["min_fold_view_A_oof_auc"], S1_pass=s1["S1_pass"]),
        exchange=dict(skipped=exch.get("skipped", False), total_pseudo_pixels=exch.get("total_pseudo_pixels")),
        holdout_dti=hold and hold.get("pooled"),
        correlation_overlap_vs_registry=dict(
            lane_dots_literal=lane_dots["literal"]["verdict"],
            lane_dots_policy=lane_dots["policy"]["verdict"],
            lane_surface_literal=lane_surface["literal"]["verdict"],
            lane_surface_policy=lane_surface["policy"]["verdict"],
            uniqueness_canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
            novel_fraction=uniq.get("novel_fraction"),
            equals_literal_prior_union=uniq.get("equals_literal_prior_union")),
        not_the_union=not_union,
        raster=dict(file=path.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
                    zip_sha256=receipt["zip_sha256"]),
        validator=dict(ok=fmt.get("ok"), problems=fmt.get("problems"),
                       nan_inside_footprint=fmt.get("nan_px_in_footprint", fmt.get("nan_count")),
                       value_range=[fmt.get("min"), fmt.get("max")],
                       crs=fmt.get("crs"), shape=fmt.get("shape"), transform=fmt.get("transform")),
        submission_name=name, note=note, note_chars=len(note),
        counts=dict(budget=BUDGET, placed=n_dots, prior_rasters=len(priors)),
        novelty_rule=novelty,
        uniqueness=dict(tier1_exact_all_priors=dict(canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
                                                   identical_to_any_prior=any(r.get("identical") for r in uniq.get("per_prior", []))),
                        tier2_novelty_informative_priors=dict(novel_fraction=uniq_inf.get("novel_fraction"),
                                                              equals_literal_prior_union=uniq_inf.get("equals_literal_prior_union"),
                                                              informative_rasters=len(informative_paths))),
        champion_reference=dict(name=CHAMPION_REF[0], reported_score=CHAMPION_REF[1],
                                evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"),
        submission_slots_used=0,
        verdict=verdict_text(fmt_ok=bool(fmt.get("ok", receipt["validator"].get("ok"))),
                             lane_ok=(lane_dots["literal"]["verdict"] == "PASS"),   # literal = authority
                             uniq_ok=bool(uniq.get("canonical_pattern_unique")
                                          and not any(r.get("identical") for r in uniq.get("per_prior", []))
                                          and not uniq_inf.get("equals_literal_prior_union")
                                          and (uniq_inf.get("novel_fraction") or 0.0) >= 1.0),
                             not_union_ok=not_union["not_union_pass"],
                             s1=s1["S1_pass"],
                             holdout_ok=bool(json.loads((EVID / "h64_control_and_verdict.json").read_text())
                                             ["holdout_eligible"])))
    write_h64("run_card", card)
    return card


def verdict_text(*, fmt_ok, lane_ok, uniq_ok, not_union_ok, s1, holdout_ok) -> str:
    """Frozen rule (knowledge/39 §4): eligible for the selector only if every gate passes AND the
    holdout beats single_B.  Even then nothing is promoted and no slot is used."""
    if fmt_ok and lane_ok and uniq_ok and not_union_ok and s1 and holdout_ok:
        return "ELIGIBLE FOR SELECTOR, NOT PROMOTED (no slot used; holdout is not board evidence)"
    download = "YES" if (fmt_ok and uniq_ok) else "NO"
    return (f"NEGATIVE, research-only. DOWNLOAD {download} (format-valid and unique); SUBMIT NO "
            "(holdout does not beat single_B and/or literal lane not PASS). "
            f"gates: format={fmt_ok} lane={lane_ok} unique={uniq_ok} not_union={not_union_ok} "
            f"S1={s1} holdout_beats_single_B={holdout_ok}")


# ------------------------------------------------------------------ main
def main(argv) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    if stage not in ("fit", "sufficiency", "exchange", "holdout", "build", "all"):
        raise SystemExit(f"unknown stage {stage!r}")
    reg = check_prereg()
    redirect()
    load = lambda name: json.loads((EVID / f"h64_{name}.json").read_text())   # noqa: E731
    if stage in ("fit", "all"):
        log("=== H64 stage fit (View A learner changed; View B identical to H61) ===")
        base.stage_fit()
    if stage in ("sufficiency", "all"):
        s1 = stage_sufficiency(reg)
    if stage in ("exchange", "build"):
        s1 = load("sufficiency")
    if stage in ("exchange", "all"):
        exch = run_exchange_or_skip(reg, s1)
    if stage == "holdout" or stage == "build":
        exch = load("pseudo_exchange")
    if stage in ("holdout", "all"):
        log("=== H64 stage holdout ===")
        base.stage_holdout()
        cv = control_and_verdict(reg)
        log(f"single_B control: {cv['control']}; holdout-eligible: {cv['holdout_eligible']}")
    if stage in ("build", "all"):
        s1 = load("sufficiency") if stage == "build" else s1
        card = stage_build(reg, s1, exch)
        log(f"verdict: {card['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
