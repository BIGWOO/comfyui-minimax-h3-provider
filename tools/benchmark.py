from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image, ImageDraw


TASK_LABELS = {
    "t2v": "t2v — 文生视频(Text to Video)",
    "i2v": "i2v — 图生视频(Image to Video)",
    "fl2v": "fl2v — 首尾帧生视频(First-Last Frame)",
    "r2v": "r2v — 参考主体生视频(Reference to Video)",
    "v2v": "v2v — 视频转视频(Video to Video)",
    "rv2v": "rv2v — 参考素材改视频(Reference Video Edit)",
}

MODELS = {
    "fl2va": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "video_vae": "minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
    "turbo": "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors",
}

PROMPTS = {
    "t2v": "A small red robot walks across a clean studio floor, steady camera, natural footsteps and quiet room ambience. No text or logo.",
    "i2v": "The illustrated subject takes two calm steps forward while the camera remains steady. Preserve appearance. Natural ambience.",
    "fl2v": "Smooth natural movement between the supplied first and last frames. Preserve subject, colors and framing. Soft ambience.",
    "r2v": "<Picture 1> walks slowly across a clean studio floor. Keep identity, colors and outfit from <Picture 1>. Natural ambience.",
    "v2v": "Keep the scene and motion from <Video 1>. Apply a gentle cinematic relight while preserving framing. Keep original timing.",
    "rv2v": "Replace the central subject in <Video 1> with <Picture 1>. Preserve camera motion and scene layout. Match the reference appearance.",
}


def create_test_assets(root: Path) -> None:
    target = root / "data/input"
    target.mkdir(parents=True, exist_ok=True)
    width, height = 512, 288

    def card(path: Path, *, x: int, color: tuple[int, int, int], label: str) -> None:
        image = Image.new("RGB", (width, height), (28, 32, 40))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            shade = int(28 + 36 * y / height)
            draw.line((0, y, width, y), fill=(shade, shade + 4, shade + 12))
        draw.rectangle((x - 35, 90, x + 35, 230), fill=color)
        draw.ellipse((x - 28, 42, x + 28, 98), fill=(230, 205, 178))
        draw.line((40, 246, width - 40, 246), fill=(160, 165, 175), width=3)
        draw.text((16, 16), label, fill=(240, 240, 245))
        image.save(path)

    card(target / "smoke-first.png", x=150, color=(180, 45, 45), label="MiniMax H3 smoke test - FIRST")
    card(target / "smoke-last.png", x=360, color=(180, 45, 45), label="MiniMax H3 smoke test - LAST")
    card(target / "smoke-reference.png", x=256, color=(45, 100, 190), label="MiniMax H3 smoke test - REFERENCE")

    wav_path = target / "smoke-tone.wav"
    sample_rate = 24000
    duration = 39 / 24
    frames = int(sample_rate * duration)
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        data = bytearray()
        for i in range(frames):
            value = int(2200 * math.sin(2 * math.pi * 440 * i / sample_rate))
            data += int(value).to_bytes(2, "little", signed=True)
        handle.writeframes(bytes(data))

    video_path = target / "smoke-source.mp4"
    if not video_path.exists():
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=512x288:rate=24",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=24000",
                "-frames:v",
                "39",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-y",
                str(video_path),
            ],
            check=True,
        )


