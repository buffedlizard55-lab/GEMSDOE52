# 81 · Why `h33-2-b2` scores 0.2778, verified from the restored bytes (2026-10-10)

This note re-measures every claim in `knowledge/76` (the previous answer to the same question) directly
from the restored rasters in this checkout and corrects what does not reproduce. Machine receipt:
`evidence/h88s_mass_lever.json` (written by `scripts/verify_h88_mass_lever.py`). Sources for the metric
and the data are listed in §7.

**Evidence labels used here.** `MEASURED` = read from bytes in this checkout. `OWNER-REPORTED` = copied
from the brief's own results table (`docs/data/ctd5_owner_reported_results.json`; the file labels every
entry `OWNER/USER-REPORTED; NOT ORGANIZER-CONFIRMED`, `receipt: null`). `PUBLIC-BOARD` = read off the
organiser's public leaderboard page and transcribed in `registry/leaderboard_snapshot_2026-10-10.json`.
No projection is written as a score anywhere below.

## 1 · What the champion file is — MEASURED

| property | measured value |
|---|---|
| container | single band, `float32`, DEFLATE, tiled, `nodata = None`, shape (3730, 3292), EPSG:32611, 100 m |
| distinct values | exactly two: {0.0, 1.0} |
| emitted mass `S` | **37,654** px (every positive carries 1.0) |
| min distance to the mapped catalogue | **223.607 m** = √(200² + 100²) — i.e. no pixel inside the 200 m ring |
| median distance to the catalogue | 1,964.688 m |
| share of mass within 300 m | 5.77 % |
| `M` = Σ p·q (300 m triangular kernel vs `labels.tif`) | **277.938** (0.738 % of the mass) |
| sha256 | `c55bafc470054e82…` (pinned in `registry/data_manifest.json` as `ref_h33_2_b2`) |

## 2 · The champion is exactly its parent minus the ring — MEASURED

`data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif` (OWNER-REPORTED 0.2600,
44,090 px) and the champion differ by **6,436 px**, and every one of them lies inside 200 m of a mapped
trace:

* `champion_equals_parent_minus_ring` = **true** (set equality of the champion's support against
  `parent support ∩ {distance > 200 m}`)
* `parent_minus_champion_all_in_ring` = **true**
* 6,436 / 44,090 = **14.597 %** of the parent's mass was deleted for **+6.83 %** relative score
  (0.2600 → 0.2778)

So the +6.8 % is not a better detector: outside the ring the two rasters are the same pixels. It is the
**free precision of not paying tax on pixels that can never earn credit** (`knowledge/06` IR-52-018).

## 3 · The metric, and the correct inversion

The organiser's published metric (transcribed in `src/gems52/metric.py`, pinned by `tests/test_metric.py`
against the organiser's own worked example) is

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )        with  FNw = |G| − T identically
```

with `T = TPw`, `S` = emitted mass, `M = Σ p·max_g k(d)`, `|G|` = hidden truth pixel count (unknown;
bracketed 5,949–12,512 px in this repo, 14,088.7 px from the nested-pair inversion of `knowledge/10`).

`knowledge/76` §3 evaluates the **reduced form** `DTI = T/(0.2·S + 0.8·|G|)`, which is exact only when
`M = T`. The same document measures `M = 277.9` while implying `T` in the thousands, so the shortcut is
not exact here. Re-inverted with the **measured** `M` (MEASURED, `evidence/h88s_mass_lever.json`):

| `|G|` | champion's implied `T` (measured-`M` inversion) | `knowledge/76`'s `M = T` value | `T` required for 0.3195 at `S = 37,654` |
|---|---|---|---|
| 5,949 px | 3,598.66 | 3,414.16 | 4,175.72 |
| 12,512 px | 5,143.03 | 4,872.72 | 5,967.74 |
| 14,089 px | **5,514.12** | 5,223.20 | **6,398.33** |

At `|G| = 14,089` that is **+16.04 % credit** at the same mass (6,398.33 / 5,514.12 = 1.1604);
equivalently a credit density of 16.99 % versus the champion's 14.64 %. The conclusion of
`knowledge/76` §3 is unchanged by the correction — only the numbers move by ≈ 2.8 %.

## 4 · The other reading: same credit, less mass (MEASURED arithmetic)

Solving the identity for the mass `S'` that reaches 0.3195 **at the champion's own implied credit**
(`T = 5,514.12`, `|G| = 14,089`, `M = 277.94`) gives **S' = 24,700.7 px**, and substituting back returns
exactly 0.31950. That is **−34.4 % mass** against the champion's 37,654 px with no extra credit.

Sanity check on the shortcut: the same solve under `M = T` gives 25,384.2 px, which is where
`knowledge/76` §4's "≈ 26,982 px" line and §7's "25,383 px" come from; the measured-`M` value is
24,700.7 px. Both readings say *fewer, better-ranked dots*.

