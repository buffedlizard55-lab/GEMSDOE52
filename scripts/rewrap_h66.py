#!/usr/bin/env python3
"""Identifier-only re-wrap of the H66 GeoTIFF so the portal note states the verdict itself.

The build wrote the note "…research-only".  A note is the only text an uploader sees next to the file,
so for a round whose verdict is DO NOT SUBMIT the note must say that, name the failing gate, and stay
inside the 140-character limit.  The decoded pixels must be bit-identical to the built file; this
script asserts that and records both hashes, exactly as `scripts/rewrap_h64.py` did.  Nothing here
changes a verdict, a gate or a score — it re-labels bytes that were already measured.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import submission_writer                        # noqa: E402

SUB = ROOT / "submission"
NOTE = ("H66 thermal-upflow corridor 24,907px; holdout below random; lane duplicate 84% near "
        "curv_scarp; DO NOT SUBMIT")


def main() -> int:
    tifs = sorted(SUB.glob("gems52-h66-*.tif"))
    assert len(tifs) == 1, f"expected one H66 raster, found {len(tifs)}"
    tif = tifs[0]
    stem = tif.stem
    assert len(NOTE) <= 140 and len(stem) <= 140
    before = hashlib.sha256(tif.read_bytes()).hexdigest()
    side = json.loads(tif.with_suffix(".json").read_text())
    with rasterio.open(tif) as ds:
        pred = ds.read(1).astype(np.float32)
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    fp = np.isfinite(sub) & (sub > -1e38)
    decoded_before = hashlib.sha256(np.ascontiguousarray(np.nan_to_num(pred)).tobytes()).hexdigest()

    receipt = submission_writer.write_submission(
        tif, pred, ROOT / "data/sample_submission.tif", fp, note=NOTE, name=stem,
        metadata=side["metadata"])
    with rasterio.open(tif) as ds:
        after = ds.read(1).astype(np.float32)
    decoded_after = hashlib.sha256(np.ascontiguousarray(np.nan_to_num(after)).tobytes()).hexdigest()
    assert decoded_before == decoded_after, "decoded pixels changed during the re-wrap"

    side2 = json.loads(tif.with_suffix(".json").read_text())
    out = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        reason="the portal note is the only text an uploader sees next to the file; for a DO-NOT-SUBMIT "
               "round it must say so and name the failing gate",
        file=stem + ".tif",
        container_sha256_before=before, container_sha256_after=receipt["sha256"],
        decoded_pixels_sha256=decoded_after, pixels_identical=bool(decoded_before == decoded_after),
        note_before=side["note"], note_after=NOTE, note_chars=len(NOTE),
        name=stem, name_chars=len(stem),
        zip_sha256=receipt["zip_sha256"], bytes=receipt["bytes"],
        gates_not_recomputed=("lane, uniqueness, holdout, canary and format results were measured on these "
                              "same decoded pixels and are unchanged; only the container metadata differs"),
    )
    (ROOT / "evidence" / "h66_rewrap.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
