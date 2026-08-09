# ComfyUI Local

Windows-native ComfyUI manager project for MiniMax H3 and future image/video model profiles.

## Hardware profile

- NVIDIA GeForce RTX 3090 24 GB
- 32 GB system RAM
- NVMe project/model storage
- Windows-managed page file

## Quick start

Run these commands in PowerShell from this directory:

```powershell
.\scripts\setup.ps1
.\scripts\download-models.ps1 -Pack all
.\scripts\start.ps1 -Profile main
```

In a second PowerShell window:

```powershell
.\scripts\verify.ps1
.\scripts\build-workflows.ps1
```

Stop the project-owned server safely with:

```powershell
.\scripts\stop.ps1
```

User workflows are written to `workflows\minimax-h3`. Models, runtime code,
virtual environments, generated media, and logs are intentionally excluded
from the manager repository.

## Launch profiles

- `main`: Dynamic VRAM, async offload, 2 GB VRAM reserve, NVMe-backed offload.
- `safe`: Dynamic VRAM, 3 GB reserve, ComfyUI execution cache disabled.
- `novram`: Emergency fallback with aggressive offload; substantially slower.

ComfyUI listens only on `127.0.0.1:8188`.

## Validated on this machine

- Six Director modes passed: T2V, I2V, FL2V, R2V, V2V, and RV2V.
- At 640 x 352, 56 frames, and 20 steps, FirstBlockCache Fast reduced the
  measured end-to-end time from 45.81 s to 35.55 s (22.41%).
- The 4-step Turbo draft completed in 25.42 s and remains FL2VA-only.
- The final FL2VA Fast run produced 124 frames at 864 x 480 with stereo audio
  in 182.75 s, without an out-of-memory retry.

## MiniMax H3 workflow roles

- `director-fl2va-quality-fbc.json`: T2V/I2V/FL2V, 25 steps, FirstBlockCache Fast.
- `director-fl2va-turbo-draft.json`: T2V/I2V/FL2V draft, 4 steps, Kijai LoRA 0.75, no FBC.
- `director-ref2va-quality-fbc.json`: R2V/V2V/RV2V, 25 steps, FirstBlockCache Fast (promoted after local A/B validation).

Do not combine FirstBlockCache with EasyCache, CacheDiT, T8 Block Cache, or
another DiT block replacement. SageAttention is not installed by this profile.

## Reproducibility

`profiles\minimax-h3\versions.lock.json` pins every source repository commit
and CUDA PyTorch build. `profiles\minimax-h3\python.lock.txt` records the full
tested Python environment.
`profiles\minimax-h3\models.json` pins model paths, byte sizes, and Hugging Face
LFS SHA-256 values. `setup.ps1` and `download-models.ps1` are idempotent.

The model weights are governed by the MiniMax H3 community license and the
licenses shown in their Hugging Face repositories.
