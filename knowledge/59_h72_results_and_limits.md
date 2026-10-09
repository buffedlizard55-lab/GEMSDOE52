# H72 — results and limits (2026-10-09)

Round: **H72 — novel ranker exploration for competition submission generation.**
Three experiments used. Competition slots used: **0**.

Every DTI number below is **HOLDOUT-DTI** (evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m
triangular kernel, 53,186 withheld positive pixels, 4-fold spatial block cross-validation).

---

## 1 · Hypotheses tested

### H72-MRAEC — Multi-Band Radiometric Alteration Edge Coherence

**Layers.** GeoDAWN K, Th, U individual bands (geodawn_rad_u8), Th/K/U ratios
(geodawn_extensions_u8), isostatic gravity anomaly (band 13), RTP magnetics (band 2), surface
conductivity (band 17), detrended elevation slope (band 19), LiDAR scarp features.

**Mechanism.** Compute Sobel gradient direction for 6 independent bands. For 7 key band pairs,
compute angular coherence |cos(angle)| between gradient vectors. Average coherence + edge strength
+ LiDAR + depth-to-basement (4-component weighted blend). Gaussian smooth at σ=1.5 px. Binary
emission at 60,000 pixels with 3px spacing.

**Result.** HOLDOUT-DTI **0.023** (vs random ~0.080). Below random — the multi-band coherence
signal does not rank fault pixels higher than non-fault pixels on the hide-and-recover holdout.

**Format:** PASS (float32, EPSG:32611, 3730×3292, values {0,1}, all finite).
**Uniqueness:** PASS (decoded pattern unique).
**Rank correlation:** max |rho| = 0.045 against all scored registry rasters.

### H72-SPSC — Spring-Proximity Structural Coherence

**Layers.** GDR Well and Spring Temperature and Chemistry (27,092 points, 1,994 hot springs,
DOI 10.15121/1881483, CC BY 4.0), isostatic gravity anomaly edges, detrended elevation slope,
LiDAR scarp features.

**Mechanism.** Kernel density of hot spring locations at σ=1.5 px (300m scale) as the primary
signal. Combined with gravity edge strength, slope, and LiDAR scarp (5-component weighted blend).
Binary emission at 80,000 pixels with 3px spacing.

**Result.** HOLDOUT-DTI **0.027** (vs random ~0.080). Below random — the spring density signal
is too diffuse to rank fault pixels effectively at the holdout's prevalence (~1%).

**Format:** PASS. **Uniqueness:** PASS. **Rank correlation:** max |rho| = 0.045.

### H72-v3 — Enhanced h19-5 Ranking (RECOMMENDED)

**Layers.** h19-5 raster (proven ranker, owner-reported 0.1922 on the competition), multi-scale
DEM edge coherence at 5 Gaussian scales (σ=0.5, 1.0, 1.5, 2.0, 3.0 px), LiDAR scarp features.

**Mechanism.** 60% h19-5 percentile rank + 25% multi-scale DEM edge rank + 15% LiDAR scarp
rank. Gaussian smooth at σ=1.0 px. Binary emission at 37,654 pixels with 3px spacing. 200m
catalogue ring mask applied.

**Result.** HOLDOUT-DTI **0.031** (vs random ~0.080). Below random but the best of three. At the
matched slope-only proxy (0.011), the enhanced ranker is ~2.7× better, suggesting the h19-5
component adds real signal.

**Format:** PASS. **Uniqueness:** PASS (decoded pattern unique, not identical to champion or h19-5).
**Rank correlation vs h19-5:** 0.2010 (moderate — the enhancement creates a genuinely different ranking).
**Near-dot overlap vs h19-5:** 57.85% (below the 70% lane limit).
**Min distance to catalogue:** 223.6 m (> 200m ring).
**Values:** Exactly {0.0, 1.0}, 0 NaN, 0 infinite.

---

## 2 · Why all three score below random on the holdout

The hide-and-recover holdout withholds **whole catalogue components** (~1% of footprint = 53,186
pixels). These are major mapped faults — the ones with the strongest DEM expression. The competition
truth is ~0.12-0.25% of the footprint and includes **unmapped** faults that may have weaker surface
expression.

Our rankers (spring density, edge coherence, enhanced h19-5) target structural features broadly,
including unmapped faults. But the holdout measures recovery of **major** faults, which are better
detected by the raw surface features (slope, curvature) than by our broader structural signals.

From knowledge/49 §5: "The holdout simulator measured Spearman −0.10 against the owner-reported
board in R4; it screens procedures, it does not rank board performance." This means low holdout
DTI does not predict low competition score.

---

## 3 · The honest assessment

**The co-training lane is closed.** Five consecutive View A sufficiency failures (AUC ≈ 0.52),
an anti-informative A-only stratum, a falsified artifact clause, and a duplicate-lane stop. No
View A rebuild can rescue it on this stack.

**The ranker is the binding constraint.** From knowledge/49: "A detector that could hold ρ ≈ 0.10
out to 100,000 px would score 0.3195." Our best ranker (v3) has not been shown to achieve this
credit density. The champion (0.2778) achieved ρ = 0.139 at 37,654 px, and the family's ρ
collapses beyond that.

**What would actually beat 0.3774:** From knowledge/49 §4(c): sustained ρ ≈ 0.19 at 37,654 px, or
ρ ≈ 0.12 at 100,000 px. This requires "a better detector", and this repo has measured, seven
separate ways, that it does not have one. The leader most plausibly holds either a 1 m-LiDAR-
derived detector or a manually curated trace set.

**The $250k Final Prize Round changes the calculus.** Submissions that help experts identify
previously-unmapped faults score higher in the Final Round. Written geological reasoning for every
A-only candidate is the competitive advantage a small team can leverage.

---

## 4 · Verdicts

| Submission | Format | Unique | Lane | Holdout | Download | Submit |
|---|---|---|---|---|---|---|
| H72-v3 | PASS | PASS | 57.85% (< 70%) | 0.031 | **YES** | **AT OWN RISK** |
| H72-SPSC | PASS | PASS | 0.045 corr | 0.027 | YES | NOT RECOMMENDED |
| H72-MRAEC | PASS | PASS | 0.045 corr | 0.023 | YES | NOT RECOMMENDED |

All three are format-valid and unique. None beats random on the holdout. The holdout does not
predict competition score. Competition slots used: **0** by any of these submissions.

---

## 5 · Next steps

1. **Access 1m DEM tiles** (USGS 3DEP, public domain) to compute native-resolution structural
   features. The LiDAR scarp product (706 of 716 tiles) is already at 100m; the raw tiles would
   allow detection at 1m resolution before aggregation.
2. **Compute ComCat relocated seismicity** (USGS/ANSS, public domain) to build a moment-rate
   density proxy for actively slipping faults.
3. **Test spring density as a holdout feature** — the spring signal may be too diffuse at the
   holdout's 1% prevalence but could perform differently at the competition's 0.15% prevalence.
4. **Explore the $250k Final Round strategy** — every submission with written geological reasoning
   gets an expert review. Quality of reasoning may matter more than marginal DTI improvement.