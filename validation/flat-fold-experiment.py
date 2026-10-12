from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = (root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
start=source.index('bool marchJob(')
end=source.index('groupshared uint pendingCount',start)
function=source[start:end]
function=function.replace('    [loop] for(;accepted<end;accepted++) {', '''    float3 delta=0,p=0;
    float fieldDerivative=0;
    int iteration=0,fieldEnd=min(384,counts.x+12);
    bool queryStart=true,direct=false,ready=false;
    [loop] while(accepted<end) {
        if(queryStart) {''')
function=function.replace('        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);', '''        fieldDerivative=prefix.derivative*t;
        delta=prefix.basis*fieldDerivative;
        float squared=dot(delta,delta);
        float denominator=1+2*dot(prefix.pole,delta)+dot(prefix.pole,prefix.pole)*squared;
        delta=(delta+prefix.pole*squared)/denominator;fieldDerivative/=denominator;
        p=prefix.origin+delta;iteration=first;direct=false;
        ready=(first>0 && dot(p,p)>4096) || iteration>=fieldEnd;
        queryStart=false;
        }
        if(!ready) {
            if(iteration>=counts.x || fieldDerivative>renderInfo.y*1.85*.001 || dot(delta,delta)>64) direct=true;
            if(!direct) {
                OrbitSample s=reference[iteration];
                delta=foldedDeltaVector(s.p.xyz,s.q.xyz,delta);
                float change=2*dot(s.q.xyz,delta)+dot(delta,delta),r2=s.next.w;
                float dc=clamp(change,.25-r2,1-r2)-clamp(0,.25-r2,1-r2);
                float k=2.8/(s.q.w+dc);
                delta=k*(delta-s.q.xyz*(dc/s.q.w));p=s.next.xyz+delta;fieldDerivative*=k;
            } else {
                float3 q=2*clamp(p,-1,1)-p;
                float k=2.8/clamp(dot(q,q),.25,1);
                p=q*k+fractalParameters.xyz;fieldDerivative*=k;
            }
            iteration++;
            ready=dot(p,p)>4096 || fieldDerivative>1e24 || iteration>=fieldEnd;
        }
        if(!ready) continue;
        float ratio=.45*length(p)/max(fieldDerivative,1e-30);
        queryStart=true;''')
function=function.replace('verify=false;accepted--;continue;', 'verify=false;continue;')
function=function.replace('        if(!verify && t>exitT) {escaped=true;break;}','        if(!verify && t>exitT) {escaped=true;break;}\n        accepted++;')
source=source[:start]+function+source[end:]
out=root/'validation/experiments/flat-fold'
out.mkdir(exist_ok=True,parents=True)
(out/'fractal.hlsl').write_text(source)
