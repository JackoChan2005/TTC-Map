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
| `TrainPosition` | `line, direction, from_station, to_station, progress, trip_id` — `to_station=None` means at `from_station`. Realtime positions also carry `eta_s, progress_floor, key`; see *Realtime* below |
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
| `map/segments.py` | Median traversal time per segment, measured from the schedule |
| `map/interpolate.py` | NTAS countdowns → positions; ages them between polls |
| `map/sources/schedule.py` | Interpolates position between consecutive scheduled stops |
| `map/sources/ntas.py` | Live NTAS fetch across all 148 platforms |
| `map/sources/snapshot.py` | Reads the recorder's snapshot; raises when unusable |
| `map/recorder.py` | Polls NTAS every 30s into an in-memory snapshot |
| `renderers/led.py` | `MapState` → packed bitmask for a board revision |

The web side is split along the same contract boundary:

- `web/js/mapModel.js` validates API data and builds schematic-map view models.
- `web/js/render/svgMap.js` is the thin DOM/SVG renderer.
- `scripts/lib/schematic.mjs` deterministically converts the geographic layout to octolinear
  station coordinates.
- `security.py` applies CSP and browser hardening headers to API and static responses.

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

NTAS answers "next train in N minutes" — a countdown to a destination, not a position — so the
snapshot stores ETAs and `map/interpolate.py` converts them per request, using the segment
traversal times `map/segments.py` measures from the schedule:

```
remaining = eta_s - age_of_snapshot
progress  = 1 - remaining / span        while 0 < remaining < span
```

Three consequences fall out of that one rule:

- **Motion between polls.** Ageing a countdown is subtraction, so the board sees trains move on
  every request rather than jumping every 30s. No velocity estimate and no per-train tracking —
  and because the anchor is a fixed future event, error shrinks as a train nears its platform
  instead of accumulating the way dead reckoning would.
- **One sighting per train.** Every platform reports every train heading its way, so a live poll
  parses ~195 sightings of ~65 trains. A train whose ETA exceeds its segment's own span has not
  entered that segment yet and is already being reported by the platform behind, so it is
  dropped. What survives is the segment the train is actually on.
- **No reversing.** NTAS reports whole minutes and revises each poll, so a held train can read
  "2 minutes" twice running. `carry_floor` seeds each new reading with where the last poll had
  that train, so a revision can only move it forwards.

The floor is keyed on `line|direction|station|nth-arrival`, which is a queue slot rather than a
vehicle. When the nearest train arrives everything behind it shifts down an index, so a reading
further out than the projection by more than a minute's rounding is treated as a different train
and gets no floor.

**Serving.** `map-state?source=auto` reads the snapshot and falls back to the schedule the
moment it is failed, missing, or older than 90s — stale realtime positions are never shown.
`?source=schedule` and `?source=ntas` force one path, which is what makes the fallback
testable.

## Known limits

NTAS still carries no train ids, so nothing here tracks a vehicle; it tracks queue slots and
countdowns, which is enough to place trains but not to follow one.

Two effects are left. NTAS reports whole minutes, so arrivals bunch into cohorts that expire
together — `ARRIVED_GRACE_S` holds an arrived train across its dwell until the next segment
picks it up, which overcounts by ~15% at the end of a poll cycle. Preferring the overcount is
deliberate: an LED that lingers reads as a dwelling train, one that blinks reads as a bug. And
segment spans are medians over the whole schedule, so a train held mid-segment sits still
rather than slowing down.

Both would be fixed by a feed carrying vehicle ids. Neither is worth more inference on top of
this one.

## Web renderer

The root page renders `shared/layouts/schematic.json` as an octolinear SVG map and polls
`/api/v1/map-state` every 10 seconds. The pure modules under `web/js/` validate every API
payload before building line, station, and train view models; the DOM renderer only draws
those validated models. `/search/` retains departure search, and `/map/` redirects old
bookmarks to the schematic homepage. See `docs/UI_PLAN.md` for the design and test strategy.

## Possible extensions

WebSocket or SSE push instead of 10s polling; history playback, since `MapState` is
serializable; another city via a different GTFS feed and a regenerated `network.json`.
