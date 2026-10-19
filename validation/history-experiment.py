from pathlib import Path
import shutil
root=Path(__file__).resolve().parent.parent
out=root/'validation/experiments/far-history'
out.mkdir(parents=True,exist_ok=True)
shutil.copytree(root/'src',out/'src',dirs_exist_ok=True)
shutil.copytree(root/'tests',out/'tests',dirs_exist_ok=True)
shutil.copy2(root/'CMakeLists.txt',out/'CMakeLists.txt')

p=out/'src/renderer.h'
s=p.read_text(encoding='utf-8').replace('    bool lastCompacted=false;', '''    ComPtr<ID3D11Texture2D> historyTexture,historyWriteTexture;
    ComPtr<ID3D11ShaderResourceView> historyView;
    ComPtr<ID3D11UnorderedAccessView> historyTarget;
    ComPtr<ID3D11Buffer> historyConstants;
    Constants previousHistory{};
    bool historyValid=false,historyFrame=false;
    double historyUnit=0;
    void prepareHistory(const World&,const View&,int palette,bool enabled);
    bool lastCompacted=false;''')
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('''void Renderer::setConstants(const World& world,const View& view,int palette) {''','''void Renderer::prepareHistory(const World& world,const View& view,int palette,bool enabled) {
    auto current=sceneConstants(world,view,palette);
    int common=-1;
    auto equal3=[](const Float4& a,const Float4& b){return a.x==b.x && a.y==b.y && a.z==b.z;};
    if(enabled && historyValid && equal3(current.right,previousHistory.right) && equal3(current.up,previousHistory.up) && equal3(current.forward,previousHistory.forward)
       && equal3(current.fractalParameters,previousHistory.fractalParameters) && current.render.x==previousHistory.render.x && current.render.y==previousHistory.render.y) {
        for(int i=0;i<std::min(current.counts[0],previousHistory.counts[0]);i++) {
            const auto& a=current.reference[i];const auto& b=previousHistory.reference[i];
            if(!equal3(a.p,b.p) || !equal3(a.q,b.q) || a.q.w!=b.q.w || !equal3(a.next,b.next) || a.next.w!=b.next.w
               || !equal3(a.x,b.x) || !equal3(a.y,b.y) || !equal3(a.z,b.z) || !equal3(a.curve,b.curve)) break;
            common=i;
        }
    }
    // Require several unchanged folds beyond the selected field prefix.
    common-=6;
    if(!historyConstants) {
        D3D11_BUFFER_DESC d{};d.ByteWidth=16;d.Usage=D3D11_USAGE_DYNAMIC;d.BindFlags=D3D11_BIND_CONSTANT_BUFFER;d.CPUAccessFlags=D3D11_CPU_ACCESS_WRITE;
        check(device->CreateBuffer(&d,nullptr,&historyConstants),"Create history constants");
    }
    double unit=world.kind==1?world.citadel.logUnit:0;
    float high=float(std::floor(unit/32)*32);
    Float4 parameters{float(common),high,float(unit-high),enabled?1.f:0.f};
    D3D11_MAPPED_SUBRESOURCE mapped{};check(context->Map(historyConstants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Map history constants");
    memcpy(mapped.pData,&parameters,16);context->Unmap(historyConstants.Get(),0);
    auto buffer=historyConstants.Get();context->CSSetConstantBuffers(1,1,&buffer);
    historyFrame=enabled;
    if(enabled) {previousHistory=current;historyUnit=unit;}
}
void Renderer::setConstants(const World& world,const View& view,int palette) {''')
s=s.replace('''        UINT capacity=UINT(renderWidth*renderHeight*samples);''','''        historyTexture.Reset();historyWriteTexture.Reset();historyView.Reset();historyTarget.Reset();historyValid=false;
        d.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;
        check(device->CreateTexture2D(&d,nullptr,&historyTexture),"Create history texture");
        check(device->CreateTexture2D(&d,nullptr,&historyWriteTexture),"Create history write texture");
        s.Format=d.Format;u.Format=d.Format;
        check(device->CreateShaderResourceView(historyTexture.Get(),&s,&historyView),"Create history view");
        check(device->CreateUnorderedAccessView(historyWriteTexture.Get(),&u,&historyTarget),"Create history target");
        UINT capacity=UINT(renderWidth*renderHeight*samples);''')
s=s.replace('''    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''','''    auto cached=historyView.Get();auto outputHistory=historyTarget.Get();
    context->CSSetShaderResources(5,1,&cached);context->CSSetUnorderedAccessViews(6,1,&outputHistory,nullptr);
    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''',1)
s=s.replace('''    context->CSSetShader(nullptr,nullptr,0);
    auto result=rayView.Get();''','''    context->CSSetShaderResources(5,1,noViews);context->CSSetUnorderedAccessViews(6,1,noTargets,nullptr);
    if(historyFrame) {context->CopyResource(historyTexture.Get(),historyWriteTexture.Get());historyValid=true;}
    context->CSSetShader(nullptr,nullptr,0);
    auto result=rayView.Get();''',1)
