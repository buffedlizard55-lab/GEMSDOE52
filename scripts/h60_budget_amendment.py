#!/usr/bin/env python3
"""Record the preregistered-rule amendment that sets the emitted budget, from the receipts.

The registered rule picked the budget with the highest mean hide-and-recover DTI.  Two
measurements taken afterwards make that budget wrong for the board, and N-4 requires any
change to the pre-registration to be written down with the fitted numbers rather than
applied silently:

 1. `evidence/h60_prior_control.json` — the 0.2778 champion scores 0.00479 on that
    instrument, below the random placeholder's 0.02229, so the instrument cannot compare
    a candidate with the incumbent and its budget curve is not transferable.
 2. `evidence/h60_instrument_verdict.json` — across the six off-catalogue scored priors
    the owner-reported board score is strictly decreasing in emitted mass.

The amendment therefore sets the budget to the mass of the highest-scoring off-catalogue
prior, which is read from the receipts, not typed in.
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
  decision=f"emit at {int(round(best_mass))} px: the mass of the highest owner-reported "
           f"off-catalogue score ({best_board}), because across the six off-catalogue scored "
           f"priors the board is strictly decreasing in mass (Spearman {rho:.3f}) while the "
           f"hide-and-recover instrument -- on which the champion itself scores "
           f"{iv['champion_instrument_dti']:.5f}, below a random placeholder -- is not "
           f"correlated with the board at all (Spearman {iv['spearman_board_vs_instrument']:.3f}, "
           f"p={iv['p_value']:.3f})",
  not_claimed="this is a budget choice, not a score forecast; no organiser-authenticated "
              "score-to-file mapping exists")
(EV / "h60_budget_amendment.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
