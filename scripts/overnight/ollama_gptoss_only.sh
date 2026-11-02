#!/usr/bin/env bash
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [ -f .env.local ] && . ./.env.local; set +a
export EVAL_LOCAL_MODELS=gpt-oss:20b
mkdir -p .local/overnight
exec >> .local/overnight/ollama_gptoss.log 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) gpt-oss-only start"
caffeinate -ims -t 28800 &
CAFFEINE=$!
.venv/bin/python -u -m surgeon.eval run ollama-gpt-oss-20b-raw --trials 1 --workers 1 --max-usd 0
code=$?
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) raw exit $code"
# Fast path: skip full harness (best-of-N × 98 is hours). Smoke harness on 5 families.
if [ "$code" -eq 0 ]; then
  .venv/bin/python -u -m surgeon.eval run ollama-gpt-oss-20b-harness --trials 1 --workers 1 --max-usd 0 \
    --cases date_filter month_range correlated_count nullable_antijoin already_indexed
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) harness-smoke exit $?"
fi
.venv/bin/python -u -m surgeon.eval report --split dev || true
bash scripts/site/sync.sh || true
# Kick Wave A finish (router/RESULTS) without waiting for human
bash scripts/overnight/finish_wave_a.sh || true
kill $CAFFEINE 2>/dev/null || true
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) gpt-oss-only done"
