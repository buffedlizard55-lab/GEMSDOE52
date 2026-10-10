#!/usr/bin/env python3
"""Independent validator for the H88 GeoTIFF, re-derived from the bytes on disk.

Checks (each is a printed boolean, and the run exits 1 if any fails):
  single band; float32; CRS EPSG:32611; shape equal to the organiser sample; Affine transform equal to the
  sample's; no NaN inside the organiser footprint; every value finite and in [0, 1]; no positive mass outside
  the footprint; positive count equals the 37,654 budget; the ZIP holds exactly that one TIFF with identical bytes.

Writes evidence/h93_validator.json.  Usage:  python scripts/verify_h88_file.py <tif> <zip>
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_submission.tif"
BUDGET = 37654


def main(tif_arg: str, zip_arg: str) -> int:
    tif, zp = (ROOT / tif_arg).resolve(), (ROOT / zip_arg).resolve()
    checks: dict[str, bool] = {}
    with rasterio.open(SAMPLE) as ref:
        sample_footprint = np.isfinite(ref.read(1))
        ref_shape, ref_crs, ref_tf = ref.shape, str(ref.crs), tuple(float(v) for v in ref.transform)[:6]
    with rasterio.open(tif) as src:
        a = src.read(1)
        checks["single_band"] = src.count == 1
        checks["float32"] = src.dtypes[0] == "float32"
        checks["crs_matches_sample"] = str(src.crs) == ref_crs == "EPSG:32611"
        checks["shape_matches_sample"] = src.shape == ref_shape
        checks["transform_matches_sample"] = tuple(float(v) for v in src.transform)[:6] == ref_tf
        nodata_declared = src.nodata
    checks["all_finite"] = bool(np.isfinite(a).all())
    checks["no_nan_inside_footprint"] = bool(np.isfinite(a[sample_footprint]).all())
    checks["values_in_0_1"] = bool(np.nanmin(a) >= 0.0 and np.nanmax(a) <= 1.0)
    checks["binary_0_1"] = bool(np.isin(a, (0.0, 1.0)).all())
    checks["no_mass_outside_footprint"] = bool(not np.any((a > 0) & ~sample_footprint))
    positives = int((a > 0).sum())
    checks["positive_count_equals_budget"] = positives == BUDGET
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        checks["zip_single_tif_identical"] = names == [tif.name] and z.read(tif.name) == tif.read_bytes()
    result = dict(
        file=str(tif.relative_to(ROOT)), file_sha256=hashlib.sha256(tif.read_bytes()).hexdigest(),
        zip=str(zp.relative_to(ROOT)), zip_sha256=hashlib.sha256(zp.read_bytes()).hexdigest(),
        shape=list(a.shape), dtype="float32", crs="EPSG:32611", nodata_declared=nodata_declared,
        positives=positives, min=float(np.min(a)), max=float(np.max(a)),
        footprint_px=int(sample_footprint.sum()), checks=checks, all_pass=all(checks.values()),
        evidence_class="local format validation; not organiser acceptance",
    )
    (ROOT / "evidence" / "h93_validator.json").write_text(json.dumps(result, indent=2) + "\n")
    for k, v in checks.items():
        print(f"{'PASS' if v else 'FAIL'}  {k}")
    print(f"positives={positives} min={result['min']} max={result['max']} sha256={result['file_sha256']}")
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
