# Builds shared/wordlists/english.txt and ESDB-COPYRIGHT.txt from the English Speller Database.
# Run once: powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build-wordlist.ps1"
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $root 'shared\wordlists'
$url = 'https://app.aspell.net/create?max_size=60&spelling=US&max_variant=0&diacritic=strip&download=wordlist&encoding=utf-8&format=inline'
$download = Join-Path ([System.IO.Path]::GetTempPath()) 'gibberish-rewriter-esdb.txt'

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $download
$lines = [System.IO.File]::ReadAllLines($download, [System.Text.Encoding]::UTF8)
Remove-Item -LiteralPath $download

# The download is a licence notice, a line holding only '---', then one word per line.
$separator = [Array]::IndexOf($lines, '---')
if ($separator -lt 1) { throw "No '---' line in the download; the ESDB format has changed." }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$notice = (($lines[0..($separator - 1)]) -join "`n").TrimEnd() + "`n"
[System.IO.File]::WriteAllText((Join-Path $outDir 'ESDB-COPYRIGHT.txt'), $notice, $utf8NoBom)

$words = New-Object 'System.Collections.Generic.SortedSet[string]' -ArgumentList ([System.StringComparer]::Ordinal)
foreach ($line in $lines[($separator + 1)..($lines.Length - 1)]) {
    $word = $line.Trim().ToLowerInvariant()
    if ($word.Length -gt 0) { [void]$words.Add($word) }
}
[System.IO.File]::WriteAllText((Join-Path $outDir 'english.txt'), (($words -join "`n") + "`n"), $utf8NoBom)

Write-Output "Wrote $($words.Count) words to $(Join-Path $outDir 'english.txt')"
