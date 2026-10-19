"""Isolate native D3D11 tests of the cone hierarchy and parallel ray intervals."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parent.parent
base=root/'validation/experiments/cone-pyramid-native'
out=root/'validation/experiments/cone-segments-native'
out.mkdir(parents=True,exist_ok=True)
for folder in ('src','tests'):shutil.copytree(base/folder,out/folder,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
shutil.copy2(root/'validation/experiments/cone-segments-32-0.05-geometric-ball-stop1.1/fractal.hlsl',out/'src/fractal.hlsl')
p=out/'src/renderer.h';s=p.read_text(encoding='utf-8')
s=s.replace('rayBegin,rayContinue,rayFinish,rayRefine;', 'rayBegin,rayContinue,rayFinish,rayRefine,raySegment;')
s=s.replace('    void present();', '''    void present();
    double warmUp(const World&,const View&,int palette);''')
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('    window=hwnd;','''    window=hwnd;
    // An extra queued frame prevents small GPU overruns from costing a full
    // refresh interval. Keep a bounded queue and a diagnostic low-latency mode.
    UINT frameLatency=2;wchar_t latencySetting[16]{};
    if(GetEnvironmentVariableW(L"AURORA_FRAME_QUEUE",latencySetting,16)) frameLatency=UINT(std::clamp(_wtoi(latencySetting),1,3));''',1)
s=s.replace('dxgiDevice->SetMaximumFrameLatency(1)', 'dxgiDevice->SetMaximumFrameLatency(frameLatency)')
s=s.replace('desc.BufferCount=2;', 'desc.BufferCount=frameLatency+1;')
s=s.replace('scheduled->SetMaximumFrameLatency(1)', 'scheduled->SetMaximumFrameLatency(frameLatency)')
s=s.replace('void Renderer::present()', '''double Renderer::warmUp(const World& world,const View& view,int palette) {
    // First dispatch can include deferred driver compilation. Do it before
    // opening the flight window, and keep startup time separate from FPS.
    wchar_t skip[2]{};
    if(GetEnvironmentVariableW(L"AURORA_SKIP_WARMUP",skip,2) && skip[0]==L'1') return 0;
    auto started=std::chrono::steady_clock::now();
    D3D11_QUERY_DESC desc{D3D11_QUERY_EVENT,0};ComPtr<ID3D11Query> done;
    check(device->CreateQuery(&desc,&done),"Create startup completion event");
    for(int frame=0;frame<8;frame++) {
        render(world,view,palette,false);context->End(done.Get());context->Flush();
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
        HRESULT completion=S_FALSE;
        while((completion=context->GetData(done.Get(),nullptr,0,0))==S_FALSE) {
            check(device->GetDeviceRemovedReason(),"GPU startup");
            if(std::chrono::steady_clock::now()>deadline) throw std::runtime_error("GPU startup timed out");
            Sleep(1);
        }
        check(completion,"Complete GPU startup");
    }
    return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
}
void Renderer::present()''',1)
s=s.replace('{"CONE_START","1"},{nullptr,nullptr}', '{"CONE_START","1"},{"COOPERATIVE_RAYS","0"},{nullptr,nullptr}')
s=s.replace('''        check(device->CreateComputeShader(finish->GetBufferPointer()''','''        macros[3].Definition="256";macros[8].Definition="1";
        auto segment=compileShader("segmentRays","cs_5_0",macros);
        check(device->CreateComputeShader(segment->GetBufferPointer(),segment->GetBufferSize(),nullptr,&raySegment[profile]),"Create parallel ray intervals");
        macros[8].Definition="0";
        check(device->CreateComputeShader(finish->GetBufferPointer()''',1)
s=s.replace('d.ByteWidth=16;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;',
    'd.ByteWidth=32;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;')
s=s.replace('u.Buffer.NumElements=4;', 'u.Buffer.NumElements=8;').replace('s.Buffer.NumElements=4;', 's.Buffer.NumElements=8;')
s=s.replace('''context->CSSetShader((batch==rayBatches-1?rayFinish:rayContinue)[profile].Get(),nullptr,0);
        context->DispatchIndirect(dispatchBuffer.Get(),0);''','''context->CSSetShader((batch==rayBatches-1?rayFinish:batch>=8?raySegment:rayContinue)[profile].Get(),nullptr,0);
        context->DispatchIndirect(dispatchBuffer.Get(),batch>=8 && batch<rayBatches-1?16:0);''',1)
p.write_text(s,encoding='utf-8')
p=out/'src/main.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('L"Aurora — Native Fractal Flight"', 'L"Aurora — Accelerated Preview"')
s=s.replace('        if(!benchmark) app.restore();','''        if(!benchmark) app.restore();
        if(!benchmark && std::wstring(commandLine).find(L"--load-flight")!=std::wstring::npos) {
            loadFlight(app.world,app.view,app.directory/L"last-flight.aurora");app.automatic=false;
        }''',1)
s=s.replace('''            ShowWindow(window,SW_SHOW);UpdateWindow(window);''','''            double startupMs=app.renderer.warmUp(app.world,app.view,app.palette);
            adapterLog<<"GPU startup preparation: "<<startupMs<<" ms\\n";adapterLog.flush();
            ShowWindow(window,SW_SHOW);UpdateWindow(window);''',1)
s=s.replace('''    int activeFrames=0,switches=0;bool previous=false;''','''    double startupMs=app.renderer.warmUp(app.world,app.view,0);
    std::ofstream startup(dir/L"startup-ms.txt");startup<<startupMs<<'\\n';
    int activeFrames=0,switches=0;bool previous=false;''',1)
p.write_text(s,encoding='utf-8')
for name in ('slow-69ms-fixture','slow-41ms-fixture','slow-45ms-fixture','slow-384ms-fixture','interior-fixture','stutter-fixture','slow-start-56ms-fixture'):
    source=root/'validation'/name/'last-flight.aurora'
    if source.exists():
        dest=out/name;dest.mkdir(exist_ok=True);shutil.copy2(source,dest/'last-flight.aurora')
print(out)
