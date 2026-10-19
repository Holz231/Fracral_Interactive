"""Change only cooperative-ray queue scheduling, preserving march arithmetic."""
from pathlib import Path
import argparse
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--rays', type=int, choices=(1, 2, 4, 8), default=2)
p.add_argument('--direct', action='store_true')
p.add_argument('--mask', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parent.parent
base = root / 'validation/experiments/cone-segments-32-0.05-geometric-ball-stop1.1'
out = root / f'validation/experiments/segment-schedule-{a.rays}'
if a.direct:
    out = out.with_name(out.name + '-direct')
if a.mask:
    out = out.with_name(out.name + '-mask')
out.mkdir(exist_ok=True)
shutil.copytree(base / 'shaders', out / 'shaders', dirs_exist_ok=True)
s = (base / 'fractal.hlsl').read_text(encoding='utf-8')
if a.rays != 2 and not a.direct:
    raise SystemExit('Different group sizes require direct enqueue')
if a.direct:
    marker = '#if SORT_RAYS\nvoid enqueueGroup('
    assert s.count(marker) == 1
    replacement = '''#if COOPERATIVE_RAYS
void enqueueGroup(uint lane,bool pending,RayJob job) {
    // Only one lane per 32-thread ray can survive. Avoid the 64-lane local
    // histogram and four group barriers for this sparse producer.
    if(pending) {
        uint slot,rank;
        InterlockedAdd(rayCount[0],1,slot);
        InterlockedAdd(rayBuckets[rayBucket(job)],1,rank);
        job.verify=(job.verify&1)|(rank<<1);
        nextRays[slot]=job;
    }
}
#elif SORT_RAYS
void enqueueGroup('''
    s = s.replace(marker, replacement)
size = a.rays * 32
for name in ('segmentJobs','segmentResults','segmentRefinement'):
    s = s.replace(f'{name}[64]', f'{name}[{size}]')
s = s.replace('[numthreads(64,1,1)]\nvoid segmentRays',f'[numthreads({size},1,1)]\nvoid segmentRays')
s = s.replace('uint index=(group.x+group.y*65535)*2+lane/32;',f'uint index=(group.x+group.y*65535)*{a.rays}+lane/32;')
s = s.replace('uint segmentGroups=(dispatchOutput[3]+1)/2;',f'uint segmentGroups=(dispatchOutput[3]+{a.rays-1})/{a.rays};')
if a.mask:
    old='''        uint chosen=lane;
        [unroll] for(uint j=0;j<31;j++) {
            if(segmentResults[chosen].y==0) chosen++;
        }'''
    new='''        uint blocked=0;
        [unroll] for(uint j=0;j<32;j++) {
            blocked|=(segmentResults[lane+j].y!=0)?(1u<<j):0;
        }
        // All-clear rays continue from their final interval. Otherwise the
        // first unresolved/hit interval wins, exactly as in the serial scan.
        uint chosen=lane+min(uint(firstbitlow(blocked)),31u);'''
    assert old in s
    s=s.replace(old,new)
source = out / 'fractal.hlsl'
source.write_text(s, encoding='utf-8')
fxc = 'C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
for entry, target in (('segmentRays','packetRays'),('prepareRays','prepareRays')):
    command = [fxc,'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges',
        '/D','UNIFORM_FOLDS=1','/D','DEFER_SURFACE_REFINE=1','/D','WORLD_KIND=1',
        '/D',f'COOPERATIVE_RAYS={1 if entry=="segmentRays" else 0}',
        '/D','RAY_CHUNK=256','/D','CONE_START=1','/Fo',str(out/f'shaders/{target}.dxil'),str(source)]
    result = subprocess.run(command,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
print(out)
