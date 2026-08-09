[CmdletBinding()]
param(
    [string]$Url = 'http://127.0.0.1:8188'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
& $python (Join-Path $projectRoot 'tools\build_workflows.py') --project-root $projectRoot --url $Url
exit $LASTEXITCODE
