#!/usr/bin/env bash
# Free Muse Glimmer LoRA SFT via Serverless Training (local JSONL — no Datasets upload).
# Docs: https://docs.fireworks.ai/fine-tuning/training-api/cookbook/muse-glimmer
#   scripts/finetune/muse_glimmer_serverless.sh plan
#   scripts/finetune/muse_glimmer_serverless.sh prepare
#   scripts/finetune/muse_glimmer_serverless.sh launch
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f .env.local ]] && set -a && source .env.local && set +a
[[ -n "${FIREWORKS_API_KEY:-}" ]] || { echo "FIREWORKS_API_KEY missing"; exit 1; }

COOKBOOK="$ROOT/.local/cookbook/training"
FILE="$ROOT/.local/training/fireworks_sft.jsonl"
RUN=${FW_RUN_ID:-sql-specialist-$(date +%Y%m%d-%H%M%S)}
PY="$ROOT/.venv/bin/python"

test -s "$FILE" || {
  echo "Build dataset first: $PY scripts/private_retrain_loop.py export-sft"
  exit 1
}
test -d "$COOKBOOK" || git clone --depth 1 https://github.com/fw-ai/cookbook.git "$ROOT/.local/cookbook"
"$PY" -c "import fireworks" 2>/dev/null || uv pip install --python "$PY" "fireworks-ai[training]"
uv pip install --python "$PY" -e "$COOKBOOK" >/dev/null

cmd="${1:-plan}"
echo "run_id=$RUN file=$FILE" | tee "$ROOT/.local/training/muse_run.env"
cd "$COOKBOOK"
case "$cmd" in
  plan)
    exec "$PY" -m examples.sft.muse_glimmer_starter plan --surface serverless --file "$FILE" --run-id "$RUN"
    ;;
  prepare)
    exec "$PY" -m examples.sft.muse_glimmer_starter prepare --file "$FILE" --run-id "$RUN"
    ;;
  launch)
    exec "$PY" -m examples.sft.muse_glimmer_starter launch --surface serverless --file "$FILE" --run-id "$RUN"
    ;;
  *)
    echo "usage: $0 plan|prepare|launch"
    exit 2
    ;;
esac
