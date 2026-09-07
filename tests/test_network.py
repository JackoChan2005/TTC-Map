import json

import pandas as pd
import pytest

from ttcmap.config import REPO_ROOT
from ttcmap.gtfs.network import build_network


def test_committed_network_preserves_all_legacy_stations_and_board_ids():
    network = json.loads((REPO_ROOT / "shared/network.json").read_text())
    registry = json.loads((REPO_ROOT / "shared/stations.json").read_text())
    assert {line["id"] for line in network["lines"]} == {
        "line-1",
        "line-2",
        "line-4",
        "line-5",
        "line-6",
    }
    assert len(next(line for line in network["lines"] if line["id"] == "line-5")["stations"]) == 25
    assert len(next(line for line in network["lines"] if line["id"] == "line-6")["stations"]) == 18
    for name in ("Cedarvale", "Eglinton", "Kennedy", "Finch West"):
        found = [s for s in network["stations"].values() if s["name"] == name]
        assert len(found) == 1 and found[0]["interchange"]
    assert set(registry) == set(network["stations"])
    assert network["stations"]["99947"]["name"] == "Kennedy"


def test_short_turn_and_its_extra_platform_are_registered(rail_feed):
    frames = rail_feed.frames
    trip = frames["trips"].iloc[0].copy()
    trip.trip_id = "short"
    frames["trips"] = pd.concat([frames["trips"], trip.to_frame().T], ignore_index=True)
    stop = frames["stops"][frames["stops"].stop_id == "p-1-0-b"].iloc[0].copy()
    stop.stop_id = stop.stop_code = "short-platform"
    frames["stops"] = pd.concat([frames["stops"], stop.to_frame().T], ignore_index=True)
    rows = frames["stop_times"][frames["stop_times"].trip_id == "t-1-0"].iloc[1:].copy()
    rows["trip_id"] = "short"
    rows.loc[rows.index[0], "stop_id"] = "short-platform"
    frames["stop_times"] = pd.concat([frames["stop_times"], rows], ignore_index=True)
    network = build_network(frames=frames)
    assert network["platforms"]["short-platform"]["station"] == "s-1-b"
    assert network["lines"][0]["stations"] == ["s-1-a", "s-1-b", "s-1-c"]


def test_missing_parent_terminal_uses_registry_name(rail_feed):
    frames = rail_feed.frames
    frames["stops"].loc[frames["stops"].stop_id == "p-1-0-c", "parent_station"] = ""
    assert build_network(frames=frames)["platforms"]["p-1-0-c"]["station"] == "s-1-c"


def test_ambiguous_registry_and_skipped_pattern_are_rejected(rail_feed):
    registry = rail_feed.registry
    registry["s-2-a"]["aliases"] = ["s-1-a"]
    (rail_feed.shared / "stations.json").write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="Ambiguous"):
        rail_feed.prepare()
