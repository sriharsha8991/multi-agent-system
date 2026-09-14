"""Project the catalog + derived alerts + maintenance into Neo4j.

Exactly 5 node labels (System, Tag, MaintenanceLog, Item, Alert) and 4
relationship types (GENERATED_ON, PERFORMED_ON, MEASURED_AT, CONSUMED). No
telemetry values ever cross into the graph (Data Separation Rule / G-07):
Tag holds only identity, units, static setpoints; Alert holds only scalar event
attributes; nothing holds a numeric array.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import catalog
from ..catalog import SYSTEM_META
from ..config import Settings, get_settings
from ..db import constraints
from ..db import neo4j as neo
from .build_telemetry import GeneratedData
from .maintenance import MaintenanceOutput

if TYPE_CHECKING:  # pragma: no cover
    from neo4j import Driver


def _system_rows() -> list[dict]:
    rows = []
    for name in catalog.systems():
        meta = dict(SYSTEM_META[name])
        meta["tag_count"] = catalog.tag_count(name)
        rows.append(meta)
    return rows


def _tag_rows(settings: Settings) -> list[dict]:
    interval = settings.sample_seconds
    return [t.tag_node(interval) for t in catalog.all_tags()]


def _item_rows(settings: Settings) -> list[dict]:
    return [i.item_node(settings.currency) for i in catalog.items()]


def seed_graph(driver: "Driver", data: GeneratedData, alerts: list[dict],
               maintenance: MaintenanceOutput, settings: Settings | None = None) -> dict[str, int]:
    settings = settings or get_settings()
    constraints.reset_graph(driver, settings)
    constraints.apply_constraints(driver, settings)

    counts: dict[str, int] = {}

    # System
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MERGE (s:System {name: row.name})
        SET s += row
        SET s.commissioned_date = date(row.commissioned_date)
        """, _system_rows(), settings=settings)
    counts["System"] = len(_system_rows())

    # Tag  (+ MEASURED_AT → System)
    tag_rows = _tag_rows(settings)
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MATCH (s:System {name: row.system})
        MERGE (t:Tag {system: row.system, tag_name: row.tag_name})
        SET t += row
        MERGE (t)-[:MEASURED_AT]->(s)
        """, tag_rows, batch=2000, settings=settings)
    counts["Tag"] = len(tag_rows)

    # Item
    item_rows = _item_rows(settings)
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MERGE (i:Item {item_code: row.item_code})
        SET i += row
        """, item_rows, settings=settings)
    counts["Item"] = len(item_rows)

    # Alert  (+ GENERATED_ON → System)
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MATCH (s:System {name: row.system})
        CREATE (a:Alert)
        SET a = row
        SET a.start_ts = datetime(row.start_ts),
            a.end_ts = datetime(row.end_ts),
            a.acknowledged_ts = CASE WHEN row.acknowledged_ts IS NULL
                                     THEN NULL ELSE datetime(row.acknowledged_ts) END
        MERGE (a)-[:GENERATED_ON]->(s)
        """, alerts, batch=1000, settings=settings)
    counts["Alert"] = len(alerts)

    # MaintenanceLog  (+ PERFORMED_ON → System)
    log_rows = [{k: v for k, v in L.items() if k != "visible_recovery"} for L in maintenance.logs]
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MATCH (s:System {name: row.system})
        CREATE (m:MaintenanceLog)
        SET m = row
        SET m.start_ts = datetime(row.start_ts),
            m.end_ts = datetime(row.end_ts)
        MERGE (m)-[:PERFORMED_ON]->(s)
        """, log_rows, batch=1000, settings=settings)
    counts["MaintenanceLog"] = len(log_rows)

    # CONSUMED (MaintenanceLog → Item) with relationship properties
    neo.unwind_write(driver,
        """
        UNWIND $rows AS row
        MATCH (m:MaintenanceLog {work_order_id: row.work_order_id})
        MATCH (i:Item {item_code: row.item_code})
        MERGE (m)-[c:CONSUMED]->(i)
        SET c.quantity = row.quantity,
            c.unit_cost_at_time = row.unit_cost_at_time,
            c.line_cost = row.line_cost,
            c.currency = row.currency
        """, maintenance.consumed, batch=1000, settings=settings)
    counts["CONSUMED"] = len(maintenance.consumed)

    return counts
