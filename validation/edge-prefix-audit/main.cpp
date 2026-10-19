#include "world.h"
#include <fstream>
#include <iostream>
#include <iomanip>
#include <random>
#include <string>
using namespace aurora;
int main(int argc,char** argv) {
    if(argc!=2) return 1;
    std::ifstream in(argv[1]);std::string header;std::getline(in,header);
    double unused=0;for(int i=0;i<11;i++) in>>unused;
    Citadel c;in>>c.constant.x>>c.constant.y>>c.constant.z;
    double unit;size_t count;in>>unit>>count;c.reference.resize(count);
    for(auto& s:c.reference) in>>s.p.x>>s.p.y>>s.p.z>>s.next.x>>s.next.y>>s.next.z;
    if(!in || count<1 || count>384) return 2;
    c.metadata();c.logUnit=unit;
    std::mt19937 gen(455);std::uniform_real_distribution<double> random(-1,1);
    std::cout<<std::setprecision(14)<<"iteration,radius_log,max_relative_error,max_float_error,max_derivative_error,pole_length,power,px,py,pz\n";
    for(size_t i=1;i<count;i++) {
        const auto& s=c.reference[i];double maximum=0,maxFloat=0,maxDerivative=0;
        for(int j=0;j<512;j++) {
            Vec3 offset=Vec3{random(gen),random(gen),random(gen)}.unit()*std::exp2(s.renderLimit)*.8,expected=offset;
            double derivative=0;
            for(size_t k=0;k<i;k++) {
                const auto& r=c.reference[k];Vec3 q=r.q+Vec3{Citadel::foldedDelta(r.p.x,r.q.x,expected.x),Citadel::foldedDelta(r.p.y,r.q.y,expected.y),Citadel::foldedDelta(r.p.z,r.q.z,expected.z)};
                derivative+=std::log2(2.8/std::clamp(q.dot(q),.25,1.));
                expected=Citadel::perturb(r,expected);
            }
            Vec3 u=(s.x*offset.x+s.y*offset.y+s.z*offset.z)*std::exp2(s.logDerivative);
            double den=1+2*s.pole.dot(u)+s.pole.dot(s.pole)*u.dot(u);
            Vec3 actual=(u+s.pole*u.dot(u))/den;
            maximum=std::max(maximum,(actual-expected).length()/std::max(1e-200,expected.length()));
            maxDerivative=std::max(maxDerivative,std::abs(s.logDerivative-std::log2(den)-derivative));
            Vec3 uf{float(u.x),float(u.y),float(u.z)},pf{float(s.pole.x),float(s.pole.y),float(s.pole.z)};
            float squared=float(uf.dot(uf)),denf=1+2*float(pf.dot(uf))+float(pf.dot(pf))*squared;
            Vec3 actualf=(uf+pf*squared)/denf;
            maxFloat=std::max(maxFloat,(actualf-expected).length()/std::max(1e-200,expected.length()));
        }
        std::cout<<i<<','<<s.renderLimit-unit<<','<<maximum<<','<<maxFloat<<','<<maxDerivative<<','<<s.pole.length()<<','<<unit+s.logDerivative<<','<<s.p.x<<','<<s.p.y<<','<<s.p.z<<'\n';
    }
}
