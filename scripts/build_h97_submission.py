#!/usr/bin/env python3
"""H97 experiment 3: build, gate and publish the round's candidate GeoTIFF.

Design (frozen in ``registry/h97_preregistration.json`` before any fit):
  field   = the lane's disagreement field, ``gems52.h97.disagreement`` (A confident, B abstains)
  budget  = K* from ``evidence/h97_holdout.json`` (the prevalence-matched off-catalogue mass-lever
            rule); K* = 37,654 when the lever was not measured for this field
  placement = ``gems52.nodes.spacing_select`` min 3 px, catalogue ring 200 m removed
  values  = binary {0,1}, zeros outside the organiser domain, no nodata tag (the champion's own
            container, knowledge/76 §1)

Outputs
  submission/<stem>.tif|zip                     canonical artifact + one-TIFF portal zip
  docs/downloads/h97-candidate.tif|zip           the site's one-click download
  docs/downloads/h97-a-only-reasoning.csv.gz     one written reason and one falsifier per emitted dot
  evidence/h97_build.json                        full receipt (format, uniqueness, lane, overlap)
  evidence/h97_a_only_segments.json              per-segment geological reasoning summary
  docs/data/submission_h97.json                  machine-readable site receipt
  evidence/h97_run_card.json                     the brief's one-JSON run card

This script never uploads anything and never sets ``approved_for_weekly_slot``.  Promotion to a
weekly slot is a separate selector step (AGENTS.md).
"""
from __future__ import annotations

import csv
import gzip
import hashlib
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

from gems52 import gates, grid, h97, metric, nodes  # noqa: E402

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
SUB = ROOT / "submission"
DL = ROOT / "docs/downloads"
EV = ROOT / "evidence"
DAD = ROOT / "docs/data"
FALLBACK_K = 37654
MIN_SPACING_PX = 3.0
LIDAR_SCARP_STRONG = 128      # of 255, on the max-of-response-bands composite


