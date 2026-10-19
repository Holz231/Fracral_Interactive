from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
body=s[s.index('bool marchJob('):s.index('groupshared uint pendingCount')]
begin=body.index('    float exitT=')
end=body.index('    #if DEFER_SURFACE_REFINE\n    if(hit)')
loop=body[begin:end]
loop=loop.replace('    float exitT=exp2(min(job.horizon-scale,24));\n','')
loop=loop.replace('    [loop] for(;accepted<end;accepted++) {','''    [loop] while(true) {
        if(loadJob) {
            if(index>=total) break;
            job=activeRays[index];position=rayPixel(job.index);rd=rayDirection(position);
            scale=job.scale;t=job.t;previous=job.previous;radius=job.radius;relaxation=job.relaxation;
            first=job.first;accepted=job.accepted;verify=(job.verify&1)!=0;
            prefix=rayPrefix(rd,first,scale);prefix.derivative=job.derivative;prefix.limit=job.limit;
            exitT=exp2(min(job.horizon-scale,24));loadJob=false;hit=false;escaped=false;
        }
        accepted++;''')
loop=loop.replace('if(t>exitT) {escaped=true;break;}', 'if(t>exitT) escaped=true;')
loop=loop.replace('if(ratio<pixel*.65) {','if(!escaped && ratio<pixel*.65) {')
loop=loop.replace('hit=true;break;','hit=true;')
loop=loop.replace('        if(radius>0 && t>previous) {','''        if(hit || escaped) {
            if(hit) {
                refinementJobs[job.index]=float4(previous,t,prefix.derivative,float(first));
                rayOutput[position]=float2(scale,2);
            } else rayOutput[position]=float2(log2(t)+scale,0);
            InterlockedAdd(rayCount[0],1,index);index+=WORKER_COUNT;loadJob=true;continue;
        }
        if(radius>0 && t>previous) {''')
loop=loop.replace('if(!verify && t>exitT) {escaped=true;break;}','''if(!verify && t>exitT) escaped=true;
        if(escaped || accepted>=MARCH_STEPS) {
            rayOutput[position]=float2(log2(t)+scale,escaped?0:-1);
            InterlockedAdd(rayCount[0],1,index);index+=WORKER_COUNT;loadJob=true;
        }''')
head='''
#ifndef WORKER_COUNT
#define WORKER_COUNT 32768
#endif
[numthreads(64,1,1)]
void persistRays(uint3 id:SV_DispatchThreadID) {
    uint index=id.x,total=dispatchInput[3];
    RayJob job=(RayJob)0;uint3 position=0;float3 rd=0;
    float pixel=1.0/(renderInfo.y*1.85);
    float scale=0,t=0,previous=0,radius=0,relaxation=0,exitT=0;
    int first=0,accepted=0;
    bool loadJob=true,verify=false,hit=false,escaped=false;
    RayPrefix prefix=(RayPrefix)0;
'''
s=s.replace('[numthreads(1,1,1)]\nvoid prepareRays',head+loop+'}\n[numthreads(1,1,1)]\nvoid prepareRays')
out=root/'validation/experiments/persistent-flat';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(s,encoding='utf-8')
