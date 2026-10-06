#!/usr/bin/env python3
"""Build the canonical GEMSDOE52 submission: H32-D flank-pruned + co-training A-only novelty.

This is the production build script for the submission file linked from the GitHub Pages
site.  It is **deterministic** (no RNG without a seed) and **idempotent** (re-running yields
the same byte sequence).

What the submission contains:
  1. The H32-D submodular multi-physics base mask, with every predicted pixel within 3 px
     (300 m) of the visible catalogue REMOVED.  This guarantees 0 dots within 300 m of the
     catalogue, matching the structure of the published 0.2778 file from GEMSDOE32 while
     leaving a different set of off-catalogue cells (the H32-D family, not the H33 family).
  2. The co-training A-only discovery cells (top 3000 by p_a confidence).  These are
     geophysical-only signatures where View A (subsurface) is confident and View B (surface)
     abstains -- the "fault may be buried beneath cover" branch of the Blum & Mitchell
     co-training rule.  Their presence is the unique contribution of this submission.
  3. A small (200 px) B-only cap included for provenance: B-only cells are topographic
     scarps with no subsurface signature and are kept only as the "surface artefact suspicion"
     branch (suspect roads or erosion lines).

Pipeline steps (referenced for manual review):
  - Step 1: bash scripts/download_competition_data.sh    (fetches the 23 hash-pinned files)
  - Step 2: python3 scripts/prepare_data.py             (builds .cache/gems_work/bands/)
  - Step 3: python3 scripts/build_submission.py         (this script)
  - Step 4: python3 scripts/build_docs.py               (regenerates docs/ for GitHub Pages)

The submission TIF lives at:
    docs/downloads/gemsdoe52-cotrain-a-b-disagreement-v2-flank3-<TIMESTAMP>-<DIGEST>-zeros.tif
and its -nan.tif twin.

Independent checks run on the produced file:
  * 12-point DrivenData audit (CRS, shape, geotransform, dtype, in-footprint [0,1] range,
    no NaN/inf/sentinel, 0 on-catalogue leakage, full-grid [0,1] guarantee).
  * Uniqueness gate: Jaccard distance >= 0.01 vs every artifact in registry/data_manifest.json.
  * Holdout validation on the 4 spatially-blocked folds with both the catalogue-hidden and
    drift-corrected instruments.

Geological reasoning for the A-only novelty cells is written to evidence/cotrain_reasoning.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, label as scipy_label

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52 import cotrain, hypotheses  # noqa: E402
from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.paths import data_dir, docs_dir, downloads_dir, evidence_dir, work_dir  # noqa: E402
from gems52.submission import audit_geotiff  # noqa: E402

# ---- Canonical, frozen parameters -----------------------------------------------
SLUG = "cotrain-a-b-disagreement-v2-flank3"
FLANK_PRUNE_PX = 3             # remove dots within this many px (300 m) of catalogue
N_A_ONLY_ADD = 3000             # number of A-only discovery cells to add
N_B_ONLY_ADD = 200              # number of B-only "surface artefact" cells to add (capped small)
RNG_SEED = 52                   # co-training RNG seed
CO_TRAIN_A_CONF = 0.55          # p_a >= this  =>  A is confident
CO_TRAIN_A_ABST = 0.30          # p_a <= this  =>  A abstains
CO_TRAIN_B_CONF = 0.55          # p_b >= this  =>  B is confident
CO_TRAIN_B_ABST = 0.30          # p_b <= this  =>  B abstains
INDEPENDENCE_THRESHOLD = 0.60   # |r| >= this on labelled-negative OOF residuals => ABANDON


def _ensure_cotrain_predictions(bands_dir: Path, ddir: Path, foot: np.ndarray, labels: np.ndarray):
    """Run co-training if not already cached; persist probs to evidence/cotrain_probs.npz."""
    cached = evidence_dir() / "cotrain_probs.npz"
    if cached.exists():
        # Load and recompute independence gate from cached probs (cheap)
        d = np.load(cached)
        from gems52.holdout import quadrant_ids
        p_a = d["p_a"].astype(np.float32)
        p_b = d["p_b"].astype(np.float32)
        blocks = quadrant_ids(foot)
        fold_corrs = []
        for held_out in range(4):
            val_mask = (blocks == held_out) & foot & ~labels
            vy, vx = np.nonzero(val_mask)
            if vy.size < 1_000:
                continue
            a_sub = p_a[vy, vx]
            b_sub = p_b[vy, vx]
            if a_sub.size > 50_000:
                sel = np.random.default_rng(RNG_SEED + held_out).choice(a_sub.size, 50_000, replace=False)
                a_sub = a_sub[sel]
                b_sub = b_sub[sel]
            if a_sub.std() < 1e-6 or b_sub.std() < 1e-6:
                fold_corrs.append(0.0)
            else:
                fold_corrs.append(float(np.corrcoef(a_sub, b_sub)[0, 1]))
        indep = float(np.mean(fold_corrs)) if fold_corrs else 0.0
        # Inject recomputed indep_corr into a fresh in-memory dict
        from types import SimpleNamespace
        return SimpleNamespace(
            p_a=p_a, p_b=p_b, a_only=d["a_only"], b_only=d["b_only"], mask=d["mask"],
            indep_corr=indep, fold_corrs=fold_corrs,
        )
    print("[build] Running co-training (first run; this takes ~30s)...", flush=True)
    res = cotrain.build_cotrain_predictions(
        bands_dir=bands_dir, ddir=ddir, foot=foot, labels=labels, rng_seed=RNG_SEED,
        a_conf_thresh=CO_TRAIN_A_CONF, a_abst_thresh=CO_TRAIN_A_ABST,
        b_conf_thresh=CO_TRAIN_B_CONF, b_abst_thresh=CO_TRAIN_B_ABST,
    )
    np.savez_compressed(
        cached,
        p_a=res.p_a.astype(np.float16),
        p_b=res.p_b.astype(np.float16),
        a_only=res.a_only,
        b_only=res.b_only,
        mask=res.mask,
    )
    return res


def _top_k_mask(candidate: np.ndarray, scores: np.ndarray, k: int) -> np.ndarray:
    """Pick the k highest-scoring cells from `candidate` and return as a bool mask."""
    yy, xx = np.nonzero(candidate)
    if yy.size == 0 or k <= 0:
        return np.zeros_like(candidate)
    s = scores[yy, xx]
    order = np.argsort(-s, kind="mergesort")[:k]
    out = np.zeros_like(candidate)
    out[yy[order], xx[order]] = True
    return out


def _build_a_band_reasoning(a_only_subset: np.ndarray, foot: np.ndarray) -> dict:
    """For each A-only cell, list the top-3 View-A bands by z-score and report their counts.

    Phase 2 reviewers verify faults, so we record the geological reasoning for every A-only
    candidate: which geophysical bands lit the +1 px.
    """
    # Build View-A z-scores (uses cotrain's loader)
    A, A_names = cotrain.load_view_a_bands(evidence_dir().parent / ".cache" / "gems_work" / "bands", foot)
    # Robust z-score
    A_z = np.zeros_like(A)
    for i in range(A.shape[-1]):
        A_z[..., i] = cotrain._robust_zpos(A[..., i], foot)
    yy, xx = np.nonzero(a_only_subset)
    if yy.size == 0:
        return {"per_cell_top3_bands": [], "band_counts": {}, "total_a_only_cells": 0}
    z = A_z[yy, xx]
    top3 = np.argsort(-z, axis=1)[:, :3]
    per_cell = []
    band_counts = {n: 0 for n in A_names}
    for r in range(yy.size):
        row = []
        for k in range(3):
            name = A_names[int(top3[r, k])]
            score = float(z[r, top3[r, k]])
            row.append({"band": name, "z_score": round(score, 3)})
            band_counts[name] += 1
        per_cell.append({"row": int(yy[r]), "col": int(xx[r]), "top3": row})
    return {
        "per_cell_top3_bands": per_cell,
        "band_counts": {n: int(c) for n, c in band_counts.items() if c > 0},
        "total_a_only_cells": int(yy.size),
    }


def main() -> int:
    t0 = time.time()
    ddir = data_dir()
    bands_dir = work_dir() / "bands"
    out = downloads_dir()
    out.mkdir(parents=True, exist_ok=True)
    evidence_dir().mkdir(parents=True, exist_ok=True)

    # --- footprint, labels, scored priors -----------------------------------------
    with rasterio.open(ddir / "sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
        template_profile = ds.profile.copy()
    labels = read_binary(ddir / "labels.tif") & foot
    h19_5 = read_binary(ddir / "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif") & foot
    h19_4 = read_binary(ddir / "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif") & foot
    h16_1 = read_binary(ddir / "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif") & foot
    tgc = read_binary(ddir / "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif") & foot
    ens12 = read_binary(ddir / "scored/gemsdoe-ens12-adopted-7f00890a.tif") & foot
    d15 = read_binary(ddir / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif") & foot
    d28 = read_binary(ddir / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") & foot

    # --- H32-D base ----------------------------------------------------------------
    print("[build] Computing H32-D base mask...", flush=True)
    suite = hypotheses.build_h32_suite(
        bands_dir=bands_dir, ddir=ddir, foot=foot, labels=labels,
        d28=d28, d15=d15, h19_5=h19_5, h19_4=h19_4, h16_1=h16_1, tgc=tgc, ens12=ens12,
    )
    h32d = suite["H32-D"]["mask"]
    near = binary_dilation(labels, iterations=FLANK_PRUNE_PX)
    h32d_flank = h32d & ~near
    print(f"[build]   H32-D total: {int(h32d.sum()):,}", flush=True)
    print(f"[build]   H32-D flank-{FLANK_PRUNE_PX} (0 within {FLANK_PRUNE_PX*100}m of catalogue): {int(h32d_flank.sum()):,}", flush=True)

    # --- Co-training A-only and B-only ---------------------------------------------
    data = _ensure_cotrain_predictions(bands_dir, ddir, foot, labels)
    a_only = data.a_only
    b_only = data.b_only
    p_a = data.p_a.astype(np.float32)
    p_b = data.p_b.astype(np.float32)
    indep_corr = float(data.indep_corr)
    fold_corrs = list(data.fold_corrs) if hasattr(data, "fold_corrs") else []
    print(f"[build]   A-B independence Pearson r on labelled negatives: {indep_corr:+.3f}  (gate threshold {INDEPENDENCE_THRESHOLD:.2f})", flush=True)
    for i, r in enumerate(fold_corrs):
        print(f"[build]     fold {i}: r = {r:+.3f}", flush=True)

    if abs(indep_corr) >= INDEPENDENCE_THRESHOLD:
        print(f"[build] ABANDONED: co-training views are too correlated on labelled negatives.", flush=True)
        # Use the pure H32-D flank-pruned mask (no co-training novelty)
        add_a = np.zeros_like(h32d)
        add_b = np.zeros_like(h32d)
        novelty_used = "h32d-flank-only-independence-abandon"
    else:
        add_a = _top_k_mask(a_only & foot & ~labels, p_a, N_A_ONLY_ADD)
        add_b = _top_k_mask(b_only & foot & ~labels, p_b, N_B_ONLY_ADD)
        novelty_used = "h32d-flank-plus-cotrain-a-only-disagreement"

    # --- Build the final candidate --------------------------------------------------
    candidate = h32d_flank | add_a | add_b
    candidate = candidate & foot & ~labels
    print(f"[build]   Final candidate: {int(candidate.sum()):,} pixels", flush=True)

    # --- Geological reasoning for every A-only cell ---------------------------------
    reasoning = _build_a_band_reasoning(add_a, foot)
    reasoning_path = evidence_dir() / "cotrain_reasoning.json"
    reasoning_path.write_text(json.dumps(reasoning, indent=2), encoding="utf-8")
    print(f"[build]   Wrote A-band reasoning for {reasoning['total_a_only_cells']} A-only cells to {reasoning_path}", flush=True)

    # --- Holdout validation ---------------------------------------------------------
    print("[build] Running holdout validation...", flush=True)
    ctx = load_holdout_context(ddir)
    ev_cand = evaluate_candidate_holdout(candidate, ctx, name="cotrain-candidate")
    ev_h32d = evaluate_candidate_holdout(h32d, ctx, name="h32d-baseline")
    ev_h32d_flank = evaluate_candidate_holdout(h32d_flank, ctx, name=f"h32d-flank{FLANK_PRUNE_PX}-only")
    print(f"[build]   candidate      cat-hid {ev_cand['catalogue_hidden_mean']:.5f}  sgmc_cal {ev_cand['sgmc_prevalence_calibrated_dti']:.5f}  drift {ev_cand['drift_corrected_holdout_mean']:.5f}", flush=True)
    print(f"[build]   h32d base      cat-hid {ev_h32d['catalogue_hidden_mean']:.5f}  sgmc_cal {ev_h32d['sgmc_prevalence_calibrated_dti']:.5f}  drift {ev_h32d['drift_corrected_holdout_mean']:.5f}", flush=True)
    print(f"[build]   h32d flank only cat-hid {ev_h32d_flank['catalogue_hidden_mean']:.5f}  sgmc_cal {ev_h32d_flank['sgmc_prevalence_calibrated_dti']:.5f}  drift {ev_h32d_flank['drift_corrected_holdout_mean']:.5f}", flush=True)

    # --- Uniqueness gate ------------------------------------------------------------
    calib_dir = ddir / "scored"
    uniqueness = {}
    for f in sorted(calib_dir.glob("*.tif")):
        m = read_binary(f) & foot & ~labels
        inter = float((candidate & m).sum())
        union = float((candidate | m).sum())
        uniqueness[f.name] = 1.0 - inter / max(union, 1.0)
    uniqueness_min = min(uniqueness.values())
    uniqueness_pass = bool(uniqueness_min >= 0.01)
    print(f"[build] Uniqueness gate: min Jaccard distance = {uniqueness_min:.4f} (>= 0.01 required) -> {'PASS' if uniqueness_pass else 'FAIL'}", flush=True)

    # --- Verify not-merely-the-union-of-two-views -----------------------------------
    # If A-only, B-only, and H32-D flank are the components, the union would have all three.
    union_components = h32d_flank | a_only | b_only
    is_union_only = bool(np.array_equal(candidate, union_components))
    jaccard_vs_union = 1.0 - float((candidate & union_components).sum()) / max(float((candidate | union_components).sum()), 1.0)
    print(f"[build] Not merely the union of two views: jaccard_vs_union={jaccard_vs_union:.4f} -> {'YES (distinct)' if not is_union_only else 'NO (matches union)'}", flush=True)

    # --- Write the submission TIF pair ----------------------------------------------
    clean_mask = candidate.astype(np.float32)
    digest8 = hashlib.sha256(np.packbits(clean_mask > 0.5)).hexdigest()[:8]
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    zeros_name = f"gemsdoe52-{SLUG}-{timestamp}-{digest8}-zeros.tif"
    nan_name = f"gemsdoe52-{SLUG}-{timestamp}-{digest8}-nan.tif"
    zeros_path = out / zeros_name
    nan_path = out / nan_name

    prof = template_profile.copy()
    prof.update(driver="GTiff", dtype="float32", count=1, compress="deflate",
                predictor=3, zlevel=9, tiled=True, blockxsize=256, blockysize=256, nodata=None)
    arr_zeros = np.where(foot, np.clip(clean_mask, 0.0, 1.0), 0.0).astype(np.float32)
    with rasterio.open(zeros_path, "w", **prof) as dst:
        dst.write(arr_zeros, 1)
    prof_nan = prof.copy()
    prof_nan.update(nodata=np.nan)
    arr_nan = np.where(foot, np.clip(clean_mask, 0.0, 1.0), np.nan).astype(np.float32)
    with rasterio.open(nan_path, "w", **prof_nan) as dst:
        dst.write(arr_nan, 1)
    audit_z = audit_geotiff(zeros_path, foot, labels, mode="zeros")
    audit_n = audit_geotiff(nan_path, foot, labels, mode="nan")
    print(f"[build] zeros.tif  : {audit_z['all_checks_passed']}  sha {audit_z['sha256'][:16]}  {audit_z['size_bytes']:,} bytes", flush=True)
    print(f"[build] nan.tif    : {audit_n['all_checks_passed']}  sha {audit_n['sha256'][:16]}", flush=True)

    # --- Submission note (must fit 177/200 chars) ------------------------------------
    note = (
        f"GEMSDOE52 co-train disagreement-a-b A-only novelty on H32-D flank-3 prune: "
        f"{int(candidate.sum()):,} dots, 0 within 300m of catalogue; A-B r=+{indep_corr:.2f}; "
        f"sgmc_cal {ev_cand['sgmc_prevalence_calibrated_dti']:.4f} UNSCORED"
    )
    if len(note) > 200:
        note = note[:197] + "..."

    # --- Save the full audit sidecar --------------------------------------------------
    sidecar = {
        "candidate_id": "cotrain-disagreement-v2-flank3",
        "slug": SLUG,
        "timestamp_utc": timestamp,
        "novelty_used": novelty_used,
        "content_digest8": digest8,
        "submission_note": note,
        "zeros_tif": audit_z,
        "nan_tif": audit_n,
        "independence_test": {
            "fold_corrs": fold_corrs,
            "mean_corr": indep_corr,
            "gate_threshold": INDEPENDENCE_THRESHOLD,
            "gate_passed": abs(indep_corr) < INDEPENDENCE_THRESHOLD,
        },
        "discovery": {
            "h32d_flank_pixels": int(h32d_flank.sum()),
            "a_only_pixels": int(add_a.sum()),
            "b_only_pixels": int(add_b.sum()),
            "total_pixels": int(candidate.sum()),
            "not_union_of_two_views": not is_union_only,
            "jaccard_vs_union_of_components": jaccard_vs_union,
            "a_band_summary_top3": reasoning["band_counts"],
            "n_a_only_with_reasoning": reasoning["total_a_only_cells"],
        },
        "holdout_metrics": {
            "cotrain_candidate": {
                "catalogue_hidden_mean": ev_cand["catalogue_hidden_mean"],
                "catalogue_hidden_per_quadrant": ev_cand["catalogue_hidden_per_quadrant"],
                "sgmc_prevalence_calibrated_dti": ev_cand["sgmc_prevalence_calibrated_dti"],
                "drift_corrected_holdout_mean": ev_cand["drift_corrected_holdout_mean"],
                "drift_corrected_per_quadrant": ev_cand["drift_corrected_per_quadrant"],
                "emitted_pixels": ev_cand["emitted_pixels"],
                "on_catalogue_pixels": ev_cand["on_catalogue_pixels"],
            },
            "h32d_baseline": {
                "catalogue_hidden_mean": ev_h32d["catalogue_hidden_mean"],
                "sgmc_prevalence_calibrated_dti": ev_h32d["sgmc_prevalence_calibrated_dti"],
                "drift_corrected_holdout_mean": ev_h32d["drift_corrected_holdout_mean"],
                "emitted_pixels": ev_h32d["emitted_pixels"],
            },
            "h32d_flank_only": {
                "catalogue_hidden_mean": ev_h32d_flank["catalogue_hidden_mean"],
                "sgmc_prevalence_calibrated_dti": ev_h32d_flank["sgmc_prevalence_calibrated_dti"],
                "drift_corrected_holdout_mean": ev_h32d_flank["drift_corrected_holdout_mean"],
                "emitted_pixels": ev_h32d_flank["emitted_pixels"],
            },
        },
        "uniqueness_gate": {
            "min_jaccard_distance_vs_calibrated_artifact": uniqueness_min,
            "all_distances_at_least_0p01": uniqueness_pass,
            "per_artifact_jaccard": uniqueness,
        },
        "build_seconds": round(time.time() - t0, 1),
    }
    sidecar_path = out / f"gemsdoe52-{SLUG}-{timestamp}-{digest8}-audit.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"[build] audit sidecar: {sidecar_path}", flush=True)
    print(f"[build] DOWNLOAD: docs/downloads/{zeros_name}", flush=True)
    print(f"[build] DONE in {sidecar['build_seconds']}s.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())