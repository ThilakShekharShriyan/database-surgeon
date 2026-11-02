#!/usr/bin/env python3
"""Overnight Database Surgeon runner.

Phases are idempotent: each checks disk markers and resumes. Never destroys
Vast instances that are not labeled database-surgeon-sft. Spend ceilings come
from state.json budgets.

Usage:
  .venv/bin/python -u scripts/overnight/orchestrator.py
  .venv/bin/python -u scripts/overnight/orchestrator.py --status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overnight import state  # noqa: E402
from overnight import vast_manager as vast  # noqa: E402

PY = ROOT / ".venv/bin/python"
RUNS = ROOT / "benchmarks/eval_v2/runs"


def load_env():
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sh(args, env=None, check=True, log_name: str | None = None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    state.log("$ " + " ".join(args))
    log_path = state.DIR / (log_name or "command.log")
    with log_path.open("a") as handle:
        handle.write("\n$ " + " ".join(args) + "\n")
        handle.flush()
        result = subprocess.run(args, cwd=ROOT, env=merged, check=False,
                                stdout=handle, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}")
    return result


def eval_cmd(*args, env=None):
    name = "eval_" + "_".join(a for a in args[:3] if not a.startswith("-")).replace("/", "-") + ".log"
    return sh([str(PY), "-u", "-m", "surgeon.eval", *args], env=env, log_name=name)


def records(system: str, split="dev") -> int:
    total = 0
    directory = RUNS / system
    if not directory.exists():
        return 0
    for path in directory.glob(f"{split}_t*.jsonl"):
        total += sum(1 for line in path.read_text().splitlines() if line.strip())
    return total


def trials_complete(system: str, needed: int, cases: int = 98) -> bool:
    directory = RUNS / system
    if not directory.exists():
        return False
    complete = 0
    for path in sorted(directory.glob("dev_t*.jsonl")):
        n = sum(1 for line in path.read_text().splitlines() if line.strip())
        if n >= cases * 0.9:  # allow a few rate-limit holes
            complete += 1
    return complete >= needed


def phase(name: str):
    def decorator(fn):
        def wrapped():
            if state.done(name):
                state.log(f"skip {name} (done)")
                return True
            state.mark(name, "running")
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                state.mark(name, "error", error=str(exc)[:500])
                state.log(f"ERROR {name}: {exc}")
                raise
            state.mark(name, "done")
            return True
        wrapped.__name__ = name
        return wrapped
    return decorator


@phase("enrich_training")
def enrich_training():
    """Grow teacher traces if the first pass stopped early (rate limits / budget)."""
    stats_path = ROOT / ".local/training/stats.json"
    traced = 0
    if stats_path.exists():
        traced = json.loads(stats_path.read_text()).get("traced", 0)
    if traced >= 50:
        # 50+ verified teacher traces is enough for overnight SFT smoke; more can
        # be added later without blocking harness / Vast.
        state.log(f"training has {traced} traces — enough to proceed")
        if not (ROOT / ".local/training/mlx/train.jsonl").exists():
            eval_cmd("train-split")
        return
    eval_cmd("train-data", "--per-template", "8", "--max-usd", "4")
    eval_cmd("train-split")


@phase("harness_main")
def harness_main():
    if not trials_complete("oss20b-harness", 3) or not trials_complete("oss120b-harness", 3):
        eval_cmd("run", "oss20b-harness", "oss120b-harness", "--trials", "3", "--max-usd", "8")


@phase("harness_ablations")
def harness_ablations():
    systems = [
        "oss20b-harness-minus-rules", "oss20b-harness-minus-catalog",
        "oss20b-harness-minus-retrieval", "oss20b-harness-minus-best_of",
        "oss20b-harness-minus-repair", "oss20b-harness-minus-precheck",
        "oss20b-harness-minus-verify", "oss20b-verify-only",
        "oss20b-harness-effort-low", "oss20b-harness-effort-high",
    ]
    missing = [s for s in systems if not trials_complete(s, 3)]
    if missing:
        eval_cmd("run", *missing, "--trials", "3", "--max-usd", "10")


@phase("ollama_baselines")
def ollama_baselines():
    # Ensure ollama is up
    subprocess.run(["ollama", "list"], capture_output=True)
    # Only gpt-oss:20b locally — qwen raws were slow and returned many wrongs.
    systems = [
        "ollama-gpt-oss-20b-raw",
        "ollama-gpt-oss-20b-harness",
    ]
    missing = [s for s in systems if not trials_complete(s, 1)]
    if missing:
        eval_cmd("run", *missing, "--trials", "1", "--workers", "1", "--max-usd", "0")


@phase("router_and_cascades")
def router_and_cascades():
    if not trials_complete("oss20b-harness", 1) or not trials_complete("oss120b-harness", 1):
        state.log("router deferred: harness runs incomplete")
        return
    eval_cmd("train-router")
    eval_cmd("cascades", "--split", "dev")
    # Materialize cascade/router as reportable systems via cascades command.
    eval_cmd("report", "--split", "dev")


@phase("vast_sft")
def vast_sft():
    budgets = state.read()["budgets"]
    vast.configure_key()
    credit = vast.credit_usd()
    state.log(f"vast credit=${credit}")
    if credit is not None and credit < 2.0:
        raise RuntimeError(f"Vast credit too low: ${credit}")
    # Never touch foreign instances.
    foreign = vast.foreign_running()
    state.log(f"vast: leaving {len(foreign)} foreign instance(s) alone: "
              + ", ".join(f"{i.get('label')}:{i.get('id')}" for i in foreign))
    instance_id = vast.create_instance(budgets["vast_max_dph"])
    vast.wait_ready(instance_id)
    vast.upload_and_train(instance_id)
    port = vast.start_vllm(instance_id)
    # Evaluate specialist against the same dev split (1 trial first).
    env = {
        "LOCAL_BASE_URL": f"http://127.0.0.1:{port}/v1",
        "SPECIALIST_PROVIDER": "local",
        "SPECIALIST_MODEL": "specialist",
        "SPECIALIST_NAME": "vast-qwen7b-sft",
    }
    eval_cmd("run", "vast-qwen7b-sft-raw", "vast-qwen7b-sft-harness",
             "--trials", "1", "--workers", "2", "--max-usd", "0", env=env)
    # Tear down GPU once eval artifacts exist — stop the bill.
    vast.destroy(instance_id)
    state.spend("vast_job", budgets["vast_usd"], "capped overnight budget for SFT+eval")


@phase("mlx_smoke")
def mlx_smoke():
    """Optional Mac LoRA if the 4-bit weights finished downloading."""
    ref = Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen2.5-Coder-7B-Instruct-4bit/refs/main"
    incomplete = list((Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen2.5-Coder-7B-Instruct-4bit/blobs").glob("*.incomplete"))
    if not ref.exists() or incomplete:
        state.log("mlx: weights incomplete; skipping Mac smoke (Vast covers fine-tune)")
        return
    train = ROOT / ".local/training/mlx/train.jsonl"
    if not train.exists():
        eval_cmd("train-split")
    sh(["bash", "scripts/finetune/mlx_lora.sh", "train"], check=False)


@phase("dev_report")
def dev_report():
    eval_cmd("report", "--split", "dev")
    # Snapshot a human-readable copy for morning.
    src = ROOT / "benchmarks/eval_v2/results/summary_dev.json"
    if src.exists():
        (state.DIR / "summary_dev.json").write_text(src.read_text())


@phase("prep_freeze_note")
def prep_freeze_note():
    """Do not run held-out overnight — only prepare the freeze candidate list."""
    note = state.DIR / "MORNING.md"
    systems = sorted(p.name for p in RUNS.iterdir() if p.is_dir()) if RUNS.exists() else []
    note.write_text(
        "# Overnight finished — morning checklist\n\n"
        "Held-out is **not** run automatically (sealed split).\n\n"
        "## Freeze candidates\n\n"
        + "\n".join(f"- `{s}`" for s in systems)
        + "\n\n```bash\n.venv/bin/python -m surgeon.eval freeze <systems…>\n"
        ".venv/bin/python -m surgeon.eval run <systems…> --split heldout --trials 1\n"
        ".venv/bin/python -m surgeon.eval report --split heldout\n```\n\n"
        "Then: `docs/RESULTS.md`, research Pages site, Rust audit (Phases 6–7).\n"
    )
    state.log(f"wrote {note}")


PHASES = [
    enrich_training,
    harness_main,
    harness_ablations,
    ollama_baselines,
    router_and_cascades,
    vast_sft,
    mlx_smoke,
    dev_report,
    prep_freeze_note,
]


def wait_for_sibling_pipeline(timeout_s=6 * 3600):
    """If the older eval_pipeline.sh is still running harness, wait rather than collide."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = subprocess.run(["pgrep", "-fl", "eval_pipeline.sh|surgeon.eval run"],
                             capture_output=True, text=True).stdout
        # Only wait if the *legacy* pipeline script is alive; we are the overnight one.
        if "eval_pipeline.sh" in out:
            state.log("waiting for legacy eval_pipeline.sh to finish…")
            time.sleep(60)
            continue
        return
    state.log("legacy pipeline wait timed out; continuing with resume semantics")


