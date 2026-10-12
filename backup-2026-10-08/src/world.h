#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace aurora {
struct Vec3 {
    double x=0,y=0,z=0;
    Vec3 operator+(Vec3 b) const {return {x+b.x,y+b.y,z+b.z};}
    Vec3 operator-(Vec3 b) const {return {x-b.x,y-b.y,z-b.z};}
    Vec3 operator*(double s) const {return {x*s,y*s,z*s};}
    Vec3 operator/(double s) const {return *this*(1/s);}
    double dot(Vec3 b) const {return x*b.x+y*b.y+z*b.z;}
    double length() const {return std::sqrt(dot(*this));}
    Vec3 unit() const {double n=length();return n>0?*this/n:Vec3{0,0,1};}
};
inline Vec3 lattice(Vec3 v) {return {.91*v.x+.22*v.y-.10*v.z,.69*v.y+.18*v.z,.18*v.x+1.04*v.z};}
inline Vec3 inverseLattice(Vec3 v) {
    double z=(v.z-.18*v.x/.91+.18*.22*v.y/(.91*.69))/(1.04+.18*.10/.91+.18*.22*.18/(.91*.69));
    double y=(v.y-.18*z)/.69;
    return {(v.x-.22*y+.10*z)/.91,y,z};
}
inline double fold(double x) {return x-2*std::floor((x+1)*.5);}
inline Vec3 fold(Vec3 v) {return {fold(v.x),fold(v.y),fold(v.z)};}
struct Parent {Vec3 n;double d,k;int level;};
inline Parent displaced(Parent p,Vec3 v) {
    double a=p.n.dot(v),r2=v.dot(v),l=std::sqrt(std::max(1+2*p.k*a+p.k*p.k*r2,1e-30));
    return {(p.n+v*p.k)/l,p.d-(2*a+p.k*r2)/(1+l),p.k/l,p.level};
}
struct Chart {Vec3 camera,child;std::vector<Parent> parents;};
struct Warp {Vec3 signs{1,1,1},normal{};bool sphere=false,inverse=false;};
inline Vec3 multiply(Vec3 a,Vec3 b) {return {a.x*b.x,a.y*b.y,a.z*b.z};}
inline Vec3 transport(Vec3 v,const Warp& w) {
    if(w.inverse) {if(w.sphere) v=v-w.normal*(2*w.normal.dot(v));return multiply(v,w.signs);}
    v=multiply(v,w.signs);return w.sphere?v-w.normal*(2*w.normal.dot(v)):v;
}
struct JuliaChart {Vec3 signs,offset,normal;int sphereBranch;};
inline Vec3 boxFold(Vec3 v) {return {2*std::clamp(v.x,-1.,1.)-v.x,2*std::clamp(v.y,-1.,1.)-v.y,2*std::clamp(v.z,-1.,1.)-v.z};}
struct Float4 {float x=0,y=0,z=0,w=0;};
struct World {
    static constexpr double radius=1.32,scale=5;
    static constexpr int maxDepth=18,maxParents=48;
    Vec3 camera{.64,.70,.59};
    int kind=0;
    Vec3 juliaConstant{1.4,1.4,.7};
    double juliaScale=2.8;
    std::vector<JuliaChart> juliaHistory;
    std::vector<Warp> warps;
    double juliaLogScale=0;
    std::vector<Parent> parents;
    std::vector<Chart> history;
    int level=0,rebases=0,unwinds=0,passages=0,depth=8,parentCount=0;
    double clearance=0,worldScale=1,initialClearance=1,zoomLog10=0,guideTimer=0;
    int nearSurfaceFrames=0;
    bool hasDestination=false;
    Vec3 destination;
    double destinationRadius=0;
    std::array<Float4,maxDepth> orbit{},octaves{};
    std::array<Float4,maxParents> parentData{},parentMeta{};
    explicit World(int type=0):kind(type) {
        if(kind==1) camera={6.5,5.4,-9.5};
        parents.reserve(64);refresh();initialClearance=clearance;prepare();
    }
    Vec3 toDomain(Vec3 v) const {return kind==1?v:lattice(v);}
    Vec3 fromDomain(Vec3 v) const {return kind==1?v:inverseLattice(v);}
    Vec3 rootCamera() const {
        if(kind!=1) return camera;
        Vec3 p=camera;
        for(auto it=juliaHistory.rbegin();it!=juliaHistory.rend();++it) {
            Vec3 q=(p-juliaConstant)/juliaScale;
            double q2=q.dot(q),k=it->sphereBranch==0?.25:it->sphereBranch==1?1/std::max(q2,1e-30):1;
            p=multiply(q*k-it->offset,it->signs);
        }
        return p;
    }
    Vec3 rootDirection(Vec3 v) const {
        if(kind!=1) return v;
        for(auto it=juliaHistory.rbegin();it!=juliaHistory.rend();++it) {
            Warp w{it->signs*(juliaScale<0?-1.:1.),it->normal,it->sphereBranch==1,true};
            v=transport(v,w);
        }
        return v.unit();
    }
    double juliaDistance(Vec3 p,int iterations=17) const {
        double derivative=1;
        for(int i=0;i<iterations;i++) {
            p=boxFold(p);double r2=p.dot(p),k=1/std::clamp(r2,.25,1.);
            p=p*(k*juliaScale)+juliaConstant;derivative*=k*std::abs(juliaScale);
            if(p.dot(p)>4096) break;
        }
        return .45*p.length()/derivative;
    }
    double distance(Vec3 v,int iterations=maxDepth,bool optimized=true) const {
        if(kind==1) return juliaDistance(v,std::min(17,iterations));
        double best=-std::numeric_limits<double>::infinity();
        Vec3 delta=v-camera;
        double r2=delta.dot(delta);
        for(const Parent& p:parents) {
            double a=p.n.dot(delta),l=std::sqrt(std::max(1+2*p.k*a+p.k*p.k*r2,1e-30));
            best=std::max(best,p.d-(2*a+p.k*r2)/(1+l));
        }
        double frequency=1;
        for(int i=0;i<iterations;i++,frequency*=scale) {
            // Exact upper bound: later octaves cannot exceed their radius.
            if(optimized && best>=radius/frequency) break;
            best=std::max(best,(radius-fold(v*frequency).length())/frequency);
        }
        return best;
    }
    void refresh() {
        clearance=distance(camera);
        if(!(clearance>0) || !std::isfinite(clearance)) throw std::runtime_error("Invalid camera clearance");
        worldScale=std::min(.8,clearance*2.5);
        depth=std::clamp(int(std::ceil(-std::log(worldScale*.00012)/std::log(scale)))+1,6,maxDepth);
        if(kind==1) depth=17;
    }
    bool advance(Vec3 v) {
        double n=v.length();if(n==0) return false;
        v=v*std::min(1.,clearance*.32/n);
        // A nominal step can straddle a very thin wall at deep zoom.  Refine
        // it instead of rejecting the whole input, so reachable chambers do
        // not feel sealed while the signed-distance collision remains intact.
        double fraction=1.;
        for(int attempt=0;attempt<9 && distance(camera+v*fraction)<=0;attempt++) fraction*=.5;
        if(distance(camera+v*fraction)<=0) return false;
        v=v*fraction;
        for(auto& p:parents) p=displaced(p,v);
        camera=camera+v;refresh();
        int work=0;
        if(kind==1) {
            // Hold the first near-surface frame briefly so the pilot can
            // actually arrive at a corner before the next chart opens.
            if(clearance<.0001) {
                if(++nearSurfaceFrames>=4) {
                    nearSurfaceFrames=0;
                    while(clearance<.0001 && work++<24) zoomIn();
                }
            } else nearSurfaceFrames=0;
            while(level>0 && clearance>.005 && work++<48) zoomOut();
        } else {
            while(clearance<.002 && work++<12) zoomIn();
            while(level>0 && clearance>.03 && work++<24) zoomOut();
        }
        return true;
    }
    void zoomIn() {
        if(kind==1) {
            Vec3 signs{std::abs(camera.x)>1?-1.:1.,std::abs(camera.y)>1?-1.:1.,std::abs(camera.z)>1?-1.:1.};
            Vec3 q=boxFold(camera),offset=q-multiply(camera,signs);
            double r2=q.dot(q),k=1/std::clamp(r2,.25,1.);
            int branch=r2<.25?0:r2<1?1:2;
            juliaHistory.push_back({signs,offset,q.unit(),branch});
            warps.push_back({signs*(juliaScale<0?-1.:1.),q.unit(),branch==1,false});
            if(hasDestination) destination=transport(destination,warps.back());
            camera=q*(k*juliaScale)+juliaConstant;
            juliaLogScale+=std::log10(k*std::abs(juliaScale));level++;rebases++;refresh();return;
        }
        Chart chart{camera,{},parents};
        Vec3 q=fold(camera);
        for(int x=-1;x<=1;x++) for(int y=-1;y<=1;y++) for(int z=-1;z<=1;z++) {
            Vec3 v=q-Vec3{2.*x,2.*y,2.*z};double r=v.length();
            if(r>1e-12) parents.push_back({v/r,radius-r,1/r,level});
        }
        for(auto& p:parents) {p.d*=scale;p.k/=scale;}
        parents.erase(std::remove_if(parents.begin(),parents.end(),[](const Parent& p){return p.d<-128;}),parents.end());
        Vec3 next=fold(camera*scale),offset=camera*scale-next;
        if(hasDestination) {destination=destination*scale-offset;destinationRadius*=scale;}
        camera=next;chart.child=camera;history.push_back(std::move(chart));
        level++;rebases++;refresh();
    }
    void zoomOut() {
        if(kind==1) {
            if(juliaHistory.empty()) return;
            auto chart=juliaHistory.back();juliaHistory.pop_back();
            Vec3 q=(camera-juliaConstant)/juliaScale;
            double k=chart.sphereBranch==0?.25:chart.sphereBranch==1?1/q.dot(q):1;
            warps.push_back({chart.signs*(juliaScale<0?-1.:1.),q.unit(),chart.sphereBranch==1,true});
            if(hasDestination) destination=transport(destination,warps.back());
            camera=multiply(q*k-chart.offset,chart.signs);
            juliaLogScale+=std::log10(k/std::abs(juliaScale));level--;unwinds++;refresh();return;
        }
        if(history.empty()) return;
        Chart chart=std::move(history.back());history.pop_back();
        Vec3 delta=(camera-chart.child)/scale;
        if(hasDestination) {destination=chart.camera+(destination-chart.child)/scale;destinationRadius/=scale;}
        parents=std::move(chart.parents);
        for(auto& p:parents) p=displaced(p,delta);
        camera=chart.camera+delta;level--;unwinds++;refresh();
    }
    void choosePassage(Vec3 forward) {
        int octave=std::max(0,int(std::round(std::log(radius/(clearance*3.5))/std::log(scale))));
        double best=-1e30;
        for(int i=octave;i<=octave+1;i++) {
            double frequency=std::pow(scale,i),r=radius/frequency;
            Vec3 focal=(camera+forward*(clearance*9))*(frequency*.5);
            Vec3 cell{std::round(focal.x),std::round(focal.y),std::round(focal.z)};
            for(int x=-1;x<=1;x++) for(int y=-1;y<=1;y++) for(int z=-1;z<=1;z++) {
                Vec3 pos=(cell+Vec3{double(x),double(y),double(z)})*(2/frequency);
                Vec3 delta=pos-camera;double n=delta.length();
                if(n<r*1.25 || n>clearance*20) continue;
                Vec3 dir=delta/n;double alignment=dir.dot(forward);
                if(alignment<.94) continue;
                double score=alignment*5-std::abs(n/clearance-8)*.025;
                if(score<=best) continue;
                double t=0;bool clear=true;
                for(int k=0;k<72 && t<n-r*.55;k++) {
                    double d=distance(camera+dir*t,14);
                    if(d<clearance*.05) {clear=false;break;}
                    t+=d*.8;
                }
                if(clear && t>=n-r*.55) {best=score;destination=pos;destinationRadius=r;hasDestination=true;}
            }
        }
    }
    Vec3 guide(Vec3 forward,double dt) {
        if(kind==1) {
            // Probe actual ray paths, rejecting directions that escape into sky.
            // Prefer nearby openings while keeping the dive aimed into detail.
            guideTimer-=dt;
            if(guideTimer<=0) {
                Vec3 right=Vec3{forward.z,0,-forward.x}.unit();
                Vec3 up{0,1,0};double best=-1e30;Vec3 chosen=(juliaConstant*.3-camera).unit();
                for(int x=-2;x<=2;x++) for(int y=-2;y<=2;y++) {
                    Vec3 candidate=(forward+right*(x*.16)+up*(y*.16)).unit();
                    double t=0,d=clearance;
                    for(int step=0;step<64 && t<clearance*24;step++) {
                        d=distance(camera+candidate*t);if(d<clearance*.015) break;t+=d*.85;
                    }
                    if(d>=clearance*.015) continue;
                    double score=candidate.dot(forward)*3+std::min(t/clearance,12.)*.035;
                    if(score>best) {best=score;chosen=candidate;}
                }
                destination=chosen;hasDestination=true;guideTimer=.35;
            }
            if(hasDestination) return (forward+(destination-forward)*(1-std::exp(-dt*.7))).unit();
            return forward;
        }
        guideTimer-=dt;
        if(hasDestination) {
            Vec3 delta=destination-camera;double n=delta.length();
            if(n<destinationRadius*.3) {passages++;hasDestination=false;guideTimer=1.2;}
            else return (forward+(delta/n-forward)*(1-std::exp(-dt*1.5))).unit();
        }
        if(clearance<.045 && guideTimer<=0) {choosePassage(forward);guideTimer=.8;}
        return forward;
    }
    void prepare() {
        if(kind==1) {
            Vec3 p=camera;
            for(int i=0;i<17;i++) {
                Vec3 q=boxFold(p);double r2=q.dot(q),denom=std::clamp(r2,.25,1.);
                parentMeta[i]={float(p.x),float(p.y),float(p.z),0};
                orbit[i]={float(q.x),float(q.y),float(q.z),0};
                octaves[i]={float(r2),float(denom),float(juliaScale),0};
                p=q*(juliaScale/denom)+juliaConstant;
                parentData[i]={float(p.x),float(p.y),float(p.z),0};
            }
            parentCount=0;depth=17;
            zoomLog10=juliaLogScale+std::log10(initialClearance/clearance);return;
        }
        double frequency=1;
        for(int i=0;i<depth;i++,frequency*=scale) {
            Vec3 q=fold(camera*frequency);
            orbit[i]={float(q.x),float(q.y),float(q.z),float(radius-q.length())};
            double s=frequency*worldScale;
            octaves[i]={float(s),float(1/s),float(radius/s),0};
        }
        parentCount=0;
        for(const auto& p:parents) {
            if(p.d < -worldScale*35) continue;
            if(parentCount==maxParents) throw std::runtime_error("Cavity budget exceeded");
            parentData[parentCount]={float(p.n.x),float(p.n.y),float(p.n.z),float(p.d/worldScale)};
            parentMeta[parentCount++]={float(p.k*worldScale),float(p.level%1000),0,0};
        }
        zoomLog10=level*std::log10(scale)+std::log10(initialClearance/clearance);
    }
};
struct View {
    double yaw=0,pitch=0;
    Vec3 axisX{1,0,0},axisY{0,1,0},axisZ{0,0,1};
    explicit View(int kind=0) {Vec3 v=(kind==1?Vec3{-6.5,-5.4,9.5}:inverseLattice({.36,.30,.41})).unit();yaw=std::atan2(v.x,v.z);pitch=std::asin(v.y);}
    Vec3 frame(Vec3 v) const {return axisX*v.x+axisY*v.y+axisZ*v.z;}
    Vec3 forward() const {return frame({std::sin(yaw)*std::cos(pitch),std::sin(pitch),std::cos(yaw)*std::cos(pitch)});}
    Vec3 right() const {return frame({std::cos(yaw),0,-std::sin(yaw)});}
    Vec3 up() const {return frame({-std::sin(yaw)*std::sin(pitch),std::cos(pitch),-std::cos(yaw)*std::sin(pitch)});}
    void face(Vec3 v) {v=v.unit();v={v.dot(axisX),v.dot(axisY),v.dot(axisZ)};yaw=std::atan2(v.x,v.z);pitch=std::asin(std::clamp(v.y,-1.,1.));}
    void apply(const Warp& w) {axisX=transport(axisX,w).unit();axisY=transport(axisY,w).unit();axisZ=transport(axisZ,w).unit();}
};
}
