# Why the catalogue-hidden holdout proxy cannot reward off-catalogue discovery

## The structural problem

The DrivenData metric is the **Distance-Weighted Tversky Index (DTI)** with
`α = 0.2` (false-positive penalty), `β = 0.8` (false-negative penalty), and a linear
300 m triangular kernel:

```
k(d) = max(1 - d/300, 0)
TP_p = sum over predicted pixels of k(d(pixel, ground-truth))
TP_g = sum over ground-truth pixels of k(d(ground-truth, predicted))
TP_w = (TP_p + TP_g) / 2
DTI = TP_w / (α·|P| + β·|G| + β·(TP_g - TP_p))
```

The official NREL/TP-5700-96647 rules document defines the metric in
[Eq. 1, page 5](https://docs.nlr.gov/docs/fy26osti/96647.pdf).

The competition scores every submission **twice** ([problem description, page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)):

1. **Round 1** &mdash; against the faults the experts mapped *before* the competition
   (the "visible catalogue", 60,988 positive pixels in `labels.tif`).
2. **Round 2** &mdash; against an *expanded* truth set that includes faults the
   panel verifies from everyone's submissions.

`β > α` (false negatives weighted 4× a false positive) precisely because the prize organisers
want novel-but-real predictions to be cheap.

## What this implies for an off-catalogue submission

Suppose a submission emits P dots entirely *off* the visible catalogue (Round 1). Then in
Round 1:

* The submission has `FP = P` (every dot is far from any catalogue pixel).
* The submission has `FN = |G_visible|` minus any small kernel weight on the off-catalogue
  pixels (still ≈ 60,988 if the submission is fully off-catalogue).
* `DTI_round1 = TP_w / (0.2·P + 0.8·60,988 + 0.8·(0 - 0))` ≈ 0.

The same submission in Round 2 might score well *if* its off-catalogue dots land on
hidden faults the panel verifies from other submissions. So **a fully off-catalogue
submission has near-zero Round 1 score and a non-zero Round 2 score** &mdash; exactly the
structure of the published 0.2778 file (`gemsdoe32-h33-h33-2-b2-...zeros.tif`, 37,654 dots,
0 within 200 m of catalogue).

## What this implies for our local holdout

The `catalogue_hidden_mean` proxy in our holdout uses the **visible** catalogue as truth,
because that is the only labelled truth we have. Any flank-pruned submission scores
near-zero on it *by construction*. The proxy cannot tell us whether the submission
will score well on Round 2.

The SGMC-calibrated off-catalogue instrument (`sgmc_prevalence_calibrated_dti`) is the
best available local proxy for Round-2-style off-catalogue coverage. It uses the
[USGS Quaternary Fault Slip/Dilation map](https://doi.org/10.5066/P9YL58W6) (62,703
SGMC off-catalogue pixels) re-calibrated to the estimated hidden-test prevalence
(|G_LB| ≈ 12,691 px). Across 9 non-leaking scored DrivenData submissions, it correlates
Spearman ρ = +0.83 with the live LB score (vs catalogue_hidden ρ = +0.14).

## The two-pronged measurement problem

We do NOT claim to know what the live LB score of any artifact in this repository is.
Every number on the site is one of:

1. A `catalogue_hidden_mean` (visible-catalogue proxy) &mdash; useful for round-1 ranking.
2. An `sgmc_prevalence_calibrated_dti` (off-catalogue proxy) &mdash; useful for round-2 ranking.
3. A `drift_corrected_holdout_mean` (composite) &mdash; Pearson r = +0.94 with live LB
   across 9 non-leaking submissions, but not significant at n = 9 (p ≈ 0.06).

The best live-mirrored prediction in GEMSDOE32 (the 0.2778 file) scored 0.10122 on
`catalogue_hidden_mean` and 0.06129 on `sgmc_prevalence_calibrated_dti`. Our
`cotrain-a-b-disagreement-v2-flank3` submission scores 0.00074 / 0.06292 on the same
proxies &mdash; lower on the first, **higher** on the second.

## The implication for the next session

To improve the live LB score of an off-catalogue submission, the next session should
focus on the **off-catalogue coverage**, not the catalogue-hidden proxy. Three concrete
next steps:

1. **Wire the USGS earthquake FDSN catalogue into the B-band prior** (H33-E in the
   predecessor repo, currently data-blocked because `earthquake.usgs.gov` returns HTTP
   000 from this sandbox). The seismicity is the strongest off-catalogue signature we
   have not yet exploited, and the supplied `deq_n100a15` / `ieq_n100a15` bands carry
   no fault-scale information (measured autocorrelation of `ieq_n100a15`: 0.9986 at
   1 km, 0.9935 at 3 km) &mdash; the raw catalogue is the fix.
2. **Try a kernel-weighted emission** instead of binary dot emission, so the flank-pruned
   file can still earn catalogue-hidden credit on the visible catalogue *kernel* (300 m
   triangular) without placing pixels directly on the catalogue.
3. **Run the full GEMSDOE32 multi-source stack** (H33-1..5 + the H32 family) on the
   co-training scaffold and pick the best-of-N candidates by `sgmc_prevalence_calibrated_dti`
   rather than `catalogue_hidden_mean`.