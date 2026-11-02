"""Rewrite-rule cache — GenRewrite-style hints from verified accepts.

Fingerprint cache reuses an exact shape. This store keeps short before→after
examples keyed by shape tokens so near-miss queries get structural hints in
the prompt without another full cold generation from scratch.
"""

from __future__ import annotations

import json
from pathlib import Path

from surgeon.sql import normalize

from .systems import shape
from .workload_cache import fingerprint

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / ".local" / "training" / "rewrite_rules.jsonl"


class RewriteRuleCache:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_PATH
        self.rules: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("original") and row.get("rewrite"):
                row.setdefault("shape", sorted(shape(row["original"])))
                self.rules.append(row)

    def remember(self, original: str, rewrite: str, meta: dict | None = None) -> None:
        if normalize(original) == normalize(rewrite):
            return
        tokens = sorted(shape(original))
        fp = fingerprint(original)
        # Dedupe by fingerprint.
        self.rules = [r for r in self.rules if r.get("fingerprint") != fp]
        row = {
            "fingerprint": fp,
            "original": original,
            "rewrite": rewrite,
            "shape": tokens,
            "hint": _hint(original, rewrite),
            "meta": meta or {},
        }
        self.rules.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps({k: v for k, v in row.items() if k != "shape"}) + "\n")

    def retrieve(self, sql: str, k: int = 3) -> list[dict]:
        if not k or not self.rules:
            return []
        target = shape(sql)
        scored = sorted(
            self.rules,
            key=lambda r: -len(target & set(r.get("shape") or []))
            / max(1, len(target | set(r.get("shape") or []))),
        )
        out = []
        for row in scored[:k]:
            out.append({
                "hint": row.get("hint") or "verified structural rewrite",
                "query": row["original"][:500],
                "rewrite": row["rewrite"][:500],
            })
        return out


def _hint(original: str, rewrite: str) -> str:
    """Tiny natural-language-ish cue from token diffs (not a formal rule DSL)."""
    before = shape(original)
    after = shape(rewrite)
    added = sorted(after - before)[:8]
    removed = sorted(before - after)[:8]
    parts = []
    if removed:
        parts.append("removed " + ", ".join(removed))
    if added:
        parts.append("added " + ", ".join(added))
    return "; ".join(parts) if parts else "structural rewrite (verified equivalent + faster)"


def seed_from_harness_runs(
    run_names: tuple[str, ...] = ("open-harness", "fw-nemotron-harness", "oss20b-harness"),
    path: Path | None = None,
) -> dict:
    """Bootstrap rule cache from sealed accepted rewrites."""
    out = path or DEFAULT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    cases = {}
    for line in (ROOT / "benchmarks" / "eval_v2" / "cases.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            cases[c["id"]] = c
    seen: set[str] = set()
    rows: list[dict] = []
    runs = ROOT / "benchmarks" / "eval_v2" / "runs"
    for name in run_names:
        f = runs / name / "dev_t0.jsonl"
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            case = cases.get(row.get("case"))
            if not case or row.get("outcome") != "accepted" or not row.get("result_sql"):
                continue
            orig, rewrite = case["sql"], row["result_sql"]
            if normalize(orig) == normalize(rewrite):
                continue
            fp = fingerprint(orig)
            if fp in seen:
                continue
            seen.add(fp)
            rows.append({
                "fingerprint": fp,
                "original": orig,
                "rewrite": rewrite,
                "hint": _hint(orig, rewrite),
                "meta": {"source": name, "case": row["case"]},
            })
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return {"rules": len(rows), "path": str(out)}
