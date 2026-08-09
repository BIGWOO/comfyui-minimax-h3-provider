from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import httpx


MODEL_FILES = {
    "fl2va": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "video_vae": "minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
    "turbo": "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors",
}


def fetch_inventory(root: Path, url: str) -> dict:
    with httpx.Client(timeout=30) as client:
        system = client.get(f"{url}/system_stats").raise_for_status().json()
        object_info = client.get(f"{url}/object_info").raise_for_status().json()
    inventory = {
        "system": system,
        "nodes": sorted(object_info),
        "object_info": object_info,
        "models": [],
    }
    manifest = json.loads((root / "profiles/minimax-h3/models.json").read_text(encoding="utf-8"))
    for model in manifest["models"]:
        if (root / "models" / model["relative_path"]).exists():
            inventory["models"].append(model["relative_path"])
    (root / "state/inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory


def find_node(workflow: dict, node_type: str) -> dict:
    matches = [node for node in workflow["nodes"] if node["type"] == node_type]
    if len(matches) != 1:
        raise ValueError(f"Expected one {node_type}, found {len(matches)}")
    return matches[0]


def find_link(workflow: dict, source_id: int, target_id: int) -> list:
    matches = [link for link in workflow["links"] if link[1] == source_id and link[3] == target_id and link[5] == "MODEL"]
    if len(matches) != 1:
        raise ValueError(f"Expected one MODEL link {source_id}->{target_id}, found {len(matches)}")
    return matches[0]


def insert_model_patch(workflow: dict, patch_type: str, widgets: list) -> None:
    loader = find_node(workflow, "UNETLoader")
    director = find_node(workflow, "MiniMaxH3Director")
    old_link = find_link(workflow, loader["id"], director["id"])
    old_link_id = old_link[0]
    workflow["links"].remove(old_link)

    node_id = max(node["id"] for node in workflow["nodes"]) + 1
    first_link_id = max(link[0] for link in workflow["links"]) + 1
    second_link_id = first_link_id + 1
    patch_node = {
        "id": node_id,
        "type": patch_type,
        "pos": [loader["pos"][0] + 330, loader["pos"][1]],
        "size": [330, 190],
        "flags": {},
        "order": max(node.get("order", 0) for node in workflow["nodes"]) + 1,
        "mode": 0,
        "inputs": [{"name": "model", "type": "MODEL", "link": first_link_id}],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": [second_link_id]}],
        "properties": {"Node name for S&R": patch_type},
        "widgets_values": widgets,
    }
    workflow["nodes"].append(patch_node)
    workflow["links"].extend(
        [
            [first_link_id, loader["id"], 0, node_id, 0, "MODEL"],
            [second_link_id, node_id, 0, director["id"], 0, "MODEL"],
        ]
    )

    loader_output = loader["outputs"][0]
    loader_output["links"] = [first_link_id if value == old_link_id else value for value in (loader_output.get("links") or [])]
    director["inputs"][0]["link"] = second_link_id
    workflow["last_node_id"] = max(workflow.get("last_node_id", 0), node_id)
    workflow["last_link_id"] = max(workflow.get("last_link_id", 0), second_link_id)


def set_director_sampling(workflow: dict, *, steps: int, sampler: str, scheduler: str = "simple") -> None:
    director = find_node(workflow, "MiniMaxH3Director")
    director["widgets_values"][3] = 1.0
    director["widgets_values"][4] = 42
    director["widgets_values"][5] = "fixed"
    director["widgets_values"][13] = steps
    director["widgets_values"][14] = sampler
    director["widgets_values"][15] = scheduler
    director["widgets_values"][16] = 12.0
    director["widgets_values"][17] = 3.0


def set_save_prefix(workflow: dict, prefix: str) -> None:
    save = find_node(workflow, "SaveVideo")
    save["widgets_values"][0] = prefix


def validate(workflow: dict, inventory: dict, root: Path) -> list[str]:
    errors: list[str] = []
    available_nodes = set(inventory["nodes"])
    for node in workflow["nodes"]:
        if node["type"] not in available_nodes and node["type"] not in {"MarkdownNote"}:
            errors.append(f"Missing node type: {node['type']}")
    for filename in MODEL_FILES.values():
        found = any(path.name == filename for path in (root / "models").rglob(filename))
        if not found:
            errors.append(f"Missing model: {filename}")
    node_ids = {node["id"] for node in workflow["nodes"]}
    for link in workflow["links"]:
        if link[1] not in node_ids or link[3] not in node_ids:
            errors.append(f"Dangling link: {link}")
    return errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    root = args.project_root.resolve()
    inventory = fetch_inventory(root, args.url)

    required_types = {"UNETLoader", "CLIPLoader", "VAELoader", "LoraLoaderModelOnly", "MiniMaxH3Director", "ApplyMiniMaxH3FirstBlockCache", "CreateVideo", "SaveVideo"}
    missing_types = sorted(required_types - set(inventory["nodes"]))
    if missing_types:
        raise RuntimeError(f"Installed inventory is missing required node types: {missing_types}")

    examples = root / "runtime/ComfyUI/custom_nodes/ComfyUI_MiniMaxH3_Director/example_workflows"
    output = root / "workflows/minimax-h3"
    output.mkdir(parents=True, exist_ok=True)

    quality = json.loads((examples / "minimax_h3_director_t2v.json").read_text(encoding="utf-8"))
    set_director_sampling(quality, steps=25, sampler="res_multistep")
    insert_model_patch(quality, "ApplyMiniMaxH3FirstBlockCache", ["H3 Fast — 0.10 / max 2", 0.10, 0.10, 0.95, 2, False])
    set_save_prefix(quality, "video/MiniMaxH3_Director_FL2VA_Quality_FBC")

    turbo = json.loads((examples / "minimax_h3_director_t2v.json").read_text(encoding="utf-8"))
    set_director_sampling(turbo, steps=4, sampler="er_sde")
    insert_model_patch(turbo, "LoraLoaderModelOnly", [MODEL_FILES["turbo"], 0.75])
    set_save_prefix(turbo, "video/MiniMaxH3_Director_FL2VA_Turbo_Draft")

    reference = json.loads((examples / "minimax_h3_director_r2v.json").read_text(encoding="utf-8"))
    set_director_sampling(reference, steps=25, sampler="res_multistep")
    insert_model_patch(reference, "ApplyMiniMaxH3FirstBlockCache", ["H3 Fast — 0.10 / max 2", 0.10, 0.10, 0.95, 2, False])
    set_save_prefix(reference, "video/MiniMaxH3_Director_REF2VA_Quality_FBC")

    products = {
        "director-fl2va-quality-fbc.json": quality,
        "director-fl2va-turbo-draft.json": turbo,
        "director-ref2va-quality-fbc.json": reference,
    }
    validation: dict[str, object] = {"ok": True, "workflows": {}}
    for filename, workflow in products.items():
        errors = validate(workflow, inventory, root)
        validation["workflows"][filename] = {"errors": errors, "node_count": len(workflow["nodes"]), "link_count": len(workflow["links"])}
        if errors:
            validation["ok"] = False
        else:
            (output / filename).write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    (root / "state/workflow-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
