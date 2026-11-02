#!/usr/bin/env bash
# Shim: remaining work is owned by bg_eval_watchdog via launchd (com.databasesurgeon.bgbench).
# Extra chat-started loops were getting SIGHUP'd when agent shells aborted.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Use: launchctl kickstart gui/\$(id -u)/com.databasesurgeon.bgbench"
if [[ -f .local/eval_v2/bg_watchdog.pid ]] && kill -0 "$(cat .local/eval_v2/bg_watchdog.pid)" 2>/dev/null; then
  echo "watchdog already running pid=$(cat .local/eval_v2/bg_watchdog.pid)"
  tail -8 .local/eval_v2/bg_watchdog.out || true
  exit 0
fi
exec bash scripts/bg_eval_watchdog.sh
