from pathlib import Path
root=Path(__file__).resolve().parent.parent
s=(root/'backup-2026-10-11-cooperative/src/fractal.hlsl').read_text()
s=s.replace('float citadelDistanceScaled(', 'static uint lastQueryCost=0;\nfloat citadelDistanceScaled(',1)
s=s.replace('    float3 delta=basis*derivative;', '    lastQueryCost=0;\n    float3 delta=basis*derivative;',1)
s=s.replace('if(dot(p,p)>4096 || derivative>1e24) return .45*length(p)/max(derivative,1e-30);', 'if(dot(p,p)>4096 || derivative>1e24) {lastQueryCost=iteration+1-lo;return .45*length(p)/max(derivative,1e-30);}',1)
marker='    #else\n    [loop] for(int i=lo;i<end;i++)'
s=s.replace(marker,'    lastQueryCost=min(iteration+1,end)-lo;\n'+marker,1)
s=s.replace('job.verify=verify;job.derivative=prefix.derivative;', 'job.verify=uint(verify)|(min(lastQueryCost,127u)<<1);job.derivative=prefix.derivative;')
s=s.replace('groupBuckets[128],groupOffsets[128]', 'groupBuckets[1024],groupOffsets[1024]')
s=s.replace('return min(127,uint(job.first));','return min(127,uint(job.first))*8+min(7u,(job.verify>>2u)&63u);')
s=s.replace('    groupBuckets[lane]=0;groupBuckets[lane+64]=0;', '    [unroll] for(uint b=0;b<16;b++) groupBuckets[lane+b*64]=0;')
s=s.replace('for(uint i=0;i<2;i++)','for(uint i=0;i<16;i++)')
s=s.replace('(pendingJob.verify&1)|((rank+groupOffsets[bucket])<<1)', '(pendingJob.verify&255)|((rank+groupOffsets[bucket])<<8)')
s=s.replace('job.verify>>1;', 'job.verify>>8;')
s=s.replace('bin<128;', 'bin<1024;')
out=root/'validation/experiments/joint-sort-fixed';out.mkdir(parents=True,exist_ok=True)
(out/'fractal.hlsl').write_text(s)
