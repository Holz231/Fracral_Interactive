#include "world.h"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
using namespace aurora;
static void require(bool condition,const char* message) {if(!condition) throw std::runtime_error(message);}
int main() {
    try {
        std::mt19937 random(4070);std::uniform_real_distribution<double> unit(-1,1);
        for(int i=0;i<1000;i++) {
            Vec3 v{unit(random),unit(random),unit(random)};
            require((inverseLattice(lattice(v))-v).length()<1e-12,"View/movement transforms disagree");
        }
        World world;Vec3 heading=Vec3{.36,.30,.41}.unit();
        double maxZoom=0;int comparisons=0,maxParents=0,continuity=0;
        for(int frame=0;frame<36000;frame++) {
            heading=world.guide(heading,1./60);
            world.advance(heading*(world.clearance*.95*1.9/60));world.prepare();
            maxZoom=std::max(maxZoom,world.zoomLog10);maxParents=std::max(maxParents,world.parentCount);
            require(world.clearance>0 && std::isfinite(world.clearance),"Flight entered invalid/solid space");
            if(frame%120==0) for(int sample=0;sample<64;sample++) {
                Vec3 p=world.camera+Vec3{unit(random),unit(random),unit(random)}*(world.clearance*20);
                require(std::abs(world.distance(p)-world.distance(p,18,false))<1e-12,"Hierarchy culling changed the distance");comparisons++;
            }
            if(frame%1800==1799) {
                Vec3 camera=world.camera;int level=world.level;
                std::array<Vec3,12> offsets;std::array<double,12> distances;
                double span=std::min(.02,world.clearance*5);
                for(int i=0;i<12;i++) {offsets[i]=Vec3{unit(random),unit(random),unit(random)}*span;distances[i]=world.distance(camera+offsets[i]);}
                world.zoomIn();
                for(int i=0;i<12;i++) {require(std::abs(world.distance(world.camera+offsets[i]*5)/5-distances[i])<3e-8,"Zoom changed nearby geometry");continuity++;}
                world.zoomOut();require(world.level==level && (world.camera-camera).length()<1e-12,"Reverse zoom failed");
            }
        }
        require(world.passages>=12,"Guided flight did not enter small openings");
        World deep;heading=Vec3{.36,.30,.41}.unit();
        for(int i=0;i<20000;i++) {
            deep.advance(heading*(deep.clearance*.95*1.9/60));deep.prepare();
            maxZoom=std::max(maxZoom,deep.zoomLog10);
            require(std::isfinite(deep.clearance) && deep.clearance>0,"Deep zoom lost precision");
        }
        require(maxZoom>14 && deep.rebases>25,"Deep coordinate rescaling was not exercised");
        require(maxParents<World::maxParents,"GPU parent capacity exceeded");
        World bench;std::vector<Vec3> samples;samples.reserve(120000);
        for(int i=0;i<120000;i++) samples.push_back({unit(random)*3,unit(random)*3,unit(random)*3});
        volatile double checksum=0;
        auto measure=[&](bool fast) {
            auto start=std::chrono::steady_clock::now();
            for(int repeat=0;repeat<3;repeat++) for(Vec3 p:samples) checksum+=bench.distance(p,18,fast);
            return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
        };
        double baseline=measure(false),optimized=measure(true);
        std::filesystem::create_directories("validation");std::ofstream out("validation/cpu-validation.json");
        out<<std::fixed<<std::setprecision(4)<<"{\n  \"guided_minutes\": 10,\n  \"passages_entered\": "<<world.passages
            <<",\n  \"distance_comparisons\": "<<comparisons<<",\n  \"zoom_continuity_checks\": "<<continuity
            <<",\n  \"max_zoom_power_of_ten\": "<<maxZoom<<",\n  \"deep_coordinate_changes\": "<<deep.rebases
            <<",\n  \"max_parent_cavities\": "<<maxParents<<",\n  \"queries\": 360000,\n  \"baseline_cpu_ms\": "<<baseline
            <<",\n  \"optimized_cpu_ms\": "<<optimized<<",\n  \"cpu_speedup\": "<<baseline/optimized
            <<"\n}\n";
        std::cout<<"PASS: "<<comparisons<<" exact-distance comparisons, "<<continuity<<" continuous zoom checks, "<<world.passages
            <<" passages; deep zoom 10^"<<maxZoom<<". CPU query speedup: "<<baseline/optimized<<"x.\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
