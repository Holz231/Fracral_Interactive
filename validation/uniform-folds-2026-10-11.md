# Uniform folds and separate surface refinement - 2026-10-11

Work is confined to `Fraktals-Weiter`. The separate `Fraktals` project is untouched.
The previously installed source, executable and flight settings are preserved in
`backup-2026-10-11-sorted-rays`.

## Rendering change

The main distance evaluator previously used a nested four-iteration escape-tail
loop within its direct fold loop. The supported compute paths now use one uniform
direct loop and vector predicates for reference-relative box folding. Outside
radius eight, the sphere-fold denominator is already one, so the arithmetic and
escape tests remain equivalent. Removing the special tail is measurably faster
on this GPU despite that tail having originally been introduced as an optimization.

The three surface bisection queries now run in an independent compute pass after
all traversal batches. A 16-byte record retains the exact lower/upper bracket,
cached derivative and reference index. The logarithmic scale is retained in the
ray output until refinement finishes. There is no recomputation of the bracket
or derivative from rounded logarithms. This removes the duplicated distance
query body from the long-running traversal shaders. Every hit still receives
all three bisections before lighting, with exactly matching output depths.

The extra record costs approximately 32 MiB at the Balanced resolution cap;
it is recreated on resize and released for Ultra. Traversal retains the existing
64-step first batch, repeated 256-step batches, sorting, conservative retries,
8,192-step budget, ray bounds and per-pixel samples. No resolution, geometry,
view distance, shading samples or precision settings were reduced. Ultra and
Vaults retain their preceding renderers.

## Comparison with the immediately preceding installed executable

RTX 4070 SUPER, Balanced, 1980 x 1058. GPU render milliseconds, excluding
upscaling, UI and presentation. Both executables replayed the same five camera
fixtures sequentially; no concurrent GPU test runs. Each fixture includes native
and 960 x 540 views plus four forward-approach snapshots. Measurements warm up
and retire individual frames. The 30 output PNGs match byte for byte between
the two executables.

| Saved view | Previous sorted build (ms) | Current build (ms) | Reduction |
|---|---:|---:|---:|
| Dense interior | 22.439 | 15.500 | 30.9% |
| Deep oblique view | 27.407 | 17.911 | 34.6% |
| Long grazing corridor | 43.866 | 30.716 | 30.0% |
| Recently captured starting view | 5.235 | 2.984 | 43.0% |
| Fine corner detail | 10.854 | 6.487 | 40.2% |

The comparison is against the preceding **sorted-ray** build, not the much
slower original pixel shader or older three-stage compaction. Per-view JSON
now calls the older three-stage measurement `three_pass_ms` instead of the
misleading `installed_ms`. `before_ms` is still the original pixel shader;
`after_ms` is the current full tracing/refinement/lighting pipeline. The fourth
pass interval includes both refinement and lighting.

Raw previous executable reports are in `uniform-folds-2026-10-11/before`;
current results and the comparison summary are in `current` and `comparison.json`.

## Validation

- Release build succeeds without warnings; both CPU geometry/flight tests pass.
- All 78 comparisons pass: 48 varied views and 30 saved/approach views.
  RGB, hit/escape/unfinished classification, and floating-point hit depths all
  match exactly. Hit-depth comparison was added specifically to validate the
  separated refinement pass; it does not merely compare appearance.
- Gap, corner, coordinate-rebase, deep-zoom, exterior, snapshot and native
  quality/palette/resize/controller checks pass.
- The 1,200-frame corner flight holds 1932 x 1086 rendering throughout a 4K
  window, with zero unfinished pixels and a GPU p95 of 5.493 ms (including upscale).
- A 300-frame heavy/light replay retains compaction from frame zero at constant
  resolution. The heavy portion averages 30.022 ms, with p95 30.089 ms;
  CPU submission averages 0.038 ms. Matched slow-frame capture passes.
- New `--flight-profile` exercises 300 forward and 300 reverse simulation steps
  from a saved camera at fixed 1980 x 1058 rendering. Four fixtures, 2,400 frames,
  pass the resolution, compaction and camera/timestamp checks. These flight
  profiles measure timing, not per-frame geometric equivalence; independent
  image/depth and corner regressions provide the correctness checks.

| 600-frame flight | Mean GPU ms | p95 GPU ms | Maximum GPU ms |
|---|---:|---:|---:|
| Long grazing corridor | 27.291 | 30.663 | 31.182 |
| Dense interior | 13.201 | 14.907 | 15.781 |
| Deep oblique view | 16.945 | 19.681 | 21.464 |
| Recently captured starting view | 4.098 | 6.931 | 7.657 |

Flight statistics exclude the first 12 timing-settling frames and include
upscaling. The asynchronously reported GPU samples are recorded during hidden
window execution. They do not establish visible display FPS or input latency.
A fixed 1/60-second simulation step makes the flight path reproducible.

## Remaining limits

Stable 60 fps in every view has **not** been reached. The hardest corridor remains
around 30-31 ms and the deep oblique flight can exceed 20 ms, above the 16.7 ms
GPU budget before presentation overhead. The dense interior flight remains below
15.8 ms in this run; that alone is not a universal 60-fps guarantee.

The long-corridor fixture still has the same 603 finite-budget unfinished pixels
at native resolution (five at 960 x 540) as the preceding renderer. Their exact
locations and statuses remain unchanged; this work does not repair that older
finite-budget limit. Standard gap/corner fixtures still require zero unfinished
pixels.

Interval/Mobius segment skipping, directional prefixes, an orbit storage buffer,
smaller batches, a short-start schedule and a combined orbit loop were evaluated
and rejected for extra cost or changed pixels. Their experimental sources/results
remain under `validation/experiments`; they are not used by this executable.

Previous executable SHA-256: `98FAB71AF4EE68C465F3A24B24C85BE9BF3839944AB30D7DAF027A563561C902`.
Current executable SHA-256: `819827E0B0300D71D894317302E13C862105EFBE7D0BF0470C52829FC6564815`.
