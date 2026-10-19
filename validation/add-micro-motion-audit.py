"""Instrument only the isolated native experiment for paired motion images."""
from pathlib import Path
root=Path(__file__).resolve().parent.parent
p=root/'validation/experiments/cone-segments-native/src/main.cpp'
s=p.read_text(encoding='utf-8')
if 'static int microMotion' in s:raise SystemExit('Micro-motion audit is already present; regenerate the native experiment first to refresh it.')
helper=r'''
static int microMotion(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"micro-motion";std::filesystem::create_directories(dir);
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    std::ofstream report(dir/L"motion.csv");report<<"frame,path,mean_max_channel_delta,pixels_over_16,max_channel_delta\n";
    std::array<std::vector<unsigned char>,2> previous;
    for(int frame=0;frame<24;frame++) {
        if(frame) {app.world.advance(app.view.forward()*.0001);app.world.prepare();}
        for(int path=0;path<2;path++) {
            app.renderer.setTracePath(path==0?0:1);app.renderer.render(app.world,app.view,0,false);
            auto pixels=app.renderer.pixels();
            if(frame) {
                double sum=0;size_t over=0;int maximum=0;
                for(size_t i=0;i<pixels.size();i+=4) {
                    int d=0;for(int c=0;c<3;c++) d=std::max(d,std::abs(int(pixels[i+c])-int(previous[path][i+c])));
                    sum+=d;over+=d>16;maximum=std::max(maximum,d);
                }
                report<<frame<<','<<path<<','<<sum/(pixels.size()/4)<<','<<over<<','<<maximum<<'\n';report.flush();
            }
            previous[path]=std::move(pixels);
            if(frame==0 || frame==23) app.renderer.capture((dir/(std::to_wstring(frame)+(path==0?L"-baseline.png":L"-candidate.png"))).wstring());
        }
    }
    return 0;
}
'''
s=s.replace('int WINAPI wWinMain(',helper+'\nint WINAPI wWinMain(',1)
s=s.replace('    bool flightMode=', '    bool microMode=std::wstring(commandLine).find(L"--micro-motion")!=std::wstring::npos;\n    bool flightMode=',1)
s=s.replace('    bool benchmark=frameMode', '    bool benchmark=microMode||frameMode',1)
s=s.replace('if(benchmark) {result=frameMode?', 'if(benchmark) {result=microMode?microMotion(app):frameMode?',1)
p.write_text(s,encoding='utf-8')
