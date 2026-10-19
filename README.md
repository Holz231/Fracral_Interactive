# Aurora — Native Fractal Flight

**Current version: Aurora-2026-10-18.** Open **Aurora 60 FPS.lnk** to continue the
latest saved flight. It adds temporal anti-aliasing against the speckle and flicker on
grazing surfaces, a faster exact fold evaluation, bounded grazing rays and a mild
dynamic-resolution safety net. In 600-frame presented flights at 1980 × 1058 Balanced,
all four heavy saved routes ran at 60 FPS with no frame interval above 20 ms (the
2026-10-17 preview: 36.5 and 44.3 FPS on the two slowest). Details, measurements and
limits are in [Aurora-2026-10-18/README.md](Aurora-2026-10-18/README.md) (German).
The preview and root executables below are unchanged.

The native preview now includes the corner precision fix; see
[validation/edge-fix-2026-10-17.md](validation/edge-fix-2026-10-17.md) for reproduction,
image comparisons and remaining frame-time limits.

An accelerated native preview is available in **Preview-2026-10-17**. Open
**Aurora Preview.lnk** to continue from its saved flight. The hardest saved view
improved from 30.6 to 16.7 ms at the same resolution and detail settings; the
tested flight route reached about 60 FPS after startup. This remains a preview
with known silhouette sampling differences and one unexplained slow test run.
See [the full validation report](validation/acceleration-2026-10-17.md). The root
executable remains the previous version; the preview has its own source snapshot,
settings and saved flight.



Double-click **AuroraFractal.exe**. This is a native 64-bit Windows application that renders through Direct3D 11 on your GPU. The executable includes its shaders and C++ runtime. No installer or internet connection is needed. `last-run.txt` identifies the selected hardware adapter.



This development copy is **Fraktals-Weiter**. The version immediately before uniform folds and deferred surface refinement is saved in `backup-2026-10-11-sorted-rays`. The version before GPU ray compaction is saved in `backup-2026-10-10-compaction`. The preceding shader and frame scheduling work is backed up in `backup-2026-10-10-stutter`. The earlier interior-view optimization is backed up in `backup-2026-10-09-interior`, and the prefix/bounds work in `backup-2026-10-09-renderer`. The separate **Fraktals** folder is the original project.



## Flying



| Control | Action |

|---|---|

| WASD | Move forward, left, back, right; select manual flight |

| Q / E | Down / up |

| Left-drag or arrow keys | Look around |

| Hold right mouse | Raw mouse look with the cursor captured |

| Double-click the scene | Toggle continuous mouse look |

| Shift | Fly faster |

| Mouse wheel or − / + | Change flight speed |

| G | Switch guided/manual flight |

| Space | Pause/resume |

| F | Borderless fullscreen |

| P | Cycle palettes |

| T | Switch Mandelbox Citadel / Iridescent Vaults |

| K | Cycle Performance, Balanced, Ultra |

| R | Return to the starting view |

| H | Hide/show the interface |

| F9 | Save the current Citadel camera for an exact performance replay |

| Escape | Release mouse capture, exit fullscreen, or pause |



Palette, speed, quality, flight mode and world choice are saved beside the executable in `settings.txt`. Flight and rendering suspend while the window is minimized or unfocused. A stationary manual view does not continuously use the GPU.



The complete Citadel reference orbit and camera orientation are saved to `last-flight.aurora` when movement stops, you release mouse look, pause, switch away from the window, close it, or press F9. This small local diagnostic file lets a troublesome view be reproduced even at extreme zoom. It does not automatically change the starting view on launch.



The app also retains the slowest Citadel GPU frame above the 16.7 ms budget for 60 fps in each session. Its exact camera is matched to the asynchronous GPU timestamp using a six-frame history. On stopping or checkpointing, it writes `slow-flight.aurora` and `slow-flight.json` beside the executable. The JSON records whether the matched frame used compaction. Capturing these frames uses memory during flight; file writing waits until a checkpoint or idle. These local files help reproduce a transient slowdown even if the next view is fast again.



Aim into an opening and fly towards it: smaller features grow into passages. Speed follows the local surface scale, and manual flight speeds up along open corridors. Each movement is subdivided using the same fractal distance calculation as rendering. You can reverse direction to fly back out. Flying straight at a solid wall reveals its finer detail; it does not pass through that wall.



