"""Offline experiment reports; reading artifacts never invokes providers."""
import hashlib
import json
from pathlib import Path

from .artifacts import persist


COMPARISON_FIELDS = (
    "artifact_version", "workload_sha256", "fixture_sha256", "evaluator_sha256",
    "selected_cases", "database", "split", "max_attempts", "max_output_tokens",
    "repeats", "statement_timeout_ms", "min_reduction", "mock",
)


def comparison_key(manifest):
    identity = {key: manifest.get(key) for key in COMPARISON_FIELDS}
    # Older experiments lack fixture/evaluator fingerprints and cannot form a fair group.
    if manifest.get("artifact_version") != 2:
        identity["legacy_run_id"] = manifest["run_id"]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def build_report(results_root, output):
    output = Path(output)
    if output.suffix != ".md":
        raise ValueError("Report output must end in .md (a companion .json index is also written).")
    groups = {}
    skipped = []
    for path in sorted(Path(results_root).glob("*/manifest.json")):
        try:
            manifest = json.loads(path.read_text())
            summary = json.loads(path.with_name("summary.json").read_text())
            if summary["run_id"] != manifest["run_id"]:
                raise ValueError("Manifest and summary identify different runs.")
            records = []
            for case_file in sorted(path.parent.glob("*.json")):
                if case_file.name in ("manifest.json", "summary.json"):
                    continue
                record = json.loads(case_file.read_text())
                if "case_id" in record:
                    records.append(record)
            groups.setdefault(comparison_key(manifest), []).append((manifest, summary, records))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            skipped.append({"directory": path.parent.name, "error": str(exc)})
    lines = ["# Database Surgeon experiment report", "",
             "Development fixtures only. Mock runs are fixed examples, not model-performance evidence.",
             "Groups require matching cases, fixture content, evaluator, database version and budgets.",
             "Incomplete and failed runs are shown explicitly. Repeated trials are needed before choosing a winner.", ""]
    index = []
    for key, runs in groups.items():
        manifest = runs[0][0]
        lines += [f"## Comparison group {key}", "",
                  f"Split: {cell(manifest.get('split', 'unknown'))}; mock: {manifest.get('mock')}; "
                  f"attempts/case: {manifest.get('max_attempts')}; output tokens/attempt: {manifest.get('max_output_tokens')}; "
                  f"timing pairs: {manifest.get('repeats')}.", "",
                  "| Run | Provider | Requested model | State | Accepted | Incorrect rejected | Errors | Estimated API cost |",
                  "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |"]
        for manifest, summary, records in runs:
            state = manifest.get("state", "legacy/unverified")
            cost = summary.get("estimated_model_cost_usd")
            cost_text = f"${cost:.6f}" if cost is not None else "unknown"
            lines.append("| " + " | ".join(cell(v) for v in (
                manifest["run_id"], manifest["provider"], manifest.get("requested_model") or "mock-fixture",
                state, f"{summary['accepted']}/{summary['cases']}",
                summary.get("incorrect_candidates_rejected", 0), summary.get("errors", 0), cost_text)) + " |")
            index.append({"run_id": manifest["run_id"], "comparison_group": key, "state": state})
        lines += ["", "### Candidate measurements", "",
                  "Each speedup is the baseline median divided by the candidate median for that attempt.", "",
                  "| Run | Case | Attempt | Returned model | Status | Baseline ms | Candidate ms | Speedup |",
                  "| --- | --- | ---: | --- | --- | ---: | ---: | ---: |"]
        for manifest, _, records in runs:
            for record in records:
                for attempt in record.get("attempts", []):
                    timing = attempt.get("benchmark", {})
                    def number(name, suffix=""):
                        value = timing.get(name)
                        return f"{value:.3f}{suffix}" if value is not None else "—"
                    lines.append("| " + " | ".join(cell(v) for v in (
                        manifest["run_id"], record["case_id"], attempt["attempt"],
                        attempt.get("generation", {}).get("model", attempt.get("returned_model", "—")),
                        attempt["status"], number("original_ms"), number("candidate_ms"), number("speedup", "x"))) + " |")
        lines.append("")
    if not groups:
        lines += ["No readable experiment artifacts found.", ""]
    if skipped:
        lines += ["## Unreadable runs", ""]
        lines += [f"- {cell(item['directory'])}: {cell(item['error'])}" for item in skipped]
    # Use the same atomic writer for the machine-readable index.
    persist(output.with_suffix(".json"), {"runs": index, "skipped": skipped})
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"groups": len(groups), "runs": len(index), "skipped": len(skipped), "report": str(output)}
