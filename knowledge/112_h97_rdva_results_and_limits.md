# 112 · H97-RDVA results and limits — view-pure radiometric DVA co-training

> **Integration namespace:** this experiment was preregistered and executed as H97 on its isolated
> branch. Before integration, `main` independently acquired a different H97 and continued through
> H102. This work is therefore published as **H97-RDVA**, without altering the frozen preregistration
> (`063174…`) or hypothesis document (`f35c14…`). It is a parallel negative archive and does not replace
> the repository's global current pointer.

**Verdict: NEGATIVE. Download: YES for research/audit. Submit: NO. Slots used: 0.**

H97 was frozen before candidate-specific channel construction in
`knowledge/97_hypotheses_H97_preregistered.md` (SHA-256
`f35c14e130af1ae00e6ed47a5a08a185125e81db8289ce30228ba7acfafc57e9`) and
`registry/h97_rdva_preregistration.json`. It followed the requested lane: A contains only potential-field /
subsurface features and B only DEM/radiometric features; disagreement controls one whole-segment exchange.

## 1. What was actually tested

* **View A:** shared gravity, magnetics, strain, seismicity, conductivity and depth-to-basement channels,
  plus 30 H82-style directional-semivariance channels from bands 13, 15 and 18.
* **View B:** shared slope, DEM curvature and radiometric channels, plus 20 directional-semivariance
  channels from bands 12/19 and the new 40-channel transform of GeoDAWN K/Th/U/total count.
* **Transform:** eight directions; 100/200/300/400/600 m lags; σ=300 m; anisotropy and log-variance.
* **Exchange:** max OOF negative-error correlation 0.121626, below the preregistered 0.60 abandon bar.
  Exactly one buffered whole-segment exchange selected 7,319 A→B pixels (578 segments) and 7,995
  B→A pixels (434 segments), 15,314 total, each with sample weight 0.25. The primary is post-B, so
  **only the A→B buried-fault donations can influence the reported primary**. The B→A refit is a
  diagnostic only and is not emitted; B-only candidates remain surface-artifact suspects.
* **Canary:** all 163 learner inputs were tested alone in every fold. Maximum direction-insensitive
  AUC was 0.6691; no value exceeded the 0.90 leakage alarm.

The added radiometric DVA implementation was not found elsewhere in the repository-wide census. H82/H84
used DVA on DEM, slope, gravity and basement but put all of those channels in one learner. H97 is therefore
new in decoded output and mechanism, not merely renamed bytes.

## 2. Primary measurement

All values in this section are **HOLDOUT-DTI** (`gems52-pooled-hide-v1`, 53,186 withheld positive
pixels, α=0.2, β=0.8, 300 m triangular kernel; 95% paired 20 km cluster bootstrap, 1,000 draws).
They are not board scores.

| arm | HOLDOUT-DTI [95% CI] |
|---|---|
| `single_B_RDVA` | **0.186482** [0.166242, 0.206787] |
| `cotrain_B_RDVA` (primary) | **0.185090** [0.164740, 0.205110] |
| `union_pre` | 0.159604 [0.139332, 0.180973] |
| `random` | 0.080599 [0.071883, 0.090135] |
| `single_A_RDVA` | 0.074664 [0.060500, 0.089608] |
| `Aonly_pre` | 0.019141 [0.014605, 0.023890] |

Primary minus `single_B_RDVA` = **−0.001392** [−0.004502, +0.001700]. The frozen bar was
H84's measured `B_DVA2` control, 0.192829 [0.170790, 0.213691]. Thus the primary misses the bar by
0.007739 and does not beat its own single-view baseline. The exchange is not promoted. The stronger
strict-B baseline is interesting but cannot be attributed specifically to radiometric DVA without the
preregistered DEM-DVA-only ablation; no post-hoc attribution is claimed.

Fold behavior is heterogeneous: primary DTI was 0.120698, 0.257763, 0.227397 and 0.236382. That is why
pooled scoring and spatial bootstrap, rather than an average of attractive folds, is reported.

