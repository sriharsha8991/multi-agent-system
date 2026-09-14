"""PostgreSQL connection helpers, read-only role setup, and COPY loading."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from ..config import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    import psycopg


def connect(settings: Settings | None = None, *, reader: bool = False,
            autocommit: bool = True) -> "psycopg.Connection":
    """Open a connection as the writer (default) or the read-only role."""
    import psycopg
    settings = settings or get_settings()
    return psycopg.connect(settings.pg_dsn(reader=reader), autocommit=autocommit)


def execute(conn: psycopg.Connection, sql: str, params: Sequence[Any] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params)


def executescript(conn: psycopg.Connection, statements: Iterable[str]) -> None:
    with conn.cursor() as cur:
        for stmt in statements:
            s = stmt.strip()
            if s:
                cur.execute(s)


def fetchall(conn: psycopg.Connection, sql: str,
             params: Sequence[Any] | None = None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetchone(conn: psycopg.Connection, sql: str,
             params: Sequence[Any] | None = None) -> tuple | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def copy_rows(conn: psycopg.Connection, table: str, columns: Sequence[str],
              rows: Iterable[Sequence[Any]]) -> int:
    """Bulk-load ``rows`` into ``table`` via COPY. Returns the row count."""
    col_list = ", ".join(f'"{c}"' for c in columns)
    n = 0
    with conn.cursor() as cur:
        with cur.copy(f'COPY "{table}" ({col_list}) FROM STDIN') as copy:
            for row in rows:
                copy.write_row(row)
                n += 1
    return n


def setup_reader_role(conn: psycopg.Connection, settings: Settings | None = None) -> None:
    """Create/refresh the deterministic, read-only role the SQL agent will use.

    ``mas_reader`` gets SELECT-only, ``default_transaction_read_only = on`` and a
    15 s statement timeout, so no generated query can mutate or hang the DB.
    """
    from psycopg import sql

    settings = settings or get_settings()
    user = settings.pg_reader_user
    pw = settings.pg_reader_password
    db = settings.pg_db
    ident = sql.Identifier(user)
    dbident = sql.Identifier(db)
    pwlit = sql.Literal(pw)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
        exists = cur.fetchone() is not None
        verb = sql.SQL("ALTER" if exists else "CREATE")
        # utility statements can't bind parameters — compose literals safely
        cur.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(verb, ident, pwlit))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(dbident, ident))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(ident))
        cur.execute(sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}"
        ).format(ident))
        cur.execute(sql.SQL(
            "ALTER ROLE {} SET default_transaction_read_only = on").format(ident))
        cur.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '15s'").format(ident))
