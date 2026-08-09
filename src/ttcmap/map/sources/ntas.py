"""Realtime train positions from TTC's NTAS (Next Train Arrival System).

Ported from node-api/src/map/sources/ntasSource.js. One request per platform
returns the next arrival times in minutes:

    [{"line": "2", "direction": "0", "nextTrains": "1, 3, 6", ...}]

A train arriving within `ntas_arriving_min` minutes is placed approaching that
platform's station from the previous station on the line. NTAS carries no train
ids, so positions are deduped per (line, direction, station).

The hand-rolled concurrency lanes of the original become an asyncio.Semaphore
over a shared keep-alive client.
"""

import asyncio
import logging

import httpx

from ttcmap.config import get_settings
from ttcmap.map.state import TrainPosition
from ttcmap.map.topology import load_topology, previous_station

log = logging.getLogger(__name__)

name = "ntas"


def _first_arrival_minutes(entry: dict) -> int | None:
    first = str(entry.get("nextTrains") or "").split(",")[0].strip()
    try:
        return int(first)
    except ValueError:
        return None


def positions_from_responses(
    topology: dict, responses: list[tuple[str, list]]
) -> list[TrainPosition]:
    """Pure: map (platform_id, entries) pairs onto deduped TrainPositions."""
    arriving_min = get_settings().ntas_arriving_min
    by_key: dict[str, TrainPosition] = {}

    for platform_id, entries in responses:
        platform = topology["platforms"].get(platform_id)
        if not platform or not isinstance(entries, list):
            continue

        for entry in entries:
            minutes = _first_arrival_minutes(entry)
            if minutes is None or minutes > arriving_min:
                continue

            try:
                direction = int(entry["direction"])
            except (KeyError, TypeError, ValueError):
                continue

            station = platform["station"]
            origin = previous_station(topology, platform["line"], direction, station)

            by_key[f"{platform['line']}|{direction}|{station}"] = TrainPosition(
                line=platform["line"],
                direction=direction,
                from_station=origin or station,
                to_station=station if origin else None,
                progress=1 - (minutes / (arriving_min + 1)) if origin else 0.0,
            )

    return list(by_key.values())


async def _fetch_platform(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, platform_id: str
) -> tuple[str, list]:
    async with semaphore:
        response = await client.get(platform_id)
        response.raise_for_status()
        return platform_id, response.json()


async def get_train_positions() -> list[TrainPosition]:
    settings = get_settings()
    topology = load_topology()
    platform_ids = list(topology["platforms"].keys())

    semaphore = asyncio.Semaphore(settings.ntas_concurrency)
    limits = httpx.Limits(max_connections=settings.ntas_concurrency)

    async with httpx.AsyncClient(
        base_url=settings.ntas_base_url, timeout=settings.ntas_timeout_s, limits=limits
    ) as client:
        settled = await asyncio.gather(
            *(_fetch_platform(client, semaphore, pid) for pid in platform_ids),
            return_exceptions=True,
        )

    ok = [result for result in settled if not isinstance(result, BaseException)]
    # a partial feed would silently blank out sections of the map, so treat it
    # as unavailable and let the caller fall back to the schedule
    if len(ok) < len(platform_ids) / 2:
        raise RuntimeError(
            f"NTAS unavailable: only {len(ok)}/{len(platform_ids)} platforms responded"
        )

    return positions_from_responses(topology, ok)