def log(m: str) -> None:
    print(f"[h97-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def sha256(p) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def k_star() -> tuple[int, dict]:
    p = EV / "h97_holdout.json"
    if not p.exists():
        raise SystemExit("evidence/h97_holdout.json is missing; run scripts/run_h97_cotrain_holdout.py")
    d = json.loads(p.read_text())
    rule = d["k_star_rule"]
    return int(rule["k_star"]), rule


def build_reasoning(idx_yx, a_rank, b_rank, cover, cover_pct, ed_cat, lidar_scarp, lidar_valid,
                    transform, shape, mode="a_only"):
    """Per-emitted-dot written geological reason and explicit falsifier (brief requirement).

    ``mode='a_only'`` writes the brief's A-only buried-fault reasoning (H97); ``mode='b_only'`` writes
    the surface-led reasoning H98 needs (View B confident, View A abstaining), where the honest
    falsifier is a *lidar scarp* on the segment: that would mean the feature is surface-mappable and
    therefore likely already in a surface-mapped catalogue, which is the opposite of the target
    population.  One shared function, two wordings - not two forks.
    """
    from rasterio.warp import transform as warp_transform
    src_crs = rasterio.crs.CRS.from_epsg(32611)
    rows = []
    ys, xs = idx_yx
    # pixel (col, row) -> projected metres -> degrees.  The first version of this function fed *pixel*
    # indices straight into the reprojection, which printed lon -121.48 / lat 0.0 for a Nevada site:
    # a plausible-looking longitude beside a latitude of exactly zero.  Caught in the three-pass review
    # against the published CSV, not by a test; the receipt value here is the same x_utm/y_utm pair the
    # row dictionary stores, converted through the file's own affine transform in both directions.
    x_utm = transform.c + (xs.astype(np.float64) + 0.5) * transform.a \
        + (ys.astype(np.float64) + 0.5) * transform.b
    y_utm = transform.f + (xs.astype(np.float64) + 0.5) * transform.d \
        + (ys.astype(np.float64) + 0.5) * transform.e
    lon, lat = warp_transform(src_crs, "EPSG:4326", x_utm.tolist(), y_utm.tolist())
    coords_xy = np.stack([xs, ys], axis=1)
    tree = cKDTree(coords_xy)
    pairs = tree.query_pairs(r=6.0, output_type="ndarray")
    parent = np.arange(len(ys))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    comp = np.array([find(i) for i in range(len(ys))])
    _, comp_lab = np.unique(comp, return_inverse=True)
    sizes = np.bincount(comp_lab)
    nn = tree.query(coords_xy, k=2)[0][:, 1]

    for i in range(len(ys)):
        y, x = int(ys[i]), int(xs[i])
        a_v, b_v = float(a_rank[y, x]), float(b_rank[y, x])
        dep = cover[y, x]
        scarp_max = int(lidar_scarp[y, x])
        valid_here = bool(lidar_valid[y, x] > 0)
        locally_falsified = bool(scarp_max >= LIDAR_SCARP_STRONG and valid_here)
        dep_txt = f"{dep:.0f} m" if np.isfinite(dep) else "not finite at this cell"
        if mode == "b_only":
            reason = (f"Surface-view ridge or scarp texture (rank {b_v:.2f}) where the potential-field "
                      f"edge family is quiet (rank {a_v:.2f}); cover to basement {dep_txt} "
                      f"(p{100*float(cover_pct[y, x]):.0f} of the footprint). Measured interpretation "
                      f"(evidence/h97_channel_screen.json): on the prevalence-matched off-catalogue "
                      f"instrument this arm carries the strongest lane-compliant signal found in this "
                      f"session, which is the opposite of the brief's stated prior for B-only dots")
            falsifier = ("falsified if a lidar scarp feature lies within 300 m on this segment (then the "
                         "feature is surface-mappable and most likely already in the catalogue, i.e. it "
                         "is a false positive for the scored population) or if the local curvature "
                         "maximum is produced by a road, canal or field boundary rather than a scarp")
        else:
            reason = (f"A-confident potential-field edge (rank {a_v:.2f}) where the surface view abstains "
                      f"(rank {b_v:.2f}); cover to basement {dep_txt} (p{100*float(cover_pct[y, x]):.0f} of "
                      f"the footprint) is consistent with burial of the geomorphic expression")
            falsifier = (("FALSIFIED LOCALLY: the lidar scarp response reaches "
                          f"{scarp_max} (of 255) within 300 m and lidar coverage is present, so this dot's "
                          "expression is surface-mappable and likely already catalogue-mapped. " if locally_falsified
                          else f"Not falsified locally: no qualifying lidar scarp response within 300 m "
                               f"(max {scarp_max} of 255, coverage {'present' if valid_here else 'absent'}). ")
                         + "Also falsified if a mapped trace within 600 m carries the same local strike "
                           "(then this is a catalogue continuation, not a new fault)")
        rows.append(dict(
            x_utm=float(transform.c + (x + 0.5) * transform.a),
            y_utm=float(transform.f + (y + 0.5) * transform.e),
            lon=round(float(lon[i]), 6), lat=round(float(lat[i]), 6),
            row=y, col=x, segment_id=int(comp_lab[i]), segment_size=int(sizes[comp_lab[i]]),
            view_a_rank=round(a_v, 4), view_b_rank=round(b_v, 4),
            cover_depth_m=None if not np.isfinite(dep) else round(float(dep), 1),
            cover_percentile=round(float(cover_pct[y, x]), 4),
            distance_to_catalogue_m=round(float(ed_cat[y, x] * 100.0), 1),
            lidar_scarp_max_3px=scarp_max,
            lidar_valid=int(valid_here),
            locally_falsified_by_lidar=int(locally_falsified),
            nn_dot_distance_px=round(float(nn[i]), 3),
            geological_reason=reason, explicit_falsifier=falsifier,
            named_confounders="lithologic contact or intrusive margin; palaeo-channel thalweg; "
                              "playa or salina edge",
        ))
    seg_path = EV / "h97_a_only_segments.json"
    seg_path.write_text(json.dumps(dict(
        n_dots=len(ys), n_segments=int(len(sizes)),
        segment_size_histogram={str(int(s)): int(c) for s, c in zip(*np.unique(sizes, return_counts=True))},
        largest_segments=int(sizes.max()) if len(sizes) else 0,
        note="segments are dots chained at 6 px for review grouping only; every dot carries its own "
             "written reason and falsifier in docs/downloads/h97-a-only-reasoning.csv.gz",
    ), indent=2) + "\n")
    return rows


def main() -> int:
    t0 = time.time()
    K, rule = k_star()
    log(f"K* = {K:,} from rule {json.dumps(rule)}")

    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
        tform, shape = ref.transform, ref.shape
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    feat_valid = grid.footprint_from(FEATURES, "all")
    eligible = feat_valid & domain
    log(f"eligible {int(eligible.sum()):,} px; catalogue {int(cat.sum()):,} px")

    a_rank = h97.view_a(str(FEATURES), eligible)
    b_rank = h97.view_b(str(FEATURES), eligible)
    field = h97.disagreement(a_rank, b_rank, eligible)
    ed_cat = ndi.distance_transform_edt(~cat)
    allowed = eligible & ~cat & (ed_cat > h97.RING_PX)
    log(f"allowed (off-catalogue, >200 m) {int(allowed.sum()):,} px")

    em = nodes.spacing_select(field, allowed, K, min_px=MIN_SPACING_PX)
    placed = int(em.sum())
    if placed < K:
        log(f"spacing_select placed {placed:,} of {K:,}; relaxing spacing for the remainder "
            f"(disclosed, not silent)")
        extra = nodes.top_k_mask(field, allowed & ~em, K - placed)
        em = em | extra
        placed = int(em.sum())
    emitted = em.astype(np.float32)
    log(f"emitted {placed:,} dots")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = f"gems52-h97-cotrain-disagree-sparse-{placed}px-{ts}"
    name = f"h97-cotrain-sparse-{placed}px"
    note = (f"H97 co-train A-conf/B-abstain, {placed}px, 3px spacing, 200m ring, "
            f"budget from prevalence-matched off-cat, zeros-outside")
    note = note[:140]
    out_path = SUB / f"{stem}.tif"
    grid.write_geotiff(out_path, emitted, nodata=None)
    log(f"wrote {out_path}")

    # ---- on-disk verification (independent re-read) ----------------------------------------
    with rasterio.open(out_path) as c:
        arr = c.read(1)
        meta = dict(count=c.count, dtype=c.dtypes[0], shape=c.shape, crs=c.crs.to_epsg(),
                    transform=tuple(c.transform), nodata=c.nodata)
    with rasterio.open(SAMPLE) as r:
        ref_meta = dict(shape=r.shape, crs=r.crs.to_epsg(), transform=tuple(r.transform))
    ys, xs = np.nonzero(em)
    tree = cKDTree(np.stack([ys, xs], axis=1))
    nn = tree.query(np.stack([ys, xs], axis=1), k=2)[0][:, 1]
    checks = dict(
        single_band=meta["count"] == 1, float32=meta["dtype"] == "float32",
        shape_match=meta["shape"] == ref_meta["shape"], crs_match=meta["crs"] == ref_meta["crs"] == 32611,
        transform_match=np.allclose(meta["transform"], ref_meta["transform"], rtol=0, atol=1e-9),
        all_finite=bool(np.isfinite(arr).all()), in_0_1=bool(arr.min() >= 0 and arr.max() <= 1),
        binary=bool(np.isin(arr, [0.0, 1.0]).all()), nodata_none=meta["nodata"] is None,
        ones=int((arr == 1).sum()), budget_match=int((arr == 1).sum()) == placed,
        outside_domain_zero=bool((arr[~domain] == 0).all()),
        on_catalogue_zero=bool((arr[cat] == 0).all()),
        collar_respected=bool((arr[(ed_cat <= h97.RING_PX) & eligible] == 0).all()),
        min_spacing_px=float(nn.min()) if nn.size else None,
        spacing_ok=bool(nn.size == 0 or nn.min() >= MIN_SPACING_PX - 1e-9),
    )
    format_ok = all(v for k, v in checks.items() if isinstance(v, bool))
    log(f"format checks {'PASS' if format_ok else 'FAIL'}: {json.dumps({k: v for k, v in checks.items() if isinstance(v, bool)})}")
    if not format_ok:
        raise SystemExit("on-disk verification failed")

    report = gates.format_report(out_path, SAMPLE, footprint=eligible)
    log(f"gates.format_report ok={report['ok']} problems={report['problems']}")

    # ---- uniqueness / lane ------------------------------------------------------------------
    site_copy = DL / "h97-candidate.tif"
    priors = [p for p in gates.find_priors([SUB, DL, ROOT / "data/scored", ROOT / "data/reference"])
              if p not in {out_path, site_copy}]
    log(f"uniqueness inventory {len(priors)} priors")
    uq = gates.uniqueness_report(emitted, priors)
    log(f"uniqueness: canonical_pattern_unique={uq['canonical_pattern_unique']} "
        f"novel_fraction={uq['novel_fraction']:.4f} gate_ok={uq['support_novelty_gate_ok']} "
        f"relation={uq['relation_to_union']}")
    lane = gates.lane_report(emitted, eligible, priors, sample=str(SAMPLE), phase="dots")
    log(f"lane literal={lane['literal']['verdict']} policy={lane['policy']['verdict']} "
        f"max_spearman={lane['policy']['max_spearman']} "
        f"max_near3px={lane['policy']['max_near_3px_fraction']} "
        f"probes={lane['policy']['universal_coverage_probes']}")

    # ---- not merely the union of the two views ----------------------------------------------
    k_union = K
    em_a = nodes.spacing_select(a_rank, allowed, k_union, min_px=MIN_SPACING_PX)
    em_b = nodes.spacing_select(b_rank, allowed, k_union, min_px=MIN_SPACING_PX)
    union = em_a | em_b
    inter = int((em & union).sum())
    not_union = dict(
        candidate_px=int(em.sum()), single_A_px=int(em_a.sum()), single_B_px=int(em_b.sum()),
        union_px=int(union.sum()),
        candidate_inside_union=int(inter),
        candidate_share_inside_union=float(inter / max(int(em.sum()), 1)),
        candidate_equals_union=bool(np.array_equal(em, union)),
        jaccard_candidate_vs_union=float(inter / max(int((em | union).sum()), 1)),
        note="the candidate is the disagreement field's own top-K, not the union of the single-view "
             "top-K sets; the share inside the union quantifies how much of it the two views alone "
             "would have produced")
    log(f"not-union: {json.dumps(not_union)}")

    # ---- A-only reasoning (brief requirement) ----------------------------------------------
    with rasterio.open(FEATURES) as ds:
        cover = ds.read(15).astype(np.float32)
        cover = np.where(np.isfinite(cover) & (cover > -1e38), cover, np.nan)
    with rasterio.open(ROOT / "data/external/lidar_scarp_features_u8.tif") as ds:
        names = [str(s).lower() for s in ds.descriptions]
        # the scarp-response composite is the max of the eight response bands; the old code read the
        # `valid` (coverage) band and labelled it "lidar_scarp", which is why the CSV could say a scarp
        # was present at a dot where there is only lidar coverage
        response = [i for i, n in enumerate(names) if n in
                    ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
                     "upface_max", "cross_max")]
        lidar_scarp = ds.read(response[0] + 1)
        for i in response[1:]:
            lidar_scarp = np.maximum(lidar_scarp, ds.read(i + 1))
        lidar_scarp = ndi.maximum_filter(lidar_scarp, size=7)      # 3 px radius = 300 m
        lidar_valid = ds.read(names.index("valid") + 1) if "valid" in names else np.ones_like(lidar_scarp)
    cv = cover[eligible]
    cover_pct = np.zeros(shape, np.float32)
    cover_pct[eligible] = np.searchsorted(np.sort(cv[np.isfinite(cv)]),
                                          np.nan_to_num(cv, nan=np.nanmin(cv) if np.isfinite(cv).any() else 0.0),
                                          side="left") / max(int(np.isfinite(cv).sum()), 1)
    rows = build_reasoning(np.nonzero(em), a_rank, b_rank, cover, cover_pct, ed_cat,
                           lidar_scarp, lidar_valid, tform, shape)
    DL.mkdir(parents=True, exist_ok=True)
    rpath = DL / "h97-a-only-reasoning.csv.gz"
    with gzip.open(rpath, "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log(f"wrote {rpath} ({len(rows):,} dots, {rpath.stat().st_size/1e6:.2f} MB gz)")

    # ---- site copies + zip ------------------------------------------------------------------
    shutil.copyfile(out_path, site_copy)
    zp = out_path.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(out_path.name, date_time=(2026, 10, 10, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, out_path.read_bytes())
    with zipfile.ZipFile(zp) as z:
        if z.namelist() != [out_path.name] or z.read(out_path.name) != out_path.read_bytes():
            raise IOError("single-TIFF ZIP roundtrip failed")
    shutil.copyfile(zp, DL / "h97-candidate.zip")
    reasoning_copy = DL / "h97-a-only-reasoning.csv.gz"
    # the CSV is written straight into the site download directory, so the "site copy" step is a
    # self-copy there; guard it instead of crashing at the very end of a completed build
    if rpath.resolve() != reasoning_copy.resolve():
        shutil.copyfile(rpath, reasoning_copy)

    sha_tif, sha_zip = sha256(out_path), sha256(zp)
    holdout = json.loads((EV / "h97_holdout.json").read_text())
    pooled = holdout["instrument1"]["pooled"]
    d = pooled["scores"]["h97_disagree"]
    r = pooled["scores"]["random"]
    paired = pooled["paired_differences"]["random"]
    verdict = ("promote" if (report["ok"] and uq["canonical_pattern_unique"]
                             and not lane["duplicate"] and rule["k_star"] < FALLBACK_K
                             and paired["ci95"][0] > 0) else "negative")

    build = dict(
        round="H97", stage="build", evidence_class="local validation only; not organizer acceptance",
        hypothesis="co-training disagreement (A confident, B abstains) with the emitted budget chosen "
                   "on a prevalence-matched off-catalogue instrument",
        mechanism="density/susceptibility edges with no surface expression = structure buried under "
                  "cover, i.e. the population the surface-mapped catalogue is least likely to hold",
        non_fault_confounder="lithologic contacts and intrusive margins; palaeo-channel thalwegs; "
                             "playa/salina edges; anthropogenic linears (roads, canals)",
        k_star=K, k_star_rule=rule,
        holdout_dti=dict(arm="h97_disagree", dti=float(d["dti"]), ci95=[float(x) for x in d["ci95"]],
                         evaluator=holdout["evaluator_version"],
                         withheld_positive_px=holdout["instrument1"]["withheld_positive_px"],
                         random_dti=float(r["dti"]), paired_vs_random=[float(paired["delta"]),
                                                                       [float(x) for x in paired["ci95"]]]),
        instrument2=holdout["instrument2"]["mass_lever"],
        independence=holdout["independence"]["receipt"]["tests"],
        format_checks=checks, format_ok=bool(report["ok"]),
        uniqueness=dict(canonical_pattern_unique=uq["canonical_pattern_unique"],
                        support_novelty_gate_ok=uq["support_novelty_gate_ok"],
                        novel_fraction=float(uq["novel_fraction"]),
                        relation_to_union=uq["relation_to_union"],
                        n_priors_checked=int(uq["n_priors_checked"]),
                        identical_to_a_prior=uq["identical_to_a_prior"]),
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
                  full_receipt="evidence/h97_lane_dots.json"),
        not_merely_the_union=not_union,
        submission_name=name, note=note, note_chars=len(note),
        file=str(out_path), file_bytes=out_path.stat().st_size, sha256=sha_tif,
        zip_file=str(zp), zip_sha256=sha_zip,
        site_download=str(site_copy), reasoning_rows=len(rows),
        verdict=verdict, build_time_s=round(time.time() - t0, 1),
    )
    EV.joinpath("h97_build.json").write_text(json.dumps(build, indent=2, default=str) + "\n")
    EV.joinpath("h97_lane_dots.json").write_text(json.dumps(lane, indent=2, default=str) + "\n")
    DAD.mkdir(parents=True, exist_ok=True)
    DAD.joinpath("submission_h97.json").write_text(json.dumps(build, indent=2, default=str) + "\n")

    run_card = dict(
        round="H97", hypothesis=build["hypothesis"], mechanism=build["mechanism"],
        named_non_fault_process=build["non_fault_confounder"],
        holdout_dti=dict(value=build["holdout_dti"]["dti"], ci95=build["holdout_dti"]["ci95"],
                         evaluator=build["holdout_dti"]["evaluator"],
                         withheld_positive_px=build["holdout_dti"]["withheld_positive_px"],
                         evidence_class="HOLDOUT-DTI"),
        instrument2_mass_lever={str(k): dict(dti=v["dti"], random_dti=v["random_dti"],
                                             credit_per_dot=v["credit_per_dot"])
                                for k, v in build["instrument2"].items()},
        correlation_overlap_vs_registry=dict(lane=build["lane"], uniqueness=build["uniqueness"],
                                             not_merely_the_union=build["not_merely_the_union"]),
        raster_sha256=sha_tif, zip_sha256=sha_zip,
        validator=dict(ok=report["ok"], problems=report["problems"], checks=checks),
        submission_name=name, note=note, slots_used=0, approved_for_weekly_slot=False,
        verdict=verdict,
        limits=["holdout truth is catalogue faults, not the organizer's scored new faults",
                "instrument 2's truth is SGMC-mapped faults absent from the catalogue, a proxy",
                "no organizer receipt exists for any file in this repository"],
    )
    EV.joinpath("h97_run_card.json").write_text(json.dumps(run_card, indent=2, default=str) + "\n")

    print("=" * 78)
    print(f"H97 CANDIDATE: {out_path.name}")
    print(f"  sha256   {sha_tif}")
    print(f"  pixels   {placed:,}   K* {K:,}   spacing >= {checks['min_spacing_px']:.2f} px")
    print(f"  name     {name}")
    print(f"  note     {note}")
    print(f"  verdict  {verdict.upper()}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
