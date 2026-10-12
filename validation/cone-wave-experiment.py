from pathlib import Path

root = Path(__file__).resolve().parent.parent
base = root/'backup-2026-10-11-cooperative/src'
s=(base/'fractal.hlsl').read_text(encoding='utf-8')
s='#ifndef CONE_START\n#define CONE_START 0\n#endif\n'+s
marker='bool initializeJob(inout RayJob job,float3 rd) {'
s=s.replace(marker,'''RWTexture2D<float> coneOutput:register(u6);
Texture2D<float> coneInput:register(t5);
[numthreads(8,8,1)]
void traceCones(uint3 id:SV_DispatchThreadID) {
    uint2 size=(uint2(renderInfo.xy)+7)/8;
    if(any(id.xy>=size)) return;
    float2 center=(float2(id.xy)*8+4);
    float2 uv=(center*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float cone=(1.414214*8+1.5)/(renderInfo.y*1.85);
    float scale=-7,t=1;
    int first=citadelStart(-7);RayPrefix prefix=rayPrefix(rd,first,scale);
    [loop] for(int i=0;i<256;i++) {
        if(t>4096) {scale+=12;t/=4096;prefix.derivative*=4096;prefix.limit/=4096;}
        if(first>0 && t>=prefix.limit) {
            [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-scale,100)));
            prefix=rayPrefix(rd,first,scale);
        }
        float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        if(d<cone*1.5 || log2(t)+scale>min(256,8-reference[0].p.w)) break;
        t*=1+.9*(d-cone)/(1+cone);
    }
    coneOutput[id.xy]=log2(t)+scale;
}
'''+marker)
s=s.replace('''    job.scale=floor(start);job.t''','''    #if CONE_START
    uint3 position=rayPixel(job.index);
    start=max(start,coneInput.Load(int3(position.xy/8,0)));
    start=min(start,job.horizon);
    #endif
    job.scale=floor(start);job.t''')
(root/'src/fractal.hlsl').write_text(s,encoding='utf-8')
s=(base/'renderer.h').read_text(encoding='utf-8')
s=s.replace('ComPtr<ID3D11ComputeShader> raySort;', '''ComPtr<ID3D11ComputeShader> raySort,coneTrace;
    ComPtr<ID3D11Texture2D> coneTexture;
    ComPtr<ID3D11ShaderResourceView> coneView;
    ComPtr<ID3D11UnorderedAccessView> coneTarget;''')
(root/'src/renderer.h').write_text(s,encoding='utf-8')
s=(base/'renderer.cpp').read_text(encoding='utf-8')
s=s.replace('{"DEFER_SURFACE_REFINE","1"},{nullptr,nullptr}', '{"DEFER_SURFACE_REFINE","1"},{"CONE_START","1"},{nullptr,nullptr}')
s=s.replace('''        if(!rayPrepare) {
''','''        if(!rayPrepare) {
            auto cone=compileShader("traceCones","cs_5_0",macros);
            check(device->CreateComputeShader(cone->GetBufferPointer(),cone->GetBufferSize(),nullptr,&coneTrace),"Create cone tracer");
''',1)
s=s.replace('''        UINT capacity=UINT(renderWidth*renderHeight*samples);''','''        D3D11_TEXTURE2D_DESC cd{};cd.Width=(renderWidth+7)/8;cd.Height=(renderHeight+7)/8;cd.MipLevels=cd.ArraySize=cd.SampleDesc.Count=1;
        cd.Format=DXGI_FORMAT_R32_FLOAT;cd.Usage=D3D11_USAGE_DEFAULT;cd.BindFlags=D3D11_BIND_UNORDERED_ACCESS|D3D11_BIND_SHADER_RESOURCE;
        coneTexture.Reset();coneView.Reset();coneTarget.Reset();
        check(device->CreateTexture2D(&cd,nullptr,&coneTexture),"Create cone bounds");
        check(device->CreateShaderResourceView(coneTexture.Get(),nullptr,&coneView),"Create cone view");
        check(device->CreateUnorderedAccessView(coneTexture.Get(),nullptr,&coneTarget),"Create cone target");
        UINT capacity=UINT(renderWidth*renderHeight*samples);''')
s=s.replace('''    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''','''    auto coneOut=coneTarget.Get();context->CSSetUnorderedAccessViews(6,1,&coneOut,nullptr);
    context->CSSetShader(coneTrace.Get(),nullptr,0);context->Dispatch((renderWidth+63)/64,(renderHeight+63)/64,1);
    context->CSSetUnorderedAccessViews(6,1,noTargets,nullptr);
    auto coneIn=coneView.Get();context->CSSetShaderResources(5,1,&coneIn);
    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''',1)
s=s.replace('''    if(measurePasses) context->End(passQueries[1].Get());
    if(measureBatches) recordRayBatch(0);''','''    context->CSSetShaderResources(5,1,noViews);
    if(measurePasses) context->End(passQueries[1].Get());
    if(measureBatches) recordRayBatch(0);''',1)
(root/'src/renderer.cpp').write_text(s,encoding='utf-8')
