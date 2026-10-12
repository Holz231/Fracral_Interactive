#ifndef MARCH_STEPS
#define MARCH_STEPS 112
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
#ifndef VIEW_DISTANCE
#define VIEW_DISTANCE 4096.0
#endif
cbuffer Scene : register(b0) {
    float4 renderInfo;
    float4 viewRight,viewUp,viewForward;
    int4 counts;
    float4 fractalParameters;
    float4 rootCamera;
    float4 rootRight,rootUp,rootForward;
    float4 orbit[18];
    float4 octaves[18];
    float4 parents[48];
    float4 parentMeta[48];
};
struct VertexOut {float4 position:SV_Position;float2 uv:TEXCOORD0;};
VertexOut vertexMain(uint id:SV_VertexID) {
    VertexOut o;
    o.uv=float2((id<<1)&2,id&2);
    o.position=float4(o.uv.x*2-1,1-o.uv.y*2,0,1);
    return o;
}
float3 toLattice(float3 p) {return float3(.91*p.x+.22*p.y-.10*p.z,.69*p.y+.18*p.z,.18*p.x+1.04*p.z);}
float3 fromNormal(float3 n) {return normalize(float3(.91*n.x+.18*n.z,.22*n.x+.69*n.y,-.10*n.x+.18*n.y+1.04*n.z));}