## 3. Artifact and gates

The frozen research artifact uses the stitched out-of-fold post-B field, excludes the full catalogue and
its 200 m collar, then places 25,400 binary dots at ≥3 px spacing with `gems52.nodes.spacing_select`.
It is written through `gems52.submission_writer`.

* **File:** `gems52-h97-rdva-cotrain-25400px-20261010-c6fbccd67b14-zeros.tif`
* **SHA-256:** `a6ca0f7b42ee722e1b04199557f84237ba186830a3b6860e38d3e4bf833722ad`
* **Decoded float32 SHA-256:** `c6fbccd67b14db1b630a99bec1c2cf28a35bb620388378ac7f9551e822465d38`
* **Short path:** `docs/downloads/h97-rdva-candidate.tif`
* **Unique submission name:** `gems52-h97-rdva-cotrain-25400px-20261010-c6fbccd67b14-zeros`
* **Note (105/140):** `H97 view-pure radiometric DVA co-training; 25,400 dots, 3px, 200m collar; research only, no slot approved`

Format passes: one float32 band, EPSG:32611, 3730×3292, sample transform/bounds, no nodata tag,
0 NaN, 0 infinity, min 0, max 1, exactly 25,400 positive cells and no mass outside the eligible footprint.
This makes the file safe to **download**; it does not approve an upload.

| gate | measured result | verdict |
|---|---|---|
| surface lane | max Spearman 0.463212 over 719 accessible census/local rasters | PASS |
| exact file identity | all 719 inventory files have a different byte length from the 117,335-byte candidate (same-length entries: 0) | no copied/renamed file |
| decoded identity | no identity among 718 aligned comparable rasters; max Jaccard 0.089561 | distinct among comparable priors |
| census completeness | one inventory blob is a 32×48 thumbnail, not the 3730×3292 submission grid (therefore not the same raster shape), but it cannot enter the aligned decoded-value audit | INCOMPLETE / disclosed |
| final-dot lane | max ≤3 px overlap 1.0000; many informative priors also exceed 0.70 | **DUPLICATE/STOP** |
| not the union | Jaccard 0.078213 vs equal-budget union-field dots; 21,715 dots outside that placement | PASS |
| holdout promotion | 0.185090 < 0.192829 and paired CI vs single B crosses zero | **FAIL** |

The apparent tension is real: the decoded pattern is different from every comparable prior, while the
brief's broader *near-dot* definition declares it a duplicate. The latter controls submission: stop and
**do not submit**. Download remains useful for audit because the bytes are valid and distinct, and the
negative result itself is a required deliverable.

Every final emitted A-confident/B-abstaining candidate is documented (2/2 rows) in the A-only reasoning
CSV. Every donated A→B whole segment is documented (578/578 rows) in the segment CSV. These are candidate
interpretations, not verified faults.

## 4. Why the owner-attributed `h33-h33-2-b2…` got 0.2778

The causal statement supported by available bytes is metric placement/pruning, not a new geology claim:

1. `h33-2-b2` has **37,654** binary dots. It is a strict subset of the owner-reported 0.2600 `d2-8`
   file (44,090 dots).
2. The removed **6,436** dots all sit 100–200 m from the public catalogue; the champion's minimum
   catalogue distance is 223.6 m and only 5.77% of its dots are within 300 m.
3. For binary, separated-dot emissions the reduced metric is
   `DTI = T / (0.2·S + 0.8·|G|)` when emitted credit and maximum-cover credit coincide. Removing mass
   `S` while retaining credited truth mass `T` raises DTI. Solving the nested 0.2600/0.2778 pair under
   the empirically supported zero-credit-ring condition gives `|G| ≈ 14,089`; the independent H87
   13-score inversion gave 14,334. These are model-based algebraic pins, not published hidden truth.
4. The champion's inferred mean kernel-credit density is about 13.87%, roughly five times the uniform
   permitted-footprint control. The intersection of two independent historical thinnings carries
   16.3–20.5% inferred credit density. Thus the 0.2778 is explained by (a) a historically corroborated
   off-catalogue field and (b) removal of denominator-only near-catalogue mass.

