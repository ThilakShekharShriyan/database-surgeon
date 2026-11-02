"""Build, validate and freeze the eval v2 case set.

Splits are by template, never by instance: a held-out template contributes no
dev or train instance, so a system cannot memorize its shape. Calcite inputs
are split by a hash of their SQL. The frozen file's sha256 goes into every run
manifest, and the runner refuses the held-out split until systems are frozen.
"""

import hashlib
import json
import math
from collections import defaultdict

from ..config import ROOT
from ..database import Database
from ..lab import LAB_CONTEXT, suite_cases
from ..workload import EVAL_SCHEMAS, SCHEMA
from .synth import TEMPLATES, instantiate

OUT = ROOT / "benchmarks" / "eval_v2"
CASES_FILE = OUT / "cases.jsonl"
MANIFEST_FILE = OUT / "manifest.json"
CONTEXT = SCHEMA + "\n" + LAB_CONTEXT
DEV_PER_TEMPLATE, HELDOUT_PER_TEMPLATE = 3, 4
HELDOUT_FRACTION = 0.3
LEGACY_KIND = {"nullable_antijoin": "trap", "count_nonnull": "trap", "already_indexed": "decoy"}


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def heldout_templates():
    """Per family, the ceil(n/3) templates with the smallest hash are held out."""
    families = defaultdict(list)
    for template in TEMPLATES:
        families[template[1]].append(template[0])
    held = set()
    for names in families.values():
        names.sort(key=_digest)
        held.update(names[:math.ceil(len(names) / 3)])
    return held


def train_instances(per_template=20, start_seed=100):
    """Training prompts come only from non-held-out templates and fresh seeds."""
    held = heldout_templates()
    return [instantiate(t, seed) for t in TEMPLATES if t[0] not in held
            for seed in range(start_seed, start_seed + per_template)]


def _candidates():
    held = heldout_templates()
    cases = []
    for template in TEMPLATES:
        split = "heldout" if template[0] in held else "dev"
        count = HELDOUT_PER_TEMPLATE if split == "heldout" else DEV_PER_TEMPLATE
        for seed in range(count):
            cases.append(dict(instantiate(template, seed), split=split))
    for case in suite_cases("all"):
        cases.append({"id": case["id"], "template": case.get("template_id", case["id"]),
                      "family": case["family"], "kind": LEGACY_KIND.get(case["id"], "rewrite"),
                      "source": case.get("source", "own_synthetic_v1"), "sql": case["sql"],
                      "reference_sql": None, "ordered": False, "split": "dev"})
    taken = {case["sql"] for case in cases}
    for line in (ROOT / "benchmarks" / "sources" / "rbot" / "calcite.jsonl").read_text().splitlines():
        record = json.loads(line)
        sql = record["input_sql"].strip().rstrip(";").strip()
        if sql in taken or record["input_sql"] in taken:
            continue
        taken.add(sql)
        name = sorted(r["name"] for r in record["rewrites"])[0]
        split = "heldout" if int(_digest(sql)[:8], 16) / 0xFFFFFFFF < HELDOUT_FRACTION else "dev"
        cases.append({"id": "calcite_" + name, "template": "calcite:" + name, "family": "calcite",
                      "kind": "rewrite", "source": "R-Bot / Apache Calcite rule test input", "sql": sql,
                      "reference_candidates": [r["output_sql"].strip().rstrip(";") for r in record["rewrites"]],
                      "reference_sql": None, "ordered": False, "split": split})
    return cases


def build(repeats=3, log=print):
    db = Database(5000)
    db.enforce_types = True
    kept, dropped = [], []
    for case in _candidates():
        try:
            db.columns(case["sql"])
            for schema in EVAL_SCHEMAS:
                db.rows(case["sql"], schema)
        except Exception as exc:  # noqa: BLE001 - unrunnable public inputs are expected
            dropped.append({"id": case["id"], "reason": str(exc)[:200]})
            continue
        references = case.pop("reference_candidates", None) or ([case["reference_sql"]] if case["reference_sql"] else [])
        case["reference_sql"] = None
        for reference in references:
            try:
                verdict = db.check(case["sql"], reference, EVAL_SCHEMAS, ordered=case["ordered"])
            except Exception:  # noqa: BLE001
                continue
            if verdict["equivalent"]:
                case["reference_sql"] = reference
                break
            if case["source"] == "synthetic":
                raise ValueError(f"Hand reference for {case['id']} is not equivalent: {verdict}")
        if case["reference_sql"]:
            timing = db.benchmark(case["sql"], case["reference_sql"], repeats)
            case["original_ms"] = round(timing["original_ms"], 3)
            case["reference_ms"] = round(timing["candidate_ms"], 3)
            case["headroom"] = timing["reduction"] >= 0.2
        else:
            plan = db.plan(case["sql"], True)
            case["original_ms"] = round(plan["Execution Time"], 3)
            case["reference_ms"] = None
            case["headroom"] = None
        case["schema_context"] = CONTEXT
        kept.append(case)
        log(f"{case['split']:8} {case['id']:40} {case['original_ms']:>9} ms  ref={case['reference_ms']}")
    ids = [case["id"] for case in kept]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids.")
    OUT.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(case, sort_keys=True) + "\n" for case in kept)
    CASES_FILE.write_text(body)
    splits = defaultdict(list)
    for case in kept:
        splits[case["split"]].append(case["id"])
    manifest = {
        "cases_sha256": _digest(body),
        "counts": {split: len(v) for split, v in splits.items()},
        "families": dict(sorted(_count(kept, "family").items())),
        "kinds": dict(sorted(_count(kept, "kind").items())),
        "heldout_templates": sorted(heldout_templates()),
        "dropped": dropped,
        "fixtures": db.preflight(EVAL_SCHEMAS)["fixtures"],
        "note": "Synthetic microfixtures on PostgreSQL 16; not benchmark-scale data.",
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def _count(cases, key):
    counts = defaultdict(int)
    for case in cases:
        counts[case[key]] += 1
    return counts


def load_cases(split):
    """Return frozen cases for "dev" or "heldout"; verifies the file hash."""
    manifest = json.loads(MANIFEST_FILE.read_text())
    body = CASES_FILE.read_text()
    if _digest(body) != manifest["cases_sha256"]:
        raise ValueError("Frozen eval v2 cases changed; rebuild deliberately with `surgeon eval build`.")
    cases = [json.loads(line) for line in body.splitlines()]
    return [case for case in cases if case["split"] == split], manifest["cases_sha256"]
