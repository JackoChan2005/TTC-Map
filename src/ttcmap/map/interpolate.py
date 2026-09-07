"""Turns NTAS countdowns into positions, and keeps them moving between polls.

The recorder polls NTAS every `ntas_poll_s` seconds but the board polls the
server every few seconds, so most frames are served from an observation that is
already several seconds old. Because an NTAS reading is a countdown to a fixed
future event rather than a snapshot of where a train is, ageing it is exact
subtraction — no velocity estimate and no per-train tracking:

    remaining = eta_s - elapsed_since_poll
    progress  = 1 - remaining / span      when remaining < span

Error shrinks as the train nears the station, which is the opposite of dead
reckoning and the reason this is anchored to arrivals rather than integrated
from a previous position.

That `remaining < span` condition is also what keeps each train counted once.
Every platform reports every train heading its way, so a train one minute from B
is simultaneously reported as four minutes from C, five from D, and so on — on
the live feed a five-minute window parses ~195 sightings of ~65 trains. A train
whose ETA exceeds the segment's own traversal time has not reached the origin of
that segment yet, so it is somewhere further back and the platform behind is
already showing it. Dropping those leaves exactly one sighting per train: the
segment it is actually on.

`advance` is pure and does not mutate the snapshot, so the recorder's positions
stay as observed and every request re-derives from them.
"""

from dataclasses import replace

from ttcmap.map.segments import span_for
from ttcmap.map.state import TrainPosition

# How long an arrived train keeps its platform before the next segment's
# sighting takes over. The countdown to the *following* station only drops
# inside that station's span once the train pulls out, so a train needs holding
# across the dwell or it blinks out while stopped.
#
# Measured against the live feed over a full 30s poll cycle: at 15s and 30s the
# train count collapses ~30% mid-cycle as the whole eta=0 cohort expires at once
# (NTAS reports whole minutes, so arrivals bunch), then climbs back. 45s is the
# shortest value that stays monotone, at the cost of holding a few trains ~14%
# longer than they are really there. Prefer the overcount: an LED that lingers
# reads as a train dwelling, one that blinks reads as a bug.
ARRIVED_GRACE_S = 45.0


def is_on_segment(eta_s: float, span_s: float) -> bool:
    """Whether a train this far out has actually entered the segment yet.

    False means the sighting belongs to a segment further back, where the
    platform behind is reporting the same train with a smaller ETA.
    """
    return -ARRIVED_GRACE_S < eta_s < span_s


def progress_from_eta(eta_s: float, span_s: float) -> float:
    """Where a train sits on a segment it will finish in `eta_s` seconds."""
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
    """Age each position by `elapsed_s`, fill in `progress`, drop duplicates.

    Positions without an ETA (the schedule source) already carry a computed
    progress and pass through untouched.
    """
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

        # long arrived: the next segment's sighting has taken this train over,
        # so holding it here would draw it twice. Unconditional — a floor must
        # not pin a train to a platform it has already left.
        if remaining <= -ARRIVED_GRACE_S:
            continue

        # still behind the origin: the platform behind is reporting it. The
        # floor is respected so a train already shown on this segment is not
        # yanked back off it by a revised ETA.
        if not is_on_segment(remaining, span) and position.progress_floor <= 0.0:
            continue

        progress = progress_from_eta(remaining, span)
        # never run backwards: a train the feed has revised later still holds
        # the ground it was last shown to have covered
        progress = min(max(progress, position.progress_floor), 1.0)

        advanced.append(replace(position, progress=progress, eta_s=max(remaining, 0.0)))

    return advanced


# How far a new reading may exceed the projected ETA and still be believed to be
# the same train. NTAS reports whole minutes, so a train can appear to gain up to
# ~60s of ETA purely from rounding; beyond that the queue has shifted underneath
# us and the key now names a different train.
REASSIGN_SLACK_S = 90.0


def carry_floor(
    positions: list[TrainPosition],
    previous: list[TrainPosition],
    elapsed_s: float,
    spans: dict | None = None,
) -> list[TrainPosition]:
    """Seed each new position's floor from where the last poll had that train.

    NTAS reports whole minutes and revises on every poll, so a train held at a
    signal reports "2 minutes" twice in a row and the naive position jumps back
    down the line. Matching on the queue key, the new reading is only allowed to
    move a train forwards.

    The key is a queue slot, not a vehicle: when the nearest train arrives, every
    train behind it shifts down one index, and the slot's floor would pin a train
    that has only just left the previous station up against the platform. A
    reading that is further out than the projection by more than the rounding
    slack is therefore treated as a different train and gets no floor.

    Only the floor is carried, never the position itself, so a train that drops
    out of the feed disappears rather than coasting — a stalled feed must not
    invent movement.
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
            # the queue shifted; this slot holds a train we have not seen before
            seeded.append(position)
            continue

        seeded.append(replace(position, progress_floor=min(max(floor, 0.0), 1.0)))

    return seeded
