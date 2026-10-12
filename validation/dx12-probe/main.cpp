#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <vector>
#include <array>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <string>
using Microsoft::WRL::ComPtr;
namespace fs=std::filesystem;
void check(HRESULT h,const char* message) {if(FAILED(h)) throw std::runtime_error(std::string(message)+" ("+std::to_string(unsigned(h))+")");}
std::vector<char> read(const fs::path& p) {
    std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f) throw std::runtime_error("Cannot read "+p.string());
    std::vector<char> bytes(size_t(f.tellg()));f.seekg(0);f.read(bytes.data(),std::streamsize(bytes.size()));return bytes;
}
struct Resource {ComPtr<ID3D12Resource> object;D3D12_RESOURCE_STATES state=D3D12_RESOURCE_STATE_COMMON;};
struct Probe {
    ComPtr<ID3D12Device> device;
    ComPtr<ID3D12CommandQueue> queue;
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> list;
    ComPtr<ID3D12DescriptorHeap> descriptors,cpuDescriptors;
    ComPtr<ID3D12RootSignature> root;
    ComPtr<ID3D12CommandSignature> indirect;
    ComPtr<ID3D12QueryHeap> queries;
    ComPtr<ID3D12Fence> fence;
    HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);
    UINT64 serial=0,frequency=0;
    UINT width=0,height=0,stride=0;
    Resource constants,rays[2],output,refinement,args,count,buckets,timestamps,depthReadback;
    Resource queueReadback;
    bool inspectQueue=false;
    int cacheStart=4;
    std::array<ComPtr<ID3D12PipelineState>,8> pipelines;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT64 copyBytes=0;
    ~Probe() {CloseHandle(event);}
    D3D12_CPU_DESCRIPTOR_HANDLE cpu(UINT index,bool mirror=false) const {
        auto h=(mirror?cpuDescriptors:descriptors)->GetCPUDescriptorHandleForHeapStart();h.ptr+=SIZE_T(index)*stride;return h;
    }
    D3D12_GPU_DESCRIPTOR_HANDLE gpu(UINT index) const {
        auto h=descriptors->GetGPUDescriptorHandleForHeapStart();h.ptr+=UINT64(index)*stride;return h;
    }
    Resource buffer(UINT64 bytes,D3D12_HEAP_TYPE heap=D3D12_HEAP_TYPE_DEFAULT,bool uav=true) {
        Resource r;D3D12_HEAP_PROPERTIES p{};p.Type=heap;
        D3D12_RESOURCE_DESC d{};d.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;d.Width=bytes;d.Height=d.DepthOrArraySize=d.MipLevels=1;
        d.SampleDesc.Count=1;d.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;d.Flags=uav?D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS:D3D12_RESOURCE_FLAG_NONE;
        r.state=heap==D3D12_HEAP_TYPE_UPLOAD?D3D12_RESOURCE_STATE_GENERIC_READ:heap==D3D12_HEAP_TYPE_READBACK?D3D12_RESOURCE_STATE_COPY_DEST:D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        check(device->CreateCommittedResource(&p,D3D12_HEAP_FLAG_NONE,&d,r.state,nullptr,IID_PPV_ARGS(&r.object)),"Create buffer");return r;
    }
    void transition(Resource& r,D3D12_RESOURCE_STATES state) {
        if(r.state==state) return;
        D3D12_RESOURCE_BARRIER b{};b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;b.Transition.pResource=r.object.Get();
        b.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;b.Transition.StateBefore=r.state;b.Transition.StateAfter=state;
        list->ResourceBarrier(1,&b);r.state=state;
    }
    void barrier() {D3D12_RESOURCE_BARRIER b{};b.Type=D3D12_RESOURCE_BARRIER_TYPE_UAV;list->ResourceBarrier(1,&b);}
    void uav(UINT index,Resource& r,UINT elements,UINT elementSize=0) {
        D3D12_UNORDERED_ACCESS_VIEW_DESC d{};d.ViewDimension=D3D12_UAV_DIMENSION_BUFFER;
        d.Format=elementSize?DXGI_FORMAT_UNKNOWN:DXGI_FORMAT_R32_UINT;d.Buffer.NumElements=elements;d.Buffer.StructureByteStride=elementSize;
        device->CreateUnorderedAccessView(r.object.Get(),nullptr,&d,cpu(index));
        device->CreateUnorderedAccessView(r.object.Get(),nullptr,&d,cpu(index,true));
    }
    void srv(UINT index,Resource& r,UINT elements,UINT elementSize=0) {
        D3D12_SHADER_RESOURCE_VIEW_DESC d{};d.ViewDimension=D3D12_SRV_DIMENSION_BUFFER;d.Shader4ComponentMapping=D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
        d.Format=elementSize?DXGI_FORMAT_UNKNOWN:DXGI_FORMAT_R32_UINT;d.Buffer.NumElements=elements;d.Buffer.StructureByteStride=elementSize;
        device->CreateShaderResourceView(r.object.Get(),&d,cpu(index));
    }
    void bind(int pipeline,UINT readQueue,UINT writeQueue) {
        list->SetPipelineState(pipelines[pipeline].Get());
        list->SetComputeRootDescriptorTable(1,gpu(readQueue*16));
        list->SetComputeRootDescriptorTable(2,gpu(32+writeQueue*16));
    }
    void clear(UINT descriptor,Resource& r) {
        transition(r,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);UINT zero[4]{};
        list->ClearUnorderedAccessViewUint(gpu(descriptor),cpu(descriptor,true),r.object.Get(),zero,0,nullptr);
    }
    void initialize(const fs::path& shaderDirectory,const std::vector<char>& data) {
        if(data.size()<16 || data.size()>65536) throw std::runtime_error("Invalid constants size");
        float dimensions[2]{};memcpy(dimensions,data.data(),sizeof(dimensions));width=UINT(dimensions[0]);height=UINT(dimensions[1]);
        if(width<64 || height<64 || width>8192 || height>8192) throw std::runtime_error("Invalid dimensions");
        if(GetEnvironmentVariableW(L"AURORA_DX12_DEBUG",nullptr,0)) {
            ComPtr<ID3D12Debug> debug;if(SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug)))) debug->EnableDebugLayer();
        }
        ComPtr<IDXGIFactory6> factory;check(CreateDXGIFactory1(IID_PPV_ARGS(&factory)),"Create DXGI factory");
        ComPtr<IDXGIAdapter1> adapter;check(factory->EnumAdapterByGpuPreference(0,DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,IID_PPV_ARGS(&adapter)),"Select GPU");
        check(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device)),"Create D3D12 device");
        D3D12_COMMAND_QUEUE_DESC q{};q.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;check(device->CreateCommandQueue(&q,IID_PPV_ARGS(&queue)),"Create queue");
        check(queue->GetTimestampFrequency(&frequency),"Read GPU timer frequency");
        check(device->CreateCommandAllocator(q.Type,IID_PPV_ARGS(&allocator)),"Create allocator");
        check(device->CreateCommandList(0,q.Type,allocator.Get(),nullptr,IID_PPV_ARGS(&list)),"Create list");check(list->Close(),"Close initial list");
        check(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)),"Create fence");
        D3D12_DESCRIPTOR_HEAP_DESC hd{};hd.Type=D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;hd.NumDescriptors=64;hd.Flags=D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
        check(device->CreateDescriptorHeap(&hd,IID_PPV_ARGS(&descriptors)),"Create descriptors");hd.Flags=D3D12_DESCRIPTOR_HEAP_FLAG_NONE;
        check(device->CreateDescriptorHeap(&hd,IID_PPV_ARGS(&cpuDescriptors)),"Create CPU descriptors");stride=device->GetDescriptorHandleIncrementSize(hd.Type);
        D3D12_DESCRIPTOR_RANGE ranges[2]{};
        ranges[0].RangeType=D3D12_DESCRIPTOR_RANGE_TYPE_SRV;ranges[0].NumDescriptors=6;
        ranges[1].RangeType=D3D12_DESCRIPTOR_RANGE_TYPE_UAV;ranges[1].NumDescriptors=6;
        D3D12_ROOT_PARAMETER parameters[3]{};parameters[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV;parameters[0].Descriptor.ShaderRegister=0;
        for(int i=0;i<2;i++) {parameters[i+1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;parameters[i+1].DescriptorTable={1,&ranges[i]};}
        D3D12_ROOT_SIGNATURE_DESC rd{};rd.NumParameters=3;rd.pParameters=parameters;
        ComPtr<ID3DBlob> blob,error;check(D3D12SerializeRootSignature(&rd,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error),"Serialize root signature");
        check(device->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&root)),"Create root signature");
        const char* names[]={"beginRays","continueRays","finishRays","prepareRays","sortRays","refineRays"};
        for(int i=0;i<6;i++) {
            auto bytes=read(shaderDirectory/(std::string(names[i])+".dxil"));
            D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};pd.pRootSignature=root.Get();pd.CS={bytes.data(),bytes.size()};
            check(device->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipelines[i])),names[i]);
        }
        if(fs::exists(shaderDirectory/"packetRays.dxil")) {
            auto bytes=read(shaderDirectory/"packetRays.dxil");D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};
            pd.pRootSignature=root.Get();pd.CS={bytes.data(),bytes.size()};
            check(device->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipelines[6])),"packetRays");
        }
        if(fs::exists(shaderDirectory/"cachedRays.dxil")) {
            auto bytes=read(shaderDirectory/"cachedRays.dxil");D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};
            pd.pRootSignature=root.Get();pd.CS={bytes.data(),bytes.size()};
            check(device->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipelines[7])),"cachedRays");
        }
        D3D12_INDIRECT_ARGUMENT_DESC argument{};argument.Type=D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH;
        D3D12_COMMAND_SIGNATURE_DESC signature{};signature.ByteStride=12;signature.NumArgumentDescs=1;signature.pArgumentDescs=&argument;
        check(device->CreateCommandSignature(&signature,nullptr,IID_PPV_ARGS(&indirect)),"Create indirect signature");
        constants=buffer((data.size()+255)&~size_t(255),D3D12_HEAP_TYPE_UPLOAD,false);
        void* mapped=nullptr;D3D12_RANGE empty{0,0};check(constants.object->Map(0,&empty,&mapped),"Map constants");memcpy(mapped,data.data(),data.size());constants.object->Unmap(0,nullptr);
        UINT capacity=width*height;rays[0]=buffer(UINT64(capacity)*48);rays[1]=buffer(UINT64(capacity)*48);
        inspectQueue=GetEnvironmentVariableW(L"AURORA_PROBE_QUEUE_CHECK",nullptr,0)!=0;
        if(inspectQueue) queueReadback=buffer(UINT64(capacity)*96+65536,D3D12_HEAP_TYPE_READBACK,false);
        UINT bucketCount=128;char setting[32]{};
        if(GetEnvironmentVariableA("AURORA_PROBE_BUCKETS",setting,sizeof(setting))) bucketCount=std::max(128,std::min(8192,atoi(setting)));
        if(GetEnvironmentVariableA("AURORA_PROBE_START",setting,sizeof(setting))) cacheStart=std::max(1,std::min(32,atoi(setting)));
        refinement=buffer(UINT64(capacity)*16);args=buffer(32);count=buffer(4);buckets=buffer(bucketCount*4);
        D3D12_RESOURCE_DESC td{};td.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;td.Width=width;td.Height=height;td.DepthOrArraySize=td.MipLevels=1;td.SampleDesc.Count=1;
        td.Format=DXGI_FORMAT_R32G32_FLOAT;td.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
        D3D12_HEAP_PROPERTIES hp{};hp.Type=D3D12_HEAP_TYPE_DEFAULT;output.state=D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        check(device->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&td,output.state,nullptr,IID_PPV_ARGS(&output.object)),"Create ray image");
        for(UINT i=0;i<2;i++) {
            UINT base=i*16;srv(base+1,rays[i],capacity,48);srv(base+2,args,8);srv(base+4,buckets,bucketCount);
            base=32+i*16;
            D3D12_UNORDERED_ACCESS_VIEW_DESC u{};u.Format=td.Format;u.ViewDimension=D3D12_UAV_DIMENSION_TEXTURE2DARRAY;u.Texture2DArray.ArraySize=1;
            device->CreateUnorderedAccessView(output.object.Get(),nullptr,&u,cpu(base));
            uav(base+1,rays[i],capacity,48);uav(base+2,args,8);uav(base+3,count,1);uav(base+4,buckets,bucketCount);uav(base+5,refinement,capacity,16);
        }
        D3D12_QUERY_HEAP_DESC query{};query.Type=D3D12_QUERY_HEAP_TYPE_TIMESTAMP;query.Count=2;
        check(device->CreateQueryHeap(&query,IID_PPV_ARGS(&queries)),"Create timer queries");timestamps=buffer(16,D3D12_HEAP_TYPE_READBACK,false);
        device->GetCopyableFootprints(&td,0,1,0,&footprint,nullptr,nullptr,&copyBytes);depthReadback=buffer(copyBytes,D3D12_HEAP_TYPE_READBACK,false);
    }
    double frame(bool capture) {
        check(allocator->Reset(),"Reset allocator");check(list->Reset(allocator.Get(),nullptr),"Reset command list");
        ID3D12DescriptorHeap* heaps[]={descriptors.Get()};list->SetDescriptorHeaps(1,heaps);list->SetComputeRootSignature(root.Get());
        list->SetComputeRootConstantBufferView(0,constants.object->GetGPUVirtualAddress());
        list->EndQuery(queries.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0);
        transition(output,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);transition(rays[0],D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
        clear(35,count);clear(36,buckets);barrier();
        bind(0,0,0);list->Dispatch((width+7)/8,(height+7)/8,1);barrier();
        for(int batch=1;batch<33;batch++) {
            transition(count,D3D12_RESOURCE_STATE_COPY_SOURCE);transition(args,D3D12_RESOURCE_STATE_COPY_DEST);
            list->CopyBufferRegion(args.object.Get(),12,count.object.Get(),0,4);
            transition(count,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);transition(args,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
            bind(3,0,0);list->Dispatch(1,1,1);barrier();
            transition(args,D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT|D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            transition(buckets,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);transition(rays[0],D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            transition(rays[1],D3D12_RESOURCE_STATE_UNORDERED_ACCESS);bind(4,0,1);list->ExecuteIndirect(indirect.Get(),1,args.object.Get(),0,nullptr,0);barrier();
            if(inspectQueue && batch==1) {
                transition(args,D3D12_RESOURCE_STATE_COPY_SOURCE);transition(buckets,D3D12_RESOURCE_STATE_COPY_SOURCE);
                list->CopyBufferRegion(queueReadback.object.Get(),0,args.object.Get(),0,32);
                list->CopyBufferRegion(queueReadback.object.Get(),32,buckets.object.Get(),0,buckets.object->GetDesc().Width);
                for(int i=0;i<2;i++) {transition(rays[i],D3D12_RESOURCE_STATE_COPY_SOURCE);
                    list->CopyBufferRegion(queueReadback.object.Get(),65536+UINT64(i)*width*height*48,rays[i].object.Get(),0,UINT64(width)*height*48);}
                transition(args,D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT|D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            }
            transition(rays[1],D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);transition(rays[0],D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
            bool packet=pipelines[6] && batch>=4 && batch<32;
            bool cached=pipelines[7] && batch>=cacheStart && batch<32;
            clear(35,count);clear(36,buckets);barrier();bind(packet?6:cached?7:batch==32?2:1,1,0);
            list->ExecuteIndirect(indirect.Get(),1,args.object.Get(),packet?16:0,nullptr,0);barrier();
        }
        bind(5,0,0);list->Dispatch((width+7)/8,(height+7)/8,1);barrier();
        list->EndQuery(queries.Get(),D3D12_QUERY_TYPE_TIMESTAMP,1);
        list->ResolveQueryData(queries.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0,2,timestamps.object.Get(),0);
        if(capture) {
            transition(output,D3D12_RESOURCE_STATE_COPY_SOURCE);
            D3D12_TEXTURE_COPY_LOCATION from{};from.pResource=output.object.Get();from.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            D3D12_TEXTURE_COPY_LOCATION to{};to.pResource=depthReadback.object.Get();to.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;to.PlacedFootprint=footprint;
            list->CopyTextureRegion(&to,0,0,0,&from,nullptr);
        }
        check(list->Close(),"Close frame");ID3D12CommandList* submitted[]={list.Get()};queue->ExecuteCommandLists(1,submitted);
        check(queue->Signal(fence.Get(),++serial),"Signal frame");check(fence->SetEventOnCompletion(serial,event),"Wait for frame");
        if(WaitForSingleObject(event,30000)!=WAIT_OBJECT_0) throw std::runtime_error("D3D12 frame timed out");
        check(device->GetDeviceRemovedReason(),"GPU completion");
        if(inspectQueue) {
            void* data=nullptr;D3D12_RANGE range{0,SIZE_T(queueReadback.object->GetDesc().Width)};
            check(queueReadback.object->Map(0,&range,&data),"Read queues");
            std::ofstream f("queue-check.bin",std::ios::binary);f.write(static_cast<const char*>(data),std::streamsize(range.End));
            const auto* header=static_cast<const UINT*>(data);UINT size=header[3],capacity=width*height;
            bool valid=size<=capacity;
            std::vector<int> positions(capacity,-1);
            const auto* source=reinterpret_cast<const UINT*>(static_cast<const char*>(data)+65536);
            const auto* sorted=source+size_t(capacity)*12;
            if(valid) for(UINT i=0;i<size;i++) {
                UINT index=source[size_t(i)*12];
                if(index>=capacity || positions[index]>=0) {valid=false;break;}
                positions[index]=int(i);
            }
            if(valid) for(UINT i=0;i<size;i++) {
                const auto* job=sorted+size_t(i)*12;UINT index=job[0];
                if(index>=capacity || positions[index]<0 || memcmp(job,source+size_t(positions[index])*12,48)!=0) {valid=false;break;}
                positions[index]=-1;
            }
            D3D12_RANGE empty{0,0};queueReadback.object->Unmap(0,&empty);inspectQueue=false;
            if(!valid) throw std::runtime_error("First sorted queue is not an exact permutation of its input; see queue-check.bin");
            std::cerr<<"Queue permutation verified: "<<size<<" jobs\n";
        }
        UINT64* times=nullptr;D3D12_RANGE range{0,16};check(timestamps.object->Map(0,&range,reinterpret_cast<void**>(&times)),"Read timestamps");
        double ms=double(times[1]-times[0])*1000/double(frequency);D3D12_RANGE empty{0,0};timestamps.object->Unmap(0,&empty);return ms;
    }
    std::vector<float> depths() {
        unsigned char* mapped=nullptr;D3D12_RANGE range{0,SIZE_T(copyBytes)};check(depthReadback.object->Map(0,&range,reinterpret_cast<void**>(&mapped)),"Read depth");
        std::vector<float> data(size_t(width)*height*2);
        for(UINT y=0;y<height;y++) memcpy(data.data()+size_t(y)*width*2,mapped+footprint.Offset+size_t(y)*footprint.Footprint.RowPitch,size_t(width)*8);
        D3D12_RANGE empty{0,0};depthReadback.object->Unmap(0,&empty);return data;
    }
};
int main(int argc,char** argv) {
    try {
        if(argc!=4) throw std::runtime_error("Usage: AuroraDX12Probe shader-directory constants.bin reference-depth.bin");
        Probe probe;probe.initialize(argv[1],read(argv[2]));
        double sum=0,maximum=0;
        for(int frame=-4;frame<12;frame++) {double ms=probe.frame(frame==11);if(frame>=0) {sum+=ms;maximum=std::max(maximum,ms);}}
        auto data=probe.depths();auto raw=read(argv[3]);if(raw.size()!=data.size()*sizeof(float)) throw std::runtime_error("Depth image size mismatch");
        std::vector<float> expected(data.size());memcpy(expected.data(),raw.data(),raw.size());
        size_t statuses=0,depths=0,unfinished=0;double maxError=0;
        for(size_t i=0;i<data.size();i+=2) {
            statuses+=data[i+1]!=expected[i+1];unfinished+=data[i+1]<0;
            if(data[i+1]>0 && expected[i+1]>0) {depths+=data[i]!=expected[i];maxError=std::max(maxError,std::abs(double(data[i])-expected[i]));}
        }
        std::ofstream capture("dx12-depth.bin",std::ios::binary);capture.write(reinterpret_cast<const char*>(data.data()),std::streamsize(data.size()*sizeof(float)));
        std::cout<<std::setprecision(9)<<"{\"width\":"<<probe.width<<",\"height\":"<<probe.height<<",\"trace_refine_ms\":"<<sum/12<<",\"max_ms\":"<<maximum
            <<",\"status_changes\":"<<statuses<<",\"hit_depth_changes\":"<<depths<<",\"max_log_depth_error\":"<<maxError<<",\"unfinished\":"<<unfinished<<"}\n";
        return statuses || depths ? 2:0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