s=s.replace('''    lastCompacted=compact;
    Timer* timer=nullptr;''','''    lastCompacted=compact;
    prepareHistory(world,view,palette,compact);
    Timer* timer=nullptr;''')
p.write_text(s,encoding='utf-8')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
s=s.replace('Texture2DArray<float2> rayImage:register(t3);','''Texture2DArray<float2> rayImage:register(t3);
Texture2DArray<float4> historyInput:register(t5);
RWTexture2DArray<float4> historyOutput:register(u6);
cbuffer History : register(b1) {float4 historyInfo;};''')
# Only alter the compute marcher, never the independent pixel-shader oracle.
start=s.index('bool marchJob(');end=s.index('groupshared uint pendingCount',start)
body=s[start:end]
body=body.replace('''        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);''','''        if(historyInfo.w>0 && first<=int(historyInfo.x)) {
            float4 cached=historyInput.Load(int4(position,0));
            float travel=cached.x+((cached.y-historyInfo.y)+(cached.z-historyInfo.z));
            if(cached.w>0 && travel>log2(t)+scale+1 && travel<job.horizon) {
                int oldFirst=citadelStart(travel);
                if(oldFirst<=int(historyInfo.x)) {
                    float dist=citadelDistanceFrom(rd,travel,oldFirst);
                    if(dist<pixel*.70) {
                        rayOutput[position]=float2(travel,1);
                        cached.w+=1;historyOutput[position]=cached;return false;
                    }
                }
            }
        }
        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);''')
start_history=body.index('        if(historyInfo.w>0 && first<=')
end_history=body.index('        float ratio=',start_history)
history_check=body[start_history:end_history].replace('pixel*.70','pixel*.65')
body=body[:start_history]+body[end_history:]
insert=body.index('        if(radius>0 && t>previous)')
body=body[:insert]+history_check+body[insert:]
body=body.replace('''        rayOutput[position]=float2(log2(t)+scale,hit?1:escaped?0:-1);return false;''','''        rayOutput[position]=float2(log2(t)+scale,hit?1:escaped?0:-1);
        if(historyInfo.w>0) historyOutput[position]=float4(0,0,0,0);return false;''')
s=s[:start]+body+s[end:]
s=s.replace('else rayOutput[id]=float2(0,0);','else {rayOutput[id]=float2(0,0);if(historyInfo.w>0) historyOutput[id]=0;}')
s=s.replace('''    rayOutput[position]=float2(log2(upper)+sample.x,1);''','''    float travel=log2(upper)+sample.x;
    rayOutput[position]=float2(travel,1);
    if(historyInfo.w>0) historyOutput[position]=float4(travel,historyInfo.yz,1);''')
p.write_text(s,encoding='utf-8')

p=out/'src/main.cpp';s=p.read_text(encoding='utf-8')
marker='static int frameProfile(App& app,bool exerciseSwitch=false,bool fly=false) {'
s=s.replace(marker,'''static int historyCheck(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"history";std::filesystem::create_directories(dir);
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    std::ofstream report(dir/L"compare.csv");report<<"frame,mean_rgb,max_rgb,pixels_over_16\\n";
    bool exactMatch=true;
    for(int frame=0;frame<120;frame++) {
        app.world.fly(app.view.forward()*(frame<60?1.:-1.),1./60,3.2);app.world.prepare();
        app.renderer.setTracePath(1);app.renderer.render(app.world,app.view,0,false);
        auto cached=app.renderer.pixels();
        if(frame%10==0) app.renderer.capture((dir/(L"cached-"+std::to_wstring(frame)+L".png")).wstring());
        app.renderer.setTracePath(0);app.renderer.render(app.world,app.view,0,false);
        auto exact=app.renderer.pixels();
        if(frame%10==0) app.renderer.capture((dir/(L"exact-"+std::to_wstring(frame)+L".png")).wstring());
        double sum=0;int maximum=0;size_t changed=0;
        for(size_t i=0;i<cached.size();i+=4) {
            int local=0;
            for(int channel=0;channel<3;channel++) {int delta=std::abs(int(cached[i+channel])-int(exact[i+channel]));sum+=delta;local=std::max(local,delta);}
            maximum=std::max(maximum,local);changed+=local>16;
        }
        report<<frame<<','<<sum/(cached.size()/4*3)<<','<<maximum<<','<<changed<<'\\n';report.flush();
        exactMatch=exactMatch && maximum==0;
    }
    return exactMatch?0:2;
}
'''+marker)
s=s.replace('bool flightMode=', 'bool historyMode=std::wstring(commandLine).find(L"--history-check")!=std::wstring::npos;\n    bool flightMode=',1)
s=s.replace('bool benchmark=frameMode','bool benchmark=historyMode||frameMode')
s=s.replace('result=frameMode?','result=historyMode?historyCheck(app):frameMode?')
p.write_text(s,encoding='utf-8')
