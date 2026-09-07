"""Build deterministic five-line topology using reviewed application station IDs."""

import json
import logging
import math
from pathlib import Path

import pandas as pd

from ttcmap.config import get_settings
from ttcmap.gtfs.rail_routes import select_rail_routes

log = logging.getLogger(__name__)
PLATFORM_SUFFIXES = [
    f" - {d} Platform" for d in ("Northbound", "Southbound", "Eastbound", "Westbound", "Subway")
]
LAYOUT_MARGIN = 30.0
LAYOUT_WIDTH = 1000.0


def station_name(name: str) -> str:
    for suffix in PLATFORM_SUFFIXES:
        name = name.removesuffix(suffix)
    return name.removesuffix(" Station").strip()


def build_network(data_dir: Path | None = None, *, frames: dict | None = None) -> dict:
    from ttcmap.gtfs.build import read_gtfs

    frames = (
        frames if frames is not None else read_gtfs(data_dir or get_settings().data_path / "gtfs")
    )
    registry = json.loads((get_settings().shared_path / "stations.json").read_text())
    names, parents = {}, {}
    for sid, entry in registry.items():
        for table, values in (
            (names, [entry["name"], *entry.get("aliases", [])]),
            (parents, entry.get("gtfsParents", [])),
        ):
            for value in values:
                if value in table and table[value] != sid:
                    raise ValueError(f"Ambiguous station registry entry: {value}")
                table[value] = sid
    stops = frames["stops"].set_index("stop_id")
    if not stops.index.is_unique:
        raise ValueError("Duplicate GTFS stop ID")
    routes = select_rail_routes(frames["routes"])
    trips = frames["trips"].merge(routes[["route_id", "line_id"]], on="route_id")
    rows = frames["stop_times"].merge(
        trips[["trip_id", "line_id", "direction_id"]], on="trip_id", validate="many_to_one"
    )
    rows["stop_sequence"] = pd.to_numeric(rows["stop_sequence"], errors="raise")
    rows = rows.sort_values(["line_id", "direction_id", "trip_id", "stop_sequence"])
    stations, platforms = {}, {}

    def register(stop_id: str) -> str:
        platform = stops.loc[stop_id]
        parent_id = platform["parent_station"]
        parent = stops.loc[parent_id] if parent_id else platform
        name = station_name(parent["stop_name"])
        by_name, by_parent = names.get(name), parents.get(parent_id)
        if by_name and by_parent and by_name != by_parent:
            raise ValueError(f"Conflicting parent/name identity: {stop_id}")
        sid = by_name or by_parent
        if not sid:
            raise ValueError(f"Register unknown station {name!r} (parent {parent_id})")
        lat, lon = float(parent["stop_lat"]), float(parent["stop_lon"])
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise ValueError(f"Invalid station coordinates: {sid}")
        stations.setdefault(
            sid,
            {
                "name": registry[sid]["name"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "lines": [],
            },
        )
        return sid

    patterns = {}
    for (line, direction, trip), group in rows.groupby(
        ["line_id", "direction_id", "trip_id"], sort=True
    ):
        pattern = []
        for stop_id in group["stop_id"]:
            sid = register(stop_id)
            mapping = {
                "station": sid,
                "line": line,
                "direction": int(direction),
                "stopCode": stops.loc[stop_id]["stop_code"] or stop_id,
            }
            if stop_id in platforms and platforms[stop_id] != mapping:
                raise ValueError(f"Conflicting platform assignment: {stop_id}")
            platforms[stop_id] = mapping
            if line not in stations[sid]["lines"]:
                stations[sid]["lines"].append(line)
            pattern.append(sid)
        patterns.setdefault((line, int(direction)), []).append((str(trip), pattern))
    lines = []
    for route in routes.itertuples():
        orders = []
        for direction in (0, 1):
            candidates = patterns.get((route.line_id, direction), [])
            if not candidates:
                raise ValueError(f"Missing trips for {route.line_id} direction {direction}")
            canonical = sorted(candidates, key=lambda item: (-len(item[1]), item[0]))[0][1]
            if len(canonical) < 2 or len(set(canonical)) != len(canonical):
                raise ValueError(f"Invalid canonical pattern for {route.line_id}")
            for trip, pattern in candidates:
                start = canonical.index(pattern[0]) if pattern[0] in canonical else -1
                if start < 0 or canonical[start : start + len(pattern)] != pattern:
                    raise ValueError(f"Unsupported rail pattern: {route.line_id} trip {trip}")
            orders.append(canonical)
        if orders[0] != list(reversed(orders[1])):
            raise ValueError(f"Directions disagree for {route.line_id}")
        lines.append(
            {
                "id": route.line_id,
                "routeId": str(route.route_id),
                "number": route.route_short_name,
                "name": route.route_long_name,
                "color": "#" + route.route_color,
                "textColor": "#" + route.route_text_color,
                "stations": orders[0],
            }
        )
    for s in stations.values():
        s["lines"].sort()
        s["interchange"] = len(s["lines"]) > 1
    return {
        "source": "TTC merged GTFS (Toronto Open Data)",
        "stationOrder": "direction_id 0 travel order",
        "lines": lines,
        "stations": dict(sorted(stations.items())),
        "platforms": dict(sorted(platforms.items())),
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
