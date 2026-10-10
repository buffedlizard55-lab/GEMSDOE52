#!/usr/bin/env python3
"""Excess-proximity statistic for the lane rule — the shared-tool fix this round reports.

The brief's lane rule stops a run when **more than 70 % of its dots fall within 3 px of one registry
raster's dots**.  Applied literally to this project's 573-raster census the rule is close to vacuous,
and the reason is measurable rather than rhetorical: a prior that already covers a large share of the
eligible footprint within 3 px captures that same share of *any* placement, including a uniform
random one.  ``gems52.gates.lane_report`` already classifies **universal**-coverage probes
(coverage >= 0.95) and reports a policy verdict beside the literal one, but a prior at, say, 0.78
coverage is still counted as an offender at a near-share of 0.80 even though chance alone predicts
0.78.

This script computes, for the priors that actually drive the verdict, the chance-corrected statistic

    excess = (near_share - coverage) / (1 - coverage)

which is 0 at chance level and 1 only when every dot sits inside the prior's 3 px halo while the halo
is small.  It does not change any verdict in this round: the pre-registered gate stays exactly as
frozen in ``knowledge/83``.  It is published so the next round can pre-register the corrected rule
instead of inventing it after seeing a result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates, structural                                  # noqa: E402

WORK = ROOT / "work/h89"
EVID = ROOT / "evidence"


def disk(r: float = 3.0):
    y, x = np.mgrid[-int(r):int(r) + 1, -int(r):int(r) + 1]
    return (y * y + x * x) <= r * r + 1e-9


def main() -> int:
    lane = json.loads((EVID / "h89_lane.json").read_text())
    dots = np.load(WORK / "dots.npy").astype(bool)
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    n_dots = int(dots.sum())
    d = disk(3.0)

    targets: list[str] = []
    for key in ("full_dots", "restricted_dots"):
        r = lane.get(key, {})
        for scope in ("literal", "policy"):
            s = r.get(scope, {})
            targets += list(s.get("near_offenders") or [])
            if s.get("max_near_source"):
                targets.append(s["max_near_source"])
    targets += [str(p) for p in sorted((ROOT / "data/scored").glob("*.tif"))]
    targets += [str(p) for p in sorted((ROOT / "data/reference").glob("*.tif"))]
    seen, rows = set(), []
    for path in targets:
        p = Path(path)
        if not p.exists() or str(p) in seen:
            continue
        seen.add(str(p))
        with rasterio.open(p) as src:
            if src.count != 1 or (src.height, src.width) != eligible.shape:
                continue
            a = gates.canonical(src.read(1))
        binary = bool(np.all((a[eligible] == 0) | (a[eligible] == 1)))
        support = (a > 0) if binary else (a >= 0.5)
        if not support.any():
            continue
        halo = ndi.binary_dilation(support, structure=d)
        coverage = float((halo & eligible).sum()) / float(eligible.sum())
        near = float((dots & halo).sum()) / n_dots
        excess = (near - coverage) / (1.0 - coverage) if coverage < 1.0 else float("nan")
        rows.append(dict(path=str(p.relative_to(ROOT)), support_px=int(support.sum()),
                         coverage_3px_of_eligible=coverage, near_3px_fraction=near,
                         excess_proximity=excess,
                         literal_offender=bool(near > 0.70),
                         excess_offender=bool(np.isfinite(excess) and excess > 0.70)))
        del a, support, halo
    rows.sort(key=lambda r: -(r["excess_proximity"] if np.isfinite(r["excess_proximity"]) else -1))
    inf_rows = [r for r in rows if r["coverage_3px_of_eligible"] < 0.95]
    worst_near = max(inf_rows, key=lambda r: r["near_3px_fraction"], default=None)
    out = dict(
        instrument="chance-corrected lane proximity (proposed shared-tool fix, reported not applied)",
        definition="excess = (near_3px_fraction - coverage_3px_of_eligible) / (1 - coverage_3px_of_eligible)",
        candidate_dots=n_dots, priors_measured=len(rows),
        max_excess=max((r["excess_proximity"] for r in rows if np.isfinite(r["excess_proximity"])), default=None),
        max_literal_near=max((r["near_3px_fraction"] for r in rows), default=None),
        n_literal_offenders=sum(r["literal_offender"] for r in rows),
        n_excess_offenders=sum(r["excess_offender"] for r in rows),
        applies_to_this_round=False,
        n_informative_measured=len(inf_rows),
        max_near_informative_coverage_lt_0_95=(worst_near["near_3px_fraction"] if worst_near else None),
        coverage_of_that_prior=(worst_near["coverage_3px_of_eligible"] if worst_near else None),
        excess_of_that_prior=(worst_near["excess_proximity"] if worst_near else None),
        max_excess_informative_coverage_lt_0_95=(max((r["excess_proximity"] for r in inf_rows), default=None)),
        n_informative_near_offenders=int(sum(r["near_3px_fraction"] > 0.70 for r in inf_rows)),
        n_informative_excess_offenders=int(sum(r["excess_proximity"] > 0.70 for r in inf_rows)),
        stability_caveat=("the ratio is unstable as coverage -> 1 (its denominator vanishes), which is why "
                          "near-total-coverage probes show excess ~1; it is meaningful only for priors that "
                          "leave a substantial part of the footprint uncovered"),
        note=("the pre-registered H89 gate is unchanged; this statistic is published so the next round "
              "can pre-register it rather than invent it after seeing a verdict"),
        per_prior=rows)
    (EVID / "h89_lane_excess.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "per_prior"}, indent=1, default=float))
    for r in rows[:8]:
        print(f"  {r['path']}: support {r['support_px']:>7,} coverage {r['coverage_3px_of_eligible']:.4f} "
              f"near {r['near_3px_fraction']:.4f} excess {r['excess_proximity']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
