#!/usr/bin/env bash
# Database readiness and correctness checks only; never calls model providers.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -ne 0 ]]; then
  printf '%s\n' 'Usage: bash scripts/check_local.sh (no arguments; no paid API calls)' >&2
  exit 2
fi

docker compose config --quiet
docker compose up -d --wait
python3 -m surgeon seed
python3 -m surgeon doctor --json
SURGEON_TEST_DATABASE=1 python3 -m unittest discover -s tests -v
python3 -m surgeon run --provider mock
python3 -m surgeon report
