#!/usr/bin/env bash
# Stage Chrome tabs for the DBSurgeon submit video.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Prefer teleprompter on a second display; keep product tabs on the main display.
open -a "Google Chrome" \
  "http://127.0.0.1:3100/demo" \
  "http://127.0.0.1:3100/research" \
  "http://127.0.0.1:3100/demo/teleprompter.html" \
  "http://127.0.0.1:3100/demo/video-cards.html" \
  "http://127.0.0.1:4343/" 2>/dev/null || \
open \
  "http://127.0.0.1:3100/demo" \
  "http://127.0.0.1:3100/research" \
  "http://127.0.0.1:3100/demo/teleprompter.html" \
  "http://127.0.0.1:3100/demo/video-cards.html" \
  "http://127.0.0.1:4343/"

# Jump IDE to the two code files to show in beat 3
if command -v cursor >/dev/null; then
  cursor -g "$ROOT/surgeon/eval/systems.py:1" >/dev/null 2>&1 || true
elif command -v code >/dev/null; then
  code -g "$ROOT/surgeon/eval/systems.py:1" >/dev/null 2>&1 || true
fi

echo "Tabs opened. Teleprompter: docs/DEMO_VIDEO.md"
echo "Record: ./scripts/record_demo.sh --project=\"DBSurgeon\""
