#!/usr/bin/env bash
# Deterministic research reproduction, NEVER a portal upload or promotion.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${GEMS_PYTHON:-python3}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 PYTHONUNBUFFERED=1
mkdir -p work/ctd5
"$PYTHON" scripts/restore_data.py --target-dir work/ctd5/input --only training_features,labels,sample_submission
"$PYTHON" scripts/prepare_data.py --data-dir work/ctd5/input --out-dir work/ctd5/prepared
"$PYTHON" scripts/audit_ctd5_sources.py --restore-frozen
PYTHONPATH=src "$PYTHON" - <<'PY'
from pathlib import Path
from gems52.structural import build, FeatureStore
p=Path('work/ctd5/features/manifest.json')
if not p.exists():
    build(features='work/ctd5/input/training_features.tif', sample='work/ctd5/input/sample_submission.tif',
          dest='work/ctd5/features', include_optional_profiles=False)
else:
    FeatureStore(p.parent)  # the runner verifies source and per-column hashes before fit
PY
"$PYTHON" scripts/run_ctd5.py canary
"$PYTHON" scripts/run_ctd5.py fit
"$PYTHON" - <<'PY'
import json, subprocess, sys
x=json.load(open('evidence/ctd5_independence.json'))
if x['allow_exchange']:
    subprocess.run([sys.executable,'scripts/run_ctd5.py','exchange'], check=True)
else:
    print('Independence gate fired: no exchange. Only pre-exchange negative artifact may be exported.')
PY
"$PYTHON" scripts/build_ctd5_submission.py
# A negative result is successful execution, NOT authorization to submit.
"$PYTHON" - <<'PY'
import json
x=json.load(open('evidence/ctd5_run_card.json'))
print('RESULT:',x['verdict'],'SUBMIT_OK:',x['submit_ok'],'TIFF:',x['raster_file'])
PY
