[CmdletBinding()]
param(
    [ValidateSet('main', 'safe', 'novram')]
    [string]$Profile = 'main',
    [int]$Port = 8188,
    [string]$Listen = '127.0.0.1',
    [switch]$Background
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
$main = Join-Path $projectRoot 'runtime\ComfyUI\main.py'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $main)) {
    throw 'Runtime is not installed. Run scripts\setup.ps1 first.'
}

@('data\input', 'data\output', 'data\temp', 'data\user', 'logs', 'state') | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $_) | Out-Null
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owners = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw "Port $Port is already in use by process $owners. Stop it or choose another port."
}

$reserve = if ($Profile -eq 'main') { '2' } else { '3' }
$databasePath = (Join-Path $projectRoot 'data\user\comfyui.db') -replace '\\', '/'
$databaseUrl = "sqlite:///$databasePath"
$args = @(
    $main,
    '--listen', $Listen,
    '--port', "$Port",
    '--models-directory', (Join-Path $projectRoot 'models'),
    '--input-directory', (Join-Path $projectRoot 'data\input'),
    '--output-directory', (Join-Path $projectRoot 'data\output'),
    '--temp-directory', (Join-Path $projectRoot 'data\temp'),
    '--user-directory', (Join-Path $projectRoot 'data\user'),
    '--database-url', $databaseUrl,
    '--reserve-vram', $reserve,
    '--enable-dynamic-vram',
    '--async-offload',
    '--fast-disk',
    '--disable-pinned-memory',
    '--enable-manager'
)

if ($Profile -in @('safe', 'novram')) {
    $args += '--cache-none'
}
if ($Profile -eq 'novram') {
    $args += '--novram'
}

$log = Join-Path $projectRoot ("logs\comfyui-{0}-{1}.log" -f $Profile, (Get-Date -Format 'yyyyMMdd-HHmmss'))
$args += @('--verbose', 'INFO', $log)
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
$env:CUDA_DEVICE_ORDER = 'PCI_BUS_ID'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "Starting ComfyUI ($Profile) at http://${Listen}:$Port"
if ($Background) {
    $argumentLine = ($args | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }) -join ' '
    $process = Start-Process -FilePath $python -ArgumentList $argumentLine -WindowStyle Hidden -PassThru
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'state') | Out-Null
    Set-Content -LiteralPath (Join-Path $projectRoot 'state\comfyui.pid') -Value $process.Id -Encoding ascii
    Write-Host "Started ComfyUI process $($process.Id)"
    exit 0
}
& $python @args
exit $LASTEXITCODE
