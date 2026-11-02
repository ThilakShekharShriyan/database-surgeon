#!/usr/bin/env bash
# Durable background eval watchdog — survives chat/agent interruptions.
# Single owner for unfinished systems → cascades + report.
# Prefer launchd (com.databasesurgeon.bgbench); avoid starting from chat shells.
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
export PATH="/opt/homebrew/opt/util-linux/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:/usr/bin:/bin"
set -a; [[ -f .env.local ]] && source .env.local; set +a
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
LOG=.local/eval_v2
mkdir -p "$LOG"
PIDFILE="$LOG/bg_watchdog.pid"
OUT="$LOG/bg_watchdog.out"

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT"; }

on_exit() {
  local code=$?
  echo "$(date -u +%H:%M:%S) watchdog exit code=$code pid=$$" >>"$OUT"
  if [[ -f "$PIDFILE" ]] && [[ "$(cat "$PIDFILE" 2>/dev/null)" == "$$" ]]; then
    rm -f "$PIDFILE"
  fi
}
trap on_exit EXIT
trap 'log "signal TERM"; exit 143' TERM
trap 'log "signal INT"; exit 130' INT
trap 'log "signal HUP (ignored)"' HUP

if [[ -f "$PIDFILE" ]]; then
  old=$(cat "$PIDFILE" 2>/dev/null || echo "")
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    echo "watchdog already running pid=$old"
    trap - EXIT
    exit 0
  fi
fi
echo $$ >"$PIDFILE"

count() {
  local f="benchmarks/eval_v2/runs/$1/dev_t0.jsonl"
  if [[ -f "$f" ]]; then
    wc -l <"$f" | tr -d ' ' || echo 0
  else
    echo 0
  fi
}

running() {
  pgrep -f "surgeon.eval run ${1}" >/dev/null 2>&1 && return 0
  return 1
}

active_eval_count() {
  local n
  n=$(pgrep -f 'surgeon.eval run ' 2>/dev/null | wc -l | tr -d ' ' || true)
  echo "${n:-0}"
}

ensure() {
  local sys="$1" budget="$2" max_parallel="${3:-3}"
  local n active
  n=$(count "$sys")
  if [[ "${n:-0}" -ge 98 ]]; then
    return 0
  fi
  if running "$sys"; then
    return 0
  fi
  active=$(active_eval_count)
  if [[ "${active:-0}" -ge "$max_parallel" ]]; then
    echo "$(date -u +%H:%M:%S) WAIT $sys (active=$active >= $max_parallel)" >>"$OUT"
    return 0
  fi
  log "START $sys at ${n}/98 budget=$budget"
  (
    cd /Users/thilakshekharshriyan/Projects/Fireworks || exit 0
    exec .venv/bin/python -u -m surgeon.eval run "$sys" --split dev --trials 1 --workers 1 --max-usd "$budget"
  ) >>"$LOG/bg_${sys}.log" 2>&1 &
  echo $! >"$LOG/bg_${sys}.pid"
  disown 2>/dev/null || true
}

FW_TARGETS=(
  "fw-fast-raw:4"
  "fw-nemotron-raw:10"
  "fw-fast-harness:12"
)
EXTRA_TARGETS=(
  "oss20b-harness:6"
  "ollama-gpt-oss-20b-harness:0"
)

log "watchdog start pid=$$ (hardened v2)"

END=$((SECONDS + 18000))
while (( SECONDS < END )); do
  all_done=1
  fw_left=0

  for spec in "${FW_TARGETS[@]}"; do
    sys="${spec%%:*}"
    budget="${spec##*:}"
    ensure "$sys" "$budget" 3
    n=$(count "$sys")
    if [[ "${n:-0}" -lt 98 ]]; then
      all_done=0
      fw_left=$((fw_left + 1))
    fi
  done

  for spec in "${EXTRA_TARGETS[@]}"; do
    sys="${spec%%:*}"
    budget="${spec##*:}"
    if [[ "$fw_left" -gt 0 ]]; then
      ensure "$sys" "$budget" 4
    else
      ensure "$sys" "$budget" 2
    fi
    n=$(count "$sys")
    if [[ "${n:-0}" -lt 98 ]]; then
      all_done=0
    fi
  done

  echo "$(date -u +%H:%M:%S) progress fast_r=$(count fw-fast-raw) nemo_r=$(count fw-nemotron-raw) fast_h=$(count fw-fast-harness) oss20=$(count oss20b-harness) ollama_h=$(count ollama-gpt-oss-20b-harness) active=$(active_eval_count)" >>"$OUT"

  if [[ "$all_done" -eq 1 ]]; then
    log "all targets 98 — cascades + report"
    .venv/bin/python -m surgeon.eval cascades --split dev >>"$OUT" 2>&1 || true
    .venv/bin/python -m surgeon.eval report --split dev >>"$OUT" 2>&1 || true
    .venv/bin/python scripts/private_retrain_loop.py seed-cache >>"$OUT" 2>&1 || true
    bash scripts/site/sync.sh >>"$OUT" 2>&1 || true
    log "DONE"
    exit 0
  fi
  sleep 45 || true
done
log "TIMEOUT"
exit 1
