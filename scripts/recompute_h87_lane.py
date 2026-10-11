#!/usr/bin/env python3
"""Recompute the H87 lane reading against the current full registry (receipt-only, no fit).

The H87 lane receipt was first written by ``scripts/eval_h87_holdout.py`` during the round that
measured H87 (IR-H88-003).  Two corrections landed afterwards and both change the lane's inputs:

* IR-H88-005: the lane's eligible domain is the shared feature store's valid mask, not "every finite
  pixel", and a round's own publisher copies (``docs/downloads/<round>-candidate.tif`` and the
  canonical name) must never be fed back in -- an artefact compared with its own bytes reports
  ``identical``/Spearman 1.0 for every round.
* IR-H88-007: prior registry growth (this round's files) and the restored scored/reference rasters.

The lane needs only the shipped raster, the eligible mask, the prior list and the grid template, so it
is recomputed here without touching the (expensive) feature store.  The holdout numbers themselves stay
in ``evidence/h87_holdout.json`` and are asserted consistent with this reading.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates                                                            # noqa: E402

EVID = ROOT / "evidence"
SAMPLE = ROOT / "data/sample_submission.tif"
STORE = ROOT / "work/r2/features"
H87_FILE = ROOT / "submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif"
PREFIX = "gems52-h87-"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    eligible = np.load(STORE / "valid.npy").astype(bool)
    with rasterio.open(H87_FILE) as ds:
        file_dots = ds.read(1).astype(np.float32)
    if file_dots.shape != eligible.shape:
        raise SystemExit("H87 raster does not match the feature-store grid")

    priors = sorted((ROOT / "data/scored").glob("*.tif"))
    ref_champ = ROOT / "data/reference/h33-2-b2-zeros.tif"
    if ref_champ.exists():
        priors.append(ref_champ)
    priors += [q for q in sorted((ROOT / "submission").glob("*.tif")) if not q.name.startswith(PREFIX)]
    priors += [q for q in sorted((ROOT / "docs/downloads").glob("*.tif")) if not q.name.startswith(PREFIX)]
    # IR-H88-005: never compare the artefact with its own copies.
    cand_sha, cand_size = sha256(H87_FILE), H87_FILE.stat().st_size
    priors = [q for q in priors
              if not (q.stat().st_size == cand_size and sha256(q) == cand_sha)]

    t0 = time.time()
    dots = gates.lane_report(file_dots, eligible, priors, sample=str(SAMPLE), phase="dots")
    surface = gates.lane_report(file_dots, eligible, priors, sample=str(SAMPLE), phase="surface")
    print(f"H87 lane recomputed in {time.time()-t0:.1f}s: registry {len(priors)}, "
          f"dots literal {dots['literal']['verdict']} / policy {dots['policy']['verdict']}, "
          f"surface literal {surface['literal']['verdict']} / policy {surface['policy']['verdict']}",
          flush=True)

    hold = json.loads((EVID / "h87_holdout.json").read_text())
    g = hold["gate"]
    if g["lane_dots_policy"] != dots["policy"]["verdict"] or g["lane_surface_policy"] != surface["policy"]["verdict"]:
        raise SystemExit("recomputed lane verdicts disagree with evidence/h87_holdout.json")

    out = dict(stage="lane_full_registry", round="H87", recomputed_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               instrument=dots["instrument"], registry_size=len(priors),
               eligible_px=int(eligible.sum()), eligible_mask_source="work/r2/features/valid.npy (store.valid)",
               candidate=str(H87_FILE.relative_to(ROOT)), candidate_sha256=sha256(H87_FILE),
               gates_sha256=sha256(ROOT / "src/gems52/gates.py"),
               note=("lane-only recomputation (scripts/recompute_h87_lane.py) with the corrected eligible mask "
                     "and the artefact's own publisher copies excluded; holdout numbers remain in "
                     "evidence/h87_holdout.json and were asserted consistent with this reading"),
               dots=dots, surface=surface)
    (EVID / "h87_lane_full_registry.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    print("wrote evidence/h87_lane_full_registry.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
