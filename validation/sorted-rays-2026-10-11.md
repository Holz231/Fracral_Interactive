# Sorted ray batches — 2026-10-11

Work is confined to `Fraktals-Weiter`. The sibling `Fraktals` was not changed.
The preceding source and executable are in `backup-2026-10-10-long-rays`.

## Root cause and change

The newly captured long-corridor view has 43,540 rays exceeding 1,000 queries,
with a mean of 193.8. The old last dispatch left those rays together for the
remaining 7,872 accepted steps. Divergent ray lengths and field prefix depths
wasted parallel GPU execution even after the initial compaction.

The new path traces 64 steps, then repeatedly compacts after 256-step batches.
Its final dispatch completes the unchanged 8,192 accepted-step budget. The 33
traversal dispatches sort unfinished rays by their prefix depth into 128 buckets.
Group-local histograms aggregate the counter updates before accessing global
memory. An exclusive scan and scatter place related work together. Deep prefix
indices above 127 share the last bucket; their actual field depth is unchanged.

The rank temporarily occupies the upper bits of the existing verifier flag,
keeping each ray job at 48 bytes. Bit zero retains the verifier. Two existing
full-capacity queues are reused; additional persistent bucket storage is 512
bytes. Indirect dispatch and sorting stay on the GPU, with no queue readback.

Performance and Balanced now use the sorted path on the first Citadel frame.
The previous timing-driven activation required an expensive single-pass frame
before acceleration could engage. Removing that switch avoids the initial
single-pass stall. Easy views pay a small extra queue cost. Ultra keeps its
original two-sample shader; Vaults is unchanged.

The distance evaluator, lighting, primary single-pass tracer, pixel sampling,
resolution budgets, visibility bounds and camera/navigation are unchanged.
Per-ray traversal preserves the original float state across batches. No fog,
coarser geometry, missing detail, sample reduction or alternate scenery was added.

## Paired measurements

RTX 4070 SUPER, 1980×1058, Balanced. Compared with the **installed three-stage
compaction**, not the much slower original single-pass shader:

| View | Installed | New | Maximum RGB error | Ray status changes |
|---|---:|---:|---:|---:|
| Long grazing corridor | 64.410 ms | 43.969 ms | 0 | 0 |
| Dense interior | 25.589 ms | 22.502 ms | 0 | 0 |
| Faster saved view | 10.399 ms | 10.883 ms | 0 | 0 |
| Latest captured view | 29.661 ms | 27.495 ms | 0 | 0 |

The long-corridor improvement is about 32% less GPU time. It remains around
44 ms: this is not a 60-fps guarantee. The unaccelerated single-pass shader
requires about 154 ms in that view, but that is not the relevant installed
performance baseline. The latest capture's 383.877 ms live spike was not
reproduced in isolation, so no claim is made that 383 ms became 27 ms.

Each measurement retires individual frames, avoiding a long uninterrupted GPU
benchmark batch that can trip Windows' watchdog. Old/new compaction order
alternates across three rounds, each with warmup and four measured frames.
The benchmark-only `SORT_RAYS=0` path reproduces the preceding three dispatches.
Reports retain single-pass `before_ms`, installed `installed_ms`, sorted
`after_ms` and four pass intervals. Timings exclude UI, presentation and scaling.

The 300-frame heavy/light runs keep the sorted path active from frame zero,
without fallback or resolution changes. For the long corridor, steady GPU
mean/p95 are 43.538/43.653 ms and CPU submission averages 0.039 ms. The light
segment averages 2.096 ms. These hidden-window measurements do not measure
visible screen delivery latency.

## Validation and limits

- Release build succeeds without warnings; both CPU geometry/flight tests pass.
- All 48 varied views and 24 saved-view/approach comparisons have identical RGB.
  Every hit/escape/unfinished status is also compared exactly.
- Four saved camera fixtures cover two resolutions and forward approaches.
- Standard corridor and corner visibility checks pass in all quality profiles.
- The 1,200-frame corner flight holds 1932×1086 Balanced rendering in a 4K
  window, with no unfinished rays; GPU p95 is 8.879 ms.
- Motion, coordinate-unit changes, exterior and snapshot regression checks pass
  at zoom levels 1, 10^6, 10^24 and 10^80.
- Native shader/quality/resize/palette checks and manual/pause/idle checks pass.
- Both 300-frame heavy/light tests pass, including camera/timestamp matching.
  Slow-frame JSON now records whether the captured frame used compaction.

The new worst-case fixture already exhausts the finite trace budget for 603
pixels at 1980×1058 (5 at 960×540) in the preceding renderer. Their locations and
statuses remain identical. This optimization does not resolve those existing
rays. Standard corridor fixtures continue to require zero unfinished pixels.

Other explored approaches are retained under `validation/experiments`: smaller
work groups, fixed and increasing batch sizes, orbit SRV storage, several queue
sort keys, affine skipping and recomputed prefixes. They were slower, less useful
or changed pixels and were not installed.

Executable SHA-256: `98FAB71AF4EE68C465F3A24B24C85BE9BF3839944AB30D7DAF027A563561C902`.
