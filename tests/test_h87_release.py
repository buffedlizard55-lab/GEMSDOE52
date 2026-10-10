"""Regression checks for the frozen H87 research-only file and published status.

No data/ or work/ directory required in CI: the pinned on-disk output and run card are enough.
"""
import csv
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]


def test_h87_download_is_format_valid_and_not_promoted():
    card = json.loads((ROOT / 'evidence/h87_run_card.json').read_text())
    tif = ROOT / 'docs/downloads' / (card['submission_name'] + '.tif')
    raw = tif.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == card['raster_sha256']
    assert card['validator']['ok'] and card['download_ok'] and not card['submit_ok']
    assert card['verdict'] == 'negative' and card['competition_slots_used'] == 0
    assert len(card['note']) <= 140
    with rasterio.open(tif) as ds:
        x = ds.read(1)
        assert ds.count == 1 and ds.dtypes == ('float32',)
        assert ds.shape == (3730, 3292) and ds.crs.to_epsg() == 32611
        assert ds.transform == Affine(100, 0, 243350, 0, -100, 4508550)
    assert np.isfinite(x).all() and 0 <= x.min() <= x.max() <= 1
    assert np.count_nonzero(x) == 37600
    with zipfile.ZipFile(tif.with_suffix('.zip')) as z:
        assert z.namelist() == [tif.name]
        assert z.read(tif.name) == raw


def test_h87_reasons_match_all_emitted_cells_and_lane_stop():
    card = json.loads((ROOT / 'evidence/h87_run_card.json').read_text())
    tif = ROOT / 'docs/downloads' / (card['submission_name'] + '.tif')
    with rasterio.open(tif) as ds:
        emitted = ds.read(1) > 0
    with gzip.open(ROOT / card['reasoning_csv_gz'], 'rt', newline='') as f:
        reader = csv.DictReader(f)
        coords = set()
        for row in reader:
            y, x = int(row['row']), int(row['col'])
            assert emitted[y, x] and (y, x) not in coords
            assert float(row['A_rank']) > float(row['B_rank'])
            assert 'not necessarily high' in row['reason']
            assert row['named_nonfault_mimic'] and row['verified_fault'] == 'no'
            coords.add((y, x))
    assert len(coords) == int(emitted.sum())
    assert card['exact_unique_vs_accessible_registry']
    assert card['surface_gate']['duplicate'] is False
    assert card['final_dots_gate']['duplicate'] is True
    assert card['final_dots_gate']['max_near_3px_fraction'] > .70
    assert any('h61-deepsharp' in r['path'] and r['near_3px_fraction'] > .70
               for r in card['final_dots_gate']['offenders'])
    assert card['not_union']['surface_differs_from_union_pixels'] > 0
    assert card['holdout_dti']['dti'] < .1745173
    for p in ('docs/index.html', 'docs/executive-summary.html',
              'docs/downloads/index.html', 'docs/h87-executive-summary.html'):
        s = (ROOT / p).read_text()
        assert 'SUBMIT NO' in s or 'OK TO SUBMIT TO THE COMPETITION: NO' in s
        assert ('gems52-h87-deepedge-Aonly-37600px-20261010.tif' in s)
