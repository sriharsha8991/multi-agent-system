"""Digests — the *only* path from data to an LLM prompt (L2).

A digest is the small, bounded, deterministic description of a table the supervisor
is allowed to see: the fixed pandas profile of ``head(5)`` (over a deterministic
order) + ``describe()`` + dtypes + null fraction. Built by code, never by an LLM,
with fixed rounding so the same frame always renders the same bytes (doc 07 §3).
The bulk payload never leaves the blackboard.
"""
from __future__ import annotations

import math

import pandas as pd

SAMPLE_ROWS = 5
ROUND = 4


def _num(value) -> float | None:
    """Round to fixed precision; NaN/Inf become None (bare NaN is invalid JSON)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, ROUND)


def profile_table(df: pd.DataFrame, *, order_by: str = "ts") -> dict:
    """Deterministic profile of a DataFrame. Requires a stable order for the sample."""
    frame = df.sort_values(order_by) if order_by in df.columns else df
    numeric = frame.select_dtypes("number")
    stats = {
        col: {k: _num(v) for k, v in numeric[col].describe().items()}
        for col in numeric.columns
    }
    ts_range = None
    if order_by in frame.columns and len(frame):
        ts_range = [str(frame[order_by].iloc[0]), str(frame[order_by].iloc[-1])]
    return {
        "kind": "table",
        "row_count": int(len(frame)),
        "columns": [f"{c}:{t}" for c, t in frame.dtypes.astype(str).items()],
        "ts_range": ts_range,
        "null_frac": {c: _num(frame[c].isna().mean()) for c in frame.columns},
        "head": frame.head(SAMPLE_ROWS).astype(str).values.tolist(),
        "stats": stats,
    }
