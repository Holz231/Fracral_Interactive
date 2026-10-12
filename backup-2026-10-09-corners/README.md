# Aurora — Native Fractal Flight

Double-click **AuroraFractal.exe**. This is a native 64-bit Windows application that renders through Direct3D 11 on your GPU. The executable includes its shaders and C++ runtime. No installer or internet connection is needed. `last-run.txt` identifies the selected hardware adapter.

This development copy is **Fraktals-Weiter**. The earlier version is saved in `backup-2026-10-08`. The separate **Fraktals** folder is the original project.

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
| Escape | Release mouse capture, exit fullscreen, or pause |

Palette, speed, quality, flight mode and world choice are saved beside the executable in `settings.txt`. Flight and rendering suspend while the window is minimized or unfocused. A stationary manual view does not continuously use the GPU.

Aim into an opening and fly towards it: smaller features grow into passages. Speed follows the local surface scale, and manual flight speeds up along open corridors. Each movement is subdivided using the same fractal distance calculation as rendering. You can reverse direction to fly back out. Flying straight at a solid wall reveals its finer detail; it does not pass through that wall.

## Geometry and image stability

The Citadel is a fixed Mandelbox Julia set: box reflection, sphere inversion, scale 2.8, constant (1.4, 1.4, 0.7). A camera reference orbit is incrementally updated in double precision. Small offsets are propagated through the orbit, retaining movement at magnifications beyond ordinary world-coordinate precision. Camera orientation stays in the original world frame. Moving closer never swaps in a different Julia set.

The near and far view use that same geometry. Logarithmic ray travel can trace from tiny nearby detail to the original outer structure. There is no fog, tiled horizon or separate background fractal. Empty space outside the fractal is clear sky. CPU navigation and GPU rendering share the reference orbit, fold rules, escape radius and distance estimate.

Materials use broad surface orientation and ambient occlusion instead of iteration-dependent colour traps. Pixel-sized normal sampling and softer specular highlights reduce shimmer. A gentle edge filter replaces the former sharpening pass. Ultra additionally traces two subpixel samples. Extremely fine silhouettes can still alias at finite screen resolution.

The implementation has a finite 384-iteration reference budget. Automated tests exercise magnification beyond **10^85** and the return flight to the original scale. At the precision limit, an unsafe forward step is rejected and you can still back away. This is deep exploration, not a claim of mathematically unlimited precision. The earlier Vaults world retains its separate spherical-cavity hierarchy.

## Performance

- GPU ray marching from a fullscreen triangle, without generated meshes.
- Conservative bounds skip tiny linear portions of the reference orbit; distant rays continue through the original fractal.
- A bounding sphere skips empty exterior rays; escape checks stop completed fractal iterations.
- Separately compiled Performance, Balanced and Ultra shaders control lighting, antialiasing and pixel budgets. Every quality level permits up to 8192 tracing steps, with immediate exit when a ray reaches a surface or leaves the fractal bounds. Narrow corridors can therefore resolve their distant walls without the previous 160 / 224 / 320-step cutoff.
- GPU timestamps control adaptive rendering resolution, down to one quarter of the window dimensions in expensive views. Quality changes the rendering budget, not the world geometry. Rendering complete distant walls can cost more than the former truncated view.
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
```

Run them from this folder. `--benchmark` measures the starting and deep views, checks every quality shader and palette, resize, controller behaviour, pause, idle and exact Vaults culling. `--regression` checks CPU/GPU distance agreement and consecutive rendered frames at zoom levels 1, 10^6, 10^24 and 10^80. It also verifies that a change of coordinate units preserves the image, and captures the exterior view. `--gaps` tests three corridor directions at zoom levels 10^6.7, 10^24 and 10^80 at 1536×820: it distinguishes surface hits, escaped rays and unfinished rays, compares with a 16384-step reference, and rejects unfinished pixels in all three quality profiles. Reports and PNGs are written under `validation`.

CPU tests compare the new field with an independent world-space evaluator, test stationary surfaces during camera recentering, deep zoom and reverse flight, boosted approaches to nine target surfaces, diagonal speed and three simulated minutes of guided Citadel flight. Vaults has separate distance, continuity and ten-minute flight tests. `ctest --test-dir build-copy -C Release --output-on-failure` runs these tests and writes their reports under `build-copy/validation`.

Source files:

- `src/citadel.h`: reference orbit, stable perturbation, precision and field queries.
- `src/world.h`: navigation, speed, guided flight and the Vaults hierarchy.
- `src/fractal.hlsl`: logarithmic ray marcher, lighting, antialiasing and field probes.
- `src/renderer.cpp`: D3D11 device, GPU timings, adaptive resolution and image readback.
- `src/main.cpp`: Win32 UI, input and native regression runs.
- `tests/citadel_tests.cpp`, `tests/world_tests.cpp`: independent geometry and movement tests.
