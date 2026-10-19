# Precision-preserving optimization screens — 2026-10-18

## Result and installed state

No candidate in this pass has a demonstrated, repeatable performance benefit.
The working `Preview-2026-10-17` executable and sources are unchanged. Its SHA-256
remains `34bdb274751e1f493fb370054ca2652b09749c7a1b73d88071f2237952c2c130`.
The root installation and sibling original project were not modified.

The useful new artifact is an in-process A/B diagnostic: it alternates complete
old/new shader banks at the same resolution and compares raw RGBA, float depths,
and visibility during 48 tiny forward/reverse camera movements. It rejects any
changed pixel, depth, or status. This is stricter than comparing each candidate
against its own serial renderer and avoids relying on screenshots alone.

Stable 60 FPS remains unproven for the most expensive saved corner view.

## Candidates

1. **Earlier direct arithmetic (precision threshold .0001 / .00001).** These
   existing isolated screens ran about 8–15% faster on the corner and 18–26%
   faster on `heavy`. They change some ray intersections, including large depth
   outliers. The .00001 corner changed 2,734 output pixels by over 16 channel
   levels. Neither threshold is installed; reference precision stays at .001.
2. **Saturating sphere clamp and precomputed clamped zero.** The latter hoists
   `clamp(0, signedLowerGap, signedUpperGap)` into the existing unused `next.w`
   field. The gaps are still computed in double precision, rounded separately,
   then clamped in float; the previous sphere-boundary repair is retained. The
   shader loses two min/max instructions per reference fold with no buffer size
   increase. Saturating the direct clamp only reverses min/max order in FXC DXBC;
   it does not reduce that shader's direct-fold instruction count.
3. **Precomputed reciprocal.** Replacing `dc / denominator` with a CPU-packed
   reciprocal changes 48,432 corner depth values and 5,288 presented pixels.
   The heavy view happens to match. Rejected: testing only one view would have
   incorrectly accepted this change.
4. **Earlier ray compaction (first batch 32 / 16 instead of 64).** The corner
   matches, but the heavy-view flight changes 658,737 / 667,435 depths across
   48 poses. The cutoff also changes where interval traversal begins. Neither
   variant demonstrates a benefit; both are rejected and remain isolated.

## Exact motion validation of candidate 2

All comparisons use 1980 × 1058, Balanced, unchanged ray budget, visibility,
lighting, precision threshold, and geometry.

| Fixture | Poses | Changed RGBA pixels | Changed depths | Changed visibility |
|---|---:|---:|---:|---:|
| sphere-boundary corner | 48 | 0 | 0 | 0 |
| heavy / slow-69 | 48 | 0 | 0 | 0 |
| newest slow capture | 48 | 0 | 0 | 0 |
| newest last flight | 48 | 0 | 0 | 0 |

That is 402,209,280 compared pixel samples across 192 poses. The separate CPU/GPU
field regression passes all 24,576 probes with the same maximum tolerance ratio
as the installed fix: 0.219204 (limit 1). Both CTest tests pass, including 240
sphere-boundary cases now using the precomputed base directly.

## Timing limitation

ComfyUI's separate `C:\Comfy\ComfyUI\standalone-env\python.exe` process, PID 17820,
was using the GPU throughout this pass. With no fractal test running, NVIDIA
reported up to 100% GPU use, 2760 MHz and about 190 W; Windows' process-specific
GPU counter later attributed 86% engine utilization to that Python process.
It was not interrupted. These samples are observations, not average utilization
over every benchmark frame.

Even with 20 ABBA rounds in one process, the small arithmetic candidate's median
paired ratios range from approximately .978 to 1.025 across views. That does
**not** establish a performance improvement. The captured times must not be
compared with yesterday's idle-GPU times or presented as a new FPS regression.
The user was asked to indicate when the separate job finishes.

## Reproduction

- `python validation/exact-fold-experiment.py combined` builds the arithmetic
  candidate from the fixed native renderer and runs four static replays.
- `python validation/add-exact-fold-ab.py` builds
  `validation/experiments/native-exact-ab/build-vs/Release/AuroraFractal.exe`.
- Run that EXE with `--fold-ab` from an isolated directory containing
  `last-flight.aurora`. Exit 0 requires exact agreement for all 48 poses. CSV
  per-frame timings and a JSON correctness report appear in `validation/fold-ab`.
- `--field-regression` retains the earlier independent CPU/GPU field check.
- `python validation/summarize-exact-folds.py` writes
  `validation/optimization-2026-10-17/exact-fold-summary.json` from saved outputs.

The user subsequently reported that ComfyUI had finished. The idle-GPU rerun
and additional screens are documented in `optimization-2026-10-18-idle.md`;
they do not establish a candidate worth installing. Do not install the
faster precision thresholds or reciprocal variant merely because their average
image differences are small. No image tolerance was relaxed in this pass.
