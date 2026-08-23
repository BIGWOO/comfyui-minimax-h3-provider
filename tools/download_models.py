from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from pathlib import Path, PurePosixPath

from huggingface_hub import hf_hub_download


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def _partial_bytes(models_root: Path, model: dict) -> int:
    repo_path = PurePosixPath(str(model["repo_path"]))
    download_root = models_root / ".cache" / "huggingface" / "download"
    partial_dir = download_root.joinpath(*repo_path.parent.parts)
    if not partial_dir.is_dir():
        return 0
    sizes = (_safe_file_size(path) for path in partial_dir.glob(f"{repo_path.name}.*.incomplete"))
    return min(max(sizes, default=0), int(model["size"]))


def transferred_bytes(
    models_root: Path,
    selected: list[dict],
    completed_paths: set[str],
    active_paths: set[str] | None = None,
) -> int:
    transferred = 0
    for model in selected:
        relative_path = str(model["relative_path"])
        size = int(model["size"])
        if relative_path in completed_paths:
            transferred += size
        elif active_paths is None or relative_path in active_paths:
            transferred += _partial_bytes(models_root, model)
    return min(sum(int(model["size"]) for model in selected), transferred)


def progress_payload(current: int, total: int, elapsed_seconds: float) -> dict:
    return {
        "event": "model-download-progress",
        "downloaded_gb": round(current / 1024**3, 2),
        "total_gb": round(total / 1024**3, 2),
        "percent": round(current * 100 / total, 1),
        "elapsed_seconds": round(elapsed_seconds),
    }


def report_progress(
    models_root: Path,
    selected: list[dict],
    completed_paths: set[str],
    active_paths: set[str],
    progress_lock: threading.Lock,
    stop: threading.Event,
    started: float,
) -> None:
    total = sum(int(model["size"]) for model in selected)
    while not stop.wait(10):
        now = time.monotonic()
        with progress_lock:
            completed_snapshot = set(completed_paths)
            active_snapshot = set(active_paths)
        current = transferred_bytes(models_root, selected, completed_snapshot, active_snapshot)
        print(json.dumps(progress_payload(current, total, now - started)), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--pack", choices=("all", "creator", "fl2va", "ref2va", "shared", "turbo"), default="creator")
    parser.add_argument("--skip-hash", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    models_root = root / "models"
    manifest = json.loads((root / "profiles/minimax-h3/models.json").read_text(encoding="utf-8"))
    selected = [model for model in manifest["models"] if args.pack in model["packs"]]
    if not selected:
        raise RuntimeError(f"No models found for pack {args.pack!r}")

    completed_paths: set[str] = set()
    active_paths: set[str] = set()
    progress_lock = threading.Lock()
    stop = threading.Event()
    progress_started = time.monotonic()
    monitor = threading.Thread(
        target=report_progress,
        args=(models_root, selected, completed_paths, active_paths, progress_lock, stop, progress_started),
        daemon=True,
    )
    monitor.start()
    try:
        for model in selected:
            target = models_root / model["relative_path"]
            valid_size = target.is_file() and target.stat().st_size == int(model["size"])
            if valid_size and not args.skip_hash:
                print(f"Verifying SHA-256: {model['relative_path']}", flush=True)
            valid_hash = valid_size and (args.skip_hash or sha256(target) == model["sha256"])
            if valid_hash:
                with progress_lock:
                    completed_paths.add(str(model["relative_path"]))
                print(f"Verified: {model['relative_path']}", flush=True)
                continue

            force = target.exists() and not valid_hash
            target.parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading: {model['repo_id']}/{model['repo_path']}", flush=True)
            relative_path = str(model["relative_path"])
            with progress_lock:
                active_paths.add(relative_path)
            try:
                hf_hub_download(
                    repo_id=model["repo_id"],
                    filename=model["repo_path"],
                    local_dir=models_root,
                    force_download=force,
                )
                if target.stat().st_size != int(model["size"]):
                    raise RuntimeError(f"Size mismatch after download: {target}")
                with progress_lock:
                    completed_paths.add(relative_path)
            finally:
                with progress_lock:
                    active_paths.discard(relative_path)
            if not args.skip_hash:
                print(f"Verifying SHA-256: {model['relative_path']}", flush=True)
                if sha256(target) != model["sha256"]:
                    raise RuntimeError(f"SHA-256 mismatch after download: {target}")
            print(f"Downloaded and verified: {model['relative_path']}", flush=True)
    finally:
        stop.set()
        monitor.join(timeout=1)

    total = sum(int(model["size"]) for model in selected)
    with progress_lock:
        final_completed = set(completed_paths)
    final_bytes = transferred_bytes(models_root, selected, final_completed, set())
    print(json.dumps(progress_payload(final_bytes, total, time.monotonic() - progress_started)), flush=True)
    print(f"Model pack complete: {args.pack}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
