"""Realtime train positions from TTC's NTAS (Next Train Arrival System).

Ported from node-api/src/map/sources/ntasSource.js. One request per platform
returns the next arrival times in minutes:

    [{"line": "2", "direction": "0", "nextTrains": "1, 3, 6", ...}]

Every arrival in that list is a train, so all of them are kept — "3" and "6"
above are the two trains queued behind the one arriving in a minute. Each is
placed approaching that platform's station from the previous station on the
line, and carries its ETA rather than a position: NTAS measures time-to-arrival,
and ttcmap.map.interpolate turns that into a position using the segment's
traversal time. Every train on the network is approaching *some* platform, so
keeping the full list covers the whole map rather than just the last minute of
each approach.

NTAS carries no train ids, so positions are deduped per
(line, direction, station, nth-arrival) — the nth entry of a platform's queue is
the same train from one poll to the next, which is enough to keep a train moving
forwards but is not a real vehicle identity.

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


def _arrival_minutes(entry: dict) -> list[int]:
    """Every arrival in "1, 3, 6", in order. Unparseable entries are dropped."""
    minutes = []
    for field in str(entry.get("nextTrains") or "").split(","):
        try:
            minutes.append(int(field.strip()))
        except ValueError:
            continue
    return minutes


def positions_from_responses(
    topology: dict, responses: list[tuple[str, list]], arriving_min: int | None = None
) -> list[TrainPosition]:
    """Pure: map (platform_id, entries) pairs onto deduped TrainPositions.

    `arriving_min` is how far ahead to look, in minutes; it defaults to the
    configured window and is a parameter so tests do not depend on settings.
    """
    if arriving_min is None:
        arriving_min = get_settings().ntas_arriving_min
    by_key: dict[str, TrainPosition] = {}

    for platform_id, entries in responses:
        platform = topology["platforms"].get(platform_id)
        if not platform or not isinstance(entries, list):
            continue

        for entry in entries:
            try:
                direction = int(entry["direction"])
            except (KeyError, TypeError, ValueError):
                continue

            station = platform["station"]
            origin = previous_station(topology, platform["line"], direction, station)

            for nth, minutes in enumerate(_arrival_minutes(entry)):
                if minutes > arriving_min:
                    # the list is ascending, so nothing after this is closer
                    break

                key = f"{platform['line']}|{direction}|{station}|{nth}"
                by_key[key] = TrainPosition(
                    line=platform["line"],
                    direction=direction,
                    from_station=origin or station,
                    to_station=station if origin else None,
                    eta_s=float(max(minutes, 0) * 60),
                    key=key,
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
