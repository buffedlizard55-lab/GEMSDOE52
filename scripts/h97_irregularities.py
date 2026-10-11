#!/usr/bin/env python3
"""Append IR-H97-* entries to registry/irregularities.json (idempotent); numbers read from receipts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "registry/irregularities.json"
ho = json.loads((ROOT / "evidence/h97_holdout.json").read_text())
orient = json.loads((ROOT / "evidence/h97_orient.json").read_text())
bf = json.loads((ROOT / "evidence/h97_build_fields.json").read_text())
fit = json.loads((ROOT / "evidence/h97_fit.json").read_text())
sc = ho["pooled"]["scores"]
lane = json.loads((ROOT / "evidence/h97_lane.json").read_text())
_rows = {r["path"].split("/")[-1]: r for r in lane["full_dots"]["per_prior"] if r.get("near_3px_fraction") is not None}
_h84 = next((r for n, r in _rows.items() if n.startswith("gems52-h84-hva-ellipse-B")), None)
d = json.loads(P.read_text())
new = [
    dict(id="IR-H97-001", title="The holdout-best 'View B' learner B_DVA2 is not a pure surface view",
         status="open - reported; lane-pure arm added",
         what_it_is=("scripts/run_h82.py BANDS = {12 det_elev, 19 det_elev_slope, 13 iso_grav_anom, 15 depth_to_base_surf, "
                     "18 iso_grav_anom_hg}; B_DVA2 = View B + DVA2 of all five, so three gravity/basement (View-A) bands "
                     "sit inside the surface learner. Its 'B-confident / A-not' disagreement is partly A-vs-A."),
         how_we_know=(f"H97 holdout: B_DVA2 {sc['B_DVA2']['dti']:.6f} vs lane-pure B_DVA2s (DVA2 of bands 12/19 only) "
                      f"{sc['B_DVA2s']['dti']:.6f}; paired {ho['vs_B_DVA2']['B_DVA2s']['delta']:+.6f} "
                      f"{[round(x, 6) for x in ho['vs_B_DVA2']['B_DVA2s']['ci95']]} (evidence/h97_holdout.json)."),
         disposition="Every co-training round must report the lane-pure View B next to B_DVA2; do not call B_DVA2 'surface-only'."),
    dict(id="IR-H97-002", title="Preregistered erosion null fraction ignored the undefined-gradient mask",
         status="closed - corrected in reporting, rule unchanged",
         what_it_is=("knowledge/97 states the isotropic erosion null as 1/3, but FL is defined only on the top 75 % of "
                     "gradient magnitude (FL = 0 elsewhere), so the correct null is 0.75 x 1/3 = 0.25."),
         how_we_know=(f"evidence/h97_orient.json: defined_fraction {orient['defined_fraction']:.4f}, all-eligible "
                      f"erosion fraction {orient['fl_ge_erosion_fraction']:.4f}; B-only pool fraction "
                      f"{bf['b_only_erosion_fraction']:.4f} (evidence/h97_build_fields.json)."),
         disposition="Only the descriptive comparison changes; the veto rule and every score are as frozen."),
    dict(id="IR-H97-003", title="Leakage canary negatives were subsampled (deviation from H84's full negatives)",
         status="closed - disclosed",
         what_it_is=("scripts/run_h97.py stage_fit draws a seeded 400,000-cell subsample of region negatives "
                     "(> 5 px from catalogue) per fold for the single-feature AUC canary; knowledge/97 did not say so."),
         how_we_know=f"evidence/h97_fit.json canary_negatives field; max canary AUC {fit['canary_max_overall']:.4f}.",
         disposition="A subsample of 400k gives AUC standard errors far below the 0.90-vs-0.67 margin; no alarm either way."),
    dict(id="IR-H97-004", title="README top block (H95) and docs/index.html title (H96) disagreed on the current round",
         status="closed - superseded by the H97 blocks",
         what_it_is=("At main 7eb226d README.md began with <!--H95-README--> while docs/index.html's <title> and AGENTS.md's "
                     "first block said H96: parallel merges (PR #101 then #102) overwrote each other's top-of-file status."),
         how_we_know="grep -n '^<!--H9' README.md -> only H95 and H91 blocks; docs/index.html line 6 title 'current status (H96)'.",
         disposition="H97 inserts delimited blocks at the top of README, AGENTS and every landing page; earlier blocks are preserved."),
    dict(id="IR-H97-005", title="H97 dots are a lane near-duplicate of this repository's own H84 file",
         status="open - reported; SUBMIT NO",
         what_it_is=("The veto changes only part of the B_DVA2 emission, so the H97 dots sit within 3 px of the H84 file's "
                     "dots (H84 = B_DVA2 + harmonic anisotropy channels, same family) far above that raster's own coverage."),
         how_we_know=(f"evidence/h97_lane.json full_dots: H84 near-3px {_h84['near_3px_fraction']:.4f} vs its 3 px coverage "
                      f"{_h84['coverage_3px_of_eligible']:.4f}; policy verdict {lane['full_dots']['policy']['verdict']} "
                      f"(max {lane['full_dots']['policy']['max_near_3px_fraction']:.4f}, a dense raster with coverage 0.53); "
                      "literal verdict DUPLICATE/STOP (universal-coverage probes)."),
         disposition="Logged as a duplicate per the parallel-run protocol; the raster is a research artefact only. Any future "
                     "B_DVA2-family emission must change the ranking materially (or use quota placement vs the H82/H84 files)."),
]
ids = {e["id"] for e in d["entries"]}
d["entries"] += [e for e in new if e["id"] not in ids]
d["generated"] = d["generated"] + " ; H97 append (IR-H97-001..005)" if "H97" not in d["generated"] else d["generated"]
P.write_text(json.dumps(d, indent=2) + "\n")
print("irregularities:", len(d["entries"]))
