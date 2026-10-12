#include "frame_budget.h"
#include <iostream>
#include <stdexcept>
using namespace aurora;
static void require(bool ok,const char* message) {if(!ok) throw std::runtime_error(message);}
int main() {try {
    FrameBudget budget;double scale=1,pixels=2000000;
    budget.observe(300,pixels,1);
    scale=budget.adjust(1./60,scale,1,pixels);
    require(scale<.6,"A severe spike must react in the next frame, including samples above 200 ms");
    double held=scale;
    for(int i=0;i<120;i++) scale=budget.adjust(1./60,scale,1,pixels*scale*scale);
    require(scale==held,"A stale timestamp must not repeatedly lower the resolution");
    budget.observe(300,pixels,2);
    scale=budget.adjust(1./60,scale,1,pixels*scale*scale);
    require(scale>=.25 && scale<held,"Second overload observation did not converge");
    FrameBudget largeDisplay;double largeScale=.25;
    for(int i=0;i<30;i++) {
        double area=3840.*2160*largeScale*largeScale;
        largeDisplay.observe(area*60/(960.*540),area,i+1);
        largeScale=largeDisplay.adjust(1./60,largeScale,1,area,.125);
    }
    require(largeScale<.16 && largeScale>=.125,"4K emergency resolution floor did not relieve corner overload");
    auto cost=budget.costPerPixel;budget.observe(.1,pixels,1);
    require(budget.costPerPixel==cost,"Out-of-order sample changed the budget");
    FrameBudget normalized;normalized.observe(40,pixels,1);
    double small=.5;
    for(int i=0;i<60;i++) small=normalized.adjust(1./60,small,1,pixels*.25);
    require(small==.5,"Old high-resolution timing was applied to a smaller target");
    FrameBudget recovery;double recovered=.3;
    for(int i=0;i<60;i++) {recovery.observe(5,pixels*.09,i+1);recovered=recovery.adjust(1./60,recovered,1,pixels*recovered*recovered);}
    require(recovered==.3,"Resolution recovered before the low-load hysteresis elapsed");
    for(int i=60;i<150;i++) {recovery.observe(5,pixels*.09,i+1);recovered=recovery.adjust(1./60,recovered,1,pixels*recovered*recovered);}
    require(recovered>.3 && recovered<.4,"Slow recovery did not work at small resolution scales");
    std::cout<<"PASS: immediate overload response, resolution-aware timing, stale samples and hysteresis\n";return 0;
} catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}}
