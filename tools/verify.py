from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
import torch


REQUIRED_NODES = {
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "LoraLoaderModelOnly",
    "MiniMaxH3Director",
    "ApplyMiniMaxH3FirstBlockCache",
    "CreateVideo",
    "SaveVideo",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    parser.add_argument("--skip-hashes", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    versions = json.loads((root / "profiles/minimax-h3/versions.lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "profiles/minimax-h3/models.json").read_text(encoding="utf-8"))
    report: dict[str, object] = {"ok": True, "checks": [], "models": [], "online": False}

    def check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    check("torch.cuda", torch.cuda.is_available(), f"torch={torch.__version__} cuda={torch.version.cuda}")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unavailable"
    check("gpu", "RTX 3090" in gpu_name, gpu_name)

    for repo in versions["repositories"]:
        target = root / repo["target"]
        try:
            actual = git_head(target)
        except Exception as exc:  # noqa: BLE001
            actual = f"error: {exc}"
        check(f"repo:{repo['name']}", actual == repo["commit"], str(actual))

    for model in manifest["models"]:
        path = root / "models" / model["relative_path"]
        exists = path.exists()
        size_ok = exists and path.stat().st_size == int(model["size"])
        hash_value = None
        hash_ok = size_ok
        if size_ok and not args.skip_hashes:
            hash_value = sha256(path)
            hash_ok = hash_value == model["sha256"]
        item = {
            "path": model["relative_path"],
            "exists": exists,
            "size_ok": size_ok,
            "hash_checked": not args.skip_hashes,
            "hash_ok": hash_ok,
            "actual_sha256": hash_value,
        }
        report["models"].append(item)
        check(f"model:{model['relative_path']}", bool(size_ok and hash_ok), json.dumps(item, ensure_ascii=False))

    try:
        with httpx.Client(timeout=30) as client:
            system = client.get(f"{args.url}/system_stats").raise_for_status().json()
            object_info = client.get(f"{args.url}/object_info").raise_for_status().json()
        report["online"] = True
        report["system"] = system
        missing = sorted(REQUIRED_NODES - set(object_info))
        check("api:required_nodes", not missing, f"missing={missing}")
        inventory = {
            "system": system,
            "nodes": sorted(object_info),
            "object_info": object_info,
            "models": [m["relative_path"] for m in manifest["models"] if (root / "models" / m["relative_path"]).exists()],
        }
        (state / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        check("api", False, f"ComfyUI unavailable: {exc}")

    (state / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
