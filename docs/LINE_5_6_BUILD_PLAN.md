# Build plan: Lines 5 and 6

Status: implemented for five-line scheduled coverage and opt-in Line 5 NTAS;
Line 5 live-enablement evidence remains an explicit release gate. Based on repository
inspection and TTC feed probes on September 7, 2026. Independently critiqued by
the `staff_plan_review` agent; required revisions and remaining gates are below.

## Intended result and boundaries

The web map and departure search include Lines 1, 2, 4, 5 and 6. All five lines
use the existing GTFS schedule, topology, TrainPosition, interpolation and
MapState pipeline. Line 5 can use the existing NTAS adapter after a coverage
check. Line 6 uses explicitly labelled scheduled positions until a verified
public realtime source becomes available. An NTAS response for a line does not,
by itself, prove that its countdowns come from live observations.

Existing physical LED indices and frame size stay fixed. A train on Line 5 can
occupy an already-mapped interchange such as Kennedy. New physical stations
require a separately verified board mapping; this plan does not invent wiring.

Do not introduce a GTFS-Realtime adapter in this build. The sampled subway trip
updates contained only Lines 1, 2 and 4. It remains a separate future improvement.

## 1. One explicit definition of supported rail lines

**Add `src/ttcmap/gtfs/rail_routes.py`.** Define a single mapping keyed by public
line number, with expected GTFS type: `{"1": 1, "2": 1, "4": 1, "5": 0, "6": 0}`.
Implement `select_rail_routes(routes)` using normalized `route_short_name`, not
`route_type in (0, 1)`. Return the raw GTFS route ID plus the stable application
ID `line-<route_short_name>`. Reject duplicate public line numbers or unexpected
types with an actionable feed-validation error. Require all five lines in a
replacement production dataset; a bad or incomplete download must not delete a
line from the map.

**Change `src/ttcmap/gtfs/build.py::build_stop_times` and
`src/ttcmap/gtfs/network.py::build_network`.** Remove both local
`SUBWAY_ROUTE_TYPE = 1` constants and replace the two type-only filters with the
shared selector. Preserve raw route IDs for feed joins; add `line_id` to the
schedule rows so display identity no longer assumes `route_id == line number`.
Preserve string identifiers when reading routes, trips, stops and parents.

**Change `src/ttcmap/routes/departures.py`.** Resolve the requested public line
number to `line_id` and query that column. `/departures?route=5` and `route=6`
must work even if TTC changes its internal route IDs.

## 2. Stable station identity and complete topology

**Add `shared/stations.json`.** This is a small, reviewed identity registry, not
a second copy of the topology. Seed application station IDs from the committed
`shared/network.json`, preserving all existing `999xx` IDs. Add stable IDs for
new stations, reviewed current GTFS parent-ID crosswalks, and explicit name aliases for renamed stations such as
Dundas/TMU and Eglinton West/Cedarvale. Feed platform and parent IDs remain
crosswalk data; they are not the application identity contract.

**Change `src/ttcmap/gtfs/network.py`.**

- Extend `PLATFORM_SUFFIXES` to include `" - Subway Platform"` and normalize
  names before registry lookup. Prefer GTFS parent relationships; use reviewed
  aliases to resolve parent names into application IDs. Use platform names only
  when a parent is absent. Reject ambiguous or unknown identity mappings rather
  than silently merging stations with the same name or assigning new IDs.
- Replace the traversal-order-dependent `station_id_by_name.setdefault` choice
  with registry resolution. Current feed parents such as Kennedy `43295` must
  resolve to the existing application Kennedy ID `99947`.
- Make `_longest_trip` deterministic: descending stop count, then ascending
  string trip ID. Use a full-length pattern for each direction. Short-turn trips
  must not determine terminal locations.
- Register platforms from **all selected trips**, not only the two longest
  trips. Validate each platform's line and direction assignment. If the feed
  reuses a platform ID incompatibly, fail validation with the conflicting rows;
  do not let dictionary assignment silently overwrite a mapping.
- Check all supported trip station sequences against the canonical direction
  order. Contiguous short-turn subsequences are valid. Reject branching or
  skipped-station patterns requiring an unsupported topology model. If the
  five-line fixture actually contains such a pattern, resolve that concrete case
  before release; do not add a general branching engine speculatively.
