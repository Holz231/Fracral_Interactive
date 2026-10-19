"""Render a diagnostic field variant at the captured corner, without installing it."""
from pathlib import Path
import argparse,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('variant',choices=['baseline','no-prefix','no-cache','precise-planes','late-direct','sphere-gaps']);args=p.parse_args()
root=Path(__file__).resolve().parent.parent
project=root/'validation/experiments/native-edge-diagnostic'
source=root/'validation/experiments/field-unroll-2/fractal.hlsl'
cpu=root/'validation/baselines/preview-2026-10-17-0803/Source/src/citadel.h'
shader=source.read_text(encoding='utf-8')
if args.variant=='no-prefix':shader=shader.replace('struct OrbitSample','\n#undef FAST_CITADEL\n#define FAST_CITADEL 0\nstruct OrbitSample',1)
if args.variant=='no-cache':shader=shader.replace('struct OrbitSample','\n#undef CACHE_PREFIX\n#define CACHE_PREFIX 0\nstruct OrbitSample',1)
if args.variant=='late-direct':shader=shader.replace('derivative>renderInfo.y*1.85*.001','derivative>renderInfo.y*1.85*100')
if args.variant=='precise-planes':
    shader=(root/'validation/experiments/native-tuned/src/fractal.hlsl').read_text(encoding='utf-8')
    cpu=root/'validation/experiments/native-tuned/src/citadel.h'
cpu_text=cpu.read_text(encoding='utf-8')
if args.variant=='sphere-gaps':
    shader=shader.replace('.25-r2','s.y.w').replace('1-r2','s.z.w')
    cpu_text=cpu_text.replace('f(s.y,0),f(s.z,0)','f(s.y,.25-s.q.dot(s.q)),f(s.z,1-s.q.dot(s.q))')
(project/'src/fractal.hlsl').write_text(shader,encoding='utf-8');(project/'src/citadel.h').write_text(cpu_text,encoding='utf-8')
subprocess.run(['cmake','--build',str(project/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
out=root/'validation/edge-report-2026-10-17'/args.variant;out.mkdir(exist_ok=True)
shutil.copy2(root/'validation/edge-report-2026-10-17/slow-capture/last-flight.aurora',out/'last-flight.aurora')
subprocess.run([str(project/'build-vs/Release/AuroraFractal.exe'),'--edge-capture'],cwd=out,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
print(out)
