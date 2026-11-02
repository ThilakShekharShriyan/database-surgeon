#!/usr/bin/env bash
# Everything that touches the database runs here, one step at a time, so no two
# evaluations ever time queries concurrently. Each step resumes if interrupted.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=.local/eval_v2/pipeline.log
step() { echo "== $(date +%H:%M:%S) $*" | tee -a "$LOG"; "$PY" -u -m surgeon.eval "$@" >> "$LOG" 2>&1; }

while ! grep -q '^done' .local/eval_v2/baselines.log 2>/dev/null; do sleep 20; done
step train-data --per-template 8 --max-usd 3
step train-split
step run oss20b-harness oss120b-harness --trials 3 --max-usd 6
step run oss20b-harness-minus-rules oss20b-harness-minus-catalog oss20b-harness-minus-retrieval \
  oss20b-harness-minus-best_of oss20b-harness-minus-repair oss20b-harness-minus-precheck \
  oss20b-harness-minus-verify oss20b-verify-only oss20b-harness-effort-low oss20b-harness-effort-high \
  --trials 3 --max-usd 6
# qwen3.5:2b dropped — hung without answering on this Mac.
step run ollama-gpt-oss-20b-raw \
  --trials 1 --workers 2 --max-usd 0
step run ollama-qwen25-coder-7b-harness --trials 1 --workers 2 --max-usd 0
step report
echo "== $(date +%H:%M:%S) pipeline finished" | tee -a "$LOG"
