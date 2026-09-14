"""Time-window resolution (L3) — frozen-anchor maths, clamped to the data that exists.

``harness.clock`` stays pure (no DB): it resolves a phrase against the pinned anchor.
This adapter adds the second half an agent needs — the telemetry only spans the seeded
window recorded in ``run_metadata``, so "last 60 days" would otherwise send queries a
month before any data exists, returning empty results and burning the agent's budget.
We clamp and say so.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from ..config import get_settings
from ..harness import clock
from ..llm.schemas import TimeSpec, TimeWindow


@lru_cache(maxsize=1)
def data_bounds() -> tuple[str, str]:
    """The window the telemetry actually covers, from ``run_metadata`` (DB is truth).

    Falls back to the configured window if the database is unreachable.
    """
    try:
        from ..db import postgres

        conn = postgres.connect(reader=True)
        try:
            rows = dict(postgres.fetchall(
                conn, "SELECT key, value FROM run_metadata "
                      "WHERE key IN ('window_start', 'window_end')"))
        finally:
            conn.close()
        if rows.get("window_start") and rows.get("window_end"):
            return rows["window_start"], rows["window_end"]
    except Exception:
        pass
    s = get_settings()
    return s.window_start.isoformat(), s.window_end.isoformat()


def resolve_window(expr: str, *, ref: datetime | None = None) -> tuple[str, str]:
    """Resolve a relative expression to concrete ISO ``[start, end)`` strings (unclamped)."""
    t0, t1 = clock.resolve_window(expr, ref=ref)
    return t0.isoformat(), t1.isoformat()


#: Standard padding around an alert. One fixed rule, so "the telemetry around alert X" is the
#: same window on every run — a traced question picked 04:00-11:00 on one run and
#: 00:00-15:00 on the next for the same alert, when the model chose the padding.
EVENT_PAD_HOURS = 2.0


def _alert_bounds(alert_id: str) -> tuple[datetime, datetime]:
    """An alert's ``(start_ts, end_ts)`` from the graph."""
    from .cypher_exec import run_read

    rows = run_read("MATCH (a:Alert {alert_id: $id}) RETURN a.start_ts AS s, a.end_ts AS e",
                    {"id": alert_id})
    if not rows:
        raise ValueError(f"unknown alert_id {alert_id!r}")
    s, e = rows[0]["s"], rows[0]["e"]
    return (s.to_native() if hasattr(s, "to_native") else s,
            e.to_native() if hasattr(e, "to_native") else e)


def resolve_timespec(spec: TimeSpec, *, clamp: bool, alert_bounds=None) -> TimeWindow:
    """Turn what the orchestrator *named* into an exact window. Raises ValueError to bounce.

    ``clamp`` limits the window to telemetry coverage — right for SQL and analysis, wrong
    for the graph, whose alert and maintenance history reaches back two years.
    """
    if spec.phrase is not None:
        try:
            t0, t1 = clock.resolve_window(spec.phrase)
        except ValueError:
            raise ValueError(f"unsupported phrase {spec.phrase!r}; supported: "
                             f"{', '.join(clock.SUPPORTED_PHRASES)} — or give start+end") from None
        source, label = "phrase", repr(spec.phrase)
    elif spec.around_alert is not None:
        pad = timedelta(hours=EVENT_PAD_HOURS)
        a0, a1 = (alert_bounds or _alert_bounds)(spec.around_alert)
        t0, t1 = a0 - pad, a1 + pad
        source, label = "alert", f"{spec.around_alert} ± {pad.total_seconds() / 3600:g} h"
    else:
        t0, t1 = _utc(spec.start), _utc(spec.end)
        source, label = "explicit", "explicit range"

    clamped = False
    if clamp:
        d0, d1 = (datetime.fromisoformat(b) for b in data_bounds())
        c0, c1 = max(t0, d0), min(t1, d1)
        if c0 >= c1:
            raise ValueError(f"window {t0.isoformat()}..{t1.isoformat()} lies outside telemetry "
                             f"coverage [{d0.isoformat()}, {d1.isoformat()}) — no sensor data "
                             "exists there")
        clamped = (c0, c1) != (t0, t1)
        t0, t1 = c0, c1
    return TimeWindow(start=t0, end=t1, label=label, source=source, clamped=clamped)


def _utc(dt: datetime | None) -> datetime:
    assert dt is not None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def resolve_window_clamped(expr: str, *, ref: datetime | None = None) -> dict:
    """Resolve *and* clamp to the available data window.

    Returns ``{start_ts, end_ts, clamped, requested_start, data_start, data_end}`` so the
    caller can tell the model plainly that it asked for more history than exists.
    """
    start, end = resolve_window(expr, ref=ref)
    data_start, data_end = data_bounds()
    clamped_start = max(start, data_start)
    clamped_end = min(end, data_end)
    return {
        "start_ts": clamped_start,
        "end_ts": clamped_end,
        "clamped": (clamped_start != start) or (clamped_end != end),
        "requested_start": start,
        "requested_end": end,
        "data_start": data_start,
        "data_end": data_end,
    }
