#!/usr/bin/env bash
# Autonomous Competition Data Placement & SHA-256 Verification Script
# Restores competition rasters (training_features.tif, labels.tif, sample_submission.tif),
# external USGS/DOE layers (3DEP LiDAR scarps, GeoDAWN radiometrics, SGMC faults, GDR 1391),
# and historical scored rasters into data/ (or GEMS_DATA_DIR) with strict SHA-256 verification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${GEMS_DATA_DIR:-$ROOT/data}"
mkdir -p "$TARGET_DIR" "$ROOT/evidence"

echo "[GEMSDOE52] Restoring and SHA-256 verifying competition data into: $TARGET_DIR"
python3 "$ROOT/scripts/restore_data.py" --group all --target-dir "$TARGET_DIR"

echo "[GEMSDOE52] Competition data placement and SHA-256 verification succeeded."
