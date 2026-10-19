"""Check float32 cone advances against independent double-precision geometry."""
import numpy as np
rng=np.random.default_rng(170426)
n=200000
h=rng.choice([64,256,540,1058,2160,4320],n).astype(np.float32)
tile=rng.choice([4,8,16],n).astype(np.float32)
uv=rng.uniform([-2,-1],[2,1],(n,2))
center=np.column_stack((uv,np.full(n,1.85)));center/=np.linalg.norm(center,axis=1)[:,None]
angular=np.float32(1.414214)*(tile-1)/(h*np.float32(1.85))
shell=np.float32(.75)/(h*np.float32(1.85));a2=angular*angular
d=((angular+shell)*rng.uniform(1.1,100,n)).astype(np.float32)
disc=(d-shell)*(d-shell)-a2*(1-np.float32(.25)*a2-d*shell)
advance=(np.sqrt(np.maximum(0,disc))-np.float32(.5)*a2-d*shell+shell*shell)/(1-shell*shell)
x=(1+np.float32(.9)*np.maximum(0,advance)).astype(np.float32)
worst=-np.inf
for sx,sy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
    q=uv+np.column_stack((sx*(tile-1)/h,sy*(tile-1)/h))
    ray=np.column_stack((q,np.full(n,1.85)));ray/=np.linalg.norm(ray,axis=1)[:,None]
    distance=np.linalg.norm(x[:,None]*ray-center,axis=1)+shell*x
    residual=distance-d
    worst=max(worst,float(residual.max()))
    if np.any(residual>0):raise AssertionError(f'Unsafe empty cone advance: {worst}')
print(f'Checked {n*4} tile corners, worst clearance residual {worst:.9g}; all advances stay inside the empty ball including the hit shell.')
