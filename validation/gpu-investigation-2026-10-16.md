# GPU bottleneck investigation — 2026-10-16

## Outcome and installation status

Stable 60 FPS has **not** been achieved in the saved grazing-corridor case.
No experimental shader or executable from this investigation was installed.
The root executable and production shader retain these SHA-256 hashes:

- `AuroraFractal.exe`: `D0298511DDAC9E605458A30770A53350A3917FFE8480340CF949153BD17E4C55`
- `src/fractal.hlsl`: `B95CF4B61F31110DF13212919889BE53DAA221EBE65161394CB5AD630D9C541B`

Resolution, view distance, accepted-step limit, shading and detail thresholds
are unchanged. All experiments are isolated under `validation/experiments`.
The sibling original project was not modified.

## Hardware profiling

NVIDIA Nsight Graphics 2026.3.1 was downloaded from NVIDIA and its Authenticode
signature validated. The MSI was extracted locally, without installing a driver.
Ordinary-user profiling failed because GPU performance counters were restricted.
The user explicitly approved an administrator profiler launch. Hardware and
shader traces then completed successfully. No persistent driver permissions or
GPU clock settings were changed; clocks were left unaltered.

The D3D12 probe runs the production FXC/DXBC trace shaders at 1980 x 1058 on the
RTX 4070 SUPER, using exported constants from `slow-69ms-fixture`. Its output
matches the D3D11 reference depth/status image exactly. It excludes lighting,
upscaling and UI, so its roughly 29 ms is not a complete app frame time.
The production native replay remains approximately 30.6 ms.

PIX markers now identify individual batches. Two separate traces collect
hardware throughput and sampled warp stalls; their percentages should not be
treated as simultaneous measurements or an additive wall-time decomposition.
Raw reports and signed third-party binaries are ignored by Git in `tools`.
The compact phase export is `nsight-2026-10-16-phases.csv`.

| Work | GPU ms |
|---|---:|
| Initial 64 steps | 3.888 |
| Continuation batches 1–4 | 12.669 |
| Continuation batches 5–16 | 5.658 |
| Continuation batches 17–32 | 5.611 |
| All queue scheduling | 0.848 |
| Surface refinement | 0.310 |
| Sum of marked work | 28.986 |

The initial pass reaches 87.5% SM instruction throughput, about 29 active lanes
per warp, and 96.7% register allocation. The first continuation reaches 80.1%
throughput with 22.2 active lanes and 90.0% register allocation. Late queues
underfill the GPU: batch 16 averages about 2 active warps per SM and batch 31
about 0.43. In the shader trace, roughly half of active-warp samples in batch 16
wait for fixed-latency dependencies. That is **not** a claim that half the whole
frame is removable wait time.

Full-frame DRAM throughput was only about 2.94%; L2 throughput was about 1.25%.
Long-scoreboard stalls were small. These measurements point to dense-pass
instruction work and sparse-pass serial dependencies, rather than bandwidth or
queue setup, as the dominant remaining problems. Simply increasing occupancy
or changing graphics APIs cannot remove the dependent work of the longest ray.

## Checks and isolated screens

The additional queue audit verified that all **1,667,306** first-pass survivors
occur exactly once in the sorted queue, with all 48 bytes preserved. The probe
subsequently produced zero changed depths or statuses; 603 unfinished rays are
an existing baseline limitation, not a new success or a resolved defect.

These are short screening timings, not multi-scene performance claims:

| Experiment | Trace + refine ms | Changed hit depths | Changed statuses |
|---|---:|---:|---:|
| Production FXC probe, queue-audited | 29.582 | 0 | 0 |
| Fast branch for unchanged box folds | 33.125 | 0 | 0 |
| Fast branch for unchanged sphere denominator | 30.002 | 92,061 | 0 |
| Both fast branches | 32.428 | 92,061 | 0 |
| Direct sphere reciprocal branch | 29.923 | 0 | 0 |
| Sparse direct enqueue, beginning at batch 8 | 36.483 | 0 | 0 |
| Late affine escape tail, beginning at batch 8 | 31.394 | 150 | 0 |
| DXC eight-sample packet, beginning at batch 8 | 28.034 | 14,795 | 381 |
| DXC eight-sample packet, beginning at batch 16 | 26.833 | 3,667 | 242 |
| DXC eight-sample packet, beginning at batch 24 | 27.803 | 1,071 | 112 |

