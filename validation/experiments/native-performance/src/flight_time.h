#pragma once
#include <algorithm>
#include <cmath>

namespace aurora {
// Preserve elapsed flight time during expensive frames. Small simulation
// steps retain collision and steering behaviour; a long suspension is capped.
template<class Update> void advanceFlightTime(double elapsed,Update&& update) {
    if(!std::isfinite(elapsed) || elapsed<=0) return;
    double duration=std::min(elapsed,.25);
    int count=std::max(1,int(std::ceil(duration*60)));
    for(int i=0;i<count;i++) update(duration/count);
}
}
