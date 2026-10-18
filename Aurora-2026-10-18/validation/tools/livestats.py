"""Summarise a frames.csv written with AURORA_FRAME_LOG."""
import csv, statistics, sys

rows = list(csv.DictReader(open(sys.argv[1])))
frames = [r for r in rows if r['kind'] == 'F']
gpu = [float(r['value_ms']) for r in rows if r['kind'] == 'G']
skip = 30
iv = [float(r['value_ms']) for r in frames[skip:]]
sc = [float(r['scale']) for r in frames[skip:]]
zoom = [float(r['zoom']) for r in frames]
s = sorted(iv)
g = sorted(gpu[skip:])
print(f"frames {len(iv)}  fps {1000 / statistics.mean(iv):.2f}  interval p50 {statistics.median(iv):.2f} p95 {s[int(len(s) * .95)]:.2f} p99 {s[int(len(s) * .99)]:.2f} max {max(iv):.2f}  >20ms {sum(v > 20 for v in iv)} >25ms {sum(v > 25 for v in iv)}")
print(f"gpu samples {len(g)}  p50 {statistics.median(g):.2f} p95 {g[int(len(g) * .95)]:.2f} max {max(g):.2f} >16.7 {sum(v > 16.7 for v in g)}")
print(f"scale p50 {statistics.median(sc):.3f} min {min(sc):.3f}  zoom {zoom[0]:.1f} -> {zoom[-1]:.1f}")