Expensive frames preserve elapsed flight time using simulation steps no longer than 1/60 second. The former 50 ms frame clamp made flight physically slow down below 20 fps. Long interruptions are capped at 250 ms to avoid a large jump on resuming.



## Geometry and image stability



The Citadel is a fixed Mandelbox Julia set: box reflection, sphere inversion, scale 2.8, constant (1.4, 1.4, 0.7). A camera reference orbit is incrementally updated in double precision. Small offsets are propagated through the orbit, retaining movement at magnifications beyond ordinary world-coordinate precision. Camera orientation stays in the original world frame. Moving closer never swaps in a different Julia set.



The near and far view use that same geometry. Ray travel uses a local linear coordinate with a logarithmic power-of-two scale, spanning tiny nearby detail through the original outer structure. There is no fog, tiled horizon or separate background fractal. Empty space outside the fractal is clear sky. CPU navigation and GPU rendering share the reference orbit, fold rules, escape radius and distance estimate.



Materials use broad surface orientation and ambient occlusion instead of iteration-dependent colour traps. Pixel-sized normal sampling and softer specular highlights reduce shimmer. A gentle edge filter replaces the former sharpening pass. Ultra additionally traces two subpixel samples. Extremely fine silhouettes can still alias at finite screen resolution.



The implementation has a finite 384-iteration reference budget. Automated tests exercise magnification beyond **10^85** and the return flight to the original scale. At the precision limit, an unsafe forward step is rejected and you can still back away. This is deep exploration, not a claim of mathematically unlimited precision. The earlier Vaults world retains its separate spherical-cavity hierarchy.



## Performance



- GPU ray marching from a fullscreen triangle, without generated meshes.

- Primary rays cover only the visible viewport and stop at the first surface. There is no offscreen mesh population to frustum-cull or hidden triangle batch to draw. Long traces along visible corners and interior passages need separate acceleration.

- Performance and Balanced trace Citadel rays in GPU batches: 64 accepted steps first, then 256-step continuations, with a final batch completing the unchanged 8192-step budget. Between batches, unfinished rays are packed and sorted into 128 buckets by their cached prefix depth. Similar field evaluations run together; long rays cannot hold up already completed pixels. Lighting follows traversal. The GPU builds indirect dispatch arguments without CPU readback. Queues, bucket storage and shaders are prepared before flight.

- This path runs from the first Citadel frame in Performance and Balanced. The previous 18 ms activation threshold required rendering an expensive single-pass frame before enabling acceleration; that delay and the subsequent path switching are removed. Easy views pay a small queue overhead. Ultra retains its original two-sample shader and Vaults its original renderer. Both remain available at their unchanged quality settings.

- Each primary ray caches its current prefix, transformed direction and derivative. Local linear travel replaces per-step logarithms and exponentials; power-of-two rebasing preserves the far range. Verified over-relaxed steps can advance farther through empty space. When the empty spheres do not overlap, tracing returns to a conservative step. Three local refinements stabilize the surface sampling position before lighting. Rejected speculative queries do not consume the accepted-step budget.

- Reference perturbation and direct folds have separate loops. The precision-sensitive subtraction is retained until float roundoff projects far below a pixel. Once the orbit is outside radius eight, only affine folds remain before escape; these use a short unrolled tail. Geometry iterations, lighting samples, antialiasing and render resolution are retained.

- Within a conservative branch-valid radius, an entire prefix of box reflections and sphere inversions is evaluated as one exact Möbius transformation. The derivative is transformed too, preserving the distance estimate. This replaces the former linear approximation with a much larger valid region and avoids repeatedly evaluating the same folds for every ray step, normal and lighting sample. Rays outside that radius continue through the original orbit.

- A tight analytic box skips empty exterior rays and ends rays as they leave the fractal. Its planes are recovered from the deepest matching affine part of the reference orbit, then stored as signed logarithmic offsets. This keeps the original outer box accurate below world-coordinate precision: a fixed world-space padding must not expand into a vast empty interval at extreme zoom. A bounding sphere also skips the exterior entry interval; escape checks stop completed fractal iterations.

- Separately compiled Performance, Balanced and Ultra shaders control lighting, antialiasing and pixel budgets. Every quality level permits up to 8192 accepted tracing steps, plus any rejected speculation, with immediate exit when a ray reaches a surface or leaves the fractal bounds. Narrow corridors can therefore resolve their distant walls without the previous 160 / 224 / 320-step cutoff. Completion is tracked explicitly so rounding a distance back to logarithmic units cannot misclassify an escaped ray as unfinished.

