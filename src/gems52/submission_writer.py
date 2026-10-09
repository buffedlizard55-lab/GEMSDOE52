"""Shared fail-closed GeoTIFF packaging, delegates to the existing grid writer/gate."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
import rasterio
from . import gates, grid


def write_submission(path, prediction, sample, footprint, *, note, name, metadata=None):
    if not name or len(name) > 140 or not note or len(note) > 140:
        raise ValueError('name and note must each have 1..140 characters')
    p = np.asarray(prediction)
    if p.ndim != 2 or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError('prediction must already be normalized, finite and in [0,1]; no silent repair')
    fp = np.asarray(footprint, bool)
    if fp.shape != p.shape or np.any((p > 0) & ~fp):
        raise ValueError('invalid footprint or positive mass outside footprint')
    template_valid = grid.footprint_from(sample, bands='all')
    if template_valid.shape != p.shape or np.any(fp & ~template_valid):
        raise ValueError('model footprint must be a subset of the sample-submission valid-data mask')
    with rasterio.open(sample) as sample_src:
        template_nodata = sample_src.nodata
    path = Path(path)
    if template_nodata is None and template_valid.all():
        # Tiny/full-grid fixtures may have no nodata cells; preserve that template contract.
        grid.write_geotiff(path, p.astype(np.float32), nodata=None)
    else:
        if template_nodata is None or not np.isnan(template_nodata):
            raise ValueError('sample template has outside cells but does not declare NaN nodata')
        # Competition sample uses NaN nodata outside its data polygon. Preserve its validity mask;
        # keep zeros (valid probabilities) elsewhere within the raster footprint.
        output = p.astype(np.float32, copy=True)
        output[~template_valid] = np.nan
        grid.write_geotiff(path, output, nodata=np.nan, valid_mask=template_valid)
    report = gates.format_report(path, sample, footprint=fp)
    if not report['ok']:
        raise ValueError(f'on-disk validator rejected output: {report["problems"]}')
    # A submission ZIP contains ONLY the one TIFF; notes/evidence are adjacent downloads.
    zp = path.with_suffix('.zip')
    with zipfile.ZipFile(zp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(path.name, date_time=(2026, 10, 8, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, path.read_bytes())
    with zipfile.ZipFile(zp) as z:
        if z.namelist() != [path.name] or z.read(path.name) != path.read_bytes():
            raise IOError('single-TIFF ZIP roundtrip failed')
    receipt = dict(file=path.name, sha256=report['sha256'], bytes=path.stat().st_size,
        submission_name=name, note=note, note_chars=len(note), validator=report,
        zip_file=zp.name, zip_sha256=hashlib.sha256(zp.read_bytes()).hexdigest(),
        approved_for_weekly_slot=False, promoted=False, submission_slots_used=0,
        status='research-only; local format validation is not organizer acceptance', metadata=metadata or {})
    path.with_suffix('.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    return receipt
