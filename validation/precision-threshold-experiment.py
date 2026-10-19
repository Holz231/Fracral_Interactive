"""Screen direct-tail precision thresholds against the fixed native renderer."""
from pathlib import Path
import argparse,shutil,subprocess,json
p=argparse.ArgumentParser();p.add_argument('threshold',choices=['0.001','0.0002','0.0001','0.00005','0.00001']);args=p.parse_args()
root=Path(__file__).resolve().parent.parent;base=root/'validation/experiments/native-edge-fixed'
out=root/'validation/experiments'/('native-threshold-'+args.threshold);out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
path=out/'src/fractal.hlsl';s=path.read_text(encoding='utf-8');assert s.count('derivative>renderInfo.y*1.85*.001')==1
s=s.replace('derivative>renderInfo.y*1.85*.001','derivative>renderInfo.y*1.85*'+args.threshold);path.write_text(s,encoding='utf-8')
path=out/'src/renderer.cpp';s=path.read_text(encoding='utf-8')
key='    for(size_t i=0;i<oldStatus.size();i++) if(oldStatus[i]>0 && newStatus[i]>0) {'
extra='''    {
        std::ofstream trace(std::filesystem::path(prefix+L"-accelerated-depth.bin"),std::ios::binary);
        for(size_t i=0;i<newStatus.size();i++) {
            float pair[]={newDepth[i],float(newStatus[i])};trace.write(reinterpret_cast<const char*>(pair),sizeof(pair));
        }
    }
'''
assert key in s;s=s.replace(key,extra+key,1);path.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--target','AuroraFractal','--parallel'],check=True,stdout=subprocess.DEVNULL)
fixtures={
 'edge':root/'validation/edge-report-2026-10-17/slow-capture/last-flight.aurora',
 'heavy':root/'validation/slow-69ms-fixture/last-flight.aurora',
 'new-slow':root/'validation/optimization-2026-10-17/new-slow.aurora',
 'new-last':root/'validation/optimization-2026-10-17/new-last.aurora',
}
for name,flight in fixtures.items():
 run=out/name;run.mkdir(exist_ok=True);shutil.copy2(flight,run/'last-flight.aurora')
 result=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--replay','--native-only'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
 report=run/'validation/replay/saved-native.json'
 if not report.exists():raise RuntimeError(f'Missing report: {run}, exit {result.returncode}')
 data=json.loads(report.read_text());print(args.threshold,name,data['after_ms'],'unfinished',data['unfinished'],flush=True)
