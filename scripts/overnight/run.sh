#!/usr/bin/env bash
# Keep the Mac awake and drive the overnight orchestrator until morning.
# Safe around foreign Vast boxes: only label=database-surgeon-sft is created/destroyed.
set -uo pipefail
cd "$(dirname "$0")/../.."
mkdir -p .local/overnight
LOG=.local/overnight/supervisor.log
exec >>"$LOG" 2>&1

echo "==== supervisor $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="

# Prevent idle sleep for 12 hours (display may sleep; network stays up).
if ! pgrep -f 'caffeinate -ims -t 43200' >/dev/null; then
  caffeinate -ims -t 43200 &
  echo "caffeinate pid $!"
fi

# Ensure Postgres is up for judging.
if ! docker ps --format '{{.Names}}' | grep -q fireworks-postgres; then
  docker compose up -d postgres || true
fi

# Ensure Ollama daemon for local model phases.
if ! curl -sf -m 2 http://127.0.0.1:11434/api/tags >/dev/null; then
  nohup ollama serve >/tmp/ollama-surgeon.log 2>&1 &
  sleep 2
fi

# Stop the thin legacy pipeline so we don't double-book the DB timer.
# The overnight runner resumes incomplete JSONL trials.
if pgrep -f 'scripts/eval_pipeline.sh' >/dev/null; then
  echo "stopping legacy eval_pipeline.sh (harness progress is on disk and will resume)"
  pkill -f 'scripts/eval_pipeline.sh' || true
  # Let in-flight surgeon.eval finish its current case writes, then resume under us.
  sleep 30
  pkill -f 'python -u -m surgeon.eval run' || true
  sleep 5
fi

export PYTHONUNBUFFERED=1
# Retry the whole graph a few times if a transient API outage kills a phase.
for attempt in 1 2 3; do
  echo "orchestrator attempt $attempt"
  if .venv/bin/python -u scripts/overnight/orchestrator.py; then
    echo "orchestrator exited cleanly"
    break
  fi
  echo "orchestrator failed; sleeping 120s before retry"
  sleep 120
done

.venv/bin/python -u scripts/overnight/orchestrator.py --status || true
echo "==== supervisor done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
