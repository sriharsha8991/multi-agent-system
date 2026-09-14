"""SQL validator (L3) — the read-only safety boundary, built on ``sqlglot``.

Parses with a real SQL grammar (not regex): rejects anything but a single SELECT,
enforces the table allowlist, blocks dangerous functions, and injects a LIMIT. This is
the hard gate — a generated query reaches the driver only after passing here (doc 06 §4).
"""
from __future__ import annotations

import difflib
import re
from functools import lru_cache

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError
from sqlglot.optimizer.qualify import qualify

from ..catalog import column_names, systems

_WRITE_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Set,
)
_BANNED_FUNCS = {
    "pg_read_file", "pg_ls_dir", "lo_import", "lo_export", "dblink", "copy",
    "pg_sleep", "pg_read_binary_file",
}


class SqlValidationError(ValueError):
    """Raised when generated SQL is unsafe or malformed — before any driver sees it."""


def default_allowed_tables() -> set[str]:
    """Allowlist from the catalog: the five system tables, their long views, catalog+meta."""
    base = set(systems())
    return base | {f"{s}_long" for s in base} | {"sensor_catalog", "run_metadata"}


def validate_sql(
    sql: str,
    *,
    allowed_tables: set[str] | None = None,
    row_limit: int = 10_000,
    dialect: str = "postgres",
) -> str:
    """Validate + normalize a generated SELECT. Returns safe SQL, or raises."""
    allowed = {t.lower() for t in (allowed_tables or default_allowed_tables())}
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except Exception as e:  # sqlglot parse failure
        raise SqlValidationError(f"parse error: {e}") from e

    if len(statements) != 1:
        raise SqlValidationError(f"exactly one statement required, got {len(statements)}")
    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, exp.Union, exp.Subquery)):
        raise SqlValidationError(f"only SELECT queries allowed (got {type(stmt).__name__})")

    for wt in _WRITE_NODES:
        if next(stmt.find_all(wt), None) is not None:
            raise SqlValidationError(f"disallowed statement type: {wt.__name__}")

    for fn in stmt.find_all(exp.Anonymous, exp.Func):
        name = (fn.name or "").lower()
        if name in _BANNED_FUNCS:
            raise SqlValidationError(f"disallowed function: {name}")

    # A CTE's alias is referenced like a table but is not one — its body's own tables are
    # still checked below, so exempting the alias opens nothing. Without this every
    # `WITH x AS (...) SELECT ... FROM x` was rejected as "table not in allowlist: x".
    cte_names = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    for table in stmt.find_all(exp.Table):
        if not table.db and table.name.lower() in cte_names:
            continue
        if table.name.lower() not in allowed:
            raise SqlValidationError(f"table not in allowlist: {table.name}")

    _check_columns(stmt, dialect)

    # inject a LIMIT on a bare SELECT (a client-side fetch cap in sql_exec backs this up)
    if isinstance(stmt, exp.Select) and stmt.args.get("limit") is None:
        stmt = stmt.limit(row_limit)

    return stmt.sql(dialect=dialect)


@lru_cache(maxsize=1)
def catalog_schema() -> dict[str, dict[str, str]]:
    """Column schema of every reachable relation, built from the catalog (no DB round trip)."""
    from ..db.ddl import SENSOR_CATALOG_COLS

    schema: dict[str, dict[str, str]] = {}
    for s in systems():
        schema[s] = {c: ("timestamptz" if c == "ts" else "double") for c in column_names(s)}
        schema[f"{s}_long"] = {"ts": "timestamptz", "tag_name": "text", "value": "double"}
    schema["sensor_catalog"] = {c: "text" for c in SENSOR_CATALOG_COLS}
    schema["run_metadata"] = {"key": "text", "value": "text"}
    return schema


def _check_columns(stmt: exp.Expression, dialect: str) -> None:
    """Reject a column that exists in no reachable relation — before the database sees it.

    Uses sqlglot's scope-aware qualification against the catalog schema. Only a name that
    no table has and the query never aliases is rejected (a hallucinated ``bearing_temp_9``
    or ``tag_type``); anything the optimizer merely cannot follow is left to the database,
    so valid SQL is never blocked by an optimizer limitation.
    """
    try:
        qualify(stmt.copy(), schema=catalog_schema(), dialect=dialect,
                validate_qualify_columns=True)
        return
    except OptimizeError as e:
        m = re.search(r"Column '([^']+)' could not be resolved", str(e))
        if not m:
            return
        name = m.group(1).split(".")[-1].strip('"').lower()
    except Exception:  # noqa: BLE001 — optimizer limitations are not validation failures
        return

    schema = catalog_schema()
    tables = {t.name.lower() for t in stmt.find_all(exp.Table) if t.name.lower() in schema}
    in_scope = {c for t in tables for c in schema[t]}
    aliases = {a.alias.lower() for a in stmt.find_all(exp.Alias) if a.alias}
    aliases |= {c.name.lower() for t in stmt.find_all(exp.TableAlias) for c in t.columns}
    if name in in_scope or name in aliases:
        return
    pool = sorted(in_scope) or sorted({c for cols in schema.values() for c in cols})
    near = difflib.get_close_matches(name, pool, n=3)
    raise SqlValidationError(f"unknown column {name!r}"
                             + (f" — did you mean {', '.join(near)}?" if near else "")
                             + " (use explore_schema for real tag names)")
