#!/usr/bin/env python3
"""H86 build: the PRE-REGISTERED holdout candidate `h86_spaced`, written as a competition GeoTIFF.

This is exactly the arm named PRIMARY in ``scripts/run_h86_holdout.py`` (H83 structural-concordance
+ geothermal combiner, metric-aware 3 px spacing, 200 m collar), emitted once on the FULL catalogue
at the full budget of 37,654 dots (the same budget as the 0.2778 reference). No post-hoc arm swap.

Outputs (all written, then re-read and verified by the script):
  submission/gems52-h86-h83conc-spaced-37654px-<UTC>.tif   (the candidate, binary {0,1}, float32)
  evidence/h86_build.json                                   (decode-level validator + uniqueness)

Writer: ``gems52.grid.write_geotiff`` with ``nodata=None`` and all-finite zeros outside the footprint,
the same container as ``data/reference/h33-2-b2-zeros.tif`` (deflate, no nodata). See README H86 block.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rasterio  # noqa: E402

import run_h83_structural_concordance as H83  # noqa: E402  shared H83 functions, not a copy
from gems52 import gates, grid, nodes  # noqa: E402

BUDGET = 37654
MIN_PX = 3.0
RING_PX = 2
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
WELLS = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
SUBMISSION_DIR = ROOT / "submission"
EVIDENCE = ROOT / "evidence/h86_build.json"


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
        ref_meta = (ref.count, ref.dtypes[0], ref.shape, ref.crs.to_epsg(), tuple(ref.transform))
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    feat_valid = H83.footprint_all_bands(str(FEATURES))
    eligible = feat_valid & domain

    conc, grav_rank, mag_rank, dem_rank, conc_count = H83.compute_structural_concordance(str(FEATURES), eligible)
    geo = H83.compute_geothermal_density(H83.load_well_spring_data(str(WELLS)), eligible, sigma_px=15.0)
    field = H83.combine_signals(conc, conc_count, grav_rank, mag_rank, dem_rank, geo, eligible, labels)

    # Full-catalogue 200 m collar, Euclidean (same rule as the holdout runner's allowed_for)
    vd = ndi.distance_transform_edt(~cat)
    allowed = eligible & ~cat & (vd > RING_PX)
    em = nodes.spacing_select(field, allowed, BUDGET, min_px=MIN_PX).astype(np.float32)
    n = int(em.sum())
    if n != BUDGET:
        raise SystemExit(f"placed {n} != budget {BUDGET}")
    # shared helper takes a binary MASK (it calls np.nonzero itself); passing coordinates was a bug
    stats = nodes.spacing_stats(em.astype(bool))
    if stats.get("p10_px", 0) < MIN_PX - 1e-9 or stats.get("median_px", 0) < MIN_PX - 1e-9:
        raise SystemExit(f"spacing violated: {stats}")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"h86-h83conc-spaced-{BUDGET}px-{ts}"
    path = SUBMISSION_DIR / f"gems52-{name}.tif"
    note = ("H86 H83 concordance+geotherm, 3px spacing, 200m catalogue collar, binary 0/1; "
            "holdout ~random; research only")
    if len(note) > 140:
        raise SystemExit(f"note too long: {len(note)}")

    receipt = grid.write_geotiff(path, em, nodata=None)

    # ---- decode-level verification from disk (independent of the writer's own re-read) ----
    with rasterio.open(path) as c:
        a = c.read(1)
        meta = (c.count, c.dtypes[0], c.shape, c.crs.to_epsg(), tuple(c.transform))
        nodata = c.nodata
    checks = dict(
        single_band=meta[0] == 1, float32=meta[1] == "float32", shape_match=meta[2] == ref_meta[2],
        crs_match=meta[3] == ref_meta[3] == 32611, transform_match=np.allclose(meta[4], ref_meta[4], rtol=0, atol=1e-6),
        all_finite=bool(np.isfinite(a).all()), in_0_1=bool(a.min() >= 0 and a.max() <= 1),
        binary=bool(np.isin(a, [0.0, 1.0]).all()), nodata_none=nodata is None,
        ones=int((a == 1).sum()), budget_exact=int((a == 1).sum()) == BUDGET,
        outside_domain_zero=bool((a[~domain] == 0).all()),
        on_catalogue_zero=bool((a[cat] == 0).all()),
        collar_respected=bool((a[(vd <= RING_PX)] == 0).all()),
    )
    checks["PASS"] = all(checks.values())
    if not checks["PASS"]:
        raise SystemExit(f"validator FAILED: {checks}")

    priors = gates.find_priors([ROOT / "submission", ROOT / "docs/downloads", ROOT / "data/scored",
                                ROOT / "data/reference"], exclude=path)
    sha = sha256_file(path)
    priors = [p for p in priors if sha256_file(p) != sha]  # drop byte-identical self-copies
    uniq = gates.uniqueness_report(a, priors)
    uniq_keep = {k: uniq[k] for k in ["n_priors_checked", "n_priors_compared", "identical_to_a_prior",
                                      "distinct_from_every_comparable_prior", "audit_complete",
                                      "equals_literal_prior_union", "novel_fraction", "union_px",
                                      "ok", "relation_to_union", "candidate_decoded_sha256"]}

    ref_pathz = ROOT / "data/reference/h33-2-b2-zeros.tif"
    with rasterio.open(ref_pathz) as r:
        rv = r.read(1)
    ref_overlap = dict(
        cells_shared_with_h33_2_b2=int(((a == 1) & (rv == 1)).sum()),
        jaccard_with_h33_2_b2=float(((a == 1) & (rv == 1)).sum() / max(int(((a == 1) | (rv == 1)).sum()), 1)),
        cells_within_200m_of_catalogue=int(((a == 1) & (vd <= RING_PX)).sum()),
        min_catalogue_distance_m=float(vd[a == 1].min() * 100.0),
        median_catalogue_distance_m=float(np.median(vd[a == 1]) * 100.0),
        share_within_300m_of_catalogue=float(((vd[a == 1]) <= 3.0).mean()),
    )

    out = dict(
        round="H86", name=name, note=note, note_chars=len(note), file=str(path.relative_to(ROOT)),
        file_bytes=path.stat().st_size, sha256=sha, decoded_sha256=uniq["candidate_decoded_sha256"],
        writer_receipt={k: receipt[k] for k in receipt if k in ("bytes", "sha256", "shape", "dtype", "crs")} if isinstance(receipt, dict) else str(receipt),
        spacing_stats=stats, validator=checks, uniqueness=uniq_keep, overlap_with_reference=ref_overlap,
        method=dict(family="H83 structural concordance (grav/mag/DEM structure tensor, 3 scales) x geothermal density",
                    arm="h86_spaced", budget=BUDGET, min_spacing_px=MIN_PX, collar_px=RING_PX,
                    catalogue_for_collar="full catalogue (submission-time only; holdout used visible-only)"),
        holdout_reference="evidence/h86_holdout.json (HOLDOUT-DTI, pooled, 60,894 withheld positives)",
        elapsed_seconds=round(time.time() - t0, 1),
    )
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps(dict(file=out["file"], sha256=sha, validator_PASS=checks["PASS"], ones=checks["ones"],
                          uniq_ok=uniq_keep["ok"], distinct=uniq_keep["distinct_from_every_comparable_prior"],
                          identical=uniq_keep["identical_to_a_prior"], novel_fraction=uniq_keep["novel_fraction"],
                          n_priors=uniq_keep["n_priors_compared"], note_chars=len(note)), indent=2, default=float))


if __name__ == "__main__":
    main()
