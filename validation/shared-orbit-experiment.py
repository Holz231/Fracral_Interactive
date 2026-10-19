from pathlib import Path

root = Path(__file__).resolve().parent.parent
base = (root / 'src/fractal.hlsl').read_text(encoding='utf-8')
for capacity in (64, 128):
    source = base.replace('float citadelDistanceScaled(', f'''
groupshared float4 localP[{capacity}], localQ[{capacity}], localNext[{capacity}];
void cacheOrbit(uint lane) {{
    for(uint i=lane;i<min(uint(counts.x),{capacity}u);i+=64) {{
        localP[i]=reference[i].p;localQ[i]=reference[i].q;localNext[i]=reference[i].next;
    }}
    GroupMemoryBarrierWithGroupSync();
}}
OrbitSample fieldSample(int i) {{
    OrbitSample s=(OrbitSample)0;
    if(i<{capacity}) {{s.p=localP[i];s.q=localQ[i];s.next=localNext[i];}}
    else s=reference[i];
    return s;
}}
float citadelDistanceScaled(''', 1)
    source = source.replace('OrbitSample s=reference[iteration];', 'OrbitSample s=fieldSample(iteration);')
    source = source.replace('void beginRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {', 'void beginRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {\n    cacheOrbit(lane);')
    source = source.replace('void continueRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {', 'void continueRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {\n    cacheOrbit(lane);')
    source = source.replace('void refineRays(uint3 position:SV_DispatchThreadID) {', 'void refineRays(uint3 position:SV_DispatchThreadID,uint lane:SV_GroupIndex) {\n    cacheOrbit(lane);')
    directory = root / f'validation/experiments/shared-orbit-{capacity}'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'fractal.hlsl').write_text(source, encoding='utf-8')
