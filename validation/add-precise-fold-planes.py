"""Preserve sub-float distances to box-fold planes in the GPU reference orbit."""
from pathlib import Path
root=Path(__file__).resolve().parent
base=root/'experiments/native-tuned/src'
p=base/'citadel.h';s=p.read_text(encoding='utf-8')
s=s.replace('struct GpuSample {Float4 p,q,next,x,y,z,curve;};','struct GpuSample {Float4 p,q,next,x,y,z,curve,edge;};')
old='f(s.pole,s.renderLimit-logUnit)};'
assert old in s
s=s.replace(old,'f(s.pole,s.renderLimit-logUnit),f({1-std::abs(s.p.x),1-std::abs(s.p.y),1-std::abs(s.p.z)},0)};')
p.write_text(s,encoding='utf-8')
p=base/'fractal.hlsl';s=p.read_text(encoding='utf-8')
s=s.replace('struct OrbitSample {float4 p,q,next,x,y,z,curve;};','struct OrbitSample {float4 p,q,next,x,y,z,curve,edge;};')
begin=s.index('float foldedDelta(');end=s.index('// Distance and offset',begin)
s=s[:begin]+'''// edge is computed from the double reference before conversion to float.
// Comparing delta with plane offsets avoids rounding before+delta back onto
// a fold plane and accidentally selecting the opposite reflection branch.
float foldedDelta(float before,float folded,float delta,float edge) {
    float upper=before>=0?edge:2-edge,lower=before>=0?edge-2:-edge;
    if(edge>=0) return delta>upper?2*upper-delta:delta<lower?2*lower-delta:delta;
    if(before>=0) return delta>upper?-delta:delta<lower?-4-delta:delta-2*upper;
    return delta<lower?-delta:delta>upper?4-delta:delta-2*lower;
}
float3 foldedDeltaVector(float3 before,float3 folded,float3 delta,float3 edge) {
    float3 upper=before>=0?edge:2-edge,lower=before>=0?edge-2:-edge;
    float3 inner=delta>upper?2*upper-delta:delta<lower?2*lower-delta:delta;
    float3 positive=delta>upper?-delta:delta<lower?-4-delta:delta-2*upper;
    float3 negative=delta<lower?-delta:delta>upper?4-delta:delta-2*lower;
    return edge>=0?inner:before>=0?positive:negative;
}
''' + s[end:]
s=s.replace('foldedDeltaVector(s.p.xyz,s.q.xyz,delta)','foldedDeltaVector(s.p.xyz,s.q.xyz,delta,s.edge.xyz)')
for axis in 'xyz':
    s=s.replace(f'foldedDelta(s.p.{axis},s.q.{axis},delta.{axis})',f'foldedDelta(s.p.{axis},s.q.{axis},delta.{axis},s.edge.{axis})')
p.write_text(s,encoding='utf-8')
print(base)
