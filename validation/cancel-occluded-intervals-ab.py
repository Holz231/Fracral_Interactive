"""Cancel only parallel intervals strictly behind an already found hit."""
from pathlib import Path
import argparse,subprocess,shutil,csv,json,statistics
p=argparse.ArgumentParser();p.add_argument('cadence',type=int,choices=[1,4,8,16,32,64],default=16,nargs='?');a=p.parse_args()
root=Path(__file__).resolve().parent.parent;base=root/'validation/experiments/native-exact-ab'
out=root/f'validation/experiments/native-cancel-intervals-{a.cadence}';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:];s=s.replace('EXACT_FOLD_OPT','SEGMENT_CANCEL')
s=s.replace('groupshared RayJob segmentJobs[32];','''#if SEGMENT_CANCEL
groupshared uint segmentCutoff;
#endif
groupshared RayJob segmentJobs[32];''',1)
start=s.index('bool marchJob(');end=s.index('groupshared uint pendingCount',start);part=s[start:end]
key='    [loop] for(;accepted<end;accepted++) {\n'
assert part.count(key)==1
part=part.replace(key,key+f'''        #if COOPERATIVE_RAYS && SEGMENT_CANCEL
        if((accepted&{a.cadence-1})==0) {{
            // Atomic reads may see an earlier (larger) cutoff, which only
            // delays cancellation. A smaller cutoff always names a real hit.
            uint cutoff;InterlockedAdd(segmentCutoff,0,cutoff);
            if(segmentLane>cutoff) break;
        }}
        #endif
''',1)
key='        if(ratio<pixel*.65) {\n';assert part.count(key)==1
part=part.replace(key,key+'''            #if COOPERATIVE_RAYS && SEGMENT_CANCEL
            // Publish inside the loop, before divergent lanes reconverge.
            // Earlier intervals still finish; no nearer surface is discarded.
            InterlockedMin(segmentCutoff,segmentLane);
            #endif
''',1)
s=s[:start]+part+s[end:]
key='void segmentRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {\n';assert s.count(key)==1
s=s.replace(key,key+'''    #if SEGMENT_CANCEL
    if(lane==0) segmentCutoff=32;
    GroupMemoryBarrierWithGroupSync();
    #endif
''',1)
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8').replace('"EXACT_FOLD_OPT"','"SEGMENT_CANCEL"');p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in ['edge','heavy','new-slow','new-last']:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab';report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('cancel',a.cadence,fixture,'exit',proc.returncode,'ms',ms,report,flush=True)
