#!/usr/bin/env python3
"""H98 lane pre-check (frozen in registry/h98_preregistration.json before any H98 fit).

Why this exists
---------------
H97's screening (``evidence/h97_channel_screen.json``) measured, on the prevalence-matched
off-catalogue instrument, that the lane's *other* disagreement case carries the signal:

    b_only  = B confident, A abstains   DTI 0.109480   (random mean 0.051925, lift +0.057555)
    band12 DEM curvature sigma 2 alone  DTI 0.117263   (lift +0.065337)
    h97 primary (A conf, B abstains)    DTI 0.005023   (lift -0.046902)

That is the opposite of the brief's prior ("where B is confident and A is not, suspect surface
artifacts") and it collides with this repository's best-scoring board family, the DEM/scarp "dotted
ridge" files.  The parallel-run protocol is explicit: if the candidate's rank correlation with any
registry raster exceeds 0.90, or more than 70 % of its dots fall within 3 px of one registry raster's
dots, the round has drifted into another lane and must stop.

So this script runs the lane and uniqueness gates FIRST, on the exact support that would ship, and
refuses to proceed to validation if the protocol fires.  Nothing here is a promotion step.

Writes ``evidence/h98_lane_precheck.json``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates, grid, h97, nodes  # noqa: E402

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
OUT = ROOT / "evidence/h98_lane_precheck.json"
K = 37654


def log(m):
    print(f"[h98-lane {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    prereg = ROOT / "registry/h98_preregistration.json"
    if not prereg.exists():
        raise SystemExit("registry/h98_preregistration.json must exist before this check runs")
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    with rasterio.open(SAMPLE) as ds:
        domain = np.isfinite(ds.read(1))
    valid = grid.footprint_from(FEATURES, "all") & domain
    cat = labels == 1
    a_rank = h97.view_a(str(FEATURES), valid)
    b_rank = h97.view_b(str(FEATURES), valid)
    field = (b_rank * (1.0 - a_rank)).astype(np.float32)
    ed = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (ed > h97.RING_PX)
    em = nodes.spacing_select(field, allowed, K, min_px=3.0)
    log(f"emitted {int(em.sum()):,} dots of a requested {K:,}")

    priors = [p for p in gates.find_priors([ROOT / "submission", ROOT / "docs/downloads",
                                            ROOT / "data/scored", ROOT / "data/reference"])]
    log(f"inventory {len(priors)} priors")
    lane = gates.lane_report(em.astype(np.float32), valid, priors, sample=str(SAMPLE), phase="dots")
    uq = gates.uniqueness_report(em.astype(np.float32), priors)
    log(f"lane literal={lane['literal']['verdict']} policy={lane['policy']['verdict']} "
        f"max_spearman={lane['policy']['max_spearman']} max_near3px={lane['policy']['max_near_3px_fraction']}")
    log(f"uniqueness canonical={uq['canonical_pattern_unique']} novel={uq['novel_fraction']:.4f} "
        f"gate_ok={uq['support_novelty_gate_ok']} identical={uq['identical_to_a_prior']}")
    most_similar = sorted([r for r in lane["per_prior"] if r.get("near_3px_fraction") is not None],
                          key=lambda r: -r["near_3px_fraction"])[:5]
    out = dict(
        schema="h98-lane-precheck-v1", stage="precheck",
        evidence_class="lane/uniqueness diagnostic, not a score",
        budget_K=K, dots=int(em.sum()),
        lane=dict(literal=lane["literal"]["verdict"], policy=lane["policy"]["verdict"],
                  max_spearman=lane["policy"]["max_spearman"],
                  max_near_3px_fraction=lane["policy"]["max_near_3px_fraction"],
                  max_near_source=lane["policy"]["max_near_source"],
                  informative_priors=lane["policy"]["informative_priors"],
                  universal_coverage_probes=lane["policy"]["universal_coverage_probes"],
                  probes=lane["policy"]["probe_paths"]),
        uniqueness=dict(canonical_pattern_unique=uq["canonical_pattern_unique"],
                        novel_fraction=float(uq["novel_fraction"]),
                        support_novelty_gate_ok=uq["support_novelty_gate_ok"],
                        identical_to_a_prior=uq["identical_to_a_prior"],
                        relation_to_union=uq["relation_to_union"],
                        n_priors_checked=int(uq["n_priors_checked"])),
        closest_five_by_dot_proximity=[dict(path=r["path"], near_3px_fraction=r["near_3px_fraction"],
                                            spearman=r.get("spearman")) for r in most_similar],
        decision=("proceed-to-validation" if (lane["policy"]["verdict"] == "PASS"
                                             and uq["canonical_pattern_unique"]
                                             and not uq["identical_to_a_prior"])
                  else "stop-duplicate-or-not-unique"),
    )
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log(f"decision: {out['decision']}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
