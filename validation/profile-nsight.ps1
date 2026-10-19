$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$tool=Join-Path $PSScriptRoot 'tools/nsight/extracted/ProgramFiles64Folder/NVIDIA Corporation/Nsight Graphics 2026.3.1/host/windows-desktop-nomad-x64/ngfx.exe'
$exe=Join-Path $PSScriptRoot 'dx12-probe/build/Release/AuroraDX12Probe.exe'
$work=Join-Path $PSScriptRoot 'dx12-probe'
# Only the profiler and this local deterministic fixture run elevated.
# No driver settings or persistent performance-counter permissions are changed.
foreach($mode in @('hardware','shader')) {
    $output=Join-Path $PSScriptRoot ('tools/nsight/capture-'+$mode)
    New-Item -ItemType Directory -Force $output | Out-Null
    $arguments=@('--activity','GPU Trace Profiler','--exe',$exe,'--dir',$work,
        '--args','shaders-fxc ../slow-69ms-fixture/validation/replay/saved-native-constants.bin ../slow-69ms-fixture/validation/replay/saved-native-depth.bin',
        '--env','AURORA_PROBE_FRAMES=120;AURORA_PROBE_MARKERS=1','--start-after-submits','8','--limit-to-submits','1','--max-duration-ms','100',
        '--architecture','Ada','--metric-set-name','Top-Level Triage','--set-gpu-clocks','unaltered',
        '--collect-screenshot','0','--hes-enabled','0','--auto-export','--output-dir',$output,'--verbose')
    if($mode -eq 'shader') {$arguments+='--real-time-shader-profiler'}
    & $tool @arguments *> (Join-Path $output 'run.log')
    $LASTEXITCODE | Set-Content (Join-Path $output 'exit-code.txt')
    if($LASTEXITCODE) {break}
}
'Complete' | Set-Content (Join-Path $PSScriptRoot 'tools/nsight/session-finished.txt')
