#!/usr/bin/env python3
"""H72 -- surface-only (View B) emission under the lane rule.

Preregistered in ``knowledge/59_hypotheses_H72_preregistered.md`` and pinned by
``registry/h72_preregistration.json``; this runner refuses to start if the hash has moved.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61.setup`` (pins, cached feature store, label-blind quadrant folds,
  buffer), ``run_h61.sample_train`` / ``learner_for`` / ``predict_flat`` / ``pct_rank`` (the same
  rows, learner and seed as H61's View-B fit, so the single_B control must reproduce H71's receipt),
  ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1), ``gems52.nodes.spacing_select``,
  ``gems52.gates`` (lane_report, uniqueness_report, canonical), ``gems52.submission_writer``, and the
  census helper ``build_h61_submission.prior_paths``.
* Round-specific: the consensus pool (lane construction in the preregistration), the single-view
  field, the arm list, the build and the run card.

Stages (checkpointed; each refuses to overwrite a receipt written from different bytes)
--------------------------------------------------------------------------------------
    fit        View-B learner per fold (H61 rows, learner, seed) + per-feature canary AUCs
    consensus  census priors -> informative set -> consensus count over the footprint
    choose     largest consensus threshold T whose greedy fill reaches the budget at max near-dot <= 0.70
    holdout    single_B control, H72_B_lane candidate (pool at fixed T), random; pooled HOLDOUT-DTI
    build      stitched shipped field -> placement -> authoritative gates -> TIF -> uniqueness -> card

Usage: ``python scripts/run_h72.py [fit|consensus|choose|holdout|build|all]``
"""
from __future__ import annotations

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
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.spatial import cKDTree                                    # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
from build_h61_submission import prior_paths                         # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, nodes, submission_writer                   # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h72_preregistration.json"
WORK = ROOT / "work/h72"
EVID = ROOT / "evidence"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
SAMPLE = ROOT / "data/sample_submission.tif"
PREFIX = "gems52-h72-"
K_FOLD = 9400
K_TOTAL = 37600
NEAR_RADIUS = 3.0
T_GRID = (200, 150, 100, 80, 60, 40)   # loosest first; fixed by amendment 59a


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h72_{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False) + "\n")
    return p


def check_prereg() -> dict:
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if digest(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H72 preregistered hypothesis document changed after registration")
    for am in reg.get("amendments", []):
        if digest(ROOT / am["document"]) != am["sha256"]:
            raise SystemExit(f"H72 amendment changed after registration: {am['document']}")
    return reg


def support_of(canon: np.ndarray):
    """Gate convention: binary priors use >0, continuous priors use >=0.5 (gates.uniqueness_report)."""
    binary = bool(np.isin(canon, [0, 1]).all())
    return (canon > 0) if binary else (canon >= 0.5), binary


def halo(support: np.ndarray) -> np.ndarray:
    return ndi.binary_dilation(support, structure=gates._disk(NEAR_RADIUS))


def max_near_share(dots: np.ndarray, prior_supports: list) -> float:
    """Max over informative priors of (dots within 3 px of that prior's support) / (all dots).

    KD-tree, inclusive Euclidean bound 3 px; the authoritative number is gates.lane_report, run once at build.
    """
    d = np.argwhere(dots)
    if len(d) == 0:
        return 1.0
    worst = 0.0
    for p in prior_supports:          # each entry is an (n, 2) coordinate array
        if len(p) == 0:
            continue
        dist, _ = cKDTree(p).query(d, k=1, distance_upper_bound=NEAR_RADIUS + 1e-9)
        share = float(np.isfinite(dist).sum()) / len(d)
        worst = max(worst, share)
    return worst


SPACING_OFFSETS = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if dy * dy + dx * dx < 9]


