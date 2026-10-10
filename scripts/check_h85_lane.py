#!/usr/bin/env python3
"""H85 lane / uniqueness gate: surface (before placement) and final dots (after placement).

Uses the shared ``gems52.gates.lane_report`` (literal + policy verdicts) and
``gates.uniqueness_report`` against every comparable prior raster. Writes evidence/h85_lane.json.
Lane thresholds are the registry's (registry/h61_preregistration.json): rank correlation > 0.90 or
> 70 % of dots within 3 px of one registry raster => DUPLICATE/STOP.
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

import run_h83_structural_concordance as H83  # noqa: E402
from gems52 import gates  # noqa: E402

CAND = Path(sys.argv[1]).resolve()
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
WELLS = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
OUT = ROOT / "evidence/h85_lane.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def slim(rep):
    """Keep every scalar and every per-prior row (the receipt must show the maximum, not a guess)."""
    keep = {}
    for k, v in rep.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            keep[k] = v
        elif isinstance(v, list) and all(not isinstance(x, (list, dict)) for x in v):
            keep[k] = v[:50]
        elif isinstance(v, list) and k == "per_prior":
            keep[k] = v
    keep["n_per_prior_rows"] = len(rep.get("per_prior", [])) if isinstance(rep.get("per_prior"), list) else None
    return keep


def maxima(rep):
    """Max over priors of every numeric per-prior field (rank correlation, near-dot share, ...)."""
    rows = rep.get("per_prior") or []
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = max(out.get(k, -np.inf), float(v))
    return out


def main():
    t0 = time.time()
    with rasterio.open(SAMPLE) as ref:
        domain = np.isfinite(ref.read(1))
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    cat = labels == 1
    eligible = H83.footprint_all_bands(str(FEATURES)) & domain
    with rasterio.open(CAND) as c:
        dots = c.read(1).astype(np.float32)
    priors = gates.find_priors([ROOT / "submission", ROOT / "docs/downloads", ROOT / "data/scored",
                                ROOT / "data/reference"], exclude=CAND)
    cs = sha(CAND)
    priors = [p for p in priors if sha(p) != cs]

    # ---- surface phase: the H83 field BEFORE placement (same computation as the build) ----
    conc, gr, mr, dr, cc = H83.compute_structural_concordance(str(FEATURES), eligible)
    geo = H83.compute_geothermal_density(H83.load_well_spring_data(str(WELLS)), eligible, sigma_px=15.0)
    field = H83.combine_signals(conc, cc, gr, mr, dr, geo, eligible, labels)
    allowed = eligible & ~cat & (ndi.distance_transform_edt(~cat) > 2)
    surface = np.where(allowed, np.clip(field, 0, 1), 0).astype(np.float32)
    surf_rep = gates.lane_report(surface, eligible, priors, sample=str(SAMPLE), phase="surface")

    # ---- dots phase: the emitted binary raster ----
    dots_rep = gates.lane_report(dots, eligible, priors, sample=str(SAMPLE), phase="dots")

    out = dict(
        round="H85", candidate=str(CAND.relative_to(ROOT)), candidate_sha256=cs,
        priors_checked=len(priors), rank_limit=0.90, near_dot_limit=0.70, near_radius_px=3.0,
        surface_before_placement=slim(surf_rep), surface_max_over_priors=maxima(surf_rep),
        final_dots=slim(dots_rep), final_dots_max_over_priors=maxima(dots_rep),
        note=("Literal verdict applies the lane rule to every prior, probes included; policy verdict excludes "
              "universal-coverage probes (see gates.lane_report docstring). A literal DUPLICATE on a registry "
              "that contains universal-coverage probes is a registry property, not a candidate property."),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps({"surface": {k: surf_rep.get(k) for k in ("verdict_literal", "verdict_policy", "max_abs_rank_corr", "max_near_dot_fraction") if k in surf_rep},
                      "dots": {k: dots_rep.get(k) for k in ("verdict_literal", "verdict_policy", "max_abs_rank_corr", "max_near_dot_fraction") if k in dots_rep},
                      "keys": sorted(dots_rep.keys())[:40]}, indent=2, default=float))


if __name__ == "__main__":
    main()
