# H88s results, limits, and what the next session must not redo

Round: **H88s** — this session's H88, renamed **H88s** in file names when it was merged into `main`
on 2026-10-10, because a **different session had already published its own H88 round** (the
basement-step / band-15 round: `knowledge/80_h88_preregistered.md`, `knowledge/81_h88_results_and_limits.md`,
`evidence/h88_holdout.json`, `evidence/h88_run_card.json`, `docs/h88.html`,
`submission/gems52-h88-basement-step-37654px-20261010.tif`). Nothing in either round was deleted: the
two are separated by the `h88s_` prefix on this round's receipts. The preregistration **bytes are
untouched** — sha256 `45a0cc62…` still verifies against `knowledge/80s_h88s_preregistration.md`, the
renamed copy of the frozen document. Recorded as **IR-H88s-010**. Lane: the brief's single method paragraph — two-view co-training between
**View A** (potential-field / subsurface: gravity, magnetics, strain, basement depth, conductivity) and
**View B** (surface: DEM curvature and slope, radiometric K/Th/U and ratios, LiDAR scarp faces), with
disagreement as the discovery signal (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).

* Preregistration: `knowledge/80s_h88s_preregistration.md`, sha256
  `45a0cc62333c4a49d044852ab61d89ec688f741d50495a0e3cb3030b3ed12093`, pinned in
  `registry/h88s_preregistration.json`; re-hashed by the runner before every stage.
* Budget amendment: `knowledge/80s_h88s_amendment_budget.md` (**80b**: a non-primary ship field is
  emitted at the round's largest registered budget).
* Runner: `scripts/run_h88s_cotrain_lane.py` (stages `channels|fit|holdout|build|card`).
* Predecessors: `knowledge/79_h86_hypotheses_ranked.md`, `knowledge/77_h83_results_and_limits.md`.

**Slots used: 0.** Verdict on the preregistered primary: **NEGATIVE**. Shipped arm: `single_B` under
amendment 80b. Download **YES**; submission is the owner's selector step.

---

## 1 · The measured result: HOLDOUT-DTI `gems52-pooled-hide-v1`

Instrument: hide-and-recover, 4 spatial folds, whole fault segments withheld with an 80 px buffer, all
catalogue-derived features recomputed from visible faults only, visible faults masked pixel-exactly,
pooled DTI over 60,894 withheld positive pixels, α = 0.2, β = 0.8, R_M = 300 m triangular kernel,
3 px metric-aware placement (`nodes.spacing_select`) inside each fold's allowed set.

| Arm | DTI | 95 % CI |
|---|---|---|
| `single_B` (shipped) | **0.179847** | [0.156326, 0.201319] |
| `exchange_B` (not shippable — see §3) | 0.180551 | [0.157340, 0.202205] |
| `b_only` | 0.163511 | [0.143678, 0.182839] |
| `union_max` | 0.152930 | [0.131725, 0.174620] |
| `corroborated_B` (**primary, preregistered**) | **0.127005** | [0.111046, 0.145475] |
| `random` (must land in [0.0702, 0.0910]) | 0.074569 | [0.065643, 0.083072] |
| `single_A` | 0.066325 | [0.049331, 0.083919] |
| `concordant` | 0.054984 | [0.041327, 0.070385] |
| `a_only` | 0.045017 | [0.033650, 0.056917] |
| paired primary − `single_B` | **−0.052841** | **[−0.067627, −0.038227]** |

The frozen promotion rule — *lower bound of the paired CI against `single_B` greater than zero* — fails
by −0.038227. The preregistered primary is **not promoted**; the NEGATIVE is the deliverable.

Budget curve for the primary (pooled): k4700 **0.080584**, k6250 **0.097457**, k9400 **0.127005** —
monotone increasing, so at this precision the constraint is not dot count.

### The two Blum & Mitchell premises, measured

| premise | measurement | outcome |
|---|---|---|
| conditional independence | block-level out-of-fold error correlation on labelled negatives, 50 px blocks: max \|ρ\| per fold 0.128789 / 0.103378 / 0.027111 / 0.141647 | **PASS** (abandon rule \|ρ\| > 0.60 does not fire) |
| View A sufficiency | mean OOF AUC **0.5154** | **FAIL** vs 0.60 |
| View B sufficiency | mean OOF AUC **0.6894** | PASS |
| pseudo-label exchange (A → B) | 199 / 198 / 196 / 198 px in 8 / 13 / 14 / 13 whole segments, donor OOF AUC 0.4988 / 0.5857 / 0.5130 / 0.4641 | **screened out in all four folds** (`sufficiency_screen_pass = false`) |
| leakage canary | best single holdout channel `B_b19_grad` AUC **0.6474** across 68 channels | PASS (alarm 0.90) |

Independence is the premise the brief worried about, and it holds. Sufficiency is the premise the
literature does not let us skip, and View A fails it for the **ninth** measured time in this repo
(0.5113–0.5362 across H61–H88). Co-training with a non-sufficient donor is not the theorem; the exchange
was produced, measured, and screened out rather than silently shipped — which is also why `exchange_B`
(0.180551, the numerically top arm) is **not** the shipped field.

## 2 · Why the shippable arm is `single_B`, and what that means

`corroborated_B` = View B evidence with the B-only disagreement stratum suppressed by View A. Suppressing
the B-only stratum does exactly what the brief says a surface-only detector should do — it strips the
surface-artefact channel — but it also strips 0.0528 of pooled DTI with it, because on this instrument the
B-only stratum is where B's recoverable skill lives. A-only candidates (the brief's buried-fault
discovery signal) score 0.045017, below the random control: with A's sufficiency at 0.5154 there is no
measurable buried-fault skill to recover in this feature set. The honest summary is: **the disagreement
strata are not carrying hidden performance in this round; B alone is.**

