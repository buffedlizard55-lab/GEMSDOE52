#!/usr/bin/env python3
"""H76 independent re-check of the H75 GeoTIFF and of the 0.2778 arithmetic.

Purpose: re-measure, from restored bytes, every claim the H75 receipt and knowledge/49 make about the
shipped file, instead of trusting the stored JSON.  Read-only: writes one receipt, changes no candidate.

Inputs (restored by ``scripts/restore_data.py``, SHA-256 verified):
  data/sample_submission.tif   grid / CRS / transform template
  data/labels.tif              catalogue: 1 = mapped fault, 0 = labelled negative, -1 = outside domain
  data/reference/h33-2-b2-zeros.tif   the file the repo maps to the owner-reported 0.2778 (OWNER-REPORTED)
  data/scored/*.tif            12 owner-scored prior submissions (OWNER-REPORTED scores)

Labels: every number is MEASURED here (re-computed from bytes).  Scores are OWNER-REPORTED, never
ORGANIZER-CONFIRMED.  Lane statistics use the repo's own definitions (3 px disk, ``gates._disk``).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from gems52.gates import _disk  # noqa: E402  the repo's exact 3 px disk

H75 = ROOT / "submission/gems52-h75-dva-variogram-anisotropy-B-37654px-20261009T200333Z.tif"
TEMPLATE = ROOT / "data/sample_submission.tif"
LABELS = ROOT / "data/labels.tif"
REF = ROOT / "data/reference/h33-2-b2-zeros.tif"
SCORED = sorted((ROOT / "data/scored").glob("*.tif"))
OUT = ROOT / "evidence/h76_verify_h75.json"

# owner-reported (public board / owner notes), attached to scored files by name token only
REPORTED = {
    "gems19-h19-5": 0.1922, "gems19-h19-4": 0.1894, "gems16-h16-1": 0.1855,
    "gems24-h25-1-dotted-h19-5-d1-5": 0.2477, "gems24-h25-1-dotted-h19-5-d2-8": 0.2600,
    "gems27-topo-gap-closure": 0.2449, "13gems_20261001": 0.0904, "8GEMSDOE_Hedge": 0.1563,
    "gems10-h25-ctx-ridge": 0.1280, "gems10-h28-dotted-ridge": 0.1839,
    "gemsdoe-ens12-adopted": 0.1563, "gemsdoe9-PLACEHOLDER": 0.0107,
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_bin(p: Path) -> np.ndarray:
    with rasterio.open(p) as d:
        v = d.read(1)
    v = np.nan_to_num(v.astype(np.float64), nan=0.0)
    return v > 0


def phi(a: np.ndarray, b: np.ndarray, elig: np.ndarray) -> float | None:
    x = a[elig].astype(np.float64)
    y = b[elig].astype(np.float64)
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def near3(dots: np.ndarray, prior: np.ndarray) -> float:
    halo = ndi.binary_dilation(prior, structure=_disk(3.0))
    return float((dots & halo).sum()) / max(int(dots.sum()), 1)


def main() -> int:
    rec: dict = {"round": "H76", "label_scope": "MEASURED here from bytes; scores OWNER-REPORTED"}

    with rasterio.open(H75) as h, rasterio.open(TEMPLATE) as t, rasterio.open(LABELS) as lb:
        raw = h.read(1)
        lab = lb.read(1)
        rec["file"] = dict(path=str(H75.relative_to(ROOT)), bytes=H75.stat().st_size, sha256=sha256(H75),
                           dtype=h.dtypes[0], count=h.count, crs=str(h.crs), shape=list(h.shape),
                           nodata=h.nodata, compress=h.profile.get("compress"))
        rec["validator_vs_template"] = dict(
            crs_match=bool(h.crs == t.crs), shape_match=bool(h.shape == t.shape),
            transform_match=bool(h.transform == t.transform),
            transform_h75=list(h.transform)[:6], transform_template=list(t.transform)[:6])
        rec["values"] = dict(nan=int(np.isnan(raw).sum()), inf=int(np.isinf(raw).sum()),
                             unique=[float(u) for u in np.unique(raw)],
                             min=float(np.nanmin(raw)), max=float(np.nanmax(raw)),
                             ones=int((raw == 1).sum()), zeros=int((raw == 0).sum()))
        dots = raw == 1
        elig = lab != -1
        rec["values"]["ones_outside_domain"] = int((dots & ~elig).sum())
        rec["values"]["in_range_0_1"] = bool(np.nanmin(raw) >= 0 and np.nanmax(raw) <= 1)

    cat = lab == 1
    cat_dist_m = ndi.distance_transform_edt(~cat) * 100.0
    rec["catalogue"] = dict(positives=int(cat.sum()), min_dist_m_of_h75_dots=float(cat_dist_m[dots].min()),
                            median_dist_m_of_h75_dots=float(np.median(cat_dist_m[dots])),
                            h75_dots_within_200m=int((cat_dist_m[dots] <= 200.0).sum()))

    # --- the 0.2778 arithmetic (knowledge/49 section 1), re-measured -----------------------------
    ref = read_bin(REF)
    d28 = next((read_bin(p) for p in SCORED if "e56ea318" in p.name), None)
    rec["reference_0_2778"] = dict(path=str(REF.relative_to(ROOT)), sha256=sha256(REF), dots=int(ref.sum()),
                                   within_200m_of_catalogue=int((ref & (cat_dist_m <= 200)).sum()),
                                   min_dist_m=float(cat_dist_m[ref].min()))
    if d28 is not None:
        removed = d28 & ~ref
        rec["d28_0_2600_vs_ref"] = dict(
            d28_dots=int(d28.sum()), ref_subset_of_d28=bool(not (ref & ~d28).any()),
            pixels_in_d28_not_ref=int(removed.sum()),
            ring_min_dist_m=float(cat_dist_m[removed].min()) if removed.any() else None,
            ring_max_dist_m=float(cat_dist_m[removed].max()) if removed.any() else None,
            ring_median_dist_m=float(np.median(cat_dist_m[removed])) if removed.any() else None,
            ratio_removed_over_d28=float(removed.sum() / d28.sum()))
    rec["reference_0_2778"]["note"] = ("pixel-level relation to the 0.2600 file is recorded in d28_0_2600_vs_ref; "
                                       "the 0.2778 score itself is OWNER-REPORTED and not reproduced here")


    # --- ring credit density implied by the two OWNER-REPORTED scores (knowledge/49 section 1-3) -----
    # Approximation: DTI ~= T / (0.2*S + 0.8*|G|) (valid when dots are > 200 m apart; M ~= T).
    # Inputs: S(0.2600)=44,090 px, S(0.2778)=37,654 px, the same |G| for both files.  Solve T from the first
    # file, then the credit lost by deleting the 6,436 ring pixels.  |G| is the repo's measured identified
    # interval [5,949.3, 12,512.1] px (knowledge/31, IR-H61-010), not the superseded point 14,088.7.
    S0, S1, dS = 44090.0, 37654.0, 6436.0
    d0, d1 = 0.2600, 0.2778
    bounds = {}
    for G in (5949.3, 12512.1, 14088.7):
        T0 = d0 * (0.2 * S0 + 0.8 * G)
        T1 = d1 * (0.2 * S1 + 0.8 * G)
        dT = T0 - T1
        bounds[str(G)] = dict(T_before=T0, T_after=T1, ring_credit=dT, ring_credit_density=dT / dS,
                              breakeven_density_0p2_times_DTI=0.2 * d0)
    rec["ring_credit_density_implied"] = dict(
        method="approximation DTI~=T/(0.2S+0.8|G|); inputs OWNER-REPORTED scores 0.2600 and 0.2778; |G| interval from repo",
        by_G=bounds,
        read="a density below 0.2*DTI (~0.052 at 0.2600) means deleting the ring RAISES DTI; the values above are the check")

    # --- H75 against the 0.2778 reference and against every restored scored prior ---------------
    rows = []
    priors = [("ref_h33_2_b2 (0.2778, owner-reported)", ref)]
    for p in SCORED:
        priors.append((p.name, read_bin(p)))
    union = np.zeros_like(dots)
    for name, pr in priors:
        union |= pr
    for name, pr in priors:
        row = dict(prior=name, prior_sha256=sha256(next(q for q in ([REF] + SCORED) if q.name == name
                                                      or (name.startswith("ref_") and q == REF))),
                   prior_dots=int(pr.sum()),
                   shared_px=int((dots & pr).sum()),
                   identical_pattern=bool(np.array_equal(dots, pr)),
                   phi_on_eligible=phi(dots, pr, elig),
                   h75_dots_within_3px_of_prior=near3(dots, pr))
        rows.append(row)
    rec["h75_vs_priors"] = rows
    rec["h75_equals_union_of_restored_priors"] = bool(np.array_equal(dots, union))
    rec["max_phi_restored_priors"] = max(r["phi_on_eligible"] for r in rows if r["phi_on_eligible"] is not None)
    rec["max_near3px_restored_priors"] = max(r["h75_dots_within_3px_of_prior"] for r in rows)
    rec["n_restored_priors"] = len(priors)

    # Pixel-wise identity against the full 565-raster census is NOT re-run here (needs the 524 published blobs);
    # the H75 receipt records decoded_unique=true over 565 priors. This check is limited to the restored 13.
    rec["census_scope"] = ("13 restored rasters (1 reference + 12 scored). The 565-raster census is in "
                           "evidence/h75_build.json and was NOT re-run in H76.")

    # Verdicts (repo thresholds: rank 0.90, near-dot 0.70)
    # Universal-coverage probes (gates.PROBE_COVERAGE = 0.95: the prior's 3 px halo covers >=95% of the
    # eligible footprint) cannot localise a lane; the repo's policy excludes them from the informative max.
    disk = _disk(3.0)
    probe_flags = {}
    for name, pr in priors:
        cov = float(ndi.binary_dilation(pr, structure=disk)[elig].mean())
        probe_flags[name] = cov >= 0.95
    inf_near = [r["h75_dots_within_3px_of_prior"] for r in rows if not probe_flags[r["prior"]]]
    inf_phi = [r["phi_on_eligible"] for r in rows if not probe_flags[r["prior"]] and r["phi_on_eligible"] is not None]
    for r in rows:
        r["universal_coverage_probe"] = bool(probe_flags[r["prior"]])
    rec["lane_policy_check_restored_set"] = dict(
        rank_limit=0.90, near_limit=0.70,
        literal_max_near3px_all_restored=rec["max_near3px_restored_priors"],
        universal_coverage_probes=[k for k, v in probe_flags.items() if v],
        informative_max_near3px=max(inf_near), informative_max_phi=max(inf_phi),
        rank_pass_informative=bool(max(inf_phi) <= 0.90), near_pass_informative=bool(max(inf_near) <= 0.70),
        scope="13 restored rasters only; the full 565-raster census (receipt: max near 0.922, 38 offenders) "
              "is NOT re-run here and remains the authority for the lane verdict")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=float))
    print(json.dumps({k: rec[k] for k in ("file", "validator_vs_template", "values", "catalogue",
                                          "reference_0_2778", "d28_0_2600_vs_ref",
                                          "h75_equals_union_of_restored_priors",
                                          "max_phi_restored_priors", "max_near3px_restored_priors",
                                          "lane_policy_check_restored_set") if k in rec}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
