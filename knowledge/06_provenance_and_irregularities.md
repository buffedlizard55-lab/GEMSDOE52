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

**IR-52-002 — "0.3195 is the highest score right now" is stale.** It is rank #7 (DARD). The live top is
0.3774 (xiaofanhu, 11 submissions), so the gap the group must close is 0.0996, not 0.0385. We flag the
user's number rather than adopting it, because acting on a remembered board is how a team optimises a
target that no longer exists.

**IR-52-003 — file↔score mappings in this family are owner reports, not organiser data.** The public board
shows a team and a number, and nothing else. The 0.2778 attribution to `h33-2-b2` is used on this site only
where the *mechanism* is what matters (deleting 6.3 % of one's own mass, all of it overlapping the mask,
raised DTI 2.6 %), and the file itself is not in the checkout. Stated on the site in the same breath as the
number.

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
