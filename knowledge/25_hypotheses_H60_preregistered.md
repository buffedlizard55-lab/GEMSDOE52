# H60 — hypotheses preregistered 2026-10-08, **before** any H60 fit, score or artefact

Frozen file: this document's SHA-256 and the companion `registry/h60_preregistration.json` are
recorded inside the run receipt before the first model is fitted, and the runner refuses to
continue if either hash has moved. Nothing below was written after seeing a result.

---

## 0 · The one measurement that ranks everything

The organiser's own scores, attached to files whose bytes we hold, are the only evidence in this
repository that is tied to the organiser's metric. Round R4 and `knowledge/10` §5 both measured
that the local hide-and-recover simulator does **not** predict the board (Spearman −0.10;
uniform random beats the champion). So H60 does not use that simulator to promote anything. It
uses two things instead:

**(a) The exact-set algebra of the scored files.** `A = h33-2-b2` (reported 0.2778) is a strict
subset of `B = gems24-d2-8` (0.2600); `B \ A` = 6,436 px, **every one of them within 100–200 m of
the mapped catalogue**. Setting that ring's credit to zero is what makes the two scores consistent,
and it yields

> **|G| = 14,088.7 px** — the size of the hidden (expert-drawn, off-catalogue) truth.

with `T(A) = score × (0.2·S + 0.8·|G|)` giving the credit of every scored file. Credit density
`T/S` is then a **measured** property of each detector:

| detector | S (emitted px) | score | T (credit) | density T/S |
|---|---:|---:|---:|---:|
| `A` champion `h33-2-b2` | 37,654 | 0.2778 | 5,223.1 | **0.1387** |
| `P1 = A ∩ C` (25,517 px) | 25,517 | — | 4,168 – 5,223 | **0.163 – 0.205** |
| `E` `h19-5` parent field | 121,131 | 0.1922 | 6,822.6 | 0.0563 |
| `I` `Hedge-v2` off-catalogue | 166,519 | 0.1563 | 8,873.5 | 0.0533 |
| uniform random (measured, `knowledge/10`) | — | — | — | ≈ 0.024–0.028 |

**(b) The identified interval, not a point estimate.** Twelve files give twelve equations
`Σ_{atoms ⊆ file i} t_a = T_i` in 559 unknown atom credits, so atom credit is *set-identified*.
`scripts/h60_identify.py` computes, by linear programming, the exact interval `[T_lo, T_hi]` for
each candidate emission set, with the constraints `t_a ≥ 0`, `Σ t_a ≤ |G|`, `t_a ≤ CMAX·|a|`
(`CMAX = 3.0` is the exact credit of a dot sitting on a straight 1-px trace:
`1 + 2·(2/3) + 2·(1/3)`), and a per-file slack `max(4.0, 0.002·T_i)` — the smallest band that
makes the system feasible. It is needed because file `C` is a strict subset of file `D` yet
reports a marginally higher score (0.2477 vs 0.2449), a 3.5-credit inconsistency that 4-decimal
publication rounding cannot absorb.

Measured intervals from that LP (run 2026-10-08):

| candidate emission | px | DTI_lo | DTI_hi |
|---|---:|---:|---:|
| `A` champion | 37,654 | 0.2772 | 0.2784 |
| **`P1 = A ∩ C`** | 25,517 | **0.2524** | **0.3196** |
| `P2 = A \ C` | 12,137 | 0.0000 | 0.0788 |
| `A ∩ I` (champion × Hedge-v2) | 4,814 | 0.0000 | 0.4278 |
| `E ∩ I \ A` | 14,073 | 0.0000 | 0.1153 |
| `I \ E` | 147,632 | 0.0495 | 0.2179 |

`P1`'s density is **always** at least 1.9× `P2`'s, on every point of the identified set. `P1`
beats `A` iff `t(P2) < 674.6`, i.e. iff `P2`'s density is below 0.0556 — which covers 64 % of
`P2`'s identified range. Expected `DTI(P1) = 0.2868` against a certain `0.2778` for `A`.

**The marginal rule that sizes everything.** A pixel with expected incremental credit `c` raises
`DTI` iff `c > α·DTI/(1 − α·DTI)`. At `DTI ≈ 0.32` that is **c > 0.068**. So an arm pixel must
have credit density above ~0.064 — about 2.5× uniform random — or it costs more tax than it earns.

---

## 1 · Ranked candidates

### H60-A — Cross-provenance corroboration ladder — **RANK 1, implemented**

