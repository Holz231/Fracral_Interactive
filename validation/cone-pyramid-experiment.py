"""Generate an isolated multilevel empty-cone prepass; never edit production."""
from pathlib import Path
import argparse
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--steps',type=int,default=256)
parser.add_argument('--last-tile',type=int,choices=(2,4,8,16),default=2)
parser.add_argument('--ball-step',action='store_true')
parser.add_argument('--stop',type=float,default=1.5)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
suffix=('-ball' if args.ball_step else '')+(f'-stop{args.stop:g}' if args.stop!=1.5 else '')
out=root/f'validation/experiments/cone-pyramid-{args.last_tile}-{args.steps}{suffix}'
out.mkdir(parents=True,exist_ok=True)
shaders=out/'shaders';shaders.mkdir(exist_ok=True)
base='#ifndef CONE_START\n#define CONE_START 0\n#endif\n'+(root/'src/fractal.hlsl').read_text(encoding='utf-8')
helpers=r'''
// A node covers all pixel centers in its tile. The normalized camera rays
// differ by at most sqrt(2)*(tile-1)/(height*focalLength). The extra .75 pixel
// protects the finite hit footprint in addition to the geometric surface.
RWTexture2DArray<float> conePyramid:register(u6);
#ifndef CONE_TILE
#define CONE_TILE 16
#endif
#ifndef CONE_LEVEL
#define CONE_LEVEL 0
#endif
#ifndef CONE_STEPS
#define CONE_STEPS 256
#endif
[numthreads(8,8,1)]
void buildCones(uint3 id:SV_DispatchThreadID) {
    uint2 size=(uint2(renderInfo.xy)+CONE_TILE-1)/CONE_TILE;
    if(any(id.xy>=size)) return;
    float2 center=float2(id.xy)*CONE_TILE+CONE_TILE*.5;
    float2 uv=(center*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float cone=(1.414214*(CONE_TILE-1)+.75)/(renderInfo.y*1.85);
    float start=-7;
    #if CONE_LEVEL > 0
    start=max(start,conePyramid[uint3(id.xy/2,CONE_LEVEL-1)]-8e-6);
    #endif
    float scale=floor(start),t=exp2(start-scale);
    int first=citadelStart(start);RayPrefix prefix=rayPrefix(rd,first,scale);
    float horizon=min(256,8-reference[0].p.w);
    [loop] for(int i=0;i<CONE_STEPS;i++) {
        if(t>4096) {scale+=12;t/=4096;prefix.derivative*=4096;prefix.limit/=4096;}
        if(first>0 && t>=prefix.limit) {
            [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-scale,100)));
            prefix=rayPrefix(rd,first,scale);
        }
        float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        if(d<cone*1.5 || log2(t)+scale>horizon) break;
        // At t*(1+s), the furthest child lies <= t*(s+cone*(1+s)) away.
        // Keep that entire region inside the empty ball at the center ray.
        t*=1+.9*(d-cone)/(1+cone);
    }
    conePyramid[uint3(id.xy,CONE_LEVEL)]=log2(t)+scale-8e-6;
}
'''
base=base.replace('bool initializeJob(',helpers+'\nbool initializeJob(',1)
base=base.replace('if(d<cone*1.5 ||',f'if(d<cone*{args.stop} ||')
if args.ball_step:
    base=base.replace('t*=1+.9*(d-cone)/(1+cone);', '''float angular=1.414214*(CONE_TILE-1)/(renderInfo.y*1.85);
        float shell=.75/(renderInfo.y*1.85),a2=angular*angular;
        // Solve |x*childDirection-centerDirection| + shell*x <= d.
        // This guards both the tile's angle and the finite hit shell.
        float discriminant=(d-shell)*(d-shell)-a2*(1-.25*a2-d*shell);
        float advance=(sqrt(max(0,discriminant))-.5*a2-d*shell+shell*shell)/(1-shell*shell);
        t*=1+.9*max(0,advance);''')
level={16:0,8:1,4:2,2:3}[args.last_tile]
base=base.replace('    job.scale=floor(start);job.t',f'''    #if CONE_START
    uint3 position=rayPixel(job.index);
    start=max(start,conePyramid[uint3(position.xy/{args.last_tile},{level})]-8e-6);
    start=min(start,job.horizon);
    #endif
    job.scale=floor(start);job.t''',1)
source=out/'fractal.hlsl';source.write_text(base,encoding='utf-8')
fxc=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
def compile(entry,target,chunk=256,extra=()):
    cmd=[str(fxc),'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges',
         '/D','UNIFORM_FOLDS=1','/D','DEFER_SURFACE_REFINE=1','/D','WORLD_KIND=1','/D','CONE_START=1',
         '/D',f'RAY_CHUNK={chunk}',*extra,'/Fo',str(shaders/f'{target}.dxil'),str(source)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
for entry in ('beginRays','continueRays','finishRays','prepareRays','sortRays','refineRays'):
    compile('continueRays' if entry=='finishRays' else entry,entry,64 if entry=='beginRays' else 8192 if entry=='finishRays' else 256)
for i,tile in enumerate((16,8,4,2)):
    if tile<args.last_tile:break
    compile('buildCones',f'cone{tile}',extra=('/D',f'CONE_TILE={tile}','/D',f'CONE_LEVEL={i}','/D',f'CONE_STEPS={args.steps}'))
print(out)
