"""Stop direct folds only when their hit predicate is already provably true."""
from pathlib import Path
import subprocess,shutil,csv,json,statistics
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-exact-ab'
out=root/'validation/experiments/native-certified-hit';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:]
s=s.replace('float citadelDistanceScaled(float3 basis,float3 origin,float3 pole,float derivative,int lo) {',
'''float citadelDistanceScaledThreshold(float3 basis,float3 origin,float3 pole,float derivative,int lo,float stopThreshold) {''',1)
old='''            if(dot(p,p)>4096 || derivative>1e24) break;'''
new='''            float radiusSquared=dot(p,p);
            if(radiusSquared>4096 || derivative>1e24) break;
            #if EXACT_FOLD_OPT
            // Box folding cannot increase |p|, and every sphere scale is >=2.8.
            // All future normalized radii are <= (|p|+|c|/1.8)/derivative.
            // With |c|=2.1, 0.5*(|p|+2) is a conservative upper bound for
            // the 0.45 distance estimate, including ample FP roundoff margin.
            // 0.5*(r^2+4) bounds [0.5*(r+2)]^2 without a square root.
            float projected=derivative*stopThreshold;
            if(projected*projected>.5*radiusSquared+2) return 0;
            #endif'''
directStart=s.index('    #if UNIFORM_FOLDS\n    [loop] for(;iteration<end;iteration++) {')
directEnd=s.index('    #else\n    [loop] for(;iteration<end;iteration++) {',directStart)
direct=s[directStart:directEnd];assert direct.count(old)==2
s=s[:directStart]+direct.replace(old,new)+s[directEnd:]
marker='float citadelDistanceFrom('
wrapper='''float citadelDistanceScaled(float3 basis,float3 origin,float3 pole,float derivative,int lo) {
    return citadelDistanceScaledThreshold(basis,origin,pole,derivative,lo,0);
}
'''
s=s.replace(marker,wrapper+marker,1)
# Only consumers that solely test d<threshold may accept an early zero. In
# particular a speculative march sample needs its full value for verification.
start=s.index('bool marchJob(');end=s.index('groupshared uint pendingCount',start)
part=s[start:end]
old='citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first)'
new='citadelDistanceScaledThreshold(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first,verify?0:pixel*.65)'
assert part.count(old)==1;part=part.replace(old,new);s=s[:start]+part+s[end:]
start=s.index('void buildCones(');end=s.index('bool initializeJob(',start);part=s[start:end]
assert part.count(old)==1;part=part.replace(old,'citadelDistanceScaledThreshold(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first,cone*1.1)');s=s[:start]+part+s[end:]
start=s.index('void refineRays(');end=s.index('float4 shadeJob(',start);part=s[start:end]
old='citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first)'
assert part.count(old)==1;part=part.replace(old,'citadelDistanceScaledThreshold(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first,pixel*.65)');s=s[:start]+part+s[end:]
p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in ['edge','heavy','new-slow','new-last']:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab';report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('certified hit',fixture,'exit',proc.returncode,'ms',ms,report,flush=True)
