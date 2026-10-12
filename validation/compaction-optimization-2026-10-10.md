# GPU ray compaction — 2026-10-10

Work was confined to `Fraktals-Weiter`. The previous executable, source,
settings and camera are in `backup-2026-10-10-compaction`. The original
`Fraktals` project was not changed.

## Change

Dense interior and corner views contain a small number of very expensive rays.
In the saved interior view, 9,124 rays require more than 1,000 accepted steps,
while the mean is 83.36. A single shader invocation combines traversal and
lighting, tying up execution groups behind their long-running rays.

Performance and Balanced now have a second Citadel rendering path:

1. Trace each visible pixel for up to 64 accepted steps.
2. Pack unfinished rays into GPU queues; trace another 256 accepted steps.
3. Pack remaining rays and finish their original 8,192-step budget.
4. Shade the resulting hit positions using the existing lighting functions.

Rejected speculative steps still roll back and do not consume the accepted-step
budget. Prefix derivatives and validity limits are carried across dispatches
with their exact rebased float values. Queues are sized for every pixel, not an
assumed percentage of surviving rays. GPU counters generate indirect dispatch
arguments without CPU readback. Buffers and shaders are prepared before flight;
they are not allocated or compiled when a difficult view triggers activation.

Automatic selection uses measured GPU times: enter compaction above 18 ms;
return to single-pass below 7 ms, after at least 60 submitted frames. Measurements
from a different path/world cannot immediately reverse the selection. Easy views
retain the lower overhead of a single pass. The queue/depth storage costs up to
about 208 MiB at Balanced's 2.1-million-pixel cap.

The original field, primary tracing, lighting and two-sample Ultra shader are
unchanged byte-for-byte. There are no changes to resolution caps, detail,
visibility, fog, shading samples, surface refinements or navigation.

## Measured results

NVIDIA GeForce RTX 4070 SUPER. Paired measurements use the same process, camera,
resolution and lighting, warmup followed by 12 timed frames. GPU pass time
excludes presentation, UI and upscaling.

| View | Resolution | Single pass | Compaction | Maximum RGB difference |
|---|---:|---:|---:|---:|
| Dense interior, zoom 10^27.06 | 1980×1058 | 44.0277 ms | 25.5332 ms | 0 |
| Saved faster view, zoom 10^32.85 | 1980×1058 | 10.2557 ms | 10.4039 ms | 0 |
| 48 varied views, mean | 960×540 | 2.74729 ms | 3.12422 ms | 0 in every view |

The dense view uses **42.0% less GPU time**. The faster views illustrate why
compaction is selected only for expensive frames. These forced-path comparisons
are not claims that compaction is faster everywhere, nor that all views reach
60 fps. The dense view remains around 25.5 ms.

`validation/interior-fixture/validation/frame-profile/switching.csv` exercises
180 heavy frames followed by 120 easy frames at fixed 1980×1058. Automatic
selection changes at frames 1 and 181, exactly twice. Mean heavy GPU time after
settling is 25.5985 ms; mean CPU submission is 0.0263 ms. The light segment returns
to single-pass and averages 1.7105 ms GPU time. Hidden-window timing does not
measure visible delivery latency. The matching slow-frame camera roundtrip passes.

## Quality scope and rejected experiments

Ultra keeps its original renderer, including both subpixel samples. The tested
split Ultra path produced tiny numerical differences at a few pixels even though
surface/sky classification matched. Adding `precise` to direction calculation
made agreement worse and was rejected. Neither change ships. Experimental source
and diagnostics are retained under `validation/experiments/ultra-compaction`.
Balanced and Performance comparisons require identical colour. Their original
sampling arithmetic is retained. Vaults also retains its existing renderer.

Four- and five-stage compaction were measured too. They did not provide a useful
consistent improvement over three stages. Sources and measurements are retained
under `validation/experiments/compact-{three,four,five}-pass`.

## Validation

- Release build succeeds without warnings; both CPU geometry/flight tests pass.
- All 48 profile comparisons are pixel-identical, with no unfinished rays and
  no surface/sky classification changes.
- Both saved camera replays and forward-approach samples are pixel-identical.
  Profiling now fails explicitly on any colour or visibility difference.
- Nine corridor views at zoom 10^6.7, 10^24 and 10^80 pass the uncropped
  16,384-step reference checks. Both compacted profiles are pixel-identical to
  single-pass; Ultra is checked with its retained renderer. No unfinished rays.
- Corner visibility checks and 1,200 flight frames pass at constant 1932×1086
  Balanced resolution in a 4K window. GPU p95 is 9.89491 ms, no unfinished pixels.
- Forced-compaction motion, coordinate-unit, exterior and snapshot regression
  checks pass at zoom 1, 10^6, 10^24 and 10^80.
- Native benchmark checks for all qualities, both worlds, palettes, resize,
  manual controls, pause and idle pass. Ultra correctly retains its original path
  even when the compaction diagnostic flag is requested.
- Heavy-to-light automatic switching passes without changing resolution or
  oscillating. The original faster fixture stays on single-pass in automatic mode.

Executable SHA-256:
`A90761654EF2ABBF3944A9E98A5AA095F7B80712A32E2C7DB301D15437FB8C64`.
