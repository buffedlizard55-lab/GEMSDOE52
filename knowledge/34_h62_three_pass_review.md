# 34 — H62 three-pass review (2026-10-09)

The brief requires multiple passes, each building on the previous, with line-by-line
verification. This is the record. Every fix is registered (IR-H62-00x) or test-pinned.

## Pass 1 — implement

- Preregistered 5 ranked hypotheses (H62-1…H62-5) + frozen decision rules **before any fit**
  (`knowledge/32`, `registry/h62_buriedcorr_preregistration.json`, SHA-256 `e3a8cfd2…`).
- Restored 23/23 manifest-pinned files autonomously (`evidence/h62_buriedcorr_preflight.json`); placed
  `data/` symlinks to the pinned bytes (gitignored) so the full suite runs in a fresh checkout.
- E1: OOF views on the shared 75-layer cache; independence 0.1763, canary 0.7136, strata
  reproduce H60D. E2: H62-1 gate chain validated on hide/tip + weak-surface subgroup.
  E3: unique artifact + all gates + run card + site pages.

## Pass 2 — review for bugs, missing requirements, edge cases (all fixed)

| finding | fix | evidence |
|---|---|---|
| submission note 156 chars > the 140-char run-card rule | shortened to 138 chars; test asserts the literal | `tests/test_h62_buriedcorr.py::test_note_and_name_limits_from_build_script` |
| H62-1 length estimator (`area//3` after cross erosion) killed thin lines — a 25-px corridor failed the ≥15 px gate | skimage `thin` skeletonisation counted per component | IR-H62-007; `test_corridor_mask_gates` (line survives, blob dies, shallow cover dies) |
| weak-surface subgroup evaluator held one full-grid mask per segment → OOM-killed mid-run (no results written) | label-index means + LUT mask build; rows checkpoint `work/h62/validation_rows.json` | IR-H62-008 |
| subgroup rows lacked `tpw/fpw/fnw` → `pooled_dti` KeyError after the cells were computed | rows carry the metric components; checkpoint prevents recomputation | this review |
| shared-template stale checkpoint: tracked evidence receipt survives a wiped gitignored `work/` cache and the stage silently skips | `run_h60d_cotrain.done(path, work_artifact)` requires the work artifact | IR-H62-006 (fixed once in the shared template, no private fork) |
| fresh checkout has no `data/` → `test_gems52_h1_pipeline` environmental failure | `data/` symlinks to the SHA-pinned `work/pinned` bytes | full suite 285 passed |
| rewritten pages dropped release-gate disclosures required by `check_site.py` / `test_ctd5` / `test_h60` ("DO NOT SUBMIT", "do not upload", "NO CERTIFIED LEADERBOARD GAIN", H58 trio, H55-EDGE + H57-alternate links) | publisher templates carry every required disclosure; `check_site.py` green | this review |

## Pass 3 — re-check against the original request

- **Unique TIF submission, obvious status:** `docs/downloads/h62-buriedcorr-candidate.tif` — decoded-pattern
  unique vs 71 priors, 100 % support novelty; hero banner on `docs/index.html` says
  "DOWNLOAD FOR REVIEW: YES · SUBMIT TO COMPETITION: NO — DO NOT SUBMIT this run" in one
  sentence. Verdict NEGATIVE is the honest reading of the frozen bar; 0 slots used.
- **Prompt in README and read every session:** the complete current prompt (including the
  parallel-run protocol and Core Values) remains verbatim in `README.md` §"Complete current
  prompt"; `AGENTS.md` requires reading it before every session.
- **Why 0.2778 / can we beat it, PhD-level, no hallucinations:** answered in `README.md` and
  `knowledge/33` from re-measured bytes (nested-pair ring deletion, |G| bracket, marginal bar)
  with the provenance conflict registered (IR-H62-009: GEMSDOE32 says "NO ORGANISER SCORE
  EXISTS"; the 0.2778 attribution is owner-reported) and the verified 2026-10-04 leaderboard
  read (#1 0.3262, #2 0.3195) labelled owner-reported.
- **3–5 new hypotheses, ranked, top validated on the spatially-blocked holdout before any
  slot:** 5 registered; H62-1 tested and adjudicated negative *before* the artifact existed;
  H62-2/3/4/5 remain registered proposals with named mimics and costs.
- **Executive summary subpage with exact submission steps:** `docs/executive-summary.html`
  leads with the status banner, paste-ready name/note, the six portal steps, and the
  "Predicted values must be in range [0, 1]" root-cause + fix (all-finite {0,1}, zeros outside
  footprint — the exporter refuses anything else and re-reads the written bytes).
- **Run card (lane protocol item 5):** `evidence/h62_buriedcorr_run_card.json` — hypothesis, mechanism,
  named non-fault mimics, HOLDOUT-DTI + CI + withheld positives, correlation/overlap vs
  registry (both lane gates + uniqueness + not-union), raster SHA-256, validator output
  (no NaN, values in [0,1], CRS/shape/transform), submission name + 138-char note,
  verdict **negative**. Negative results are deliverables.
- **Labels:** every number in the receipts/site is HOLDOUT-DTI (evaluator pinned) or
  OWNER-REPORTED; projections are explicitly not scores (`conditional_projection_not_a_score`).
- **Budget:** 3 experiments (E1 baselines/canary, E2 H62-1 validation, E3 build+gates);
  2 attempted infra re-runs after registered bugs; no further experiments after E3.

## Residual risks / what the next session should do

1. **Organizer authentication** of mirror bytes and score-to-file mappings remains the blocker
   for any ORGANIZER-CONFIRMED number. Everything else is labelled.
2. **Instrument/board divergence** (IR-H60-003) is unresolved: the hide instrument cannot
   certify or kill an off-catalogue strategy. A credible path needs either organizer-confirmed
   receipts for ≥ 3 more files (identification) or a new instrument.
3. **Novel-ground scarcity:** ~99.2 % of the corridor population sits inside prior support;
   any future unique discovery file must find genuinely new signal or new external data
   (the free official candidates are listed in `knowledge/04_free_data_and_licenses.md`).
4. The zero-field budget fill (35,920/37,627 px) is disclosed; if a selector ever overrode the
   negative verdict, the crest-only subset is the only mass carrying the discovery signal —
   and a 1,707-px file is score-capped near 0.10 by the |G| term alone. Both facts are in
   `evidence/h62_buriedcorr_build.json`.

## Post-merge re-verification (2026-10-09) — IR-H62-010

After the concurrent rounds merged (PRs #43–46) the merge was re-audited: both test suites pass
(322 tests), `scripts/check_site.py` is green, the register is unioned to 133 entries (mine renumbered
IR-H62-006..009, the supersession registered as IR-H62-010), and the artifact was re-certified against
the merged registry (37,626 px candidate, novel fraction 1.0 vs 80 priors; the 37,627 freeze retained
as superseded provenance). The two H62 works are kept distinct: this round's shared paths carry the
`h62-buriedcorr` / `H62_BURIEDCORR` suffixes because the concordance round landed its own
`h62-*`/`H62_*` names first. Residual risks from the three passes stand; add: every registry-relative
claim in this document is a point-in-time measurement against a live registry (see IR-H62-010).
