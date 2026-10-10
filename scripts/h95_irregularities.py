#!/usr/bin/env python3
"""Add/refresh the IR-H95-* entries in registry/irregularities.json (idempotent: same id is replaced)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "registry/irregularities.json"
E1 = json.loads((ROOT / "evidence/h95_e1_h87_holdout.json").read_text())["pooled"]["scores"]



def ent(i, sev, status, title, what, how, effect, handling, disp):
    return dict(id=f"IR-H95-{i:03d}", round="H95", severity=sev, status=status, title=title, what_it_is=what,
                how_we_know=how, measured_effect=effect, handling=handling, disposition=disp)


new = [
    ent(1, "high", "measured and disclosed",
        "The H87 raster was published as the current submission with no holdout evaluation; measured now, its emission rule is below random",
        "README/site on main presented gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif with 'No holdout DTI score yet'. "
        "H95 experiment E1 re-implemented the H87 views from scripts/build_h87_cotrain_wavelength.py (sha recorded) and scored them on gems52-pooled-hide-v1.",
        "evidence/h95_e1_h87_holdout.json (HOLDOUT-DTI, 53,186 withheld positive px, 1,000 paired cluster-bootstrap draws).",
        f"h87_disagreement {E1['h87_disagreement']['dti']:.6f} [{E1['h87_disagreement']['ci95'][0]:.4f}, {E1['h87_disagreement']['ci95'][1]:.4f}] vs random "
        f"{E1['random']['dti']:.6f}; h87_single_A {E1['h87_single_A']['dti']:.6f}, h87_single_B {E1['h87_single_B']['dti']:.6f}, h87_union_max {E1['h87_union_max']['dti']:.6f}.",
        "H87 is labelled research-only / do not upload wherever H95 publishes; no promote verdict without a measured holdout (same rule as IR-H89-003).",
        "closed for H87: negative"),
    ent(2, "medium", "open - disclosed",
        "The brief names 0.3195 as the score to beat, but the official leaderboard #1 is 0.3774",
        "The session brief says 'the leaderboard high is 0.3774' and also asks to beat 0.3195. On the official leaderboard fetched 2026-10-10, 0.3195 is rank #8 (DARD); #1 is xiaofanhu 0.3774; our best owner-reported score is 0.2778 (#22).",
        "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ (fetched 2026-10-10).",
        "Both bars are reported; P(Win) is judged against 0.3774 (rank 1) and top-5 prize money against 0.3300 (#4) / 0.3262 (#5).",
        "Report both, never conflate.", "disclosed"),
    ent(3, "medium", "open - instrument limitation",
        "The off-catalogue SGMC proxy that ranks the board in the right order is dominated by emitted mass",
        "Segment-thinned SGMC-off-catalogue truth (|G| 10k) gives Spearman +0.567 vs 13 owner-reported board scores (0.911 excluding a lattice probe), but emitted mass alone gives -0.889, and the lattice probe r13 is an outlier (0.0757).",
        "evidence/h95_board_instrument.json (DIAGNOSTIC).",
        "Spearman vs board, n=13: catalogue-anchored hide-and-recover -0.49 on this 13-file set; SGMC all -0.539; "
        "SGMC off-catalogue unthinned +0.162; segment-thinned |G| 10k +0.567; emitted mass alone -0.889.",
        "Used only to choose between two pre-registered budgets (frozen rule); never reported as a score and never used for promotion.",
        "kept as diagnostic"),
    ent(4, "low", "deviation - more conservative",
        "Lane/uniqueness roots widened beyond the frozen preregistration list",
        "registry/h95_preregistration.json lists data/scored, data/reference, submission/, docs/downloads/. The gates stage also scans work/h95/priors, the 526-blob sibling-repository census restored by scripts/fetch_prior_inventory.py via api.github.com.",
        "scripts/run_h95.py stage_gates; work/h95/prior_fetch_receipt.json.",
        "More priors can only make the uniqueness and lane gates harder to pass.",
        "Disclosed in the run card 'deviations'.", "accepted"),
    ent(5, "medium", "resolved by rename",
        "Round identifier collision: this round ran as H88, but main acquired H88-H94 from parallel sessions before merge",
        "The session froze its protocol as H88 (registry + knowledge doc). Between branch creation (bc26fe2) and merge, main merged PR #89 (H89, H78) and later PRs carrying H88, H89-H92, H93 and H94. A second fetch at publish time showed main already holds a different H88 round (cotrain-strict-AB).",
        "git fetch origin main; git ls-tree origin/main shows evidence/h88_run_card.json, knowledge/80_h88_preregistered.md, docs/downloads/h88-candidate.tif from another session.",
        "Identifier-only rename H88 -> H95 (next free). The frozen preregistration keeps its bytes (knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md; SHA-256 pin still matches registry/h95_preregistration.json 'frozen_under_label': 'H88'). Hypothesis ids inside it (H88-1..H88-5) map to H95-1..H95-5. No file of the other H88 round was touched.",
        "Rename, fast-forward to main, then insert H95 blocks idempotently.", "resolved"),
    ent(6, "high", "measured - lane duplicate, verdict stays SUBMIT NO",
        "The H95 raster is a lane near-duplicate of the parallel H93 raster that reached main one minute after our build",
        "H95 built its file at 22:35:22Z; the other session's gems52-h93-abs-cotrain-37654px-20261010T223629Z-zeros.tif (View B + four basement-step channels, same shared H61 View B learner) was written at 22:36:29Z and merged to main while the H95 gates ran. Both fields sit close to the shared single-view-B stitched field (H95 cotrain_B is statistically equal to single_B: paired delta CI spans 0).",
        "scripts/h95_supplemental_closure.py -> evidence/h95_gates.json 'supplemental_closure_after_merge' (shared gems52.gates.lane_report, unmodified).",
        "0.8048 of H95 dots lie within 3 px of the H93 file's dots while that file's 3 px halo covers only 0.1435 of the footprint (about 5.6x chance); not identical (Jaccard 0.0999).",
        "Per the brief's lane rule (>70% within 3 px of one registry raster) this is a duplicate: stop. Combined with the failed holdout gate the H95 file is research-only.",
        "SUBMIT NO; future rounds should not re-run the shared H61 View B learner with minor channel additions."),
]
d = json.loads(P.read_text())
ids = {e["id"] for e in new}
d["entries"] = [e for e in d["entries"] if e.get("id") not in ids] + new
P.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
print(f"{len(d['entries'])} entries; wrote {sorted(ids)}")
