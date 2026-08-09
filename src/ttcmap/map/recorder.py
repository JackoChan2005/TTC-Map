"""Polls NTAS on a fixed cadence and keeps the latest snapshot in memory.

Ported from node-api/src/map/rtRecorder.js. The snapshot used to be a single row
in a SQLite table purely because `npm run sync` ran as a separate process; with
one process it is just module state.

A single failed poll marks the snapshot 'error' so serving falls back to the
schedule simulation immediately — stale realtime positions are never shown.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.map.sources import ntas
from ttcmap.map.state import TrainPosition

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    polled_at: datetime
    status: str  # ok | error
    positions: list[TrainPosition] = field(default_factory=list)


_snapshot: Snapshot | None = None


def get_snapshot() -> Snapshot | None:
    return _snapshot


def set_snapshot(snapshot: Snapshot | None) -> None:
    """Exposed for tests."""
    global _snapshot
    _snapshot = snapshot


async def poll_once() -> Snapshot:
    """Poll NTAS once, bounded so a hanging feed cannot stall the loop.

    Without the deadline, 148 platforms at concurrency 10 against an
    unresponsive host take (148/concurrency) x request-timeout to fail — well
    past the poll interval, leaving the recorder blocked and the board holding a
    frame it believes is current.
    """
    global _snapshot
    settings = get_settings()
    try:
        positions = await asyncio.wait_for(
            ntas.get_train_positions(), timeout=settings.ntas_poll_timeout_s
        )
        _snapshot = Snapshot(polled_at=datetime.now(UTC), status="ok", positions=positions)
    except TimeoutError:
        log.warning(
            "NTAS poll exceeded %ss; map falls back to schedule", settings.ntas_poll_timeout_s
        )
        _snapshot = Snapshot(polled_at=datetime.now(UTC), status="error", positions=[])
    except Exception as error:
        log.warning("NTAS poll failed (%s); map falls back to schedule", error)
        _snapshot = Snapshot(polled_at=datetime.now(UTC), status="error", positions=[])
    return _snapshot


async def poll_loop() -> None:
    interval = get_settings().ntas_poll_s
    snapshot = await poll_once()
    if snapshot.status == "ok":
        log.info(
            "NTAS recorder started (%d trains, polling every %ds)",
            len(snapshot.positions),
            interval,
        )

    while True:
        await asyncio.sleep(interval)
        try:
            await poll_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("NTAS recorder loop error")
