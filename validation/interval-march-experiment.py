"""Isolated analytic interval proof inside the sparse continuation marcher.

Avoid solving branch quadratics when Bernstein control values already establish
that no root can lie in the candidate interval. Keep the production fallback.
"""
from pathlib import Path

root=Path(__file__).resolve().parent.parent
base=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
old=(root/'validation/experiments/segment-mobius/fractal.hlsl').read_text(encoding='utf-8')
helpers=old[old.index('struct RayCurve'):old.index('[numthreads(64,1,1)]\nvoid skipRays')]
start=helpers.index('float minimumQuadratic(')
helpers=helpers[:start]+'''float boundedRoot(float3 p,float upper) {
    float signAtStart=p.x<0?-1:1;
    float3 b=signAtStart*float3(p.x,p.x+.5*p.y*upper,p.x+upper*(p.y+upper*p.z));
    float error=dot(abs(p),float3(1,upper,upper*upper))*8e-6+1e-20;
    [branch] if(min(b.x,min(b.y,b.z))>error) return upper;
    return min(upper,firstRoot(p)*.98);
}
'''+helpers[start:]
helpers=helpers.replace('firstRoot(c.w)*.98','boundedRoot(c.w,upper)')
helpers=helpers.replace('firstRoot(norm-4096*c.w)*.98','boundedRoot(norm-4096*c.w,upper)')
helpers=helpers.replace('min(firstRoot(component-c.w),firstRoot(component+c.w))*.98',
    'min(boundedRoot(component-c.w,upper),boundedRoot(component+c.w,upper))')
helpers=helpers.replace('min(firstRoot(norm-.25*c.w),firstRoot(norm-c.w))*.98',
    'min(boundedRoot(norm-.25*c.w,upper),boundedRoot(norm-c.w,upper))')
helpers=helpers.replace('upper<pixel*4','upper<pixel*2')
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
            float maximum=min(.25,max(.02,ratio*64));
            maximum=min(maximum,exitT/t-1);
            if(maximum>ratio*6) {
                float skip=mobiusClearStep(rd,t,scale,maximum,pixel);
                if(skip>ratio*6) {
                    previous=t;t*=1+skip;radius=0;relaxation=.9;verify=false;
                    nextProof=accepted+1;
                    continue;
                }
            }
        }
        #endif
'''+point,1)
out=root/'validation/experiments/interval-march'
out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(front+body,encoding='utf-8')
