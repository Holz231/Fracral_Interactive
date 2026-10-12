# Renderer optimization — 2026-10-09

Hardware: NVIDIA GeForce RTX 4070 SUPER. Native D3D11 Release build.

## Changes

1. Compose branch-valid orbit prefixes as exact Möbius maps, including the distance derivative. Finish the outward escape tail directly.
2. Recover exterior planes from a matching affine orbit prefix. The previous fixed 1e-13 world-space padding became enormous relative to the camera at deep zoom and forced long traces through empty space beside corners.
3. Keep the selected quality profile's resolution fixed. Remove the emergency resolution reduction.

## Measurements

The 48 `--profile` views use the same 960×540 resolution, ray limit and lighting for both shaders, with four warmup frames before timing three frames. Average fractal-pass time: **9.60 ms → 5.17 ms**. The slowest optimized view took 11.26 ms. Average per-pixel maximum RGB difference was **0.0324 of one 8-bit channel level**; the largest scene average was 0.0764. Differences are concentrated at fine silhouettes. All 48 views had zero unfinished rays.

In the 1200-frame corner flight, using constant **1932×1086** rendering in a 4K window, the intermediate composed-prefix build with the old root-space bounds measured **100.95 ms GPU p95**. Recovering the planes from the orbit reduced that to 27.18 ms; the final escape-tail optimization measured **24.84 ms**. Final report: [corners/summary.json](corners/summary.json). It records zero unfinished rays and no resolution changes. These timings include upscaling, exclude UI and presentation, and are not guaranteed screen frame rates.

## Validation

- Both CPU suites pass, including 34,797 composed-prefix comparisons and analytic plane recovery down to 10^-120.
- `--regression` passes at initial scale and zoom 10^6, 10^24 and 10^80; snapshot save/load renders pixel-identically at all checkpoints.
- `--gaps` passes all nine corridor views and all three quality profiles, retaining distant surfaces.
- `--corners` passes the two uncropped-reference comparisons and the complete fixed-resolution flight.
- `--benchmark` passes quality, palette, resize, flight controls, pause/idle and Vaults checks.
- `--replay` successfully reloads and profiles the saved deep camera fixture.

The user's exact screenshot camera was not available as an orbit snapshot. The tests reproduce the same class of deep-zoom exterior-corner problem; they do not establish 60 fps for every possible camera. Future problem views can be saved with F9 to `last-flight.aurora` and replayed exactly.
