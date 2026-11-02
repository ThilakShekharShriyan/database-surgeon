#!/usr/bin/env bash
# Full baseline → our stack. Safe to re-run; skips systems already at 98/98.
# Usage: bash scripts/run_full_benchmark.sh
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [[ -f .env.local ]] && source .env.local; set +a
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
LOG=.local/eval_v2
mkdir -p "$LOG"
# Portable lock (macOS often lacks flock on PATH)
if ! .venv/bin/python - "$LOG/full_bench.lock" <<'PY'
import fcntl, os, sys
path = sys.argv[1]
fp = open(path, "a+")
try:
    fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(2)
os.write(1, b"lock ok\n")
# Keep FD open for process lifetime via inherited fd in bash? Re-exec hold:
# Write pid and rely on single orchestrator; child keeps lock by staying alive.
import atexit
atexit.register(lambda: None)
# Pass lock fd to parent via env using a holding subprocess is hard in bash;
# use pidfile instead:
pid_path = path + ".pid"
if os.path.exists(pid_path):
    try:
        old = int(open(pid_path).read().strip())
        os.kill(old, 0)
        sys.exit(2)  # still alive
    except (ValueError, OSError, ProcessLookupError):
        pass
open(pid_path, "w").write(str(os.getppid()))
sys.exit(0)
PY
then
  echo "full benchmark already running"; exit 0
fi

count() {
  local f="benchmarks/eval_v2/runs/$1/dev_t0.jsonl"
  [[ -f "$f" ]] && wc -l <"$f" | tr -d ' ' || echo 0
}

run_sys() {
  local sys="$1" budget="${2:-6}"
  local n; n=$(count "$sys")
  if [[ "$n" -ge 98 ]]; then
    echo "$(date -u +%H:%M:%S) SKIP $sys ($n/98)"
    return 0
  fi
  echo "$(date -u +%H:%M:%S) RUN  $sys at $n/98 budget=\$$budget"
  .venv/bin/python -u -m surgeon.eval run "$sys" --split dev --trials 1 --workers 1 --max-usd "$budget" \
    >>"$LOG/full_${sys}.log" 2>&1
  echo "$(date -u +%H:%M:%S) EXIT $sys code=$? now=$(count "$sys")/98"
}

echo "=== PHASE 0: wait for in-flight fw-nemotron if another loop holds it ==="
# If LaunchAgent is mid-nemotron, wait until 98 or process gone (max ~2h)
END=$((SECONDS + 7200))
while (( SECONDS < END )); do
  n=$(count fw-nemotron-harness)
  if [[ "$n" -ge 98 ]]; then
    echo "nemotron complete $n"
    break
  fi
  if pgrep -f 'surgeon.eval run fw-nemotron-harness' >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%S) waiting nemotron… $n/98"
    sleep 60 || true
    continue
  fi
  # nothing running — we'll resume in phase 1
  echo "$(date -u +%H:%M:%S) no in-flight nemotron process (at $n/98); continuing"
  break
done

echo "=== PHASE 1: BASELINE (closed + open raw + rules) ==="
run_sys rules-only 0
run_sys frontier-raw 8
run_sys open-raw 4
run_sys oss20b-raw 4
run_sys oss120b-raw 4
run_sys fw-fast-raw 3
run_sys fw-nemotron-raw 6

echo "=== PHASE 2: HARNESS BASELINES ==="
run_sys open-harness 6
run_sys fw-gpt-oss-harness 6
run_sys fw-fast-harness 8
run_sys fw-nemotron-harness 10

echo "=== PHASE 3: OUR CASCADES (replay from stage JSONL — no extra model $) ==="
.venv/bin/python -m surgeon.eval cascades --split dev | tee "$LOG/cascades_full.txt"

echo "=== PHASE 4: REPORT + SITE ==="
.venv/bin/python -m surgeon.eval report --split dev | tee "$LOG/report_full_dev.txt"
bash scripts/site/sync.sh || true
.venv/bin/python - <<'PY' | tee "$LOG/baseline_ours_summary.json"
import json
from pathlib import Path
out = {}
for name in [
  "rules-only","frontier-raw","open-raw","open-harness",
  "fw-fast-raw","fw-fast-harness","fw-nemotron-raw","fw-nemotron-harness",
  "cascade-open-fw","cascade-nemotron","cascade-surgeon","cascade-oss-fw",
]:
  f = Path(f"benchmarks/eval_v2/runs/{name}/dev_t0.jsonl")
  if not f.exists():
    out[name] = {"n": 0}; continue
  rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
  n = len(rows)
  a = sum(1 for r in rows if r.get("outcome") == "accepted")
  w = sum(1 for r in rows if r.get("outcome") == "incorrect")
  c = sum(float(r.get("cost_usd") or 0) for r in rows)
  out[name] = {
    "n": n, "accept": a, "accept_rate": round(a / n, 4) if n else None,
    "wrong": w, "cost_usd": round(c, 4),
  }
print(json.dumps(out, indent=2))
PY
echo DONE
