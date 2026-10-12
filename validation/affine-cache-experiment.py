from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
helpers=r'''
struct AffineCache {float3 center,orientation,delta;float multiplier,radius;int first,sourceFirst;};
AffineCache buildAffineCache(RayPrefix prefix,float t,int first) {
    AffineCache c=(AffineCache)0;c.sourceFirst=first;
    float derivative=prefix.derivative*t;
    float3 delta=prefix.basis*derivative;
    float squared=dot(delta,delta);
    float denominator=1+2*dot(prefix.pole,delta)+dot(prefix.pole,prefix.pole)*squared;
    delta=(delta+prefix.pole*squared)/denominator;derivative/=denominator;
    c.delta=delta;
    float3 p=prefix.origin+delta,orientation=1;
    float multiplier=1,radius=1e20;
    bool direct=false;
    int end=min(min(384,counts.x+12),first+8);
    [loop] for(int iteration=first;iteration<end;iteration++) {
        float norm=length(p);
        if(norm>64 || derivative>1e24) break;
        float3 boxMargin=abs(abs(p)-1);
        float margin=min(min(boxMargin.x,boxMargin.y),min(boxMargin.z,64-norm));
        float3 q=2*clamp(p,-1,1)-p;
        float r=length(q);
        if(r>.5 && r<1) break;
        margin=min(margin,min(abs(r-.5),abs(r-1)));
        radius=min(radius,margin*.85/multiplier);
        if(radius<1e-12) break;
        orientation*=abs(p)>1?-1:1;
        float k;
        if(iteration>=counts.x || derivative>renderInfo.y*1.85*.001 || dot(delta,delta)>64) direct=true;
        if(!direct) {
            OrbitSample sample=reference[iteration];
            delta=foldedDeltaVector(sample.p.xyz,sample.q.xyz,delta);
            float change=2*dot(sample.q.xyz,delta)+dot(delta,delta),r2=sample.next.w;
            float dc=clamp(change,.25-r2,1-r2)-clamp(0,.25-r2,1-r2);
            k=2.8/(sample.q.w+dc);
            delta=k*(delta-sample.q.xyz*(dc/sample.q.w));p=sample.next.xyz+delta;
        } else {k=2.8/clamp(dot(q,q),.25,1);p=q*k+fractalParameters.xyz;}
        derivative*=k;multiplier*=k;
        if(dot(p,p)>4096 || derivative>1e24) break;
        if(derivative>renderInfo.y*1.85*.002) {
            c.center=p;c.orientation=orientation;c.multiplier=multiplier;c.first=iteration+1;c.radius=radius;
        }
    }
    return c;
}
float affineCachedDistance(AffineCache c,RayPrefix prefix,float derivative,int first) {
    float3 delta=prefix.basis*derivative;
    float squared=dot(delta,delta);
    float denominator=1+2*dot(prefix.pole,delta)+dot(prefix.pole,prefix.pole)*squared;
    delta=(delta+prefix.pole*squared)/denominator;derivative/=denominator;
    float3 difference=delta-c.delta;
    if(c.radius<=0 || first!=c.sourceFirst || dot(difference,difference)>=c.radius*c.radius) return -1;
    float3 p=c.center+(c.orientation*difference)*c.multiplier;
    derivative*=c.multiplier;
    int end=min(384,counts.x+12);
    if(dot(p,p)>4096 || derivative>1e24) return .45*length(p)/max(derivative,1e-30);
    [loop] for(int iteration=c.first;iteration<end;iteration++) {
        float3 q=2*clamp(p,-1,1)-p;
        float k=2.8/clamp(dot(q,q),.25,1);
        p=q*k+fractalParameters.xyz;derivative*=k;
        if(dot(p,p)>4096 || derivative>1e24) break;
    }
    return .45*length(p)/max(derivative,1e-30);
}
'''
s='#ifndef CACHED_CURVE\n#define CACHED_CURVE 0\n#endif\n'+s
s=s.replace('bool marchJob(', helpers+'\nbool marchJob(',1)
where=s.index('bool marchJob(');prefix,body=s[:where],s[where:]
body=body.replace('    float exitT=exp2(min(job.horizon-scale,24));','''    float exitT=exp2(min(job.horizon-scale,24));
    #if CACHED_CURVE
    AffineCache cache=buildAffineCache(prefix,t,first);
    #endif''',1)
body=body.replace('        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);','''        float ratio=-1;
        #if CACHED_CURVE
        ratio=affineCachedDistance(cache,prefix,prefix.derivative*t,first);
        #endif
        if(ratio<pixel*2) ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);''',1)
out=root/'validation/experiments/affine-cache';out.mkdir(exist_ok=True,parents=True)
(out/'fractal.hlsl').write_text(prefix+body)
