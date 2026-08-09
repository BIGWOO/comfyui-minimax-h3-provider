[CmdletBinding()]
param(
    [ValidateSet('all', 'fl2va', 'ref2va', 'shared', 'turbo')]
    [string]$Pack = 'all',
    [switch]$SkipHash
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifest = Get-Content -Raw -LiteralPath (Join-Path $projectRoot 'profiles\minimax-h3\models.json') | ConvertFrom-Json
$python = Join-Path $projectRoot '.venvs\main\Scripts\python.exe'
$hf = Join-Path $projectRoot '.venvs\main\Scripts\hf.exe'
$modelsRoot = Join-Path $projectRoot 'models'

if (-not (Test-Path -LiteralPath $hf)) {
    throw 'Hugging Face CLI is missing. Run scripts\setup.ps1 first.'
}

$env:HF_HUB_DISABLE_TELEMETRY = '1'
$selected = @($manifest.models | Where-Object { $_.packs -contains $Pack })
if ($selected.Count -eq 0) {
    throw "No models found for pack '$Pack'."
}

foreach ($model in $selected) {
    $target = Join-Path $modelsRoot ($model.relative_path -replace '/', '\')
    $valid = $false
    $forceDownload = $false
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target
        $valid = $item.Length -eq [int64]$model.size
        if ($valid -and -not $SkipHash) {
            $valid = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant() -eq $model.sha256
            $forceDownload = -not $valid
        }
    }
    if ($valid) {
        Write-Host "Verified: $($model.relative_path)"
        continue
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    $downloadArgs = @('download', $model.repo_id, $model.repo_path, '--local-dir', $modelsRoot)
    if ($forceDownload) {
        Write-Warning "Hash mismatch; forcing a clean Hugging Face repair: $($model.relative_path)"
        $downloadArgs += '--force-download'
    } elseif (Test-Path -LiteralPath $target) {
        Write-Host "Resuming or repairing incomplete model: $($model.relative_path)"
    }
    & $hf @downloadArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $($model.repo_id)/$($model.repo_path)"
    }
    $item = Get-Item -LiteralPath $target
    if ($item.Length -ne [int64]$model.size) {
        throw "Size mismatch after download: $target"
    }
    if (-not $SkipHash) {
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        if ($actualHash -ne $model.sha256) {
            throw "SHA-256 mismatch after download: $target"
        }
    }
    Write-Host "Downloaded and verified: $($model.relative_path)"
}

Write-Host "Model pack complete: $Pack"
