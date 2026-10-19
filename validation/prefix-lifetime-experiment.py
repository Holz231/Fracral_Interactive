"""Shorten live prefix vectors without changing field arithmetic."""
from pathlib import Path
import subprocess
import shutil
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/cone-segments-32-0.05-geometric-ball-stop1.1'
out=root/'validation/experiments/cone-segments-short-prefix';out.mkdir(parents=True,exist_ok=True)
shutil.copytree(base/'shaders',out/'shaders',dirs_exist_ok=True)
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
where='float2 traceCitadel('
s=s.replace(where,'''float rayDistance(float3 rd,float derivative,int first) {
    OrbitSample a=reference[first];
    float3 basis=a.x.xyz*rd.x+a.y.xyz*rd.y+a.z.xyz*rd.z;
    return citadelDistanceScaled(basis,a.p.xyz,a.curve.xyz,derivative,first);
}
'''+where,1)
s=s.replace('citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first)','rayDistance(rd,prefix.derivative*t,first)')
s=s.replace('citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first)','rayDistance(rd,prefix.derivative*middle,first)')
source=out/'fractal.hlsl';source.write_text(s,encoding='utf-8')
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
for entry,target,chunk in [('beginRays','beginRays',64),('continueRays','continueRays',256),('continueRays','finishRays',8192),('segmentRays','packetRays',256),('refineRays','refineRays',256)]:
    result=subprocess.run([fxc,'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges',
        '/D','UNIFORM_FOLDS=1','/D','DEFER_SURFACE_REFINE=1','/D','WORLD_KIND=1','/D','CONE_START=1',
        '/D',f'COOPERATIVE_RAYS={int(entry=="segmentRays")}','/D',f'RAY_CHUNK={chunk}',
        '/Fo',str(out/f'shaders/{target}.dxil'),str(source)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
print(out)