def place_quota(field, pool, K, quotas):
    """Greedy top-K with hard-core spacing (d^2 >= 9 px^2, as nodes.spacing_select) and per-prior quotas.

    quotas: list of (packed_halo_bits, cap). A quota prior's 3 px halo is forbidden for the rest of
    the placement once its cap is reached, so the cap can never be exceeded (amendment 59a).
    """
    h, w = field.shape
    ncell = h * w
    f = field.ravel()
    idx = np.flatnonzero(pool.ravel())
    order = idx[np.argsort(-f[idx], kind="stable")]
    taken = np.zeros(ncell, bool)
    forb = np.zeros(ncell, bool)
    packed = [q for q, _ in quotas]
    caps = [c for _, c in quotas]
    counts = [0] * len(quotas)
    sel = []
    for fi in order:
        if len(sel) >= K:
            break
        fi = int(fi)
        if taken[fi] or forb[fi]:
            continue
        sel.append(fi)
        y, x = divmod(fi, w)
        for dy, dx in SPACING_OFFSETS:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w:
                taken[yy * w + xx] = True
        for k, pk in enumerate(packed):
            if (int(pk[fi >> 3]) >> (7 - (fi & 7))) & 1:
                counts[k] += 1
                if counts[k] == caps[k]:
                    forb |= np.unpackbits(pk, count=ncell).astype(bool)
    out = np.zeros(ncell, bool)
    out[np.asarray(sel, dtype=np.int64)] = True
    return out.reshape(h, w), len(sel)


def min_separation_ok(dots: np.ndarray) -> bool:
    p = np.argwhere(dots)
    if len(p) < 2:
        return True
    d, _ = cKDTree(p).query(p, k=2)
    return bool(d[:, 1].min() >= 3.0 - 1e-9)


def place_lane(field, pool, K, sups, eligible_shape, limit=0.70, rounds=6):
    """Lane-feasible placement: plain greedy, then quotas for every informative prior above the limit,
    re-placed until no prior exceeds it. Returns (dots, receipt)."""
    cap = int(np.floor(limit * K))
    quotas, qidx = [], set()
    history = []
    dots, n = None, 0
    for r in range(rounds):
        dots, n = place_quota(field, pool, K, quotas)
        shares = []
        for k, p in enumerate(sups):
            if len(p) == 0:
                shares.append(0.0)
                continue
            dist, _ = cKDTree(p).query(np.argwhere(dots), k=1, distance_upper_bound=NEAR_RADIUS + 1e-9)
            shares.append(float(np.isfinite(dist).sum()) / max(1, int(dots.sum())))
        worst = max(shares) if shares else 0.0
        over = [k for k, s in enumerate(shares) if s > limit and k not in qidx]
        history.append(dict(round=r, dots=int(dots.sum()), quotas=len(quotas), worst=worst, new_offenders=len(over)))
        log(f"  place_lane round {r}: dots {int(dots.sum())}/{K} quotas {len(quotas)} worst {worst:.4f} new {len(over)}")
        if int(dots.sum()) != K:
            break
        if not over:
            break
        for k in over:
            halo_k = ndi.binary_dilation(_mask_from(sups[k], eligible_shape), structure=gates._disk(NEAR_RADIUS))
            quotas.append((np.packbits(halo_k.ravel()), cap))
            qidx.add(k)
    ok = bool(dots is not None and int(dots.sum()) == K and history and history[-1]["worst"] <= limit
              and history[-1]["new_offenders"] == 0)
    return dots, dict(ok=ok, worst=history[-1]["worst"] if history else None, rounds=history,
                      quota_cap=cap, quota_priors=len(quotas), spacing_ok=min_separation_ok(dots) if dots is not None else False)


def _mask_from(coords, shape):
    m = np.zeros(shape, bool)
    if len(coords):
        m[coords[:, 0], coords[:, 1]] = True
    return m


def informative_supports(eligible, reg):
    """Distinct informative census priors as sparse support coordinates (same rule as stage_consensus)."""
    priors, _ = prior_paths(CENSUS, ("submission",))
    priors = [q for q in priors if not q.name.startswith(PREFIX) and q.exists()]
    sups, seen = [], set()
    for path in priors:
        with rasterio.open(path) as src:
            a = gates.canonical(src.read(1))
        dsha = hashlib.sha256(a.astype("<f4").tobytes()).hexdigest()
        if dsha in seen:
            continue
        seen.add(dsha)
        sup, _ = support_of(a)
        if sup.sum() == 0:
            continue
        if (halo(sup) & eligible).sum() / max(1, eligible.sum()) >= H72["thresholds"]["universal_coverage_probe_threshold"]:
            continue
        sups.append(np.argwhere(sup).astype(np.int32))
        del sup, a
    return sups


