import numpy as np, rasterio, json, glob
from scipy import ndimage as ndi
D='/home/user/GEMSDOE52/data/'
with rasterio.open(D+'sample_submission.tif') as s: dom=np.isfinite(s.read(1)); prof=s.profile
with rasterio.open(D+'labels.tif') as s: cat=s.read(1)==1
with rasterio.open(D+'training_features.tif') as s:
    desc=s.descriptions; slope=s.read(19); dtb=s.read(15); elev=s.read(12)
print('bands', desc)
ok=dom&(slope>-1e30)&(dtb>-1e30)
dcat=ndi.distance_transform_edt(~cat)*100
q_slope=np.quantile(slope[ok],[.25,.5,.75]); q_dtb=np.quantile(dtb[ok],[.25,.5,.75])
print('footprint slope quartiles',q_slope,'dtb quartiles',q_dtb)
def prof_of(mask,name):
    m=mask&ok
    n=int(m.sum())
    r=dict(name=name,n=n,
      slope_med=float(np.median(slope[m])), dtb_med=float(np.median(dtb[m])),
      frac_slope_top_quartile=float((slope[m]>q_slope[2]).mean()),
      frac_dtb_bottom_quartile=float((dtb[m]<q_dtb[0]).mean()),
      dcat_min=float(dcat[m].min()), dcat_med=float(np.median(dcat[m])),
      frac_within_300m=float((dcat[m]<=300).mean()))
    return r
out=[prof_of(dom,'footprint'),prof_of(cat,'catalogue (labels==1)')]
files={'champion h33-2-b2 (0.2778)':D+'reference/h33-2-b2-zeros.tif'}
for f in sorted(glob.glob(D+'scored/*.tif')): files[f.split('/')[-1][:60]]=f
for k,f in files.items():
    with rasterio.open(f) as s: a=s.read(1); 
    v=np.unique(a[np.isfinite(a)]) 
    m=np.isfinite(a)&(a>0)
    r=prof_of(m,k); r['distinct_values']=int(len(v)); r['mass']=float(np.nansum(np.where(m,a,0)))
    out.append(r)
for r in out: print(json.dumps(r))
json.dump(out,open('/home/user/GEMSDOE52/work/h95/champ_probe.json','w'),indent=1)
