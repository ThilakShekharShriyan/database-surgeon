#!/usr/bin/env bash
# Non-Groq overnight path: Ollama → Vast SFT → MLX smoke → router (if possible) → report → site.
# Survives Cursor exits when launched via launchd (com.databasesurgeon.rest).
set -uo pipefail
cd /Users/thilakshekharshriyan/Projects/Fireworks
# launchd PATH is bare; Homebrew + venv tools must be explicit.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Users/thilakshekharshriyan/Projects/Fireworks/.venv/bin:$PATH"
set -a
[ -f .env.local ] && . ./.env.local
set +a
export DEMO_SYSTEM="${DEMO_SYSTEM:-cascade-local}"
mkdir -p .local/overnight
LOG=.local/overnight/build_rest.log
exec >>"$LOG" 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) build_rest start PATH=$PATH"

caffeinate -ims -t 43200 &
CAFFEINE_PID=$!
trap 'kill $CAFFEINE_PID 2>/dev/null || true' EXIT

.venv/bin/python -u - <<'PY'
import sys, time, os, subprocess
from pathlib import Path
sys.path.insert(0, "scripts")
from overnight import state, vast_manager as vast

ROOT = Path(".").resolve()
state.ensure()
state.log("build_rest: phase ollama")

# --- Ollama baselines (serial, 1 trial) ---
# Keep only the strong local model (qwen raws were slow + unsafe).
systems = [
    "ollama-gpt-oss-20b-raw",
    "ollama-gpt-oss-20b-harness",
]
ollama = "/opt/homebrew/bin/ollama"
if Path(ollama).exists():
    subprocess.run([ollama, "list"], check=False)
else:
    state.log("ollama binary missing on PATH; continuing anyway")
code = subprocess.run(
    [".venv/bin/python", "-u", "-m", "surgeon.eval", "run", *systems,
     "--trials", "1", "--workers", "1", "--max-usd", "0"],
    check=False,
).returncode
state.log(f"ollama eval exit={code}")
state.mark("ollama_baselines", "done")

# --- Vast SFT (own label only) ---
state.log("build_rest: phase vast_sft")
if state.read().get("phases", {}).get("vast_sft", {}).get("status") == "done":
    state.log("vast_sft already done — skip")
elif (ROOT / ".local/training/adapters/vast-qwen25-coder-7b").exists():
    state.log("vast adapters on disk — mark done, skip remote")
    state.mark("vast_sft", "done")
else:
    try:
        for line in (ROOT / ".env.local").read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        vast.configure_key()
        foreign = vast.foreign_running()
        state.log("vast: leaving foreign alone: " + ", ".join(f"{i.get('label')}:{i.get('id')}" for i in foreign))
        budgets = state.read()["budgets"]
        iid = vast.create_instance(budgets.get("vast_max_dph", 0.35))
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
            [".venv/bin/python", "-u", "-m", "surgeon.eval", "run",
             "vast-qwen7b-sft-raw", "vast-qwen7b-sft-harness",
             "--trials", "1", "--workers", "1", "--max-usd", "0",
             "--cases", "date_filter", "month_range", "correlated_count",
             "nullable_antijoin", "already_indexed"],
            env=env, check=False,
        )
        vast.destroy(iid)
        state.mark("vast_sft", "done")
    except Exception as exc:  # noqa: BLE001
        state.log(f"vast_sft FAILED: {exc}")
        state.mark("vast_sft", "error", error=str(exc)[:400])
        try:
            vast.destroy()
        except Exception as e:  # noqa: BLE001
            state.log(f"destroy: {e}")

# --- MLX LoRA smoke (after Ollama so they don't fight for memory) ---
state.log("build_rest: phase mlx_smoke")
train = ROOT / ".local/training/mlx/train.jsonl"
if train.exists():
    env = dict(os.environ)
    env["MLX_ITERS"] = env.get("MLX_ITERS", "100")
    env["MLX_BATCH"] = "1"
    code = subprocess.run(["bash", "scripts/finetune/mlx_lora.sh", "train"], env=env).returncode
    state.mark("mlx_smoke", "done" if code == 0 else "error", error=f"exit {code}")
else:
    state.log("mlx: no train.jsonl; skip")
    state.mark("mlx_smoke", "skipped")

# --- Router / cascades when enough stage coverage ---
state.log("build_rest: phase router")
try:
    subprocess.run([".venv/bin/python", "-u", "-m", "surgeon.eval", "train-router"], check=False)
    subprocess.run([".venv/bin/python", "-u", "-m", "surgeon.eval", "cascades", "--split", "dev"], check=False)
    state.mark("router_and_cascades", "done")
except Exception as exc:  # noqa: BLE001
    state.mark("router_and_cascades", "error", error=str(exc)[:200])

subprocess.run([".venv/bin/python", "-u", "-m", "surgeon.eval", "report", "--split", "dev"], check=False)
subprocess.run(["bash", "scripts/site/sync.sh"], check=False)
state.log("build_rest complete")
state.mark("build_rest", "done")
PY

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) build_rest exit $?"
