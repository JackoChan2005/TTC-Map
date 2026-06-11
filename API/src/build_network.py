import json

import globals
import pandas as pd

# Output: <repo root>/shared/network.json — the canonical subway topology.
# Stations are listed in direction_id 0 travel order for each line.
NETWORK_PATH = globals.home_dir.parent / "shared" / "network.json"

PLATFORM_SUFFIXES = [" - Northbound Platform", " - Southbound Platform",
                     " - Eastbound Platform", " - Westbound Platform"]


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
        station_id_by_name: dict[str, str] = {}

        for _, route in subway_routes.iterrows():
            trip_stops = self.longest_trip(dfs["trips"], dfs["stop_times"],
                                           route["route_id"], direction_id=0)
            if trip_stops.empty:
                print(f"Warning: no trips found for route {route['route_id']}, skipping")
                continue

            line_id = f"line-{route['route_id']}"
            station_ids = []

            for stop_id in trip_stops["stop_id"]:
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
                if line_id not in stations[station_id]["lines"]:
                    stations[station_id]["lines"].append(line_id)
                station_ids.append(station_id)

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
        }

    def write(self) -> None:
        network = self.build()
        NETWORK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(NETWORK_PATH, "w") as f:
            json.dump(network, f, indent=2)

        total = sum(len(line["stations"]) for line in network["lines"])
        interchanges = [s["name"] for s in network["stations"].values() if s["interchange"]]
        print(f"Wrote {NETWORK_PATH}")
        for line in network["lines"]:
            print(f"  {line['name']}: {len(line['stations'])} stations ({line['color']})")
        print(f"  {len(network['stations'])} unique stations "
              f"({total} line-stops, {len(interchanges)} interchanges: {', '.join(sorted(interchanges))})")


if __name__ == "__main__":
    b = network_builder()
    b.write()
