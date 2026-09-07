"""Public rail identity, independent of feed-specific route IDs."""

import pandas as pd

RAIL_TYPES = {"1": 1, "2": 1, "4": 1, "5": 0, "6": 0}


def select_rail_routes(routes: pd.DataFrame) -> pd.DataFrame:
    routes = routes.copy()
    routes["route_short_name"] = routes["route_short_name"].astype(str).str.strip()
    selected = routes[routes["route_short_name"].isin(RAIL_TYPES)].copy()
    if set(selected["route_short_name"]) != set(RAIL_TYPES):
        raise ValueError("GTFS must contain all rail lines: 1, 2, 4, 5, 6")
    if selected["route_short_name"].duplicated().any() or selected["route_id"].duplicated().any():
        raise ValueError("Ambiguous rail route identity")
    for row in selected.itertuples():
        if int(row.route_type) != RAIL_TYPES[row.route_short_name]:
            raise ValueError(f"Unexpected route type for rail line {row.route_short_name}")
    selected["line_id"] = "line-" + selected["route_short_name"]
    return selected.sort_values("route_short_name")
