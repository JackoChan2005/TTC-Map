"""Departure search for the web frontend.

Replaces node-api's /api/route-search and the Python /departing/{time_str}, which
answered the same question with two different implementations of Toronto service
time. Both now go through ttcmap.map.toronto_time.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ttcmap.db import query
from ttcmap.map.toronto_time import WEEKDAY_COLUMNS, get_toronto_parts

router = APIRouter()

DEPARTURE_WINDOW_SECONDS = 120
MAX_ROWS = 200

_SQL = """
    SELECT
        sst.trip_id, sst.stop_sequence, sst.route_id, sst.service_id,
        sst.direction_id, sst.stop_id, sst.stop_name,
        sst.arrival_time, sst.departure_time, sst.departing_time_sec
    FROM SUBWAY_STOP_TIMES sst
    JOIN SERVICE_DAYS sd ON sd.service_id = sst.service_id
    WHERE sd.{day} = 1
      AND CAST(sst.route_id AS TEXT) = ?
      AND sst.departing_time_sec BETWEEN ? AND ?
    ORDER BY sst.departure_time
    LIMIT ?
"""


def normalize_route(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned.isdigit():
        return str(int(cleaned))
    return cleaned


@router.get("/departures")
def get_departures(route: str, at: str | None = None) -> dict:
    requested_route = normalize_route(route)
    if not requested_route:
        raise HTTPException(400, 'Query parameter "route" is required')

    if at:
        try:
            moment = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(400, 'Query parameter "at" must be a valid date/time') from error
    else:
        moment = datetime.now(UTC)

    window = get_toronto_parts(moment)
    if window.day not in WEEKDAY_COLUMNS:
        raise HTTPException(400, 'Query parameter "at" must be a valid date/time')

    rows = query(
        _SQL.format(day=window.day),
        (requested_route, window.sec, window.sec + DEPARTURE_WINDOW_SECONDS, MAX_ROWS),
    )

    if not rows:
        raise HTTPException(
            404,
            f"No trains for route {requested_route} in the next 2 minutes",
        )

    matches = [
        {
            "sourceKey": f"{row['trip_id']}-{row['stop_sequence']}",
            "recordTime": row["departure_time"],
            "updatedAt": None,
            "deltaSeconds": row["departing_time_sec"] - window.sec,
            "payload": row,
        }
        for row in rows
    ]

    return {
        "route": requested_route,
        "requestedAt": moment.isoformat(),
        "serviceDay": window.day,
        "totalMatches": len(matches),
        "bestMatch": matches[0],
        "matches": matches,
    }
