#!/usr/bin/env python3
"""Independent re-validation of the H88 GeoTIFF from disk (does not import the writer).

Checks, each recorded with its measured value:
* file sha256 equals the run card; bytes, single band, dtype float32
* CRS, shape and geotransform equal the organiser template (data/sample_submission.tif)
* every pixel finite (NaN count 0) and in [0, 1]; no value outside the footprint is positive
* positive count; dots are binary; minimum pairwise spacing among dots (must be >= 3 px)
* no dot inside the 200 m (2 px) catalogue collar of data/labels.tif
* zip archive contains exactly one GeoTIFF whose bytes equal the raster

Writes evidence/h88_independent_verify.json. Usage: python scripts/verify_h88.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
NAME = "gems52-h88-basement-step-37654px-20261010.tif"
RASTER = ROOT / "submission" / NAME
DL = ROOT / "docs/downloads/h88-candidate.tif"
ZIP = ROOT / "docs/downloads/h88-candidate.zip"
RUN_CARD = ROOT / "evidence/h88_run_card.json"


def main() -> int:
    rec: dict = {"file": str(RASTER.relative_to(ROOT))}
    raw = RASTER.read_bytes()
    rec["sha256"] = hashlib.sha256(raw).hexdigest()
    rec["bytes"] = len(raw)
    card = json.loads(RUN_CARD.read_text())
    rec["run_card_sha256"] = card["raster_sha256"]
    rec["sha256_matches_run_card"] = rec["sha256"] == card["raster_sha256"]
    rec["download_copy_identical"] = DL.exists() and DL.read_bytes() == raw
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        rec["zip_members"] = names
        member = [n for n in names if n.lower().endswith(".tif")]
        rec["zip_tif_identical"] = len(member) == 1 and z.read(member[0]) == raw
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        smp = ref.read(1)
        ref_shape, ref_crs, ref_tf = ref.shape, str(ref.crs), tuple(ref.transform)[:6]
        footprint = np.isfinite(smp) & (smp > -1e38)
    with rasterio.open(RASTER) as src:
        a = src.read(1)
        rec["count_bands"] = src.count
        rec["dtype"] = src.dtypes[0]
        rec["shape"] = [src.height, src.width]
        rec["crs"] = str(src.crs)
        rec["transform"] = list(src.transform)[:6]
        rec["nodata_tag"] = src.nodata
        rec["shape_matches_template"] = (src.height, src.width) == ref_shape
        rec["crs_matches_template"] = rec["crs"] == ref_crs
        rec["transform_matches_template"] = tuple(src.transform)[:6] == ref_tf
    rec["nan_count_all"] = int(np.isnan(a).sum())
    rec["nan_count_inside_footprint"] = int((np.isnan(a) & footprint).sum())
    rec["min"], rec["max"] = float(np.nanmin(a)), float(np.nanmax(a))
    rec["all_in_0_1"] = bool(np.nanmin(a) >= 0.0 and np.nanmax(a) <= 1.0)
    rec["values_unique"] = sorted(np.unique(a).tolist())
    rec["positive_outside_footprint"] = int(((a > 0) & ~footprint).sum())
    pos = a > 0
    rec["n_dots"] = int(pos.sum())
    rec["binary"] = bool(set(np.unique(a).tolist()) <= {0.0, 1.0})
    # minimum pairwise spacing among dots (Euclidean, pixel units; 100 m cells)
    ij = np.argwhere(pos).astype(float)
    tree = cKDTree(ij)
    d2, _ = tree.query(ij, k=2)
    nn = d2[:, 1]
    rec["nn_min_px"] = float(nn.min())
    rec["nn_median_px"] = float(np.median(nn))
    rec["spacing_at_least_3px"] = bool(nn.min() >= 3.0 - 1e-9)
    # catalogue collar: distance from every dot to the nearest labelled fault pixel
    with rasterio.open(ROOT / "data/labels.tif") as src:
        cat = src.read(1) == 1
    dcat = ndimage.distance_transform_edt(~cat)
    rec["dots_within_200m_of_catalogue"] = int((dcat[pos] <= 2.0).sum())
    rec["catalogue_positive_px"] = int(cat.sum())
    rec["validator_PASS"] = bool(
        rec["sha256_matches_run_card"] and rec["download_copy_identical"] and rec["zip_tif_identical"]
        and rec["count_bands"] == 1 and rec["dtype"] == "float32"
        and rec["shape_matches_template"] and rec["crs_matches_template"] and rec["transform_matches_template"]
        and rec["nan_count_all"] == 0 and rec["all_in_0_1"] and rec["binary"]
        and rec["positive_outside_footprint"] == 0 and rec["spacing_at_least_3px"]
        and rec["dots_within_200m_of_catalogue"] == 0)
    out = ROOT / "evidence/h88_independent_verify.json"
    out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({k: rec[k] for k in ("validator_PASS", "n_dots", "nn_min_px", "nn_median_px",
                                          "dots_within_200m_of_catalogue", "min", "max", "crs",
                                          "shape", "sha256")}, indent=1, default=str))
    return 0 if rec["validator_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