- Assert one shared interchange at Cedarvale, Eglinton, Kennedy and Finch West;
  every platform refers to a known station; direction 1 reverses the expected
  line order; no repeated station appears in a canonical line.

**Regenerate `shared/network.json`, `shared/layouts/geographic.json` and
`shared/layouts/schematic.json`.** Use `uv run ttcmap build-network` followed by
`node scripts/build-schematic.mjs` during development. Keep the existing JS
schematic generator as the sole implementation; do not add a Python copy or a
Node requirement to server startup. Visually review the new interchanges and
all 25 Line 5 / 18 Line 6 station positions. Those counts are acceptance checks
for the inspected feed, not permanent assumptions about future extensions.

## 3. Correct scheduled positions and departures

**Change `src/ttcmap/gtfs/build.py`.** Read optional `calendar_dates.txt` into
`SERVICE_EXCEPTIONS(service_id, date, exception_type)`, creating an empty table
when absent. Swap it together with the existing schedule tables. Validate
service references, date formats, duplicate trip/sequence rows and exception
types. Add an ordered per-trip ordinal or explicit next-stop columns while
building the filtered rail rows; do not assume GTFS sequences differ by one.

**Change `src/ttcmap/map/toronto_time.py`.** Add the local service date to
`ServiceWindow`. Derive the previous date by subtracting a day from the Toronto
calendar date, not by subtracting 24 hours from a UTC timestamp. Preserve GTFS
times beyond 24:00. Retain the current civil-clock interpolation model and add
DST-boundary tests; document that this is schedule simulation.

**Add `src/ttcmap/gtfs/service_calendar.py`.** Implement one reusable active
service selection: base weekday service within inclusive start/end dates,
plus date-specific additions, minus date-specific removals. Exception-only
service must work. Keep this selection inside the caller's DB read transaction.

**Change `src/ttcmap/map/sources/schedule.py` and
`src/ttcmap/routes/departures.py`.** Both use that service selector and service
windows. Deduplicate schedule sightings by `(service_date, trip_id)`, not just
trip ID. Departure search must cover the next two minutes across midnight and
include departures encoded above 24:00 on yesterday's service date. Preserve its
existing response shape and limit. Add a line filter to the schedule source so
automatic mode queries only lines requiring scheduled positions.

**Change `src/ttcmap/map/sources/schedule.py` and
`src/ttcmap/map/segments.py`.** Replace `b.stop_sequence = a.stop_sequence + 1`
with the importer-derived next-stop relationship. Preserve current median
departure-to-departure timing. Validate positive spans. Unsupported skipped-stop
patterns fail build validation rather than drawing a direct shortcut. Keep
segment medians across the published feed, cached by generation; date-specific
segment statistics are outside this build.

An expired schedule is unavailable, not a successful empty fallback. Report it
in health and return a clear 503 when a requested frame requires it. A valid
schedule with no active trips is a successful empty result.

## 4. Per-line NTAS polling and honest source selection

**Change `src/ttcmap/config.py` and `.env.example`.** Add an explicit configurable
`ntas_enabled_lines: set[str]` of public line numbers and
`ntas_min_coverage_by_line: dict[str, float]` with defaults
`{"1": 0.5, "2": 0.5, "4": 0.5, "5": 0.9}`. Validate coverage values in
`(0, 1]`. Initially enable `1,2,4`; enable `5` only after
the acceptance probe below. Line 6 remains schedule-only. Do not increase request
concurrency as a response to HTTP 403. Keep the existing 30-second cadence,
5-second request timeout, 25-second cycle deadline and 90-second maximum age
unless measurements justify changing them.
Validate configuration at startup: only 1/2/4/5 may be NTAS-enabled in this
adapter version. Reject unknown values and Line 6 rather than ignoring them.

**Change `src/ttcmap/map/sources/ntas.py`.**

- Replace the flat list result with typed per-line poll results containing
  positions, observation times, expected/valid/failed platform counts per
  direction, and a machine-readable reason.
- Poll only enabled lines. Schedule platform requests fairly across lines so
  Line 5 cannot monopolize the connection pool. Collect completed results before
  the deadline; cancel and await pending tasks. A Line 5 timeout must not discard
  completed Line 1/2/4 observations.
