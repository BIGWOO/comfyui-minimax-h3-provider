[CmdletBinding()]
param(
    [string]$Url = 'http://127.0.0.1:8188',
    [ValidateSet('all', 'creator', 'fl2va', 'ref2va', 'shared', 'turbo')]
    [string]$Pack = 'creator',
    [switch]$SkipHashes
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Runtime is not installed. Run scripts\setup.ps1 first.'
}
$args = @((Join-Path $projectRoot 'tools\verify.py'), '--project-root', $projectRoot, '--url', $Url, '--pack', $Pack)
if ($SkipHashes) { $args += '--skip-hashes' }
& $python @args
exit $LASTEXITCODE
