#!/usr/bin/env python3
"""Private Postgres retrain loop (eval-recipes pattern + Fireworks optional SFT).

Business problem
----------------
Agentic stacks (coding agents, BI copilots, ORM generators) explode SELECT volume
against customer PostgreSQL. Query shapes and schemas are *IP* — they must not
leave the VPC. Frontier APIs bill per call and still ship corrupt SQL without a
gate.

Loop (all steps local by default)
---------------------------------
  1. Ingest pg_stat_statements / workload JSONL (stays on disk under .local/)
  2. Run surgical harness (hard gate: equivalence + speedup)
  3. Score with eval-recipes-shaped soft recipes (shape / abstain / tools)
  4. Export only *accepted* turns to SFT JSONL (never held-out templates)
  5. Optional: Fireworks managed LoRA on Muse Glimmer (free SFT thru 2026-11-30)
     — upload only the verified-win chat rows, from the customer account
  6. Re-eval specialist vs open-raw / frontier on the fixed eval_v2 gate

Usage
-----
  .venv/bin/python scripts/private_retrain_loop.py plan
  .venv/bin/python scripts/private_retrain_loop.py score-runs
  .venv/bin/python scripts/private_retrain_loop.py export-sft
  .venv/bin/python scripts/private_retrain_loop.py pitch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from surgeon.eval_recipes_bridge import (  # noqa: E402
    evaluate_sql_turn,
    training_eligible,
)

OUT = ROOT / ".local" / "training"
RUNS = ROOT / "benchmarks" / "eval_v2" / "runs"


BUSINESS_PITCH = """
# Private specialist loop — judge / customer pitch

**Who.** Platform DBAs + FinOps owning PostgreSQL under agentic traffic
(coding agents, text-to-SQL, ORM codegen). Workload fingerprints are private.

**Why now.** Agent fleets multiply SELECT calls 10–100×. Every unguarded LLM
rewrite is another chance to corrupt rows *and* another frontier API invoice.
You cannot ship schemas/SQL to a third-party trainer without a trust boundary.

**What we do.**
1. Keep raw `pg_stat_statements` + schemas in-VPC.
2. Fingerprint cache (pos/neg) so repeated agent shapes skip the LLM at $0.
3. Verify candidates with the surgical harness (0 wrong returned SLA).
4. Score turns with Eval-Recipes-style recipes (code + soft judges).
5. Distill only accepted rewrites into a LoRA (Fireworks Muse Glimmer SFT is
   free until 2026-11-30) — or train fully on-prem (MLX / Vast). Optional DPO
   on (accepted ≻ incorrect) once ≥200 pairs exist.
6. Serve the specialist *behind* the same harness; re-measure on sealed eval_v2.

**FT flywheel (optional).** Harness is the product. SFT/DPO only raise first-pass
accept and cut cascade spend — never replace equivalence. See docs/CRAZY_HARNESS.md.

**Money.** Cut DB CPU on slow queries (FinOps) *and* collapse $/1k agent SQL
calls via fingerprint cache + rules + small specialist cascade. Training data
never includes held-out templates.
""".strip()


def cmd_plan(_: argparse.Namespace) -> None:
    stats_path = OUT / "specialist_stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    print(
        json.dumps(
            {
                "mode": "private_retrain_loop",
                "eval_recipes": {
                    "upstream": "https://github.com/microsoft/eval-recipes",
                    "local_bridge": "surgeon/eval_recipes_bridge.py",
                    "hard_gate": "harness_outcome (accepted ≥80)",
                    "soft": ["sql_json_shape", "tool_usage_abstain"],
                },
                "privacy": {
                    "raw_sql_default": "stays under .local/ / customer VPC",
                    "export_policy": "accepted harness wins only; no held-out templates",
                    "optional_upload": "Fireworks managed SFT on customer account",
                },
                "sft_ready": stats,
                "workload_cache": str((OUT / "workload_cache.jsonl").relative_to(ROOT))
                if (OUT / "workload_cache.jsonl").exists()
                else None,
                "flywheel": "docs/CRAZY_HARNESS.md",
                "next": [
                    "python scripts/private_retrain_loop.py seed-cache",
                    "python scripts/private_retrain_loop.py score-runs",
                    "python scripts/private_retrain_loop.py export-sft",
                    "FW_BASE_MODEL=accounts/fireworks/models/muse-glimmer-30b "
                    "bash scripts/finetune/fireworks_sft.sh train   # free SFT thru Nov 30",
                    "SPECIALIST_PROVIDER=fireworks SPECIALIST_MODEL=accounts/<acct>/models/<lora> "
                    ".venv/bin/python -m surgeon.eval run specialist-harness --split dev",
                ],
            },
            indent=2,
        )
    )


def cmd_seed_cache(_: argparse.Namespace) -> None:
    from surgeon.eval.workload_cache import seed_from_harness_runs

    print(json.dumps(seed_from_harness_runs(), indent=2))


async def _score_row(case_id: str, row: dict) -> dict:
    messages = [
        {
            "role": "user",
            "content": f"case={case_id}",
            "metadata": {
                "outcome": row.get("outcome"),
                "speedup": row.get("speedup") or 0,
            },
        },
        {
            "role": "assistant",
            "content": json.dumps(
                {"sql": row.get("result_sql") or "", "rationale": row.get("rationale") or ""}
            ),
        },
    ]
    outputs = await evaluate_sql_turn(messages)
    return {
        "case": case_id,
        "eligible": training_eligible(outputs),
        "scores": [o.__dict__ for o in outputs],
    }


def cmd_score_runs(_: argparse.Namespace) -> None:
    prefer = ["open-harness", "oss20b-harness", "rules-only"]
    path = None
    for name in prefer:
        candidate = RUNS / name / "dev_t0.jsonl"
        if candidate.exists():
            path = candidate
            break
    if not path:
        print(json.dumps({"error": "no harness run JSONL found under benchmarks/eval_v2/runs"}))
        sys.exit(1)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    async def _all() -> list[dict]:
        return list(await asyncio.gather(*[_score_row(r["case"], r) for r in rows]))

    scored = asyncio.run(_all())
    eligible = sum(1 for s in scored if s["eligible"])
    out = OUT / "eval_recipes_scores.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(s) + "\n" for s in scored))
    print(
        json.dumps(
            {
                "source": str(path.relative_to(ROOT)),
                "scored": len(scored),
                "training_eligible": eligible,
                "out": str(out),
            },
            indent=2,
        )
    )


def cmd_export_sft(_: argparse.Namespace) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_specialist_dataset", ROOT / "scripts" / "build_specialist_dataset.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.main()
    print(
        json.dumps(
            {
                "note": "SFT rows are verified wins only — still treat as sensitive; "
                "upload only from the customer Fireworks account or train on-prem.",
                "stats": json.loads((OUT / "specialist_stats.json").read_text()),
            },
            indent=2,
        )
    )


def cmd_pitch(_: argparse.Namespace) -> None:
    print(BUSINESS_PITCH)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=["plan", "seed-cache", "score-runs", "export-sft", "pitch"],
    )
    args = p.parse_args()
    {
        "plan": cmd_plan,
        "seed-cache": cmd_seed_cache,
        "score-runs": cmd_score_runs,
        "export-sft": cmd_export_sft,
        "pitch": cmd_pitch,
    }[args.command](args)


if __name__ == "__main__":
    main()
