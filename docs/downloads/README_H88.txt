H88 downloads (research artefacts; see docs/index.html for verdicts)
====================================================================

Round file (27,000 dots) : gems52-h88-cotrain-strat-pmcal-27000px-20261010T222229Z.tif
  sha256                 : a12cd504d7d7d4aa02223343d5b7482a12e3b58a6778c957365fb74f2778da41
  OK to download         : yes
  OK to submit           : no -- loses to single_B on both hide instruments; lane shows
                           97.9% of its dots within 3 px of the published h83-candidate
  A-only reasoning rows  : gems52-h88-cotrain-strat-pmcal-27000px-a-only-reasoning.csv

H87 file (37,654 dots)   : gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif
  sha256                 : a861069b8c780738b83245c1f736313d043989ca33554377f6dffb0465d8e9c3
  OK to download         : yes
  OK to submit           : no -- its field sits at random on the mandate instrument
                           (paired vs random -0.017952), and the
                           shipped file itself scored 0.006474 (58.7% of its dots
                           violate its own 3 px minimum spacing).

Format of both files: single-band float32 GeoTIFF, EPSG:32611, 3730x3292 at 100 m, values in
[0,1], zero outside the footprint, no nodata tag.

Receipts: evidence/h88_run_card.json, evidence/h88_holdout.json, evidence/h88_pm_budget.json,
evidence/h87_holdout.json, evidence/h87_lane_full_registry.json
