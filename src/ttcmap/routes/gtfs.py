"""Readiness and per-line source diagnostics for the published dataset."""

from datetime import UTC, datetime

from fastapi import APIRouter

from ttcmap.config import get_settings
from ttcmap.db import DatasetUnavailable, read_dataset
from ttcmap.gtfs.refresh import get_last_result, refresh
from ttcmap.gtfs.service_calendar import require_schedule
from ttcmap.map.recorder import get_snapshot
from ttcmap.map.sources.schedule import operating_lines
from ttcmap.map.sources.snapshot import snapshot_is_usable
from ttcmap.map.toronto_time import get_service_windows

router = APIRouter()


@router.get("/health")
def health() -> dict:
    now = datetime.now(UTC)
    settings = get_settings()
    snapshot = get_snapshot()
    gtfs = {"ready": False}
    realtime = {"status": snapshot.status if snapshot else "no-snapshot", "lines": {}}
    try:
        with read_dataset() as dataset:
            windows = get_service_windows(now)
            valid_by_line = {}
            for line in dataset.network["lines"]:
                try:
                    require_schedule(dataset, windows[0].date, windows[1], {line["id"]})
                    valid_by_line[line["id"]] = True
                except DatasetUnavailable:
                    valid_by_line[line["id"]] = False
            valid = all(valid_by_line.values())
            gtfs = {
                "ready": valid,
                "scheduleValid": valid,
                "scheduleValidByLine": valid_by_line,
                "generation": dataset.generation,
                "version": dataset.version,
                "importerRevision": dataset.revision,
            }
            available = {key for key, valid in valid_by_line.items() if valid}
            operating = operating_lines(dataset, now, available) if available else set()
            for line in dataset.network["lines"]:
                key = line["id"]
                enabled = key.removeprefix("line-") in settings.ntas_enabled_lines
                poll = snapshot.lines.get(key) if snapshot else None
                usable = enabled and snapshot_is_usable(poll, now, generation=dataset.generation)
                reason = (
                    None
                    if usable
                    else "snapshot_unavailable"
                    if enabled
                    else "realtime_not_enabled"
                )
                if usable and poll.prediction_count == 0:
                    if not valid_by_line[key]:
                        usable, reason = False, "schedule_unavailable"
                    elif key in operating:
                        usable, reason = False, "insufficient_predictions"
                source = "ntas" if usable else "schedule" if valid_by_line[key] else None
                if settings.map_source == "schedule":
                    source, reason = ("schedule" if valid_by_line[key] else None), "forced_schedule"
                elif settings.map_source == "ntas" and not usable:
                    source = None
                realtime["lines"][key] = {
                    "configured": settings.map_source,
                    "realtimeEnabled": enabled,
                    "source": source,
                    "reason": reason,
                    "polledAt": poll.polled_at.isoformat() if poll else None,
                    "ageSeconds": (now - poll.polled_at).total_seconds() if poll else None,
                    "validPlatforms": list(poll.valid) if poll else None,
                    "expectedPlatforms": list(poll.expected) if poll else None,
                    "pollReason": poll.reason if poll else None,
                }
    except DatasetUnavailable as error:
        gtfs["reason"] = str(error)
    result = get_last_result()
    gtfs["lastRefresh"] = result.as_dict() if result else None
    return {
        "status": "ok" if gtfs["ready"] else "degraded",
        "timestamp": now.isoformat(),
        "gtfs": gtfs,
        "realtime": realtime,
    }


@router.get("/gtfs/status")
def gtfs_status() -> dict:
    return health()["gtfs"]


@router.post("/gtfs/refresh")
async def gtfs_refresh(force: bool = False) -> dict:
    return (await refresh(force=force)).as_dict()
