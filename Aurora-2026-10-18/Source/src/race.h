#pragma once
#include "world.h"
#include <cstring>
#include <filesystem>
#include <fstream>

namespace aurora {
// A recorded camera position. The reference orbit (not a root-space coordinate)
// keeps it exact at any zoom, like the camera itself.
struct RacePoint {double time=0,logUnit=0;std::vector<Vec3> orbit;};
inline RacePoint racePoint(const Citadel& citadel,double time) {
    RacePoint point;point.time=time;point.logUnit=citadel.logUnit;point.orbit.reserve(citadel.reference.size());
    for(const auto& s:citadel.reference) point.orbit.push_back(s.p);
    return point;
}
inline int raceBranch(Vec3 p) {
    auto side=[](double v){return v>1?2:v< -1?0:1;};
    Vec3 q=boxFold(p);double r2=q.dot(q);
    return side(p.x)+3*side(p.y)+9*side(p.z)+27*(r2<=.25?0:r2<1?1:2);
}
// Position of a recorded point relative to the camera, in camera units.
// Orbit sample 0 is the exact root-space difference but loses resolution at
// deep zoom. Later samples magnify the difference; they are used while both
// orbits follow the same fold branches and the prefix is linear (the same
// bound the distance field uses).
inline Vec3 raceOffset(const Citadel& camera,const RacePoint& point) {
    size_t count=std::min(camera.reference.size(),point.orbit.size());
    Vec3 linearOffset{},resolvedOffset{};bool haveLinear=false,haveResolved=false;
    for(size_t i=0;i<count;i++) {
        const auto& s=camera.reference[i];Vec3 delta=point.orbit[i]-s.p;
        double power=-(camera.logUnit+s.logDerivative);
        if(power<1000) {
            Vec3 offset=Vec3{delta.dot(s.x),delta.dot(s.y),delta.dot(s.z)}*std::exp2(std::max(power,-1000.));
            double size=offset.length();
            bool resolved=delta.length()>1e-9*(1+s.p.length());
            bool linear=i==0 || camera.logUnit+std::log2(std::max(size,1e-300))<s.limit;
            if(resolved && linear) {linearOffset=offset;haveLinear=true;}
            if(resolved && !haveResolved) {resolvedOffset=offset;haveResolved=true;}
        }
        if(raceBranch(s.p)!=raceBranch(point.orbit[i])) break;
    }
    return haveLinear?linearOffset:haveResolved?resolvedOffset:Vec3{};
}
// Time trial from a start snapshot to a finish gate. The first flight defines
// the track; every faster run replaces the ghost.
struct Race {
    enum class State {Idle,Recording,Countdown,Running,Finished};
    static constexpr double sampleInterval=.05,countdownSeconds=3,gateRadius=.4,flightSpeed=2.5,minimumSeconds=2,maximumSeconds=900;
    State state=State::Idle;
    bool hasTrack=false,newBest=false,firstRun=false;
    World startWorld{1};
    View startView{1};
    RacePoint finish;
    std::vector<RacePoint> best,current;
    double bestTime=0,time=0,countdown=0,finishedTime=0,previousBest=0;
    bool active() const {return state!=State::Idle;}
    // The clock runs (and frames must be rendered) even without input.
    bool ticking() const {return state==State::Recording || state==State::Countdown || state==State::Running;}
    bool frozen() const {return state==State::Countdown;}
    bool fixedSpeed() const {return ticking();}
    void stop() {state=State::Idle;current.clear();}
    void beginTrack(const World& world,const View& view) {
        startWorld=world;startView=view;current.clear();time=0;newBest=false;
        current.push_back(racePoint(world.citadel,0));state=State::Recording;
    }
    // Ends the first flight: the camera position becomes the finish gate.
    bool finishTrack(const World& world) {
        if(state!=State::Recording || time<minimumSeconds) return false;
        finish=racePoint(world.citadel,time);current.push_back(finish);
        // Later runs stop when they enter the gate, not at its centre. Time the
        // first flight the same way, or every repeat would beat it for free.
        size_t entered=0;
        while(entered+1<current.size() && raceOffset(world.citadel,current[entered]).length()>=gateRadius) entered++;
        current.resize(entered+1);
        if(current.size()<2 || current.back().time<minimumSeconds*.5) {current.clear();state=State::Idle;return false;}
        best=std::move(current);current.clear();bestTime=finishedTime=best.back().time;previousBest=0;
        hasTrack=true;newBest=true;firstRun=true;state=State::Finished;return true;
    }
    bool start(World& world,View& view) {
        if(!hasTrack) return false;
        world=startWorld;world.motionReset=true;world.cameraMotion={};view=startView;
        current.clear();time=0;countdown=countdownSeconds;newBest=false;firstRun=false;state=State::Countdown;return true;
    }
    // Distance to the finish in finish units; gateRadius is its free space.
    double finishDistance(const Citadel& camera) const {
        return raceOffset(camera,finish).length()*std::exp2(std::clamp(camera.logUnit-finish.logUnit,-1000.,1000.));
    }
    // Advance by one simulation step, after the camera moved. Returns true
    // when the stored track changed (a new best run).
    bool update(const World& world,double dt) {
        if(state==State::Countdown) {
            countdown-=dt;
            if(countdown<=0) {state=State::Running;time=0;current.clear();current.push_back(racePoint(world.citadel,0));}
            return false;
        }
        if(state!=State::Recording && state!=State::Running) return false;
        time+=dt;
        if(time>maximumSeconds) {stop();return false;}
        if(state==State::Running && finishDistance(world.citadel)<gateRadius) {
            current.push_back(racePoint(world.citadel,time));finishedTime=time;previousBest=bestTime;
            newBest=time<bestTime;
            if(newBest) {best=std::move(current);bestTime=time;}
            current.clear();state=State::Finished;return newBest;
        }
        if(time-current.back().time>=sampleInterval) current.push_back(racePoint(world.citadel,time));
        return false;
    }
    // Ghost position at race time t relative to the camera (camera units).
    bool ghost(const Citadel& camera,double t,Vec3& offset,double& logUnit) const {
        if(best.empty()) return false;
        if(t<=best.front().time) {offset=raceOffset(camera,best.front());logUnit=best.front().logUnit;return true;}
        if(t>=best.back().time) {offset=raceOffset(camera,best.back());logUnit=best.back().logUnit;return true;}
        size_t lo=0,hi=best.size()-1;
        while(lo+1<hi) {size_t mid=(lo+hi)/2;if(best[mid].time<=t) lo=mid;else hi=mid;}
        const auto& a=best[lo];const auto& b=best[hi];
        double f=(t-a.time)/std::max(b.time-a.time,1e-12);
        Vec3 from=raceOffset(camera,a),to=raceOffset(camera,b);
        offset=from+(to-from)*f;logUnit=a.logUnit+(b.logUnit-a.logUnit)*f;return true;
    }
    bool saveGhost(const std::filesystem::path& path) const {
        if(!hasTrack) return false;
        std::ofstream out(path,std::ios::binary);
        auto number=[&](double v){out.write(reinterpret_cast<const char*>(&v),sizeof(v));};
        auto point=[&](const RacePoint& p) {
            number(p.time);number(p.logUnit);number(double(p.orbit.size()));
            for(Vec3 v:p.orbit) {number(v.x);number(v.y);number(v.z);}
        };
        out.write(magic,sizeof(magic));number(bestTime);point(finish);number(double(best.size()));
        for(const auto& p:best) point(p);
        out.flush();return bool(out);
    }
    // The caller restores startWorld/startView from the matching snapshot.
    void loadGhost(const std::filesystem::path& path) {
        std::ifstream in(path,std::ios::binary);
        auto invalid=[](){throw std::runtime_error("Invalid or missing race ghost");};
        char header[sizeof(magic)]{};in.read(header,sizeof(header));
        if(!in || std::memcmp(header,magic,sizeof(magic))!=0) invalid();
        auto number=[&](){double v=0;in.read(reinterpret_cast<char*>(&v),sizeof(v));if(!in || !std::isfinite(v)) invalid();return v;};
        auto point=[&]() {
            RacePoint p;p.time=number();p.logUnit=number();double count=number();
            if(p.time<0 || p.time>maximumSeconds+1 || p.logUnit< -2000 || p.logUnit>1000 || count<1 || count>Citadel::capacity || count!=std::floor(count)) invalid();
            p.orbit.resize(size_t(count));
            for(auto& v:p.orbit) {v.x=number();v.y=number();v.z=number();if(v.length()>1e100) invalid();}
            return p;
        };
        double seconds=number();RacePoint gate=point();double count=number();
        if(seconds<minimumSeconds*.5 || seconds>maximumSeconds || count<2 || count>maximumSeconds/sampleInterval+4 || count!=std::floor(count)) invalid();
        std::vector<RacePoint> points(static_cast<size_t>(count));
        double previous=0;
        for(auto& p:points) {p=point();if(p.time<previous) invalid();previous=p.time;}
        best=std::move(points);finish=std::move(gate);bestTime=seconds;hasTrack=true;state=State::Idle;current.clear();
    }
private:
    static constexpr char magic[12]={'A','U','R','O','R','A','R','A','C','E','1','\n'};
};
}
