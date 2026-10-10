#!/usr/bin/env python3
"""Assemble the H95 JSON run card (protocol-mandated) and knowledge/95 from the receipts only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
L = lambda n: json.loads((EVID / n).read_text())
E1, E2, E3, B, G = (L("h95_e1_h87_holdout.json"), L("h95_e2_lane_holdout.json"), L("h95_e3_proxy_sgmc.json"),
                    L("h95_build.json"), L("h95_gates.json"))
REG = json.loads((ROOT / "registry/h95_preregistration.json").read_text())
prereg_doc = ROOT / "knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md"
prereg_sha = hashlib.sha256(prereg_doc.read_bytes()).hexdigest()
assert prereg_sha == REG["hypothesis_sha256"], "knowledge/93 changed after it was frozen"

tif = ROOT / B["path"]
with rasterio.open(tif) as s:
    a = s.read(1)
vals = sorted(float(v) for v in np.unique(a))
fmt = G["format"]
validator = (f"{fmt['bands']} band {fmt['dtype']}, {fmt['crs']}, {fmt['height']} rows x {fmt['width']} cols, transform/bounds = "
             f"sample_submission.tif: {'yes' if not any('transform' in p or 'bounds' in p for p in fmt['problems']) else 'NO'}, "
             f"{fmt['nan_pixels']} NaN, {fmt['infinity_pixels']} inf, values exactly {vals}, "
             f"{fmt['n_nonzero']:,} emitted cells, nodata tag {fmt['nodata']}; problems: {fmt['problems'] or 'none'}")

s2, s1 = E2["pooled"]["scores"], E1["pooled"]["scores"]
d = E2["promotion"]["paired_vs_single_B"]
U, LS, LD, NU = G["uniqueness"], G["lane_surface"], G["lane_dots"], G["not_the_union"]
gates = {
    "control_reproduction": dict(pass_=E2["control_reproduction"]["ok"],
                                 detail=f"single_B {E2['control_reproduction']['single_B']:.6f} vs H61 {E2['control_reproduction']['target']} (tol 1e-3)"),
    "leakage_canary": dict(pass_=not E2["canary"]["any_alarm"] and not E1["canary_any_alarm"],
                           detail=f"max single-feature AUC {E2['canary']['max_alarm']:.4f} (E2), {max(E1['canary_max_auc'].values()):.4f} (E1); alarm 0.90"),
    "independence": dict(pass_=E2["independence"]["allow_exchange"],
                         detail=f"max |rho| {E2['independence']['max_abs_rho']:.4f} over {E2['independence']['n_blocks']} blocks; abandon >= 0.60"),
    "holdout_promotion": dict(pass_=E2["promotion"]["promote"],
                              detail=f"cotrain_B {s2['cotrain_B']['dti']:.6f} vs bar {REG['promotion']['holdout_bar']}; paired vs single_B {d['delta']:+.6f} [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]"),
    "format": dict(pass_=fmt["ok"], detail=validator),
    "uniqueness": dict(pass_=bool(U["distinct_from_every_comparable_prior"]) and not U["equals_literal_prior_union"],
                       detail=f"{U['n_priors_checked']} priors checked, identical to none: {not U['identical_to_a_prior']}, novel fraction {U['novel_fraction']:.4f}, max Jaccard {U['max_jaccard']:.4f} ({Path(U['max_jaccard_prior']).name}), incomparable {len(U['incomparable_priors'])}"),
    "lane_surface": dict(pass_=LS["literal"]["verdict"] != "DUPLICATE/STOP",
                         detail=f"max Spearman {LS['literal']['max_spearman']:.4f} (bar 0.90); literal {LS['literal']['verdict']}"),
    "lane_dots_policy": dict(pass_=LD["policy"]["verdict"] != "DUPLICATE/STOP",
                             detail=f"literal {LD['literal']['verdict']} (max near-3px {LD['literal']['max_near_3px_fraction']:.4f}); policy {LD['policy']['verdict']} (universal-coverage probes excluded)"),
    "not_the_union": dict(pass_=not NU["is_union"],
                          detail=f"Jaccard vs union-max dots {NU['jaccard_vs_union_dots']:.4f}, vs single-A {NU['jaccard_vs_singleA_dots']:.4f}, vs single-B {NU['jaccard_vs_singleB_dots']:.4f}; {NU['dots_not_in_union']:,} dots not in the union placement"),
}
SC = G.get("supplemental_closure_after_merge")
if SC:
    gates["uniqueness"]["pass_"] = gates["uniqueness"]["pass_"] and SC["distinct_from_every_comparable"] and not SC["identical_to_any"]
    gates["uniqueness"]["detail"] += (f"; supplemental closure vs {SC['n_new_rasters']} rasters merged to main after the gates ran "
                                      f"({SC['commit_range']}): identical to none, max Jaccard {SC['max_jaccard']:.4f}")
    top = SC["near_3px_top"][0]
    gates["lane_dots_policy"]["pass_"] = gates["lane_dots_policy"]["pass_"] and SC["lane_dots_policy"] != "DUPLICATE/STOP"
    gates["lane_dots_policy"]["detail"] += (f"; supplemental closure: {top[0]:.4f} of our dots within 3 px of {top[1]} whose own halo covers "
                                            f"only {top[2]:.4f} of the footprint -> genuine near-duplicate (IR-H95-006)")
gates = {k: dict(**{"pass": v["pass_"]}, detail=v["detail"]) for k, v in gates.items()}
failed = [k for k, v in gates.items() if not v["pass"]]
submit_ok = not failed
why = ("All pre-registered gates passed." if submit_ok else
       f"Failed gate(s): {', '.join(failed)}. " +
       (f"The co-trained field scored {s2['cotrain_B']['dti']:.4f} on HOLDOUT-DTI, below the promotable best {REG['promotion']['holdout_bar']} (paired vs single_B CI spans 0)." if not E2["promotion"]["promote"] else "") +
       (" Its dots are also a lane near-duplicate of the parallel H93 file (IR-H95-006)." if G.get("supplemental_closure_after_merge", {}).get("lane_dots_policy") == "DUPLICATE/STOP" else ""))
K = B["budget"]
ts = B["stem"].split("-")[-3]
name = f"h95-cotrainB-segthin-{K}px-{ts}"
note = (f"H95 co-trained surface view (A->B whole-segment pseudo-labels), {K} binary dots, 3px spacing, 200m catalogue ring cut")
assert len(note) <= 140, len(note)

card = dict(
    round="H95", generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    preregistration="knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md", preregistration_sha256=prereg_sha,
    experiments_used=3, slots_used=0,
    hypothesis=("A View-B (surface: DEM curvature/slope + GeoDAWN radiometrics) learner retrained once with whole-segment "
                "pseudo-labels donated where View A (potential field/subsurface) is confident (rank >= 0.95) and View B "
                "abstains (rank 0.35-0.65) recovers more withheld faults than the single-view View B baseline."),
    mechanism=("Buried normal faults juxtapose basement blocks of different density/susceptibility (View A sees an edge) "
               "while basin fill hides the scarp (View B silent); donating those segments teaches View B the surface "
               "texture of fault-adjacent cover (subtle curvature, radiometric contrast) so it can extend into cover."),
    named_non_fault_mimic=("A-only: buried lithological contact / intrusive margin (a density or susceptibility step with "
                           "no displacement). B-only: section-line roads and graded tracks (cardinal linear curvature) and "
                           "erosion rills / drainage incision on fans (fall-line slope breaks)."),
    disagreement=(f"A-only dots in the shipped file: {G['strata']['a_only']:,} of {G['strata']['total']:,} (each with a reasoning row in "
                  f"the CSV); B-only: {G['strata']['b_only']:,}; both confident: {G['strata']['both_confident']:,}. On the holdout the "
                  f"A-only stratum (disagreement_pre) scores {s2['disagreement_pre']['dti']:.4f} vs random {s2['random']['dti']:.4f}."),
    holdout=dict(evidence_class="HOLDOUT-DTI", evaluator_version=E2["evaluator_version"],
                 withheld_positive_pixels=s2["single_B"]["withheld_positive_pixels"],
                 e2_scores={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in s2.items()},
                 e2_paired_cotrainB_minus_singleB=dict(delta=d["delta"], ci95=d["ci95"]),
                 e1_h87_scores={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in s1.items()}),
    proxy_sgmc=dict(evidence_class=E3["evidence_class"], shipped_budget=E3["shipped_budget"],
                    results={k: v["mean"] for k, v in E3["results"].items()}),
    lane=dict(surface=LS["literal"], dots_literal=LD["literal"], dots_policy=LD["policy"], n_priors=G["n_priors"]),
    uniqueness={k: U[k] for k in ("n_priors_checked", "identical_to_a_prior", "novel_fraction", "max_jaccard",
                                  "max_jaccard_prior", "equals_literal_prior_union")},
    not_the_union=NU,
    raster=dict(path=B["path"], sha256=B["file_sha256"], bytes=B["bytes"], decoded_sha256=B["decoded_sha256"],
                min_dist_to_catalogue_m=B["min_dist_to_catalogue_m"], within_300m=B["within_300m"]),
    validator_output=validator, gates=gates,
    submission=dict(name=name, note=note, note_chars=len(note)),
    verdict=dict(label="promote" if submit_ok else "negative", submit_ok=submit_ok, download_ok=bool(fmt["ok"]), why=why),
    deviations=["Lane/uniqueness roots widened beyond the frozen list to include work/h95/priors (the 526-blob "
                "sibling-repository census restored via api.github.com) — strictly more conservative."],
    limitations=[
        "HOLDOUT-DTI measures recovery of withheld USGS-catalogue faults; the hidden test set is new expert-identified faults NOT in that database, and this instrument's Spearman vs the public board is about -0.10 (IR-H60-003).",
        "PROXY-SGMC (E3) tracks emitted mass as much as placement (|rho| 0.889 for mass alone); it chose the budget but is never a score.",
        "View A (potential field) is insufficient again: out-of-quadrant AUC near 0.5, so it has little reliable signal to donate.",
        "Independence was measured on catalogue-zero proxies, not verified absences.",
    ],
)
(EVID / "h95_run_card.json").write_text(json.dumps(card, indent=1, default=str) + "\n")

# knowledge/95 — results and limits (generated, so no number is typed)
rows = "\n".join(f"| `{k}` | {v['dti']:.6f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}] |" for k, v in sorted(s2.items(), key=lambda t: -t[1]["dti"]))
rows1 = "\n".join(f"| `{k}` | {v['dti']:.6f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}] |" for k, v in sorted(s1.items(), key=lambda t: -t[1]["dti"]))
e3rows = "\n".join(f"| {k} | {v['placed']:,} | {v['mean']:.5f} |" for k, v in sorted(E3["results"].items(), key=lambda t: -t[1]["mean"]))
g = "\n".join(f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in gates.items())
doc = f"""# 82 · H95 results and limits (generated by `scripts/h95_run_card.py` from the receipts)

