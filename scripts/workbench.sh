#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if curl -fsS --max-time 2 http://127.0.0.1:3100/api/snapshot >/dev/null 2>&1; then
  printf '%s\n' 'Workbench is already running: http://127.0.0.1:3100'
  exit 0
fi
api_pid=''
if ! curl -fsS --max-time 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then
  python3 -m surgeon.service --port 8765 &
  api_pid=$!
fi
cleanup() { if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM
npm --prefix web run dev
