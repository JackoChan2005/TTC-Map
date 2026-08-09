"""Ported from node-api/test/ntasSource.test.js."""

from ttcmap.map.sources.ntas import positions_from_responses

TOPOLOGY = {
    "lines": [{"id": "line-2", "stations": ["a", "b", "c"]}],
    "stations": {"a": {"name": "Alpha"}, "b": {"name": "Beta"}, "c": {"name": "Gamma"}},
    "platforms": {
        "p1": {"station": "b", "line": "line-2", "direction": 0},
        "p2": {"station": "a", "line": "line-2", "direction": 0},
    },
}


def test_train_arriving_within_threshold_is_placed_approaching_the_station():
    positions = positions_from_responses(
        TOPOLOGY, [("p1", [{"line": "2", "direction": "0", "nextTrains": "1, 4, 7"}])]
    )
    assert len(positions) == 1
    assert positions[0].from_station == "a"
    assert positions[0].to_station == "b"


def test_train_far_away_is_ignored():
    positions = positions_from_responses(
        TOPOLOGY, [("p1", [{"line": "2", "direction": "0", "nextTrains": "5, 9"}])]
    )
    assert positions == []


def test_terminal_station_with_no_previous_stop_reports_at_station():
    positions = positions_from_responses(
        TOPOLOGY, [("p2", [{"line": "2", "direction": "0", "nextTrains": "0"}])]
    )
    assert positions[0].from_station == "a"
    assert positions[0].to_station is None


def test_malformed_next_trains_and_unknown_platforms_are_skipped():
    positions = positions_from_responses(
        TOPOLOGY,
        [
            ("p1", [{"line": "2", "direction": "0", "nextTrains": ""}]),
            ("unknown", [{"line": "2", "direction": "0", "nextTrains": "0"}]),
        ],
    )
    assert positions == []


def test_missing_direction_is_skipped_rather_than_raising():
    positions = positions_from_responses(TOPOLOGY, [("p1", [{"nextTrains": "1"}])])
    assert positions == []


def test_repeat_sightings_of_a_station_are_deduped():
    # NTAS carries no train ids, so two entries for the same line/direction/station
    # must collapse to one position rather than double-counting a train
    positions = positions_from_responses(
        TOPOLOGY,
        [
            ("p1", [{"line": "2", "direction": "0", "nextTrains": "1"}]),
            ("p1", [{"line": "2", "direction": "0", "nextTrains": "0"}]),
        ],
    )
    assert len(positions) == 1
