from pathlib import Path
root=Path(__file__).resolve().parent.parent
base=(root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
old=(root/'validation/experiments/segment-mobius/fractal.hlsl').read_text()
helpers=old[old.index('struct RayCurve'):old.index('[numthreads(64,1,1)]\nvoid skipRays')]
helpers=helpers[:helpers.index('float mobiusClearStep')]+helpers[helpers.index('float mobiusClearStep'):].replace(
    'float mobiusClearStep(float3 rd,float start,float scale,float maximum,float pixel) {',
    '''struct CachedCurve {float3 n0,n1,n2,w;float derivative,anchor,upper;int first;};
CachedCurve buildCachedCurve(float3 rd,float start,float scale) {
    CachedCurve cache=(CachedCurve)0;cache.anchor=start;
    float maximum=.125,pixel=1/(renderInfo.y*1.85);''',1)
helpers=helpers.replace('return 0;', 'return cache;')
start=helpers.index('        if((iteration>first || first>0) &&')
end=helpers.index('        float3 centerPoint',start)
helpers=helpers[:start]+'''        if((iteration>first || first>0) && (norm.x>4096*c.w.x || c.derivative>1e24*c.w.x) || iteration==end) return cache;
        if(iteration>first && c.derivative/c.w.x>renderInfo.y*1.85*.001 && upper>.004) {
            cache.n0=base*c.w.x+c.n0;cache.n1=base*c.w.y+c.n1;cache.n2=base*c.w.z+c.n2;
            cache.w=c.w;cache.derivative=c.derivative;cache.first=iteration;cache.upper=upper*.95;
        }
        if(upper<.004) return cache;
''' +helpers[end:]
helpers+=r'''
float cachedDistance(CachedCurve c,float t) {
    float s=t/c.anchor-1;
    float denominator=c.w.x+s*(c.w.y+s*c.w.z);
    float3 p=(c.n0+s*(c.n1+s*c.n2))/denominator;
    float derivative=c.derivative*(1+s)/denominator;
    int end=min(384,counts.x+12);
    [loop] for(int iteration=c.first;iteration<end;iteration++) {
        float3 q=2*clamp(p,-1,1)-p;
        float k=2.8/clamp(dot(q,q),.25,1);
        p=q*k+fractalParameters.xyz;derivative*=k;
        if(dot(p,p)>4096 || derivative>1e24) break;
    }
    return .45*length(p)/max(derivative,1e-30);
}
'''
base='#ifndef CACHED_CURVE\n#define CACHED_CURVE 0\n#endif\n'+base
base=base.replace('bool marchJob(', helpers+'\nbool marchJob(',1)
where=base.index('bool marchJob(')
prefix,body=base[:where],base[where:]
body=body.replace('    float exitT=exp2(min(job.horizon-scale,24));','''    float exitT=exp2(min(job.horizon-scale,24));
    #if CACHED_CURVE
    CachedCurve cache=buildCachedCurve(rd,t,scale);
    #endif''',1)
body=body.replace('            scale+=12;t/=4096;', '''            #if CACHED_CURVE
            cache.anchor/=4096;
            #endif
            scale+=12;t/=4096;''',1)
body=body.replace('        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);', '''        float ratio;
        #if CACHED_CURVE
        float relativeCache=t/cache.anchor-1;
        if(cache.upper>0 && relativeCache>=0 && relativeCache<cache.upper) {
            ratio=cachedDistance(cache,t);
            if(ratio<pixel*2) ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        } else
        #endif
        ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);''',1)
out=root/'validation/experiments/cached-ray';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(prefix+body)
