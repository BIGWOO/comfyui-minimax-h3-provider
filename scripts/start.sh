#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile="main"
host="127.0.0.1"
port="8188"
background=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) profile="$2"; shift 2 ;;
    --host) host="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --background) background=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$profile" =~ ^(main|safe|novram)$ ]] || { echo "Invalid profile" >&2; exit 2; }
python="$project_root/.venvs/main/bin/python"
main="$project_root/runtime/ComfyUI/main.py"
[[ -x "$python" && -f "$main" ]] || { echo "Run scripts/setup.sh first" >&2; exit 1; }
if command -v ss >/dev/null && ss -ltn "sport = :$port" | grep -q LISTEN; then
  echo "Port $port is already in use" >&2
  exit 1
fi

reserve=2
[[ "$profile" == "main" ]] || reserve=3
mkdir -p "$project_root/data/input" "$project_root/data/output" "$project_root/data/temp" "$project_root/data/user" "$project_root/logs" "$project_root/state"
args=("$main" --listen "$host" --port "$port"
  --models-directory "$project_root/models"
  --input-directory "$project_root/data/input"
  --output-directory "$project_root/data/output"
  --temp-directory "$project_root/data/temp"
  --user-directory "$project_root/data/user"
  --database-url "sqlite:///$project_root/data/user/comfyui.db"
  --reserve-vram "$reserve" --enable-dynamic-vram --async-offload --fast-disk --enable-manager)
[[ "$profile" == "main" ]] || args+=(--cache-none)
[[ "$profile" == "novram" ]] && args+=(--novram)
export HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUTF8=1 PYTHONIOENCODING=utf-8
if [[ "$background" == true ]]; then
  log="$project_root/logs/comfyui-$profile-$(date +%Y%m%d-%H%M%S).log"
  nohup "$python" "${args[@]}" >"$log" 2>&1 &
  echo $! > "$project_root/state/comfyui.pid"
  echo "Started ComfyUI PID $! at http://$host:$port; log: $log"
else
  exec "$python" "${args[@]}"
fi
