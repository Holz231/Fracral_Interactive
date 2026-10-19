#ifndef COOPERATIVE_RAYS
#define COOPERATIVE_RAYS 0
#endif
#ifndef CONE_START
#define CONE_START 0
#endif
#ifndef UNIFORM_FOLDS
#define UNIFORM_FOLDS 0
#endif
#ifndef DEFER_SURFACE_REFINE
#define DEFER_SURFACE_REFINE 0
#endif
#ifndef MARCH_STEPS
#define MARCH_STEPS 8192
#endif
#ifndef SHADOW_STEPS
#define SHADOW_STEPS 4
#endif
#ifndef AO_STEPS
#define AO_STEPS 3
#endif
#ifndef FAST_FIELD
#define FAST_FIELD 1
#endif
#ifndef PIXEL_SAMPLES
#define PIXEL_SAMPLES 1
#endif
#ifndef TRACE_DIAGNOSTIC
#define TRACE_DIAGNOSTIC 0
#endif
#ifndef BOX_CULL
#define BOX_CULL 1
#endif
#ifndef FAST_CITADEL
#define FAST_CITADEL 1
#endif
#ifndef CACHE_PREFIX
#define CACHE_PREFIX 1
#endif
#ifndef FAST_MARCH
#define FAST_MARCH 1
#endif
#ifndef COMPACT_REFINE
#define COMPACT_REFINE 1
#endif
#ifndef WORLD_KIND
#define WORLD_KIND -1
#endif
#if WORLD_KIND == 0 || WORLD_KIND == 1
#define SCENE_KIND WORLD_KIND
#else
#define SCENE_KIND counts.w
#endif
#if TRACE_DIAGNOSTIC == 3
static uint fieldIterations=0;
#endif
struct OrbitSample {float4 p,q,next,x,y,z,curve;};
cbuffer Scene : register(b0) {
    float4 renderInfo;
    float4 viewRight,viewUp,viewForward;
    int4 counts;
    float4 fractalParameters;
    float4 orbit[18],octaves[18],parents[48],parentMeta[48];
    OrbitSample reference[384];
    float4 boundsLow,boundsHigh;
};
struct VertexOut {float4 position:SV_Position;float2 uv:TEXCOORD0;};
VertexOut vertexMain(uint id:SV_VertexID) {
    VertexOut o;o.uv=float2((id<<1)&2,id&2);
    o.position=float4(o.uv.x*2-1,1-o.uv.y*2,0,1);return o;
}
float3 toLattice(float3 p) {return float3(.91*p.x+.22*p.y-.10*p.z,.69*p.y+.18*p.z,.18*p.x+1.04*p.z);}
float vaultDistance(float3 local,float footprint) {
    float best=-1e10,localSquared=dot(local,local);
    [loop] for(int j=0;j<counts.y;j++) {
        float4 p=parents[j];float k=parentMeta[j].x,a=dot(p.xyz,local);
        float l=sqrt(max(1+2*k*a+k*k*localSquared,1e-20));
        best=max(best,p.w-(2*a+k*localSquared)/(1+l));
    }
    [loop] for(int i=0;i<counts.x;i++) {
        float4 o=octaves[i];
        #if FAST_FIELD
        if(best>=o.z) break;
        #endif
        float r=o.z/footprint;if(r<14) break;
        float4 ref=orbit[i];float3 d=local*o.x;
        d-=2*floor((ref.xyz+d+1)*.5);float3 q=ref.xyz+d;
        float change=(2*dot(ref.xyz,d)+dot(d,d))/max(1.32-ref.w+length(q),1e-12);
        best=max(best,(ref.w-(1-smoothstep(14,28,r))*1.32-change)*o.y);
    }
    return best*.8;
}
float foldedDelta(float before,float folded,float delta) {
    float p=before+delta;
    if((before>1 && p>1)||(before< -1 && p< -1)) return -delta;
    if(abs(before)<=1 && abs(p)<=1) return delta;
    return 2*clamp(p,-1,1)-p-folded;
}
float3 foldedDeltaVector(float3 before,float3 folded,float3 delta) {
    float3 p=before+delta;
    bool3 outer=((before>1)&&(p>1))||((before<-1)&&(p<-1));
    bool3 inner=(abs(before)<=1)&&(abs(p)<=1);
    return inner?delta:outer?-delta:2*clamp(p,-1,1)-p-folded;
}
// Distance and offset use the same scale. Logarithmic travel preserves the
// actual ancestors in the far view; it never substitutes a background world.
int citadelStart(float radiusLog) {
    int lo=0,hi=counts.x;
    [loop] while(lo+1<hi) {
        int mid=(lo+hi)/2;
        #if FAST_CITADEL
        if(radiusLog<reference[mid].curve.w) lo=mid;else hi=mid;
        #else
        if(radiusLog<reference[mid].x.w) lo=mid;else hi=mid;
        #endif
    }
    return lo;
}
float prefixLimit(int index) {
    #if FAST_CITADEL
    return reference[index].curve.w;
    #else
    return reference[index].x.w;
    #endif
}
float citadelDistanceScaled(float3 basis,float3 origin,float3 pole,float derivative,int lo) {
    float3 delta=basis*derivative;
    #if FAST_CITADEL
    float squared=dot(delta,delta);
    float denominator=1+2*dot(pole,delta)+dot(pole,pole)*squared;
    delta=(delta+pole*squared)/denominator;derivative/=denominator;
    #endif
    float3 p=origin+delta;
    // The last folded point of a skipped prefix may already be the first
    // escape. Do not apply another fold and change its distance estimate.
    if(lo>0 && dot(p,p)>4096) return .45*length(p)/max(derivative,1e-30);
    bool direct=false;
    int end=min(384,counts.x+12);
    #if FAST_CITADEL && CACHE_PREFIX
    int iteration=lo;
    [loop] for(;iteration<end;iteration++) {
        // Once one float ULP in orbit space projects far below one pixel,
        // subsequent folds no longer need reference-precision subtraction.
        if(iteration>=counts.x || derivative>renderInfo.y*1.85*.001 || dot(delta,delta)>64) break;
        #if TRACE_DIAGNOSTIC == 3
        fieldIterations++;
        #endif
        OrbitSample s=reference[iteration];
        #if UNIFORM_FOLDS
        delta=foldedDeltaVector(s.p.xyz,s.q.xyz,delta);
        #else
        delta=float3(foldedDelta(s.p.x,s.q.x,delta.x),foldedDelta(s.p.y,s.q.y,delta.y),foldedDelta(s.p.z,s.q.z,delta.z));
        #endif
        float change=2*dot(s.q.xyz,delta)+dot(delta,delta),r2=s.next.w;
        float dc=clamp(change,.25-r2,1-r2)-clamp(0,.25-r2,1-r2);
        float k=2.8/(s.q.w+dc);
        delta=k*(delta-s.q.xyz*(dc/s.q.w));p=s.next.xyz+delta;derivative*=k;
        if(dot(p,p)>4096 || derivative>1e24) return .45*length(p)/max(derivative,1e-30);
    }
    [loop] for(;iteration<end;iteration++) {
        #if TRACE_DIAGNOSTIC == 3
        fieldIterations++;
        #endif
        // A uniform loop avoids the nested escape-tail loop and its live
        // state. Outside radius eight the sphere denominator is already one,
        // so the arithmetic and bailout points are identical.
        #if !UNIFORM_FOLDS
        if(dot(p,p)>64) {
            [unroll] for(int tail=0;tail<4;tail++) {
                if(iteration+tail>=end) break;
                p=(2*clamp(p,-1,1)-p)*2.8+fractalParameters.xyz;derivative*=2.8;
                #if TRACE_DIAGNOSTIC == 3
                if(tail>0) fieldIterations++;
                #endif
                if(dot(p,p)>4096 || derivative>1e24) break;
            }
            break;
        }
        #endif
        float3 q=2*clamp(p,-1,1)-p;
        float k=2.8/clamp(dot(q,q),.25,1);
        p=q*k+fractalParameters.xyz;derivative*=k;
        if(dot(p,p)>4096 || derivative>1e24) break;
    }
    #else
    [loop] for(int i=lo;i<end;i++) {
        #if FAST_CITADEL
        // Once the orbit is outside radius eight it grows toward escape; its
        // small offset no longer needs reference-precision propagation. Finish
        // those folds directly, without loading another six-vector sample.
        if(dot(p,p)>64) direct=true;
        #endif
        #if TRACE_DIAGNOSTIC == 3
        fieldIterations++;
        #endif
        float k=1;
        if(!direct && i<counts.x) {
            OrbitSample s=reference[i];
            if(dot(delta,delta)>64) {p=s.p.xyz+delta;direct=true;}
            else {
                delta=float3(foldedDelta(s.p.x,s.q.x,delta.x),foldedDelta(s.p.y,s.q.y,delta.y),foldedDelta(s.p.z,s.q.z,delta.z));
                float change=2*dot(s.q.xyz,delta)+dot(delta,delta),r2=s.next.w;
                float dc=clamp(change,.25-r2,1-r2)-clamp(0,.25-r2,1-r2);
                k=2.8/(s.q.w+dc);
                delta=k*(delta-s.q.xyz*(dc/s.q.w));p=s.next.xyz+delta;
            }
        } else direct=true;
        if(direct) {p=2*clamp(p,-1,1)-p;k=2.8/clamp(dot(p,p),.25,1);p=p*k+fractalParameters.xyz;}
        derivative*=k;
        if(dot(p,p)>4096 || derivative>1e24) break;
    }
    #endif
    return .45*length(p)/max(derivative,1e-30);
}
float citadelDistanceFrom(float3 offset,float logScale,int lo) {
    OrbitSample a=reference[lo];
    float power=a.p.w+logScale;
    if(power>60) return .45*length(offset);
    return citadelDistanceScaled(a.x.xyz*offset.x+a.y.xyz*offset.y+a.z.xyz*offset.z,a.p.xyz,a.curve.xyz,exp2(max(power,-120)),lo);
}
float citadelDistance(float3 offset,float logScale) {
    return citadelDistanceFrom(offset,logScale,citadelStart(log2(max(length(offset),1e-30))+logScale));
}
float scene(float3 p,float scale) {
    if(SCENE_KIND==1) return citadelDistance(p,scale);
    float factor=exp2(clamp(scale,-100,100));
    return vaultDistance(toLattice(p*factor),max(.00005,factor/renderInfo.y))/factor;
}
float3 stone(float3 n,float ao) {
    float3 warm=float3(.64,.40,.16),cool=float3(.035,.15,.22);
    if(counts.z==1) {warm=float3(.60,.73,.80);cool=float3(.055,.13,.28);}
    if(counts.z==2) {warm=float3(.43,.58,.38);cool=float3(.035,.14,.12);}
    // Broad orientation and occlusion, independent of reference depth.
    return lerp(cool,warm,smoothstep(.08,.78,ao)*(.70+.30*saturate(n.y*.5+.5)));
}
float3 shade(float3 rd,float logTravel,float pixelWidth) {
    float h=max(pixelWidth*1.25,1e-5);
    float3 a=float3(1,-1,-1),b=float3(-1,-1,1),c=float3(-1,1,-1),d=float3(1,1,1);
    float3 grad=a*scene(rd+a*h,logTravel)+b*scene(rd+b*h,logTravel)+c*scene(rd+c*h,logTravel)+d*scene(rd+d*h,logTravel);
    float3 n=dot(grad,grad)>1e-25?normalize(grad):-rd;
    if(dot(n,rd)>0) n=-n;
    float ao=0,weight=1;
    [unroll] for(int j=0;j<AO_STEPS;j++) {
        float radius=max(h*4,.006)*exp2(float(j)*1.7);
        ao+=saturate(1-scene(rd+n*radius,logTravel)/radius)*weight;weight*=.5;
    }
    ao=saturate(1-ao*.5);
    float3 light=normalize(float3(-.55,.8,-.4));float diffuse=saturate(dot(n,light));
    float shadow=1;
    #if SHADOW_STEPS > 0
    float t=max(h*6,.008);
    [loop] for(int j=0;j<SHADOW_STEPS;j++) {
        float dist=scene(rd+n*h*3+light*t,logTravel);
        shadow=min(shadow,saturate(12*dist/t));t+=max(dist,t*.7);
    }
    #endif
    float3 material=stone(n,ao);
    float facing=saturate(dot(n,-rd));
    float3 color=material*(.18+.26*facing+diffuse*(.45+.65*shadow))*ao;
    color+=float3(.04,.09,.14)*(.3+.7*saturate(n.y))*ao;
    color+=float3(.70,.60,.42)*pow(saturate(dot(n,normalize(light-rd))),18)*shadow*.1;
    return color;
}
float3 finishColor(float3 col) {
    col=saturate((col*(2.51*col+.03))/(col*(2.43*col+.59)+.14));
    return pow(col,.4545);
}
float3 skyColor(float3 rd) {
    return lerp(float3(.007,.013,.025),float3(.025,.052,.08),saturate(rd.y*.5+.5));
}
bool clipPlane(float direction,float logBound,bool positive,inout float enter,inout float leave) {
    if(abs(direction)<1e-20) return positive;
    float crossing=logBound-log2(abs(direction));
    if(direction>0) {
        if(!positive) return false;
        leave=min(leave,crossing);
    } else if(!positive) enter=max(enter,crossing);
    return enter<=leave;
}
bool clipBounds(float3 rd,inout float horizon) {
    float enter=-1000;
    // Only the exit/miss is used: changing the start would shift surface hits.
    // Clip the actual rays; expanding a plane with distance would create an
    // endless strip of grazing sky rays when approaching a sharp corner.
    [unroll] for(int axis=0;axis<3;axis++) {
        bool lowPositive=(int(boundsLow.w)&(1<<axis))!=0;
        bool highPositive=(int(boundsHigh.w)&(1<<axis))!=0;
        if(!clipPlane(-rd[axis],boundsLow[axis],!lowPositive,enter,horizon)) return false;
        if(!clipPlane(rd[axis],boundsHigh[axis],highPositive,enter,horizon)) return false;
    }
    return true;
}
struct RayPrefix {float3 basis,origin,pole;float derivative,limit;};
RayPrefix rayPrefix(float3 rd,int first,float scale) {
    OrbitSample a=reference[first];RayPrefix r;
    r.basis=a.x.xyz*rd.x+a.y.xyz*rd.y+a.z.xyz*rd.z;r.origin=a.p.xyz;r.pole=a.curve.xyz;
    r.derivative=exp2(max(a.p.w+scale,-120));r.limit=exp2(min(prefixLimit(first)-scale,100));return r;
}
float2 traceCitadel(float3 rd,float pixel,float start,float horizon,out int steps) {
    // A local linear travel coordinate avoids log/exp and cancellation on every
    // step. Rebase its power-of-two scale only when it leaves a small float range.
    float scale=floor(start),t=exp2(start-scale),previous=t,previousRadius=0,relaxation=.9;
    float exitT=exp2(min(horizon-scale,24));bool verify=false,hit=false,escaped=false;
    int first=citadelStart(start);RayPrefix prefix=rayPrefix(rd,first,scale);
    steps=0;
    [loop] for(int i=0;i<MARCH_STEPS;i++) {
        steps++;
        if(t>4096) {
            scale+=12;t/=4096;previous/=4096;prefix.derivative*=4096;prefix.limit/=4096;
            exitT=exp2(min(horizon-scale,24));
        }
        if(first>0 && t>=prefix.limit) {
            [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-scale,100)));
            prefix=rayPrefix(rd,first,scale);
        }
        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        if(verify) {
            float relative=t/previous;
            if(previousRadius+ratio*relative<(relative-1)*1.00001) {
                // A rejected speculative sample is not an accepted advance.
                // Keep the full progress budget for narrow, grazing passages.
                t=previous*(1+max(previousRadius*.9,1e-7));relaxation=1;verify=false;i--;continue;
            }
            if(t>exitT) {escaped=true;break;}
        }
        if(ratio<pixel*.65) {
            float lower=previous,upper=t;
            #if COMPACT_REFINE
            [loop]
            #else
            [unroll]
            #endif
            for(int refine=0;refine<3;refine++) {
                float middle=(lower+upper)*.5;
                float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first);
                if(d<pixel*.65) upper=middle;else lower=middle;
            }
            t=upper;hit=true;break;
        }
        if(previousRadius>0 && t>previous) {
            float relative=t/previous;
            float slope=(previousRadius-ratio*relative)/max(relative-1,1e-7);
            relaxation=clamp(1.85/(1+max(0,slope)),.9,1.85);
        }
        previous=t;previousRadius=ratio;t*=1+max(ratio*relaxation,1e-7);verify=relaxation>1;
        if(!verify && t>exitT) {escaped=true;break;}
    }
    // Converting back to logarithms can round a just-escaped t onto the exact
    // horizon. Carry completion explicitly instead of testing that rounded log.
    return float2(log2(t)+scale,hit?1:escaped?0:-1);
}
float4 renderRay(float2 uv) {
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float pixel=1.0/(renderInfo.y*1.85);
    float travel=-7.0;
    float horizon=20;
    if(SCENE_KIND==1) {
        float3 origin=reference[0].p.xyz;
        float along=dot(origin,rd);
        float3 closest=origin-rd*along;
        float halfChord=sqrt(max(0,64-dot(closest,closest)));
        float exitDistance=-along+halfChord;
        if(exitDistance<=0 || dot(closest,closest)>64) {
            #if TRACE_DIAGNOSTIC
            return float4(0,0,1,1);
            #else
            return float4(finishColor(skyColor(rd)),1);
            #endif
        }
        horizon=log2(exitDistance)-reference[0].p.w;
        float entry=-along-halfChord;
        if(entry>0) travel=max(travel,log2(entry)-reference[0].p.w);
        #if BOX_CULL
        if(!clipBounds(rd,horizon)) {
            #if TRACE_DIAGNOSTIC
            return float4(0,0,1,1);
            #else
            return float4(finishColor(skyColor(rd)),1);
            #endif
        }
        // Keep the finite pixel footprint at the exit, including float-plane
        // roundoff. Unlike angular plane expansion this cannot run to infinity.
        horizon+=max(1e-4,2*pixel);
        #endif
    }
    bool hit=false,complete=false;int steps=0;
    #if FAST_MARCH
    if(SCENE_KIND==1) {
        float2 result=traceCitadel(rd,pixel,travel,horizon,steps);travel=result.x;hit=result.y>0;complete=result.y>=0;
    } else
    #endif
    {
        [loop] for(int i=0;i<MARCH_STEPS;i++) {
            steps=i+1;
            float ratio=scene(rd,travel);
            if(ratio<pixel*.65) {hit=true;break;}
            travel+=log2(1+max(ratio*.9,1e-7));
            if(travel>horizon) break;
        }
        complete=hit || travel>horizon;
    }
    #if TRACE_DIAGNOSTIC == 3
    return float4(steps,fieldIterations,hit?1:0,travel);
    #elif TRACE_DIAGNOSTIC == 2
    return float4(travel,hit?1:complete?0:-1,0,1);
    #elif TRACE_DIAGNOSTIC
    return float4(hit?float3(0,1,0):complete?float3(0,0,1):float3(1,0,0),1);
    #else
    return float4(finishColor(hit?shade(rd,travel,pixel):skyColor(rd)),complete?1:0);
    #endif
}
float4 samplePixel(float2 position) {
    float2 uv=(position*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    #if PIXEL_SAMPLES > 1
    float2 sub=float2(.5,.5)/renderInfo.y;
    float4 a=renderRay(uv-sub),b=renderRay(uv+sub);
    return float4((a.rgb+b.rgb)*.5,min(a.a,b.a));
    #else
    return renderRay(uv);
    #endif
}
float4 fractalMain(VertexOut input):SV_Target {
    return samplePixel(input.position.xy);
}
Texture2D frameTexture:register(t0);
// Split long Citadel traces into 64, then repeated 256-step batches. Group
// surviving rays by prefix depth between batches; shade after tracing so
// finished pixels do not keep lighting state alive behind long corridor rays.
// The full step budget, conservative retries and surface refinements remain.
#ifndef SORT_RAYS
#define SORT_RAYS 1
#endif
#ifndef RAY_CHUNK
#define RAY_CHUNK 64
#endif
struct RayJob {
    uint index;float horizon,scale,t,previous,radius,relaxation;
    int first,accepted;uint verify;float derivative,limit;
};
RWTexture2DArray<float2> rayOutput:register(u0);
RWStructuredBuffer<RayJob> nextRays:register(u1);
RWBuffer<uint> dispatchOutput:register(u2);
RWBuffer<uint> rayCount:register(u3);
RWBuffer<uint> rayBuckets:register(u4);
RWStructuredBuffer<float4> refinementJobs:register(u5);
Buffer<uint> bucketOffsets:register(t4);
StructuredBuffer<RayJob> activeRays:register(t1);
Buffer<uint> dispatchInput:register(t2);
Texture2DArray<float2> rayImage:register(t3);
uint3 rayPixel(uint index) {
    uint w=uint(renderInfo.x),h=uint(renderInfo.y);
    return uint3(index%w,(index/w)%h,index/(w*h));
}
float3 rayDirection(uint3 position) {
    float2 uv=((float2(position.xy)+.5)*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    return normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
}

// A node covers all pixel centers in its tile. The normalized camera rays
// differ by at most sqrt(2)*(tile-1)/(height*focalLength). The extra .75 pixel
// protects the finite hit footprint in addition to the geometric surface.
RWTexture2DArray<float> conePyramid:register(u6);
#ifndef CONE_TILE
#define CONE_TILE 16
#endif
#ifndef CONE_LEVEL
#define CONE_LEVEL 0
#endif
#ifndef CONE_STEPS
#define CONE_STEPS 256
#endif
[numthreads(8,8,1)]
void buildCones(uint3 id:SV_DispatchThreadID) {
    uint2 size=(uint2(renderInfo.xy)+CONE_TILE-1)/CONE_TILE;
    if(any(id.xy>=size)) return;
    float2 center=float2(id.xy)*CONE_TILE+CONE_TILE*.5;
    float2 uv=(center*2-renderInfo.xy)/renderInfo.y;uv.y=-uv.y;
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float cone=(1.414214*(CONE_TILE-1)+.75)/(renderInfo.y*1.85);
    float start=-7;
    #if CONE_LEVEL > 0
    start=max(start,conePyramid[uint3(id.xy/2,CONE_LEVEL-1)]-8e-6);
    #endif
    float scale=floor(start),t=exp2(start-scale);
    int first=citadelStart(start);RayPrefix prefix=rayPrefix(rd,first,scale);
    float horizon=min(256,8-reference[0].p.w);
    [loop] for(int i=0;i<CONE_STEPS;i++) {
        if(t>4096) {scale+=12;t/=4096;prefix.derivative*=4096;prefix.limit/=4096;}
        if(first>0 && t>=prefix.limit) {
            [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-scale,100)));
            prefix=rayPrefix(rd,first,scale);
        }
        float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        if(d<cone*1.01 || log2(t)+scale>horizon) break;
        // At t*(1+s), the furthest child lies <= t*(s+cone*(1+s)) away.
        // Keep that entire region inside the empty ball at the center ray.
        float angular=1.414214*(CONE_TILE-1)/(renderInfo.y*1.85);
        float shell=.75/(renderInfo.y*1.85),a2=angular*angular;
        // Solve |x*childDirection-centerDirection| + shell*x <= d.
        // This guards both the tile's angle and the finite hit shell.
        float discriminant=(d-shell)*(d-shell)-a2*(1-.25*a2-d*shell);
        float advance=(sqrt(max(0,discriminant))-.5*a2-d*shell+shell*shell)/(1-shell*shell);
        t*=1+.9*max(0,advance);
    }
    conePyramid[uint3(id.xy,CONE_LEVEL)]=log2(t)+scale-8e-6;
}

