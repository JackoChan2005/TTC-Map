"""One bounded, fair poll produces independent per-line snapshots."""

import asyncio
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from types import MappingProxyType

from ttcmap.config import get_settings
from ttcmap.db import read_dataset
from ttcmap.map import interpolate
from ttcmap.map.segments import segment_spans
from ttcmap.map.sources.ntas import LinePoll, poll_lines

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    polled_at: datetime
    lines: Mapping[str, LinePoll] = field(default_factory=dict)
    status: str = "ok"

    def __post_init__(self):
        object.__setattr__(self, "lines", MappingProxyType(dict(self.lines)))

    @property
    def positions(self):
        return [p for line in self.lines.values() for p in line.positions]


_snapshot: Snapshot | None = None


def get_snapshot() -> Snapshot | None:
    return _snapshot


def set_snapshot(snapshot: Snapshot | None) -> None:
    global _snapshot
    _snapshot = snapshot


def _poll_context():
    with read_dataset() as dataset:
        return dataset.network, dataset.generation, segment_spans(dataset)


async def poll_once() -> Snapshot:
    global _snapshot
    previous = _snapshot
    try:
        topology, generation, spans = await asyncio.to_thread(_poll_context)
        cutoff = max(
            get_settings().ntas_arriving_min, math.ceil(max(spans.values(), default=300) / 60) + 1
        )
        lines = await poll_lines(topology, generation, cutoff)
        for key, line in list(lines.items()):
            old = previous.lines.get(key) if previous else None
            elapsed = (line.polled_at - old.polled_at).total_seconds() if old else 0
            if (
                old
                and old.status == line.status == "ok"
                and old.generation == line.generation
                and 0 <= elapsed <= get_settings().snapshot_max_age_s
            ):
                lines[key] = replace(
                    line,
                    positions=tuple(
                        interpolate.carry_floor(
                            list(line.positions), list(old.positions), elapsed, spans
                        )
                    ),
                )
        status = "ok" if all(line.status == "ok" for line in lines.values()) else "partial"
        _snapshot = Snapshot(datetime.now(UTC), lines, status)
    except Exception as error:
        log.warning("NTAS poll unavailable: %s", error)
        _snapshot = Snapshot(datetime.now(UTC), status="error")
    return _snapshot


async def poll_loop() -> None:
    loop = asyncio.get_running_loop()
    while True:
        started = loop.time()
        await poll_once()
        await asyncio.sleep(max(0, get_settings().ntas_poll_s - (loop.time() - started)))
