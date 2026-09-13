"""Ported from node-api/test/stateEngine.test.js."""

from ttcmap.map.state import TrainPosition, compute_map_state

TOPOLOGY = {
    "lines": [{"id": "line-1", "stations": ["a", "b", "c"]}],
    "stations": {"a": {"name": "Alpha"}, "b": {"name": "Beta"}, "c": {"name": "Gamma"}},
    "platforms": {},
}


def test_low_progress_snaps_to_departure_station():
    state = compute_map_state(
        TOPOLOGY,
        [TrainPosition(line="line-1", direction=0, from_station="a", to_station="b", progress=0.1)],
    )
    assert state.trains[0]["at"] == "a"
    assert state.trains[0]["between"] is None
    assert state.stationsWithTrains == {"a": 1}


def test_high_progress_snaps_to_arrival_station():
    state = compute_map_state(
        TOPOLOGY,
        [
            TrainPosition(
                line="line-1", direction=0, from_station="a", to_station="b", progress=0.95
            )
        ],
    )
    assert state.trains[0]["at"] == "b"
    assert state.trains[0]["stationName"] == "Beta"


def test_mid_progress_stays_between_with_nearest_station_counted():
    state = compute_map_state(
        TOPOLOGY,
        [TrainPosition(line="line-1", direction=0, from_station="a", to_station="b", progress=0.6)],
    )
    assert state.trains[0]["at"] is None
    assert state.trains[0]["between"] == ["a", "b"]
    assert state.stationsWithTrains == {"b": 1}


def test_positions_at_unknown_stations_are_dropped():
    state = compute_map_state(
        TOPOLOGY,
        [
            TrainPosition(
                line="line-1", direction=0, from_station="nope", to_station="b", progress=0.5
            )
        ],
    )
    assert state.trainCount == 0


def test_to_none_means_at_the_from_station():
    state = compute_map_state(
        TOPOLOGY,
        [TrainPosition(line="line-1", direction=1, from_station="c", to_station=None, progress=0)],
    )
    assert state.trains[0]["at"] == "c"


def test_progress_is_clamped_into_range():
    state = compute_map_state(
        TOPOLOGY,
        [TrainPosition(line="line-1", direction=0, from_station="a", to_station="b", progress=9.0)],
    )
    assert state.trains[0]["progress"] == 1.0
    assert state.trains[0]["at"] == "b"


def test_fallback_flag_is_only_serialized_when_set():
    state = compute_map_state(TOPOLOGY, [], source="schedule")
    assert "fallback" not in state.as_dict()
    state.fallback = True
    assert state.as_dict()["fallback"] is True
