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
// minimumScale: lowest traced scale per axis under dynamic resolution. Ultra renders
// up to 5 MP (2980 x 1676 in 4K fullscreen) and needs the lower floor only there.
// capStart: while the pixel cap limits the render size, a new render target (start,
// resize, quality switch) begins at minimumScale. At full scale heavy views would
// take ~35 ms per frame until resolution control has its first timing sample.
struct Profile {const wchar_t* name;int steps,shadows,ao;double pixels,minimumScale;bool capStart;};
inline constexpr int traceLimit=8192;
inline constexpr int gpuTimingSlots=6;
inline constexpr Profile profiles[]={{L"Performance",traceLimit,0,2,1000000,.75,false},{L"Balanced",traceLimit,4,3,2100000,.75,false},{L"Ultra",traceLimit,8,4,5000000,.55,true}};
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
struct alignas(16) FrameConstants {
    Float4 jitter,prevRight,prevUp,prevForward,prevCamera,temporal,output;
};
class Renderer {
    HWND window=nullptr;
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDXGISwapChain1> swap;
    HANDLE frameReady=nullptr;
    UINT swapFlags=0;
    ComPtr<ID3D11Texture2D> backBuffer,sceneTexture;
    ComPtr<ID3D11RenderTargetView> backTarget,sceneTarget;
    ComPtr<ID3D11ShaderResourceView> sceneView;
    ComPtr<ID3D11Buffer> constants,foldConstants,frameConstants;
    // Temporal anti-aliasing: two history targets at render resolution.
    std::array<ComPtr<ID3D11Texture2D>,2> historyTextures;
    std::array<ComPtr<ID3D11RenderTargetView>,2> historyTargets;
    std::array<ComPtr<ID3D11ShaderResourceView>,2> historyViews;
    ComPtr<ID3D11PixelShader> temporalShader,presentTemporalShader;
    int historyIndex=0,jitterIndex=0;
    bool historyValid=false,frameTemporal=false;
    Vec3 previousRight{},previousUp{},previousForward{};
    double previousUnit=0;
    float previousJitterX=0,previousJitterY=0;
    void makeHistory();
    void renderFrame(const World&,const View&,int palette);
    void temporalPass();
    ComPtr<ID3D11VertexShader> vertex;
    ComPtr<ID3D11PixelShader> presentShader;
    std::array<ComPtr<ID3D11PixelShader>,3> shaders;
    std::array<ComPtr<ID3D11PixelShader>,3> vaultShaders;
    std::array<ComPtr<ID3D11PixelShader>,3> gapStatus,gapColor;
    ComPtr<ID3D11PixelShader> gapDepth,gapUltra;
    std::array<ComPtr<ID3D11PixelShader>,3> profileShaders;
    std::array<ComPtr<ID3D11ComputeShader>,3> rayBegin,rayContinue,rayFinish,rayRefine,raySegment;
    std::array<ComPtr<ID3D11PixelShader>,3> rayResolve;
    ComPtr<ID3D11ComputeShader> rayPrepare;
    ComPtr<ID3D11ComputeShader> raySort;
    std::array<ComPtr<ID3D11ComputeShader>,3> coneShaders;
    ComPtr<ID3D11Texture2D> coneTexture;
    ComPtr<ID3D11UnorderedAccessView> coneTarget;
    ComPtr<ID3D11Buffer> bucketBuffer;
    ComPtr<ID3D11UnorderedAccessView> bucketUav;
    ComPtr<ID3D11ShaderResourceView> bucketView;
    ComPtr<ID3D11PixelShader> rayStatusShader;
    bool lastCompacted=false;
    int tracePath=-1;
    ComPtr<ID3D11Texture2D> rayTexture;
    ComPtr<ID3D11UnorderedAccessView> rayTarget,dispatchUav,rayCountUav;
    ComPtr<ID3D11ShaderResourceView> rayView,dispatchView;
    ComPtr<ID3D11Buffer> dispatchBuffer,rayCountBuffer,refineBuffer;
    ComPtr<ID3D11UnorderedAccessView> refineTarget;
    std::array<ComPtr<ID3D11Buffer>,2> rayQueues;
    std::array<ComPtr<ID3D11ShaderResourceView>,2> rayQueueViews;
    std::array<ComPtr<ID3D11UnorderedAccessView>,2> rayQueueTargets;
    int rayWidth=0,rayHeight=0,raySamples=0;
    static constexpr int rayChunk=64;
    static constexpr int maxRayBatches=33;
    // Rays finish long before the 20th batch; empty batches still cost time.
    static constexpr int rayBatches=20,segmentBatch=8;
    std::array<ComPtr<ID3D11Query>,5> passQueries;
    bool measurePasses=false,legacyScheduling=false,measureBatches=false;
    std::array<ComPtr<ID3D11Query>,maxRayBatches*2+1> batchQueries;
    ComPtr<ID3D11Buffer> batchCounts;
    void recordRayBatch(int batch);
    std::array<ComPtr<ID3D11ComputeShader>,4> legacyRays;
    ComPtr<ID3D11Buffer> statsBuffer,statsReadback;
    ComPtr<ID3D11UnorderedAccessView> statsUav;
    UINT statsCount=0;bool collectStats=false;
    void legacyWavefrontPass(int profile);
    std::array<double,4> profileWavePasses(const World&,const View&);
    ComPtr<ID3D11SamplerState> sampler;
    ComPtr<ID3D11RasterizerState> rasterizer;
    ComPtr<ID2D1Factory> d2dFactory;
    ComPtr<IDWriteFactory> writeFactory;
    ComPtr<ID2D1RenderTarget> overlay;
    ComPtr<ID2D1SolidColorBrush> brush;
    std::array<ComPtr<IDWriteTextFormat>,3> fonts;
    struct Timer {ComPtr<ID3D11Query> disjoint,start,end;bool pending=false;uint64_t serial=0;double scale=1;};
    std::array<Timer,gpuTimingSlots> timers;
    int timerCursor=0;
    int width=0,height=0,renderWidth=0,renderHeight=0,quality=1;
    // Traced size per frame. Equals the render (output) size unless dynamic
    // resolution lowers it to keep the GPU frame inside its budget.
    int traceWidth=0,traceHeight=0;
    double dynamicScale=1,latestScale=1;bool freshSample=false,resumePending=true;
    uint64_t resumeSerial=0;
    // First dynamic-resolution scale after a new render target (Profile::capStart).
    double restartScale=1;bool restartPending=false;
    // After a capStart restart resolution control starts at once (slow samples cannot
    // lower the floor) and samples up to climbSerial may raise the scale in one step.
    // Idle resume waits settleFrames=20 as before.
    uint64_t settleFrames=20,climbSerial=0;

