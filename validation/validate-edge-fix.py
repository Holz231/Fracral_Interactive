"""Sequential native comparisons of the delivered preview and the boundary fix."""
from pathlib import Path
import subprocess,shutil,json
root=Path(__file__).resolve().parent.parent
out=root/'validation/edge-report-2026-10-17/native-comparison';out.mkdir(exist_ok=True)
executables={'preview':root/'validation/baselines/preview-2026-10-17-0803/AuroraFractal.exe','fixed':root/'validation/experiments/native-edge-fixed/build-vs/Release/AuroraFractal.exe'}
fixtures={'edge':root/'validation/edge-report-2026-10-17/slow-capture/last-flight.aurora'}
for name in ('slow-69ms','slow-41ms','slow-45ms','slow-384ms','interior','stutter','slow-start-56ms'):
    fixtures[name]=root/f'validation/{name}-fixture/last-flight.aurora'
reports={}
for name,flight in fixtures.items():
    reports[name]={}
    for version,exe in executables.items():
        run=out/name/version;run.mkdir(parents=True,exist_ok=True);shutil.copy2(flight,run/'last-flight.aurora')
        process=subprocess.run([str(exe),'--replay','--native-only'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
        report=run/'validation/replay/saved-native.json'
        if not report.exists():raise RuntimeError(f'Missing report: {run}, exit {process.returncode}')
        data=json.loads(report.read_text());data['exit_code']=process.returncode;reports[name][version]=data
        print(name,version,'GPU ms',data['after_ms'],'unfinished',data['unfinished'],flush=True)
        (out/'summary.json').write_text(json.dumps(reports,indent=2)+'\n')
for version,exe in executables.items():
    run=out/'motion'/version;run.mkdir(parents=True,exist_ok=True);shutil.copy2(fixtures['edge'],run/'last-flight.aurora')
    subprocess.run([str(exe),'--micro-motion'],cwd=run,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Micro-motion',version,'complete',flush=True)
run=out/'flight';run.mkdir(exist_ok=True);shutil.copy2(fixtures['edge'],run/'last-flight.aurora')
subprocess.run([str(executables['fixed']),'--flight-profile'],cwd=run,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
print('Fixed forward/reverse flight complete',flush=True)
run=out/'smoke';run.mkdir(exist_ok=True)
subprocess.run([str(executables['fixed']),'--benchmark'],cwd=run,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
print('Native smoke complete',flush=True)
