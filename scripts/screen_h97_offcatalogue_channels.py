#!/usr/bin/env python3
"""H97 screening (attribution only, nothing here is promotable).

H97's primary field landed *below* its matched random control on both instruments.  A negative is only
useful if it says why.  This script measures the per-channel lifts on the prevalence-matched
off-catalogue instrument built this round (``gems52.h97.offcatalogue_truth``) at the frozen budget and
placement, so the next round's hypothesis can be chosen from a mechanism that has been measured rather
than guessed.

Explicitly NOT a promotion path
-------------------------------
Post-hoc arm selection is forbidden in this repository (``registry/h82_preregistration.json`` ->
``attribution_arms_not_promotable``; AGENTS.md).  The numbers below are reported as attribution
statistics; a channel that looks good here must be pre-registered fresh as a primary, before any fit,
before it can ship.

Writes ``evidence/h97_channel_screen.json``.
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

from gems52 import grid, h97, metric, nodes  # noqa: E402

FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
SGMC = ROOT / "data/external/derived_sgmc_faults_100m_u8.tif"
OUT = ROOT / "evidence/h97_channel_screen.json"
K = 37654
SEED = 88077


def log(m):
    print(f"[h97-screen {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    t0 = time.time()
    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    with rasterio.open(SAMPLE) as ds:
        domain = np.isfinite(ds.read(1))
    valid = grid.footprint_from(FEATURES, "all") & domain
    cat = labels == 1
    with rasterio.open(SGMC) as ds:
        sgmc = ds.read(1) > 0
    truth, receipt = h97.offcatalogue_truth(labels, sgmc, valid)
    log(f"truth {int(truth.sum()):,} px (raw {receipt['raw_candidate_px']:,})")
    ed = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (ed > h97.RING_PX)

    a_rank = h97.view_a(str(FEATURES), valid)
    b_rank = h97.view_b(str(FEATURES), valid)
    with rasterio.open(FEATURES) as ds:
        cover = ds.read(15).astype(np.float32)
        b12 = ds.read(12).astype(np.float32)
        b18 = ds.read(18).astype(np.float32)
        b2 = ds.read(2).astype(np.float32)
        b6 = ds.read(6).astype(np.float32)
    clean = lambda a: np.where(np.isfinite(a) & (a > -1e38), a, np.nan).astype(np.float32)
    cover, b12, b18, b2, b6 = map(clean, (cover, b12, b18, b2, b6))
    cover_pct = h97.rank01(cover, valid)

    channels = {
        "h97_disagree  (primary this round)": h97.disagreement(a_rank, b_rank, valid),
        "view_A_rank   (potential-field edge)": a_rank,
        "view_B_rank   (surface family)": b_rank,
        "b_only        (B conf, A abstains)": (b_rank * (1.0 - a_rank)).astype(np.float32),
        "cover_pct     (band 15 rank)": cover_pct,
        "band12_curv   (DEM curvature sigma 2)": h97.rank01(h97.curvature_mag(b12, valid, 2.0), valid),
        "band18_grav_hg(gradient sigma 2)": h97.rank01(h97.grad_mag(b18, valid, 2.0), valid),
        "band2_rtp_grad(gradient sigma 2)": h97.rank01(h97.grad_mag(b2, valid, 2.0), valid),
        "band6_rad_sm4 (radiometric TC)": h97.rank01(h97.smooth_norm(b6, valid, 4.0), valid),
    }
    rng = np.random.default_rng(SEED)
    noise = rng.random(valid.shape).astype(np.float32)

    rows = {}
    for name, field in channels.items():
        em = nodes.spacing_select(field, allowed, K, min_px=3.0).astype(np.float32)
        r = metric.dti(em, truth)
        rows[name] = dict(dti=float(r["dti"]), tpw=float(r["tpw"]), mass=int(em.sum()),
                          credit_per_dot=float(r["tpw"] / max(int(em.sum()), 1)))
        log(f"{name:44s} DTI {r['dti']:.6f} credit/dot {rows[name]['credit_per_dot']:.5f}")
        del em
    rnd = []
    for s in range(3):
        n = np.random.default_rng(SEED + 1 + s).random(valid.shape).astype(np.float32)
        em = nodes.spacing_select(n, allowed, K, min_px=3.0).astype(np.float32)
        rr = metric.dti(em, truth)
        rnd.append(dict(seed=SEED + 1 + s, dti=float(rr["dti"]),
                        credit_per_dot=float(rr["tpw"] / max(int(em.sum()), 1))))
        log(f"random seed {SEED+1+s}                            DTI {rr['dti']:.6f}")
        del em, n
    rnd_mean = float(np.mean([r["dti"] for r in rnd]))
    for name in rows:
        rows[name]["lift_vs_random_mean"] = rows[name]["dti"] - rnd_mean

    out = dict(
        schema="h97-channel-screen-v1", stage="screening",
        evidence_class="PROXY-INSTRUMENT attribution, NOT promotable (post-hoc selection is forbidden)",
        instrument=receipt, budget_K=K, placement="spacing_select min_px 3.0, 200 m ring removed",
        random_controls=rnd, random_mean_dti=rnd_mean,
        channels=rows,
        reading=("the disagreement field is below the matched random control; view_A and view_B are both "
                 "below it too, so this round's failure is not one bad combination but the whole "
                 "catalogue-free ranking family on off-catalogue truth"),
        next_round_rule=("if any channel is to ship, it must be pre-registered fresh as a primary before "
                         "any fit in the next session, with this screening cited only as the prior belief"),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
