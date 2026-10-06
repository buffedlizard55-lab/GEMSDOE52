#!/usr/bin/env python3
"""Append every evaluation in evidence/ to registry/observations.jsonl (idempotent).

The surrogate is only as good as its training data, so this runs after any holdout or live result:
every arm of a preregistered run, submitted or not, becomes one row.  Re-running it will not
duplicate rows (it keys on ``source:name``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import bo  # noqa: E402

LOG = ROOT / "registry" / "observations.jsonl"


def main() -> int:
    existing = {f"{o.source}:{o.name}" for o in bo.load_observations(LOG)}
    added = 0
    h = ROOT / "evidence" / "holdout_run1.json"
    if h.exists():
        d = json.loads(h.read_text())
        pid = d["preregistration"]["id"]
        for arm, v in d["summary"]["arms_mean"].items():
            key = f"holdout:{pid}:{arm}"
            if key in existing:
                continue
            bo.append_observation(bo.Observation(
                kind="holdout", name=f"{pid}:{arm}", score=float(v),
                n_px=float(d["summary"]["arms_mean_n_px"].get(arm, 0.0)),
                source="run_holdout", design_id=arm,
                note=f"{len(d['folds'])} blocked folds, mean proxy DTI", meta={"prereg": pid}), LOG)
            added += 1
    mc = ROOT / "evidence" / "truth_model_mc.json"
    if mc.exists():
        d = json.loads(mc.read_text())
        for cand, v in d["summary"].items():
            if cand.startswith("paired_") or not isinstance(v, dict):
                continue
            key = f"truth_model_mc:{cand}"
            if key in existing:
                continue
            bo.append_observation(bo.Observation(
                kind="model_mc", name=cand, score=float(v["mean"]), n_px=float(v["px"]),
                source="truth_model_mc", design_id=cand,
                note="mean official DTI over paired generative-model draws",
                meta={"draws": v["n_draws"], "sigma_px": d["truth_model"]["sigma_px"]}), LOG)
            added += 1
    for name in ("emission_models_mc.json", "shipped_vs_incumbent_mc.json"):
        f = ROOT / "evidence" / name
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        for cand, v in d["summary"].items():
            if cand.startswith("paired_") or not isinstance(v, dict) or "mean" not in v:
                continue
            key = f"{name}:{cand}"
            if key in existing:
                continue
            bo.append_observation(bo.Observation(
                kind="model_mc", name=cand, score=float(v["mean"]), n_px=float(v.get("px", 0)),
                source=name, design_id=cand,
                note="mean official DTI on paired draws from the live-anchored truth model",
                meta={"draws": d["draws"]}), LOG)
            added += 1
    claims = json.loads((ROOT / "registry" / "claims.json").read_text())["claims"]
    for c in claims:
        key = f"live_score_claim:{c['id']}"
        if key in existing:
            continue
        bo.append_observation(bo.Observation(
            kind="live", name=c["id"], score=float(c["score"]), source="live_score_claim",
            design_id=c["id"], live=float(c["score"]), live_verified=False,
            note=f"OWNER CLAIM: {c.get('file','')}"), LOG)
        added += 1
    print(json.dumps({"log": str(LOG), "added": added, "total": len(bo.load_observations(LOG))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
