# H60D strict lane recheck (2026-10-08)

- Artifact: `submission/gems52-h60d-dis_contrast-arm37654px.tif`, SHA-256 `18bd0efd582f107ccb988fc20016203c323846bf63d3ecea1f75a0670e4586e8`.
- Tool: `scripts/audit_uniqueness.py` (shared `gates.lane_uniqueness_report`), receipt `evidence/h60d_strict_lane_recheck.json`.
- Surface (rank) phase: max Spearman -0.00018 → passes.
- Dots phase: 99.95% of the 37,654 dots lie within 3 px of `13gems_20261001_r13-lattice-s5_v2_nan-outside.tif` → **above 0.70 → DUPLICATE/STOP**.
- The earlier H60D "lane clean" result (IR-H60D-005 / H60-6) excluded calibration rasters from the proximity component. The user's protocol names "any registry raster", so that exemption is withdrawn. The shared gate and `h60d.lane_drift_report` no longer exempt calibration rasters; their tests were updated.
- Consequence: the registry's dense 5 px calibration lattice covers 99.9% of the eligible footprint within 3 px, so any non-empty dot raster fails this literal rule. This is flagged for owner review (IR-H60D-007). The rule itself was not changed.
- Verdict: H60D remains research-only. No slot. No new placement was generated after the STOP.
