#!/usr/bin/env bash
# Run from a normal terminal with Docker and network access. Never source key files.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -gt 1 ]]; then
  printf '%s\n' 'Usage: bash scripts/first_baseline.sh [OPENAI_MODEL]' >&2
  exit 2
fi
case "${1:-}" in
  -h|--help)
    printf '%s\n' 'Usage: bash scripts/first_baseline.sh [OPENAI_MODEL]' 'Runs database checks, model discovery, then paid comparisons when a closed model is configured.'
    exit 0
    ;;
  -*)
    printf 'Unsupported option: %s\n' "$1" >&2
    printf '%s\n' 'Usage: bash scripts/first_baseline.sh [OPENAI_MODEL]' 'The optional argument is a model ID; --yolo is not supported.' >&2
    exit 2
    ;;
esac

docker compose up -d --wait
python3 -m surgeon seed
python3 -m surgeon doctor --json
SURGEON_TEST_DATABASE=1 python3 -m unittest discover -s tests -v
python3 -m surgeon run --provider mock

# These are read-only API requests. Failure stops before paid inference.
python3 -m surgeon models openai
python3 -m surgeon models groq

closed_model="${1:-}"
if [[ -z "$closed_model" ]]; then
  closed_model="$(python3 -c 'import os; from surgeon.config import load_env; load_env(); print(os.getenv("OPENAI_MODEL", ""))')"
fi
if [[ -z "$closed_model" ]]; then
  printf '%s\n' 'Set OPENAI_MODEL in .env.local to an accessible closed frontier model, then rerun this script.' >&2
  exit 2
fi

# Same workload, one attempt each, identical output budget; no silent model fallback.
python3 -m surgeon run --provider openai --model "$closed_model" --attempts 1 --max-output-tokens 4096
python3 -m surgeon run --provider groq --attempts 1 --max-output-tokens 4096
python3 -m surgeon report
