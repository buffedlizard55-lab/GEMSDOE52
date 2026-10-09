# 43 · H66 — frozen pre-registration (co-training lane, one tested candidate, four carried proposals)

**Frozen before any H66 fit, canary, exchange or holdout.** The runner `scripts/run_h66.py` refuses to
run if this file's SHA-256 differs from the value pinned in `registry/h66_preregistration.json`.
Any later change must go in a new dated amendment file, not an edit here.

**Status labels used below:** `MEASURED` (read from bytes or a receipt this session), `REPO` (already
in this repository, cited by file), `UNVERIFIED` (a claim I could not check from a primary source).
`HYPOTHESIS` means a proposal, not a finding.

---

## 0 · Starting facts (re-verified this session, not carried over)

1. **0.2778 anatomy (`MEASURED`, `work/h66/champion_check.json`).** The champion
   `data/reference/h33-2-b2-zeros.tif` (SHA-256 prefix `c55bafc4…`, 37,654 positive pixels, values {0,1}, 0 NaN)
   is a pixel-exact subset of the gems24 d2-8 raster (44,090 positives, NaN background; reported 0.2600).
   The 6,436 removed pixels all lie 100–200 m from the mapped catalogue (min 100 m, median 100 m,
   max 200 m; 5,092 below 200 m and 1,344 at exactly 200 m). The champion adds zero pixels to d2-8.
   The champion's nearest dot to the catalogue is 223.6 m; its median distance is 1,964.7 m.
   Champion spacing is near-lattice (nearest-neighbour min 2.83 px, median 3.00 px).
   **Interpretation boundary:** the subset chain is a pixel fact; the score attribution (which file scored
   0.2778) is owner-reported and unlinked on the board (IR-H65-003).
2. **Public board (`REPO`, dated snapshot `registry/leaderboard_snapshot_2026-10-08.json`, observed
   2026-10-08T21:40:41Z).** #1 xiaofanhu 0.3774; #2 alexoktaba 0.3345; #7 DARD 0.3195; #13 extradr19 0.2778
   (12 submissions). The brief's "0.3195 is the highest" is contradicted by the snapshot (IR-H65-002).
   The live leaderboard page is client-rendered; this session's `fetch_page` returned "Loading…", so the
   snapshot is **not re-verified live** today. It is public-board data, not organiser-confirmed.
3. **Sample description conflict (`MEASURED`).** The DrivenData page describes the sample as predicting
   "total fault absence". `data/sample_submission.tif` has 60,988 ones, all on labelled faults
   (`data/labels.tif`). Logged as IR-H66-001.
4. **Premise status before this round (`REPO`, receipts in `evidence/`).** View A out-of-quadrant AUC:
   H61 0.5163, H63 0.5362, H64 0.5230, H65-A 0.5202. View B: H61 0.6843, H63 0.6862. Pass rule: mean ≥ 0.60
   and minimum ≥ 0.55 (§3). Every View A construction so far has failed it.
5. **Holdout reference (`REPO`, `evidence/h61_holdout.json`).** Best comparable control `single_B` = 0.174517,
   95% cluster-bootstrap CI [0.152316, 0.196299], 53,186 withheld positives, 153 clusters. The H61
   disagreement arm = 0.030584. Random placement = 0.080426.

## 1 · Hypotheses (ranked by expected DTI gain × probability ÷ cost; no numeric gain is claimed)

Expected-gain language is qualitative on purpose. The repo has no measured gain for any of these.

