"""Source selection for the map state engine.

Ported from node-api/src/map/index.js.

  auto      the last recorded NTAS snapshot; falls back to the schedule
            simulation the moment that snapshot is failed, missing or stale
  schedule  static GTFS simulation only
  ntas      a live NTAS fetch (raises when the feed is down)
"""

import asyncio
from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.map.sources import ntas, schedule, snapshot
from ttcmap.map.state import MapState, compute_map_state
from ttcmap.map.topology import load_topology

SOURCES = ("schedule", "ntas")


async def get_map_state(now: datetime | None = None, source: str | None = None) -> MapState:
    now = now or datetime.now(UTC)
    topology = load_topology()
    mode = source or get_settings().map_source or "auto"

    if mode == "schedule":
        positions = await asyncio.to_thread(schedule.get_train_positions, now)
        return compute_map_state(topology, positions, source="schedule")

    if mode == "ntas":
        positions = await ntas.get_train_positions()
        return compute_map_state(topology, positions, source="ntas")

    if mode != "auto":
        raise ValueError(f"Unknown map source: {mode}")

    try:
        positions = snapshot.get_train_positions(now)
        return compute_map_state(topology, positions, source="ntas")
    except Exception:
        positions = await asyncio.to_thread(schedule.get_train_positions, now)
        state = compute_map_state(topology, positions, source="schedule")
        state.fallback = True
        return state
