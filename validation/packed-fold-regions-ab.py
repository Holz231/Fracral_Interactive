"""Preclassify the reference box-fold regions without changing float math."""
from pathlib import Path
import argparse,subprocess,shutil,csv,json,statistics
p=argparse.ArgumentParser();p.add_argument('--fixtures',nargs='+',default=['edge','heavy']);a=p.parse_args()
root=Path(__file__).resolve().parent.parent;base=root/'validation/experiments/native-exact-ab'
fixed=root/'validation/experiments/native-edge-fixed'
out=root/'validation/experiments/native-packed-fold-regions';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copytree(fixed/'tests',out/'tests',dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:];s=s.replace('EXACT_FOLD_OPT','PACKED_FOLD_REGIONS')
key='// Distance and offset use the same scale.'
helper='''float3 foldedDeltaPacked(OrbitSample s,float3 delta) {
    float3 p=s.p.xyz+delta;
    uint3 previous=(uint(s.next.w)>>uint3(0,2,4))&3;
    uint3 current=uint3(p>1)|(uint3(p<-1)<<1);
    bool3 unchanged=previous==current;
    return unchanged?(current==0?delta:-delta):2*clamp(p,-1,1)-p-s.q.xyz;
}
'''
assert s.count(key)==1;s=s.replace(key,helper+key,1)
key='        delta=foldedDeltaVector(s.p.xyz,s.q.xyz,delta);';assert s.count(key)==1
s=s.replace(key,'''        #if PACKED_FOLD_REGIONS
        delta=foldedDeltaPacked(s,delta);
        #else
'''+key+'\n        #endif',1)
p.write_text(s,encoding='utf-8')
p=out/'src/citadel.h';s=(fixed/'src/citadel.h').read_text(encoding='utf-8')
key='f(s.next,r2)';assert s.count(key)==1
s=s.replace(key,'f(s.next,region(float(s.p.x))|(region(float(s.p.y))<<2)|(region(float(s.p.z))<<4))',1)
key='    std::array<GpuSample,capacity> gpu() const {';assert s.count(key)==1
s=s.replace(key,key+'''
        // Classify the rounded GPU value, matching the original shader.
        auto region=[](float v)->unsigned {return v>1?1:v<-1?2:0;};''',1)
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8').replace('"EXACT_FOLD_OPT"','"PACKED_FOLD_REGIONS"');p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in a.fixtures:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab'
    if not (folder/'comparison.json').exists():raise RuntimeError((run/'aurora-error.txt').read_text())
    report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('packed-regions',fixture,'exit',proc.returncode,'ms',ms,report,flush=True)
