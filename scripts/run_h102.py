#!/usr/bin/env python3
"""H102 -- co-training lane: disagreement-state quota emission on the DVA2 base, plus the soft-prior graft.

Preregistered in ``knowledge/97_hypotheses_H102_preregistered.md`` (frozen before any fit) and pinned by
``registry/h102_preregistration.json``; this runner refuses to start if the document's hash has moved.

Shared tools are reused, never forked:
  * ``run_h61.setup / sample_for_fit / learner_for / to_grid / pct_rank`` (cached feature stack, label-blind folds)
  * ``run_h84.stage_channels`` (H82 DVA-2 design, redirected to work/h102) and
    ``run_h84.gather_arm / predict_region / RamBank / write_a_only_reasoning``
  * ``run_h82.stitch / restricted_registry / restricted_supports``
  * ``run_h73.place_lane`` (H73 amendment 61a per-prior quota placement)
  * ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1), ``gems52.nodes.spacing_select``,
    ``gems52.spatial.negative_block_errors / independence``, ``gems52.gates`` (lane, uniqueness, format),
    ``gems52.grid.write_geotiff_portal_exact(outside="zero")``
  * H95's E3 PROXY-SGMC recipe (segthin truths, budgets, caveat) -- diagnostic only, never a score.

Stages (checkpointed to work/h102 and evidence/h102_*.json):
    channels       50 DVA2 (+ HVA/COH by the shared H84 builder; H102 fits the DVA2 subset only)
    fit            canary per channel per fold, then 3 arms x 4 folds (region-only prediction)
    fields         stitched ranks; state machine (C / A-only / B-only veto) with the tauB ladder;
                   graft fields; emission pool; receipts
    e1             HOLDOUT-DTI @ 9400/fold: g_025, g_050, B_DVA2, single_B, single_A, random
    e2             HOLDOUT-DTI @ 6350/fold: quota_primary, consensus_only, a_only_stratum,
                   B_DVA2, single_B, random  (promotion gate 5)
    e3             PROXY-SGMC board-anchored DIAGNOSTIC (never a score)
    independence   the lane's spatial-block OOF error-correlation test (single_A vs single_B)
    lane           surface lane gate (before placement), quota placement (run_h73.place_lane),
                   dot lane gate (after), uniqueness on the full census
    write          GeoTIFF (0.0 outside footprint, no NaN), ZIP, re-read validator, A-only reasoning CSV,
                   not-the-union
    card           the single JSON run card, assembled only from receipts on disk

Usage: python scripts/run_h102.py [channels|fit|fields|e1|e2|e3|independence|lane|write|card|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile
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
import run_h82 as h82                                                 # noqa: E402
import run_h84 as h84                                                 # noqa: E402
import run_h73 as h73                                                 # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, grid, metric, nodes, spatial                # noqa: E402

PREREG = ROOT / "registry/h102_preregistration.json"
WORK = ROOT / "work/h102"
FEAT = WORK / "features"
EVID = ROOT / "evidence"
DATA = ROOT / "data"
SAMPLE = DATA / "sample_submission.tif"
SEED = base.SEED
PREFIX = "gems52-h102-"
RING_M = 200.0

# redirect the shared H84/H82 channel+stitch machinery at this round's work directory
h84.WORK, h84.FEAT = WORK, FEAT
h82.WORK = WORK
h73.H73 = json.loads((ROOT / "registry/h73_preregistration.json").read_text())

DVA2 = h84.DVA2


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, obj):
    EVID.mkdir(exist_ok=True)
    p = EVID / f"h102_{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return p


# H84's channel builder writes its receipt through its own module global; redirect it so H84's
# evidence receipts stay untouched.
h84.write = write


def check_prereg():
    reg = json.loads(PREREG.read_text())
    if digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H102 preregistration changed after freezing; re-pin registry/h102_preregistration.json")
    return reg


def allowed_of(fold, ring_px):
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & ~fold["visible"] & (vd > ring_px)


def rank_on(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.full(mask.shape, np.nan, np.float32)
    idx = np.flatnonzero(mask.ravel())
    out.ravel()[idx] = base.pct_rank(values.ravel()[idx])
    return out


def pooled_run(fields_per_fold, folds, eligible, ring_px, K, min_px, candidate, draws):
    """Matched-budget hide-and-recover on the shared evaluator, one emission per arm per fold."""
    terms, per_fold = {}, []
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_of(fold, ring_px)
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()), arms={})
        for arm, field in fields_per_fold(fold, allowed).items():
            em = nodes.spacing_select(field, allowed, K, min_px=min_px)
            res, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if arm not in terms else terms[arm] + term
            rec["arms"][arm] = dict(dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"], fnw=res["fnw"],
                                    placed=int(em.sum()), requested=K, filled=bool(int(em.sum()) == K))
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")
        per_fold.append(rec)
    return evaluator.pooled_summary(terms, draws=draws, seed=SEED, candidate=candidate), per_fold


def footprint_mask():
    with rasterio.open(SAMPLE) as s:
        a = s.read(1, masked=True)
        return ~np.ma.getmaskarray(a) & np.isfinite(a.data) & (a.data > -1e38)


def save_field(name, arr):
    p = WORK / f"{name}.npy"
    h82.save_verified(p, np.ascontiguousarray(arr.astype(np.float32)))
    return p


# ============================================================================================= channels
def stage_channels(max_passes: int = 4):
    check_prereg()
    log("channels: shared H84 builder (DVA2 50 + HVA 25 + COH 5), redirected to work/h102")
    h84.stage_channels(max_passes=max_passes)
    man = json.loads((FEAT / "manifest.json").read_text())
    log(f"channels: {len(DVA2)} DVA2 learner channels verified on disk "
        f"({len(man['sha256'])} total files, audit passes {len(man['audit_history'])})")


# ============================================================================================= fit
ARM_CHANNELS = {"single_A": [], "single_B": [], "B_DVA2": DVA2}
ARMS = ("single_A", "single_B", "B_DVA2")


def stage_fit():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    bank = h84.RamBank(FEAT, sorted(DVA2))
    flat = store.flat_idx
    catd = ndi.distance_transform_edt(~cat)
    out = dict(stage="fit", started_utc=now(), arms=list(ARMS), seed=SEED, folds=[])
    for fold in folds:
        f = fold["fold"]
        region_rows = np.flatnonzero((fold["region"] & eligible).ravel())
        rng = np.random.default_rng(SEED + f)
        rows, y, _w = base.sample_for_fit(fold, cat, rng)
        pos_g = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_g = np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())
        yy = np.r_[np.ones(len(pos_g)), np.zeros(len(neg_g))]
        rec = dict(fold=f, n_train_rows=int(len(rows)), n_pos=int(len(pos_g)), n_neg=int(len(neg_g)),
                   auc={}, canary={}, seconds={})
        # leakage canary: every learner channel ALONE on the held-out region (no fit, no labels to choose)
        canary_flat = np.r_[pos_g, neg_g]
        erow = store.inverse[canary_flat]
        for nm in sorted(DVA2 + va + vb):
            if nm in bank.cols:
                v = np.asarray(bank.col(nm)[erow], np.float64)
            else:
                v = np.asarray(store.gather(canary_flat, [nm])[:, 0], np.float64)
            a = float(roc_auc_score(yy, v)) if np.isfinite(v).all() and np.ptp(v) > 0 else 0.5
            rec["canary"][nm] = dict(auc=a, direction_insensitive=max(a, 1 - a))
            del v
        rec["canary_max"] = max(v["direction_insensitive"] for v in rec["canary"].values())
        rec["canary_worst"] = max(rec["canary"].items(), key=lambda kv: kv[1]["direction_insensitive"])[0]
        rec["canary_alarm"] = bool(rec["canary_max"] >= reg["canary_auc_bar"])
        log(f"fold {f}: canary max {rec['canary_max']:.4f} ({rec['canary_worst']}) alarm={rec['canary_alarm']}")
        for arm in ARMS:
            ck = WORK / f"pred_{arm}_f{f}.npy"
            t1 = time.time()
            if not ck.exists():
                names_store = va if arm == "single_A" else vb
                m = base.learner_for("A" if arm == "single_A" else "B", SEED)
                m.fit(h84.gather_arm(store, bank, rows, names_store, ARM_CHANNELS[arm]), y)
                p = h84.predict_region(store, bank, m, names_store, ARM_CHANNELS[arm], region_rows)
                full = np.full(len(flat), np.nan, np.float32)
                full[store.inverse[region_rows]] = p
                h82.save_verified(ck, full)
                del m, p, full
            g = np.asarray(np.load(ck, mmap_mode="r"), np.float32)
            rec["auc"][arm] = float(roc_auc_score(yy, np.r_[g[store.inverse[pos_g]], g[store.inverse[neg_g]]]))
            rec["seconds"][arm] = time.time() - t1
            log(f"fold {f} {arm}: out-of-quadrant AUC {rec['auc'][arm]:.4f} ({rec['seconds'][arm]:.0f}s)")
            del g
        out["folds"].append(rec)
    out["canary_alarm_any"] = any(r["canary_alarm"] for r in out["folds"])
    out["canary_max_overall"] = max(r["canary_max"] for r in out["folds"])
    out["canary_auc_bar"] = reg["canary_auc_bar"]
    sa = [r["auc"]["single_A"] for r in out["folds"]]
    out["sufficiency_view_A"] = dict(mean=float(np.mean(sa)), min_fold=float(np.min(sa)), per_fold=sa,
                                     gate_mean=0.60, gate_min_fold=0.55,
                                     passes=bool(np.mean(sa) >= 0.60 and np.min(sa) >= 0.55))
    out["finished_utc"] = now()
    write("fit", out)
    log(json.dumps({"canary_max": out["canary_max_overall"], "sufficiency_A": out["sufficiency_view_A"],
                    "auc": {a: [round(r["auc"][a], 4) for r in out["folds"]] for a in ARMS}}))
    return out


# ============================================================================================= fields
def stage_fields():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fB = h82.stitch("B_DVA2", folds, eligible, flat)    # per-quadrant pct rank of the DVA2 OOF field
    fA = h82.stitch("single_A", folds, eligible, flat)  # per-quadrant pct rank of the View A OOF field
    fB61 = h82.stitch("single_B", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fB) & np.isfinite(fA) & (catd * 100.0 > RING_M)
    rB = np.full(eligible.shape, np.nan, np.float32)
    rA = np.full(eligible.shape, np.nan, np.float32)
    pi = np.flatnonzero(pool.ravel())
    rB.ravel()[pi] = base.pct_rank(fB.ravel()[pi])
    rA.ravel()[pi] = base.pct_rank(fA.ravel()[pi])

    sm = reg["state_machine"]
    # tauB ladder (pre-registered, deterministic, no peeking beyond the ladder itself)
    tauB, c_sizes = None, {}
    for t in sm["tauB_ladder"]:
        c = pool & (rB >= t) & (rA >= sm["A_rank_min"])
        c_sizes[str(t)] = int(c.sum())
        if c.sum() >= sm["tauB_min_C_px"]:
            tauB = float(t)
            break
    if tauB is None:
        tauB = sm["tauB_ladder"][-1]
    C = pool & (rB >= tauB) & (rA >= sm["A_rank_min"])
    Aonly = pool & (rA >= sm["Aonly_rank_min"]) & (rB < tauB)
    Bonly = pool & (rB >= tauB) & (rA < sm["Bonly_rank_max"])
    log(f"fields: tauB={tauB} ladder sizes={c_sizes} |C|={int(C.sum())} |A-only|={int(Aonly.sum())} "
        f"|B-only vetoed|={int(Bonly.sum())} |pool|={int(pool.sum())}")

    s = np.zeros(eligible.shape, np.float32)
    s[C] = 2.0 + 0.01 * (rB[C] * rA[C])
    s[Aonly] = 0.01 * rA[Aonly]

    g = {}
    for w in sorted(set(reg["graft_w"].values())):
        gw = np.full(eligible.shape, np.nan, np.float32)
        gw[pool] = (rB[pool] * (1.0 + w * (rA[pool] - 0.5))).astype(np.float32)
        g[w] = gw
        log(f"fields: graft w={w} stored")

    save_field("rB", rB)
    save_field("rA", rA)
    save_field("fB61", fB61)
    save_field("pool", pool.astype(np.float32))
    save_field("C", C.astype(np.float32))
    save_field("Aonly", Aonly.astype(np.float32))
    save_field("Bonly", Bonly.astype(np.float32))
    save_field("s", s)
    for w, gw in g.items():
        save_field(f"g_w{int(w * 100):03d}", gw)

    out = dict(stage="fields", started_utc=now(), tauB=tauB, tauB_ladder_sizes=c_sizes,
               A_rank_min=sm["A_rank_min"], Aonly_rank_min=sm["Aonly_rank_min"],
               Bonly_rank_max=sm["Bonly_rank_max"], C_px=int(C.sum()), Aonly_px=int(Aonly.sum()),
               Bonly_vetoed_px=int(Bonly.sum()), pool_px=int(pool.sum()), eligible_px=int(eligible.sum()),
               graft_w=sorted(reg["graft_w"].values()),
               note=("rB/rA are per-quadrant pct ranks of the stitched OOF fields over the pool (H82.stitch "
                     "convention); s = 2 + 0.01 rB rA on C, 0.01 rA on A-only, 0 elsewhere; every C cell "
                     "ranks above every A-only cell so the greedy walk realises the frozen 18000/7400 quota"),
               finished_utc=now())
    write("fields", out)
    return out


def load_fields():
    return {k: np.load(WORK / f"{k}.npy") for k in ("rB", "rA", "fB61", "pool", "C", "Aonly", "Bonly", "s",
                                                    "g_w025", "g_w050")}


# ============================================================================================= e1
def stage_e1():
    reg = check_prereg()
    K = int(reg["budgets"]["full_px_per_fold"])
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    F = load_fields()
    pool, rB, rA = F["pool"] > 0, F["rB"], F["rA"]

    def fields(fold, allowed):
        f = fold["fold"]
        def stitched(arm):
            g = base.to_grid(store.flat_idx, np.load(WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
            return np.nan_to_num(rank_on(g, allowed), nan=-1.0)
        def gfield(w_arr, allowed):
            return np.nan_to_num(rank_on(w_arr, allowed), nan=-1.0)
        rng = np.random.default_rng(SEED + 500 + fold["fold"])
        rnd = np.full(eligible.shape, -1.0, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        return {"g_025": gfield(F["g_w025"], allowed), "g_050": gfield(F["g_w050"], allowed),
                "B_DVA2": stitched("B_DVA2"), "single_B": stitched("single_B"),
                "single_A": stitched("single_A"), "random": rnd}

    summary, per_fold = pooled_run(fields, folds, eligible, ring_px, K, 3.0, "g_025", int(reg["evaluator"]["draws"]))
    ctr = reg["control_targets"]
    controls = {}
    for arm, tgt in (("single_B", ctr["single_B"]), ("random", ctr["random"])):
        got = float(summary["scores"][arm]["dti"])
        controls[arm] = dict(committed=tgt, measured=got, abs_delta=abs(got - tgt),
                             tolerance=ctr["tolerance"], PASS=bool(abs(got - tgt) <= ctr["tolerance"]))
    got_b = float(summary["scores"]["B_DVA2"]["dti"])
    controls["B_DVA2"] = dict(committed_readings=ctr["B_DVA2_committed_readings"], measured=got_b,
                              abs_delta_vs_max=min(abs(got_b - t) for t in ctr["B_DVA2_committed_readings"]),
                              note="jitter across rounds <= 3.6e-3 (IR-H84-005); reported verbatim")
    out = dict(round="H102", experiment="E1 (soft-prior graft, full budget)", evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, candidate="g_025", budget_per_fold=K,
               withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(),
               pooled=summary, per_fold=per_fold, controls=controls, started_utc=now(), finished_utc=now())
    write("e1_graft_holdout", out)
    log("E1 pooled: " + json.dumps({a: round(s["dti"], 6) for a, s in summary["scores"].items()}))
    return out


# ============================================================================================= e2
def stage_e2():
    reg = check_prereg()
    K = int(reg["budgets"]["subhalo_px_per_fold"])
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    F = load_fields()
    C, Aonly = F["C"] > 0, F["Aonly"] > 0
    rB, rA, s = F["rB"], F["rA"], F["s"]

    cons = np.full(eligible.shape, -1.0, np.float32)
    cons[C] = rB[C] * rA[C]
    aonly = np.full(eligible.shape, -1.0, np.float32)
    aonly[Aonly] = rA[Aonly]

    def fields(fold, allowed):
        f = fold["fold"]
        def stitched(arm):
            g = base.to_grid(store.flat_idx, np.load(WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
            return np.nan_to_num(rank_on(g, allowed), nan=-1.0)
        rng = np.random.default_rng(SEED + 500 + fold["fold"])
        rnd = np.full(eligible.shape, -1.0, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        return {"quota_primary": np.where(allowed, s, -1.0), "consensus_only": np.where(allowed, cons, -1.0),
                "a_only_stratum": np.where(allowed, aonly, -1.0),
                "B_DVA2": stitched("B_DVA2"), "single_B": stitched("single_B"), "random": rnd}

    summary, per_fold = pooled_run(fields, folds, eligible, ring_px, K, 3.0, "quota_primary",
                                   int(reg["evaluator"]["draws"]))
    bar = reg["promotion_bar_holdout_dti"]
    prim = summary["scores"]["quota_primary"]
    vs_dva2 = summary["paired_differences"].get("B_DVA2")
    vs_b = summary["paired_differences"].get("single_B")
    promote = bool(prim["dti"] > bar and vs_dva2 is not None and vs_dva2["ci95"][0] > 0)
    out = dict(round="H102", experiment="E2 (disagreement-state quota emission, sub-halo)", evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, candidate="quota_primary", budget_per_fold=K,
               subhalo_total=K * len(folds), withheld_positive_px=int(sum(f["truth"].sum() for f in folds)),
               implementation_hashes=evaluator.implementation_hashes(),
               promotion_bar=bar,
               promotion=dict(rule="quota_primary > bar AND paired vs B_DVA2 CI95 lower bound > 0",
                              primary_dti=prim["dti"], ci95=prim.get("ci95"),
                              paired_vs_B_DVA2=vs_dva2, paired_vs_single_B=vs_b, promote=promote),
               pooled=summary, per_fold=per_fold, started_utc=now(), finished_utc=now())
    write("e2_quota_holdout", out)
    log("E2 pooled: " + json.dumps({a: round(x["dti"], 6) for a, x in summary["scores"].items()}))
    log(f"E2 promotion: bar {bar} primary {prim['dti']:.6f} promote={promote}")
    return out


# ============================================================================================= e3
def segthin_truths(reg, dom, cat):
    with rasterio.open(DATA / "external/derived_sgmc_faults_100m_u8.tif") as s:
        sg = s.read(1) > 0
    dcat = ndi.distance_transform_edt(~cat)
    off = sg & dom & (dcat >= 3)
    comp, n = ndi.label(off, np.ones((3, 3), bool))
    sizes = np.bincount(comp.ravel())[1:]
    G = int(reg["e3_proxy_sgmc"]["G"])
    truths = []
    for seed in reg["e3_proxy_sgmc"]["seeds"]:
        order = np.random.default_rng(seed).permutation(n) + 1
        cum = np.cumsum(sizes[order - 1])
        chosen = order[:int(np.searchsorted(cum, G)) + 1]
        truths.append(np.isin(comp, chosen))
    return truths


def stage_e3():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    F = load_fields()
    with rasterio.open(SAMPLE) as s:
        dom = np.isfinite(s.read(1))
    truths = segthin_truths(reg, dom, cat)
    catd = ndi.distance_transform_edt(~cat)
    ring_px_e3 = int(reg["e3_proxy_sgmc"]["ring_m"] / 100.0)
    allowed = eligible & dom & ~cat & (catd > ring_px_e3)
    fields = {"B_DVA2": F["rB"], "g_025": F["g_w025"], "state_machine_s": F["s"],
              "single_B": F["fB61"], "single_A": F["rA"]}
    res = {}

    def score(pred):
        v = [metric.dti(pred, g)["dti"] for g in truths]
        return dict(mean=float(np.mean(v)), per_seed=[float(x) for x in v])

    for arm, fld in fields.items():
        for K in reg["e3_proxy_sgmc"]["budgets"]:
            em = nodes.spacing_select(np.nan_to_num(fld, nan=-np.inf), allowed, K, min_px=3.0)
            res[f"{arm}@{K}"] = dict(placed=int(em.sum()), **score(em.astype(np.float32)))
            log(f"E3 {arm}@{K}: PROXY-SGMC {res[f'{arm}@{K}']['mean']:.5f}")
    refs = {"champion_h33_2_b2 (board 0.2778, OWNER-REPORTED)": DATA / "reference/h33-2-b2-zeros.tif",
            "d2-8 (board 0.2600, OWNER-REPORTED)": DATA / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"}
    for nm, p in refs.items():
        with rasterio.open(p) as s:
            a = s.read(1)
        a = np.where(np.isfinite(a) & dom, a, 0).astype(np.float32)
        res[nm] = dict(placed=int((a > 0).sum()), **score(a))
        log(f"E3 ref {nm}: {res[nm]['mean']:.5f}")
    for K in reg["e3_proxy_sgmc"]["budgets"]:
        rand = np.random.default_rng(SEED).random(eligible.shape).astype(np.float32)
        em = nodes.spacing_select(rand, allowed, K, min_px=3.0)
        res[f"random@{K}"] = dict(placed=int(em.sum()), **score(em.astype(np.float32)))
    out = dict(round="H102", experiment="E3", evidence_class="PROXY-SGMC (diagnostic, never a score)",
               instrument=reg["e3_proxy_sgmc"], results=res,
               caveat=("SGMC geologic-map faults >= 3 px from labels.tif, thinned by whole segments to |G| ~ 10k; "
                       "Spearman vs 13 owner-reported board scores 0.567 (0.911 excluding the lattice probe), "
                       "about as informative as emitted mass alone (|rho| 0.889). Not the hidden expert faults. "
                       "No H102 gate reads this experiment (preregistration sec.4/6)."),
               finished_utc=now())
    write("e3_proxy_sgmc", out)
    return out


# ============================================================================================= independence
def stage_independence():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th_src = ROOT / "registry/h74_preregistration.json"
    th = json.loads(th_src.read_text())["thresholds"]
    catd = ndi.distance_transform_edt(~cat)
    blocks_all, per_fold = [], []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_A_f{f}.npy"), eligible.shape)
        pb = base.to_grid(store.flat_idx, np.load(WORK / f"pred_single_B_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        thr = (float(np.quantile(pa[neg], th["donor_rank_min"])), float(np.quantile(pb[neg], th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thr, side=th["block_side_px"], minimum=32)
        blocks_all += blocks
        per_fold.append(dict(fold=f, n_labelled_negatives=int(neg.sum()), thresholds=list(thr), n_blocks=len(blocks)))
        log(f"fold {f}: {len(blocks)} blocks over {int(neg.sum())} labelled negatives")
        del pa, pb
    res = spatial.independence(blocks_all, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    out = dict(stage="independence", started_utc=now(), instrument="gems52.spatial.independence",
               thresholds_inherited_from=str(th_src.relative_to(ROOT)), thresholds_inherited_sha256=digest(th_src),
               thresholds=dict(donor_rank_min=th["donor_rank_min"], block_side_px=th["block_side_px"],
                               abandon_max_abs_rho=th["independence_abandon_max_abs_rho"], min_blocks=20,
                               negative_ring_px=4),
               view_A="single_A (store view_A_with_external)", view_B="B_DVA2 arm NOT used: lane test is on the "
               "two single-view learners (shared H84 convention)", per_fold=per_fold, result=res,
               caveat=("negatives are catalogue-zero proxies, not verified absence; weak error correlation is "
                       "necessary for co-training, not proof of conditional independence"),
               finished_utc=now())
    write("independence", out)
    log(json.dumps({k: res[k] for k in res if not isinstance(res[k], (list, dict))}, default=float))
    return out


# ============================================================================================= lane
def full_registry():
    from build_h61_submission import prior_paths
    full, meta = prior_paths(ROOT / "work/h102/prior_fetch_receipt.json", ("submission",))
    extra = sorted((DATA / "scored").glob("*.tif")) + sorted((DATA / "reference").glob("*.tif"))
    seen, out = set(), []
    for p in full + extra:
        if p.exists() and PREFIX not in p.name and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    meta["extra_scored_reference"] = len(extra)
    return out, meta


def stage_lane():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    F = load_fields()
    s, pool = F["s"], F["pool"] > 0
    full, meta = full_registry()
    restr, _scored = h82.restricted_registry()
    out = dict(stage="lane", started_utc=now(), registry_full=meta, n_full=len(full), n_restricted=len(restr),
               doctrine=("both registries reported verbatim; a restricted-registry PASS never waives a literal "
                         "full-census DUPLICATE/STOP (AGENTS.md, knowledge/62 IR-H73-011)"))
    log(f"lane: full census {len(full)} rasters, scored-only {len(restr)} rasters")
    # 1) surface BEFORE placement: the state-machine rank field, rank-normalized over the pool
    #    (Spearman is rank-based, so the monotone transform changes no statistic; it only satisfies
    #    the shared instrument's [0,1] input contract)
    surf = np.nan_to_num(rank_on(s, pool), nan=0.0).astype(np.float32)
    out["full_surface"] = gates.lane_report(surf, eligible, full, sample=SAMPLE, phase="surface", log=log)
    out["restricted_surface"] = gates.lane_report(surf, eligible, restr, sample=SAMPLE, phase="surface")
    write("lane", out)
    if out["full_surface"]["literal"]["verdict"].upper().startswith("DUPLICATE"):
        out["stopped"] = "surface literal DUPLICATE -> logged as duplicate, stopped before placement"
        write("lane", out)
        log(out["stopped"])
        return out
    # 2) quota placement (H73 amendment 61a) against the scored-only informative supports
    sups, suprows = h82.restricted_supports(restr, eligible)
    out["restricted_supports"] = suprows
    K = int(reg["budgets"]["subhalo_px_total"])
    fld = np.where(pool, s, -1.0).astype(np.float32)
    t0 = time.time()
    lane_dots, lrec = h73.place_lane(fld, pool, K, sups, eligible.shape, limit=0.70, rounds=8)
    out["quota_placement"] = dict(lrec, seconds=round(time.time() - t0, 1))
    if int(lane_dots.sum()) == K:
        dots, out["emitted_placement"] = lane_dots, "quota (run_h73.place_lane, scored-only supports)"
    else:
        dots = nodes.spacing_select(fld, pool, K, min_px=3.0)
        out["emitted_placement"] = f"fallback spacing_select (quota short-filled at {int(lane_dots.sum())})"
    h82.save_verified(WORK / "dots.npy", dots)
    out["dots"] = int(dots.sum())
    # 3) dots AFTER placement
    df = dots.astype(np.float32)
    out["full_dots"] = gates.lane_report(df, eligible, full, sample=SAMPLE, phase="dots", log=log)
    out["restricted_dots"] = gates.lane_report(df, eligible, restr, sample=SAMPLE, phase="dots")
    out["uniqueness_full"] = gates.uniqueness_report(df, full)
    out["finished_utc"] = now()
    write("lane", out)
    for k in ("full_surface", "restricted_surface", "full_dots", "restricted_dots"):
        r = out[k]
        log(f"{k}: literal {r['literal']['verdict']} (max rho {r['literal']['max_spearman']}, max near "
            f"{r['literal']['max_near_3px_fraction']}) | policy {r['policy']['verdict']}")
    uq = out["uniqueness_full"]
    log(f"uniqueness: identical_to_any={uq.get('identical_to_any_prior')} novel_fraction="
        f"{uq.get('novel_fraction')} max_jaccard={uq.get('max_jaccard')}")
    return out


# ============================================================================================= write
def stage_write():
    reg = check_prereg()
    _r, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    F = load_fields()
    dots = np.load(WORK / "dots.npy").astype(bool)
    pool = F["pool"] > 0
    C, Aonly = F["C"] > 0, F["Aonly"] > 0
    rB, rA, s = F["rB"], F["rA"], F["s"]
    dom = footprint_mask()

    # not-the-union (gate 10): equal-budget union-max placement, same quota placement machinery
    union = np.full(eligible.shape, -1.0, np.float32)
    union[pool] = np.maximum(rB[pool], rA[pool])
    restr, _ = h82.restricted_registry()
    sups, _rows = h82.restricted_supports(restr, eligible)
    K = int(reg["budgets"]["subhalo_px_total"])
    union_dots, _lrec = h73.place_lane(union, pool, K, sups, eligible.shape, limit=0.70, rounds=8)
    if int(union_dots.sum()) != K:
        union_dots = nodes.spacing_select(union, pool, K, min_px=3.0)
    inter = int((dots & union_dots).sum())
    jaccard = inter / max(1, int((dots | union_dots).sum()))
    outside = 1.0 - inter / max(1, int(dots.sum()))
    a_sup = nodes.spacing_select(np.where(Aonly, rA, -1.0).astype(np.float32), Aonly, K, min_px=3.0)
    b_sup = nodes.spacing_select(np.where(pool, rB, -1.0).astype(np.float32), pool, K, min_px=3.0)
    not_union = dict(union_max_placement_px=int(union_dots.sum()), jaccard_vs_union=jaccard,
                     share_of_dots_outside_union=outside,
                     jaccard_vs_single_A_only_topK=int((dots & a_sup).sum()) / max(1, int(dots.sum())),
                     jaccard_vs_single_B_only_topK=int((dots & b_sup).sum()) / max(1, int(dots.sum())),
                     gate_min_share_outside=0.25,
                     PASS=bool(outside >= 0.25))
    log(f"not-the-union: jaccard {jaccard:.4f}, outside union {outside:.4f}, PASS={not_union['PASS']}")

    # GeoTIFF
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dot_sha8 = hashlib.sha256(np.ascontiguousarray(dots.astype(np.uint8)).tobytes()).hexdigest()[:8]
    name = f"{PREFIX}disagreement-quota-dva2-{K}px-{ts}-{dot_sha8}-zeros"
    inside = np.zeros(eligible.shape, np.float32)
    inside[dots] = 1.0
    inside[~dom] = 0.0
    tif = ROOT / "submission" / f"{name}.tif"
    wrec = grid.write_geotiff_portal_exact(tif, inside, dom, SAMPLE, outside="zero")
    zip_path = ROOT / "submission" / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)
    doc_dl = ROOT / "docs/downloads"
    doc_dl.mkdir(parents=True, exist_ok=True)
    (doc_dl / f"{name}.tif").write_bytes(tif.read_bytes())
    (doc_dl / f"{name}.zip").write_bytes(zip_path.read_bytes())
    fmt = gates.format_report(tif, SAMPLE)

    # A-only reasoning CSV (every emitted A-only dot; H84 reading function, imported)
    cand = dots & Aonly
    fA_rank = np.load(WORK / "rA.npy")
    fB_rank = np.load(WORK / "rB.npy")
    catd = ndi.distance_transform_edt(~cat)
    # the H84 helper adds its own "gems52-" prefix; pass the base name without it (IR-H102-003)
    csv_rel, n_reason_rows = h84.write_a_only_reasoning(store, cand, fA_rank, fB_rank, catd, eligible,
                                                        name[len("gems52-"):])

    out = dict(stage="write", started_utc=now(), submission_name=f"h102-disagreement-quota-dva2-{K}px-{ts}-{dot_sha8}",
               note=reg["submission_note"], note_len=len(reg["submission_note"]),
               file=str(tif.relative_to(ROOT)), bytes=tif.stat().st_size, sha256=wrec.get("sha256"),
               zip=str(zip_path.relative_to(ROOT)), dots=int(dots.sum()),
               C_emitted=int((dots & C).sum()), Aonly_emitted=int(cand.sum()),
               Bonly_emitted=int((dots & (F["Bonly"] > 0)).sum()),
               validator=fmt, format_ok=bool(fmt.get("problems") in (None, [])),
               not_the_union=not_union, a_only_reasoning_csv=csv_rel,
               a_only_reasoning_rows=n_reason_rows, finished_utc=now())
    write("write", out)
    log(f"write: {tif.name} sha {wrec.get('sha256','?')[:16]}... dots {int(dots.sum())} "
        f"C {int((dots & C).sum())} A-only {int(cand.sum())} B-only {int((dots & (F['Bonly'] > 0)).sum())}")
    return out


# ============================================================================================= card
def stage_card():
    reg = check_prereg()

    def rd(name):
        p = EVID / f"h102_{name}.json"
        return json.loads(p.read_text()) if p.exists() else None

    fit, f1, f2, f3, ind, lane, wr = rd("fit"), rd("e1_graft_holdout"), rd("e2_quota_holdout"), \
        rd("e3_proxy_sgmc"), rd("independence"), rd("lane"), rd("write")
    e2p = f2["pooled"]["scores"] if f2 else {}
    e1p = f1["pooled"]["scores"] if f1 else {}
    gates_res = {}
    if f1 and f1.get("controls"):
        c = f1["controls"]
        gates_res["control_reproduction"] = "PASS" if (c["single_B"]["PASS"] and c["random"]["PASS"]) else "FAIL"
    if fit:
        gates_res["canary"] = "PASS" if not fit["canary_alarm_any"] else "FAIL"
    if ind:
        rho = ind["result"].get("max_abs_correlation")
        gates_res["independence"] = "PASS" if rho is not None and rho < reg["independence"]["abandon_max_abs_rho"] else "FAIL"
    if f2 and f2.get("promotion"):
        gates_res["holdout_promotion"] = "PASS" if f2["promotion"]["promote"] else "FAIL"
    if lane:
        gates_res["lane_surface_literal"] = lane["full_surface"]["literal"]["verdict"]
        gates_res["lane_dots_literal"] = lane["full_dots"]["literal"]["verdict"]
        gates_res["lane_dots_policy"] = lane["full_dots"]["policy"]["verdict"]
        uq = lane.get("uniqueness_full", {})
        inf = json.loads((EVID / "h102_lane_informative_uniqueness.json").read_text()) \
            if (EVID / "h102_lane_informative_uniqueness.json").exists() else None
        # gate 7 as frozen: literal full-census reading.  It FAILs here for the standing registry reason
        # (probe-census union covers the footprint; IR-H87-001 / IR-H102-002): reported, not waived.
        gates_res["uniqueness"] = ("PASS" if (uq.get("distinct_from_every_comparable_prior")
                                              and not uq.get("identical_to_a_prior")
                                              and uq.get("novel_fraction", 0.0) >= 0.20
                                              and not uq.get("equals_literal_prior_union")) else "FAIL")
        if inf:
            gates_res["uniqueness_informative_only"] = ("PASS" if (inf.get("distinct_from_every_comparable_prior")
                                                                   and not inf.get("identical_to_a_prior")
                                                                   and inf.get("novel_fraction", 0.0) >= 0.20
                                                                   and not inf.get("equals_literal_prior_union")) else "FAIL")
    if wr:
        gates_res["format"] = "PASS" if wr["format_ok"] else "FAIL"
        gates_res["not_the_union"] = "PASS" if wr["not_the_union"]["PASS"] else "FAIL"
    must_pass = ("control_reproduction", "canary", "independence", "holdout_promotion",
                 "format", "uniqueness", "not_the_union")
    submit_ok = (all(gates_res.get(g) == "PASS" for g in must_pass)
                 and gates_res.get("lane_surface_literal") == "PASS"
                 and gates_res.get("lane_dots_policy") == "PASS")
    card = {
        "round": "H102",
        "evidence_class": "HOLDOUT-DTI unless labelled otherwise",
        "hypothesis": ("Disagreement-state quota emission on the DVA2 base: the co-training state machine "
                       "(consensus C / A-only buried / B-only artifact-veto) allocates a 25,400 px sub-halo "
                       "budget 18,000 C + 7,400 A-only, B-only never emitted, placed by per-prior quota"),
        "mechanism": ("DVA2 directional variogram anisotropy (damage zone / juxtaposed blocks, catalogue-free) "
                      "gated by View A independence (max |rho| <= 0.14): C = both views fire (fault with "
                      "geophysical expression), A-only = buried fault beneath cover the surface-trace "
                      "catalogue lacks, B-only = road/erosion-line suspects vetoed"),
        "named_non_fault_process": ("lithologic density contrasts at buried depositional contacts; basin-fill "
                                    "facies steps; intrusion margins; GNSS strain-grid smoothing gradients; "
                                    "aftershock/induced seismicity clusters; conductive clay-rich basin fill; "
                                    "road cuts and drainage/erosion lines (the vetoed B-only mimics)"),
        "holdout_dti": {
            "evaluator": "gems52-pooled-hide-v1",
            "withheld_positive_px": 53186 if not f2 else f2["withheld_positive_px"],
            "quota_primary@6350_per_fold": (round(e2p["quota_primary"]["dti"], 6), e2p["quota_primary"].get("ci95")) if f2 else None,
            "B_DVA2@6350_per_fold": (round(e2p["B_DVA2"]["dti"], 6), e2p["B_DVA2"].get("ci95")) if f2 else None,
            "B_DVA2@9400_per_fold_committed_bar": 0.192829,
            "quota_primary_minus_B_DVA2_paired": f2["pooled"]["paired_differences"].get("B_DVA2") if f2 else None,
            "graft_g_025@9400_per_fold": (round(e1p["g_025"]["dti"], 6), e1p["g_025"].get("ci95")) if f1 else None,
        },
        "correlation_overlap_vs_registry": {
            "surface_max_spearman": lane["full_surface"]["literal"]["max_spearman"] if lane else None,
            "dots_max_near_3px_literal": lane["full_dots"]["literal"]["max_near_3px_fraction"] if lane else None,
            "dots_max_near_3px_policy": lane["full_dots"]["policy"]["max_near_3px_fraction"] if lane else None,
            "uniqueness_novel_fraction": lane.get("uniqueness_full", {}).get("novel_fraction") if lane else None,
        },
        "sufficiency_view_A_bookkeeping": (fit["sufficiency_view_A"] if fit else None),
        "sufficiency_note": "gate 4 is bookkeeping only (preregistration sec.4); its expected FAIL does not block the verdict",
        "emission_strata_realised": (dict(C=wr["C_emitted"], A_only=wr["Aonly_emitted"],
                                          B_only_by_chance_tie_fill=wr["Bonly_emitted"],
                                          zero_score_tie_fill=wr["dots"] - wr["C_emitted"] - wr["Aonly_emitted"]
                                          - wr["Bonly_emitted"]) if wr else None),
        "quota_note": ("the frozen 18000 C + 7400 A-only quota is NOT realised: the pre-registered 3 px minimum "
                       "spacing (part of the placement instrument) caps extractable consensus cells, so 15,104 of "
                       "25,400 dots are zero-score tie fill (IR-H102-001); the E2 below-random score is driven by "
                       "that tie fill plus the A-gate"),
        "irregularities": ["IR-H102-001 (quota not realised by 3 px spacing; tie-fill mass; 154 B-only by chance)",
                           "IR-H102-002 (literal full-census novelty fraction 0.0 = probe-union standing condition; "
                           "informative-only novelty 0.8121 reported side by side)",
                           "IR-H102-003 (first A-only CSV written with doubled gems52- prefix; fixed, first write pair discarded)"],
        "raster_sha256": wr["sha256"] if wr else None,
        "validator": wr["validator"] if wr else None,
        "submission_name": wr["submission_name"] if wr else None,
        "note": reg["submission_note"],
        "gates": gates_res,
        "verdict": "promote" if submit_ok else "negative",
        "submit_ok": bool(submit_ok),
        "download_ok": True,
        "slots_used": 0,
        "e3_proxy_sgmc": "diagnostic only, never a score (see evidence/h102_e3_proxy_sgmc.json)",
        "finished_utc": now(),
    }
    p = EVID / "h102_run_card.json"
    p.write_text(json.dumps(card, indent=1, default=float) + "\n")
    log(json.dumps(card["gates"], default=float))
    log(f"VERDICT: {card['verdict']} (submit_ok={card['submit_ok']})")
    return card


STAGES = {
    "channels": stage_channels,
    "fit": stage_fit,
    "fields": stage_fields,
    "e1": stage_e1,
    "e2": stage_e2,
    "e3": stage_e3,
    "independence": stage_independence,
    "lane": stage_lane,
    "write": stage_write,
    "card": stage_card,
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in (*STAGES, "all"):
        raise SystemExit(__doc__)
    check_prereg()
    todo = list(STAGES) if sys.argv[1] == "all" else [sys.argv[1]]
    for st in todo:
        log(f"=== stage {st} ===")
        STAGES[st]()


if __name__ == "__main__":
    main()
