#include <windows.h>
#include <d3dcompiler.h>
#include <d3d11shader.h>
#include <wrl/client.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
using Microsoft::WRL::ComPtr;
int main(int argc,char** argv) {
 if(argc!=2) return 2;
 std::ifstream input(argv[1],std::ios::binary);std::string source((std::istreambuf_iterator<char>(input)),{});
 for(int mode=0;mode<3;mode++) for(auto chunk:{"64","256","8192"}) {
  const char* entry=std::string(chunk)=="64"?"beginRays":"continueRays";
  D3D_SHADER_MACRO macros[]={{"RAY_CHUNK",chunk},{"WORLD_KIND","1"},{"PIXEL_SAMPLES","1"},{"SHADOW_STEPS","4"},{"AO_STEPS","3"},{"UNIFORM_FOLDS",mode?"1":"0"},{"DEFER_SURFACE_REFINE",mode==2?"1":"0"},{nullptr,nullptr}};
  ComPtr<ID3DBlob> blob,error;
  auto hr=D3DCompile(source.data(),source.size(),argv[1],macros,nullptr,entry,"cs_5_0",D3DCOMPILE_OPTIMIZATION_LEVEL3|D3DCOMPILE_ENABLE_STRICTNESS,0,&blob,&error);
  if(FAILED(hr)) {if(error) std::cerr<<static_cast<const char*>(error->GetBufferPointer());return 3;}
  ComPtr<ID3D11ShaderReflection> reflection;D3DReflect(blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&reflection));D3D11_SHADER_DESC desc{};reflection->GetDesc(&desc);
  std::cout<<mode<<","<<chunk<<",temps="<<desc.TempRegisterCount<<",instructions="<<desc.InstructionCount<<",dynamicFlow="<<desc.DynamicFlowControlCount<<",bytes="<<blob->GetBufferSize()<<"\n";
  if(mode==2 && std::string(chunk)=="256") {ComPtr<ID3DBlob> dis;D3DDisassemble(blob->GetBufferPointer(),blob->GetBufferSize(),0,nullptr,&dis);std::ofstream out("shader-assembly.txt");out.write(static_cast<const char*>(dis->GetBufferPointer()),dis->GetBufferSize());}
 }
}
