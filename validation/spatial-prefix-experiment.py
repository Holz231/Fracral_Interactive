from pathlib import Path
root=Path(__file__).resolve().parent.parent
base=root/'backup-2026-10-11-cooperative/src'
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
s='#ifndef SPATIAL_SORT\n#define SPATIAL_SORT 0\n#endif\n'+s
s=s.replace('''groupshared uint groupBuckets[128],groupOffsets[128];''','''#if SPATIAL_SORT
groupshared uint pendingBuckets[64],pendingOffsets[64],scanTotals[128];
#else
groupshared uint groupBuckets[128],groupOffsets[128];
#endif''')
s=s.replace('''    return min(127,uint(job.first));''','''    #if SPATIAL_SORT
    uint3 pixel=rayPixel(job.index);
    uint2 tile=min(uint2(7,7),pixel.xy*8/uint2(renderInfo.xy));
    return min(127,uint(job.first))*64+tile.y*8+tile.x;
    #else
    return min(127,uint(job.first));
    #endif''')
start=s.index('#if SORT_RAYS\nvoid enqueueGroup')
s=s[:start]+s[start:].replace('#if SORT_RAYS\nvoid enqueueGroup',r'''#if SORT_RAYS && SPATIAL_SORT
void enqueueGroup(uint lane,bool pending,RayJob job) {
    if(lane==0) pendingCount=0;
    GroupMemoryBarrierWithGroupSync();
    if(pending) {uint slot;InterlockedAdd(pendingCount,1,slot);pendingRays[slot]=job;}
    GroupMemoryBarrierWithGroupSync();
    RayJob pendingJob=(RayJob)0;
    if(lane<pendingCount) {pendingJob=pendingRays[lane];pendingBuckets[lane]=rayBucket(pendingJob);}
    GroupMemoryBarrierWithGroupSync();
    uint rank=0,total=0,leader=lane,bucket=0;
    if(lane<pendingCount) {
        bucket=pendingBuckets[lane];
        [loop] for(uint i=0;i<pendingCount;i++) {
            bool equal=pendingBuckets[i]==bucket;
            if(equal) {total++;if(i<lane) rank++;leader=min(leader,i);}
        }
        if(rank==0) InterlockedAdd(rayBuckets[bucket],total,pendingOffsets[lane]);
    }
    if(lane==0) InterlockedAdd(rayCount[0],pendingCount,pendingBase);
    GroupMemoryBarrierWithGroupSync();
    if(lane<pendingCount) {
        pendingJob.verify=(pendingJob.verify&1)|((rank+pendingOffsets[leader])<<1);
        nextRays[pendingBase+lane]=pendingJob;
    }
}
#elif SORT_RAYS
void enqueueGroup''',1)
start=s.index('[numthreads(1,1,1)]\nvoid prepareRays')
end=s.index('[numthreads(64,1,1)]\nvoid sortRays',start)
old=s[start:end]
s=s[:start]+r'''#if SPATIAL_SORT
[numthreads(128,1,1)]
void prepareRays(uint lane:SV_GroupIndex) {
    if(lane==0) {
        uint groups=(dispatchOutput[3]+63)/64;
        dispatchOutput[0]=min(groups,65535);dispatchOutput[1]=max(1,(groups+65534)/65535);dispatchOutput[2]=1;
    }
    uint begin=lane*64,sum=0;
    [loop] for(uint i=0;i<64;i++) {uint n=rayBuckets[begin+i];rayBuckets[begin+i]=sum;sum+=n;}
    scanTotals[lane]=sum;
    GroupMemoryBarrierWithGroupSync();
    if(lane==0) {
        uint total=0;
        [loop] for(uint i=0;i<128;i++) {uint n=scanTotals[i];scanTotals[i]=total;total+=n;}
    }
    GroupMemoryBarrierWithGroupSync();
    uint base=scanTotals[lane];
    [loop] for(uint i=0;i<64;i++) rayBuckets[begin+i]+=base;
}
#else
'''+old+'#endif\n'+s[end:]
(root/'src/fractal.hlsl').write_text(s,encoding='utf-8')
(root/'src/renderer.h').write_text((base/'renderer.h').read_text(encoding='utf-8'),encoding='utf-8')
s=(base/'renderer.cpp').read_text(encoding='utf-8').replace('{"DEFER_SURFACE_REFINE","1"},{nullptr,nullptr}', '{"DEFER_SURFACE_REFINE","1"},{"SPATIAL_SORT","1"},{nullptr,nullptr}').replace('d.ByteWidth=128*4;u.Buffer.NumElements=s.Buffer.NumElements=128;','d.ByteWidth=8192*4;u.Buffer.NumElements=s.Buffer.NumElements=8192;')
(root/'src/renderer.cpp').write_text(s,encoding='utf-8')
