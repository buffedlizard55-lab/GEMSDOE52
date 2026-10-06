#!/usr/bin/env bash
# Fetch the raw USGS earthquake catalogue (FDSN event web service) for the GeoDAWN footprint.
#
# WHY: the competition's seismic bands (`ieq_n100a15`, `deq_n100a15`) are computed on a 100 km
# radius; measured in this checkout they are 0.9935-correlated with themselves at a 3 km lag, i.e.
# they carry no information at the 300 m scale the metric resolves.  A raw epicentre catalogue
# (plus moment tensors / nodal planes) is the resolution upgrade, and it is free and official.
#
# SOURCE (official): https://earthquake.usgs.gov/fdsnws/event/1/  (USGS FDSN event web service)
#   docs: https://earthquake.usgs.gov/fdsnws/event/1/
#   ComCat UI: https://earthquake.usgs.gov/earthquakes/search/
#
# STATUS: NOT runnable from the Arena sandbox, whose egress allow-list admits api.github.com and
# pypi.org but returns HTTP 000 for earthquake.usgs.gov (measured 2026-10-04).  Run this on any
# unrestricted machine; it writes data/external/eq_catalog.csv and prints its sha256.
#
# Usage:  bash scripts/fetch_earthquake_catalog.sh [OUTDIR]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/data/external}"
mkdir -p "$OUT"
# Footprint (EPSG:32611, 243350/4508550 origin, 3730x3292 cells at 100 m) in WGS84 is approximately
# 38.0-41.0 N, 120.5-117.0 W; the GeoDAWN study area is the northwestern Great Basin.
curl -sS --fail --retry 3 --max-time 600 \
  "https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=1900-01-01&minmagnitude=1.5&minlatitude=37.5&maxlatitude=41.5&minlongitude=-121.0&maxlongitude=-116.5&orderby=time" \
  -o "$OUT/eq_catalog.csv"
python3 - "$OUT/eq_catalog.csv" <<'PY'
import hashlib, sys, pathlib
p = pathlib.Path(sys.argv[1])
print("bytes:", p.stat().st_size)
print("sha256:", hashlib.sha256(p.read_bytes()).hexdigest())
print("source: USGS FDSN event web service (https://earthquake.usgs.gov/fdsnws/event/1/)")
PY
