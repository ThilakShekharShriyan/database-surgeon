#!/usr/bin/env bash
# Rent one GPU on Vast.ai, train SFT+DPO LoRA, serve it with vLLM, and reach it
# only through an SSH tunnel bound to 127.0.0.1 (no public port).
# Needs: `pip install vastai`, VAST_API_KEY in .env.local, an SSH key added to Vast.
#   scripts/finetune/vast/launch.sh up        # rent (prints instance id)
#   scripts/finetune/vast/launch.sh train ID  # copy data, train
#   scripts/finetune/vast/launch.sh serve ID  # vLLM + tunnel on 127.0.0.1:8000
#   scripts/finetune/vast/launch.sh down ID   # destroy (stops billing)
set -euo pipefail
cd "$(dirname "$0")/../../.."
set -a; [ -f .env.local ] && . ./.env.local; set +a
: "${VAST_API_KEY:?Set VAST_API_KEY in .env.local}"
vastai set api-key "$VAST_API_KEY" >/dev/null
MAX_DPH=${VAST_MAX_DOLLARS_PER_HOUR:-1.20}
IMAGE=${VAST_IMAGE:-vllm/vllm-openai:latest}
BASE=${VAST_BASE_MODEL:-unsloth/Qwen2.5-Coder-7B-Instruct}

ssh_args() { vastai ssh-url "$1" | sed -E 's#ssh://([^@]+)@([^:]+):([0-9]+)#-p \3 \1@\2#'; }

case "${1:-}" in
  up)
    # Cheapest verified 24GB+ GPU under the hourly ceiling.
    OFFER=$(vastai search offers "gpu_ram>=24 num_gpus=1 verified=true reliability>0.98 dph_total<=$MAX_DPH" \
      -o dph_total --raw | python3 -c 'import json,sys; o=json.load(sys.stdin); print(o[0]["id"] if o else "")')
    [ -n "$OFFER" ] || { echo "No offer under \$$MAX_DPH/h"; exit 1; }
    vastai create instance "$OFFER" --image "$IMAGE" --disk 60 --ssh --direct
    ;;
  train)
    ID=${2:?instance id}
    read -r -a SSH <<<"$(ssh_args "$ID")"
    scp -P "${SSH[1]}" .local/training/fireworks_sft.jsonl "${SSH[2]}:sft.jsonl"
    scp -P "${SSH[1]}" .local/training/dpo.jsonl "${SSH[2]}:dpo.jsonl"
    scp -P "${SSH[1]}" scripts/finetune/vast/train_trl.py "${SSH[2]}:train_trl.py"
    ssh "${SSH[@]}" "pip install -q unsloth trl datasets && python train_trl.py --base $BASE"
    ;;
  serve)
    ID=${2:?instance id}
    read -r -a SSH <<<"$(ssh_args "$ID")"
    ssh "${SSH[@]}" "nohup vllm serve $BASE --enable-lora --lora-modules specialist=out/dpo \
      --host 127.0.0.1 --port 8000 --max-model-len 8192 > vllm.log 2>&1 &"
    echo "Tunnel: 127.0.0.1:8000 -> instance (Ctrl-C to close)"
    echo "Eval:   LOCAL_BASE_URL=http://127.0.0.1:8000/v1 SPECIALIST_PROVIDER=local SPECIALIST_MODEL=specialist"
    exec ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 "${SSH[@]}"
    ;;
  down) vastai destroy instance "${2:?instance id}" ;;
  *) echo "usage: $0 up|train ID|serve ID|down ID"; exit 2 ;;
esac
