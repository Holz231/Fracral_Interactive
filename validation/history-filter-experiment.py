from pathlib import Path
root=Path(__file__).resolve().parent.parent
directory=root/'validation/experiments/far-history/src'
p=directory/'renderer.cpp';s=p.read_text(encoding='utf-8').replace('common-=6;historyCommon=common;', 'common-=1;historyCommon=common;');p.write_text(s,encoding='utf-8')
p=directory/'fractal.hlsl';s=p.read_text(encoding='utf-8')
start=s.index('bool marchJob(');end=s.index('groupshared uint pendingCount',start)
body=s[start:end]
a=body.index('        if(historyInfo.w>0 && first<=');b=body.index('        if(radius>0 && t>previous)',a)
body=body[:a]+'''        if(cacheValid && first<=int(historyInfo.x)) {
            if(log2(t)+scale+1<cacheTravel) {
                float distance=citadelDistanceFrom(rd,cacheTravel,cacheFirst);
                if(distance<pixel*.65) {
                    rayOutput[position]=float2(cacheTravel,1);
                    cached.w+=1;historyOutput[position]=cached;return false;
                }
            }
            cacheValid=false;
        }
'''+body[b:]
insert=body.index('    [loop] for(;accepted<end;accepted++)')
body=body[:insert]+'''    float4 cached=0;float cacheTravel=0;int cacheFirst=0;bool cacheValid=false;
    if(historyInfo.w>0 && historyInfo.x>=0) {
        cached=historyInput.Load(int4(position,0));
        cacheTravel=cached.x+((cached.y-historyInfo.y)+(cached.z-historyInfo.z));
        if(cached.w>0 && cacheTravel<job.horizon && cacheTravel>log2(t)+scale+1) {
            cacheFirst=citadelStart(cacheTravel);
            cacheValid=cacheFirst<=int(historyInfo.x);
            // Reject a silhouette or rapidly changing depth neighbourhood.
            if(cacheValid) {
                [unroll] for(int cy=-1;cy<=1;cy++) {
                    [unroll] for(int cx=-1;cx<=1;cx++) {
                        int2 neighbour=int2(position.xy)+int2(cx,cy);
                        if(any(neighbour<0) || any(neighbour>=int2(renderInfo.xy))) cacheValid=false;
                        else {
                            float4 other=historyInput.Load(int4(neighbour,0,0));
                            float difference=(other.x-cached.x)+(other.y-cached.y)+(other.z-cached.z);
                            if(other.w<=0 || abs(difference)>.004) cacheValid=false;
                        }
                    }
                }
            }
        }
    }
'''+body[insert:]
s=s[:start]+body+s[end:];p.write_text(s,encoding='utf-8')