- Rendering resolution stays fixed for the selected window size and quality profile. Performance, Balanced and Ultra retain their respective 1.0, 2.1 and 5.0 million pixel caps, up to the window's native resolution. There is no automatic emergency reduction to 480 pixels. GPU timestamps measure cost without changing image quality.

- Each world has dedicated quality shaders, eliminating the other world's field evaluation branches. The three surface refinements execute in one compact loop instead of three copies of the field evaluator. The 48-view comparison and all four saved problem views remain pixel-identical to the preceding renderer.

- A DXGI frame-latency event schedules input sampling and simulation before each new frame. Message-aware waiting keeps input and window events responsive instead of blocking them behind Present. V-sync and the one-frame queue limit remain enabled. This improves input scheduling; it does not replace the need to reduce GPU rendering cost.

- Compiled shaders are cached in `%LOCALAPPDATA%/AuroraFractal/ShaderCache`, keyed by complete source, compiler configuration, entry point, target and macros. Missing or invalid bytecode is recompiled. Quality and world variants are prepared at startup, so switching worlds does not compile during flight.



The field evaluator now uses a uniform fold loop instead of a nested escape-tail loop. Surface-hit bisection runs in its own GPU pass using the original bracket, reference depth and derivative. All three precision queries remain; each supported pixel is still traced and shaded at the same resolution. This adds a 16-byte refinement record per render pixel (about 32 MiB at the Balanced cap).

Measured results and remaining worst-case limits are documented in [the uniform-fold report](validation/uniform-folds-2026-10-11.md). The preceding batching change is described in [the sorted-ray report](validation/sorted-rays-2026-10-11.md). The worst saved corridor still exceeds the 16.7 ms GPU budget; stable 60 fps in every view has not been achieved.



The HUD reports actual GPU render time, including upscaling. `validation/gpu-benchmark.json` records measured fractal-pass times at 1280×720 on the selected adapter, excluding upscaling, UI and v-sync. Actual cost depends on the view, resolution and GPU load. Ultra spends more GPU time on antialiasing and lighting.



## Build and validation



Requires Visual Studio 2022 C++ tools, the Windows SDK and CMake:



```powershell

powershell -ExecutionPolicy Bypass -File .\build.ps1

```



Close this copy of Aurora before replacing its executable. The script builds into **build-copy**, runs both CPU test programs, then copies the Release executable here. The old `build` directory came from the original project and must not be used for this copy. Shaders are embedded automatically when rebuilt.



The native GPU checks run without opening an interactive window:



```powershell

Start-Process .\AuroraFractal.exe -ArgumentList '--benchmark' -WindowStyle Hidden -Wait

Start-Process .\AuroraFractal.exe -ArgumentList '--regression' -WindowStyle Hidden -Wait

Start-Process .\AuroraFractal.exe -ArgumentList '--gaps' -WindowStyle Hidden -Wait

Start-Process .\AuroraFractal.exe -ArgumentList '--corners' -WindowStyle Hidden -Wait

Start-Process .\AuroraFractal.exe -ArgumentList '--profile' -WindowStyle Hidden -Wait

Start-Process .\AuroraFractal.exe -ArgumentList '--replay' -WindowStyle Hidden -Wait

```



Run them from this folder. `--benchmark` measures the starting and deep views, checks every quality shader and palette, resize, controller behaviour, pause, idle and exact Vaults culling. `--regression` checks CPU/GPU distance agreement and consecutive rendered frames at zoom levels 1, 10^6, 10^24 and 10^80. It also verifies that a change of coordinate units preserves the image, and captures the exterior view. `--gaps` tests three corridor directions at zoom levels 10^6.7, 10^24 and 10^80 at 1536×820: it distinguishes surface hits, escaped rays and unfinished rays, compares with an uncropped 16384-step reference, and rejects unfinished pixels in all three quality profiles. It also compares the single-pass and compacted Performance/Balanced images; Ultra is checked using its retained original renderer. A separate CPU slab test and GPU depth readback identify former cone-tolerance hits outside the actual bounding box.



