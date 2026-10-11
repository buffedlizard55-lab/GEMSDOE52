#!/usr/bin/env python3
"""Preserve the historical H60 budget amendment without treating it as a score rule.

This legacy record selected a budget using an internal hide-and-recover diagnostic and
owner-reported score labels. The diagnostic lacks the metadata needed for a reportable
HOLDOUT-DTI claim; the score labels have no organizer file/hash receipt. Small-sample rank
associations are exploratory and are not evidence of causality, leaderboard calibration, or
submission eligibility. This script is retained for provenance and should not be rerun as a
current selection procedure.
"""
import json, sys
from pathlib import Path
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"
BOARD = {  # owner-reported filename attribution, NOT organiser-authenticated
 'champion_h33_2_b2': 0.2778,
 'gems24-h25-1-dotted-h19-5-d2-8-202': 0.2600,
 'gems24-h25-1-dotted-h19-5-d1-5-202': 0.2477,
 'gems27-topo-gap-closure-t-v2-on-d1': 0.2449,
 'gems19-h19-5-powerlaw-budget-multi': 0.1922,
 'gems16-h16-1-topo-geophys-baseline': 0.1855,
}
pc = json.loads((EV / "h60_prior_control.json").read_text())
iv = json.loads((EV / "h60_instrument_verdict.json").read_text())
sel = json.loads((EV / "h60_selection.json").read_text())
rows = sorted(((BOARD[k], pc[k]["mean_px"]) for k in BOARD if k in pc), key=lambda r: -r[0])
best_board, best_mass = rows[0]
masses = [r[1] for r in rows]; boards = [r[0] for r in rows]
rho = float(spearmanr(masses, boards).statistic)
if rho > -0.9:
    print(f"[amendment] NOT APPLIED: board-vs-mass Spearman {rho:.3f} is not monotone enough")
    sys.exit(1)
out = dict(
  amends="registry/h60_preregistration.json", reason="N-4: recorded as an amendment with the "
  "fitted numbers, never applied silently",
  registered_choice=sel["selected"],
  registered_budget=int(sel["selected"]["budget"]),
  amended_budget=int(round(best_mass)),
  arm_unchanged=sel["selected"]["arm"],
  evidence=dict(
    champion_instrument_dti=iv["champion_instrument_dti"],
    placeholder_instrument_dti=iv["placeholder_instrument_dti"],
    champion_scores_below_random_placeholder=bool(iv["champion_instrument_dti"]
                                                 < iv["placeholder_instrument_dti"]),
    spearman_board_vs_instrument=iv["spearman_board_vs_instrument"],
    spearman_p_value=iv["p_value"],
    off_catalogue_family=[dict(board=b, mean_px=int(round(m))) for b, m in rows],
    spearman_board_vs_mass_off_catalogue=rho),
  decision=(f"Historical H60 budget amendment to {int(round(best_mass))} px, preserved only as "
           f"provenance. It was derived from owner-reported score labels and a legacy internal "
           f"diagnostic; neither is a current competition ranking or causal score explanation. "
           f"The six-label mass association (Spearman {rho:.3f}) and 13-label diagnostic association "
           f"(Spearman {iv['spearman_board_vs_instrument']:.3f}, p={iv['p_value']:.3f}) are "
           f"exploratory and not submission evidence."),
  not_claimed="this is a budget choice, not a score forecast; no organiser-authenticated "
              "score-to-file mapping exists")
(EV / "h60_budget_amendment.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
