#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."
LOG=.local/overnight/continue.log
exec >>"$LOG" 2>&1
echo "==== continue $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="

need_lines() {
  local sys=$1 trials=$2
  local n=0 t
  for t in benchmarks/eval_v2/runs/$sys/dev_t*.jsonl; do
    [ -f "$t" ] || continue
    c=$(wc -l < "$t" | tr -d ' ')
    [ "$c" -ge 90 ] && n=$((n+1))
  done
  [ "$n" -ge "$trials" ]
}

while true; do
  if need_lines oss20b-harness 3 && need_lines oss120b-harness 3; then
    echo "$(date +%H:%M:%S) harness complete on disk"
    break
  fi
  if ! pgrep -f 'surgeon.eval run oss20b-harness' >/dev/null; then
    echo "$(date +%H:%M:%S) harness process gone; relaunching"
    nohup caffeinate -ims -t 43200 .venv/bin/python -u -m surgeon.eval run oss20b-harness oss120b-harness --trials 3 --max-usd 8 >> .local/overnight/eval_run_oss20b-harness_oss120b-harness.log 2>&1 &
  fi
  echo "$(date +%H:%M:%S) waiting… 20b=$(wc -l < benchmarks/eval_v2/runs/oss20b-harness/dev_t0.jsonl 2>/dev/null | tr -d ' ') lines"
  sleep 90
done

.venv/bin/python - <<'PY'
import sys, time
sys.path.insert(0, "scripts")
from overnight import state
d = state.read()
d.setdefault("phases", {})["harness_main"] = {
    "status": "done",
    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
d["phase"] = "harness_main"
state.write(d)
PY

caffeinate -ims -t 43200 .venv/bin/python -u scripts/overnight/orchestrator.py --from-phase harness_ablations
echo "==== continue done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
