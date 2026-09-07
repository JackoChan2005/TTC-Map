"""Validate rail GTFS and publish one complete SQLite dataset."""

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from ttcmap.config import get_settings
from ttcmap.db import connect
from ttcmap.gtfs.rail_routes import select_rail_routes

IMPORTER_REVISION = "rail-5-lines-v1"
GTFS_FILES = {n: f"{n}.txt" for n in ("routes", "trips", "stops", "calendar")}
EXCEPTION_COLUMNS = ["service_id", "date", "exception_type"]


def gtfs_time_to_seconds(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"Invalid GTFS time: {value}")
    return hours * 3600 + minutes * 60 + seconds


def read_gtfs(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {
        name: pd.read_csv(data_dir / filename, dtype=str, keep_default_na=False)
        for name, filename in GTFS_FILES.items()
    }
    routes = select_rail_routes(frames["routes"])
    frames["trips"] = frames["trips"][frames["trips"]["route_id"].isin(routes["route_id"])]
    trip_ids = set(frames["trips"]["trip_id"])
    chunks = pd.read_csv(
        data_dir / "stop_times.txt", dtype=str, keep_default_na=False, chunksize=200_000
    )
    frames["stop_times"] = pd.concat(
        [chunk[chunk["trip_id"].isin(trip_ids)] for chunk in chunks], ignore_index=True
    )
    path = data_dir / "calendar_dates.txt"
    frames["calendar_dates"] = (
        pd.read_csv(path, dtype=str, keep_default_na=False)
        if path.exists()
        else pd.DataFrame(columns=EXCEPTION_COLUMNS)
    )
    return frames


def validate_calendars(frames: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    calendar = frames["calendar"].copy()
    exceptions = frames["calendar_dates"][EXCEPTION_COLUMNS].copy()
    if calendar["service_id"].duplicated().any():
        raise ValueError("Duplicate calendar service")
    if exceptions.duplicated(["service_id", "date"]).any():
        raise ValueError("Duplicate service exception")
    for col in ("start_date", "end_date"):
        pd.to_datetime(calendar[col], format="%Y%m%d", errors="raise")
    pd.to_datetime(exceptions["date"], format="%Y%m%d", errors="raise")
    if (calendar["start_date"] > calendar["end_date"]).any():
        raise ValueError("Reversed calendar dates")
    for col in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        if not calendar[col].isin(["0", "1"]).all():
            raise ValueError(f"Invalid weekday flag: {col}")
        calendar[col] = calendar[col].astype(int)
    if not exceptions["exception_type"].isin(["1", "2"]).all():
        raise ValueError("Invalid service exception type")
    exceptions["exception_type"] = exceptions["exception_type"].astype(int)
    known = set(calendar["service_id"]) | set(exceptions["service_id"])
    if not set(frames["trips"]["service_id"]) <= known:
        raise ValueError("Trip references unknown service")
    return calendar.sort_values("service_id"), exceptions.sort_values(["service_id", "date"])


def build_stop_times(frames: dict) -> pd.DataFrame:
    routes = select_rail_routes(frames["routes"])
    trips = frames["trips"].merge(routes[["route_id", "line_id"]], on="route_id")
    if trips["trip_id"].duplicated().any():
        raise ValueError("Duplicate trip ID")
    if not trips["direction_id"].isin(["0", "1"]).all():
        raise ValueError("Invalid rail direction")
    rows = frames["stop_times"].merge(
        trips[["trip_id", "route_id", "line_id", "service_id", "direction_id"]],
        on="trip_id",
        validate="many_to_one",
    )
    if set(trips["trip_id"]) != set(rows["trip_id"]):
        raise ValueError("Rail trip has no stop times")
    if not set(rows["stop_id"]) <= set(frames["stops"]["stop_id"]):
        raise ValueError("Unknown rail stop")
    rows = rows.merge(
        frames["stops"][["stop_id", "stop_code", "stop_name"]],
        on="stop_id",
        validate="many_to_one",
    )
    sequence = pd.to_numeric(rows["stop_sequence"], errors="raise")
    if ((sequence % 1 != 0) | (sequence < 0)).any():
        raise ValueError("Invalid stop sequence")
    rows["stop_sequence"] = sequence.astype(int)
    if rows.duplicated(["trip_id", "stop_sequence"]).any():
        raise ValueError("Duplicate trip/stop sequence")
    rows["direction_id"] = rows["direction_id"].astype(int)
    rows["departing_time_sec"] = rows["departure_time"].map(gtfs_time_to_seconds)
    rows["arrival_time"].map(gtfs_time_to_seconds)
    rows = rows.sort_values(["trip_id", "stop_sequence"]).reset_index(drop=True)
    grouped = rows.groupby("trip_id", sort=False)
    rows["next_stop_id"] = grouped["stop_id"].shift(-1)
    rows["next_departing_time_sec"] = grouped["departing_time_sec"].shift(-1).astype("Int64")
    spans = rows["next_departing_time_sec"] - rows["departing_time_sec"]
    if (spans.dropna() <= 0).any():
        raise ValueError("Rail departures must increase along a trip")
    columns = [
        "trip_id",
        "route_id",
        "line_id",
        "service_id",
        "direction_id",
        "stop_id",
        "stop_code",
        "stop_name",
        "stop_sequence",
        "arrival_time",
        "departure_time",
        "departing_time_sec",
        "next_stop_id",
        "next_departing_time_sec",
    ]
    return rows[columns]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_digest() -> str:
    shared = get_settings().shared_path
    digest = hashlib.sha256(IMPORTER_REVISION.encode())
    for path in (shared / "stations.json", shared / "layouts/schematic.json"):
        digest.update(canonical_json(json.loads(path.read_text(encoding="utf-8"))).encode())
    return digest.hexdigest()


def prepare_dataset(data_dir: Path, *, frames: dict | None = None) -> tuple[dict, dict]:
    from ttcmap.gtfs.network import build_geographic_layout, build_network

    frames = frames if frames is not None else read_gtfs(data_dir)
    calendar, exceptions = validate_calendars(frames)
    rows = build_stop_times(frames)
    network = build_network(data_dir, frames=frames)
    geographic = build_geographic_layout(network)
    shared = get_settings().shared_path
    schematic = json.loads((shared / "layouts/schematic.json").read_text(encoding="utf-8"))
    missing = set(network["stations"]) - set(schematic["stations"])
    if missing:
        raise ValueError(f"Schematic missing stations {sorted(missing)}; regenerate layout")
    for point in schematic["stations"].values():
        if not all(
            isinstance(point.get(k), (int, float)) and math.isfinite(point[k]) for k in ("x", "y")
        ):
            raise ValueError("Invalid schematic coordinates")
    tables = {"SUBWAY_STOP_TIMES": rows, "SERVICE_DAYS": calendar, "SERVICE_EXCEPTIONS": exceptions}
    artifact = {"network": network, "layouts": {"geographic": geographic, "schematic": schematic}}
    artifact["inputsDigest"] = input_digest()
    digest = hashlib.sha256()
    digest.update(IMPORTER_REVISION.encode())
    digest.update(canonical_json(artifact).encode())
    digest.update(canonical_json(json.loads((shared / "stations.json").read_text())).encode())
    for name, frame in sorted(tables.items()):
        digest.update(name.encode())
        digest.update(canonical_json(json.loads(frame.to_json(orient="records"))).encode())
    artifact["generation"] = digest.hexdigest()
    return tables, artifact


def publish_dataset(tables: dict, artifact: dict, version: str | None) -> int:
    """Staging is disposable; only the final transaction changes active data."""
    get_settings().database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        for name, frame in tables.items():
            frame.to_sql(name + "__staging", conn, if_exists="replace", index=False)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for name in tables:
                conn.execute(f"DROP TABLE IF EXISTS {name}")
                conn.execute(f"ALTER TABLE {name}__staging RENAME TO {name}")
            conn.execute(
                "CREATE INDEX idx_sst_line_time ON SUBWAY_STOP_TIMES(line_id, departing_time_sec)"
            )
            conn.execute("CREATE INDEX idx_sst_trip ON SUBWAY_STOP_TIMES(trip_id, stop_sequence)")
            conn.execute("CREATE INDEX idx_sst_service ON SUBWAY_STOP_TIMES(service_id)")
            conn.execute("CREATE UNIQUE INDEX idx_exception ON SERVICE_EXCEPTIONS(service_id,date)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS active_dataset "
                "(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, "
                "version TEXT, revision TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO active_dataset VALUES (1,?,?,?)",
                (canonical_json(artifact), version, IMPORTER_REVISION),
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta VALUES ('gtfs_last_modified', ?)",
                (version or "unknown",),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return len(tables["SUBWAY_STOP_TIMES"])


def build(data_dir: Path | None = None) -> int:
    from ttcmap.gtfs.refresh_lock import refresh_lock

    with refresh_lock():
        tables, artifact = prepare_dataset(data_dir or get_settings().data_path / "gtfs")
        return publish_dataset(tables, artifact, None)
