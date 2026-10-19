"""Screen arithmetic hoisting without lowering the reference precision threshold."""
from pathlib import Path
import argparse, shutil, subprocess, json

p=argparse.ArgumentParser()
p.add_argument('variant',choices=['saturate','sphere-base','combined','reciprocal'])
p.add_argument('--fixtures',nargs='+',default=['edge','heavy','new-slow','new-last'])
a=p.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-threshold-0.001'
out=root/'validation/experiments'/('native-exact-'+a.variant)
out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
path=out/'src/fractal.hlsl';s=path.read_text(encoding='utf-8')
if a.variant=='reciprocal':
    assert s.count('dc/s.q.w')==2
    s=s.replace('dc/s.q.w','dc*s.next.w')
    c=out/'src/citadel.h';t=c.read_text(encoding='utf-8')
    assert t.count('f(s.next,r2)')==1
    t=t.replace('f(s.next,r2)','f(s.next,1.0f/float(s.denom))')
    c.write_text(t,encoding='utf-8')
if a.variant in ('saturate','combined'):
    assert s.count('clamp(dot(q,q),.25,1)')==3
    s=s.replace('clamp(dot(q,q),.25,1)','max(saturate(dot(q,q)),.25)')
    s=s.replace('clamp(dot(p,p),.25,1)','max(saturate(dot(p,p)),.25)')
if a.variant in ('sphere-base','combined'):
    assert s.count('clamp(0,s.y.w,s.z.w)')==2
    s=s.replace('clamp(0,s.y.w,s.z.w)','s.next.w')
    s=s.replace('// y.w/z.w are precomputed signed sphere-boundary distances, not rounded radii.',
        '// y.w/z.w retain signed sphere-boundary distances; next.w is their clamped zero.')
    c=out/'src/citadel.h';t=c.read_text(encoding='utf-8')
    assert t.count('f(s.next,r2)')==1
    t=t.replace('f(s.next,r2)','f(s.next,std::clamp(0.f,float(.25-r2),float(1-r2)))')
    c.write_text(t,encoding='utf-8')
path.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
fixtures={
 'edge':root/'validation/edge-report-2026-10-17/slow-capture/last-flight.aurora',
 'heavy':root/'validation/slow-69ms-fixture/last-flight.aurora',
 'new-slow':root/'validation/optimization-2026-10-17/new-slow.aurora',
 'new-last':root/'validation/optimization-2026-10-17/new-last.aurora',
}
for name in a.fixtures:
    run=out/name;run.mkdir(exist_ok=True);shutil.copy2(fixtures[name],run/'last-flight.aurora')
    result=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--replay','--native-only'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    report=run/'validation/replay/saved-native.json'
    if not report.exists():raise RuntimeError(f'Missing report {run}, exit {result.returncode}')
    data=json.loads(report.read_text());print(a.variant,name,data['after_ms'],'unfinished',data['unfinished'],flush=True)
