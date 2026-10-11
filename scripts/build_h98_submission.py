#!/usr/bin/env python3
"""H98 build: package, gate and publish the round's candidate (built only if the round promoted).

Reuses the shared pieces rather than forking them:
  * ``gems52.h97`` for the two views (unchanged from H97; no retuning),
  * ``gems52.nodes.spacing_select`` for placement,
  * ``gems52.gates`` for the format, uniqueness and lane gates,
  * ``scripts/build_h97_submission.py`` for the reasoning writer (``mode='b_only'``) and hashing.

Writes ``evidence/h98_build.json``, ``evidence/h98_run_card.json``, ``docs/data/submission_h98.json``,
``docs/downloads/h98-candidate.tif|zip`` and ``docs/downloads/h98-b-only-reasoning.csv.gz``.
"""
from __future__ import annotations

import csv
import gzip
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import gates, grid, h97, nodes            # noqa: E402
from build_h97_submission import build_reasoning, sha256  # noqa: E402  (shared, not copied)

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
SUB = ROOT / "submission"
DL = ROOT / "docs/downloads"
EV = ROOT / "evidence"
DAD = ROOT / "docs/data"
K = 37654
MIN_SPACING_PX = 3.0


def log(m):
    print(f"[h98-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    t0 = time.time()
    hold = json.loads((EV / "h98_holdout.json").read_text())
    if hold["verdict"] != "promote":
        raise SystemExit("H98 did not promote on the holdout; nothing is built (the protocol is explicit)")
    pooled = hold["pooled"]
    d = pooled["scores"]["h98_bonly"]
    r = pooled["scores"]["random"]
    paired = pooled["paired_differences"]["random"]
    log(f"holdout ok: {d['dti']:.6f} vs random {r['dti']:.6f}")

    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
        tform, shape = ref.transform, ref.shape
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    valid = grid.footprint_from(FEATURES, "all") & domain
    a_rank = h97.view_a(str(FEATURES), valid)
    b_rank = h97.view_b(str(FEATURES), valid)
    field = (b_rank * (1.0 - a_rank)).astype(np.float32)
    ed = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (ed > h97.RING_PX)
    em = nodes.spacing_select(field, allowed, K, min_px=MIN_SPACING_PX)
    placed = int(em.sum())
    if placed < K:
        log(f"placed {placed:,} of {K:,}; relaxing for the remainder (disclosed)")
        em = em | nodes.top_k_mask(field, allowed & ~em, K - placed)
        placed = int(em.sum())
    emitted = em.astype(np.float32)
    log(f"emitted {placed:,} dots")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = f"gems52-h98-bonly-scarp-{placed}px-{ts}"
    name = f"h98-bonly-scarp-{placed}px"
    note = (f"H98 B-confident/A-abstain DEM scarp dots, {placed}px, 3px spacing, 200m ring, "
            f"zeros-outside, lane-gated")
    note = note[:140]
    out_path = SUB / f"{stem}.tif"
    grid.write_geotiff(out_path, emitted, nodata=None)

    with rasterio.open(out_path) as c:
        arr = c.read(1)
        meta = dict(count=c.count, dtype=c.dtypes[0], shape=c.shape, crs=c.crs.to_epsg(),
                    transform=tuple(c.transform), nodata=c.nodata)
    ys, xs = np.nonzero(em)
    nn = cKDTree(np.stack([ys, xs], 1)).query(np.stack([ys, xs], 1), k=2)[0][:, 1]
    checks = dict(
        single_band=meta["count"] == 1, float32=meta["dtype"] == "float32",
        shape_match=meta["shape"] == shape, crs_match=meta["crs"] == 32611,
        transform_match=np.allclose(meta["transform"], tuple(tform), rtol=0, atol=1e-9),
        all_finite=bool(np.isfinite(arr).all()), in_0_1=bool(arr.min() >= 0 and arr.max() <= 1),
        binary=bool(np.isin(arr, [0.0, 1.0]).all()), nodata_none=meta["nodata"] is None,
        ones=int((arr == 1).sum()), budget_match=int((arr == 1).sum()) == placed,
        outside_domain_zero=bool((arr[~domain] == 0).all()),
        on_catalogue_zero=bool((arr[cat] == 0).all()),
        collar_respected=bool((arr[(ed <= h97.RING_PX) & valid] == 0).all()),
        min_spacing_px=float(nn.min()) if nn.size else None,
        spacing_ok=bool(nn.size == 0 or nn.min() >= MIN_SPACING_PX - 1e-9),
    )
    format_ok = all(v for k, v in checks.items() if isinstance(v, bool))
    if not format_ok:
        raise SystemExit(f"on-disk verification failed: {checks}")
    report = gates.format_report(out_path, SAMPLE, footprint=valid)

    site_copy = DL / "h98-candidate.tif"
    priors = [p for p in gates.find_priors([SUB, DL, ROOT / "data/scored", ROOT / "data/reference"])
              if p not in {out_path, site_copy}]
    uq = gates.uniqueness_report(emitted, priors)
    lane = gates.lane_report(emitted, valid, priors, sample=str(SAMPLE), phase="dots")
    log(f"uniqueness canonical={uq['canonical_pattern_unique']} novel={uq['novel_fraction']:.4f}")
    log(f"lane literal={lane['literal']['verdict']} policy={lane['policy']['verdict']} "
        f"max_spearman={lane['policy']['max_spearman']} max_near3px={lane['policy']['max_near_3px_fraction']}")

    em_a = nodes.spacing_select(a_rank, allowed, K, min_px=MIN_SPACING_PX)
    em_b = nodes.spacing_select(b_rank, allowed, K, min_px=MIN_SPACING_PX)
    union = em_a | em_b
    inter = int((em & union).sum())
    not_union = dict(candidate_px=int(em.sum()), union_px=int(union.sum()),
                     candidate_inside_union=inter,
                     candidate_share_inside_union=float(inter / max(placed, 1)),
                     candidate_equals_union=bool(np.array_equal(em, union)),
                     jaccard_candidate_vs_union=float(inter / max(int((em | union).sum()), 1)),
                     note="the candidate is the B-confident/A-abstains ranking's own top-K, not the "
                          "union of the single-view top-K sets")

    with rasterio.open(FEATURES) as ds:
        cover = ds.read(15).astype(np.float32)
        cover = np.where(np.isfinite(cover) & (cover > -1e38), cover, np.nan)
    with rasterio.open(ROOT / "data/external/lidar_scarp_features_u8.tif") as ds:
        names = [str(s).lower() for s in ds.descriptions]
        lidar = (ds.read(names.index("valid") + 1) > 0).astype(np.uint8) if "valid" in names else (ds.read(1) > 0).astype(np.uint8)
    cv = cover[valid]
    cover_pct = np.zeros(shape, np.float32)
    cover_pct[valid] = np.searchsorted(np.sort(cv[np.isfinite(cv)]),
                                       np.nan_to_num(cv, nan=np.nanmin(cv)), side="left") / max(int(np.isfinite(cv).sum()), 1)
    rows = build_reasoning(np.nonzero(em), a_rank, b_rank, cover, cover_pct, ed, lidar, tform, shape,
                           mode="b_only")
    DL.mkdir(parents=True, exist_ok=True)
    rpath = DL / "h98-b-only-reasoning.csv.gz"
    with gzip.open(rpath, "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    shutil.copyfile(out_path, site_copy)
    zp = out_path.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(out_path.name, date_time=(2026, 10, 10, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, out_path.read_bytes())
    shutil.copyfile(zp, DL / "h98-candidate.zip")
    sha_tif, sha_zip = sha256(out_path), sha256(zp)

    promote = bool(report["ok"] and uq["canonical_pattern_unique"] and not lane["duplicate"]
                   and hold["verdict"] == "promote")
    build = dict(
        round="H98", stage="build", evidence_class="local validation only; not organizer acceptance",
        hypothesis="the lane's second disagreement case: surface-view scarp and ridge texture where the "
                   "potential-field edge family is quiet",
        mechanism="youthful fault scarps are topographic; a fault the catalogue lacks because it was never "
                  "field-checked still has a scarp, while the potential-field edge family is blind to it",
        non_fault_confounder="roads, canals, field boundaries, stream banks and terrace edges are also "
                             "curvature maxima; the lidar scarp channel and the catalogue-distance field "
                             "are the two checks written into the reasoning file",
        holdout_dti=dict(arm="h98_bonly", dti=float(d["dti"]), ci95=[float(x) for x in d["ci95"]],
                         random_dti=float(r["dti"]),
                         paired_vs_random=[float(paired["delta"]), [float(x) for x in paired["ci95"]]],
                         evaluator=hold["evaluator_version"],
                         withheld_positive_px=hold["withheld_positive_px"]),
        screening_prior_belief="evidence/h97_channel_screen.json (proxy instrument; not promotable by itself)",
        format_checks=checks, format_ok=bool(report["ok"]),
        uniqueness=dict(canonical_pattern_unique=uq["canonical_pattern_unique"],
                        support_novelty_gate_ok=uq["support_novelty_gate_ok"],
                        novel_fraction=float(uq["novel_fraction"]),
                        relation_to_union=uq["relation_to_union"],
                        identical_to_a_prior=uq["identical_to_a_prior"],
                        n_priors_checked=int(uq["n_priors_checked"])),
        lane=dict(literal=lane["literal"]["verdict"], policy=lane["policy"]["verdict"],
                  literal_max_spearman=lane["literal"]["max_spearman"],
                  literal_max_near_3px_fraction=lane["literal"]["max_near_3px_fraction"],
                  literal_max_near_source=lane["literal"]["max_near_source"],
                  literal_rank_offenders=lane["literal"]["rank_offenders"],
                  literal_near_offenders=lane["literal"]["near_offenders"],
                  max_spearman=lane["policy"]["max_spearman"],
                  max_near_3px_fraction=lane["policy"]["max_near_3px_fraction"],
                  max_near_source=lane["policy"]["max_near_source"],
                  informative_priors=lane["policy"]["informative_priors"],
                  universal_coverage_probes=lane["policy"]["universal_coverage_probes"],
                  probe_paths=lane["policy"]["probe_paths"],
                  probe_coverage=lane["policy"]["probe_coverage"],
                  full_receipt="evidence/h98_lane_dots.json"),
        not_merely_the_union=not_union,
        submission_name=name, note=note, note_chars=len(note),
        file=str(out_path), file_bytes=out_path.stat().st_size, sha256=sha_tif,
        zip_file=str(zp), zip_sha256=sha_zip, site_download=str(site_copy),
        reasoning_rows=len(rows), verdict="promote" if promote else "negative",
        build_time_s=round(time.time() - t0, 1),
    )
    EV.joinpath("h98_build.json").write_text(json.dumps(build, indent=2, default=str) + "\n")
    EV.joinpath("h98_lane_dots.json").write_text(json.dumps(lane, indent=2, default=str) + "\n")
    DAD.joinpath("submission_h98.json").write_text(json.dumps(build, indent=2, default=str) + "\n")
    card = dict(round="H98", hypothesis=build["hypothesis"], mechanism=build["mechanism"],
                named_non_fault_process=build["non_fault_confounder"],
                holdout_dti=build["holdout_dti"], screening_prior_belief=build["screening_prior_belief"],
                correlation_overlap_vs_registry=dict(lane=build["lane"], uniqueness=build["uniqueness"],
                                                     not_merely_the_union=not_union),
                raster_sha256=sha_tif, zip_sha256=sha_zip,
                validator=dict(ok=report["ok"], problems=report["problems"], checks=checks),
                submission_name=name, note=note, slots_used=0, approved_for_weekly_slot=False,
                verdict=build["verdict"],
                limits=["screening chose the arm; the holdout instrument is independent of that choice but "
                        "measures catalogue truth, not the organizer's scored faults",
                        "the B-only arm contradicts the brief's stated prior for this case; both are recorded",
                        "no organizer receipt exists for any file in this repository"])
    EV.joinpath("h98_run_card.json").write_text(json.dumps(card, indent=2, default=str) + "\n")
    print("=" * 78)
    print(f"H98 CANDIDATE: {out_path.name}")
    print(f"  sha256 {sha_tif}\n  pixels {placed:,}\n  name   {name}\n  verdict {build['verdict'].upper()}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
