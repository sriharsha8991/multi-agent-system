"""Full 22-gate suite against live databases. Skipped if the DBs aren't reachable."""

from __future__ import annotations

import pytest

from mas.config import get_settings
from mas.eval import consistency


def _dbs_available(settings) -> bool:
    try:
        from mas.db import neo4j as neo
        from mas.db import postgres as pg
        with pg.connect(settings) as c:
            pg.fetchone(c, "SELECT 1")
        d = neo.get_driver(settings)
        try:
            neo.run_read(d, "RETURN 1 AS x", settings=settings)
        finally:
            d.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def results():
    settings = get_settings()
    if not _dbs_available(settings):
        pytest.skip("Postgres/Neo4j not reachable — run `make up && make seed` first")
    return consistency.run_all(settings)


def test_all_gates_green(results):
    failed = [r for r in results if not r.passed]
    assert not failed, "\n" + consistency.format_report(results)


def test_gate_count(results):
    assert len(results) == 22
