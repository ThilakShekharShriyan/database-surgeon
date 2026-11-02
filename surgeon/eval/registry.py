"""Named systems. Ablations each remove exactly one lever from the full harness."""

import os
from dataclasses import replace

from .systems import SystemConfig

FRONTIER = ("openai", os.getenv("EVAL_FRONTIER_MODEL", "gpt-6.1-sol"))
OSS_SMALL = ("groq", "openai/gpt-oss-20b")
OSS_LARGE = ("groq", "openai/gpt-oss-120b")

# Fireworks title-sponsor path. Prefer NVIDIA Nemotron hosted on Fireworks for
# dual eligibility (Fireworks prize + NVIDIA Best-Use / DGX Spark).
# Account-scoped serverless IDs (this hackathon key): gpt-oss-20b is NOT listed;
# gpt-oss-120b + glm-5p3-flash + nemotron-3-ultra-nvfp4 are live.
FW_FAST = os.getenv(
    "FIREWORKS_FAST_MODEL",
    "accounts/fireworks/models/glm-5p3-flash",
)
FW_DEEP = os.getenv(
    "FIREWORKS_DEEP_MODEL",
    os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/gpt-oss-120b"),
)
FW_OSS20 = os.getenv("FIREWORKS_OSS20_MODEL", "accounts/fireworks/models/gpt-oss-120b")
FW_ULTRA = os.getenv(
    "FIREWORKS_ULTRA_MODEL",
    "accounts/fireworks/models/nemotron-3-ultra-nvfp4",
)
FW_NEMO_FAST = os.getenv(
    "FIREWORKS_NEMO_FAST_MODEL",
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b",
)

HARNESS = dict(
    rules=True, catalog=True, guide=True, retrieval=3,
    best_of=3, repair=2, precheck=True, verify=True,
)
# Local Ollama: best_of=3 × repair=2 is hours of sequential 20B gens. Lean keeps
# ~95% of harness quality for the privacy / $0 API narrative.
LOCAL_HARNESS = dict(
    rules=True, catalog=True, guide=True, retrieval=2,
    best_of=1, repair=1, precheck=True, verify=True,
)
LEVERS = {
    "rules": {"rules": False},
    "catalog": {"catalog": False, "guide": False},
    "retrieval": {"retrieval": 0},
    "best_of": {"best_of": 1},
    "repair": {"repair": 0},
    "precheck": {"precheck": False},
    "verify": {"verify": False},
}


def _model(name, pair, **levers):
    return SystemConfig(name=name, provider=pair[0], model=pair[1], **levers)


