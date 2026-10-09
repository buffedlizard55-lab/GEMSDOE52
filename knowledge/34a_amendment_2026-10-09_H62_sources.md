# 34a — Dated amendment to the H62 protocol §4 (sources), 2026-10-09

**Scope.** This note corrects the claim in `knowledge/34_hypotheses_H62_preregistered.md` §4 that
every source was "checked this session". It does **not** edit the frozen protocol. The frozen file's
SHA-256 is still `4d9d559fe6e4b42cffef206d366ccf785b1eda2146a686be98e376a1352bef71`, and
`registry/h62_preregistration.json` still pins it. No H62 decision rule, threshold, feature or verdict
changes here. The H62-A premise verdict stands as recorded in `knowledge/35_h62_results_and_limits.md`.

**Why.** Session check (2026-10-09): only some §4 items were opened. The rest were either cited from
secondary references or not reached. The labels below replace the blanket claim.

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
| 8 | §2 (H62-C) statement that `prd-tnm.s3.amazonaws.com` and `nhd.usgs.gov` are outside the egress allowlist | The sandbox's stated allowlist (github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org) does not include either host. No network request to either host was made to test it. | **CONFIGURATION-CONSISTENT, UNTESTED by request.** |

## What this changes for the record

* Items 4–6 were the sources the protocol uses for the metric, the masking rule and the dataset
  identity. They have not been checked. Nothing in H62 depends on them for a number. Any claim about
  how the metric treats masked or known faults is **UNVERIFIED** until those pages are read.
* Items 2 and 3 support only the existence of the citations. They do not support any physical or
  numerical claim taken from those papers. §2 (H62-B) attributes the tilt-angle method to Miller &
  Singh (1994); that attribution rests on item 2 and is **UNVERIFIED** as to the method's content.
* The protocol's §1 band-15 attribution was already marked unverified before any fit (session record,
  action 14). This amendment does not change that.

## Not changed

* `knowledge/34_hypotheses_H62_preregistered.md` (frozen, unedited).
* `registry/h62_preregistration.json` (unedited, hash unchanged).
* No H62 result, threshold or decision is revised by this note.
