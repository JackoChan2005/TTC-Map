# Frontend redesign: API capability audit

Design source: root `desktop_ui_design.md`. Original reference images are kept
locally pending provenance confirmation; they supplied visual direction, not
transit data. See `ASSETS.md`.

## Architecture and reuse

The active application is `src/ttcmap/app.py`: FastAPI routers under `/api/v1`
followed by static `web/` files. The legacy `API/` and `node-api/` directories
are not registered applications. This redesign retains vanilla ES modules,
the generation-aware map poller, network/state validation and schematic geometry.
The old SVG renderer is replaced by an interactive geographic/schematic renderer.
The two page documents share one bootstrap and stylesheet. The former separate
search client and stylesheet are removed; transit HTTP access is in `web/js/api.js`.
There are no added runtime dependencies or transit backend changes. The security
policy now permits tile images from `tile.openstreetmap.org` and an origin-only
referrer, as required by the map provider.

## UI to API mapping

All paths below are relative to `/api/v1`.

| UI feature | Endpoint and verified fields | Support and behavior |
|---|---|---|
| Overview, line cards, station/line search, transfers | `GET /map-config`: `generation`, `network.lines[]` (`id`, `number`, `routeId`, `name`, `color`, `textColor`, `stations`), `network.stations`, `network.platforms`, `layout` | Supported. Search filters published names/numbers locally; no search endpoint exists. Includes Lines 1, 2, 4, 5, 6 when published. No hardcoded transit records. |
| Geographic station map | `GET /map-config`: `network.stations[id].lat/lon`; OpenStreetMap raster tiles | Supported real street background with station coordinates projected to Web Mercator. Route connections remain approximate because the transit API has no track geometry. |
| Schematic map | `GET /map-config`: `layout` | Supported; existing schematic remains available, also used if station coordinates are missing or invalid. |
| Train markers and source labels | `GET /map-state`: `generation`, `generatedAt`, `source`, `lineSources[id].source/reason`, `trains[].line/direction/at/between/progress/stationName` | Supported as inferred positions, not GPS. Filled live markers and outlined scheduled markers; estimates can be hidden. Unknown station references are not drawn. Failed requests clear all markers. |
| Route focus and station timeline | Same network and state data | Supported. Route bounding-box fit, other lines dimmed, directional station order from the canonical direction-0 order; transfers use actual station memberships. Timeline marks trains at/approaching stations. |
| Station scheduled departures | `GET /departures?route=<number>`: `requestedAt`, `matches[].deltaSeconds`, `payload.stop_id/direction_id` joined through `network.platforms[stop_id].station/line` | Partial substitute for the design's live countdowns. Two-minute, line-wide, maximum-200-row window only; no claim of exhaustive future arrivals. Cache ages countdowns and expires past results. |
| Timetable search page | `GET /departures?route=<number>&at=<ISO8601>`: `matches[].payload`, `requestedAt` | Supported. Local datetime input is explicitly labelled with the browser time zone, sent with an offset via ISO UTC; results show Toronto/service time. Retains raw schedule record disclosure. Handles 404 as no departures, plus empty results and failures. |
| Data availability dialog | `GET /health`: `status`, `gtfs.ready`, `realtime.lines[id].source` | Supported as data diagnostics only. Never presented as good service or on-time status. |
| Pan, zoom, reset, collapse, appearance, navigation | No additional requests | Supported locally. Route/station selections use query parameters and browser history. Appearance preferences last for the session. |

Station coordinates and schematic now come from one atomic `/map-config`
response. The pixel-only equirectangular `/layout/geographic` is deliberately
not used to overlay Web Mercator tiles. The existing poller rejects
map-state/config generation mismatches. Config is reused across ten-second
state polls. Route detail departures share
one in-flight promise/cache per route for 30 seconds. Navigation tokens prevent
late search/departure responses from overwriting another selection.

## Recently introduced capabilities incorporated

Reviewed commit `5187df4` (Lines 5/6 and per-line source reliability), router
registration, every current route handler, topology generation, map-state
serialization, departure SQL/response construction, health diagnostics and the
old frontend clients. There are no extra active route handlers hidden behind
the legacy directories.

- Retains the recently added atomic `/map-config` endpoint rather than reverting
  to independently fetched network/schematic artifacts.
- Uses `/health` and the coordinates already exposed by `/map-config`.
  The refinement removes the separate geographic layout request.
- Uses expanded topology for Lines 5/6 and `map-state.lineSources`, including
  unavailable lines and scheduled fallbacks. Line 6's scheduled source is never
  called live. Line 5 remains governed by backend configuration.
- Reuses `/departures` for route details as well as the existing search page.
  The backend's current service calendar logic remains authoritative.