float4 vaultField(float3 local,float footprint,bool shade,out float level) {
    float best=-1e10;
    float3 normal=float3(0,1,0);
    level=renderInfo.w;
    float localSquared=dot(local,local);
    [loop] for(int j=0;j<counts.y;j++) {
        float4 parent=parents[j];
        float k=parentMeta[j].x,a=dot(parent.xyz,local);
        float l=sqrt(max(1+2*k*a+k*k*localSquared,1e-20));
        float d=parent.w-(2*a+k*localSquared)/(1+l);
        if(d>best) {
            best=d;
            if(shade) {normal=-(parent.xyz+k*local)/l;level=parentMeta[j].y;}
        }
    }
    [loop] for(int i=0;i<counts.x;i++) {
        float4 octave=octaves[i];
        #if FAST_FIELD
        if(best>=octave.z) break;
        #endif
        float screenRadius=octave.z/footprint;
        if(screenRadius<14) break;
        float resolved=smoothstep(14,28,screenRadius);
        float4 reference=orbit[i];
        float3 delta=local*octave.x;
        delta-=2*floor((reference.xyz+delta+1)*.5);
        float3 q=reference.xyz+delta;
        float r=length(q);
        float change=(2*dot(reference.xyz,delta)+dot(delta,delta))/max(1.32-reference.w+r,1e-12);
        float d=(reference.w-(1-resolved)*1.32-change)*octave.y;
        if(d>best) {
            best=d;
            if(shade) {normal=-q/max(r,1e-12);level=renderInfo.w+i;}
        }
    }
    return float4(normal,best);
}
float foldedOffset(float before,float folded,float delta) {
    float p=before+delta;
    if((before>1 && p>1) || (before< -1 && p< -1)) return -delta;
    if(abs(before)<=1 && abs(p)<=1) return delta;
    return 2*clamp(p,-1,1)-p-folded;
}
float4 citadelField(float3 local,float footprint,bool shade,out float trap) {
    float3 delta=local*renderInfo.z;
    float3 jx=float3(1,0,0),jy=float3(0,1,0),jz=float3(0,0,1),tail=0;
    float derivative=1;
    bool direct=false;
    trap=10;
    [loop] for(int i=0;i<17;i++) {
        float3 ref=orbit[i].xyz,before=parentMeta[i].xyz,p=before+delta;
        if(!direct && (dot(before,before)>64 || dot(delta,delta)>64)) {direct=true;tail=p;}
        float3 q;float k,r2;
        if(direct) {
            p=tail;q=2*clamp(p,-1,1)-p;r2=dot(q,q);k=1/clamp(r2,.25,1);
            tail=q*(fractalParameters.w*k)+fractalParameters.xyz;
        } else {
            delta=float3(foldedOffset(before.x,ref.x,delta.x),foldedOffset(before.y,ref.y,delta.y),foldedOffset(before.z,ref.z,delta.z));
            q=ref+delta;
            float r0=octaves[i].x,denom0=octaves[i].y;
            float change=2*dot(ref,delta)+dot(delta,delta);
            float denominatorChange=clamp(change,.25-r0,1-r0)-clamp(0,.25-r0,1-r0);
            k=1/(denom0+denominatorChange);r2=max(0,r0+change);
            delta=fractalParameters.w*k*(delta-ref*(denominatorChange/denom0));
            tail=parents[i].xyz+delta;
        }
        if(shade) {
            float3 signs=float3(abs(p.x)>1?-1:1,abs(p.y)>1?-1:1,abs(p.z)>1?-1:1);
            signs*=sign(octaves[i].z);
            jx*=signs;jy*=signs;jz*=signs;
            if(r2>.25 && r2<1) {
                jx-=q*(2*dot(q,jx)/r2);jy-=q*(2*dot(q,jy)/r2);jz-=q*(2*dot(q,jz)/r2);
            }
            trap=min(trap,sqrt(r2));
        }
        derivative*=abs(octaves[i].z)*k;
        if(i>=4 && derivative*renderInfo.z*footprint>32) break;
        if(dot(tail,tail)>4096) break;
    }
    float3 normal=shade?normalize(float3(dot(jx,tail),dot(jy,tail),dot(jz,tail))):float3(0,1,0);
    return float4(normal,.45*length(tail)/(derivative*renderInfo.z));
}
float globalDistance(float3 p) {
    float3 z=p;
    float derivative=1;
    [loop] for(int i=0;i<17;i++) {
        z=2*clamp(z,-1,1)-z;
        float r2=dot(z,z),k=1/clamp(r2,.25,1);
        z=z*(fractalParameters.w*k)+fractalParameters.xyz;
        derivative*=abs(fractalParameters.w)*k;
        if(dot(z,z)>4096) break;
    }
    return .45*length(z)/max(derivative,1e-20);
}
float3 globalNormal(float3 p) {
    float h=.00035;
    float3 a=float3(1,-1,-1),b=float3(-1,-1,1),c=float3(-1,1,-1),d=float3(1,1,1);
    return normalize(a*globalDistance(p+a*h)+b*globalDistance(p+b*h)+c*globalDistance(p+c*h)+d*globalDistance(p+d*h));
}
float3 repeatedPoint(float3 p) {
    const float period=8.0;
    float3 cell=floor((p+period*.5)/period);
    float3 q=p-cell*period;
    float3 parity=fmod(abs(cell),2.0);
    q=lerp(q,-q,parity);
    return q;
}
float repeatedDistance(float3 p) {
    float3 z=repeatedPoint(p);float derivative=1;
    [loop] for(int i=0;i<10;i++) {
        z=2*clamp(z,-1,1)-z;
        float r2=dot(z,z),k=1/clamp(r2,.25,1);
        z=z*(fractalParameters.w*k)+fractalParameters.xyz;
        derivative*=abs(fractalParameters.w)*k;
        if(dot(z,z)>4096) break;
    }
    return .45*length(z)/max(derivative,1e-20);
}
float4 field(float3 local,float footprint,bool shade,out float level) {
    [branch] if(counts.w==1) return citadelField(local,footprint,shade,level);
    return vaultField(local,footprint,shade,level);
}
float scene(float3 domain,float footprint) {
    float unused;
    return field(domain,footprint,false,unused).w*(counts.w==1?1:.8);
}
float aoAt(float3 p,float3 domainNormal,float footprint) {
    float occ=0,weight=1;
    [unroll] for(int i=0;i<AO_STEPS;i++) {
        float h=.016+.08*i;
        occ+=(h-scene(p+domainNormal*h,footprint))*weight;
        weight*=.62;
    }
    return clamp(1-3.2*occ,.06,1);
}
float shadowAt(float3 p,float3 domainLight,float footprint) {
    float res=1,t=.025;
    [loop] for(int i=0;i<SHADOW_STEPS;i++) {
        float h=scene(p+domainLight*t,footprint);
        res=min(res,10*max(h,0)/t);
        t+=clamp(h,.025,.35);
        if(t>2.5 || res<.04) break;
    }
    return clamp(res,.08,1);
}
float3 palette(float x) {
    if(counts.w==1) {
        float t=.5+.5*cos(x*6.28318);
        if(counts.z==0) return lerp(float3(.025,.12,.17),float3(.72,.39,.115),smoothstep(.05,.85,t));
        if(counts.z==1) return lerp(float3(.07,.18,.32),float3(.69,.80,.85),t);
        return lerp(float3(.025,.12,.105),float3(.43,.61,.33),t);
    }
    if(counts.z==1) return lerp(float3(.34,.025,.12),float3(1,.61,.13),.5+.5*cos(6.28318*x+float3(0,.65,1.25)));
    if(counts.z==2) {
        float3 blue=lerp(float3(.025,.12,.30),float3(.36,.17,.68),.5+.5*cos(6.28318*x));
        return lerp(blue,float3(.48,.76,.90),pow(.5+.5*sin(6.28318*x+.8),4));
    }
    return lerp(float3(.025,.52,.57),float3(.60,.09,.24),.5+.5*cos(x*6.28318));
}
float3 environment(float3 r) {
    float a=pow(max(dot(r,normalize(float3(-.65,.8,-.3))),0),9);
    float b=pow(max(dot(r,normalize(float3(.7,-.2,.6))),0),14);
    float band=pow(.5+.5*sin(r.y*5+r.z*2),24);
    float strip=pow(max(0,1-abs(r.x*.6+r.y*.8-.22)*5),4);
    return palette(.1)*a*1.3+palette(.56)*b*1.4+float3(.82,.9,1)*band*.85+float3(1,.72,.38)*strip*.8;
}
float4 fractalMain(VertexOut input):SV_Target {
    float2 uv=(input.position.xy*2-renderInfo.xy)/renderInfo.y;
    uv.y=-uv.y;
    float3 rd=normalize(viewRight.xyz*uv.x+viewUp.xyz*uv.y+viewForward.xyz*1.85);
    float3 domainRay=counts.w==1?rd:toLattice(rd);
    float t=0,eps=.0008,footprint=.00005,glow=0;
    bool rootMode=counts.w==1 && renderInfo.z>.03;
    float rayHorizon=max(VIEW_DISTANCE,12.0/max(renderInfo.z,1e-6));
    bool hit=false;
    if(!rootMode) {
        [loop] for(int i=0;i<MARCH_STEPS;i++) {
            footprint=max(.00005,t*1.2/renderInfo.y);
            float d=scene(domainRay*t,footprint);
            eps=max(.00008,t*.52/renderInfo.y);
            glow+=.0045*exp(-d*20-t*.035);
            if(d<eps) {hit=true;break;}
            t+=max(d*.93,.0001);
            if(t>rayHorizon) break;
        }
    }
    bool globalHit=false;float globalT=.5,farGlow=0,farPhase=0;float3 globalPoint=0,globalN=float3(0,1,0);
    if((rootMode || !hit) && counts.w==1) {
        if(rootMode) globalT=.001;
        [loop] for(int i=0;i<128;i++) {
            float3 globalRay=normalize(rootRight.xyz*uv.x+rootUp.xyz*uv.y+rootForward.xyz*1.85);
            float3 gp=rootCamera.xyz+globalRay*globalT;
            float gd=globalDistance(gp);
            float globalEps=rootMode?max(.00035,globalT*.00045):max(.00025,globalT*.00035);
            if(gd<globalEps) {globalHit=true;globalPoint=gp;globalN=globalNormal(gp);break;}
            globalT+=max(min(gd*.8,.5),.00015);
            if(globalT>(rootMode?rayHorizon:96)) break;
        }
    }
    if(!rootMode && !hit && !globalHit && counts.w==1) {
        [loop] for(int i=0;i<96;i++) {
            float repeatT=.8+float(i)*1.35;
            float3 repeatRay=normalize(rootRight.xyz*uv.x+rootUp.xyz*uv.y+rootForward.xyz*1.85);
            float3 rp=rootCamera.xyz+repeatRay*repeatT;
            float rd2=repeatedDistance(rp);
            float distantSignal=exp(-rd2*5.5)*exp(-repeatT*.004)*.012;
            farGlow+=distantSignal;
            farPhase+=dot(repeatedPoint(rp),float3(.16,.31,.24))*distantSignal;
        }
    }
    if(farGlow>1e-5) farPhase/=farGlow;
    farGlow=saturate(farGlow);
    float3 fog=counts.w==1?float3(.026,.060,.092):float3(.004,.012,.026);
    float3 col=counts.w==1
        ?lerp(float3(.006,.012,.024),float3(.028,.075,.12),saturate(.50+uv.y*.34))+environment(rd)*.035
        :fog;
    if(hit) {
        float3 p=domainRay*t;
        float level;
        float3 motif=field(p,footprint,true,level).xyz;
        float3 n=counts.w==1?normalize(motif):fromNormal(motif),eye=-rd;
        #if SHADOW_STEPS > 0
        if(counts.w==1) {
            float h=max(eps*.85,.00015);
            float3 a=float3(1,-1,-1),b=float3(-1,-1,1),c=float3(-1,1,-1),d=float3(1,1,1);
            float3 gradient=a*scene(p+a*h,footprint)+b*scene(p+b*h,footprint)+c*scene(p+c*h,footprint)+d*scene(p+d*h,footprint);
            if(dot(gradient,gradient)>1e-18) n=normalize(gradient);
        }
        #endif
        float3 light=normalize(viewRight.xyz*(-.65)+viewUp.xyz*.85-viewForward.xyz*.5);
        float3 dn=counts.w==1?n:toLattice(n);
        float ao=aoAt(p,dn,footprint);
        float sh=shadowAt(p+dn*eps*3,counts.w==1?light:toLattice(light),footprint);
        float facing=saturate(dot(n,eye)),edge=pow(1-facing,2.5);
        float phase=.18+dot(motif,float3(.16,.31,.24))+level*.09+edge*.3;
        float wave=motif.y*6+motif.x*3+2*sin(motif.z*3+motif.x*2);
        float vein=pow(.5+.5*cos(wave*9),32);
        float enamel=smoothstep(-.3,.55,sin(wave+level*.7));
        float3 material=lerp(float3(.26,.36,.39),palette(phase),.65+.3*enamel);
        col=material*(.035+facing*.16+max(dot(n,light),0)*sh)*ao;
        col+=environment(reflect(rd,n))*(.2+edge*.65)*sqrt(ao);
        col+=lerp(float3(1,1,1),palette(phase+.2),.2)*pow(max(dot(n,normalize(light+eye)),0),90)*sh*1.8;
        col=lerp(col,col*.4+float3(.5,.3,.12)*.35,vein*.5);
        col+=palette(phase+.4)*pow(1-facing,5)*1.4*(.3+.7*ao);
        if(counts.w==1) {
            material=palette(.15+level*.82);
            col=material*(.055+facing*.11+max(dot(n,light),0)*sh*1.65)*ao;
            col+=material*float3(.14,.24,.34)*(.3+.7*saturate(dot(n,viewUp.xyz)))*sqrt(ao);
            col+=float3(.04,.15,.22)*pow(saturate(dot(n,normalize(viewRight.xyz*.8-viewUp.xyz*.2))),2)*sqrt(ao)*.35;
            col+=float3(1,.86,.64)*pow(max(dot(n,normalize(light+eye)),0),36)*sh*.35;
            col+=environment(reflect(rd,n))*.045*sqrt(ao);
            col+=palette(.35)*pow(1-facing,4)*.08;
        }
    }
    if(globalHit) {
        float3 eye=-rd,gn=globalN;
        float3 light=normalize(viewRight.xyz*(-.65)+viewUp.xyz*.85-viewForward.xyz*.5);
        float facing=saturate(dot(gn,eye));
        float diffuse=max(dot(gn,light),0);
        float3 material=palette(.18+dot(gn,float3(.16,.31,.24)));
        col=material*(.08+facing*.18+diffuse*1.15);
        col+=float3(1,.86,.64)*pow(max(dot(gn,normalize(light+eye)),0),42)*.4;
    }
    if(!hit && !globalHit) {
        col+=palette(.22+farPhase)*farGlow*.34+environment(rd)*farGlow*.08;
    }
    col+=palette(.48+rd.y*.15)*glow*.13;
    col*=1.12;
    col=saturate((col*(2.51*col+.03))/(col*(2.43*col+.59)+.14));
    col=pow(col,.4545);
    col*=1-.25*dot(uv,uv)/(1+dot(uv,uv));
    return float4(col,1);
}
Texture2D frameTexture:register(t0);
SamplerState linearSampler:register(s0);
float4 presentMain(VertexOut input):SV_Target {
    uint w,h;frameTexture.GetDimensions(w,h);
    float2 texel=1./float2(w,h);
    float3 c=frameTexture.SampleLevel(linearSampler,input.uv,0).rgb;
    float3 a=frameTexture.SampleLevel(linearSampler,input.uv+float2(texel.x,0),0).rgb;
    float3 b=frameTexture.SampleLevel(linearSampler,input.uv-float2(texel.x,0),0).rgb;
    float3 d=frameTexture.SampleLevel(linearSampler,input.uv+float2(0,texel.y),0).rgb;
    float3 e=frameTexture.SampleLevel(linearSampler,input.uv-float2(0,texel.y),0).rgb;
    float3 lo=min(c,min(min(a,b),min(d,e))),hi=max(c,max(max(a,b),max(d,e)));
    return float4(clamp(c*1.4-(a+b+d+e)*.1,lo,hi),1);
}
