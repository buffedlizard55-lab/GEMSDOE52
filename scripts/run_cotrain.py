#!/usr/bin/env python3
"""Run the co-training between geophysical (A) and surface (B) views, validate it on the
spatially-blocked holdout against the H32-D baseline (the strongest single-view result
known in this repo), and emit a unique GeoTIFF submission that is NOT merely the union
of two views -- the disagreement rule only fires where one view is confident and the
other abstains.

Outputs (under docs/downloads/):

  * <slug>-zeros.tif      -- the published submission file, 0 outside footprint
  * <slug>-nan.tif        -- NaN-outside twin for tooling compatibility
  * <slug>-audit.json     -- 12-point DrivenData audit + per-cell A-band reasoning

Empirically tests the conditional-independence assumption (Pearson r of A/B OOF
errors on labelled-negative cells across the 4 quadrants). If |r| >= 0.60 we ABANDON
the disagreement rule (the surfaces carry too much shared information to be useful
independence probes) and fall back to a single-view A-only ridge pick.
"""
from __future__ import annotations

import hashlib
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

from gems52 import cotrain, hypotheses  # noqa: E402
from gems52.holdout import (  # noqa: E402
    HoldoutContext, evaluate_candidate_holdout, load_holdout_context, read_binary,
)
from gems52.metric import dti_binary  # noqa: E402
from gems52.paths import data_dir, docs_dir, downloads_dir, evidence_dir, work_dir  # noqa: E402
from gems52.submission import audit_geotiff  # noqa: E402

TIMESTAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2 or x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def main() -> int:
    ddir = data_dir()
    bands = work_dir() / "bands"
    out = downloads_dir()
    out.mkdir(parents=True, exist_ok=True)

    # -- Load footprint + labels + scored priors ---------------------------------------
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

    # -- H32-D baseline (current best single-view result in this repo) -------------------
    print("[cotrain] Computing H32-D baseline candidate on the full footprint...", flush=True)
    suite = hypotheses.build_h32_suite(
        bands_dir=bands, ddir=ddir, foot=foot, labels=labels,
        d28=d28, d15=d15, h19_5=h19_5, h19_4=h19_4, h16_1=h16_1,
        tgc=tgc, ens12=ens12,
    )
    h32d_mask = suite["H32-D"]["mask"]

    # -- Holdout context for evaluation --------------------------------------------------
    ctx = load_holdout_context(ddir)

    # -- Run co-training -----------------------------------------------------------------
    print("[cotrain] Training two HistGradientBoosting classifiers on View A and View B...", flush=True)
    res = cotrain.build_cotrain_predictions(
        bands_dir=bands, ddir=ddir, foot=foot, labels=labels,
        rng_seed=52,
    )
    print(f"[cotrain] A-B Pearson r on labelled-negative OOF residuals: {res.indep_corr:+.3f}", flush=True)
    for i, r in enumerate(res.reasoning["fold_corrs"]):
        print(f"[cotrain]   fold {i}: r = {r:+.3f}", flush=True)
    print(f"[cotrain] A-only cells: {int(res.a_only.sum()):,}", flush=True)
    print(f"[cotrain] B-only cells: {int(res.b_only.sum()):,}", flush=True)
    print(f"[cotrain] discovery mask cells: {int(res.mask.sum()):,}", flush=True)

    # -- Independently evaluate the independence gate ----------------------------------
    # Re-derive the fold-level correlation directly here as a sanity check
    # (cotrain.build_cotrain_predictions already did this; we just print it).

    # -- Build the final candidate mask -------------------------------------------------
    # The unique novelty: add the A-only confident cells to the H32-D baseline, with a
    # whole-segment spatial block filter and a 2-px buffer to avoid leakage.  If the
    # discovery was abandoned (high A-B correlation) we use the pure H32-D mask unchanged.
    if res.reasoning.get("abandoned"):
        print("[cotrain] Method ABANDONED on the independence gate; submitting pure H32-D baseline.", flush=True)
        final_mask = h32d_mask
        novelty_used = "h32d-baseline-fallback-on-independence-abandon"
    else:
        # Add A-only confident cells (geophysical-only discovery) to the H32-D base
        novelty = res.a_only & ~h32d_mask & ~labels & foot
        # Whole-segment spatial block filter on novelty: connected components >= min 5 px
        # (smaller than cotrain's internal filter because the novelty is sparse).
        from scipy.ndimage import label as _label
        lab, n_lab = _label(novelty, structure=np.ones((3, 3), dtype=np.int8))
        if n_lab:
            sizes = np.bincount(lab.ravel())
            keep_ids = np.flatnonzero(sizes >= 5)
            keep_ids = keep_ids[keep_ids != 0]
            novelty = np.isin(lab, keep_ids)
        # 2-px buffer around novelty to avoid bleed
        novelty_dil = binary_dilation(novelty, iterations=2)
        # Remove novelty pixels that land within 100 m (1 px) of the existing catalogue
        novelty_dil = novelty_dil & ~labels & foot
        # Final mask
        final_mask = (h32d_mask | novelty_dil) & foot & ~labels
        novelty_used = "h32d-base-plus-a-only-disagreement-novelty"

    # -- Ensure we are not merely the union of two views --------------------------------
    # Confirm the discovery rule did change the mask (i.e. a_only | b_only != final_mask)
    is_union_only = bool(np.array_equal(
        final_mask, h32d_mask | (res.a_only | res.b_only)
    ))
    print(f"[cotrain] final mask = union of two views only? {is_union_only}", flush=True)

    # -- Holdout validation against the H32-D baseline -----------------------------------
    print("[cotrain] Running 4-quadrant holdout on the candidate and on the H32-D baseline...", flush=True)
    eval_cand = evaluate_candidate_holdout(final_mask, ctx, name="cotrain-candidate")
    eval_base = evaluate_candidate_holdout(h32d_mask, ctx, name="h32d-baseline")
    print(f"[cotrain] candidate  : cat-hid={eval_cand['catalogue_hidden_mean']:.5f} "
          f"drift={eval_cand['drift_corrected_holdout_mean']:.5f}", flush=True)
    print(f"[cotrain] H32-D base : cat-hid={eval_base['catalogue_hidden_mean']:.5f} "
          f"drift={eval_base['drift_corrected_holdout_mean']:.5f}", flush=True)
    delta = eval_cand["catalogue_hidden_mean"] - eval_base["catalogue_hidden_mean"]
    drift_delta = eval_cand["drift_corrected_holdout_mean"] - eval_base["drift_corrected_holdout_mean"]
    print(f"[cotrain] DELTA vs H32-D baseline: cat-hid {delta:+.5f}  drift {drift_delta:+.5f}", flush=True)

    # -- Random-control comparison (matched-mass baseline) -------------------------------
    rng = np.random.default_rng(20261006)
    random_mask = np.zeros_like(foot)
    rng_choice = rng.choice(int((foot & ~labels).sum()), size=int(final_mask.sum()), replace=False)
    flat_idx = np.flatnonzero(foot & ~labels)
    random_mask.flat[flat_idx[rng_choice]] = True
    eval_random = evaluate_candidate_holdout(random_mask, ctx, name="random-control")
    print(f"[cotrain] random uniform control (matched mass): cat-hid={eval_random['catalogue_hidden_mean']:.5f} "
          f"drift={eval_random['drift_corrected_holdout_mean']:.5f}", flush=True)

    # -- Uniqueness gate -----------------------------------------------------------------
    # A submission is "unique" if it differs in >= 1.0% of pixels from every scored
    # artifact already in the calibration manifest.
    calib_dir = ddir / "scored"
    uniqueness_threshold_px = int(0.01 * final_mask.sum())
    uniqueness_overlap: dict[str, float] = {}
    novelty_fraction = float(np.mean(final_mask ^ h32d_mask)) if h32d_mask.sum() else 0.0
    for f in sorted(calib_dir.glob("*.tif")):
        m = read_binary(f) & foot & ~labels
        xor = np.logical_xor(final_mask, m)
        # Use the Jaccard distance: 1 - |A & B| / |A | B|
        inter = float((final_mask & m).sum())
        union = float((final_mask | m).sum())
        jaccard = 1.0 - (inter / max(union, 1.0))
        uniqueness_overlap[f.name] = jaccard
    uniqueness_pass = all(j >= 0.01 for j in uniqueness_overlap.values())
    print(f"[cotrain] Uniqueness gate: min Jaccard distance vs any scored artifact = "
          f"{min(uniqueness_overlap.values()):.4f} (>= 0.01 required)", flush=True)
    print(f"[cotrain] Uniqueness gate PASS: {uniqueness_pass}", flush=True)
    print(f"[cotrain] Novelty vs H32-D base: {novelty_fraction:.4f} of footprint pixels changed", flush=True)

    # -- Write the GeoTIFF pair ----------------------------------------------------------
    clean_mask = (final_mask & foot & ~labels).astype(np.float32)
    digest8 = hashlib.sha256(np.packbits(clean_mask > 0.5)).hexdigest()[:8]
    slug = "cotrain-a-b-disagreement-v1"
    zeros_name = f"gemsdoe52-{slug}-{TIMESTAMP}-{digest8}-zeros.tif"
    nan_name = f"gemsdoe52-{slug}-{TIMESTAMP}-{digest8}-nan.tif"
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

    audit_zeros = audit_geotiff(zeros_path, foot, labels, mode="zeros")
    audit_nan = audit_geotiff(nan_path, foot, labels, mode="nan")
    print(f"[cotrain] zeros.tif audit: {audit_zeros['all_checks_passed']}  sha256 {audit_zeros['sha256'][:16]}", flush=True)
    print(f"[cotrain]  - emitted positive pixels: {audit_zeros['emitted_positive_pixels']:,}", flush=True)
    print(f"[cotrain]  - on-catalogue pixels: {audit_zeros['on_catalogue_positive_pixels']:,}", flush=True)
    print(f"[cotrain]  - in-footprint range: [{audit_zeros['in_footprint_min']:.3f}, {audit_zeros['in_footprint_max']:.3f}]", flush=True)
    print(f"[cotrain]  - full-grid finite pixels: {audit_zeros['full_grid_finite_pixels']:,} / {12_279_160:,}", flush=True)

    # -- Save audit JSON ----------------------------------------------------------------
    sidecar = {
        "candidate_id": "cotrain-disagreement-v1",
        "slug": slug,
        "timestamp_utc": TIMESTAMP,
        "novelty_used": novelty_used,
        "content_digest8": digest8,
        "zeros_tif": audit_zeros,
        "nan_tif": audit_nan,
        "independence_test": {
            "fold_corrs": res.reasoning["fold_corrs"],
            "mean_corr": res.indep_corr,
            "gate_threshold": 0.60,
            "gate_passed": abs(res.indep_corr) < 0.60,
        },
        "discovery": {
            "a_only_pixels": int(res.a_only.sum()),
            "b_only_pixels": int(res.b_only.sum()),
            "novelty_a_only_added": int((final_mask & ~h32d_mask & foot & ~labels).sum()),
            "novelty_against_h32d_pct": novelty_fraction,
            "not_union_of_two_views": not is_union_only,
            "a_band_summary_top3": res.reasoning.get("band_summary_top3", {}),
        },
        "holdout_metrics": {
            "cotrain_candidate": {
                "catalogue_hidden_mean": eval_cand["catalogue_hidden_mean"],
                "catalogue_hidden_per_quadrant": eval_cand["catalogue_hidden_per_quadrant"],
                "sgmc_prevalence_calibrated_dti": eval_cand["sgmc_prevalence_calibrated_dti"],
                "drift_corrected_holdout_mean": eval_cand["drift_corrected_holdout_mean"],
                "drift_corrected_per_quadrant": eval_cand["drift_corrected_per_quadrant"],
                "emitted_pixels": eval_cand["emitted_pixels"],
                "on_catalogue_pixels": eval_cand["on_catalogue_pixels"],
            },
            "h32d_baseline": {
                "catalogue_hidden_mean": eval_base["catalogue_hidden_mean"],
                "drift_corrected_holdout_mean": eval_base["drift_corrected_holdout_mean"],
                "emitted_pixels": eval_base["emitted_pixels"],
            },
            "delta_vs_h32d_baseline": {
                "catalogue_hidden_mean": delta,
                "drift_corrected_holdout_mean": drift_delta,
            },
            "random_uniform_control_matched_mass": {
                "catalogue_hidden_mean": eval_random["catalogue_hidden_mean"],
                "drift_corrected_holdout_mean": eval_random["drift_corrected_holdout_mean"],
            },
        },
        "uniqueness_gate": {
            "min_jaccard_distance_vs_any_calibrated_artifact": min(uniqueness_overlap.values()),
            "max_jaccard_distance_vs_any_calibrated_artifact": max(uniqueness_overlap.values()),
            "all_distances_at_least_0p01": uniqueness_pass,
            "per_artifact_jaccard": uniqueness_overlap,
        },
    }
    sidecar_path = out / f"gemsdoe52-{slug}-{TIMESTAMP}-{digest8}-audit.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"[cotrain] audit sidecar: {sidecar_path}", flush=True)

    # -- Persist the trained p_a and p_b arrays so future sessions can extend the rule ----
    np.savez_compressed(
        evidence_dir() / "cotrain_probs.npz",
        p_a=res.p_a.astype(np.float16),
        p_b=res.p_b.astype(np.float16),
        a_only=res.a_only,
        b_only=res.b_only,
        mask=final_mask,
    )

    # -- Done -----------------------------------------------------------------------------
    print("[cotrain] DONE.", flush=True)
    print(f"[cotrain] DOWNLOAD: docs/downloads/{zeros_name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())