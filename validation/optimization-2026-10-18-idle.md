# Idle-GPU follow-up — 2026-10-18

## Decision

No new rendering change is installed. The exact-arithmetic candidate is slower
on the critical corner in both repetitions, and additional loop/scheduling
variants show no reliable improvement. The installed preview remains SHA-256
`34bdb274751e1f493fb370054ca2652b09749c7a1b73d88071f2237952c2c130`.
The root installation and sibling `Fraktals` were not modified.

The expensive saved corner still exceeds the 16.67 ms budget for 60 FPS. The
measurements below are GPU fractal-pass timings, excluding UI and presentation,
not measured visible frame rates.

## Environment and primary rerun

After the user confirmed that ComfyUI finished, no Python or Aurora process was
running. The GPU initially reported 5% utilization, 210 MHz, 5.98 W and 44 °C.
The tests run sequentially with shader warmup. Each comparison alternates the
old and new shader banks for 20 ABBA rounds in one process, using the same
camera, resources, resolution (1980 × 1058), and Balanced settings.

| Fixture | Repetition | Existing shader ms | Combined candidate ms | Time change |
|---|---:|---:|---:|---:|
| Corner | 1 | 22.089 | 22.584 | +2.24% |
| Corner | 2 | 22.137 | 22.972 | +3.77% |
| Heavy corridor | 1 | 16.966 | 17.062 | +0.56% |
| Heavy corridor | 2 | 16.601 | 16.747 | +0.88% |
| New slow capture | 1 | 4.301 | 4.301 | +0.01% |
| New slow capture | 2 | 4.364 | 4.375 | +0.26% |
| New last flight | 1 | 4.572 | 4.537 | -0.77% |
| New last flight | 2 | 4.353 | 4.337 | -0.37% |

All eight runs return 0: their 384 moving camera poses have zero changed raw
RGBA pixels, float depths, or visibility statuses. This establishes tested
equivalence, not a speedup. The tiny last-flight improvement does not compensate
for the repeated corner regression.

Raw results and timings are preserved separately from the earlier contended
measurements in `optimization-2026-10-18-idle/{fixture}-{repetition}`.

## Additional screens

Numbers are paired old → candidate GPU ms from each run. Do not compare raw
times across rows as optimization gains; clocks and desktop activity vary.

| Change | Corner | Heavy corridor | Decision |
|---|---:|---:|---|
| Reference folds unrolled ×2 | 21.344 → 21.291 | 16.477 → 16.554 | Within variation; no consistent gain |
| Reference folds unrolled ×3 | 23.735 → 23.621 | 17.424 → 17.558 | Within variation; no consistent gain |
| First compaction at 16 steps | 24.131 → 25.037 | 18.863 → 19.317 | Slower |
| First compaction at 128 steps | 25.958 → 26.353 | 22.120 → 22.392 | Slower |
| Precomputed sphere base alone | 21.946 → 22.533 | 17.180 → 17.256 | Slower |
| Certified hit predicate | 21.984 → 22.676 | 16.721 → 17.763 | Slower |

The new compaction screens compensate the first continuation so that both
paths reach the original 320-step boundary, retaining every later interval
start. This corrects the experimental methodology of simply changing the
initial chunk. They now match exactly during both 48-pose flights; there is
still no speed benefit.

The reference-loop variants preserve every fold, bailout, and direct-arithmetic
transition. Both sizes match exactly in the two flights. Hoisting the sphere
base alone also matches all four flights, but removing two DXBC instructions is
not enough to demonstrate a benefit on this GPU.

The certified-hit experiment uses a conservative bound on all remaining direct
folds for the saved world's Julia constant, whose norm is 2.1. Box folding
cannot increase the point's norm and each sphere scale is at least 2.8, so the
remaining normalized radius is bounded by `(r + 2.1/1.8) / derivative`.
The looser bound `sqrt(.5*r*r+2) / derivative` safely bounds the .45 distance
estimate with roundoff margin in these fixtures. Only callers that need the
hit predicate can use it; speculative-step verification and lighting continue
to compute the original distance. It matches all four 48-pose flights exactly,
but the per-fold checks cost more than the removed iterations. It is rejected,
not a general-purpose implementation for arbitrary user-edited Julia constants.

## Reproduction and remaining work

- `reference-unroll-ab.py 2` or `3` builds/runs the reference-loop screens.
- `early-compaction-ab.py 16` or `128` builds/runs the matched-boundary screens.
- `certified-hit-ab.py` builds/runs the threshold-predicate screen for the
  existing four fixtures.
- All diagnostics use `--fold-ab`; exit 0 requires exact color, depth and
  visibility agreement over 48 forward/reverse poses. No tolerance was relaxed.
- `optimization-2026-10-18-idle/summary.json` records the primary rerun and the
  loop, scheduling and isolated-base screens. Certified-hit results remain in
  `experiments/native-certified-hit/{fixture}/validation/fold-ab`.

The earlier profiling result still applies: dense distance-field work and the
sequential work of long grazing rays dominate. These screens do not establish
that arithmetic hoisting, reference unrolling, or earlier compaction solves the
remaining 60 FPS requirement. Resolution, detail, view distance and geometry
were not reduced to produce a favorable number.
