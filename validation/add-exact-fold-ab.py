"""Add alternating old/new shader measurements and exact motion comparison."""
from pathlib import Path
import shutil,subprocess,argparse
p=argparse.ArgumentParser();p.add_argument('--chunk',type=int,choices=[16,32,64,128],default=64);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/native-exact-combined'
out=root/'validation/experiments'/('native-exact-ab' if a.chunk==64 else f'native-chunk-{a.chunk}');out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
s='''#ifndef EXACT_FOLD_OPT
#define EXACT_FOLD_OPT 1
#endif
#if EXACT_FOLD_OPT
#define SPHERE_DENOM(q) max(saturate(dot(q,q)),.25)
#define SPHERE_BASE(s) s.next.w
#else
#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
#endif
'''+s.replace('max(saturate(dot(q,q)),.25)','SPHERE_DENOM(q)').replace('max(saturate(dot(p,p)),.25)','SPHERE_DENOM(p)').replace('-s.next.w','-SPHERE_BASE(s)')
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.h';s=p.read_text(encoding='utf-8').replace('    double profileView(', '    void profileExactFolds(const World&,const View&,const std::wstring&);\n    double profileView(')
s=s.replace('static constexpr int rayChunk=64;',f'static constexpr int rayChunk={a.chunk};');p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8')
method=r'''
void Renderer::profileExactFolds(const World& world,const View& view,const std::wstring& prefix) {
    struct Bank {
        ComPtr<ID3D11ComputeShader> begin,next,finish,segment,refine;
        ComPtr<ID3D11PixelShader> resolve;
        std::array<ComPtr<ID3D11ComputeShader>,3> cones;
    };
    prepareWaveShaders(1);prepareWaveTargets(1);
    Bank optimized{rayBegin[1],rayContinue[1],rayFinish[1],raySegment[1],rayRefine[1],rayResolve[1],coneShaders},original;
    D3D_SHADER_MACRO macros[]={{"SHADOW_STEPS","4"},{"AO_STEPS","3"},{"PIXEL_SAMPLES","1"},{"RAY_CHUNK","64"},{"WORLD_KIND","1"},{"UNIFORM_FOLDS","1"},{"DEFER_SURFACE_REFINE","1"},{"CONE_START","1"},{"COOPERATIVE_RAYS","0"},{"EXACT_FOLD_OPT","0"},{nullptr,nullptr}};
    auto compute=[&](const char* entry,ComPtr<ID3D11ComputeShader>& shader) {
        auto b=compileShader(entry,"cs_5_0",macros);check(device->CreateComputeShader(b->GetBufferPointer(),b->GetBufferSize(),nullptr,&shader),"Create exact-fold comparison shader");
    };
    compute("beginRays",original.begin);compute("refineRays",original.refine);
    macros[3].Definition="256";compute("continueRays",original.next);
    macros[3].Definition="8192";compute("continueRays",original.finish);
    macros[3].Definition="256";macros[8].Definition="1";compute("segmentRays",original.segment);macros[8].Definition="0";
    auto resolve=compileShader("resolveRays","ps_5_0",macros);
    check(device->CreatePixelShader(resolve->GetBufferPointer(),resolve->GetBufferSize(),nullptr,&original.resolve),"Create exact-fold comparison shading");
    for(int level=0;level<3;level++) {
        std::string tile=std::to_string(16>>level),index=std::to_string(level);
        D3D_SHADER_MACRO cm[]={{"UNIFORM_FOLDS","1"},{"WORLD_KIND","1"},{"CONE_TILE",tile.c_str()},{"CONE_LEVEL",index.c_str()},{"EXACT_FOLD_OPT","0"},{nullptr,nullptr}};
        auto blob=compileShader("buildCones","cs_5_0",cm);
        check(device->CreateComputeShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&original.cones[level]),"Create exact-fold comparison cones");
    }
    auto select=[&](bool candidate) {
        const auto& b=candidate?optimized:original;
        rayBegin[1]=b.begin;rayContinue[1]=b.next;rayFinish[1]=b.finish;raySegment[1]=b.segment;rayRefine[1]=b.refine;rayResolve[1]=b.resolve;coneShaders=b.cones;
    };
    // Same process, resources and constants. ABBA reverses order to distribute
    // external load and clock drift; retain individual timings, not just a mean.
    for(int i=0;i<12;i++) {select(i%2);measure(nullptr,world,view,1,1);}
    std::ofstream timings(std::filesystem::path(prefix+L"-timings.csv"));timings<<"round,order,candidate,gpu_ms\n";
    for(int round=0;round<20;round++) for(int order=0;order<4;order++) {
        bool candidate=(order==1 || order==2) ^ bool(round%2);select(candidate);
        timings<<round<<','<<order<<','<<candidate<<','<<measure(nullptr,world,view,1,1)<<'\n';
    }
    timings.flush();
    D3D11_TEXTURE2D_DESC desc{};rayTexture->GetDesc(&desc);desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> readback;check(device->CreateTexture2D(&desc,nullptr,&readback),"Create exact-fold depth readback");
    auto depth=[&]() {
        context->CopyResource(readback.Get(),rayTexture.Get());D3D11_MAPPED_SUBRESOURCE m{};
        check(context->Map(readback.Get(),0,D3D11_MAP_READ,0,&m),"Read exact-fold depth");
        std::vector<float> result(size_t(renderWidth)*renderHeight*2);
        for(int y=0;y<renderHeight;y++) memcpy(result.data()+size_t(y)*renderWidth*2,static_cast<unsigned char*>(m.pData)+size_t(y)*m.RowPitch,size_t(renderWidth)*8);
        context->Unmap(readback.Get(),0);return result;
    };
    World moving=world;size_t colorChanges=0,depthChanges=0,statusChanges=0;int maximum=0;
    for(int frame=0;frame<48;frame++) {
        if(frame) {moving.advance(view.forward()*(frame<24?.0001:-.0001));moving.prepare();}
        setConstants(moving,view,0);select(false);wavefrontPass(1);auto before=pixels();auto beforeDepth=depth();
        select(true);wavefrontPass(1);auto after=pixels();auto afterDepth=depth();
        for(size_t i=0;i<before.size();i+=4) {
            int error=0;for(int c=0;c<4;c++) error=std::max(error,std::abs(int(before[i+c])-int(after[i+c])));
            maximum=std::max(maximum,error);colorChanges+=error!=0;
        }
        for(size_t i=0;i<beforeDepth.size();i+=2) {
            depthChanges+=beforeDepth[i]!=afterDepth[i] || !std::isfinite(afterDepth[i]);
            statusChanges+=beforeDepth[i+1]!=afterDepth[i+1];
        }
    }
    std::ofstream report(std::filesystem::path(prefix+L".json"));
    report<<"{\"poses\":48,\"width\":"<<renderWidth<<",\"height\":"<<renderHeight<<",\"changed_rgba_pixels\":"<<colorChanges<<",\"max_rgba_error\":"<<maximum<<",\"changed_depths\":"<<depthChanges<<",\"changed_statuses\":"<<statusChanges<<"}\n";report.flush();
    select(true);
    if(colorChanges || depthChanges || statusChanges) throw std::runtime_error("Exact fold optimization changed the rendered flight");
}
'''
s=s.replace('double Renderer::profileView(',method+'\ndouble Renderer::profileView(',1);p.write_text(s,encoding='utf-8')
p=out/'src/main.cpp';s=p.read_text(encoding='utf-8')
fn='''static int exactFoldAB(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"fold-ab";std::filesystem::create_directories(dir);
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    app.renderer.profileExactFolds(app.world,app.view,(dir/L"comparison").wstring());return 0;
}
'''
s=s.replace('static int replay(',fn+'\nstatic int replay(',1)
s=s.replace('    bool fieldMode=', '    bool foldMode=std::wstring(commandLine).find(L"--fold-ab")!=std::wstring::npos;\n    bool fieldMode=',1)
s=s.replace('bool benchmark=fieldMode||','bool benchmark=foldMode||fieldMode||',1)
s=s.replace('result=fieldMode?fieldRegression(app)', 'result=foldMode?exactFoldAB(app):fieldMode?fieldRegression(app)',1)
p.write_text(s,encoding='utf-8')
p=out/'tests/citadel_tests.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('float dc=std::clamp(change,packed.y.w,packed.z.w)-std::clamp(0.f,packed.y.w,packed.z.w);',
'''require(packed.next.w==std::clamp(0.f,packed.y.w,packed.z.w),"Precomputed sphere base lost boundary precision");
            float dc=std::clamp(change,packed.y.w,packed.z.w)-packed.next.w;''')
p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True)
print(out)
