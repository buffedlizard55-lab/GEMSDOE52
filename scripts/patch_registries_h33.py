#!/usr/bin/env python3
"""Append this session's hypotheses and irregularities to the registries (idempotent).

Adds H33-A..E to ``registry/hypotheses.json`` and six findings to
``registry/irregularities.json``.  Every statement carries the command or file that produced it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52.h33 import H33_SPECS  # noqa: E402

HYPOTHESES = [
    {
        "id": "H33-A", "rank": 1, "status": "measured (not promoted)",
        "title": "Multi-physics oriented-lineament consensus",
        "layers": H33_SPECS["H33-A"]["layers"],
        "signature": H33_SPECS["H33-A"]["signature"],
        "why_off_catalogue": H33_SPECS["H33-A"]["why_off_catalogue"],
        "differs_from_repo": H33_SPECS["H33-A"]["novelty"],
        "implementation": "src/gems52/h33.py::build_h33a; measured by scripts/run_h33.py",
        "measured": {"catalogue_hidden_mean_44090px": 0.01874,
                     "sgmc_prevalence_calibrated_dti_44090px": 0.02832,
                     "uniform_random_control_catalogue_hidden_44090px": 0.03438},
        "verdict": "BELOW the uniform-random control on the catalogue-hidden instrument (-45%); "
                   "the instrument measures agreement with the mapped catalogue, and this surface "
                   "deliberately selects what the catalogue under-represents. NOT PROMOTED.",
    },
    {
        "id": "H33-B", "rank": 2, "status": "measured (not promoted)",
        "title": "Aligned drainage-valley chains",
        "layers": H33_SPECS["H33-B"]["layers"],
        "signature": H33_SPECS["H33-B"]["signature"],
        "why_off_catalogue": H33_SPECS["H33-B"]["why_off_catalogue"],
        "differs_from_repo": H33_SPECS["H33-B"]["novelty"],
        "implementation": "src/gems52/h33.py::build_h33b; measured by scripts/run_h33.py",
        "measured": {"catalogue_hidden_mean_44090px": 0.02177,
                     "sgmc_prevalence_calibrated_dti_44090px": 0.09072,
                     "incumbent_sgmc": 0.06059},
        "verdict": "STRONGEST off-catalogue signal of the five (+49.8% over the incumbent on the "
                   "SGMC-only instrument) and the WORST-class reading on the catalogue instrument "
                   "(-37% vs random). The two instruments disagree in sign -- recorded as holdout "
                   "drift, not as a win. NOT PROMOTED.",
    },
    {
        "id": "H33-C", "rank": 3, "status": "measured (not promoted)",
        "title": "En-echelon scarplet chain vote on the 1 m LiDAR scarp product",
        "layers": H33_SPECS["H33-C"]["layers"],
        "signature": H33_SPECS["H33-C"]["signature"],
        "why_off_catalogue": H33_SPECS["H33-C"]["why_off_catalogue"],
        "differs_from_repo": H33_SPECS["H33-C"]["novelty"],
        "implementation": "src/gems52/h33.py::build_h33c; measured by scripts/run_h33.py",
        "measured": {"catalogue_hidden_mean_44090px": 0.02407,
                     "sgmc_prevalence_calibrated_dti_44090px": 0.02990},
        "verdict": "Below the random control on the catalogue instrument. NOT PROMOTED.",
    },
    {
        "id": "H33-D", "rank": 4, "status": "measured (not promoted)",
        "title": "Long-straight conductive / basement structural boundary",
        "layers": H33_SPECS["H33-D"]["layers"],
        "signature": H33_SPECS["H33-D"]["signature"],
        "why_off_catalogue": H33_SPECS["H33-D"]["why_off_catalogue"],
        "differs_from_repo": H33_SPECS["H33-D"]["novelty"],
        "implementation": "src/gems52/h33.py::build_h33d; measured by scripts/run_h33.py",
        "measured": {"catalogue_hidden_mean_44090px": 0.00394,
                     "sgmc_prevalence_calibrated_dti_44090px": 0.00418},
        "verdict": "Weakest of the five on both instruments (a 3x3 directional-coherence window is "
                   "too short for a 'long-straight' criterion). NOT PROMOTED.",
    },
    {
        "id": "H33-E", "rank": 5, "status": "DATA-BLOCKED (source named, obtainability not verified here)",
        "title": "Sub-kilometre seismicity lineaments and nodal-plane traces from the raw earthquake catalogue",
        "layers": ["ieq_n100a15 (16) and deq_n100a15 (10) would be replaced/augmented by a raw "
                   "epicentre catalogue (USGS FDSN event web service) plus moment tensors"],
        "signature": "epicentre density lineaments + focal-mechanism nodal-plane strikes as fault-plane "
                     "proxies at the epicentre",
        "why_off_catalogue": "instrumental seismicity is a dynamic inventory: blind, low-slip-rate "
                             "faults light up seismically while leaving no scarp for a geomorphic map",
        "differs_from_repo": "the supplied seismic bands are computed on a 100 km radius; measured "
                             "here, ieq is 0.9935-correlated with itself at a 3 km lag, i.e. constant "
                             "at the metric's 300 m resolution",
        "implementation": "scripts/fetch_earthquake_catalog.sh (ready to run; NOT runnable from this "
                          "sandbox: curl to earthquake.usgs.gov returns HTTP 000, browsing path HTTP 500)",
        "measured": {"ieq_autocorr_1km": 0.9986, "ieq_autocorr_3km": 0.9935, "ieq_autocorr_10km": 0.9534,
                     "deq_autocorr_3km": 0.8408},
        "verdict": "NAMED SOURCE, obtainability NOT verified from this environment; ranked and NOT "
                   "proposed as ready, per the brief's rule for externally-dependent candidates.",
    },
]

IRREGULARITIES = [
    {
        "id": "IR-32-MANIFEST-01", "severity": "high", "status": "fixed 2026-10-04",
        "statement": "scripts/run_pipeline.py requires scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif, which was absent from registry/data_manifest.json and therefore never restored; the documented reproduce command (and step [3/6]) aborted with rasterio CPLE_OpenFailedError.",
        "evidence": "traceback reproduced twice this session; the file was then pinned from the GEMSDOE27 manifest (sha256 33003374335d84bf885f2d8f5e9dd4c57044c8ec58fa6a0d7fa581e8bc41c11d, 1,635,084 bytes) and fetch_mirrors.sh now reports 23/23 PASS.",
        "mitigation": "manifest entry added (group 'scored'); fetch_mirrors.sh fails closed on digest mismatch.",
    },
    {
        "id": "IR-32-INSTR-01", "severity": "high", "status": "open (instrument defect, quantified)",
        "statement": "The repository's promotion instrument drift_corrected_holdout_mean is discontinuous in the number of dots placed on the visible catalogue: holdout.py sets debiased_folds = dti and sym_factor = 1/(1+(n/60000)^2) whenever n_on_cat > 0. Adding ONE dot on a mapped fault to the 0.2600 emission moves drift 0.14801 -> 0.07831 (-47%) while catalogue_hidden_mean (0.09832) and SGMC (0.06059) are unchanged.",
        "evidence": "controlled experiment this session: base mask + 1 catalogue pixel at (yy[0], xx[0]); outputs recorded in the session log and reproducible from src/gems52/holdout.py lines ~200-215.",
        "consequence": "every cross-candidate drift comparison that straddles this branch is invalid, and every artifact in this repository that was 'promoted' happens to carry 0 on-catalogue dots.",
        "mitigation": "slot decisions this session require on_catalogue_pixels == 0 AND agreement with the catalogue-hidden and SGMC instruments (registry/slot_plan.json); a branch-free estimator is proposed as next work.",
    },
    {
        "id": "IR-32-INSTR-02", "severity": "medium", "status": "open (cross-repository contradiction)",
        "statement": "Over the 12 stored artifacts with owner-reported live scores the rank correlation with the live board is: catalogue_hidden Spearman +0.140, catalogue_hidden_strict +0.140, SGMC-calibrated +0.537, drift-corrected +0.529 (LOO MAE 0.053). The sibling repository GEMSDOE29 reports +0.709 for the catalogue-hidden proxy on a set of ten stored artifacts. The two measurements disagree about the same instrument.",
        "evidence": "evidence/instrument_calibration.json (this checkout, n=12, scripts/calibrate_instrument.py).",
        "mitigation": "only the drift/SGMC pair is used for promotion here, and both are labelled as weak rankers (n=12, p approx 0.09); the contradiction is disclosed rather than resolved.",
    },
    {
        "id": "IR-32-SITE-01", "severity": "high", "status": "fixed 2026-10-04",
        "statement": "The published site's one-click file (gems52-heatfield-44090-cv-supconfined-zeros.tif) measures catalogue_hidden 0.11549 but SGMC-calibrated 0.01124 and drift 0.07789 -- below the owner-reported 0.2600 incumbent on two of the three instruments -- while the README's slot table advertised the H32-D family that the site never offered. The obvious download was therefore not the best-validated artifact.",
        "evidence": "evidence/h33_probe_controls.json; registry/submission_build.json before/after this session.",
        "mitigation": "scripts/build_slot_plan.py selects the headline artifact by the frozen rule and rewrites registry/submission_build.json; the site is regenerated from it.",
    },
    {
        "id": "IR-32-DUP-01", "severity": "low", "status": "flagged",
        "statement": "registry/irregularities.json contains the id IR-32-FIELD-01 twice, so an id-based lookup silently returns the first entry only.",
        "evidence": "python3 -c \"import json;print([x['id'] for x in json.load(open('registry/irregularities.json'))['items']])\"",
        "mitigation": "flagged for a deduplicating pass; ids are stable and referenced from the site, so the rename is deferred to avoid breaking links.",
    },
    {
        "id": "IR-32-H33-01", "severity": "medium", "status": "open (instrument power)",
        "statement": "All four label-free H33 surfaces score BELOW a uniform-random control on the catalogue-hidden instrument at 44,090 px (H33-A 0.01874, H33-B 0.02177, H33-C 0.02407, H33-D 0.00394, union 0.02006, random 0.03438), while H33-B scores 0.09072 on the off-catalogue SGMC instrument against the incumbent's 0.06059. The catalogue-hidden instrument therefore has no power to rank hypotheses whose purpose is to find faults the catalogue lacks.",
        "evidence": "evidence/h33_holdout.json; evidence/h33_candidates.json.",
        "mitigation": "the sign disagreement is reported as the session's central finding; promotion stays gated on the identification experiment (measuring T, K and F live) rather than on this instrument.",
    },
]


def main() -> int:
    hp = ROOT / "registry" / "hypotheses.json"
    h = json.loads(hp.read_text())
    have = {x["id"] for x in h["hypotheses"]}
    added_h = [x for x in HYPOTHESES if x["id"] not in have]
    h["hypotheses"].extend(added_h)
    hp.write_text(json.dumps(h, indent=1) + "\n", encoding="utf-8")
    print(f"hypotheses.json: +{len(added_h)} (total {len(h['hypotheses'])})")

    ip = ROOT / "registry" / "irregularities.json"
    d = json.loads(ip.read_text())
    have = {x["id"] for x in d["items"]}
    added_i = [x for x in IRREGULARITIES if x["id"] not in have]
    d["items"].extend(added_i)
    ip.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    print(f"irregularities.json: +{len(added_i)} (total {len(d['items'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
