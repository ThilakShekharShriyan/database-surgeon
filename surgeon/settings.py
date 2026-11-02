"""Typed runtime settings for production-style workloads.

Load once per process via `Settings.load()`. Env vars remain the source of
truth; this object is the single place code should read knobs from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .config import ROOT, load_env


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    pg_host: str = "127.0.0.1"
    pg_port: str = "55432"
    pg_database: str = "surgeon"
    statement_timeout_ms: int = 5000
    min_reduction: float = 0.20
    demo_system: str = "cascade-surgeon"
    eval_local_models: List[str] = field(default_factory=lambda: ["gpt-oss:20b"])
    local_base_url: str = "http://127.0.0.1:11434/v1"
    service_port: int = 8765
    vast_label: str = "database-surgeon-sft"
    vast_max_dph: float = 0.45
    vast_sft_epochs: float = 1.0
    vast_image: str = "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime"

    @classmethod
    def load(cls) -> "Settings":
        load_env()
        models = [
            m.strip()
            for m in os.getenv("EVAL_LOCAL_MODELS", "gpt-oss:20b").split(",")
            if m.strip()
        ]
        return cls(
            pg_host=os.getenv("PGHOST", "127.0.0.1"),
            pg_port=os.getenv("PGPORT", "55432"),
            pg_database=os.getenv("PGDATABASE", "surgeon"),
            statement_timeout_ms=int(os.getenv("STATEMENT_TIMEOUT_MS", "5000")),
            min_reduction=float(os.getenv("MIN_REDUCTION", "0.20")),
            demo_system=os.getenv("DEMO_SYSTEM", "cascade-surgeon"),
            eval_local_models=models or ["gpt-oss:20b"],
            local_base_url=os.getenv("LOCAL_BASE_URL", "http://127.0.0.1:11434/v1"),
            service_port=int(os.getenv("SURGEON_PORT", "8765")),
            vast_max_dph=float(os.getenv("VAST_MAX_DPH", "0.45")),
            vast_sft_epochs=float(os.getenv("VAST_SFT_EPOCHS", "1")),
            vast_image=os.getenv(
                "VAST_IMAGE", "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime"
            ),
        )


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.load()
    return _SETTINGS
