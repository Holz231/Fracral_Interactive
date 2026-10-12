from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
old=(root/'validation/experiments/interval-box/fractal.hlsl').read_text()
helpers=old[old.index('float3 intervalMinimumAbs'):old.index('[numthreads(64,1,1)]\nvoid skipRays')]
helpers=helpers.replace('    int end=min(384,counts.x+12);', '''    float3 boxHigh=(2*2.8*(1+2.8)+fractalParameters.xyz*(2.8-1))/(2.8*2.8-1);
    float3 boxLow=2*2.8+fractalParameters.xyz-boxHigh*2.8;
    int end=min(384,counts.x+12);''')
helpers=helpers.replace('        if(iteration>first || first>0) {','''        float3 excess=max(max(lower-boxHigh,boxLow-upper),0);
        float bound=.45*max(excess.x,max(excess.y,excess.z))/max(derivative,1e-30);
        if(min(bound,escapeBound)>pixel*.75) return true;
        if(iteration>first || first>0) {''',1)
helpers+=r'''
void skipFoldBounds(inout RayJob job,float3 rd) {
    float safe=job.previous*(1+max(job.radius*.9,1e-7));
    float start=(job.verify&1)!=0?safe:job.t;
    float exitT=exp2(min(job.horizon-job.scale,24)),furthest=start;
    float pixel=1/(renderInfo.y*1.85);
    [loop] for(int probe=0;probe<8;probe++) {
        float span=min(.0625,exitT/start-1);
        if(span<pixel*8 || !emptyInterval(rd,start,job.scale,span,pixel)) break;
        start*=1+span*.99;furthest=start;
    }
    if(furthest>job.t*(1+pixel*4)) {
        job.t=job.previous=furthest;job.radius=0;job.relaxation=.9;job.verify=0;
        job.first=citadelStart(log2(furthest)+job.scale);
        RayPrefix prefix=rayPrefix(rd,job.first,job.scale);job.derivative=prefix.derivative;job.limit=prefix.limit;
    }
}
'''
s=s.replace('groupshared uint pendingCount',helpers+'\ngroupshared uint pendingCount',1)
s=s.replace('        pending=marchJob(job,rayDirection(position),position);','''        #if CACHED_CURVE
        skipFoldBounds(job,rayDirection(position));
        #endif
        pending=marchJob(job,rayDirection(position),position);''',1)
out=root/'validation/experiments/fold-bounds';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(s)