def timeline(task: str, *, width: int, height: int, frames: int, prompt: str) -> str:
    base = {
        "version": 4,
        "editMode": "global",
        "timelineMode": "gen_blank",
        "totalFrames": frames,
        "frameRate": 24.0,
        "width": width,
        "height": height,
        "refMaxSize": max(width, height),
        "output": {
            "mode": "fixed",
            "longEdge": max(width, height),
            "width": width,
            "height": height,
            "maxExportFrames": 0,
            "exportMode": "all",
            "audioMode": "generate",
            "continuityEnabled": False,
            "continuityOverlapFrames": 9,
        },
        "videoClips": [],
        "video": {"fileName": "", "videoFile": "", "subfolder": "", "type": "input", "frames": [], "frameMap": []},
        "global": {
            "taskType": TASK_LABELS[task],
            "prompt": prompt,
            "refs": [],
            "referenceVideo": {},
            "continuousReference": False,
            "genImage": {"imageFile": ""},
        },
        "segments": [{"id": "s0", "start": 0, "length": frames, "frameCount": frames, "prompt": "", "taskType": "", "refs": [], "referenceVideo": {}}],
        "runSelectEnabled": False,
        "runSelection": [],
    }
    if task == "i2v":
        base["timelineMode"] = "gen_image"
        base["global"]["genImage"] = {"imageFile": "smoke-first.png", "width": 512, "height": 288}
        base["segments"][0]["genImage"] = {"imageFile": "smoke-first.png", "width": 512, "height": 288}
    elif task == "fl2v":
        base["timelineMode"] = "fl2v"
        base["shots"] = [
            {
                "id": "shot0",
                "startImage": {"imageFile": "smoke-first.png", "width": 512, "height": 288},
                "endImage": {"imageFile": "smoke-last.png", "width": 512, "height": 288},
                "durationSec": frames / 24,
                "prompt": prompt,
                "negativePrompt": "bad video",
            }
        ]
    elif task == "r2v":
        base["global"]["refs"] = [{"index": 0, "imageFile": "smoke-reference.png"}]
    elif task in {"v2v", "rv2v"}:
        base["timelineMode"] = "video"
        base["video"] = {"fileName": "smoke-source.mp4", "videoFile": "smoke-source.mp4", "subfolder": "", "type": "input", "frames": [], "frameMap": []}
        if task == "rv2v":
            base["global"]["refs"] = [{"index": 0, "imageFile": "smoke-reference.png"}]
    return json.dumps(base, ensure_ascii=False)


def allowed_inputs(object_info: dict, node_type: str) -> set[str]:
    spec = object_info[node_type].get("input", {})
    return set(spec.get("required", {})) | set(spec.get("optional", {})) | set(spec.get("hidden", {}))


def default_inputs(object_info: dict, node_type: str) -> dict:
    result: dict = {}
    spec = object_info[node_type].get("input", {})
    for section in ("required", "optional"):
        for name, schema in spec.get(section, {}).items():
            if not isinstance(schema, list) or not schema:
                continue
            kind = schema[0]
            meta = schema[1] if len(schema) > 1 and isinstance(schema[1], dict) else {}
            if "default" in meta:
                result[name] = meta["default"]
            elif isinstance(kind, list) and kind:
                result[name] = kind[0]
    return result


def filtered(object_info: dict, node_type: str, values: dict) -> dict:
    allowed = allowed_inputs(object_info, node_type)
    base = default_inputs(object_info, node_type)
    base.update({key: value for key, value in values.items() if key in allowed})
    return base


