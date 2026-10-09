#!/usr/bin/env python3
"""H66 board algebra: re-derived from restored bytes, not quoted from any prior document.

Answers, on measurements made in this session:

1. What the 0.2778 file *is*, as a set relation to four other organiser-scored files.
2. The credit density rho = T/S that each organiser-scored file implies, at three |G| brackets.
3. The marginal-acceptance test the metric itself defines, applied to the family's own rho(S) curve.
4. The rho required to reach any target score at any budget - in particular 0.3195 and 0.3774.

Everything is computed from ``data/`` files whose SHA-256 matches registry/data_manifest.json
(checked by scripts/run_h66.py preflight).  Published scores are OWNER-REPORTED (the board prints no
filename); they are never labelled ORGANIZER-CONFIRMED here.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ALPHA, BETA, R_M, PIXEL_M = 0.2, 0.8, 300.0, 100.0

# owner-reported board scores, copied from the current user brief; NOT organiser receipts
FILES = {
    "ref_h33_2_b2": ("reference/h33-2-b2-zeros.tif", 0.2778),
    "d2_8": ("scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif", 0.2600),
    "d1_5": ("scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif", 0.2477),
    "tgc": ("scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif", 0.2449),
    "h19_5": ("scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif", 0.1922),
}
G_BRACKETS = (14_088.7, 18_000.0, 27_400.0)


def load(rel):
    with rasterio.open(DATA / rel) as ds:
        return ds.read(1).astype(np.float32) > 0


def main() -> int:
    with rasterio.open(DATA / "labels.tif") as ds:
        cat = ds.read(1) > 0
    dcat = ndi.distance_transform_edt(~cat, sampling=PIXEL_M)
    masks = {k: load(rel) for k, (rel, _) in FILES.items()}
    scores = {k: s for k, (_, s) in FILES.items()}

    out = dict(
        evidence_class="MEASURED on restored integrity-pinned bytes; published scores are OWNER-REPORTED",
        metric="DTI = T / (0.2*(T + S - M) + 0.8*|G|); with M = T (dots separated by >200 m) this is "
               "DTI = T / (0.2*S + 0.8*|G|), so rho = T/S = score * (0.2 + 0.8*|G|/S)",
        files={}, set_relations={}, rho_curve=[], marginal_acceptance=[], required_rho={},
    )
    for k, m in masks.items():
        out["files"][k] = dict(px=int(m.sum()), owner_reported_score=scores[k],
                               min_dist_to_catalogue_m=round(float(dcat[m].min()), 1),
                               median_dist_to_catalogue_m=round(float(np.median(dcat[m])), 1),
                               frac_within_200m=round(float((dcat[m] < 200).mean()), 4),
                               frac_within_300m=round(float((dcat[m] < 300).mean()), 4))
    # both directions matter: "A \ B = 0" proves a subset, "B \ A" measures what deleting it bought
    pairs = [("ref_h33_2_b2", "d2_8"), ("d2_8", "ref_h33_2_b2"),
             ("ref_h33_2_b2", "h19_5"), ("h19_5", "ref_h33_2_b2"), ("d2_8", "h19_5"),
             ("d1_5", "h19_5"), ("h19_5", "d1_5"), ("d1_5", "tgc"), ("tgc", "d1_5"),
             ("ref_h33_2_b2", "d1_5"), ("d1_5", "ref_h33_2_b2")]
    for a, b in pairs:
        A, B = masks[a], masks[b]
        d = dcat[A & ~B]
        out["set_relations"][f"{a}__minus__{b}"] = dict(
            px=int((A & ~B).sum()),
            dist_min_m=(round(float(d.min()), 1) if d.size else None),
            dist_max_m=(round(float(d.max()), 1) if d.size else None),
            subset=bool((A & ~B).sum() == 0))
    out["set_relations"]["P1_champion_and_d15"] = int((masks["ref_h33_2_b2"] & masks["d1_5"]).sum())
    out["set_relations"]["P2_champion_not_d15"] = int((masks["ref_h33_2_b2"] & ~masks["d1_5"]).sum())

    order = sorted(masks, key=lambda k: masks[k].sum())
    for G in G_BRACKETS:
        row = []
        for k in order:
            S = int(masks[k].sum())
            T = scores[k] * (ALPHA * S + BETA * G)
            row.append(dict(G=G, file=k, S=S, score=scores[k], implied_T=round(T, 1),
                            rho=round(T / S, 4)))
        out["rho_curve"] += row
        # marginal acceptance between consecutive budgets on the same field family
        for (k1, k2) in zip(order, order[1:]):
            S1, S2 = int(masks[k1].sum()), int(masks[k2].sum())
            T1 = scores[k1] * (ALPHA * S1 + BETA * G)
            T2 = scores[k2] * (ALPHA * S2 + BETA * G)
            mrho = (T2 - T1) / max(1, (S2 - S1))
            bar = ALPHA * scores[k1]          # accept iff marginal rho > alpha * DTI
            out["marginal_acceptance"].append(
                dict(G=G, from_file=k1, to_file=k2, dS=S2 - S1, dT=round(T2 - T1, 1),
                     marginal_rho=round(float(mrho), 4), acceptance_bar=round(float(bar), 4),
                     should_add=bool(mrho > bar)))
        for target in (0.2778, 0.3195, 0.3774, 0.464):
            out["required_rho"][f"target_{target}_G_{G}"] = {
                str(S): round(target * (ALPHA + BETA * G / S), 4)
                for S in (25_517, 37_654, 44_090, 60_069, 100_000, 121_131)}
    xs = [int(masks[k].sum()) for k in order]
    ys = [scores[k] for k in order]
    sr = stats.spearmanr(xs, ys)
    out["mass_vs_board"] = dict(n=len(xs), spearman=round(float(sr.statistic), 4),
                                p=round(float(sr.pvalue), 6),
                                reading="board score is strictly decreasing in emitted mass across the "
                                        "five owner-reported off-catalogue files of this family")
    p = ROOT / "evidence" / "h66_board_algebra.json"
    p.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(json.dumps({k: out[k] for k in ("files", "set_relations", "mass_vs_board")}, indent=1))
    print("\nrequired rho to reach a target score (G = 14,088.7):",
          json.dumps(out["required_rho"]["target_0.3195_G_14088.7"], indent=1))
    print("\nmarginal acceptance (G = 14,088.7):")
    for r in out["marginal_acceptance"]:
        if r["G"] == G_BRACKETS[0]:
            print("  ", r)
    print(f"\nwrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