- Validate JSON structure and entry `line`, `direction`, `stopCode` against the
  platform crosswalk. HTTP 200 alone is not usable data. Reject negative ETAs;
  parse all valid nonnegative minutes in order without letting malformed fields
  crash the poll. Test unsorted input explicitly rather than relying on `break`.
- Evaluate coverage per line **and direction**. Centralize a coverage policy with
  a provisional 50% threshold for existing lines, preserving the old numeric
  threshold while preventing one healthy direction from masking a failed one.
  Require 90% for Line 5's initial live-enablement gate. Exclude only verified
  departure-only terminal platforms from that denominator. These thresholds must
  be measured against normal existing-line behavior before rollout; a stricter
  existing-line threshold is a separate explicit tuning change.
- Distinguish valid empty queues from request/schema failures. If an entire line
  has no usable predictions while its valid schedule indicates operating service, mark it
  `insufficient_predictions` and use schedule estimates. Do not describe this as
  a confirmed service outage. Evaluate prediction availability before applying
  the map's ETA display cutoff. Determine operating service from resolved service
  dates and scheduled trip first/last times, including dwell periods, rather than
  whether a simulated train happens to be between two stations at that instant.
- Retain ETA-based interpolation and queue-slot identities. Calculate the needed
  ETA cutoff from validated segment times so a new segment longer than five
  minutes is not made invisible by the existing `ntas_arriving_min=5` default.

**Change `src/ttcmap/map/recorder.py` and
`src/ttcmap/map/sources/snapshot.py`.** Store immutable per-line snapshots with
dataset generation and observation times. Failed lines lose usable positions
immediately; successful lines survive unrelated failures. Reject stale,
future-dated or generation-mismatched observations. Use conservative observation
age, not poll-completion time, so a slow poll does not freshen old data. Carry
progress floors only across matching line, generation and queue-slot identity.

**Change `src/ttcmap/map/__init__.py` and `src/ttcmap/map/state.py`.**

- `source=auto`: choose NTAS or schedule independently for each line and merge
  exactly one source per line. A healthy Line 5 and scheduled Line 6 is normal.
- `source=schedule`: all five lines use the schedule.
- `source=ntas`: use fresh recorder snapshots for NTAS-enabled lines only; expose
  other lines as excluded/unsupported. Return 503 if any configured NTAS-enabled line
  is unhealthy. Do not trigger another full platform fan-out per HTTP request.
  Document this deliberate change from the current direct-fetch behavior.
  Before the first usable poll, return 503. If no lines are enabled, return 503
  with reason `no_realtime_lines_configured`. Unsupported lines do not themselves
  fail the request and never get substituted scheduled trains in this mode.
- Any explicit `at` uses scheduled computation in auto mode; reject an explicit
  combination of `source=ntas` and `at` instead of ageing current observations
  against a historical clock.
- Add `lineSources` and `generation`; derive each train's source by its line to
  avoid redundant metadata. Top-level `source` is
  `ntas`, `schedule`, or `mixed`, based on selected line sources even when a line
  currently has no trains. Set `fallback=true` only when an enabled realtime line
  needed scheduled fallback, not because Line 6 is intentionally scheduled.
- Use explicit unavailable-source errors. If a required fallback cannot be
  calculated, return 503 with the affected line rather than a plausible partial
  frame or silently blanking the line.

## 5. Idempotent refresh and consistent publication

The existing staging-table transaction is worth keeping, but it does not cover
the subsequently written topology files or the later feed-version update.

**Change `src/ttcmap/gtfs/ckan.py`.** Select a ZIP resource by declared format/name
and URL, not merely the first non-datastore resource. Fetch metadata once per
refresh and pass that package through download and version recording. Extract
into a unique staging directory so a missing file cannot be inherited from a
previous download. Validate ZIP members, required files and duplicate basenames.

**Change `src/ttcmap/db.py`, `src/ttcmap/gtfs/build.py` and
`src/ttcmap/gtfs/refresh.py`.** Add a single `active_dataset` row holding topology,
geographic layout, validated schematic layout, generation/content digest, feed
version and importer revision. Stage and validate everything first. Publish the
row, schedule/calendar tables and version metadata in the **same SQLite
transaction**. Keep the prior dataset on any build or validation failure.

