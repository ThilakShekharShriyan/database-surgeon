"""One client for every model endpoint the eval compares.

groq / fireworks / local use OpenAI-compatible chat completions; openai uses the
Responses API. "local" covers Ollama, mlx_lm.server and vLLM (on this Mac or a
Vast.ai box) through LOCAL_BASE_URL. Keys come from .env.local only.

Responses are cached on disk by (payload, sample index), so re-running a judge
or resuming an interrupted run costs nothing and returns identical text. The
cached record keeps the original latency and token counts, so latency and cost
metrics still describe the live call.
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.parse

from ..config import ROOT
from ..providers import ProviderHTTPError, credential_pool, request_json

BASES = {"openai": "https://api.openai.com/v1", "groq": "https://api.groq.com/openai/v1",
         "fireworks": "https://api.fireworks.ai/inference/v1"}
PRICES = json.loads((ROOT / "benchmarks" / "prices.json").read_text())["models"]
CACHE_DIR = ROOT / ".local" / "llm_cache"
SCHEMA = {
    "type": "object",
    "properties": {"sql": {"type": "string"}, "rationale": {"type": "string"}},
    "required": ["sql", "rationale"], "additionalProperties": False,
}
_cursor_lock = threading.Lock()
_cursor = {}
_spend_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


class Spend:
    """Shared spend ceiling for one run; unknown-price calls are counted, not guessed."""

    def __init__(self, ceiling_usd):
        self.ceiling, self.usd, self.unpriced_calls = ceiling_usd, 0.0, 0

    def add(self, cost):
        with _spend_lock:
            if cost is None:
                self.unpriced_calls += 1
            else:
                self.usd += cost
            if self.ceiling is not None and self.usd > self.ceiling:
                raise BudgetExceeded(f"Spend ceiling ${self.ceiling:.2f} reached; run stopped.")


def price(provider, model, input_tokens, cached_tokens, output_tokens):
    if provider == "local":
        return 0.0  # no API charge; the Mac's hardware and power are not priced
    rate = PRICES.get(f"{provider}:{model}")
    if not rate:
        return None
    return ((input_tokens - cached_tokens) * rate["input"] + cached_tokens * rate["cached_input"]
            + output_tokens * rate["output"]) / 1_000_000


class Client:
    def __init__(self, provider, model, reasoning_effort=None, max_output_tokens=4096, spend=None):
        self.provider, self.model = provider, model
        self.reasoning_effort, self.max_output_tokens = reasoning_effort, max_output_tokens
        self.spend = spend
        if provider == "local":
            self.base = os.getenv("LOCAL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
            self.keys = [("local", os.getenv("LOCAL_API_KEY", "local"))]
        else:
            self.base = BASES[provider]
            self.keys = credential_pool(provider)
            if not self.keys:
                raise ValueError(f"{provider.upper()}_API_KEY is not set in .env.local.")

    @property
    def label(self):
        effort = f"@{self.reasoning_effort}" if self.reasoning_effort else ""
        return f"{self.provider}:{self.model}{effort}"

    def _payload(self, system, user):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if self.provider == "openai":
            payload = {"model": self.model, "input": messages, "store": False,
                       "max_output_tokens": self.max_output_tokens,
                       "text": {"format": {"type": "json_schema", "name": "sql_candidate",
                                           "strict": True, "schema": SCHEMA}}}
            if self.reasoning_effort:
                payload["reasoning"] = {"effort": self.reasoning_effort}
            return "/responses", payload
        payload = {"model": self.model, "messages": messages, "max_completion_tokens": self.max_output_tokens}
        if self.provider == "local":
            payload["response_format"] = {"type": "json_object"}
            payload["max_tokens"] = self.max_output_tokens
        else:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "sql_candidate", "strict": True, "schema": SCHEMA}}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        return "/chat/completions", payload

    def complete(self, system, user, sample=0):
        """Return {sql, rationale, tokens..., latency_ms, cost_usd, cached, error}."""
        endpoint, payload = self._payload(system, user)
        digest = hashlib.sha256(json.dumps([self.base, payload, sample], sort_keys=True).encode()).hexdigest()
        path = CACHE_DIR / digest[:2] / (digest + ".json")
        if path.exists():
            record = json.loads(path.read_text())
            record["from_cache"] = True
            if self.spend:
                self.spend.add(record.get("cost_usd"))
            return record
        record = self._call(endpoint, payload)
        if self.spend:
            self.spend.add(record.get("cost_usd"))
        if not record.get("transient"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record))
        record["from_cache"] = False
        return record

    def _call(self, endpoint, payload):
        started = time.perf_counter()
        waited, attempts = 0.0, 0
        while True:
            with _cursor_lock:
                index = _cursor.get(self.provider, 0) % len(self.keys)
                _cursor[self.provider] = index + 1
            _, key = self.keys[index]
            attempts += 1
            try:
                raw = request_json(self.base + endpoint, key, payload)
                break
            except ProviderHTTPError as exc:
                if self.provider == "local" and exc.status in (400, 501) and "response_format" in payload:
                    # Some Ollama models lack structured output; the prompt still asks for JSON.
                    payload = {k: v for k, v in payload.items() if k != "response_format"}
                    continue
                if exc.status in (429, 500, 502, 503) and attempts < 8:
                    pause = min(60.0, max(exc.retry_after, 2.0 * attempts)) / max(1, len(self.keys) - 1)
                    time.sleep(pause)
                    waited += pause
                    continue
                return {"error": f"HTTP {exc.status}", "transient": exc.status in (429, 500, 502, 503),
                        "latency_ms": (time.perf_counter() - started) * 1000, "attempts": attempts,
                        "throttle_wait_ms": waited * 1000, "cost_usd": None}
            except (RuntimeError, OSError) as exc:
                if attempts < 3:
                    time.sleep(2)
                    continue
                return {"error": str(exc)[:200], "transient": True, "attempts": attempts,
                        "latency_ms": (time.perf_counter() - started) * 1000, "cost_usd": None}
        latency = (time.perf_counter() - started) * 1000
        record = parse(self.provider, raw)
        record.update(model=raw.get("model", self.model), latency_ms=latency, attempts=attempts,
                      throttle_wait_ms=waited * 1000, provider=self.provider)
        record["cost_usd"] = price(self.provider, self.model, record["input_tokens"],
                                   record["cached_tokens"], record["output_tokens"])
        return record


def parse(provider, raw):
    usage = raw.get("usage") or {}
    if provider == "openai":
        parts = [p for item in raw.get("output", []) if item.get("type") == "message" for p in item.get("content", [])]
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "output_text")
        tokens = (usage.get("input_tokens", 0), (usage.get("input_tokens_details") or {}).get("cached_tokens", 0),
                  usage.get("output_tokens", 0))
        complete = raw.get("status") == "completed"
    else:
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        # Fireworks reasoning models (gpt-oss, GLM, Nemotron) often put the
        # visible answer in content and scratchpad in reasoning_content — or the
        # reverse when the token budget is spent on thinking. Prefer content,
        # then fall back to reasoning so JSON extraction still works.
        text = (message.get("content") or message.get("reasoning_content") or "")
        tokens = (usage.get("prompt_tokens", 0), (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                  usage.get("completion_tokens", 0))
        complete = choice.get("finish_reason") in ("stop", "length", None) or bool(text)
    record = {"input_tokens": tokens[0], "cached_tokens": tokens[1] or 0, "output_tokens": tokens[2],
              "sql": None, "rationale": "", "error": None}
    data = extract_json(text)
    if not complete and not data:
        record["error"] = "incomplete output"
    elif not data or not isinstance(data.get("sql"), str):
        record["error"] = "unparseable output"
    else:
        record["sql"], record["rationale"] = data["sql"].strip(), str(data.get("rationale", ""))[:600]
    return record


def extract_json(text):
    """Strict JSON first; local models sometimes wrap it in prose or a code fence."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    match = re.search(r"\{.*\}", text or "", re.S)
    if match:
        try:
            return json.loads(match.group())
        except ValueError:
            pass
    fence = re.search(r"```sql\s*(.*?)```", text or "", re.S | re.I)
    return {"sql": fence.group(1), "rationale": ""} if fence else None