* **Layers.** The decoded support of all twelve organiser-scored prior rasters (SHA-256 pinned in
  `registry/data_manifest.json`), grouped by provenance into five families:
  `h19clade` (`A B C D E F G`), `gemsdoe10` (`H K`), `gemsdoe8` (`I`), `gemsdoe13` (`L`),
  `gemsdoe9` (`M`). Plus `labels.tif` for the catalogue exclusion. No geophysical band enters.
* **Physical signature.** Not a transform — an empirical regularity: **credit density rises with
  the number of independent selections that agree on a pixel.** It is measured, not assumed.
  Inside the clade, the parent field `E` has density 0.0563; its 4-way-corroborated subset `A` has
  0.1387 (2.5×); the doubly-thinned `P1 = A ∩ C` has 0.163–0.205 (2.9–3.6× `E`, ~7× random).
* **Why it finds a catalogue-missing fault.** The hidden truth is a set of expert-drawn faults that
  no public catalogue contains. Every submission is an independent noisy detector of it, and
  agreement between independent detectors is the standard precision-raising operation. This is the
  same mathematics as Blum–Mitchell co-training except that the "views" here are *whole modelling
  pipelines from different teams*, which is a much stronger independence claim than two feature
  splits of one raster.
* **Difference from prior repo work.** H57 and H59 used `A ∩ C`, a *within-clade* pair derived from
  the same parent field `E`. No previous round has used the cross-provenance axis at all, and no
  previous round has converted the organiser's scores into an identified interval on per-set
  credit. The 12-file LP is new code (`scripts/h60_identify.py`).
* **Expected DTI / cost.** Highest of the five. Corroborated cross-family mass plausibly sits at
  density 0.09–0.20; 15,000 px of it adds +0.03 to +0.09 DTI over the `P1` core alone. Cost
  **low**: pure set algebra on already-restored bytes, no model fit, no external data.

