# Architecture

One Python service serves a rail map, scheduled departure search and ESP32 LED
frames. Node is an optional development tool for generating the schematic and
running frontend tests; it is not needed for service startup.

## Modules and contracts

| Path | Responsibility |
| --- | --- |
| `src/ttcmap/gtfs/rail_routes.py` | Select public lines 1/2/4/5/6 and validate their GTFS types |
| `src/ttcmap/gtfs/ckan.py` | Discover the ZIP resource, retain content-addressed ZIPs, verify offline cache, isolate extraction |
| `src/ttcmap/gtfs/build.py` | Validate and order rail stop times; build canonical content hashes; stage and publish tables/artifacts |
| `src/ttcmap/gtfs/network.py` | Resolve stable station identities and validate full/short-turn patterns in both directions |
| `shared/stations.json` | Reviewed application station identities, aliases and GTFS parent crosswalk |
| `src/ttcmap/gtfs/service_calendar.py` | Resolve service dates, weekday calendars, exceptions and validity |
| `src/ttcmap/gtfs/refresh.py` | Coordinate version checks, importer upgrades and publication |
| `src/ttcmap/gtfs/refresh_lock.py` | Native OS writer lock shared by CLI and server |
| `src/ttcmap/db.py` | SQLite access and a transaction-pinned Dataset context |
| `src/ttcmap/map/sources/ntas.py` | Validate and aggregate bounded HTTP polls by line and direction |
| `src/ttcmap/map/recorder.py` | Store immutable observations and carry progress floors within a generation |
| `src/ttcmap/map/sources/schedule.py` | Query dated scheduled positions and operating-service windows |
| `src/ttcmap/map/segments.py` | Generation-scoped median traversal times from explicit next-stop relationships |
| `src/ttcmap/map/interpolate.py` | Convert countdowns into estimated segment progress |
| `src/ttcmap/map/__init__.py` | Choose one source per line and assemble a consistent MapState |
| `web/js/pollMap.js` | Serialize browser polling and match state to config generation |
| `src/ttcmap/renderers/led.py` | Preserve the board's packed station-occupancy bitmask |

## Published state

`data/ttc.db` contains `SUBWAY_STOP_TIMES`, `SERVICE_DAYS`,
`SERVICE_EXCEPTIONS`, and one `active_dataset` row. The row stores topology,
layouts, generation, feed-cache identity, source version and importer revision.
Runtime never falls back to reading shared topology JSON. Shared files are
reviewable build inputs/exports; the schematic is validated before publication.

A writer builds staging tables while readers continue using the old dataset.
The final transaction swaps all tables and updates the active row and metadata.
A failed preparation or transaction leaves the previous complete dataset active.
OS locking prevents the CLI and service from colliding on staging tables. A
request pins a single SQLite read transaction and does not await HTTP while
holding it. Late polls carry their old generation and cannot be applied to a new
dataset. Segment caches are bounded and keyed by generation.

The supported deployment is one server worker on one host with local SQLite.
The OS lock also coordinates local CLI invocations. A cloud-synchronized folder
is not a supported way to share the active database across hosts.

## Source policy

`NTAS_ENABLED_LINES` defaults to `["1","2","4"]`; only 1/2/4/5 are accepted.
Line 5's 90% valid-response threshold per direction is an initial enablement gate.
Existing lines retain the provisional 50% numeric threshold, now checked per
direction. Thresholds are configuration, not provider guarantees; measure before
changing them. All platforms are included until a departure-only terminal
exclusion is verified. Line 6 is never polled by this adapter.

- `auto`: combine live and scheduled lines. `fallback` flags only an enabled
  live line needing scheduled substitution.
- `schedule`: scheduled estimates for all lines.
- `ntas`: fresh recorder data for all configured live lines, with other lines
  explicitly excluded. A missing, failed or stale enabled line returns 503.
  This mode performs no additional platform HTTP requests. No enabled lines or
  no initial snapshot also returns 503.
- Explicit `at`: use schedules; `source=ntas&at=...` returns 400. Naive timestamps
  mean Toronto local time. Prefer timestamps with explicit offsets around DST.

`lineSources` is the authoritative per-line source metadata. Top-level `source`
may be `mixed`, including when one selected line currently has no trains. A lack
of predictions during scheduled service is not proof of a suspension: the map
labels the substitute as a schedule. No public reliable Line 6 live source is
claimed. Adding GTFS-Realtime is a separate change.

## Refresh and upgrade operations

Refresh is CLI-only. The former HTTP refresh route is removed. Browser viewers
can read state and diagnostics but cannot trigger publication.

Use `uv run ttcmap refresh` to check metadata and rebuild when the feed, importer
revision or local registry/layout inputs change. `--force` rebuilds even if the
version is unchanged. The recorded metadata comes from the package used for the
download. A compatible published dataset remains usable if CKAN is offline.
An importer-only offline rebuild can use the verified cached ZIP referenced by
the active dataset. Unverified old extracted files are not an offline cache.

Existing installations need a first new-format publication; until then data
endpoints report readiness 503. Before upgrading a deployed service, back up its
SQLite database with SQLite's backup API, retain the matching application
revision, and run the rebuild before switching traffic. Restore the matching DB
and code together for rollback. Do not copy an active WAL database as a single
file or restore only JSON exports.

For new stations or layout changes:

```sh
uv run ttcmap build-network
node scripts/build-schematic.mjs
uv run ttcmap refresh --force
```

`build-network` uses the published verified ZIP and only writes shared exports.
For an explicitly extracted feed use `build-network --data-dir <directory>`.
Review `shared/stations.json` first if identity resolution fails. Unknown station
identities, unsupported patterns or missing layout coordinates reject a refresh
and leave the prior dataset active. The generator does not run at server startup.

## Validation

The test fixtures contain all five rail lines plus an excluded streetcar,
feed-specific route IDs, nonconsecutive stop sequences and dated calendars.
Tests cover mixed sources, per-line timeout isolation, snapshot generations,
calendar exceptions, midnight service, exact LED bytes, transactional failure,
reader consistency, offline upgrade, OS-lock recovery and deterministic rebuilds.
Frontend tests verify mixed labels, serialized polling and generation reloads.
Live TTC availability is not a CI dependency.
