from copy import deepcopy

import pytest

from ttcmap.gtfs.build import build_stop_times, gtfs_time_to_seconds
from ttcmap.gtfs.rail_routes import select_rail_routes


def test_selects_five_lines_by_public_identity_excluding_streetcars(rail_feed):
    rows = build_stop_times(rail_feed.frames)
    assert set(rows.line_id) == {"line-1", "line-2", "line-4", "line-5", "line-6"}
    assert set(rows.route_id) == {"raw-1", "raw-2", "raw-4", "raw-5", "raw-6"}
    assert len(rows) == 30
    first = rows.iloc[0]
    assert first.stop_sequence == 10
    assert first.next_stop_id == "p-1-0-b"
    assert first.next_departing_time_sec == 43320


def test_missing_line_and_wrong_type_reject_replacement(rail_feed):
    routes = rail_feed.frames["routes"]
    with pytest.raises(ValueError, match="all rail"):
        select_rail_routes(routes[routes.route_short_name != "6"])
    routes.loc[routes.route_short_name == "6", "route_type"] = "3"
    with pytest.raises(ValueError, match="Unexpected route type"):
        select_rail_routes(routes)


def test_duplicate_sequence_rejects_feed(rail_feed):
    rail_feed.frames["stop_times"].loc[1, "stop_sequence"] = "10"
    with pytest.raises(ValueError, match="Duplicate trip/stop"):
        build_stop_times(rail_feed.frames)


def test_generation_covers_schedule_exceptions_and_is_order_independent(rail_feed):
    _, before = rail_feed.prepare()
    original = deepcopy(rail_feed.frames)
    for key, frame in rail_feed.frames.items():
        rail_feed.frames[key] = frame.sample(frac=1, random_state=3)
    _, shuffled = rail_feed.prepare()
    assert before["generation"] == shuffled["generation"]
    rail_feed.frames["stop_times"].loc[0, "departure_time"] = "12:00:01"
    _, changed = rail_feed.prepare()
    assert changed["generation"] != before["generation"]
    rail_feed.frames.update(original)
    rail_feed.frames["calendar_dates"].loc[0] = ["W", "20260907", "2"]
    assert rail_feed.prepare()[1]["generation"] != before["generation"]


def test_gtfs_after_midnight_times_and_invalid_minutes():
    assert gtfs_time_to_seconds("25:30:00") == 91800
    with pytest.raises(ValueError):
        gtfs_time_to_seconds("12:60:00")