# --------------------------------------------------------------------------------------------
def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    WORK.mkdir(parents=True, exist_ok=True)
    out = dict(stage="fit", started_utc=now(), view_B_features=vb, n_B=len(vb), seed=SEED, folds=[])
    inv = store.inverse
    catd = ndi.distance_transform_edt(~cat)
    for fold in folds:
        f = fold["fold"]
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        t0 = time.time()
        X = store.gather(rows, vb)
        m = base.learner_for("B", SEED)
        m.fit(X, y)
        del X
        p = base.predict_flat(store, m, vb, flat)
        np.save(WORK / f"pred_B_f{f}.npy", p)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        oof_auc = float(roc_auc_score(np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))],
                                      np.r_[p[inv[pos_g]], p[inv[neg_g]]]))
        # canary: every B feature ALONE, measured on the held-out region (no fit, no labels used to choose)
        g_all = np.r_[pos_g, neg_g]
        y_all = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        canary = {}
        for name in vb:
            v = store.gather(g_all, [name])[:, 0]
            ok = np.isfinite(v)
            a = float(roc_auc_score(y_all[ok], v[ok])) if ok.sum() > 10 and len(np.unique(y_all[ok])) == 2 else 0.5
            canary[name] = dict(auc=a, direction_insensitive=max(a, 1 - a))
        rec = dict(fold=f, n_train=int(len(rows)), n_pos=int(y.sum()), region_px=int(fold["region"].sum()),
                   truth_px=int(fold["truth"].sum()), heldout_region_auc_B=oof_auc,
                   fit_predict_seconds=round(time.time() - t0, 1), canary=canary,
                   canary_max_direction_insensitive=max(c["direction_insensitive"] for c in canary.values()))
        out["folds"].append(rec)
        log(f"fold {f}: B region AUC {oof_auc:.4f}; canary max {rec['canary_max_direction_insensitive']:.4f}")
    out["canary_alarm"] = any(r["canary_max_direction_insensitive"] >= H72["thresholds"]["canary_auc_alarm"]
                              for r in out["folds"])
    out["finished_utc"] = now()
    write("fit", out)
    return out


# --------------------------------------------------------------------------------------------
def stage_consensus():
    """Census priors -> informative set -> consensus count (distinct decoded patterns covering each pixel)."""
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    if not CENSUS.exists():
        raise SystemExit("census receipt missing: run scripts/fetch_prior_inventory.py first")
    priors, pmeta = prior_paths(CENSUS, ("submission",))
    priors = [p for p in priors if not p.name.startswith(PREFIX) and p.exists()]
    log(f"registry: {len(priors)} rasters ({pmeta})")
    footprint_px = int(eligible.sum())
    consensus = np.zeros(eligible.shape, np.uint16)
    seen, table = set(), []
    for path in priors:
        try:
            with rasterio.open(path) as src:
                if src.count != 1 or src.shape != eligible.shape:
                    raise ValueError("not aligned")
                a = gates.canonical(src.read(1))
            dsha = hashlib.sha256(a.astype("<f4").tobytes()).hexdigest()
            sup, binary = support_of(a)
            cov = float((halo(sup) & eligible).sum()) / footprint_px
            rec = dict(path=str(path), decoded_sha256=dsha, binary=binary, support_px=int(sup.sum()),
                       coverage_3px_of_footprint=cov, universal_coverage_probe=cov >= H72["thresholds"]["universal_coverage_probe_threshold"],
                       duplicate_of_earlier=dsha in seen)
            if not rec["duplicate_of_earlier"] and not rec["universal_coverage_probe"] and sup.sum() > 0:
                consensus += halo(sup).astype(np.uint16)
            seen.add(dsha)
            table.append(rec)
        except Exception as exc:
            table.append(dict(path=str(path), error=f"{type(exc).__name__}: {str(exc)[:160]}"))
    WORK.mkdir(parents=True, exist_ok=True)
    np.save(WORK / "consensus.npy", consensus)
    informative = [r for r in table if "error" not in r and not r["duplicate_of_earlier"]
                   and not r["universal_coverage_probe"] and r["support_px"] > 0]
    out = dict(stage="consensus", finished_utc=now(), n_rasters=len(priors), n_informative_distinct=len(informative),
               n_probes=sum(1 for r in table if r.get("universal_coverage_probe")),
               n_duplicates=sum(1 for r in table if r.get("duplicate_of_earlier")),
               n_errors=sum(1 for r in table if "error" in r), census=pmeta, consensus_max=int(consensus.max()),
               consensus_on_footprint_max=int(consensus[eligible].max()), per_raster=table)
    write("consensus", out)
    log(f"consensus: {len(informative)} informative distinct priors; max {int(consensus[eligible].max())}")
    return out


