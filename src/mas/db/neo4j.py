"""Neo4j driver helpers and batched write utilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ..config import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from neo4j import Driver


def get_driver(settings: Settings | None = None) -> "Driver":
    from neo4j import GraphDatabase
    settings = settings or get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


def run_read(driver: Driver, cypher: str, params: dict[str, Any] | None = None,
             *, database: str | None = None, settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    db = database or settings.neo4j_database
    with driver.session(database=db) as session:
        return [r.data() for r in session.run(cypher, params or {})]


def run_write(driver: Driver, cypher: str, params: dict[str, Any] | None = None,
              *, database: str | None = None, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    db = database or settings.neo4j_database
    with driver.session(database=db) as session:
        session.run(cypher, params or {}).consume()


def unwind_write(driver: Driver, cypher: str, rows: Sequence[dict[str, Any]],
                 *, batch: int = 1000, database: str | None = None,
                 settings: Settings | None = None) -> int:
    """Run ``cypher`` (which must reference ``$rows``) over ``rows`` in batches."""
    settings = settings or get_settings()
    db = database or settings.neo4j_database
    total = 0
    with driver.session(database=db) as session:
        for start in range(0, len(rows), batch):
            chunk = rows[start:start + batch]
            session.run(cypher, {"rows": chunk}).consume()
            total += len(chunk)
    return total