def status():
    data = state.read()
    print(json.dumps(data, indent=2))
    print("--- runs ---")
    if RUNS.exists():
        for path in sorted(RUNS.iterdir()):
            if path.is_dir():
                print(f"{path.name:40} {records(path.name):4d} records")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--skip-vast", action="store_true")
    parser.add_argument("--from-phase", default="")
    args = parser.parse_args()
    load_env()
    state.ensure()
    if args.status:
        status()
        return
    state.log("=== overnight orchestrator start ===")
    wait_for_sibling_pipeline()
    started = not args.from_phase
    for fn in PHASES:
        name = fn.__name__
        if args.from_phase and not started:
            if name == args.from_phase:
                started = True
            else:
                continue
        if args.skip_vast and name == "vast_sft":
            state.log("skip vast_sft by flag")
            continue
        # Soft-continue on non-fatal phases so one failure does not waste the night.
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            state.log(f"phase {name} failed: {exc}")
            if name in ("vast_sft",):
                try:
                    vast.destroy()
                except Exception as cleanup:  # noqa: BLE001
                    state.log(f"vast cleanup: {cleanup}")
            # Keep going for measurement phases; stop only if harness_main hard-fails.
            if name == "harness_main":
                raise
    state.log("=== overnight orchestrator complete ===")
    data = state.read()
    data["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.write(data)


if __name__ == "__main__":
    main()
