#!/usr/bin/env python3
"""Explicit bounded comparison: 14 cases x three models x one candidate attempt."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from surgeon.config import load_env
from surgeon.__main__ import run
from surgeon.artifacts import persist
from surgeon.config import ROOT

load_env()
runs = []
for provider, model in (("groq", "openai/gpt-oss-20b"),
                        ("groq", "openai/gpt-oss-120b"),
                        ("openai", "gpt-6.1-sol")):
    print("Starting bounded comparison: " + provider + " / " + model, flush=True)
    args = argparse.Namespace(provider=provider, model=model, suite="all", case=None,
                              attempts=1, max_output_tokens=4096, repeats=5,
                              min_reduction=.20, timeout_ms=5000)
    directory, summary = run(args)
    runs.append({"run_id": directory.name, "model": model, "summary": summary})
    persist(ROOT / "results" / "today-comparison.json", {"runs": runs, "scope": "development / synthetic microfixtures"})
print(json.dumps({"completed_models": len(runs), "errors": sum(r["summary"]["errors"] for r in runs)}, indent=2))
