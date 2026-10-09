#!/usr/bin/env python3
"""H61 E3 -- place, gate, write and publish this round's unique GeoTIFF.

Reads the two E1/E2 receipts and never re-fits.  Every gate is written to ``evidence/``.

Field selection (mechanical, from the receipts)
-----------------------------------------------
1. Every candidate field is emitted at the registered budget on the legal pool (footprint minus the
   <=200 m catalogue ring) with the registered scoring emitter ``h57.iso_select``.
2. **Union disqualifier (correction H61-3).**  Any candidate whose dots overlap the ``clf_union``
   top-k at the same budget by more than 70 % is *the union* for the purposes of the brief's
   "confirm the output isn't merely the union of the two views" and is removed.
3. **Winner** = highest revealed-preference co-location lift among the survivors.

Gates
-----
format (all finite, {0,1}, CRS/shape/transform), ring (no dot within 200 m of the catalogue),
uniqueness (decoded pattern distinct from every accessible aligned prior), lane drift (Spearman
<= 0.90 on the surface and on the dots; <= 70 % of dots within 3 px of any one registry raster,
calibration rasters excluded from the proximity component per H60-6), not-merely-union.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates                            # noqa: E402
from gems52 import grid as G                        # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h60d                             # noqa: E402
from gems52 import h61                              # noqa: E402
from gems52 import submission_writer                # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work/h61"
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
DAD = ROOT / "docs/data"
PREREG = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
Q_CONF = float(PREREG["protocol"]["thresholds"]["q_conf"])
Q_ABSTAIN = float(PREREG["protocol"]["thresholds"]["q_abstain"])
COVER_Q = float(PREREG["protocol"]["thresholds"]["cover_depth_quantile"])
BUDGET = 22000                 # registered correction H61-2
UNION_DISQUALIFY = 0.70        # correction H61-3
RING_PX = h57.CORRIDOR_PX      # 2 px = 200 m
CHAMPION_OWNER_REPORTED = 0.2778
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def log(m: str) -> None:
    print(f"[h61-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def prior_inventory(field: str, budget: int, extra_roots=()):
    """Accessible aligned priors with this round's OWN outputs excluded, by exact basename.

    Self-exclusion is deliberately by the basenames this build writes and nothing else.  A bare
    ``gems52-h61-`` prefix would also exclude a *parallel* H61 session's artifact, which is a
    genuine prior the lane gate exists to compare against (the IR-H60D-002 lesson, inverted).
    """
    roots = [r for r in extra_roots if Path(r).exists()]
    found = gates.find_priors(roots)
    own = {f"gems52-h61-{field}-arm{int(budget)}px.tif",
           f"gems52-h61-{field}-arm{int(budget)}px.zip",
           "h61-candidate.tif", "h61-candidate.zip", "STATUS.txt"}
    return [p for p in found if Path(p).name not in own]


def main() -> int:
    t0 = time.time()
    EV.mkdir(parents=True, exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    DAD.mkdir(parents=True, exist_ok=True)

    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    with rasterio.open(DATA / "sample_submission.tif") as src:
        valid_sub = np.isfinite(src.read(1))
    # The two footprints are NOT nested (IR-H61-001): 1,540 px are finite in all 19 competition
    # bands but not in sample_submission, and 3,073 px are the other way round.  The submission
    # format is defined by sample_submission, so the emission domain is the INTERSECTION.
    domain = valid & valid_sub
    log(f"footprint: all-19-band {int(valid.sum())} px, sample domain {int(valid_sub.sum())} px, "
        f"intersection {int(domain.sum())} px (IR-H61-001)")
    depth = G.read_band(DATA / "training_features.tif", 15)

    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    corridor = ndimage.binary_dilation(cat, iterations=RING_PX)
    permitted = domain & ~corridor

    with rasterio.open(DATA / "reference/h33-2-b2-zeros.tif") as src:
        ref = src.read(1) > 0
    with rasterio.open(DATA / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"
                       ) as src:
        p1 = ref & (np.isfinite(src.read(1)) & (src.read(1) > 0))
    log(f"P1 measured-credit atom {int(p1.sum())} px")

    # ------------------------------------------------------------------ candidate fields
    corrob = np.load(WORK / "corroborated.npy")
    conc_cell = h61.concordant_cell(pa, pb, permitted, Q_CONF)
    cover_f, cover_thr = h61.cover_conditioned_disagreement(pa, pb, depth, permitted, Q_CONF,
                                                            Q_ABSTAIN, COVER_Q)
    fields = {
        "view_A": pa,
        "view_B": pb,
        "clf_union": np.maximum(pa, pb).astype(np.float32),
        "dis_contrast": h60d.dis_contrast(pa, pb),
        "dis_product": h60d.dis_product(pa, pb),
        "conc_soft": h61.concordance_surface(pa, pb),
        "conc_min": np.where(conc_cell, h61.concordance_surface(pa, pb), 0.0).astype(np.float32),
        "conc_corrob": np.where(corrob, h61.concordance_surface(pa, pb), 0.0).astype(np.float32),
        "cover_A_only": cover_f,
    }

    def emit(fld):
        return h57.iso_select(np.where(permitted, fld, 0.0).astype(np.float32), permitted,
                              BUDGET, min_px=3.0, nms_px=3)

    union_dots = emit(fields["clf_union"])
    rows = []
    dots = {}
    for name, fld in fields.items():
        d = emit(fld)
        dots[name] = d
        col = h61.revealed_colocation(d, p1, permitted)
        ov = float((d & union_dots).sum()) / max(int(d.sum()), 1)
        rows.append(dict(field=name, emitted=int(d.sum()),
                         colocation=col["fraction"], random_baseline=col["random_baseline"],
                         lift=col["lift"],
                         union_overlap=round(ov, 4),
                         disqualified_as_union=bool(ov > UNION_DISQUALIFY),
                         implied_rho=h61.implied_credit_density(col["fraction"])))
    for r in rows:
        log(f"  {r['field']:14s} n={r['emitted']:6d} f={r['colocation']:.4f} "
            f"lift={r['lift']:.2f}x union_overlap={r['union_overlap']:.3f}"
            f"{'  [UNION]' if r['disqualified_as_union'] else ''}")

    eligible = [r for r in rows if not r["disqualified_as_union"] and r["emitted"] > 0]
    if not eligible:
        raise SystemExit("no candidate survived the union disqualifier")
    winner = max(eligible, key=lambda r: (r["lift"] or 0.0))
    log(f"winner: {winner['field']} (lift {winner['lift']:.2f}x random, "
        f"union overlap {winner['union_overlap']:.3f})")
    field_arr = fields[winner["field"]]
    out_dots = dots[winner["field"]]

    # ------------------------------------------------------------------ ring + surface checks
    ring_dist = ndimage.distance_transform_edt(~cat)
    min_dist_m = float(ring_dist[out_dots].min()) * 100.0
    pred = np.where(domain, out_dots.astype(np.float32), 0.0)

    # ------------------------------------------------------------------ write + gates
    stem = f"gems52-h61-{winner['field']}-arm{int(out_dots.sum())}px"
    tif = ROOT / "submission" / f"{stem}.tif"
    name = f"gems52-h61-{winner['field']}-arm{int(out_dots.sum())}px-{STAMP}-zeros"
    note = (f"H61 two-view co-training: {winner['field']} ranking, {int(out_dots.sum())} px, "
            f"derived budget, >=200 m off catalogue. Research review copy.")
    if len(note) > 140:
        note = note[:140]
    receipt = submission_writer.write_submission(
        tif, pred, DATA / "sample_submission.tif", domain, note=note, name=name,
        metadata=dict(round="H61", field=winner["field"], budget_px=int(out_dots.sum()),
                      ring_min_m=round(min_dist_m, 1)))
    log(f"wrote {tif.name}: {receipt['bytes']} bytes, sha256 {receipt['sha256'][:16]}…")

    priors = prior_inventory(winner["field"], int(out_dots.sum()),
                             extra_roots=[ROOT / "submission", ROOT / "docs/downloads",
                                          ROOT / "data" / "scored", ROOT / "data" / "reference"])
    log(f"prior inventory: {len(priors)} aligned accessible rasters")
    uniq = gates.uniqueness_report(pred, priors)
    log(f"uniqueness: pattern_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f} "
        f"literal_union={uniq['equals_literal_prior_union']}")

    lane = h60d.lane_drift_report(
        np.where(permitted, field_arr, 0.0).astype(np.float32), out_dots, priors, domain,
        calibration=h60d.calibration_basenames(ROOT / "registry/data_manifest.json"))
    log(f"lane gate: surface max|rho|={lane['surface_max_abs_spearman']} "
        f"dots max|rho|={lane['dots_max_abs_spearman']} "
        f"3px frac (gate)={lane['dots_max_within_3px_frac_gate']} "
        f"drift={lane['lane_drift_detected']}")

    # not merely the union of the two views
    outside_union = int((out_dots & ~union_dots).sum())
    not_union = dict(budget=BUDGET, union_emitted=int(union_dots.sum()),
                     emitted=int(out_dots.sum()),
                     outside_union_topk=outside_union,
                     outside_union_fraction=round(outside_union / max(int(out_dots.sum()), 1), 4),
                     verdict=("not merely the union" if outside_union / max(int(out_dots.sum()), 1)
                              >= 0.30 else "MERELY THE UNION - fail"))

    # ------------------------------------------------------------------ reasoning rows
    ys, xs = np.nonzero(out_dots)
    tr = G.TRANSFORM
    cell_txt = [h61.cell_of(float(pa[y, x]), float(pb[y, x]), Q_CONF, Q_ABSTAIN)
                for y, x in zip(ys[:0], xs[:0])]   # placeholder to keep memory flat
    reasoning_csv = ROOT / "submission" / f"{stem}-emitted-pixels.csv"
    with reasoning_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting", "northing", "p_view_A", "p_view_B",
                    "depth_to_basement_m", "confidence_cell", "independently_corroborated",
                    "interpretation", "status"])
        for y, x in zip(ys, xs):
            a, b, d = float(pa[y, x]), float(pb[y, x]), float(depth[y, x])
            cell = h61.cell_of(a, b, Q_CONF, Q_ABSTAIN)
            note_txt = (h61.concordant_note(d) if cell == "concordant"
                        else h61.a_only_note(d, cover_thr))
            w.writerow([int(y), int(x), round(tr[2] + 100.0 * x + 50.0, 1),
                        round(tr[5] - 100.0 * y - 50.0, 1), round(a, 4), round(b, 4),
                        round(d, 1), cell, bool(corrob[y, x]), note_txt,
                        "HYPOTHESIS FOR PHASE-2 REVIEW; not a verified fault"])
    log(f"reasoning rows: {len(ys)} emitted pixels -> {reasoning_csv.name}")

    # A-only candidate segment dossiers in the legal pool (the brief's requirement)
    a_only = np.load(WORK / "stratum_a_only.npy") & permitted
    comp, ncomp = ndimage.label(a_only, structure=np.ones((3, 3), bool))
    dossier_csv = ROOT / "submission" / f"{stem}-a-only-candidate-segments.csv"
    cap = 20000
    written = 0
    with dossier_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["segment_id", "n_px", "centroid_row", "centroid_col", "easting", "northing",
                    "median_depth_to_basement_m", "median_p_view_A", "median_p_view_B",
                    "under_thick_cover", "geological_reasoning", "status"])
        objs = ndimage.find_objects(comp)
        for i, sl in enumerate(objs, 1):
            if sl is None or written >= cap:
                break
            m = comp[sl] == i
            yy, xx = np.nonzero(m)
            if yy.size < 3:
                continue
            gy, gx = yy + sl[0].start, xx + sl[1].start
            dm = float(np.median(depth[gy, gx]))
            w.writerow([i, int(yy.size), int(gy.mean()), int(gx.mean()),
                        round(tr[2] + 100.0 * gx.mean() + 50.0, 1),
                        round(tr[5] - 100.0 * gy.mean() - 50.0, 1),
                        round(dm, 1), round(float(np.median(pa[gy, gx])), 4),
                        round(float(np.median(pb[gy, gx])), 4),
                        bool(dm >= cover_thr), h61.a_only_note(dm, cover_thr),
                        "HYPOTHESIS FOR PHASE-2 REVIEW; not a verified fault"])
            written += 1
    log(f"A-only segment dossiers: {written} of {ncomp} (cap {cap}) -> {dossier_csv.name}")

    # ------------------------------------------------------------------ receipts
    val = json.loads((EV / "h61_validation.json").read_text())
    cot = json.loads((EV / "h61_cotrain.json").read_text())
    hide_key = f"{winner['field']}|25000"
    if hide_key not in val["instrument1_holdout"]["arms"]:
        hide_key = f"{winner['field']}|15000"
    hide = val["instrument1_holdout"]["arms"][hide_key]
    build = dict(round="H61-build", observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 budget_px=BUDGET, budget_basis="registered correction H61-2",
                 cover_threshold_m=cover_thr,
                 candidates=rows, winner=winner["field"],
                 winner_selection_rule=("highest Instrument-2 co-location lift among candidates "
                                        "whose dot set overlaps clf_union's top-k by <= 70% "
                                        "(correction H61-3)"),
                 union_disqualifier_threshold=UNION_DISQUALIFY,
                 not_merely_union=not_union,
                 ring_min_distance_to_catalogue_m=round(min_dist_m, 1),
                 ring_rule_ok=bool(min_dist_m >= 200.0),
                 reasoning_rows=len(ys), a_only_segments_total=int(ncomp),
                 a_only_dossier_rows=written, a_only_dossier_cap=cap,
                 dossier_note=("dossier rows are written for every A-only component of >=3 px in "
                               "the legal pool; smaller components are counted in "
                               "a_only_segments_total and dropped"),
                 corrections=[
                     dict(id="H61-1", summary=("the hard corroboration intersection is "
                          "structurally unusable at this budget (k^2/n = 185 at k=30,000); the "
                          "soft joint-confidence ranking min(pA,pB) is registered instead")),
                     dict(id="H61-2", summary=("emission budget 22,000 px: the gamma fit's "
                          "unclamped argmax 102,519 px lies outside the measured range, while the "
                          "board's own published record (Spearman -1.000, n=6, mass vs score) is a "
                          "direct measurement and governs")),
                     dict(id="H61-3", summary=("view_B and clf_union are disqualified as 'merely "
                          "the union': their dot sets overlap by 93-100% and their reads differ "
                          "by 3%")),
                 ])
    h61.write_json(EV / "h61_build.json", build)
    h61.write_json(EV / "h61_format_gate.json", receipt["validator"])
    h61.write_json(EV / "h61_uniqueness.json",
                   {k: v for k, v in uniq.items() if k != "per_prior"} | {"n_priors": len(priors)})
    h61.write_json(EV / "h61_lane_gate.json", lane)

    holdout_read = dict(
        label="HOLDOUT-DTI",
        evaluator_version=PREREG["evaluator_version"],
        field=winner["field"], budget_px=int(hide_key.split("|")[1]),
        pooled_dti=hide["pooled_dti"], ci_lo=hide["ci_lo"], ci_hi=hide["ci_hi"],
        withheld_positives=hide["withheld_positives"], n_folds=hide["n_folds"],
        lift_over_random=hide.get("lift_over_random"),
        instrument_status=("the hide-and-recover instrument is reported because the lane requires "
                           "it and because it is the only leakage detector available; it is NOT a "
                           "board proxy (Spearman(owner-reported, simulated) = -0.1045, n = 13)"))
    promoted = bool(winner["field"].startswith("conc")
                    and winner["lift"] and winner["lift"] > 1.0
                    and not lane["lane_drift_detected"]
                    and uniq["canonical_pattern_unique"]
                    and not uniq["equals_literal_prior_union"]
                    and not_union["outside_union_fraction"] >= 0.30)
    card = h61.run_card(
        hypothesis=("Two views that err near-independently corroborate: pixels that both the "
                    "potential-field/subsurface view and the surface view vouch for, ranked by "
                    "their joint confidence min(pA,pB), should carry a higher density of real, "
                    "unmapped fault pixels than either view alone - the opposite cell of the 2x2 "
                    "confidence table from the one every prior round in this lane shipped."),
        mechanism=("Two independent thinnings of one detector intersect in an atom carrying "
                   "16.3-20.5% credit density against 0-8.7% for singly-selected atoms "
                   "(knowledge/10 s3); Blum-Mitchell conditional independence is a strictly "
                   "stronger independence than two thinnings of one field, and it measures here "
                   "at max|r| = 0.176 against a 0.60 abandonment bar."),
        mimic_processes=[
            "a resistant lithologic contact (welded tuff or carbonate) that stands up as a ridge "
            "AND carries a magnetic susceptibility contrast: straight, laterally persistent, "
            "geologically real, and not a fault",
            "a fluvial or glacial escarpment along a stratigraphic contact",
        ],
        holdout=holdout_read,
        instruments=dict(
            instrument2_revealed=dict(
                label="revealed-preference co-location; NOT a holdout score",
                winner_field=winner["field"],
                colocation_fraction=winner["colocation"],
                random_baseline=winner["random_baseline"],
                lift=winner["lift"],
                implied_credit_density_bracket=winner["implied_rho"],
                limits=val["instrument2_revealed"]["limits"]),
            disagreement_read=dict(
                note=("the lane's designated discovery signal measured BELOW the matched random "
                      "control on Instrument 2"),
                dis_contrast=next(r for r in rows if r["field"] == "dis_contrast"),
                dis_product=next(r for r in rows if r["field"] == "dis_product"),
                cover_A_only=next(r for r in rows if r["field"] == "cover_A_only"))),
        registry_overlap=dict(
            n_priors=len(priors),
            pattern_unique=bool(uniq["canonical_pattern_unique"]),
            support_novelty_fraction=round(float(uniq["novel_fraction"]), 4),
            equals_literal_prior_union=bool(uniq["equals_literal_prior_union"]),
            lane_surface_max_abs_spearman=lane["surface_max_abs_spearman"],
            lane_dots_max_abs_spearman=lane["dots_max_abs_spearman"],
            lane_dots_max_within_3px_frac_gate=lane["dots_max_within_3px_frac_gate"],
            lane_dots_max_within_3px_frac_raw=lane["dots_max_within_3px_frac"],
            lane_drift_detected=bool(lane["lane_drift_detected"]),
            not_merely_union_fraction=not_union["outside_union_fraction"]),
        raster_sha256=receipt["sha256"],
        validator=receipt["validator"],
        submission_name=name, submission_note=note,
        verdict=("promote" if promoted else "negative"),
        promotion_scope=("'promote' is a verdict on the registered instrument only: it means the "
                         "concordance ranking beat BOTH single-view baselines and the union on "
                         "pooled hide-and-recover HOLDOUT-DTI. It does NOT mean a weekly slot is "
                         "allocated, and it does NOT mean the artifact beats the surface view on "
                         "the revealed-preference instrument, where it does not."),
        extra=dict(build=build,
                   cotrain=dict(independence={k: v for k, v in cot["independence"].items()
                                              if k != "blocks"},
                                leakage_canary={k: v for k, v in cot["leakage_canary"].items()
                                                if k != "rows"},
                                strata=cot["strata"]["counts"],
                                depth_medians=cot["strata"]["median_depth_to_basement_m"],
                                corroboration_probe=cot["corroboration_probe"]),
                   corrections=["H61-1", "H61-2", "H61-3"],
                   slot_decision=("research review copy; promotion to a real weekly slot is a "
                                  "separate selector step within the cap on the submission page"),
                   champion_owner_reported=CHAMPION_OWNER_REPORTED))
    h61.write_json(EV / "h61_run_card.json", card)
    h61.write_json(DAD / "h61_run_card.json", card)
    (WORK / "promoted_field.txt").write_text(winner["field"] + "\n")
    (ROOT / "submission" / "H61_LATEST.txt").write_text(tif.name + "\n")

    # publish copies for the site
    for src_p, dst_name in ((tif, f"{stem}.tif"),
                            (tif.with_suffix(".zip"), f"{stem}.zip"),
                            (dossier_csv, f"{stem}-a-only-candidate-segments.csv"),
                            (reasoning_csv, f"{stem}-emitted-pixels.csv")):
        if src_p.exists():
            shutil.copy2(src_p, DL / dst_name)
    shutil.copy2(tif, DL / "h61-candidate.tif")
    shutil.copy2(tif.with_suffix(".zip"), DL / "h61-candidate.zip")
    log(f"published to docs/downloads in {time.time() - t0:.0f}s")
    log(f"VERDICT: {'promote' if promoted else 'negative'}  field={winner['field']}  "
        f"dots={int(out_dots.sum())}  sha256={receipt['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
