#!/usr/bin/env bash
# Full all-round advantages benchmark — quality, safety, cost, latency, cache, cascade, held-out.
# Durable under launchd (com.databasesurgeon.fullbench). Skips completed systems; shares DB fairly.
set -uo pipefail
trap "" HUP
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [[ -f .env.local ]] && source .env.local; set +a
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
LOG=.local/eval_v2
mkdir -p "$LOG" .local/training
PIDFILE="$LOG/all_advantages.pid"
OUT="$LOG/all_advantages.out"

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT"; }

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "all-advantages bench already running pid=$(cat "$PIDFILE")"
  exit 0
fi
echo $$ >"$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

count() {
  local sys="$1" split="${2:-dev}"
  local f="benchmarks/eval_v2/runs/$sys/${split}_t0.jsonl"
  [[ -f "$f" ]] && wc -l <"$f" | tr -d ' ' || echo 0
}

need_for() { [[ "${1}" == "heldout" ]] && echo 73 || echo 98; }

running() {
  pgrep -f "surgeon.eval run ${1}" >/dev/null 2>&1
}

active() {
  local n
  n=$(pgrep -f 'surgeon.eval run ' 2>/dev/null | wc -l | tr -d ' ' || true)
  echo "${n:-0}"
}

run_sys() {
  local sys="$1" split="${2:-dev}" budget="${3:-8}"
  local need; need=$(need_for "$split")
  local n; n=$(count "$sys" "$split")
  if [[ "$n" -ge "$need" ]]; then
    log "SKIP $sys $split ($n/$need)"
    return 0
  fi
  # Wait for a free DB slot (max 2 concurrent evals to keep verify stable).
  local waited=0
  while [[ "$(active)" -ge 2 ]]; do
    if running "$sys"; then
      log "WAIT $sys already in-flight"
      return 0
    fi
    sleep 30
    waited=$((waited + 30))
    if [[ "$waited" -gt 7200 ]]; then
      log "TIMEOUT waiting for slot for $sys"
      return 1
    fi
  done
  if running "$sys"; then
    log "SKIP start $sys (process exists)"
    return 0
  fi
  log "RUN  $sys $split at $n/$need budget=\$$budget"
  .venv/bin/python -u -m surgeon.eval run "$sys" --split "$split" --trials 1 --workers 1 --max-usd "$budget" \
    >>"$LOG/adv_${sys}_${split}.log" 2>&1 || true
  log "DONE $sys $split now=$(count "$sys" "$split")/$need"
}

log "all-advantages bench start pid=$$"

# Offline measurements (fast)
.venv/bin/python scripts/measure_cache_ab.py >>"$OUT" 2>&1 || true
PGUSER="${PGUSER_ADMIN:-surgeon_admin}" PGPASSWORD="${PGPASSWORD_ADMIN:-local-admin-only}" \
  .venv/bin/python scripts/pg_stat_workload_slice.py >>"$OUT" 2>&1 || true

# --- DEV: baselines & harness stack (skips if complete) ---
run_sys rules-only dev 0
run_sys frontier-raw dev 8
run_sys open-raw dev 4
run_sys fw-fast-raw dev 4
run_sys fw-nemotron-raw dev 8
run_sys open-harness dev 8
run_sys fw-gpt-oss-harness dev 8
run_sys fw-fast-harness dev 10
run_sys fw-nemotron-harness dev 12
run_sys cache-rules dev 0
run_sys open-harness-nocache dev 8
run_sys oss20b-harness dev 6
run_sys ollama-gpt-oss-20b-harness dev 0

# Specialist (optional)
export SPECIALIST_PROVIDER="${SPECIALIST_PROVIDER:-fireworks}"
export SPECIALIST_MODEL="${SPECIALIST_MODEL:-accounts/thilaksshriyan-0lo68/models/muse-starter-sl-sql-specialist-20261102-112625}"
export SPECIALIST_NAME="${SPECIALIST_NAME:-specialist}"
if .venv/bin/python - <<'PY'
import os, json, urllib.request
model=os.environ["SPECIALIST_MODEL"]; key=os.environ.get("FIREWORKS_API_KEY","")
body=json.dumps({"model":model,"messages":[{"role":"user","content":"OK"}],"max_tokens":4,"temperature":0}).encode()
req=urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=body,
  headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
try:
  with urllib.request.urlopen(req, timeout=60) as r:
    d=json.load(r)
  raise SystemExit(0 if not d.get("error") else 1)
except Exception:
  raise SystemExit(1)
PY
then
  run_sys specialist-raw dev 4
  run_sys specialist-harness dev 6
else
  log "specialist unavailable — skip"
fi

# --- HELDOUT: generalization ---
run_sys rules-only heldout 0
run_sys open-harness heldout 10
run_sys fw-fast-harness heldout 10
run_sys frontier-raw heldout 8

# --- Cascades (replay, cheap) + reports ---
log "cascades + reports"
.venv/bin/python -m surgeon.eval cascades --split dev >>"$OUT" 2>&1 || true
.venv/bin/python -m surgeon.eval cascades --split heldout >>"$OUT" 2>&1 || true
.venv/bin/python -m surgeon.eval report --split dev | tee "$LOG/report_advantages_dev.txt" | tee -a "$OUT"
.venv/bin/python -m surgeon.eval report --split heldout | tee "$LOG/report_advantages_heldout.txt" | tee -a "$OUT"
.venv/bin/python scripts/private_retrain_loop.py seed-cache >>"$OUT" 2>&1 || true
.venv/bin/python scripts/measure_cache_ab.py >>"$OUT" 2>&1 || true
.venv/bin/python scripts/write_advantages_scoreboard.py | tee -a "$OUT"
bash scripts/site/sync.sh >>"$OUT" 2>&1 || true

log "ALL ADVANTAGES BENCH DONE"
exit 0
