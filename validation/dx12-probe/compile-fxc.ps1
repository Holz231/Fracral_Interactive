param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
foreach($entry in @('beginRays','continueRays','finishRays','prepareRays','sortRays','refineRays')) {
    $chunk=256; $function=$entry
    if($entry -eq 'beginRays') {$chunk=64}
    if($entry -eq 'finishRays') {$chunk=8192; $function='continueRays'}
    & $fxc /nologo /T cs_5_0 /E $function /D UNIFORM_FOLDS=1 /D DEFER_SURFACE_REFINE=1 /D WORLD_KIND=1 /D "RAY_CHUNK=$chunk" /O3 /Ges /Fo "$OutputDirectory/$entry.dxil" $Source
    if($LASTEXITCODE) {throw "FXC failed for $entry"}
}
