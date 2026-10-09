#!/usr/bin/env python3
"""H66cover -- co-training lane, round 2026-10-09: the cover-gated A-only emission (H66-A).

Namespaced h66cover-* after a parallel-session label collision (IR-H66-015): the site's
h66-* names belong to the structural-coherence H66 (PR #56).

Lane: the brief's co-training paragraph.  View A is potential-field/subsurface, View B is surface,
and disagreement is the discovery signal.  Preregistered in
``knowledge/43_h66cover_hypotheses_preregistered.md`` and pinned by ``registry/h66cover_preregistration.json``;
this runner refuses to start if the hash moves.

What is shared and what is not
------------------------------
* Shared, not forked: ``run_h61`` supplies ``setup``, ``stage_canary``, ``stage_fit`` and
  ``stage_exchange`` (identical views, identical learner, identical seed -- H61's fits are
  reproduced, not re-tuned), and the evaluator ``gems52.evaluate_holdout``
  (gems52-pooled-hide-v1).  ``build_h61_submission`` supplies the prior-census loader.
* Round-specific: one extra holdout arm ``h66a_cover_gated_a_only`` alongside the six frozen H61
  arms, and the build field of knowledge/43 section 4:

      field66 = (rankA - rankB) * cover_norm   where rankA >= 0.95 and 0.35 <= rankB <= 0.65
                = -1                           elsewhere

  with cover_norm the log1p min-max normalised depth-to-basement (raw_band_15) over the allowed
  domain.  Every emitted cell is an A-only candidate by construction (buried-beneath-cover reading
  of the disagreement signal).

Stages
------
    canary      base.stage_canary (leakage canary, reused unchanged)               -- E1
    fit         base.stage_fit (both views, every fold)                           -- E1
    exchange    base.stage_exchange (independence screen + one whole-segment
                confident-to-abstaining pseudo-label round)                      -- E1/E2
    holdout     seven arms, pooled HOLDOUT-DTI + paired 95% CI, candidate both
                disagreement_post (frozen H61 comparison) and h66a (this round)    -- E2
    build       exact novelty, metric-aware placement, per-raster cap, lane gates
                (surface before placement, dots after), not-union, GeoTIFF,
                reasoning CSV, projection, run card (nothing is uploaded)        -- E3

Usage: ``python scripts/run_h66.py [canary|fit|exchange|holdout|build|all]``
"""
from __future__ import annotations

import csv
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
from scipy.stats import rankdata                                     # noqa: E402

import run_h61 as base                                               # noqa: E402
import build_h61_submission as b61                                   # noqa: E402  (prior census helper only)
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, metric, nodes, spatial, structural, submission_writer  # noqa: E402

