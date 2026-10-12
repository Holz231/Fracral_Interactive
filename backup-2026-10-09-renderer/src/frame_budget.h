#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace aurora {
// GPU samples belong to the resolution at submission, not the current target.
// Fast overload response and slow recovery avoid repeatedly missing v-sync.
struct FrameBudget {
    double costPerPixel=0,cooldown=0,lowTime=0;
    uint64_t newest=0,used=0;
    void observe(double milliseconds,double pixels,uint64_t serial) {
        if(serial<=newest || !std::isfinite(milliseconds) || milliseconds<=0 || pixels<=0) return;
        newest=serial;double sample=milliseconds/pixels;
        costPerPixel=costPerPixel==0?sample:std::max(sample,costPerPixel*.94+sample*.06);
    }
    double adjust(double seconds,double scale,double cap,double pixels,double floor=.25) {
        cooldown+=seconds;
        double predicted=costPerPixel*pixels;
        lowTime=costPerPixel>0 && predicted<8.5?lowTime+seconds:0;
        if(!costPerPixel || newest==used) return scale;
        double next=scale;
        if(predicted>14.5 && (cooldown>=.10 || predicted>22)) {
            next*=std::clamp(std::sqrt(11.5/predicted),.55,.96);lowTime=0;
        } else if(lowTime>=1.5 && cooldown>=.5) next*=1.06;
        next=std::clamp(next,std::min(floor,cap),cap);
        if(next!=scale) {cooldown=0;used=newest;}
        return next;
    }
};
}
