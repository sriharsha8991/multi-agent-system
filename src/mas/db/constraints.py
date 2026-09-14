"""Neo4j constraints + indexes, built and applied in code.

Exactly the 5 node labels and 4 relationship types the spec allows; uniqueness
and lookup indexes support the cross-DB bridge and the demo queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import Settings, get_settings
from . import neo4j as neo

if TYPE_CHECKING:  # pragma: no cover - typing only
    from neo4j import Driver

# The canonical label / relationship sets (asserted by gates G-05 / G-06).
NODE_LABELS = ("System", "Tag", "MaintenanceLog", "Item", "Alert")
REL_TYPES = ("GENERATED_ON", "PERFORMED_ON", "MEASURED_AT", "CONSUMED")

CONSTRAINTS = [
    "CREATE CONSTRAINT system_name IF NOT EXISTS "
    "FOR (s:System) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT item_code IF NOT EXISTS "
    "FOR (i:Item) REQUIRE i.item_code IS UNIQUE",
    "CREATE CONSTRAINT wo_id IF NOT EXISTS "
    "FOR (m:MaintenanceLog) REQUIRE m.work_order_id IS UNIQUE",
    "CREATE CONSTRAINT alert_id IF NOT EXISTS "
    "FOR (a:Alert) REQUIRE a.alert_id IS UNIQUE",
    "CREATE CONSTRAINT tag_key IF NOT EXISTS "
    "FOR (t:Tag) REQUIRE (t.system, t.tag_name) IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX alert_start IF NOT EXISTS FOR (a:Alert) ON (a.start_ts)",
    "CREATE INDEX alert_system IF NOT EXISTS FOR (a:Alert) ON (a.system)",
    "CREATE INDEX wo_start IF NOT EXISTS FOR (m:MaintenanceLog) ON (m.start_ts)",
    "CREATE INDEX tag_system IF NOT EXISTS FOR (t:Tag) ON (t.system)",
]


def apply_constraints(driver: Driver, settings: Settings | None = None) -> None:
    for stmt in CONSTRAINTS + INDEXES:
        neo.run_write(driver, stmt, settings=settings)


def reset_graph(driver: Driver, settings: Settings | None = None) -> None:
    """Delete all nodes/relationships so the seed is idempotent."""
    neo.run_write(driver, "MATCH (n) DETACH DELETE n", settings=settings)


def init_neo4j(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    driver = get_driver_and_apply(settings)
    driver.close()


def get_driver_and_apply(settings: Settings | None = None) -> Driver:
    settings = settings or get_settings()
    driver = neo.get_driver(settings)
    apply_constraints(driver, settings)
    return driver
