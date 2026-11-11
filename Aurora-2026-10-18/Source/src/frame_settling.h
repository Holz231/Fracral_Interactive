#pragma once

namespace aurora {
// Count completed still frames, so message wakes cannot shorten accumulation.
class FrameSettling {
    int remaining=0;
public:
    bool pending() const {return remaining>0;}
    void clear() {remaining=0;}
    void rendered(bool moving,bool temporal) {
        if(!temporal) clear();
        else if(moving) remaining=48;
        else if(remaining>0) --remaining;
    }
};
}
