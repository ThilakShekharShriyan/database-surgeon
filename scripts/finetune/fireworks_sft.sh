#!/usr/bin/env bash
# Managed LoRA SFT on Fireworks (docs.fireworks.ai/fine-tuning/fine-tuning-models).
# Default base: Muse Glimmer 30B — SFT free via UI/API until 2026-11-30.
#   scripts/finetune/fireworks_sft.sh check
#   scripts/finetune/fireworks_sft.sh train
#   scripts/finetune/fireworks_sft.sh status
#   scripts/finetune/fireworks_sft.sh deploy
#   scripts/finetune/fireworks_sft.sh teardown
# Prefer REST when firectl is missing (hackathon accounts).
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
[[ -f .env.local ]] && set -a && source .env.local && set +a

BASE=${FW_BASE_MODEL:-accounts/fireworks/models/muse-glimmer-30b}
DATASET=${FW_DATASET:-sql-rewrite-sft-v1}
OUTPUT=${FW_OUTPUT_MODEL:-sql-specialist-v1}
JOB=${FW_JOB:-sql-specialist-sft-v1}
FILE=.local/training/fireworks_sft.jsonl
ACCT=${FW_ACCOUNT_ID:-thilaksshriyan-0lo68}
API=https://api.fireworks.ai/v1

need_key() { [[ -n "${FIREWORKS_API_KEY:-}" ]] || { echo "FIREWORKS_API_KEY missing (.env.local)"; exit 1; }; }
need_data() {
  test -s "$FILE" || {
    echo "Build dataset first:"
    echo "  .venv/bin/python scripts/private_retrain_loop.py export-sft"
    exit 1
  }
}

rest_train() {
  need_key
  need_data
  # Account gate: some hackathon accounts return
  # "dataset uploads are temporarily disabled". Prefer Serverless Training
  # (local JSONL, no Datasets upload) via the Muse Glimmer starter.
  local n size
  n=$(wc -l < "$FILE" | tr -d ' ')
  size=$(wc -c < "$FILE" | tr -d ' ')
  echo "Creating dataset $DATASET ($n examples) on accounts/$ACCT …"
  # Quote ${DATASET}:… so zsh does not treat :upload as a parameter modifier.
  curl -sS -X POST "$API/accounts/$ACCT/datasets" \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"datasetId\":\"$DATASET\",\"dataset\":{\"displayName\":\"SQL specialist SFT\",\"exampleCount\":\"$n\",\"userUploaded\":{},\"format\":\"CHAT\"}}" \
    | tee ".local/training/fw_dataset_create.json"
  echo
  echo "Requesting signed upload endpoint …"
  local ep
  ep=$(curl -sS -X POST "$API/accounts/$ACCT/datasets/${DATASET}:getUploadEndpoint" \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"filenameToSize\":{\"fireworks_sft.jsonl\":\"$size\"}}")
  echo "$ep" | tee ".local/training/fw_upload_ep.json"
  if echo "$ep" | grep -q 'temporarily disabled'; then
    echo
    echo "Managed Datasets upload is disabled on this account."
    echo "Use Serverless Training instead (keeps JSONL local, Muse Glimmer SFT free thru Nov 30):"
    echo "  bash scripts/finetune/muse_glimmer_serverless.sh"
    echo "Or ask Fireworks to enable dataset uploads / use the UI with a preloaded dataset."
    echo "Preloaded on this account: onboarding-prompt-router, onboarding-cord-receipts"
    exit 1
  fi
  echo "Uploading $FILE via :upload …"
  curl -sS -X POST "$API/accounts/$ACCT/datasets/${DATASET}:upload" \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" \
    -F "file=@${FILE};type=application/jsonl;filename=fireworks_sft.jsonl" \
    | tee ".local/training/fw_dataset_upload.json"
  echo
  curl -sS -X POST "$API/accounts/$ACCT/datasets/${DATASET}:validateUpload" \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" \
    -H "Content-Type: application/json" -d '{}' \
    | tee ".local/training/fw_dataset_validate.json"
  echo
  echo "Starting SFT job $JOB → $OUTPUT (base=$BASE) …"
  curl -sS -X POST "$API/accounts/$ACCT/supervisedFineTuningJobs" \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"supervisedFineTuningJobId\": \"$JOB\",
      \"supervisedFineTuningJob\": {
        \"baseModel\": \"$BASE\",
        \"dataset\": \"accounts/$ACCT/datasets/$DATASET\",
        \"outputModel\": \"accounts/$ACCT/models/$OUTPUT\",
        \"loraRank\": ${FW_LORA_RANK:-8},
        \"epochs\": ${FW_EPOCHS:-1}
      }
    }" | tee ".local/training/fw_sft_job.json"
  echo
  echo "Watch: bash scripts/finetune/fireworks_sft.sh status"
  echo "UI: https://app.fireworks.ai/dashboard/fine-tuning/create?type=supervised&baseModel=$BASE"
}

case "${1:-}" in
  check)
    if command -v firectl >/dev/null 2>&1; then
      firectl model get -a fireworks "${BASE##*/}" | grep -Ei 'tunable|lora|name' || true
    else
      need_key
      curl -sS -H "Authorization: Bearer $FIREWORKS_API_KEY" \
        "$API/accounts/fireworks/models/${BASE##*/}" | .venv/bin/python -c \
        "import sys,json; m=json.load(sys.stdin); bd=m.get('baseModelDetails') or {}; print('name',m.get('name')); print('display',m.get('displayName')); print('supervisedLoraTunable',m.get('supervisedLoraTunable')); print('supportsServerlessTraining',m.get('supportsServerlessTraining')); print('base.tunable',bd.get('tunable'))"
    fi
    ;;
  train)
    if command -v firectl >/dev/null 2>&1; then
      need_data
      firectl dataset create "$DATASET" "$FILE" || true
      firectl sftj create --job-id "$JOB" --base-model "$BASE" --dataset "$DATASET" \
        --output-model "$OUTPUT" --lora-rank "${FW_LORA_RANK:-8}" --epochs "${FW_EPOCHS:-1}"
    else
      rest_train
    fi
    ;;
  status)
    need_key
    curl -sS -H "Authorization: Bearer $FIREWORKS_API_KEY" \
      "$API/accounts/$ACCT/supervisedFineTuningJobs/$JOB" | .venv/bin/python -m json.tool
    ;;
  deploy)
    if command -v firectl >/dev/null 2>&1; then
      firectl deployment create "$OUTPUT" --deployment-shape default
    else
      echo "Deploy via UI or firectl (dedicated capacity bills while up)."
      echo "Model: accounts/$ACCT/models/$OUTPUT"
    fi
    ;;
  teardown)
    echo "Delete dedicated deployment when done — it bills while running."
    echo "firectl deployment list | grep $OUTPUT"
    ;;
  *)
    echo "usage: $0 check|train|status|deploy|teardown"
    exit 2
    ;;
esac
# Evaluate with: SPECIALIST_PROVIDER=fireworks SPECIALIST_MODEL=accounts/<you>/models/$OUTPUT \
#   .venv/bin/python -m surgeon.eval run specialist-raw specialist-harness
