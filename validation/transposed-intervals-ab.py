"""Separate interval tracing from ordered reduction to regroup independent rays."""
from pathlib import Path
import argparse,subprocess,shutil,csv,json,statistics
p=argparse.ArgumentParser();p.add_argument('rays',type=int,choices=[1,2,4,8,16,32]);p.add_argument('--fixtures',nargs='+',default=['edge','heavy']);a=p.parse_args()
root=Path(__file__).resolve().parent.parent;base=root/'validation/experiments/native-exact-ab'
out=root/f'validation/experiments/native-transposed-intervals-{a.rays}';out.mkdir(exist_ok=True)
for name in ('src','tests'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
shutil.copy2(base/'CMakeLists.txt',out/'CMakeLists.txt')
p=out/'src/fractal.hlsl';s=p.read_text(encoding='utf-8')
begin=s.index('#if EXACT_FOLD_OPT\n');end=s.index('#ifndef COOPERATIVE_RAYS',begin)
s=s[:begin]+'''#define SPHERE_DENOM(q) clamp(dot(q,q),.25,1)
#define SPHERE_BASE(s) clamp(0,s.y.w,s.z.w)
'''+s[end:];s=s.replace('EXACT_FOLD_OPT','TRANSPOSE_INTERVALS')
s=f'''#ifndef FLAT_INTERVALS
#define FLAT_INTERVALS 0
#endif
#define PACKET_RAYS {a.rays}
#define PACKET_CAPACITY 16384
'''+s
marker='RWTexture2DArray<float2> rayOutput:register(u0);'
s=s.replace(marker,'''// 48-byte job, 8-byte result, 16-byte bisection record: 72 bytes.
struct IntervalState {RayJob job;float2 result;float4 refinement;};
RWStructuredBuffer<IntervalState> intervalStates:register(u7);
'''+marker,1)
start=s.index('    segmentRefinement[segmentLane]=float4(previous,t,prefix.derivative,float(first));')
end=s.index('    return !hit && !escaped && accepted<MARCH_STEPS;',start)
old=s[start:end]
s=s[:start]+'''    #if FLAT_INTERVALS
    IntervalState interval;
    interval.job=job;interval.refinement=float4(previous,t,prefix.derivative,float(first));
    interval.result=float2(hit?scale:log2(t)+scale,hit?2:escaped?0:accepted>=MARCH_STEPS?-1:-2);
    intervalStates[segmentLane]=interval;
    #else
'''+old+'    #endif\n'+s[end:]
key='    uint segmentGroups=(dispatchOutput[3]+0)/1;'
assert s.count(key)==1
s=s.replace(key,'''    uint count=dispatchOutput[3];
    bool flat=TRANSPOSE_INTERVALS && count<=PACKET_CAPACITY;
    uint flatGroups=flat?((count+PACKET_RAYS-1)/PACKET_RAYS)*PACKET_RAYS:0;
    dispatchOutput[8]=min(flatGroups,65535);
    dispatchOutput[9]=max(1,(flatGroups+65534)/65535);dispatchOutput[10]=1;
    uint reduceGroups=flat?(count+63)/64:0;
    dispatchOutput[12]=min(reduceGroups,65535);
    dispatchOutput[13]=max(1,(reduceGroups+65534)/65535);dispatchOutput[14]=1;
    uint segmentGroups=flat?0:count;''',1)
s+='''
#if COOPERATIVE_RAYS && FLAT_INTERVALS
[numthreads(32,1,1)]
void flatIntervals(uint3 id:SV_DispatchThreadID) {
    uint linearIndex=id.x+id.y*(65535*32);
    uint index=(linearIndex/(PACKET_RAYS*32))*PACKET_RAYS+linearIndex%PACKET_RAYS;
    uint part=(linearIndex/PACKET_RAYS)%32;
    if(index>=dispatchInput[3]) return;
    segmentLane=index*32+part;
    RayJob original=activeRays[index],job=original;uint3 position=rayPixel(job.index);
    float3 rd=rayDirection(position);
    float begin=original.t*pow(1.05,float(part)),end=original.t*pow(1.05,float(part+1));
    float logBegin=log2(begin)+job.scale;
    float boundary=log2(end)+original.scale;
    job.horizon=min(original.horizon,boundary+max(4e-5,abs(boundary)*2e-7));
    if(part>0) {
        job.t=job.previous=begin;job.radius=0;job.relaxation=.9;job.verify=0;
        job.first=citadelStart(logBegin);
        RayPrefix prefix=rayPrefix(rd,job.first,job.scale);
        job.derivative=prefix.derivative;job.limit=prefix.limit;
    }
    if(logBegin<=original.horizon) marchJob(job,rd,position);
    else {
        IntervalState interval=(IntervalState)0;interval.job=job;interval.result=float2(logBegin,0);
        intervalStates[segmentLane]=interval;
    }
}
#endif
[numthreads(64,1,1)]
void reduceIntervals(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {
    uint index=id.x+id.y*(65535*64);RayJob job=(RayJob)0;bool pending=false;
    if(index<dispatchInput[3]) {
        RayJob original=activeRays[index];uint chosen=index*32;
        [loop] for(uint j=0;j<31;j++) {
            if(intervalStates[chosen].result.y!=0) break;
            chosen++;
        }
        IntervalState selected=intervalStates[chosen];job=selected.job;float2 result=selected.result;
        job.horizon=original.horizon;
        pending=result.y==-2 || (result.y==0 && result.x<=original.horizon);
        if(pending && job.accepted>=MARCH_STEPS) {pending=false;result.y=-1;}
        if(!pending) {
            uint3 position=rayPixel(job.index);rayOutput[position]=result;
            if(result.y==2) refinementJobs[job.index]=selected.refinement;
        }
    }
    enqueueGroup(lane,pending,job);
}
'''
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.h';s=p.read_text(encoding='utf-8')
s=s.replace('rayBegin,rayContinue,rayFinish,rayRefine,raySegment;', 'rayBegin,rayContinue,rayFinish,rayRefine,raySegment,rayFlat,rayReduce;')
s=s.replace('    ComPtr<ID3D11ComputeShader> rayPrepare;', '''    bool transposeScheduling=true;
    ComPtr<ID3D11Buffer> intervalBuffer;
    ComPtr<ID3D11UnorderedAccessView> intervalTarget;
    ComPtr<ID3D11ComputeShader> rayPrepare;''')
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8').replace('"EXACT_FOLD_OPT"','"TRANSPOSE_INTERVALS"')
key='''        macros[8].Definition="0";
        check(device->CreateComputeShader(finish->GetBufferPointer()'''
assert s.count(key)==1
s=s.replace(key,'''        D3D_SHADER_MACRO flatMacros[11]{};
        std::copy(macros,macros+9,flatMacros);flatMacros[9]={"FLAT_INTERVALS","1"};
        auto flat=compileShader("flatIntervals","cs_5_0",flatMacros);
        check(device->CreateComputeShader(flat->GetBufferPointer(),flat->GetBufferSize(),nullptr,&rayFlat[profile]),"Create transposed intervals");
        macros[8].Definition="0";
        auto reduce=compileShader("reduceIntervals","cs_5_0",macros);
        check(device->CreateComputeShader(reduce->GetBufferPointer(),reduce->GetBufferSize(),nullptr,&rayReduce[profile]),"Create ordered interval reduction");
        check(device->CreateComputeShader(finish->GetBufferPointer()''',1)
key='''        if(!rayPrepare) {
            for(int level=0;level<3;level++) {''';assert s.count(key)==1
s=s.replace(key,'''        if(!rayPrepare) {
            D3D11_BUFFER_DESC intervals{};intervals.ByteWidth=16384*32*72;intervals.StructureByteStride=72;
            intervals.Usage=D3D11_USAGE_DEFAULT;intervals.BindFlags=D3D11_BIND_UNORDERED_ACCESS;intervals.MiscFlags=D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;
            check(device->CreateBuffer(&intervals,nullptr,&intervalBuffer),"Create bounded interval workspace");
            check(device->CreateUnorderedAccessView(intervalBuffer.Get(),nullptr,&intervalTarget),"Create interval workspace target");
            for(int level=0;level<3;level++) {''',1)
s=s.replace('d.ByteWidth=32;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;d.MiscFlags=D3D11_RESOURCE_MISC_DRAWINDIRECT_ARGS;', 'd.ByteWidth=64;d.Usage=D3D11_USAGE_DEFAULT;d.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;d.MiscFlags=D3D11_RESOURCE_MISC_DRAWINDIRECT_ARGS;')
s=s.replace('u.Buffer.NumElements=8;','u.Buffer.NumElements=16;').replace('s.Buffer.NumElements=8;','s.Buffer.NumElements=16;')
key='''    auto cones=coneTarget.Get();context->CSSetUnorderedAccessViews(6,1,&cones,nullptr);''';assert s.count(key)==1
s=s.replace(key,'''    auto intervals=intervalTarget.Get();context->CSSetUnorderedAccessViews(7,1,&intervals,nullptr);
'''+key,1)
key='''        context->DispatchIndirect(dispatchBuffer.Get(),batch>=8 && batch<rayBatches-1?16:0);''';assert s.count(key)==1
s=s.replace(key,key+'''
        if(transposeScheduling && batch>=8 && batch<rayBatches-1) {
            context->CSSetShader(rayFlat[profile].Get(),nullptr,0);context->DispatchIndirect(dispatchBuffer.Get(),32);
            context->CSSetShader(rayReduce[profile].Get(),nullptr,0);context->DispatchIndirect(dispatchBuffer.Get(),48);
        }''',1)
key='''    if(measurePasses) context->End(passQueries[4].Get());
    if(measureBatches) context->End(batchQueries[rayBatches*2].Get());''';assert s.count(key)==1
s=s.replace(key,'''    context->CSSetUnorderedAccessViews(7,1,noTargets,nullptr);
'''+key,1)
s=s.replace('ComPtr<ID3D11ComputeShader> begin,next,finish,segment,refine;', 'ComPtr<ID3D11ComputeShader> begin,next,finish,segment,refine,prepare;')
s=s.replace('rayRefine[1],rayResolve[1],coneShaders},original;', 'rayRefine[1],rayPrepare,rayResolve[1],coneShaders},original;')
s=s.replace('macros[8].Definition="0";\n    auto resolve=', 'macros[8].Definition="0";compute("prepareRays",original.prepare);\n    auto resolve=',1)
s=s.replace('rayRefine[1]=b.refine;rayResolve', 'rayRefine[1]=b.refine;rayPrepare=b.prepare;transposeScheduling=candidate;rayResolve',1)
p.write_text(s,encoding='utf-8')
subprocess.run(['cmake','-S',str(out),'-B',str(out/'build-vs'),'-G','Visual Studio 17 2022','-A','x64'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['cmake','--build',str(out/'build-vs'),'--config','Release','--parallel'],check=True,stdout=subprocess.DEVNULL)
for fixture in a.fixtures:
    run=out/fixture;run.mkdir(exist_ok=True);shutil.copy2(base/fixture/'last-flight.aurora',run/'last-flight.aurora')
    proc=subprocess.run([str(out/'build-vs/Release/AuroraFractal.exe'),'--fold-ab'],cwd=run,creationflags=subprocess.CREATE_NO_WINDOW)
    folder=run/'validation/fold-ab';report=json.loads((folder/'comparison.json').read_text())
    rows=list(csv.DictReader((folder/'comparison-timings.csv').open()))
    ms=[statistics.mean(float(x['gpu_ms']) for x in rows if int(x['candidate'])==i) for i in range(2)]
    print('transposed',a.rays,fixture,'exit',proc.returncode,'ms',ms,report,flush=True)

