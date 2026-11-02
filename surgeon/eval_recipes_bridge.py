"""Eval-Recipes-shaped evaluators for SQL surgery (privacy-first).

microsoft/eval-recipes defines *recipes*: mix of deterministic code + optional
LLM judges that return ``EvaluationOutput(score 0–100, applicable, metadata)``.
We mirror that protocol without requiring their Docker CLI-agent harness.

Hard gate for production / training labels remains our execution harness
(equivalence + speedup). Soft recipes catch agentic regressions (tool misuse,
guidance drift) without shipping raw workloads off-box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EvaluationOutput:
    """Compatible with eval_recipes.schemas.EvaluationOutput shape."""

    eval_name: str
    applicable: bool
    score: float  # 0–100
    metadata: dict[str, Any] = field(default_factory=dict)


class EvaluatorProtocol(Protocol):
    async def evaluate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> EvaluationOutput: ...


def _last_assistant(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return ""


class SqlJsonShapeEvaluator:
    """Soft recipe: assistant must return {"sql": ..., "rationale": ...}."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    async def evaluate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> EvaluationOutput:
        import json

        raw = _last_assistant(messages).strip()
        if not raw:
            return EvaluationOutput("sql_json_shape", True, 0.0, {"reason": "empty"})
        try:
            # tolerate fenced JSON
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            obj = json.loads(raw)
        except Exception as exc:
            return EvaluationOutput("sql_json_shape", True, 0.0, {"reason": str(exc)[:120]})
        ok = isinstance(obj, dict) and isinstance(obj.get("sql"), str) and obj["sql"].strip()
        return EvaluationOutput(
            "sql_json_shape",
            True,
            100.0 if ok else 25.0,
            {"has_rationale": bool(obj.get("rationale")) if isinstance(obj, dict) else False},
        )


class HarnessOutcomeEvaluator:
    """Hard recipe: score from a prior harness row (never trusts the LLM alone).

    Expected metadata on the last user message: ``harness_outcome``, ``speedup``.
    Outcomes: accepted | abstained | incorrect | error.
    """

    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    async def evaluate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> EvaluationOutput:
        meta: dict[str, Any] = {}
        for msg in reversed(messages):
            if isinstance(msg.get("harness"), dict):
                meta = msg["harness"]
                break
            if msg.get("role") == "user" and isinstance(msg.get("metadata"), dict):
                meta = msg["metadata"]
                break
        outcome = (meta.get("outcome") or meta.get("harness_outcome") or "").lower()
        speedup = float(meta.get("speedup") or 0)
        if outcome == "accepted":
            # Cap at 100; reward extra speedup lightly.
            score = min(100.0, 80.0 + min(20.0, max(0.0, (speedup - 1.25) * 10)))
        elif outcome == "abstained":
            score = 55.0  # safe no-op is better than corruption
        elif outcome == "incorrect":
            score = 0.0
        else:
            score = 20.0
        return EvaluationOutput(
            "harness_outcome",
            True,
            score,
            {"outcome": outcome or "unknown", "speedup": speedup},
        )


class ToolUsageAbstainEvaluator:
    """Agentic recipe: if EXPLAIN / verify tools fail, model must abstain (keep original)."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    async def evaluate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> EvaluationOutput:
        tool_failed = False
        for msg in messages:
            if msg.get("role") == "tool" and (
                msg.get("is_error") or "error" in str(msg.get("content", "")).lower()[:80]
            ):
                tool_failed = True
                break
        if not tool_failed:
            return EvaluationOutput("tool_usage_abstain", False, 0.0, {})
        assistant = _last_assistant(messages).lower()
        # Heuristic: abstain language or identical SQL echoed as unchanged
        abstained = any(w in assistant for w in ("unchanged", "abstain", "keep the original", "not confident"))
        return EvaluationOutput(
            "tool_usage_abstain",
            True,
            100.0 if abstained else 10.0,
            {"tool_failed": True, "abstained": abstained},
        )


async def evaluate_sql_turn(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    evaluations: list[Any] | None = None,
) -> list[EvaluationOutput]:
    """High-level API analogous to eval_recipes.evaluate.evaluate."""
    registry: dict[str, type] = {
        "sql_json_shape": SqlJsonShapeEvaluator,
        "harness_outcome": HarnessOutcomeEvaluator,
        "tool_usage_abstain": ToolUsageAbstainEvaluator,
    }
    selected = evaluations or ["sql_json_shape", "harness_outcome", "tool_usage_abstain"]
    out: list[EvaluationOutput] = []
    for item in selected:
        if isinstance(item, str):
            out.append(await registry[item]().evaluate(messages, tools))
        else:
            out.append(await item().evaluate(messages, tools))
    return out


def training_eligible(outputs: list[EvaluationOutput], *, min_harness: float = 80.0) -> bool:
    """Only export SFT when the hard harness recipe clears — privacy boundary gate."""
    by = {o.eval_name: o for o in outputs}
    hard = by.get("harness_outcome")
    return bool(hard and hard.applicable and hard.score >= min_harness)