## Existing routes deliberately unused

| Endpoint | Reason |
|---|---|
| `GET /network` | Duplicates topology already received atomically from `/map-config`. |
| `GET /layout/geographic` | Pixel-only equirectangular layout cannot directly align to Web Mercator tiles; atomic network coordinates are the better source. |
| `GET /layout/schematic` | Matching schematic already included in `/map-config`. Other valid layout names are not assumed to exist. |
| `GET /led-state`, `GET /led-state.bin` | Hardware renderer contracts, not browser map data. |
| `GET /gtfs/status` | Subset of `/health`; no duplicate diagnostic request needed. |
| CLI `ttcmap refresh` | Publication is CLI-only; the former HTTP write route was removed. Browser refresh only reloads reads. |
| `map-state?source=ntas/schedule&at=...` variants | The main map follows backend automatic source policy. Historical time selection remains in timetable search. |

## Missing capabilities and intentional limitations

| Design feature | Missing information | Current partial support / future integration |
|---|---|---|
| Exact rail alignment / GPS positions | No served GTFS shapes or vehicle GPS coordinates | Real OSM streets and API station coordinates are supported. Routes connect stations approximately; map-state progress positions trains on those connections. Validated shapes and vehicle coordinates would improve precision. |
| Per-station live arrival countdowns/headway on cards | Public map-state serialization does not expose NTAS ETA, platform arrival queues or observation age | Two-minute scheduled departures only. A station/direction arrival endpoint should expose ETA, observation time, source and freshness. Route cards show source labels rather than fabricated minutes. |
| “All lines running normally”, disruptions, on-time status | No alerts or operational-status endpoint; health measures data readiness | Informational unavailable state plus official TTC website link. Add alerts with affected routes/stations, severity, validity and timestamps. |
| Address search and point-to-point journey planning | No geocoder, itinerary planner, walking legs or transfer-time model | Search existing stations/lines. A geocoding service and journey-planning API would be needed for those additional search modes. |
| Full station departure board | Line-wide two-minute endpoint capped at 200 rows; no pagination or longer horizon | Current timetable search preserved. Add station, direction, horizon and pagination to departure data for comprehensive boards. |
| Location centering | Browser geolocation is not connected in this iteration | No invented user location. This could be implemented as an opt-in browser permission flow using published station coordinates; it does not inherently need a transit endpoint. |
| Accounts, contact form and remote preferences pictured in reference | No authentication, profile, contact submission or preference persistence services | These decorative reference controls are not presented as working actions. About, service information and session appearance controls are functional. |

No mock/demo transit data ships in `web/`, and no static JSON is silently used
when the real API fails. Populated browser-test fixtures exist only in the
optional test runner and are explicitly identified in its code and artifacts.

## Map refinement: September 12, 2026

- Verified `map-state.trains[].direction` is 0/1, following/reversing canonical
  `line.stations`. `between` is serialized in travel order. At-station arrows
  use the next segment tangent, or incoming tangent at terminals. Missing or
  inconsistent direction produces a neutral round marker.
- Live arrows use the route colour; schedule arrows have a coloured dashed
  outline. Single-line stations have coloured rings, and transfers have segmented
  rings for connected lines. Opposing arrow glyphs sit 3.5 screen pixels to the
  travel-side of their anchor so that they remain distinguishable; the underlying
  API-derived position does not change.
- Nearby observations on the same line, direction and source share a marker;
  its tooltip reports the count. No observations or coordinates are fabricated.
- Below zoom 10.8 only interchange stations, routes and trains remain. At
  10.8–12 terminals join them; at 12–13.2 ordinary stations and eligible names
  appear. At 13.2+ labels also show line numbers. Collision detection places
  transfer labels first and uses leader lines in crowded areas. Disabling
  ordinary names never disables interchange labels. Off-screen or covered
  stations need no label.
- Marker sizes are bounded in screen pixels. Wheel zoom anchors to the pointer;
  button zoom anchors to the usable map area beside or above the panel.
- Tiles use browser image loading and normal HTTP caching for the visible
  viewport only: no proxy, prefetch, offline download or alternate transit feed.
  A tile error leaves the transit overlay working with an unavailable notice.
- Provider: [OpenStreetMap tile service](https://operations.osmfoundation.org/policies/tiles/).
  Visible attribution links to its copyright page. This is a best-effort external
  service. The URL is isolated in the map renderer; switching providers also
  requires updating CSP and attribution. Pan/zoom regression tests intercept tiles;
  one fixed-viewport integration check verifies real imagery without scanning
  the public tile service.

## Validation

See `UI_VALIDATION.md` for commands, route coverage, screenshots and actual
backend availability observed during this task.
