# 100 · H97 and H98 results (kept OUT of the pinned preregistration documents)


> **Identifier history (IR-H97-008).** This round was pre-registered and run as **H88/H89**. A parallel session
> merged its own H88/H89 round to `main` (PR #94), so the round was renamed **H92/H93**; `main` then filled H92, H93,
> H94, H95 and H96 with further parallel rounds, so it was renamed again to **H97/H98** and its knowledge documents
> to 97-100. Both renames are mechanical: the substitution chain reproduces the frozen preregistration texts byte for
> byte (`evidence/h97_identifier_rename.diff`), and both registry pins verify. No hypothesis, threshold, arm or
> result changed; the shipped GeoTIFF bytes are unchanged (`sha256 dbbdc071…9914`).

The preregistration pins (`registry/h97_preregistration.json`, `registry/h98_preregistration.json`) hash the whole
hypothesis document, so those documents stay frozen exactly as they were before the first fit — the same discipline
as every earlier round, where results live in this kind of separate file plus the JSON receipts. The pinned files
still carry their original "§4 · Result — see the receipts" placeholder; the results are here.

Every number below is HOLDOUT-DTI with the evaluator version, the withheld positive count and a 95 % CI.

---

## H97 · Result (experiment 1 — strict negative)

Instrument: `gems52-pooled-hide-v1`, **53,186 withheld positive pixels**, 153 physical 20 km spatial
clusters, 1,000-draw paired percentile bootstrap, 9,400 dots/fold/arm, 3.0 px minimum separation,
200 m visible-catalogue collar. Receipts: `evidence/h97_fit.json`, `evidence/h97_holdout.json`;
the shipped artifact card is `evidence/h97_build.json` and the brief-format round card is
`evidence/h97_run_card.json`.
Every number below is HOLDOUT-DTI.

### 4.1 Sufficiency — the representation change did not make View A sufficient

| Fold | View A held-out-region AUC | View B held-out-region AUC |
|---|---|---|
| 0 | 0.5275 | 0.6812 |
| 1 | 0.5339 | 0.7500 |
| 2 | 0.4929 | 0.6713 |
| 3 | 0.5724 | 0.6848 |
| **mean** | **0.5317** | **0.6968** |

View A is at chance — the ninth consecutive View-A sufficiency failure in this repository (fold 2
even lands below chance). DVA on magnetic + isostatic-gravity bands did **not** repair the view.

Leakage canary: max single-channel AUC **0.5977** (bar 0.90) — no leakage.
Independence: max |ρ| **0.4510** (folds 77/43/28/28 blocks) → `abandon_required = False` on both the
brief's 0.90 bar and the repository's stricter 0.60. The brief's abandonment test passes; the
method still fails, because independence without sufficiency gives co-training nothing to donate.

### 4.2 Pooled HOLDOUT-DTI (primary = `xtex_dis`)

| Arm | DTI | 95 % CI | Paired vs primary (CI) |
|---|---|---|---|
| **`xtex_dis` (primary)** | **0.034799** | **[0.026938, 0.044011]** | — |
| `xtex_agree` (consensus) | 0.128009 | [0.112310, 0.143335] | −0.093211 [−0.107202, −0.078695] |
| `single_Atex` | 0.081910 | [0.069143, 0.095862] | −0.047111 [−0.056514, −0.037718] |
| `single_Btex` | 0.164883 | [0.145264, 0.183945] | −0.130084 [−0.149840, −0.110301] |
| `random` (control) | 0.080426 | [0.070223, 0.090973] | **−0.045627 [−0.054106, −0.037194]** |

The `random` control reproduces the committed H82/H85 receipt **0.080426** exactly. The primary
scores **below the random floor** with a paired CI entirely below zero: as the brief warns,
"co-training can also amplify bias" — here the A-confident ∧ B-abstains selection is
anti-informative. Nothing in §2's rank-1 hypothesis survives its own preregistered test.

### 4.3 Artifact and follow-up

The H97 artifact was built despite the negative, because the deliverable requires one unique,
format-valid TIF plus the A-only geological reasoning: `submission/gems52-h97-cotrain-atexture-
disagreement-20261010T222354Z.tif` (sha256 `dbbdc071…`, 37,654 dots, max lane Spearman 0.0179,
novel fraction 0.6826), card `evidence/h97_build.json`, verdict **DOWNLOAD YES, SUBMIT NO**.
The H98 follow-up (long lags, 400–800 m) was preregistered separately in `knowledge/98` and is
also a strict negative — the "wrong scale" explanation for View A is closed. See `knowledge/99` §7
for the two routes that could actually beat 0.3195, neither of which this round's representation
change addresses.

---

## H98 · Result (experiment 2 — strict negative)

Instrument: `gems52-pooled-hide-v1`, **53,186 withheld positive pixels**, 153 physical 20 km spatial
clusters, 1,000-draw paired percentile bootstrap (seed 61052), 9,400 dots/fold/arm, 3.0 px minimum
separation, 200 m visible-catalogue collar. Receipts: `evidence/h98_fit.json`,
`evidence/h98_holdout.json`, `evidence/h98_run_card.json`. Every number below is HOLDOUT-DTI.

### 4.1 Sufficiency — View A still fails at 400–800 m

| Fold | View A held-out-region AUC | View B held-out-region AUC |
|---|---|---|
| 0 | 0.5368 | 0.6718 |
| 1 | 0.5529 | 0.7296 |
| 2 | 0.4913 | 0.6430 |
| 3 | 0.5327 | 0.6864 |
| **mean** | **0.5284** | **0.6827** |

View A at long lags (0.5284) is statistically indistinguishable from View A at short lags
(H97: 0.5317). The "wrong scale" explanation for the H97 failure is therefore **closed**: the
potential-field view carries no measurable catalogue-fault signal at either lag family.

Leakage canary: max single-channel AUC **0.5950** (bar 0.90) — no leakage.
Independence: max |ρ| **0.4455** (folds 77/43/28/28 blocks) → `abandon_required = False` on both the
brief's 0.90 bar and the repository's stricter 0.60; the views are independent but the donor is not
sufficient.

### 4.2 Pooled HOLDOUT-DTI (primary = `xtex_dis`)

| Arm | DTI | 95 % CI | Paired vs primary (CI) |
|---|---|---|---|
| **`xtex_dis` (primary)** | **0.034697** | **[0.026536, 0.043153]** | — |
| `xtex_agree` (consensus) | 0.121582 | [0.107204, 0.137463] | −0.086884 [−0.101257, −0.074418] |
| `single_Atex` | 0.074913 | [0.061878, 0.087712] | −0.040215 [−0.050002, −0.030530] |
| `single_Btex` | 0.152616 | [0.133818, 0.170412] | −0.117918 [−0.135790, −0.099863] |
| `random` (control) | 0.080426 | [0.070223, 0.090973] | **−0.045728 [−0.052841, −0.038856]** |

The `random` control reproduces the committed H82/H85 receipt **0.080426** exactly, so the
instrument is reproduced inside this clone. The frozen decision rule required the primary's paired
CI lower bound to be **above 0**; it is **−0.052841**, so **H98-L is a strict negative**: the
disagreement arm does not merely under-perform — it scores *below the random floor*, i.e. the
A-confident ∧ B-abstains selection is anti-informative on the catalogue-recoverable population.

### 4.3 What this closes

* The co-training lane's last open representation hypothesis (deep/long-scale boundary texture) is
  dead for this footprint; both fine-scale (H97) and coarse-scale (H98) DVA primaries land ≈ 0.0347
  against a 0.080426 floor.
* Together with the repository's nine amplitude-representation View-A failures, the honest reading
  is: **the potential-field/subsurface view, as this project can construct it, does not locate
  catalogue faults on this footprint**, and the brief's own safeguard applies verbatim — a donor
  that is not sufficient has nothing to donate.
* Next lever is not representation; it is *population*: see `knowledge/99` §7 (off-catalogue
  detector + an instrument tied to the scored population) and the H98-B/H98-S candidates in §2 of
  this file (seismicity lineation, band-15 cover step), which remain untested.
