#!/usr/bin/env bash
# Probe FIREWORKS_API_KEY + NVIDIA Nemotron / gpt-oss serverless models.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env.local ] && . ./.env.local; set +a
KEY="${FIREWORKS_API_KEY:-}"
if [ -z "$KEY" ]; then
  echo "FIREWORKS_API_KEY is empty in .env.local"
  echo "Paste a live key from fireworks.ai (or hackathon desk credits), then re-run:"
  echo "  bash scripts/probe_fireworks.sh"
  exit 2
fi
MODELS=(
  "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b"
  "accounts/fireworks/models/gpt-oss-20b"
  "accounts/fireworks/models/nemotron-3-ultra-nvfp4"
  "accounts/fireworks/models/gpt-oss-120b"
)
ok=0
for m in "${MODELS[@]}"; do
  code=$(curl -s -o /tmp/fw_probe.json -w '%{http_code}' \
    https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply OK\"}],\"max_tokens\":4,\"temperature\":0}")
  body=$(python3 -c "import json;d=json.load(open('/tmp/fw_probe.json'));print(((d.get('choices') or [{}])[0].get('message') or {}).get('content') or d.get('error') or d)" 2>/dev/null | head -c 160)
  echo "$code $m :: $body"
  [ "$code" = "200" ] && ok=$((ok+1))
done
echo "live_models=$ok/${#MODELS[@]}"
[ "$ok" -gt 0 ] || exit 1
