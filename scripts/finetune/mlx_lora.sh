#!/usr/bin/env bash
# LoRA SFT on Apple silicon with MLX, then serve an OpenAI-compatible endpoint
# on loopback for `python -m surgeon.eval run specialist-*`.
#   scripts/finetune/mlx_lora.sh train   # writes .local/training/adapters/$NAME
#   scripts/finetune/mlx_lora.sh serve   # http://127.0.0.1:8080/v1
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
BASE=${MLX_BASE_MODEL:-mlx-community/Qwen2.5-Coder-7B-Instruct-4bit}
NAME=${MLX_ADAPTER_NAME:-sql-specialist}
ADAPTER=.local/training/adapters/$NAME
DATA=.local/training/mlx

case "${1:-train}" in
  train)
    test -s "$DATA/train.jsonl" || { echo "Run: .venv/bin/python -m surgeon.eval train-split"; exit 1; }
    mkdir -p "$ADAPTER"
    # Completion-only loss: the prompt (schema, plan, query) is masked; only the
    # JSON answer is learned.
    $PY -m mlx_lm lora --model "$BASE" --train --data "$DATA" --adapter-path "$ADAPTER" \
      --iters "${MLX_ITERS:-300}" --batch-size "${MLX_BATCH:-2}" --num-layers "${MLX_LAYERS:-16}" \
      --learning-rate "${MLX_LR:-1e-4}" --max-seq-length 4096 --mask-prompt \
      --steps-per-eval 50 --val-batches 10 --save-every 100 --grad-checkpoint
    ;;
  serve)
    exec $PY -m mlx_lm server --model "$BASE" --adapter-path "$ADAPTER" --host 127.0.0.1 --port "${MLX_PORT:-8080}"
    ;;
  serve-base)
    exec $PY -m mlx_lm server --model "$BASE" --host 127.0.0.1 --port "${MLX_PORT:-8080}"
    ;;
  *) echo "usage: $0 train|serve|serve-base"; exit 2 ;;
esac
# Evaluate with: LOCAL_BASE_URL=http://127.0.0.1:8080/v1 SPECIALIST_PROVIDER=local \
#   SPECIALIST_MODEL=$BASE .venv/bin/python -m surgeon.eval run specialist-raw specialist-harness
