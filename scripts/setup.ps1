[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$lockPath = Join-Path $projectRoot 'profiles\minimax-h3\versions.lock.json'
$lock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

function Sync-Repository {
    param($Repository)
    $target = Join-Path $projectRoot $Repository.target
    if (-not (Test-Path -LiteralPath (Join-Path $target '.git'))) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Invoke-Checked git @('clone', '--filter=blob:none', $Repository.url, $target)
    }
    Invoke-Checked git @('-C', $target, 'fetch', '--quiet', 'origin', $Repository.commit)
    Invoke-Checked git @('-C', $target, '-c', 'advice.detachedHead=false', 'checkout', '--force', $Repository.commit)
    $actual = (& git -C $target rev-parse HEAD).Trim()
    if ($actual -ne $Repository.commit) {
        throw "Commit mismatch for $($Repository.name): $actual"
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required but was not found in PATH.'
}

foreach ($repo in $lock.repositories) {
    Sync-Repository $repo
}

$venv = Join-Path $projectRoot '.venvs\main'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Invoke-Checked uv @('venv', '--python', $lock.python, $venv)
}

Invoke-Checked uv (@('pip', 'install', '--python', $python, '--index-url', $lock.torch_index) + @($lock.torch_packages))

$comfy = Join-Path $projectRoot 'runtime\ComfyUI'
$pythonLock = Join-Path $projectRoot 'profiles\minimax-h3\python.lock.txt'
if (Test-Path -LiteralPath $pythonLock) {
    Invoke-Checked uv @('pip', 'install', '--python', $python, '-r', $pythonLock)
} else {
    Invoke-Checked uv @('pip', 'install', '--python', $python, '-r', (Join-Path $comfy 'requirements.txt'))

    $managerRequirements = Join-Path $comfy 'manager_requirements.txt'
    if (Test-Path -LiteralPath $managerRequirements) {
        Invoke-Checked uv @('pip', 'install', '--python', $python, '-r', $managerRequirements)
    }

    $directorRequirements = Join-Path $comfy 'custom_nodes\ComfyUI_MiniMaxH3_Director\requirements.txt'
    Invoke-Checked uv @('pip', 'install', '--python', $python, '-r', $directorRequirements)
    Invoke-Checked uv @('pip', 'install', '--python', $python, 'huggingface_hub', 'httpx', 'pytest')
}

$state = Join-Path $projectRoot 'state'
New-Item -ItemType Directory -Force -Path $state | Out-Null
& uv pip freeze --python $python | Set-Content -LiteralPath (Join-Path $state 'resolved-packages.txt') -Encoding utf8

Invoke-Checked $python @('-c', 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))')
Write-Host "Setup complete: $projectRoot"