    double resolutionScale=1,gpuMs=0,latestGpuMs=0;
    uint64_t frameSerial=0,newestGpuSerial=0;
    bool timerReady=false;
    ComPtr<ID3D11PixelShader> compilePixel(int steps,int shadows,int ao,bool fast,int diagnostic=0,bool cull=true,bool fastCitadel=true,bool cachePrefix=true,bool fastMarch=true,bool compact=true,int kind=1,int samples=0);
    void makeBackBuffer();
    void makeSceneTarget(int w,int h);
    Constants sceneConstants(const World&,const View&,int palette) const;
    void setConstants(const World&,const View&,int palette);
    void scenePass(ID3D11PixelShader*,ID3D11RenderTargetView* target=nullptr);
    void prepareWaveShaders(int profile);
    void prepareWaveTargets();
    void wavefrontPass(int profile);
    void upscaleScene();
    void collectTimings();
    double measure(ID3D11PixelShader*,const World&,const View&,int frames,int waveProfile=-1);
public:
    std::wstring adapterName;
    std::function<void(uint64_t,double)> onGpuTiming;
    Renderer()=default;
    Renderer(const Renderer&)=delete;
    Renderer& operator=(const Renderer&)=delete;
    ~Renderer() {if(frameReady) CloseHandle(frameReady);}
    void initialize(HWND,int,int,bool paced=true);
    bool waitForFrame();
    void setTracePath(int path) {tracePath=path;}
    bool usedCompaction() const {return lastCompacted;}
    bool hasFramePacing() const {return frameReady!=nullptr;}
    void resize(int,int);
    void setQuality(int);
    // Temporal anti-aliasing for the compacted Citadel path (interactive default).
    bool temporalEnabled=true;
    // Dynamic resolution (temporal path only): keep GPU frames near the budget.
    bool dynamicResolution=true;
    // minimumScale 0 uses the profile floor; AURORA_DRS_MIN sets one for all profiles.
    double frameBudgetMs=13.5,minimumScale=0;
    void updateDynamicScale();
    double lowestScale() const {return minimumScale>0?minimumScale:profiles[quality].minimumScale;}
    // The GPU clocks down while the view is idle. Frames right after resuming
    // are slow for that reason alone; keep them out of resolution control and
    // slow-frame capture.
    void markIdle() {resumePending=true;settleFrames=20;}
    bool settledSample(uint64_t serial) const {return serial>=resumeSerial+20;}
    // The flight loop clears this for still frames (nothing moving): a capStart
    // restart then waits for the camera to move, and stills keep full scale.
    bool flying=true;
    // Offline flight tests: feed a synchronously measured GPU frame time.
    void feedFrameTime(double ms) {latestGpuMs=ms;latestScale=dynamicScale;freshSample=true;updateDynamicScale();}
    float temporalBlend=.1f,temporalSharpen=.25f;
    void resetHistory() {historyValid=false;}
    void render(const World&,const View&,int palette,bool timed=true);
    void present();
    double warmUp(const World&,const View&,int palette);
    void beginOverlay(float scale=1);
    void endOverlay();
    void rect(float x,float y,float w,float h,D2D1_COLOR_F color,float radius=0);
    void text(const std::wstring&,float x,float y,float w,float h,int font,D2D1_COLOR_F color);
    void capture(const std::wstring& path);
    std::vector<unsigned char> pixels();
    // Presented back buffer (BGRA8, after temporal resolve and upscaling).
    std::vector<unsigned char> presented();
    double validateField(const World& world,const View& view);
    double fieldProbeMaxPixelError=0;
    double fieldProbeMaxToleranceRatio=0;
    bool validateGaps(const World& world,const View& view,const std::wstring& prefix);
    double profileView(const World& world,const View& view,const std::wstring& prefix,bool captureImages=true);
    std::pair<double,double> benchmark(const World&,const View&);
    void profileRayBatches(const World&,const View&,const std::wstring& path);
    double profileMilliseconds(const World&,const View&,int profile);
    // Complete interactive frame path (trace, shade, upscale), retired one frame at a time.
    std::vector<double> sampleFrames(const World&,const View&,int frames,int warmup);
    // Diagnostics (shaders compiled with TRACE_STATS=1): field calls/iterations
    // per pixel, plus the traced (log depth, status) image of the compacted path.
    std::vector<uint32_t> traceStatistics(const World&,const View&,std::vector<float>* rays=nullptr);
    double frameMilliseconds(const World& world,const View& view) {return measure((world.kind==1?shaders:vaultShaders)[quality].Get(),world,view,1);}
    int benchmarkMaxPixelDifference=0;
    size_t benchmarkPixelsOverTolerance=0;
    double milliseconds() const {return gpuMs;}
    double sampledMilliseconds() const {return latestGpuMs;}
    uint64_t submittedSerial() const {return frameSerial;}
    int sceneWidth() const {return renderWidth;}
    int sceneHeight() const {return renderHeight;}
    int tracedWidth() const {return traceWidth;}
    int tracedHeight() const {return traceHeight;}
    double resolutionFactor() const {return dynamicScale;}
};
}
