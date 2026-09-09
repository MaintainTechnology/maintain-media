"""PostgreSQL authority; transactions commit at caller boundaries."""
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from abr_engine.config import ROOT, Settings


def connect(settings: Settings) -> psycopg.Connection[dict[str, Any]]:
    conn = psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5)
    conn.execute("SET TIME ZONE 'UTC'")
    conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(settings.schema_name)))
    conn.execute("SET statement_timeout = '30s'")
    return conn


@contextmanager
def transaction(settings: Settings) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with connect(settings) as conn:
        yield conn


def lock(conn, *keys: str) -> None:
    namespace = conn.execute("SELECT current_schema() AS name").fetchone()["name"]
    for key in sorted(set(keys)):
        value = int.from_bytes(hashlib.sha256((namespace + ":" + key).encode()).digest()[:8], "big", signed=True)
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (value,))


def migrate(settings: Settings, directory: Path | None = None) -> list[str]:
    applied = []
    with transaction(settings) as conn:
        if conn.info.server_version // 10000 != 16:
            raise ValueError("PostgreSQL 16 is required")
        lock(conn, "migrations")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (name text PRIMARY KEY, digest text NOT NULL)")
        for file in sorted((directory or ROOT / "migrations").glob("*.sql")):
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            prior = conn.execute("SELECT digest FROM schema_migration WHERE name=%s", (file.name,)).fetchone()
            if prior:
                if prior["digest"] != digest:
                    raise ValueError("Applied migration checksum mismatch")
                continue
            conn.execute(file.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migration VALUES (%s,%s)", (file.name, digest))
            applied.append(file.name)
    return applied
