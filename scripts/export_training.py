#!/usr/bin/env python3
"""Export reviewed-by-execution development seeds; never launch training."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from surgeon.config import ROOT
from surgeon.workload import SCHEMA, seed_sql
from surgeon.lab import suite_cases
from surgeon.providers import SYSTEM
from surgeon.artifacts import persist

output = ROOT / ".local" / "training"
output.mkdir(parents=True, exist_ok=True)
current_fixture = hashlib.sha256((SCHEMA + seed_sql()).encode()).hexdigest()
cases = {case["id"]: case for case in suite_cases("all")}
rows, provenance, seen = [], [], set()
for manifest_path in sorted((ROOT / "results").glob("*/manifest.json")):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("mock") or manifest.get("state") != "completed" or manifest.get("split") != "development":
        continue
    if manifest.get("fixture_sha256") != current_fixture:
        continue
    for path in manifest_path.parent.glob("*.json"):
        record = json.loads(path.read_text())
        case = cases.get(record.get("case_id"))
        if not case:
            continue
        for attempt in record.get("attempts", []):
            generation = attempt.get("generation")
            if not generation or attempt["status"] not in ("accepted", "no_change"):
                continue
            identity = hashlib.sha256((record["original_sql"] + "\n" + generation["sql"]).encode()).hexdigest()
            if identity in seen:
                continue
            seen.add(identity)
            user = {"query": record["original_sql"], "schema": SCHEMA + "\n" + case.get("schema_context", ""),
                    "previous_attempts": []}
            assistant = {"sql": generation["sql"], "rationale": generation["rationale"]}
            rows.append({"messages": [{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": json.dumps(user)},
                                      {"role": "assistant", "content": json.dumps(assistant)}]})
            provenance.append({"row": len(rows), "source_run": manifest["run_id"], "case_id": case["id"],
                               "template_id": case.get("template_id", case["id"]), "model": generation["model"],
                               "status": attempt["status"], "identity_sha256": identity,
                               "label": "finite-instance-verified development seed; manual review required",
                               "input_reconstruction": "schema-only SFT prompt; original EXPLAIN plan was not persisted",
                               "on_policy_rl_eligible": False})
data = "".join(json.dumps(row) + "\n" for row in rows)
(output / "seed_sft.jsonl").write_text(data)
manifest = {"version": 1, "split": "training_seed_from_development", "rows": len(rows),
            "unique_template_groups": len({r["template_id"] for r in provenance}),
            "fixture_sha256": current_fixture, "jsonl_sha256": hashlib.sha256(data.encode()).hexdigest(),
            "ready_for_training": False, "on_policy_rl_eligible": False,
            "blockers": ["Manual SQL/label review", "Create independent validation/test split", "Verify provider/model training rights and tokenization"],
            "note": "No held-out data or public reference rewrites exported. Distinct query/target pairs are deduplicated; template variants still need group-aware splits.",
            "provenance": provenance}
persist(output / "manifest.json", manifest)
print(json.dumps({"rows": len(rows), "unique_template_groups": manifest["unique_template_groups"],
                  "dataset": str(output / "seed_sft.jsonl"), "ready_for_training": False}, indent=2))
