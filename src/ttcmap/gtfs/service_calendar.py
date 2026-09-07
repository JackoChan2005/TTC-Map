"""Shared dated service selection for positions and departure search."""

from ttcmap.db import Dataset, DatasetUnavailable
from ttcmap.map.toronto_time import WEEKDAY_COLUMNS, ServiceWindow


def active_services(dataset: Dataset, window: ServiceWindow) -> set[str]:
    if window.day not in WEEKDAY_COLUMNS:
        raise ValueError("Invalid weekday")
    conn, date = dataset.conn, window.date
    base = {
        r[0]
        for r in conn.execute(
            f"SELECT service_id FROM SERVICE_DAYS WHERE {window.day}=1 "
            "AND start_date<=? AND end_date>=?",
            (date, date),
        )
    }
    for row in conn.execute(
        "SELECT service_id,exception_type FROM SERVICE_EXCEPTIONS WHERE date=?", (date,)
    ):
        if row[1] == 1:
            base.add(row[0])
        else:
            base.discard(row[0])
    return base


def schedule_valid(dataset: Dataset, date: str, line: str) -> bool:
    # Only calendars actually used by this rail line establish its coverage.
    return bool(
        dataset.conn.execute(
            "SELECT 1 FROM SERVICE_DAYS c WHERE start_date<=? AND end_date>=? "
            "AND EXISTS (SELECT 1 FROM SUBWAY_STOP_TIMES s WHERE s.service_id=c.service_id "
            "AND s.line_id=?) UNION ALL "
            "SELECT 1 FROM SERVICE_EXCEPTIONS c WHERE date=? AND exception_type=1 "
            "AND EXISTS (SELECT 1 FROM SUBWAY_STOP_TIMES s WHERE s.service_id=c.service_id "
            "AND s.line_id=?) LIMIT 1",
            (date, date, line, date, line),
        ).fetchone()
    )


def require_schedule(
    dataset: Dataset,
    date: str,
    previous: ServiceWindow | None = None,
    lines: set[str] | None = None,
) -> None:
    required = lines if lines is not None else {line["id"] for line in dataset.network["lines"]}
    previous_services = active_services(dataset, previous) if previous is not None else set()
    for line in sorted(required):
        if schedule_valid(dataset, date, line):
            continue
        # The final service day's own >24:00 trips remain available on that line.
        if (
            previous_services
            and dataset.conn.execute(
                "SELECT 1 FROM SUBWAY_STOP_TIMES WHERE line_id=? AND service_id IN ("
                + ",".join("?" for _ in previous_services)
                + ") AND departing_time_sec>=? LIMIT 1",
                (line, *sorted(previous_services), previous.sec),
            ).fetchone()
        ):
            continue
        raise DatasetUnavailable(
            f"{line}: schedule unavailable for service date {date}; refresh GTFS"
        )
