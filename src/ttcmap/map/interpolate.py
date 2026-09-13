"""Estimate segment progress from aged NTAS countdowns and scheduled travel times.

Discard sightings outside the estimated segment to reduce duplicate observations.
Each request derives positions from the unchanged snapshot; these are not GPS fixes.
"""

from dataclasses import replace

from ttcmap.map.segments import span_for
from ttcmap.map.state import TrainPosition

# Hold arrivals briefly across dwell and whole-minute ETA rounding.
ARRIVED_GRACE_S = 45.0


def is_on_segment(eta_s: float, span_s: float) -> bool:
    """Accept the estimated segment window, including arrival grace."""
    return -ARRIVED_GRACE_S < eta_s < span_s


def progress_from_eta(eta_s: float, span_s: float) -> float:
    if span_s <= 0:
        return 1.0
    if eta_s >= span_s:
        return 0.0
    if eta_s <= 0:
        return 1.0
    return 1.0 - (eta_s / span_s)


def advance(
    positions: list[TrainPosition], elapsed_s: float, spans: dict | None = None
) -> list[TrainPosition]:
    """Age NTAS estimates without mutating snapshots; leave schedule positions unchanged."""
    elapsed_s = max(elapsed_s, 0.0)
    advanced = []

    for position in positions:
        if position.eta_s is None:
            advanced.append(position)
            continue

        remaining = position.eta_s - elapsed_s
        span = (
            spans.get((position.from_station, position.to_station), 120.0)
            if spans is not None
            else span_for(position.from_station, position.to_station)
        )

        # Expire arrivals even when a progress floor is set.
        if remaining <= -ARRIVED_GRACE_S:
            continue

        # Exclude earlier segments unless a revised ETA would remove an existing sighting.
        if not is_on_segment(remaining, span) and position.progress_floor <= 0.0:
            continue

        progress = progress_from_eta(remaining, span)
        # A revised ETA must not move a matching sighting backward.
        progress = min(max(progress, position.progress_floor), 1.0)

        advanced.append(replace(position, progress=progress, eta_s=max(remaining, 0.0)))

    return advanced


# Allow whole-minute ETA rounding before treating a queue slot as reassigned.
REASSIGN_SLACK_S = 90.0


def carry_floor(
    positions: list[TrainPosition],
    previous: list[TrainPosition],
    elapsed_s: float,
    spans: dict | None = None,
) -> list[TrainPosition]:
    """Prevent backward jumps between matching queue slots.

    Reset the floor when the ETA jump suggests a different train. Carry only
    the floor, so observations missing from the next poll disappear.
    """
    if not previous:
        return positions

    projected: dict[str, tuple[float, float]] = {}
    for position in previous:
        if position.key is None or position.eta_s is None:
            continue
        remaining = position.eta_s - elapsed_s
        span = (
            spans.get((position.from_station, position.to_station), 120.0)
            if spans is not None
            else span_for(position.from_station, position.to_station)
        )
        projected[position.key] = (remaining, progress_from_eta(remaining, span))

    seeded = []
    for position in positions:
        match = projected.get(position.key or "")
        if match is None or position.eta_s is None:
            seeded.append(position)
            continue

        remaining, floor = match
        if position.eta_s > remaining + REASSIGN_SLACK_S:
            seeded.append(position)
            continue

        seeded.append(replace(position, progress_floor=min(max(floor, 0.0), 1.0)))

    return seeded
