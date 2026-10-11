# 80a · H88 amendment — the shipped-budget rule (frozen before any H88 fit)

Amendment to [`knowledge/80`](80_hypotheses_H88_preregistered.md). The hypothesis document stays frozen;
this file is the decision rule for how many dots H88 ships, declared **before** the holdout stage runs so
the budget cannot be chosen to flatter a result.

## Rule

1. For the primary arm `corroborated_B`, compute the pooled HOLDOUT-DTI at total emitted budgets
   **18,800** (4,700·4), **25,000** (6,250·4) and **37,600** (9,400·4) dots, same folds, same seeds.
2. Ship the **smallest** total budget whose pooled point estimate is **≥** the pooled point estimate at
   37,600 dots.
3. If no smaller budget clears that bar, ship at 37,600 dots and record the negative.
4. All three 95 % paired spatial-cluster CIs are reported next to the point estimates. The rule uses
   point estimates only and is therefore a **noisy** selection rule; that limitation is stated in the
   run card and in the results note.

## Why this rule exists (measured, ordinal — not a projection)

* The catalogue-side champion line `h33-2-b2` (0.2778, 37,654 px) is a strict subset of `d2-8`
  (0.2600, 44,090 px): the 6,436 px deleted are exactly the pixels inside 200 m of a mapped trace, so
  the deletion was free precision. Both facts are re-measured from the restored bytes in
  `evidence/h88_mass_lever.json`.
* Across the restored scored family the owner-reported score falls monotonically with emitted mass:
  Spearman(mass, score) = −0.928 (n = 13, `knowledge/76` §4, re-measured in `evidence/h88_mass_lever.json`).
* Those two facts say *fewer, better placed dots dominate*. They do **not** say what the optimal budget
  is, and no board score is projected from them anywhere in this round.

## What would falsify the rule

If the pooled DTI at 25,000 dots is below the pooled DTI at 37,600 dots on this instrument, then mass
discipline does not transfer to the instrument's ranking and the round ships the larger file and says so.
