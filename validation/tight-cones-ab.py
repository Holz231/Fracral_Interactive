"""Screen a conservative cone fitted to the actual four corner directions.

This changes traversal sampling, so the exact comparison is expected to reject
differences. Export first-pose depths and cone starts for independent auditing.
"""
from pathlib import Path
import argparse, subprocess, shutil, csv, json, statistics

p=argparse.ArgumentParser()
p.add_argument('--fixtures',nargs='+',default=['edge','heavy'])
p.add_argument('--last-tile',type=int,choices=[2,4],default=4)
p.add_argument('--stop',type=float,default=1.1)
a=p.parse_args()
if a.stop<=1: p.error('--stop must stay strictly above 1')
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-exact-ab'
out=root/f'validation/experiments/native-tight-cones-{a.last_tile}-{a.stop:g}';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
# Restore the canonical CPU layout and tests; only the cone bound changes.
fixed=root/'validation/experiments/native-edge-fixed'
shutil.copy2(fixed/'src/citadel.h',out/'src/citadel.h')
shutil.copytree(fixed/'tests',out/'tests',dirs_exist_ok=True)
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:];s=s.replace('EXACT_FOLD_OPT','TIGHT_CONES')
old='    float cone=(1.414214*(CONE_TILE-1)+.75)/(renderInfo.y*1.85);'
new='''    float angular=1.414214*(CONE_TILE-1)/(renderInfo.y*1.85);
    float shell=.75/(renderInfo.y*1.85);
    #if TIGHT_CONES
    // Unnormalized child rays are positive combinations of the four corner
    // rays. A circular cone narrower than a hemisphere is convex, so a cone
    // containing those four directions contains every pixel-center direction.
    float2 low=float2(id.xy)*CONE_TILE+.5;
    float2 high=min(low+CONE_TILE-1,renderInfo.xy-.5);
    float radius=0;
    [unroll] for(int corner=0;corner<4;corner++) {
        float2 cornerPixel=float2((corner&1)?high.x:low.x,(corner&2)?high.y:low.y);
        float2 cuv=(cornerPixel*2-renderInfo.xy)/renderInfo.y;cuv.y=-cuv.y;
        float3 direction=normalize(viewRight.xyz*cuv.x+viewUp.xyz*cuv.y+viewForward.xyz*1.85);
        radius=max(radius,length(direction-rd));
    }
    // Include float normalization error; never enlarge the old valid bound.
    angular=min(angular,radius+2e-6);
    float cone=angular+shell;
    #else
    float cone=(1.414214*(CONE_TILE-1)+.75)/(renderInfo.y*1.85);
    #endif'''
assert s.count(old)==1;s=s.replace(old,new,1)
s=s.replace('        float angular=1.414214*(CONE_TILE-1)/(renderInfo.y*1.85);\n        float shell=.75/(renderInfo.y*1.85),a2=angular*angular;',
            '        float a2=angular*angular;',1)
s=s.replace('if(d<cone*1.1 ||',f'if(d<cone*(TIGHT_CONES?{a.stop}:1.1) ||',1)
if a.last_tile==2:
    s=s.replace('start=max(start,conePyramid[uint3(position.xy/4,2)]-8e-6);',
                'start=max(start,conePyramid[uint3(position.xy/(TIGHT_CONES?2:4),TIGHT_CONES?3:2)]-8e-6);',1)
p.write_text(s,encoding='utf-8')
if a.last_tile==2:
    p=out/'src/renderer.h';s=p.read_text(encoding='utf-8')
    s=s.replace('std::array<ComPtr<ID3D11ComputeShader>,3> coneShaders;',
                'int coneLevels=4;\n    std::array<ComPtr<ID3D11ComputeShader>,4> coneShaders;')
    p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8').replace('"EXACT_FOLD_OPT"','"TIGHT_CONES"')
if a.last_tile==2:
    s=s.replace('std::array<ComPtr<ID3D11ComputeShader>,3> cones;','std::array<ComPtr<ID3D11ComputeShader>,4> cones;')
    s=s.replace('for(int level=0;level<3;level++)','for(int level=0;level<4;level++)')
    s=s.replace('for(int level=0;level<4;level++) {\n        int tile=16>>level;context->CSSetShader',
                'for(int level=0;level<coneLevels;level++) {\n        int tile=16>>level;context->CSSetShader',1)
    s=s.replace('cd.Width=(renderWidth+3)/4;cd.Height=(renderHeight+3)/4;cd.ArraySize=3;',
                'cd.Width=(renderWidth+1)/2;cd.Height=(renderHeight+1)/2;cd.ArraySize=4;',1)
    s=s.replace('const auto& b=candidate?optimized:original;',
                'const auto& b=candidate?optimized:original;coneLevels=candidate?4:3;',1)
key='''        setConstants(moving,view,0);select(false);wavefrontPass(1);auto before=pixels();auto beforeDepth=depth();
        select(true);wavefrontPass(1);auto after=pixels();auto afterDepth=depth();'''
assert s.count(key)==1
s=s.replace(key,'''        setConstants(moving,view,0);select(false);wavefrontPass(1);auto before=pixels();auto beforeDepth=depth();
        if(frame==0) {upscaleScene();capture(prefix+L"-before.png");}
        select(true);wavefrontPass(1);auto after=pixels();auto afterDepth=depth();
        if(frame==0) {
            upscaleScene();capture(prefix+L"-after.png");
            auto save=[&](const wchar_t* suffix,const void* data,size_t bytes) {
                std::ofstream file(std::filesystem::path(prefix+suffix),std::ios::binary);
                file.write(static_cast<const char*>(data),bytes);
                if(!file) throw std::runtime_error("Cannot export cone audit");
            };
            save(L"-before-depth.bin",beforeDepth.data(),beforeDepth.size()*sizeof(float));
            save(L"-after-depth.bin",afterDepth.data(),afterDepth.size()*sizeof(float));
            const auto constants=sceneConstants(moving,view,0);
            save(L"-constants.bin",&constants,sizeof(constants));
            D3D11_TEXTURE2D_DESC coneDesc{};coneTexture->GetDesc(&coneDesc);
            coneDesc.Usage=D3D11_USAGE_STAGING;coneDesc.BindFlags=0;coneDesc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
            ComPtr<ID3D11Texture2D> coneRead;
            check(device->CreateTexture2D(&coneDesc,nullptr,&coneRead),"Create cone audit readback");
            context->CopyResource(coneRead.Get(),coneTexture.Get());
            for(int level=0;level<3;level++) {
                int tile=16>>level,w=(renderWidth+tile-1)/tile,h=(renderHeight+tile-1)/tile;
                D3D11_MAPPED_SUBRESOURCE map{};
                check(context->Map(coneRead.Get(),level,D3D11_MAP_READ,0,&map),"Read cone audit");
                std::vector<float> cone(size_t(w)*h);
                for(int y=0;y<h;y++) memcpy(cone.data()+size_t(y)*w,static_cast<const char*>(map.pData)+size_t(y)*map.RowPitch,size_t(w)*4);
                context->Unmap(coneRead.Get(),level);
                save((L"-cone-"+std::to_wstring(tile)+L".bin").c_str(),cone.data(),cone.size()*4);
            }
        }''',1)
p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in a.fixtures:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab'
    if not (folder/'comparison.json').exists():
        raise RuntimeError(f'{fixture}: exit {proc.returncode}, '+(run/'aurora-error.txt').read_text())
    report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('tight-cones',fixture,'exit',proc.returncode,'ms',ms,report,flush=True)

