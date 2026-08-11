"""Schedule-based train positions.

Ported from node-api/src/map/sources/scheduleSource.js. A train is between
consecutive stops A and B when A's departure has passed and B's has not. This is
static GTFS, so it is a simulation of where trains *should* be, not live data —
it is what the map falls back to when the realtime feed is unavailable.
"""

from datetime import UTC, datetime

from ttcmap.db import query
from ttcmap.map.state import TrainPosition
from ttcmap.map.topology import load_topology
from ttcmap.map.toronto_time import WEEKDAY_COLUMNS, get_service_windows

name = "schedule"

# `day` is interpolated into the SQL because a column name cannot be bound as a
# parameter. It is safe only because it comes from WEEKDAY_COLUMNS, never from
# the request — keep that guard if this query is ever edited.
_SQL = """
    SELECT
        a.trip_id           AS tripId,
        a.direction_id      AS direction,
        a.stop_id           AS fromStop,
        b.stop_id           AS toStop,
        a.departing_time_sec AS depSec,
        b.departing_time_sec AS arrSec
    FROM SUBWAY_STOP_TIMES a
    JOIN SUBWAY_STOP_TIMES b
      ON b.trip_id = a.trip_id
     AND b.stop_sequence = a.stop_sequence + 1
    JOIN SERVICE_DAYS sd
      ON sd.service_id = a.service_id
    WHERE sd.{day} = 1
      AND a.departing_time_sec <= ?
      AND b.departing_time_sec > ?
"""


def get_train_positions(now: datetime | None = None) -> list[TrainPosition]:
    now = now or datetime.now(UTC)
    topology = load_topology()
    by_trip: dict[str, TrainPosition] = {}

    for window in get_service_windows(now):
        if window.day not in WEEKDAY_COLUMNS:
            continue

        rows = query(_SQL.format(day=window.day), (window.sec, window.sec))

        for row in rows:
            origin = topology["platforms"].get(str(row["fromStop"]))
            destination = topology["platforms"].get(str(row["toStop"]))
            if not origin or not destination:
                continue

            span = row["arrSec"] - row["depSec"]
            by_trip[row["tripId"]] = TrainPosition(
                line=origin["line"],
                direction=row["direction"],
                trip_id=row["tripId"],
                from_station=origin["station"],
                to_station=destination["station"],
                progress=(window.sec - row["depSec"]) / span if span > 0 else 0.0,
            )

    return list(by_trip.values())
