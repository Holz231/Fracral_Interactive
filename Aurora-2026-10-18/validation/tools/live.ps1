# Runs the interactive app (visible window) in guided flight from a saved view
# for a few seconds with the per-frame log enabled, then closes it gracefully.
param([string]$Exe, [string]$Fixture, [string]$Out, [int]$Seconds = 30, [string]$Defines = "")
$ErrorActionPreference = 'Stop'
Remove-Item -Recurse -Force $Out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path
Copy-Item $Exe "$Out\AuroraFractal.exe" -Force
Copy-Item $Fixture "$Out\last-flight.aurora" -Force
Set-Content -Path "$Out\settings.txt" -Value "0 1 3.8 1 1" -Encoding ascii
$env:AURORA_FRAME_LOG = "$Out\frames.csv"
$env:AURORA_AUTOPILOT = "1"
$env:AURORA_KEEP_ACTIVE = "1"
if ($Defines) { $env:AURORA_SHADER_DEFINES = $Defines }
$p = Start-Process -FilePath "$Out\AuroraFractal.exe" -ArgumentList @('--load-flight') -WorkingDirectory $Out -PassThru
Remove-Item Env:AURORA_FRAME_LOG; Remove-Item Env:AURORA_AUTOPILOT; Remove-Item Env:AURORA_KEEP_ACTIVE
if ($Defines) { Remove-Item Env:AURORA_SHADER_DEFINES }
Start-Sleep -Seconds $Seconds
$null = $p.CloseMainWindow()
$null = $p.WaitForExit(15000)
"exit: $($p.ExitCode)"
if (Test-Path "$Out\aurora-error.txt") { "ERROR: " + (Get-Content "$Out\aurora-error.txt") }
