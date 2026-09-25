<#
.SYNOPSIS
    Runs every automated test in the repository.

.DESCRIPTION
    Four parts, each reported on its own line and none of them stopping the others:
      1. the C# suites, Core and App;
      2. the Python suite;
      3. the layout dump check: --dump-layouts from both apps against shared/layouts/us-arabic101.json,
         compared as parsed JSON because the two writers escape non-ASCII differently;
      4. with -Integration, the opt-in Windows tests in both languages, which need a desktop session.

    The layout check is skipped, with a message, when English (US) 04090409 and Arabic (101) 04012C01
    are not both installed: it reads the real keyboard layouts and there is nothing to compare without them.

.PARAMETER Integration
    Sets GIBBERISH_INTEGRATION=1 for both test runners, which enables the tests that touch the clipboard,
    the real layouts and the single-instance mutex.

.EXAMPLE
    .\scripts\test-all.ps1
    .\scripts\test-all.ps1 -Integration
#>
[CmdletBinding()]
param([switch]$Integration)

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo 'python\.venv\Scripts\python.exe'
$snapshot = Join-Path $repo 'shared\layouts\us-arabic101.json'
$results = [ordered]@{}

if ($Integration) {
    $env:GIBBERISH_INTEGRATION = '1'
    Write-Host 'Integration tests enabled (GIBBERISH_INTEGRATION=1).' -ForegroundColor Yellow
} else {
    Remove-Item Env:\GIBBERISH_INTEGRATION -ErrorAction SilentlyContinue
}

function Test-LayoutPairInstalled {
    # The same two layouts the snapshot was taken from; GetKeyboardLayoutList through the Python app's own bindings.
    $probe = @'
import sys
sys.path.insert(0, sys.argv[1])
from gibberish_rewriter.win.layout_reader import installed_layouts
sys.exit(0 if {0x04090409, 0x04012C01} <= set(installed_layouts()) else 1)
'@
    & $python -c $probe (Join-Path $repo 'python\src') 2>$null
    return $LASTEXITCODE -eq 0
}

function Compare-Json($left, $right) {
    # Single quotes inside: PowerShell strips double quotes when it builds a native command line.
    $compare = @'
import json, sys
with open(sys.argv[1], encoding='utf-8') as a, open(sys.argv[2], encoding='utf-8') as b:
    sys.exit(0 if json.load(a) == json.load(b) else 1)
'@
    & $python -c $compare $left $right
    return $LASTEXITCODE -eq 0
}

Write-Host "`n=== C# ===" -ForegroundColor Cyan
dotnet test (Join-Path $repo 'csharp\GibberishRewriter.slnx') --nologo
$results['C# tests'] = $LASTEXITCODE -eq 0

Write-Host "`n=== Python ===" -ForegroundColor Cyan
Push-Location (Join-Path $repo 'python')
& $python -m pytest -q
$results['Python tests'] = $LASTEXITCODE -eq 0
Pop-Location

Write-Host "`n=== Layout dump ===" -ForegroundColor Cyan
if (-not (Test-LayoutPairInstalled)) {
    Write-Host 'Skipped: English (US) 04090409 and Arabic (101) 04012C01 are not both installed.' -ForegroundColor Yellow
    $results['Layout dump'] = $null
} else {
    $temp = Join-Path ([System.IO.Path]::GetTempPath()) ('gibberish-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $temp | Out-Null
    try {
        $exe = Join-Path $repo 'csharp\src\GibberishRewriter.App\bin\Release\net10.0-windows\GibberishRewriter.exe'
        if (-not (Test-Path $exe)) {
            dotnet build (Join-Path $repo 'csharp\src\GibberishRewriter.App') -c Release --nologo | Out-Null
        }
        $csharpDump = Join-Path $temp 'csharp.json'
        $pythonDump = Join-Path $temp 'python.json'
        (Start-Process $exe -ArgumentList '--dump-layouts', $csharpDump -Wait -PassThru -NoNewWindow).ExitCode | Out-Null
        Push-Location (Join-Path $repo 'python')
        & $python -m gibberish_rewriter --dump-layouts $pythonDump
        Pop-Location
        $ok = (Test-Path $csharpDump) -and (Test-Path $pythonDump) `
            -and (Compare-Json $csharpDump $snapshot) -and (Compare-Json $pythonDump $snapshot)
        $results['Layout dump'] = $ok
        if ($ok) { Write-Host 'Both apps match the snapshot.' -ForegroundColor Green }
        else { Write-Host 'A dump does not match shared/layouts/us-arabic101.json.' -ForegroundColor Red }
    } finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
foreach ($name in $results.Keys) {
    if ($null -eq $results[$name]) { Write-Host ("{0,-14} skipped" -f $name) -ForegroundColor Yellow }
    elseif ($results[$name]) { Write-Host ("{0,-14} passed" -f $name) -ForegroundColor Green }
    else { Write-Host ("{0,-14} FAILED" -f $name) -ForegroundColor Red }
}
if (-not $Integration) {
    Write-Host 'Windows integration tests were not run. Add -Integration to include them.' -ForegroundColor Yellow
}
exit ($results.Values | Where-Object { $_ -eq $false } | Measure-Object).Count
