#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock="$project_root/profiles/minimax-h3/versions.lock.json"

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required to read the version lock" >&2; exit 1; }

python3 - "$lock" <<'PY' | while IFS=$'\t' read -r name url commit target; do
import json, sys
for repo in json.load(open(sys.argv[1], encoding="utf-8"))["repositories"]:
    print(repo["name"], repo["url"], repo["commit"], repo["target"], sep="\t")
PY
  destination="$project_root/$target"
  if [[ ! -d "$destination/.git" ]]; then
    mkdir -p "$(dirname "$destination")"
    git clone --filter=blob:none "$url" "$destination"
  fi
  git -C "$destination" fetch --quiet origin "$commit"
  git -C "$destination" -c advice.detachedHead=false checkout --force "$commit"
  [[ "$(git -C "$destination" rev-parse HEAD)" == "$commit" ]] || {
    echo "Commit mismatch for $name" >&2
    exit 1
  }
done

python_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["python"])' "$lock")"
venv="$project_root/.venvs/main"
python="$venv/bin/python"
if [[ ! -x "$python" ]]; then
  uv venv --python "$python_version" "$venv"
fi

mapfile -t torch_args < <(python3 - "$lock" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1], encoding="utf-8"))
print(lock["torch_index"])
print(*lock["torch_packages"], sep="\n")
PY
)
uv pip install --python "$python" --index-url "${torch_args[0]}" "${torch_args[@]:1}"
uv pip install --python "$python" -r "$project_root/profiles/minimax-h3/python.lock.txt"
mkdir -p "$project_root/state"
uv pip freeze --python "$python" > "$project_root/state/resolved-packages.txt"
"$python" -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))'
echo "Setup complete: $project_root"
