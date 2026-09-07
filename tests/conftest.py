"""Small independent five-line GTFS fixture; no network or production database."""

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from ttcmap.config import get_settings
from ttcmap.gtfs.build import prepare_dataset, publish_dataset
from ttcmap.map import recorder, segments


@pytest.fixture
def rail_feed(tmp_path, monkeypatch):
    settings = get_settings()
    shared, data = tmp_path / "shared", tmp_path / "data"
    (shared / "layouts").mkdir(parents=True)
    data.mkdir()
    monkeypatch.setattr(settings, "shared_dir", shared)
    monkeypatch.setattr(settings, "db_path", data / "ttc.db")
    monkeypatch.setattr(settings, "data_dir", data)
    registry, stops, trips, times, routes = {}, [], [], [], []
    for line in ("1", "2", "4", "5", "6"):
        routes.append(
            dict(
                route_id="raw-" + line,
                route_short_name=line,
                route_long_name="Line " + line,
                route_type="0" if line in "56" else "1",
                route_color="FF8000",
                route_text_color="FFFFFF",
            )
        )
        for station in "abc":
            sid = f"s-{line}-{station}"
            registry[sid] = {"name": sid, "gtfsParents": [sid], "aliases": []}
            stops.append(
                dict(
                    stop_id=sid,
                    stop_code="",
                    stop_name=sid,
                    parent_station="",
                    stop_lat="43.7",
                    stop_lon=str(-79.5 + len(stops) * 0.001),
                )
            )
        for direction in (0, 1):
            tid = f"t-{line}-{direction}"
            trips.append(
                dict(
                    trip_id=tid,
                    route_id="raw-" + line,
                    service_id="W",
                    direction_id=str(direction),
                    trip_short_name="",
                )
            )
            for i, station in enumerate("abc" if direction == 0 else "cba"):
                pid, sid = f"p-{line}-{direction}-{station}", f"s-{line}-{station}"
                stops.append(
                    dict(
                        stop_id=pid,
                        stop_code=pid,
                        stop_name=sid + " Station - Subway Platform",
                        parent_station=sid,
                        stop_lat="43.7",
                        stop_lon="-79.4",
                    )
                )
                times.append(
                    dict(
                        trip_id=tid,
                        stop_id=pid,
                        stop_sequence=str((i + 1) * 10),
                        arrival_time=f"12:0{i * 2}:00",
                        departure_time=f"12:0{i * 2}:00",
                    )
                )
    routes.append(
        dict(
            route_id="501",
            route_short_name="501",
            route_type="0",
            route_long_name="Queen",
            route_color="FF0000",
            route_text_color="FFFFFF",
        )
    )
    calendar = dict(
        service_id="W",
        start_date="20260101",
        end_date="20261231",
        **{
            d: "1"
            for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        },
    )
    frames = {
        "routes": pd.DataFrame(routes),
        "trips": pd.DataFrame(trips),
        "stops": pd.DataFrame(stops),
        "stop_times": pd.DataFrame(times),
        "calendar": pd.DataFrame([calendar]),
        "calendar_dates": pd.DataFrame(columns=["service_id", "date", "exception_type"]),
    }
    (shared / "stations.json").write_text(json.dumps(registry))
    layout = {
        "name": "schematic",
        "width": 1000,
        "height": 500,
        "stations": {sid: {"x": i * 30, "y": i % 3 * 30} for i, sid in enumerate(registry)},
    }
    (shared / "layouts/schematic.json").write_text(json.dumps(layout))

    def prepare():
        return prepare_dataset(Path("unused"), frames=frames)

    def publish():
        tables, artifact = prepare()
        publish_dataset(tables, artifact, "fixture-version")
        return artifact

    recorder.set_snapshot(None)
    segments.clear_cache()
    yield SimpleNamespace(
        frames=frames,
        registry=registry,
        prepare=prepare,
        publish=publish,
        data=data,
        shared=shared,
        settings=settings,
    )
    recorder.set_snapshot(None)
    segments.clear_cache()
