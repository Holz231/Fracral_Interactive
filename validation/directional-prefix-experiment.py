from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
marker='int citadelStart(float radiusLog) {'
s=s.replace(marker,'''RWTexture2DArray<float> coneLimitsOut:register(u6);
Texture2DArray<float> coneLimits:register(t5);
static uint2 prefixTile=uint2(0,0);
float directionalLimit(int i) {return coneLimits.Load(int4(prefixTile,i,0));}
float positiveRoot(float a,float b,float c) {
    float root=1e30;
    if(abs(a)<1e-25) {
        if(abs(b)>1e-25 && -c/b>0) root=-c/b;
    } else {
        float disc=b*b-4*a*c;
        if(disc>=0) {
            float q=-.5*(b+(b>=0?1:-1)*sqrt(disc));
            float x=q/a,y=abs(q)>1e-30?c/q:1e30;
            if(x>0) root=min(root,x);
            if(y>0) root=min(root,y);
        }
    }
    return root;
}
float planeLimit(float3 p,float3 v,float3 pole,int axis,float boundary,float spread) {
    float c=p[axis]-boundary;
    float3 coefficient=2*c*pole;coefficient[axis]+=1;
    float b=dot(coefficient,v)-(c>=0?1:-1)*length(coefficient)*spread;
    float a=c*dot(pole,pole)+pole[axis];
    return positiveRoot(a,b,c);
}
float sphereLimit(float3 p,float3 v,float3 pole,float radius,float spread) {
    float c=dot(p,p)-radius*radius;
    float3 coefficient=2*(c*pole+p);
    float b=dot(coefficient,v)-(c>=0?1:-1)*length(coefficient)*spread;
    float a=c*dot(pole,pole)+2*dot(p,pole)+1;
    return positiveRoot(a,b,c);
}
[numthreads(8,8,1)]
void prefixCones(uint3 id:SV_DispatchThreadID) {
    uint2 size=(uint2(renderInfo.xy)+15)/16;
    if(any(id.xy>=size)) return;
    float2 center=float2(id.xy)*16+8;
    float2 uv=(center*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float spread=1.414214*16/(renderInfo.y*1.85)+2e-6;
    float limit=1024;
    [loop] for(int i=0;i<counts.x;i++) {
        OrbitSample r=reference[i];
        coneLimitsOut[uint3(id.xy,i)]=max(limit,r.curve.w);
        float3 p=r.p.xyz,pole=r.curve.xyz;
        float3 v=r.x.xyz*rd.x+r.y.xyz*rd.y+r.z.xyz*rd.z;
        float bound=1e30;
        [unroll] for(int axis=0;axis<3;axis++) {
            if(p[axis]>=-1) bound=min(bound,planeLimit(p,v,pole,axis,1,spread));
            if(p[axis]<=1) bound=min(bound,planeLimit(p,v,pole,axis,-1,spread));
        }
        // Sphere branches apply to the BOX-FOLDED point, not p itself.
        // Transform orientation and pole by the unchanged box reflection.
        float3 sign=float3(abs(p.x)>1?-1:1,abs(p.y)>1?-1:1,abs(p.z)>1?-1:1);
        float3 q=r.q.xyz;float squared=dot(q,q);
        if(squared<=1) bound=min(bound,sphereLimit(q,v*sign,pole*sign,.5,spread));
        if(squared>=.25) bound=min(bound,sphereLimit(q,v*sign,pole*sign,1,spread));
        bound=min(bound,sphereLimit(p,v,pole,64,spread));
        limit=min(limit,log2(max(bound*.85,1e-30))-r.p.w);
    }
}
'''+marker)
s=s.replace('radiusLog<reference[mid].curve.w','radiusLog<directionalLimit(mid)')
s=s.replace('return reference[index].curve.w;', 'return directionalLimit(index);')
s=s.replace('float3 rd=rayDirection(id);job.index=', 'prefixTile=id.xy/16;float3 rd=rayDirection(id);job.index=')
s=s.replace('job=activeRays[index];uint3 position=rayPixel(job.index);', 'job=activeRays[index];uint3 position=rayPixel(job.index);prefixTile=position.xy/16;')
s=s.replace('uint index=position.x+uint(renderInfo.x)*position.y;', 'prefixTile=position.xy/16;uint index=position.x+uint(renderInfo.x)*position.y;')
out=root/'validation/experiments/directional-prefix';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(s,encoding='utf-8')
