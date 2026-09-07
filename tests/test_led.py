"""LED renderer: the bit packing the ESP32 firmware depends on.

New in the Python port — the JS renderer had no tests, and this is the contract
the PCB is designed against, so it is the one that must not drift.
"""

import json

import pytest

from ttcmap.config import REPO_ROOT
from ttcmap.map.state import MapState
from ttcmap.renderers.led import load_led_map, pack_bits, render_led_state


def make_state(stations_with_trains: dict[str, int]) -> MapState:
    return MapState(
        generatedAt="2026-08-09T12:00:00+00:00",
        source="schedule",
        trainCount=sum(stations_with_trains.values()),
        trains=[],
        stationsWithTrains=stations_with_trains,
    )


def test_pack_bits_is_lsb_first_within_each_byte():
    assert pack_bits([0], 8) == b"\x01"
    assert pack_bits([7], 8) == b"\x80"
    assert pack_bits([0, 3], 8) == b"\x09"
    assert pack_bits([], 8) == b"\x00"


def test_pack_bits_allocates_one_byte_per_eight_leds():
    assert len(pack_bits([], 8)) == 1
    assert len(pack_bits([], 9)) == 2
    assert len(pack_bits([8], 9)) == 2
    assert pack_bits([8], 9) == b"\x00\x01"


def test_rendered_bits_hex_matches_the_on_list():
    led_map = load_led_map("rev-a")
    state = make_state({"99992": 1, "99972": 2})

    rendered = render_led_state(state, led_map)

    assert rendered["on"] == [0, 3]
    assert rendered["bits"] == "09"
    assert rendered["_packed"] == pack_bits(rendered["on"], led_map["ledCount"])


def test_empty_state_lights_nothing():
    led_map = load_led_map("rev-a")
    rendered = render_led_state(make_state({}), led_map)
    assert rendered["on"] == []
    assert rendered["bits"] == "00"


def test_invalid_led_map_name_is_rejected():
    # the name reaches this from a query parameter, so path traversal must fail
    with pytest.raises(ValueError):
        load_led_map("../../etc/passwd")


def test_unknown_led_map_returns_none():
    assert load_led_map("no-such-board") is None


def test_every_led_maps_to_a_real_station():
    """A silkscreen referencing a station the topology does not have would
    silently never light up."""
    topology = json.loads((REPO_ROOT / "shared/network.json").read_text())
    led_map = load_led_map("rev-a")

    unknown = [led for led in led_map["leds"] if led["station"] not in topology["stations"]]
    assert unknown == [], f"LED map references unknown stations: {unknown}"

    assert len(led_map["leds"]) <= led_map["ledCount"]
    assert len({led["index"] for led in led_map["leds"]}) == len(led_map["leds"])
