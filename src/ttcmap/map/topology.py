"""Load topology and layouts from the published dataset."""

import re
from pathlib import Path

from ttcmap.config import get_settings

# Validate user-supplied layout and board names before path construction.
SAFE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def load_topology() -> dict:
    from ttcmap.db import read_dataset

    with read_dataset() as dataset:
        return dataset.network


def safe_json_path(directory: Path, name: str, kind: str) -> Path:
    if not SAFE_NAME.match(name):
        raise ValueError(f"Invalid {kind} name: {name}")
    return directory / f"{name}.json"


def load_layout(name: str) -> dict | None:
    from ttcmap.db import read_dataset

    safe_json_path(get_settings().shared_path / "layouts", name, "layout")
    with read_dataset() as dataset:
        return dataset.payload["layouts"].get(name)


def station_order(topology: dict, line_id: str, direction: int) -> list[str]:
    """Stations of a line in travel order (network.json lists direction 0 order)."""
    line = next((line for line in topology["lines"] if line["id"] == line_id), None)
    if not line:
        return []
    return line["stations"] if direction == 0 else list(reversed(line["stations"]))


def previous_station(topology: dict, line_id: str, direction: int, station_id: str) -> str | None:
    """The station a train came from, given the station it is approaching."""
    order = station_order(topology, line_id, direction)
    try:
        index = order.index(station_id)
    except ValueError:
        return None
    return order[index - 1] if index > 0 else None
