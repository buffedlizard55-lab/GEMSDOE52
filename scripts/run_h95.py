#!/usr/bin/env python3
"""H95 -- co-training lane, first scored on a board-anchored instrument; plus H87's first holdout.

Preregistered in ``knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md`` (frozen; SHA-256 pinned in
``registry/h95_preregistration.json``).  This runner refuses to start if that file's bytes moved.

Nothing here is a private fork of a shared tool:
  * fit / canary / independence / one whole-segment exchange  -> ``run_h61`` stages, redirected
    to ``work/h95`` and ``evidence/h95_stages`` (``run_h70.redirect`` precedent);
  * folds -> ``gems52.spatial.folds`` (label-blind-quadrants-v2, 80 px buffer, whole segments);
  * scoring -> ``gems52.evaluate_holdout`` (gems52-pooled-hide-v1) and ``gems52.metric``;
  * placement -> ``gems52.nodes.spacing_select`` (3 px);
  * packaging -> ``gems52.grid.write_geotiff_portal_exact(outside="zero")``;
  * gates -> ``gems52.gates`` (format_report, uniqueness_report, lane_report, find_priors);
  * H87 views -> imported from ``scripts/build_h87_cotrain_wavelength.py`` (not copied).

Stages:  e1 | e2 | e3 | build | gates | all
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

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import spearmanr                                    # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, grid, metric, nodes, spatial               # noqa: E402

REG_PATH = ROOT / "registry/h95_preregistration.json"
WORK = ROOT / "work/h95"
STAGE_EV = ROOT / "evidence/h95_stages"
EVID = ROOT / "evidence"
DATA = ROOT / "data"
SAMPLE = DATA / "sample_submission.tif"
SEED = 88052


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=float) + "\n")
    return path


def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    if sha(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("H95 preregistered document changed after registration; refusing to run")
    return reg


def write_stage(name: str, obj) -> Path:
    # Same file names the shared H61 stages expect, but under evidence/h95_stages and never docs/.
    return dump(STAGE_EV / f"h61_{name}.json", obj)


def redirect() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE_EV.mkdir(parents=True, exist_ok=True)
    base.WORK = WORK
    base.EVID = STAGE_EV
    base.write = write_stage


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


# ------------------------------------------------------------------------------------------ E1
def stage_e1():
    """H87's shipped rule on the shared hide-and-recover instrument (its first holdout)."""
    reg = check_prereg()
    th = reg["thresholds"]
    import build_h87_cotrain_wavelength as H87
    _, store, cat, eligible, folds, _, _, ring_px = base.setup()
    t0 = time.time()
    # H87's views are catalogue-free: computed once over the shared eligible footprint.
    vA = H87.compute_view_a(str(DATA / "training_features.tif"), eligible)
    vB = H87.compute_view_b(str(DATA / "training_features.tif"), str(DATA / "external/geodawn_rad_u8.tif"),
                            str(DATA / "external/geodawn_extensions_u8.tif"), eligible)
    dis = H87.compute_disagreement_field(vA, vB, eligible, cat)   # `cat` is an unused argument in H87
    np.save(WORK / "h87_viewA.npy", vA); np.save(WORK / "h87_viewB.npy", vB); np.save(WORK / "h87_dis.npy", dis)
    log(f"H87 views computed in {time.time()-t0:.0f}s")

    # leakage canary: each H87 input band alone + each H87 field, on held-out truth vs far negatives
    bands = {5: "iso_grav_anom_slope", 11: "iso_grav_anom_vg", 18: "iso_grav_anom_hg", 3: "tmi_hg",
             9: "tmi_vg", 4: "geod_2ndinv", 7: "geod_shearrate", 15: "depth_to_base_surf",
             17: "cond_surf", 12: "det_elev", 19: "det_elev_slope"}
    chans = {}
    with rasterio.open(DATA / "training_features.tif") as src:
        for b, nm in bands.items():
            chans[f"band{b:02d}_{nm}"] = src.read(b).astype(np.float32)
    with rasterio.open(DATA / "external/geodawn_extensions_u8.tif") as src:
        chans["ext_ThK"] = src.read(1).astype(np.float32)
    with rasterio.open(DATA / "external/geodawn_rad_u8.tif") as src:
        chans["ext_U"] = src.read(3).astype(np.float32)
    chans.update(h87_viewA=vA, h87_viewB=vB, h87_disagreement=dis)
    catd = ndi.distance_transform_edt(~cat)
    canary = {k: [] for k in chans}
    rng = np.random.default_rng(SEED)
    for fold in folds:
        pos = np.flatnonzero((fold["truth"] & fold["region"] & eligible).ravel())
        neg = np.flatnonzero((fold["region"] & eligible & ~cat & (catd > 5)).ravel())
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        for k, a in chans.items():
            x = np.nan_to_num(a.ravel()[np.r_[pos, neg]], nan=0.0, posinf=0.0, neginf=0.0)
            auc = float(roc_auc_score(y, x))
            canary[k].append(max(auc, 1 - auc))
    del chans
    canary_max = {k: float(max(v)) for k, v in canary.items()}
    log("canary max (direction-insensitive) AUC: " + json.dumps({k: round(v, 4) for k, v in canary_max.items()}))

    # independence of the two H87 views' errors on labelled negatives (scores are the OOF "errors"
    # of an untrained scorer on catalogue-zero pixels; same block statistic as the lane)
    rows = []
    for fold in folds:
        neg = fold["region"] & eligible & ~cat & (catd > 4)
        thr = (float(np.quantile(vA[neg], th["donor_rank_min"])), float(np.quantile(vB[neg], th["donor_rank_min"])))
        rows += spatial.negative_block_errors(vA, vB, neg, fold["fold"], thr, side=th["block_side_px"], minimum=32)
    indep = spatial.independence(rows, threshold=th["independence_abandon_max_abs_rho"], min_blocks=20)
    indep.pop("blocks", None)
    log(f"H87 independence max|rho| {indep['max_abs_correlation']}")
    del catd

    def fields(fold, allowed):
        rA, rB = rank_on(vA, allowed), rank_on(vB, allowed)
        r = np.random.default_rng(SEED + 500 + fold["fold"])
        rnd = np.zeros(allowed.shape, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = r.random(len(idx), dtype=np.float32)
        return {"h87_disagreement": np.where(allowed, dis, -1.0).astype(np.float32),
                "h87_single_A": np.nan_to_num(rA, nan=-1.0), "h87_single_B": np.nan_to_num(rB, nan=-1.0),
                "h87_union_max": np.nan_to_num(np.maximum(rA, rB), nan=-1.0), "random": rnd}

    summary, per_fold = pooled_run(fields, folds, eligible, ring_px, int(th["budget_dots_per_fold_per_arm"]),
                                   float(th["min_dot_separation_px"]), "h87_disagreement", int(th["bootstrap_draws"]))
    out = dict(round="H95", experiment="E1 (H87-V)", evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
               candidate="h87_disagreement", pooled=summary, per_fold=per_fold, canary_max_auc=canary_max,
               canary_alarm=th["canary_auc_alarm"], canary_any_alarm=bool(max(canary_max.values()) > th["canary_auc_alarm"]),
               independence=indep, folds_receipts=[f["receipt"] for f in folds],
               h87_script_sha256=sha(ROOT / "scripts/build_h87_cotrain_wavelength.py"), finished_utc=now())
    dump(EVID / "h95_e1_h87_holdout.json", out)
    log("E1 pooled: " + json.dumps({a: round(s["dti"], 6) for a, s in summary["scores"].items()}))
    return out


# ------------------------------------------------------------------------------------------ E2
def stage_e2():
    reg = check_prereg()
    th = reg["thresholds"]
    redirect()
    log("E2: shared H61 canary"); base.stage_canary()
    log("E2: shared H61 fit"); base.stage_fit()
    log("E2: shared H61 independence + one exchange"); base.stage_exchange()
    _, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx

    def fields(fold, allowed):
        f = fold["fold"]
        g = {k: base.to_grid(flat, np.load(WORK / f"pred_{k}_f{f}.npy"), eligible.shape)
             for k in ("pre_A", "pre_B", "post_B")}
        r = {k: rank_on(v, allowed) for k, v in g.items()}
        rng = np.random.default_rng(base.SEED + 500 + f)      # H61's random seed -> identical control
        rnd = np.zeros(eligible.shape, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        return {"single_A": np.nan_to_num(r["pre_A"], nan=-1.0),
                "single_B": np.nan_to_num(r["pre_B"], nan=-1.0),
                "union_max": np.nan_to_num(np.maximum(r["pre_A"], r["pre_B"]), nan=-1.0),
                "disagreement_pre": np.nan_to_num(r["pre_A"] - r["pre_B"], nan=-1.0),
                "cotrain_B": np.nan_to_num(r["post_B"], nan=-1.0),
                "random": rnd}

    summary, per_fold = pooled_run(fields, folds, eligible, ring_px, int(th["budget_dots_per_fold_per_arm"]),
                                   float(th["min_dot_separation_px"]), reg["primary_arm"], int(th["bootstrap_draws"]))
    ex = json.loads((STAGE_EV / "h61_pseudo_exchange.json").read_text())
    fit = json.loads((STAGE_EV / "h61_fit_checkpoint.json").read_text())
    can = json.loads((STAGE_EV / "h61_canary.json").read_text())
    ctrl = summary["scores"]["single_B"]["dti"]
    target = reg["control_target"]
    prim = summary["scores"][reg["primary_arm"]]
    diff = summary["paired_differences"]["single_B"]
    promote = bool(prim["dti"] > reg["promotion"]["holdout_bar"] and diff["ci95"][0] > 0)
    out = dict(round="H95", experiment="E2 (H95-1 lane)", evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
               candidate=reg["primary_arm"], pooled=summary, per_fold=per_fold,
               control_reproduction=dict(single_B=ctrl, target=target["single_B"], abs_diff=abs(ctrl - target["single_B"]),
                                         ok=bool(abs(ctrl - target["single_B"]) <= target["tolerance"])),
               sufficiency_oof_auc={f"view_{v}": [r[f"view_{v}"]["heldout_region_auc"] for r in fit["folds"]] for v in ("A", "B")},
               refit_oof_auc={f"refit_{v}": [r["directions"].get(f"refit_{v}", {}).get("heldout_region_auc") for r in ex["folds"]] for v in ("A", "B")},
               independence=dict(max_abs_rho=ex["independence_pre"]["max_abs_correlation"],
                                 n_blocks=ex["independence_pre"]["n_blocks"], allow_exchange=ex["allowed_exchange"],
                                 abandon_threshold=th["independence_abandon_max_abs_rho"]),
               pseudo_pixels_total=ex.get("total_pseudo_pixels"),
               canary=dict(max_alarm=can["max_alarm_across_folds"], fitted_top5_max=can["max_fitted_top5_heldout_auc"],
                           any_alarm=can["any_alarm"], alarm=th["canary_auc_alarm"]),
               promotion=dict(rule=reg["promotion"], primary_dti=prim["dti"], paired_vs_single_B=diff, promote=promote),
               finished_utc=now())
    dump(EVID / "h95_e2_lane_holdout.json", out)
    log("E2 pooled: " + json.dumps({a: round(s["dti"], 6) for a, s in summary["scores"].items()}))
    log(f"E2 control single_B {ctrl:.6f} vs target {target['single_B']} ; promote={promote}")
    return out


# ------------------------------------------------------------------------------------------ E3
def segthin_truths(reg, dom, cat):
    with rasterio.open(DATA / "external/derived_sgmc_faults_100m_u8.tif") as s:
        sg = s.read(1) > 0
    dcat = ndi.distance_transform_edt(~cat)
    off = sg & dom & (dcat >= 3)
    comp, n = ndi.label(off, np.ones((3, 3), bool))
    sizes = np.bincount(comp.ravel())[1:]
    G = int(reg["e3"]["G"])
    truths = []
    for seed in reg["e3"]["seeds"]:
        order = np.random.default_rng(seed).permutation(n) + 1
        cum = np.cumsum(sizes[order - 1])
        chosen = order[:int(np.searchsorted(cum, G)) + 1]
        truths.append(np.isin(comp, chosen))
    return truths


def stitched_fields():
    """Full-domain stitched OOF fields: quadrant f takes the fold-f model (trained outside it)."""
    _, store, cat, eligible, folds, _, _, _ = base.setup()
    flat = store.flat_idx
    out = {k: np.full(eligible.shape, np.nan, np.float32) for k in ("pre_A", "pre_B", "post_B")}
    for fold in folds:
        q = fold["quadrant"] & eligible
        for k in out:
            g = base.to_grid(flat, np.load(WORK / f"pred_{k}_f{fold['fold']}.npy"), eligible.shape)
            out[k][q] = rank_on(g, q)[q]          # within-quadrant rank, exactly as the holdout ranks
    return out, cat, eligible


def arm_fields(st, eligible):
    rA, rB, rP = st["pre_A"], st["pre_B"], st["post_B"]
    vA = np.load(WORK / "h87_viewA.npy"); vB = np.load(WORK / "h87_viewB.npy"); dis = np.load(WORK / "h87_dis.npy")
    return {"cotrain_B": rP, "single_B": rB, "single_A": rA, "union_max": np.fmax(rA, rB),
            "disagreement_pre": rA - rB, "h87_disagreement": np.where(eligible, dis, np.nan),
            "h87_single_B": np.where(eligible, vB, np.nan), "h87_single_A": np.where(eligible, vA, np.nan)}


def stage_e3():
    reg = check_prereg()
    st, cat, eligible = stitched_fields()
    with rasterio.open(SAMPLE) as s:
        dom = np.isfinite(s.read(1))
    truths = segthin_truths(reg, dom, cat)
    catd = ndi.distance_transform_edt(~cat)
    ring_px = reg["e3"]["ring_m"] / 100.0
    allowed = eligible & dom & ~cat & (catd > ring_px)
    res = {}

    def score(pred):
        v = [metric.dti(pred, g)["dti"] for g in truths]
        return dict(mean=float(np.mean(v)), per_seed=[float(x) for x in v])

    for arm, fld in arm_fields(st, eligible).items():
        for K in reg["e3"]["budgets"]:
            em = nodes.spacing_select(np.nan_to_num(fld, nan=-np.inf), allowed, K, min_px=3.0)
            np.save(WORK / f"e3_{arm}_{K}.npy", np.flatnonzero(em.ravel()))
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
    rand = np.random.default_rng(SEED).random(eligible.shape).astype(np.float32)
    for K in reg["e3"]["budgets"]:
        em = nodes.spacing_select(rand, allowed, K, min_px=3.0)
        res[f"random@{K}"] = dict(placed=int(em.sum()), **score(em.astype(np.float32)))
    budgets = reg["e3"]["budgets"]
    chosen = max(budgets, key=lambda K: res[f"{reg['primary_arm']}@{K}"]["mean"])
    out = dict(round="H95", experiment="E3", evidence_class="PROXY-SGMC (diagnostic, never a score)",
               instrument=reg["e3"], results=res, shipped_budget=int(chosen),
               shipped_budget_rule=reg["shipped_budget_rule"],
               caveat=("SGMC geologic-map faults >= 3 px from labels.tif, thinned by whole segments to |G| ~ 10k; "
                       "Spearman vs 13 owner-reported board scores 0.567 (0.911 excluding the lattice probe), "
                       "about as informative as emitted mass alone (|rho| 0.889). Not the hidden expert faults."),
               finished_utc=now())
    dump(EVID / "h95_e3_proxy_sgmc.json", out)
    log(f"E3 shipped budget by rule: {chosen}")
    return out


# ------------------------------------------------------------------------------------------ build
def stage_build():
    reg = check_prereg()
    e2 = json.loads((EVID / "h95_e2_lane_holdout.json").read_text())
    e3 = json.loads((EVID / "h95_e3_proxy_sgmc.json").read_text())
    K = int(e3["shipped_budget"])
    st, cat, eligible = stitched_fields()
    with rasterio.open(SAMPLE) as s:
        dom = np.isfinite(s.read(1))
    catd = ndi.distance_transform_edt(~cat)
    allowed = eligible & dom & ~cat & (catd > 2.0)
    field = st["post_B"]
    em = nodes.spacing_select(np.nan_to_num(field, nan=-np.inf), allowed, K, min_px=3.0)
    assert int(em.sum()) == K, "budget not filled"
    # cross-check: identical to the E3 emission of the same arm/budget
    e3_idx = np.load(WORK / f"e3_{reg['primary_arm']}_{K}.npy")
    assert np.array_equal(np.flatnonzero(em.ravel()), e3_idx), "build differs from the E3-scored emission"
    pred = em.astype(np.float32)
    footprint = dom
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dhash = hashlib.sha256(pred.astype("<f4").tobytes()).hexdigest()
    stem = f"gems52-h95-cotrainB-segthin-{K}px-{ts}-{dhash[:8]}-zeros"
    path = ROOT / "submission" / f"{stem}.tif"
    back = grid.write_geotiff_portal_exact(path, pred, footprint, SAMPLE, outside="zero")
    np.save(WORK / "final_field.npy", np.nan_to_num(field, nan=0.0).astype(np.float32))
    np.save(WORK / "final_pred_idx.npy", np.flatnonzero(em.ravel()))
    meta = dict(path=str(path.relative_to(ROOT)), stem=stem, budget=K, decoded_sha256=dhash,
                file_sha256=sha(path), bytes=path.stat().st_size, writer=back.get("portal_exact"),
                min_dist_to_catalogue_m=float(catd[em].min() * 100), within_300m=int((catd[em] <= 3).sum()),
                e2_promote=e2["promotion"]["promote"], built_utc=now())
    dump(EVID / "h95_build.json", meta)
    log(f"built {path.name} sha256 {meta['file_sha256'][:16]}")
    return meta


# ------------------------------------------------------------------------------------------ gates
def stage_gates():
    reg = check_prereg()
    th = reg["thresholds"]
    meta = json.loads((EVID / "h95_build.json").read_text())
    path = ROOT / meta["path"]
    with rasterio.open(SAMPLE) as s:
        dom = np.isfinite(s.read(1))
    fmt = gates.format_report(path, SAMPLE, footprint=dom)
    with rasterio.open(path) as s:
        pred = s.read(1)
    st, cat, eligible = stitched_fields()
    field = np.nan_to_num(st["post_B"], nan=0.0).astype(np.float32)
    # own-copy exclusion (IR-H85-001): exclude every file whose name carries this build's stem/hash
    priors = [p for p in gates.find_priors([DATA / "scored", DATA / "reference", ROOT / "submission",
                                            ROOT / "docs/downloads", WORK / "priors"], exclude=path)
              if meta["decoded_sha256"][:8] not in p.name and "h95-candidate" not in p.name]
    log(f"{len(priors)} priors for uniqueness/lane")
    uniq = gates.uniqueness_report(pred, priors)
    uniq_small = {k: v for k, v in uniq.items() if k != "per_prior"}
    uniq_small["max_jaccard"] = max((r.get("jaccard", 0) for r in uniq["per_prior"]), default=0)
    uniq_small["max_jaccard_prior"] = max(uniq["per_prior"], key=lambda r: r.get("jaccard", 0))["path"]
    lane_s = gates.lane_report(field, eligible, priors, sample=SAMPLE, phase="surface")
    lane_d = gates.lane_report(pred.astype(np.float32), eligible, priors, sample=SAMPLE, phase="dots")

    def lane_small(r):
        keep = {k: v for k, v in r.items() if k != "per_prior"}
        rows = [x for x in r.get("per_prior", []) if "error" not in x]
        keep["top_rank"] = sorted(((x.get("spearman") or 0.0, x["path"]) for x in rows), key=lambda t: -t[0])[:3]
        keep["top_near"] = sorted(((x.get("near_3px_fraction") or 0.0, x["path"], x.get("universal_coverage_probe"))
                                   for x in rows), key=lambda t: -t[0])[:5]
        return keep
    # not-the-union: same placement on max(rank A, rank B) over the same allowed set
    catd = ndi.distance_transform_edt(~cat)
    allowed = eligible & dom & ~cat & (catd > 2.0)
    K = int(meta["budget"])
    u = nodes.spacing_select(np.nan_to_num(np.fmax(st["pre_A"], st["pre_B"]), nan=-np.inf), allowed, K, min_px=3.0)
    a_only = nodes.spacing_select(np.nan_to_num(st["pre_A"], nan=-np.inf), allowed, K, min_px=3.0)
    b_only = nodes.spacing_select(np.nan_to_num(st["pre_B"], nan=-np.inf), allowed, K, min_px=3.0)
    d = pred > 0
    sub = np.flatnonzero(eligible.ravel())[::7]
    not_union = dict(jaccard_vs_union_dots=float((d & u).sum() / max((d | u).sum(), 1)),
                     jaccard_vs_singleA_dots=float((d & a_only).sum() / max((d | a_only).sum(), 1)),
                     jaccard_vs_singleB_dots=float((d & b_only).sum() / max((d | b_only).sum(), 1)),
                     dots_not_in_union=int((d & ~u).sum()),
                     spearman_field_vs_unionmax=float(spearmanr(field.ravel()[sub],
                                                                np.nan_to_num(np.fmax(st["pre_A"], st["pre_B"]), nan=0).ravel()[sub]).statistic),
                     is_union=bool(np.array_equal(d, u)))
    # strata of the shipped dots + A-only reasoning rows
    rA, rB = st["pre_A"], st["pre_B"]
    yy, xx = np.nonzero(d)
    a_conf = (rA[yy, xx] >= th["donor_rank_min"])
    b_abst = (rB[yy, xx] >= th["receiver_rank_interval"][0]) & (rB[yy, xx] <= th["receiver_rank_interval"][1])
    b_conf = rB[yy, xx] >= th["donor_rank_min"]
    strata = dict(a_only=int((a_conf & b_abst).sum()), b_only=int((b_conf & (rA[yy, xx] >= 0.35) & (rA[yy, xx] <= 0.65)).sum()),
                  both_confident=int((a_conf & b_conf).sum()), total=int(d.sum()))
    sel = np.flatnonzero(a_conf & b_abst)
    with rasterio.open(DATA / "training_features.tif") as src:
        cover = src.read(15); slope = src.read(19); ggrad = src.read(18); mag = src.read(3)
        T = src.transform
    pct = lambda a, m: np.nanpercentile(np.where(a > -1e30, a, np.nan)[eligible], m)
    cov_med, sl_med, gg_p75, mg_p75 = pct(cover, 50), pct(slope, 50), pct(ggrad, 75), pct(mag, 75)
    rows = ["row,col,utm_x_m,utm_y_m,rank_A,rank_B,cover_thickness_m_band15,slope_band19,grav_hg_band18,tmi_hg_band3,dist_to_catalogue_m,reasoning"]
    for i in sel:
        r, c = int(yy[i]), int(xx[i])
        x, y = T * (c + 0.5, r + 0.5)
        why = []
        why.append("thick cover" if cover[r, c] > cov_med else "thin cover")
        why.append("strong gravity gradient" if ggrad[r, c] > gg_p75 else "moderate gravity gradient")
        why.append("strong magnetic gradient" if mag[r, c] > mg_p75 else "weak magnetic gradient")
        why.append("low slope" if slope[r, c] < sl_med else "moderate/high slope")
        text = ("A-only: subsurface view confident (rank %.2f) while the surface view abstains (rank %.2f); %s. "
                "Reading: a basement density/susceptibility step without a geomorphic scarp, consistent with a normal "
                "fault buried by basin fill if cover is thick; mimics: lithologic contact, intrusive margin, "
                "basin-margin facies change." % (rA[r, c], rB[r, c], ", ".join(why)))
        rows.append(f"{r},{c},{x:.1f},{y:.1f},{rA[r, c]:.4f},{rB[r, c]:.4f},{cover[r, c]:.1f},{slope[r, c]:.3f},"
                    f"{ggrad[r, c]:.5g},{mag[r, c]:.5g},{catd[r, c]*100:.1f},\"{text}\"")
    rpath = ROOT / "submission" / f"{meta['stem']}-a-only-reasoning.csv"
    rpath.write_text("\n".join(rows) + "\n")
    out = dict(round="H95", format=fmt, uniqueness=uniq_small, lane_surface=lane_small(lane_s), lane_dots=lane_small(lane_d),
               not_the_union=not_union, strata=strata, a_only_reasoning_csv=str(rpath.relative_to(ROOT)),
               a_only_rows=int(len(sel)), n_priors=len(priors), finished_utc=now())
    dump(EVID / "h95_gates.json", out)
    log(json.dumps(dict(format_ok=fmt["ok"], uniq=uniq_small.get("canonical_pattern_unique"),
                        novel=uniq_small.get("novel_fraction"), lane_surface=lane_s["literal"]["verdict"], lane_dots_literal=lane_d["literal"]["verdict"], lane_dots_policy=lane_d["policy"]["verdict"],
                        not_union=not_union, strata=strata), default=str)[:1500])
    return out


def main(argv):
    stage = argv[1] if len(argv) > 1 else "all"
    stages = ["e1", "e2", "e3", "build", "gates"] if stage == "all" else [stage]
    for s in stages:
        t0 = time.time()
        log(f"=== H95 {s} ===")
        {"e1": stage_e1, "e2": stage_e2, "e3": stage_e3, "build": stage_build, "gates": stage_gates}[s]()
        log(f"--- {s} done in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