bool initializeJob(inout RayJob job,float3 rd) {
    float pixel=1.0/(renderInfo.y*1.85),start=-7;
    float3 origin=reference[0].p.xyz;float along=dot(origin,rd);
    float3 closest=origin-rd*along;
    float halfChord=sqrt(max(0,64-dot(closest,closest))),exitDistance=-along+halfChord;
    if(exitDistance<=0 || dot(closest,closest)>64) return false;
    job.horizon=log2(exitDistance)-reference[0].p.w;
    float entry=-along-halfChord;if(entry>0) start=max(start,log2(entry)-reference[0].p.w);
    if(!clipBounds(rd,job.horizon)) return false;
    job.horizon+=max(1e-4,2*pixel);
    #if CONE_START
    uint3 position=rayPixel(job.index);
    start=max(start,conePyramid[uint3(position.xy/4,2)]-8e-6);
    start=min(start,job.horizon);
    #endif
    job.scale=floor(start);job.t=exp2(start-job.scale);job.previous=job.t;job.relaxation=.9;
    job.first=citadelStart(start);RayPrefix prefix=rayPrefix(rd,job.first,job.scale);
    job.derivative=prefix.derivative;job.limit=prefix.limit;return true;
}
#if COOPERATIVE_RAYS
groupshared RayJob segmentJobs[64];
groupshared float2 segmentResults[64];
groupshared float4 segmentRefinement[64];
static uint segmentLane;
#endif
bool marchJob(inout RayJob job,float3 rd,uint3 position) {
    float pixel=1.0/(renderInfo.y*1.85);
    float scale=job.scale,t=job.t,previous=job.previous,radius=job.radius,relaxation=job.relaxation;
    int first=job.first,accepted=job.accepted,end=min(MARCH_STEPS,accepted+RAY_CHUNK);
    bool verify=(job.verify&1)!=0,hit=false,escaped=false;
    RayPrefix prefix=rayPrefix(rd,first,scale);
    // Preserve the exact rebased float values across dispatches. Recomputing
    // these from logarithms introduces colour/depth changes at chunk borders.
    prefix.derivative=job.derivative;prefix.limit=job.limit;
    float exitT=exp2(min(job.horizon-scale,24));
    [loop] for(;accepted<end;accepted++) {
        if(t>4096) {
            scale+=12;t/=4096;previous/=4096;prefix.derivative*=4096;prefix.limit/=4096;
            exitT=exp2(min(job.horizon-scale,24));
        }
        if(first>0 && t>=prefix.limit) {
            [loop] do {first--;} while(first>0 && t>=exp2(min(prefixLimit(first)-scale,100)));
            prefix=rayPrefix(rd,first,scale);
        }
        float ratio=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*t,first);
        if(verify) {
            float relative=t/previous;
            if(radius+ratio*relative<(relative-1)*1.00001) {
                t=previous*(1+max(radius*.9,1e-7));relaxation=1;verify=false;accepted--;continue;
            }
            if(t>exitT) {escaped=true;break;}
        }
        if(ratio<pixel*.65) {
            #if DEFER_SURFACE_REFINE
            hit=true;break;
            #else
            float lower=previous,upper=t;
            [loop] for(int refine=0;refine<3;refine++) {
                float middle=(lower+upper)*.5;
                float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first);
                if(d<pixel*.65) upper=middle;else lower=middle;
            }
            t=upper;hit=true;break;
            #endif
        }
        if(radius>0 && t>previous) {
            float relative=t/previous;
            float slope=(radius-ratio*relative)/max(relative-1,1e-7);
            relaxation=clamp(1.85/(1+max(0,slope)),.9,1.85);
        }
        previous=t;radius=ratio;t*=1+max(ratio*relaxation,1e-7);verify=relaxation>1;
        if(!verify && t>exitT) {escaped=true;break;}
    }
    #if COOPERATIVE_RAYS
    job.scale=scale;job.t=t;job.previous=previous;job.radius=radius;job.relaxation=relaxation;
    job.first=first;job.accepted=accepted;job.verify=verify;job.derivative=prefix.derivative;job.limit=prefix.limit;
    segmentRefinement[segmentLane]=float4(previous,t,prefix.derivative,float(first));
    segmentResults[segmentLane]=float2(hit?scale:log2(t)+scale,hit?2:escaped?0:accepted>=MARCH_STEPS?-1:-2);
    return !hit && !escaped && accepted<MARCH_STEPS;
    #endif
    #if DEFER_SURFACE_REFINE
    if(hit) {
        // Preserve the exact bracket, cached derivative and reference depth.
        // The independent pass performs the same three bisection queries.
        refinementJobs[job.index]=float4(previous,t,prefix.derivative,float(first));
        rayOutput[position]=float2(scale,2);return false;
    }
    #endif
    if(hit || escaped || accepted>=MARCH_STEPS) {
        rayOutput[position]=float2(log2(t)+scale,hit?1:escaped?0:-1);return false;
    }
    job.scale=scale;job.t=t;job.previous=previous;job.radius=radius;job.relaxation=relaxation;
    job.first=first;job.accepted=accepted;job.verify=verify;job.derivative=prefix.derivative;job.limit=prefix.limit;
    return true;
}
groupshared uint pendingCount,pendingBase;
groupshared RayJob pendingRays[64];
groupshared uint groupBuckets[128],groupOffsets[128];
uint rayBucket(RayJob job) {
    // Only scheduling changes: clamping deep prefixes affects grouping, never
    // their stored depth or field evaluation.
    return min(127,uint(job.first));
}
#if SORT_RAYS
void enqueueGroup(uint lane,bool pending,RayJob job) {
    if(lane==0) pendingCount=0;
    groupBuckets[lane]=0;groupBuckets[lane+64]=0;
    GroupMemoryBarrierWithGroupSync();
    if(pending) {uint slot;InterlockedAdd(pendingCount,1,slot);pendingRays[slot]=job;}
    GroupMemoryBarrierWithGroupSync();
    RayJob pendingJob=(RayJob)0;uint rank=0,bucket=0;
    if(lane<pendingCount) {
        pendingJob=pendingRays[lane];bucket=rayBucket(pendingJob);
        InterlockedAdd(groupBuckets[bucket],1,rank);
    }
    GroupMemoryBarrierWithGroupSync();
    if(lane==0) InterlockedAdd(rayCount[0],pendingCount,pendingBase);
    [unroll] for(uint i=0;i<2;i++) {
        uint b=lane+i*64;
        if(groupBuckets[b]) InterlockedAdd(rayBuckets[b],groupBuckets[b],groupOffsets[b]);
    }
    GroupMemoryBarrierWithGroupSync();
    if(lane<pendingCount) {
        // Queue rank shares the flag word; bit zero remains the trace verifier.
        pendingJob.verify=(pendingJob.verify&1)|((rank+groupOffsets[bucket])<<1);
        nextRays[pendingBase+lane]=pendingJob;
    }
}
#else
void enqueueGroup(uint lane,bool pending,RayJob job) {
    if(lane==0) pendingCount=0;
    GroupMemoryBarrierWithGroupSync();
    if(pending) {uint slot;InterlockedAdd(pendingCount,1,slot);pendingRays[slot]=job;}
    GroupMemoryBarrierWithGroupSync();
    if(lane==0) InterlockedAdd(rayCount[0],pendingCount,pendingBase);
    GroupMemoryBarrierWithGroupSync();
    if(lane<pendingCount) nextRays[pendingBase+lane]=pendingRays[lane];
}
#endif
[numthreads(8,8,1)]
void beginRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {
    RayJob job=(RayJob)0;bool pending=false;
    if(id.x<uint(renderInfo.x) && id.y<uint(renderInfo.y)) {
        float3 rd=rayDirection(id);job.index=id.x+uint(renderInfo.x)*(id.y+uint(renderInfo.y)*id.z);
        if(initializeJob(job,rd)) pending=marchJob(job,rd,id);
        else rayOutput[id]=float2(0,0);
    }
    enqueueGroup(lane,pending,job);
}
[numthreads(64,1,1)]
void continueRays(uint3 id:SV_DispatchThreadID,uint lane:SV_GroupIndex) {
    uint index=id.x+id.y*(65535*64);RayJob job=(RayJob)0;bool pending=false;
    if(index<dispatchInput[3]) {
        job=activeRays[index];uint3 position=rayPixel(job.index);
        pending=marchJob(job,rayDirection(position),position);
    }
    #if RAY_CHUNK < MARCH_STEPS
    enqueueGroup(lane,pending,job);
    #endif
}
[numthreads(1,1,1)]
void prepareRays(uint3 id:SV_DispatchThreadID) {
    uint groups=(dispatchOutput[3]+63)/64;
    dispatchOutput[0]=min(groups,65535);dispatchOutput[1]=max(1,(groups+65534)/65535);dispatchOutput[2]=1;
    uint segmentGroups=(dispatchOutput[3]+1)/2;
    dispatchOutput[4]=min(segmentGroups,65535);
    dispatchOutput[5]=max(1,(segmentGroups+65534)/65535);dispatchOutput[6]=1;
    #if SORT_RAYS
    uint offset=0;
    [loop] for(uint bin=0;bin<128;bin++) {uint count=rayBuckets[bin];rayBuckets[bin]=offset;offset+=count;}
    #endif
}
[numthreads(64,1,1)]
void sortRays(uint3 id:SV_DispatchThreadID) {
    uint index=id.x+id.y*(65535*64);
    if(index>=dispatchInput[3]) return;
    RayJob job=activeRays[index];uint rank=job.verify>>1;
    nextRays[bucketOffsets[rayBucket(job)]+rank]=job;
}
[numthreads(8,8,1)]
void refineRays(uint3 position:SV_DispatchThreadID) {
    if(position.x>=uint(renderInfo.x) || position.y>=uint(renderInfo.y)) return;
    float2 sample=rayOutput[position];if(sample.y!=2) return;
    uint index=position.x+uint(renderInfo.x)*position.y;
    float4 job=refinementJobs[index];float lower=job.x,upper=job.y;
    float3 rd=rayDirection(position);int first=int(job.w);
    RayPrefix prefix=rayPrefix(rd,first,sample.x);prefix.derivative=job.z;
    float pixel=1/(renderInfo.y*1.85);
    [loop] for(int refine=0;refine<3;refine++) {
        float middle=(lower+upper)*.5;
        float d=citadelDistanceScaled(prefix.basis,prefix.origin,prefix.pole,prefix.derivative*middle,first);
        if(d<pixel*.65) upper=middle;else lower=middle;
    }
    rayOutput[position]=float2(log2(upper)+sample.x,1);
}
float4 shadeJob(uint3 p) {
    float2 surface=rayImage.Load(int4(p,0));float3 rd=rayDirection(p);
    return float4(finishColor(surface.y>0?shade(rd,surface.x,1.0/(renderInfo.y*1.85)):skyColor(rd)),surface.y>=0?1:0);
}
float4 resolveRays(VertexOut input):SV_Target {
    uint2 p=uint2(input.position.xy);float4 a=shadeJob(uint3(p,0));
    return a;
}
float4 resolveRayStatus(VertexOut input):SV_Target {
    return float4(rayImage.Load(int4(int2(input.position.xy),0,0)),0,1);
}
float4 probeMain(VertexOut input):SV_Target {
    int i=int(input.position.x);
    float3 offset=float3((i*13)%23-11,(i*7)%19-9,(i*17)%29-14)*.125;
    float scale=float(i/32)*3-9;
    return float4(citadelDistance(offset,scale),0,0,1);
}
SamplerState linearSampler:register(s0);
float4 presentMain(VertexOut input):SV_Target {
    uint w,h;frameTexture.GetDimensions(w,h);float2 texel=1./float2(w,h);
    float3 c=frameTexture.SampleLevel(linearSampler,input.uv,0).rgb;
    float3 a=frameTexture.SampleLevel(linearSampler,input.uv+float2(texel.x,0),0).rgb;
    float3 b=frameTexture.SampleLevel(linearSampler,input.uv-float2(texel.x,0),0).rgb;
    float3 d=frameTexture.SampleLevel(linearSampler,input.uv+float2(0,texel.y),0).rgb;
    float3 e=frameTexture.SampleLevel(linearSampler,input.uv-float2(0,texel.y),0).rgb;
    float3 lo=min(c,min(min(a,b),min(d,e))),hi=max(c,max(max(a,b),max(d,e)));
    float contrast=max(hi.r-lo.r,max(hi.g-lo.g,hi.b-lo.b));
    return float4(lerp(c,(a+b+d+e+c*4)/8,smoothstep(.12,.42,contrast)*.6),1);
}

