#include "world.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <string>
using namespace aurora;

int main(int argc,char** argv) {
    try {
        if(argc!=6) throw std::runtime_error("Usage: audit flight samples.csv output.csv width height");
        std::ifstream flight(argv[1]);std::string line;std::getline(flight,line);
        if(line!="AURORA_FLIGHT_1") throw std::runtime_error("Invalid flight header");
        auto number=[&](){double v;if(!(flight>>v)||!std::isfinite(v)) throw std::runtime_error("Invalid flight number");return v;};
        auto vector=[&](){return Vec3{number(),number(),number()};};
        World world(1);View view(1);view.yaw=number();view.pitch=number();
        view.axisX=vector();view.axisY=vector();view.axisZ=vector();world.citadel.constant=vector();
        double unit=number();int count=int(number());if(count<1||count>Citadel::capacity) throw std::runtime_error("Invalid orbit count");
        world.citadel.reference.resize(count);
        for(auto& sample:world.citadel.reference) {sample.p=vector();sample.next=vector();}
        world.citadel.metadata();world.citadel.logUnit=unit;
        const double width=std::stod(argv[4]),height=std::stod(argv[5]),epsilon=.65/(height*1.85);
        std::ifstream samples(argv[2]);std::ofstream out(argv[3]);if(!samples||!out) throw std::runtime_error("Cannot open audit files");
        std::getline(samples,line);
        out<<"x,y,baseline_log2,candidate_log2,cone_log2,baseline_de_over_epsilon,candidate_de_over_epsilon,cpu_log2,cpu_steps,cpu_hit,cone_passed_cpu_hit,baseline_status,candidate_status\n"<<std::setprecision(15);
        int completed=0;
        while(std::getline(samples,line)) {
            std::replace(line.begin(),line.end(),',',' ');std::istringstream row(line);
            int x,y;double before,after,cone;if(!(row>>x>>y>>before>>after>>cone)) throw std::runtime_error("Invalid sample row");
            int beforeStatus=1,afterStatus=1;row>>beforeStatus>>afterStatus;
            Vec3 direction=(view.right()*((2*(x+.5)-width)/height)+view.up()*(-(2*(y+.5)-height)/height)+view.forward()*1.85).unit();
            auto ratio=[&](double logTravel){double t=std::exp2(logTravel);return world.citadel.distance(direction*t)/t;};
            double t=std::exp2(-7.),limit=std::exp2(std::max(before,after)+1),cpu=-1000;int step=0;
            for(;step<131072 && t<limit;step++) {
                double distance=world.citadel.distance(direction*t);
                if(!std::isfinite(distance)||distance<0) throw std::runtime_error("Non-finite CPU field");
                if(distance<epsilon*t) {cpu=std::log2(t);break;}
                t+=std::max(distance*.8,t*1e-8);
            }
            out<<x<<','<<y<<','<<before<<','<<after<<','<<cone<<','<<ratio(before)/epsilon<<','<<ratio(after)/epsilon<<','<<cpu<<','<<step<<','<<(cpu!=-1000)<<','<<(cpu!=-1000 && cone>cpu)<<','<<beforeStatus<<','<<afterStatus<<'\n';
            if(++completed%32==0) {out.flush();std::cout<<"Audited "<<completed<<" rays\n"<<std::flush;}
        }
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
