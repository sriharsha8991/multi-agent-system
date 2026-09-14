"""SQL executor (L3) — run validated SELECTs as the read-only role.

Wraps the existing ``mas.db.postgres`` layer: connects as ``mas_reader`` (SELECT-only,
read-only transaction, 15 s timeout) and applies a client-side row cap. No new connection
code. Only ``validate_sql``-approved strings should be passed here.
"""
from __future__ import annotations

import pandas as pd

from ..db import postgres


def run_select(sql: str, *, row_cap: int = 100_000) -> pd.DataFrame:
    """Execute a validated SELECT as ``mas_reader`` and return a DataFrame."""
    conn = postgres.connect(reader=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d.name for d in cur.description]
            rows = cur.fetchmany(row_cap)
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()
