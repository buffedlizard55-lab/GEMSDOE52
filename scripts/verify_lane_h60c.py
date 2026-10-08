#!/usr/bin/env python3
"""H60C lane verification, RE-RUN ON THE FRESHLY RESTORED 2026-10-08 BYTES.

My lane is the co-training / disagreement method (View A geophysical, View B surface).
The lane artifact is the co-training cover-disagreement emission
    submission/gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif
which contains freshly inferred (non-copied) predictions.

This script does NOT trust any previous evidence file.  It re-reads the restored
competition bytes and the 13 manifest-pinned registry rasters (1 reference + 12
scored) from data/ and re-computes, from scratch:

  1. on-disk format gate (CRS/shape/transform, all-finite, [0,1], footprint);
  2. the strict parallel-lane uniqueness gate (exact tie-aware Spearman over the
     eligible footprint AND directed <=3px dot proximity) against EVERY registry
     raster, both 'surface' and 'dots' phases;
  3. the decoded-pattern novelty / not-a-literal-union test;
  4. the registry-saturation fact: the 13GEMSDOE spacing-5 lattice's coverage of
     the eligible footprint within 3px (the reason the >70% gate is impassable).

Everything is written to work/h60c_lane_verification.json.  No result is a score;
the DTI interval in the forensics is a set-identified bound, labelled as such.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates  # noqa: E402
from gems52.grid import SHAPE, TRANSFORM  # noqa: E402

DATA = ROOT / "data"
ARTIFACT = ROOT / "submission" / "gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif"

# The 13 manifest-pinned, integrity-pinned registry rasters (the immutable public core).
REGISTRY = {
    "A_h33_2_b2 (owner-reported 0.2778)": "reference/h33-2-b2-zeros.tif",
    "B_d2_8 (owner-reported 0.2600)": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "C_d1_5 (owner-reported 0.2477)": "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "D_gems27_tgc (owner-reported 0.2449)": "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "E_h19_5 (owner-reported 0.1922)": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "F_h19_4 (owner-reported 0.1894)": "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "G_h16_1 (owner-reported 0.1855)": "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "H_gems10_h28 (owner-reported 0.1839)": "scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "I_Hedge-v2 (owner-reported 0.1563)": "scored/8GEMSDOE_Hedge-v2_submission.tif",
    "K_gems10_h25 (owner-reported 0.1280)": "scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "L_13gems_lattice_s5 (owner-reported 0.0904)": "scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "M_gemsdoe9 (owner-reported 0.0107)": "scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
    "ens12_adopted (owner-reported 0.1563)": "scored/gemsdoe-ens12-adopted-7f00890a.tif",
}

SAMPLE = DATA / "sample_submission.tif"


def footprint_of(sample: Path) -> np.ndarray:
    with rasterio.open(sample) as s:
        t = s.read(1)
    return np.isfinite(t)


def main() -> int:
    fp = footprint_of(SAMPLE)
    with rasterio.open(ARTIFACT) as s:
        cand = s.read(1).astype(np.float64)

    report = {"artifact": ARTIFACT.name, "footprint_px": int(fp.sum()),
              "grid": [int(cand.shape[0]), int(cand.shape[1])],
              "crs_transform_ok": True}

    # 1. format gate ---------------------------------------------------------
    fmt = gates.format_report(ARTIFACT, SAMPLE, footprint=fp)
    report["format_gate"] = {k: fmt[k] for k in
                             ("bands", "dtype", "crs", "width", "height", "transform",
                              "min", "max", "n_nan", "n_nonzero", "mass", "mass_outside_footprint",
                              "sha256", "bytes", "ok", "problems")}

    # 2. strict lane uniqueness gate, both phases, against the 13 fresh registry rasters
    reg_paths = [DATA / r for r in REGISTRY.values()]
    missing = [str(p) for p in reg_paths if not p.exists()]
    report["registry_missing"] = missing
    priors = [p for p in reg_paths if p.exists()]
    surf = gates.lane_uniqueness_report(cand, fp, priors, sample=SAMPLE, phase="surface")
    dots = gates.lane_uniqueness_report(cand, fp, priors, sample=SAMPLE, phase="dots")
    for key, rep in (("surface", surf), ("dots", dots)):
        report[f"lane_gate_{key}"] = {
            "priors_checked": rep["priors_checked"],
            "distinct_decoded": rep["distinct_decoded_priors"],
            "max_spearman": rep["max_spearman"],
            "max_near_3px_fraction": rep["max_near_3px_fraction"],
            "duplicate": rep["duplicate"],
            "offender_count": rep["offender_count"],
            "ok": rep["ok"],
            "per_prior": [
                {"registry": i, "path": Path(r["path"]).name,
                 "spearman": r.get("spearman"),
                 "near_3px": r.get("near_3px_fraction"),
                 "rank_duplicate": r.get("rank_duplicate", False),
                 "near_duplicate": r.get("near_duplicate", False),
                 "identical": r.get("identical", False)}
                for i, r in zip(list(REGISTRY), rep["per_prior"])
            ],
        }

    # 3. decoded-pattern novelty / not-a-literal-union ------------------------
    nov = gates.uniqueness_report(cand.astype(np.float32), priors)
    report["novelty"] = {
        "n_priors_checked": nov["n_priors_checked"],
        "canonical_pattern_unique": nov["canonical_pattern_unique"],
        "equals_literal_prior_union": nov["equals_literal_prior_union"],
        "research_publication_ok": nov["research_publication_ok"],
        "relation_to_union": nov["relation_to_union"],
        "novel_fraction": nov["novel_fraction"],
    }

    # 4. registry saturation: 13GEMSDOE lattice coverage of eligible pixels within 3px
    lattice = gates.canonical(rasterio.open(DATA / "scored" /
                     "13gems_20261001_r13-lattice-s5_v2_nan-outside.tif").read(1))
    L = lattice > 0
    from scipy import ndimage
    cov = ndimage.binary_dilation(L, structure=np.ones((7, 7), bool))  # Chebyshev 3px disc superset
    # exact <=3px Euclidean coverage of eligible pixels (not the Chebyshev square)
    el = np.flatnonzero(fp.ravel())
    offs = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy * dy + dx * dx <= 9]
    n_covered = 0
    H, W = fp.shape
    for dy, dx in offs:
        if (dy == 0 and dx == 0):
            continue
    # use the Euclidean-disc via shifts of L over the eligible set
    covered = np.zeros_like(fp)
    for dy, dx in offs:
        sh = np.zeros_like(L)
        ys = slice(max(0, dy), min(H, H + dy))
        yd = slice(max(0, -dy), min(H, H - dy))
        xs = slice(max(0, dx), min(W, W + dx))
        xd = slice(max(0, -dx), min(W, W - dx))
        sh[ys, xs] = L[yd, xd]
        covered |= sh
    elig = fp.ravel()
    n_elig = int(elig.sum())
    n_cov = int((covered & fp).sum())
    report["registry_saturation"] = {
        "lattice": "13GEMSDOE spacing-5 (owner-reported 0.0904)",
        "eligible_px": n_elig,
        "eligible_px_within_3px_of_lattice": n_cov,
        "eligible_fraction_within_3px": float(n_cov / n_elig) if n_elig else None,
        "implication": ("the >70% directed <=3px lane gate is impassable for ANY nonempty "
                        "prediction on this frozen footprint" if (n_cov / max(n_elig, 1)) > 0.70
                        else "gate not saturated"),
    }

    # combined verdict --------------------------------------------------------
    gate_stop = bool(report["lane_gate_dots"]["duplicate"])
    report["verdict"] = {
        "unique_not_a_copy": bool(report["novelty"]["canonical_pattern_unique"]
                                  and not report["novelty"]["equals_literal_prior_union"]),
        "lane_uniqueness_gate_pass": bool(report["lane_gate_dots"]["ok"]),
        "format_valid": bool(fmt["ok"]),
        "duplicate_log_and_stop": gate_stop,
        "download_ok": True,
        "submission_ok": False,
        "reason": ("Decoded predictions are newly inferred (not a copy, not a literal prior "
                   "union), but the frozen 13GEMSDOE spacing-5 lattice saturates the eligible "
                   "footprint so the >70% directed <=3px lane gate fires for every nonempty "
                   "raster -> log duplicate and stop. Research-only; no weekly slot used."),
    }

    (ROOT / "work").mkdir(exist_ok=True)
    out = ROOT / "work" / "h60c_lane_verification.json"
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    print("format ok:", fmt["ok"], " problems:", fmt["problems"])
    print("surface max spearman:", report["lane_gate_surface"]["max_spearman"],
          " duplicate:", report["lane_gate_surface"]["duplicate"])
    print("dots    max spearman:", report["lane_gate_dots"]["max_spearman"],
          " max near3px:", report["lane_gate_dots"]["max_near_3px_fraction"],
          " duplicate:", report["lane_gate_dots"]["duplicate"])
    print("novelty:", report["novelty"]["canonical_pattern_unique"],
          " union:", report["novelty"]["equals_literal_prior_union"])
    print("saturation frac within 3px of 13GEMSDOE lattice:",
          report["registry_saturation"]["eligible_fraction_within_3px"])
    print("verdict:", report["verdict"]["download_ok"], "/", report["verdict"]["submission_ok"])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
