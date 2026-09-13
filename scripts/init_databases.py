#!/usr/bin/env python
"""Spin up both databases: Postgres schema + reader role, Neo4j constraints.

Idempotent — safe to re-run. Drops & recreates the Postgres schema and (re)applies
Neo4j constraints/indexes. Does NOT populate data (see seed_all.py).
"""

from __future__ import annotations

import _bootstrap  # noqa: F401 - side-effect import: puts src/ on sys.path
import time

from mas import catalog
from mas.config import get_settings
from mas.db import constraints, ddl
from mas.db import neo4j as neo


def main() -> None:
    settings = get_settings()
    problems = catalog.validate()
    if problems:
        raise SystemExit("Catalog invalid:\n  " + "\n  ".join(problems))

    print("[init] Postgres: creating schema + reader role ...")
    t0 = time.time()
    ddl.init_postgres(settings)
    print(f"[init] Postgres schema ready ({time.time()-t0:.1f}s)")

    print("[init] Neo4j: applying constraints + indexes ...")
    driver = neo.get_driver(settings)
    try:
        constraints.apply_constraints(driver, settings)
    finally:
        driver.close()
    print("[init] Neo4j constraints ready")
    print("[init] done.")


if __name__ == "__main__":
    main()
