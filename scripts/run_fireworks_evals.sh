#!/usr/bin/env bash
# Run once FIREWORKS_API_KEY is live. Probes Nemotron/gpt-oss then evaluates.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env.local ] && . ./.env.local; set +a
bash scripts/probe_fireworks.sh
mkdir -p .local/eval_v2
export DEMO_SYSTEM=cascade-surgeon
# Prefer cheap Lightning triage + gpt-oss deep for the 98-case table
.venv/bin/python -u -m surgeon.eval run \
  rules-only open-raw open-harness fw-nemotron-harness cascade-surgeon \
  --trials 1 --workers 2 --max-usd 3 \
  2>&1 | tee .local/eval_v2/fireworks_evals.log
.venv/bin/python -m surgeon.eval report --split dev
bash scripts/site/sync.sh || true
echo "Fireworks evals complete. Refresh Judge pitch tab."
