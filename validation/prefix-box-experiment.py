from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
helpers=r'''
float boundRoot(float3 p) {
    float bound=1e20;
    if(abs(p.z)<1e-20) {if(p.y<0) bound=-p.x/p.y;return bound;}
    float discriminant=p.y*p.y-4*p.z*p.x;
    if(discriminant<0) return bound;
    float q=-.5*(p.y+(p.y>=0?1:-1)*sqrt(discriminant));
    float a=q/p.z,b=q!=0?p.x/q:1e20;
    if(a>=0) bound=min(bound,a);if(b>=0) bound=min(bound,b);return bound;
}
float prefixBoxSkip(RayPrefix prefix,float t,float pixel) {
    float d=prefix.derivative*t;
    if(d<1e-9 || d>1e9) return 0;
    float3 w=float3(1,2*dot(prefix.pole,prefix.basis)*d,dot(prefix.pole,prefix.pole)*d*d);
    float3 high=(2*2.8*(1+2.8)+fractalParameters.xyz*(2.8-1))/(2.8*2.8-1);
    float3 low=2*2.8+fractalParameters.xyz-high*2.8;
    float skip=0;
    [unroll] for(int axis=0;axis<3;axis++) {
        float3 n=float3(prefix.origin[axis],prefix.origin[axis]*w.y+prefix.basis[axis]*d,prefix.origin[axis]*w.z+prefix.pole[axis]*d*d);
        [unroll] for(int side=0;side<2;side++) {
            float3 excess=side==0?low[axis]*w-n:n-high[axis]*w;
            excess.y-=pixel*.70/.45*d;
            float3 local=float3(excess.x+excess.y+excess.z,excess.y+2*excess.z,excess.z);
            float error=dot(abs(excess),float3(1,1,1))*2e-5+1e-15;
            if(local.x>error) {
                local.x-=error;
                skip=max(skip,boundRoot(local)*.98);
            }
        }
    }
    return min(skip,max(0,prefix.limit/t-1)*.98);
}
'''
s='#ifndef PREFIX_BOX_SKIP\n#define PREFIX_BOX_SKIP 0\n#endif\n'+s
s=s.replace('bool marchJob(',helpers+'\nbool marchJob(',1)
where=s.index('bool marchJob(')
prefix,body=s[:where],s[where:]
body=body.replace('    float exitT=exp2(min(job.horizon-scale,24));','''    float exitT=exp2(min(job.horizon-scale,24));
    #if PREFIX_BOX_SKIP
    float skip=prefixBoxSkip(prefix,previous,pixel);
    float next=previous*(1+skip);
    if(skip>.01 && next>t) {
        t=min(next,exitT);previous=t;radius=0;relaxation=.9;verify=false;
    }
    #endif''',1)
# Keep the ordinary marcher and its accepted-step budget after the proof.
out=root/'validation/experiments/prefix-box';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(prefix+body,encoding='utf-8')
