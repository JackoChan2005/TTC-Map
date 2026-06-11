# Map architecture plan

Goal: a scalable map pipeline where the data source, map geometry, and display
target can each be swapped without touching the others. Every seam is a small
JSON contract:

```
sources (schedule | NTAS realtime)        — produce TrainPosition[]
        ↓
map state engine (pure)  ← network.json   — produces MapState frames
        ↓
renderers (web SVG | LED bitmask | ...)   — consume MapState via mapping files
```

Contracts:
- `TrainPosition`: `{ line, direction, from, to, progress, tripId? }` (`to: null` = at `from`)
- `MapState`: `{ generatedAt, source, trainCount, trains[], stationsWithTrains }`
- `shared/network.json`: canonical topology — lines, ordered stations, platforms
- `shared/layouts/<name>.json`: x/y per station for a visual design
- `Hardware/led-maps/<name>.json`: station → LED index for a board revision

## Status

### Phase 0 — canonical topology ✅ done
`API/src/build_network.py` generates `shared/network.json` from the GTFS feed:
70 stations, 3 lines, 4 interchanges, official colors, 148 platform ids mapped
to stations per line/direction. Also emits `shared/layouts/geographic.json`
(equirectangular projection). Regenerate after GTFS updates.

### Phase 1 — map state engine ✅ done
`node-api/src/map/`: pure `stateEngine.js` (no DB/HTTP imports), Toronto
time/service-day helpers with the GTFS >24:00 late-night window handled,
`sources/scheduleSource.js` interpolating positions between consecutive stops.
Endpoints: `/api/v1/network`, `/api/v1/layout/:name`, `/api/v1/map-state`
(`?source=schedule|ntas|auto`, `?at=` for schedule time travel).
Verified: 71 trains on a Wednesday evening (42/26/3 per line), 0 at 3:30 AM.
Unit tests in `node-api/test/` (`npm test`).

### Phase 2 — web renderer ✅ done
`node-api/public/map/` draws the network + layout as SVG and overlays trains,
polling every 10s. Geographic layout today; a schematic or PCB-styled design is
just another file in `shared/layouts/`.

### Phase 3 — LED renderer ✅ endpoint done, firmware pending
`Hardware/led-maps/rev-a.json` (8 LEDs → terminals + interchanges; update to
match the real silkscreen) + `/api/v1/led-state?map=rev-a` returning a packed
hex bitmask. Remaining: ESP32 firmware to poll it and shift out to the 74HC595s.
A "future renderer" = a new mapping file + (optionally) a small adapter module
in `node-api/src/map/renderers/` — no engine changes.

### Phase 4 — realtime source ✅ done
`sources/ntasSource.js` polls TTC NTAS
(`https://ntas.ttc.ca/api/ntas/get-next-train-time/<platformId>`) for all 148
platforms (keep-alive, concurrency 10, 30s cache, ~2s per refresh). Trains
arriving within 1 minute are placed approaching that station. `MAP_SOURCE=auto`
(default) uses NTAS and falls back to schedule when the feed is down.
Verified live: 92 trains, plausible per-line distribution.
Known limits: NTAS has no train ids, so adjacent stations can double-count a
train, and position within a segment is approximate.

### Phase 5 — future options (unchanged)
WebSocket/SSE push, schematic layout file, history playback (MapState is
serializable), other cities via a different GTFS + regenerated network.json.

## Next up
1. ESP32 firmware: HTTP poll of `/api/v1/led-state` + 74HC595 driver (Phase 3 hardware half).
2. Schematic layout file for a cleaner web map.
3. Dedup heuristic for NTAS double-counting (merge adjacent-station sightings per line/direction).
