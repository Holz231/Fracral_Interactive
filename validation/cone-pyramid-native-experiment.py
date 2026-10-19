"""Build the screened 16->8->4 cone hierarchy in an isolated D3D11 app copy."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parent.parent
out=root/'validation/experiments/cone-pyramid-native'
out.mkdir(parents=True,exist_ok=True)
shutil.copytree(root/'src',out/'src',dirs_exist_ok=True)
shutil.copytree(root/'tests',out/'tests',dirs_exist_ok=True)
shutil.copy2(root/'CMakeLists.txt',out/'CMakeLists.txt')
shutil.copy2(root/'validation/experiments/cone-pyramid-4-256/fractal.hlsl',out/'src/fractal.hlsl')
p=out/'src/renderer.h'
s=p.read_text(encoding='utf-8').replace('    ComPtr<ID3D11ComputeShader> raySort;', '''    ComPtr<ID3D11ComputeShader> raySort;
    std::array<ComPtr<ID3D11ComputeShader>,3> coneShaders;
    ComPtr<ID3D11Texture2D> coneTexture;
    ComPtr<ID3D11UnorderedAccessView> coneTarget;''')
p.write_text(s,encoding='utf-8')
p=out/'src/renderer.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('{"DEFER_SURFACE_REFINE","1"},{nullptr,nullptr}', '{"DEFER_SURFACE_REFINE","1"},{"CONE_START","1"},{nullptr,nullptr}')
s=s.replace('''        if(!rayPrepare) {''','''        if(!rayPrepare) {
            for(int level=0;level<3;level++) {
                std::string tile=std::to_string(16>>level),index=std::to_string(level);
                D3D_SHADER_MACRO coneMacros[]={{"UNIFORM_FOLDS","1"},{"WORLD_KIND","1"},{"CONE_TILE",tile.c_str()},{"CONE_LEVEL",index.c_str()},{nullptr,nullptr}};
                auto cone=compileShader("buildCones","cs_5_0",coneMacros);
                check(device->CreateComputeShader(cone->GetBufferPointer(),cone->GetBufferSize(),nullptr,&coneShaders[level]),"Create cone hierarchy shader");
            }''',1)
s=s.replace('''        UINT capacity=UINT(renderWidth*renderHeight*samples);''','''        coneTarget.Reset();coneTexture.Reset();
        D3D11_TEXTURE2D_DESC cd{};cd.Width=(renderWidth+3)/4;cd.Height=(renderHeight+3)/4;cd.ArraySize=3;cd.MipLevels=cd.SampleDesc.Count=1;
        cd.Format=DXGI_FORMAT_R32_FLOAT;cd.Usage=D3D11_USAGE_DEFAULT;cd.BindFlags=D3D11_BIND_UNORDERED_ACCESS;
        check(device->CreateTexture2D(&cd,nullptr,&coneTexture),"Create cone hierarchy texture");
        check(device->CreateUnorderedAccessView(coneTexture.Get(),nullptr,&coneTarget),"Create cone hierarchy target");
        UINT capacity=UINT(renderWidth*renderHeight*samples);''',1)
s=s.replace('''    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''','''    auto cones=coneTarget.Get();context->CSSetUnorderedAccessViews(6,1,&cones,nullptr);
    for(int level=0;level<3;level++) {
        int tile=16>>level;context->CSSetShader(coneShaders[level].Get(),nullptr,0);
        context->Dispatch((renderWidth+tile*8-1)/(tile*8),(renderHeight+tile*8-1)/(tile*8),1);
    }
    context->ClearUnorderedAccessViewUint(rayCountUav.Get(),zeros);
    context->ClearUnorderedAccessViewUint(bucketUav.Get(),zeros);''',1)
s=s.replace('''    if(measurePasses) context->End(passQueries[1].Get());
    if(measureBatches) recordRayBatch(0);''','''    context->CSSetUnorderedAccessViews(6,1,noTargets,nullptr);
    if(measurePasses) context->End(passQueries[1].Get());
    if(measureBatches) recordRayBatch(0);''',1)
p.write_text(s,encoding='utf-8')
p=out/'src/main.cpp';s=p.read_text(encoding='utf-8')
s=s.replace('''    app.renderer.profileView(app.world,app.view,(dir/L"saved-native").wstring());
    if(batches) app.renderer.profileRayBatches(app.world,app.view,(dir/L"batches.csv").wstring());''','''    if(batches) app.renderer.profileRayBatches(app.world,app.view,(dir/L"batches.csv").wstring());
    app.renderer.profileView(app.world,app.view,(dir/L"saved-native").wstring());''')
p.write_text(s,encoding='utf-8')
fixture=out/'fixture';fixture.mkdir(exist_ok=True)
shutil.copy2(root/'validation/slow-69ms-fixture/last-flight.aurora',fixture/'last-flight.aurora')
print(out)
