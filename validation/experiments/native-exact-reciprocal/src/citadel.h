#pragma once
// Included by world.h after Vec3/Float4. The camera is represented by its
// reference orbit, so moving deeper never substitutes a different Julia set.
namespace aurora {
struct Citadel {
    static constexpr int capacity=384;
    struct Sample {Vec3 p,q,next,x{1,0,0},y{0,1,0},z{0,0,1},pole{};double logDerivative=0,limit=1024,denom=1,renderLimit=1024;};
    struct GpuSample {Float4 p,q,next,x,y,z,curve;};
    std::vector<Sample> reference;
    double logUnit=0,clearance=1;
    Vec3 constant{1.4,1.4,.7};
    static constexpr double expansion=2.8;
    static constexpr double boundsPadding=1e-13;
    std::array<Vec3,2> outerBounds() const {
        // The alternating box reflections have a period-two envelope. Outside
        // it, each two iterations expand the excess by at least scale^2; a
        // sphere fold can only move that component farther outside the envelope.
        double s=expansion;Vec3 base{2*s*(1+s),2*s*(1+s),2*s*(1+s)};
        Vec3 high=(base+constant*(s-1))/(s*s-1);
        return {Vec3{2*s,2*s,2*s}+constant-high*s,high};
    }
    std::pair<double,double> relativePlane(int axis,int side) const {
        auto box=outerBounds();auto component=[&](Vec3 p){return axis==0?p.x:axis==1?p.y:p.z;};
        // The outer planes alternate between their two analytic bounds under
        // an affine fold. Read their offset from the deepest matching orbit
        // sample, where camera motion is still represented accurately. A fixed
        // root-space epsilon would grow into kilometres of empty camera space.
        size_t depth=0;int currentSide=side;
        while(depth+1<reference.size()) {
            const auto& s=reference[depth];double p=component(s.p);
            if(s.denom!=1 || (currentSide?p<=1:p>=-1)) break;
            depth++;currentSide=1-currentSide;
        }
        double d=(component(box[currentSide])-component(reference[depth].p))*(depth%2?-1:1);
        d+=(side?boundsPadding:-boundsPadding);
        return {d,-double(depth)*std::log2(expansion)};
    }
    std::array<Float4,2> cameraBounds() const {
        std::array<Float4,2> result{};
        // Store signed logarithmic offsets so deep camera units cannot overflow.
        for(int side=0;side<2;side++) {
            auto x=relativePlane(0,side),y=relativePlane(1,side),z=relativePlane(2,side);
            auto logarithm=[&](std::pair<double,double> p){return float(std::log2(std::max(1e-300,std::abs(p.first)))+p.second-logUnit);};
            int signs=(x.first>=0?1:0)|(y.first>=0?2:0)|(z.first>=0?4:0);
            result[side]={logarithm(x),logarithm(y),logarithm(z),float(signs)};
        }
        return result;
    }
    static Vec3 foldPoint(Vec3 p) {return boxFold(p);}
    static double foldedDelta(double p,double q,double d) {
        double t=p+d;
        if((p>1 && t>1)||(p< -1 && t< -1)) return -d;
        if(std::abs(p)<=1 && std::abs(t)<=1) return d;
        return 2*std::clamp(t,-1.,1.)-t-q;
    }
    static Vec3 perturb(const Sample& s,Vec3 d) {
        d={foldedDelta(s.p.x,s.q.x,d.x),foldedDelta(s.p.y,s.q.y,d.y),foldedDelta(s.p.z,s.q.z,d.z)};
        double r2=s.q.dot(s.q),change=2*s.q.dot(d)+d.dot(d);
        double dc=std::clamp(change,.25-r2,1-r2)-std::clamp(0.,.25-r2,1-r2);
        return (d-s.q*(dc/s.denom))*(expansion/(s.denom+dc));
    }
    static Vec3 orient(Vec3 v,const Sample& s) {
        v=multiply(v,{std::abs(s.p.x)>1?-1.:1.,std::abs(s.p.y)>1?-1.:1.,std::abs(s.p.z)>1?-1.:1.});
        double r2=s.q.dot(s.q);
        return r2>.25 && r2<1?v-s.q*(2*s.q.dot(v)/r2):v;
    }
    void metadata() {
        double derivative=0,limit=1024,renderLimit=1024;Vec3 x{1,0,0},y{0,1,0},z{0,0,1},pole{};
        for(auto& s:reference) {
            s.q=foldPoint(s.p);double r=s.q.length();s.denom=std::clamp(r*r,.25,1.);
            s.x=x;s.y=y;s.z=z;s.pole=pole;s.logDerivative=derivative;s.limit=limit;s.renderLimit=renderLimit;
            // The skipped prefix is linear to much less than a pixel. Include
            // both branch boundaries and sphere curvature in the bound.
            double bound=std::min({.01,std::abs(std::abs(s.p.x)-1),std::abs(std::abs(s.p.y)-1),std::abs(std::abs(s.p.z)-1),std::abs(r-.5),std::abs(r-1)});
            limit=std::min(limit,std::log2(std::max(1e-300,bound*1e-4))-derivative);
            // A fold prefix is a conformal (Mobius) map within its branches.
            // Its displacement is bounded by u/(1-|pole|*u), so this radius
            // preserves every box/sphere branch without a linear approximation.
            double branch=std::max(0.,std::min({std::abs(std::abs(s.p.x)-1),std::abs(std::abs(s.p.y)-1),std::abs(std::abs(s.p.z)-1),std::abs(r-.5),std::abs(r-1),64-s.p.length()}))*.9;
            double radius=branch/(1+pole.length()*branch);
            renderLimit=std::min(renderLimit,std::log2(std::max(1e-300,radius))-derivative);
            pole=multiply(pole,{std::abs(s.p.x)>1?-1.:1.,std::abs(s.p.y)>1?-1.:1.,std::abs(s.p.z)>1?-1.:1.});
            if(r>.5 && r<1) {pole=pole+s.q/(r*r);pole=pole-s.q*(2*s.q.dot(pole)/(r*r));}
            pole=pole/(expansion/s.denom);
            x=orient(x,s);y=orient(y,s);z=orient(z,s);
            derivative+=std::log2(expansion/s.denom);
        }
        const auto& last=reference.back();
        double logDistance=std::log2(.45*last.next.length())-last.logDerivative-std::log2(expansion/last.denom);
        logUnit=logDistance+std::log2(2.5);
        clearance=.4;
    }
    void reset(Vec3 p) {
        reference.clear();logUnit=0;
        for(int i=0;i<capacity;i++) {
            Sample s;s.p=p;s.q=foldPoint(p);s.denom=std::clamp(s.q.dot(s.q),.25,1.);
            p=s.q*(expansion/s.denom)+constant;s.next=p;reference.push_back(s);
            if(p.dot(p)>4096) break;
        }
        metadata();
    }
    int start(double logRadius) const {
        int lo=0,hi=int(reference.size());
        while(lo+1<hi) {int mid=(lo+hi)/2;if(logRadius<reference[mid].limit) lo=mid;else hi=mid;}
        return lo;
    }
    // Return distance in camera units. Same reference/perturbation recurrence
    // and escape radius as the GPU; no synthetic horizon or scene switching.
    double distance(Vec3 offset) const {
        double size=offset.length();int first=start(logUnit+std::log2(std::max(size,1e-300)));
        const auto& a=reference[first];
        double dlog=logUnit+a.logDerivative;
        Vec3 delta=(a.x*offset.x+a.y*offset.y+a.z*offset.z)*std::exp2(dlog),p=a.p+delta;
        int end=std::min(capacity,int(reference.size())+12);
        for(int i=first;i<end;i++) {
            if(i<int(reference.size())) {
                const auto& s=reference[i];Vec3 q=s.q+Vec3{foldedDelta(s.p.x,s.q.x,delta.x),foldedDelta(s.p.y,s.q.y,delta.y),foldedDelta(s.p.z,s.q.z,delta.z)};
                double k=expansion/std::clamp(q.dot(q),.25,1.);
                delta=perturb(s,delta);p=s.next+delta;dlog+=std::log2(k);
            } else {Vec3 q=foldPoint(p);double k=expansion/std::clamp(q.dot(q),.25,1.);p=q*k+constant;dlog+=std::log2(k);}
            if(p.dot(p)>4096) break;
        }
        return .45*p.length()*std::exp2(-dlog);
    }
    bool move(Vec3 offset) {
        int first=start(logUnit+std::log2(std::max(offset.length(),1e-300)));
        const auto& a=reference[first];
        Vec3 delta=(a.x*offset.x+a.y*offset.y+a.z*offset.z)*std::exp2(logUnit+a.logDerivative);
        // Retain small changes along the entire orbit. Early samples may be
        // below double precision, but their magnified descendants still move.
        auto old=reference;
        for(int i=0;i<first;i++) {
            const auto& s=old[i];double k=std::exp2(logUnit+s.logDerivative);
            Vec3 d=(s.x*offset.x+s.y*offset.y+s.z*offset.z)*k;
            reference[i].p=s.p+d;
            reference[i].next=s.next+perturb(s,d);
        }
        Vec3 p=old[first].p+delta;reference.resize(first);
        for(int i=first;i<capacity;i++) {
            Sample s;s.p=p;
            if(i<int(old.size())) {delta=perturb(old[i],delta);p=old[i].next+delta;}
            else {Vec3 q=foldPoint(p);p=q*(expansion/std::clamp(q.dot(q),.25,1.))+constant;}
            s.next=p;reference.push_back(s);
            if(p.dot(p)>4096) break;
        }
        // An unescaped orbit at the capacity limit has no trustworthy distance.
        // Keep the previous camera instead of inventing a new close surface.
        if(reference.back().next.dot(reference.back().next)<=4096) {
            reference=std::move(old);return false;
        }
        metadata();return true;
    }
    std::array<GpuSample,capacity> gpu() const {
        std::array<GpuSample,capacity> result{};
        auto f=[](Vec3 v,double w){return Float4{float(v.x),float(v.y),float(v.z),float(w)};};
        // y.w/z.w retain signed distances to the sphere-fold boundaries. A
        // rounded radius can equal 0.25 or 1 even when the reference is still
        // many camera units from that branch at a deep zoom. Subtract first
        // in double precision, then pack the small differences themselves.
        for(size_t i=0;i<reference.size();i++) {
            const auto& s=reference[i];double r2=s.q.dot(s.q);
            result[i]={f(s.p,logUnit+s.logDerivative),f(s.q,s.denom),f(s.next,1.0f/float(s.denom)),
                f(s.x,s.limit-logUnit),f(s.y,.25-r2),f(s.z,1-r2),f(s.pole,s.renderLimit-logUnit)};
        }
        return result;
    }
};
}
