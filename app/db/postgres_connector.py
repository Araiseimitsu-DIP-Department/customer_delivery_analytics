# -*- coding: utf-8 -*-
"""PostgreSQL connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Iterable

import psycopg
from psycopg import sql as psycopg_sql
from psycopg.rows import dict_row

from app.config import settings


class PostgresConnectionError(Exception):
    """PostgreSQL 接続に失敗した場合のエラー。"""


@dataclass(frozen=True)
class PostgresConnections:
    deliveries: psycopg.Connection
    masters: psycopg.Connection


@contextmanager
def open_connection(url: str) -> Generator[psycopg.Connection, None, None]:
    try:
        conn = psycopg.connect(url, connect_timeout=settings.POSTGRES_CONNECT_TIMEOUT_SECONDS)
        schema = settings.resolve_postgres_schema()
        if schema:
            conn.execute(psycopg_sql.SQL("SET search_path TO {}").format(psycopg_sql.Identifier(schema)))
    except Exception as exc:  # noqa: BLE001
        raise PostgresConnectionError(f"PostgreSQL への接続に失敗しました。\n詳細: {exc}") from exc
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def open_app_connections() -> Generator[PostgresConnections, None, None]:
    deliveries_url = settings.resolve_deliveries_database_url()
    masters_url = settings.resolve_masters_database_url()
    with open_connection(deliveries_url) as deliveries_conn:
        if masters_url == deliveries_url:
            yield PostgresConnections(deliveries=deliveries_conn, masters=deliveries_conn)
            return
        with open_connection(masters_url) as masters_conn:
            active_deliveries_conn = deliveries_conn
            if not table_exists(deliveries_conn, "deliveries") and table_exists(masters_conn, "deliveries"):
                active_deliveries_conn = masters_conn
            yield PostgresConnections(deliveries=active_deliveries_conn, masters=masters_conn)


def table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s)", (table_name,)).fetchone()
    return bool(row and row[0])


def fetch_all_dicts(
    conn: psycopg.Connection,
    sql: str,
    params: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, tuple(params or ()))
        return [dict(row) for row in cur.fetchall()]
