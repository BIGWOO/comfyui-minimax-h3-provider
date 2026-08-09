[CmdletBinding()]
param(
    [string]$Url = 'http://127.0.0.1:8188',
    [ValidateSet('smoke', 'benchmark', 'final', 'all')]
    [string]$Suite = 'benchmark',
    [string]$Case
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
$args = @((Join-Path $projectRoot 'tools\benchmark.py'), '--project-root', $projectRoot, '--url', $Url, '--suite', $Suite)
if ($Case) { $args += @('--case', $Case) }
& $python @args
exit $LASTEXITCODE
