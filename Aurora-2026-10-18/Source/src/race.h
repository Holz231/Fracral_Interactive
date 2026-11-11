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
// Time trial from a start snapshot to a finish gate, flown by a visible ship
// in front of a chase camera. The free camera shrinks instantly as it nears a
// wall and never arrives. The ship has a size of its own that follows the
// surrounding scale with a delay: a gentle approach zooms in, a fast one puts
// the ship's hull on the surface, and that contact ends the run.
struct Race {
    enum class State {Idle,Recording,Countdown,Running,Finished,Crashed};
    // Ship radius and speed in ship units.
    static constexpr double shipRadius=.06,shipSpeed=1.2,boostFactor=2,slowFactor=.3;
    // The camera follows chaseDistance radii behind and a little above the ship.
    static constexpr double chaseDistance=12,chaseDrop=.22;
    // The ship settles at comfortRatio radii from the nearest wall, at adaptRate per second.
    static constexpr double comfortRatio=16,adaptRate=.3;
    static constexpr double sampleInterval=.05,countdownSeconds=3,gateRadius=.4,minimumSeconds=2,maximumSeconds=900;
    State state=State::Idle;
    bool hasTrack=false,newBest=false;
    World startWorld{1};
    View startView{1};
    RacePoint finish;
    std::vector<RacePoint> best,current;
    double bestTime=0,time=0,countdown=0,finishedTime=0,previousBest=0;
    double shipLogUnit=-1e6;   // log2 of one ship unit, in the scale of Citadel::logUnit
    bool active() const {return state!=State::Idle;}
    // The clock runs (and frames must be rendered) even without input.
    bool ticking() const {return state==State::Recording || state==State::Countdown || state==State::Running;}
    bool frozen() const {return state==State::Countdown;}
    // One ship unit in current camera units.
    double shipScale(const Citadel& camera) const {return std::exp2(std::clamp(shipLogUnit-camera.logUnit,-1000.,1000.));}
    // Ship centre relative to the camera, and its hull radius, in camera units.
    Vec3 shipOffset(const Citadel& camera,const View& view) const {
        return (view.forward()-view.up()*chaseDrop)*(chaseDistance*shipRadius*shipScale(camera));
    }
    double hullRadius(const Citadel& camera) const {return shipRadius*shipScale(camera);}
    // Distance from the ship's centre to the nearest surface in ship radii; 1 is contact.
    double wallRatio(const World& world,const View& view) const {
        return world.citadel.distance(shipOffset(world.citadel,view))/hullRadius(world.citadel);
    }
    // The ship's position as a recorded point with its own reference orbit.
    RacePoint shipPoint(const World& world,const View& view,double seconds) const {
        Citadel ship=world.citadel;
        if(!ship.move(shipOffset(world.citadel,view))) ship=world.citadel;
        return racePoint(ship,seconds);
    }
    void settle(const World& world,const View& view) {
        shipLogUnit=world.citadel.logUnit+std::log2(.4/(comfortRatio*shipRadius));
        for(int i=0;i<6;i++) shipLogUnit+=std::log2(std::max(wallRatio(world,view),1e-6)/comfortRatio);
    }
    void stop() {state=State::Idle;current.clear();}
    void beginTrack(const World& world,const View& view) {
        startWorld=world;startView=view;settle(world,view);current.clear();time=0;newBest=false;
        current.push_back(shipPoint(world,view,0));state=State::Recording;
    }
    // Speed in ship units, whatever the distance to the walls. throttle 1 is cruise.
    void fly(World& world,Vec3 direction,double dt,double throttle) const {
        double magnitude=direction.length();if(magnitude<1e-12) return;
        Vec3 ray=direction/magnitude;
        double remaining=shipSpeed*throttle*dt*shipScale(world.citadel);
        for(int i=0;i<96 && remaining>1e-12;i++) {
            double step=std::min(remaining,world.clearance*.7),before=world.citadel.logUnit;
            if(!world.advance(ray*step)) break;
            remaining=(remaining-step)*std::exp2(before-world.citadel.logUnit);
        }
    }
    // Ship distance to the finish in finish units; gateRadius is its free space.
    double finishDistance(const World& world,const View& view) const {
        return (raceOffset(world.citadel,finish)-shipOffset(world.citadel,view)).length()*std::exp2(std::clamp(world.citadel.logUnit-finish.logUnit,-1000.,1000.));
    }
    // Ends the laying-out flight: the ship's position becomes the finish gate.
    bool finishTrack(const World& world,const View& view) {
        if(state!=State::Recording || time<minimumSeconds) return false;
        finish=shipPoint(world,view,time);current.push_back(finish);
        // Later runs stop when they enter the gate, not at its centre. Time the
        // first flight the same way, or every repeat would beat it for free.
        Vec3 ship=shipOffset(world.citadel,view);
        double gate=gateRadius*std::exp2(std::clamp(finish.logUnit-world.citadel.logUnit,-1000.,1000.));
        size_t entered=0;
        while(entered+1<current.size() && (raceOffset(world.citadel,current[entered])-ship).length()>=gate) entered++;
        current.resize(entered+1);
        if(current.size()<2 || current.back().time<minimumSeconds*.5) {current.clear();state=State::Idle;return false;}
        best=std::move(current);current.clear();bestTime=finishedTime=best.back().time;previousBest=0;
        hasTrack=true;newBest=true;state=State::Finished;return true;
    }
    bool start(World& world,View& view) {
        if(!hasTrack) return false;
        world=startWorld;world.motionReset=true;world.cameraMotion={};view=startView;
        settle(world,view);
        current.clear();time=0;countdown=countdownSeconds;newBest=false;state=State::Countdown;return true;
    }
    // Advance by one simulation step, after the camera moved. Returns true
    // when the stored track changed (a new best run).
    bool update(const World& world,const View& view,double dt) {
        if(state==State::Countdown) {
            countdown-=dt;
            if(countdown<=0) {state=State::Running;time=0;current.clear();current.push_back(shipPoint(world,view,0));}
            return false;
        }
        if(state!=State::Recording && state!=State::Running) return false;
        time+=dt;
        if(time>maximumSeconds) {stop();return false;}
        double ratio=wallRatio(world,view);
        if(ratio<1) {finishedTime=time;current.clear();state=State::Crashed;return false;}
        shipLogUnit+=std::log2(ratio/comfortRatio)*(1-std::exp(-adaptRate*dt));
        if(state==State::Running && finishDistance(world,view)<gateRadius) {
            current.push_back(shipPoint(world,view,time));finishedTime=time;previousBest=bestTime;
            newBest=time<bestTime;
            if(newBest) {best=std::move(current);bestTime=time;}
            current.clear();state=State::Finished;return newBest;
        }
        if(time-current.back().time>=sampleInterval) current.push_back(shipPoint(world,view,time));
        return false;
    }
    // Ghost position at race time t relative to the camera (camera units).
    bool ghost(const Citadel& camera,double t,Vec3& offset) const {
        if(best.empty()) return false;
        if(t<=best.front().time) {offset=raceOffset(camera,best.front());return true;}
        if(t>=best.back().time) {offset=raceOffset(camera,best.back());return true;}
        size_t lo=0,hi=best.size()-1;
        while(lo+1<hi) {size_t mid=(lo+hi)/2;if(best[mid].time<=t) lo=mid;else hi=mid;}
        const auto& a=best[lo];const auto& b=best[hi];
        double f=(t-a.time)/std::max(b.time-a.time,1e-12);
        Vec3 from=raceOffset(camera,a),to=raceOffset(camera,b);
        offset=from+(to-from)*f;return true;
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
    static constexpr char magic[12]={'A','U','R','O','R','A','R','A','C','E','3','\n'};
};
// Lays out a track: the guided dive's steering, slowing near walls so that the
// ship has time to shrink instead of hitting them.
struct RacePilot {
    static Vec3 steer(World& world,Vec3 forward,double dt) {return world.guide(forward.unit(),dt);}
    static double throttle(const Race& race,const World& world,const View& view) {return std::clamp((race.wallRatio(world,view)-2)/8,.1,1.);}
};
}