Verdict: **{card['verdict']['label'].upper()}** — {why} Slots used: 0. Experiments: 3 of 3.

## E2 · co-training lane, HOLDOUT-DTI (`{E2['evaluator_version']}`, {s2['single_B']['withheld_positive_pixels']:,} withheld positive px)

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{rows}

Paired cotrain_B − single_B: {d['delta']:+.6f} [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]. Pseudo-labelled px donated: {E2['pseudo_pixels_total']}.
View sufficiency (out-of-quadrant AUC per fold): A {E2['sufficiency_oof_auc']['view_A']}, B {E2['sufficiency_oof_auc']['view_B']}.
Refit after one exchange: A {E2['refit_oof_auc']['refit_A']}, B {E2['refit_oof_auc']['refit_B']}.

## E1 · first holdout of the shipped H87 rule

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{rows1}

## E3 · PROXY-SGMC (diagnostic only)

| field@budget | dots | mean DTI (5 seeds) |
|---|---|---|
{e3rows}

## Gates

| gate | result | measured |
|---|---|---|
{g}

## Limits

""" + "\n".join(f"- {x}" for x in card["limitations"]) + "\n"
(ROOT / "knowledge/95_h95_results_and_limits.md").write_text(doc)
print(json.dumps(dict(verdict=card["verdict"], failed=failed, name=name, note=note), indent=1))
