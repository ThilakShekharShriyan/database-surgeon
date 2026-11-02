#!/usr/bin/env bash
# Entry point for launchd — survives Cursor/shell exits.
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
# Load API keys without printing them
set -a
[ -f .env.local ] && . ./.env.local
set +a

mkdir -p .local/overnight
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) launchd entry" >> .local/overnight/launchd.out.log

# Keep the machine from idle-sleeping while we work.
caffeinate -ims -t 43200 &
CAFFEINE_PID=$!

# 1) Finish harness if incomplete
need() {
  local sys=$1 want=$2 n=0
  for f in benchmarks/eval_v2/runs/"$sys"/dev_t*.jsonl; do
    [ -f "$f" ] || continue
    c=$(wc -l < "$f" | tr -d ' ')
    [ "$c" -ge 90 ] && n=$((n+1))
  done
  [ "$n" -ge "$want" ]
}

if ! need oss20b-harness 3 || ! need oss120b-harness 3; then
  echo "$(date +%H:%M:%S) running harness" >> .local/overnight/launchd.out.log
  .venv/bin/python -u -m surgeon.eval run oss20b-harness oss120b-harness --trials 3 --max-usd 8 \
    >> .local/overnight/eval_run_oss20b-harness_oss120b-harness.log 2>&1
fi

# Mark harness done for the orchestrator
.venv/bin/python - <<'PY'
import sys, time
sys.path.insert(0, "scripts")
from overnight import state
d = state.read()
d.setdefault("phases", {})["enrich_training"] = {"status": "done", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
d["phases"]["harness_main"] = {"status": "done", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
d["phase"] = "harness_main"
state.write(d)
PY

# 2) Rest of overnight (ablations → ollama → router → vast → report)
.venv/bin/python -u scripts/overnight/orchestrator.py --from-phase harness_ablations \
  >> .local/overnight/night.log 2>&1
code=$?
kill "$CAFFEINE_PID" 2>/dev/null || true
exit $code
