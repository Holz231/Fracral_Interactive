# Scheduling investigation — 2026-10-11

## Outcome

No new rendering optimization from this investigation is installed. Sixteen
experiments failed to establish a reliable improvement over the already installed
uniform-fold/deferred-refinement renderer, or changed image/depth results. The
final `src/fractal.hlsl` is byte-for-byte identical to
`backup-2026-10-11-uniform-folds/src/fractal.hlsl`. Resolution, lighting, view
bounds, the 8192 accepted-step budget and the original render scheduling remain
unchanged. Stable 60 fps in all saved difficult views is **not achieved**.

The retained code change is an opt-in diagnostic:

```
AuroraFractal.exe --replay --native-only --batch-details
```

Run it from a fixture directory containing `last-flight.aurora`. It writes the
normal strict image/depth comparison plus `validation/replay/batches.csv`.
The CSV records input/surviving ray counts and separate scheduling/tracing times
for each of 33 batches, then surface refinement/lighting. It uses two warm-up
frames and eight measured frames. Count copies, 67 timestamp queries and CPU
readback are enabled only for this explicit diagnostic, never in interactive
flight. Each recorded frame completes before the next is submitted. The code
rejects non-monotonic timestamps, clock changes and growing survivor counts.
Detailed timing includes instrumentation overhead and excludes display/UI time.

## What the new measurement establishes

RTX 4070 SUPER, Balanced, fixed 1980×1058, saved grazing corridor at zoom 10^26.833.
The ordinary uninstrumented renderer was measured at 30.597 ms before the detailed
capture. The older three-pass timing in replay JSON is a historical comparator,
not the installed baseline.

| Work | Mean instrumented GPU time |
|---|---:|
| First 64 steps | 3.952 ms |
| First continuation | 8.437 ms |
| Batches 2-4 | 4.303 ms |
| Batches 5-16 | 5.712 ms |
| Batches 17-32 | 5.905 ms |
| All queue scheduling | 0.807 ms |
| Refinement and lighting | 1.530 ms |

After the first 64 steps, 1,667,306 of 2,094,840 rays remain. The next batch reduces
that to 218,470. By batch 17 only 4,068 remain, but the last sixteen batches still
cost about 5.9 ms. All queue scheduling totals approximately 0.8 ms. This rules out
queue setup alone as a sufficient route to the missing ~14 ms. It does not prove
which hardware bottleneck dominates individual distance-field instructions.

Moving the first compaction later, sorting by measured last-query work, widening
bins, immediately refilling finished workers, and using sparse four-thread groups
were tested; none merits replacing the current renderer. Sparse groups helped
some final tiny queues slightly but increased total time. Segment skipping also
changed some depths/visibility and was rejected, despite filling one previously
unfinished pixel. No comparison tolerance was weakened to accept an experiment.

## Rejected or inconclusive experiments

Single fixture measurements below are screening results, not multi-scene speedup
claims. Sub-millisecond differences from the roughly 30–31 ms baseline are not a
reliable improvement. Sources and JSON remain in `validation/experiments`.

| Experiment | GPU ms | Maximum RGB difference | Changed hit depths | Status changes |
|---|---:|---:|---:|---:|
| uniform-compiler-o1 | 30.568 | 0 | 0 | 0 |
| uniform-cost-sort | 34.292 | 0 | 0 | 0 |
| uniform-direct-enqueue | 30.728 | 0 | 0 | 0 |
| uniform-fixed-prefix-loop | 54.090 | 3 | 167 | 0 |
| uniform-group-128 | 30.825 | 0 | 0 | 0 |
| uniform-initial-256 | 53.538 | 0 | 0 | 0 |
| uniform-joint-cost-sort | 925.101 | 168 | 4035 | 3 |
| uniform-persistent-1 | 108.315 | 0 | 0 | 0 |
| uniform-persistent-32 | 70.530 | 0 | 0 | 0 |
| uniform-prefix-boundary | 46.209 | 0 | 0 | 0 |
| uniform-radius-sort-512 | 31.074 | 0 | 0 | 0 |
| uniform-recomputed-prefix | 30.486 | 0 | 0 | 0 |
| uniform-segment-current | 32.583 | 154 | 26342 | 1 |
| uniform-separated-tail | 31.722 | 0 | 0 | 0 |
| uniform-sparse-group-4 | 31.308 | 0 | 0 | 0 |
| uniform-twofold-loop | 30.366 | 0 | 0 | 0 |

The joint cost-sort variant failed badly and was discarded; its root cause was
not established. The 256-step initial batch also showed more timing variation
than other screens, so its result must not be interpreted as a controlled ratio.
`validation/tools/shader-metrics` contains a small D3D compiler/reflection utility;
its DXBC temporary-register count is not a measurement of NVIDIA physical
register occupancy.

## New saved case and remaining limitations

`validation/slow-45ms-fixture` preserves the latest matched slow-frame snapshot
(45.1779 ms captured live, zoom 10^13.169). It replays at approximately 18.35–18.38 ms
in isolation. The 45-to-18 difference is **not** an optimization result: the camera
was replayed under different runtime load and the shader was unchanged.

The original renderer has 603 unfinished rays in the grazing corridor and 863 in
the newly preserved native view. Their counts and hit/sky classifications are
unchanged by the final build. The profiler does not fix these finite-budget limits.

## Verification

Release build and both CTest geometry/continuity tests passed. Full six-view
replays (saved 960×540, saved native 1980×1058, four forward-approach checkpoints)
are run for both the new fixture and the grazing corridor. Results and final
executable hash are recorded in `scheduling-2026-10-11/verification.json`.
The profiling CSV additionally checks survivor monotonicity and fixed resolution.
Source changes are confined to `Fraktals-Weiter`; the original `Fraktals` is untouched.
