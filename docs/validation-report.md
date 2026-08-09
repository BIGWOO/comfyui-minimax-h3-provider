# MiniMax H3 local validation report

Validated on 2026-08-10 with an NVIDIA GeForce RTX 3090 24 GB, 32 GB RAM,
Python 3.12, PyTorch 2.13.0+cu130, and ComfyUI 0.31.0.

## Environment

- CUDA was available and the GPU was identified correctly.
- `/system_stats` and `/object_info` responded successfully.
- AIMixer Director and MiniMax H3 FirstBlockCache registered successfully.
- All six model files matched their pinned byte sizes and SHA-256 values.
- The six upstream FirstBlockCache unit tests passed.

## Director smoke tests

All tests used 512 x 288 and 39 frames. Every case produced an MP4 with video,
stereo audio, the expected frame count, and a successful Director execution
report.

| Mode | Result | End-to-end time |
| --- | --- | ---: |
| T2V | Passed | 25.39 s |
| I2V | Passed | 25.61 s |
| FL2V | Passed | 25.50 s |
| R2V | Passed | 25.69 s |
| V2V | Passed | 30.50 s |
| RV2V | Passed | 30.48 s |
| FL2VA Turbo, 4 steps | Passed | 25.42 s |

## Performance gate

The comparison used the same prompt and seed at 640 x 352, 56 frames. Quality
runs used 20 steps; Turbo used 4 steps.

| Configuration | End-to-end time | Relative to baseline |
| --- | ---: | ---: |
| No cache | 45.813 s | Baseline |
| FirstBlockCache Safe | 35.485 s | 22.54% faster |
| FirstBlockCache Fast | 35.547 s | 22.41% faster |
| Turbo LoRA, 4 steps | 25.422 s | 44.51% faster |

Representative frames from Baseline, Safe, and Fast retained the same subject
and composition without obvious cache corruption. Fast passed the required 10%
gate, so it is the default in both quality workflows. Turbo remains a separate
FL2VA-only draft workflow and does not stack with FirstBlockCache.

## Final acceptance run

The final FL2VA Fast test completed without an out-of-memory retry:

- 864 x 480
- 124 frames at 24 fps (5.17 seconds)
- 25 steps
- stereo audio at 32 kHz
- 182.75 seconds end-to-end
- 22,999 MiB observed peak VRAM reading

Generated outputs and raw machine reports are intentionally ignored by Git.
Re-run `scripts\benchmark.ps1` to regenerate them.
