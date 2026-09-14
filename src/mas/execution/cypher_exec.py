"""Cypher executor (L3) — run validated Cypher in a READ-access session.

Opens a session with ``default_access_mode=READ`` so the driver itself refuses writes —
the hard gate behind ``validate_cypher``. Reuses ``mas.db.neo4j.get_driver``.
"""
from __future__ import annotations

from typing import Any

from ..db import neo4j as neo


def run_read(cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Execute validated read-only Cypher; return a list of record dicts."""
    from neo4j import READ_ACCESS

    driver = neo.get_driver()
    try:
        with driver.session(default_access_mode=READ_ACCESS) as session:
            return [r.data() for r in session.run(cypher, params or {})]
    finally:
        driver.close()


def explain(cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Plan the query without running it; return the server's notifications.

    ``EXPLAIN`` reports unknown labels, relationship types and property keys with positions
    (verified against this database), so misspelled names are caught before execution.
    Syntax errors raise from the driver as usual.
    """
    from neo4j import READ_ACCESS

    driver = neo.get_driver()
    try:
        with driver.session(default_access_mode=READ_ACCESS) as session:
            summary = session.run("EXPLAIN " + cypher, params or {}).consume()
            out = []
            for n in summary.notifications or []:
                if isinstance(n, dict):
                    out.append(n)
                else:
                    out.append({"code": getattr(n, "code", ""), "title": getattr(n, "title", ""),
                                "description": getattr(n, "description", "")})
            return out
    finally:
        driver.close()
