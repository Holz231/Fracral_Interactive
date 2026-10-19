"""Change the first compaction point, preserving all subsequent ray intervals."""
from pathlib import Path
import argparse,subprocess,shutil,csv,json,statistics
p=argparse.ArgumentParser();p.add_argument('chunk',type=int,choices=[16,32,128,256]);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-exact-ab'
out=root/f'validation/experiments/native-early-compaction-{a.chunk}';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:];p.write_text(s,encoding='utf-8')
p=out/'src/renderer.h';s=p.read_text(encoding='utf-8')
s=s.replace('rayBegin,rayContinue,rayFinish,rayRefine,raySegment;','rayBegin,rayContinue,rayFinish,rayRefine,raySegment,rayEarlyContinue;')
s=s.replace('static constexpr int rayChunk=64;',f'static constexpr int rayChunk={a.chunk};');p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('''        macros[3].Definition="256";auto next=compileShader("continueRays","cs_5_0",macros);''','''        // Preserve the original 320-step boundary after the first continuation.
        std::string earlyChunk=std::to_string(320-rayChunk);macros[3].Definition=earlyChunk.c_str();
        auto early=compileShader("continueRays","cs_5_0",macros);
        check(device->CreateComputeShader(early->GetBufferPointer(),early->GetBufferSize(),nullptr,&rayEarlyContinue[profile]),"Create early compaction continuation");
        macros[3].Definition="256";auto next=compileShader("continueRays","cs_5_0",macros);''')
s=s.replace('(batch==rayBatches-1?rayFinish:batch>=8?raySegment:rayContinue)[profile]', '(batch==rayBatches-1?rayFinish:batch>=8?raySegment:batch==1?rayEarlyContinue:rayContinue)[profile]')
s=s.replace('ComPtr<ID3D11ComputeShader> begin,next,finish,segment,refine;', 'ComPtr<ID3D11ComputeShader> begin,next,finish,segment,refine,early;')
s=s.replace('rayRefine[1],rayResolve[1],coneShaders},original;', 'rayRefine[1],rayEarlyContinue[1],rayResolve[1],coneShaders},original;')
s=s.replace('compute("continueRays",original.next);', 'compute("continueRays",original.next);original.early=original.next;')
s=s.replace('rayRefine[1]=b.refine;rayResolve', 'rayRefine[1]=b.refine;rayEarlyContinue[1]=b.early;rayResolve')
p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in ['edge','heavy']:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab';report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('early compaction',a.chunk,fixture,'exit',proc.returncode,'ms',ms,report,flush=True)