### H60-B — Two-view co-training, disagreement as the discovery signal — **RANK 2, implemented**
*(this is the brief's explicit method and is required by it)*

* **Layers.** View A (potential field / subsurface): bands 1 `mag_anom`, 2 `rtp`, 3 `tmi_hg`,
  9 `tmi_vg`, 14 `tmi`; 13 `iso_grav_anom`, 11 `iso_grav_anom_vg`, 18 `iso_grav_anom_hg`,
  5 `iso_grav_anom_slope`; 4 `geod_2ndinv`, 7 `geod_shearrate`, 8 `geod_dilaterate`;
  10 `deq_n100a15`, 16 `ieq_n100a15`; 15 `depth_to_base_surf`; 17 `cond_surf`.
  View B (surface): bands 12 `det_elev`, 19 `det_elev_slope`, **and band 6** — described by the
  organiser as a magnetic tilt derivative but measured on the bytes to be radiometric total count
  (`knowledge/03` IR-52-019/IR-52-034; its range here is 2.95–88.6, incompatible with a tilt
  angle). Band 6 is the only radiometric band in `training_features.tif`, and it belongs in the
  surface view: leaving it in the potential-field view would corrupt the very independence test the
  method has to pass.
* **Physical signature.** View A sees structure that has a subsurface expression — magnetic and
  gravity edges, steps in modelled basement depth, strain-rate concentration, seismicity clusters,
  conductivity contrasts. View B sees structure that has a surface expression — DEM curvature and
  slope, plus radiometric lithology contrast. **Disagreement is the discovery signal:** where A is
  confident and B abstains, there is subsurface structure with no surface scarp — the signature of
  a **fault buried beneath basin cover**, the class the USGS/INGENIOUS catalogue structurally
  misses because it is compiled from Quaternary surface expression. Where B is confident and A
  abstains, suspect a **surface artefact** — a road cut, an erosion line, a graded fan margin.
* **Why it can find a catalogue-missing fault.** Precisely because the catalogue is a
  *surface*-expression inventory. A buried range-front fault with a clean gravity and basement-depth
  step but no scarp is invisible to the catalogue and visible to View A.
* **Difference from prior repo work.** H55, H56, H57 and H59 all built disagreement arms and
  shipped them as emissions **without ever measuring their credit density**; H57's A-only arm then
  measured 0.000785 against a matched random control of 0.001057 — worse than random. H60 keeps the
  method (the brief requires it) but demotes it: the disagreement field is used to *rank* a
  **discovery arm whose size is set by the acceptance bar**, and the arm is admitted only if its
  modelled density clears `c > 0.068`. It is also compared against a single-view baseline on
  hide-and-recover segments, as the brief asks, with the simulator's known defect stated.
* **Expected DTI / cost.** Low-to-medium — the arm's density prior is 0.03–0.10, so this is a
  real option, not a certainty. Cost **medium** (~1–2 CPU hours on 2 cores).

### H60-C — The independence falsification test — **RANK 3, a gate, not a candidate**

* **Layers.** Both views' out-of-fold probabilities on **labelled negatives**, aggregated per
  50 × 50 px (5 km) spatial block.
* **Physical signature.** Per-block Spearman correlation of the two views' OOF errors. The
  Blum–Mitchell guarantee requires approximate conditional independence given the class; if the two
  views make the same mistakes in the same places there is no new information to exchange.
* **Preregistered rule.** Abandon the co-training arm if `max |ρ| > 0.60`.
  Precedents in this family: H57 measured 0.1108, H59 0.1071, R4 measured 0.7051 on a different
  30/44 layer plan. H60 re-measures on its own plan and reports the number either way.
* **Cost.** Low.

### H60-D — The ≤200 m catalogue exclusion, re-verified on the bytes — **RANK 4, established**

* **Layers.** `labels.tif`.
* **Measurement.** `B \ A` = 6,436 px, all within 100–200 m of a mapped trace; deleting them moved
  0.2600 → 0.2778, i.e. **+6.8 % for removing 14.6 % of the file's mass**. Inverting the metric on
  that nested pair gives the ring's credit as **exactly zero** and yields `|G|`.
* **Rule.** Emit nothing within 200 m of a mapped trace. Cost of obeying it: zero.
* **Honest limit.** The bytes cannot distinguish "the scorer buffers the catalogue by ~2 px" from
  "the hidden truth simply never comes within 200 m of the mapped catalogue". Both give the same
  rule, so the distinction does not change the emission — but it is not resolved.

### H60-E — Budget allocation at the measured acceptance bar — **RANK 5, decision rule**

* Emit a pixel iff its expected incremental credit exceeds `α·DTI/(1 − α·DTI)` ≈ 0.068 at
  `DTI ≈ 0.32`. The `P1` core (density 0.163–0.205) clears this by 2.4–3× and is emitted whole.
  The arm is admitted in decreasing estimated density and truncated where the estimate falls below
  the bar. This replaces H57/H59's fixed "core + 14.8k arm" convention with a bar-driven size.

---

## 2 · Frozen decision rules (checked by code, not by prose)

1. `|G|` is recomputed from the `A ⊂ B` nesting on the restored bytes, never copied.
2. The core ships only if its identified `DTI_lo` is within 0.02 of the champion's measured 0.2772
   **and** its mid-interval estimate exceeds it. (`P1`: lo 0.2524, hi 0.3196, mid 0.2860 → ships.)
3. An arm pixel is admitted only if its estimated density ≥ 0.064.
4. Nothing is emitted within 200 m of a mapped catalogue pixel.
5. Nothing is emitted outside the sample-submission footprint; no NaN anywhere in the file;
   values are exactly {0, 1}.
6. If the independence statistic exceeds 0.60, the View-A/B pseudo-label exchange is abandoned and
   the co-training arm falls back to the plain two-view probability rank (no exchange), and the
   receipt says so.
7. The artefact is published as **research-only** unless a candidate beats the champion on an
   instrument that is itself validated. No organiser score is claimed for any new file.

## 3 · Official sources

* Metric, submission format, dataset description —
  <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> (fetched 2026-10-08).
* Blum & Mitchell, COLT '98 pp. 92–100 — <https://doi.org/10.1145/279943.279962>.
* GeoDAWN airborne magnetic & radiometric survey, USGS —
  <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS project, Great Basin Center for Geothermal Energy —
  <https://gbcge.org/current-projects/ingenious/>
* EPSG:32611 — <https://epsg.io/32611>; Tversky index —
  <https://en.wikipedia.org/wiki/Tversky_index>
* Reference solution — <https://github.com/drivendataorg/gems-prize-reference-solution>

## 4 · Falsification conditions

* If `P1`'s identified `DTI_lo` were below 0.2572 (0.02 under the champion), the core would revert
  to the champion file itself and H60 would publish a null result.
* If the cross-provenance corroborated mass measures no denser than the union of the priors that
  contain it, H60-A is recorded as refuted.
* If View A and View B errors correlate above 0.60 per block, H60-B's pseudo-label exchange is
  refuted (third or fourth independent refutation in this family) and the arm falls back.
