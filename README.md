# MiniMax H3 ComfyUI Provider

Reproducible MiniMax H3 runtime for Creator IP Studio and direct ComfyUI use.
It pins ComfyUI, Director, FirstBlockCache, Python packages, and every model
artifact instead of committing runtime code or model weights.

## Hardware and storage

- NVIDIA GPU with at least 24 GB VRAM is the validated baseline.
- 32 GB system RAM and a system-managed page file or swap are recommended.
- The default `creator` model pack needs about 43 GB; reserve at least 70 GB.
- The full FL2VA + Ref2VA pack is 63.8 GB; reserve at least 100 GB.

The validated machine is an RTX 3090 24 GB on Windows. Linux cloud GPU hosts
use the same version and model locks, but should still run the smoke test before
production work.

## Windows installation

Requirements: Git, PowerShell 7, `uv`, a current NVIDIA driver, and sufficient
free SSD/NVMe space. A system CUDA Toolkit is not required.

```powershell
git clone https://github.com/BIGWOO/comfyui-minimax-h3-provider.git
cd comfyui-minimax-h3-provider
./scripts/setup.ps1
./scripts/download-models.ps1 -Pack creator
./scripts/start.ps1 -Profile main -Background
./scripts/verify.ps1 -Pack creator
```

## Linux/cloud installation

Requirements: Git, Bash, Python 3, `uv`, a compatible NVIDIA driver, and a
working NVIDIA GPU assignment.

```bash
git clone https://github.com/BIGWOO/comfyui-minimax-h3-provider.git
cd comfyui-minimax-h3-provider
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/download-models.sh --pack creator
./scripts/start.sh --profile main --background
./scripts/verify.sh --pack creator
```

The secure default listens only on `127.0.0.1:8188`. On a private cloud network
you may pass `--host 0.0.0.0` on Linux or `-Listen 0.0.0.0` on Windows, but add
firewall and authentication controls before exposing it beyond the host.

## Model packs

| Pack | Contents | Approximate size |
| --- | --- | ---: |
| `creator` | FL2VA, shared encoders/VAEs, Turbo LoRA | 42.8 GB |
| `all` | Creator pack plus Ref2VA | 63.8 GB |
| `shared` | Text encoder and video/audio VAEs | 21.5 GB |
| `fl2va` | FL2VA diffusion model only | 21.0 GB |
| `ref2va` | Ref2VA diffusion model only | 21.0 GB |
| `turbo` | Four-step Turbo LoRA only | 0.3 GB |

Downloads resume through Hugging Face and are checked against pinned byte sizes
and SHA-256 hashes. Model and upstream licenses remain authoritative.

## Runtime profiles

- `main`: Dynamic VRAM, async offload, 2 GB reserve.
- `safe`: 3 GB reserve and disabled ComfyUI execution cache.
- `novram`: emergency aggressive offload; substantially slower.

FirstBlockCache Fast is the validated quality default. Turbo is a separate
four-step draft path and is not stacked with FirstBlockCache.

## Provider API

The service exposes the standard ComfyUI REST surface:

- `GET /system_stats`
- `GET /object_info`
- `POST /prompt`
- `GET /history/{prompt_id}`
- `GET /view`

Creator IP Studio checks it with:

```powershell
studio provider check minimax-h3
studio provider h3-generate --prompt "A cinematic studio shot" --preset draft
```

## One-prompt installation

Give a coding agent this prompt:

```text
Install the MiniMax H3 provider from:
https://github.com/BIGWOO/comfyui-minimax-h3-provider

Read README.md completely. Inspect the NVIDIA GPU, VRAM, RAM, free disk, Git,
Python, uv, and driver before changing anything. Use the creator model pack and
the secure localhost default. Ask before downloading the approximately 43 GB
model pack or changing firewall/system settings. Run setup, start the provider,
run verification with hashes, then use Creator IP Studio to run a 512x288,
39-frame Turbo draft smoke test with synthetic content. Return versions, GPU,
health result, prompt ID, generation time, and the absolute output path.
```

## Reproducibility and validation

- `profiles/minimax-h3/versions.lock.json` pins upstream Git commits and PyTorch.
- `profiles/minimax-h3/python.lock.txt` pins the tested Python environment.
- `profiles/minimax-h3/models.json` pins model paths, sizes, hashes, and packs.
- `state/inventory.json` records the live node/API inventory after verification.

Local validation covered T2V, I2V, FL2V, R2V, V2V, and RV2V. The 864x480,
124-frame, 25-step FL2VA acceptance run completed in 182.75 seconds with a
22,999 MiB peak VRAM reading. See `docs/validation-report.md` for details.

## Safety and licensing

Keep the API private, use only media you are authorized to process, and review
the MiniMax H3, ComfyUI, Director, FirstBlockCache, and model repository terms
before teaching, redistributing, or using generated media commercially.

This repository's original scripts and documentation are Apache-2.0 licensed.
Third-party components and model weights retain their own terms.
