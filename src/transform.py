from typing import Any

import globals
import pandas as pd
import sqlite3

base_dir = globals.home_dir

data_dir = base_dir / "data"
db_dir = base_dir / "db"

files = {
    "calendar_dates": "calendar_dates.txt",
    "calendar": "calendar.txt",
    "routes": "routes.txt",
    "stop_times": "stop_times.txt",
    "stops": "stops.txt",
    "trips": "trips.txt"
}

# Container to hold the DataFrames
dfs = {}

for var_name, filename in files.items():
    path = data_dir / filename
    print(f"reading {path}...")
    
    # Handle the specific dtype requirement for stop_times
    kwargs: dict[str, Any] = {'dtype': {'stop_headsign': str}} if var_name == "stop_times" else {}
    
    dfs[var_name] = pd.read_csv(path, **kwargs)

calendar_dates = dfs["calendar_dates"]
calendar = dfs["calendar"]
routes = dfs["routes"]
stop_times = dfs["stop_times"]
stops = dfs["stops"]
trips = dfs["trips"]

subway_routes = routes[routes['route_type'] == 1].copy()
route_ids = set(subway_routes['route_id'])

subway_trips = trips[trips['route_id'].isin(route_ids)].copy()
trip_ids = set(subway_trips['trip_id'])

subway_stop_times = stop_times.merge(subway_trips[['trip_id','route_id','service_id','trip_short_name','direction_id']], on='trip_id')
subway_stop_times = subway_stop_times.merge(stops[['stop_id','stop_code','stop_name']], on='stop_id')
subway_stop_times = subway_stop_times.sort_values(['trip_id', 'stop_sequence'])

id_cols = [col for col in subway_stop_times.columns if '_id' in col]
other_cols = [col for col in subway_stop_times.columns if '_id' not in col]
subway_stop_times = subway_stop_times[id_cols + other_cols]

print("Sending data to db...")
sd_conn = sqlite3.connect(db_dir / "SERVICEDAYS.db")
calendar.to_sql("SERVICEDAYS", sd_conn, if_exists="replace")
si_conn = sqlite3.connect(db_dir / "SUBWAYINFO.db")
subway_stop_times.to_sql("SUBWAYINFO", si_conn, if_exists="replace")

print("\nService Days:")
df_check = pd.read_sql("SELECT * FROM SERVICEDAYS", sd_conn)
print(df_check.head())
print("\nSubway Info:")
df_check = pd.read_sql("SELECT * FROM SUBWAYINFO", si_conn)
print(df_check.head())