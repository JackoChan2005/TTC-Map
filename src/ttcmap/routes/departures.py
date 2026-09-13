"""Scheduled departures using Toronto service dates."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException

from ttcmap.db import DatasetUnavailable, read_dataset
from ttcmap.gtfs.service_calendar import active_services, require_schedule
from ttcmap.map.toronto_time import TORONTO_TZ, get_service_windows, get_toronto_parts

router = APIRouter()

DEPARTURE_WINDOW_SECONDS = 120
MAX_ROWS = 200


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

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TORONTO_TZ)
    window = get_toronto_parts(moment)
    windows = get_service_windows(moment)
    end_window = get_toronto_parts(moment + timedelta(seconds=DEPARTURE_WINDOW_SECONDS))
    if end_window.date != window.date:
        from dataclasses import replace

        windows.append(replace(end_window, sec=window.sec - 86400))
    rows = []
    try:
        with read_dataset() as dataset:
            require_schedule(dataset, window.date, windows[1], {"line-" + requested_route})
            require_schedule(
                dataset,
                end_window.date,
                get_service_windows(moment + timedelta(seconds=DEPARTURE_WINDOW_SECONDS))[1],
                {"line-" + requested_route},
            )
            for service_window in windows:
                services = active_services(dataset, service_window)
                if not services:
                    continue
                matches = dataset.conn.execute(
                    "SELECT * FROM SUBWAY_STOP_TIMES WHERE line_id=? AND service_id IN ("
                    + ",".join("?" for _ in services)
                    + ") AND departing_time_sec BETWEEN ? AND ? "
                    "ORDER BY departing_time_sec LIMIT ?",
                    (
                        "line-" + requested_route,
                        *sorted(services),
                        service_window.sec,
                        service_window.sec + DEPARTURE_WINDOW_SECONDS,
                        MAX_ROWS,
                    ),
                )
                for row in matches:
                    row = dict(row)
                    row["service_date"] = service_window.date
                    row["delta"] = row["departing_time_sec"] - service_window.sec
                    rows.append(row)
    except DatasetUnavailable as error:
        raise HTTPException(503, str(error)) from error
    rows.sort(key=lambda row: (row["delta"], row["trip_id"], row["stop_sequence"]))
    rows = rows[:MAX_ROWS]

    if not rows:
        raise HTTPException(
            404,
            f"No trains for route {requested_route} in the next 2 minutes",
        )

    matches = [
        {
            "sourceKey": f"{row['service_date']}:{row['trip_id']}-{row['stop_sequence']}",
            "recordTime": row["departure_time"],
            "updatedAt": None,
            "deltaSeconds": row["delta"],
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
