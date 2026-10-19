"""Summarize saved screening results; do not treat contended timings as idle FPS."""
from pathlib import Path
import csv,json,statistics
import numpy as np
from PIL import Image

root=Path(__file__).resolve().parent.parent
experiments=root/'validation/experiments'
result={'timing_environment':'Concurrent ComfyUI GPU workload, not isolated FPS evidence','static':[],'motion':[]}
for name in ['native-threshold-0.0001','native-threshold-0.00001','native-exact-saturate','native-exact-sphere-base','native-exact-combined','native-exact-reciprocal']:
    for fixture in ['edge','heavy','new-slow','new-last']:
        p=experiments/name/fixture/'validation/replay'
        q=experiments/'native-threshold-0.001'/fixture/'validation/replay'
        if not (p/'saved-native.json').exists():continue
        before=np.fromfile(q/'saved-native-accelerated-depth.bin',np.float32).reshape(-1,2)
        after=np.fromfile(p/'saved-native-accelerated-depth.bin',np.float32).reshape(-1,2)
        im0=np.asarray(Image.open(q/'saved-native-after.png')).astype(np.int16)
        im1=np.asarray(Image.open(p/'saved-native-after.png')).astype(np.int16)
        error=np.abs(im0-im1)
        result['static'].append({'variant':name,'fixture':fixture,
            'changed_depths':int(np.sum(before[:,0]!=after[:,0])),
            'changed_statuses':int(np.sum(before[:,1]!=after[:,1])),
            'changed_pixels':int(np.sum(np.any(error!=0,axis=-1))),
            'rgb_mean_error':float(error[...,:3].mean()),
            'pixels_over_16':int(np.sum(np.max(error[...,:3],axis=-1)>16)),
            'gpu_ms':json.loads((p/'saved-native.json').read_text())['after_ms']})
for name in ['native-exact-ab','native-chunk-32','native-chunk-16']:
    for fixture in ['edge','heavy','new-slow','new-last']:
        p=experiments/name/fixture/'validation/fold-ab'
        if not (p/'comparison.json').exists():continue
        rows=list(csv.DictReader((p/'comparison-timings.csv').open()))
        before=[float(row['gpu_ms']) for row in rows if row['candidate']=='0']
        after=[float(row['gpu_ms']) for row in rows if row['candidate']=='1']
        pairs=[]
        for i in range(20):
            a=[float(row['gpu_ms']) for row in rows if int(row['round'])==i and row['candidate']=='0']
            b=[float(row['gpu_ms']) for row in rows if int(row['round'])==i and row['candidate']=='1']
            pairs.append(statistics.mean(b)/statistics.mean(a))
        result['motion'].append({'variant':name,'fixture':fixture,
            **json.loads((p/'comparison.json').read_text()),
            'old_mean_ms':statistics.mean(before),'new_mean_ms':statistics.mean(after),
            'median_paired_ratio':statistics.median(pairs)})
out=root/'validation/optimization-2026-10-17/exact-fold-summary.json'
out.write_text(json.dumps(result,indent=2)+'\n')
print(out)
