#!/usr/bin/env python
"""Populate both databases end-to-end.

    physics telemetry  ->  Postgres (COPY)
    alert detection    ->  Alert nodes
    maintenance/items  ->  MaintenanceLog / Item / CONSUMED
    graph projection   ->  Neo4j

Runs the schema spin-up first (idempotent), so a bare `python scripts/seed_all.py`
against empty databases works on its own.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401 - side-effect import: puts src/ on sys.path
import time

from mas.config import get_settings
from mas.db import ddl
from mas.db import neo4j as neo
from mas.datagen import alerts as al
from mas.datagen import build_telemetry as bt
from mas.datagen import graph_seed
from mas.datagen import maintenance as mnt


def main() -> None:
    settings = get_settings()
    t0 = time.time()
    print(f"[seed] anchor={settings.anchor.isoformat()} seed={settings.master_seed} "
          f"currency={settings.currency}")

    # 1. schema spin-up (idempotent)
    ddl.init_postgres(settings)

    # 2. telemetry generation + COPY
    print("[seed] generating physics telemetry ...")
    data = bt.generate_all(settings)
    print(f"[seed] generated {sum(len(v) for v in data.arrays.values())} series "
          f"({time.time()-t0:.1f}s); loading Postgres ...")
    counts = bt.load_to_postgres(data, settings)
    print(f"[seed] Postgres rows: {counts}")

    # 3. alerts from final telemetry
    alerts = al.detect(data)
    print(f"[seed] detected {len(alerts)} alerts "
          f"({sum(1 for a in alerts if a['has_telemetry'])} in-window)")

    # 4. maintenance + items + consumption
    maintenance = mnt.build(data, alerts, settings)
    print(f"[seed] {len(maintenance.logs)} maintenance logs, "
          f"{len(maintenance.consumed)} consumption edges")

    # 5. project into Neo4j
    driver = neo.get_driver(settings)
    try:
        gcounts = graph_seed.seed_graph(driver, data, alerts, maintenance, settings)
    finally:
        driver.close()
    print(f"[seed] Neo4j: {gcounts}")
    print(f"[seed] done in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    main()
