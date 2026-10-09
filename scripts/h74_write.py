#!/usr/bin/env python3
"""Write the H74 B_DVA 37,654-dot GeoTIFF, validate it from disk, compare with the 0.2778 reference."""
import hashlib, json, sys, shutil, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np, rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr
from gems52 import submission_writer, structural
elig = structural.FeatureStore(ROOT / "work/r2/features").valid
dots = np.load(ROOT / "work/h74/dots.npy")
pred = dots.astype(np.float32)
name = "h74-dva-variogram-anisotropy-B-37654px-20261009"
note = "H74: View-B + directional variogram anisotropy (det_elev/slope/grav); 200m ring cut; binary 37654 dots; holdout +0.012 vs B"
assert len(note) <= 140, len(note)
out = ROOT / "submission" / f"gems52-{name}.tif"
rec = submission_writer.write_submission(out, pred, ROOT / "data/sample_submission.tif", elig, note=note, name=name,
                                         metadata=dict(round="H74"))
with rasterio.open(out) as a, rasterio.open(ROOT / "data/sample_submission.tif") as s:
    v = a.read(1)
    val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=a.shape, crs_match=a.crs == s.crs,
               shape_match=a.shape == s.shape, transform_match=a.transform == s.transform,
               nan=int(np.isnan(v).sum()), min=float(np.nanmin(v)), max=float(np.nanmax(v)),
               values=sorted(np.unique(v).tolist()), ones=int((v == 1).sum()))
val["PASS"] = bool(val["count"] == 1 and val["crs_match"] and val["shape_match"] and val["transform_match"]
                   and val["nan"] == 0 and val["min"] >= 0 and val["max"] <= 1)
with rasterio.open(ROOT / "data/labels.tif") as d:
    cat = d.read(1) == 1
catd = ndi.distance_transform_edt(~cat) * 100
cmp = {}
for k, p in (("ref_h33_2_b2_0.2778", "data/reference/h33-2-b2-zeros.tif"),):
    with rasterio.open(ROOT / p) as d:
        r = np.nan_to_num(d.read(1)) > 0
    near = ndi.binary_dilation(r, structure=np.ones((7, 7), bool))
    cmp[k] = dict(shared_px=int((r & dots).sum()), near3px_share=float(near[dots].mean()),
                  spearman_on_footprint=float(spearmanr(r[elig][::7], dots[elig][::7]).statistic))
sha = hashlib.sha256(out.read_bytes()).hexdigest()
dl = ROOT / "docs/downloads"; shutil.copy(out, dl / "h74-candidate.tif")
with zipfile.ZipFile(dl / "h74-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
    z.write(out, out.name)
res = dict(file=str(out.relative_to(ROOT)), bytes=out.stat().st_size, sha256=sha, name=name, note=note,
           validator=val, catalogue_min_dist_m=float(catd[dots].min()), catalogue_median_dist_m=float(np.median(catd[dots])),
           vs_reference=cmp, writer_receipt=rec)
(ROOT / "evidence/h74_build.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps({k: v for k, v in res.items() if k != "writer_receipt"}, indent=1, default=str))
