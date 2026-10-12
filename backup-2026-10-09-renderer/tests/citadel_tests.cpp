#include "world.h"
#include <iostream>
#include <random>
#include <fstream>
#include <filesystem>
using namespace aurora;
static void require(bool yes,const char* what) {if(!yes) throw std::runtime_error(what);}
static double direct(Vec3 p,int count) {
    double derivative=1;
    for(int i=0;i<count;i++) {p=boxFold(p);double k=2.8/std::clamp(p.dot(p),.25,1.);p=p*k+Vec3{1.4,1.4,.7};derivative*=k;if(p.dot(p)>4096) break;}
    return .45*p.length()/derivative;
}
int main() {try {
    std::mt19937 gen(8841);std::uniform_real_distribution<double> u(-1,1);
    int comparisons=0;double maxError=0,maxDrift=0;
    auto envelope=Citadel{}.outerBounds();int boundsChecks=0;
    for(int axis=0;axis<3;axis++) for(int side=0;side<2;side++) for(int i=0;i<256;i++) {
        Vec3 p{u(gen)*5,u(gen)*5,u(gen)*5};
        double bound=axis==0?envelope[side].x:axis==1?envelope[side].y:envelope[side].z;
        double position=bound+(side?1:-1)*std::pow(10.,-8+(i%9));
        if(axis==0) p.x=position;else if(axis==1) p.y=position;else p.z=position;
        bool escaped=false;
        for(int iteration=0;iteration<256;iteration++) {
            p=boxFold(p);p=p*(2.8/std::clamp(p.dot(p),.25,1.))+Vec3{1.4,1.4,.7};
            if(p.dot(p)>4096) {escaped=true;break;}
        }
        require(escaped,"Bounding planes excluded actual fractal geometry");boundsChecks++;
    }
    gen.seed(8841);
    for(int view=0;view<60;view++) {
        Citadel w;w.reset({u(gen)*7,u(gen)*7,u(gen)*7});double unit=std::exp2(w.logUnit);
        for(int j=0;j<100;j++) {
            Vec3 d=Vec3{u(gen),u(gen),u(gen)}*std::pow(10.,j%5-2);
            double a=w.distance(d),b=direct(w.reference[0].p+d*unit,std::min(Citadel::capacity,int(w.reference.size())+12))/unit;
            double error=std::abs(a-b)/std::max(1e-8,b);maxError=std::max(maxError,error);comparisons++;
            require(error<.003,"Camera-relative field disagrees with independent world-space field");
        }
    }
    World w(1);View v(1);int movementChecks=0;
    for(int frame=0;frame<65000 && w.zoomLog10<85;frame++) {
        if(frame%400==0) {
            Vec3 motion=v.forward()*.003;
            std::array<Vec3,20> points;std::array<double,20> values;
            for(int i=0;i<20;i++) {points[i]=Vec3{u(gen),u(gen),u(gen)}*std::pow(10.,i%4-1);values[i]=w.citadel.distance(points[i]);}
            double before=w.citadel.logUnit;w.advance(motion);double ratio=std::exp2(before-w.citadel.logUnit);
            for(int i=0;i<20;i++) {
                double after=w.citadel.distance((points[i]-motion)*ratio)/ratio;
                double drift=std::abs(after-values[i])/std::max(.0001,values[i]);maxDrift=std::max(maxDrift,drift);movementChecks++;
                if(drift>.03) std::cerr<<"drift "<<drift<<" zoom "<<w.zoomLog10<<" sample "<<i<<'\n';
                require(drift<.03,"A stationary surface moved during camera recentering");
            }
        }
        w.advance(v.forward()*.013);
        require(w.warps.empty(),"Citadel must not rotate or replace the world during zoom");
        require(std::isfinite(w.citadel.logUnit) && std::abs(w.citadel.distance({})-.4)<1e-5,"Invalid deep camera clearance");
    }
    std::cout<<"depth "<<w.zoomLog10<<" iterations "<<w.depth<<" maximum relative field error "<<maxError<<" drift "<<maxDrift<<'\n';
    require(w.zoomLog10>80,"Did not reach deep precision range");
    double reached=w.zoomLog10;
    World limit=w;bool stopped=false;
    for(int frame=0;frame<150000;frame++) {
        double before=limit.citadel.logUnit;
        if(!limit.advance(v.forward()*.026)) {
            require(limit.citadel.logUnit==before,"Precision limit changed the scene");
            stopped=true;break;
        }
    }
    require(stopped,"Precision capacity guard was not exercised");
    require(limit.advance(v.forward()*-.026),"Could not back away from the precision limit");
    for(int frame=0;frame<50000 && w.zoomLog10>1;frame++) w.advance(v.forward()*-.026);
    std::cout<<"reverse depth "<<w.zoomLog10<<'\n';
    require(w.zoomLog10<1,"Cannot fly back from the deep surface into the original world");
    // A fixed target must get closer in physical coordinates while flying.
    Citadel approach;approach.reset({6.5,5.4,-9.5});Vec3 origin=approach.reference[0].p,dir=(origin*-1).unit();
    double travelled=0;
    for(int i=0;i<800;i++) {double physical=std::exp2(approach.logUnit)*.02;approach.move(dir*.02);travelled+=physical;}
    require(travelled>8,"Visible target cannot be approached");
    require((approach.reference[0].p-(origin+dir*travelled)).length()<1e-8,"Movement diverges from the visible world");
    // The actual input controller must follow its target ray, independent of
    // input vector length, and stop before the first independently traced wall.
    int flightChecks=0;double closestTargetFraction=0;
    for(int rayIndex=0;rayIndex<9;rayIndex++) {
        World flight(1),diagonal(1);View look(1);
        Vec3 ray=(look.forward()+look.right()*((rayIndex%3-1)*.12)+look.up()*((rayIndex/3-1)*.12)).unit();
        Vec3 start=flight.camera;double wall=0;
        for(int i=0;i<2000;i++) {
            double d=direct(start+ray*wall,256);
            if(d<1e-9) break;
            wall+=d*.8;
        }
        require(wall<30,"Test ray did not find its target surface");
        for(int frame=0;frame<180;frame++) {
            flight.fly(ray,1./60,15);diagonal.fly(ray*3,1./60,15);
            Vec3 delta=flight.camera-start;double progress=delta.dot(ray);
            require((delta-ray*progress).length()<1e-10,"Flight veered away from the selected target");
            require(progress<wall+1e-7,"Fast flight crossed a surface instead of entering its detail");
            require(std::abs(flight.citadel.logUnit-diagonal.citadel.logUnit)<1e-6,"Diagonal input changed flight speed");
            require(flight.depth<Citadel::capacity,"Controller exhausted precision during ordinary flight");
            closestTargetFraction=std::max(closestTargetFraction,progress/wall);flightChecks++;
        }
        std::cout<<"target "<<rayIndex<<" reached fraction "<<(flight.camera-start).length()/wall<<" zoom "<<flight.zoomLog10<<'\n';
        require((flight.camera-start).length()>wall*.99,"Visible surface did not get closer during boosted flight");
    }
    World guided(1);Vec3 heading=View(1).forward();
    for(int frame=0;frame<10800;frame++) {
        heading=guided.guide(heading,1./60);
        guided.advance(heading*(guided.clearance*1.9*.95/60));
        require(std::isfinite(guided.zoomLog10) && guided.depth<Citadel::capacity,"Guided flight exhausted its precision");
    }
    require(guided.zoomLog10>8,"Guided flight stopped exploring the detail");
    std::filesystem::create_directories("validation");std::ofstream out("validation/citadel-validation.json");
    out<<"{\"world_comparisons\":"<<comparisons<<",\"stationary_surface_checks\":"<<movementChecks<<",\"max_relative_field_error\":"<<maxError<<",\"max_relative_drift\":"<<maxDrift<<",\"deep_zoom_log10\":"<<reached<<",\"reverse_zoom_log10\":"<<w.zoomLog10<<",\"physical_distance_travelled\":"<<travelled<<",\"controller_checks\":"<<flightChecks<<",\"closest_target_fraction\":"<<closestTargetFraction<<",\"guided_minutes\":3,\"guided_zoom_log10\":"<<guided.zoomLog10<<"}\n";
    std::cout<<"PASS: shared field, fixed targets, deep zoom, reverse flight and "<<boundsChecks<<" exterior bound checks\n";return 0;
} catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}}