## 5 · Why that reading has board evidence (OWNER-REPORTED scores, MEASURED masses)

| file | measured mass | OWNER-REPORTED score |
|---|---:|---:|
| `h33-2-b2` (champion) | 37,654 | 0.2778 |
| `d2-8` | 44,090 | 0.2600 |
| `d1-5` | 60,069 | 0.2477 |
| `topo-gap-closure-t-v2-on-d1-5` | 61,328 | 0.2449 |
| `h19-5` | 121,131 | 0.1922 |
| `h19-4` | 123,779 | 0.1894 |
| `h16-1` | 123,939 | 0.1855 |
| `h28-dotted-ridge` | 69,281 | 0.1839 |
| `ens12-adopted` | 172,974 | 0.1563 |
| `Hedge-v2` | 227,507 | 0.1563 |
| `h25-ctx-ridge` | 174,232 | 0.1280 |
| `r13-lattice-s5` | 206,895 | 0.0904 |

Spearman(mass, score) = **−0.9282** (n = 12, p < 1e-5) — the `knowledge/76` §4 value reproduces exactly.
`gemsdoe9-PLACEHOLDER-2314b599` (0.0107) is **excluded**: its own manifest id says the bytes are a
stand-in, so its mass is not the real submission's mass (flagged, IR-H88-003).

This correlation is an **ordinal** family statistic over owner-reported scores, not a forecast. The
repo's own instrument cannot rank these files: Spearman(owner-reported, holdout DTI) = −0.1045
(`knowledge/06` IR-52-017). So the honest statement is: *on this family, less mass went with higher score;
the mechanism (a masked pixel can never earn credit but always pays the tax) is measured; the exact
optimal budget is not measured by anything in this repo.*

## 6 · Answer in one paragraph

`h33-h33-2-b2` scores 0.2778 because it is the 0.2600 parent raster with the 6,436 px inside 200 m of a
mapped trace deleted (14.597 % of the parent's mass, MEASURED set equality), and because a masked pixel
can never earn credit while still paying the false-positive tax. Beating 0.3195 needs either **+16.0 %
credit at the same mass** (measured-`M` inversion) or the **same credit in 24,700.7 px instead of
37,654 px** (−34.4 % mass). The repo's mass-vs-score family statistic (−0.9282, n = 12) says the second
route has the better evidence base here, and the repo's own hide-and-recover instrument has never been
used to choose a budget — which is exactly what H88 does (`knowledge/82`).

## 7 · Sources and verification status

* Metric and worked example: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric>
  (transcribed in `src/gems52/metric.py`; `tests/test_metric.py` pins the organiser's 0.6026516673… example).
* Leaderboard (team-level, PUBLIC-BOARD): <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
  — snapshot `registry/leaderboard_snapshot_2026-10-10.json`: #1 xiaofanhu 0.3774, #8 DARD 0.3195,
  #22 extradr19 0.2778. The brief's "0.3195 is the highest score" conflicts with its own "0.3774"
  line; the board resolves it (IR-H85-008, re-flagged as IR-H88-004).
* Rasters: `data/reference/h33-2-b2-zeros.tif`, `data/scored/*.tif`, `data/labels.tif` — restored by
  `scripts/restore_data.py` from SHA-256-pinned mirrors (`registry/data_manifest.json`, 23/23 pins
  verified; integrity-pinned, **not** organiser-authenticated).
* Owner-reported scores: `docs/data/ctd5_owner_reported_results.json` (73 entries, all
  `OWNER/USER-REPORTED; NOT ORGANIZER-CONFIRMED`, all receipts null).
* Blum & Mitchell (background for the lane, not used above): <https://doi.org/10.1145/279943.279962>.

## 8 · Irregularities flagged in this note

* **IR-H88-001** — `knowledge/76` §7 still says the champion deleted "6.3 % of the mass". Measured:
  **14.597 %**. The same document's §4 and `knowledge/01` §5 item 2 carry the correct 14.6 %, so this is
  a stale sentence, not a different measurement.
* **IR-H88-002** — `knowledge/76` §3's table is computed from the `M = T` reduced form while §1 of the
  same document measures `M = 277.9`. Corrected values are in §3 above.
* **IR-H88-003** — `gemsdoe9-PLACEHOLDER-2314b599.tif` is a placeholder in the manifest and must not be
  used as a data point for mass–score correlation. Excluded here; the correlation reported above uses
  the remaining 12 files.
* **IR-H88-004** — brief-vs-board conflict on "highest score" (0.3195 vs 0.3774); board snapshot says
  0.3774 is #1 and 0.3195 is #8. Restated from IR-H85-008 so this round does not lose it.
