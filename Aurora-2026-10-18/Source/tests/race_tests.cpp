#include "race.h"
#include <iostream>
#include <string>
using namespace aurora;
static void require(bool yes,const std::string& message) {if(!yes) throw std::runtime_error(message);}
static double error(Vec3 a,Vec3 b) {return (a-b).length()/std::max(b.length(),1e-300);}
// Moves a copy of the camera in several steps and checks the recovered offset.
static void offsets(World world,const char* label) {
    const Citadel camera=world.citadel;
    Citadel near=camera;Vec3 small{.11,-.05,.2};
    require(near.move(small),std::string(label)+": small move rejected");
    require(error(raceOffset(camera,racePoint(near,0)),small)<1e-6,std::string(label)+": nearby offset is wrong");
    Citadel tiny=camera;Vec3 hair{2e-7,1e-7,-3e-7};
    require(tiny.move(hair),std::string(label)+": tiny move rejected");
    require(error(raceOffset(camera,racePoint(tiny,0)),hair)<1e-4,std::string(label)+": sub-pixel offset is wrong");
    require(raceOffset(camera,racePoint(camera,0)).length()==0,std::string(label)+": camera is not at its own position");
    // A longer path: the unit changes while moving, so sum in the first unit.
    World far=world;Vec3 expected{};Vec3 direction=Vec3{.3,.2,-.9}.unit();
    for(int i=0;i<40;i++) {
        double unit=far.citadel.logUnit;
        Vec3 step=direction*std::min(.2,far.clearance*.7);
        if(!far.citadel.move(step)) break;
        far.refresh();
        expected=expected+step*std::exp2(unit-camera.logUnit);
    }
    require(expected.length()>.5,std::string(label)+": test path did not move");
    require(error(raceOffset(camera,racePoint(far.citadel,0)),expected)<2e-3,std::string(label)+": distant offset is wrong");
}
static void fly(World& world,const View& view,Race& race,int steps,bool& changed) {
    for(int i=0;i<steps && race.ticking();i++) {
        if(!race.frozen()) world.fly(view.forward(),1./60,Race::flightSpeed);
        changed=race.update(world,1./60) || changed;
    }
}
int main() {
    try {
        World world(1);View view(1);
        offsets(world,"start");
        for(int step=0;step<100000 && world.zoomLog10<20;step++) world.advance(view.forward()*.013);
        require(world.zoomLog10>=20,"Test flight did not reach deep zoom");
        offsets(world,"zoom 1e20");

        // First flight defines the track.
        world=World(1);view=View(1);Race race;bool changed=false;
        require(!race.start(world,view),"Race started without a track");
        race.beginTrack(world,view);
        fly(world,view,race,30,changed);
        require(!race.finishTrack(world) && race.state==Race::State::Recording,"A too short track was accepted");
        fly(world,view,race,270,changed);
        require(race.finishTrack(world),"Track was not accepted");
        require(race.state==Race::State::Finished && race.hasTrack && race.best.size()>20,"Track run was not stored");
        double first=race.bestTime;
        require(first>2 && first<=5.0001,"Track time is implausible");
        require(race.finishDistance(world.citadel)<1e-9,"Finish gate is not at the end of the track");

        // Same line again: returns to the start, counts down, ends at the gate.
        Vec3 away=raceOffset(world.citadel,race.best.front());
        require(away.length()>1,"Track has no length");
        require(race.start(world,view),"Race did not start");
        require(raceOffset(world.citadel,race.best.front()).length()<1e-9,"Race did not return to the start");
        const Citadel startLine=world.citadel;
        changed=false;fly(world,view,race,179,changed);
        require(race.state==Race::State::Countdown,"Countdown ended early");
        require(raceOffset(startLine,racePoint(world.citadel,0)).length()==0,"Camera moved during the countdown");
        fly(world,view,race,2,changed);
        require(race.state==Race::State::Running,"Countdown did not end");
        fly(world,view,race,600,changed);
        require(race.state==Race::State::Finished,"Finish gate was not detected");
        require(std::abs(race.finishedTime-first)<.11,"Repeating the same line gave a different time");

        // A slower run keeps the ghost; the ghost is ahead while waiting.
        double best=race.bestTime;size_t ghostSize=race.best.size();
        require(race.start(world,view),"Second race did not start");
        changed=false;fly(world,view,race,181,changed);
        for(int i=0;i<60;i++) changed=race.update(world,1./60) || changed;
        Vec3 ghost;double unit=0;
        require(race.ghost(world.citadel,race.time,ghost,unit),"No ghost during the race");
        require(ghost.dot(view.forward())>.05 && ghost.unit().dot(view.forward())>.99,"Ghost is not ahead on the recorded line");
        fly(world,view,race,900,changed);
        require(race.state==Race::State::Finished && !race.newBest && !changed,"A slower run replaced the ghost");
        require(race.finishedTime>best+.9 && race.bestTime==best && race.best.size()==ghostSize,"Best time changed after a slower run");

        // A faster run replaces it: shorten the track by starting a new one closer.
        Race quick=race;quick.bestTime=best+10;
        require(quick.start(world,view),"Third race did not start");
        changed=false;fly(world,view,quick,182,changed);fly(world,view,quick,900,changed);
        require(quick.state==Race::State::Finished && quick.newBest && changed && quick.bestTime<best+.2,"A faster run did not become the ghost");

        auto path=std::filesystem::temp_directory_path()/L"aurora-race-test.bin";
        require(race.saveGhost(path),"Ghost was not saved");
        Race loaded;loaded.loadGhost(path);
        require(loaded.hasTrack && loaded.bestTime==race.bestTime && loaded.best.size()==race.best.size(),"Loaded ghost differs");
        require(loaded.best.back().orbit.size()==race.best.back().orbit.size() && loaded.finish.logUnit==race.finish.logUnit,"Loaded finish differs");
        require(loaded.best[7].orbit[1].x==race.best[7].orbit[1].x,"Loaded orbit differs");
        {std::ofstream damaged(path,std::ios::binary|std::ios::trunc);damaged<<"AURORARACE1\nbroken";}
        bool rejected=false;try {Race bad;bad.loadGhost(path);} catch(const std::exception&) {rejected=true;}
        std::filesystem::remove(path);
        require(rejected,"Damaged ghost file was accepted");
        std::cout<<"PASS: ghost offsets at zoom 1 and 1e20, track recording, countdown, finish gate, best time and ghost file\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
