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
float citadelDistanceCached(float3 basis,float4 origin,float3 pole,float logScale,int lo) {
    float power=origin.w+logScale;
    if(power>60) return .45*length(basis);
    float derivative=exp2(max(power,-120));
    float3 delta=basis*derivative;
    #if FAST_CITADEL
    float squared=dot(delta,delta);
    float denominator=1+2*dot(pole,delta)+dot(pole,pole)*squared;
    delta=(delta+pole*squared)/denominator;derivative/=denominator;
    #endif
    float3 p=origin.xyz+delta;
    // The last folded point of a skipped prefix may already be the first
    // escape. Do not apply another fold and change its distance estimate.
    if(lo>0 && dot(p,p)>4096) return .45*length(p)/max(derivative,1e-30);
    bool direct=false;
    int end=min(384,counts.x+12);
    [loop] for(int i=lo;i<end;i++) {
        #if FAST_CITADEL && CACHE_PREFIX
        if(derivative>renderInfo.y*1.85*.001) direct=true;
        if(dot(p,p)>64) {
            // Outside radius eight, |boxFold(p)| >= |p|-2*sqrt(3)>1:
            // sphere inversion is impossible. With scale 2.8 and |c|=2.1,
            // four affine folds suffice to reach the radius-64 escape sphere.
            [unroll] for(int tail=0;tail<4;tail++) {
                if(i+tail>=end) break;
                p=(2*clamp(p,-1,1)-p)*2.8+fractalParameters.xyz;derivative*=2.8;
                #if TRACE_DIAGNOSTIC == 3
                fieldIterations++;
                #endif
                if(dot(p,p)>4096 || derivative>1e24) break;
            }
            return .45*length(p)/max(derivative,1e-30);
        }
        #elif FAST_CITADEL
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
    return .45*length(p)/max(derivative,1e-30);
}
float citadelDistanceFrom(float3 offset,float logScale,int lo) {
    OrbitSample a=reference[lo];
    return citadelDistanceCached(a.x.xyz*offset.x+a.y.xyz*offset.y+a.z.xyz*offset.z,a.p,a.curve.xyz,logScale,lo);
}
float citadelDistance(float3 offset,float logScale) {
    return citadelDistanceFrom(offset,logScale,citadelStart(log2(max(length(offset),1e-30))+logScale));
}
float scene(float3 p,float scale) {
    if(counts.w==1) return citadelDistance(p,scale);
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
float4 renderRay(float2 uv) {
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float pixel=1.0/(renderInfo.y*1.85);
    float travel=-7.0;
    float horizon=20;
    if(counts.w==1) {
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
    bool hit=false;int steps=0;
    #if CACHE_PREFIX
    float radiusOffset=log2(max(length(rd),1e-30));
    int first=counts.w==1?citadelStart(travel+radiusOffset):0;
    float limit=prefixLimit(first);
    OrbitSample prefix=reference[first];
    float3 basis=prefix.x.xyz*rd.x+prefix.y.xyz*rd.y+prefix.z.xyz*rd.z;
    float4 origin=prefix.p;float3 pole=prefix.curve.xyz;
    #endif
    #if FAST_MARCH
    float previousTravel=travel,previousRadius=0,relaxation=.9;
    bool verify=false;
    #endif
    // Rays in narrow passages can need hundreds of steps before the far wall.
    // All display profiles allow the same long trace; completed rays exit here
    // immediately. A small quality budget must not turn unfinished rays into sky.
    [loop] for(int i=0;i<MARCH_STEPS;i++) {
        steps=i+1;
        float ratio;
        #if CACHE_PREFIX
        if(counts.w==1) {
            // Travel only increases. Retain the valid prefix until this ray
            // actually leaves its domain instead of searching all over again.
            if(first>0 && travel+radiusOffset>=limit) {
                [loop] while(first>0 && travel+radiusOffset>=limit) {first--;limit=prefixLimit(first);}
                prefix=reference[first];basis=prefix.x.xyz*rd.x+prefix.y.xyz*rd.y+prefix.z.xyz*rd.z;
                origin=prefix.p;pole=prefix.curve.xyz;
            }
            ratio=citadelDistanceCached(basis,origin,pole,travel,first);
        } else ratio=scene(rd,travel);
        #else
        ratio=scene(rd,travel);
        #endif
        #if FAST_MARCH
        if(verify) {
            float relative=exp2(travel-previousTravel);
            if(previousRadius+ratio*relative<(relative-1)*1.00001) {
                // Disjoint empty spheres do not prove the intervening space
                // empty. Return to the previous conservative step before
                // accepting a hit or an exit.
                travel=previousTravel+log2(1+max(previousRadius*.9,1e-7));
                relaxation=1;verify=false;
                #if CACHE_PREFIX
                first=counts.w==1?citadelStart(travel+radiusOffset):0;limit=prefixLimit(first);
                prefix=reference[first];basis=prefix.x.xyz*rd.x+prefix.y.xyz*rd.y+prefix.z.xyz*rd.z;
                origin=prefix.p;pole=prefix.curve.xyz;
                #endif
                continue;
            }
            if(travel>horizon) break;
        }
        #endif
        if(ratio<pixel*.65) {
            #if FAST_MARCH
            // Locate the same pixel-footprint boundary regardless of the
            // accepted step length; otherwise larger safe steps change normal
            // sampling depth and make fine surfaces sparkle.
            if(counts.w==1) {
                float lower=previousTravel,upper=travel;
                [unroll] for(int refine=0;refine<3;refine++) {
                    float middle=(lower+upper)*.5;
                    #if CACHE_PREFIX
                    float middleDistance=citadelDistanceCached(basis,origin,pole,middle,first);
                    #else
                    float middleDistance=scene(rd,middle);
                    #endif
                    if(middleDistance<pixel*.65) upper=middle;else lower=middle;
                }
                travel=upper;
            }
            #endif
            hit=true;break;
        }
        #if FAST_MARCH
        if(counts.w==1 && previousRadius>0 && travel>previousTravel) {
            float relative=exp2(travel-previousTravel);
            float slope=(previousRadius-ratio*relative)/max(relative-1,1e-7);
            relaxation=clamp(1.85/(1+max(0,slope)),.9,1.85);
        }
        previousTravel=travel;previousRadius=ratio;
        travel+=log2(1+max(ratio*relaxation,1e-7));
        verify=relaxation>1;
        if(!verify && travel>horizon) break;
        #else
        travel+=log2(1+max(ratio*.9,1e-7));
        if(travel>horizon) break;
        #endif
    }
    #if TRACE_DIAGNOSTIC == 3
    return float4(steps,fieldIterations,hit?1:0,travel);
    #elif TRACE_DIAGNOSTIC == 2
    return float4(travel,hit?1:travel>horizon?0:-1,0,1);
    #elif TRACE_DIAGNOSTIC
    return float4(hit?float3(0,1,0):travel>horizon?float3(0,0,1):float3(1,0,0),1);
    #else
    return float4(finishColor(hit?shade(rd,travel,pixel):skyColor(rd)),hit || travel>horizon?1:0);
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