`union_max` (0.152930) is below `single_B`, so the output is not merely the union of the two views — the
brief's test passes as a statement about the file, not as an achievement: the union is worse.

## 3 · Shipped-bytes diagnostic, and the collar-vs-receipt discrepancy

The shipped bytes were re-scored **after** the build, independently of the arm receipt
(`scripts/verify_h88s_shipped_holdout.py` → `evidence/h88s_shipped_holdout.json`,
`docs/data/h88s_shipped_holdout.json`, 218.5 s):

* shipped pooled HOLDOUT-DTI **0.006391** [0.005553, 0.007242] — against the arm receipt's 0.179847;
* fold-0 fresh recompute reproduces the arm receipt exactly (0.116999, TPw 3001.9) while the shipped
  slice of that same fold scores 0.003888 (TPw 97.0): the difference is the **200 m catalogue collar**,
  1,859 of 3,001 recoverable cover-carrying dots sit inside it (they carry 2,904 of the 3,001 cover);
* the receipt carries `instrument_note`: this number is near zero **by construction** — the instrument's
  truth is the mapped catalogue and the file emits nothing within 200 m of it. It is a
  catalogue-overlap diagnostic, not a detector measurement and not an organiser score.

This discrepancy is the round's most important bookkeeping lesson: **the arm DTI and the shipped-bytes
DTI measure different things** (a detector against withheld segments vs. the actual file against a
catalogue it was told to avoid). Quote them together or not at all.

## 4 · Deliberate exclusions (the round's discipline)

* `exchange_B` — top pooled arm, excluded by the amended donor-sufficiency screen (§1). Do not ship it
  without a new preregistration.
* Near-trace corridor emission — forbidden (IR-52-018): no emitted pixel within 200 m of a mapped trace.
* Ring stripping: 37,600 graded dots → 6,423 dropped inside the 200 m collar → 31,156 emitted. The build
  also ran a **global 3 px spacing pass** after ring stripping and dropped 21 further dots (one per
  cross-fold pair closer than 3 px), so "3 px minimum spacing" is true globally, not only per fold.
* Same-round self-comparison: a rebuilt round's files were being compared with the round's *own* earlier
  artefacts, forcing `unique = False` / lane `DUPLICATE` / ρ = 1.0 on a legitimate build (builds 2 and 3,
  IR-52-026). Fixed by **same-round exclusion**, recorded in `gates.same_round_excluded` (jaccard 1.0,
  1.0, 0.999326 ×3) — never by deleting audit files.

## 5 · A-only candidates for Phase 2 reviewers