# --------------------------------------------------------------------------------------------
def _fold_fields(folds, store, cat, ring_px, eligible):
    """Per fold: allowed domain (label-blind), B percentile rank over allowed."""
    flat = store.flat_idx
    out = []
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        g = base.to_grid(flat, np.load(WORK / f"pred_B_f{f}.npy"), eligible.shape)
        r = np.full(eligible.shape, np.nan, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        out.append(dict(fold=f, allowed=allowed, rank=r, grid=g))
    return out


def stage_choose():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    cons = np.load(WORK / "consensus.npy")
    ff = _fold_fields(folds, store, cat, ring_px, eligible)
    rB = np.full(eligible.shape, np.nan, np.float32)
    for d in ff:
        m = np.isfinite(d["rank"]) & ~np.isfinite(rB)
        rB[m] = d["rank"][m]
    finite = eligible & np.isfinite(rB)
    field = np.where(finite, rB, -1.0).astype(np.float32)
    sups = informative_supports(eligible, reg)
    log(f"informative supports for the search: {len(sups)}")
    trials, chosen = [], None
    for T in H72["thresholds"]["consensus_T_grid"]:
        pool = finite & (cons <= T)
        n_pool = int(pool.sum())
        if n_pool < K_TOTAL:
            trials.append(dict(T=T, pool_px=n_pool, ok=False, reason="pool smaller than budget"))
            continue
        t0 = time.time()
        dots, rec = place_lane(field, pool, K_TOTAL, sups, eligible.shape, limit=H72["thresholds"]["lane_near_dot_fraction"])
        trials.append(dict(T=T, pool_px=n_pool, seconds=round(time.time() - t0, 1), **rec))
        log(f"T={T}: pool {n_pool} px, ok={rec['ok']}, worst {rec['worst']}")
        if rec["ok"]:
            chosen = dict(T=T, pool_px=n_pool, worst_near_share=rec["worst"], quota_priors=rec["quota_priors"])
            break
    out = dict(stage="choose", finished_utc=now(), placement="place_lane (greedy + per-prior quota, amendment 59a)",
               trials=trials, chosen=chosen, n_informative_supports=len(sups),
               limit=H72["thresholds"]["lane_near_dot_fraction"],
               note="fast KD-tree screen during search; the authoritative lane_report runs once in build")
    write("choose", out)
    if chosen is None:
        log("NO lane-feasible consensus threshold found under the amended placement: a measured wall")
    return out


# --------------------------------------------------------------------------------------------
def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = H72["thresholds"]
    ch = json.loads((EVID / "h72_choose.json").read_text())["chosen"]
    if ch is None:
        raise SystemExit("holdout refused: no lane-feasible consensus threshold (see h72_choose)")
    T = ch["T"]
    cons = np.load(WORK / "consensus.npy")
    flat = store.flat_idx
    arms = ("single_B", "H72_B_lane", "random")
    terms = {a: None for a in arms}
    SUPS = informative_supports(eligible, reg)
    out = dict(stage="holdout", started_utc=now(), budget_per_fold=K_FOLD, min_separation_px=3.0,
               consensus_threshold_T=T, arms=list(arms), folds=[])
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = base.to_grid(flat, np.load(WORK / f"pred_B_f{f}.npy"), eligible.shape)
        ai = np.flatnonzero(allowed.ravel())
        r = np.full(eligible.shape, np.nan, np.float32)
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)
        fields = {
            "single_B": (np.nan_to_num(r, nan=-1.0), allowed),
            "random": (rnd, allowed),
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(fold["region"].sum()), pool_px_candidate=int((allowed & (cons <= T)).sum()),
                   arms={})
        # the candidate arm uses the same lane placement as the shipped file (amendment 59a)
        t0 = time.time()
        em_c, rec_c = place_lane(np.nan_to_num(r, nan=-1.0), allowed & (cons <= T), K_FOLD, SUPS,
                                 eligible.shape, limit=th["lane_near_dot_fraction"])
        result_c, term_c = evaluator.evaluate(em_c.astype(np.float32), fold, eligible, block_side=200)
        terms["H72_B_lane"] = term_c if terms["H72_B_lane"] is None else terms["H72_B_lane"] + term_c
        row = dict(result_c)
        row.update(placed=int(em_c.sum()), requested=K_FOLD, filled=bool(em_c.sum() == K_FOLD),
                   lane_ok=rec_c["ok"], lane_worst=rec_c["worst"], quota_priors=rec_c["quota_priors"],
                   spacing_ok=rec_c["spacing_ok"], seconds=round(time.time() - t0, 1))
        rec["arms"]["H72_B_lane"] = row
        log(f"fold {f} arm H72_B_lane: placed {int(em_c.sum())}/{K_FOLD} DTI {result_c['dti']:.6f} lane_ok {rec_c['ok']}")
        for arm, (field, dom) in fields.items():
            t0 = time.time()
            em = nodes.spacing_select(field, dom, K_FOLD, min_px=3.0)
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=int(em.sum()), requested=K_FOLD, filled=bool(em.sum() == K_FOLD),
                       seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {f} arm {arm}: placed {int(em.sum())}/{K_FOLD} DTI {result['dti']:.6f}")
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                             candidate="H72_B_lane")
    out["all_arms_filled"] = bool(all(a["arms"][k]["filled"] for a in out["folds"] for k in arms))
    out["withheld_positive_pixels"] = out["pooled"]["scores"]["H72_B_lane"]["withheld_positive_pixels"]
    out["finished_utc"] = now()
    out["caveat"] = ("HOLDOUT-DTI on the label-blind quadrant splitter; an instrument reading, not a forecast "
                     "and not an organiser score.")
    write("holdout", out)
    return out


