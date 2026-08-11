"""Integration tests for the database-to-ESP32 LED-frame pipeline.

These tests stop at the hardware boundary: the exact bytes returned by the
firmware endpoint.  The ESP32 firmware does not have an HTTP/74HC595 consumer
yet, so exercising physical GPIO requires that production code to exist first.
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ttcmap.map as map_engine
from ttcmap.config import get_settings
from ttcmap.map import recorder
from ttcmap.map.recorder import Snapshot
from ttcmap.map.state import TrainPosition
from ttcmap.map.topology import clear_cache
from ttcmap.routes import map as map_routes


NOW = datetime(2026, 8, 5, 16, 0, tzinfo=UTC)  # Wednesday, noon in Toronto


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is not None else NOW.replace(tzinfo=None)


@pytest.fixture()
def pipeline(tmp_path, monkeypatch):
    """Build the smallest real GTFS DB/topology/board needed by the API."""
    settings = get_settings()
    data_dir = tmp_path / "data"
    shared_dir = tmp_path / "shared"
    led_maps_dir = tmp_path / "hardware" / "led-maps"
    data_dir.mkdir()
    shared_dir.mkdir()
    led_maps_dir.mkdir(parents=True)

    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(settings, "db_path", data_dir / "ttc.db")
    monkeypatch.setattr(settings, "shared_dir", shared_dir)
    monkeypatch.setattr(settings, "led_maps_dir", led_maps_dir)
    monkeypatch.setattr(map_engine, "datetime", FrozenDateTime)

    topology = {
        "lines": [{"id": "line-1", "stations": ["99992", "99969"]}],
        "stations": {
            "99992": {"name": "Finch"},
            "99969": {"name": "Union"},
        },
        "platforms": {
            "finch-platform": {
                "station": "99992",
                "line": "line-1",
                "direction": 0,
            },
            "union-platform": {
                "station": "99969",
                "line": "line-1",
                "direction": 0,
            },
        },
    }
    (shared_dir / "network.json").write_text(json.dumps(topology))

    led_map = {
        "name": "rev-a",
        "ledCount": 8,
        "leds": [
            {"index": 0, "designator": "D1", "station": "99992", "stationName": "Finch"},
            {"index": 3, "designator": "D4", "station": "99969", "stationName": "Union"},
        ],
    }
    (led_maps_dir / "rev-a.json").write_text(json.dumps(led_map))

    with sqlite3.connect(settings.database_path) as conn:
        conn.executescript(
            """
            CREATE TABLE SUBWAY_STOP_TIMES (
                trip_id TEXT NOT NULL,
                stop_sequence INTEGER NOT NULL,
                service_id TEXT NOT NULL,
                direction_id INTEGER NOT NULL,
                stop_id TEXT NOT NULL,
                departing_time_sec INTEGER NOT NULL
            );
            CREATE TABLE SERVICE_DAYS (
                service_id TEXT PRIMARY KEY,
                monday INTEGER NOT NULL,
                tuesday INTEGER NOT NULL,
                wednesday INTEGER NOT NULL,
                thursday INTEGER NOT NULL,
                friday INTEGER NOT NULL,
                saturday INTEGER NOT NULL,
                sunday INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO SERVICE_DAYS VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("weekday", 0, 0, 1, 0, 0, 0, 0),
        )
        conn.executemany(
            "INSERT INTO SUBWAY_STOP_TIMES VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("trip-1", 1, "weekday", 0, "finch-platform", 12 * 3600),
                ("trip-1", 2, "weekday", 0, "union-platform", 12 * 3600 + 600),
            ],
        )

    clear_cache()
    recorder.set_snapshot(None)
    app = FastAPI()
    app.include_router(map_routes.router, prefix="/api/v1")

    with TestClient(app) as client:
        yield client

    recorder.set_snapshot(None)
    clear_cache()


def test_schedule_database_becomes_exact_esp32_frame(pipeline):
    """SQLite -> schedule source -> map state -> renderer -> HTTP bytes."""
    response = pipeline.get("/api/v1/led-state.bin?map=rev-a&source=schedule")

    assert response.status_code == 200
    assert response.content == b"\x01"  # Finch is LED 0, packed LSB-first
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["x-source"] == "schedule"
    assert response.headers["x-led-count"] == "8"
    assert response.headers["etag"]


def test_binary_and_json_endpoints_describe_the_same_frame(pipeline):
    binary = pipeline.get("/api/v1/led-state.bin?map=rev-a&source=schedule")
    payload = pipeline.get("/api/v1/led-state?map=rev-a&source=schedule").json()

    assert binary.content == bytes.fromhex(payload["bits"])
    assert payload["on"] == [0]
    assert payload["source"] == binary.headers["x-source"]


def test_esp32_can_skip_an_unchanged_frame_with_etag(pipeline):
    first = pipeline.get("/api/v1/led-state.bin?map=rev-a&source=schedule")
    unchanged = pipeline.get(
        "/api/v1/led-state.bin?map=rev-a&source=schedule",
        headers={"If-None-Match": first.headers["etag"]},
    )

    assert unchanged.status_code == 304
    assert unchanged.content == b""
    assert unchanged.headers["etag"] == first.headers["etag"]


@pytest.mark.parametrize("status,age_s", [("error", 1), ("ok", 91)])
def test_bad_realtime_snapshot_falls_back_to_database(pipeline, status, age_s):
    recorder.set_snapshot(
        Snapshot(
            polled_at=NOW - timedelta(seconds=age_s),
            status=status,
            positions=[
                TrainPosition(line="line-1", direction=0, from_station="99969")
            ],
        )
    )

    response = pipeline.get("/api/v1/led-state.bin?map=rev-a")

    assert response.status_code == 200
    assert response.content == b"\x01"
    assert response.headers["x-source"] == "schedule"


def test_fresh_realtime_snapshot_reaches_the_esp32_without_db_fallback(pipeline):
    recorder.set_snapshot(
        Snapshot(
            polled_at=NOW - timedelta(seconds=5),
            status="ok",
            positions=[
                TrainPosition(line="line-1", direction=0, from_station="99969")
            ],
        )
    )

    response = pipeline.get("/api/v1/led-state.bin?map=rev-a")

    assert response.status_code == 200
    assert response.content == b"\x08"  # Union is LED 3
    assert response.headers["x-source"] == "ntas"


def test_frame_uses_the_bit_order_documented_for_esp32(pipeline):
    recorder.set_snapshot(
        Snapshot(
            polled_at=NOW,
            status="ok",
            positions=[
                TrainPosition(line="line-1", direction=0, from_station="99992"),
                TrainPosition(line="line-1", direction=0, from_station="99969"),
            ],
        )
    )

    frame = pipeline.get("/api/v1/led-state.bin?map=rev-a").content

    assert frame == b"\x09"
    assert bool((frame[0] >> 0) & 1) is True
    assert bool((frame[0] >> 3) & 1) is True
    assert bool((frame[0] >> 1) & 1) is False