The generation digest includes canonical sorted schedule rows, service calendars
and exceptions, topology/layout JSON, registry inputs, and importer revision.
Do not hash transient timestamps or SQLite file bytes. A separate importer revision forces a
one-time rebuild of existing installations even when CKAN's timestamp has not
changed. Subsequent unchanged checks skip rebuilding. Repeating a forced build
on identical inputs produces identical application IDs, rows and artifact JSON,
with the same content generation and no duplicates. Retain a verified downloaded
ZIP with its checksum/manifest after successful publication. When offline, an
importer-only rebuild may use that validated ZIP and its original feed identity;
never claim it is the newest remote feed. Unverified legacy extracted files are
not a cache. A failed attempt leaves the active revision unchanged so retry works.
Specify canonical serialization: fixed column ordering; rows sorted by their
logical primary keys; IDs as strings, times as integers, missing values as JSON
null; sorted JSON keys. A one-second departure change or one calendar exception
must change generation, while shuffled identical source rows must not.

**Change `src/ttcmap/map/topology.py`, `src/ttcmap/map/segments.py` and source
callers.** Read the active dataset and schedule from one short read transaction
for each computation. Pass the connection/dataset context into helpers instead
of opening a fresh connection via every `db.query` call. Never hold this read
transaction while awaiting NTAS HTTP requests. Cache derived topology and segment
spans by generation. Publication invalidates old observations by generation even
if an old poll finishes after the commit.

**Change `src/ttcmap/cli.py`.** `build-network` explicitly generates reviewable
exports from an extracted feed and registry. It does not change the runtime
active dataset. Startup migrates an old database by rebuilding. Until the first
new-format publication succeeds, runtime data endpoints return readiness 503;
do not implement an untested legacy read adapter. Offline upgrades succeed only
with a verified cached artifact; otherwise readiness explicitly reports the
missing input while retry remains possible. Runtime reads must not
silently alternate between DB artifacts and shared files.
Check importer revision before the existing CKAN-error "keep current data"
early return in `refresh()`. A missing revision must not silently skip migration.
For a deployed service, build the new dataset before switching traffic; budget
the initial rebuild explicitly rather than promising uninterrupted first upgrade.

The checked-in schematic is a build input. If a future topology contains station
IDs without coordinates, reject that replacement and retain the last complete
dataset with a visible refresh error. Document the operator command to regenerate
the layout. This deliberately avoids a second layout implementation.

