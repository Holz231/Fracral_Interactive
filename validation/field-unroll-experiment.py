"""Group identical direct folds to reduce loop control without changing math."""
from pathlib import Path
import argparse
import shutil
import subprocess

p=argparse.ArgumentParser();p.add_argument('factor',type=int,choices=(2,3,4));a=p.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/segment-schedule-1-direct'
out=root/f'validation/experiments/field-unroll-{a.factor}'
out.mkdir(exist_ok=True);shutil.copytree(base/'shaders',out/'shaders',dirs_exist_ok=True)
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
start=s.index('    [loop] for(;iteration<end;iteration++) {',s.index('    [loop] for(;iteration<end;iteration++) {')+1)
end=s.index('    #else\n    [loop] for(int i=lo;',start)
original=s[start:end]
body='''        {
            #if TRACE_DIAGNOSTIC == 3
            fieldIterations++;
            #endif
            float3 q=2*clamp(p,-1,1)-p;
            float k=2.8/clamp(dot(q,q),.25,1);
            p=q*k+fractalParameters.xyz;derivative*=k;
            if(dot(p,p)>4096 || derivative>1e24) break;
        }
'''
replacement='    #if UNIFORM_FOLDS\n    [loop] for(;iteration<end;iteration++) {\n'
replacement+=('        if(++iteration>=end) break;\n').join([body]*a.factor)
replacement+='    }\n    #else\n'+original+'    #endif\n'
s=s[:start]+replacement+s[end:]
source=out/'fractal.hlsl';source.write_text(s,encoding='utf-8')
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
entries=[('beginRays','beginRays',64),('continueRays','continueRays',256),('continueRays','finishRays',8192),('segmentRays','packetRays',256),('refineRays','refineRays',256)]
entries += [('buildCones',f'cone{16>>level}',256) for level in range(3)]
for entry,target,chunk in entries:
    extra=[]
    if entry=='buildCones':
        tile=int(target[4:]);extra=['/D',f'CONE_TILE={tile}','/D',f'CONE_LEVEL={ {16:0,8:1,4:2}[tile] }']
    result=subprocess.run([fxc,'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges',
        '/D','UNIFORM_FOLDS=1','/D','DEFER_SURFACE_REFINE=1','/D','WORLD_KIND=1','/D','CONE_START=1',
        '/D',f'COOPERATIVE_RAYS={int(entry=="segmentRays")}','/D',f'RAY_CHUNK={chunk}',*extra,
        '/Fo',str(out/f'shaders/{target}.dxil'),str(source)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
print(out)