`evidence/h88s_a_only_reasoning.json` + `.csv` (600 of 31,424 A-only arm dots, deterministic cap):
each row carries pixel row/col, distance to the mapped catalogue, the depth-to-basement and
gravity-gradient channel values, and a written hypothesis + confounder. The shipped file contains
**0** A-only pixels by construction, so this export is the brief's discovery signal handed forward — it
is not a submission and claims no score.

## 6 · Irregularities flagged in this round

* **IR-H88-005** — the H87 artefact was published before its holdout existed; the H88 round closes that
  by re-scoring H87's *field* on H88's folds (`evidence/h88s_h87field_holdout.json`: 0.056889
  [0.043642, 0.072293], **worse than the same-fold random control**, paired −0.01768 [−0.03074, −0.003495]).
  Never score the shipped H87 raster itself.
* **IR-H88-006** — `registry/h88s_preregistration.json` labels the 3-experiment/2-hour budget as the
  binding constraint; this round used 1 fit and 1 holdout (well inside).
* **IR-H88-007** — `scripts/check_site.py` was red with 22 stale failures from earlier rounds; retargeted,
  and `check_h88` added so the three H88 pages are re-derived from receipts on every run.
* **IR-H88-008 / amendment 80b** — the preregistered primary lost its promotion test; the shipped field is
  the permitted arm with the highest pooled estimate (`single_B`), not the primary. The run card says so.
* **IR-H88-009** — the first H88 build (sha `fa53d6bb7e56…`, 31,177 dots) had 42 dots in 21 pairs closer
  than 3 px across fold boundaries; the global spacing pass dropped 21 dots, giving the final 31,156.
* **IR-H88s-010** — two independent sessions ran an "H88" round. This note's round is the
  sufficiency-screened co-training lane (`h88s_*`); the other is the basement-step round (`h88_*`,
  receipts on `main`). The rename is cosmetic: receipt values, hashes and the shipped bytes are
  unchanged, and `registry/h88s_preregistration.json` records the rename with the frozen hash intact.
* **IR-H88-001 … 004** — see `knowledge/81` (stale 6.3 % claim; reduced-form mass table; placeholder
  raster excluded from correlation; brief-vs-board "highest score" conflict).

## 7 · Limitations

1. No organiser score exists for any number in this repo; the holdout instrument does not rank board
   scores (Spearman −0.1045, n = 13, IR-52-017).
2. The shipped budget was chosen by a point estimate on a noisy instrument (`knowledge/80s`) — a stated
   limitation, not a validated rule.
3. View A is used only as a suppressor; its sufficiency failure means the brief's buried-fault discovery
   signal remains **unmeasured**, not disproved.
4. The 200 m collar is a hedge against the champion's measured ring lever; it also makes the shipped-bytes
   DTI near zero by construction (§3).
5. `training_features.tif` is the graded, interpolated competition raster; all surface channels inherit
   its gridding.

## 8 · Next session: do not redo, do instead

* **Do not** re-run `fit`/`holdout` hoping for a different primary verdict — the NEGATIVE is the record.
* **Do not** ship `exchange_B` without a new preregistration that changes the donor screen.
* **Do not** re-argue the near-trace corridor arm (IR-52-018) or score the H87 raster itself.
* Before spending a slot: re-check mass budget against the champion arithmetic in
  `knowledge/76`/`knowledge/81` and the |G| bracket; a 0.3195 attempt needs ≈ 4,176–6,398 recoverable
  positives at |G| 5,949–14,089 — no arm measured here is within reach.
* Open leads (unregistered, ranked in `knowledge/79`): 2 m soil temperature (GDR 1391 unreachable from
  this sandbox), cover-thickness step (band 15), seismicity lineation, geodetic strain.

## 9 · Evidence index (all under `evidence/`, mirrored to `docs/data/`)

`h88s_channels.json` · `h88s_fit.json` · `h88s_holdout.json` · `h88s_h87field_holdout.json` ·
`h88s_build.json` (final: 31,156 dots, sha256 `124081c0c05fc882ed8c04a2b036c574d4208c10275bb2ede90dd4d2d52246a7`,
129,943 B, gates format/unique/lane/not_union all True) · `h88s_shipped_holdout.json` ·
`h88s_a_only_reasoning.json` · `h88s_run_card.json`.
