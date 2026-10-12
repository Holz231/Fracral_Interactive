# Remaining stutter investigation — 2026-10-10

Work was confined to `Fraktals-Weiter`. The preceding installed build, source,
camera and settings are in `backup-2026-10-10-stutter`; `Fraktals` was not changed.

## Installed changes

- Dedicated Citadel and Vaults shaders remove runtime branches between their
  unrelated distance fields. All three quality profiles retain their pixel
  budgets, lighting, sample counts, geometry and accepted-step limits.
- The three surface refinements use a compact loop. They still evaluate the
  same three positions; no refinement or surface detail is discarded.
- A waitable DXGI swap chain waits before camera/input sampling, with Windows
  messages able to interrupt the wait. V-sync and a one-frame queue remain on.
  Resize retains the required swap-chain flags. The owned event is closed.
- Shader bytecode is cached locally using a key covering source, entry, target,
  compiler configuration and every macro. Invalid/missing cache data recompiles.
- Six recent camera records are matched to asynchronous GPU timestamp serials.
  The worst Citadel frame exceeding 16.7 ms is retained in memory and saved to
  `slow-flight.aurora` plus timing metadata when idle or checkpointing. It does
  not write a camera file on every moving frame.

## Matched GPU comparisons

RTX 4070 SUPER. Before/after shaders ran in the same executable and process.
Twelve timed frames follow warmup. These times cover the fractal pass, excluding
UI, upscaling and presentation; they are not claims about screen FPS.

| Case | Resolution | Before | After | Image difference |
|---|---:|---:|---:|---:|
| Latest saved view, zoom 10^32.85 | 1980×1058 | 10.6882 ms | 10.2680 ms | 0 |
| Dense interior, zoom 10^27.06 | 1980×1058 | 46.7109 ms | 44.5232 ms | 0 |
| 48 varied views, mean | 960×540 | 2.85025 ms | 2.73676 ms | 0 in every view |
| 48 varied views, maximum | 960×540 | 5.09030 ms | 4.91537 ms | 0 in every view |

All 48 comparisons and both saved camera replays had zero unresolved rays and
zero surface/sky classification changes. Forward replay checkpoints are included
in the fixture reports. The dense interior is still too expensive for 60 fps;
this is an incremental improvement, not a claim that every view is now smooth.

A tested 8×8 conservative cone prepass was rejected: it reduced ray queries but
did not consistently improve total GPU time and changed sampling positions.
Its source and results are retained under `experiments/tile8`; it is not shipped.

## Validation

- Release build and both CTest geometry/flight tests passed.
- `--regression`: CPU/GPU field, motion, coordinate units and snapshot roundtrips
  passed at zoom 1, 10^6, 10^24 and 10^80.
- `--gaps`: all corridor/quality visibility checks passed.
- `--corners`: 1200 frames with a fixed 1932×1086 render target; GPU p95
  9.98086 ms, zero unfinished pixels, resolution unchanged. This includes
  upscaling but excludes UI/presentation.
- `--profile`: all 48 views were pixel-identical to the preceding renderer.
- `--benchmark`: all quality shaders, worlds, resize, palettes, manual controls,
  pause and idle checks passed; Vaults culling remained pixel-identical.
- `--frame-profile`: matched GPU/camera capture was saved and loaded back with
  the same coordinate scale and orientation. In the hidden diagnostic window,
  final frame-loop mean was 16.671 ms and p95 17.459 ms; mean Present CPU blocking
  was 0.157 ms versus 16.286 ms for the legacy queue. Waiting moved before input
  sampling; it was not eliminated. This test does not measure visible delivery
  times or end-to-end input latency.

Final executable SHA-256:
`33C0B8521F9EB93758F59FA0AA3F308DDB013D86B02E9AF30BE80DD68CB41388`.

Primary reference for frame-event scheduling:
https://learn.microsoft.com/en-us/windows/uwp/gaming/reduce-latency-with-dxgi-1-3-swap-chains
