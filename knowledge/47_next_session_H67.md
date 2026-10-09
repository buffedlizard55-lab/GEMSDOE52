# 47 · Next session: what to run, what is blocked, and what H66 leaves open

Written at the end of round H66 (2026-10-09). This is the hand-over document: it assumes the reader has
read `README.md`'s H66 block, `knowledge/44` (results and limits) and `knowledge/45` (board algebra),
and it does not repeat them.

## 1 · The single decision only the user can make

The measurements now point at a **structural conflict inside the brief itself**, and no amount of
modelling resolves it:

* The only object in this repository with a *measured* credit density high enough to approach the
  brief's stated bar is the 25,517 px credited core **P1** (ρ ∈ [0.163, 0.205] ⇒
  DTI ∈ [0.2546, 0.3190]; `knowledge/10` §3, re-derived in `knowledge/45` §4).
* The brief's PARALLEL-RUN PROTOCOL clause 1 forbids emitting it: **any subset of P1 has 100 % of its
  dots within 3 px of an existing registry raster**, so it is a lane duplicate by construction, and the
  instruction is "log it as a duplicate and stop".
* P1's own upper bound (0.3190) is **below** 0.3195 anyway, and far below the 0.3774 the board
  actually showed on 2026-10-09.

So the choice for the next session is explicit, and it should be put to the user before any compute is
spent:

| option | what it buys | what it costs |
|---|---|---|
| **A. Keep the 70 % lane rule** | every artefact is genuinely new information for the Final Prize Round's expert review | no candidate can be shown to beat 0.2778; the expected score of a fully novel field at 25k px is DTI ∈ [0.0428, 0.2126] |
| **B. Waive it for a P1-derived file** | DTI ∈ [0.2546, 0.3190], the best *measured* interval in the repo | it is a duplicate of `gems52-h60c-core25517px-arm9668px` and `gems52-h57-union-novel-core25517px-arm14804px`; it adds no new information and burns a slot on a re-emission |
| **C. Spend the slot on a better *detector*, not a better placement** | the only path above 0.32 (§3) | needs data this sandbox cannot fetch, and probably more than one session |

H66 ran option A and reported the negative honestly. Nothing in this repository currently supports
claiming a leaderboard gain, and the run card says so in those words.

## 2 · What H66 killed (do not retest)

* **Thermal-upflow corridors as an emission.** 952 legal seeds (≥ 300 m from the catalogue, measured
  temperature ≥ 60 °C or reservoir geothermometer ≥ 100 °C or class Hot), strike-aligned ±6 px,
  hard-gated on an independent geophysical edge at rank ≥ 0.50: HOLDOUT-DTI **0.015432**
  [0.010756, 0.021313] against uniform random **0.056623**, paired −0.041191
  [−0.047743, −0.034102]. Below random, not merely below the baseline. This is the third strike
  against the thermal-spring family (N-20: +0.00003; H58: 22 px survived) and the first with a CI.
* **The thermal lane is also spatially saturated.** 84.08 % of the final dots lie within 3 px of
  `15GEMSDOE docs/downloads/gems-cleanup-a-20260928T195952Z-curv_scarp.tif` (362,327 dots), while the
  maximum Jaccard with any single prior is 0.0138. The corridors run *alongside* an existing
  curvature-scarp emission without reusing its pixels: new pixels, redundant locations. Any future
  hypothesis whose emission is "linear features in the basin" should expect the same collision, and
  should measure it **before** building, on the surface, exactly as the brief requires.
* **Co-training, round four.** S1 failed again: View A mean out-of-quadrant OOF AUC **0.5930**
  (min fold 0.5462) against a bar of ≥ 0.60 mean and ≥ 0.55 fold. It is the best View A this repo has
  measured (H61 0.5163, H63 0.5362, H64 0.5230) and it still fails. Four consecutive failures of the
  same premise is a result about the layers, not about the tuning.

## 3 · What to run next, ranked by the criterion the metric actually rewards

`knowledge/45` §4 shows the required credit density *falls* with budget (ρ ≥ 0.1595 at 37,654 px for
0.3195, but only ρ ≥ 0.0999 at 100,000 px). So the right question for a new hypothesis is not "is it
geologically clever?" but **"how slowly does its marginal credit density decay?"** Ranked on that:

