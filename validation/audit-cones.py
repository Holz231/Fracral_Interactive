"""Audit every cached start against the baseline; select independent CPU checks."""
from pathlib import Path
import argparse
import json
import numpy as np

p=argparse.ArgumentParser()
p.add_argument('experiment',type=Path)
p.add_argument('reference',type=Path)
p.add_argument('--width',type=int,default=1980)
p.add_argument('--height',type=int,default=1058)
a=p.parse_args();w,h=a.width,a.height
old=np.fromfile(a.reference,dtype='<f4').reshape(h,w,2)
new=np.fromfile(a.experiment/'dx12-depth.bin',dtype='<f4').reshape(h,w,2)
report={};last=None
for tile in (16,8,4,2):
    path=a.experiment/f'cone-{tile}.bin'
    if not path.exists():continue
    c=np.fromfile(path,dtype='<f4').reshape((h+tile-1)//tile,(w+tile-1)//tile)
    last=np.repeat(np.repeat(c,tile,axis=0),tile,axis=1)[:h,:w]
    hits=old[:,:,1]>0;margin=old[:,:,0]-last
    report[str(tile)]={'baseline_hits_skipped':int(np.count_nonzero(hits & (margin<0))),
        'minimum_log2_margin':float(margin[hits].min()),'finite':bool(np.isfinite(c).all())}
if last is None:raise ValueError('No cone exports')
both=(old[:,:,1]>0)&(new[:,:,1]>0);delta=new[:,:,0]-old[:,:,0]
report['depth']={'closer_by_over_1_percent':int(np.count_nonzero(both & (delta< -np.log2(1.01)))),
    'farther_by_over_1_percent':int(np.count_nonzero(both & (delta>np.log2(1.01)))),
    'farther_by_over_2x':int(np.count_nonzero(both & (delta>1))),
    'lost_hits':int(np.count_nonzero((old[:,:,1]>0)&(new[:,:,1]<=0))),
    'unfinished':int(np.count_nonzero(new[:,:,1]<0))}
indices=np.flatnonzero(both);order=indices[np.argsort(delta.ravel()[indices])]
rng=np.random.default_rng(42017)
unfinished=np.flatnonzero((old[:,:,1]<0)&(new[:,:,1]>0))
changed=np.flatnonzero(both & (np.abs(delta)>np.log2(1.01)))
lost=np.flatnonzero((old[:,:,1]>0)&(new[:,:,1]<=0))
gained=np.flatnonzero((old[:,:,1]==0)&(new[:,:,1]>0))
sample=np.unique(np.concatenate((order[:64],order[-64:],rng.choice(indices,min(64,len(indices)),False),
    rng.choice(unfinished,min(64,len(unfinished)),False),rng.choice(changed,min(64,len(changed)),False),lost,gained)))
rows=np.column_stack((sample%w,sample//w,old[:,:,0].ravel()[sample],new[:,:,0].ravel()[sample],last.ravel()[sample],old[:,:,1].ravel()[sample],new[:,:,1].ravel()[sample]))
np.savetxt(a.experiment/'geometry-samples.csv',rows,delimiter=',',header='x,y,baseline,candidate,cone,baseline_status,candidate_status',comments='',fmt=['%d','%d','%.9g','%.9g','%.9g','%d','%d'])
(a.experiment/'start-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if any(report[str(t)]['baseline_hits_skipped'] for t in (16,8,4,2) if str(t) in report):raise SystemExit(2)
