#!/usr/bin/env python3
"""One-off identifier re-wrap of the H64 GeoTIFF (round renamed from H62 before merge).

The H62 build wrote its name and note into the TIF metadata. `main` already uses the H62 name for a
different round, so the TIF is re-written with H64 identifiers. The decoded pixels must be
bit-identical to the built file; the script asserts that and records both hashes. Lane and uniqueness
results were computed on those same pixels, so they are not recomputed.
"""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, rasterio
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import submission_writer  # noqa: E402

OLD_TIF = ROOT / "docs/downloads/h64-candidate.tif"       # built file, H62 metadata (pre-rewrap)
SUBM = ROOT / "submission"
STEM = "gems52-h64-sufgate-cotrain-37600px-20261009T022631Z"
NOTE = "H64 S1 fail; exact-novel vs registry; lane DUPLICATE (70% rule); research only, do not submit"
OLD_SHA = "739a8e7c4b54436508fc2b9da6b8ddc56e44a0d1ad273dc88c07a2003637f8bb"
BUDGET = 37600
PREREG = json.loads((ROOT / "registry/h64_preregistration.json").read_text())["hypothesis_sha256"]

def main() -> int:
    assert hashlib.sha256(OLD_TIF.read_bytes()).hexdigest() == OLD_SHA, "built TIF is not the expected file"
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    footprint = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(OLD_TIF) as ds:
        pred = ds.read(1).astype(np.float32)
    assert len(NOTE) <= 140 and len(STEM) <= 140
    path = SUBM / f"{STEM}.tif"
    receipt = submission_writer.write_submission(
        path, pred, sample=ROOT / "data/sample_submission.tif", footprint=footprint,
        note=NOTE, name=STEM, metadata=dict(round="H64", preregistration=PREREG, budget=BUDGET))
    with rasterio.open(path) as ds:
        new_pred = ds.read(1)
    identical = bool(np.array_equal(pred, new_pred))
    assert identical, "pixels changed during re-wrap"
    card_p = ROOT / "evidence/h64_run_card.json"
    card = json.loads(card_p.read_text())
    card["round"] = "H64"
    card["raster"] = dict(file=path.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
                          zip_sha256=receipt["zip_sha256"])
    card["validator"] = dict(ok=receipt["validator"].get("ok"), problems=receipt["validator"].get("problems"),
                             nan_inside_footprint=receipt["validator"].get("nan_px_in_footprint",
                                                                           receipt["validator"].get("nan_count")),
                             value_range=[receipt["validator"].get("min"), receipt["validator"].get("max")],
                             crs=receipt["validator"].get("crs"), shape=receipt["validator"].get("shape"),
                             transform=receipt["validator"].get("transform"))
    card["submission_name"] = STEM
    card["note"] = NOTE
    card["note_chars"] = len(NOTE)
    card["rewrap"] = dict(
        from_sha256=OLD_SHA, to_sha256=receipt["sha256"], pixels_identical=identical,
        reason=("identifier rename H62 -> H64 before merge: main already uses the H62 name for a different round "
                "(PR #46). Decoded pixels are unchanged; lane and uniqueness results computed on the same pixels."),
        rewrapped_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    card_p.write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(file=path.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
                          pixels_identical=identical, note_chars=len(NOTE)), indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
