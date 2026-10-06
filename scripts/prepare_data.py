#!/usr/bin/env python3
"""Prepare and cache the strictly disjoint View A (subsurface/potential-field) and
View B (surface DEM/radiometrics) feature stacks from data/ into data/prepared/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52.features import build_two_view_features  # noqa: E402


def main() -> int:
    t0 = time.time()
    data_dir = ROOT / "data"
    out_dir = data_dir / "prepared"
    print("[GEMSDOE52] Building View A (Subsurface/Potential-Field) and View B (Surface DEM/Radiometrics) stacks...")
    manifest = build_two_view_features(data_dir=data_dir, out_dir=out_dir, include_external_radiometrics=True)
    manifest["elapsed_seconds"] = round(time.time() - t0, 2)
    (out_dir / "prepared_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "data" / "prepared_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "evidence").mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence" / "prepared_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"[GEMSDOE52] Prepared View A ({len(manifest['view_a_channels'])} channels) "
        f"and View B ({len(manifest['view_b_channels'])} channels) in {manifest['elapsed_seconds']}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