def api_workflow(
    object_info: dict,
    *,
    task: str,
    width: int,
    height: int,
    frames: int,
    steps: int,
    cache_mode: str | None,
    turbo: bool,
    prefix: str,
) -> dict:
    ref_family = task in {"r2v", "v2v", "rv2v"}
    model_name = MODELS["ref2va" if ref_family else "fl2va"]
    prompt: dict[str, dict] = {
        "1": {"class_type": "UNETLoader", "inputs": filtered(object_info, "UNETLoader", {"unet_name": model_name, "weight_dtype": "default"})},
        "2": {"class_type": "CLIPLoader", "inputs": filtered(object_info, "CLIPLoader", {"clip_name": MODELS["text"], "type": "minimax", "device": "default"})},
        "3": {"class_type": "VAELoader", "inputs": filtered(object_info, "VAELoader", {"vae_name": MODELS["video_vae"]})},
        "4": {"class_type": "VAELoader", "inputs": filtered(object_info, "VAELoader", {"vae_name": MODELS["audio_vae"]})},
    }
    model_ref: list = ["1", 0]
    next_id = 5
    if cache_mode:
        prompt[str(next_id)] = {
            "class_type": "ApplyMiniMaxH3FirstBlockCache",
            "inputs": filtered(
                object_info,
                "ApplyMiniMaxH3FirstBlockCache",
                {
                    "model": model_ref,
                    "mode": cache_mode,
                    "threshold": 0.10,
                    "start_percent": 0.10,
                    "end_percent": 0.95,
                    "max_consecutive_hits": 2,
                    "temporal_guard": False,
                },
            ),
        }
        model_ref = [str(next_id), 0]
        next_id += 1
    if turbo:
        prompt[str(next_id)] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": filtered(object_info, "LoraLoaderModelOnly", {"model": model_ref, "lora_name": MODELS["turbo"], "strength_model": 0.75}),
        }
        model_ref = [str(next_id), 0]
        next_id += 1

    director_id = str(next_id)
    director_values = {
        "model": model_ref,
        "video_vae": ["3", 0],
        "audio_vae": ["4", 0],
        "clip": ["2", 0],
        "task_type": TASK_LABELS[task],
        "global_prompt": PROMPTS[task],
        "cfg": 1.0,
        "seed": 424242,
        "frame_rate": 24.0,
        "width": width,
        "height": height,
        "ref_max_size": max(width, height),
        "total_frames": frames,
        "timeline_data": timeline(task, width=width, height=height, frames=frames, prompt=PROMPTS[task]),
        "steps": steps,
        "sampler": "er_sde" if turbo else "res_multistep",
        "scheduler": "simple",
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "clear_vram_between_segments": True,
        "export_source_images": False,
    }
    prompt[director_id] = {"class_type": "MiniMaxH3Director", "inputs": filtered(object_info, "MiniMaxH3Director", director_values)}
    next_id += 1

    create_id = str(next_id)
    prompt[create_id] = {
        "class_type": "CreateVideo",
        "inputs": filtered(object_info, "CreateVideo", {"images": [director_id, 0], "fps": [director_id, 2], "audio": [director_id, 1]}),
    }
    next_id += 1
    save_id = str(next_id)
    prompt[save_id] = {
        "class_type": "SaveVideo",
        "inputs": filtered(object_info, "SaveVideo", {"video": [create_id, 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}),
    }
    return prompt


def gpu_memory_mib() -> int | None:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
            timeout=10,
        )
        return int(output.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None


def run_prompt(client: httpx.Client, url: str, workflow: dict, *, timeout_seconds: int = 10800) -> dict:
    queued = client.post(f"{url}/prompt", json={"prompt": workflow, "client_id": "comfyui-local-benchmark"})
    queued.raise_for_status()
    prompt_id = queued.json()["prompt_id"]
    started = time.monotonic()
    peak_vram = gpu_memory_mib()
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Prompt {prompt_id} exceeded {timeout_seconds}s")
        history = client.get(f"{url}/history/{prompt_id}").json()
        current = gpu_memory_mib()
        if current is not None:
            peak_vram = max(peak_vram or current, current)
        if prompt_id in history:
            item = history[prompt_id]
            return {"prompt_id": prompt_id, "seconds": elapsed, "peak_vram_mib": peak_vram, "history": item}
        time.sleep(5)


def cases_for_suite(suite: str) -> list[dict]:
    smoke = [
        {"name": f"smoke-{task}", "task": task, "width": 512, "height": 288, "frames": 39, "steps": 8, "cache": "H3 Safe — 0.08 / max 2", "turbo": False}
        for task in ("t2v", "i2v", "fl2v", "r2v", "v2v", "rv2v")
    ]
    smoke.append({"name": "smoke-turbo", "task": "t2v", "width": 512, "height": 288, "frames": 39, "steps": 4, "cache": None, "turbo": True})
    benchmark = [
        {"name": "benchmark-baseline", "task": "t2v", "width": 640, "height": 352, "frames": 56, "steps": 20, "cache": None, "turbo": False},
        {"name": "benchmark-safe", "task": "t2v", "width": 640, "height": 352, "frames": 56, "steps": 20, "cache": "H3 Safe — 0.08 / max 2", "turbo": False},
        {"name": "benchmark-fast", "task": "t2v", "width": 640, "height": 352, "frames": 56, "steps": 20, "cache": "H3 Fast — 0.10 / max 2", "turbo": False},
        {"name": "benchmark-turbo", "task": "t2v", "width": 640, "height": 352, "frames": 56, "steps": 4, "cache": None, "turbo": True},
    ]
    final = [{"name": "final-fl2va-fast", "task": "t2v", "width": 864, "height": 480, "frames": 124, "steps": 25, "cache": "H3 Fast — 0.10 / max 2", "turbo": False}]
    return {"smoke": smoke, "benchmark": benchmark, "final": final, "all": smoke + benchmark + final}[suite]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    parser.add_argument("--suite", choices=("smoke", "benchmark", "final", "all"), default="benchmark")
    parser.add_argument("--case", help="Run one named case from the selected suite")
    args = parser.parse_args()
    root = args.project_root.resolve()
    create_test_assets(root)
    with httpx.Client(timeout=30) as client:
        system = client.get(f"{args.url}/system_stats").raise_for_status().json()
        object_info = client.get(f"{args.url}/object_info").raise_for_status().json()
        required = {"UNETLoader", "CLIPLoader", "VAELoader", "LoraLoaderModelOnly", "MiniMaxH3Director", "ApplyMiniMaxH3FirstBlockCache", "CreateVideo", "SaveVideo"}
        missing = sorted(required - set(object_info))
        if missing:
            raise RuntimeError(f"Missing node types: {missing}")

        result = {"suite": args.suite, "started": datetime.now().isoformat(), "system": system, "cases": []}
        cases = cases_for_suite(args.suite)
        if args.case:
            cases = [case for case in cases if case["name"] == args.case]
            if not cases:
                raise ValueError(f"Unknown case for suite {args.suite}: {args.case}")
        for case in cases:
            prefix = f"minimax-h3-tests/{case['name']}"
            workflow = api_workflow(
                object_info,
                task=case["task"],
                width=case["width"],
                height=case["height"],
                frames=case["frames"],
                steps=case["steps"],
                cache_mode=case["cache"],
                turbo=case["turbo"],
                prefix=prefix,
            )
            (root / "tests/api_workflows").mkdir(parents=True, exist_ok=True)
            (root / "tests/api_workflows" / f"{case['name']}.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
            started = datetime.now().isoformat()
            try:
                run = run_prompt(client, args.url, workflow)
                status = run["history"].get("status", {})
                ok = bool(status.get("completed", status.get("status_str") == "success"))
                case_result = {**case, "started": started, "ok": ok, "seconds": run["seconds"], "peak_vram_mib": run["peak_vram_mib"], "prompt_id": run["prompt_id"], "outputs": run["history"].get("outputs", {}), "status": status}
            except Exception as exc:  # noqa: BLE001
                case_result = {**case, "started": started, "ok": False, "error": str(exc)}
            result["cases"].append(case_result)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            (root / "state" / f"benchmark-{args.suite}-{timestamp}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                client.post(f"{args.url}/free", json={"unload_models": True, "free_memory": True})
            except Exception:  # noqa: BLE001
                pass

    by_name = {case["name"]: case for case in result["cases"]}
    if "benchmark-baseline" in by_name and "benchmark-fast" in by_name and by_name["benchmark-baseline"].get("ok") and by_name["benchmark-fast"].get("ok"):
        baseline = by_name["benchmark-baseline"]["seconds"]
        fast = by_name["benchmark-fast"]["seconds"]
        result["fast_speedup_percent"] = round((baseline - fast) / baseline * 100, 2)
        result["fast_meets_10_percent"] = result["fast_speedup_percent"] >= 10

    result["completed"] = datetime.now().isoformat()
    output = root / "state" / f"benchmark-{args.suite}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(case.get("ok") for case in result["cases"]) else 1


if __name__ == "__main__":
    sys.exit(main())
