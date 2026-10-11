# 82 · H97 results and limits (2026-10-10)

Preregistered in [`registry/h97_preregistration.json`](../registry/h97_preregistration.json) and
[`knowledge/80`](80_h97_hypotheses_preregistered.md) before any fit; the frozen draft that was
withdrawn before any fit is disclosed inside the registration file itself.

**Slots used: 0. Competition uploads: 0. Organizer receipts: 0.** Every other team's score quoted here
is an owner-reported leaderboard value.

Receipts: `evidence/h97_holdout.json` (both instruments + independence + canary),
`evidence/h97_credit_curve.json` (the mass lever on the twelve restored owner-reported files),
`evidence/h97_channel_screen.json` (per-channel screening on the prevalence-matched instrument),
`evidence/h97_build.json` + `evidence/h97_run_card.json` (the artifact).

---

## 1 · The lane, measured on the shared instrument (HOLDOUT-DTI)

Instrument: `gems52-pooled-hide-v1` — label-blind quadrants, buffer 80 px, whole catalogue components
hidden, 200 m collar taken from the VISIBLE catalogue only, 9,400 dots per fold per arm,
`nodes.spacing_select` at 3 px, 60,894 withheld positive pixels, 1,000 paired 20 km block-bootstrap
draws. Inputs verified against the manifest pins (features `4371c82e…`, labels `7ba308cc…`).

| arm | HOLDOUT-DTI | 95% CI | note |
|---|---:|---|---|
| `h97_disagree` (primary: A confident, B abstains) | **0.045947** | [0.033706, 0.059307] | below the control |
| `single_A` (potential-field edge family alone) | 0.068460 | [0.055921, 0.081430] | single-view baseline |
| `single_B` (surface family alone) | 0.054606 | [0.041452, 0.068289] | single-view baseline |
| `random` (same allowed set, same budget) | **0.076551** | [0.068175, 0.084557] | floor control |

* Paired: `h97_disagree` − `random` = **−0.030604** [−0.043238, −0.016560]. The primary is *below* the
  control, and both single-view baselines are below it too. **Verdict: NEGATIVE** on this instrument —
  the round's frozen promotion rule fails on the first clause.
* Leakage canary: max per-arm AUC 0.5888 (`single_B`), alarm 0.90 → no alarm. No channel reads a label.
* Independence (the Blum–Mitchell premise, brief-mandated): 6,390 blocks of 50×50 px on catalogue-zero
  proxies inside each fold's TRAIN domain — Spearman **0.089** (MSE) and **0.097** (FPR), far below the
  0.60 abandonment threshold. The views *are* independent; independence without sufficiency simply
  cannot donate anything here, which is the same result the repository has recorded eight times.

## 2 · The mass lever, measured where it belongs (new instrument)

`knowledge/76` §6 named the blocker: the H83 off-catalogue instrument over-rewards recall (55,562 truth
px against an incumbent |G| bracket of ≈14,000). H97 fixed that by thinning the same truth to
**14,089 px** with a fixed seed (`gems52-offcatalogue-prevalence-matched-v1`).

| emitted budget K | field DTI | matched random | credit per dot |
|---:|---:|---:|---:|
| 8,000 | 0.001125 | 0.016399 | 0.00181 |
| 15,000 | 0.002386 | 0.028108 | 0.00227 |
| 25,517 | 0.003488 | 0.042326 | 0.00224 |
| 30,000 | 0.004004 | 0.046632 | 0.00231 |
| 37,654 | 0.005023 | 0.053372 | 0.00251 |

* The field is **10× worse than random** at every budget: the emitted budget was *not* the binding
  problem. `K* = 37,654` under the frozen rule (`best_K_measuring = null`), and the round therefore
  cannot promote on the mass lever either.
* The reference champion file (`data/reference/h33-2-b2-zeros.tif`, owner-reported 0.2778, scored as-is
  for context, never re-emitted) gets **0.068021** on this instrument against a matched random
  **0.053372** — a lift of only +0.0147 at 37,654 px. So even the best owner-reported file in this
  family is weakly separated from random *on this proxy truth*, which is a limit of the proxy as much
  as of the file, and is reported as such.
