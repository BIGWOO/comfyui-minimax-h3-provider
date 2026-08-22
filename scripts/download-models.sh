#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pack="creator"
extra=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack) pack="$2"; shift 2 ;;
    --skip-hash) extra+=("--skip-hash"); shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
python="$project_root/.venvs/main/bin/python"
[[ -x "$python" ]] || { echo "Run scripts/setup.sh first" >&2; exit 1; }
export HF_HUB_DISABLE_TELEMETRY=1
"$python" "$project_root/tools/download_models.py" --project-root "$project_root" --pack "$pack" "${extra[@]}"
