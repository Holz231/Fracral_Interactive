# Aurora — Native Fractal Flight

Double-click **AuroraFractal.exe**. This is a native, 64-bit Windows program using Direct3D 11 on your GPU. It does not use a browser, Electron, Python, a local server, or an internet connection. The executable includes its shaders and C++ runtime; no installer is needed.

The app selects the high-performance hardware adapter. `last-run.txt` records the adapter actually selected. On this machine the validation run selected the **NVIDIA GeForce RTX 4070 SUPER**.

The default **Mandelbox Citadel** is inspired by the architectural cities and nested tunnels in [Deeper Zoom Into Fractal Worlds](https://www.youtube.com/watch?v=bOLTCBTex-s). It has recursive towers, terraces, spherical arches and passages, with warm stone, blue recesses, soft shadows and distance haze. **T** switches to the earlier Iridescent Vaults world.

## Flying

| Control | Action |
|---|---|
| WASD | Move forward, left, back, right; switches to manual flight |
| Q / E | Down / up |
| Left-drag or arrow keys | Look around |
| Hold right mouse | Raw mouse look with the cursor captured |
| Double-click the scene | Toggle continuous mouse look |
| Shift | Fly faster |
| Mouse wheel or − / + | Change flight speed |
| G | Switch guided/manual flight |
| Space | Pause/resume |
| F | Borderless fullscreen |
| P | Cycle Sunstone, Azure, Jade; in Vaults: Opaline, Ember, Nocturne |
| T | Switch Mandelbox Citadel / Iridescent Vaults |
| K | Cycle Performance, Balanced, Ultra |
| R | Return to the starting view |
| H | Hide/show the interface |
| Escape | Release mouse capture; otherwise exit fullscreen or pause |

The buttons offer the same common actions. Palette, speed, quality, guided/manual mode and world choice are saved beside the executable in `settings.txt`.

Flight speed follows the nearby surface scale. The view keeps a 4096-unit minimum ray horizon and expands it with the current chart scale at deep zoom, with no distance fog and a longer-lens perspective. Empty space is rendered as a dark clear sky instead of a grey haze, while distant towers and tunnel mouths keep their material color behind nearer folded walls, even after entering a much smaller recursive chart. As openings get smaller, the coordinate system is rescaled and the camera orientation follows the fractal's folds. You can enter the enlarged detail and fly back out. The Citadel guide probes paths into the structure so it keeps exploring detail. Like any finite program, this is an effectively endless experience, not a claim of mathematically unlimited memory or precision.

Citadel uses a Mandelbox Julia iteration: box reflection, sphere inversion, scale 2.8 and constant (1.4, 1.4, 0.7). It evaluates up to 17 iterations per local chart. Reversible chart changes keep navigation near ordinary coordinate magnitudes and renew the detail budget. The renderer uses a double precision reference orbit, small GPU offsets and a direct evaluation fallback when a ray diverges from the reference. Vaults uses a separate hierarchy of spherical cavities with preserved parent charts.

## Performance

- Fullscreen triangle and GPU distance-field ray marching; no mesh generation or downloads.
- Exact bounds skip finer cavity octaves in Vaults; escape and pixel-footprint bounds limit Citadel iterations.
- Analytic normals in Performance; pixel-sized normal sampling smooths Citadel lighting in Balanced and Ultra. Reference orbits and octave factors are precomputed on the CPU.
- Three separately compiled quality shaders (160/224/320 ray steps), plus GPU timestamp driven resolution adjustment and a lightweight sharpening/upscaling pass.
- Double precision CPU navigation and camera-relative GPU coordinates.
- No repeated rendering while paused or stationary in manual mode. Rendering and flight suspend when minimized or unfocused.
- V-sync and one queued frame keep presentation smooth and input responsive.

The quality choice sets the ray/lighting budget and maximum pixel budget. Adaptive resolution changes image resolution to fit GPU load; it does not cap how deeply you can explore. The FPS display measures presented frames, while `ms GPU` measures the fractal render and upscaling passes separately from v-sync and interface drawing.

## Source and validation

- `src/world.h`: double precision fractal, collision distances and reversible scale charts.
- `src/fractal.hlsl`: GPU renderer and upscaler.
- `src/renderer.cpp`: Direct3D device, GPU selection, asynchronous timings and image validation.
- `src/main.cpp`: native Win32 window, Direct2D interface, raw mouse input and flight controls.
- `tests/world_tests.cpp`: reference distance comparisons, scale continuity and sustained flight tests.

Rebuild using Visual Studio 2022 C++ tools, the Windows SDK and CMake:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The build script compiles Release, runs the CPU validation, and places the executable in this folder. Source changes to the shader are embedded at build time.

Run native GPU validation from this folder:

```powershell
Start-Process .\AuroraFractal.exe -ArgumentList '--benchmark' -WindowStyle Hidden -Wait
```

This writes `validation/gpu-benchmark.json` and two rendered PNGs. It times the Citadel starting view and a deep chart at 1280×720 using the actual Balanced and Ultra shaders. A separate Vaults comparison checks exact octave culling disabled/enabled at identical resolution and ray/lighting budgets. Results are GPU pass times, not whole-application FPS or a comparison against a browser. The test also exercises all quality shaders, palettes, world switching, resize, manual movement, pause and idle behavior.

On the RTX 4070 SUPER, the measured Citadel fractal pass took **1.11–10.64 ms in Balanced** and **1.34–12.77 ms in Ultra** for the wide start view and a deep chart at 1280×720, excluding upscaling, interface drawing and v-sync. Other views and larger resolutions can cost more; adaptive resolution responds to GPU load.

`validation/cpu-validation.json` records ten simulated minutes in each world, 1,200 Citadel chart/geometry/orientation checks, reverse flight out of 17 deep charts, and the Vaults reference distance comparisons. Citadel reached 91 scale changes and a maximum recorded zoom of 10^45.15. `--gallery` additionally saves several viewpoints and guided-flight captures after 20, 60 and 180 simulated seconds. Hardware clocks and background GPU work can change timings. The Windows app itself has no dependency on the test programs or source files.