* Mass lever on the twelve restored owner-reported files (`evidence/h97_credit_curve.json`):
  Spearman(mass, score) **−0.928**, log–log elasticity **−0.917**; inverting the published identity at
  |G| = 14,088.7 px puts the implied credited mass in **4,620–6,824** while emitted mass spans
  37,654–343,816. Arithmetic targets (not forecasts): at the champion's implied `T = 5,223.1`, DTI
  0.3195 needs `S ≤ 25,384`; at the champion's `S = 37,654`, it needs `T ≥ 6,007` (+15.0 %).

## 3 · The screening that explains the negative — and contradicts the brief's B-only prior

Same prevalence-matched instrument, same budget and placement, one channel at a time
(`evidence/h97_channel_screen.json`; random mean **0.051925** over three seeds):

| channel | DTI | lift vs random |
|---|---:|---:|
| `band12_curv` (DEM curvature σ2, alone) | **0.117263** | **+0.065337** |
| `b_only` (View B confident, View A abstains) | **0.109480** | **+0.057555** |
| `view_B_rank` (the surface family) | 0.095051 | +0.043126 |
| `view_A_rank` (potential-field edge family) | 0.043752 | −0.008173 |
| `band2_rtp_grad` | 0.042446 | −0.009479 |
| `band18_grav_hg` | 0.029520 | −0.022405 |
| `band6_rad` (radiometric TC) | 0.025058 | −0.026867 |
| `cover_pct` (band 15 rank) | 0.013665 | −0.038260 |
| `h97_disagree` (this round's primary) | 0.005023 | −0.046902 |

**Reading.** On off-catalogue truth the *surface* view carries the signal and the *potential-field edge*
family is anti-informative; the lane's B-only case — which the brief tells us to read as surface
artefacts — is the strongest lane-compliant arm measured in this session. That is the opposite of the
brief's stated prior for that case, and both are recorded (`registry/irregularities.json`
IR-H97-003). The screening is **not promotable in itself** (post-hoc arm selection is forbidden in this
repository); it is the prior belief for H98, whose arm was frozen before its own fit and validated on
the *other* instrument.

**Mechanistic reading of the failure.** View A here is a rank of gradient *magnitude*: it is large over
outcrops and range fronts and small over basins. Requiring it to be confident while View B abstains
therefore selects *flat, high-gradient-magnitude* ground — the least fault-like combination for the
off-catalogue population. A physically-motivated View A edge map (directional ridges rather than
magnitude) is the natural next attempt; magnitude ranking is now measured as the defect.

## 4 · The artifact (download-only)

* `submission/gems52-h97-cotrain-disagree-sparse-37654px-20261010T224136Z.tif` (also
  `docs/downloads/h97-candidate.tif`), 37,654 dots, binary, min dot separation ≥3 px, 200 m catalogue
  ring respected, all pixels finite in [0,1], no nodata tag. Name `h97-cotrain-sparse-37654px`
  (29 chars), note 117/140 chars — both in `evidence/h97_build.json`.
* SHA-256 `eed99c0b544b1731a4dd2e10c2f4db65a90316e149c3c4a6673256459d95f5f2`; zip
  `59691c56cf1fb63f0da11bbed062119eeed7b1adbc6f70aef0dd2ee36e23c6fb`; single-TIFF zip round-trip verified.
* Format: 14/14 on-disk checks pass, `gates.format_report ok = True problems = []`.
* Uniqueness (147 priors, `evidence/h97_build.json`): `canonical_pattern_unique = True`,
  `identical_to_a_prior = False`, novel fraction 0.672518, relation `strictly-novel-and-selective`.
* Not merely the union: the candidate is the disagreement field's own top-K, not the union of the
  single-view top-K sets — 2,136 of 37,654 cells (5.67 %) lie inside that union, Jaccard 0.0193,
  `candidate_equals_union = False`.
