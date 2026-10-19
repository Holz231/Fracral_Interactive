# Native acceleration preview — 17 October 2026

This is a separate preview in `Preview-2026-10-17`. The root executable and shader, and the sibling `Fraktals` project, have not been replaced. The preview includes a source snapshot and keeps its own settings, saved flight and slow-frame captures.

## Result and scope

On the RTX 4070 SUPER, the most expensive saved view improved from **30.624 to 16.743 ms** for the GPU fractal rendering pass at **1980 × 1058, Balanced**. This is a 45.3% reduction. It excludes UI, presentation and display timing. The production baseline is the previous compacted renderer's `after_ms`, not the much slower monolithic diagnostic shader's `before_ms`.

| Saved view | Installed GPU ms | Preview GPU ms |
|---|---:|---:|
| slow-69ms | 30.624 | 16.743 |
| slow-41ms | 26.314 | 15.005 |
| slow-45ms | 18.378 | 11.182 |
| slow-384ms | 17.911 | 10.689 |
| interior | 15.500 | 10.659 |
| stutter | 6.487 | 5.539 |
| slow-start-56ms | 2.984 | 2.736 |

The fixture names describe historical captures, not today's baseline. The hardest view was rechecked after the final interval-boundary rounding change; the other table entries precede that small conservative change.

The final `startup-warm` 600-frame forward/reverse flight test kept resolution fixed. After the first 30 frames, its 570 frame intervals averaged **59.982 FPS**, with **16.937 ms p95**, **17.111 ms maximum**, and **zero intervals above 25 ms**. Across all 600 frames there was one 33.197 ms interval while the presentation queue initially filled. The reported all-frame average is slightly above 60 because the first two queue submissions complete immediately; it is not a physical display-rate measurement. GPU time averaged 14.153 ms after frame 30, with a 17.605 ms maximum.

This is not a guarantee of stable 60 FPS in every possible view. One earlier run of the same warmup build averaged only 34 FPS, with GPU times roughly doubled. The same executable then reproduced the faster result, and a paired warmup-on/off check did not reproduce the slowdown. The cause of that run remains unresolved. It is retained in `experiments/cone-segments-native/startup-comparison.json`, rather than discarded. GPU clock/power samples accompany subsequent runs.

## What changed

- A 16 → 8 → 4 pixel cone hierarchy shares conservative empty-space traversal. Each final pixel still performs its own distance queries, surface refinement and shading. The cone includes the full pixel hit footprint; it does not replace distant surfaces with a low-resolution image.
- Long pending rays use 32 parallel, ordered intervals after continuation batch 8. A later interval is accepted only after earlier intervals have escaped; unresolved earlier work is preserved. Interval ends are rounded outward to prevent gaps during logarithmic coordinate conversion.
- Three presentation buffers and a maximum frame latency of two let the CPU and GPU overlap when a frame slightly exceeds one refresh interval. This trades up to one extra queued frame of input latency for smoother pacing. Diagnostic `AURORA_FRAME_QUEUE=1` retains the previous queue size. [Microsoft's DXGI guidance](https://learn.microsoft.com/en-us/windows/uwp/gaming/reduce-latency-with-dxgi-1-3-swap-chains) describes this tradeoff.
- Eight completed startup renders prepare the active shader path before the interactive window is shown. Preparation measured 227–246 ms in the successful warmed runs. This moves actual GPU/driver preparation into startup, rather than merely excluding it from the FPS log. `AURORA_SKIP_WARMUP=1` exists only for comparison.
- Startup event polling now reports failed GPU completion queries as errors.

Resolution, lighting settings, fractal detail, the 8192-step ray budget, world bounds, fog behavior and camera movement have not been reduced. The acceleration applies to Citadel Performance/Balanced. Ultra retains its original two-sample rendering path.

## Validation and remaining image differences

- CTest: **2/2 passed** (geometry and continuity).
- Native `--benchmark`: **exit 0**; deep flight, resizing, all quality shaders/palettes, movement/pause/idle and world switching exercised. Vault culling comparison remained pixel-identical.
- Independent double-precision checks of 800,000 randomized cone corners found no violation of the proposed empty-ball bound. This assumes the underlying fractal distance estimate is conservative; it does not prove that estimate mathematically.
- Across all seven saved views, **no cached cone start was beyond a baseline surface hit**. The initial 1,969 selected CPU ray checks also found no cached start beyond the CPU's first hit.
- The strict Citadel image/depth comparison **does not pass**. It has not been weakened. Changing the march start and interval sampling changes some grazing silhouette hits and shading. The hardest view had no hit-to-sky changes, zero unfinished rays versus 603 before, mean maximum-channel difference 0.944/255, and 13,257 pixels with a channel difference over 16 (about 0.63%).
- Explicitly auditing every lost/gained silhouette pixel in two other fixtures found 31 and 44 old hits becoming sky. The independent CPU tracer found hits for 24 and 41 of those rays. Conversely, 39 and 37 old sky rays became hits, of which the CPU found hits for 34 and 32. None of those cached starts crossed the CPU's first hit. These residual sampling differences are real and remain unresolved; they are why this is a preview rather than a silent replacement.
- A 24-pose small forward-motion comparison was similar, not better in every metric: mean maximum-channel temporal difference 0.2007 versus 0.1987 for the old path; about 2,201 versus 2,144 pixels per frame changed by over 16 levels. This does not establish flicker-free motion for all paths.

## Reproduction and evidence

Primary implementation generators: `cone-pyramid-experiment.py`, `cone-segments-experiment.py`, `cone-pyramid-native-experiment.py`, `cone-segments-native-experiment.py`. The native experiment source is in `experiments/cone-segments-native/src`; its exact packaged snapshot is also under the preview's `Source` folder.

Key reports beneath `validation`:

- `experiments/cone-segments-native/final-flight/validation/replay/saved-native.json`: final hardest-view rendering comparison. Its strict replay intentionally exits with failure on the recorded image/depth changes.
- `experiments/cone-segments-native/startup-comparison.json`: complete warmup tests, including the slow outlier.
- `experiments/cone-segments-native/startup-warm/validation/frame-profile/flight.csv`: final 600-frame test.
- `experiments/cone-segments-native/frame-queue-comparison.json`: presentation queue comparisons.
- `experiments/cone-segments-native/release-smoke/validation/gpu-benchmark.json`: final native smoke test.
- `experiments/cone-segments-32-0.05-geometric-ball-stop1.1/audits`: cone starts, independent CPU checks and `edge-summary.json`. These probe captures precede the final outward interval rounding; they are not represented as final-build pixel-equivalence tests.
- `validate-cone-math.py`, `audit-cones.py`, `geometry-audit`: independent audit code. `audit-cones.py` now explicitly includes every lost/gained silhouette pixel instead of sampling only hit-to-hit rays.

Installed version hashes, verified unchanged:

```text
AuroraFractal.exe D0298511DDAC9E605458A30770A53350A3917FFE8480340CF949153BD17E4C55
src/fractal.hlsl B95CF4B61F31110DF13212919889BE53DAA221EBE65161394CB5AD630D9C541B
```

Further release work remains: resolve the silhouette sampling differences and explain/reproduce the doubled-GPU-time outlier, then validate longer routes with actual presentation timing. Do not infer a global 60 FPS guarantee from this one successful short route.
