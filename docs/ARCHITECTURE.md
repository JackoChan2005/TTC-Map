# Architecture

Goal: a pipeline where the data source, the map geometry, and the display target can each be
swapped without touching the others. Every seam is a small JSON contract.

```
sources (schedule | NTAS realtime | recorded snapshot)   produce TrainPosition[]
        ↓
map state engine (pure)  ← shared/network.json          produces MapState frames
        ↓
renderers (web SVG | LED bitmask | ...)                 consume MapState via mapping files
```

Adding a display means adding a mapping file, not changing the engine. Adding a data source
means writing something that returns `TrainPosition[]`. Neither knows about the other.

## Contracts

| Contract | Shape |
|---|---|
| `TrainPosition` | `line, direction, from_station, to_station, progress, trip_id` — `to_station=None` means at `from_station` |
| `MapState` | `{generatedAt, source, trainCount, trains[], stationsWithTrains}` (+ `fallback` when degraded) |
| `shared/network.json` | Canonical topology: lines, ordered stations, platform → station map |
| `shared/layouts/<name>.json` | x/y per station for one visual design |
| `hardware/led-maps/<name>.json` | station → LED index for one board revision |

`MapState` keys are camelCase because the web frontend consumes them directly.

## Modules

| Module | Role |
|---|---|
| `gtfs/ckan.py` | Toronto Open Data client: feed version + zip download |
| `gtfs/build.py` | GTFS → `SUBWAY_STOP_TIMES` / `SERVICE_DAYS`, via staged tables |
| `gtfs/network.py` | GTFS → `shared/network.json` + `layouts/geographic.json` |
| `gtfs/refresh.py` | Version check, rebuild orchestration, periodic re-check |
| `map/state.py` | The pure engine. No database, no HTTP, no clock beyond `generatedAt` |
| `map/toronto_time.py` | Service-day and late-night window handling — the only copy |
| `map/topology.py` | Loads and caches `network.json`, layouts |
| `map/sources/schedule.py` | Interpolates position between consecutive scheduled stops |
| `map/sources/ntas.py` | Live NTAS fetch across all 148 platforms |
| `map/sources/snapshot.py` | Reads the recorder's snapshot; raises when unusable |
| `map/recorder.py` | Polls NTAS every 30s into an in-memory snapshot |
| `renderers/led.py` | `MapState` → packed bitmask for a board revision |

## Data flow

**Static schedule.** On startup and every 6 hours, `gtfs/refresh.py` compares CKAN's
`metadata_modified` against the `meta` table. Only on a difference does it download and
rebuild — the feed changes every few weeks, so almost every check is a no-op. The rebuild
regenerates `network.json` in the same pass, so the topology cannot drift from the schedule
tables.

The rebuild writes to `*__staging` tables and swaps them in under one transaction. SQLite DDL
is transactional and the database runs in WAL mode, so readers keep seeing the previous data
for the several minutes the pandas merge takes. The merge itself runs on a worker thread, so
the API stays responsive throughout.

**Realtime.** `map/recorder.py` polls TTC's NTAS endpoint for every platform on a 30s cadence
(concurrency 10 over a keep-alive client, ~2s per refresh) and stores the result in memory. If
fewer than half the platforms respond, the whole poll is treated as failed rather than serving
a half-blank map.

**Serving.** `map-state?source=auto` reads the snapshot and falls back to the schedule the
moment it is failed, missing, or older than 90s — stale realtime positions are never shown.
`?source=schedule` and `?source=ntas` force one path, which is what makes the fallback
testable.

## Known limits

NTAS carries no train ids, so adjacent stations can double-count one train, and position
within a segment is approximate. Positions are deduped per (line, direction, station), which
bounds the error but does not remove it. A dedup heuristic merging adjacent-station sightings
per line/direction is the obvious next improvement.

## Possible extensions

WebSocket or SSE push instead of 10s polling; a schematic layout file for a cleaner web map
(purely a new file in `shared/layouts/`); history playback, since `MapState` is serializable;
another city via a different GTFS feed and a regenerated `network.json`.
