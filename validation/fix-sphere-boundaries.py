"""Preserve sphere-fold branch distances before converting the orbit to float."""
from pathlib import Path
root=Path(__file__).resolve().parent/'experiments/native-edge-fixed'
cpu=root/'src/citadel.h';shader=root/'src/fractal.hlsl';test=root/'tests/citadel_tests.cpp'
s=cpu.read_text(encoding='utf-8')
old='for(size_t i=0;i<reference.size();i++) {const auto& s=reference[i];result[i]={f(s.p,logUnit+s.logDerivative),f(s.q,s.denom),f(s.next,s.q.dot(s.q)),f(s.x,s.limit-logUnit),f(s.y,0),f(s.z,0),f(s.pole,s.renderLimit-logUnit)};}'
new='''// y.w/z.w retain signed distances to the sphere-fold boundaries. A
        // rounded radius can equal 0.25 or 1 even when the reference is still
        // many camera units from that branch at a deep zoom. Subtract first
        // in double precision, then pack the small differences themselves.
        for(size_t i=0;i<reference.size();i++) {
            const auto& s=reference[i];double r2=s.q.dot(s.q);
            result[i]={f(s.p,logUnit+s.logDerivative),f(s.q,s.denom),f(s.next,r2),
                f(s.x,s.limit-logUnit),f(s.y,.25-r2),f(s.z,1-r2),f(s.pole,s.renderLimit-logUnit)};
        }'''
assert old in s;s=s.replace(old,new);cpu.write_text(s,encoding='utf-8')
s=shader.read_text(encoding='utf-8')
s=s.replace(',r2=s.next.w;', ';').replace('.25-r2','s.y.w').replace('1-r2','s.z.w')
s=s.replace('struct OrbitSample {', '// y.w/z.w are precomputed signed sphere-boundary distances, not rounded radii.\nstruct OrbitSample {',1)
shader.write_text(s,encoding='utf-8')
s=test.read_text(encoding='utf-8')
testcode=r'''
static void verifyPackedSphereBoundaries() {
    int checked=0;
    for(double boundary:{.25,1.}) for(int side:{-1,1}) for(int exponent=20;exponent<=48;exponent+=2) {
        double gap=side*std::ldexp(1.,-exponent),component=std::sqrt((boundary+gap)*.5);
        Citadel c;Citadel::Sample sample;sample.p=sample.q={component,component,0};
        sample.denom=std::clamp(sample.q.dot(sample.q),.25,1.);
        sample.next=sample.q*(2.8/sample.denom)+c.constant;c.reference.push_back(sample);
        auto packed=c.gpu()[0];
        for(double factor:{-4.,-.25,.25,4.}) {
            Vec3 delta=sample.q.unit()*(std::abs(gap)*factor);
            Vec3 expected=Citadel::perturb(sample,delta);
            float dx=float(delta.x),dy=float(delta.y),dz=float(delta.z);
            float change=2*(packed.q.x*dx+packed.q.y*dy+packed.q.z*dz)+(dx*dx+dy*dy+dz*dz);
            float dc=std::clamp(change,packed.y.w,packed.z.w)-std::clamp(0.f,packed.y.w,packed.z.w);
            float k=2.8f/(packed.q.w+dc);
            Vec3 actual{(dx-packed.q.x*(dc/packed.q.w))*k,(dy-packed.q.y*(dc/packed.q.w))*k,(dz-packed.q.z*(dc/packed.q.w))*k};
            require((actual-expected).length()/expected.length()<2e-5,"Packed sphere fold changed branch near a sub-float boundary");
            checked++;
        }
    }
    require(checked==240,"Missing packed sphere boundary cases");
}
'''
assert 'static void verifyPackedSphereBoundaries' not in s
s=s.replace('int main() {try {',testcode+'\nint main() {try {\n    verifyPackedSphereBoundaries();',1)
test.write_text(s,encoding='utf-8')
print(root)
