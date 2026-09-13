"""Frozen-anchor time resolution (L1).

All "now"/relative-time reasoning happens here in code against the pinned
``run_metadata`` anchor — never by the model (doc 06 §3 stage 1). This removes the
largest source of run-to-run nondeterminism in any text-to-query system.
"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime, timedelta

from ..config import get_settings


def anchor() -> datetime:
    """The frozen 'now' (tz-aware UTC), resolved exactly once via Settings."""
    return get_settings().anchor


def resolve_window(expr: str, *, ref: datetime | None = None) -> tuple[datetime, datetime]:
    """Resolve a relative-time expression to a concrete ``[t0, t1)`` against the anchor.

    Supports the spec's phrasings: "yesterday", "today", "last N days/hours",
    "past week". Unknown expressions raise — resolution is deterministic or it fails
    loudly rather than guessing.
    """
    now = ref or anchor()
    e = expr.strip().lower()

    if e in {"yesterday"}:
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return end - timedelta(days=1), end
    if e in {"today"}:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if e in {"last week", "past week", "last 7 days"}:
        return now - timedelta(days=7), now

    m = re.fullmatch(r"(?:last|past) (\d+) (hours?|days?|weeks?|months?)", e)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith("month"):
            return _months_before(now, n), now
        delta = {"hour": timedelta(hours=n), "day": timedelta(days=n),
                 "week": timedelta(weeks=n)}[unit.rstrip("s")]
        return now - delta, now

    raise ValueError(f"unresolvable time expression: {expr!r}")


#: Phrases ``resolve_window`` accepts — quoted back to the model when it sends another.
SUPPORTED_PHRASES = ("yesterday", "today", "last week", "last N hours", "last N days",
                     "last N weeks", "last N months")


def _months_before(dt: datetime, n: int) -> datetime:
    """Same instant ``n`` calendar months earlier, day clamped to the target month's length."""
    y, m0 = divmod(dt.month - 1 - n, 12)
    year, month = dt.year + y, m0 + 1
    return dt.replace(year=year, month=month, day=min(dt.day, monthrange(year, month)[1]))
