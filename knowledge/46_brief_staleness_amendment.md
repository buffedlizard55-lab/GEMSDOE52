# 46 · Amendment: the repository's verbatim copy of the user brief is stale (2026-10-09, H66)

**Status: flagged, not repaired.** This document records a discrepancy between the prompt this round was
run against and the "verbatim" copy the repository keeps, and says exactly what was and was not done
about it. Nothing here was transcribed from memory where a measurement could be made instead.

## 1 · What the repository holds

`README.md` embeds the current user brief in a fenced block under the heading
*"Complete current prompt — 2026-10-09, verbatim — read before working"*, and
`knowledge/36_current_user_brief_2026-10-09.md` holds the same text. The two are **byte-identical**:
both fenced blocks are 28,761 characters and both hash to SHA-256 `4e48a18e5a532fd4…` (measured this
session with a fenced-block extraction over both files). That satisfies the standing instruction
"put this prompt into the repo readme and read it every time we work on the project" for the H63–H65
rounds.

## 2 · What this round's prompt additionally contains

The H66 prompt's per-repository score list is longer than the embedded copy. Six identifiers that
appear in the H66 prompt were searched for across every `*.md`, `*.json` and `*.py` file in this
checkout (excluding `.git`) and returned **zero hits anywhere in the repository**:

| identifier in the H66 prompt | hits in README's embedded brief | hits anywhere in the repo |
|---|---|---|
| `h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros` | 0 | 0 |
| `h54c-manifest-edge-20261009T025732Z-73454bc5` | 0 | 0 |
| `h59-cover-ds-belief-b2xh33d-20261008T184547Z-b79c4c61d8d8` | 0 | 0 |
| `55GEMSDOE` (placeholder entry) | 0 | 0 |
| `56GEMSDOE` (placeholder entry) | 0 | 0 |
| `57GEMSDOE` (placeholder entry) | 0 | 0 |

For contrast, the identifiers that *are* in the embedded copy were re-checked and are present:
`xscale-worm-persistence` (1), `sup01-hgb21-sep40-n40000` (1), `h51-km-faultzone` (1),
`gate_ortho_w0.25-40k` (1), `h60-lidarscarp-s2p0` (1), `h53-twostage` (1).

The embedded copy's `GEMSDOE48` entry is an empty score line (`:`), and its list ends at
`54GEMSDOE`; the H66 prompt carries a filename for `GEMSDOE48` and continues to `57GEMSDOE`.

**Reading.** These are the artefacts of *parallel* sessions running from the same prompt (the brief's
own PARALLEL-RUN PROTOCOL says this session is one of several). The user's score list is updated as
those sessions submit, so the embedded copy is simply a snapshot taken earlier on the same day. This
is staleness, not corruption, and it does not change any H66 measurement.

## 3 · What was deliberately NOT done

The stale block was **not** re-typed from working memory. Re-embedding 28,761 characters of the
prompt, or the new score values, from recall would put unverified numbers into the one file the
repository tells every future session to trust first — the exact failure mode the standing
instruction "no hallucinations, flag irregularities" exists to prevent. The correct repair is
mechanical: paste the current prompt into the fenced block in `README.md` and into
`knowledge/36`, then re-run the byte-identity check in §1.

Two claims in the brief *were* independently re-verified this session, and both are corrected in the
H66 README block with links:

1. **The leaderboard cannot be fetched.** `https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/`
   is JavaScript-rendered and returns only "Loading…" to a page fetch, so no score in the brief's list
   can be confirmed from the board in this environment. The last live reading recorded by this
   repository (2026-10-09, `knowledge/41*`) is #1 xiaofanhu **0.3774**, #7 DARD **0.3195**,
   #13 extradr19 **0.2778** — labelled PUBLIC BOARD, never ORGANIZER-CONFIRMED. The brief's claim that
   0.3195 is the highest score is therefore not supported (this is IR-H65-002, unchanged).
2. **The prize structure is two rounds, and the second one changes the objective.** From
   [problem page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/),
   fetched 2026-10-09: the Initial Prize Round ($50,000) is scored on a **private** test set; the
   Final Prize Round ($250,000) re-scores the **same single chosen submission** against an **expanded**
   label set — the initial labels *plus* previously-unknown faults that the expert panel verifies after
   reviewing **every team's** submission, and "predictions that helped experts identify
   previously-unmapped faults can score higher here than in the Initial Prize Round". Competitors must
   choose one submission for both rounds before the deadline, without knowing private performance.

Consequence, and it is the one place where the amendment changes behaviour: a file whose every emitted
cluster carries written, falsifiable geological reasoning has prize value in round two that its
HOLDOUT-DTI does not express. That is why H66 ships a reasoning row per emitted pixel
(`submission/gems52-h66-a-only-and-segment-reasoning.csv`, 24,907 rows) even though the round is
negative and the file must not be submitted.

## 4 · Logged as

`registry/irregularities.json` → **IR-H66-011** (low severity, open). Disposition: the next session
re-embeds the current prompt verbatim and re-runs the §1 byte-identity check; until then the embedded
copy is treated as a snapshot of 2026-10-09 that is missing at least six later entries.