* **Lane, reported verbatim both ways.** Literal (every aligned prior): `DUPLICATE/STOP` — one
  near-offender, `data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, whose 3 px halo covers
  **99.90 %** of the eligible area (a universal-coverage probe by the shared template's own definition,
  `gates.py` H61 repair; ρ 0.00036). No admissible raster can pass the literal rule against a probe of
  that kind. Policy (priors that localise something, 146 informative + 1 probe): `PASS`, max ρ 0.02569,
  max near-3 px 0.41456, and that maximum's source is **this repository's own H87 candidate**, not a
  third-party raster. Against the board-winning `h33-2-b2-zeros.tif`: ρ −0.00584, 3.61 % within 3 px.
  Against our own H87 raster the exact-cell overlap is 1,235 of 37,654 (Jaccard 0.0167) — a different
  emission, not a re-emanation of the previous round.
* **Verdict: negative → download only.** `approved_for_weekly_slot = False`, `slots_used = 0`,
  `docs/data/submission_h97.json` mirrors the receipt; `submission/LATEST.txt` is deliberately **not**
  rewritten, because this file is not the round's promoted output.

### 4.1 · The gate demonstrably bites (disclosed incident)

The first build crashed after writing the artifact but before writing receipts (a self-copy of the
reasoning CSV). The second build then compared its candidate against the crashed run's leftover copy —
a different filename, same bytes — and correctly returned `identical_to_a_prior = True`,
`canonical_pattern_unique = False`, lane `DUPLICATE/STOP`. That is the uniqueness gate doing its job on
a stale copy of itself. The stale copies were moved out of `submission/`, no gate was relaxed, and the
third build is the receipt cited above (147 priors, `identical_to_a_prior = False`). The full per-prior
lane table is `evidence/h97_lane_dots.json`.

## 5 · Limits

1. Both instruments measure *catalogue-linked* truth families (hidden catalogue segments; SGMC faults
   absent from the catalogue). Neither is the organizer's scored population, and the repository has
   measured that board and instrument are not correlated here.
2. The prevalence-matched instrument fixes the *recall* bias of the H83 instrument; it does not fix the
   population bias (SGMC is itself a published survey, so unknown parts of it may sit in the
   organizer's excluded set).
3. Screening is a single-instrument, single-budget measurement; it is a prior belief, not a validation.
4. Nothing in this round touches the organizer's hidden truth, and no upload was made, so no board number
   is claimed.

### 4.2 · What the three-pass review caught (fixed before publication)

The review asked the CSV the brief demands as a deliverable to justify its own columns, and found two
defects in the *reasoning file* — not in the raster, whose receipts were unaffected:

1. **Coordinates.** `lon`/`lat` were produced by feeding pixel indices straight into the reprojection, so
   the first rows read `lon -121.48, lat 0.0` for a Nevada site: a plausible-looking longitude beside a
   latitude of exactly zero. The values are now computed from the file's own affine transform
   (pixel → metres → degrees) and verified against an independent `pyproj` transform; the first row now
   reads `-119.291688, 40.704677`.
2. **A mislabelled column.** `lidar_scarp_3px` was the *coverage* band of the lidar feature stack
   (`valid`, 1 where lidar data exist), not a scarp response at all. The CSV now carries
   `lidar_scarp_max_3px` (maximum of the eight scarp-response bands within 300 m), `lidar_valid`, and
   `locally_falsified_by_lidar`, and the falsifier sentence states which of the two cases applies at that
   dot instead of asking the reader to infer it.

Both fixes are in `scripts/build_h97_submission.py`; the round's receipts were regenerated afterwards
(the raster bytes are unchanged: SHA-256 `eed99c0b…` before and after, because the field, placement and
budget did not change). The bug class is recorded here because it is the same one that bit `h97.py`
earlier in the session — a name reused for two different quantities — and because neither defect would
have been caught by any test in the repository.
