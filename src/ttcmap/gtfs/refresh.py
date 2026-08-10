"""GTFS refresh orchestration.

Ported from node-api/src/sync/syncJob.js, minus the subprocess: the pipeline it
used to spawn is now an in-process function call. The version-check logic is
unchanged — the feed changes every few weeks, so we compare CKAN's
metadata_modified against the value stored in `meta` and only rebuild on a
difference (or when the database is missing).

Also unchanged from the JS: when CKAN is unreachable we keep serving the data we
already have rather than failing, unless there is nothing to serve yet.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.db import get_meta, set_meta, table_exists
from ttcmap.gtfs import build, ckan, network
from ttcmap.map import segments, topology

log = logging.getLogger(__name__)

GTFS_VERSION_META_KEY = "gtfs_last_modified"
STOP_TIMES_TABLE = "SUBWAY_STOP_TIMES"

_lock = asyncio.Lock()
_last_result: "RefreshResult | None" = None


@dataclass
class RefreshResult:
    status: str  # ok | skipped | error
    updated: bool
    message: str
    version: str | None = None
    recordCount: int | None = None
    ranAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict:
        return asdict(self)


def get_last_result() -> RefreshResult | None:
    return _last_result


def database_is_missing() -> bool:
    return not get_settings().database_path.exists() or not table_exists(STOP_TIMES_TABLE)


def _rebuild() -> int:
    """Blocking: download, extract, rebuild tables, regenerate network.json."""
    package = ckan.get_package_metadata()
    data_dir = ckan.download_and_extract(package)
    count = build.build(data_dir)
    # regenerating the topology is part of the rebuild, so network.json cannot
    # drift from the schedule tables the way it did when this was a manual step
    network.write_network(data_dir)
    # both caches are derived from what we just replaced, and POST /gtfs/refresh
    # has no other invalidation point, so drop them here rather than at the call
    # sites
    topology.clear_cache()
    segments.clear_cache()
    return count


async def refresh(force: bool = False) -> RefreshResult:
    global _last_result

    if _lock.locked():
        return RefreshResult(status="skipped", updated=False, message="refresh already running")

    async with _lock:
        db_missing = database_is_missing()
        stored_version = get_meta(GTFS_VERSION_META_KEY)

        remote_version: str | None = None
        try:
            remote_version = await asyncio.to_thread(ckan.get_feed_version)
        except Exception as error:
            if not db_missing and stored_version:
                result = RefreshResult(
                    status="ok",
                    updated=False,
                    message=f"GTFS version check failed ({error}); keeping current data",
                    version=stored_version,
                )
                _last_result = result
                return result
            log.warning("CKAN version check failed and there is no local data: %s", error)

        if not force and not db_missing and stored_version and remote_version == stored_version:
            result = RefreshResult(
                status="ok",
                updated=False,
                message=f"GTFS feed unchanged ({remote_version})",
                version=stored_version,
            )
            _last_result = result
            return result

        try:
            # the pandas merge runs for minutes; keep it off the event loop so
            # map-state and led-state keep answering during a rebuild
            count = await asyncio.to_thread(_rebuild)
        except Exception as error:
            log.exception("GTFS refresh failed")
            result = RefreshResult(
                status="error", updated=False, message=str(error), version=stored_version
            )
            _last_result = result
            return result

        if remote_version:
            set_meta(GTFS_VERSION_META_KEY, remote_version)

        result = RefreshResult(
            status="ok",
            updated=True,
            message=f"rebuilt from GTFS feed ({remote_version or 'version unknown'})",
            version=remote_version,
            recordCount=count,
        )
        _last_result = result
        return result


async def refresh_loop() -> None:
    """Re-check the feed on the configured interval for the life of the process."""
    interval = get_settings().gtfs_check_interval_s
    while True:
        await asyncio.sleep(interval)
        try:
            result = await refresh()
            log.info("Scheduled GTFS check: %s", result.message)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scheduled GTFS check failed")
