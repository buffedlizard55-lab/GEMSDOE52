# The file protocol vs the arm protocol: measured on the champion raster (branch merge note)

*Written while merging branch `arena/04b2bb40-gemsdoe52` into `main` (2026-10-10). Recorded as
IR-H98-002. Nothing here overrides a round receipt; it is a measurement boundary that every round's
"is this file submittable?" answer depends on.*

## What was measured

`scripts/measure_champion_file_protocol.py` scores shipped rasters **verbatim** on the shared
hide-and-recover instrument (`gems52-pooled-hide-v1`, `src/gems52/evaluate_holdout.py`, pooled over the
four label-blind quadrant folds; predictions on visible-catalogue pixels are zeroed). Receipt:
`evidence/h88_champion_file_protocol.json`, copy in `docs/data/`.

| file | dots | min dot spacing | median distance to the known catalogue | pooled DTI (file protocol) |
|---|---|---|---|---|
| `data/reference/h33-2-b2-zeros.tif` (champion, **owner-reported board 0.2778**) | 37,654 | 3.000 px | 19.6 px | **0.006570** |
| `submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif` | 37,654 | 3.000 px | 21.2 px | **0.006474** |
| `submission/gems52-h88-cotrain-strat-pmcal-27000px-20261010T222229Z.tif` (measurement witness) | 27,000 | 3.000 px | 17.9 px | **0.015268** |

Truth per fold: 53,186 withheld positive pixels, α = 0.2, β = 0.8, 300 m triangular kernel. The
champion's file score decomposes as T = 323.4 of a possible |G| = 53,186, i.e. 0.6 % of the withheld
truth. All three files sit in one spatial family: a catalogue-flank placement with 3 px minimum dot
spacing and a median 18–21 px (1.8–2.1 km) stand-off from the mapped faults, and about a third of the
withheld truth is further than 300 m from that flank.

## Why it matters

1. **A file-protocol DTI near 0.006 carries no evidence against a catalogue-flank file.** The
   owner-reported 0.2778 champion scores the same as a fresh 37,654-dot catalogue-flank emission on
   this instrument. Any page that presents a file-level 0.006 as a rejection is misreading the
   instrument.
2. **Arm-protocol numbers are the only comparable ones in this repository** (a per-fold top-k quota
   placed inside each fold's fair region). The bars used by the round gates — single_B `0.174571`,
   B_DVA2 `0.192829`, random `0.080426` at 9,400 dots/fold — are arm numbers and are labelled as such.
3. **Neither protocol is the public board.** The board prints team-level scores; across the 13
   restore-able scored rasters the instrument and the board rank differently. The only board-derived
   evidence in this repository is the owner-reported mass/score relation (Spearman −0.94 over those 13
   rasters), i.e. fewer, better-placed dots.
4. **Every future promotion gate must state which protocol its bar belongs to.** This is the leakage of
   meaning that IR-H88-007 warned about in this branch's lineage; it is re-stated here after the merge
   because main's H88/H89 rounds use the same words for different numbers.

## Reproduce

```bash
# needs the restored data/ rasters; the submission rasters are in the repository
PYTHONPATH=src:scripts python3 scripts/measure_champion_file_protocol.py
```

The script re-reads `data/labels.tif`, rebuilds the four folds through `run_h83.setup()`, and writes the
receipt with the evaluator's implementation hashes. `scripts/recompute_h87_lane.py` is the companion
harness for lane-only checks (eligible domain = the feature store's valid mask; an artefact's own
publisher copies are excluded so it is never compared with itself).
