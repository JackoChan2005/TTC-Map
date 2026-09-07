from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ttcmap.db import DatasetUnavailable, read_dataset
from ttcmap.gtfs.service_calendar import active_services
from ttcmap.map.sources.schedule import get_train_positions
from ttcmap.map.toronto_time import get_service_windows, get_toronto_parts
from ttcmap.routes.departures import router

NOW = datetime(2026, 9, 7, 16, 1, tzinfo=UTC)


def test_nonconsecutive_sequence_produces_positions_for_all_five_lines(rail_feed):
    rail_feed.publish()
    positions = get_train_positions(NOW)
    assert len(positions) == 10
    assert {p.line for p in positions} == {"line-1", "line-2", "line-4", "line-5", "line-6"}
    assert all(p.progress == 0.5 for p in positions)


def test_holiday_removal_and_exception_only_addition(rail_feed):
    frames = rail_feed.frames
    frames["trips"].loc[0, "service_id"] = "H"
    frames["calendar_dates"] = pd.DataFrame(
        [["W", "20260907", "2"], ["H", "20260907", "1"]],
        columns=["service_id", "date", "exception_type"],
    )
    rail_feed.publish()
    with read_dataset() as dataset:
        assert active_services(dataset, get_toronto_parts(NOW)) == {"H"}
    positions = get_train_positions(NOW)
    assert len(positions) == 1 and positions[0].line == "line-1"


def test_expired_calendar_fails_instead_of_silent_empty_positions(rail_feed):
    rail_feed.publish()
    with pytest.raises(DatasetUnavailable, match="service date"):
        get_train_positions(datetime(2027, 1, 2, 17, tzinfo=UTC))


def test_valid_no_service_returns_no_trains(rail_feed):
    rail_feed.publish()
    assert get_train_positions(datetime(2026, 9, 7, 20, tzinfo=UTC)) == []


def test_departure_search_crosses_midnight_and_preserves_raw_route_id(rail_feed):
    times = rail_feed.frames["stop_times"]
    times.loc[times.trip_id == "t-5-0", "departure_time"] = ["23:59:00", "24:00:00", "24:02:00"]
    times.loc[times.trip_id == "t-6-0", "departure_time"] = ["00:00:00", "00:02:00", "00:04:00"]
    rail_feed.publish()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    for route in ("5", "6"):
        r = client.get("/departures", params={"route": route, "at": "2026-09-07T23:59:30-04:00"})
        assert r.status_code == 200, r.text
        assert r.json()["bestMatch"]["deltaSeconds"] == 30
        assert r.json()["bestMatch"]["payload"]["route_id"] == "raw-" + route


def test_previous_toronto_date_across_dst_transition():
    # UTC minus 24h can still be the same Toronto date near the autumn transition.
    windows = get_service_windows(datetime(2026, 11, 2, 4, 30, tzinfo=UTC))
    assert [w.date for w in windows] == ["20261101", "20261031"]


def test_last_service_day_trips_continue_after_calendar_end(rail_feed):
    frames = rail_feed.frames
    frames["calendar"]["end_date"] = "20260906"
    mask = frames["stop_times"].trip_id == "t-5-0"
    frames["stop_times"].loc[mask, "departure_time"] = ["24:00:00", "24:02:00", "24:04:00"]
    rail_feed.publish()
    positions = get_train_positions(datetime(2026, 9, 7, 4, 1, tzinfo=UTC), lines={"line-5"})
    assert len(positions) == 1 and positions[0].line == "line-5"


def test_other_lines_cannot_mask_expired_line5_schedule(rail_feed):
    frames = rail_feed.frames
    old = frames["calendar"].iloc[0].copy()
    old.service_id, old.end_date = "expired", "20260905"
    frames["calendar"] = pd.concat([frames["calendar"], old.to_frame().T], ignore_index=True)
    frames["trips"].loc[frames["trips"].route_id == "raw-5", "service_id"] = "expired"
    rail_feed.publish()
    with pytest.raises(DatasetUnavailable, match="line-5"):
        get_train_positions(NOW, lines={"line-5"})
    assert get_train_positions(NOW, lines={"line-6"})
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert (
        client.get("/departures", params={"route": "6", "at": NOW.isoformat()}).status_code == 200
    )
    assert (
        client.get("/departures", params={"route": "5", "at": NOW.isoformat()}).status_code == 503
    )


def test_calendar_helper_imports_without_map_package_initialization():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "from ttcmap.gtfs.service_calendar import active_services"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
