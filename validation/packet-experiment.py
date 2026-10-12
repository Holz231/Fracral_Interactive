from pathlib import Path
root=Path(__file__).resolve().parent.parent
source=(root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
source=source.replace('    #if SORT_RAYS\n    uint offset=0;', '''    dispatchOutput[4]=min((dispatchOutput[3]+7)/8,65535);
    dispatchOutput[5]=max(1,((dispatchOutput[3]+7)/8+65534)/65535);dispatchOutput[6]=1;
    #if SORT_RAYS
    uint offset=0;''')
source+=r'''
groupshared RayJob packetJobs[8];
groupshared uint packetState[8];
groupshared float4 packetValues[64];
groupshared float2 packetPrefix[64];
[numthreads(64,1,1)]
void packetRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {
    uint packet=lane/8,part=lane%8;
    uint index=(group.x+group.y*65535)*8+packet;
    RayJob initial=(RayJob)0;
    if(part==0) {
        if(index<dispatchInput[3]) initial=activeRays[index];
        packetJobs[packet]=initial;packetState[packet]=index<dispatchInput[3]?1:0;
    }
    GroupMemoryBarrierWithGroupSync();
    uint3 position=rayPixel(packetJobs[packet].index);
    float3 rd=rayDirection(position);
    float pixel=1/(renderInfo.y*1.85);
    int end=min(MARCH_STEPS,packetJobs[packet].accepted+256);
    [loop] for(int block=0;block<256;block++) {
        if(part==0 && packetState[packet]==1) {
            RayJob j=packetJobs[packet];
            if(j.t>4096) {j.scale+=12;j.t/=4096;j.previous/=4096;j.derivative*=4096;j.limit/=4096;}
            packetJobs[packet]=j;
        }
        GroupMemoryBarrierWithGroupSync();
        RayJob job=packetJobs[packet];
        if(packetState[packet]==1) {
            float t=job.t+part*max(job.radius*job.previous*1.6,job.t*1e-6);
            int first=job.first;RayPrefix prefix=rayPrefix(rd,first,job.scale);
            prefix.derivative=job.derivative;prefix.limit=job.limit;
            if(first>0 && t>=prefix.limit) {
                [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-job.scale,100)));
                prefix=rayPrefix(rd,first,job.scale);
            }
            float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
            packetValues[lane]=float4(t,ratio,prefix.derivative,float(first));
            packetPrefix[lane]=float2(prefix.limit,job.scale);
        }
        GroupMemoryBarrierWithGroupSync();
        if(part==0 && packetState[packet]==1) {
            bool done=false;
            float exitT=exp2(min(job.horizon-job.scale,24));
            [loop] for(uint p=0;p<8;p++) {
                if(job.accepted>=end) break;
                float4 v=packetValues[lane+p];float t=v.x,ratio=v.y;
                float relative=t/job.previous;
                if((p>0 || (job.verify&1)!=0) && job.radius+ratio*relative<(relative-1)*1.00001) {
                    if(p==0) {job.t=job.previous*(1+max(job.radius*.9,1e-7));job.relaxation=1;job.verify=0;}
                    break;
                }
                job.first=int(v.w);job.derivative=v.z;job.limit=packetPrefix[lane+p].x;
                if(t>exitT) {rayOutput[position]=float2(log2(t)+job.scale,0);done=true;break;}
                if(ratio<pixel*.65) {
                    refinementJobs[job.index]=float4(job.previous,t,job.derivative,float(job.first));
                    rayOutput[position]=float2(job.scale,2);done=true;break;
                }
                if(job.radius>0 && t>job.previous) {
                    float slope=(job.radius-ratio*relative)/max(relative-1,1e-7);
                    job.relaxation=clamp(1.85/(1+max(0,slope)),.9,1.85);
                }
                job.previous=t;job.radius=ratio;job.t=t*(1+max(ratio*job.relaxation,1e-7));job.verify=job.relaxation>1;
                job.accepted++;
                if(job.verify==0 && job.t>exitT) {rayOutput[position]=float2(log2(job.t)+job.scale,0);done=true;break;}
            }
            if(!done && job.accepted>=MARCH_STEPS) {rayOutput[position]=float2(log2(job.t)+job.scale,-1);done=true;}
            packetJobs[packet]=job;
            if(done) packetState[packet]=0;
            else if(job.accepted>=end) packetState[packet]=2;
        }
        GroupMemoryBarrierWithGroupSync();
        // Every lane evaluates the same group predicate before this loop exit.
        uint active=0;
        [unroll] for(uint p=0;p<8;p++) active|=packetState[p]==1;
        if(active==0) break;
    }
    RayJob result=packetJobs[packet];
    enqueueGroup(lane,part==0 && packetState[packet]!=0,result);
}
'''
out=root/'validation/experiments/packet-eight';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(source)
