# 57a · H71 preregistration amendment — the lane-quiet domain is measured INFEASIBLE; the lane's own rule is enforced as a placement cap instead

**Status: amendment to `knowledge/57` (H71), recorded before the H71 build ran. The frozen thresholds, the
candidate definition, the experiments and the verdict rule of 57 are unchanged.** Written after E1/E2
completed and before E3, when the quiet domain was measured for the first time.

## 1 · What was measured

H71-B as preregistered places the A-only discovery stratum in the **lane-quiet domain**: emitted cells
≥ 3 px from every informative registry prior's positive pixel, so the directed near-dot fraction against
every informative prior is 0 by construction.

The first H71 build measured that domain on the actual registry (553 rasters: 526 census priors + 29 local
submission artefacts, of which 516 informative and 35 universal-coverage probes under the authoritative
`gems52.gates` classification):

* allowed domain (footprint ∩ sample-mask-finite, after the catalogue 200 m exclusion ring): **4,325,298 px**
* union of the 516 informative priors' positive pixels, dilated by 3 px: **covers 100.00% of the allowed
  domain — the lane-quiet domain is 0 px.**

The registry's informative priors do not merely saturate the literal lane rule (that was already
measured: the literal rule fails for every nonempty raster because of universal-coverage probes). Their
3 px halos *collectively blanket* the allowed domain, so **no nonempty emission can have a directed
near-dot fraction of 0 against every informative prior**. H71-B's placement premise is falsified by
measurement, not by preference.

This is the same wall H64 hit from the other side: H64's constrained placement (cap only the current
offenders, iterate) filled 31,487 of 37,600 at the template budget and could not fill even 20,000.

## 2 · The amendment

The lane rule the brief states is: *more than 70% of the emitted dots within 3 px of one registry
raster's dots = drifted into another lane → log as duplicate and stop.* H71's build therefore enforces
**that rule itself** as a placement constraint:

* placement domain = A-only stratum ∩ allowed ∩ **exact-novel** (excludes every informative prior's
  positive pixel — the H64-declared rule, conservative: the union of `> 0` supports is a superset of
  every prior's `≥ 0.5` contour, so the lane's own statistic can only count fewer near-dots than this);
* greedy placement in field order at the preregistered 3 px separation, with a **per-informative-prior
  near-dot cap of `floor(0.70 · B)`** — a candidate cell is skipped if taking it would push any
  informative prior over the lane's 70% bar;
* the budget B is the **largest that still fills** under the caps (scanned downward from the stratum
  capacity at 3 px, floored at 500 dots);
* the dots lane check after placement then verifies the built file against the same rule
  (`gems52.gates.lane_report`, literal + policy), and the run card's verdict rule is unchanged: the
  policy lane must read PASS on the final dots.

This is the lane's own rule applied as a constraint on placement. It is not a re-tuning of the lane, not
a relaxation of the bar, and not a change to the candidate field, the thresholds, or the verdict rule.
If the capped placement cannot fill a usable budget either, the build stops and the round reports
NEGATIVE with the measurement, exactly as H64 did.

## 3 · What does not change

* H71-A (the candidate): strict A-only stratum on the post-exchange OOF ranks, field = rankA on the
  stratum, −inf elsewhere. Unchanged.
* Thresholds: donor ≥ 0.95, receiver abstain [0.35, 0.65], 3 px separation, 200 m catalogue exclusion,
  23,000 build cap. Unchanged.
* Verdict rule: promote only if format + policy lane (surface and dots) + uniqueness both tiers +
  not-the-union + holdout-eligible. Unchanged. The holdout comparison already measured: the candidate
  does **not** beat single_B (paired Δ −0.050144, 95% CI [−0.064233, −0.036779] at the matched budget
  1,264 dots/fold), so the expected verdict is NEGATIVE regardless of how the placement lands.
* Experiment count: E1 (diagnostics) and E2 (exchange + holdout) are done; this amendment governs E3
  (build + audit), the third and last experiment. The round spends no weekly slot.