The packet variants increase unfinished rays, despite occasionally reducing time.
They are rejected. The other screens provide no reliable improvement. No image
comparison tolerance was relaxed to accept these variants.

## Other experiments retained from this investigation

Earlier local screens include shared-orbit caches, persistent workers, directional
prefix limits, interval bounds and temporal far-depth reuse. Their source and
results remain available. They either failed equivalence checks or did not
provide a reliable speedup. Some earlier packet/persistent timings occurred
while a separate ComfyUI job used the GPU; they must not be compared directly
with the idle-GPU results above. The unrelated job was not stopped.

The filtered far-history experiment's 600-frame flight has 599 valid GPU samples:
mean 26.755 ms, p95 29.546 ms, maximum 35.829 ms. It also changes edge pixels.
It is not installed and is not evidence of stable 60 FPS. Its `--history-check`
now returns 2 for any RGB mismatch instead of returning 0 merely because the
experiment ran to completion. The generator received the same correction.

The additional `slow-41ms-fixture` preserves a captured 41.1308 ms camera pose.
Its unchanged production replay takes 26.3143 ms in isolation, with zero
depth/status/RGB differences and 1,046 existing unfinished rays. This captured
versus isolated timing difference is not an optimization gain.

## Final validation

### Follow-up: interval traversal prototypes

The follow-up after the user's "was jetz?" implements isolated interval tests
inside the sparse continuation loop, starting at batch 8. The original shader
and executable remain unchanged. `interval-march-experiment.py` uses homogeneous
quadratic ray curves and Bernstein sign bounds to avoid unnecessary root solves.
It produces an exactly matching image, but 28.932 ms is within baseline timing
variation and does not establish a speedup.

`interval-box-march-experiment.py` bounds complete folded intervals, including
branch crossings, and tests them repeatedly rather than only between batches.
It fills some formerly unfinished rays but costs 40.145 ms (14,525 changed hit
depths, 385 status changes, 218 unfinished). Limiting proof work to four or eight
folds gives 36.769 / 37.911 ms, with 221 / 219 unfinished rays respectively.
These are rejected performance screens, not validated geometric replacements.
The added proof work currently costs more than the stepping it saves. A repeated
interval check in each ray's inner loop is therefore not a demonstrated solution.

The probe and far-history experiment rebuilt successfully. The full 120-frame
history check exited 2 as expected, correctly rejecting its image differences.
Both production CTest tests (`citadel_continuity`, `fractal_geometry`) passed.
`git diff --check` and Python syntax checks for the new diagnostic scripts passed.
The production executable and shader hashes above were rechecked unchanged.

## Reproduction and next architectural question

- Build `validation/dx12-probe/build` in Release. The six ordinary FXC shaders
  are in `validation/dx12-probe/shaders-fxc`.
- Run `AuroraDX12Probe.exe shader-directory constants.bin reference-depth.bin`.
  Exit 0 requires identical finite hit depths and statuses; exit 2 reports
  differences. `AURORA_PROBE_QUEUE_CHECK=1` enables the permutation audit.
- `AURORA_PROBE_FRAMES` extends the measured run (default 12, minimum 12).
- `validation/profile-nsight.ps1` performs the approved profiler workflow.
  It needs counter access and the local Nsight/PIX dependencies, and does not
  change persistent settings. `AURORA_PROBE_MARKERS=1` is diagnostic only.
- `python validation/summarize-nsight.py` regenerates the compact phase CSV.

The next substantial improvement needs to reduce the *sequential distance-field
queries* for grazing rays while proving that intervening geometry is not skipped.
The current tests show why more queue rearrangements and speculative temporal
depth reuse alone are insufficient. Any replacement needs independent geometric
validation: the old finite-step renderer can itself miss subpixel grazing hits,
so its image is a strict regression oracle, not a mathematical ground truth.

References: [NVIDIA download](https://developer.nvidia.com/nsight-graphics/get-started),
[GPU Trace documentation](https://docs.nvidia.com/nsight-graphics/UserGuide/gpu-trace-overview.html),
[counter permissions](https://developer.nvidia.com/nvidia-development-tools-solutions-err_nvgpuctrperm-permission-issue-performance-counters),
[Microsoft PIX events](https://github.com/microsoft/PixEvents).
