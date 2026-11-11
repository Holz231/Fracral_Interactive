#include "frame_settling.h"
#include <iostream>
#include <stdexcept>
using namespace aurora;
static void require(bool yes,const char* message) {if(!yes) throw std::runtime_error(message);}
int main() {
    try {
        FrameSettling settle;
        require(!settle.pending(),"New view scheduled unnecessary frames");
        settle.rendered(true,true);
        // A busy message queue can wake the loop repeatedly before a frame is ready.
        for(int wake=0;wake<1000;wake++) require(settle.pending(),"Input consumed the still-frame budget");
        for(int frame=0;frame<47;frame++) {
            settle.rendered(false,true);
            require(settle.pending(),"Temporal accumulation ended too soon");
        }
        settle.rendered(false,true);require(!settle.pending(),"Stationary view never went idle");
        settle.rendered(true,true);
        for(int frame=0;frame<20;frame++) settle.rendered(false,true);
        settle.rendered(true,true); // Mouse look or new history restarts accumulation.
        int rendered=0;
        while(settle.pending()) {settle.rendered(false,true);require(++rendered<=48,"Unbounded still frames");}
        require(rendered==48,"Changed view did not get a complete accumulation");
        settle.rendered(true,false);require(!settle.pending(),"Non-temporal renderer wasted still frames");
        settle.rendered(true,true);settle.rendered(false,false);
        require(!settle.pending(),"Switching worlds retained temporal work");
        settle.rendered(true,true);settle.clear();require(!settle.pending(),"Suspended window kept rendering");
        std::cout<<"PASS: completed-frame settling, input wakes, camera changes and non-temporal idle\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
