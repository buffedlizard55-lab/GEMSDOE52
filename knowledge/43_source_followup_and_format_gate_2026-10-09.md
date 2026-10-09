# 43 · Source follow-up and submission-mask audit (2026-10-09)

**Scope.** This is a dated follow-up to the frozen H65 record. It does not edit or rerun H65, authorize E3, select a submission, or spend a portal slot. No candidate raster was emitted. The H65-A premise result and its original run card remain unchanged.

## Official-source checks completed in this follow-up

### DrivenData scoring and raster contract

Read the official [GEMS problem/scoring page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) (all returned page chunks) and the organizer-staff [masking clarification, post 4](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4).

- Metric: distance-weighted Tversky with α = 0.2, β = 0.8 and a 300 m triangular kernel.
- Raster: one float32 band, EPSG:32611, 100 m cells, bounds/grid matching the supplied training/template raster, values in [0,1]. The official page says cells outside the data bounds should be null/NaN.
- Masking: organizer staff says the known-fault mask is pixel-exact and identical to the provided known-fault labels. It is not a 300 m exemption: nearby predictions can be penalized, and new-fault truth can occur within 300 m of a known trace.

The staff clarification is the reason not to use the scoring kernel as a free buffer around known faults.

### The official template and this repository's old writer

The manifest-pinned `data/sample_submission.tif` was read directly in this checkout. It is a 1-band float32 raster on the expected grid, with `nodata=NaN`; 5,167,373 cells are finite and 7,111,787 are NaN. The current H60 marker TIFF and the archived H63 TIFF instead have no nodata tag and are finite zeros outside that mask.

That is a real discrepancy between the public template/specification and the earlier all-finite compatibility policy. It does **not** establish what caused the user's historical portal error: the rejected bytes and portal receipt remain unavailable. See `IR-H65-007` (not reproduced) and new `IR-H65-008` (shared-writer/template-mask discrepancy).

**Central repair made:** `gems52.submission_writer.write_submission` now reads the sample's finite-data mask, writes NaN/nodata only outside that mask, and preserves valid zero probabilities inside it. `gems52.gates.format_report` now compares the candidate's valid mask and NoData metadata to the sample, rejects NaN inside the sample footprint and finite values outside it, and evaluates [0,1] only on valid sample pixels. `gems52.grid.write_geotiff` accepts this explicit mask path while retaining the finite-array behavior for generic fixtures. Tests use small synthetic rasters; no competition TIFF was written or retroactively changed. Local validation still is not an organizer receipt.

### INGENIOUS Geothermal Data Repository (GDR 1391)

Fetched the official [GDR 1391 record](https://gdr.openei.org/submissions/1391), DOI [10.15121/1881483](https://doi.org/10.15121/1881483), and the [CC BY 4.0 license deed](https://creativecommons.org/licenses/by/4.0/).

- The GDR page labels the dataset **publicly accessible** and displays CC BY 4.0. It lists `wellspringdata.gdb.zip` (19.85 MB) for well/spring temperature and chemistry, and `great_basin_q_volcanics.zip` (9.44 MB) for Quaternary volcanic vents and flows. The page says the datasets may be redistributed with attribution and links to the license.
- The official landing page and resource links were obtainable through page fetch. Attempts to retrieve/parse the two binary ZIP URLs with the available page-fetch tool failed. No official GDR archive bytes were saved, and no byte-for-byte comparison to an official archive or GDR checksum was possible in this session.
- The repository's *derived owner mirror* was obtainable through the allowed GitHub transport using `scripts/restore_data.py --only ext_gdr_wellspring_in_footprint,ext_gdr_volcanic_vents_in_footprint`. Both files matched their repository manifest pins exactly:
  - `data/external/gdr_wellspring_in_footprint.csv`: 2,146,771 bytes, SHA-256 `122718e65bdf55aab0ee12ad20d80062f0deb1de957225a61ad880dd5dc196ea`.
  - `data/external/gdr_volcanic_vents_in_footprint.csv`: 672 bytes, SHA-256 `f91bafbaccaaf2754e71d60434fc0f9eb2c7b880c6e714883f4974542ff6a0bf`.
- The well/spring CSV has 27,092 rows but 12,570 distinct row/column coordinates, so rows are not independent sites. Its `dist_known_fault_px` column is label-derived and is expressly excluded from any future feature, filter, or hypothesis test. No row or value from either restored mirror was used in a model or score in this follow-up.
- License status is source-page verified; the CSV's exact derivation from the official GDB is **not authenticated**. The manifest pin verifies the owner-mirror bytes only.

### Other official geologic context

- Fetched the official [USGS GeoDAWN release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI `10.5066/P93LGLVQ`: Area 1 nominal flight-line spacing is 200 m; Area 2 is 400 m; clearance varies by area and terrain. A 100 m raster cell is not an independent 100 m airborne measurement.
- Fetched the official [USGS 3DEP products page](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services): products are free/no-use-restriction, but 1 m coverage is limited and expanding. Exact 1 m tile coverage/bytes for this footprint were not obtained.
- Fetched the official [USGS blind-geothermal systems report](https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and), DOI `10.2172/1724080`: it describes integrated site studies and transfer/terminating gravity-gradient settings. This supports plausibility for testing a mechanism; it does not confirm a fault at any predicted pixel or describe hidden competition labels.
- Fetched the author-hosted [Blum & Mitchell co-training paper](https://www.cs.cmu.edu/~avrim/Papers/cotrain.pdf), DOI `10.1145/279943.279962`. Its formal framework assumes two views that are each sufficient and compatible with the target. The repo's measured View-A sufficiency failures mean that co-training theory is not grounds to proceed after the registered premise gates failed.

## Resulting source labels

The DrivenData page, staff mask post, USGS GeoDAWN, 3DEP and blind-geothermal report are now **fetched official sources** for the claims above. GDR 1391's public-access/license listing is **fetched official metadata**, but the GDR binary resource bytes and the owner's derived CSV are **not byte-authenticated to one another**. The competition rasters remain manifest-pinned owner mirrors, not organizer-authenticated downloads.

No leaderboard score was refreshed or called ORGANIZER-CONFIRMED. No external score or submission receipt was used.
