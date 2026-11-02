"""Shared SQL text helpers used by lab, eval, and the demo service.

Keep validation (safety) in `database.validate_sql`. Keep *comparison*
normalization here so every caller agrees what “same SQL” means.
"""

from __future__ import annotations

import re

from .database import validate_sql

__all__ = ["normalize", "validate_sql", "same_sql"]


def normalize(sql: str | None) -> str:
    """Collapse whitespace and strip a trailing semicolon for equality checks."""
    return re.sub(r"\s+", " ", (sql or "").strip().rstrip(";").strip())


def same_sql(a: str | None, b: str | None) -> bool:
    return normalize(a) == normalize(b)
