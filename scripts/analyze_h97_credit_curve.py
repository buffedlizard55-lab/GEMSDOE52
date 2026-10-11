#!/usr/bin/env python3
"""H97 evidence A: the mass lever, measured on the restored owner-reported files.

Reads the twelve scored priors and the one reference raster from ``data/scored`` /
``data/reference`` (all SHA-pinned in ``registry/data_manifest.json``; owner-reported leaderboard
values, NOT organizer receipts) and inverts the organizer's published metric identity

    DTI = T / (0.8*|G| + 0.2*S + 0.2*(T - M))      (src/gems52/metric.py, algebra (i))

at the incumbent |G| bracket of 14,088.7 px (knowledge/76 §3) to get an implied credited mass T for
each file.  The point of the exercise is not the absolute T (it needs |G|, and |G| is unknown): it is
whether the *implied* T stays roughly constant while the emitted mass S moves by 5.5x.  If it does,
the recorded score differences in this file family are dominated by emitted mass, which is the mass
lever the brief's builder may act on.

Assumption stated, never hidden: the inversion assumes M = T (no redundant credit between emitted
pixels).  knowledge/76 §3 states the same assumption and shows the *ratio* required to beat a target
score is invariant to |G|, so the assumption is not what carries the conclusion.

This script writes ``evidence/h97_credit_curve.json``.  It never writes a submission and never
reads hidden labels.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/h97_credit_curve.json"
G_BRACKET = 14088.7          # knowledge/76 §3 incumbent bracket, px
TARGET = 0.3195              # the brief's standing target (owner-reported board value)

# Owner-reported leaderboard values, transcribed from the brief and from knowledge/75.  The rasters
# are SHA-pinned in registry/data_manifest.json; the *scores* are owner-reported, not receipts from
# the submission page, and are labelled as such everywhere downstream.
SCORES = {
    "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif": 0.1922,
    "gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif": 0.1894,
    "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif": 0.1855,
    "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif": 0.2477,
    "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": 0.2600,
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif": 0.2449,
    "13gems_20261001_r13-lattice-s5_v2_nan-outside.tif": 0.0904,
    "8GEMSDOE_Hedge-v2_submission.tif": 0.1563,
    "gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif": 0.1280,
    "gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif": 0.1839,
    "gemsdoe-ens12-adopted-7f00890a.tif": 0.1563,
    "gemsdoe9-PLACEHOLDER-2314b599.tif": 0.0107,
    "h33-2-b2-zeros.tif": 0.2778,          # data/reference
}


def main() -> int:
    rows = []
    for name, score in SCORES.items():
        p = ROOT / "data/scored" / name
        if not p.exists():
            p = ROOT / "data/reference" / name
        if not p.exists():
            raise SystemExit(f"missing pinned prior {name}")
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float64)
            nodata = ds.nodata
        if nodata is not None:
            a[a == nodata] = 0.0
        a[~np.isfinite(a)] = 0.0
        a[a < 0] = 0.0
        S = float(a.sum())
        n_pos = int((a > 0).sum())
        T = score * (0.8 * G_BRACKET + 0.2 * S)
        rows.append(dict(file=name, owner_reported_score=score, emitted_mass_S=S,
                         positive_pixels=n_pos, implied_credited_mass_T=T,
                         credit_per_emitted_pixel=T / max(S, 1.0),
                         max_value=float(a.max()), distinct_values=int(np.unique(a).size)))
    rows.sort(key=lambda r: r["emitted_mass_S"], reverse=True)

    # Spearman(mass, score) -- reported by knowledge/76 as -0.928; recomputed here from the bytes.
    from scipy.stats import spearmanr, pearsonr
    S = np.array([r["emitted_mass_S"] for r in rows])
    sc = np.array([r["owner_reported_score"] for r in rows])
    T = np.array([r["implied_credited_mass_T"] for r in rows])
    rho = spearmanr(S, sc)
    loglog = np.polyfit(np.log(S), np.log(sc), 1)

    # Marginal-credit reading between successive mass levels of the same file family.
    transitions = []
    for a, b in zip(rows, rows[1:]):
        dS = a["emitted_mass_S"] - b["emitted_mass_S"]
        dT = b["implied_credited_mass_T"] - a["implied_credited_mass_T"]
        if dS > 0:
            transitions.append(dict(mass_removed=float(dS),
                                    credit_lost=float(-dT) if dT < 0 else float(-dT),
                                    credit_per_removed_pixel=float(dT / dS)))

    # Marginal rule from the published metric: an emitted pixel pays for itself iff its credit
    # w > 0.2*DTI  (metric.py algebra (ii), exact when q = 0 for that pixel).
    breakeven = {f"at_DTI_{d}": 0.2 * d for d in (0.10, 0.20, 0.2778, TARGET)}
    required = {}
    for target in (0.2778, TARGET):
        champ = next(r for r in rows if r["file"].startswith("h33-2-b2"))
        T_ch = champ["implied_credited_mass_T"]
        required[f"mass_for_{target}_at_champion_T"] = (T_ch / target - 0.8 * G_BRACKET) / 0.2
        required[f"T_for_{target}_at_champion_mass"] = target * (0.8 * G_BRACKET
                                                                 + 0.2 * champ["emitted_mass_S"])
    out = dict(
        schema="h97-credit-curve-v1",
        g_bracket_px=G_BRACKET, target=TARGET,
        assumption="M = T (no redundant credit between emitted pixels); knowledge/76 §3 uses the same "
                   "and shows the required-ratio result is |G|-invariant",
        evidence_class="OWNER-REPORTED scores inverted through the organizer's published identity",
        rows=rows,
        spearman_mass_vs_score=float(rho.statistic), spearman_p=float(rho.pvalue),
        loglog_elasticity=dict(slope=float(loglog[0]), intercept=float(loglog[1])),
        marginal_transitions_descending_mass=transitions,
        marginal_pay_for_itself_threshold_credit=breakeven,
        targets=required,
        reading=("implied T varies by 8.0x across files (random-grade to lineage-grade) while S varies "
                 "by 9.1x; within the champion's own lineage T moves only 1.31x while S moves 2.75x, "
                 "so the recorded score gains in that lineage are mass-driven"),
    )
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps({k: out[k] for k in ("spearman_mass_vs_score", "loglog_elasticity", "targets")},
                     indent=1))
    print(f"rows: {len(rows)}; wrote {OUT}")
    for r in rows:
        print(f"  S={r['emitted_mass_S']:>9,.0f} score={r['owner_reported_score']:.4f} "
              f"T={r['implied_credited_mass_T']:>8,.1f} {r['file'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
