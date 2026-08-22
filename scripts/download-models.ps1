[CmdletBinding()]
param(
    [ValidateSet('all', 'creator', 'fl2va', 'ref2va', 'shared', 'turbo')]
    [string]$Pack = 'creator',
    [switch]$SkipHash
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Runtime is not installed. Run scripts\setup.ps1 first.'
}
$arguments = @((Join-Path $projectRoot 'tools\download_models.py'), '--project-root', $projectRoot, '--pack', $Pack)
if ($SkipHash) { $arguments += '--skip-hash' }
$env:HF_HUB_DISABLE_TELEMETRY = '1'
& $python @arguments
exit $LASTEXITCODE
