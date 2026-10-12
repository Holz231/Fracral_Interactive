#include "renderer.h"
#include "flight_time.h"
#include <windowsx.h>
#include <dwmapi.h>
#include <shellapi.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <random>

extern "C" {
__declspec(dllexport) DWORD NvOptimusEnablement=1;
__declspec(dllexport) int AmdPowerXpressRequestHighPerformance=1;
}
using namespace aurora;
using Clock=std::chrono::steady_clock;
static constexpr wchar_t windowClass[]=L"AuroraFractalNative";
static constexpr const wchar_t* palettes[][3]={{L"Opaline",L"Ember",L"Nocturne"},{L"Sunstone",L"Azure",L"Jade"}};
struct Button {float x,y,w,h;int id;};
static bool saveFlight(const World&,const View&,const std::filesystem::path&);
static void loadFlight(World&,View&,const std::filesystem::path&);
struct App {
    HWND window=nullptr;
    Renderer renderer;
    World world{1};
    View view{1};
    bool initialized=false,active=true,dirty=true,automatic=true,paused=false,hud=true,fullscreen=false,persist=true;
    bool dragging=false,rightHeld=false,freeLook=false,cursorHidden=false;
    int width=1440,height=900,palette=0,quality=1,hover=-1,lastX=0,lastY=0;
    float uiScale=1;
    double speed=1.9,fps=0;
    std::array<bool,256> keys{};
    std::vector<Button> buttons;
    WINDOWPLACEMENT placement{sizeof(WINDOWPLACEMENT)};
    DWORD windowStyle=WS_OVERLAPPEDWINDOW;
    std::filesystem::path directory;
    std::wstring statusNote;
    struct FlightFrame {Citadel citadel;View view{1};uint64_t serial=0;int width=0,height=0,quality=1;};
    std::array<FlightFrame,gpuTimingSlots> flightFrames;
    FlightFrame slowestFrame;
    double slowestGpuMs=1000./60;
    bool slowFlightPending=false;
    uint64_t recordedSerial=0;
    void enableFlightDiagnostics() {
        renderer.onGpuTiming=[this](uint64_t serial,double milliseconds) {
            const auto& frame=flightFrames[serial%gpuTimingSlots];
            if(frame.serial!=serial || milliseconds<=slowestGpuMs) return;
            slowestFrame=frame;slowestGpuMs=milliseconds;slowFlightPending=true;
        };
    }
    void recordFlightFrame() {
        if(!persist || world.kind!=1) return;
        uint64_t serial=renderer.submittedSerial();if(!serial || serial==recordedSerial) return;
        recordedSerial=serial;auto& frame=flightFrames[serial%gpuTimingSlots];
        frame.citadel=world.citadel;frame.view=view;frame.serial=serial;
        frame.width=renderer.sceneWidth();frame.height=renderer.sceneHeight();frame.quality=quality;
    }
    void saveSlowFlight() {
        if(!persist || !slowFlightPending) return;
        World captured(1);captured.citadel=slowestFrame.citadel;captured.refresh();captured.prepare();
        if(!saveFlight(captured,slowestFrame.view,directory/L"slow-flight.aurora")) return;
        std::ofstream out(directory/L"slow-flight.json");
        out<<"{\"gpu_ms\":"<<slowestGpuMs<<",\"width\":"<<slowestFrame.width<<",\"height\":"<<slowestFrame.height
            <<",\"quality\":"<<slowestFrame.quality<<",\"zoom\":"<<captured.zoomLog10<<"}\n";
        slowFlightPending=false;
    }
    bool locked() const {return rightHeld||freeLook;}
    void cursor() {
        bool lock=locked() && active;
        if(lock!=cursorHidden) {ShowCursor(lock?FALSE:TRUE);cursorHidden=lock;}
        if(lock) {
            RECT r{};GetClientRect(window,&r);POINT a{r.left,r.top},b{r.right,r.bottom};ClientToScreen(window,&a);ClientToScreen(window,&b);
            RECT screen{a.x,a.y,b.x,b.y};ClipCursor(&screen);
        } else ClipCursor(nullptr);
    }
    void releaseLook() {rightHeld=freeLook=dragging=false;ReleaseCapture();cursor();}
    void manual() {automatic=false;world.hasDestination=false;dirty=true;}
    void rotate(int dx,int dy) {manual();view.yaw+=dx*.003;view.pitch=std::clamp(view.pitch-dy*.003,-1.52,1.52);}
    void setFullscreen() {
        releaseLook();
        if(!fullscreen) {
            placement.length=sizeof(placement);GetWindowPlacement(window,&placement);
            MONITORINFO mi{sizeof(mi)};GetMonitorInfo(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&mi);
            SetWindowLongPtr(window,GWL_STYLE,windowStyle&~WS_OVERLAPPEDWINDOW);
            SetWindowPos(window,HWND_TOP,mi.rcMonitor.left,mi.rcMonitor.top,mi.rcMonitor.right-mi.rcMonitor.left,mi.rcMonitor.bottom-mi.rcMonitor.top,SWP_FRAMECHANGED);
            fullscreen=true;
        } else {
            SetWindowLongPtr(window,GWL_STYLE,windowStyle);SetWindowPlacement(window,&placement);
            SetWindowPos(window,nullptr,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_FRAMECHANGED);fullscreen=false;
        }
        dirty=true;
    }
    void save() {
        if(!persist) return;
        std::ofstream out(directory/L"settings.txt");
        if(out) out<<palette<<' '<<quality<<' '<<speed<<' '<<automatic<<' '<<world.kind<<'\n';
    }
    void checkpoint() {
        if(persist && initialized && world.kind==1)
            saveFlight(world,view,directory/L"last-flight.aurora");
        saveSlowFlight();
    }
    void restore() {
        std::ifstream in(directory/L"settings.txt");int p=0,q=1,a=1;double s=1.9;
        if(in>>p>>q>>s>>a) {
            palette=std::clamp(p,0,2);quality=std::clamp(q,0,2);speed=std::clamp(s,.2,5.);automatic=a!=0;
            int kind=1;if(in>>kind) {kind=std::clamp(kind,0,1);world=World(kind);view=View(kind);}
        }
    }
    void action(int id) {
        switch(id) {
            case 0: automatic=!automatic;world.hasDestination=false;paused=false;break;
            case 1: paused=!paused;break;
            case 2: palette=(palette+1)%3;break;
            case 3: quality=(quality+1)%3;renderer.setQuality(quality);break;
            case 4: setFullscreen();break;
            case 5: world=World(world.kind);view=View(world.kind);paused=false;break;
            case 6: speed=std::max(.2,speed-.1);break;
            case 7: speed=std::min(5.,speed+.1);break;
            case 8: world=World(1-world.kind);view=View(world.kind);paused=false;automatic=true;break;
        }
        dirty=true;save();if(paused) checkpoint();
    }
    int hit(float x,float y) const {
        if(!hud) return -1;
        for(const auto& b:buttons) if(x>=b.x && y>=b.y && x<b.x+b.w && y<b.y+b.h) return b.id;
        return -1;
    }
    bool moving() const {
        if(paused) return false;
        return automatic||keys['W']||keys['A']||keys['S']||keys['D']||keys['Q']||keys['E']||keys[VK_LEFT]||keys[VK_RIGHT]||keys[VK_UP]||keys[VK_DOWN];
    }
    void update(double dt) {
        if(!moving()) return;
        if(automatic) {
            Vec3 d=world.guide(world.toDomain(view.forward()).unit(),dt);
            view.face(world.fromDomain(d));world.advance(d*(dt*speed*world.clearance*.95));
        } else {
            view.yaw+=dt*.9*(int(keys[VK_RIGHT])-int(keys[VK_LEFT]));
            view.pitch=std::clamp(view.pitch+dt*.9*(int(keys[VK_UP])-int(keys[VK_DOWN])),-1.52,1.52);
            double f=int(keys['W'])-int(keys['S']),r=int(keys['D'])-int(keys['A']),y=int(keys['E'])-int(keys['Q']);
            Vec3 dir=view.forward()*f+view.right()*r+view.frame({0,y,0});
            double rate=speed*(keys[VK_SHIFT]?3:1)/(world.kind==1?1:std::max(1.,std::sqrt(f*f+r*r+y*y)));
            world.fly(world.toDomain(dir),dt,rate/(world.kind==1?1:1.25));
        }
        for(const auto& warp:world.warps) view.apply(warp);
        world.warps.clear();
        world.prepare();dirty=true;
    }
    void overlay() {
        buttons.clear();if(!hud) return;
        auto panel=D2D1::ColorF(.025f,.045f,.065f,.87f),ink=D2D1::ColorF(.87f,.94f,.96f),muted=D2D1::ColorF(.52f,.67f,.72f),teal=D2D1::ColorF(.40f,.88f,.84f);
        const float w=width/uiScale,h=height/uiScale;
        renderer.beginOverlay(uiScale);
        renderer.rect(22,20,330,100,panel,12);
        renderer.text(L"A U R O R A",38,30,285,38,2,ink);
        renderer.text(world.kind==1?L"MANDELBOX CITADEL":L"IRIDESCENT VAULTS",40,69,290,24,0,muted);
        renderer.text(paused?L"PAUSED":automatic?L"GUIDED DIVE":L"FREE FLIGHT",40,92,270,24,0,teal);
        renderer.rect(214,88,122,25,hover==8?D2D1::ColorF(.19f,.26f,.3f):D2D1::ColorF(.1f,.15f,.19f),5);
        renderer.text(L"T  Change world",224,91,108,22,0,ink);buttons.push_back({214,88,122,25,8});
        renderer.rect(w-250,20,228,100,panel,12);
        std::wostringstream perf;
        if(!moving()) perf<<L"GPU idle";
        else if(fps>0) perf<<std::fixed<<std::setprecision(0)<<fps<<L" fps";
        else perf<<L"Ready";
        if(renderer.milliseconds()>0) perf<<L"  /  "<<std::fixed<<std::setprecision(1)<<renderer.milliseconds()<<L" ms GPU";
        renderer.text(perf.str(),w-234,32,205,28,1,ink);
        std::wostringstream detail;detail<<renderer.sceneWidth()<<L" x "<<renderer.sceneHeight()<<L"  /  "<<profiles[quality].name;
        renderer.text(detail.str(),w-234,63,210,22,0,muted);
        std::wostringstream zoom;zoom<<L"Zoom  ";
        if(world.zoomLog10<5) zoom<<std::fixed<<std::setprecision(world.zoomLog10<1?1:0)<<std::pow(10.,world.zoomLog10)<<L"x";
        else zoom<<L"10^"<<std::fixed<<std::setprecision(1)<<world.zoomLog10<<L"x";
        renderer.text(zoom.str(),w-234,87,205,24,0,teal);
        float toolbarY=h-116;
        renderer.rect(22,toolbarY,w-44,94,panel,12);
        float x=36;
        auto button=[&](int id,float size,const std::wstring& label,bool selected=false) {
            float y=toolbarY+13;
            auto color=selected?D2D1::ColorF(.13f,.39f,.39f):id==hover?D2D1::ColorF(.19f,.26f,.30f):D2D1::ColorF(.10f,.15f,.19f);
            renderer.rect(x,y,size,34,color,6);renderer.text(label,x+10,y+7,size-14,23,0,ink);
            buttons.push_back({x,y,size,34,id});x+=size+8;
        };
        bool compact=w<1060;
        button(0,compact?112.f:135.f,automatic?L"G  Take control":L"G  Guided dive",automatic);
        button(1,78,paused?L"Continue":L"Pause",paused);
        button(2,100,palettes[world.kind][palette]);
        button(3,compact?112.f:130.f,profiles[quality].name);
        button(4,compact?80.f:100.f,compact?L"F  Screen":L"F  Fullscreen");
        button(5,66,L"R  Reset");
        if(x+156<w-32) {
            button(6,30,L"-");
            std::wostringstream v;v<<std::fixed<<std::setprecision(1)<<speed<<L"x";
            renderer.text(v.str(),x+8,toolbarY+21,62,24,0,ink);x+=65;
            button(7,30,L"+");
        }
        renderer.text(L"WASD move    Q/E down / up    Drag / hold right mouse to look    Shift boost    Wheel speed    Space pause    H hide",38,toolbarY+60,w-76,24,0,muted);
        if(!automatic) {
            renderer.rect(w*.5f-5,h*.5f-.5f,10,1,D2D1::ColorF(.8f,.95f,1.f,.48f));
            renderer.rect(w*.5f-.5f,h*.5f-5,1,10,D2D1::ColorF(.8f,.95f,1.f,.48f));
        }
        renderer.endOverlay();
    }
};
static LRESULT CALLBACK windowProc(HWND hwnd,UINT message,WPARAM w,LPARAM l) {
    auto* app=reinterpret_cast<App*>(GetWindowLongPtr(hwnd,GWLP_USERDATA));
    if(message==WM_NCCREATE) {
        app=static_cast<App*>(reinterpret_cast<CREATESTRUCT*>(l)->lpCreateParams);
        app->window=hwnd;SetWindowLongPtr(hwnd,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(app));
    }
    if(!app) return DefWindowProc(hwnd,message,w,l);
    try {
        switch(message) {
        case WM_ERASEBKGND:return 1;
        case WM_PAINT:{PAINTSTRUCT p{};BeginPaint(hwnd,&p);EndPaint(hwnd,&p);app->dirty=true;return 0;}
        case WM_SIZE:
            if(w!=SIZE_MINIMIZED && LOWORD(l)>0 && HIWORD(l)>0) {
                app->width=LOWORD(l);app->height=HIWORD(l);
                if(app->initialized) app->renderer.resize(app->width,app->height);
                app->dirty=true;app->cursor();
            }return 0;
        case WM_DPICHANGED:{app->uiScale=float(HIWORD(w))/96;auto* r=reinterpret_cast<RECT*>(l);SetWindowPos(hwnd,nullptr,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER);return 0;}
        case WM_GETMINMAXINFO:{auto* info=reinterpret_cast<MINMAXINFO*>(l);float scale=float(GetDpiForWindow(hwnd))/96;info->ptMinTrackSize={LONG(900*scale),LONG(570*scale)};return 0;}
        case WM_ACTIVATEAPP:app->active=w!=0;if(!app->active) {app->checkpoint();app->keys.fill(false);app->releaseLook();}app->dirty=true;return 0;
        case WM_LBUTTONDOWN: {
            int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l),button=app->hit(x/app->uiScale,y/app->uiScale);
            if(button>=0) app->action(button);
            else {app->dragging=true;app->lastX=x;app->lastY=y;app->manual();SetCapture(hwnd);}
            return 0;
        }
        case WM_LBUTTONUP:app->dragging=false;ReleaseCapture();app->checkpoint();return 0;
        case WM_LBUTTONDBLCLK:
            if(app->hit(GET_X_LPARAM(l)/app->uiScale,GET_Y_LPARAM(l)/app->uiScale)<0) {app->freeLook=!app->freeLook;app->dragging=false;app->manual();app->cursor();}return 0;
        case WM_RBUTTONDOWN:app->rightHeld=true;app->manual();SetCapture(hwnd);app->cursor();return 0;
        case WM_RBUTTONUP:app->rightHeld=false;ReleaseCapture();app->cursor();app->checkpoint();return 0;
        case WM_CAPTURECHANGED:app->dragging=false;if(!app->freeLook){app->rightHeld=false;app->cursor();}return 0;
        case WM_MOUSEMOVE: {
            int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);
            if(app->dragging && !app->locked()) app->rotate(x-app->lastX,y-app->lastY);
            app->lastX=x;app->lastY=y;
            int hover=app->hit(x/app->uiScale,y/app->uiScale);if(hover!=app->hover){app->hover=hover;app->dirty=true;}
            return 0;
        }
        case WM_MOUSEWHEEL:app->speed=std::clamp(app->speed+GET_WHEEL_DELTA_WPARAM(w)/double(WHEEL_DELTA)*.1,.2,5.);app->dirty=true;app->save();return 0;
        case WM_INPUT:
            if(app->locked() && app->active) {
                RAWINPUT input{};UINT size=sizeof(input);
                if(GetRawInputData(reinterpret_cast<HRAWINPUT>(l),RID_INPUT,&input,&size,sizeof(RAWINPUTHEADER))==size && input.header.dwType==RIM_TYPEMOUSE)
                    app->rotate(input.data.mouse.lLastX,input.data.mouse.lLastY);
            }
            return DefWindowProc(hwnd,message,w,l);
        case WM_KEYDOWN:case WM_SYSKEYDOWN: {
            if(w<256) app->keys[w]=true;
            if(l&(1LL<<30)) return 0;
            switch(w) {
            case 'G':app->action(0);break;case VK_SPACE:app->action(1);break;case 'P':app->action(2);break;case 'K':app->action(3);break;
            case 'F':app->action(4);break;case 'R':app->action(5);break;case VK_OEM_MINUS:case VK_SUBTRACT:app->action(6);break;
            case VK_OEM_PLUS:case VK_ADD:app->action(7);break;
            case 'H':app->hud=!app->hud;app->dirty=true;break;
            case 'T':app->action(8);break;
            case VK_F9:app->checkpoint();break;
            case VK_ESCAPE:if(app->locked()) app->releaseLook();else if(app->fullscreen) app->setFullscreen();else app->action(1);break;
            case 'W':case 'A':case 'S':case 'D':case 'Q':case 'E':case VK_UP:case VK_DOWN:case VK_LEFT:case VK_RIGHT:app->manual();break;
            default:return DefWindowProc(hwnd,message,w,l);
            }return 0;
        }
        case WM_KEYUP:case WM_SYSKEYUP: {
            bool moving=app->moving();if(w<256) app->keys[w]=false;
            if(moving && !app->moving()) app->checkpoint();return 0;
        }
        case WM_CLOSE:app->checkpoint();app->save();DestroyWindow(hwnd);return 0;
        case WM_DESTROY:app->releaseLook();PostQuitMessage(0);return 0;
        }
    } catch(const std::exception& e) {MessageBoxA(hwnd,e.what(),"Aurora graphics error",MB_OK|MB_ICONERROR);DestroyWindow(hwnd);return 0;}
    return DefWindowProc(hwnd,message,w,l);
}
static std::string utf8(const std::wstring& text) {
    int n=WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),nullptr,0,nullptr,nullptr);
    std::string result(n,'\0');WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),result.data(),n,nullptr,nullptr);return result;
}
static int validateNative(App& app) {
    auto dir=std::filesystem::current_path()/L"validation";std::filesystem::create_directories(dir);
    app.uiScale=1;app.width=1280;app.height=720;app.renderer.resize(1280,720);
    app.world.prepare();double initialBalanced=app.renderer.profileMilliseconds(app.world,app.view,1);
    double initialUltra=app.renderer.profileMilliseconds(app.world,app.view,2);
    app.renderer.setQuality(1);app.renderer.render(app.world,app.view,0,false);app.overlay();app.renderer.capture((dir/L"aurora-native.png").wstring());
    // Capture a reproducible deep view in the same original Julia set.
    Vec3 heading=app.view.forward();
    for(int i=0;i<24000;i++) {
        app.world.advance(heading*(app.world.clearance*.95*1.9/60));app.world.prepare();
        for(const auto& warp:app.world.warps) {heading=transport(heading,warp);app.view.apply(warp);}
        app.world.warps.clear();
        if(app.world.zoomLog10>=6) break;
    }
    if(app.world.zoomLog10<6) throw std::runtime_error("Native validation did not reach deep detail");
    app.world.prepare();double deepBalanced=app.renderer.profileMilliseconds(app.world,app.view,1);
    double deepUltra=app.renderer.profileMilliseconds(app.world,app.view,2);
    app.quality=2;app.palette=2;app.renderer.setQuality(2);app.renderer.render(app.world,app.view,2,false);app.overlay();app.renderer.capture((dir/L"deep-flight.png").wstring());
    int deepIterations=app.world.depth;double deepZoom=app.world.zoomLog10;
    // Exercise resize, every quality shader and each palette on the GPU.
    for(int i=0;i<3;i++) {app.renderer.resize(960+i*160,640+i*40);app.renderer.setQuality(i);app.renderer.render(app.world,app.view,i,false);}
    // Exercise the same input/controller functions used by the real window.
    app.action(5);app.automatic=false;app.paused=false;app.keys['W']=true;
    Vec3 before=app.world.camera;app.update(1./60);
    if((app.world.camera-before).length()<=0) throw std::runtime_error("Manual forward input did not move the camera");
    app.keys.fill(false);before=app.world.camera;app.update(.1);
    if((app.world.camera-before).length()!=0 || app.moving()) throw std::runtime_error("Idle input kept moving");
    app.automatic=true;app.paused=true;app.update(.1);
    if((app.world.camera-before).length()!=0) throw std::runtime_error("Pause failed to freeze flight");
    app.action(1);app.action(0);app.action(2);app.action(3);app.action(8);
    app.world.prepare();app.renderer.render(app.world,app.view,0,false);app.action(8);
    World vault;View vaultView;auto culling=app.renderer.benchmark(vault,vaultView);
    int pixelError=app.renderer.benchmarkMaxPixelDifference;
    size_t changed=app.renderer.benchmarkPixelsOverTolerance;
    std::ofstream report(dir/L"gpu-benchmark.json");
    report<<std::fixed<<std::setprecision(4)<<"{\n  \"adapter\": \""<<utf8(app.renderer.adapterName)<<"\",\n"
        <<"  \"world\": \"Mandelbox Julia citadel\",\n  \"resolution\": \"1280x720\",\n  \"timing_scope\": \"GPU fractal pass; excludes upscaling, UI and vsync\",\n"
        <<"  \"balanced\": {\"max_ray_steps\": "<<profiles[1].steps<<", \"shadow_steps\": 4, \"initial_gpu_ms\": "<<initialBalanced<<", \"deep_gpu_ms\": "<<deepBalanced<<"},\n"
        <<"  \"ultra\": {\"max_ray_steps\": "<<profiles[2].steps<<", \"shadow_steps\": 8, \"initial_gpu_ms\": "<<initialUltra<<", \"deep_gpu_ms\": "<<deepUltra<<"},\n"
        <<"  \"vault_culling_check\": {\"ray_steps\": 132, \"shadow_steps\": 8, \"baseline_gpu_ms\": "<<culling.first<<", \"optimized_gpu_ms\": "<<culling.second<<", \"max_channel_difference\": "<<pixelError<<", \"pixels_over_one_level\": "<<changed<<"},\n"
        <<"  \"deep_reference_iterations\": "<<deepIterations<<",\n  \"deep_zoom_log10\": "<<deepZoom<<",\n  \"all_quality_shaders_and_resize_passed\": true,\n  \"manual_pause_idle_and_controls_passed\": true\n}\n";
    if(changed) throw std::runtime_error("GPU image equivalence test failed; see validation/gpu-benchmark.json");
    return 0;
}
static int gallery(App& app) {
    auto dir=std::filesystem::current_path()/L"validation";std::filesystem::create_directories(dir);
    app.renderer.resize(960,600);app.renderer.setQuality(2);
    const Vec3 cameras[]={{3.8,2.6,-5.5},{3.1,1.6,-4.5},{.6,.15,-3.1},{1.5,1.15,-4.6},{.1,.1,-3.1},{2.5,3.,-3.8},{-2.6,1.7,-4.8},{.8,1.1,-2.}};
    for(int i=0;i<8;i++) {
        app.world=World(1);
        app.world.citadel.reset(cameras[i]);app.world.refresh();app.world.prepare();
        app.view=View(1);app.view.face(Vec3{.4,.7,0}-app.world.camera);
        app.renderer.render(app.world,app.view,0,false);app.renderer.capture((dir/(L"gallery-"+std::to_wstring(i)+L".png")).wstring());
    }
    app.world=World(1);app.view=View(1);app.automatic=true;
    std::ofstream flight(dir/L"gallery-flight.txt");
    for(int frame=0;frame<10800;frame++) {
        app.update(1./60);
        if(frame==1199 || frame==3599 || frame==10799) {
            app.renderer.render(app.world,app.view,0,false);app.renderer.capture((dir/(L"guided-"+std::to_wstring(frame/60+1)+L".png")).wstring());
            flight<<frame/60+1<<" seconds: level "<<app.world.level<<", zoom "<<app.world.zoomLog10<<", clearance "<<app.world.clearance<<", position "<<app.world.camera.x<<", "<<app.world.camera.y<<", "<<app.world.camera.z<<'\n';
        }
    }
    return 0;
}
static int regression(App& app) {
    auto dir=std::filesystem::current_path()/L"validation"/L"regression";std::filesystem::create_directories(dir);
    app.renderer.resize(960,600);app.renderer.setQuality(1);app.world=World(1);app.view=View(1);
    std::ofstream report(dir/L"report.json");report<<"{\n  \"checkpoints\": [\n";
    bool passed=true;int checkpoint=0;
    auto difference=[](const std::vector<unsigned char>& a,const std::vector<unsigned char>& b) {
        double sum=0;for(size_t i=0;i<a.size();i++) if(i%4!=3) sum+=std::abs(int(a[i])-int(b[i]));
        return sum/(a.size()*.75*255.);
    };
    for(double target:{0.,6.,24.,80.}) {
        for(int step=0;step<100000 && app.world.zoomLog10<target;step++) app.world.advance(app.view.forward()*.013);
        if(app.world.zoomLog10<target) throw std::runtime_error("Regression flight did not reach checkpoint");
        app.world.prepare();double fieldError=app.renderer.validateField(app.world,app.view);
        app.renderer.render(app.world,app.view,0,false);auto before=app.renderer.pixels();
        auto flightPath=dir/L"roundtrip.aurora";
        if(!saveFlight(app.world,app.view,flightPath)) throw std::runtime_error("Could not save flight snapshot");
        World restored(1);View restoredView(1);loadFlight(restored,restoredView,flightPath);
        app.renderer.render(restored,restoredView,0,false);
        if(before!=app.renderer.pixels()) throw std::runtime_error("Flight snapshot changed the rendered image");
        app.renderer.capture((dir/(L"depth-"+std::to_wstring(int(target))+L"-before.png")).wstring());
        World saved=app.world;
        // Changing only the camera unit must not replace or recolour a room.
        app.world.citadel.logUnit+=1;
        app.renderer.render(app.world,app.view,0,false);double scaleError=difference(before,app.renderer.pixels());
        app.world=saved;double motionError=0;
        for(int frame=0;frame<12;frame++) {
            app.world.advance(app.view.forward()*.0003);app.renderer.render(app.world,app.view,0,false);
            auto after=app.renderer.pixels();motionError=std::max(motionError,difference(before,after));before=std::move(after);
            if(frame==11) app.renderer.capture((dir/(L"depth-"+std::to_wstring(int(target))+L"-after.png")).wstring());
        }
        if(checkpoint++) report<<",\n";
        report<<"    {\"zoom_log10\":"<<app.world.zoomLog10<<",\"gpu_field_relative_error\":"<<fieldError<<",\"unit_change_mean_pixel_error\":"<<scaleError<<",\"motion_max_mean_pixel_change\":"<<motionError<<"}";report.flush();
        passed=passed && fieldError<.04 && scaleError<.025 && motionError<.025;
    }
    report<<"\n  ],\n  \"passed\": "<<(passed?"true":"false")<<"\n}\n";
    // Outside view checks exactly the same field and shading as the interior.
    app.world=World(1);app.world.citadel.reset({18,14,-26});app.world.prepare();app.view.face(app.world.camera*-1.);
    app.renderer.render(app.world,app.view,0,false);app.renderer.capture((dir/L"exterior.png").wstring());
    if(!passed) throw std::runtime_error("Continuity regression failed; see validation/regression/report.json");
    return 0;
}
static int gaps(App& app) {
    auto dir=std::filesystem::current_path()/L"validation"/L"gaps";std::filesystem::create_directories(dir);
    app.renderer.resize(1536,820);app.renderer.setQuality(1);app.world=World(1);app.view=View(1);
    bool passed=true;View original=app.view;
    for(double target:{6.7,24.,80.}) {
        for(int i=0;i<100000 && app.world.zoomLog10<target;i++) app.world.advance(original.forward()*.013);
        app.world.prepare();
        for(int i=0;i<3;i++) {
            app.view=original;app.view.yaw+=i*.55;
            passed=app.renderer.validateGaps(app.world,app.view,(dir/(L"depth-"+std::to_wstring(int(target))+L"-view-"+std::to_wstring(i))).wstring()) && passed;
        }
    }
    if(!passed) throw std::runtime_error("Unfinished or inconsistent corridor rays; see validation/gaps");
    return 0;
}
static int corners(App& app) {
    auto dir=std::filesystem::current_path()/L"validation"/L"corners";std::filesystem::create_directories(dir);
    app.renderer.resize(960,540);app.renderer.setQuality(1);
    std::ofstream report(dir/L"flight.csv");report<<"path,frame,zoom,cpu_ms,gpu_ms,iterations,prefix\n";
    auto box=app.world.citadel.outerBounds();Vec3 low=box[0],high=box[1];bool passed=true;
    for(int path=0;path<3;path++) {
        app.world=World(1);app.view=View(1);
        Vec3 target{high.x,high.y,low.z};
        if(path==2) target=target+Vec3{-.003,-.002,.001};
        if(path) app.view.face(target-app.world.camera);
        double maxCpu=0;
        for(int frame=0;frame<9000 && app.world.zoomLog10<40;frame++) {
            auto begin=Clock::now();app.world.fly(app.view.forward(),1./60,3.2);app.world.prepare();
            maxCpu=std::max(maxCpu,std::chrono::duration<double,std::milli>(Clock::now()-begin).count());
            if(frame%120==0) {
                double gpu=app.renderer.frameMilliseconds(app.world,app.view);
                report<<path<<','<<frame<<','<<app.world.zoomLog10<<','<<maxCpu<<','<<gpu<<','<<app.world.depth<<','<<app.world.citadel.start(app.world.citadel.logUnit)<<'\n';report.flush();maxCpu=0;
                if(path==1 && (frame==600 || frame==1320)) passed=app.renderer.validateGaps(app.world,app.view,(dir/(L"corner-"+std::to_wstring(frame))).wstring()) && passed;
            }
        }
        app.renderer.render(app.world,app.view,0,false);app.renderer.capture((dir/(L"path-"+std::to_wstring(path)+L".png")).wstring());
    }
    // Keep the selected pixel budget fixed throughout the 4K-window flight.
    // Readback synchronizes the hidden test;
    // timing comes from the GPU queries, not that readback's CPU wait.
    app.renderer.resize(3840,2160);app.renderer.setQuality(1);app.world=World(1);app.view=View(1);
    app.view.face(Vec3{high.x,high.y,low.z}-app.world.camera);
    for(int i=0;i<600;i++) app.world.fly(app.view.forward(),1./60,3.2);
    std::ofstream fixed(dir/L"fixed-4k.csv");fixed<<"frame,zoom,gpu_ms,width,height\n";
    int fixedWidth=app.renderer.sceneWidth(),fixedHeight=app.renderer.sceneHeight();bool resolutionStable=true;size_t unfinished=0;
    std::vector<double> settled;
    for(int frame=0;frame<1200;frame++) {
        app.world.fly(app.view.forward(),1./60,3.2);app.world.prepare();
        app.renderer.render(app.world,app.view,0,true);auto image=app.renderer.pixels();
        fixed<<frame<<','<<app.world.zoomLog10<<','<<app.renderer.sampledMilliseconds()<<','<<app.renderer.sceneWidth()<<','<<app.renderer.sceneHeight()<<'\n';
        resolutionStable=resolutionStable && app.renderer.sceneWidth()==fixedWidth && app.renderer.sceneHeight()==fixedHeight;
        if(frame>60 && app.renderer.sampledMilliseconds()>0) settled.push_back(app.renderer.sampledMilliseconds());
        for(size_t i=3;i<image.size();i+=4) unfinished+=image[i]<128;
    }
    std::sort(settled.begin(),settled.end());
    double p95=settled.empty()?1000:settled[size_t((settled.size()-1)*.95)];
    std::ofstream summary(dir/L"summary.json");
    passed=passed && !unfinished;
    summary<<"{\"fixed_4k_gpu_p95_ms\":"<<p95<<",\"width\":"<<fixedWidth<<",\"height\":"<<fixedHeight<<",\"unfinished\":"<<unfinished<<",\"visibility_passed\":"<<(passed?"true":"false")<<",\"resolution_stable\":"<<(resolutionStable?"true":"false")<<"}\n";
    app.renderer.capture((dir/L"fixed-4k.png").wstring());
    if(!passed || !resolutionStable || settled.empty()) throw std::runtime_error("Corner visibility or fixed-resolution regression failed; see validation/corners");
    return 0;
}
static bool saveFlight(const World& world,const View& view,const std::filesystem::path& path) {
    std::ofstream out(path);out<<std::setprecision(17)<<"AURORA_FLIGHT_1\n";
    auto vec=[&](Vec3 p){out<<p.x<<' '<<p.y<<' '<<p.z<<'\n';};
    out<<view.yaw<<' '<<view.pitch<<'\n';vec(view.axisX);vec(view.axisY);vec(view.axisZ);vec(world.citadel.constant);
    out<<world.citadel.logUnit<<' '<<world.citadel.reference.size()<<'\n';
    for(const auto& s:world.citadel.reference) {vec(s.p);vec(s.next);}
    out.flush();return bool(out);
}
static void loadFlight(World& world,View& view,const std::filesystem::path& path) {
    std::ifstream in(path);std::string header;std::getline(in,header);
    auto invalid=[](){throw std::runtime_error("Invalid or missing flight snapshot");};
    if(header!="AURORA_FLIGHT_1") invalid();
    auto number=[&](){double v=0;if(!(in>>v) || !std::isfinite(v)) invalid();return v;};
    auto vec=[&](){return Vec3{number(),number(),number()};};
    World next(1);View direction(1);direction.yaw=number();direction.pitch=number();
    direction.axisX=vec();direction.axisY=vec();direction.axisZ=vec();next.citadel.constant=vec();
    double unit=number();int count=0;
    if(!(in>>count) || count<1 || count>Citadel::capacity || unit< -2000 || unit>1000) invalid();
    next.citadel.reference.resize(count);
    for(auto& s:next.citadel.reference) {s.p=vec();s.next=vec();if(s.p.length()>1e100 || s.next.length()>1e100) invalid();}
    if(next.citadel.reference.back().next.length()<=64) invalid();
    next.citadel.metadata();next.citadel.logUnit=unit;next.juliaConstant=next.citadel.constant;
    next.refresh();next.prepare();world=std::move(next);view=direction;
}
static int replay(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"replay";std::filesystem::create_directories(dir);
    app.renderer.resize(960,540);app.renderer.setQuality(1);
    app.renderer.profileView(app.world,app.view,(dir/L"saved-view").wstring());
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    app.renderer.profileView(app.world,app.view,(dir/L"saved-native").wstring());
    app.renderer.resize(960,540);app.renderer.setQuality(1);
    for(int frame=0;frame<120;frame++) {
        app.world.fly(app.view.forward(),1./60,3.2);app.world.prepare();
        if(frame%30==29) app.renderer.profileView(app.world,app.view,(dir/(L"approach-"+std::to_wstring(frame+1))).wstring());
    }
    return 0;
}
static int frameProfile(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"frame-profile";
    std::filesystem::create_directories(dir);
    app.width=1980;app.height=1058;app.uiScale=1;app.renderer.resize(app.width,app.height);
    app.renderer.setQuality(1);app.automatic=false;app.paused=false;app.keys.fill(false);
    // Exercise automatic slow-frame capture in the isolated validation folder.
    app.directory=dir;app.persist=true;app.slowestGpuMs=0;app.enableFlightDiagnostics();
    std::ofstream output(dir/(app.renderer.hasFramePacing()?L"paced.csv":L"legacy.csv"));
    output<<"frame,wait_ms,prepare_ms,submit_ms,overlay_ms,present_ms,total_ms,gpu_ms\n";
    auto ms=[](auto a,auto b){return std::chrono::duration<double,std::milli>(b-a).count();};
    for(int frame=0;frame<180;frame++) {
        auto begin=Clock::now();
        while(!app.renderer.waitForFrame()) {
            MSG message{};while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)) {
                if(message.message==WM_QUIT) throw std::runtime_error("Frame profile interrupted");
                TranslateMessage(&message);DispatchMessage(&message);
            }
        }
        auto a=Clock::now();app.world.prepare();auto b=Clock::now();
        app.renderer.render(app.world,app.view,0);app.recordFlightFrame();auto c=Clock::now();
        app.overlay();auto d=Clock::now();app.renderer.present();auto e=Clock::now();
        output<<frame<<','<<ms(begin,a)<<','<<ms(a,b)<<','<<ms(b,c)<<','<<ms(c,d)<<','<<ms(d,e)<<','<<ms(begin,e)<<','<<app.renderer.sampledMilliseconds()<<'\n';
    }
    if(!app.slowestFrame.serial) throw std::runtime_error("Frame profile collected no matched GPU timings");
    app.saveSlowFlight();
    World restored(1);View restoredView(1);loadFlight(restored,restoredView,dir/L"slow-flight.aurora");
    if(restored.citadel.logUnit!=app.slowestFrame.citadel.logUnit || restoredView.yaw!=app.slowestFrame.view.yaw ||
       restoredView.pitch!=app.slowestFrame.view.pitch) throw std::runtime_error("Slow frame did not retain its camera");
    return 0;
}
static int hunt(App& app) {
    auto dir=std::filesystem::current_path()/L"validation"/L"hunt";std::filesystem::create_directories(dir);
    app.renderer.resize(480,256);app.renderer.setQuality(1);
    std::mt19937 random(99147);std::uniform_real_distribution<double> unit(-1,1);double worst=0;
    for(int path=0;path<48;path++) {
        app.world=World(1);app.view=View(1);
        Vec3 target{unit(random)*2.8,unit(random)*2.8,unit(random)*2.8};
        Vec3 heading=(target-app.world.camera).unit();app.view.face(heading);
        for(int frame=0;frame<18000 && app.world.zoomLog10<31.7 && app.world.zoomLog10> -10;frame++) app.world.fly(heading,1./60,3.2);
        if(!std::isfinite(app.world.zoomLog10) || app.world.zoomLog10<= -10) continue;
        app.world.prepare();View arrived=app.view;
        for(int view=0;view<6;view++) {
            app.view=arrived;app.view.yaw+=view*1.03;app.view.pitch=std::clamp(arrived.pitch+unit(random)*.8,-1.5,1.5);
            auto name=L"path-"+std::to_wstring(path)+L"-view-"+std::to_wstring(view);
            double ms=app.renderer.profileView(app.world,app.view,(dir/name).wstring(),false);
            if(ms>worst) {
                worst=ms;saveFlight(app.world,app.view,dir/L"worst.flight");
                app.renderer.render(app.world,app.view,0,false);app.renderer.capture((dir/L"worst.png").wstring());
                std::ofstream summary(dir/L"worst.txt");summary<<utf8(name)<<" GPU "<<ms<<" ms zoom "<<app.world.zoomLog10<<'\n';
            }
        }
    }
    return 0;
}
static int profile(App& app) {
    auto dir=std::filesystem::current_path()/L"validation"/L"profile";std::filesystem::create_directories(dir);
    app.renderer.resize(960,540);app.renderer.setQuality(1);View original(1);
    for(double target:{6.7,31.7,80.}) {
        for(int i=0;i<100000 && app.world.zoomLog10<target;i++) app.world.advance(original.forward()*.013);
        app.world.prepare();
        for(int i=0;i<8;i++) {
            app.view=original;app.view.yaw+=i*.55;
            app.renderer.profileView(app.world,app.view,(dir/(L"depth-"+std::to_wstring(int(target))+L"-view-"+std::to_wstring(i))).wstring());
        }
    }
    for(int path=0;path<6;path++) {
        app.world=World(1);app.view=View(1);
        Vec3 heading=(app.view.forward()+app.view.right()*((path%3-1)*.18)+app.view.up()*((path/3)*.18)).unit();
        app.view.face(heading);
        for(int frame=0;frame<18000 && app.world.zoomLog10<31.7;frame++) app.world.fly(heading,1./60,3.2);
        app.world.prepare();View arrived=app.view;
        for(int view=0;view<4;view++) {
            app.view=arrived;app.view.yaw+=view*.8;
            app.renderer.profileView(app.world,app.view,(dir/(L"flight-"+std::to_wstring(path)+L"-view-"+std::to_wstring(view))).wstring());
        }
    }
    return 0;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR commandLine,int) {
    bool frameMode=std::wstring(commandLine).find(L"--frame-profile")!=std::wstring::npos;
    bool legacyPacing=std::wstring(commandLine).find(L"--legacy-pacing")!=std::wstring::npos;
    bool replayMode=std::wstring(commandLine).find(L"--replay")!=std::wstring::npos;
    bool huntMode=std::wstring(commandLine).find(L"--hunt")!=std::wstring::npos;
    bool profileMode=std::wstring(commandLine).find(L"--profile")!=std::wstring::npos;
    bool cornersMode=std::wstring(commandLine).find(L"--corners")!=std::wstring::npos;
    bool gapsMode=std::wstring(commandLine).find(L"--gaps")!=std::wstring::npos;
    bool galleryMode=std::wstring(commandLine).find(L"--gallery")!=std::wstring::npos;
    bool regressionMode=std::wstring(commandLine).find(L"--regression")!=std::wstring::npos;
    bool benchmark=frameMode||replayMode||huntMode||profileMode||cornersMode||gapsMode||regressionMode||galleryMode||std::wstring(commandLine).find(L"--benchmark")!=std::wstring::npos;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    int result=0;
    try {
        App app;app.persist=!benchmark;
        wchar_t executable[MAX_PATH]{};GetModuleFileName(nullptr,executable,MAX_PATH);app.directory=std::filesystem::path(executable).parent_path();
        if(!benchmark) app.restore();
        WNDCLASSEX wc{sizeof(wc)};wc.style=CS_HREDRAW|CS_VREDRAW|CS_DBLCLKS;wc.lpfnWndProc=windowProc;wc.hInstance=instance;
        wc.hCursor=LoadCursor(nullptr,IDC_ARROW);wc.hIcon=LoadIcon(nullptr,IDI_APPLICATION);wc.lpszClassName=windowClass;RegisterClassEx(&wc);
        RECT bounds{0,0,benchmark?1280:1440,benchmark?720:900};AdjustWindowRectEx(&bounds,app.windowStyle,FALSE,0);
        HWND window=CreateWindowEx(0,windowClass,L"Aurora — Native Fractal Flight",app.windowStyle,CW_USEDEFAULT,CW_USEDEFAULT,bounds.right-bounds.left,bounds.bottom-bounds.top,nullptr,nullptr,instance,&app);
        if(!window) throw std::runtime_error("Could not create the flight window");
        app.uiScale=benchmark?1:float(GetDpiForWindow(window))/96;
        BOOL dark=TRUE;DwmSetWindowAttribute(window,20,&dark,sizeof(dark));
        RECT client{};GetClientRect(window,&client);app.width=client.right;app.height=client.bottom;
        app.renderer.initialize(window,app.width,app.height,!legacyPacing);app.initialized=true;app.renderer.setQuality(app.quality);
        RAWINPUTDEVICE raw{1,2,0,window};RegisterRawInputDevices(&raw,1,sizeof(raw));
        if(benchmark) {result=frameMode?frameProfile(app):replayMode?replay(app):huntMode?hunt(app):profileMode?profile(app):cornersMode?corners(app):gapsMode?gaps(app):regressionMode?regression(app):galleryMode?gallery(app):validateNative(app);DestroyWindow(window);}
        else {
            app.enableFlightDiagnostics();
            std::ofstream adapterLog(app.directory/L"last-run.txt");adapterLog<<"Direct3D 11 hardware adapter: "<<utf8(app.renderer.adapterName)<<"\n";adapterLog.flush();
            ShowWindow(window,SW_SHOW);UpdateWindow(window);
            auto last=Clock::now(),stats=last;int frames=0;bool quit=false;
            while(!quit) {
                MSG message{};
                while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)) {
                    if(message.message==WM_QUIT){quit=true;break;}
                    TranslateMessage(&message);DispatchMessage(&message);
                }
                if(quit) break;
                if(!app.active || IsIconic(window)) {MsgWaitForMultipleObjectsEx(0,nullptr,INFINITE,QS_ALLINPUT,MWMO_INPUTAVAILABLE);last=Clock::now();stats=last;frames=0;continue;}
                if(!app.moving() && !app.dirty) {app.saveSlowFlight();MsgWaitForMultipleObjectsEx(0,nullptr,INFINITE,QS_ALLINPUT,MWMO_INPUTAVAILABLE);last=Clock::now();stats=last;frames=0;continue;}
                if(!app.renderer.waitForFrame()) continue;
                auto now=Clock::now();double dt=std::chrono::duration<double>(now-last).count();last=now;
                advanceFlightTime(dt,[&](double step){app.update(step);});
                if(app.dirty) {
                    app.world.prepare();app.renderer.render(app.world,app.view,app.palette);app.recordFlightFrame();app.overlay();app.renderer.present();app.dirty=false;frames++;
                    double elapsed=std::chrono::duration<double>(now-stats).count();
                    if(elapsed>=.75) {app.fps=frames/elapsed;frames=0;stats=now;}
                }
            }
        }
    } catch(const std::exception& e) {
        std::ofstream log(std::filesystem::current_path()/L"aurora-error.txt");log<<e.what()<<'\n';
        if(!benchmark) MessageBoxA(nullptr,e.what(),"Aurora could not start",MB_OK|MB_ICONERROR);
        result=1;
    }
    CoUninitialize();return result;
}