### H66-A · Local-scale, low-capacity View A (THE ONE TESTED THIS ROUND) — RANK 1
* **Layers.** The 14 View A channels whose scale is ≤ 3 px (≤ 300 m, the metric's kernel radius R):
  `A_RTP_grad_1`, `A_RTP_grad_3`, `A_gravity_grad_1`, `A_gravity_grad_3`, `A_cover_grad_1`,
  `A_cover_grad_3`, `A_gravity_cover_signed_1`, `A_gravity_cover_signed_3`, `A_gravity_persistence_1_3`,
  `A_cover_persistence_1_3`, `A_gravity_coherence`, `A_cover_coherence`, `X_mag_TMI_up150_grad1`,
  `X_mag_TMI_up150_grad3`. Excluded: all 16 raw bands (regional bands 10, 15, 16, 17 included), every
  σ = 8 channel, every `_3_8` persistence channel, and `X_mag_TMI_up150_rank` (a rank of an absolute level).
* **Physical signature.** A fault juxtaposes blocks with contrasting density or susceptibility, which
  produces a narrow gradient ridge or sign change at the fault line. The ridge should be local and
  persistent along strike.
* **Named mimic.** Lithologic contacts, intrusion margins, and survey-levelling stripes produce the same
  local edges. A linear readout over local edges cannot separate them, so a positive result would not
  identify faults on its own.
* **Why catalogue-missing.** Blind or under-cover faults with small throw do not reach the mapped
  catalogue, but their local gradient signature should still be present in the potential field.
* **Difference from the repo.** H61 and H64 (View A) used regional raw bands with gradient-boosted
  learners. H63 removed all raw band values (`src/gems52/h63.py` asserts it) but kept gradient boosting, and
  H65-A used cross-strike offsets of two regional bands. No round has tested a monotone (logistic) readout
  restricted to local channels as the sole View A. H66-A tests whether the failure was capacity or location
  memorisation.
* **Cost.** Low, about 30–60 CPU minutes, reusing the H61 runner and the cached store.

### H66-B · Survey-levelling stripe veto on magnetic edges (precision term) — RANK 2, NOT RUN
* **Layers.** Magnetic bands 2 (RTP), 3 (`tmi_hg`), 9 (`tmi_vg`), and their derivatives.
* **Signature.** Gridded aeromagnetic data carry levelling and micro-levelling stripes: long, straight,
  near-parallel, periodic at the flight or tie-line spacing. Stripe-aligned edges are artefacts, not
  faults, so vetoing them removes false positives the disagreement field would otherwise rank high.
* **Repo status.** `REPO`: "survey levelling stripe" appears only as a named confounder in a deferred
  list, unimplemented and unvalidated. No veto exists.
* **Validation (pre-stated, not run here).** Estimate stripe orientation and period from the footprint's
  2-D spectrum with no labels. Veto only edge pixels within ±10° of the stripe orientation. Test on the
  spatially blocked holdout against the same arms. Promote nothing unless it beats the matched control.
* **Cost.** 1–2 hours.

### H66-C · Tilt-angle zero contours (carried from H65-B; not run) — RANK 3, NOT RUN
* **Layers.** Bands 9 (`tmi_vg`) and 3 (`tmi_hg`); tilt θ = arctan(VD / THD).
* **Signature.** Zero crossings of the tilt angle approximate source edges, a sign-aware transform that
  the repo's tested gradient-magnitude and persistence channels do not contain. The method's
  attribution to Miller & Singh (1994) is `UNVERIFIED` (`knowledge/41a`, item 2).
* **Expected gain.** Low: it is still an edge detector and the local-edge family has measured about 0.52.
* **Cost.** About 30 minutes. Not run.

### H66-D · Mapping-coverage residual (observation-process hypothesis, not geology) — RANK 4, NOT RUN
* **Idea.** Mapped catalogues are incomplete unevenly, following mapping effort rather than geology. Where
  the local edge density (H66-A channels) is high but the fold-visible catalogue density is low, unmapped
  faults are more likely than in well-mapped areas.
* **Mimic.** Density of survey or sheet boundaries. Label-blind construction is required: only the fold's
  visible catalogue may enter, and the hidden components must never define the residual.
* **Repo status.** `REPO`: completeness is discussed only for the seismicity catalogue (ComCat), not for
  the mapped-fault catalogue. Not implemented.
* **Cost.** About 1 hour. Not run.

### Considered and rejected as already covered (not new, not repeated)
* Euler deconvolution: already in the README's scored-file records (`h8-euler-lineament…`, `h32-1-…euler…`
  reported 0.2649, `h38-1-…euler…` reported 0.2707; owner-reported, `REPO`).
* Quaternary-fault (QFaults) traces as positive priors: `REPO`, one pixel of footprint coverage.
* Cross-field structural coincidence: `REPO`, `C_*` cross features in the store manifest.
* Gap bridging between collinear traces: `REPO`, H55-4.
* R5-H1 to R5-H5 (trace-correction corridor first): proposed in `knowledge/33`, not run. R5-H1 is the
  highest-ranked untested idea in the repo and is outside this lane.

## 2 · H66-A protocol (frozen)

1. **Feature rule.** `A_local` = the View A channel names that (a) end in `_1`, `_3`, `_1_3`, `grad1`,
   `grad3`, or `_coherence`, (b) do not start with `raw_band_`, and (c) do not contain `rank`. Expected
   result: exactly the 14 channels in §1. The runner asserts this list and refuses any other size.
2. **View B.** Unchanged from H61 (37 channels, `learner()` gradient boosting, SEED 61052).
3. **View A learner.** `Pipeline(SimpleImputer(median), StandardScaler, LogisticRegression(C=1.0,
   max_iter=2000))`. Same training sample as H61 (`sample_train`, max 20,000 positives and 60,000
   negatives per fold, fold-own domain only).
4. **Secondary diagnostic (not gating, not used for any emission).** Shallow gradient boosting
   (`max_depth=3`, `max_iter=150`, `learning_rate=0.05`, `min_samples_leaf=200`) on the same 14 channels,
   region AUC only. Its purpose is to say whether nonlinearity rescues the premise.
