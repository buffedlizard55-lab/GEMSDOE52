# 49 · Evidence about the reported 0.2778 — provenance and non-causal limits

**Current correction (2026-10-09):** `0.2778` is not the highest public score. In the live official
DrivenData board observation saved at `evidence/leaderboard_observation_2026-10-09T201800Z.json`,
`extradr19` is rank 17 at 0.2778; the top row is 0.3774. The board exposes a team-level public score,
not a filename, TIFF hash, upload receipt, or causal explanation. The byte comparison below is an
exact local set relation, **not proof of why an organizer score changed**.

This note supersedes earlier language in the repository that called the deletion of near-catalogue
pixels a measured cause, treated those pixels as automatically score-free, or described 0.2778 as the
highest public value. Historical score/file pairings remain owner-reported unless a matching organizer
receipt is located.

## Four distinct evidence classes

| Evidence class | Current evidence | What it establishes / does not establish |
|---|---|---|
| **PUBLIC-LEADERBOARD observation** | At 2026-10-09 20:18 UTC, official DrivenData rows include #1 `xiaofanhu` 0.3774, #2 `alexoktaba` 0.3361, #7 `DARD` 0.3195, and #17 `extradr19` 0.2778. | A live, team-level public-board reading only. It does not identify a file or explain score movement. See [`evidence/leaderboard_observation_2026-10-09T201800Z.json`](../evidence/leaderboard_observation_2026-10-09T201800Z.json) and the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/). |
| **OWNER/USER-REPORTED file/score association** | `evidence/ctd5_owner_reported_results.json` associates the label `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` with 0.2778. | The report has no organizer receipt and no authenticated file SHA. It is not an organizer-confirmed score-to-file match. |
| **LOCAL MIRROR / pixel facts** | `data/reference/h33-2-b2-zeros.tif`, SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, has 37,654 positive cells. It is an exact subset of the locally mirrored d2-8 raster (SHA-256 `91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8`, 44,090 positive cells). | Local bytes and decoded pixels only. The matching `e5eb6e7e` filename token does not match the recorded hash variants; these bytes do not authenticate an upload or score. |
| **ORGANIZER-CONFIRMED receipt** | None located that binds a submission identifier, file hash, and score. | **No organizer-confirmed 0.2778 file/score mapping is available in this repository.** |

## Exact local pixel comparison (not causal evidence)

Recomputed against the correct d2-8 parent and the restored `data/labels.tif`:

- H33 is a strict 37,654-cell subset of d2-8's 44,090 cells: **6,436 cells removed, zero added**.
- All 6,436 removed cells are 100–200 m from positive cells in the provided known-fault raster: 5,092 at 100 m and 1,344 at 200 m. The nearest H33 cell is 223.6068 m from a positive cell in that raster.
- These are measured geometric relations to the local training/known-fault mask. They say nothing by themselves about which hidden new-fault pixels were scored or about any organizer's change in score.

The official [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
sets the distance-weighted Tversky evaluation around the **new faults**. In the official
[scoring-clarification forum reply](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4),
competition staff says the known-fault mask is pixel-exact and identical to the provided training fault
labels; only new-fault ground truth is scored; and new-fault pixels may occur within 300 m of a known
trace. Therefore, a 100–200 m distance to a known trace is **not** evidence of zero credit or automatic
penalty. A new fault can lie in the same neighborhood and receive distance-kernel credit. The available
local labels cannot reveal whether that occurred for the hidden scored set.

### Defensible conclusion

The byte comparison is **consistent with a precision-pruning hypothesis**, because the owner-reported
0.2778-labelled bitmap is smaller than the separate owner-reported 0.2600-labelled bitmap. It does not
identify the hidden truth, authenticate either reported score, or prove that pruning caused the reported
score difference. There is no causal explanation established here for why an organizer score changed.

## HOLDOUT-DTI is a separate evidence class

Any hide-and-recover result in this repository is an internal measurement, not a public-board observation
or an organizer receipt. Report it with the evaluator, withheld-positive count, and 95% interval; do not
use it to authenticate or causally explain 0.2778. For example, H75's internal comparison is
`HOLDOUT-DTI` from `gems52-pooled-hide-v1`, with 53,186 withheld positives and 9,400 placements per fold:
`B_DVA` = 0.186352 [0.164675, 0.207868] versus `single_B` = 0.174517 [0.152316, 0.196299], paired
Δ = +0.011835 [0.006791, 0.017362]. This is not a leaderboard forecast; H75's separate terminal
`DUPLICATE/STOP` gate means **NOT FOR SUBMISSION**. Full fold/CI receipt: `evidence/h75_holdout.json`.

## Official reviewable sources

- [DrivenData problem statement and evaluation metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [DrivenData live public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [DrivenData staff clarification on the known-fault mask and 300 m neighborhood](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4)
- [USGS GeoDAWN survey release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ). The locally restored competition rasters remain owner-maintained mirrors, not organizer-authenticated bytes.

## Reproduction references

- `evidence/h61_forensics.json` — byte hashes, subset relationships, and distances.
- `evidence/ctd5_owner_reported_results.json` — owner-reported association, without receipt/hash authentication.
- `evidence/leaderboard_observation_2026-10-09T201800Z.json` — live board transcription with scope limits.
- `data/labels.tif` and `data/reference/h33-2-b2-zeros.tif` — local inputs used for the pixel comparison.
