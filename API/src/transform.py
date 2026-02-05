from typing import Any

import globals
import pandas as pd
import sqlite3

class transformer:
    def __init__(self) -> None:
        self.files = {
            "calendar": "calendar.txt",
            "routes": "routes.txt",
            "stop_times": "stop_times.txt",
            "stops": "stops.txt",
            "trips": "trips.txt"
        }
        self.data_dir = globals.data_dir

    def read_data(self) -> dict:
        dfs = {}
        for var_name, filename in self.files.items():
            path = self.data_dir / filename
            print(f"reading {path}...")
            
            # Handle the specific dtype requirement for stop_times
            kwargs: dict[str, Any] = {'dtype': {'stop_headsign': str}} if var_name == "stop_times" else {}
            
            dfs[var_name] = pd.read_csv(path, **kwargs)
        return dfs

    def transform(self) -> None:
        dfs = self.read_data()

        calendar = dfs["calendar"]
        routes = dfs["routes"]
        stop_times = dfs["stop_times"]
        stops = dfs["stops"]
        trips = dfs["trips"]

        subway_routes = routes[routes['route_type'] == 1].copy()
        route_ids = set(subway_routes['route_id'])

        subway_trips = trips[trips['route_id'].isin(route_ids)].copy()

        subway_stop_times = stop_times.merge(subway_trips[['trip_id','route_id','service_id','trip_short_name','direction_id']], on='trip_id')
        subway_stop_times = subway_stop_times.merge(stops[['stop_id','stop_code','stop_name']], on='stop_id')
        subway_stop_times = subway_stop_times.sort_values(['trip_id', 'stop_sequence'])

        subway_stop_times['departing_time_sec'] = subway_stop_times['departure_time'].apply(globals.gtfs_time_to_seconds)

        id_cols = [col for col in subway_stop_times.columns if '_id' in col]
        other_cols = [col for col in subway_stop_times.columns if '_id' not in col]
        subway_stop_times = subway_stop_times[id_cols + other_cols]

        print("Sending data to db...")
        conn = sqlite3.connect(globals.conn)
        calendar.to_sql("SERVICE_DAYS", conn, if_exists="replace", index=False)
        subway_stop_times.to_sql("SUBWAY_STOP_TIMES", conn, if_exists="replace", index=False)

        print("Service Days:")
        df_check = pd.read_sql("SELECT * FROM SERVICE_DAYS", conn)
        print(df_check.head())
        print("\nSubway Info:")
        df_check = pd.read_sql("SELECT * FROM SUBWAY_STOP_TIMES", conn)
        print(df_check.head())

if __name__ == "__main__":
    t = transformer()
    t.transform()