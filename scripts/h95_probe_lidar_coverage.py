import numpy as np, rasterio, json
from scipy.stats import spearmanr
exec(open('/home/user/GEMSDOE52/scripts/h95_probe_board_instrument.py').read().split("with rasterio.open(D+'sample")[0])
with rasterio.open(D+'sample_submission.tif') as s: dom=np.isfinite(s.read(1))
with rasterio.open(D+'external/lidar_scarp_features_u8.tif') as s: lv=s.read(12)>0
with rasterio.open(D+'labels.tif') as s: cat=s.read(1)==1
print('lidar coverage of footprint', float((lv&dom).sum()/dom.sum()), 'catalogue in lidar', float((lv&cat).sum()/cat.sum()))
rows=[]
for k,sc in BOARD.items():
    with rasterio.open(D+k) as s: a=s.read(1)
    m=np.isfinite(a)&(a>0)&dom
    rows.append((k.split('/')[-1][:40],sc,int(m.sum()),float(lv[m].mean())))
    print(rows[-1])
y=[r[1] for r in rows]; f=[r[3] for r in rows]; n=[r[2] for r in rows]
print('spearman(lidar frac, board)',spearmanr(f,y).statistic,' spearman(mass,board)',spearmanr(n,y).statistic)
