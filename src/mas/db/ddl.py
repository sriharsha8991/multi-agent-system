"""Generate the Postgres schema *in code* from the catalog, and apply it.

No static ``schema.sql`` — the 5 wide tables, ``sensor_catalog``, ``run_metadata``
and the 5 ``*_long`` views are all derived from the same ``TagSpec`` objects the
rest of the pipeline uses, so column sets cannot drift from the catalog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import catalog
from ..config import Settings, get_settings
from . import postgres as pg

if TYPE_CHECKING:  # pragma: no cover - typing only
    import psycopg

SENSOR_CATALOG_COLS = [
    "system", "tag_name", "family", "unit", "description", "kks_tag", "location",
    "sensor_type", "precision", "normal_min", "normal_max", "alarm_lolo",
    "alarm_lo", "alarm_hi", "alarm_hihi", "is_derived",
]


def table_ddl(system: str) -> str:
    cols = [f'  "ts" TIMESTAMPTZ PRIMARY KEY']
    for t in catalog.tags_for(system):
        cols.append(f'  "{t.tag_name}" DOUBLE PRECISION')
    body = ",\n".join(cols)
    return f'CREATE TABLE "{system}" (\n{body}\n);'


def sensor_catalog_ddl() -> str:
    return """
CREATE TABLE sensor_catalog (
  system            TEXT NOT NULL,
  tag_name          TEXT NOT NULL,
  family            TEXT NOT NULL,
  unit              TEXT,
  description       TEXT,
  kks_tag           TEXT,
  location          TEXT,
  sensor_type       TEXT,
  precision         DOUBLE PRECISION,
  normal_min        DOUBLE PRECISION,
  normal_max        DOUBLE PRECISION,
  alarm_lolo        DOUBLE PRECISION,
  alarm_lo          DOUBLE PRECISION,
  alarm_hi          DOUBLE PRECISION,
  alarm_hihi        DOUBLE PRECISION,
  is_derived        BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (system, tag_name)
);
""".strip()


def run_metadata_ddl() -> str:
    return "CREATE TABLE run_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);"


def long_view_ddl(system: str) -> str:
    rows = []
    for i, t in enumerate(catalog.tags_for(system)):
        if i == 0:
            rows.append(f"    ('{t.tag_name}'::text, \"{t.tag_name}\"::double precision)")
        else:
            rows.append(f"    ('{t.tag_name}', \"{t.tag_name}\")")
    values = ",\n".join(rows)
    return (
        f'CREATE VIEW "{system}_long" AS\n'
        f'SELECT ts, u.tag_name, u.value\n'
        f'FROM "{system}",\n'
        f'LATERAL (VALUES\n{values}\n) AS u(tag_name, value);'
    )


def drop_statements() -> list[str]:
    stmts = []
    for s in catalog.systems():
        stmts.append(f'DROP VIEW IF EXISTS "{s}_long" CASCADE;')
    for s in catalog.systems():
        stmts.append(f'DROP TABLE IF EXISTS "{s}" CASCADE;')
    stmts.append("DROP TABLE IF EXISTS sensor_catalog CASCADE;")
    stmts.append("DROP TABLE IF EXISTS run_metadata CASCADE;")
    return stmts


def create_statements() -> list[str]:
    stmts = [sensor_catalog_ddl(), run_metadata_ddl()]
    for s in catalog.systems():
        stmts.append(table_ddl(s))
    for s in catalog.systems():
        stmts.append(long_view_ddl(s))
    return stmts


def create_schema(conn: psycopg.Connection) -> None:
    """Idempotently (re)create the whole Postgres schema."""
    pg.executescript(conn, drop_statements())
    pg.executescript(conn, create_statements())


def populate_sensor_catalog(conn: psycopg.Connection) -> int:
    """Fill ``sensor_catalog`` from the in-code catalog (mirror of Neo4j Tag)."""
    rows = []
    for t in catalog.all_tags():
        r = t.catalog_row()
        rows.append(tuple(r[c] for c in SENSOR_CATALOG_COLS))
    pg.execute(conn, "TRUNCATE sensor_catalog")
    return pg.copy_rows(conn, "sensor_catalog", SENSOR_CATALOG_COLS, rows)


def write_run_metadata(conn: psycopg.Connection, meta: dict[str, str]) -> None:
    pg.execute(conn, "TRUNCATE run_metadata")
    with conn.cursor() as cur:
        for k, v in meta.items():
            cur.execute(
                "INSERT INTO run_metadata (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (k, v),
            )


def read_run_metadata(conn: psycopg.Connection) -> dict[str, str]:
    return dict(pg.fetchall(conn, "SELECT key, value FROM run_metadata"))


def init_postgres(settings: Settings | None = None) -> None:
    """Entry point for schema spin-up: create schema + reader role."""
    settings = settings or get_settings()
    with pg.connect(settings) as conn:
        create_schema(conn)
        pg.setup_reader_role(conn, settings)
