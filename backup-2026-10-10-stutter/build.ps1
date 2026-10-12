$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
if ($cmakeCommand) {
    $cmakeExecutable = $cmakeCommand.Source
} else {
    $vswhereExecutable = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $installation = & $vswhereExecutable -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $cmakeExecutable = Join-Path $installation 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    if (!(Test-Path -LiteralPath $cmakeExecutable)) { throw 'CMake and the Visual Studio C++ tools are required to rebuild.' }
}
Push-Location $projectRoot
try {
    & $cmakeExecutable -S . -B build-copy -G 'Visual Studio 17 2022' -A x64
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
    & $cmakeExecutable --build build-copy --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed.' }
    & '.\build-copy\Release\FractalTests.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Fractal geometry validation failed.' }
    & '.\build-copy\Release\CitadelTests.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Citadel geometry and movement validation failed.' }
    Copy-Item -LiteralPath '.\build-copy\Release\AuroraFractal.exe' -Destination '.\AuroraFractal.exe' -Force
    Write-Host 'Built AuroraFractal.exe. Double-click it to fly.'
} finally { Pop-Location }