SEED = base.SEED
WORK = ROOT / "work/h66"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
REG_PATH = ROOT / "registry/h66cover_preregistration.json"
BUDGET = int(os.environ.get("H66_BUDGET", "37600"))   # template budget (H61/H63/H64 comparable)
REUSE_GATES = os.environ.get("H66_REUSE_GATES") == "1"   # hash-verified receipt reuse only
NOVELTY_RADIUS_PX = 3
MAX_NOVELTY_ITER = 12
NOVELTY_MIN_PX = 3.0
PREFIX = "gems52-h66-"
H66A_ARM = "h66a_cover_gated_a_only"
CHAMPION_REF = ("ref_h33_2_b2", 0.2778)
ARMS = tuple(base.ARMS) + (H66A_ARM,)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_h66cover(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h66cover_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"h66cover_{name}.json").write_text(p.read_text())
    return p


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pct(v: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1] over finite entries, ties averaged (H61 operating rank)."""
    v = np.asarray(v, np.float64)
    good = np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if good.any():
        out[good] = (rankdata(v[good], method="average") - 0.5) / float(good.sum())
    return out.astype(np.float32)


# ------------------------------------------------------------------ preregistration + redirects
def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if sha(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("H66 preregistered document changed after registration; refusing to run")
    for am in reg.get("amendments", []):
        if sha(ROOT / am["document"]) != am["sha256"]:
            raise SystemExit(f"H66 amendment changed after registration: {am['document']}")
    # the shared H61 stages re-verify the H61 document themselves inside base.setup()
    h61 = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
    if sha(ROOT / h61["hypothesis_document"]) != h61["hypothesis_sha256"]:
        raise SystemExit("H61 preregistered document moved; the shared stages refuse to run")
    reg["thresholds"] = dict(h61["thresholds"])          # H66 restates no threshold
    return reg


def redirect() -> None:
    """Point the shared H61 stages at H66 storage.  Nothing under evidence/h61_* is written."""
    WORK.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.write = write_h66cover
    # learner_for is deliberately NOT overridden: H66 changes no learner.


def cover_norm_over(store, allowed_idx: np.ndarray) -> np.ndarray:
    """log1p(depth to basement), min-max normalised over the given allowed rows."""
    cov = store.gather(allowed_idx, ["raw_band_15"])[:, 0].astype(np.float64)
    c = np.log1p(np.maximum(cov, 0.0))
    lo, hi = float(c.min()), float(c.max())
    return ((c - lo) / (hi - lo)).astype(np.float32) if hi > lo else np.zeros_like(c, np.float32)


def h66a_field(rank_a: np.ndarray, rank_b: np.ndarray, cover_norm: np.ndarray,
               allowed_idx: np.ndarray, shape: tuple, th: dict) -> np.ndarray:
    """The frozen H66-A field (knowledge/43 section 4).  -1 outside the A-only gate."""
    gate = (rank_a >= th["donor_rank_min"]) & (rank_b >= th["receiver_rank_interval"][0]) \
        & (rank_b <= th["receiver_rank_interval"][1])
    field = np.full(int(np.prod(shape)), -1.0, np.float32)
    fa = np.full(int(np.prod(shape)), -1.0, np.float32)
    fb = np.full(int(np.prod(shape)), -1.0, np.float32)
    fc = np.zeros(int(np.prod(shape)), np.float32)
    fa[allowed_idx] = rank_a
    fb[allowed_idx] = rank_b
    fc[allowed_idx] = cover_norm
    field[allowed_idx] = np.where(gate, (fa[allowed_idx] - fb[allowed_idx]) * fc[allowed_idx], -1.0)
    return field.reshape(shape)


# ------------------------------------------------------------------ E2: holdout, seven arms
def stage_holdout66(reg) -> dict:
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = reg["thresholds"]
    flat = store.flat_idx
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    ex = json.loads((EVID / "h66cover_pseudo_exchange.json").read_text())
    if not ex.get("allowed_exchange", False):
        log("NOTE: the independence screen fired; post-exchange arms are refits without transfer")
    out = dict(stage="holdout", started_utc=now(), budget_per_arm_per_fold=K,
               min_separation_px=min_px, arms=list(ARMS), folds=[],
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               h66a_rule="field66 = (rankA - rankB) * cover_norm(log1p(raw_band_15)) inside "
                         "rankA >= 0.95 and 0.35 <= rankB <= 0.65; -1 elsewhere; per fold over the "
                         "fold's own allowed domain")
    terms = {a: None for a in ARMS}
    for fold in folds:
        f = fold["fold"]
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        allowed_idx = np.flatnonzero(allowed.ravel())
        g = {}
        for v in ("A", "B"):
            g[f"pre_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f}.npy"), eligible.shape)
            g[f"post_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        r_pre = {v: np.full(g[f"pre_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        r_post = {v: np.full(g[f"post_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r_pre[v].ravel()[allowed_idx] = pct(g[f"pre_{v}"].ravel()[allowed_idx])
            r_post[v].ravel()[allowed_idx] = pct(g[f"post_{v}"].ravel()[allowed_idx])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        cover_norm = cover_norm_over(store, allowed_idx)
        fields = {
            "single_A": np.nan_to_num(r_pre["A"], nan=-1.0),
            "single_B": np.nan_to_num(r_pre["B"], nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(r_pre["A"], r_pre["B"]), nan=-1.0),
            "disagreement_pre": np.nan_to_num(r_pre["A"] - r_pre["B"], nan=-1.0),
            "disagreement_post": np.nan_to_num(r_post["A"] - r_post["B"], nan=-1.0),
            "random": rnd,
            H66A_ARM: h66a_field(r_post["A"].ravel()[allowed_idx], r_post["B"].ravel()[allowed_idx],
                                 cover_norm, allowed_idx, eligible.shape, th),
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()), arms={})
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
            row.update(placed=n, requested=K, filled=bool(n == K), seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {f} arm {arm}: emitted {n}/{K} DTI {result['dti']:.6f} tpw {result['tpw']:.1f}")
        # not-the-union diagnostics on the H66-A arm, reusing the already-placed arms
        d_em = em_by_arm[H66A_ARM] > 0
        a_em, b_em, u_em = em_by_arm["single_A"], em_by_arm["single_B"], em_by_arm["union_max"]
        dis_field = fields[H66A_ARM][allowed]
        union_field = fields["union_max"]
        rec["not_the_union_h66a"] = dict(
            h66a_cells_vs_A=int((d_em != a_em).sum()), h66a_cells_vs_B=int((d_em != b_em).sum()),
            h66a_cells_vs_union=int((d_em != u_em).sum()),
            h66a_dots_also_in_A=int((d_em & a_em).sum()),
            h66a_dots_also_in_B=int((d_em & b_em).sum()),
            h66a_dots_also_in_union=int((d_em & u_em).sum()),
            jaccard_with_union_max=float((d_em & u_em).sum() / max(1, int((d_em | u_em).sum()))),
            spearman_h66a_vs_unionmax=float(np.corrcoef(rankdata(dis_field),
                                                       rankdata(union_field[allowed]))[0, 1]),
            a_only_gate_px=int(((fields[H66A_ARM] > -1) & allowed).sum()),
            emitted_cells_inside_gate=int((d_em & (fields[H66A_ARM] > -1)).sum()),
            note="the H66-A field is zero outside the A-only stratum; max(A,B) is positive wherever "
                 "either view is high, so the field is not a rescaling of the union")
        for k in ("random", "disagreement_pre"):
            em_by_arm.pop(k, None)
        out["folds"].append(rec)
        del g, r_pre, r_post, fields
    pooled_frozen = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                             candidate="disagreement_post")
    pooled_h66a = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                           candidate=H66A_ARM)
    out["pooled_frozen_candidate_disagreement_post"] = pooled_frozen
    out["pooled"] = pooled_h66a          # this round's candidate
    out["pooled_h66a_candidate"] = pooled_h66a
    out.update(finished_utc=now(),
               withheld_positive_pixels=pooled_h66a["scores"][H66A_ARM]["withheld_positive_pixels"],
               all_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"] for arm in ARMS)),
               paired_h66a_minus_single_B=pooled_h66a["paired_differences"]["single_B"],
               caveat="HOLDOUT-DTI on the corrected label-blind-quadrants-v2 splitter. This simulator "
                      "measured Spearman -0.10 against the owner-reported board in round R4, so it "
                      "screens procedures; it does not by itself promote anything.")
    write_h66cover("holdout", out)
    return out


# ------------------------------------------------------------------ E3: build
def stage_build66(reg) -> dict:
    th = reg["thresholds"]
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    flat, inv, shape = store.flat_idx, store.inverse, eligible.shape
    N = int(np.prod(shape))
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
        sample_grid = (ref.shape, ref.crs, ref.transform)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    del sub
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    folds = list(spatial.folds(cat, eligible, buffer_px=th["buffer_px"]))

    # ---- OUT-OF-FOLD mosaic of the post-exchange views (identical to the H61 build)
    mos = {}
    for v in ("A", "B"):
        g = np.full(N, np.nan, np.float32)
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
    n_allowed_pre = int(allowed.sum())
    log(f"emission domain: eligible {int(eligible.sum())} -> allowed {n_allowed_pre}")

    # ---- registry: census + informative/probe classification (H64 rule, knowledge/39c)
    priors_all, pmeta = b61.prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
    priors_all = [p for p in priors_all if not p.name.startswith(PREFIX)]
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
        if cov >= gates.PROBE_COVERAGE:
            probes.append(dict(name=pp.name, coverage_3px_of_eligible=round(cov, 6)))
            continue
        informative.append(pp)
        supports[pp.name] = np.flatnonzero(sup.ravel()).astype(np.int32)
    exact_union = np.zeros(N, bool)
    for nm in supports:
        exact_union[supports[nm]] = True
    allowed = allowed & ~exact_union.reshape(shape)
    novelty = dict(rule=("(1) no emitted cell is a positive pixel of an informative registry raster; "
                         "(2) no emitted cell lies within 3 px of a positive pixel of an informative "
                         "registry raster whose near-dot share of the emission exceeds 0.70 (the "
                         "lane's per-raster rule); universal-coverage probes (3 px coverage >= "
                         f"{gates.PROBE_COVERAGE}) are excluded as in gates.lane_report policy"),
                   radius_px=NOVELTY_RADIUS_PX, near_limit=gates.NEAR_LIMIT,
                   informative_rasters=len(informative), probe_rasters=len(probes), probes=probes,
                   rasters_skipped_shape=n_skip, exact_union_px=int(exact_union.sum()),
                   allowed_before=n_allowed_pre, allowed_after_exact=int(allowed.sum()),
                   carried_from="knowledge/39c (H64 declared post hoc; applied identically here)")
    log(f"novelty (1) exact: informative {len(informative)}, probes {len(probes)}; allowed "
        f"{n_allowed_pre} -> {int(allowed.sum())}")
    if int(allowed.sum()) < 1:
        raise SystemExit("exact novelty leaves no cells")

    # ---- the frozen H66-A field over the allowed domain
    allowed_idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[allowed_idx] = pct(mos["A"].ravel()[allowed_idx])
    rankB.ravel()[allowed_idx] = pct(mos["B"].ravel()[allowed_idx])
    cover_norm = np.zeros(shape, np.float32)
    cover_norm.ravel()[allowed_idx] = cover_norm_over(store, allowed_idx)
    field = h66a_field(rankA.ravel()[allowed_idx], rankB.ravel()[allowed_idx],
                       cover_norm.ravel()[allowed_idx], allowed_idx, shape, th)
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)
    gate_mask = (field > -1.0) & allowed
    # BUDGET DEFECT, DISCLOSED (IR-H66-013): the frozen field is positive only inside the A-only
    # gate, and the exact-novelty mask (the lane's own uniqueness rule) leaves just
    # gate_mask.sum() gate cells.  The template budget BUDGET cannot be filled from a gated field:
    # placing over `allowed` would emit -1 (non-gate) cells and falsify "every emitted cell is an
    # A-only candidate".  The budget is therefore a CAP: the emission is the gate support, placed by
    # the same metric-aware selector at 3 px separation.  The holdout arm measured the same field at
    # the template budget WITHOUT the registry-novelty constraint (the holdout cannot model other
    # teams' submissions); the shipped file is smaller, and the run card says so.
    n_gate = int(gate_mask.sum())
    n_target = min(BUDGET, n_gate)
    log(f"H66-A gate cells (A-confident & B-abstain, exact-novel): {n_gate}; "
        f"template budget {BUDGET} -> placement target {n_target}")

    # ---- lane gate on the SURFACE, before placement (the brief's order)
    surface_field = np.where(allowed, (field - field[allowed].min()) /
                             max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    lane_surface = None
    if REUSE_GATES:
        prev_path = EVID / "h66cover_lane_surface.json"
        if prev_path.exists():
            prev = json.loads(prev_path.read_text())
            want = hashlib.sha256(surface_field.astype("<f4").tobytes()).hexdigest()
            if prev.get("candidate_decoded_sha256") == want:
                lane_surface = prev
                log("reusing the surface lane receipt (decoded sha verified against the field)")
    if lane_surface is None:
        lane_surface = gates.lane_report(surface_field, allowed, priors_all,
                                         sample=ROOT / "data/sample_submission.tif",
                                         phase="surface", log=log)
        write_h66cover("lane_surface", lane_surface)
    log(f"surface lane: literal {lane_surface['literal']['verdict']} "
        f"policy {lane_surface['policy']['verdict']} "
        f"(probes {lane_surface['policy']['universal_coverage_probes']})")

    # ---- metric-aware placement over the GATE SUPPORT + the per-raster 70% cap
    disk = gates._disk(NOVELTY_RADIUS_PX)
    cap = int(np.floor(gates.NEAR_LIMIT * n_target))
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
        idx = np.flatnonzero(gate_mask.ravel())     # the emission domain is the A-only gate
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
            flat_i = int(idx[pos])
            y, x = divmod(flat_i, shape[1])
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

    em0 = nodes.spacing_select(field, gate_mask, n_target, min_px=3.0)
    counts0 = _near_counts(em0)
    offenders = {nm: c for nm, c in counts0.items() if c > cap}
    it_log = [dict(round=0, placed=int(em0.sum()), gate_cells=n_gate, target=n_target,
                   offenders=len(offenders), unconstrained=True)]
    log(f"novelty (2) unconstrained over the gate: placed {int(em0.sum())} of {n_target} "
        f"(gate cells {n_gate}); rasters over cap {cap}: {len(offenders)}")
    em = em0
    halos_all = {}
    lane_rule_violated = False
    for rnd in range(1, MAX_NOVELTY_ITER + 1):
        if not offenders:
            break
        for nm in offenders:
            if nm not in halos_all:
                halos_all[nm] = ndi.binary_dilation(_sup2d(nm), structure=disk)
        em, taken = _constrained_select(halos_all)
        if taken < n_target:
            # H64 precedent: keep the unconstrained emission, carry the DUPLICATE label, let the
            # dots lane gate (the authority) read the final raster.  The file must still be built.
            log(f"WARNING: constrained placement placed {taken} of {n_target}; keeping the "
                f"unconstrained emission and letting the dots lane gate decide")
            em = em0
            lane_rule_violated = True
            break
        counts = _near_counts(em)
        offenders = {nm: c for nm, c in counts.items() if c > cap and nm not in halos_all}
        it_log.append(dict(round=rnd, placed=taken, constrained_rasters=len(halos_all),
                           new_offenders=len(offenders)))
        log(f"novelty (2) round {rnd}: placed {taken}, constrained {len(halos_all)} rasters, "
            f"new offenders {len(offenders)}")
    final_counts = _near_counts(em)
    worst = max(final_counts.items(), key=lambda kv: kv[1])
    n_em = int(em.sum())
    # The lane rule is SHARE-based: "more than 70% of the candidate's OWN dots within 3 px of one
    # raster's dots".  With a sparse gate the placed count (n_em) is below the target, so the cap
    # that matters is 0.70 x n_em, not 0.70 x n_target.  A violation is logged as a duplicate and
    # the build continues: the dots lane gate (the authority) reads the final raster, and the
    # frozen protocol's resolution is to carry the DUPLICATE label, not to shrink the emission
    # (H64 precedent).  IR-H66-014.
    lane_rule_violated = bool(worst[1] > gates.NEAR_LIMIT * n_em)
    novelty.update(mode="exact_and_lane",
                   per_raster_rule=("greedy placement over the A-only gate support at 3 px; the "
                                    "lane rule is share-based: no informative raster may hold more "
                                    f"than {gates.NEAR_LIMIT} of the candidate's own dots within "
                                    f"{NOVELTY_RADIUS_PX:g} px"),
                   near_limit=gates.NEAR_LIMIT, cap_dots=cap, cap_is_share_of_target=True,
                   iterations=it_log,
                   constrained_rasters=sorted(halos_all),
                   worst_raster_near_dots=dict(name=worst[0], count=worst[1],
                                               share=round(worst[1] / max(1, n_em), 6),
                                               lane_share_limit=gates.NEAR_LIMIT),
                   allowed_final=int(allowed.sum()), min_px=NOVELTY_MIN_PX,
                   lane_rule_violated=lane_rule_violated,
                   budget_note=(f"the frozen gate field is positive on {n_gate} exact-novel cells; "
                                f"the template budget {BUDGET} is a cap, not a target; the shipped "
                                f"emission is {n_em} cells"))
    write_h66cover("novelty", novelty)

    emission = em
    n_dots = int(emission.sum())
    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")
    if int((emission & ~gate_mask).sum()):
        raise SystemExit("emitted cell outside the A-only gate")

    # ---- not-the-union check on the shipped emission
    a_em = nodes.spacing_select(np.where(allowed, rankA, -1.0).astype(np.float32),
                                allowed, n_dots, min_px=3.0)
    b_em = nodes.spacing_select(np.where(allowed, rankB, -1.0).astype(np.float32),
                                allowed, n_dots, min_px=3.0)
    u_em = nodes.spacing_select(union_field, allowed, n_dots, min_px=3.0)
    d = emission
    not_union = dict(
        cells_differing_from_view_A=int((d != a_em).sum()),
        cells_differing_from_view_B=int((d != b_em).sum()),
        cells_differing_from_union_max=int((d != u_em).sum()),
        dots_shared_with_view_A=int((d & a_em).sum()),
        dots_shared_with_view_B=int((d & b_em).sum()),
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(field[allowed]),
                                                     rankdata(union_field[allowed]))[0, 1]),
        emitted_cells_inside_a_only_gate=int((d & gate_mask).sum()),
        gate_cells_total=int(gate_mask.sum()),
        not_union_pass=bool((d != u_em).any() and (d != a_em).any() and (d != b_em).any()
                            and not np.array_equal(d, u_em)),
        verdict="the emission is not max(A,B), not either single view, and not their union; every "
                "emitted cell lies inside the A-only (A-confident, B-abstaining) gate")
    write_h66cover("not_union", not_union)

    # ---- write the artefact (fail-closed writer; refuses NaN / out-of-range / bad grid)
    stem = f"gems52-h66-covergate-cotrain-{n_dots}px"
    sub_name = f"{stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    note = ("H66 co-training disagreement, cover-gated A-only (buried-beneath-cover) arm; "
            "3px dots; >200m off catalogue; research only, not slot-approved")
    assert len(note) <= 140, len(note)
    SUBM.mkdir(parents=True, exist_ok=True)
    path = SUBM / f"{stem}.tif"
    receipt = submission_writer.write_submission(
        path, pred, ROOT / "data/sample_submission.tif", sub_finite,
        note=note[:140], name=sub_name[:140],
        metadata=dict(round="H66cover", preregistration=sha(ROOT / reg["hypothesis_document"]),
                      budget=BUDGET, placed=n_dots, min_separation_px=3.0,
                      field="cover-gated A-only disagreement: (rankA-rankB)*log1p(cover) inside "
                            "rankA>=0.95 & 0.35<=rankB<=0.65",
                      views=dict(A=va_names(store), B=vb_names(store)),
                      catalogue_exclusion_m=th["catalogue_exclusion_m"]))
    fmt = receipt["validator"]
    log(f"wrote {path} sha256 {receipt['sha256']} bytes {receipt['bytes']} dots {n_dots}")

    # publish the download copies (canonical + short alias + single-TIFF ZIPs)
    DOWN.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(path, DOWN / path.name)
    shutil.copyfile(path.with_suffix(".zip"), DOWN / path.with_suffix(".zip").name)
    shutil.copyfile(path, DOWN / "h66cover-candidate.tif")
    shutil.copyfile(path.with_suffix(".zip"), DOWN / "h66cover-candidate.zip")
    # the scheduled feed rebuilds docs/data/submission.json from LATEST.txt + this receipt
    ev_receipt = json.loads(path.with_suffix(".json").read_text())
    ev_receipt.update(round="H66cover", stem=stem, short_tif="h66cover-candidate.tif",
                      short_zip="h66cover-candidate.zip", nonzero_px=n_dots,
                      submission_note=note[:140])
    (EVID / f"submission_{stem}.json").write_text(json.dumps(ev_receipt, indent=2) + "\n")
    (ROOT / "submission/LATEST.txt").write_text(path.name + "\n")

    # ---- final lane gate on the DOTS
    lane_dots = gates.lane_report(pred, eligible, priors_all,
                                  sample=ROOT / "data/sample_submission.tif",
                                  phase="dots", log=log)
    write_h66cover("lane_dots", lane_dots)
    log(f"dots lane: literal {lane_dots['literal']['verdict']} "
        f"policy {lane_dots['policy']['verdict']}")

    uniq = gates.uniqueness_report(pred, [p for p in priors_all if p != path], top=None)
    uniq_inf = gates.uniqueness_report(pred, [p for p in informative if p != path], top=None)
    write_h66cover("uniqueness", dict(tier1_all_priors=dict(
        canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
        identical_to_any_prior=any(r.get("identical") for r in uniq.get("per_prior", [])),
        equals_literal_prior_union=uniq.get("equals_literal_prior_union"),
        novel_fraction=uniq.get("novel_fraction"), n_priors=uniq.get("n_priors_checked")),
        tier2_informative_priors=dict(
        canonical_pattern_unique=uniq_inf.get("canonical_pattern_unique"),
        novel_fraction=uniq_inf.get("novel_fraction"),
        equals_literal_prior_union=uniq_inf.get("equals_literal_prior_union"),
        n_priors=uniq_inf.get("n_priors_checked"))))

    # ---- geological reasoning for every emitted cell (all are A-only candidates)
    ys, xs = np.nonzero(emission)
    CTX = ("raw_band_15", "raw_band_19", "A_gravity_grad_3", "X_rad_ThK_rank", "X_rad_K_rank",
           "X_mag_TMI_up150_grad3", "raw_band_13", "raw_band_17", "raw_band_04", "raw_band_16")
    ctx_rows = store.gather(ys * shape[1] + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h66-a-only-reasoning.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "distance_to_mapped_trace_m",
                    "view_A_operating_rank", "view_B_operating_rank", "disagreement_rank_diff",
                    "cover_norm_weight", "strict_A_only", "cover_depth_to_base_m", "dem_slope",
                    "gravity_grad_sigma3", "isostatic_grav_anom", "near_surface_conductivity",
                    "rad_ThK_rank", "rad_K_rank", "tmi_up150_grad3", "strain_second_invariant",
                    "earthquake_density", "geological_hypothesis", "named_non_fault_mimic",
                    "falsifier", "evidence_class"])
        for i, (y, x) in enumerate(zip(ys, xs)):
            w.writerow([
                int(y), int(x), 243350.0 + 100.0 * (x + 0.5), 4508550.0 - 100.0 * (y + 0.5),
                round(float(cat_dist[y, x]), 1),
                round(float(rankA[y, x]), 6), round(float(rankB[y, x]), 6),
                round(float(rankA[y, x] - rankB[y, x]), 6),
                round(float(cover_norm[y, x]), 6), 1,
                round(float(ctx["raw_band_15"][i]), 1), round(float(ctx["raw_band_19"][i]), 4),
                round(float(ctx["A_gravity_grad_3"][i]), 6),
                round(float(ctx["raw_band_13"][i]), 4), round(float(ctx["raw_band_17"][i]), 4),
                round(float(ctx["X_rad_ThK_rank"][i]), 4), round(float(ctx["X_rad_K_rank"][i]), 4),
                round(float(ctx["X_mag_TMI_up150_grad3"][i]), 6),
                round(float(ctx["raw_band_04"][i]), 4), round(float(ctx["raw_band_16"][i]), 4),
                "Buried or cover-hidden fault (the brief's A-only reading): a deep potential-field "
                "fabric step (upward-continued TMI and isostatic gravity gradient) beneath thick "
                "sedimentary cover, with no DEM scarp and no radiometric lineament, i.e. structure "
                "that does not reach the surface and so is missing from a surface-mapped catalogue. "
                "HYPOTHESIS, not verified geology.",
                "Non-fault basin-fill density boundary or volcanic lithologic contact; buried "
                "palaeo-channel or alluvial-fan margin; road/erosion lineament (the brief's B-only "
                "artifact reading, excluded here by the B-abstain gate but not eliminated); "
                "upward-continued flight-line artefact of the airborne survey.",
                "Independent evidence of offset at this location: a displaced contact or marker bed, "
                "deflected or offset drainage, a facies termination, a published structural "
                "interpretation, or field observation. None is claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")

    # ---- PROJECTION (never a score)
    foren = json.loads((EVID / "h61_forensics.json").read_text())
    G_lo = foren["G_identification"]["masked"]["G_lower_bound"]
    G_hi = foren["G_identification"]["masked"]["G_upper_bound"]
    hold = json.loads((EVID / "h66cover_holdout.json").read_text())
    hd = hold["pooled"]["scores"][H66A_ARM]
    S = float(n_dots)
    proj = {}
    for tag, G in (("G_lower", G_lo), ("G_upper", G_hi)):
        be = CHAMPION_REF[1] * (metric.ALPHA * S + metric.BETA * G) / S
        proj[tag] = dict(G_px=G, emitted_px=S,
                         breakeven_credit_density_to_match_champion=be,
                         dti_if_density_equals_holdout_arm=(hd["tpw"] / max(1.0, S)) * S /
                         (metric.ALPHA * S + metric.BETA * G))
    proj.update(
        evidence_class="PROJECTION FROM OWNER-REPORTED SCORES AND A LOCAL SIMULATOR; NOT A SCORE, "
                       "NOT ORGANIZER-CONFIRMED, NOT A LEADERBOARD FORECAST",
        formula="DTI = T/(0.2*(T+S-M)+0.8*(|G|-T)) with M~T for sparse dots => DTI = d*S/(0.2S+0.8|G|)",
        holdout_arm_density=hd["tpw"] / max(1.0, S),
        holdout_arm_density_caveat=("HOLDOUT-DTI measures recovery of withheld *catalogue* components "
                                   "in a simulator that measured Spearman -0.10 against the "
                                   "owner-reported board in round R4; it is not a density estimate for "
                                   "hidden off-catalogue expert-drawn truth."),
        champion=dict(id=CHAMPION_REF[0], reported=CHAMPION_REF[1],
                      evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"))
    write_h66cover("projection", proj)

    # ---- verdict (frozen rule, knowledge/43 section 6)
    fmt_ok = bool(fmt.get("ok"))
    lane_policy_ok = bool(lane_dots["policy"]["verdict"] == "PASS")
    lane_literal_ok = bool(lane_dots["literal"]["verdict"] == "PASS")
    uniq_ok = bool(uniq.get("canonical_pattern_unique")
                   and not any(r.get("identical") for r in uniq.get("per_prior", []))
                   and not uniq.get("equals_literal_prior_union")
                   and (uniq_inf.get("novel_fraction") or 0.0) >= 1.0)
    paired = hold["paired_h66a_minus_single_B"]
    beats = bool(paired["delta"] > 0 and paired["ci95"][0] > 0)
    promote = bool(fmt_ok and lane_policy_ok and uniq_ok and not_union["not_union_pass"] and beats)
    verdict = ("ELIGIBLE FOR SELECTOR, NOT PROMOTED (no slot used; holdout is not board evidence)"
               if promote else
               f"NEGATIVE, research-only. DOWNLOAD {'YES' if (fmt_ok and uniq_ok) else 'NO'} "
               f"(format-valid and unique on decoded pixels); SUBMIT NO "
               f"(gates: format={fmt_ok} lane_policy={lane_policy_ok} unique={uniq_ok} "
               f"not_union={not_union['not_union_pass']} beats_single_B={beats}). "
               "No certified leaderboard gain.")

    ex = json.loads((EVID / "h66cover_pseudo_exchange.json").read_text())
    card = dict(
        round="H66cover", generated_utc=now(), lane=reg["lane"],
        hypothesis=("Where the potential-field/subsurface view is confident and the surface view "
                    "abstains, the fault may be buried beneath cover; gating the disagreement "
                    "signal by modelled cover thickness concentrates the emission on thick-cover "
                    "A-only segments, the stratum a surface-mapped catalogue structurally cannot "
                    "contain."),
        mechanism=("Blum-Mitchell two-view co-training, H61 views/learner/seed reused unchanged; "
                   "one confident-to-abstaining whole-segment pseudo-label round after a measured "
                   "independence screen; the shipped field is (rankA - rankB) * log1p(cover) "
                   "inside rankA >= 0.95 and 0.35 <= rankB <= 0.65, placed by nodes.spacing_select "
                   "at 3 px separation."),
        named_non_fault_process=("basin-fill density boundary or volcanic lithologic contact; "
                                 "buried palaeo-channel or alluvial-fan margin; road/erosion "
                                 "lineament; upward-continued flight-line artefact"),
        independence=dict(max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
                          threshold=th["independence_abandon_max_abs_rho"],
                          allow_exchange=ex.get("allowed_exchange"),
                          blocks=(ex.get("independence_pre") or {}).get("n_blocks"),
                          note="spatial-block OOF errors on held-out catalogue-zero negatives; "
                               "proxies, not verified absence"),
        canary=dict(max_raw_auc=json.loads((EVID / "h66cover_canary.json").read_text())["max_alarm_across_folds"],
                    alarm=th["canary_auc_alarm"],
                    any_alarm=json.loads((EVID / "h66cover_canary.json").read_text())["any_alarm"]),
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI", evaluator=hold["pooled"]["evaluator_version"],
            withheld_positive_pixels=hold["pooled"]["scores"][H66A_ARM]["withheld_positive_pixels"],
            candidate=hd["dti"], ci95=hd["ci95"],
            single_B_baseline=hold["pooled"]["scores"]["single_B"],
            controls={k: dict(dti=v["dti"], ci95=v["ci95"])
                      for k, v in hold["pooled"]["scores"].items() if k != H66A_ARM},
            paired_h66a_minus_single_B=paired,
            all_arms_filled_budget=hold["all_arms_filled"],
            budget_per_arm_per_fold=hold["budget_per_arm_per_fold"],
            pseudo_label_pixels=ex.get("total_pseudo_pixels"),
            frozen_comparison_candidate="disagreement_post",
            simulator_validity=("R4 measured Spearman -0.10 between this simulator and the "
                                "owner-reported board; it screens procedures and does not promote.")),
        correlation_overlap_vs_registry=dict(
            lane_surface_literal=lane_surface["literal"]["verdict"],
            lane_surface_policy=lane_surface["policy"]["verdict"],
            lane_dots_literal=lane_dots["literal"]["verdict"],
            lane_dots_policy=lane_dots["policy"]["verdict"],
            lane_dots_policy_max_near=lane_dots["policy"].get("max_near_3px_fraction"),
            lane_dots_policy_max_near_source=lane_dots["policy"].get("max_near_source"),
            lane_surface_policy_max_spearman=lane_surface["policy"].get("max_spearman"),
            informative_priors=lane_dots["policy"]["informative_priors"],
            universal_coverage_probes=lane_dots["policy"]["universal_coverage_probes"],
            uniqueness_canonical_pattern_unique=uniq.get("canonical_pattern_unique"),
            novel_fraction_all_priors=uniq.get("novel_fraction"),
            novel_fraction_informative=uniq_inf.get("novel_fraction"),
            equals_literal_prior_union=uniq.get("equals_literal_prior_union")),
        not_the_union=not_union,
        projection=proj,
        raster=dict(file=path.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
                    zip_sha256=receipt["zip_sha256"], download=f"docs/downloads/{path.name}",
                    short_alias="docs/downloads/h66cover-candidate.tif"),
        validator=dict(ok=fmt.get("ok"), problems=fmt.get("problems"),
                       nan_inside_footprint=fmt.get("nan_px_in_footprint", fmt.get("nan_count")),
                       value_range=[fmt.get("min"), fmt.get("max")],
                       crs=fmt.get("crs"), shape=fmt.get("shape"), transform=fmt.get("transform")),
        submission_name=sub_name, note=note, note_chars=len(note),
        counts=dict(budget_template=BUDGET, budget_target=n_target, placed=n_dots,
                    gate_cells=int(gate_mask.sum()),
                    prior_rasters=len(priors_all), informative_rasters=len(informative),
                    probe_rasters=len(probes),
                    budget_note=(f"the frozen gate field is positive on {int(gate_mask.sum())} "
                                 f"exact-novel cells; the template budget {BUDGET} is a cap; "
                                 f"the shipped emission is {n_dots} cells (IR-H66-013)")),
        champion_reference=dict(name=CHAMPION_REF[0], reported_score=CHAMPION_REF[1],
                                evidence_class="OWNER-REPORTED, NOT ORGANIZER-CONFIRMED"),
        submission_slots_used=0,
        verdict=verdict,
        promote=promote)
    write_h66cover("run_card", card)
    log(f"verdict: {verdict}")
    return card


def va_names(store):
    return store.manifest["view_A_with_external"]


def vb_names(store):
    return store.manifest["view_B_with_external"]


# ------------------------------------------------------------------ main
def main(argv) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    if stage not in ("canary", "fit", "exchange", "holdout", "build", "all"):
        raise SystemExit(f"unknown stage {stage!r}")
    reg = check_prereg()
    redirect()
    if stage in ("canary", "all"):
        log("=== H66 stage canary (shared H61 stage, unchanged) ===")
        base.stage_canary()
    if stage in ("fit", "all"):
        log("=== H66 stage fit (shared H61 stage, unchanged) ===")
        base.stage_fit()
    if stage in ("exchange", "all"):
        log("=== H66 stage exchange (independence screen + one pseudo-label round) ===")
        base.stage_exchange()
    if stage in ("holdout", "all"):
        log("=== H66 stage holdout (seven arms) ===")
        stage_holdout66(reg)
    if stage in ("build", "all"):
        log("=== H66 stage build ===")
        stage_build66(reg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
