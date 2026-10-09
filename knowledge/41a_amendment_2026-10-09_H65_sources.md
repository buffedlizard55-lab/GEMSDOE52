# 34a — Dated amendment to the H65 protocol §4 (sources), 2026-10-09

**Scope.** This note corrects the claim in `knowledge/41_hypotheses_H65_preregistered.md` §4 that
every source was "checked this session". It does **not** edit the frozen protocol. The frozen file's
SHA-256 is still `4d9d559fe6e4b42cffef206d366ccf785b1eda2146a686be98e376a1352bef71`, and
`registry/h65_preregistration.json` still pins it. No H65 decision rule, threshold, feature or verdict
changes here. The H65-A premise verdict stands as recorded in `knowledge/42_h65_results_and_limits.md`.

**Why.** Session check (2026-10-09): only some §4 items were opened. The rest were either cited from
secondary references or not reached. The labels below replace the blanket claim.

## Rename record (identity of the frozen protocol)

This round was first written as H62. `main` already contains a different H62 (PR #46) and later
H63 and H64 rounds, so this round is filed as **H65**, the next free number on `main`.

* **Frozen body unchanged.** The protocol keeps its original title and labels (`H62`) inside the file so its bytes
  do not move. It was moved, byte-for-byte, from `knowledge/34_hypotheses_H62_preregistered.md` to
  `knowledge/41_hypotheses_H65_preregistered.md`. Its SHA-256 is still `4d9d559fe6e4b42cffef206d366ccf785b1eda2146a686be98e376a1352bef71`, see below. Every
  "H62" or "H62-A" in that file means **this round**, not PR #46's H62.
* **Registry pin.** `registry/h65_preregistration.json` (moved from `registry/h62_preregistration.json`) pins the
  same hash. Its `hypothesis_document`, `runner` and `operator_audit` path fields were updated. No hash field changed.
* **Code.** `scripts/run_h65.py`, `scripts/h65_operator_audit.py` and `tests/test_h65.py` were renamed. Only file paths
  and output filenames changed. Feature and receipt key names such as `H62_b15_…` and `h62_A_mean_oof_auc` were kept, so
  receipts match the code that wrote them.
* **Receipts.** `evidence/h65_{canary,operator_audit,premise,run_card}.json` are renamed copies of the H62-labelled receipts.
  Their contents were not rewritten, except that the run card's path fields were updated to the new names.
* **Not re-run.** No premise fit was repeated under the new name. The H65 premise receipt is the one produced under the H62 label.
* **Checks performed.** `sha256sum knowledge/41_hypotheses_H65_preregistered.md` gives `4d9d559fe6e4b42cffef206d366ccf785b1eda2146a686be98e376a1352bef71`.
  `registry/h65_preregistration.json` has `hypothesis_sha256` equal to that value.

## Item-by-item status

| # | Source as cited in §4 | What was actually checked in this session | Label |
|---|---|---|---|
| 1 | Blum & Mitchell (1998), COLT '98, DOI 10.1145/279943.279962 — https://dl.acm.org/doi/10.1145/279943.279962 | The ACM record was fetched through doi.org; the citation details matched. Pages 92–100 were **not read**. | Record VERIFIED. Paper body **UNVERIFIED**. |
| 2 | Miller & Singh (1994), J. Applied Geophysics 32, 213–217 | Cited in the reference list of https://link.springer.com/article/10.1007/s00024-023-03375-y (a search-result snippet). The paper itself was **not** opened. | **CITATION-ONLY** (secondary). Content **UNVERIFIED**. |
| 3 | Blakely & Simpson (1986), Geophysics 51, 1494–1498 | Cited in the reference list of https://jesphys.ut.ac.ir/article_58910.html (a search-result snippet). The paper itself was **not** opened. | **CITATION-ONLY** (secondary). Content **UNVERIFIED**. |
| 4 | Metric, format and dataset — https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ | **Not opened in this session.** | **UNVERIFIED**. |
| 5 | Masking clarification — https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4 | **Not opened in this session.** | **UNVERIFIED**. |
| 6 | USGS GeoDAWN release, DOI 10.5066/P93LGLVQ — https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and | **Not opened in this session.** | **UNVERIFIED**. |
| 7 | Competition leaderboard (listed as a live check, 2026-10-09) — https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ | Live fetch 2026-10-09, chunk 0 of 3: #1 xiaofanhu 0.3774, #7 DARD 0.3195, #13 extradr19 0.2778 read directly. #2 alexoktaba 0.3345 is taken from `registry/leaderboard_snapshot_2026-10-08.json`, not from the live page. | VERIFIED for #1, #7, #13 (live). #2 and the other rows: from the 2026-10-08 snapshot. Public-board values; **not ORGANIZER-CONFIRMED**. |
| 8 | §2 (H65-C) statement that `prd-tnm.s3.amazonaws.com` and `nhd.usgs.gov` are outside the egress allowlist | The sandbox's stated allowlist (github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org) does not include either host. No network request to either host was made to test it. | **CONFIGURATION-CONSISTENT, UNTESTED by request.** |

## What this changes for the record

* Items 4–6 were the sources the protocol uses for the metric, the masking rule and the dataset
  identity. They have not been checked. Nothing in H65 depends on them for a number. Any claim about
  how the metric treats masked or known faults is **UNVERIFIED** until those pages are read.
* Items 2 and 3 support only the existence of the citations. They do not support any physical or
  numerical claim taken from those papers. §2 (H65-B) attributes the tilt-angle method to Miller &
  Singh (1994); that attribution rests on item 2 and is **UNVERIFIED** as to the method's content.
* The protocol's §1 band-15 attribution was already marked unverified before any fit (session record,
  action 14). This amendment does not change that.

## Not changed

* `knowledge/41_hypotheses_H65_preregistered.md` (frozen, unedited).
* `registry/h65_preregistration.json` (unedited, hash unchanged).
* No H65 result, threshold or decision is revised by this note.
