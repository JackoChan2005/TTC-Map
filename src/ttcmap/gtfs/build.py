"""Build the subway schedule tables from an extracted GTFS feed.

Ported from API/src/transform.py. Two behavioural changes:

  * The rebuild writes to staging tables and swaps them in under one transaction,
    so readers keep seeing the previous data for the several minutes the pandas
    merge takes instead of querying a half-built table.
  * The DROP TABLE synced_records / sync_runs lines are gone with those tables.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from ttcmap.config import get_settings
from ttcmap.db import connect

log = logging.getLogger(__name__)

GTFS_FILES = {
    "calendar": "calendar.txt",
    "routes": "routes.txt",
    "stop_times": "stop_times.txt",
    "stops": "stops.txt",
    "trips": "trips.txt",
}

SUBWAY_ROUTE_TYPE = 1

INDEXES = [
    ("idx_sst_route_time", "SUBWAY_STOP_TIMES(route_id, departing_time_sec)"),
    ("idx_sst_trip", "SUBWAY_STOP_TIMES(trip_id, stop_sequence)"),
    ("idx_sst_service", "SUBWAY_STOP_TIMES(service_id)"),
]


def gtfs_time_to_seconds(value: str) -> int:
    """GTFS clock times run past 24:00:00 for after-midnight service."""
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def read_gtfs(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for name, filename in GTFS_FILES.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"GTFS file not found: {path}")

        # trip_id mixes numeric and text values in the merged TTC feed, so it
        # must be read as str on both sides of the merge
        kwargs: dict = {}
        if name == "stop_times":
            kwargs = {"dtype": {"trip_id": str, "stop_headsign": str}}
        elif name == "trips":
            kwargs = {"dtype": {"trip_id": str}}

        log.info("Reading %s", path)
        frames[name] = pd.read_csv(path, **kwargs)
    return frames


def build_stop_times(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Subway-only stop_times enriched with route, service, direction and stop name."""
    routes = frames["routes"]
    trips = frames["trips"]
    stops = frames["stops"]
    stop_times = frames["stop_times"]

    subway_routes = routes[routes["route_type"] == SUBWAY_ROUTE_TYPE]
    route_ids = set(subway_routes["route_id"])
    subway_trips = trips[trips["route_id"].isin(route_ids)]

    merged = stop_times.merge(
        subway_trips[["trip_id", "route_id", "service_id", "trip_short_name", "direction_id"]],
        on="trip_id",
    )
    merged = merged.merge(stops[["stop_id", "stop_code", "stop_name"]], on="stop_id")
    merged = merged.sort_values(["trip_id", "stop_sequence"])
    merged["departing_time_sec"] = merged["departure_time"].apply(gtfs_time_to_seconds)

    id_cols = [col for col in merged.columns if "_id" in col]
    other_cols = [col for col in merged.columns if "_id" not in col]
    return merged[id_cols + other_cols]


def _swap_in(conn: sqlite3.Connection, live: str, staging: str) -> None:
    conn.execute(f"DROP TABLE IF EXISTS {live}")
    conn.execute(f"ALTER TABLE {staging} RENAME TO {live}")


def write_tables(stop_times: pd.DataFrame, calendar: pd.DataFrame) -> int:
    """Write both tables via staging, then swap them in atomically."""
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        log.info("Writing %d stop times to staging tables", len(stop_times))
        conn.execute("DROP TABLE IF EXISTS SUBWAY_STOP_TIMES__staging")
        conn.execute("DROP TABLE IF EXISTS SERVICE_DAYS__staging")
        calendar.to_sql("SERVICE_DAYS__staging", conn, if_exists="replace", index=False)
        stop_times.to_sql("SUBWAY_STOP_TIMES__staging", conn, if_exists="replace", index=False)

        # SQLite DDL is transactional: under WAL, readers keep seeing the old
        # tables until this commit lands.
        conn.execute("BEGIN IMMEDIATE")
        for index_name, _ in INDEXES:
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        _swap_in(conn, "SUBWAY_STOP_TIMES", "SUBWAY_STOP_TIMES__staging")
        _swap_in(conn, "SERVICE_DAYS", "SERVICE_DAYS__staging")
        for index_name, target in INDEXES:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {target}")
        conn.commit()

    log.info("Swapped in %d stop times, %d service days", len(stop_times), len(calendar))
    return len(stop_times)


def build(data_dir: Path | None = None) -> int:
    """Read the extracted feed and rebuild the schedule tables. Returns row count."""
    data_dir = data_dir or (get_settings().data_path / "gtfs")
    frames = read_gtfs(data_dir)
    stop_times = build_stop_times(frames)
    return write_tables(stop_times, frames["calendar"])
