# Aurora — Native Fractal Flight

Double-click **AuroraFractal.exe**. This is a native 64-bit Windows application that renders through Direct3D 11 on your GPU. The executable includes its shaders and C++ runtime. No installer or internet connection is needed. `last-run.txt` identifies the selected hardware adapter.

This development copy is **Fraktals-Weiter**. The version before this rendering optimization is saved in `backup-2026-10-09-renderer`. The separate **Fraktals** folder is the original project.

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

Aim into an opening and fly towards it: smaller features grow into passages. Speed follows the local surface scale, and manual flight speeds up along open corridors. Each movement is subdivided using the same fractal distance calculation as rendering. You can reverse direction to fly back out. Flying straight at a solid wall reveals its finer detail; it does not pass through that wall.

## Geometry and image stability

The Citadel is a fixed Mandelbox Julia set: box reflection, sphere inversion, scale 2.8, constant (1.4, 1.4, 0.7). A camera reference orbit is incrementally updated in double precision. Small offsets are propagated through the orbit, retaining movement at magnifications beyond ordinary world-coordinate precision. Camera orientation stays in the original world frame. Moving closer never swaps in a different Julia set.

The near and far view use that same geometry. Logarithmic ray travel can trace from tiny nearby detail to the original outer structure. There is no fog, tiled horizon or separate background fractal. Empty space outside the fractal is clear sky. CPU navigation and GPU rendering share the reference orbit, fold rules, escape radius and distance estimate.

Materials use broad surface orientation and ambient occlusion instead of iteration-dependent colour traps. Pixel-sized normal sampling and softer specular highlights reduce shimmer. A gentle edge filter replaces the former sharpening pass. Ultra additionally traces two subpixel samples. Extremely fine silhouettes can still alias at finite screen resolution.

The implementation has a finite 384-iteration reference budget. Automated tests exercise magnification beyond **10^85** and the return flight to the original scale. At the precision limit, an unsafe forward step is rejected and you can still back away. This is deep exploration, not a claim of mathematically unlimited precision. The earlier Vaults world retains its separate spherical-cavity hierarchy.

## Performance

- GPU ray marching from a fullscreen triangle, without generated meshes.
- Within a conservative branch-valid radius, an entire prefix of box reflections and sphere inversions is evaluated as one exact Möbius transformation. The derivative is transformed too, preserving the distance estimate. This replaces the former linear approximation with a much larger valid region and avoids repeatedly evaluating the same folds for every ray step, normal and lighting sample. Rays outside that radius continue through the original orbit.
- A tight analytic box skips empty exterior rays and ends rays as they leave the fractal. Its planes are recovered from the deepest matching affine part of the reference orbit, then stored as signed logarithmic offsets. This keeps the original outer box accurate below world-coordinate precision: a fixed world-space padding must not expand into a vast empty interval at extreme zoom. A bounding sphere also skips the exterior entry interval; escape checks stop completed fractal iterations.
- Separately compiled Performance, Balanced and Ultra shaders control lighting, antialiasing and pixel budgets. Every quality level permits up to 8192 tracing steps, with immediate exit when a ray reaches a surface or leaves the fractal bounds. Narrow corridors can therefore resolve their distant walls without the previous 160 / 224 / 320-step cutoff.
- Rendering resolution stays fixed for the selected window size and quality profile. Performance, Balanced and Ultra retain their respective 1.0, 2.1 and 5.0 million pixel caps, up to the window's native resolution. There is no automatic emergency reduction to 480 pixels. GPU timestamps measure cost without changing image quality.
- V-sync and one queued frame keep presentation responsive.

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

Run them from this folder. `--benchmark` measures the starting and deep views, checks every quality shader and palette, resize, controller behaviour, pause, idle and exact Vaults culling. `--regression` checks CPU/GPU distance agreement and consecutive rendered frames at zoom levels 1, 10^6, 10^24 and 10^80. It also verifies that a change of coordinate units preserves the image, and captures the exterior view. `--gaps` tests three corridor directions at zoom levels 10^6.7, 10^24 and 10^80 at 1536×820: it distinguishes surface hits, escaped rays and unfinished rays, compares with an uncropped 16384-step reference, and rejects unfinished pixels in all three quality profiles. A separate CPU slab test and GPU depth readback identify former cone-tolerance hits outside the actual bounding box.

`--corners` samples three approaches at fixed 960×540 resolution, compares two difficult corner views against the uncropped reference, and runs 1200 consecutive flight frames in a 4K window at a constant Balanced rendering resolution. It rejects unresolved rays and any resolution change. Its GPU p95 statistic excludes the first 60 settling frames and includes upscaling; it excludes readback, UI and presentation time and is not a screen FPS measurement. Reports and PNGs are written under `validation`.

`--profile` compares the old linear prefix and the composed prefix in 48 views at the same 960×540 resolution, lighting and ray budget. Each measurement warms up the shader before timing; reports include per-pixel differences, unfinished rays and baseline iteration counts. `--replay` runs the same comparison for `last-flight.aurora` in the current folder. `--hunt` searches additional deterministic flight paths for costly views. These developer tools run sequentially so they do not compete for the GPU. The snapshot roundtrip is checked for pixel-identical rendering by `--regression` at all four zoom checkpoints.

CPU tests compare the field with an independent world-space evaluator, check escape outside all six bounding planes, test stationary surfaces during camera recentering, deep zoom and reverse flight, boosted approaches to nine target surfaces, diagonal speed and three simulated minutes of guided Citadel flight. They compare the composed displacement and derivative with individually evaluated folds in 34,797 cases, including deep orbits. Analytic corner orbits verify recovered plane offsets down to 10^-120, where the root camera alone cannot represent the displacement. Vaults has separate distance, continuity and ten-minute flight tests. `ctest --test-dir build-copy -C Release --output-on-failure` runs these tests; geometry reports are written under `build-copy/validation`.

Source files:

- `src/citadel.h`: reference orbit, stable perturbation, precision and field queries.
- `src/world.h`: navigation, speed, guided flight and the Vaults hierarchy.
- `src/fractal.hlsl`: logarithmic ray marcher, lighting, antialiasing and field probes.
- `src/renderer.cpp`: D3D11 device, GPU timings, fixed quality budgets and image readback.
- `src/main.cpp`: Win32 UI, input and native regression runs.
- `tests/citadel_tests.cpp`, `tests/world_tests.cpp`: geometry, composed transformations and movement tests.
