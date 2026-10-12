#pragma once
#include "world.h"
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_6.h>
#include <d2d1.h>
#include <dwrite.h>
#include <wrl/client.h>
#include <string>
#include <functional>

namespace aurora {
using Microsoft::WRL::ComPtr;
inline void check(HRESULT hr,const char* operation) {if(FAILED(hr)) throw std::runtime_error(std::string(operation)+" failed ("+std::to_string(static_cast<unsigned>(hr))+")");}
struct Profile {const wchar_t* name;int steps,shadows,ao;double pixels;};
inline constexpr int traceLimit=8192;
inline constexpr Profile profiles[]={{L"Performance",traceLimit,0,2,1000000},{L"Balanced",traceLimit,4,3,2100000},{L"Ultra",traceLimit,8,4,5000000}};
struct alignas(16) Constants {
    Float4 render,right,up,forward;
    std::array<int,4> counts{};
    Float4 fractalParameters;
    std::array<Float4,18> orbit,octaves;
    std::array<Float4,48> parents,parentMeta;
    std::array<Citadel::GpuSample,Citadel::capacity> reference;
    Float4 boundsLow,boundsHigh;
};
static_assert(sizeof(Constants)%16==0 && sizeof(Constants)<=65536,"D3D11 constant buffer layout");
class Renderer {
    HWND window=nullptr;
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDXGISwapChain1> swap;
    ComPtr<ID3D11Texture2D> backBuffer,sceneTexture;
    ComPtr<ID3D11RenderTargetView> backTarget,sceneTarget;
    ComPtr<ID3D11ShaderResourceView> sceneView;
    ComPtr<ID3D11UnorderedAccessView> sceneUav,rayCounterUav;
    ComPtr<ID3D11Buffer> rayCounter;
    ComPtr<ID3D11ComputeShader> persistentShader;
    ComPtr<ID3D11Buffer> constants;
    ComPtr<ID3D11VertexShader> vertex;
    ComPtr<ID3D11PixelShader> presentShader;
    std::array<ComPtr<ID3D11PixelShader>,3> shaders;
    std::array<ComPtr<ID3D11PixelShader>,3> gapStatus,gapColor;
    ComPtr<ID3D11PixelShader> gapDepth;
    std::array<ComPtr<ID3D11PixelShader>,3> profileShaders;
    ComPtr<ID3D11SamplerState> sampler;
    ComPtr<ID3D11RasterizerState> rasterizer;
    ComPtr<ID2D1Factory> d2dFactory;
    ComPtr<IDWriteFactory> writeFactory;
    ComPtr<ID2D1RenderTarget> overlay;
    ComPtr<ID2D1SolidColorBrush> brush;
    std::array<ComPtr<IDWriteTextFormat>,3> fonts;
    struct Timer {ComPtr<ID3D11Query> disjoint,start,end;bool pending=false;uint64_t serial=0;};
    std::array<Timer,6> timers;
    int timerCursor=0;
    int width=0,height=0,renderWidth=0,renderHeight=0,quality=1;
    double resolutionScale=1,gpuMs=0,latestGpuMs=0;
    uint64_t frameSerial=0,newestGpuSerial=0;
    bool timerReady=false;
    ComPtr<ID3D11PixelShader> compilePixel(int steps,int shadows,int ao,bool fast,int diagnostic=0,bool cull=true,bool fastCitadel=true,bool cachePrefix=true,bool fastMarch=true);
    void makeBackBuffer();
    void makeSceneTarget(int w,int h);
    void setConstants(const World&,const View&,int palette);
    void scenePass(ID3D11PixelShader*,ID3D11RenderTargetView* target=nullptr);
    void persistentPass();
    void upscaleScene();
    void collectTimings();
    double measure(ID3D11PixelShader*,const World&,const View&,int frames,bool persistent=false);
public:
    std::wstring adapterName;
    void initialize(HWND,int,int);
    void resize(int,int);
    void setQuality(int);
    void render(const World&,const View&,int palette,bool timed=true);
    void present();
    void beginOverlay(float scale=1);
    void endOverlay();
    void rect(float x,float y,float w,float h,D2D1_COLOR_F color,float radius=0);
    void text(const std::wstring&,float x,float y,float w,float h,int font,D2D1_COLOR_F color);
    void capture(const std::wstring& path);
    std::vector<unsigned char> pixels();
    double validateField(const World& world,const View& view);
    bool validateGaps(const World& world,const View& view,const std::wstring& prefix);
    double profileView(const World& world,const View& view,const std::wstring& prefix,bool captureImages=true);
    std::pair<double,double> benchmark(const World&,const View&);
    double profileMilliseconds(const World&,const View&,int profile);
    double frameMilliseconds(const World& world,const View& view) {return measure(shaders[quality].Get(),world,view,1);}
    int benchmarkMaxPixelDifference=0;
    size_t benchmarkPixelsOverTolerance=0;
    double milliseconds() const {return gpuMs;}
    double sampledMilliseconds() const {return latestGpuMs;}
    int sceneWidth() const {return renderWidth;}
    int sceneHeight() const {return renderHeight;}
};
}
