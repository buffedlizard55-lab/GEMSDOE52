#!/usr/bin/env python3
"""R5 driver: two-view co-training on the trace detector, localisation assay, budget, emission.

Stages (each checkpoints to ``work/r5`` so a crash does not cost the round -- the lesson round 4
paid for with an entire uncommitted implementation, ``knowledge/23`` §0):

  1 stack    the two views' feature stacks as float32 memmaps
  2 oof      whole-block 4-fold out-of-fold propensity per view
  3 cotrain  independence test, disagreement strata, pseudo-label exchange and its measured effect
  4 fields   the preregistered candidate fields (trace, trace+habitat, single-view baselines, random)
  5 assay    hide-and-seek on whole held-out catalogue segments: lateral error, ribbon credit,
             exact simulator DTI, at matched budgets, for every field
  6 budget   the metric's own marginal test picks the budget from the measured credit curve
  7 emit     the final raster on the real legal set, gates, receipts

Usage:  python scripts/run_r5.py [--stages 1,2,3,4,5,6,7] [--folds 4] [--quick]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates as G                    # noqa: E402
from gems52 import grid as GRID                  # noqa: E402
from gems52_r5 import cotrain_r5 as C            # noqa: E402
from gems52_r5 import emit_r5 as EM              # noqa: E402
from gems52_r5 import layers as L                # noqa: E402
from gems52_r5 import localize as Z              # noqa: E402
from gems52_r5 import revealed_r5 as RV          # noqa: E402
from gems52_r5 import traces as T                # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"
SUB = ROOT / "submission"
DOCS = ROOT / "docs"
BUDGETS = (5_000, 10_000, 20_000, 30_000, 40_000, 60_000, 80_000)
TAU_MAIN = 0.99
TAU_WIDE = 0.95
CORRIDOR_M = 200.0
TARGET = 0.3195            # the owner-reported current board best this round has to beat
CHAMPION = 0.2778          # h33-2-b2, this family's best and the file we hold the bytes of
log = lambda m: print(m, flush=True)             # noqa: E731


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stage1_stack(valid, corrob, persist_all, log):
    out = {}
    for view in ("A", "B"):
        p = WORK / f"feat{view}.dat"
        names = C.feature_names(view)
        if p.exists() and p.stat().st_size == len(names) * valid.size * 4:
            log(f"[stack] view {view}: reusing {p} ({len(names)} layers)")
        else:
            log(f"[stack] view {view}: building {len(names)} layers")
            C.build_stack(view, valid, corrob, persist_all, log=log)
        out[view] = np.memmap(p, dtype=np.float32, mode="r", shape=(len(names),) + valid.shape)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="1,2,3,4,5,6,7")
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--quick", action="store_true", help="fewer budgets and one fold (smoke test)")
    args = ap.parse_args()
    stages = {int(s) for s in args.stages.split(",")}
    budgets = (10_000, 30_000) if args.quick else BUDGETS
    WORK.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # ---------------------------------------------------------------- inputs, verified
    valid = np.load(WORK / "valid.npy")
    cat = L.catalogue()
    corr99 = np.load(WORK / f"corrobor_{TAU_MAIN:g}.npy")
    corr95 = np.load(WORK / f"corrobor_{TAU_WIDE:g}.npy")
    edt_cat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    fams = {}
    for f in L.FAMILIES:
        z = np.load(WORK / f"fam_{f}.npz")
        fams[f] = dict(resp=z["resp"], theta=z["theta"], agree=z["agree"])
    persist_all = {f: T.persistence_length(np.load(WORK / f"trace_{f}_{TAU_MAIN:g}.npy"))
                   for f in L.FAMILIES}
    persist_max = ndimage.maximum_filter(
        np.max(np.stack([persist_all[f] for f in L.FAMILIES]), axis=0), size=5)
    resp_max = np.max(np.stack([fams[f]["resp"] for f in L.FAMILIES]), axis=0)
    legal_full = valid & (edt_cat > CORRIDOR_M)
    log(f"[inputs] footprint {int(valid.sum())} px, catalogue {int(cat.sum())} px, "
        f"legal (off-ring) {int(legal_full.sum())} px")
    log(f"[inputs] corroboration >=2 at tau {TAU_MAIN}: {int((corr99 >= 2).sum())} px, "
        f"at tau {TAU_WIDE}: {int((corr95 >= 2).sum())} px")

    inputs = dict(footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
                  legal_off_ring_px=int(legal_full.sum()),
                  corrob_ge2_tau99=int((corr99 >= 2).sum()), corrob_ge3_tau99=int((corr99 >= 3).sum()),
                  corrob_ge2_tau95=int((corr95 >= 2).sum()),
                  labels_sha=sha(ROOT / "data/labels.tif"),
                  features_sha=sha(ROOT / "data/training_features.tif"),
                  sample_sha=sha(ROOT / "data/sample_submission.tif"))

    # ---------------------------------------------------------------- stage 1: stacks
    if 1 in stages:
        stacks = stage1_stack(valid, corr99, persist_all, log)
    else:
        stacks = None

    # ---------------------------------------------------------------- stage 2: blocked OOF
    bid = C.block_ids(valid.shape, valid)
    buf = C.block_buffer(bid, buffer_px=4)
    fold = C.make_folds(bid, k=args.folds)
    pos = cat & valid
    neg = valid & ~cat
    sample = C.sample_rows(pos, neg, ~buf)
    log(f"[folds] {int(bid.max()) + 1} blocks of 20 km, {args.folds} whole-block folds, "
        f"buffer {int(buf.sum())} px, sample {sample['n_pos']}+{sample['n_neg']} rows")
    oof = {}
    oof_path = {v: WORK / f"oof_{v}.npy" for v in ("A", "B")}
    receipts = {}
    if 2 in stages:
        for v in ("A", "B"):
            if oof_path[v].exists():
                oof[v] = np.load(oof_path[v])
                log(f"[oof] view {v}: reusing cached field")
                continue
            t0 = time.time()
            field, rec = C.fit_oof(stacks[v], sample, fold, buf, valid, log=log, tag=f"_{v}")
            np.save(oof_path[v], field)
            oof[v] = field
            receipts[v] = dict(folds=rec, seconds=time.time() - t0,
                               mean_auc=float(np.mean([r["auc"] for r in rec])),
                               n_layers=len(C.feature_names(v)),
                               layers=C.feature_names(v))
            log(f"[oof] view {v}: mean fold AUC {receipts[v]['mean_auc']:.4f} "
                f"in {receipts[v]['seconds']:.1f}s")
        C.save_json(EVID / "r5_model.json", dict(views=receipts, folds=dict(
            n_blocks=int(bid.max()) + 1, n_folds=args.folds, buffer_px=4,
            sample_pos=sample["n_pos"], sample_neg=sample["n_neg"], seed=C.SEED),
            inputs=inputs))
    else:
        for v in ("A", "B"):
            if oof_path[v].exists():
                oof[v] = np.load(oof_path[v])

    # ---------------------------------------------------------------- stage 3: co-training
    if 3 in stages:
        t0 = time.time()
        depth = L.read("features", 15, valid=valid)
        slope = L.read("features", 19, valid=valid)
        indep = C.independence(oof["A"], oof["B"], pos, neg, bid)
        log(f"[independence] {indep['n_blocks']} blocks, spearman {indep.get('spearman')}, "
            f"pearson {indep.get('pearson')}, max|r| {indep.get('max_abs')} -> {indep.get('verdict')}")
        strata = C.disagreement_strata(oof["A"], oof["B"], legal_full, depth, slope)
        log(f"[disagreement] A-only {strata['a_only']['px']} px (median depth "
            f"{strata['a_only'].get('median_depth_to_basement_m')} m), "
            f"B-only {strata['b_only']['px']} px (median depth "
            f"{strata['b_only'].get('median_depth_to_basement_m')} m)")
        pl = C.pseudo_labels(oof["A"], oof["B"], legal_full, fold, buf)
        log(f"[pseudo-labels] A->B {pl['a_to_b']['px']} px in {pl['a_to_b']['segments']} segments "
            f"(leak-free {pl['a_to_b']['leak_free']}); B->A {pl['b_to_a']['px']} px in "
            f"{pl['b_to_a']['segments']} segments")
        # measure the exchange: refit the receiver with the donor's confident/abstaining segments
        from sklearn.metrics import roc_auc_score
        exchange = {}
        rows0, cols0 = sample["rows"], sample["cols"]
        f0 = fold[rows0, cols0] == 0
        for donor, recv in (("A", "B"), ("B", "A")):
            key = "a_to_b" if donor == "A" else "b_to_a"
            mask = pl[key]["mask"]
            auc_base = float(roc_auc_score(sample["y"][f0],
                                           C._lookup(oof[recv], rows0[f0], cols0[f0])))
            res = C.apply_pseudo_labels(stacks[recv], sample, fold, buf, valid, mask, 1,
                                        log=log, tag=f"_{recv}")
            auc_pl = float(res["fold0_auc"])
            exchange[f"{donor}_to_{recv}"] = dict(
                pseudo_px=pl[key]["px"], segments=pl[key]["segments"],
                leak_free=pl[key]["leak_free"],
                measured_on="the original labelled fold-0 rows only, before and after; the "
                            "pseudo-labels themselves are never scored, because that would "
                            "measure donor-reproduction, not gain",
                fold0_auc_before=auc_base, fold0_auc_after=auc_pl,
                fold0_auc_including_pseudo=res["fold0_auc_including_pseudo"],
                delta_fold0_auc=auc_pl - auc_base)
            log(f"[exchange] {donor}->{recv}: fold-0 AUC {auc_base:.4f} -> {auc_pl:.4f} "
                f"({auc_pl - auc_base:+.4f})")
            del res
        C.save_json(EVID / "r5_cotrain.json", dict(
            independence=indep,
            disagreement={k: v for k, v in strata.items() if not k.endswith("mask")},
            pseudo_labels={k: {kk: vv for kk, vv in v.items() if kk != "mask"}
                           for k, v in pl.items()},
            exchange=exchange, seconds=time.time() - t0,
            verdict=("co-training premise " + indep.get("verdict", "?") +
                     "; pseudo-label exchange measured, not assumed"),
            inputs=inputs))
        del depth, slope

    # ---------------------------------------------------------------- stage 4: fields
    hab_union = np.nanmax(np.stack([np.nan_to_num(oof["A"], nan=0.0),
                                    np.nan_to_num(oof["B"], nan=0.0)]), axis=0)
    persist_n = np.log1p(persist_max) / max(float(np.percentile(persist_max[valid], 99.9)), 1e-9)
    c99 = corr99.astype(np.float64) / 6.0
    c95 = corr95.astype(np.float64) / 6.0
    rmax = np.nan_to_num(resp_max, nan=0.0)
    hnorm = C.rank_within(hab_union, legal_full)
    hnorm = np.nan_to_num(hnorm, nan=0.0)
    fields = {
        "F1_trace": 1.0 * c99 + 0.5 * c95 + 0.35 * rmax,
        "F2_trace_persist": 1.0 * c99 + 0.5 * c95 + 0.35 * rmax + 0.5 * persist_n,
        "F3_trace_persist_habitat": 1.0 * c99 + 0.5 * c95 + 0.35 * rmax + 0.5 * persist_n
                                    + 0.5 * hnorm,
        "F4_habitat_only": hnorm,
        "F5_A_only": np.nan_to_num(C.rank_within(oof["A"], legal_full), nan=0.0),
        "F6_B_only": np.nan_to_num(C.rank_within(oof["B"], legal_full), nan=0.0),
        "F7_union_max": np.nan_to_num(C.rank_within(hab_union, legal_full), nan=0.0),
    }
    if 4 in stages:
        for k, v in fields.items():
            np.save(WORK / f"field_{k}.npy", v.astype(np.float32))
        log(f"[fields] wrote {len(fields)} candidate fields")

    # ---------------------------------------------------------------- stage 5: assay
    if 5 in stages:
        t0 = time.time()
        fold_id = Z.component_folds(cat, valid, n_folds=args.folds)
        assay = {}
        n_folds = 1 if args.quick else args.folds
        for k in range(n_folds):
            fm = Z.fold_masks(cat, valid, fold_id, k)
            log(f"[assay] fold {k}: hidden {fm['hidden_px']} px, legal {fm['legal_px']} px, "
                f"truth survival inside legal {fm['truth_survival_in_legal']:.4f}")
            if fm["truth_survival_in_legal"] < 0.9:
                raise RuntimeError("held-out truth is not placeable; the ring mask was built "
                                   "from the full catalogue instead of the visible one")
            assay[k] = dict(fold={kk: vv for kk, vv in fm.items()
                                if kk in ("fold", "hidden_px", "legal_px", "truth_survival_in_legal")},
                            fields={})
            legal = fm["legal"]
            rng = np.random.default_rng(C.SEED + k)
            rnd = rng.random(valid.shape).astype(np.float32)
            for name, field in list(fields.items()) + [("F8_random", rnd)]:
                rows = []
                for b in budgets:
                    dots = Z.place_dots(np.where(legal, field, -np.inf), legal, b, min_sep_px=3.0)
                    res = Z.assay(dots.astype(np.float32), fm)
                    rows.append(dict(budget=b, requested=b, emitted=res["emitted_px"],
                                     shortfall=list(Z.place_dots.last_shortfall),
                                     dti=res["dti"], tpw=res["tpw"], capture=res["capture"],
                                     q=res["q"], q_within_1px=res["q_within_1px"],
                                     mean_lattice_dist_px=res["mean_lattice_dist_px"],
                                     ribbon_credit_per_dot=res["ribbon_credit_per_dot"],
                                     ribbon_cover_per_dot=res["ribbon_cover_per_dot"],
                                     hist=res["hist"]))
                    log(f"    [assay {k}] {name:26s} S={res['emitted_px']:6d} "
                        f"simDTI={res['dti']:.4f} q={res['q']:.4f} "
                        f"q<=1px={res['q_within_1px']:.4f} c/dot={res['ribbon_credit_per_dot']:.3f}")
                assay[k]["fields"][name] = rows
            del fm
        C.save_json(WORK / "r5_assay.json", dict(
            budgets=list(budgets), folds=assay, seconds=time.time() - t0,
            truth="whole held-out catalogue components (mapped faults), density-matched to |G|",
            caveat="mapped traces are easier than unmapped ones; see localize.project delta"))
        log(f"[assay] done in {time.time() - t0:.1f}s")

    # ---------------------------------------------------------------- stage 6: budget
    if 6 in stages:
        assay = json.loads((WORK / "r5_assay.json").read_text())
        sel = {}
        for name in assay["folds"]["0"]["fields"]:
            per_budget = {}
            for b in budgets:
                cs, gs, ds = [], [], []
                for k, fk in assay["folds"].items():
                    row = next(r for r in fk["fields"][name] if r["budget"] == b)
                    cs.append(row["ribbon_credit_per_dot"]); gs.append(row["ribbon_cover_per_dot"])
                    ds.append(row["dti"])
                per_budget[int(b)] = dict(credit_per_dot=float(np.mean(cs)),
                                          cover_per_dot=float(np.mean(gs)),
                                          simulator_dti=float(np.mean(ds)),
                                          simulator_dti_folds=[float(x) for x in ds])
            bs = sorted(per_budget)
            curve = {delta: EM.budget_from_curve(
                bs, [per_budget[b]["credit_per_dot"] for b in bs],
                [per_budget[b]["cover_per_dot"] for b in bs], RV.G_PX, delta=delta)
                for delta in (1.0, 0.5, 0.25)}
            sel[name] = dict(per_budget=per_budget, curves={f"{d:g}": curve[d] for d in curve},
                             best_at_delta1=curve[1.0]["best"],
                             best_at_delta05=curve[0.5]["best"],
                             best_at_delta025=curve[0.25]["best"])
            log(f"[budget] {name:26s} best@delta1 S={curve[1.0]['best']['budget']} "
                f"DTI={curve[1.0]['best']['projected_dti']:.4f} | "
                f"delta0.5 S={curve[0.5]['best']['budget']} "
                f"DTI={curve[0.5]['best']['projected_dti']:.4f} | "
                f"sim={max(per_budget[b]['simulator_dti'] for b in bs):.4f}")
        C.save_json(EVID / "r5_budget.json", dict(g_px=RV.G_PX, target=TARGET, fields=sel,
                                                  inputs=inputs))

    # ---------------------------------------------------------------- stage 7: emission
    if 7 in stages:
        budget_sel = json.loads((EVID / "r5_budget.json").read_text())
        # pick the field whose delta=0.5 projection is best, ties broken by delta=1 then simulator
        def key(nm):
            f = budget_sel["fields"][nm]
            return (f["best_at_delta05"]["projected_dti"], f["best_at_delta1"]["projected_dti"],
                    max(v["simulator_dti"] for v in f["per_budget"].values()))
        winner = max(budget_sel["fields"], key=key)
        s_star = budget_sel["fields"][winner]["best_at_delta05"]["budget"]
        log(f"[emit] winner {winner} at budget {s_star} (delta=0.5 projection "
            f"{budget_sel['fields'][winner]['best_at_delta05']['projected_dti']:.4f})")
        field = np.load(WORK / f"field_{winner}.npy")
        dots = Z.place_dots(np.where(legal_full, field, -np.inf), legal_full, int(s_star),
                            min_sep_px=3.0)
        emission = np.zeros(valid.shape, np.float32)
        emission[dots] = 1.0
        log(f"[emit] {int(emission.sum())} px, shortfall {Z.place_dots.last_shortfall}")
        SUB.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        h8 = sha(WORK / "valid.npy")[:12]
        name = f"gems52-r5-traceribbon-{int(emission.sum())}px-{stamp}-{h8}-zeros"
        tif = SUB / f"{name}.tif"
        info = GRID.write_geotiff(tif, emission)
        # gates
        prior_roots = [ROOT / "data/scored", ROOT / "data/reference", ROOT / "submission",
                       ROOT / "docs/downloads"]
        priors = G.find_priors(prior_roots, exclude=tif)
        fmt = G.format_report(tif, ROOT / "data/sample_submission.tif", footprint=valid)
        uniq = G.uniqueness_report(emission, priors)
        d_emit = edt_cat[emission > 0]
        receipt = dict(
            name=name, tif=str(tif), bytes=info["bytes"], sha256=info["sha256"],
            emitted_px=int(emission.sum()), winner_field=winner, budget_requested=int(s_star),
            min_separation_px=3.0, corridor_m=CORRIDOR_M,
            min_distance_to_catalogue_m=float(d_emit.min()) if d_emit.size else None,
            median_distance_to_catalogue_m=float(np.median(d_emit)) if d_emit.size else None,
            values=dict(min=info["min"], max=info["max"], unique=info["unique_values"],
                        nan=info["nan_pixels"], all_finite=bool(info["nan_pixels"] == 0),
                        in_unit_interval=bool(info["min"] >= 0.0 and info["max"] <= 1.0)),
            format_gate=dict(ok=fmt["ok"], problems=fmt["problems"]),
            uniqueness_gate=dict(ok=uniq["ok"], pattern_unique=uniq["canonical_pattern_unique"],
                                 n_priors=uniq["n_priors_checked"],
                                 novel_fraction=uniq["novel_fraction"],
                                 equals_literal_prior_union=uniq["equals_literal_prior_union"],
                                 relation=uniq["relation_to_union"]),
            projection=budget_sel["fields"][winner],
            inputs=inputs, seconds=time.time() - t_start)
        C.save_json(EVID / "r5_emission.json", receipt)
        C.save_json(DOCS / "data" / "r5_emission.json", receipt)
        log(f"[emit] wrote {tif} ({info['bytes']} bytes, sha {info['sha256'][:16]}...) "
            f"format_ok={fmt['ok']} unique={uniq['canonical_pattern_unique']} "
            f"novel={uniq['novel_fraction']:.3f}")
    log(f"[done] {time.time() - t_start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
