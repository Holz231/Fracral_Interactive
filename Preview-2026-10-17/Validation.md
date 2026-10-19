# Corner precision fix — 17 October 2026

The updated `Preview-2026-10-17` corrects the reproduced noisy, dark surface patches
when approaching a junction of edges. The root executable and sibling `Fraktals`
project remain separate. The previous preview executable and source are archived
in `validation/baselines/preview-2026-10-17-0803`.

## Cause and correction

The reference orbit stores a squared radius in double precision. The GPU formerly
rounded that radius to float before subtracting the sphere-fold thresholds, 0.25
and 1. Near a threshold, the small signed difference was lost. At deep zoom that
small difference can represent many camera units. The GPU then selected a
different fold branch from the CPU, changing geometry and producing unstable
surface normals. The cone traversal magnified the bad field into visible blocks.

Both signed threshold distances are now computed in double precision before
conversion to float. They occupy the previously unused `y.w` and `z.w` orbit
components; the constant-buffer size is unchanged. All reference perturbation
paths use those distances. Camera movement, ray budget, visibility, resolution,
lighting and fractal iteration limits are unchanged.

The build also includes the separately tested direct cooperative queue append,
one 32-thread ray per group, and two identical direct folds per loop iteration.
Before the precision correction, those optimizations produced bit-identical
depth/status images in seven saved views.

## Evidence

The reproducer is `edge-report-2026-10-17/slow-capture/last-flight.aurora` and is
included in the source snapshot as `tests/fixtures/edge-sphere.aurora`.

- The captured view's original GPU/CPU field error fell from 210.577 to 0.004323
  using the existing relative-error diagnostic (denominator floor 0.0001).
- A 48-pose forward/reverse micro-movement test checked 24,576 GPU/CPU samples.
  The final bound is `abs(error) <= 0.00002 * abs(expected) + 0.05 * footprint`,
  where `footprint = max(1, length(offset)) / (height * 1.85)` in the probe's
  normalized scale. The corrected maximum error/allowance ratio is **0.219204**;
  the old field fails the same test at **5807.55**. The allowed ratio is 1.
- For transparency, exploratory relative-only (2%) and pixel-only (0.1 pixel)
  checks failed at 0.0304098 and 0.140185 respectively. Those reports are retained.
  The combined bound accommodates float scale rounding for large distances while
  enforcing a small absolute tolerance near zero-distance surfaces. Raw metrics
  remain in the report; this is not a claim of pixel-exact geometry.
- 240 boundary cases cover both sides of both sphere thresholds down to 2^-48.
  The old packing fails this regression; the new packing passes. CTest: **2/2**.
- The 24-frame micro-movement render test reduced accelerated-path pixels with
  a channel change over 16/255 from **16,072 to 2,661 per frame** (83.4%). Mean
  maximum-channel change fell from 0.8128 to 0.2889. These are temporal image
  differences during actual motion, not a guarantee that every changed pixel
  was erroneous.
- Native smoke checks passed: all qualities, palettes, resize, movement, pause,
  idle and world switching. Vault culling remained pixel-identical.
- All eight saved-view comparisons had zero unfinished accelerated rays.
  The strict serial-versus-accelerated image comparison still reports differences
  and exits nonzero; that existing check has not been relaxed. At the corner,
  mean maximum-channel difference fell from 19.388 to 0.812, and pixels over
  16 levels fell from 425,788 to 10,595. Silhouette/sampling differences remain.

## Performance and limits

Native GPU fractal-pass times at 1980 × 1058, Balanced; UI/presentation excluded:

| View | Previous preview ms | Updated preview ms |
|---|---:|---:|
| Reproduced corner | 20.667 | 21.251 |
| slow-69ms | 16.705 | 16.449 |
| slow-41ms | 15.027 | 14.717 |
| slow-45ms | 11.226 | 11.035 |
| slow-384ms | 10.725 | 10.611 |
| interior | 10.670 | 10.569 |
| stutter | 5.550 | 5.492 |
| slow-start-56ms | 2.747 | 3.029 |

The corrected corner renders real surfaces instead of the corrupted patches;
its static GPU time remains above the 16.67 ms budget. This update does **not**
establish stable 60 FPS in every view. The live capture recorded 268.563 ms, but
that large stall did not reproduce in the isolated static measurements.

A 600-frame forward/reverse flight from this corner kept resolution fixed.
After 30 startup frames, it averaged **59.878 FPS**, with **16.930 ms p95**,
**33.429 ms maximum**, and one frame above 25 ms. GPU time averaged 14.493 ms,
maximum 18.389 ms. Further frame-time work remains.

## Reproduction

The source snapshot builds with Visual Studio 2022 and the Windows SDK:

```powershell
cmake -S Source -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

For the GPU field regression, make an isolated working folder, copy
`Source/tests/fixtures/edge-sphere.aurora` there as `last-flight.aurora`, then run
the absolute executable path with `--field-regression` from that folder. The
report is written beneath its `validation` directory. Do not overwrite a user's
saved flight just to run the test.

Primary evidence is under `validation/edge-report-2026-10-17`: variant captures,
the old and new field regressions, `native-comparison/summary.json`, both
`motion` runs, `flight/validation/frame-profile/flight.csv`, and the smoke report.
`native-edge-fixed/src` is the final implementation; `Source` in the preview
contains the exact packaged source.