The score-to-filename link is still **owner-reported, not organizer-authenticated**: the board snapshot
shows a team and value, not a raster hash. This limits “why” to a strongly byte-supported explanation,
not a proof of organizer internals.

At the same 37,654 mass, 0.3195 requires about **1.150×** the champion's credited mass and 0.3774 about
**1.36×**, under the same reduced-metric assumptions. H97 did not demonstrate either gain: its only
honest numerical evidence is HOLDOUT-DTI, and that instrument is not an organizer score. No upload was
made. Therefore beating 0.2778, 0.3195 or 0.3774 is **not demonstrated**.

## 5. Official reference solution review

The official DrivenData repository was cloned and pinned at commit
`aebe92f7c8a990f0e3443451b7a825d9afd6336b` (2026-06-16). Its notebook:

* min/max normalizes all numeric channels and uses all channels by default;
* trains five ResNet18-encoder U-Nets over random 128×128 labelled patch splits, five epochs each;
* uses Tversky loss α=0.2, β=0.8 and averages each split's held patches;
* applies a sigmoid, so predictions are nominally in [0,1]; and
* writes one GeoTIFF using the labels raster CRS and transform.

It does **not** implement whole-fault-segment spatial holdout, an 80 px leakage buffer, two physically
separate views, disagreement exchange, catalogue masking/collar placement, prior uniqueness or the
final validator. `y_out = np.zeros(...)` defaults to float64 and the writer uses `dtype=y_final.dtype`,
so the notebook as pinned appears to write float64 rather than the competition's float32 requirement.
It also writes from the labels grid rather than validating against `sample_submission.tif`. H97 does not
copy that method; the review only confirms the official baseline's normalization/loss/output conventions.
Manual review: https://github.com/drivendataorg/gems-prize-reference-solution/commit/aebe92f7c8a990f0e3443451b7a825d9afd6336b

## 6. What is settled and what remains

* **Settled negative:** adding one weighted A→B disagreement exchange to this strict radiometric-DVA B
  view does not improve it. Do not repeat threshold variants without a new physical signal.
* **Useful measurement:** strict surface/radiometric DVA B reaches 0.186482, better than historical plain
  B but below the mixed-physics 0.192829 control. The physics split matters when comparing names.
* **A-only warning:** direct A-only placement is very poor on this holdout (0.019141), and View A OOF AUC
  is weak in three folds. A-only remains a geological hypothesis, not a promotable raster stratum.
* **Next scientific move:** test the preregistered road/drainage orientation veto only if a fresh round
  can freeze its geometry before evaluation; otherwise stop this lane. External 2 m temperature remains
  blocked until the official free table is obtained and SHA-pinned.
* **Operational fix:** large `.npy` files repeatedly lost their first 3,968 payload bytes after fsync and
  immediate verification. H97 added atomic temp-file replacement to shared `run_h82.save_verified` and a
  content-pinned 1,024-value zero guard page for H97 runtime arrays. Scientific values exclude the guard.

## 7. Final cumulative review

1. **Implementation/verification pass:** re-read the canonical TIFF, both published aliases and both ZIPs;
   verified the SHA-256, decoded SHA-256, exact sample grid, finite `[0,1]` values, spacing, catalogue
   collar, reasoning row counts, frozen preregistration hashes and all reported gates.
2. **Bug/edge-case pass:** repaired the shared large-array writer with temp-file fsync plus atomic replace;
   retained H97's guarded runtime vectors; separated research-download safety from slot approval; made
   receipts checkout-portable; and, after detecting a parallel-round collision, namespaced every mutable
   publication path as H97-RDVA while retaining the byte-frozen preregistration and hypothesis hashes.
3. **Full requirement pass:** the complete test suite, static-site checker, byte-serving checks,
   `git diff --check` and Python compilation are rerun after integration with current `main`; the PR record
   is the authority for their final counts.

Machine-readable authority: `evidence/h97_rdva_run_card.json`.
