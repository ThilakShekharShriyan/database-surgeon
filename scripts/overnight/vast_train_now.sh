#!/usr/bin/env bash
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PWD/.venv/bin:$PATH"
set -a; [ -f .env.local ] && . ./.env.local; set +a
exec >> .local/overnight/vast_sft.log 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) vast_train_now start"
caffeinate -ims -t 14400 &
CAFFEINE=$!
.venv/bin/python -u - <<'PY'
import os, sys, subprocess
from pathlib import Path
sys.path.insert(0, "scripts")
for line in Path(".env.local").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
from overnight import state, vast_manager as vast
state.ensure()
vast.configure_key()
if state.read().get("phases", {}).get("vast_sft", {}).get("status") == "done":
    state.log("vast already done")
    raise SystemExit(0)
budgets = state.read().get("budgets", {})
try:
    iid = vast.create_instance(budgets.get("vast_max_dph", 0.45))
    state.log(f"vast_train_now on {iid}")
    vast.wait_ready(iid, timeout_s=2400)
    vast.upload_and_train(iid)
    port = vast.start_vllm(iid)
    env = dict(os.environ)
    env.update({
        "LOCAL_BASE_URL": f"http://127.0.0.1:{port}/v1",
        "SPECIALIST_PROVIDER": "local",
        "SPECIALIST_MODEL": "specialist",
        "SPECIALIST_NAME": "vast-qwen7b-sft",
    })
    subprocess.run(
        [".venv/bin/python", "-u", "-m", "surgeon.eval", "run", "vast-qwen7b-sft-raw",
         "--trials", "1", "--workers", "1", "--max-usd", "0",
         "--cases", "date_filter", "month_range", "correlated_count",
         "nullable_antijoin", "already_indexed"],
        env=env, check=False,
    )
    vast.destroy(iid)
    state.mark("vast_sft", "done")
    state.log("vast_train_now complete")
except Exception as exc:
    state.log(f"vast_train_now FAILED: {exc}")
    state.mark("vast_sft", "error", error=str(exc)[:400])
    try:
        vast.destroy()
    except Exception as e:
        state.log(f"destroy: {e}")
PY
kill $CAFFEINE 2>/dev/null || true
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) vast_train_now exit $?"
