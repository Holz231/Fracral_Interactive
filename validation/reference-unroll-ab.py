"""Screen identical reference folds with less loop-control overhead."""
from pathlib import Path
import argparse,subprocess,shutil,csv,json,statistics
p=argparse.ArgumentParser();p.add_argument('factor',type=int,choices=[2,3,4]);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-exact-ab'
out=root/f'validation/experiments/native-reference-unroll-{a.factor}';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
path=out/'src/fractal.hlsl';s=path.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:]
start=s.index('    [loop] for(;iteration<end;iteration++) {')
end=s.index('    #if UNIFORM_FOLDS\n    [loop] for(;iteration<end;',start)
original=s[start:end]
body=original[original.index('{\n')+2:original.rfind('    }')]
replacement='    #if EXACT_FOLD_OPT\n    [loop] for(;iteration<end;iteration++) {\n'
replacement+=('\n        if(++iteration>=end) break;\n').join('        {\n'+body+'        }\n' for _ in range(a.factor))
replacement+='    }\n    #else\n'+original+'    #endif\n'
s=s[:start]+replacement+s[end:];path.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in ['edge','heavy']:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab';report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('reference unroll',a.factor,fixture,'exit',proc.returncode,'ms',ms,report,flush=True)
