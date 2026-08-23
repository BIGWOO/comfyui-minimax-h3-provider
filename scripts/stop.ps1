[CmdletBinding()]
param(
    [int]$Port = 8188
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$expectedMain = (Join-Path $projectRoot 'runtime\ComfyUI\main.py').ToLowerInvariant()
$pidFile = Join-Path $projectRoot 'state\comfyui.pid'
$listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)

if ($listeners.Count -eq 0) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "No ComfyUI listener found at 127.0.0.1:$Port"
    exit 0
}

foreach ($processId in ($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
    $commandLine = [string]$process.CommandLine
    if (-not $commandLine.ToLowerInvariant().Contains($expectedMain)) {
        throw "Process $processId owns port $Port but is not this project's ComfyUI; refusing to stop it."
    }

    Stop-Process -Id $processId
    Wait-Process -Id $processId -Timeout 15 -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped ComfyUI process $processId at 127.0.0.1:$Port"
}
