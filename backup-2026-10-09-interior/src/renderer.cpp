#include "renderer.h"
#include "shader_data.h"
#include <d3dcompiler.h>
#include <wincodec.h>
#include <chrono>
#include <thread>
#include <fstream>
#include <filesystem>

namespace aurora {
static ComPtr<ID3DBlob> compileShader(const char* entry,const char* target,const D3D_SHADER_MACRO* macros=nullptr) {
    ComPtr<ID3DBlob> result,error;
    HRESULT hr=D3DCompile(shaderSource,sizeof(shaderSource)-1,"fractal.hlsl",macros,nullptr,entry,target,
        D3DCOMPILE_OPTIMIZATION_LEVEL3|D3DCOMPILE_ENABLE_STRICTNESS,0,&result,&error);
    if(FAILED(hr)) throw std::runtime_error(error?static_cast<const char*>(error->GetBufferPointer()):"Shader compilation failed");
    return result;
}
ComPtr<ID3D11PixelShader> Renderer::compilePixel(int steps,int shadows,int ao,bool fast,int diagnostic,bool cull,bool fastCitadel) {
    std::string s=std::to_string(steps),h=std::to_string(shadows),a=std::to_string(ao),d=std::to_string(diagnostic);
    D3D_SHADER_MACRO macros[]={{"MARCH_STEPS",s.c_str()},{"SHADOW_STEPS",h.c_str()},{"AO_STEPS",a.c_str()},{"FAST_FIELD",fast?"1":"0"},{"PIXEL_SAMPLES",shadows>=8?"2":"1"},{"TRACE_DIAGNOSTIC",d.c_str()},{"BOX_CULL",cull?"1":"0"},{"FAST_CITADEL",fastCitadel?"1":"0"},{nullptr,nullptr}};
    auto blob=compileShader("fractalMain","ps_5_0",macros);
    ComPtr<ID3D11PixelShader> shader;
    check(device->CreatePixelShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&shader),"Create fractal shader");
    return shader;
}
void Renderer::initialize(HWND hwnd,int w,int h) {
    window=hwnd;
    ComPtr<IDXGIFactory1> factory;
    check(CreateDXGIFactory1(IID_PPV_ARGS(&factory)),"Create graphics factory");
    ComPtr<IDXGIAdapter1> chosen;
    ComPtr<IDXGIFactory6> modern;
    if(SUCCEEDED(factory.As(&modern))) modern->EnumAdapterByGpuPreference(0,DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,IID_PPV_ARGS(&chosen));
    if(!chosen) {
        SIZE_T biggest=0;
        for(UINT i=0;;i++) {
            ComPtr<IDXGIAdapter1> candidate;
            if(factory->EnumAdapters1(i,&candidate)==DXGI_ERROR_NOT_FOUND) break;
            DXGI_ADAPTER_DESC1 d{};candidate->GetDesc1(&d);
            if(!(d.Flags&DXGI_ADAPTER_FLAG_SOFTWARE) && (!chosen || d.DedicatedVideoMemory>biggest)) {chosen=candidate;biggest=d.DedicatedVideoMemory;}
        }
    }
    if(!chosen) throw std::runtime_error("No hardware graphics adapter found");
    DXGI_ADAPTER_DESC1 adapter{};chosen->GetDesc1(&adapter);adapterName=adapter.Description;
    D3D_FEATURE_LEVEL levels[]={D3D_FEATURE_LEVEL_11_1,D3D_FEATURE_LEVEL_11_0},actual;
    HRESULT hr=D3D11CreateDevice(chosen.Get(),D3D_DRIVER_TYPE_UNKNOWN,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        levels,2,D3D11_SDK_VERSION,&device,&actual,&context);
    if(hr==E_INVALIDARG) hr=D3D11CreateDevice(chosen.Get(),D3D_DRIVER_TYPE_UNKNOWN,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        levels+1,1,D3D11_SDK_VERSION,&device,&actual,&context);
    check(hr,"Create Direct3D 11 device");
    ComPtr<IDXGIDevice1> dxgiDevice;
    if(SUCCEEDED(device.As(&dxgiDevice))) dxgiDevice->SetMaximumFrameLatency(1);
    ComPtr<IDXGIFactory2> factory2;check(factory.As(&factory2),"Get swap chain factory");
    DXGI_SWAP_CHAIN_DESC1 desc{};
    desc.Width=static_cast<UINT>(w);desc.Height=static_cast<UINT>(h);desc.Format=DXGI_FORMAT_B8G8R8A8_UNORM;
    desc.SampleDesc.Count=1;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.BufferCount=2;
    desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;desc.Scaling=DXGI_SCALING_STRETCH;desc.AlphaMode=DXGI_ALPHA_MODE_IGNORE;
    check(factory2->CreateSwapChainForHwnd(device.Get(),window,&desc,nullptr,nullptr,&swap),"Create swap chain");
    factory->MakeWindowAssociation(window,DXGI_MWA_NO_ALT_ENTER);
    auto v=compileShader("vertexMain","vs_5_0");
    check(device->CreateVertexShader(v->GetBufferPointer(),v->GetBufferSize(),nullptr,&vertex),"Create fullscreen vertex shader");
    auto p=compileShader("presentMain","ps_5_0");
    check(device->CreatePixelShader(p->GetBufferPointer(),p->GetBufferSize(),nullptr,&presentShader),"Create upscaler");
    for(int i=0;i<3;i++) shaders[i]=compilePixel(profiles[i].steps,profiles[i].shadows,profiles[i].ao,true);
    D3D11_BUFFER_DESC bd{};bd.ByteWidth=sizeof(Constants);bd.Usage=D3D11_USAGE_DYNAMIC;
    bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;bd.CPUAccessFlags=D3D11_CPU_ACCESS_WRITE;
    check(device->CreateBuffer(&bd,nullptr,&constants),"Create scene constants");
    D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
    check(device->CreateSamplerState(&sd,&sampler),"Create upscaling sampler");
    D3D11_RASTERIZER_DESC rd{};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;rd.DepthClipEnable=TRUE;
    check(device->CreateRasterizerState(&rd,&rasterizer),"Create rasterizer");
    check(D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED,d2dFactory.GetAddressOf()),"Create text drawing factory");
    check(DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED,__uuidof(IDWriteFactory),reinterpret_cast<IUnknown**>(writeFactory.GetAddressOf())),"Create font factory");
    const float sizes[]={13,16,27};
    for(int i=0;i<3;i++) check(writeFactory->CreateTextFormat(L"Segoe UI",nullptr,i==2?DWRITE_FONT_WEIGHT_SEMI_BOLD:DWRITE_FONT_WEIGHT_NORMAL,
        DWRITE_FONT_STYLE_NORMAL,DWRITE_FONT_STRETCH_NORMAL,sizes[i],L"en-us",&fonts[i]),"Create font");
    timerReady=true;
    for(auto& timer:timers) {
        D3D11_QUERY_DESC q{D3D11_QUERY_TIMESTAMP_DISJOINT,0};
        if(FAILED(device->CreateQuery(&q,&timer.disjoint))) {timerReady=false;break;}
        q.Query=D3D11_QUERY_TIMESTAMP;
        if(FAILED(device->CreateQuery(&q,&timer.start)) || FAILED(device->CreateQuery(&q,&timer.end))) {timerReady=false;break;}
    }
    width=w;height=h;makeBackBuffer();setQuality(1);
}
void Renderer::makeBackBuffer() {
    check(swap->GetBuffer(0,IID_PPV_ARGS(&backBuffer)),"Get swap chain buffer");
    check(device->CreateRenderTargetView(backBuffer.Get(),nullptr,&backTarget),"Create back target");
    ComPtr<IDXGISurface> surface;check(backBuffer.As(&surface),"Get overlay surface");
    auto props=D2D1::RenderTargetProperties(D2D1_RENDER_TARGET_TYPE_DEFAULT,
        D2D1::PixelFormat(DXGI_FORMAT_UNKNOWN,D2D1_ALPHA_MODE_PREMULTIPLIED),96,96);
    check(d2dFactory->CreateDxgiSurfaceRenderTarget(surface.Get(),&props,&overlay),"Create Direct2D overlay");
    check(overlay->CreateSolidColorBrush(D2D1::ColorF(1,1,1),&brush),"Create text brush");
    overlay->SetTextAntialiasMode(D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE);
}
void Renderer::resize(int w,int h) {
    if(w<=0 || h<=0 || (w==width && h==height)) return;
    context->OMSetRenderTargets(0,nullptr,nullptr);
    overlay.Reset();brush.Reset();backTarget.Reset();backBuffer.Reset();
    context->Flush();
    check(swap->ResizeBuffers(0,w,h,DXGI_FORMAT_UNKNOWN,0),"Resize swap chain");
    width=w;height=h;makeBackBuffer();
    double cap=std::min(1.,std::sqrt(profiles[quality].pixels/(double(w)*h)));
    resolutionScale=cap;
    makeSceneTarget(std::max(64,int(width*resolutionScale)),std::max(64,int(height*resolutionScale)));
}
void Renderer::makeSceneTarget(int w,int h) {
    w=std::max(64,w&~1);h=std::max(64,h&~1);
    if(w==renderWidth && h==renderHeight) return;
    ID3D11ShaderResourceView* none=nullptr;context->PSSetShaderResources(0,1,&none);
    context->OMSetRenderTargets(0,nullptr,nullptr);
    sceneView.Reset();sceneTarget.Reset();sceneTexture.Reset();
    D3D11_TEXTURE2D_DESC d{};d.Width=w;d.Height=h;d.MipLevels=1;d.ArraySize=1;
    d.Format=DXGI_FORMAT_R8G8B8A8_UNORM;d.SampleDesc.Count=1;d.Usage=D3D11_USAGE_DEFAULT;
    d.BindFlags=D3D11_BIND_RENDER_TARGET|D3D11_BIND_SHADER_RESOURCE;
    check(device->CreateTexture2D(&d,nullptr,&sceneTexture),"Create fractal render texture");
    check(device->CreateRenderTargetView(sceneTexture.Get(),nullptr,&sceneTarget),"Create fractal render target");
    check(device->CreateShaderResourceView(sceneTexture.Get(),nullptr,&sceneView),"Create fractal texture view");
    renderWidth=w;renderHeight=h;
}
void Renderer::setQuality(int q) {
    quality=std::clamp(q,0,2);gpuMs=latestGpuMs=0;newestGpuSerial=frameSerial;
    resolutionScale=std::min(1.,std::sqrt(profiles[quality].pixels/(double(width)*height)));
    makeSceneTarget(int(width*resolutionScale),int(height*resolutionScale));
}
static Float4 asFloat(Vec3 v) {return {float(v.x),float(v.y),float(v.z),0};}
void Renderer::setConstants(const World& world,const View& view,int palette) {
    Constants data{};
    data.render={float(renderWidth),float(renderHeight),float(world.worldScale),float(world.level%1000)};
    data.right=asFloat(view.right());data.up=asFloat(view.up());data.forward=asFloat(view.forward());
    data.counts={world.depth,world.parentCount,palette,world.kind};
    data.fractalParameters=asFloat(world.juliaConstant);data.fractalParameters.w=float(world.juliaScale);
    if(world.kind==1) {
        data.reference=world.citadel.gpu();auto bounds=world.citadel.cameraBounds();
        data.boundsLow=bounds[0];data.boundsHigh=bounds[1];
    }
    data.orbit=world.orbit;data.octaves=world.octaves;data.parents=world.parentData;data.parentMeta=world.parentMeta;
    D3D11_MAPPED_SUBRESOURCE mapped{};
    check(context->Map(constants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Update camera constants");
    memcpy(mapped.pData,&data,sizeof(data));context->Unmap(constants.Get(),0);
    ID3D11Buffer* buffer=constants.Get();context->PSSetConstantBuffers(0,1,&buffer);
}
void Renderer::scenePass(ID3D11PixelShader* shader,ID3D11RenderTargetView* output) {
    ID3D11ShaderResourceView* none=nullptr;context->PSSetShaderResources(0,1,&none);
    context->IASetInputLayout(nullptr);context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    context->VSSetShader(vertex.Get(),nullptr,0);context->PSSetShader(shader,nullptr,0);
    context->GSSetShader(nullptr,nullptr,0);context->RSSetState(rasterizer.Get());
    context->OMSetBlendState(nullptr,nullptr,0xffffffff);context->OMSetDepthStencilState(nullptr,0);
    D3D11_VIEWPORT vp{0,0,float(renderWidth),float(renderHeight),0,1};context->RSSetViewports(1,&vp);
    ID3D11RenderTargetView* target=output?output:sceneTarget.Get();context->OMSetRenderTargets(1,&target,nullptr);
    context->Draw(3,0);
}
void Renderer::collectTimings() {
    if(timerReady) for(auto& timer:timers) {
        if(!timer.pending) continue;
        D3D11_QUERY_DATA_TIMESTAMP_DISJOINT disjoint{};
        if(context->GetData(timer.disjoint.Get(),&disjoint,sizeof(disjoint),D3D11_ASYNC_GETDATA_DONOTFLUSH)!=S_OK) continue;
        UINT64 start=0,end=0;
        if(context->GetData(timer.start.Get(),&start,sizeof(start),D3D11_ASYNC_GETDATA_DONOTFLUSH)!=S_OK ||
           context->GetData(timer.end.Get(),&end,sizeof(end),D3D11_ASYNC_GETDATA_DONOTFLUSH)!=S_OK) continue;
        timer.pending=false;
        if(!disjoint.Disjoint && disjoint.Frequency && end>start) {
            double sample=double(end-start)*1000/disjoint.Frequency;
            if(sample>0 && std::isfinite(sample) && timer.serial>newestGpuSerial) {
                latestGpuMs=sample;
                gpuMs=gpuMs==0?sample:gpuMs*.85+sample*.15;
                newestGpuSerial=timer.serial;
            }
        }
    }
}
void Renderer::render(const World& world,const View& view,int palette,bool timed) {
    setConstants(world,view,palette);collectTimings();
    Timer* timer=nullptr;
    if(timed && timerReady && !timers[timerCursor].pending) {
        timer=&timers[timerCursor];timer->serial=++frameSerial;
        context->Begin(timer->disjoint.Get());context->End(timer->start.Get());
    }
    scenePass(shaders[quality].Get());
    upscaleScene();
    if(timer) {context->End(timer->end.Get());context->End(timer->disjoint.Get());timer->pending=true;timerCursor=(timerCursor+1)%int(timers.size());}
}
void Renderer::upscaleScene() {
    ID3D11RenderTargetView* target=backTarget.Get();context->OMSetRenderTargets(1,&target,nullptr);
    D3D11_VIEWPORT vp{0,0,float(width),float(height),0,1};context->RSSetViewports(1,&vp);
    context->PSSetShader(presentShader.Get(),nullptr,0);
    ID3D11ShaderResourceView* image=sceneView.Get();context->PSSetShaderResources(0,1,&image);
    ID3D11SamplerState* filter=sampler.Get();context->PSSetSamplers(0,1,&filter);
    context->Draw(3,0);
}
void Renderer::present() {check(swap->Present(1,0),"Present frame");}
void Renderer::beginOverlay(float scale) {context->OMSetRenderTargets(0,nullptr,nullptr);overlay->BeginDraw();overlay->SetTransform(D2D1::Matrix3x2F::Scale(scale,scale));}
void Renderer::endOverlay() {check(overlay->EndDraw(),"Draw flight controls");}
void Renderer::rect(float x,float y,float w,float h,D2D1_COLOR_F color,float radius) {
    brush->SetColor(color);auto r=D2D1::RectF(x,y,x+w,y+h);
    if(radius>0) overlay->FillRoundedRectangle(D2D1::RoundedRect(r,radius,radius),brush.Get());
    else overlay->FillRectangle(r,brush.Get());
}
void Renderer::text(const std::wstring& label,float x,float y,float w,float h,int font,D2D1_COLOR_F color) {
    brush->SetColor(color);overlay->DrawText(label.c_str(),UINT32(label.size()),fonts[std::clamp(font,0,2)].Get(),D2D1::RectF(x,y,x+w,y+h),brush.Get());
}
void Renderer::capture(const std::wstring& path) {
    D3D11_TEXTURE2D_DESC d{};backBuffer->GetDesc(&d);d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;d.MiscFlags=0;
    ComPtr<ID3D11Texture2D> staging;check(device->CreateTexture2D(&d,nullptr,&staging),"Create screenshot staging texture");
    context->CopyResource(staging.Get(),backBuffer.Get());
    D3D11_MAPPED_SUBRESOURCE map{};check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&map),"Read screenshot");
    try {
        ComPtr<IWICImagingFactory> wic;check(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&wic)),"Create image encoder");
        ComPtr<IWICStream> stream;check(wic->CreateStream(&stream),"Create image stream");check(stream->InitializeFromFilename(path.c_str(),GENERIC_WRITE),"Open screenshot");
        ComPtr<IWICBitmapEncoder> encoder;check(wic->CreateEncoder(GUID_ContainerFormatPng,nullptr,&encoder),"Create PNG encoder");check(encoder->Initialize(stream.Get(),WICBitmapEncoderNoCache),"Initialize PNG encoder");
        ComPtr<IWICBitmapFrameEncode> frame;check(encoder->CreateNewFrame(&frame,nullptr),"Create PNG frame");check(frame->Initialize(nullptr),"Initialize PNG frame");
        check(frame->SetSize(width,height),"Set PNG size");WICPixelFormatGUID format=GUID_WICPixelFormat32bppBGRA;check(frame->SetPixelFormat(&format),"Set PNG format");
        if(format!=GUID_WICPixelFormat32bppBGRA) throw std::runtime_error("PNG encoder rejected BGRA pixels");
        check(frame->WritePixels(height,map.RowPitch,map.RowPitch*height,static_cast<BYTE*>(map.pData)),"Write screenshot pixels");
        check(frame->Commit(),"Commit PNG frame");check(encoder->Commit(),"Commit PNG file");
    } catch(...) {context->Unmap(staging.Get(),0);throw;}
    context->Unmap(staging.Get(),0);
}
std::vector<unsigned char> Renderer::pixels() {
    D3D11_TEXTURE2D_DESC d{};sceneTexture->GetDesc(&d);d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> staging;check(device->CreateTexture2D(&d,nullptr,&staging),"Create readback texture");
    context->CopyResource(staging.Get(),sceneTexture.Get());D3D11_MAPPED_SUBRESOURCE m{};
    check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&m),"Read scene pixels");
    std::vector<unsigned char> result(size_t(d.Width)*d.Height*4);
    for(UINT y=0;y<d.Height;y++) memcpy(result.data()+size_t(y)*d.Width*4,static_cast<unsigned char*>(m.pData)+size_t(y)*m.RowPitch,size_t(d.Width)*4);
    context->Unmap(staging.Get(),0);return result;
}
double Renderer::validateField(const World& world,const View& view) {
    setConstants(world,view,0);
    auto blob=compileShader("probeMain","ps_5_0");ComPtr<ID3D11PixelShader> probe;
    check(device->CreatePixelShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&probe),"Create probe shader");
    D3D11_TEXTURE2D_DESC d{};d.Width=512;d.Height=1;d.MipLevels=d.ArraySize=1;d.SampleDesc.Count=1;
    d.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_RENDER_TARGET;
    ComPtr<ID3D11Texture2D> target,staging;ComPtr<ID3D11RenderTargetView> rtv;
    check(device->CreateTexture2D(&d,nullptr,&target),"Create field probe target");
    check(device->CreateRenderTargetView(target.Get(),nullptr,&rtv),"Create probe RTV");
    context->IASetInputLayout(nullptr);context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    context->VSSetShader(vertex.Get(),nullptr,0);context->PSSetShader(probe.Get(),nullptr,0);
    context->RSSetState(rasterizer.Get());D3D11_VIEWPORT vp{0,0,512,1,0,1};context->RSSetViewports(1,&vp);
    ID3D11RenderTargetView* output=rtv.Get();context->OMSetRenderTargets(1,&output,nullptr);context->Draw(3,0);
    d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    check(device->CreateTexture2D(&d,nullptr,&staging),"Create field readback");context->CopyResource(staging.Get(),target.Get());
    D3D11_MAPPED_SUBRESOURCE m{};check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&m),"Read field probes");
    double maxError=0;
    for(int i=0;i<512;i++) {
        Vec3 offset{double((i*13)%23-11)*.125,double((i*7)%19-9)*.125,double((i*17)%29-14)*.125};
        double scale=std::exp2(double(i/32)*3-9),expected=world.citadel.distance(offset*scale)/scale;
        float actual=static_cast<float*>(m.pData)[i*4];
        double error=std::isfinite(actual)?std::abs(double(actual)-expected)/std::max(1e-4,expected):1e20;
        maxError=std::max(maxError,error);
    }
    context->Unmap(staging.Get(),0);context->OMSetRenderTargets(0,nullptr,nullptr);
    return maxError;
}
bool Renderer::validateGaps(const World& world,const View& view,const std::wstring& prefix) {
    setConstants(world,view,0);
    std::ofstream report(std::filesystem::path(prefix+L"-rays.txt"));
    report<<"resolution "<<renderWidth<<'x'<<renderHeight<<'\n';
    int budgets[]={224,traceLimit,traceLimit*2};
    std::array<std::vector<unsigned char>,3> status;
    bool passed=true;
    for(int index=0;index<3;index++) {
        int steps=budgets[index];
        if(!gapStatus[index]) gapStatus[index]=compilePixel(steps,4,3,true,1,index!=2);
        scenePass(gapStatus[index].Get());auto data=pixels();size_t pending=0,hits=0,escaped=0;
        for(size_t i=0;i<data.size();i+=4) {pending+=data[i]>128;hits+=data[i+1]>128;escaped+=data[i+2]>128;}
        report<<steps<<" steps: pending "<<pending<<", hit "<<hits<<", escaped "<<escaped<<'\n';report.flush();
        if(index==1 && pending) passed=false;
        status[index]=std::move(data);
        upscaleScene();capture(prefix+L"-"+std::to_wstring(steps)+L"-status.png");
        if(!gapColor[index]) gapColor[index]=compilePixel(steps,4,3,true,0,index!=2);
        scenePass(gapColor[index].Get());upscaleScene();capture(prefix+L"-"+std::to_wstring(steps)+L".png");
        report<<"gpu_ms "<<measure(gapColor[index].Get(),world,view,index==2?1:12)<<'\n';
    }
    // Read the uncropped hit depth, so the independent bound test also checks
    // cone hits beyond a box exit, not just rays which miss the whole box.
    if(!gapDepth) gapDepth=compilePixel(traceLimit*2,4,3,true,2,false);
    D3D11_TEXTURE2D_DESC depthDesc{};depthDesc.Width=renderWidth;depthDesc.Height=renderHeight;
    depthDesc.MipLevels=depthDesc.ArraySize=depthDesc.SampleDesc.Count=1;
    depthDesc.Format=DXGI_FORMAT_R32_FLOAT;depthDesc.Usage=D3D11_USAGE_DEFAULT;depthDesc.BindFlags=D3D11_BIND_RENDER_TARGET;
    ComPtr<ID3D11Texture2D> depthTarget,depthReadback;ComPtr<ID3D11RenderTargetView> depthView;
    check(device->CreateTexture2D(&depthDesc,nullptr,&depthTarget),"Create ray depth target");
    check(device->CreateRenderTargetView(depthTarget.Get(),nullptr,&depthView),"Create ray depth view");
    scenePass(gapDepth.Get(),depthView.Get());
    depthDesc.Usage=D3D11_USAGE_STAGING;depthDesc.BindFlags=0;depthDesc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    check(device->CreateTexture2D(&depthDesc,nullptr,&depthReadback),"Create ray depth readback");
    context->CopyResource(depthReadback.Get(),depthTarget.Get());D3D11_MAPPED_SUBRESOURCE depthMap{};
    check(context->Map(depthReadback.Get(),0,D3D11_MAP_READ,0,&depthMap),"Read ray depths");
    std::vector<float> depths(size_t(renderWidth)*renderHeight);
    for(int y=0;y<renderHeight;y++) memcpy(depths.data()+size_t(y)*renderWidth,static_cast<unsigned char*>(depthMap.pData)+size_t(y)*depthMap.RowPitch,renderWidth*sizeof(float));
    context->Unmap(depthReadback.Get(),0);
    // Double-precision slab test, independent of the shader's float log-space
    // clipping. Recover the planes from the reference orbit because the root
    // camera has already lost its sub-ulp displacement at extreme zoom. The old
    // cone-based hit tolerance could colour pixels whose centre ray missed the
    // entire object; accept their removal only when this separate test proves it.
    auto outsideBox=[&](size_t pixel) {
        double x=(2*(double(pixel%renderWidth)+.5)-renderWidth)/renderHeight;
        double y=(renderHeight-2*(double(pixel/renderWidth)+.5))/renderHeight;
        Vec3 ray=(view.right()*x+view.up()*y+view.forward()*1.85).unit();
        double enter=0,leave=1e300,direction[]={ray.x,ray.y,ray.z};
        for(int axis=0;axis<3;axis++) {
            auto low=world.citadel.relativePlane(axis,0),high=world.citadel.relativePlane(axis,1);
            double lo=low.first*std::exp2(low.second),hi=high.first*std::exp2(high.second);
            if(std::abs(direction[axis])<1e-30) {if(lo>0 || hi<0) return true;continue;}
            double a=lo/direction[axis],b=hi/direction[axis];
            enter=std::max(enter,std::min(a,b));leave=std::min(leave,std::max(a,b));
        }
        if(enter>leave) return true;
        double logLeave=std::log2(leave)-world.citadel.logUnit;
        // A tiny log-space allowance covers the independent CPU/GPU ray rounding.
        bool beyond=depths[pixel]>logLeave+1e-4;
        if(!beyond) report<<"interior_difference "<<pixel%renderWidth<<','<<pixel/renderWidth<<" depth "<<depths[pixel]<<" exit "<<logLeave<<'\n';
        return beyond;
    };
    size_t recovered=0,changed=0,referenceDifference=0,exteriorPixels=0,completedEscapes=0;
    for(size_t i=0;i<status[0].size();i+=4) {
        recovered+=status[0][i]>128 && status[1][i+1]>128;
        changed+=status[0][i]<128 && (status[0][i+1]!=status[1][i+1] || status[0][i+2]!=status[1][i+2]);
        bool different=status[1][i]!=status[2][i] || status[1][i+1]!=status[2][i+1] || status[1][i+2]!=status[2][i+2];
        if(different && status[1][i+2]>128 && status[2][i]>128) completedEscapes++;
        else if(different && status[1][i+2]>128 && outsideBox(i/4)) exteriorPixels++;
        else referenceDifference+=different;
    }
    passed=passed && !changed && !referenceDifference;
    report<<"restored_surface_pixels "<<recovered<<"\nchanged_resolved_rays "<<changed<<"\nreference_difference "<<referenceDifference<<"\nverified_exterior_pixels "<<exteriorPixels<<"\ncompleted_escape_rays "<<completedEscapes<<'\n';
    for(int profile=0;profile<3;profile++) {
        scenePass(shaders[profile].Get());auto data=pixels();size_t unfinished=0;
        for(size_t i=3;i<data.size();i+=4) unfinished+=data[i]<128;
        passed=passed && !unfinished;
        report<<"profile "<<profile<<": unfinished "<<unfinished<<'\n';
    }
    report<<"passed "<<passed<<'\n';return passed;
}
double Renderer::profileView(const World& world,const View& view,const std::wstring& prefix,bool captureImages) {
    if(!profileShaders[0]) {
        profileShaders[0]=compilePixel(traceLimit,4,3,true,0,true,false);
        profileShaders[1]=compilePixel(traceLimit,4,3,true,0,true,true);
        profileShaders[2]=compilePixel(traceLimit,4,3,true,3,true,false);
    }
    auto baseline=profileShaders[0],optimized=profileShaders[1];
    setConstants(world,view,0);scenePass(baseline.Get());auto before=pixels();if(captureImages) {upscaleScene();capture(prefix+L"-before.png");}
    scenePass(optimized.Get());auto after=pixels();if(captureImages) {upscaleScene();capture(prefix+L"-after.png");}
    double error=0;size_t different=0,unfinished=0;int maximum=0;
    for(size_t i=0;i<after.size();i+=4) {
        int e=0;for(int c=0;c<3;c++) e=std::max(e,std::abs(int(before[i+c])-int(after[i+c])));
        error+=e;maximum=std::max(maximum,e);different+=e>16;unfinished+=after[i+3]<128;
    }
    double oldMs=measure(baseline.Get(),world,view,3),newMs=measure(optimized.Get(),world,view,3);
    D3D11_TEXTURE2D_DESC d{};d.Width=renderWidth;d.Height=renderHeight;d.MipLevels=d.ArraySize=d.SampleDesc.Count=1;
    d.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_RENDER_TARGET;
    ComPtr<ID3D11Texture2D> target,readback;ComPtr<ID3D11RenderTargetView> targetView;
    check(device->CreateTexture2D(&d,nullptr,&target),"Create profiling target");
    check(device->CreateRenderTargetView(target.Get(),nullptr,&targetView),"Create profiling view");
    scenePass(profileShaders[2].Get(),targetView.Get());
    d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    check(device->CreateTexture2D(&d,nullptr,&readback),"Create profiling readback");context->CopyResource(readback.Get(),target.Get());
    D3D11_MAPPED_SUBRESOURCE m{};check(context->Map(readback.Get(),0,D3D11_MAP_READ,0,&m),"Read profiling counts");
    double totalSteps=0,totalIterations=0;size_t slow=0;float maxSteps=0;
    for(int y=0;y<renderHeight;y++) {
        const float* row=reinterpret_cast<const float*>(static_cast<unsigned char*>(m.pData)+size_t(y)*m.RowPitch);
        for(int x=0;x<renderWidth;x++) {totalSteps+=row[x*4];totalIterations+=row[x*4+1];slow+=row[x*4]>1000;maxSteps=std::max(maxSteps,row[x*4]);}
    }
    context->Unmap(readback.Get(),0);
    std::ofstream report(std::filesystem::path(prefix+L".json"));
    report<<"{\"zoom\":"<<world.zoomLog10<<",\"width\":"<<renderWidth<<",\"height\":"<<renderHeight
        <<",\"before_ms\":"<<oldMs<<",\"after_ms\":"<<newMs<<",\"mean_channel_error\":"<<error/(after.size()/4)
        <<",\"max_channel_error\":"<<maximum<<",\"changed_over_16\":"<<different<<",\"unfinished\":"<<unfinished
        <<",\"mean_steps\":"<<totalSteps/(renderWidth*renderHeight)<<",\"mean_iterations\":"<<totalIterations/(renderWidth*renderHeight)
        <<",\"rays_over_1000\":"<<slow<<",\"max_steps\":"<<maxSteps<<"}\n";
    return oldMs;
}
double Renderer::measure(ID3D11PixelShader* shader,const World& world,const View& view,int frames) {
    if(!timerReady) throw std::runtime_error("GPU timestamp queries unavailable");
    setConstants(world,view,0);
    for(int i=0;i<(frames==1?0:4);i++) scenePass(shader);
    Timer timer;D3D11_QUERY_DESC desc{D3D11_QUERY_TIMESTAMP_DISJOINT,0};
    check(device->CreateQuery(&desc,&timer.disjoint),"Create benchmark timer");desc.Query=D3D11_QUERY_TIMESTAMP;
    check(device->CreateQuery(&desc,&timer.start),"Create start timestamp");check(device->CreateQuery(&desc,&timer.end),"Create end timestamp");
    context->Begin(timer.disjoint.Get());context->End(timer.start.Get());
    for(int i=0;i<frames;i++) scenePass(shader);
    context->End(timer.end.Get());context->End(timer.disjoint.Get());context->Flush();
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
    D3D11_QUERY_DATA_TIMESTAMP_DISJOINT disjoint{};
    while(context->GetData(timer.disjoint.Get(),&disjoint,sizeof(disjoint),0)!=S_OK) {
        if(std::chrono::steady_clock::now()>deadline) throw std::runtime_error("GPU benchmark timed out");
        Sleep(1);
    }
    UINT64 start=0,end=0;check(context->GetData(timer.start.Get(),&start,sizeof(start),0),"Read start timestamp");check(context->GetData(timer.end.Get(),&end,sizeof(end),0),"Read end timestamp");
    if(disjoint.Disjoint || !disjoint.Frequency) throw std::runtime_error("GPU clock changed during benchmark; retry");
    return double(end-start)*1000/disjoint.Frequency/frames;
}
std::pair<double,double> Renderer::benchmark(const World& world,const View& view) {
    makeSceneTarget(1280,720);
    auto baseline=compilePixel(132,8,3,false),optimized=compilePixel(132,8,3,true);
    // Same camera, resolution, ray budget and lighting; only exact culling differs.
    double original=0,fast=0;
    for(int i=0;i<3;i++) {
        if(i%2) {fast+=measure(optimized.Get(),world,view,24);original+=measure(baseline.Get(),world,view,24);}
        else {original+=measure(baseline.Get(),world,view,24);fast+=measure(optimized.Get(),world,view,24);}
    }
    setConstants(world,view,0);scenePass(baseline.Get());auto reference=pixels();
    scenePass(optimized.Get());auto result=pixels();
    benchmarkMaxPixelDifference=0;benchmarkPixelsOverTolerance=0;
    for(size_t i=0;i<result.size();i+=4) {
        int error=0;for(int c=0;c<3;c++) error=std::max(error,std::abs(int(reference[i+c])-int(result[i+c])));
        benchmarkMaxPixelDifference=std::max(benchmarkMaxPixelDifference,error);
        if(error>1) benchmarkPixelsOverTolerance++;
    }
    return {original/3,fast/3};
}
double Renderer::profileMilliseconds(const World& world,const View& view,int profile) {
    makeSceneTarget(1280,720);
    // Warm up the selected scene before measuring sustained GPU pass time.
    measure(shaders.at(profile).Get(),world,view,48);
    double total=0;
    for(int i=0;i<3;i++) total+=measure(shaders.at(profile).Get(),world,view,32);
    return total/3;
}
}
