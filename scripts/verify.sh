#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
url="http://127.0.0.1:8188"
pack="creator"
extra=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) url="$2"; shift 2 ;;
    --pack) pack="$2"; shift 2 ;;
    --skip-hashes) extra+=("--skip-hashes"); shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
"$project_root/.venvs/main/bin/python" "$project_root/tools/verify.py" \
  --project-root "$project_root" --url "$url" --pack "$pack" "${extra[@]}"
