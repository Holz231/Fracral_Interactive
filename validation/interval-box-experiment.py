from pathlib import Path
root=Path(__file__).resolve().parent.parent
base=root/'backup-2026-10-11-cooperative/src'
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
extra=r'''
float3 intervalMinimumAbs(float3 low,float3 high) {
    return max(max(low,-high),0);
}
float3 intervalMaximumAbs(float3 low,float3 high) {
    return max(abs(low),abs(high));
}
void multiplyInterval(inout float3 low,inout float3 high,float a,float b) {
    float3 newLow=min(low*a,low*b),newHigh=max(high*a,high*b);
    low=newLow;high=newHigh;
}
bool emptyInterval(float3 rd,float start,float scale,float span,float pixel) {
    int first=citadelStart(log2(start*(1+span))+scale);
    RayPrefix prefix=rayPrefix(rd,first,scale);
    float d=prefix.derivative*start,d2=d*d,r=1+span;
    float3 lo=prefix.basis*d,hi=lo*r;
    float3 lower=min(lo,hi),upper=max(lo,hi);
    lo=prefix.pole*d2;hi=lo*r*r;lower+=min(lo,hi);upper+=max(lo,hi);
    float a=dot(prefix.pole,prefix.pole)*d2,b=2*dot(prefix.pole,prefix.basis)*d;
    float w0=1+b+a,w1=1+b*r+a*r*r;
    float wLow=min(w0,w1),wHigh=max(w0,w1);
    if(a>0) {float at=clamp(-b/(2*a),1,r);wLow=min(wLow,1+b*at+a*at*at);}
    float wError=(1+abs(b)*r+a*r*r)*4e-6;wLow-=wError;wHigh+=wError;
    if(wLow<=0 || d<1e-12 || d>1e12) return false;
    multiplyInterval(lower,upper,1/wHigh,1/wLow);
    lower+=prefix.origin;upper+=prefix.origin;
    float derivative=d*r/wLow,escapeBound=1e20;
    int end=min(384,counts.x+12);
    [loop] for(int iteration=first;iteration<=end;iteration++) {
        float3 margin=(intervalMaximumAbs(lower,upper)+1)*2e-6;
        lower-=margin;upper+=margin;derivative*=1.000002;
        float3 nearPoint=intervalMinimumAbs(lower,upper),farPoint=intervalMaximumAbs(lower,upper);
        float nearSquared=dot(nearPoint,nearPoint),farSquared=dot(farPoint,farPoint);
        if(iteration>first || first>0) {
            if(derivative>1e24) return false;
            if(farSquared>4096) escapeBound=min(escapeBound,28.8/max(derivative,1e-30));
            if(escapeBound<pixel*.7) return false;
            if(nearSquared>4096 || iteration==end)
                return min(escapeBound,.45*sqrt(nearSquared)/max(derivative,1e-30))>pixel*.7;
        }
        if(iteration==end) return false;
        float3 foldedLow=2*clamp(lower,-1,1)-lower,foldedHigh=2*clamp(upper,-1,1)-upper;
        float3 qLow=min(foldedLow,foldedHigh),qHigh=max(foldedLow,foldedHigh);
        qLow=(lower<=-1 && upper>=-1)?min(qLow,-1):qLow;
        qHigh=(lower<=1 && upper>=1)?max(qHigh,1):qHigh;
        nearPoint=intervalMinimumAbs(qLow,qHigh);farPoint=intervalMaximumAbs(qLow,qHigh);
        float kLow=2.8/clamp(dot(farPoint,farPoint),.25,1),kHigh=2.8/clamp(dot(nearPoint,nearPoint),.25,1);
        multiplyInterval(qLow,qHigh,kLow,kHigh);
        lower=qLow+fractalParameters.xyz;upper=qHigh+fractalParameters.xyz;derivative*=kHigh;
    }
    return false;
}
[numthreads(64,1,1)]
void skipRays(uint3 id:SV_DispatchThreadID) {
    uint index=id.x+id.y*(65535*64);if(index>=dispatchInput[3]) return;
    RayJob job=nextRays[index];float3 rd=rayDirection(rayPixel(job.index));
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
        nextRays[index]=job;
    }
}
'''
s=s.replace('[numthreads(8,8,1)]\nvoid refineRays',extra+'\n[numthreads(8,8,1)]\nvoid refineRays')
(root/'src/fractal.hlsl').write_text(s,encoding='utf-8')
s=(base/'renderer.h').read_text(encoding='utf-8').replace('ComPtr<ID3D11ComputeShader> raySort;','ComPtr<ID3D11ComputeShader> raySort,raySkip;')
(root/'src/renderer.h').write_text(s,encoding='utf-8')
s=(base/'renderer.cpp').read_text(encoding='utf-8').replace('        if(!rayPrepare) {','''        if(!rayPrepare) {
            auto skip=compileShader("skipRays","cs_5_0",macros);
            check(device->CreateComputeShader(skip->GetBufferPointer(),skip->GetBufferSize(),nullptr,&raySkip),"Create interval proof shader");''',1)
s=s.replace('''        context->CSSetShader(raySort.Get(),nullptr,0);context->DispatchIndirect(dispatchBuffer.Get(),0);''','''        context->CSSetShader(raySort.Get(),nullptr,0);context->DispatchIndirect(dispatchBuffer.Get(),0);
        if(batch>=2) {context->CSSetShader(raySkip.Get(),nullptr,0);context->DispatchIndirect(dispatchBuffer.Get(),0);}''',1)
(root/'src/renderer.cpp').write_text(s,encoding='utf-8')