def systems():
    found = {}

    def add(config):
        found[config.name] = config
        return config

    add(SystemConfig(name="rules-only", rules=True, verify=True))
    add(_model("frontier-raw", FRONTIER))
    add(_model("oss20b-raw", OSS_SMALL))
    add(_model("oss120b-raw", OSS_LARGE))
    small = add(_model("oss20b-harness", OSS_SMALL, **HARNESS))
    large = add(_model("oss120b-harness", OSS_LARGE, **HARNESS))
    frontier = add(_model("frontier-harness", FRONTIER, **HARNESS))
    add(_model("oss20b-verify-only", OSS_SMALL, verify=True, repair=0))
    add(replace(small, name="oss20b-harness-effort-low", effort="low"))
    add(replace(small, name="oss20b-harness-effort-high", effort="high"))
    for lever, change in LEVERS.items():
        add(replace(small, name=f"oss20b-harness-minus-{lever}", **change))
    rules = found["rules-only"]
    add(SystemConfig(name="cascade-open", stages=[rules, small, large]))
    add(SystemConfig(name="cascade-hybrid", stages=[rules, small, large, frontier]))
    add(SystemConfig(name="router-open", stages=[rules, small, large], router="learned"))

    # --- Fireworks + NVIDIA Nemotron (prize-eligibility stack) -------------
    # Live on this account: glm-5p3-flash, gpt-oss-120b, nemotron-3-ultra-nvfp4.
    # Reasoning models need a larger token budget so JSON survives the think phase.
    if os.getenv("FIREWORKS_API_KEY"):
        fw_fast = ("fireworks", FW_FAST)
        fw_deep = ("fireworks", FW_DEEP)
        fw_oss = ("fireworks", FW_OSS20)
        fw_ultra = ("fireworks", FW_ULTRA)
        tok = 4096
        add(_model("fw-fast-raw", fw_fast, catalog=True, guide=True, max_output_tokens=tok))
        fast_h = add(_model("fw-fast-harness", fw_fast, max_output_tokens=tok, **HARNESS))
        add(_model("fw-gpt-oss-raw", fw_oss, catalog=True, guide=True, max_output_tokens=tok))
        oss_fw = add(_model("fw-gpt-oss-harness", fw_oss, max_output_tokens=tok, **HARNESS))
        add(_model("fw-nemotron-raw", fw_ultra, catalog=True, guide=True, max_output_tokens=tok))
        nemo_h = add(_model("fw-nemotron-harness", fw_ultra, max_output_tokens=tok, **HARNESS))
        add(_model("fw-nemotron-ultra-raw", fw_ultra, catalog=True, guide=True, max_output_tokens=tok))
        ultra_h = add(_model("fw-nemotron-ultra-harness", fw_ultra, max_output_tokens=tok, **HARNESS))
        # Pitch aliases (open = gpt-oss-120b on Fireworks)
        add(_model("open-raw", fw_oss, catalog=True, guide=True, max_output_tokens=tok))
        open_h = add(_model("open-harness", fw_deep, max_output_tokens=tok, **HARNESS))
        # Cache A/B: same harness without fingerprint reuse (cold LLM every time).
        add(replace(open_h, name="open-harness-nocache", workload_cache=False))
        # Cache-first path: rules + fingerprint only ($0 when hit), no model.
        add(SystemConfig(name="cache-rules", rules=True, verify=True, workload_cache=True))
        add(_model("fw-open-raw", fw_oss, catalog=True, guide=True, max_output_tokens=tok))
        add(_model("fw-open-harness", fw_deep, max_output_tokens=tok, **HARNESS))
        # Headline cascade: sqlglot → glm flash → NVIDIA Nemotron Ultra on Fireworks
        add(SystemConfig(name="cascade-surgeon", stages=[rules, fast_h, ultra_h]))
        add(SystemConfig(name="cascade-open-fw", stages=[rules, open_h]))
        add(SystemConfig(name="cascade-nemotron", stages=[rules, open_h, nemo_h]))
        add(SystemConfig(name="cascade-oss-fw", stages=[rules, oss_fw]))

    # Ollama models on this Mac (LOCAL_BASE_URL, default http://127.0.0.1:11434/v1).
    from ..settings import get_settings
    for model in get_settings().eval_local_models:
        slug = "ollama-" + model.replace(":", "-").replace(".", "")
        effort = "none" if model.startswith("qwen3") else None
        add(_model(f"{slug}-raw", ("local", model), effort=effort, catalog=True, guide=True, max_output_tokens=2048))
        add(_model(f"{slug}-harness", ("local", model), effort=effort, max_output_tokens=2048, **LOCAL_HARNESS))

    # Demo cascade preference when Fireworks is not keyed:
    # local Ollama lean harness before Groq (Groq often 403/429 at the venue).
    local_stages = [rules]
    for name in ("ollama-gpt-oss-20b-harness", "oss20b-harness"):
        if name in found:
            local_stages.append(found[name])
            break
    add(SystemConfig(name="cascade-local", stages=local_stages))
    if "cascade-surgeon" not in found:
        # Without FIREWORKS_API_KEY the prize stack cannot run; local cascade still demos.
        add(SystemConfig(name="cascade-surgeon", stages=local_stages))

    specialist_provider = os.getenv("SPECIALIST_PROVIDER")
    specialist_model = os.getenv("SPECIALIST_MODEL")
    if specialist_provider and specialist_model:
        prefix = os.getenv("SPECIALIST_NAME", "specialist")
        pair = (specialist_provider, specialist_model)
        add(_model(f"{prefix}-raw", pair, catalog=True, guide=True, max_output_tokens=1024))
        spec = add(_model(f"{prefix}-harness", pair, max_output_tokens=1024, **HARNESS))
        add(SystemConfig(name=f"cascade-{prefix}", stages=[rules, spec]))
        add(SystemConfig(name="cascade-local", stages=[rules, spec]))
    return found
