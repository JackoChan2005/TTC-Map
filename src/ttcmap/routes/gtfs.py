"""GTFS refresh and health endpoints.

Replaces /api/sync/run, /api/sync/status and /api/health. The /api/records
endpoints are gone with the synced_records table they served — it was a JSON copy
of SUBWAY_STOP_TIMES rewritten in full on every rebuild.
"""

from datetime import UTC, datetime

from fastapi import APIRouter

from ttcmap.db import get_meta, table_exists
from ttcmap.gtfs.refresh import (
    GTFS_VERSION_META_KEY,
    STOP_TIMES_TABLE,
    get_last_result,
    refresh,
)
from ttcmap.map.recorder import get_snapshot

router = APIRouter()


@router.get("/health")
def health() -> dict:
    snapshot = get_snapshot()
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "gtfs": {
            "ready": table_exists(STOP_TIMES_TABLE),
            "version": get_meta(GTFS_VERSION_META_KEY),
        },
        "realtime": {
            "status": snapshot.status if snapshot else "no-snapshot",
            "polledAt": snapshot.polled_at.isoformat() if snapshot else None,
            "trainCount": len(snapshot.positions) if snapshot else 0,
        },
    }


@router.get("/gtfs/status")
def gtfs_status() -> dict:
    result = get_last_result()
    return {
        "version": get_meta(GTFS_VERSION_META_KEY),
        "ready": table_exists(STOP_TIMES_TABLE),
        "lastRefresh": result.as_dict() if result else None,
    }


@router.post("/gtfs/refresh")
async def gtfs_refresh(force: bool = False) -> dict:
    result = await refresh(force=force)
    return result.as_dict()
