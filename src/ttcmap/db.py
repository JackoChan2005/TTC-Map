"""SQLite access for the single ttc.db database.

One process, one writer, so the two-database split by ownership that the Node
server needed (Python-owned GTFS file + Node-owned realtime file) collapses into
one file. The realtime snapshot no longer lives in SQLite at all — see
ttcmap.map.recorder.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from ttcmap.config import get_settings

BUSY_TIMEOUT_MS = 5000


class DatasetUnavailable(RuntimeError):
    """No compatible, completely published schedule is available."""


@dataclass
class Dataset:
    conn: sqlite3.Connection
    payload: dict
    version: str | None
    revision: str

    @property
    def generation(self) -> str:
        return self.payload["generation"]

    @property
    def network(self) -> dict:
        return self.payload["network"]


@contextmanager
def read_dataset() -> Iterator[Dataset]:
    """Pin every query in a computation to one SQLite WAL read snapshot."""
    if not get_settings().database_path.exists():
        raise DatasetUnavailable("GTFS dataset not built; run ttcmap refresh")
    with connect(readonly=True) as conn:
        conn.execute("BEGIN")
        try:
            row = conn.execute("SELECT * FROM active_dataset WHERE id=1").fetchone()
        except sqlite3.OperationalError as error:
            raise DatasetUnavailable("GTFS migration pending; run ttcmap refresh") from error
        if row is None:
            raise DatasetUnavailable("GTFS dataset not published")
        from ttcmap.gtfs.build import IMPORTER_REVISION

        if row["revision"] != IMPORTER_REVISION:
            raise DatasetUnavailable("GTFS importer upgrade pending; run ttcmap refresh")
        yield Dataset(conn, json.loads(row["payload"]), row["version"], row["revision"])


@contextmanager
def connect(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    """Open a connection to ttc.db with WAL and row access by column name."""
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)

    if readonly and path.exists():
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)

    try:
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        if not readonly:
            conn.execute("PRAGMA journal_mode = WAL")
        yield conn
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def init_schema() -> None:
    """Create the tables the app owns. GTFS tables are created by the rebuild."""
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.commit()


def get_meta(key: str) -> str | None:
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def table_exists(name: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        return row is not None
