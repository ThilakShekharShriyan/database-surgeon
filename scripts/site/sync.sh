#!/usr/bin/env bash
# Export credential-free research evidence to the app and static companion.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -x .venv/bin/python ]; then
  .venv/bin/python scripts/export_research.py
else
  python3 scripts/export_research.py
fi
for py in .venv/bin/python python3; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import matplotlib" 2>/dev/null; then
    "$py" scripts/site/make_figures.py
    break
  fi
done
