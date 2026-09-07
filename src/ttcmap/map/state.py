"""The map state engine — pure, no database or HTTP.

Ported from node-api/src/map/stateEngine.js. Sources are injected by the caller,
which is what lets the schedule simulation, the NTAS feed and a recorded snapshot
be swapped without the engine or any renderer knowing.

  TrainPosition: line, direction, from, to, progress, trip_id
                 from/to are station ids; to=None means the train is at `from`.
  MapState:      generatedAt, source, trainCount, trains[], stationsWithTrains

JSON keys stay camelCase because the web frontend reads them directly.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

AT_STATION_THRESHOLD = 0.2


@dataclass(frozen=True)
class TrainPosition:
    line: str
    direction: int
    from_station: str
    to_station: str | None = None
    progress: float = 0.0
    trip_id: str | None = None

    # NTAS reports a countdown to the destination, not a position, so realtime
    # positions carry the ETA and have `progress` filled in later by
    # ttcmap.map.interpolate once the age of the observation is known.
    # Schedule positions compute `progress` directly and leave this None.
    eta_s: float | None = None
    # Lower bound carried across polls so a revised ETA cannot run a train
    # backwards down the line. See interpolate.carry_floor.
    progress_floor: float = 0.0
    # Stable identity for one sighting: line|direction|station|nth-arrival.
    # NTAS has no train ids, so this is only good for matching consecutive
    # polls of the same queue position, which is all the floor needs.
    key: str | None = None


@dataclass
class MapState:
    generatedAt: str
    source: str
    trainCount: int
    trains: list[dict[str, Any]]
    stationsWithTrains: dict[str, int]
    fallback: bool = False
    generation: str | None = None
    lineSources: dict = field(default_factory=dict)
    _extra: dict = field(default_factory=dict, repr=False)

    def as_dict(self) -> dict:
        payload = {
            "generatedAt": self.generatedAt,
            "source": self.source,
            "trainCount": self.trainCount,
            "trains": self.trains,
            "stationsWithTrains": self.stationsWithTrains,
        }
        payload["generation"] = self.generation
        payload["lineSources"] = self.lineSources
        if self.fallback:
            payload["fallback"] = True
        return payload


def compute_map_state(
    topology: dict,
    positions: list[TrainPosition],
    source: str = "unknown",
    generated_at: str | None = None,
) -> MapState:
    trains: list[dict[str, Any]] = []
    stations_with_trains: dict[str, int] = {}

    for pos in positions:
        if pos.from_station not in topology["stations"]:
            continue

        has_segment = (
            pos.to_station is not None
            and pos.to_station in topology["stations"]
            and pos.to_station != pos.from_station
        )
        progress = min(max(pos.progress or 0.0, 0.0), 1.0) if has_segment else 0.0

        at: str | None = None
        between: list[str] | None = None
        if not has_segment or progress <= AT_STATION_THRESHOLD:
            at = pos.from_station
        elif progress >= 1 - AT_STATION_THRESHOLD:
            at = pos.to_station
        else:
            between = [pos.from_station, pos.to_station]

        nearest = at if at is not None else (pos.from_station if progress < 0.5 else pos.to_station)
        stations_with_trains[nearest] = stations_with_trains.get(nearest, 0) + 1

        trains.append(
            {
                "line": pos.line,
                "direction": pos.direction,
                "tripId": pos.trip_id,
                "at": at,
                "between": between,
                "progress": progress,
                "nearestStation": nearest,
                "stationName": topology["stations"][nearest]["name"],
            }
        )

    return MapState(
        generatedAt=generated_at or datetime.now(UTC).isoformat(),
        source=source,
        trainCount=len(trains),
        trains=trains,
        stationsWithTrains=stations_with_trains,
    )
