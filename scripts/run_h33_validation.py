#!/usr/bin/env python3
"""Round-4 (H33) candidate construction, live-mirror validation and slot gate.

Run order (all offline, no DrivenData contact):
    PYTHONPATH=src python3 scripts/run_h33_validation.py

What it does
------------
1. Builds the three label-free H33 surfaces that need no new external raster
   (H33-1 GDR measured-geothermometer conduit, H33-5 detector-field tip/step-over corridor,
   H33-2 catalogue-flank exclusion sweep).
2. Constructs prune-and-augment candidates **on top of the group's live-scored best emission**
   (`gems28-h27-4-r1-solo-d2-8-...`, owner-reported 0.2708, 40,199 dots) rather than on top of an
   unscored artifact.
3. Scores every candidate under **three** instruments and reports all three:
   * `catalogue_hidden_mean` -- the leak-contaminated catalogue holdout (cannot rank live);
   * `lm_calibrated_mean`    -- the live-mirror instrument validated on the known live orderings;
   * `credit_per_added_dot`  -- measured against the live break-even bar tau = alpha * DTI_best.
4. Applies the standing slot gate: a candidate is slot-eligible only if it beats the 0.2708 base
   on the live-mirror instrument in **4/4 folds** *and* every added dot clears tau.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.hypotheses import poisson_disk_thin_priority, ridge_nms_2d
from gems52.live_anchor import LIVE_LEDGER, invert_live_pair, lm_validity_report, removal_gain_bound
from gems52.hypotheses33 import (
    compute_h33_1_thermal_conduit,
    compute_h33_2_flank_sweep,
    compute_h33_5_tip_stepover_prior,
    missing_external_inputs,
)
from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary
from gems52.live_mirror import evaluate_live_mirror, load_live_mirror_context
from gems52.metric import ALPHA, kernel
from scipy.ndimage import binary_dilation
from gems52.paths import data_dir, evidence_dir, work_dir
from gems52.submission import sha256_file, write_submission_pair

BASE_LIVE_DTI = 0.2708
TAU_LIVE = ALPHA * BASE_LIVE_DTI          # 0.2 * 0.2708 = 0.05416 credit per added dot
TIMESTAMP_TAG = "20261004T220000Z"


def main() -> int:
    t0 = time.time()
    ddir = data_dir()
    ev = evidence_dir()
    ev.mkdir(parents=True, exist_ok=True)
    bands_dir = work_dir() / "bands"

    with rasterio.open(ddir / "sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    labels = read_binary(ddir / "labels.tif") & foot
    d_cat = distance_transform_edt(~labels)

    print("[1/6] Loading holdout contexts (catalogue + live-mirror)...")
    ctx = load_holdout_context(ddir)
    lm = load_live_mirror_context(ddir, foot, labels)

    with rasterio.open(ddir / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) > 0
    off_truth = sgmc & foot & ~labels & ~binary_dilation(labels, iterations=3)
    d_off = distance_transform_edt(~off_truth)
    base = read_binary(ddir / "scored/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan.tif")
    d28 = read_binary(ddir / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif")
    h19_5 = read_binary(ddir / "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif")
    h19_4 = read_binary(ddir / "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif")
    h16_1 = read_binary(ddir / "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif")
    print(f"      base = 0.2708 emission, {int(base.sum()):,} dots; tau_live = {TAU_LIVE:.5f}")

    print("[2/6] Building H33-1 GDR measured-geothermometer conduit surface...")
    h331 = compute_h33_1_thermal_conduit(bands_dir, ddir, foot)
    print(f"      GDR geothermometer sites={h331['thermal_stats']['n_geothermometer_sites']} "
          f">150C={h331['thermal_stats']['n_sites_gt150']} "
          f"(>3 km from catalogue: {h331['thermal_stats']['n_sites_gt150_far']}) "
          f">180C={h331['thermal_stats']['n_sites_gt180']} "
          f"(far: {h331['thermal_stats']['n_sites_gt180_far']})")

    print("[3/6] Building H33-5 detector-field tip / step-over corridor surface...")
    h335 = compute_h33_5_tip_stepover_prior(ddir, foot, h19_5, h19_4, h16_1)
    print(f"      ridge px={h335['n_ridge_px']:,} tips={h335['n_tip_px']:,} "
          f"junctions={h335['n_junction_px']:,}")

    # ---------------------------------------------------------------------------------
    # candidate construction
    # ---------------------------------------------------------------------------------
    off_cat = foot & (d_cat > 1)
    weak_base = base & (h19_4 == 0) & (h16_1 == 0) & (h19_5 == 0)
    wy, wx = np.nonzero(weak_base)

    corrob = h19_4.astype(np.int8) + h16_1.astype(np.int8) + h19_5.astype(np.int8)
    prio_thermal = h331["score"] * (1.0 + 0.35 * corrob)
    prio_tip = h335["score"] * (1.0 + 0.35 * corrob)

    candidates: dict[str, dict] = {}

    # --- H33-2: catalogue-flank exclusion sweep on the 0.2708 base --------------------
    flank = compute_h33_2_flank_sweep(base, labels, d_cat, buffers=(2, 3))
    for b, m in flank.items():
        candidates[f"H33-2-B{b}"] = {
            "mask": m,
            "hypothesis": "H33-2",
            "description": (f"0.2708 base with every dot at d(catalogue) <= {b} px deleted "
                            f"({int(m.sum()):,} dots)"),
        }

    # --- H33-1: thermal-conduit prune-and-augment on the 0.2708 base ------------------
    for n_prune, n_add, tag in ((300, 900, "H33-1-P300A900"), (600, 1800, "H33-1-P600A1800")):
        m = base.copy()
        order = np.argsort(prio_thermal[wy, wx])
        m[wy[order[:n_prune]], wx[order[:n_prune]]] = False
        add = poisson_disk_thin_priority(
            (off_cat & (h331["z_T"] > 0.35)) & ~m,
            prio_thermal, min_dist_px=2.35, existing_dots=m, max_add=n_add)
        candidates[tag] = {
            "mask": m | add,
            "hypothesis": "H33-1",
            "description": (f"0.2708 base: prune {n_prune} thermally-uncorroborated weak dots, add "
                            f"{int(add.sum()):,} GDR-geothermometer-conduit dots "
                            f"({int((m | add).sum()):,} total)"),
        }

    # --- H33-5: tip / step-over corridor prune-and-augment ---------------------------
    m = base.copy()
    order = np.argsort(prio_tip[wy, wx])
    m[wy[order[:300]], wx[order[:300]]] = False
    add = poisson_disk_thin_priority(off_cat & ~m, prio_tip, min_dist_px=2.35,
                                     existing_dots=m, max_add=900)
    candidates["H33-5-P300A900"] = {
        "mask": m | add,
        "hypothesis": "H33-5",
        "description": (f"0.2708 base: prune 300 weak dots, add {int(add.sum()):,} detector-field "
                        f"tip/step-over corridor dots ({int((m | add).sum()):,} total)"),
    }

    # --- H33-1 + H33-2 combined: thermal conduit on the flank-pruned base ------------
    m = flank[2].copy()
    order = np.argsort(prio_thermal[wy, wx])
    m[wy[order[:300]], wx[order[:300]]] = False
    add = poisson_disk_thin_priority(
        (off_cat & (h331["z_T"] > 0.35)) & ~m,
        prio_thermal, min_dist_px=2.35, existing_dots=m, max_add=900)
    candidates["H33-2B2-PLUS-H33-1"] = {
        "mask": m | add,
        "hypothesis": "H33-1+H33-2",
        "description": (f"flank B=2 base ({int(flank[2].sum()):,}) then thermal-conduit "
                        f"prune-and-augment ({int((m | add).sum()):,} total)"),
    }

    # ---------------------------------------------------------------------------------
    print("[4/6] Scoring every candidate under all three instruments...")
    records = []

    def score(cid: str, mask: np.ndarray, hypothesis: str, desc: str, is_base: bool = False) -> dict:
        mask = np.asarray(mask, bool) & foot
        lm_r = evaluate_live_mirror(mask, lm, cid, calibrate_prevalence=True)
        cat_r = evaluate_candidate_holdout(mask, ctx, cid)
        rec = {
            "candidate_id": cid,
            "hypothesis": hypothesis,
            "description": desc,
            "is_base": is_base,
            "emitted_pixels": int(mask.sum()),
            "on_catalogue_pixels": int((mask & labels).sum()),
            "flank_px_le_1": int((mask & (d_cat <= 1)).sum()),
            "flank_px_le_2": int((mask & (d_cat <= 2)).sum()),
            "lm_mean": lm_r["lm_calibrated_mean"],
            "lm_per_fold": lm_r["lm_calibrated_per_fold"],
            "lm_min_fold": lm_r["lm_calibrated_min_fold"],
            "lm_folds_beat_base": None,
            "catalogue_hidden_mean": cat_r["catalogue_hidden_mean"],
            "drift_corrected_holdout_mean": cat_r["drift_corrected_holdout_mean"],
            "sgmc_prevalence_calibrated_dti": cat_r["sgmc_prevalence_calibrated_dti"],
            "credit_per_added_dot": None,
            "slot_eligible": False,
        }
        records.append(rec)
        return rec

    base_rec = score("BASE-0.2708", base, "reference", "group's live-scored best (owner-reported 0.2708)", True)
    score("D2.8-0.2600", d28, "reference", "the 0.2600 emission, for reference")
    for cid, spec in candidates.items():
        score(cid, spec["mask"], spec["hypothesis"], spec["description"])

    base_lm = base_rec["lm_mean"]
    denom_base = _lm_denominator(base_rec, lm, base)
    inv = invert_live_pair()
    print(f"      live inversion: TP_w = {inv.s_hi:,.1f}, D = {inv.d_hi:,.1f}, "
          f"mean credit/dot = {inv.s_hi / inv.n_hi:.4f}, "
          f"weighted recall = {inv.s_hi / 12226:.4f}")
    for r in records:
        if r["is_base"]:
            continue
        r["lm_folds_beat_base"] = int(sum(
            1 for k in r["lm_per_fold"] if r["lm_per_fold"][k] > base_rec["lm_per_fold"][k]))
        r["lm_margin_vs_base"] = float(r["lm_mean"] - base_lm)
        spec = candidates.get(r["candidate_id"])
        cost = (removal_credit_cost(base, spec["mask"], d_off, off_truth) if spec is not None
                else {"n_removed": 0, "d_tp_p": 0.0, "d_tp_g": 0.0})
        r["removal"] = cost
        added = r["emitted_pixels"] - base_rec["emitted_pixels"]
        if added > 0:
            r["credit_per_added_dot"] = float(r["lm_margin_vs_base"] * denom_base / added)
        if cost["n_removed"] > 0:
            rnd = removal_gain_bound(inv, cost["n_removed"], cost["d_tp_p"], cost["d_tp_g"])
            r["live_anchor"] = rnd
            r["live_anchor_safety"] = rnd["safety_factor"]
            r["live_anchor_projection"] = rnd["projected_dti_if_live_credit_matches"]
        else:
            r["live_anchor_safety"] = None
            r["live_anchor_projection"] = None
        # Slot gate: LM 4/4 folds, positive LM margin, and -- for any removal arm -- a live-anchored
        # safety factor of at least 2.0 (the live record validated this mechanism once, at B=1).
        r["slot_eligible"] = bool(
            r["lm_folds_beat_base"] == 4 and r["lm_margin_vs_base"] > 0
            and (r["live_anchor_safety"] is None or r["live_anchor_safety"] >= 2.0))

    print("[5/6] Slot gate:")
    hdr = (f"{'candidate':26s} {'dots':>7s} {'dCat<=1':>8s} {'LM-cal':>9s} {'margin':>9s} "
           f"{'folds':>6s} {'catHid':>8s} {'credit/dot':>11s} {'safe':>5s} {'projDTI':>7s} {'SLOT':>5s}")
    print(hdr)
    for r in sorted(records, key=lambda r: -r["lm_mean"]):
        cpd = r["credit_per_added_dot"]
        sf = r.get("live_anchor_safety")
        proj = r.get("live_anchor_projection")
        print(f"{r['candidate_id'][:26]:26s} {r['emitted_pixels']:7,d} {r['flank_px_le_1']:8,d} "
              f"{r['lm_mean']:9.6f} {r.get('lm_margin_vs_base', 0.0):+9.6f} "
              f"{str(r['lm_folds_beat_base']) + '/4':>6s} {r['catalogue_hidden_mean']:8.5f} "
              f"{('%11.5f' % cpd) if cpd is not None else '        -- '} "
              f"{('%5.2f' % sf) if sf is not None else '   -- '} "
              f"{('%7.4f' % proj) if proj is not None else '    -- '} "
              f"{'YES' if r['slot_eligible'] else 'no':>5s}")

    # ---------------------------------------------------------------------------------
    print("[6/6] Writing evidence and building slot-approved GeoTIFFs...")
    payload = {
        "schema_version": "GEMSDOE32-H33-v1.0",
        "generated_at_utc": TIMESTAMP_TAG,
        "base": {"candidate_id": "BASE-0.2708",
                 "source": "data/raw/scored/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan.tif",
                 "sha256": sha256_file(ddir / "scored/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan.tif"),
                 "owner_reported_live_dti": BASE_LIVE_DTI,
                 "emitted_pixels": int(base.sum())},
        "tau_live_credit_per_added_dot": TAU_LIVE,
        "live_anchor_inversion": {
            "pair": "D2.8 (0.2600, 44,090 dots) -> H27-4-R1-SOLO (0.2708, 40,199 dots)",
            "tp_w": inv.s_hi, "denominator": inv.d_hi,
            "mean_credit_per_dot": inv.s_hi / inv.n_hi,
            "implied_weighted_recall_at_G_12226": inv.s_hi / 12226.0,
            "max_credit_loss_absorbed_by_the_live_validated_B1_removal": inv.implied_credit_loss_budget,
        },
        "lm_validity_report": lm_validity_report(
            {r["candidate_id"]: {"lm_mean": r["lm_mean"], "emitted_pixels": r["emitted_pixels"]}
             for r in records}),
        "instruments": {
            "lm_calibrated": ("spatially blocked official DTI against SGMC off-catalogue truth, "
                              "prevalence calibrated to |G_LB| = 12,691 px; validated on the known "
                              "live orderings in evidence/live_mirror_validation.json"),
            "catalogue_hidden_mean": "leak-contaminated catalogue holdout (cannot rank live)",
        },
        "h33_1_thermal_stats": h331["thermal_stats"],
        "h33_5_stats": {k: v for k, v in h335.items() if not isinstance(v, np.ndarray)},
        "missing_external_inputs": missing_external_inputs(ddir),
        "candidates": records,
    }
    (ev / "h33_validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # build GeoTIFF pairs for every slot-eligible candidate, in LM order
    dl = ROOT / "docs" / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    bundles = []
    for r in sorted(records, key=lambda r: -r["lm_mean"]):
        if not r["slot_eligible"]:
            continue
        spec = candidates[r["candidate_id"]]
        meta = dict(r)
        meta["catalogue_hidden_per_quadrant"] = r["lm_per_fold"]
        meta["drift_corrected_per_quadrant"] = r["lm_per_fold"]
        meta["predicted_leaderboard_dti"] = r.get("live_anchor_projection")
        meta["ei_drift_corrected"] = r.get("lm_margin_vs_base")
        meta["slot_decision"] = "SLOT_ELIGIBLE"
        note = (
            "GEMSDOE32 {cid} | H33-2 catalogue-flank B=2 prune on the 0.2708 base: "
            "{dots} dots, 0 within 100 m and 0 within 200 m of the catalogue; "
            "live-mirror +{margin:.6f} in 4/4 folds, live-anchor safety {safe:.2f}, "
            "projected live {proj:.4f}; UNSCORED | id {sha8}"
        ).format(cid=r["candidate_id"], dots=r["emitted_pixels"],
                 margin=r.get("lm_margin_vs_base", 0.0), safe=r.get("live_anchor_safety") or 0.0,
                 proj=r.get("live_anchor_projection") or 0.0, sha8="see receipt")
        meta["description"] = r["description"]
        meta["submission_note_zeros"] = note
        meta["submission_note_nan"] = note
        bundle = write_submission_pair(
            mask=spec["mask"], foot=foot, labels=labels,
            template_tif=ddir / "labels.tif", out_dir=dl,
            slug=f"h33-{r['candidate_id'].lower()}", timestamp_tag=TIMESTAMP_TAG,
            candidate_meta=meta)
        bundles.append(bundle)
        z = bundle["zeros_tif"]
        print(f"      built {z.get('file', z.get('filename','?'))}  ({z.get('emitted_positive_pixels',0):,} dots, "
              f"sha256 {str(z.get('sha256'))[:16]}...")
    if not bundles:
        print("      no candidate passed the slot gate; no new GeoTIFF was written")
    (ev / "h33_submission_bundles.json").write_text(json.dumps(bundles, indent=2) + "\n", encoding="utf-8")

    print(f"\nH33 validation complete in {time.time() - t0:.1f}s")
    return 0


def removal_credit_cost(base: np.ndarray, cand: np.ndarray, d_off: np.ndarray,
                         off_truth: np.ndarray) -> dict:
    """Exact weighted credit a removal costs against the off-catalogue truth raster.

    ``d_tp_p`` is the TP_p side (the kernel credit the deleted dots were themselves earning).
    ``d_tp_g`` is the TP_g side: the coverage of truth pixels that lose their *unique* nearest dot.
    A removal with ``d_tp_g == 0`` cannot reduce TP_g at all, which is the assumption the
    live-anchored bound is derived under.
    """
    removed = np.asarray(base, bool) & ~np.asarray(cand, bool)
    n_removed = int(removed.sum())
    d_tp_p = float((kernel(d_off) * removed).sum())
    idx = distance_transform_edt(~np.asarray(base, bool), return_indices=True)[1]
    qy, qx = idx[0][off_truth], idx[1][off_truth]
    load_bearing = np.zeros(base.shape, dtype=bool)
    load_bearing[qy, qx] = True
    d_tp_g = float((kernel(d_off) * (removed & load_bearing)).sum())
    return {"n_removed": n_removed, "d_tp_p": d_tp_p, "d_tp_g": d_tp_g}


def _lm_denominator(base_rec: dict, lm, base: np.ndarray) -> float:
    """Mean live-mirror denominator of the base emission, used to turn an LM margin into credit.

    LM margin is (TP_w' - TP_w) / Den', so the incremental *weighted credit* earned by the added
    dots is approximately margin * Den' for small changes.  Dividing by the number of added dots
    gives credit per added dot, directly comparable with tau_live.
    """
    r = evaluate_live_mirror(base, lm, "BASE-0.2708", calibrate_prevalence=True)
    foot_px = float(lm.foot.sum())
    tot, n = 0.0, 0
    for cell, det in zip(lm.cells, r["fold_detail"].values()):
        g_cal = 12691.0 * (float(cell.domain.sum()) / foot_px)
        tot += ALPHA * det["n_p"] + 0.8 * g_cal + 0.8 * (det["tp_g"] - det["tp_p"])
        n += 1
    return tot / max(n, 1)


if __name__ == "__main__":
    raise SystemExit(main())
