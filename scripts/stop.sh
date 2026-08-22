#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pid_file="$project_root/state/comfyui.pid"
if [[ ! -f "$pid_file" ]]; then
  echo "No provider PID file found"
  exit 0
fi
pid="$(<"$pid_file")"
if ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$pid_file"
  echo "Provider is not running"
  exit 0
fi
command_line="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
[[ "$command_line" == *"$project_root/runtime/ComfyUI/main.py"* ]] || {
  echo "PID $pid is not this project's ComfyUI; refusing to stop it" >&2
  exit 1
}
kill "$pid"
rm -f "$pid_file"
echo "Stopped ComfyUI PID $pid"
