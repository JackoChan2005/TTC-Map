"""Prepare off-thread, validate, and atomically publish one active dataset."""

import asyncio
import json
import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from filelock import Timeout

from ttcmap.config import get_settings
from ttcmap.db import connect
from ttcmap.gtfs import build, ckan
from ttcmap.gtfs.refresh_lock import refresh_lock

log = logging.getLogger(__name__)
GTFS_VERSION_META_KEY = "gtfs_last_modified"
STOP_TIMES_TABLE = "SUBWAY_STOP_TIMES"
_lock = asyncio.Lock()
_last_result = None


@dataclass
class RefreshResult:
    status: str
    updated: bool
    message: str
    version: str | None = None
    recordCount: int | None = None
    ranAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict:
        return asdict(self)


def get_last_result():
    return _last_result


def active_metadata() -> tuple[dict, str | None, str | None]:
    with connect() as conn:
        try:
            row = conn.execute("SELECT * FROM active_dataset WHERE id=1").fetchone()
        except sqlite3.OperationalError:
            row = None
    return (
        (json.loads(row["payload"]), row["version"], row["revision"]) if row else ({}, None, None)
    )


def database_is_missing() -> bool:
    return active_metadata()[2] != build.IMPORTER_REVISION


def _refresh_sync(force: bool) -> RefreshResult:
    try:
        with refresh_lock():
            active, version, revision = active_metadata()
            compatible = (
                revision == build.IMPORTER_REVISION
                and active.get("inputsDigest") == build.input_digest()
            )
            try:
                package = ckan.get_package_metadata()
            except Exception as error:
                package = None
                if compatible and not force:
                    return RefreshResult(
                        "ok", False, f"CKAN unavailable; keeping published data: {error}", version
                    )
            remote = package.get("metadata_modified") if package else version
            if compatible and not force and package and remote is not None and remote == version:
                return RefreshResult("ok", False, "GTFS feed unchanged", version)
            with ckan.feed_input(package, active.get("feedCache")) as (directory, cache):
                tables, artifact = build.prepare_dataset(directory)
                artifact["feedCache"] = cache
                count = build.publish_dataset(tables, artifact, cache["version"])
            return RefreshResult(
                "ok", True, "Published complete five-line dataset", cache["version"], count
            )
    except Timeout:
        return RefreshResult("skipped", False, "refresh already running")
    except Exception as error:
        log.exception("GTFS refresh failed; previous dataset retained")
        return RefreshResult("error", False, str(error))


async def refresh(force: bool = False) -> RefreshResult:
    global _last_result
    if _lock.locked():
        return RefreshResult("skipped", False, "refresh already running")
    async with _lock:
        _last_result = await asyncio.to_thread(_refresh_sync, force)
        return _last_result


async def refresh_loop() -> None:
    while True:
        await asyncio.sleep(get_settings().gtfs_check_interval_s)
        await refresh()
