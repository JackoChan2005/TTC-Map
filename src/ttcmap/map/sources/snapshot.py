"""Freshness and generation checks for each independently polled line."""

from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.map.sources.ntas import LinePoll


def snapshot_is_usable(
    snapshot: LinePoll | None,
    now: datetime | None = None,
    max_age_s: float | None = None,
    generation: str | None = None,
) -> bool:
    if snapshot is None or snapshot.status != "ok":
        return False
    age = ((now or datetime.now(UTC)) - snapshot.polled_at).total_seconds()
    return 0 <= age <= (get_settings().snapshot_max_age_s if max_age_s is None else max_age_s) and (
        generation is None or generation == snapshot.generation
    )
