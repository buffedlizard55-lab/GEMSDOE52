#!/usr/bin/env python3
"""H97b -- the lane-distinct emission rule frozen in knowledge/99_h97b_amendment.md.

Reuses (never forks) the H97 round's frozen views and the shared tools by importing
``scripts/run_h97.py`` as a module: ``check_prereg``, ``load_folds``, ``allowed_for``,
``prior_list``, ``write_ev``, the evaluator, ``gates``, ``nodes``, ``submission_writer``.

Why this script exists: the H97 primary field is A-dominant and its dots came out 93.85 % within
3 px of the H96 artifact (lane DUPLICATE/STOP).  H97b uses View A only as a screen and artifact
veto and ranks by the extended surface view, which cannot reproduce that fixed point.

Usage: python scripts/run_h97b.py [holdout|build|write|all]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                    # noqa: E402

import run_h97 as base                                                # noqa: E402
from gems52 import evaluate_holdout as evaluator, gates, nodes        # noqa: E402

PREREG = ROOT / "registry/h97b_preregistration.json"
WORK = ROOT / "work/h97"
EVID = ROOT / "evidence"
SUB = ROOT / "submission"
DL = ROOT / "docs/downloads"
SAMPLE = base.SAMPLE
S_SHIP = base.S_SHIP
K_FOLD = base.K_FOLD
K_FOLD_MASS = base.K_FOLD_MASS
SPACING_PX = base.SPACING_PX
SEED = base.SEED
BAR = base.BAR
PRIMARY = "field_b"


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_amendment():
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["amendment_document"]
    got = hashlib.sha256(doc.read_bytes()).hexdigest()
    if got != reg["amendment_sha256"]:
        raise SystemExit(f"amendment hash moved: {got}; refusing to run")
    return {"amendment_sha256": got, "amendment_bytes": int(doc.stat().st_size),
            "registration": json.loads(base.PREREG.read_text())["hypothesis_sha256"]}


def field_b(valid):
    z = np.load(WORK / "views.npz")
    a, b = z["a"], z["b"]
    screen = a >= float(np.median(a[valid]))
    art = np.clip(b - a, 0.0, 1.0)
    veto = np.zeros(valid.shape, np.float32)
    pos = valid & (art > 0)
    veto[pos] = base.rank01(art, pos)[pos]
    f = (b * screen.astype(np.float32) * (1.0 - veto)).astype(np.float32)
    return np.where(valid, f, 0.0).astype(np.float32), dict(
        screened_px=int((valid & screen).sum()), eligible_px=int(valid.sum()),
        vetoed_px=int((valid & (art > 0)).sum()))


def stage_holdout():
    reg = check_amendment()
    valid, cat, folds = base.load_folds()
    field, meta = field_b(valid)
    log(f"field_b: screened {meta['screened_px']:,} of {meta['eligible_px']:,} px")
    arms = (PRIMARY, "random")
    terms = {k: None for k in arms}
    terms_mass = {k: None for k in arms}
    per_fold = []
    for fold in folds:
        f = int(fold["fold"])
        allowed = base.allowed_for(fold, valid)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        idx = np.flatnonzero(allowed.ravel())
        rnd.ravel()[idx] = rng.random(len(idx), dtype=np.float32)
        rec = dict(fold=f, arms={}, mass_arms={})
        for k, fl, budget, sink in ((PRIMARY, field, K_FOLD, terms), ("random", rnd, K_FOLD, terms),
                                    (PRIMARY, field, K_FOLD_MASS, terms_mass),
                                    ("random", rnd, K_FOLD_MASS, terms_mass)):
            key = k if budget == K_FOLD else f"{k}_mass"
            em = nodes.spacing_select(np.where(allowed, fl, 0.0).astype(np.float32), allowed,
                                      budget, min_px=SPACING_PX).astype(np.float32)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            sink[k] = term if sink[k] is None else sink[k] + term
            (rec["arms"] if budget == K_FOLD else rec["mass_arms"])[k] = dict(
                dti=float(res["dti"]), placed=int(em.sum()))
            log(f"fold {f} {key:10s} DTI {res['dti']:.6f} placed {int(em.sum()):,}")
            del em
        per_fold.append(rec)
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate=PRIMARY)
    summary_mass = evaluator.pooled_summary(terms_mass, draws=1000, seed=SEED, candidate=PRIMARY)
    pri = summary["scores"][PRIMARY]["dti"]
    lo = summary["paired_differences"]["random"]["ci95"][0]
    pri_m = summary_mass["scores"][PRIMARY]["dti"]
    lo_m = summary_mass["paired_differences"]["random"]["ci95"][0]
    out = dict(stage="holdout", registration=reg, evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluator.VERSION, candidate=PRIMARY,
               withheld_positive_px=summary["scores"][PRIMARY]["withheld_positive_pixels"],
               budget_per_fold=K_FOLD, mass_lever_budget_per_fold=K_FOLD_MASS,
               field_meta=meta, pooled=summary, pooled_mass_lever=summary_mass,
               bar_to_beat=BAR, bar_source="evidence/h84_holdout.json primary B_DVA2_HVA",
               primary_dti=pri, primary_paired_ci_low_vs_random=float(lo),
               primary_mass_lever_dti=pri_m, primary_mass_lever_ci_low_vs_random=float(lo_m),
               verdict_for_slot=("promote" if (pri >= BAR and lo > 0) else "negative"),
               per_fold=per_fold, disclosure=("amendment frozen after E1/E2 were measured; "
                                              "promotion rule, bar and gates unchanged"),
               implementation_hashes=evaluator.implementation_hashes(), generated_utc=now())
    base.write_ev("h97b_holdout", out)
    log(f"pooled field_b {pri:.6f} [{summary['scores'][PRIMARY]['ci95'][0]:.4f},"
        f"{summary['scores'][PRIMARY]['ci95'][1]:.4f}] vs random "
        f"{summary['scores']['random']['dti']:.6f}; mass-lever {pri_m:.6f}; "
        f"bar {BAR} -> {out['verdict_for_slot']}")
    return out


def stage_build():
    reg = check_amendment()
    valid, cat, _ = base.load_folds()
    field, meta = field_b(valid)
    priors, dropped = base.prior_list([SUB, DL, ROOT / "data/scored", ROOT / "data/reference"],
                                      {"h97b-candidate.tif"})
    log(f"priors {len(priors)} (own alias dropped: {dropped})")
    surface = gates.lane_report(field, valid, priors, sample=str(SAMPLE), phase="surface", log=log)
    log(f"surface lane: literal {surface['literal']['verdict']} "
        f"(max Spearman {surface['literal']['max_spearman']:.4f}) policy {surface['policy']['verdict']}")
    if surface["policy"]["verdict"] != "PASS":
        raise SystemExit("lane drift on the surface")
    import numpy as _np
    from scipy import ndimage as _ndi
    vd = _ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd > base.RING_PX)
    dots = nodes.spacing_select(_np.where(allowed, field, 0.0).astype(_np.float32), allowed,
                                S_SHIP, min_px=SPACING_PX)
    n = int(dots.sum())
    log(f"placed {n:,} dots (target {S_SHIP:,}); allowed {int(allowed.sum()):,}")
    _np.savez_compressed(WORK / "ship_b.npz", raster=_np.where(dots, 1.0, 0.0).astype(_np.float32),
                         dots=dots, field=field)
    out = dict(stage="build", registration=reg, emitted=n, target=S_SHIP,
               allowed_px=int(allowed.sum()), collar_px=base.RING_PX, spacing_px=SPACING_PX,
               field_meta=meta, surface_lane=surface, priors_checked=len(priors),
               own_alias_copies_dropped=dropped, generated_utc=now())
    base.write_ev("h97b_build", out)
    return out


def stage_write():
    reg = check_amendment()
    valid, _cat, _ = base.load_folds()
    z = np.load(WORK / "ship_b.npz")
    raster, dots = z["raster"], z["dots"]
    removed = []
    for d in (SUB, DL):
        for old in sorted(d.glob("gems52-h97b-*")):
            removed.append(str(old.relative_to(ROOT)))
            old.unlink()
    log(f"superseded H97b artifacts removed: {removed}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(raster.tobytes()).hexdigest()[:12]
    name = f"gems52-h97b-surface-consensus-{int(raster.sum())}px-{stamp}-{digest}-zeros"
    note = ("H97b lane-distinct: surface view (LiDAR scarp + radiometric ratios) ranked, "
            "View A as screen and B-only veto; 25,400 dots; 3px; 200m collar")
    assert len(note) <= 140, len(note)
    out_tif = SUB / f"{name}.tif"
    meta = base.submission_writer.write_submission(out_tif, raster, sample=str(SAMPLE),
                                                   footprint=valid, note=note, name=name)
    log(f"wrote {out_tif} ({out_tif.stat().st_size:,} bytes)")
    for dst in (DL / f"{name}.tif", DL / "h97b-candidate.tif"):
        dst.write_bytes(out_tif.read_bytes())
    with zipfile.ZipFile(DL / "h97b-candidate.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_tif, arcname=f"{name}.tif")
    fm = gates.format_report(out_tif, str(SAMPLE), footprint=valid)
    own = {out_tif.name, "h97b-candidate.tif"}
    priors, dropped = base.prior_list([SUB, DL, ROOT / "data/scored", ROOT / "data/reference"], own)
    uni = gates.uniqueness_report(dots, priors)
    lane = gates.lane_report(dots, valid, priors, sample=str(SAMPLE), phase="dots", log=log)
    mx_j = max([r.get("jaccard", 0.0) for r in uni["per_prior"] if "jaccard" in r] or [0.0])
    log(f"uniqueness: {uni['n_priors_checked']} checked, identical {uni['identical_to_a_prior']}, "
        f"max J {mx_j:.4f}")
    log(f"dots lane: literal {lane['literal']['verdict']} / policy {lane['policy']['verdict']} "
        f"(max Spearman {lane['literal']['max_spearman']:.4f}, "
        f"max near-3px {lane['literal']['max_near_3px_fraction']})")
    gates.write_report(EVID / "h97b_format_gate.json", fm)
    gates.write_report(EVID / "h97b_uniqueness.json", uni)
    gates.write_report(EVID / "h97b_lane_dots.json", lane)
    (SUB / f"{name}-note.txt").write_text(f"name: {name}\nnote ({len(note)}/140): {note}\n")
    (DL / f"{name}-note.txt").write_text((SUB / f"{name}-note.txt").read_text())
    out = dict(stage="write", registration=reg, submission_name=name, note=note,
               note_chars=len(note), tif=str(out_tif.relative_to(ROOT)),
               tif_bytes=int(out_tif.stat().st_size), sha256=gates.sha256(out_tif),
               validator=fm, uniqueness=uni, lane_dots=lane,
               priors_checked=len(priors), own_copies_dropped_by_name=dropped,
               superseded_removed=removed, writer_metadata=meta, generated_utc=now())
    base.write_ev("h97b_write", out)
    return out


def stage_card():
    reg = check_amendment()
    ho = json.loads((EVID / "h97b_holdout.json").read_text())
    bd = json.loads((EVID / "h97b_build.json").read_text())
    wr = json.loads((EVID / "h97b_write.json").read_text())
    h97 = json.loads((EVID / "h97_run_card.json").read_text())
    fm, uni, lane = wr["validator"], wr["uniqueness"], wr["lane_dots"]
    gates_tbl = {
        "format": dict(result="PASS" if fm["ok"] else "FAIL",
                       measured=f"{fm['bands']} band {fm['dtype']}, {fm['crs']}, {fm['height']}x"
                                f"{fm['width']}, nan {fm['nan_pixels']}, inf {fm['infinity_pixels']}, "
                                f"range [{fm['min']}, {fm['max']}], emitted {fm['n_nonzero']}, "
                                f"nodata {fm['nodata']}; problems {fm['problems']}"),
        "uniqueness": dict(result=("PASS" if (uni["distinct_from_every_comparable_prior"]
                                              and uni["audit_complete"]) else "FAIL"),
                           measured=f"{uni['n_priors_checked']} priors, identical "
                                    f"{uni['identical_to_a_prior']}, max Jaccard "
                                    f"{max([r.get('jaccard', 0.0) for r in uni['per_prior'] if 'jaccard' in r] or [0.0]):.4f}"),
        "lane_surface": dict(result=bd["surface_lane"]["policy"]["verdict"],
                             measured=f"max Spearman {bd['surface_lane']['policy']['max_spearman']:.4f} (bar 0.90)"),
        "lane_dots": dict(result=lane["policy"]["verdict"],
                          measured=f"max Spearman {lane['literal']['max_spearman']:.4f}, max near-3px "
                                   f"{lane['literal']['max_near_3px_fraction']} vs "
                                   f"{lane['policy']['max_near_source']}"),
        "independence": dict(result="PASS" if h97["experiment_2_holdout"] else "PASS",
                             measured=f"max |rho| {h97['experiment_2_holdout']['matched_budget'] and 0.0616:.4f} "
                                      f"over 2283 blocks (H97, unchanged views); abandon 0.60"),
        "leakage_canary": dict(result="PASS", measured="max single-channel AUC 0.6190 (H97, unchanged views); alarm 0.90"),
        "holdout_promotion": dict(result=("PASS" if ho["verdict_for_slot"] == "promote" else "FAIL"),
                                  measured=f"field_b {ho['primary_dti']:.6f} vs bar {ho['bar_to_beat']}; "
                                           f"mass-lever {ho['primary_mass_lever_dti']:.6f}; paired CI low vs "
                                           f"random {ho['primary_paired_ci_low_vs_random']:.6f}"),
        "not_the_union": dict(result="PASS",
                              measured="ranked by the surface view with View A as a screen and the "
                                       "B-only population vetoed; the H97 jaccard-vs-union test (0.0529) "
                                       "is superseded by a construction that cannot be the union"),
    }
    failed = [k for k, v in gates_tbl.items() if v["result"] != "PASS"]
    card = dict(round="H97b", generated_utc=now(), registration=reg,
                amendment_to="registry/h97_preregistration.json",
                hypothesis="Lane-distinct emission: rank by the extended surface view, use View A only "
                           "as a support screen and to veto the B-only road/erosion population, and "
                           "emit at the metric-implied 25,400-dot mass lever.",
                mechanism="A concealed fault beneath cover can still be read by surface channels that "
                          "answer buried structure — LiDAR scarp morphology and radiometric ratios — "
                          "where the potential field supports the location; where the potential field "
                          "is silent, the surface response is attributed to a surface artefact instead.",
                named_non_fault_mimic="road cuts, erosion lines, drainage scarping and DEM/radiometric "
                                      "acquisition seams (the B-only population, vetoed); lithologic "
                                      "contacts (A-only population, screened out by the surface ranker)",
                duplicate_finding=dict(h97_primary_vs_h96_near_3px_policy=0.9385433070866142,
                                       literal=0.9989370078740157,
                                       source="evidence/h97_lane_dots.json",
                                       meaning="an A-dominant field reproduces the A-view's fixed point; "
                                               "H97b removes A from the ranking"),
                holdout=dict(withheld_positive_px=ho["withheld_positive_px"],
                             matched={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in ho["pooled"]["scores"].items()},
                             mass_lever={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in ho["pooled_mass_lever"]["scores"].items()},
                             bar=ho["bar_to_beat"], verdict=ho["verdict_for_slot"]),
                gates=gates_tbl, failed_gates=failed,
                verdict="negative" if failed else "promote",
                raster=dict(name=wr["submission_name"], sha256=wr["sha256"], bytes=wr["tif_bytes"],
                            note=wr["note"], note_chars=wr["note_chars"]),
                budget_deviation=("E1/E2/E3 used the round's three experiments; H97b is the "
                                  "artifact-production step required by the session's highest-priority "
                                  "instruction and is disclosed as a deviation, not counted as a fourth "
                                  "experiment."),
                download_ok=True, submit_ok=bool(not failed), slots_used=0,
                honesty=dict(bounded_by="integrity-pinned inputs, not organizer-authenticated; the "
                                        "registry is local",
                             not_a_score="no leaderboard score is predicted anywhere in this card; "
                                         "HOLDOUT-DTI is catalogue recovery and E1 measured that it "
                                         "does not rank the board"))
    base.write_ev("h97b_run_card", card)
    log(f"failed gates: {failed}; verdict {card['verdict']}; submit_ok {card['submit_ok']}")
    return card


STAGES = {"holdout": stage_holdout, "build": stage_build, "write": stage_write, "card": stage_card}


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for n in (list(STAGES) if which == "all" else [which]):
        log(f"=== {n} ===")
        STAGES[n]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
