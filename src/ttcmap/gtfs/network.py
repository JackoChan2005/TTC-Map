"""Generate the canonical subway topology from the GTFS feed.

Ported from API/src/build_network.py. Writes shared/network.json (lines with
stations in direction_id 0 travel order, plus a platform stop_id -> station map
that both realtime and schedule sources use) and shared/layouts/geographic.json.

Unlike the original this runs as part of every GTFS refresh, so network.json can
no longer silently go stale after the feed changes.
"""

import json
import logging
import math
from pathlib import Path

import pandas as pd

from ttcmap.config import get_settings

log = logging.getLogger(__name__)

PLATFORM_SUFFIXES = [
    " - Northbound Platform",
    " - Southbound Platform",
    " - Eastbound Platform",
    " - Westbound Platform",
]
LAYOUT_MARGIN = 30.0
LAYOUT_WIDTH = 1000.0
SUBWAY_ROUTE_TYPE = 1


def _read_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    if not (data_dir / "routes.txt").exists():
        raise FileNotFoundError(f"GTFS files not found in {data_dir}. Run a GTFS refresh first.")
    return {
        "routes": pd.read_csv(data_dir / "routes.txt"),
        "trips": pd.read_csv(data_dir / "trips.txt", dtype={"trip_id": str}),
        "stop_times": pd.read_csv(
            data_dir / "stop_times.txt",
            dtype={"trip_id": str, "stop_headsign": str},
            usecols=["trip_id", "stop_id", "stop_sequence"],
        ),
        "stops": pd.read_csv(data_dir / "stops.txt"),
    }


def station_name(platform_name: str) -> str:
    for suffix in PLATFORM_SUFFIXES:
        platform_name = platform_name.removesuffix(suffix)
    # parent stations are named "Spadina", platforms "Spadina Station";
    # normalize so both map to the same station
    return platform_name.removesuffix(" Station")


def _longest_trip(
    trips: pd.DataFrame, stop_times: pd.DataFrame, route_id, direction_id: int
) -> pd.DataFrame:
    candidates = trips[(trips["route_id"] == route_id) & (trips["direction_id"] == direction_id)]
    stops = stop_times[stop_times["trip_id"].isin(set(candidates["trip_id"]))]
    if stops.empty:
        return stops
    best_trip = stops.groupby("trip_id")["stop_sequence"].count().idxmax()
    return stops[stops["trip_id"] == best_trip].sort_values("stop_sequence")


def build_network(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or (get_settings().data_path / "gtfs")
    frames = _read_data(data_dir)
    routes = frames["routes"]
    stops = frames["stops"].set_index("stop_id")

    subway_routes = routes[routes["route_type"] == SUBWAY_ROUTE_TYPE].sort_values("route_id")

    lines: list[dict] = []
    stations: dict[str, dict] = {}
    platforms: dict[str, dict] = {}
    station_id_by_name: dict[str, str] = {}

    def register_station(stop_id) -> str:
        platform = stops.loc[stop_id]
        parent_id = platform["parent_station"]

        if pd.notna(parent_id):
            station_id = str(int(parent_id))
            parent = stops.loc[int(parent_id)]
            name = station_name(str(parent["stop_name"]))
            lat, lon = parent["stop_lat"], parent["stop_lon"]
        else:
            name = station_name(str(platform["stop_name"]))
            station_id = name.lower().replace(" ", "-")
            lat, lon = platform["stop_lat"], platform["stop_lon"]

        # some platforms lack a parent_station (e.g. Spadina on Line 1);
        # merge by name so interchanges stay one station
        station_id = station_id_by_name.setdefault(name, station_id)

        if station_id not in stations:
            stations[station_id] = {
                "name": name,
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
                "lines": [],
            }
        return station_id

    for _, route in subway_routes.iterrows():
        trip_stops = _longest_trip(
            frames["trips"], frames["stop_times"], route["route_id"], direction_id=0
        )
        if trip_stops.empty:
            log.warning("No trips found for route %s, skipping", route["route_id"])
            continue

        line_id = f"line-{route['route_id']}"
        station_ids = []

        for stop_id in trip_stops["stop_id"]:
            station_id = register_station(stop_id)
            if line_id not in stations[station_id]["lines"]:
                stations[station_id]["lines"].append(line_id)
            station_ids.append(station_id)

        # platform stop_ids for both directions, so realtime and schedule
        # sources can map NTAS/stop_times rows back to stations
        for direction_id in (0, 1):
            direction_stops = _longest_trip(
                frames["trips"], frames["stop_times"], route["route_id"], direction_id
            )
            for stop_id in direction_stops["stop_id"]:
                platforms[str(stop_id)] = {
                    "station": register_station(stop_id),
                    "line": line_id,
                    "direction": direction_id,
                }

        lines.append(
            {
                "id": line_id,
                "routeId": int(route["route_id"]),
                "name": str(route["route_long_name"]),
                "color": f"#{route['route_color']}",
                "textColor": f"#{route['route_text_color']}",
                "stations": station_ids,
            }
        )

    for station in stations.values():
        station["interchange"] = len(station["lines"]) > 1

    return {
        "source": "TTC merged GTFS (Toronto Open Data)",
        "stationOrder": "direction_id 0 travel order",
        "lines": lines,
        "stations": stations,
        "platforms": platforms,
    }


def build_geographic_layout(network: dict) -> dict:
    """Equirectangular projection onto a 1000-wide canvas, aspect preserved."""
    lats = [s["lat"] for s in network["stations"].values()]
    lons = [s["lon"] for s in network["stations"].values()]
    lat_mid = math.radians((min(lats) + max(lats)) / 2)
    lon_span = (max(lons) - min(lons)) * math.cos(lat_mid)
    lat_span = max(lats) - min(lats)

    scale = (LAYOUT_WIDTH - 2 * LAYOUT_MARGIN) / lon_span
    height = lat_span * scale + 2 * LAYOUT_MARGIN

    layout = {
        station_id: {
            "x": round((s["lon"] - min(lons)) * math.cos(lat_mid) * scale + LAYOUT_MARGIN, 1),
            "y": round((max(lats) - s["lat"]) * scale + LAYOUT_MARGIN, 1),
        }
        for station_id, s in network["stations"].items()
    }

    return {
        "name": "geographic",
        "width": round(LAYOUT_WIDTH),
        "height": round(height),
        "stations": layout,
    }


def write_network(data_dir: Path | None = None) -> dict:
    """Build and write shared/network.json + shared/layouts/geographic.json."""
    settings = get_settings()
    network = build_network(data_dir)

    network_path = settings.shared_path / "network.json"
    network_path.parent.mkdir(parents=True, exist_ok=True)
    network_path.write_text(json.dumps(network, indent=2))

    layout = build_geographic_layout(network)
    layout_path = settings.shared_path / "layouts" / "geographic.json"
    layout_path.parent.mkdir(parents=True, exist_ok=True)
    layout_path.write_text(json.dumps(layout, indent=2))

    interchanges = sorted(s["name"] for s in network["stations"].values() if s["interchange"])
    log.info(
        "Wrote %s: %d lines, %d stations, %d platforms, %d interchanges (%s)",
        network_path,
        len(network["lines"]),
        len(network["stations"]),
        len(network["platforms"]),
        len(interchanges),
        ", ".join(interchanges),
    )
    return network