`--corners` samples three approaches at fixed 960×540 resolution, compares two difficult corner views against the uncropped reference, and runs 1200 consecutive flight frames in a 4K window at a constant Balanced rendering resolution. It rejects unresolved rays and any resolution change. Its GPU p95 statistic excludes the first 60 settling frames and includes upscaling; it excludes readback, UI and presentation time and is not a screen FPS measurement. Reports and PNGs are written under `validation`.



`--profile` compares the single-pass Citadel shader with the complete GPU compaction and lighting pipeline in 48 views at 960×540, with matching lighting and resolution. Measurements warm up each path and retire GPU work one frame at a time, so pathological views do not form one long watchdog-sized batch. Reports include the original single-pass time (`before_ms`), the historical three-stage compaction time (`three_pass_ms`; older reports called it `installed_ms`), the current renderer time (`after_ms`), four pass intervals (the last includes refinement and lighting), pixel differences, unfinished rays, single-pass query/iteration counts and surface/sky classification changes. Historical/current compaction timings alternate order over three rounds. These in-process historical timings are not the immediately preceding sorted build; the report separately compares that saved executable. `--replay` uses `last-flight.aurora` in the current folder, tests both 960×540 and 1980×1058, and samples a two-second forward approach. Add `--native-only` for just the 1980x1058 saved view. The new worst-case fixture already has 603 unfinished pixels in both preceding paths at 1980×1058; this optimization preserves them and does not claim to solve that separate finite-budget limit. The standard corridor checks still require zero unfinished pixels. The reported `mean_channel_error` is the mean of each pixel's largest RGB-channel difference on a 0–255 scale. The compaction comparison requires identical colour, identical hit/escape/unfinished classification and exact hit depths; motion and visibility also have separate regression checks. `--hunt` searches additional deterministic flight paths for costly views. GPU tools run sequentially so they do not compete for the GPU. Snapshot roundtrip rendering remains pixel-identical at all four zoom checkpoints.



`--frame-profile` replays the saved camera at 1980×1058 and records CPU submission, overlay, Present, frame-event wait and GPU times in `validation/frame-profile`. Add `--legacy-pacing` to compare the old queue. Add `--trace-legacy` to force single-pass tracing or `--trace-compact` to force compaction for supported Citadel profiles. These flags never change quality. `--frame-profile --exercise-switch` retains its historical name: it now changes from a heavy view to a light view and checks that every frame, including the first, stays on the compacted path at constant resolution. This also validates the automatic slow-frame snapshot. `--flight-profile` runs 600 frames from the saved camera, flying forwards for 300 fixed 1/60-second simulation steps and backwards for 300, while retaining the same resolution and recording `flight.csv`. Hidden-window timings are diagnostic and do not establish onscreen frame delivery or input latency.



CPU tests compare the field with an independent world-space evaluator, check escape outside all six bounding planes, test stationary surfaces during camera recentering, deep zoom and reverse flight, boosted approaches to nine target surfaces, diagonal speed and three simulated minutes of guided Citadel flight. They compare the composed displacement and derivative with individually evaluated folds in 34,797 cases, including deep orbits. Analytic corner orbits verify recovered plane offsets down to 10^-120, where the root camera alone cannot represent the displacement. Vaults has separate distance, continuity and ten-minute flight tests. `ctest --test-dir build-copy -C Release --output-on-failure` runs these tests; geometry reports are written under `build-copy/validation`.



Source files:



- `src/citadel.h`: reference orbit, stable perturbation, precision and field queries.

- `src/world.h`: navigation, speed, guided flight and the Vaults hierarchy.

- `src/fractal.hlsl`: logarithmic ray marcher, lighting, antialiasing and field probes.

- `src/renderer.cpp`: D3D11 device, GPU timings, fixed quality budgets and image readback.

- `src/main.cpp`: Win32 UI, input and native regression runs.

- `src/flight_time.h`: bounded simulation substeps that preserve elapsed flight time.

- `tests/citadel_tests.cpp`, `tests/world_tests.cpp`: geometry, composed transformations and movement tests.



### Detailed batch profiling (2026-10-11)

`--replay --native-only --batch-details` adds `validation/replay/batches.csv` with
per-batch GPU times and surviving ray counts. Profiling readbacks are disabled in
normal flight. Sixteen further optimization experiments did not establish a
reliable gain, so the established renderer and its image quality are retained.
The difficult corridor still takes about 30–31 ms; stable 60 fps is not yet met.
See [the measurements and rejected experiments](validation/scheduling-2026-10-11.md).
