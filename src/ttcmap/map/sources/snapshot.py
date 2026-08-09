"""Train positions from the in-memory NTAS snapshot the recorder maintains.

Ported from node-api/src/map/sources/snapshotSource.js. Raises when the snapshot
is failed, missing or stale so the caller falls back — one failed poll means no
realtime data is served rather than stale positions.
"""

from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.map import recorder
from ttcmap.map.state import TrainPosition

name = "snapshot"


def snapshot_is_usable(
    snapshot: "recorder.Snapshot | None",
    now: datetime | None = None,
    max_age_s: float | None = None,
) -> bool:
    """Pure; the freshness rule, exercised directly by tests."""
    if snapshot is None or snapshot.status != "ok":
        return False
    if max_age_s is None:
        max_age_s = get_settings().snapshot_max_age_s
    now = now or datetime.now(UTC)

    return (now - snapshot.polled_at).total_seconds() <= max_age_s


def get_train_positions(now: datetime | None = None) -> list[TrainPosition]:
    snapshot = recorder.get_snapshot()
    if not snapshot_is_usable(snapshot, now):
        raise RuntimeError("realtime snapshot unavailable (failed, missing or stale)")
    return snapshot.positions
