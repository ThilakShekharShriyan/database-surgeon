#!/usr/bin/env bash
# Close the critique gaps: strict verify re-runs, held-out, cache A/B, specialist, reports.
set -uo pipefail
cd "$(dirname "$0")/.."
trap "" HUP
PIDFILE=.local/eval_v2/frontier_hardening.pid
mkdir -p .local/eval_v2
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "frontier hardening already running pid=$(cat "$PIDFILE")"
  exit 0
fi
echo $$ >"$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [[ -f .env.local ]] && source .env.local; set +a
export PYTHONUNBUFFERED=1
LOG=.local/eval_v2
mkdir -p "$LOG" .local/training

count() {
  local f="benchmarks/eval_v2/runs/$1/$2_t0.jsonl"
  [[ -f "$f" ]] && wc -l <"$f" | tr -d ' ' || echo 0
}

archive_leaky() {
  # Archive pre-strict runs that returned incorrect so we don't mix contracts.
  local dest=".local/eval_v2/archive_prestrict_$(date +%Y%m%d)"
  mkdir -p "$dest"
  for sys in fw-nemotron-harness fw-nemotron-raw cascade-nemotron cascade-surgeon; do
    local f="benchmarks/eval_v2/runs/$sys/dev_t0.jsonl"
    if [[ -f "$f" ]] && rg -q '"outcome": "incorrect"' "$f" 2>/dev/null; then
      echo "archive $sys -> $dest"
      mkdir -p "$dest/$sys"
      mv "$f" "$dest/$sys/" || true
    fi
  done
}

run_sys() {
  local sys="$1" split="${2:-dev}" budget="${3:-8}"
  local n; n=$(count "$sys" "$split")
  local need=98
  [[ "$split" == "heldout" ]] && need=73
  if [[ "$n" -ge "$need" ]]; then
    echo "$(date -u +%H:%M:%S) SKIP $sys $split ($n/$need)"
    return 0
  fi
  echo "$(date -u +%H:%M:%S) RUN  $sys $split at $n/$need"
  .venv/bin/python -u -m surgeon.eval run "$sys" --split "$split" --trials 1 --workers 1 --max-usd "$budget" \
    >>"$LOG/frontier_${sys}_${split}.log" 2>&1 || true
  echo "$(date -u +%H:%M:%S) now $(count "$sys" "$split")/$need"
}

echo "=== 0) cache A/B measurement (offline) ==="
.venv/bin/python scripts/measure_cache_ab.py | tee "$LOG/cache_ab.txt"

echo "=== 1) pg_stat workload slice ==="
PGUSER="${PGUSER_ADMIN:-surgeon_admin}" PGPASSWORD="${PGPASSWORD_ADMIN:-local-admin-only}" \
  .venv/bin/python scripts/pg_stat_workload_slice.py | tee "$LOG/pg_stat_slice.txt"

echo "=== 2) archive leaky pre-strict runs ==="
archive_leaky

echo "=== 3) strict-verify re-runs (dev) for previously leaky / headline systems ==="
run_sys open-harness dev 8
run_sys fw-fast-harness dev 10
run_sys fw-nemotron-harness dev 12
run_sys cache-rules dev 0
run_sys open-harness-nocache dev 8

echo "=== 4) held-out open-harness (+ rules / frontier if cheap) ==="
run_sys rules-only heldout 0
run_sys open-harness heldout 10

echo "=== 5) specialist LoRA vs base (serverless Muse specialist if present) ==="
export SPECIALIST_PROVIDER="${SPECIALIST_PROVIDER:-fireworks}"
export SPECIALIST_MODEL="${SPECIALIST_MODEL:-accounts/thilaksshriyan-0lo68/models/muse-starter-sl-sql-specialist-20261102-112625}"
export SPECIALIST_NAME="${SPECIALIST_NAME:-specialist}"
# Probe one completion; skip eval if model unavailable
if .venv/bin/python - <<'PY'
import os, json, urllib.request
model=os.environ["SPECIALIST_MODEL"]
key=os.environ.get("FIREWORKS_API_KEY","")
body=json.dumps({"model":model,"messages":[{"role":"user","content":"Reply OK"}],"max_tokens":8,"temperature":0}).encode()
req=urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=body,
  headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
try:
  with urllib.request.urlopen(req, timeout=90) as r:
    d=json.load(r)
  err=d.get("error")
  print("specialist_probe", "ERR" if err else "OK", err or "")
  raise SystemExit(1 if err else 0)
except Exception as e:
  print("specialist_probe FAIL", e)
  raise SystemExit(1)
PY
then
  run_sys specialist-harness dev 6
  run_sys specialist-raw dev 4
else
  echo "specialist model not reachable — skip LoRA eval (deploy/payment may be required)"
fi

echo "=== 6) cascades + reports (dev + heldout) ==="
.venv/bin/python -m surgeon.eval cascades --split dev | tee "$LOG/cascades_frontier_dev.txt"
.venv/bin/python -m surgeon.eval report --split dev | tee "$LOG/report_frontier_dev.txt"
.venv/bin/python -m surgeon.eval report --split heldout | tee "$LOG/report_frontier_heldout.txt"
.venv/bin/python scripts/private_retrain_loop.py seed-cache || true
bash scripts/site/sync.sh || true

echo "=== 7) write docs/RESULTS.md snapshot via python ==="
.venv/bin/python - <<'PY' | tee "$LOG/frontier_summary.json"
import json
from pathlib import Path
from collections import Counter
ROOT = Path('.')
rows_out = {}
for split in ("dev", "heldout"):
  need = 98 if split == "dev" else 73
  for name in [
    "rules-only","frontier-raw","open-raw","open-harness","open-harness-nocache",
    "cache-rules","fw-fast-harness","fw-nemotron-harness","cascade-surgeon",
    "cascade-nemotron","specialist-harness","specialist-raw",
  ]:
    f = ROOT / f"benchmarks/eval_v2/runs/{name}/{split}_t0.jsonl"
    key = f"{name}:{split}"
    if not f.exists():
      rows_out[key] = {"n": 0}; continue
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    n = len(rows)
    c = Counter(r.get("outcome") for r in rows)
    lat = sorted(float(r.get("latency_ms") or 0) for r in rows)
    llm = sorted(float(r.get("llm_ms") or 0) for r in rows)
    def pct(vs, q):
      if not vs: return None
      return vs[min(len(vs)-1, max(0, int((len(vs)-1)*q)))]
    rows_out[key] = {
      "n": n, "complete": n >= need,
      "accept": c.get("accepted", 0),
      "accept_rate": round(c.get("accepted", 0)/n, 4) if n else None,
      "wrong": c.get("incorrect", 0),
      "latency_p50_ms": pct(lat, 0.5),
      "latency_p95_ms": pct(lat, 0.95),
      "llm_p50_ms": pct(llm, 0.5),
      "llm_p95_ms": pct(llm, 0.95),
    }
cache = {}
p = Path(".local/training/cache_ab_report.json")
if p.exists():
  cache = json.loads(p.read_text())
print(json.dumps({"systems": rows_out, "cache_ab": {k: cache.get(k) for k in (
  "hit_rate","positive_hits","negative_hits","misses","estimated_speedup_factor",
  "open_harness_llm_p50_ms") if k in cache}}, indent=2))
PY

echo DONE
