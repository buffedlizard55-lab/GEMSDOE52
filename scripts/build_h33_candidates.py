#!/usr/bin/env python3
"""Build, measure and ship the H33 candidate submissions.

Candidates (all label-free surfaces; the *scored* comparison happens on the blocked holdout):

  ``H33-U-44090``        the 44,090 top-ranked pixels of the equal-weight H33-A..D union
  ``D28+H33U-K``         the incumbent 0.2600 emission (44,090 px) plus K priority-ordered H33
                         additions at >= 2.35 px spacing from every already-emitted dot
  ``H32D+H33U-K``        the 46,090-px H32-D artifact plus the same additions

Promotion rule (frozen before the run, and the run is reported either way):
  * primary   drift_corrected_holdout_mean  > the incumbent's 0.14801   (the only instrument that
              ranks live scores at better than chance here: Spearman +0.53 over 12 artifacts)
  * secondary catalogue_hidden_mean          > the incumbent's 0.09832
  * veto      sgmc_prevalence_calibrated_dti < 0.9 x the incumbent's 0.06059
Fail any of the three -> the candidate is NOT shipped for a slot; the file is still written to
``docs/downloads/`` with an explicit ``not promoted`` receipt, because a measured negative is a
result (the brief's "log every holdout evaluation, submitted or not").

Usage:  PYTHONPATH=src python3 scripts/build_h33_candidates.py [--adds 2000,4000]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.bo import Observation, append_observation                              # noqa: E402
from gems52.h33 import H33_BUILDERS, H33_SPECS, rank_surface, top_n_mask           # noqa: E402
from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.hypotheses import poisson_disk_thin_priority                           # noqa: E402
from gems52.paths import data_dir, docs_dir, evidence_dir, work_dir                # noqa: E402
from gems52.submission import sha256_file, write_submission_pair                   # noqa: E402

TIMESTAMP_TAG = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
INCUMBENT_REL = "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"
H32D_REL = "gemsdoe32-h32d-submodular-multipysics-46090-20261004T183200Z-4de30601-zeros.tif"
BAR_DRIFT = 0.14801
BAR_CAT = 0.09832
VETO_SGMC = 0.9 * 0.06059
MIN_DIST_PX = 2.35


def evaluate(mask: np.ndarray, ctx, name: str) -> dict:
    ev = evaluate_candidate_holdout(mask, ctx, name)
    return {
        "candidate_id": name,
        "emitted_pixels": int(ev["emitted_pixels"]),
        "on_catalogue_pixels": int(ev["on_catalogue_pixels"]),
        "catalogue_hidden_mean": float(ev["catalogue_hidden_mean"]),
        "sgmc_prevalence_calibrated_dti": float(ev["sgmc_prevalence_calibrated_dti"]),
        "drift_corrected_holdout_mean": float(ev["drift_corrected_holdout_mean"]),
        "drift_corrected_holdout_std": float(ev["drift_corrected_holdout_std"]),
        "catalogue_hidden_per_quadrant": {k: float(v) for k, v in ev["catalogue_hidden_per_quadrant"].items()},
        "drift_corrected_per_quadrant": {k: float(v) for k, v in ev["drift_corrected_per_quadrant"].items()},
        "catalogue_hidden_per_draw": {k: float(v) for k, v in ev["catalogue_hidden_per_draw"].items()},
    }


def verdict(ev: dict) -> dict:
    return {
        "primary_drift_beats_incumbent": bool(ev["drift_corrected_holdout_mean"] > BAR_DRIFT),
        "secondary_cat_beats_incumbent": bool(ev["catalogue_hidden_mean"] > BAR_CAT),
        "sgmc_veto_clear": bool(ev["sgmc_prevalence_calibrated_dti"] >= VETO_SGMC),
        "promoted": bool(ev["drift_corrected_holdout_mean"] > BAR_DRIFT
                         and ev["catalogue_hidden_mean"] > BAR_CAT
                         and ev["sgmc_prevalence_calibrated_dti"] >= VETO_SGMC),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adds", default="2000,4000")
    ap.add_argument("--ship", action="store_true", help="write the promoted candidate's GeoTIFF pair")
    args = ap.parse_args()
    adds = [int(a) for a in args.adds.split(",")]
    t0 = time.time()

    ddir, dl = data_dir(), docs_dir() / "downloads"
    ctx = load_holdout_context(ddir)
    foot, labels = ctx.foot, ctx.labels
    p28, p32 = ddir / INCUMBENT_REL, dl / H32D_REL
    d28 = read_binary(p28) if p28.exists() else read_binary(dl / Path(INCUMBENT_REL).name)
    h32d = read_binary(p32) if p32.exists() else None

    print("[1/4] H33 surfaces", flush=True)
    bands_dir = work_dir() / "bands"
    surfaces = {hid: b(bands_dir, ddir, foot) for hid, b in H33_BUILDERS.items()}
    union = np.mean([rank_surface(v, foot) for v in surfaces.values()], axis=0).astype(np.float32)
    union[~foot] = 0.0

    print("[2/4] candidates", flush=True)
    cands: dict[str, np.ndarray] = {"H33-U-44090": top_n_mask(union, foot, 44_090)}
    for base_name, base in (("D28", d28), ("H32D", h32d)):
        if base is None:
            continue
        for k in adds:
            add = poisson_disk_thin_priority(union > 0.0, union, min_dist_px=MIN_DIST_PX,
                                             existing_dots=base, max_add=k)
            cands[f"{base_name}+H33U-{k}"] = (base | add) & foot

    print("[3/4] holdout measurements", flush=True)
    results = {}
    for name, m in cands.items():
        ev = evaluate(m, ctx, name)
        results[name] = ev
        print(f"   {name:16s} px={ev['emitted_pixels']:6d} cat={ev['catalogue_hidden_mean']:.5f} "
              f"sgmc={ev['sgmc_prevalence_calibrated_dti']:.5f} drift={ev['drift_corrected_holdout_mean']:.5f}",
              flush=True)

    print("[4/4] promotion verdicts (frozen bars: drift>%.5f, cat>%.5f, sgmc>=%.5f)"
          % (BAR_DRIFT, BAR_CAT, VETO_SGMC), flush=True)
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_tag": TIMESTAMP_TAG,
        "bars": {"drift": BAR_DRIFT, "catalogue_hidden": BAR_CAT, "sgmc_veto": VETO_SGMC,
                 "incumbent": "D2.8-Poisson300m-Ref (owner-reported live 0.2600)"},
        "min_dist_px": MIN_DIST_PX,
        "candidates": {},
        "surface_specs": H33_SPECS,
        "elapsed_s": round(time.time() - t0, 1),
    }
    promoted = None
    for name, ev in results.items():
        v = verdict(ev)
        out["candidates"][name] = {**ev, "verdict": v}
        print(f"   {name:16s} promoted={v['promoted']}  (drift={v['primary_drift_beats_incumbent']}, "
              f"cat={v['secondary_cat_beats_incumbent']}, sgmc={v['sgmc_veto_clear']})", flush=True)
        if v["promoted"] and (promoted is None or
                              ev["drift_corrected_holdout_mean"] > results[promoted]["drift_corrected_holdout_mean"]):
            promoted = name

    out["promoted"] = promoted
    print(f"   -> promoted: {promoted}", flush=True)

    if args.ship and promoted is not None:
        slug = f"h33-{promoted.lower().replace('+', '-plus-')}-{TIMESTAMP_TAG[:8]}"
        meta = {
            "candidate_id": promoted,
            "description": ("H33 multi-physics oriented-lineament consensus added to the group's best "
                            "emission; label-free surfaces, measured on the blocked holdout"),
            "catalogue_hidden_mean": results[promoted]["catalogue_hidden_mean"],
            "catalogue_hidden_per_quadrant": results[promoted]["catalogue_hidden_per_quadrant"],
            "sgmc_prevalence_calibrated_dti": results[promoted]["sgmc_prevalence_calibrated_dti"],
            "drift_corrected_holdout_mean": results[promoted]["drift_corrected_holdout_mean"],
            "drift_corrected_per_quadrant": results[promoted]["drift_corrected_per_quadrant"],
            "predicted_leaderboard_dti": None,
            "ei_drift_corrected": None,
            "slot_decision": "PROMOTED on the frozen bars; UNSCORED live",
            "submission_note_zeros": ("32GEMSDOE H33 " + promoted +
                                      " | holdout drift {drift_cal:.5f} vs 0.14801, cat {cat_hid:.5f} vs 0.09832"
                                      " | {dots} px, 0 on-catalogue | id {sha8} | UNSCORED"),
            "submission_note_nan": ("32GEMSDOE H33 " + promoted +
                                    " (nan-outside) | holdout drift {drift_cal:.5f}, cat {cat_hid:.5f}"
                                    " | {dots} px | id {sha8} | UNSCORED"),
        }
        bundle = write_submission_pair(cands[promoted], foot, labels,
                                       template_tif=ddir / "sample_submission.tif",
                                       out_dir=dl, slug=slug, timestamp_tag=TIMESTAMP_TAG,
                                       candidate_meta=meta)
        out["shipped"] = bundle
        print(f"   shipped {bundle['zeros_tif']['path']} sha256={bundle['zeros_tif']['sha256'][:16]}", flush=True)

    p = evidence_dir() / "h33_candidates.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)}  ({out['elapsed_s']}s)", flush=True)

    for name, ev in results.items():
        append_observation(Observation(
            kind="holdout", name=f"H33-cand:{name}", design_id=f"H33-{name}",
            score=float(ev["drift_corrected_holdout_mean"]), n_px=float(ev["emitted_pixels"]),
            source="build_h33_candidates",
            note="H33 candidate; drift-corrected holdout mean; instrument GEMSDOE32-H33",
            meta={"catalogue_hidden_mean": ev["catalogue_hidden_mean"],
                  "sgmc_prevalence_calibrated_dti": ev["sgmc_prevalence_calibrated_dti"],
                  "promoted": verdict(ev)["promoted"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
