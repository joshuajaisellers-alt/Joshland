"""SQLite-backed persistence utilities for the Correspondence Tracker."""
from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Generator, Iterable, Optional

SCHEMA_VERSION = 1


class Database:
    """Lightweight SQLite wrapper that ensures required tables exist."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: Optional[sqlite3.Connection] = None

    @contextlib.contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._ensure_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _ensure_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            self._apply_migrations(self._connection)
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            version = self._get_schema_version(conn)
            if version < SCHEMA_VERSION:
                self._create_schema(conn)
                self._set_schema_version(conn, SCHEMA_VERSION)

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                preferred_channel TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS correspondences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('incoming', 'outgoing')),
                medium TEXT,
                subject TEXT,
                body TEXT,
                attachment_path TEXT,
                sentiment TEXT,
                tags TEXT,
                related_topic TEXT,
                sent_at TEXT NOT NULL,
                follow_up_date TEXT,
                response_status TEXT DEFAULT 'pending',
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            );
            """
        )

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        cur = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        conn.execute(
            "REPLACE INTO metadata (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )

    def execute(self, sql: str, parameters: Iterable | None = None) -> sqlite3.Cursor:
        with self.connection() as conn:
            return conn.execute(sql, parameters or [])

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable]) -> sqlite3.Cursor:
        with self.connection() as conn:
            return conn.executemany(sql, seq_of_parameters)

    def query(self, sql: str, parameters: Iterable | None = None) -> list[sqlite3.Row]:
        with self.connection() as conn:
            cur = conn.execute(sql, parameters or [])
            return cur.fetchall()


__all__ = ["Database", "SCHEMA_VERSION"]
