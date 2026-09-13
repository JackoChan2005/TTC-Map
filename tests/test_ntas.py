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

WINDOW_MIN = 5


def parse(responses, arriving_min=WINDOW_MIN):
    return positions_from_responses(TOPOLOGY, responses, arriving_min=arriving_min)


def test_train_arriving_is_placed_approaching_the_station():
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "1"}])])
    assert len(positions) == 1
    assert positions[0].from_station == "a"
    assert positions[0].to_station == "b"


def test_every_arrival_in_the_list_becomes_a_train():
    # "1, 4" is two trains queued for the same platform; keeping only the first
    # is what left most of the map dark
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "1, 4, 7"}])])
    assert [p.eta_s for p in positions] == [60.0, 240.0]


def test_arrivals_beyond_the_window_are_ignored():
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "9, 12"}])])
    assert positions == []


def test_eta_is_carried_rather_than_a_position():
    # the parser must not guess a position; interpolate does that once the age
    # of the observation is known
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "3"}])])
    assert positions[0].eta_s == 180.0
    assert positions[0].progress == 0.0


def test_terminal_station_with_no_previous_stop_reports_at_station():
    positions = parse([("p2", [{"line": "2", "direction": "0", "nextTrains": "0"}])])
    assert positions[0].from_station == "a"
    assert positions[0].to_station is None


def test_malformed_next_trains_and_unknown_platforms_are_skipped():
    positions = parse(
        [
            ("p1", [{"line": "2", "direction": "0", "nextTrains": ""}]),
            ("unknown", [{"line": "2", "direction": "0", "nextTrains": "0"}]),
        ]
    )
    assert positions == []


def test_unparseable_arrivals_do_not_drop_the_rest():
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "x, 2"}])])
    assert [p.eta_s for p in positions] == [120.0]


def test_missing_direction_is_skipped_rather_than_raising():
    positions = parse([("p1", [{"nextTrains": "1"}])])
    assert positions == []


def test_repeat_sightings_of_a_queue_slot_are_deduped():
    # NTAS carries no train ids, so two responses covering the same
    # line/direction/station must collapse per queue position rather than
    # double-counting the same trains
    positions = parse(
        [
            ("p1", [{"line": "2", "direction": "0", "nextTrains": "1, 4"}]),
            ("p1", [{"line": "2", "direction": "0", "nextTrains": "0, 3"}]),
        ]
    )
    assert len(positions) == 2
    assert {p.key for p in positions} == {"line-2|0|b|0", "line-2|0|b|1"}


def test_unsorted_and_negative_arrivals_do_not_hide_valid_predictions():
    positions = parse([("p1", [{"line": "2", "direction": "0", "nextTrains": "9, -1, 2, 1"}])])
    assert [p.eta_s for p in positions] == [60, 120]


def test_wrong_line_or_direction_is_not_assigned_to_platform():
    assert parse([("p1", [{"line": "5", "direction": "0", "nextTrains": "1"}])]) == []
    assert parse([("p1", [{"line": "2", "direction": "1", "nextTrains": "1"}])]) == []
