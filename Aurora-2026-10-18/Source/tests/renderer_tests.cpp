#include "renderer.h"
#include <objbase.h>
#include <iostream>
using namespace aurora;
static void require(bool yes,const char* message) {if(!yes) throw std::runtime_error(message);}
namespace aurora {
// Exercise transitions against a real D3D device, including states normally
// reached only after delayed GPU timestamps arrive during an interactive flight.
struct RendererTestAccess {
    static void queuePreparation(Renderer& r) {
        auto read=[&](ID3D11Buffer* source) {
            D3D11_BUFFER_DESC desc{};source->GetDesc(&desc);
            desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=desc.MiscFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
            ComPtr<ID3D11Buffer> staging;check(r.device->CreateBuffer(&desc,nullptr,&staging),"Create queue test readback");
            std::vector<UINT> result(desc.ByteWidth/sizeof(UINT));r.context->CopyResource(staging.Get(),source);
            D3D11_MAPPED_SUBRESOURCE mapped{};check(r.context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped),"Read queue arguments");
            memcpy(result.data(),mapped.pData,desc.ByteWidth);r.context->Unmap(staging.Get(),0);return result;
        };
        FrameConstants frame{};frame.output.z=1;
        D3D11_MAPPED_SUBRESOURCE mapped{};check(r.context->Map(r.frameConstants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Set empty queue test constants");
        memcpy(mapped.pData,&frame,sizeof(frame));r.context->Unmap(r.frameConstants.Get(),0);
        auto frameBuffer=r.frameConstants.Get();r.context->CSSetConstantBuffers(2,1,&frameBuffer);
        auto prepare=[&](UINT count) {
            r.context->UpdateSubresource(r.rayCountBuffer.Get(),0,nullptr,&count,0,0);
            UINT stale[4]{77,77,77,77};r.context->ClearUnorderedAccessViewUint(r.dispatchUav.Get(),stale);
            r.context->CopySubresourceRegion(r.dispatchBuffer.Get(),0,12,0,0,r.rayCountBuffer.Get(),0,nullptr);
            auto dispatch=r.dispatchUav.Get(),buckets=r.bucketUav.Get();
            r.context->CSSetUnorderedAccessViews(2,1,&dispatch,nullptr);r.context->CSSetUnorderedAccessViews(4,1,&buckets,nullptr);
            r.context->CSSetShader(r.rayPrepare.Get(),nullptr,0);r.context->Dispatch(1,1,1);
            ID3D11UnorderedAccessView* none=nullptr;r.context->CSSetUnorderedAccessViews(2,1,&none,nullptr);r.context->CSSetUnorderedAccessViews(4,1,&none,nullptr);
            return read(r.dispatchBuffer.Get());
        };
        UINT stale[4]{77,77,77,77};r.context->ClearUnorderedAccessViewUint(r.bucketUav.Get(),stale);
        auto empty=prepare(0);
        for(int at:{0,4,8,12}) require(empty[at]==0 && empty[at+1]==1 && empty[at+2]==1,"Empty queue retained stale dispatch arguments");
        require(empty[3]==0,"Empty queue count changed");
        for(UINT bucket:read(r.bucketBuffer.Get())) require(bucket==77,"Empty queue still scanned unused buckets");
        auto checkCounts=[&](const std::vector<UINT>& counts) {
            UINT total=0;for(UINT count:counts) total+=count;
            r.context->UpdateSubresource(r.bucketBuffer.Get(),0,nullptr,counts.data(),0,0);
            auto active=prepare(total);UINT groups=(total+63)/64;
            auto checkDispatch=[&](int at,UINT x,UINT y) {
                require(active[at]==x && active[at+1]==y && active[at+2]==1,"Queue dispatch dimensions changed");
            };
            checkDispatch(0,std::min(groups,65535u),std::max(1u,(groups+65534)/65535));
            checkDispatch(4,std::min(total,65535u),std::max(1u,(total+65534)/65535));
            checkDispatch(8,total<16384?0:active[0],active[1]);
            checkDispatch(12,total<16384?active[4]:0,active[5]);
            require(active[3]==total,"Queue preparation changed the ray count");
            auto offsets=read(r.bucketBuffer.Get());UINT prefix=0;
            for(size_t i=0;i<counts.size();i++) {require(offsets[i]==prefix,"Queue lost its exact bucket prefix sum");prefix+=counts[i];}
        };
        // Check both sides of every parallel scan boundary, including the last
        // bucket. Compare integer GPU offsets to an independent serial CPU sum.
        for(size_t bucket=0;bucket<128;bucket++) {
            std::vector<UINT> counts(128);counts[bucket]=17;checkCounts(counts);
        }
        for(UINT total:{1u,63u,64u,65u,16383u,16384u,16385u,65535u,65536u,4194240u,4194304u,8294400u}) {
            std::vector<UINT> counts(128,total/128);
            for(UINT i=0;i<total%128;i++) counts[i]++;
            checkCounts(counts);
            std::fill(counts.begin(),counts.end(),0);counts[0]=total/3;counts[63]=total/3;counts[127]=total-2*(total/3);
            checkCounts(counts);
        }
    }
    static void stableWeights(Renderer& r) {
        // A small traced image can be far from the output pixel centre. Absolute
        // Gaussian weights used to underflow and pull a uniform image to black.
        r.resize(512,512);r.makeSceneTarget(64,64);r.traceWidth=r.traceHeight=64;
        World world(1);View view(1);r.setConstants(world,view,0);
        std::vector<unsigned char> current(64*64*4,128);
        r.context->UpdateSubresource(r.sceneTexture.Get(),0,nullptr,current.data(),64*4,0);
        std::vector<float> rays(64*64*2);
        for(size_t i=0;i<rays.size();i+=2) rays[i+1]=1;
        r.context->UpdateSubresource(r.rayTexture.Get(),0,nullptr,rays.data(),64*2*sizeof(float),0);
        std::vector<uint16_t> history(512*512*4);
        for(size_t i=0;i<history.size();i+=4) history[i]=history[i+1]=history[i+2]=0x3800; // .5
        r.historyIndex=0;r.context->UpdateSubresource(r.historyTextures[0].Get(),0,nullptr,history.data(),512*4*sizeof(uint16_t),0);
        auto f=[](Vec3 p){return Float4{float(p.x),float(p.y),float(p.z),0};};
        FrameConstants frame{};frame.jitter={.49f,.49f,0,0};frame.prevRight=f(view.right());frame.prevUp=f(view.up());frame.prevForward=f(view.forward());
        frame.temporal={1,.1f,0,1};frame.output={512,512,0,0};
        D3D11_MAPPED_SUBRESOURCE mapped{};
        check(r.context->Map(r.frameConstants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Set large-upscale test constants");
        memcpy(mapped.pData,&frame,sizeof(frame));r.context->Unmap(r.frameConstants.Get(),0);
        auto buffer=r.frameConstants.Get();r.context->PSSetConstantBuffers(2,1,&buffer);
        r.frameTemporal=true;r.temporalPass();r.upscaleScene();auto result=r.presented();
        for(size_t i=0;i<result.size();i++) if(i%4!=3)
            require(result[i]>=126 && result[i]<=130,"Large upscale ratio darkened a uniform image");
    }
    static void temporalDepth(Renderer& r) {
        r.resize(64,64);r.makeSceneTarget(64,64);r.traceWidth=r.traceHeight=64;
        World world(1);View view(1);r.setConstants(world,view,0);
        std::vector<unsigned char> current(64*64*4);
        for(int y=0;y<64;y++) for(int x=0;x<64;x++) {
            size_t i=size_t(y*64+x)*4;unsigned char c=(x+y)%2?255:0;
            current[i]=current[i+1]=current[i+2]=c;current[i+3]=255;
        }
        r.context->UpdateSubresource(r.sceneTexture.Get(),0,nullptr,current.data(),64*4,0);
        auto resolve=[&](bool valid,uint16_t oldDepth,bool surface,float unitChange=0,float hitDepth=0) {
            std::vector<float> rays(64*64*2);
            for(size_t i=0;i<rays.size();i+=2) {rays[i]=hitDepth;rays[i+1]=surface?1.f:0.f;}
            r.context->UpdateSubresource(r.rayTexture.Get(),0,nullptr,rays.data(),64*2*sizeof(float),0);
            std::vector<uint16_t> history(64*64*4);
            for(size_t i=0;i<history.size();i+=4) {history[i]=history[i+1]=history[i+2]=0x3000;history[i+3]=oldDepth;} // RGB = .125
            r.historyIndex=0;r.context->UpdateSubresource(r.historyTextures[0].Get(),0,nullptr,history.data(),64*4*sizeof(uint16_t),0);
            auto f=[](Vec3 p){return Float4{float(p.x),float(p.y),float(p.z),0};};
            FrameConstants frame{};frame.prevRight=f(view.right());frame.prevUp=f(view.up());frame.prevForward=f(view.forward());
            frame.prevCamera.w=unitChange;frame.temporal={valid?1.f:0.f,.1f,0,1};frame.output={64,64,0,0};
            D3D11_MAPPED_SUBRESOURCE mapped{};
            check(r.context->Map(r.frameConstants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Set temporal test constants");
            memcpy(mapped.pData,&frame,sizeof(frame));r.context->Unmap(r.frameConstants.Get(),0);
            auto buffer=r.frameConstants.Get();r.context->PSSetConstantBuffers(2,1,&buffer);
            r.frameTemporal=true;r.temporalPass();r.upscaleScene();return r.presented();
        };
        auto fallback=resolve(false,0,true);
        auto blocked=resolve(true,0x4800,true); // Old surface at log depth 8, current at 0.
        require(fallback==blocked,"Disoccluded surface retained stale history");
        auto matching=resolve(true,0,true);
        require(matching!=fallback,"Matching surface lost temporal accumulation");
        auto rebased=resolve(true,0x3c00,true,1); // Same geometry in units twice as large.
        require(rebased==matching,"Camera-unit rebase rejected matching depth");
        auto wrongUnit=resolve(true,0,true,1);
        require(wrongUnit==fallback,"Depth comparison ignored the camera-unit change");
        require(resolve(true,0x5a40,true,0,200)==matching,"Far depth overflowed temporal reprojection"); // log depth 200
        auto skyFallback=resolve(false,0,false);
        require(resolve(true,0,false)==skyFallback,"Newly revealed sky retained a surface trail");
        require(resolve(true,0x7b53,false)!=skyFallback,"Sky rotation discarded valid sky history"); // 60000 sentinel
    }
    static void run(Renderer& r) {
        r.temporalEnabled=true;r.temporalUpscale=true;r.dynamicResolution=true;
        World world(1);View view(1);
        auto history0=r.historyTextures[0],history1=r.historyTextures[1];
        r.render(world,view,0,false);
        require(r.restartedHistory(),"First temporal frame reused uninitialized history");
        r.render(world,view,0,false);
        require(!r.restartedHistory(),"Unchanged view discarded temporal history");
        r.render(world,view,1,false);
        require(r.restartedHistory(),"Palette change blended old surface colours");
        r.render(world,view,1,false);
        require(!r.restartedHistory(),"Palette kept invalidating history");

        // At this window size Balanced and Ultra have the same render dimensions.
        int w=r.renderWidth,h=r.renderHeight;
        r.freshSample=true;r.latestGpuMs=100;r.dynamicScale=.75;
        r.setQuality(2);
        require(r.renderWidth==w && r.renderHeight==h,"Fixture did not exercise identical render sizes");
        require(!r.historyValid && !r.freshSample && r.dynamicScale==1,"Quality switch retained old history or timings");
        require(r.historyTextures[0]==history0 && r.historyTextures[1]==history1,"Same-size quality switch reallocated histories");
        r.render(world,view,1,false);
        require(r.restartedHistory(),"Same-size quality switch reused old lighting");
        r.setQuality(0); // Render size changes; output-size histories should survive.
        require(r.renderWidth!=w || r.renderHeight!=h,"Fixture did not exercise a render-size change");
        require(r.historyTextures[0]==history0 && r.historyTextures[1]==history1,"Render-size change reallocated output histories");

        // Pausing must trace at full profile resolution even after a slow flight.
        r.resumePending=false;r.freshSample=true;r.latestScale=.75;r.latestGpuMs=100;
        r.dynamicScale=.75;r.flying=false;
        r.render(world,view,1);
        require(r.tracedWidth()==r.sceneWidth() && r.tracedHeight()==r.sceneHeight(),"Still view retained reduced resolution");
        // A stale flight/idle sample must not immediately throttle the next flight.
        r.flying=true;r.freshSample=true;r.latestScale=1;r.latestGpuMs=100;
        r.markIdle();r.render(world,view,1);
        require(r.dynamicScale==1,"Resume consumed a stale timing sample");

        r.dynamicScale=.75;r.freshSample=true;r.resize(1600,900);
        require(!r.freshSample && r.dynamicScale==1 && !r.historyValid,"Resize kept old resolution control state");
        require(r.historyWidth==1600 && r.historyHeight==900,"Resize did not update temporal output size");
        r.render(world,view,1,false);
        require(r.restartedHistory(),"Resized frame sampled old history");
        // Readback retires all preceding GPU work and also checks a usable image.
        auto image=r.presented();
        require(image.size()==size_t(1600)*900*4,"Presented image size is wrong");
        bool visible=false;for(size_t i=0;i<image.size();i+=4) visible|=image[i]!=0 || image[i+1]!=0 || image[i+2]!=0;
        require(visible,"Renderer produced an empty image");

        // Preserve the bounded Ultra startup when a paused 4K view resumes.
        r.resize(3840,2160);r.setQuality(2);r.flying=false;
        r.render(world,view,1);
        require(r.dynamicScale==1 && r.restartPending,"Paused 4K view consumed the flight startup scale");
        r.flying=true;r.render(world,view,1);
        require(r.dynamicScale==r.lowestScale() && !r.restartPending,"Ultra 4K resumed at an unbounded resolution");
        r.presented();
        temporalDepth(r);
        stableWeights(r);
        queuePreparation(r);
    }
};
}
int main() {
    CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    HWND window=CreateWindowExW(0,L"STATIC",L"Aurora renderer tests",WS_OVERLAPPEDWINDOW,0,0,1280,900,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    int result=0;
    try {
        require(window!=nullptr,"Could not create hidden test window");
        Renderer renderer;renderer.initialize(window,1280,900,false);
        RendererTestAccess::run(renderer);
        std::cout<<"PASS: temporal invalidation, texture reuse, resolution transitions, depth rejection, sky, camera-unit rebasing and exact queue preparation\n";
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';result=1;}
    if(window) DestroyWindow(window);
    CoUninitialize();return result;
}
