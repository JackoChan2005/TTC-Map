import json

import globals
import pandas as pd

# Output: <repo root>/shared/network.json — the canonical subway topology.
# Stations are listed in direction_id 0 travel order for each line.
NETWORK_PATH = globals.home_dir.parent / "shared" / "network.json"

PLATFORM_SUFFIXES = [" - Northbound Platform", " - Southbound Platform",
                     " - Eastbound Platform", " - Westbound Platform"]
LAYOUT_PATH = globals.home_dir.parent / "shared" / "layouts" / "geographic.json"
LAYOUT_MARGIN = 30.0


class network_builder:
    def __init__(self) -> None:
        self.data_dir = globals.data_dir

    def read_data(self) -> dict:
        if not (self.data_dir / "routes.txt").exists():
            raise FileNotFoundError(
                f"GTFS files not found in {self.data_dir}. Run update_db.py first."
            )
        return {
            "routes": pd.read_csv(self.data_dir / "routes.txt"),
            "trips": pd.read_csv(self.data_dir / "trips.txt", dtype={"trip_id": str}),
            "stop_times": pd.read_csv(
                self.data_dir / "stop_times.txt",
                dtype={"trip_id": str, "stop_headsign": str},
                usecols=["trip_id", "stop_id", "stop_sequence"],
            ),
            "stops": pd.read_csv(self.data_dir / "stops.txt"),
        }

    def station_name(self, platform_name: str) -> str:
        for suffix in PLATFORM_SUFFIXES:
            platform_name = platform_name.removesuffix(suffix)
        # parent stations are named "Spadina", platforms "Spadina Station";
        # normalize so both map to the same station
        return platform_name.removesuffix(" Station")

    def longest_trip(self, trips: pd.DataFrame, stop_times: pd.DataFrame,
                     route_id, direction_id: int) -> pd.DataFrame:
        candidates = trips[(trips["route_id"] == route_id)
                           & (trips["direction_id"] == direction_id)]
        st = stop_times[stop_times["trip_id"].isin(set(candidates["trip_id"]))]
        if st.empty:
            return st
        counts = st.groupby("trip_id")["stop_sequence"].count()
        best_trip = counts.idxmax()
        return st[st["trip_id"] == best_trip].sort_values("stop_sequence")

    def build(self) -> dict:
        dfs = self.read_data()
        routes = dfs["routes"]
        stops = dfs["stops"].set_index("stop_id")

        subway_routes = routes[routes["route_type"] == 1].sort_values("route_id")

        lines = []
        stations: dict[str, dict] = {}
        platforms: dict[str, dict] = {}
        station_id_by_name: dict[str, str] = {}

        def register_station(stop_id) -> str:
            platform = stops.loc[stop_id]
            parent_id = platform["parent_station"]

            if pd.notna(parent_id):
                station_id = str(int(parent_id))
                parent = stops.loc[int(parent_id)]
                name = self.station_name(str(parent["stop_name"]))
                lat, lon = parent["stop_lat"], parent["stop_lon"]
            else:
                name = self.station_name(str(platform["stop_name"]))
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
            trip_stops = self.longest_trip(dfs["trips"], dfs["stop_times"],
                                           route["route_id"], direction_id=0)
            if trip_stops.empty:
                print(f"Warning: no trips found for route {route['route_id']}, skipping")
                continue

            line_id = f"line-{route['route_id']}"
            station_ids = []

            for stop_id in trip_stops["stop_id"]:
                station_id = register_station(stop_id)
                if line_id not in stations[station_id]["lines"]:
                    stations[station_id]["lines"].append(line_id)
                station_ids.append(station_id)

            # platform stop_ids for both directions, so realtime sources and
            # the schedule source can map stop_times/NTAS rows to stations
            for direction_id in (0, 1):
                direction_stops = self.longest_trip(dfs["trips"], dfs["stop_times"],
                                                    route["route_id"], direction_id)
                for stop_id in direction_stops["stop_id"]:
                    platforms[str(stop_id)] = {
                        "station": register_station(stop_id),
                        "line": line_id,
                        "direction": direction_id,
                    }

            lines.append({
                "id": line_id,
                "routeId": int(route["route_id"]),
                "name": str(route["route_long_name"]),
                "color": f"#{route['route_color']}",
                "textColor": f"#{route['route_text_color']}",
                "stations": station_ids,
            })

        for station in stations.values():
            station["interchange"] = len(station["lines"]) > 1

        return {
            "source": "TTC merged GTFS (Toronto Open Data)",
            "stationOrder": "direction_id 0 travel order",
            "lines": lines,
            "stations": stations,
            "platforms": platforms,
        }

    def build_geographic_layout(self, network: dict) -> dict:
        # equirectangular projection of station coordinates onto a
        # 1000-wide canvas, latitude scaled so distances keep their aspect
        import math

        lats = [s["lat"] for s in network["stations"].values()]
        lons = [s["lon"] for s in network["stations"].values()]
        lat_mid = math.radians((min(lats) + max(lats)) / 2)
        lon_span = (max(lons) - min(lons)) * math.cos(lat_mid)
        lat_span = max(lats) - min(lats)

        width = 1000.0
        scale = (width - 2 * LAYOUT_MARGIN) / lon_span
        height = lat_span * scale + 2 * LAYOUT_MARGIN

        layout = {}
        for station_id, s in network["stations"].items():
            x = (s["lon"] - min(lons)) * math.cos(lat_mid) * scale + LAYOUT_MARGIN
            y = (max(lats) - s["lat"]) * scale + LAYOUT_MARGIN
            layout[station_id] = {"x": round(x, 1), "y": round(y, 1)}

        return {
            "name": "geographic",
            "width": round(width),
            "height": round(height),
            "stations": layout,
        }

    def write(self) -> None:
        network = self.build()
        NETWORK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(NETWORK_PATH, "w") as f:
            json.dump(network, f, indent=2)

        layout = self.build_geographic_layout(network)
        LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LAYOUT_PATH, "w") as f:
            json.dump(layout, f, indent=2)
        print(f"Wrote {LAYOUT_PATH}")

        total = sum(len(line["stations"]) for line in network["lines"])
        interchanges = [s["name"] for s in network["stations"].values() if s["interchange"]]
        print(f"Wrote {NETWORK_PATH} ({len(network['platforms'])} platforms)")
        for line in network["lines"]:
            print(f"  {line['name']}: {len(line['stations'])} stations ({line['color']})")
        print(f"  {len(network['stations'])} unique stations "
              f"({total} line-stops, {len(interchanges)} interchanges: {', '.join(sorted(interchanges))})")


if __name__ == "__main__":
    b = network_builder()
    b.write()
