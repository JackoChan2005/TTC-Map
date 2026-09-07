"""Scheduled estimates, using one published dataset and Toronto service dates."""

from datetime import UTC, datetime

from ttcmap.db import Dataset, read_dataset
from ttcmap.gtfs.service_calendar import active_services, require_schedule
from ttcmap.map.state import TrainPosition
from ttcmap.map.toronto_time import get_service_windows


def _rows(dataset: Dataset, now: datetime, lines: set[str]):
    windows = get_service_windows(now)
    require_schedule(dataset, windows[0].date, windows[1], lines)
    for window in windows:
        services = active_services(dataset, window)
        if not services or not lines:
            continue
        params = (*sorted(services), *sorted(lines), window.sec, window.sec)
        rows = dataset.conn.execute(
            "SELECT * FROM SUBWAY_STOP_TIMES WHERE service_id IN ("
            + ",".join("?" for _ in services)
            + ") AND line_id IN ("
            + ",".join("?" for _ in lines)
            + ") AND departing_time_sec<=? AND next_departing_time_sec>?",
            params,
        )
        yield window, rows


def operating_lines(dataset: Dataset, now: datetime, lines: set[str] | None = None) -> set[str]:
    windows = get_service_windows(now)
    require_schedule(dataset, windows[0].date, windows[1], lines)
    result = set()
    for window in windows:
        services = active_services(dataset, window)
        if not services:
            continue
        rows = dataset.conn.execute(
            "SELECT line_id FROM SUBWAY_STOP_TIMES WHERE service_id IN ("
            + ",".join("?" for _ in services)
            + ") GROUP BY line_id,trip_id HAVING MIN(departing_time_sec)<=? "
            "AND MAX(departing_time_sec)>=?",
            (*sorted(services), window.sec, window.sec),
        )
        result.update(row[0] for row in rows)
    return result if lines is None else result & lines


def get_train_positions(
    now: datetime | None = None, *, dataset: Dataset | None = None, lines: set[str] | None = None
) -> list[TrainPosition]:
    now = now or datetime.now(UTC)
    if dataset is None:
        with read_dataset() as current:
            return get_train_positions(now, dataset=current, lines=lines)
    if lines is None:
        lines = {line["id"] for line in dataset.network["lines"]}
    platforms = dataset.network["platforms"]
    positions = []
    for window, rows in _rows(dataset, now, lines):
        for row in rows:
            a, b = platforms[row["stop_id"]], platforms[row["next_stop_id"]]
            span = row["next_departing_time_sec"] - row["departing_time_sec"]
            positions.append(
                TrainPosition(
                    line=row["line_id"],
                    direction=row["direction_id"],
                    trip_id=f"{window.date}:{row['trip_id']}",
                    from_station=a["station"],
                    to_station=b["station"],
                    progress=(window.sec - row["departing_time_sec"]) / span,
                )
            )
    return positions
