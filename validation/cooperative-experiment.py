from pathlib import Path

root = Path(__file__).resolve().parent.parent
base = root / 'backup-2026-10-11-cooperative/src'
s = (base/'fractal.hlsl').read_text(encoding='utf-8')
s = '#ifndef COOPERATIVE_RAYS\n#define COOPERATIVE_RAYS 0\n#endif\n' + s
s = s.replace('bool marchJob(inout RayJob job,float3 rd,uint3 position) {', '''#if COOPERATIVE_RAYS
groupshared RayJob segmentJobs[64];
groupshared float2 segmentResults[64];
groupshared float4 segmentRefinement[64];
static uint segmentLane;
#endif
bool marchJob(inout RayJob job,float3 rd,uint3 position) {''')
s = s.replace('''    #if DEFER_SURFACE_REFINE
    if(hit) {''', '''    #if COOPERATIVE_RAYS
    job.scale=scale;job.t=t;job.previous=previous;job.radius=radius;job.relaxation=relaxation;
    job.first=first;job.accepted=accepted;job.verify=verify;job.derivative=prefix.derivative;job.limit=prefix.limit;
    segmentRefinement[segmentLane]=float4(previous,t,prefix.derivative,float(first));
    segmentResults[segmentLane]=float2(hit?scale:log2(t)+scale,hit?2:escaped?0:accepted>=MARCH_STEPS?-1:-2);
    return !hit && !escaped && accepted<MARCH_STEPS;
    #endif
    #if DEFER_SURFACE_REFINE
    if(hit) {''')
start = s.index('[numthreads(64,1,1)]\nvoid continueRays')
end = s.index('[numthreads(1,1,1)]\nvoid prepareRays', start)
old = s[start:end]
new = '''#if COOPERATIVE_RAYS
[numthreads(64,1,1)]
void continueRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {
    uint index=(group.x+group.y*65535)*8+lane/8;
    uint part=lane%8;segmentLane=lane;
    RayJob original=(RayJob)0,job=(RayJob)0;bool pending=false;
    segmentResults[lane]=float2(0,0);
    if(index<dispatchInput[3]) {
        original=activeRays[index];job=original;uint3 position=rayPixel(job.index);
        float3 rd=rayDirection(position);
        float begin=original.t*(1+.05*part),end=original.t*(1+.05*(part+1));
        job.horizon=min(original.horizon,log2(end)+original.scale);
        if(part>0) {
            job.t=job.previous=begin;job.radius=0;job.relaxation=.9;job.verify=0;
            job.first=citadelStart(log2(begin)+job.scale);
            RayPrefix prefix=rayPrefix(rd,job.first,job.scale);
            job.derivative=prefix.derivative;job.limit=prefix.limit;
        }
        marchJob(job,rd,position);
    }
    segmentJobs[lane]=job;
    GroupMemoryBarrierWithGroupSync();
    if(part==0 && index<dispatchInput[3]) {
        uint chosen=lane;
        [unroll] for(uint j=0;j<7;j++) {
            if(segmentResults[chosen].y==0) chosen++;
        }
        job=segmentJobs[chosen];float2 result=segmentResults[chosen];
        job.horizon=original.horizon;
        pending=result.y==-2 || (result.y==0 && result.x<=original.horizon);
        if(pending && job.accepted>=MARCH_STEPS) {pending=false;result.y=-1;}
        if(!pending) {
            uint3 position=rayPixel(job.index);rayOutput[position]=result;
            if(result.y==2) refinementJobs[job.index]=segmentRefinement[chosen];
        }
    }
    enqueueGroup(lane,pending,job);
}
#else
''' + old + '#endif\n'
s = s[:start]+new+s[end:]
s = s.replace('''    #if SORT_RAYS
    uint offset=0;''', '''    dispatchOutput[4]=min((dispatchOutput[3]+7)/8,65535);
    dispatchOutput[5]=max(1,((dispatchOutput[3]+7)/8+65534)/65535);dispatchOutput[6]=1;
    #if SORT_RAYS
    uint offset=0;''')
(root/'src/fractal.hlsl').write_text(s,encoding='utf-8')
s = (base/'renderer.h').read_text(encoding='utf-8').replace('rayBegin,rayContinue,rayFinish,rayRefine;', 'rayBegin,rayContinue,rayFinish,rayRefine,rayCooperative;')
(root/'src/renderer.h').write_text(s,encoding='utf-8')
s = (base/'renderer.cpp').read_text(encoding='utf-8')
s = s.replace('{"DEFER_SURFACE_REFINE","1"},{nullptr,nullptr}', '{"DEFER_SURFACE_REFINE","1"},{"COOPERATIVE_RAYS","0"},{nullptr,nullptr}')
s = s.replace('''        macros[3].Definition="8192";auto finish''', '''        macros[7].Definition="1";
        auto cooperative=compileShader("continueRays","cs_5_0",macros);
        check(device->CreateComputeShader(cooperative->GetBufferPointer(),cooperative->GetBufferSize(),nullptr,&rayCooperative[profile]),"Create cooperative tracer");
        macros[7].Definition="0";
        macros[3].Definition="8192";auto finish''')
s = s.replace('d.ByteWidth=16;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;', 'd.ByteWidth=32;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;')
s = s.replace('u.Buffer.NumElements=4;', 'u.Buffer.NumElements=8;').replace('s.Buffer.NumElements=4;', 's.Buffer.NumElements=8;')
s = s.replace('''context->CSSetShader((batch==rayBatches-1?rayFinish:rayContinue)[profile].Get(),nullptr,0);
        context->DispatchIndirect(dispatchBuffer.Get(),0);''', '''context->CSSetShader((batch==rayBatches-1?rayFinish:batch>=2?rayCooperative:rayContinue)[profile].Get(),nullptr,0);
        context->DispatchIndirect(dispatchBuffer.Get(),batch>=2 && batch<rayBatches-1?16:0);''')
(root/'src/renderer.cpp').write_text(s,encoding='utf-8')
