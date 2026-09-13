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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from itertools import zip_longest

import httpx

from ttcmap.config import get_settings
from ttcmap.map.state import TrainPosition
from ttcmap.map.topology import previous_station

log = logging.getLogger(__name__)

name = "ntas"


def _arrival_minutes(entry: dict) -> list[int]:
    """Every arrival in "1, 3, 6", in order. Unparseable entries are dropped."""
    minutes = []
    for field in str(entry.get("nextTrains") or "").split(","):
        try:
            minute = int(field.strip())
            if minute >= 0:
                minutes.append(minute)
        except ValueError:
            continue
    return sorted(minutes)


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

            if direction != platform["direction"] or str(entry.get("line")) != platform[
                "line"
            ].removeprefix("line-"):
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


@dataclass(frozen=True)
class LinePoll:
    line: str
    generation: str
    polled_at: datetime
    positions: tuple[TrainPosition, ...] = ()
    expected: tuple[int, int] = (0, 0)
    valid: tuple[int, int] = (0, 0)
    prediction_count: int = 0
    status: str = "error"
    reason: str | None = "poll_failed"


def valid_response(platform: dict, entries: object) -> bool:
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        if (
            str(entry.get("line")) != platform["line"].removeprefix("line-")
            or str(entry.get("direction")) != str(platform["direction"])
            or str(entry.get("stopCode")) != platform["stopCode"]
            or not isinstance(entry.get("nextTrains"), str)
        ):
            return False
        # Empty is a valid queue. A nonempty wholly malformed queue is not healthy.
        if entry["nextTrains"].strip() and not _arrival_minutes(entry):
            return False
    return True


async def poll_lines(topology: dict, generation: str, arriving_min: int) -> dict[str, LinePoll]:
    settings = get_settings()
    by_line = {
        line["id"]: []
        for line in topology["lines"]
        if line["id"].removeprefix("line-") in settings.ntas_enabled_lines
    }
    for pid, platform in topology["platforms"].items():
        if platform["line"] in by_line:
            by_line[platform["line"]].append(pid)
    # Interleave lines before tasks enter the shared semaphore; no late-line starvation.
    order = [pid for group in zip_longest(*by_line.values()) for pid in group if pid]
    if not order:
        return {}
    started = datetime.now(UTC)
    semaphore = asyncio.Semaphore(settings.ntas_concurrency)
    completed = {}
    async with httpx.AsyncClient(
        base_url=settings.ntas_base_url, timeout=settings.ntas_timeout_s
    ) as client:

        async def fetch(pid):
            async with semaphore:
                observed = datetime.now(UTC)
                try:
                    response = await client.get(topology["platforms"][pid]["stopCode"])
                    response.raise_for_status()
                    entries = response.json()
                    if valid_response(topology["platforms"][pid], entries):
                        completed[pid] = (observed, entries)
                except (httpx.HTTPError, ValueError):
                    pass

        tasks = [asyncio.create_task(fetch(pid)) for pid in order]
        try:
            await asyncio.wait(tasks, timeout=settings.ntas_poll_timeout_s)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    results = {}
    for line, pids in by_line.items():
        expected, valid = [0, 0], [0, 0]
        positions, prediction_count = [], 0
        for pid in pids:
            direction = topology["platforms"][pid]["direction"]
            expected[direction] += 1
            if pid not in completed:
                continue
            valid[direction] += 1
            observed, entries = completed[pid]
            prediction_count += sum(len(_arrival_minutes(e)) for e in entries)
            offset = (observed - started).total_seconds()
            positions.extend(
                replace(pos, eta_s=pos.eta_s + offset)
                for pos in positions_from_responses(topology, [(pid, entries)], arriving_min)
            )
        threshold = settings.ntas_min_coverage_by_line[line.removeprefix("line-")]
        ok = all(expected[d] and valid[d] / expected[d] >= threshold for d in (0, 1))
        results[line] = LinePoll(
            line,
            generation,
            started,
            tuple(positions) if ok else (),
            tuple(expected),
            tuple(valid),
            prediction_count,
            "ok" if ok else "error",
            None if ok else "insufficient_coverage",
        )
    return results
