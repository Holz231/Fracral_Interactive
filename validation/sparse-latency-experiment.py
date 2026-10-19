"""Spread only sparse queues across SMs without per-group histogram barriers."""
from pathlib import Path

root=Path(__file__).resolve().parent.parent
s=(root/'src/fractal.hlsl').read_text(encoding='utf-8')
s=s.replace('    #if SORT_RAYS\n    uint offset=0;', '''    uint lanes=dispatchOutput[3]<2048?1:dispatchOutput[3]<8192?4:8;
    uint sparse=(dispatchOutput[3]+lanes-1)/lanes;
    dispatchOutput[4]=min(sparse,65535);dispatchOutput[5]=max(1,(sparse+65534)/65535);dispatchOutput[6]=1;
    #if SORT_RAYS
    uint offset=0;''')
s+='''
[numthreads(32,1,1)]
void sparseRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {
    uint lanes=dispatchInput[3]<2048?1:dispatchInput[3]<8192?4:8;
    if(lane>=lanes) return;
    uint index=(group.x+group.y*65535)*lanes+lane;
    if(index>=dispatchInput[3]) return;
    RayJob job=activeRays[index];uint3 position=rayPixel(job.index);
    if(marchJob(job,rayDirection(position),position)) {
        uint rank,slot;
        InterlockedAdd(rayBuckets[rayBucket(job)],1,rank);
        InterlockedAdd(rayCount[0],1,slot);
        job.verify=(job.verify&1)|(rank<<1);
        nextRays[slot]=job;
    }
}
'''
out=root/'validation/experiments/sparse-latency'
out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(s,encoding='utf-8')
