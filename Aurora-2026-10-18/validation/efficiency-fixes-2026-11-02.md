# Rendering efficiency and state fixes — 2026-11-02

This update targets the current `Aurora-2026-10-18` application.

## Changes

- Reuse both temporal history textures when their output dimensions match. Quality
  switches that change only the traced size retain the existing allocations. At
  3840 × 2160 this avoids recreating 126.6 MiB of history textures per switch.
- Invalidate history on palette and quality changes, including Balanced/Ultra
  switches at window sizes where their render dimensions match. The first frame
  uses the new surface colours and lighting without blending the old profile.
- Reset resolution-control samples on quality/size changes. Set the resume timing
  boundary before collecting asynchronous results, so a stale sample cannot reduce
  the resumed view's resolution.
- Render stationary views at the full selected profile resolution. Ultra's bounded
  startup scale remains pending while paused and applies when flight resumes in 4K.
- Count completed accumulation frames. Mouse-only camera changes and restarted
  temporal history receive a fresh 48-frame accumulation; Vaults, legacy tracing,
  and disabled temporal antialiasing go idle without those extra frames.

The efficiency gains concern texture allocation and unnecessary idle rendering.
These checks do not establish an improvement in sustained flight FPS.

## Verification

Windows Release build, MSVC 19.44, NVIDIA GeForce RTX 4070 SUPER:

- CTest: **4/4 passed** (`citadel_continuity`, `fractal_geometry`,
  `frame_settling`, `renderer_state`). The new renderer test uses a real D3D11 device
  in a hidden window. It exercises palette changes, equal-size quality changes,
  render-size changes with history reuse, stale timing samples, full-resolution
  stills, resize, and paused-to-flight Ultra 4K startup.
- `--benchmark`: passed all quality, resize, controller, pause and idle checks;
  Vaults culling comparison had zero changed pixels.
- `--regression`: passed the four zoom checkpoints through 10^80 and snapshot
  roundtrips.
- `--field-regression` using `corner.aurora`: passed 24,576 CPU/GPU samples over
  48 poses; maximum tolerance ratio **0.544497** (limit 1).
- Before/after `--bench-views`, Balanced, 1980 × 1058, 16 measured frames per view:
  **14/14 PNGs identical by SHA-256**, zero unfinished pixels in every view.
  This comparison uses the diagnostic default with temporal antialiasing off;
  the temporal transition behaviour is covered by `renderer_state`.

Raw checks, image comparisons and the previous executable are retained under
`build/validation/efficiency-fixes/`. Existing finite-precision and legacy
comparison limits described in the main README still apply.

## Reproduce

From the repository root:

```powershell
cmake -S Aurora-2026-10-18/Source -B Aurora-2026-10-18/build -G "Visual Studio 17 2022" -A x64
cmake --build Aurora-2026-10-18/build --config Release --parallel 2
ctest --test-dir Aurora-2026-10-18/build -C Release --output-on-failure
```

The `renderer_state` test requires a hardware D3D11 adapter. Use `-LE gpu` to run
only the three CPU tests on machines without one.