| # | candidate | why it could hold ρ out to 60k–150k px | cost | data source (free / official) | obtainable here? |
|---|---|---|---|---|---|
| 1 | **Directional variogram anisotropy** (H66-C, `knowledge/43` rank 3) | a *statistical* operator, orthogonal to every gradient/Laplacian/Hessian/structure-tensor channel already in the repo, and N-11 killed gradient coherence, not semivariance anisotropy. Damage zones are 300–900 m wide, i.e. matched to the kernel | medium-high | none new: band 12, band 19, `lidar_scarp_features_u8` | **yes** |
| 2 | **Antithetic / paired-margin inference from band 15** (H66-B, rank 2) | conditioned on the catalogue's geometry but emitting off it, so off-catalogue by construction; half-graben asymmetry means the gently-dipping margin is systematically under-mapped, which is a *population* of faults rather than a scatter of points | medium | none new: bands 15, 13, 18, 12 | **yes** |
| 3 | **A 1 m-derived scarp product at native resolution** | the one lever that could plausibly reach ρ ≈ 0.12 at 100k px, because at a 100 m scoring cell the 1 m expression of a scarp is aliased away; the owner's CI already reduced 706 of 716 tiles once | high | **USGS 3DEP 1 m DEM**, public domain, <https://www.usgs.gov/3d-elevation-program>; tile list in the competition's `1m_DEM_links.csv` | **no** — bash egress is limited to github.com / codeload / api.github.com / pypi.org; only the already-mirrored 12-band LiDAR product is reachable |
| 4 | **Drainage-deflection corridors** (H66-D, rank 4) | classic field criterion for covered faults in Basin and Range piedmonts; the repo has never derived a flow network | high | same 3DEP tiles (a D8 network on the 100 m band 12 is aliased) | **no** |
| 5 | **Seismicity-ridge coincidence** (H66-E, rank 5) | cheapest to implement, but bands 10 and 16 are 100 km-radius smoothings, far coarser than the 300 m kernel, and H59-4 already built `rank(band 16) × rank(∇band 16)` | low | none new | yes, but expected gain is the lowest |

Run 1 and 2 **before** anything that needs new data. Both are pure re-combinations of already-mirrored,
integrity-pinned bands, so a session can reach a holdout number without any fetch.

## 4 · Instrument work that has to happen before any of it can be believed

* **The hide-and-recover instrument cannot rank the board** (IR-H60-003, N-9: it scores the
  organiser-referenced 0.2778 champion at 0.00479, below a random placeholder at 0.02229;
  Spearman(board, instrument) = −0.099, n = 13, p = 0.748). H66 adds a third demonstration: uniform
  random beat the supervised single-view arm in the same table. **Fixing or replacing this instrument is
  worth more than another hypothesis.** Concretely: (a) publish the instrument's ranking of *all*
  owner-scored files beside every future HOLDOUT-DTI, so a reader can see it fails; (b) try a truth set
  built from the *expanded* label definition the Final Round actually uses (expert-verified
  previously-unmapped faults) rather than the mapped catalogue — nothing in the sandbox can build that,
  which is itself the finding; (c) report DTI at the competition's own prevalence (≈ 0.12–0.25 %) instead
  of the holdout's ≈ 1.18 %.
* **S2 cannot gate anything** (IR-H66-005): the independence statistic spans 0.0078–0.7625 across five
  rounds on the same data. Freeze feature set, learner and block size in the pre-registration, or
  demote S2 to a diagnostic.
* **Two shared-tool repairs, once, in the template** (the brief's clause 2 says fix it once and report
  it, never keep a private fork):
  * `gates.uniqueness_report` conflates "identical to a prior" with "a prior failed to open"
    (IR-H66-007). Return `identical_priors` and `unreadable_priors` separately.
  * `PROBE_COVERAGE = 0.95` is structuring-element-dependent (IR-H66-008): the raster that decided this
    round's lane verdict measures 0.8886 under the gate's radius-3 disk and 0.9648 under a square 7×7
    element. Publish the element with the threshold, and treat > ~0.85 under either as a probe.
* **Every future runner must call `grid.footprint_from(bands='all')`** (IR-H66-002). 3,073 in-domain
  cells carry the nodata sentinel; ranking against −3.4e38 silently collapses every channel and still
  produces a format-valid file. This is the highest-severity defect found this round and it is one line.

## 5 · Housekeeping the next session inherits

* `README.md`'s verbatim brief is a stale snapshot of the same day's prompt: six identifiers in the
  H66 prompt have zero hits anywhere in this checkout (IR-H66-011, `knowledge/46`). Repair is
  mechanical — paste, then re-run the byte-identity check in `knowledge/46` §1. **Do not retype it from
  memory.**
* `scripts/run_h64.py` cannot be re-executed in a fresh checkout: its `base.setup()` needs cached
  `work/pred_pre_{A,B}_f{fold}.npy` that are not in git. Any cross-round control comparison against
  H64's stored 0.174517 is therefore a **declared difference**, not a reproduced control.
* Budget honesty: H66 used 3 of 3 experiments but **overran the 2 h wall clock** (cold sandbox, 3.9 GB
  RAM, 2 CPUs, a 19-band restore, a 526-blob prior census fetch, and five runner defects). A session
  that starts cold should assume ~1 h of restore+fetch before the first experiment, and the prior
  census alone is > 227 MB in `work/`.
* Artefacts are reproducible: `scripts/run_h66.py` is a fixed point on decoded pixels
  (SHA-256 `969bb11b7403d9c7506ad609084bcdfe…` from two independent runs), so a future session can
  re-verify the whole round in ~25 minutes without re-deriving anything by hand.