#if COOPERATIVE_RAYS
[numthreads(64,1,1)]
void segmentRays(uint3 group:SV_GroupID,uint lane:SV_GroupIndex) {
    uint index=(group.x+group.y*65535)*2+lane/32;
    uint part=lane%32;segmentLane=lane;
    RayJob original=(RayJob)0,job=(RayJob)0;bool pending=false;
    segmentResults[lane]=float2(0,0);
    if(index<dispatchInput[3]) {
        original=activeRays[index];job=original;uint3 position=rayPixel(job.index);
        float3 rd=rayDirection(position);
        float begin=original.t*pow(1.05,float(part)),end=original.t*pow(1.05,float(part+1));
        float logBegin=log2(begin)+job.scale;
        job.horizon=min(original.horizon,log2(end)+original.scale);
        if(part>0) {
            job.t=job.previous=begin;job.radius=0;job.relaxation=.9;job.verify=0;
            job.first=citadelStart(logBegin);
            RayPrefix prefix=rayPrefix(rd,job.first,job.scale);
            job.derivative=prefix.derivative;job.limit=prefix.limit;
        }
        if(logBegin<=original.horizon) marchJob(job,rd,position);
        else segmentResults[lane]=float2(logBegin,0);
    }
    segmentJobs[lane]=job;
    GroupMemoryBarrierWithGroupSync();
    if(part==0 && index<dispatchInput[3]) {
        uint chosen=lane;
        [unroll] for(uint j=0;j<31;j++) {
            if(segmentResults[chosen].y==0) chosen++;
        }
        job=segmentJobs[chosen];float2 result=segmentResults[chosen];
        job.horizon=original.horizon;
        pending=result.y==-2 || (result.y==0 && result.x<=original.horizon);
        if(pending && job.accepted>=MARCH_STEPS) {pending=false;result.y=-1;}
        if(!pending) {
            uint3 position=rayPixel(job.index);rayOutput[position]=result;
            if(result.y==2) refinementJobs[job.index]=segmentRefinement[chosen];
        }
    }
    enqueueGroup(lane,pending,job);
}
#endif
