"""Allow branch crossings by bounding their full image, not only one branch."""
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--fold-limit',type=int,default=0)
options=parser.parse_args()
if options.fold_limit<0:
    parser.error('fold limit must be nonnegative')
root=Path(__file__).resolve().parent.parent
base=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
old=(root/'validation/experiments/fold-bounds/fractal.hlsl').read_text(encoding='utf-8')
helpers=old[old.index('float3 intervalMinimumAbs'):old.index('void skipFoldBounds')]
if options.fold_limit:
    helpers=helpers.replace('for(int iteration=first;iteration<=end;iteration++) {',
        f'for(int iteration=first;iteration<=min(end,first+{options.fold_limit});iteration++) {{')
base='#ifndef INTERVAL_MARCH\n#define INTERVAL_MARCH 0\n#endif\n'+base
base=base.replace('bool marchJob(',helpers+'\nbool marchJob(',1)
start=base.index('bool marchJob(')
front,body=base[:start],base[start:]
body=body.replace('    float exitT=exp2(min(job.horizon-scale,24));','''    float exitT=exp2(min(job.horizon-scale,24));
    #if INTERVAL_MARCH
    int nextProof=accepted;
    #endif''',1)
point='        if(radius>0 && t>previous) {'
assert body.count(point)==1
body=body.replace(point,'''        #if INTERVAL_MARCH
        if(accepted>=nextProof && ratio<.02) {
            nextProof=accepted+32;
            float span=min(.125,max(.01,ratio*32));
            span=min(span,exitT/t-1);
            if(span>ratio*6 && emptyInterval(rd,t,scale,span,pixel)) {
                previous=t;t*=1+span*.99;radius=0;relaxation=.9;verify=false;
                nextProof=accepted+1;
                continue;
            }
        }
        #endif
'''+point,1)
suffix=f'-{options.fold_limit}' if options.fold_limit else ''
out=root/('validation/experiments/interval-box-march'+suffix)
out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(front+body,encoding='utf-8')
