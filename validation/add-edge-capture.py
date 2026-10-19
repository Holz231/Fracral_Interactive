"""Add a single-frame render-path comparison to the isolated edge diagnostic."""
from pathlib import Path

p=Path(__file__).resolve().parent/'experiments/native-edge-diagnostic/src/main.cpp'
s=p.read_text(encoding='utf-8')
assert 'static int edgeCapture' not in s
helper=r'''
static int edgeCapture(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"edge-capture";
    std::filesystem::create_directories(dir);
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    for(int path=0;path<2;path++) {
        app.renderer.setTracePath(path);app.renderer.render(app.world,app.view,0,false);
        auto name=path?L"accelerated":L"serial";
        app.renderer.capture((dir/(std::wstring(name)+L".png")).wstring());
        auto pixels=app.renderer.pixels();
        std::ofstream raw(dir/(std::wstring(name)+L".rgba"),std::ios::binary);
        raw.write(reinterpret_cast<const char*>(pixels.data()),pixels.size());
    }
    return 0;
}
'''
s=s.replace('int WINAPI wWinMain(',helper+'\nint WINAPI wWinMain(',1)
s=s.replace('    bool microMode=', '    bool edgeCaptureMode=std::wstring(commandLine).find(L"--edge-capture")!=std::wstring::npos;\n    bool microMode=',1)
s=s.replace('    bool benchmark=microMode', '    bool benchmark=edgeCaptureMode||microMode',1)
s=s.replace('if(benchmark) {result=microMode?', 'if(benchmark) {result=edgeCaptureMode?edgeCapture(app):microMode?',1)
p.write_text(s,encoding='utf-8')
