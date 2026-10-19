"""Pair the cone prepass with ordered, independent intervals for sparse rays."""
from pathlib import Path
import argparse
import shutil
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--parts',type=int,choices=(4,8,16,32,64),default=8)
parser.add_argument('--span',type=float,default=.05)
parser.add_argument('--spacing',choices=('linear','geometric'),default='linear')
parser.add_argument('--pyramid',default='cone-pyramid-4-256')
parser.add_argument('--shell',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments'/args.pyramid
suffix='-geometric' if args.spacing=='geometric' else ''
if args.pyramid!='cone-pyramid-4-256':suffix+='-'+args.pyramid.removeprefix('cone-pyramid-4-256-')
if args.shell:suffix+='-shell'
out=root/f'validation/experiments/cone-segments-{args.parts}-{args.span:g}{suffix}'
out.mkdir(parents=True,exist_ok=True)
shutil.copytree(base/'shaders',out/'shaders',dirs_exist_ok=True)
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
s='#ifndef COOPERATIVE_RAYS\n#define COOPERATIVE_RAYS 0\n#endif\n'+s
s=s.replace('bool marchJob(inout RayJob job,float3 rd,uint3 position) {', '''#if COOPERATIVE_RAYS
groupshared RayJob segmentJobs[64];
groupshared float2 segmentResults[64];
groupshared float4 segmentRefinement[64];
static uint segmentLane;
#endif
bool marchJob(inout RayJob job,float3 rd,uint3 position) {''')
s=s.replace('''    #if DEFER_SURFACE_REFINE
    if(hit) {''','''    #if COOPERATIVE_RAYS
    job.scale=scale;job.t=t;job.previous=previous;job.radius=radius;job.relaxation=relaxation;
    job.first=first;job.accepted=accepted;job.verify=verify;job.derivative=prefix.derivative;job.limit=prefix.limit;
    segmentRefinement[segmentLane]=float4(previous,t,prefix.derivative,float(first));
    segmentResults[segmentLane]=float2(hit?scale:log2(t)+scale,hit?2:escaped?0:accepted>=MARCH_STEPS?-1:-2);
    return !hit && !escaped && accepted<MARCH_STEPS;
    #endif
    #if DEFER_SURFACE_REFINE
    if(hit) {''',1)
parts=args.parts;rays=64//parts
s+=f'''
#if COOPERATIVE_RAYS
[numthreads(64,1,1)]
void segmentRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {{
    uint index=(group.x+group.y*65535)*{rays}+lane/{parts};
    uint part=lane%{parts};segmentLane=lane;
    RayJob original=(RayJob)0,job=(RayJob)0;bool pending=false;
    segmentResults[lane]=float2(0,0);
    if(index<dispatchInput[3]) {{
        original=activeRays[index];job=original;uint3 position=rayPixel(job.index);
        float3 rd=rayDirection(position);
        float begin=original.t*(1+{args.span}*part),end=original.t*(1+{args.span}*(part+1));
        float logBegin=log2(begin)+job.scale;
        // Round the interval end outward. Adjacent intervals must still
        // overlap after conversion through logarithmic camera coordinates.
        float boundary=log2(end)+original.scale;
        job.horizon=min(original.horizon,boundary+max(4e-5,abs(boundary)*2e-7));
        if(part>0) {{
            job.t=job.previous=begin;job.radius=0;job.relaxation=.9;job.verify=0;
            job.first=citadelStart(logBegin);
            RayPrefix prefix=rayPrefix(rd,job.first,job.scale);
            job.derivative=prefix.derivative;job.limit=prefix.limit;
        }}
        if(logBegin<=original.horizon) marchJob(job,rd,position);
        else segmentResults[lane]=float2(logBegin,0);
    }}
    segmentJobs[lane]=job;
    GroupMemoryBarrierWithGroupSync();
    if(part==0 && index<dispatchInput[3]) {{
        uint chosen=lane;
        [unroll] for(uint j=0;j<{parts-1};j++) {{
            if(segmentResults[chosen].y==0) chosen++;
        }}
        job=segmentJobs[chosen];float2 result=segmentResults[chosen];
        job.horizon=original.horizon;
        pending=result.y==-2 || (result.y==0 && result.x<=original.horizon);
        if(pending && job.accepted>=MARCH_STEPS) {{pending=false;result.y=-1;}}
        if(!pending) {{
            uint3 position=rayPixel(job.index);rayOutput[position]=result;
            if(result.y==2) refinementJobs[job.index]=segmentRefinement[chosen];
        }}
    }}
    enqueueGroup(lane,pending,job);
}}
#endif
'''
s=s.replace('''    #if SORT_RAYS
    uint offset=0;''',f'''    uint segmentGroups=(dispatchOutput[3]+{rays-1})/{rays};
    dispatchOutput[4]=min(segmentGroups,65535);
    dispatchOutput[5]=max(1,(segmentGroups+65534)/65535);dispatchOutput[6]=1;
    #if SORT_RAYS
    uint offset=0;''',1)
if args.shell:
    s=s.replace('pixel*.65','pixel*.65065')
    marker='float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);'
    assert s.count(marker)==2
    s=s.replace(marker,marker+'\n        float stepRatio=max(0,(ratio-pixel*.65)/(1+pixel*.65));')
    for previous in ('radius','previousRadius'):
        s=s.replace(previous+'+ratio*relative',previous+'+stepRatio*relative')
        s=s.replace(previous+'-ratio*relative',previous+'-stepRatio*relative')
        s=s.replace(previous+'=ratio;',previous+'=stepRatio;')
    s=s.replace('max(ratio*relaxation,1e-7)','max(stepRatio*relaxation,1e-7)')
source=out/'fractal.hlsl';source.write_text(s,encoding='utf-8')
if args.spacing=='geometric':
    s=s.replace(f'float begin=original.t*(1+{args.span}*part),end=original.t*(1+{args.span}*(part+1));',
        f'float begin=original.t*pow({1+args.span},float(part)),end=original.t*pow({1+args.span},float(part+1));')
    source.write_text(s,encoding='utf-8')
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
entries=[('segmentRays','packetRays'),('prepareRays','prepareRays')]
if args.shell:entries += [('beginRays','beginRays'),('continueRays','continueRays'),('continueRays','finishRays'),('refineRays','refineRays')]
for entry,target in entries:
    command=[fxc,'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges',
        '/D','UNIFORM_FOLDS=1','/D','DEFER_SURFACE_REFINE=1','/D','WORLD_KIND=1',
        '/D',f'COOPERATIVE_RAYS={1 if entry=="segmentRays" else 0}',
        '/D',f'RAY_CHUNK={64 if entry=="beginRays" else 8192 if target=="finishRays" else 256}','/D','CONE_START=1',
        '/Fo',str(out/f'shaders/{target}.dxil'),str(source)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
print(out)
