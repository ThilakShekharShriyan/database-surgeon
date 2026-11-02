#!/usr/bin/env bash
# When gpt-oss (+ optional vast adapter) are ready: router, cascades, RESULTS, site.
# Safe to re-run; skips work that is not ready yet.
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [ -f .env.local ] && . ./.env.local; set +a
LOG=.local/overnight/finish_wave_a.log
mkdir -p .local/overnight
exec >>"$LOG" 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) finish_wave_a"

ready() {
  local f="benchmarks/eval_v2/runs/$1/dev_t0.jsonl"
  [ -f "$f" ] && [ "$(wc -l <"$f" | tr -d ' ')" -ge 90 ]
}

# Wait up to ~3h for gpt-oss raw (harness optional for first RESULTS draft)
for _ in $(seq 1 180); do
  if ready ollama-gpt-oss-20b-raw; then break; fi
  echo "$(date +%H:%M:%S) waiting gpt-oss raw…"
  sleep 60
done

if ! ready ollama-gpt-oss-20b-raw; then
  echo "gpt-oss raw incomplete; abort"
  exit 1
fi

# Train router from whatever stages exist (rules + any harness/open)
.venv/bin/python -u -m surgeon.eval train-router || true
.venv/bin/python -u -m surgeon.eval cascades --split dev || true
.venv/bin/python -u -m surgeon.eval report --split dev
bash scripts/site/sync.sh

# Refresh RESULTS from report (non-destructive append stamp)
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess, datetime
out = subprocess.check_output([".venv/bin/python", "-m", "surgeon.eval", "report", "--split", "dev"], text=True)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
path = Path("docs/RESULTS.md")
text = path.read_text() if path.exists() else "# Results\n"
marker = "<!-- AUTO-REPORT -->"
block = f"{marker}\n\n### Auto report ({stamp} UTC)\n\n```\n{out.strip()}\n```\n"
if marker in text:
    pre, _, rest = text.partition(marker)
    # drop old auto block through next --- or EOF
    tail = rest.split("\n## ", 1)
    text = pre.rstrip() + "\n\n" + block + (("\n## " + tail[1]) if len(tail) == 2 else "")
else:
    text = text.rstrip() + "\n\n" + block
path.write_text(text)
print("RESULTS updated")
PY

.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "scripts")
from overnight import state
state.mark("finish_wave_a", "done")
state.log("finish_wave_a complete")
PY
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) finish_wave_a exit 0"