**Change `pyproject.toml` and `uv.lock`; add `src/ttcmap/gtfs/refresh_lock.py`.**
Use a cross-process refresh lock in addition to the current asyncio lock, because
the CLI can refresh while the server is running. Acquire it before staging, use
OS-released locking rather than an unrecoverable marker file, and return a clear
already-refreshing result. Use the native Windows/Unix backends of `filelock`
with `FileLock(<resolved-db-path> + ".refresh.lock", timeout=0)`; all entry points
derive the same lock path from the database path. Acquire and release inside the
same rebuild worker context, including cached-input rebuilds. Unsupported native
backends fail clearly rather than silently selecting a marker-file fallback.
Add the dependency with `uv add filelock` during implementation and commit the
resolved lockfile. The deployment remains one server worker on one host; a
OneDrive folder does not provide multi-host SQLite coordination. See the
[filelock documentation](https://py-filelock.readthedocs.io/en/latest/).
Acquisition order is in-process asyncio guard, OS writer lock, read active
revision, prepare staging, SQLite publish transaction. Release in `finally` and
never delete the lock file as a cleanup step. Test that terminating the lock
owner allows the next process to acquire without manual stale-file removal.

## 6. API, web, hardware and operational visibility

**Change `src/ttcmap/routes/map.py`.** Add `/api/v1/map-config` returning network,
schematic layout and generation together from one read transaction. Retain the
existing network/layout endpoints. Add generation to map-state responses.

**Change `web/main.js`, `web/js/mapModel.js`, `web/js/format.js` and
`web/js/render/svgMap.js`.** Load the combined map config. Recognize `mixed`
instead of coercing every non-NTAS value to `schedule`. Show source by line in
the legend, using wording such as `Line 6: scheduled` and `Line 5: scheduled
(live predictions unavailable)`. On state/config generation mismatch, reload the
config and redraw before displaying that state; discard out-of-order refresh
responses. Do not draw old trains on newly loaded topology.

**Change `web/search/index.html` and `web/search/app.js`.** Describe results as
scheduled departures and include 5/6 in the route examples; keep the existing
search response rendering. It is not a live vehicle search.

**Change `src/ttcmap/routes/gtfs.py`.** Report active generation, importer revision,
schedule validity, last refresh outcome, and each line's configured/selected
source, observation age, coverage and reason. Readiness means a valid published
dataset, not simply that `SUBWAY_STOP_TIMES` exists.

**Review `src/ttcmap/renderers/led.py`, `src/ttcmap/routes/map.py` and
`Hardware/led-maps/rev-a.json`.** Verify preserved station references and exact
LSB-first bit output. Do not reassign LEDs to fit new stations. JSON and
`X-Source` may report `mixed`; audit the actual firmware consumer for enum
assumptions before release. The binary byte count and bit indices do not change.

**Update `README.md`, `docs/DATA_FLOW.md`, `docs/ARCHITECTURE.md` and
`docs/FIRMWARE_API.md`.** Document five-line coverage, source semantics, Line 6's
scheduled status, generation publication, rebuild/rollback procedures, and
hardware coverage limits. Use the actual `Hardware/` directory casing in paths.

## 7. Build sequence and acceptance tests

1. Add reviewed five-line GTFS fixtures and station registry. Implement route
   selection, station resolution, ordered stop adjacency and calendars.
2. Regenerate and visually verify the five-line layouts. Implement transactional
   dataset publication and upgrade detection before enabling the new importer.
3. Implement per-line NTAS results, deadline preservation, snapshots and source
   composition. Initially exercise all five lines in schedule mode.
4. Update API/web source and generation handling. Verify the LED contract.
5. Run bounded live Line 5 acceptance probes at normal service times, including
   both directions, terminals and off-peak operation. Record HTTP/schema success,
   empty responses, cycle duration and 403s. Stop on rate-limit responses; do not
   retry aggressively. Compare changing predictions to TTC's station display
   data where publicly available and document remaining provenance uncertainty.
   Enable Line 5 NTAS only if it meets the documented coverage/deadline policy;
   otherwise ship Line 5 with clearly labelled schedules.

New focused tests:

- `tests/test_gtfs_build.py`: 1/2/4/5/6 included, streetcars and replacement buses
  excluded, raw route ID differs from public number, nonconsecutive sequences,
  calendar exceptions, duplicate/invalid feed rows.
- `tests/test_network.py`: stable old IDs, aliases, missing terminal parents,
  both directions, short turns, all platforms, ambiguous identity rejection,
  deterministic generation under shuffled input rows.
- `tests/test_service_calendar.py`: holiday additions/removals, exception-only
  service, validity boundaries, midnight departure window and >24-hour trips.
- `tests/test_refresh.py`: old-version upgrade with unchanged feed metadata,
  identical repeated refresh, missing/invalid ZIP members, failure immediately
  before commit, successful commit followed by restart, concurrent CLI/server
  refresh, and request readers observing wholly old or wholly new data.
- Extend `tests/test_ntas.py`, `tests/test_recorder.py`, `tests/test_snapshot.py`
  and `tests/test_interpolate.py`: one line timeout preserves others, bad payloads,
  empty queues, direction coverage, cutoff exceeding five minutes, stale/mismatched
  generation, late completion after refresh, Line 6 never polled.
- Extend `tests/test_state.py`, `tests/test_db_to_esp32.py` and `tests/test_led.py`:
  mixed sources, fallback failure 503, zero-service periods, shared interchange
  occupancy, and unchanged packed bytes/ETag behavior.
- Extend `tests/web/mapModel.test.mjs` and `tests/web/schematic.test.mjs`; add
  `tests/web/format.test.mjs` and a controlled frontend reload test for mixed
  labels, generation changes and out-of-order responses.

Run `uv run pytest`, `uv run ruff check src tests`, and
`node --test tests/web/*.test.mjs`. Automated tests use local fixtures and mocked
HTTP; live TTC availability is a recorded acceptance observation, not a CI
dependency. Verify an upgrade from the existing database as well as a clean boot.

Rollback: disable Line 5 in the NTAS-enabled configuration to retain schedules.
For application rollback across the dataset schema change, stop the service and
restore the pre-upgrade SQLite backup with the matching application revision;
do not restore only shared JSON files. Make the backup with SQLite's backup API,
not a raw copy of an active WAL database.

## Independent staff-engineer critique and disposition

The reviewer performed two passes: first against the design and repository,
then against this written plan. Its conclusion after the second pass was that
the design is coherent, conditional on making the remaining contracts explicit.
Those corrections are included above. Implementation validation and the subsequent
code review are recorded below.

| Severity | Critique | Required response in this plan |
| --- | --- | --- |
| Blocker | Per-line health alone cannot isolate a hanging request when the outer timeout discards the entire gather. | Fair bounded scheduling; retain completed results; cancel pending requests; test a Line 5 hang. |
| Blocker | Raw GTFS parent IDs break the existing station/LED contract. | Reviewed identity registry and crosswalk; assert every existing station and LED reference remains stable. |
| Blocker | A populated Line 5 endpoint does not establish reliable live coverage. | Explicit live eligibility; schedules by default until bounded multi-period acceptance evidence exists. |
| Blocker | Separately replaced JSON files and DB tables are not an atomic dataset. | One singleton artifact row in the schedule commit, plus one read transaction per computation. |
| Blocker | Forced NTAS semantics could make every request fail because Line 6 has no live feed. | Only configured live lines are required; excluded lines are reported; startup/no-enabled-lines are explicit 503 cases. |
| High | GTFS stop sequence numbers need not be consecutive. | Build ordered next-stop relationships in both schedule and segment queries; fixture sequences 10/20/30. |
| High | Empty predictions may reflect an actual suspension, not a broken API. | Label fallback as scheduled estimates with an insufficient-predictions reason; never infer a confirmed outage. |
| High | Raising coverage thresholds can silently push established lines onto schedules. | Preserve the existing numeric baseline initially; measure both directions and terminal exclusions; make stricter tuning explicit. |
| High | Calendar exceptions, validity ranges and midnight lookahead are missing. | Shared dated service resolution in map and departures, including previous-day >24-hour departures. |
| High | An importer upgrade can be skipped when the remote feed is unchanged or unreachable. | Revision check before offline early return; verified cached rebuild or explicit migration pending. |
| High | Topology-only hashes miss schedule changes and retain stale derived state. | Hash canonical schedule/calendar/artifact contents; generation-scope caches and observations. |
| High | An asyncio lock does not coordinate the CLI and server processes. | Native OS writer lock at a shared DB-derived path; process-termination recovery test. |
| Medium | A coordinate for every station does not prove Line 5's multi-interchange schematic is readable. | Actual five-line rendering review for crossings, station collisions and labels. |
| Scope | Generic branching, skipped-stop projection, historical datasets and date-aware segment statistics would expand the project. | Reject unsupported concrete patterns, retain one active dataset, and defer those features unless acceptance fixtures prove a need. |

## Release gates and implementation validation

- Complete: reviewed station registry covering 234 platforms and 109 stations;
  all 70 pre-existing station IDs are preserved.
- Complete: deterministic five-line import and rendered schematic inspection
  using the existing generator, with a reproducibility/collision regression test.
  Interactive browser validation was unavailable because no browser was connected.
- Complete: failure-injection and upgrade tests prove the old complete dataset
  survives failed refreshes and healthy live lines survive another line's timeout.
- Recorded Line 5 live acceptance evidence before enabling NTAS for it. If the
  evidence fails, deliver working labelled schedules for both new lines and keep
  the live-enablement gate explicitly open; do not describe full live support as
  completed.

Validation on September 7, 2026: 106 Python tests and 33 frontend tests pass;
Ruff passes. The independent implementation review found and verified a fix
for calendar validity incorrectly accepting an expired line based on unrelated
services. Calendar checks now use each requested line's referenced services.
The reviewer reported no remaining blocking findings. Standalone calendar
imports and Windows process-lock recovery were also corrected and verified.

Real-feed integration: a forced offline rebuild of the verified TTC ZIP published
211,406 schedule rows with the same dataset generation. At September 7, 2026,
12:01 Toronto time, the API returned scheduled trains on all five lines and
12 Line 5 / 9 Line 6 departure matches. Map configuration and state generations
matched; health was ready, and forced NTAS correctly returned 503 before polling.
