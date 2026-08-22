from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    for model in selected:
        target = models_root / model["relative_path"]
        valid_size = target.is_file() and target.stat().st_size == int(model["size"])
        valid_hash = valid_size and (args.skip_hash or sha256(target) == model["sha256"])
        if valid_hash:
            print(f"Verified: {model['relative_path']}")
            continue

        force = target.exists() and not valid_hash
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading: {model['repo_id']}/{model['repo_path']}")
        hf_hub_download(
            repo_id=model["repo_id"],
            filename=model["repo_path"],
            local_dir=models_root,
            force_download=force,
        )
        if target.stat().st_size != int(model["size"]):
            raise RuntimeError(f"Size mismatch after download: {target}")
        if not args.skip_hash and sha256(target) != model["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch after download: {target}")
        print(f"Downloaded and verified: {model['relative_path']}")

    print(f"Model pack complete: {args.pack}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
