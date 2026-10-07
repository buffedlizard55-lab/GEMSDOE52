> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 06 · Provenance and the irregularities register

The machine-readable twin of this file is `docs/irregularities.html`; this note is the version that keeps
the *reasoning* about each item, because a register without reasoning gets re-litigated every session.

## 1. What is verified how

| claim | verification | strength |
|---|---|---|
| metric formula, constants (α=0.2, β=0.8, R=300 m=3 px), kernel `k(d)=max(1−d/R,0)`, format rules (single band float32 in [0,1], EPSG:32611, 100 m, same bounds, null/NaN outside footprint), two rounds with a blind final pick | official page 967, re-read 2026-10-06 21:33 UTC; `src/gems52/metric.py` reproduces the page's own worked example (3.00/1.89/2.00 → 0.60) in `tests/test_metric.py` | **strong** — code + page agree |
| mask is pixel-exact to the training labels; only new-fault truth counts; near-trace predictions are penalised unless new truth is there; new truth *may* sit within 300 m of a known trace | chrisk-dd (organiser staff), community thread 11516 post #4, 21 Sep | **strong** — staff statement, and it changed our design |
| Phase-2 pool = test set updated by expert review of all Phase-1 submissions; no details of test faults | chrisk-dd, community thread 11527 post #7, 23 Sep | **strong** |
| board contents (24 rows, #1 0.3774, #13 this group 0.2778, column header "Best public DW-Tversky (in descending order)", submission counts 11 / 10) | fetched twice, 21:2x and 21:33 UTC, byte-identical; committed to `registry/leaderboard_snapshot_2026-10-06.json` | **strong for the board itself** |
| "the file that scored 0.2778 was `h33-2-b2`, = `h27-4-r1` minus 2,545 masked pixels (40,199→37,654)" | sibling-session owner report; the raster is **not** in this checkout, and the board carries no filename/hash/receipt | **weak** — arithmetic reproduces from files we do have, the pairing does not verify |
| every DTI, gate, fold, strata and layer-screen number in `evidence/` | computed in this repo from the pinned input rasters (`scripts/prepare_data.py` verifies 23 sha256 pins) | **strong and reproducible** |
| band inventory (19 bands; no radiometric channel) | organiser's data README, published as `docs/data/band_inventory.json` | **strong** |
| external datasets in `knowledge/04` | one live metadata/request probe each, with the exact query string recorded; **no bulk download from this environment** | **medium — deliberately labelled per row** |

## 2. Register

**IR-52-001 — there is no radiometric band.** Sibling notes mention gamma-ray features. The provided data
has 19 bands, none radiometric. Any feature builder that silently emits `B_gr`-like channels is wrong.
*Mitigated*: features are checked against the published inventory.

**IR-52-011a — the standing brief's View-B definition names "any radiometric bands in `training_features.tif`".**
Read strictly the clause is conditional, and the condition is false: the official file carries 19 bands and
none is radiometric (`IR-52-001`, `evidence/band_inventory.json`). The conditional is therefore satisfied
vacuously, not contradicted — but a builder that reads only the brief will look for bands that do not exist.
*Resolved*: View B takes radiometry from the GeoDAWN external bundle (`data/external/geodawn_rad_u8.tif`,
4 bands: K, Th, TC and the Th/K ratio, plus `geodawn_extensions_u8.tif` band 1), hash-pinned in
`registry/data_manifest.json`; the code path is `src/gems52/dicoincidence.py::CHANNELS` family
``radiometric``.

**IR-52-002 — "0.3195 is the highest score right now" is stale.** It is rank #7 (DARD). The live top is
0.3774 (xiaofanhu, 11 submissions), so the gap the group must close is 0.0996, not 0.0385. We flag the
user's number rather than adopting it, because acting on a remembered board is how a team optimises a
target that no longer exists.

**IR-52-003 — file↔score mappings in this family are owner reports, not organiser data.** The public board
shows a team and a number, and nothing else. The 0.2778 attribution to `h33-2-b2` is used on this site only
where the *mechanism* is what matters (deleting 6.3 % of one's own mass, all of it overlapping the mask,
raised DTI 2.6 %), and the file itself is not in the checkout. Stated on the site in the same breath as the
number.

**IR-52-020 — the session-2 brief's "0.3195 is the highest score right now" is the *brief's* number, and the
board says 0.3774.** This is the same disagreement as **IR-52-002** (where it is recorded as a stale user
number); it is listed again under the number the brief itself uses, `IR-52-020`, so that a reviewer holding
the brief and this register side by side can find the entry without having to know our internal numbering.
Both readings are true of different moments: 0.3195 is a real row (rank #7, DARD, 10 submissions) in
`registry/leaderboard_snapshot_2026-10-06.json`, and 0.3774 is the live #1 (xiaofanhu, 11 submissions) in
the same fetch. The operational consequence is the one already recorded: the gap to close is 0.0996, not
0.0385, and any target quoted from a memory rather than a fetch is treated as stale.

**IR-52-022 — we overwrote our own uncommitted work, and recovered it from the bytecode.** The H53-1
detector was written earlier in this session but never committed. While restoring it, two of its files were
replaced by rewrites: `src/gems52/structure.py` (overwritten by a draft with a different API, which broke
`dicoincidence.py` and `tests/test_structure.py` until noticed) and `scripts/validate_h53.py` +
`scripts/h53_detect.py` (replaced by this session's rewritten versions of the same procedure).
*Recovery, and its limits*: `structure.py` was recovered from the module's verified bytecode
(`src/gems52/__pycache__/structure.cpython-311.pyc`, compiled from the pre-overwrite source — the pyc records
the source's size and mtime, both of which match the lost file and not the draft), including its docstrings
and numerical steps; the reconstruction is checked **behaviourally** against the loaded bytecode module on
synthetic line/noise/mixed fields (max absolute difference < 1e-6 on energy, coherence, azimuth and the
along-strike persistence), and the one latent defect in the lost source (`with_lambda=True` referenced
unbound globals `lam1`/`lam2`) is fixed rather than reproduced. The two scripts are **not** recoverable —
they had no bytecode cache — so what survives of the pre-registered H53 gate is its rule, recorded in
`registry/preregistration_h53.json` with an explicit provenance note and the timestamps that show the gate
ran before the submission was written. The mitigation is the obvious one and is this session's action: the
whole H53 module set and its scripts are committed in the PR that closes this session, so a later rewrite
cannot destroy work that the repository already holds.

**IR-52-021 — the brief's "single remaining blocker to training is data placement" is stale in this
checkout.** That sentence describes the state of a *different* sibling checkout. Here `scripts/restore_data.py`
has already run to completion: `data/restore_receipt.json` exists, `ALL_VERIFIED=True`, 23 sha256 pins
verified, 907 MB of rasters present (`training_features.tif` 418,912,844 B, `labels.tif` 425,830 B,
`sample_submission.tif` 1,599,597 B). No `download_competition_data.sh` run is needed or possible from this
sandbox (egress-restricted). Consequence: any session that re-runs the restore or treats data placement as
the blocker is spending its budget on a solved problem — the real binders are the weekly submission limit
and the fact that the only offline truth is the catalogue itself.

**IR-52-004 — the rules document's host differs from the brief's citation.** `docs.nlr.gov` is cited; the
document resolves at `www.nlr.gov/docs/fy26osti/96647.pdf`. Not a contradiction, but a link that a human
following the brief would 404 on, so both are printed on `docs/sources.html`.

**IR-52-005 — `sample_submission.tif` contains 60,988 positive pixels, all of them on labelled fault
pixels.** A sample submission that is *not* empty, in a competition whose metric penalises catalogue
overlap. Two consequences: copying it is forbidden by the brief and would also be a metric own-goal.
*Mitigated*: emission is computed on `valid & ~catalogue`, and `gates.uniqueness_report` fails a candidate
whose mass is a subset of a prior's.

**IR-52-006 — the rules page and the portal validator disagree about no-data.** Page: "null or NaN where
there is no data". Validator: values must satisfy `0 ≤ v ≤ 1`, which NaN cannot. Writing 0.0 outside the
footprint is scoring-identical and passes both, so that is the encoding; NaN anywhere in a candidate is now
a named gate failure. This is the actual mechanism of the historical "Predicted values must be in range
[0, 1]" rejection.

**IR-52-007 — we shipped a bug in our own writer tonight, and the gate caught it.**
`grid.write_geotiff` built its affine with `from_origin(TRANSFORM[2], TRANSFORM[0], TRANSFORM[4],
TRANSFORM[5])` instead of `(c, f, a, −e)`; the first file written today therefore had
`transform (-100, 0, 243350, 0, -4508550, 100)`, `res [100, 4508550]` and a southern bound of −1.68e10 m.
`gates.format_report` compared it against `data/sample_submission.tif` and returned
`format_ok=False` with three named problems, so nothing reached the site in that state. The rejected file's
sha256 (`427159429ffcc206…`) and its evidence record are kept under
`evidence/submission_*-r1-rejected-transform.json`; the bytes are not in the repo.
*Fixed*: the writer now builds `Affine(*TRANSFORM)` and asserts the reconstruction (cell size 100 m, origin
from `c,f`) before writing, and `read_geotiff` re-reads the file so the receipt describes the bytes, not the
intent. Recorded here because "the gate found a bug in the thing that writes the gate's input" is the
evidence that the gate is real.

**IR-52-008 — the brief's verbatim wording is unrecoverable in this workspace.** Single commit, no brief
file, `grep -rl "Blum"` hits only our own module. Restated faithfully in `knowledge/00` with this
provenance note; no quotation marks were invented.

**IR-52-009 — this sandbox has no network egress** (`SSL_ERROR_SYSCALL` / TLS EOF for
`www.drivendata.org`). Live fetching belongs to `.github/workflows/feed.yml`; anything timestamped as
"live" in the sandbox came through the agent's page-fetch tool, and says so.

**IR-52-010 — the pre-registered promotion gate failed for the brief's own mechanism.** Co-training
pseudo-labels: −0.0158 (tip) and −0.0303 (hide) DTI against the naive union at equal budget, 0/4 fold
support on both instruments, `promoted=false` on both. Published, not buried; the disagreement *strata*
survive, the label round does not. No submission slot was spent.

**IR-52-011 — the first pre-registration's blend weights were asserted, not fitted**, and point the wrong
way for this population. Any re-weighting must appear as a *named arm* in `evidence/holdout_*.json`, never
as a quiet config change; `wt_A20B80` exists precisely to make the fitted version auditable.

**IR-52-012 — closed. The file was built nine minutes before the composite sweep finished** (corridor share
0.0 by explicit command line rather than by sweep verdict); the sweep then selected that same configuration,
and rebuilding from `evidence/composite.json` reproduced the identical sha256, so the interim state is now
only a provenance footnote. What replaced it in the record is the *substantive* caveat: The two extremes are both measured
(`union_cor|37654` 0.0320 tip / 0.0001 hide; `B_only|37654` 0.0291 / 0.0518), so the selection record in
`evidence/submission_*.json` says `selection_source: explicit --far/--cor/--split`, `promoted: false`,
`forced: true`. the sweep's control bar was misdefined in its first version (a
`max`-over-random-variants control that handed the corridor arm its own score as the bar to beat), and
`evidence/composite.json` now stores both selections. Fixed rule: `beats_random_all: true`
(tip +16.7 %, hide +32.1 % over matched-budget random), `beats_union_bar: false` (+0.0051 on tip against the
registered +0.010), `promoted: false`. Every interior split that funds the corridor scores lower on the
sum — see `knowledge/05` §3b.

**IR-45-001 (inherited) — the footprint area disagrees across the family**: 5,165,852 / 5,165,840 /
5,167,373 px. We recount → **5,165,840** (catalogue 60,894 px = 1.1803 % of it; the third number is a mask
definition with a 1-px collar). All fractions on the site are against the recount.

**IR-52-013 — the board implies the weekly limit is being consumed by the leaders.** xiaofanhu has 11
submissions at the top, our team 10. Nothing about this repo's schedule assumes we can iterate on the
leaderboard freely; that is what the two instruments and the register are for.

## 3. Three passes, what each one did (as the brief requires)

* **Pass 1 — build.** Metric, grid, features, co-training, holdout, gates written from the official pages;
  inputs pinned by sha256; metric unit-tested against the page's own worked example.
* **Pass 2 — re-derive independently.** Re-fetched the board (identical), recomputed the arm tables on both
  instruments, re-read every claim on this site against its `evidence/*.json`, wrote the register above, and
  cross-checked the 0.2778 mechanism against the sibling rasters actually present.
* **Pass 3 — try to break the publication path.** `scripts/check_site.py` (committed): dead links, JSON the
  JS asks for but the feed never writes, unbalanced inline scripts, hard-coded numbers on the numbers page,
  and a byte-for-byte re-serve of the .tif through a local HTTP server. It is this pass that surfaced
  IR-52-007 (writer transform), the `exists` flag the hero block needs, the missing
  `feed.html`/`irregularities.html`/`sources.html` that the nav pointed at, a TDZ bug in `feed.html`'s
  inline script, two page scripts that did not parse at all (`docs/tables.js`, unbalanced row-array
  literal; `docs/exec.js`, `a && b ?? c`), and the 0-byte-NaN encoding question that became IR-52-006.
  Six of these were invisible in the browser: a broken script on a data-driven page renders as "no data",
  which is why `check_site.py` parses the JS instead of loading the page and eyeballing it.

## 4. What would change our mind

1. `evidence/composite.json` selecting an interior corridor share that passes rule 1 on both instruments.
2. A relocated ComCat layer (D-1) that ranks far-field mass better than `B_only` on the hide instrument —
   the only incumbent we have not yet beaten.
3. Well-based stratigraphic offset (D-3) confirming or killing H52-1: if the marker bed does not step
   across an A-only structure, the "buried range-front fault" story is an artefact and the A-only stratum
   should stop informing the ranking at all.

**IR-52-016 — the scheduled board fetch reaches the page and reads nothing.** First CI run, 22:28 UTC:
HTTP 200 from `www.drivendata.org` (so GitHub's egress is fine, unlike this sandbox's TLS EOF), then
`leaderboard table parsed empty — page layout changed`, because the board table is built client-side and the
server HTML contains no `<tr>` rows to parse. The parser raises rather than publishing an empty board; the
run fell back to the dated snapshot and reported why. **Consequence for how this site must be read: "live
data feed" means live-attempted, snapshot-served for the leaderboard** — every other number on the site comes
from `evidence/`, which we generate ourselves, and is genuinely regenerated on every push. Closing this needs
a data endpoint the organiser publishes; guessing at one is not a fix, so the status line stays visible
instead.

---

## Additions from the H53 round (2026-10-07)

The register on [the site](../docs/irregularities.html) is authoritative and is generated by
`scripts/make_site_pages.py`; these are the one-line summaries so that `knowledge/` does not send a
reader to HTML for a fact.

**IR-52-017 — the validation instrument does not predict the organiser's score.** Spearman
ρ(reported, simulated DTI) = −0.1045, p = 0.734, n = 13 over every restored scored file. The group's
best file on the board ranks *last* of 13 on the instrument (lift 0.09× mass-matched random) and the
file the instrument ranks first scored 0.1563. Full measurement and the confound that was checked and
excluded: `knowledge/03` N-9. **Every selection made through that gate inherits the defect**, including
the `promoted: false, forced: true` decision recorded in `docs/data/submission.json` for the H52 file.

**IR-52-018 — the ≤200 m ring around the mapped catalogue earns exactly zero credit.**
`h33-2-b2` (0.2778) ⊂ `gems24-d2-8` (0.2600); the 6,436 px difference lies entirely inside 200 m of a
mapped trace and deleting it *raised* the score 6.8 %. `min` distance-to-catalogue inside `h33-2-b2` is
223.6 m, so it holds 0 px in the ring. This **contradicts** `knowledge/01` §5 item 2 and `knowledge/02`
H52-2, which made ranking that ring the primary emitter arm; §5 item 2 is now struck through with the
measurement. The staff claim that the mask is pixel-exact survives as a statement; the bytes say scoring
behaves as if there were a ~2 px ring, or as if the hidden truth never comes within 200 m. Both readings
give the same rule and the bytes cannot separate them.

**IR-52-019 — no feature available here re-ranks inside the champion file.** Best blocked AUC on the
credited-vs-uncredited contrast: 0.5453 over 63 point/local-differential features (the maximum of 63
tests), 0.5122 over 108 structure-tensor features. Habitat is strongly identifiable (AUC 0.7023 for the
champion's dots against uniform random) and strongly useless — the tiers carrying 4–20× less credit have
habitat AUCs of 0.68–0.70. `knowledge/03` N-10, N-11. Consequence: `ρ_novel` is a stated prior, never a
point estimate.

**IR-52-020 — a per-block AUC of 1.000 over n = 3 samples** appeared in the first H53 build. Blocks now
carry `counted_in_mean` (n ≥ 500) and the mean uses only counted blocks; the raw list is kept.
`knowledge/03` N-13.

**IR-52-021 — `gates.find_priors` treated competition inputs as prior submissions.** Sweeping a root
containing `data/training_features.tif` read band 1 of a 19-band feature stack as somebody's answer and
produced a "prior union" of 5,363,764 px against a 5,167,373 px footprint, which silently emptied the
novel-pixel pool to 93 px. Fixed with a `NOT_A_SUBMISSION` skip list plus
`tests/test_gates.py::test_find_priors_skips_competition_inputs`; the union is now 1,062,207 px over 18
real prior rasters.

**IR-52-022 — the downloads index was always one run behind the downloads directory.**
`refresh_feed.py` built `docs/downloads/index.html` before copying rasters into it, so the current
submission was on disk and absent from the table — the "download the file and submit it" promise pointed
at the previous round's artefact. Rasters are now staged first, and a one-click ZIP (raster + the note to
paste + the evidence JSON) is written beside the TIF.

**Carried forward, unchanged and still open:** IR-52-003 (no file→score mapping is
organiser-authenticated — every number in `knowledge/07` inherits this), IR-52-008 (there is no
radiometric band *in `training_features.tif`*; the radiometrics are the external
`geodawn_rad_u8.tif` / `geodawn_extensions_u8.tif` layers, which is what the brief's conditional clause
resolves to here), IR-52-009 (the external GDR CSVs are derived, not organiser-authenticated),
IR-52-016 (the scheduled board fetch reaches the page and reads nothing, because the table is built
client-side; the site therefore serves a dated snapshot and says so).

**IR-52-029 — two rounds shipped a submission in parallel, and this site now offers the later one.**
PR #8 merged to `main` while the H54 round was running, shipping
`gems52-h53-coincidence-gated-singles-37654px-r1.tif` (cross-dataset orientation coincidence, promoted on
the tip/hide instruments at +21 % / +28 % over the repo's previous best at that budget). This round ships
`gems52-h54-revealed-core-strike-continuation-50517px-r1.tif` and `submission/LATEST.txt` now points at
it. **That is one session's judgement call over another's shipped artefact, so it is flagged rather than
made quietly.**

The reason is a measurement, not a preference: `knowledge/03` N-9 / `IR-52-023` establish that the tip and
hide instruments carry no information about the organiser's score (Spearman ρ(reported, simulated DTI) =
−0.1045, p = 0.734, n = 13 over every restored scored file; the group's best file on the board ranks
*last* of the 13 on them). A promotion earned on those instruments is therefore not evidence about the
score. The H54 file's retained half rests on a different kind of claim — exact arithmetic on five scored
files standing in verified nesting relations, giving `t(A & C) ∈ [4,168, 5,223]` and hence
`DTI(core alone) ∈ [0.2546, 0.3190]` — which does not depend on any simulator being right.

Neither artefact is deleted. Both stay in `submission/`, both stay listed on the download page with their
own gate verdicts, and the H53 code, evidence and hypotheses keep their numbering (this round is
renumbered **H54**, `knowledge/10` and `knowledge/11`, precisely so that it does not collide). The H53
raster also becomes a *prior* for the uniqueness gate: measured prior union 1,117,016 px over 21 rasters,
novel pool 440,798 px, **0** collisions between the H54 novel mass and any prior pixel.

**Reverting is one line** — point `submission/LATEST.txt` back at the H53 file and re-run
`scripts/refresh_feed.py`. Nothing else in the repo depends on which of the two is offered.

## H55 / current-source refresh (2026-10-07)

**IR-52-030 — the current official public leaderboard differs from the stale prompt.** Arena's dated
fetch of the rendered DrivenData page on 2026-10-07 reports a leader at **0.3774**, `DARD` rank 7 at
**0.3195**, and participant `extradr19` rank 13 at **0.2778**. The page does not expose a TIFF name or
hash, so it does not connect that 0.2778 score to `H33-2-B2`; participant identity is not authenticated
to this repo. `registry/leaderboard_snapshot_2026-10-07.json` is the observed table; scheduled
DrivenData access remains disabled by policy.

**IR-52-031 — the old prior inventory was not local.** The prior check found all 377 eligible TIFFs
missing under ignored `data/review/priors/`. `scripts/review_sources.py --download-priors --workers 4`
then refreshed the owner-site trees and downloaded 395 distinct linked TIFF URLs; 389 are aligned,
single-band competition-grid priors and all 389 bytes are now present. Four linked TIFFs are not
eligible predictions and two formerly linked owner-repository blobs no longer resolve. 53GEMSDOE and
54GEMSDOE still have no supplied links. This is the finite accessible inventory, not a proof about
private/unlinked/external-storage files; the raw file-to-score mapping remains unknown.

**IR-52-032 — the GDR 1391 metadata is reachable but the promised raw point archives are not.** The
official GDR record page was fetched. The linked well/spring ZIP still failed direct TLS
(`SSL_ERROR_SYSCALL`) and the paleo-geothermal ZIP returned HTTP 500. No raw GDR feature entered H55;
H55-2 is not viable until the official bytes can be acquired and hashed. See `evidence/source_review_h55.json`.

**IR-52-033 — H55-1 improved the local mean slightly, then failed its frozen slot gate.** The new
signed gravity/RTP LoG-edge feature set produced mean DTI **0.195217** versus the strongest comparable
surface-only View-B baseline **0.194671**, paired lift **+0.000546**, positive in **2/4** folds. The
preregistered threshold is +0.005 mean and 3/4 positive. No slot was used. The candidate is a research
artifact only; this score is catalogue-component hide/recover, not a public leaderboard result.

**IR-52-034 — the H55 co-training premise is only partly measured.** H55 View-A/B negative-error
correlation had a maximum absolute blockwise coefficient **0.08443** in 2,093 50×50 blocks. This let a
separate exchange experiment proceed but does not prove conditional independence. Sending A-generated
pseudo-segments to B changed B's mean by **+0.001488** over its baseline (3/4 folds positive), below the
registered +0.005 threshold; sending B to H55-A changed A's mean by **−0.004381** (0/4 positive). Neither
exchange was used in the H55 primary TIFF.

**IR-52-035 — support novelty still fails closed.** The 389-raster inventory is broader than the former
383-entry snapshot. The new candidate's exact decoded-pattern comparison, strict all-prior support
novelty, and matched-budget A/B max-union results are recorded separately in
`evidence/submission_h55.json`/`evidence/uniqueness_h55.json`; a saturated prior union is not treated as
evidence of identity. The original >=20% support-novelty diagnostic is not waived for slot eligibility.

**IR-52-036 — the new file was not uploaded.** No DrivenData portal request was made, no organizer score
was observed, no acceptance claim is made, and no weekly slot was used. The TIF's on-disk format check
is local evidence only. The new official rule's generative-AI narrative requirement is addressed in
`knowledge/13_ai_use_h55.md`.

**IR-52-037 — post-run code review found a preregistration-to-implementation mismatch.** The frozen
H55-1 candidate-feature list names gravity bands 13/11/18 and magnetic bands 2/9 for the signed-LoG
edge transforms. The implementation actually computes the new LoG/sign-change channels for gravity
band 13 and RTP band 2 only; bands 11/18/9 remain raw or pre-existing R2 features, not H55-transformed
channels. The +0.000546, 2/4 result and the research TIFF therefore evaluate this narrower implemented
variant, not the complete registered feature set. The original preregistration/hash and results are
preserved; no retroactive amendment is made. Do not tune the omitted channels on the same four folds;
any future test needs a separate preregistration and untouched confirmation design. Machine-readable
audit: `evidence/protocol_deviation_h55.json`. The failed gate and no-upload decision are unchanged.
