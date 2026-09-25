# Builds a self-contained copy of the C# app into dist\ that runs on any 64-bit Windows 10 or 11 PC without .NET installed.
# Run:            powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\publish.ps1"
# Also install:   powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\publish.ps1" -Install
# -Install copies dist\ to %LOCALAPPDATA%\Programs\GibberishRewriter, a folder that stays put, so "Start with Windows" can point at it.
param(
    [switch]$Install
)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'csharp\src\GibberishRewriter.App'
$dist = Join-Path $root 'dist'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GibberishRewriter'

# Check before deleting anything: a running exe is locked, and a half-deleted folder leaves it without shared\.
$folders = @($dist)
if ($Install) { $folders += $installDir }
foreach ($folder in $folders) {
    $running = Get-Process -Name 'GibberishRewriter' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($folder + '\', [System.StringComparison]::OrdinalIgnoreCase) }
    if ($running) { throw "Gibberish Rewriter is running from $folder. Exit it from its tray icon first." }
}

if (Test-Path -LiteralPath $dist) { Remove-Item -LiteralPath $dist -Recurse -Force }

& dotnet publish "$project" -c Release -r win-x64 --self-contained `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true -p:DebugType=none -o "$dist"
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed with exit code $LASTEXITCODE." }

# The test vectors are copied with shared\ but the app never reads them.
Remove-Item -LiteralPath (Join-Path $dist 'shared\vectors') -Recurse -Force

$size = (Get-ChildItem -LiteralPath $dist -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Output ("Published to {0} ({1:N0} MB)" -f $dist, ($size / 1MB))

if ($Install) {
    if (Test-Path -LiteralPath $installDir) { Remove-Item -LiteralPath $installDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Copy-Item -Path (Join-Path $dist '*') -Destination $installDir -Recurse
    Write-Output "Installed to $installDir"
    Write-Output "Start $(Join-Path $installDir 'GibberishRewriter.exe'), then tick 'Start with Windows' in its tray menu."
}