# --------------------------------------------------------------------------------------------
def stage_build():
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = H72["thresholds"]
    ch = json.loads((EVID / "h72_choose.json").read_text())["chosen"]
    if ch is None:
        raise SystemExit("build refused: no lane-feasible consensus threshold")
    th = H72["thresholds"]
    T = ch["T"]
    cons = np.load(WORK / "consensus.npy")
    ff = _fold_fields(folds, store, cat, ring_px, eligible)
    rB = np.full(eligible.shape, np.nan, np.float32)
    for d in ff:
        m = np.isfinite(d["rank"]) & ~np.isfinite(rB)
        rB[m] = d["rank"][m]
    pool = eligible & np.isfinite(rB) & (cons <= T)
    field = np.where(pool, rB, -1.0).astype(np.float32)
    sups = informative_supports(eligible, reg)
    em, prec = place_lane(field, pool, K_TOTAL, sups, eligible.shape, limit=th["lane_near_dot_fraction"])
    n = int(em.sum())
    if n != K_TOTAL or not prec["ok"]:
        raise SystemExit(f"build refused: placed {n} of {K_TOTAL}, lane ok={prec['ok']}")
    write("build_placement", dict(stage="build_placement", receipt=prec, consensus_T=T, dots=n))
    pred = em.astype(np.float32)
    # ----- authoritative lane gates on the final dots and the surface field
    priors, pmeta = prior_paths(CENSUS, ("submission",))
    priors = [p for p in priors if not p.name.startswith(PREFIX)]
    surface = np.where(eligible & np.isfinite(rB), rB, 0.0).astype(np.float32)
    surf_allowed = eligible & np.isfinite(rB)
    lane_surface = gates.lane_report(surface, surf_allowed, priors, sample=SAMPLE, phase="surface", log=log)
    write("lane_surface", lane_surface)
    lane_dots = gates.lane_report(pred, eligible, priors, sample=SAMPLE, phase="dots", log=log)
    write("lane_dots", lane_dots)
    uniq = gates.uniqueness_report(pred, priors, top=None)
    write("uniqueness", uniq)
    # ----- write, validate, package
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"gems52-h72-surfaceB-lanefeasible-{K_TOTAL}px-{stamp}"
    note = ("H72 surface-only B rank, consensus-pool lane-feasible, 3 px spacing; holdout measured; "
            "research, not slot-approved")
    path = SUBM / f"{name}.tif"
    rec = submission_writer.write_submission(path, pred, SAMPLE, eligible, note=note, name=name,
                                             metadata=dict(round="H72", consensus_T=T,
                                                           lane_policy=lane_dots["policy"]["verdict"],
                                                           lane_literal=lane_dots["literal"]["verdict"]))
    write("build", dict(stage="build", finished_utc=now(), file=str(path.relative_to(ROOT)),
                        receipt=rec, consensus_T=T, dots=n, registry=pmeta,
                        registry_rasters=len(priors)))
    return rec


