#!/usr/bin/env python3
"""H88 -- support-size calibration of the two-view disagreement emission.

Motivation (measured, not assumed)
----------------------------------
`h33-h33-2-b2-...-zeros` is the highest-scoring file this project family has reported
(0.2778, owner-reported).  Two organiser-shaped facts about it are checkable on the
restored bytes and were re-verified in this round:

* it emits exactly 37,654 pixels, none on a catalogue pixel, minimum distance to the
  mapped catalogue 2.236 px (no pixel within 2 px);
* its parent `gems24-h25-1-dotted-h19-5-d2-8-...` emits 44,090 pixels and reported 0.2600;
  the 6,436-pixel difference is entirely inside the 2 px catalogue ring.

The published metric admits an exact reduction (algebra in `gems52.metric`, re-derived and
numerically checked in `stage_audit`):

    DTI = T / ( 0.2*S + 0.8*|G| - 0.2*delta ),   delta = M - T >= 0

with S the emitted mass, T the credited mass, |G| the truth pixel count and delta the
double-coverage mass.  At fixed credit T the score therefore **falls with every emitted
pixel that adds no credit** -- a pure tax of 0.2 per pixel.  The family's convention of
emitting ~37.6k pixels was inherited from that one file; the question this round asks is
whether the support size itself is the lever, and how to calibrate it.

The calibration problem: the shared hide-and-recover instrument scores a truth field whose
prevalence in its evaluation regions is 1.16 % (measured, `stage_audit`), while the same
module's docstring matches folds to the 0.112-0.294 % bracket.  An emission budget tuned on a
4-10x denser truth field is tuned too high.  This round measures the DTI-vs-budget curve on
the instrument and maps the optimum through the measured prevalence ratio.

Lane
----
The brief's co-training paragraph.  Views, folds, learners, evaluator, placement and writer
are the template's; nothing here forks a shared tool (`run_h61.setup/stage_fit`, `gems52.spatial
.folds`, `gems52.evaluate_holdout`, `gems52.nodes.spacing_select`, `gems52.cotrain.strata`,
`gems52.submission_writer`, `gems52.gates`).

Stages: audit | fit | ladder | emit | all
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

import run_h61 as base                                                # noqa: E402
from gems52 import cotrain as CT                                      # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, metric, nodes                               # noqa: E402

WORK = ROOT / "work/h88"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
SUB = ROOT / "submission"
DOWN = ROOT / "docs/downloads"
SEED = base.SEED
# (label, dots per fold) -> totals 4.7k, 9.4k, 18.8k, 37.6k, 75.2k across 4 folds
BUDGET_LADDER = (("4k7", 1175), ("9k4", 2350), ("18k8", 4700), ("37k6", 9400), ("75k2", 18800))
ARMS = ("single_B", "union_max", "disagreement_post", "a_only_stratum", "random")


def log(*a, **k):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h88_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    if DOCS.exists():
        (DOCS / f"h88_{name}.json").write_text(p.read_text())
    return p


def digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------ audit
def stage_audit():
    """Three independent checks: instrument prevalence, the metric reduction, the board algebra."""
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    out = dict(stage="h88-audit", generated_utc=now(), evaluator=evaluator.VERSION,
               implementation_hashes=evaluator.implementation_hashes())

    # 1 --- what prevalence does the shared instrument actually score?
    prev = []
    tot_t = tot_r = 0
    for fold in folds:
        t = int((fold["truth"] & fold["region"] & eligible).sum())
        r = int((fold["region"] & eligible).sum())
        tot_t += t
        tot_r += r
        prev.append(dict(fold=fold["fold"], region_px=r, truth_px=t,
                         prevalence=t / r if r else None))
    pooled = tot_t / tot_r
    # The bracket the repository's own holdout module states for the board's |G|.
    bracket = (0.00112, 0.00294)
    out["instrument_prevalence"] = dict(
        per_fold=prev, pooled_prevalence=pooled, pooled_truth_px=tot_t, pooled_region_px=tot_r,
        board_bracket_lo=bracket[0], board_bracket_mid=0.0020, board_bracket_hi=bracket[1],
        ratio_to_lo=pooled / bracket[0], ratio_to_mid=pooled / 0.0020, ratio_to_hi=pooled / bracket[1],
        splitter="gems52.spatial.folds (label-blind quadrants v2, buffer 80 px)",
        finding=("the shared instrument scores a truth field 3.9x-10.3x denser than the board "
                 "bracket its own module docstring matches to; spatial.folds performs no "
                 "prevalence thinning (holdout.PREVALENCE_TARGETS/_thin_to_prevalence are used "
                 "only by holdout.make_folds)"))

    # 2 --- the metric reduction, checked numerically against the template's own authority
    rng = np.random.default_rng(SEED)
    checks = []
    g = np.zeros((500, 500), bool)
    ys = rng.choice(500, 90, replace=False)
    xs = rng.choice(500, 90, replace=False)
    g[ys, xs] = True
    p_sparse = np.zeros_like(g, float)
    p_sparse[ys, xs] = 1.0                      # one dot per truth pixel: delta = 0 by construction
    r_sparse = metric.dti(p_sparse, g)
    dl = r_sparse["m_covers"] - r_sparse["tpw"]
    checks.append(dict(case="sparse 1:1", dti=r_sparse["dti"], delta=float(dl),
                       closed_form=r_sparse["tpw"] / (0.2 * r_sparse["mass"]
                                                      + 0.8 * r_sparse["n_truth"] - 0.2 * dl)))
    p_clump = ndi.binary_dilation(p_sparse, np.ones((3, 3), bool)).astype(float)
    r_clump = metric.dti(p_clump, g)
    dl2 = r_clump["m_covers"] - r_clump["tpw"]
    checks.append(dict(case="clumped 3x3", dti=r_clump["dti"], delta=float(dl2),
                       closed_form=r_clump["tpw"] / (0.2 * r_clump["mass"]
                                                     + 0.8 * r_clump["n_truth"] - 0.2 * dl2)))
    for c in checks:
        c["closed_form_matches"] = bool(abs(c["dti"] - c["closed_form"]) < 1e-9)
    out["metric_reduction"] = dict(
        identity="DTI = T / (0.2*S + 0.8*|G| - 0.2*delta), delta = m_covers - T >= 0",
        checked=checks,
        note=("delta is the double-coverage mass; it is 0 exactly when no two emitted pixels claim "
              "the same truth pixel, and it only ever helps the score. The published page's worked "
              "triple is pinned by tests/test_metric.py and is not re-derived here."))

    # 3 --- |G| from the two nested ORGANISER-SHAPED scores this family reported (owner-reported)
    import glob
    ref = glob.glob(str(ROOT / "data/reference/*.tif"))[0]
    par = glob.glob(str(ROOT / "data/scored/*d2-8*.tif"))[0]

    def pos(path):
        with rasterio.open(path) as s:
            a = np.nan_to_num(s.read(1), nan=0.0)
        return a > 0

    R, P = pos(ref), pos(par)
    s_ref, s_par = int(R.sum()), int(P.sum())
    d_ref, d_par = 0.2778, 0.2600

    def solve_g(a_score, a_px, b_score, b_px):
        # a_score/b_score = (0.2*b_px + 0.8G)/(0.2*a_px + 0.8G)  with identical T (ring credit 0)
        k = a_score / b_score
        return (k * 0.2 * a_px - 0.2 * b_px) / (0.8 * (1.0 - k)) if k != 1 else None

    g_px = solve_g(d_ref, s_ref, d_par, s_par)
    # sensitivity to the 4-dp rounding of the two reported scores
    lo = solve_g(d_ref - 0.00005, s_ref, d_par + 0.00005, s_par)
    hi = solve_g(d_ref + 0.00005, s_ref, d_par - 0.00005, s_par)
    with rasterio.open(ROOT / "data/sample_submission.tif") as _s:
        _smp = _s.read(1)
    sample_fp = int((np.isfinite(_smp) & (_smp > -1e38)).sum())
    cat_px = int(cat.sum())
    footprint_px = int(eligible.sum())
    out["board_algebra"] = dict(
        reference=dict(file=Path(ref).name, positives=s_ref, sha256=digest(ref)),
        parent=dict(file=Path(par).name, positives=s_par, sha256=digest(par)),
        reference_subset_of_parent=bool((R & ~P).sum() == 0),
        parent_minus_reference=int((P & ~R).sum()),
        parent_minus_reference_all_within_2px_of_catalogue=bool(
            (P & ~R).sum() == int(((P & ~R) & (ndi.distance_transform_edt(~cat) <= 2.0)).sum())),
        reference_min_distance_to_catalogue_px=float(ndi.distance_transform_edt(~cat)[R].min()),
        scores=dict(reference=d_ref, parent=d_par, provenance="owner-reported on the family site, "
                                                             "not an organiser receipt"),
        implied_truth_px=g_px, implied_truth_px_rounding_band=[lo, hi],
        catalogue_px=cat_px, eligible_px=footprint_px,
        implied_truth_fraction_of_footprint=g_px / footprint_px if g_px else None,
        board_credit_T_implied_by_reference_score=(
            None if not g_px else d_ref * (0.2 * s_ref + 0.8 * g_px)),
        beats_03195_needs_T_at_S_ref=(None if not g_px else
                                      0.3195 * (0.2 * s_ref + 0.8 * g_px)),
        beats_03195_needs_T_at_S_10000=(None if not g_px else
                                        0.3195 * (0.2 * 10000 + 0.8 * g_px)),
        sample_submission_footprint_px=sample_fp,
        implied_truth_fraction_of_sample_footprint=(g_px / sample_fp if g_px else None),
        note=("T is recovered from the score's own definition; it is a reconstruction from two "
              "owner-reported scores, not a measurement of any submission's internals."))
    # The prevalence ratio that the budget correction uses: instrument truth density against the
    # density implied by the two scores, computed here rather than quoted from a docstring.
    ip = out["instrument_prevalence"]
    derived_prev = (out["board_algebra"]["implied_truth_fraction_of_sample_footprint"]
                    if out["board_algebra"]["implied_truth_px"] else None)
    out["prevalence_correction"] = dict(
        instrument_prevalence=ip["pooled_prevalence"],
        board_prevalence_from_docstring_bracket=dict(lo=bracket[0], mid=0.0020, hi=bracket[1]),
        board_prevalence_from_score_algebra=derived_prev,
        ratio_instrument_over_docstring_mid=ip["pooled_prevalence"] / 0.0020,
        ratio_instrument_over_score_algebra=(ip["pooled_prevalence"] / derived_prev
                                             if derived_prev else None),
        used_for_budget_correction="ratio_instrument_over_score_algebra",
        reasoning=("a budget tuned on a denser truth field is tuned too high; for a self-similar "
                   "field the crossing where the marginal dot stops paying moves roughly in "
                   "proportion to the density of truth, so the board budget is the instrument "
                   "optimum divided by this ratio. This is a proportionality argument, not a "
                   "measurement on the board, and it is reported with both ratios."))
    write("audit", out)
    log(json.dumps(out["instrument_prevalence"], default=str)[:600])
    log(json.dumps({k: v for k, v in out["board_algebra"].items()
                    if k not in ("reference", "parent")}, default=str)[:900])
    return out


# ------------------------------------------------------------------------------------ fit / ladder
def ensure_fit():
    need = [WORK.parent / "h61" / f"pred_pre_{v}_f{f}.npy" for v in ("A", "B") for f in range(4)]
    if not all(p.exists() for p in need):
        log("shared fit checkpoints absent; running run_h61.stage_fit() (template, not forked)")
        base.stage_fit()
    else:
        log("reusing template fit checkpoints work/h61/pred_pre_*.npy")


def ensure_exchange():
    need = [WORK.parent / "h61" / f"pred_post_{v}_f{f}.npy" for v in ("A", "B") for f in range(4)]
    if not all(p.exists() for p in need):
        log("shared exchange checkpoints absent; running run_h61.stage_exchange() (template, not forked)")
        base.stage_exchange()
    else:
        log("reusing template exchange checkpoints work/h61/pred_post_*.npy")


def fold_fields(store, fold, ring_px):
    """The in-lane fields for one fold, defined exactly as run_h61.stage_holdout defines them."""
    eligible = store.valid
    flat = store.flat_idx
    f = fold["fold"]
    vis_dist = ndi.distance_transform_edt(~fold["visible"])
    allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
    del vis_dist
    g = {}
    for v in ("A", "B"):
        for tag in ("pre", "post"):
            p = WORK.parent / "h61" / f"pred_{tag}_{v}_f{f}.npy"
            g[f"{tag}_{v}"] = base.to_grid(flat, np.load(p), eligible.shape)
    allowed_idx = np.flatnonzero(allowed.ravel())
    r = {}
    for tag in ("pre", "post"):
        for v in ("A", "B"):
            grid = np.full(eligible.shape, np.nan, np.float32)
            grid.ravel()[allowed_idx] = base.pct_rank(g[f"{tag}_{v}"].ravel()[allowed_idx])
            r[f"{tag}_{v}"] = grid
    rng = np.random.default_rng(SEED + 500 + f)
    rnd = np.zeros(eligible.shape, np.float32)
    rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
    # the brief's hard discovery stratum: A confident, B abstains (whole-grid, catalogue-free)
    strata = CT.strata(np.nan_to_num(r["pre_A"], nan=-1.0).ravel(),
                       np.nan_to_num(r["pre_B"], nan=-1.0).ravel(),
                       eligible, q_conf=0.98, q_abstain_hi=0.60)
    a_only = (strata["mask"] == 2).astype(np.float32)
    fields = {
        "single_B": np.nan_to_num(r["pre_B"], nan=-1.0),
        "union_max": np.nan_to_num(np.maximum(r["pre_A"], r["pre_B"]), nan=-1.0),
        "disagreement_post": np.nan_to_num(r["post_A"] - r["post_B"], nan=-1.0),
        "a_only_stratum": a_only,
        "random": rnd,
    }
    return allowed, fields, dict(a_only_px=int(a_only.sum()), allowed_px=int(allowed.sum()),
                                 truth_px=int((fold["truth"] & eligible & fold["region"]).sum()))


def stage_ladder():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    ensure_fit()
    ensure_exchange()
    out = dict(stage="h88-ladder", generated_utc=now(), evaluator=evaluator.VERSION,
               budgets={lab: k for lab, k in BUDGET_LADDER}, arms=list(ARMS),
               min_separation_px=3.0,
               selection_rule=("maximise the pooled HOLDOUT-DTI at a common budget; an in-lane arm "
                               "is only promotable if it beats the single_B control at the same "
                               "budget with a paired CI excluding zero"),
               folds=[])
    terms = {(a, lab): None for a in ARMS for lab, _ in BUDGET_LADDER}
    for fold in folds:
        allowed, fields, meta = fold_fields(store, fold, ring_px)
        rec = dict(fold=fold["fold"], **meta, arms={})
        for arm in ARMS:
            fld = np.full(eligible.shape, -1.0, np.float32)
            fld[allowed] = fields[arm][allowed]
            row = {}
            for lab, k in BUDGET_LADDER:
                t0 = time.time()
                em = nodes.spacing_select(fld, allowed, k, min_px=3.0)
                n = int(em.sum())
                pred = em.astype(np.float32)
                res, term = evaluator.evaluate(pred, fold, eligible, block_side=200)
                terms[(arm, lab)] = term if terms[(arm, lab)] is None else terms[(arm, lab)] + term
                # delta of the closed form, from the template's own node identities
                nd = nodes.node_dti(em, fold["truth"] & fold["region"], eligible)
                S = float(n)
                delta = (S - nd["tax"]) - nd["T"]
                row[lab] = dict(dti=res["dti"], placed=n, requested=k, fill=n / k if k else None,
                                T=nd["T"], G=nd["G"], tax=nd["tax"], delta=delta,
                                closed_form=(nd["T"] / (0.2 * S + 0.8 * nd["G"] - 0.2 * delta)
                                             if nd["G"] else None),
                                seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {fold['fold']} {arm}: " +
                " ".join(f"{lab}={row[lab]['dti']:.4f}" for lab, _ in BUDGET_LADDER))
        out["folds"].append(rec)
    # pooled summaries per budget, candidate = disagreement_post (the brief's discovery signal)
    out["pooled"] = {}
    for lab, k in BUDGET_LADDER:
        tbm = {a: terms[(a, lab)] for a in ARMS}
        out["pooled"][lab] = evaluator.pooled_summary(tbm, draws=1000, seed=SEED,
                                                      candidate="disagreement_post")
    # instrument-optimal budget per arm, then the prevalence-corrected board budget
    _pc = json.loads((EVID / "h88_audit.json").read_text())["prevalence_correction"]
    ratio = float(_pc["ratio_instrument_over_score_algebra"] or _pc["ratio_instrument_over_docstring_mid"])
    optimum = {}
    labs = [lab for lab, _ in BUDGET_LADDER]
    for a in ARMS:
        curve = {lab: out["pooled"][lab]["scores"][a]["dti"] for lab in labs}
        best = max(curve, key=lambda l: curve[l])
        k_inst = dict(BUDGET_LADDER)[best]
        optimum[a] = dict(curve=curve, instrument_optimum_label=best,
                          instrument_optimum_dots_per_fold=k_inst,
                          instrument_optimum_total=k_inst * 4,
                          prevalence_ratio=ratio,
                          board_corrected_total_dots=int(round(k_inst * 4 / ratio)),
                          monotone_rising=bool(all(curve[lab] <= curve[labs[i + 1]]
                                                   for i, lab in enumerate(labs[:-1]))),
                          note=("the correction is a proportionality argument for a self-similar "
                                "field, not a measurement on the board; when monotone_rising is "
                                "true the instrument optimum is only bounded below by the top rung "
                                "and the corrected board budget is likewise a lower bound"))
    out["optimum"] = optimum
    out["finished_utc"] = now()
    write("ladder", out)
    log("optimum: " + json.dumps({a: dict(board=optimum[a]["board_corrected_total_dots"],
                                          inst=optimum[a]["instrument_optimum_label"],
                                          best=round(max(optimum[a]["curve"].values()), 6))
                                  for a in ARMS}, default=str))
    return out


# ------------------------------------------------------------------------------------ emit
def view_rank_mosaic(folds, store, shape, ring_px, eligible, tags=("post",)):
    """Out-of-fold percentile-rank mosaics of both views, one quadrant per fold.

    ``ranks[tag][view]`` holds the within-fold percentile rank of that view's prediction on the
    fold's emission strip and NaN elsewhere, so the whole-footprint field is strictly out-of-fold.
    ``strata`` (returned only when ``"pre"`` is requested, else None) is the shared
    ``cotrain.strata`` mask over the *pre* fields: 0 silent, 1 concordant, 2 A-only, 3 B-only.
    ``cotrain.strata`` needs FLATTENED inputs -- pass ``.ravel()`` -- or it raises at
    ``src/gems52/cotrain.py:283``.
    """
    ranks = {t: {"A": np.full(shape, np.nan, np.float32), "B": np.full(shape, np.nan, np.float32)}
             for t in tags}
    strata_acc = np.zeros(shape, np.int8) if "pre" in tags else None
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        idx = np.flatnonzero(allowed.ravel())
        pre = {}
        for tag in tags:
            for v in ("A", "B"):
                g = base.to_grid(store.flat_idx,
                                 np.load(WORK.parent / "h61" / f"pred_{tag}_{v}_f{f}.npy"), shape)
                ranks[tag][v].ravel()[idx] = base.pct_rank(g.ravel()[idx])
                del g
                if tag == "pre":
                    pre[v] = base.to_grid(store.flat_idx,
                                          np.load(WORK.parent / "h61" / f"pred_pre_{v}_f{f}.npy"),
                                          shape)
        if "pre" in tags:
            st = CT.strata(np.nan_to_num(pre["A"], nan=-1.0).ravel(),
                           np.nan_to_num(pre["B"], nan=-1.0).ravel(),
                           eligible, q_conf=0.98, q_abstain_hi=0.60)["mask"]
            strata_acc.ravel()[idx] = st.ravel()[idx]
            del st
        del pre
    return ranks, strata_acc


def disagreement_field(ranks):
    """rank(A_post) - rank(B_post) over the whole footprint (NaN rows become -1)."""
    return np.nan_to_num(ranks["A"] - ranks["B"], nan=-1.0)


def union_field(ranks):
    """max(rank(A), rank(B)) over the whole footprint -- the mandated comparator, never shipped."""
    return np.nan_to_num(np.maximum(ranks["A"], ranks["B"]), nan=-1.0)


def placement_field(field, cat, eligible, sample_path):
    """Metric-aware placement domain: footprint, outside the 200 m collar, never on catalogue."""
    with rasterio.open(sample_path) as s:
        smp = s.read(1)
    footprint = np.isfinite(smp) & (smp > -1e38)
    dcat = ndi.distance_transform_edt(~cat)
    allowed = footprint & eligible & (dcat > 2.0) & ~cat
    del dcat
    fld = np.full(field.shape, -1.0, np.float32)
    fld[allowed] = field[allowed]
    return fld, allowed, footprint


def stage_emit():
    """Assemble the out-of-fold field over the whole footprint, place it, write the portal file."""
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    ensure_fit()
    ensure_exchange()
    audit = json.loads((EVID / "h88_audit.json").read_text())
    ladder = json.loads((EVID / "h88_ladder.json").read_text())
    # pre-registered pick: the in-lane arm with the best pooled DTI at its instrumentation optimum;
    # ties and negatives fall back to the brief's mandated discovery field.
    # The brief mandates the disagreement field, and it forbids shipping merely the union of the two
    # views, so `union_max` and `single_B` are comparators only and can never be the shipped arm.
    best_arm = "disagreement_post"
    best_val = max(ladder["optimum"][best_arm]["curve"].values())
    control_val = max(ladder["optimum"]["single_B"]["curve"].values())
    k_total = int(ladder["optimum"][best_arm]["board_corrected_total_dots"])
    k_total = max(1500, min(k_total, 120000))
    log(f"shipped arm {best_arm} pooled-instrument max {best_val:.6f} vs single_B {control_val:.6f}; "
        f"board-corrected budget {k_total}")

    # ---- whole-footprint out-of-fold mosaic of the two views (each quadrant from its own fold)
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        shape = ds.shape
    ranks, strata_acc = view_rank_mosaic(folds, store, shape, ring_px, eligible, tags=("post", "pre"))
    if best_arm == "disagreement_post":
        field = disagreement_field(ranks["post"])
    elif best_arm == "union_max":
        field = union_field(ranks["post"])
    else:
        field = (strata_acc == 2).astype(np.float32)
    del ranks

    # ---- placement domain: footprint, outside the 200 m catalogue collar (Euclidean, template rule)
    fld, allowed, footprint = placement_field(field, cat, eligible,
                                              ROOT / "data/sample_submission.tif")
    em = nodes.spacing_select(fld, allowed, k_total, min_px=3.0).astype(np.float32)
    n = int(em.sum())
    log(f"placed {n} of {k_total} dots; allowed {int(allowed.sum()):,} px")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"h88-cotrain-disagreement-support-cal-{n}px-20261010"
    fname = f"gems52-h88-cotrain-disagree-supportcal-{n}px-{ts}.tif"
    SUB.mkdir(parents=True, exist_ok=True)
    from gems52 import submission_writer
    rec = submission_writer.write_submission(
        SUB / fname, em, ROOT / "data/sample_submission.tif", footprint,
        note=f"H88 co-train disagreement {best_arm}, prevalence-calibrated {n}px, 3px spacing, 200m collar",
        name=name,
        metadata=dict(arm=best_arm, dots=n, min_separation_px=3.0, catalogue_collar_m=200,
                      board_corrected_budget=k_total,
                      instrument_max_pooled_dti=best_val, single_B_instrument_max=control_val))
    log(f"wrote {SUB / fname} sha256 {rec['sha256'][:16]} zip {rec['zip_file']}")

    # ---- downloads copies (short alias, byte-identical)
    DOWN.mkdir(parents=True, exist_ok=True)
    for src, alias in ((SUB / fname, DOWN / fname), (SUB / fname, DOWN / "h88-candidate.tif"),
                       (SUB / fname, DOWN / "h88-candidate.zip")):
        if alias.suffix == ".zip":
            import shutil
            shutil.copy2(SUB / (Path(fname).with_suffix(".zip").name), alias)
        else:
            import shutil
            shutil.copy2(src, alias)
    return rec, fname, n, best_arm, best_val, control_val


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="all",
                    choices=["audit", "fit", "ladder", "emit", "all"])
    a = ap.parse_args()
    if a.stage in ("audit", "all"):
        stage_audit()
    if a.stage in ("fit", "all"):
        ensure_fit()
        ensure_exchange()
    if a.stage in ("ladder", "all"):
        stage_ladder()
    if a.stage in ("emit", "all"):
        stage_emit()
