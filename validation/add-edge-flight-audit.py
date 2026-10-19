"""Replay the user's approach and check camera recentering independently."""
from pathlib import Path
p=Path(__file__).resolve().parent/'experiments/native-tuned/src/main.cpp'
s=p.read_text(encoding='utf-8')
assert 'static int edgeFlight' not in s
helper=r'''
static int edgeFlight(App& app) {
    loadFlight(app.world,app.view,std::filesystem::current_path()/L"last-flight.aurora");
    auto dir=std::filesystem::current_path()/L"validation"/L"edge-flight";
    std::filesystem::create_directories(dir);
    app.renderer.resize(1980,1058);app.renderer.setQuality(1);
    std::ofstream report(dir/L"flight.csv");
    report<<"frame,zoom,reference_depth,cpu_stationary_drift,gpu_field_error,dark_pixels,unfinished\n"<<std::setprecision(12);
    for(int frame=0;frame<=1200;frame++) {
        if(frame) {app.world.fly(app.view.forward(),1./60,3.8);app.world.prepare();}
        if(frame%60) continue;
        World shifted=app.world;Vec3 motion=app.view.forward()*.003;
        double before=shifted.citadel.logUnit;shifted.advance(motion);
        double ratio=std::exp2(before-shifted.citadel.logUnit),drift=0;
        for(int i=0;i<48;i++) {
            Vec3 direction=(app.view.forward()+app.view.right()*((i%4-1.5)*.3)+app.view.up()*(((i/4)%4-1.5)*.3)).unit();
            Vec3 point=direction*std::exp2(double(i/16)*6-3);
            double a=app.world.citadel.distance(point),b=shifted.citadel.distance((point-motion)*ratio)/ratio;
            drift=std::max(drift,std::abs(a-b)/std::max(.0001,a));
        }
        double field=app.renderer.validateField(app.world,app.view);
        app.renderer.render(app.world,app.view,0,false);auto pixels=app.renderer.pixels();
        size_t dark=0,unfinished=0;
        for(size_t i=0;i<pixels.size();i+=4) {
            dark+=std::max({pixels[i],pixels[i+1],pixels[i+2]})<16;
            unfinished+=pixels[i+3]<128;
        }
        app.renderer.capture((dir/(L"frame-"+std::to_wstring(frame)+L".png")).wstring());
        saveFlight(app.world,app.view,dir/(L"frame-"+std::to_wstring(frame)+L".aurora"));
        report<<frame<<','<<app.world.zoomLog10<<','<<app.world.depth<<','<<drift<<','<<field<<','<<dark<<','<<unfinished<<'\n';report.flush();
    }
    return 0;
}
'''
s=s.replace('static int frameProfile(',helper+'\nstatic int frameProfile(',1)
s=s.replace('    bool benchmark=microMode', '    bool edgeMode=std::wstring(commandLine).find(L"--edge-flight")!=std::wstring::npos;\n    bool benchmark=edgeMode||microMode',1)
s=s.replace('if(benchmark) {result=microMode?', 'if(benchmark) {result=edgeMode?edgeFlight(app):microMode?',1)
p.write_text(s,encoding='utf-8')
