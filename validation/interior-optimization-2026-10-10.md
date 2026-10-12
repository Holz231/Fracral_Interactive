# Interior and corner optimization — 2026-10-10

Native D3D11 Release build on NVIDIA GeForce RTX 4070 SUPER. Work was confined to **Fraktals-Weiter**. The previously installed executable and sources are preserved in `backup-2026-10-09-interior`.

## Reproduction and measurements

The saved camera at zoom 10^27.0635 closely matches the user's dense interior screenshot. Its complete reference orbit and orientation are preserved in `interior-fixture/last-flight.aurora`. Run `--replay` with that directory as the working directory to repeat the test.

| Test | Previous renderer | Current renderer |
|---|---:|---:|
| Saved interior, 1980 × 1058 | 118.801 ms | 46.128 ms |
| Saved interior, 960 × 540 | 26.110 ms | 10.427 ms |
| 48-view average, 960 × 540 | 5.184 ms | 2.859 ms |
| 1200-frame corner flight, 1932 × 1086, GPU p95 | 24.84 ms in the previous recorded run | 10.264 ms |

The first three rows time the fractal pass, with four warmup frames and twelve timed frames per shader. The corner flight includes upscaling but excludes UI, readback and presentation. The static interior comparison is about **2.58× faster** at the same resolution. It remains too expensive for 60 fps; these results do not claim otherwise. Times vary with GPU load and clocks.

The four additional forward-approach checkpoints at 960 × 540 take 7.51–9.40 ms, previously 18.72–24.12 ms. The saved view and every approach checkpoint have **zero unfinished rays and zero surface/sky classification changes** against the previous renderer. All 48 profile views also have zero unfinished rays.

## Implementation

- Cache the active composed prefix, transformed ray direction, origin and derivative until the ray leaves that prefix's valid radius.
- March in a local linear coordinate with a logarithmic scale. Rebase by exact powers of two instead of computing logarithms and exponentials for every step.
- Use adaptive over-relaxation with an empty-sphere overlap check. On failure, return to a conservative step. Refine the final surface sampling position three times before lighting. Rejected speculative queries do not consume the 8192 accepted-step budget.
- Separate precision-sensitive reference perturbation from the simpler direct iteration loop. Switch only once float orbit-space roundoff projects far below a pixel. Beyond radius eight, finish the affine escape tail without unnecessary reference loads or sphere inversion tests.
- Carry hit, escape and unfinished states explicitly. A linear distance just beyond a bound may round back onto that bound when converted to logarithms; the state must not be reconstructed from that rounded value.
- Preserve elapsed flight time through expensive frames using bounded simulation substeps. Previously, the 50 ms frame clamp discarded time and physically slowed navigation below 20 fps. Long suspensions remain capped at 250 ms.
- Split embedded shader literals to respect MSVC's per-literal size limit.

Resolution caps, geometry depth, far view, shadows, AO and antialiasing settings are retained. No fog, artificial horizon, geometry replacement or automatic resolution reduction was added. Primary rays already cover only the viewport and stop at their first hit; exterior bounding-box and sphere culling remain enabled.

## Image and correctness checks

- Both CPU suites pass, including the new comparison of equal-duration flight at 60 fps and 10 fps, plus elapsed-time and suspension checks.
- `--regression` passes at initial scale, 10^6, 10^24 and 10^80. Snapshot roundtrips remain pixel-identical. Maximum recorded field relative error is 0.006421; maximum mean inter-frame RGB change is 0.007935 on a 0–1 scale.
- `--gaps` passes all nine views, all three quality profiles and comparisons against the uncropped 16384-step reference. No incomplete rays remain.
- `--corners` passes visibility and its 1200-frame fixed-resolution flight.
- `--benchmark` passes quality/palette/resize, manual flight, pause, idle and exact Vaults culling checks.
- `--profile` and the exact saved-camera `--replay` complete successfully. Final native captures were visually inspected.

The new sampling positions are not pixel-identical to the previous conservative marcher. At the saved native view, mean per-pixel maximum RGB difference is 4.444 out of 255, while surface/sky classification is identical. Across all 24,883,200 pixels in the 48-view sweep, 457 previously classified surface pixels become sky and 85 change the other way; these sparse footprint/silhouette differences remain a limitation of finite pixel sampling. The renderer does not promise alias-free infinitely small details.

Alternative wavefront scheduling, persistent compute workers, cone prepasses, deferred shading and additional inner-bound tests were benchmarked and rejected where they were slower or altered the image. They are not in the installed rendering path; exploratory copies remain under `experiments`.

Built executable SHA-256: `5B296F11DFC3424237C4D25E0FA8F65FAC5BD3562B4A0953D3B355CD9DF4E674`.

Detailed data: `interior-fixture/validation/replay/*.json`, `profile/*.json`, `corners/summary.json`, `gaps/depth-*-rays.txt`, `regression/report.json`, and `gpu-benchmark.json`.