H72: dict = {}

# --------------------------------------------------------------------------------------------
def stage_control():
    """Instrument check only: single_B and random at the preregistered budget (no candidate arm).

    Runs when no lane-feasible threshold exists, so the reproduction check (target 0.174571 from H71) still
    tells the reader whether this sandbox's instrument matches the committed one. It is not a candidate score.
    """
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    arms = ("single_B", "random")
    terms = {a: None for a in arms}
    out = dict(stage="control", started_utc=now(), budget_per_fold=K_FOLD, arms=list(arms), folds=[],
               reproduction_target_H71=0.174571, reproduction_tolerance=H72["thresholds"]["control_reproduction_tolerance"])
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = base.to_grid(flat, np.load(WORK / f"pred_B_f{f}.npy"), eligible.shape)
        ai = np.flatnonzero(allowed.ravel())
        r = np.full(eligible.shape, np.nan, np.float32)
        r.ravel()[ai] = base.pct_rank(g.ravel()[ai])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)
        rec = dict(fold=f, arms={})
        for arm, field in (("single_B", np.nan_to_num(r, nan=-1.0)), ("random", rnd)):
            em = nodes.spacing_select(field, allowed, K_FOLD, min_px=3.0)
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=int(em.sum()), requested=K_FOLD, filled=bool(em.sum() == K_FOLD))
            rec["arms"][arm] = row
            log(f"control fold {f} {arm}: placed {int(em.sum())} DTI {result['dti']:.6f}")
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=int(H72["thresholds"]["bootstrap_draws"]), seed=SEED,
                                             candidate="single_B")
    d = out["pooled"]["scores"]["single_B"]["dti"]
    out["single_B_dti"] = d
    out["reproduction_abs_delta"] = abs(d - out["reproduction_target_H71"])
    out["reproduction_pass"] = bool(out["reproduction_abs_delta"] <= out["reproduction_tolerance"])
    out["finished_utc"] = now()
    write("control", out)
    return out


def main(argv=None) -> int:
    global H72
    argv = list(sys.argv[1:] if argv is None else argv)
    stage = argv[0] if argv else "all"
    H72 = check_prereg()
    if stage in ("fit", "all"):
        stage_fit()
    if stage in ("consensus", "all"):
        stage_consensus()
    if stage in ("choose", "all"):
        stage_choose()
    if stage in ("holdout", "all"):
        stage_holdout()
    if stage in ("build", "all"):
        stage_build()
    if stage == "control":
        stage_control()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