5. **Canary.** Unchanged H61 canary on all 73 features (36 + 37), alarm at single-feature AUC > 0.90.
   Any alarm drops that feature and is reported as leakage until proven otherwise.
6. **Premise gate (inherited from H65 §3).** Out-of-quadrant AUC for View A_local over the four label-blind
   folds: PASS only if the mean ≥ 0.60 and the minimum ≥ 0.55.
7. **Exchange, holdout and emission.** The H61 exchange stage and the H61 holdout stage run unchanged,
   through the documented module-global hooks (`WORK`, `EVID`, `DOCS`, `setup`, `learner_for`). The
   runner never edits `run_h61.py`. Thresholds are inherited from `registry/h61_preregistration.json`
   (hash checked): budget 9,400 dots per fold per arm, minimum separation 3 px, 200 m catalogue exclusion,
   1,000 bootstrap draws, seed 520810.
8. **Shipped field.** Rank difference `rankA_post − rankB_post` on the out-of-fold mosaic, as in H61. The
   global budget is 37,600 dots (the H61 convention). Placed by `nodes.spacing_select` on the allowed
   domain.
9. **Gates on the dots.** Format (`submission_writer`, fail-closed), lane gate (`gates.lane_report`,
   surface and dots, literal and policy), uniqueness through `scripts/audit_uniqueness.py` with the census
   receipt as the third argument, and not-the-union check. The census is `work/h61/prior_fetch_receipt.json`
   from `scripts/fetch_prior_inventory.py`, over the 526-blob inventory.
10. **Verdict and slot rule.** Research-only unless ALL of: premise PASS; holdout `disagreement_post`
    DTI > `single_B` DTI with the paired 95% CI excluding 0; format PASS; lane literal and policy PASS;
    uniqueness PASS. Even then the artefact is only *eligible*. Promotion is a separate selector step, and
    nothing in this round uploads anything or consumes a weekly slot.
11. **Reproduction check.** The holdout's `single_B` arm should reproduce H61's 0.174517 exactly if the
    store and the seeds match. A mismatch is reported as a reproduction failure before any other result is
    read.

## 3 · Frozen decision rules

* Premise: PASS only if mean ≥ 0.60 and min ≥ 0.55 (H65 §3, unchanged).
* Canary alarm: single-feature AUC > 0.90 (inherited).
* Holdout comparison: `disagreement_post` DTI vs `single_B` DTI, paired cluster bootstrap, 1,000 draws, seed
  520810. Beating the control means DTI difference > 0 with the 95% CI excluding 0.
* Independence: max |ρ| ≥ 0.6 abandons the exchange (inherited). H66 reports the exchange's own status
  either way.

## 4 · Experiment budget

* **E1** = H66-A canary + fit + premise gate (+ the non-gating diagnostic).
* **E2** = H66-A exchange + holdout + emission + gates.
* **E3** = reserved and **not authorised** unless E1 passes. No further co-training variant is proposed
  here.
* Total: at most 2 experiments this session, within the 3-experiment and 2-hour budget.

## 5 · Sources (`UNVERIFIED` unless stated)

* Blum & Mitchell (1998), DOI 10.1145/279943.279962. Record `VERIFIED` in `knowledge/41a`; body `UNVERIFIED`.
* Miller & Singh (1994), Blakely & Simpson (1986): citation-only, `UNVERIFIED` (`knowledge/41a` items 2–3).
* USGS GeoDAWN DOI 10.5066/P93LGLVQ: cited, not re-opened this session.
* DrivenData metric and format page (fetched 2026-10-09, `MEASURED`), HeroX rules and NLR rules PDF
  (fetched 2026-10-09; `knowledge/36` for rule anchors).
* Leaderboard: dated snapshot only (see §0.2).

## 6 · Access, legal and review flags

* DrivenData Terms of Use prohibit automatic access and reproduction or distribution beyond listed
  exceptions (`REPO` `registry/source_policy.json`; fetched terms, last modified 2014-08-07). Competition
  rasters are mirrored on public GitHub repositories. **Flag for legal review.** H66 reads mirrored bytes
  from GitHub only, and the leaderboard came from one public page fetch.
* Input SHA pins authenticate the mirror bytes only, not organiser authentication (`knowledge/36`).
* Eligibility: the NLR rules require the registrant to certify eligibility, and that person must be the user.
  The agent cannot certify it.

## 7 · AI-use disclosure

An AI agent (Arena.ai Agent Mode) wrote the code, this protocol, and the review text. The rules
(NLR §3.2) require disclosure in the submission narrative; this file is that disclosure for H66. No
geologist verified any structure, no field observation was collected, and no organiser score, acceptance,
or leaderboard gain is claimed for any H66 output.
