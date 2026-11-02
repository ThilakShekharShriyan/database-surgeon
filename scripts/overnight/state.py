"""Persistent overnight state. All paths are under .local/overnight/."""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / ".local" / "overnight"
STATE = DIR / "state.json"
LEDGER = DIR / "spend.jsonl"
LOG = DIR / "night.log"

_DEFAULT = {
    "phase": "boot",
    "phases": {},
    "vast_instance_id": None,
    "vast_label": "database-surgeon-sft",
    "budgets": {
        "groq_openai_usd": 20.0,
        "vast_usd": 8.0,
        "vast_max_dph": 1.20,
    },
    "notes": [],
}


def ensure():
    DIR.mkdir(parents=True, exist_ok=True)
    if not STATE.exists():
        payload = dict(_DEFAULT)
        payload["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        STATE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read():
    ensure()
    return json.loads(STATE.read_text())


def write(data):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(STATE)


def mark(phase: str, status: str, **extra):
    data = read()
    entry = {"status": status, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **extra}
    data["phases"][phase] = entry
    if status in ("running", "done"):
        data["phase"] = phase
    write(data)
    log(f"phase {phase} -> {status}" + (f" {extra}" if extra else ""))


def done(phase: str) -> bool:
    return read().get("phases", {}).get(phase, {}).get("status") == "done"


def log(message: str):
    DIR.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    with LOG.open("a") as handle:
        handle.write(line + "\n")


def spend(kind: str, usd: float | None, detail: str):
    DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as handle:
        handle.write(json.dumps({
            "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": kind, "usd": usd, "detail": detail,
        }) + "\n")
