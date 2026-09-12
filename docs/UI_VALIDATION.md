# Redesign validation

Initial redesign validated on September 11, with the geographic-map refinement
validated on September 12, 2026 (America/Toronto). The application is
served by its existing FastAPI CLI at `http://127.0.0.1:8000/`.

## Commands and results

The existing Windows launcher environment was used because this repository's
README warns against updating the OneDrive-managed `.venv`.

| Command | Result |
|---|---|
| `& "$env:LOCALAPPDATA/TTC-Map/venv/Scripts/python.exe" -m pytest` | 106 passed. One existing Starlette/httpx deprecation warning from the installed backend test dependencies. |
| `& "$env:LOCALAPPDATA/TTC-Map/venv/Scripts/python.exe" -m ruff check src tests` | Passed. |
| `node --test tests/web/*.test.mjs` | 47 passed, including platform joins, countdown aging, atomic config, Web Mercator projection, directional tangents, missing-coordinate/direction fallbacks, tile bounds and label collisions. |
| `Get-Content -Raw web/main.js \| node --input-type=module --check` | Passed. |
| `Get-Content -Raw web/js/render/explorerMap.js \| node --input-type=module --check` | Passed. Other ES modules were parsed by the browser and unit tests. |
| `node tests/web/browser-smoke.mjs` | Passed in installed Chrome, headless. |
| `node tests/web/map-lod-smoke.mjs` | Passed: wide-to-close zoom, all eight interchanges retained, label collision checks, marker bounds, neutral direction fallback and tile outage. Tiles intercepted in this test. |
| `node tests/web/basemap-live.mjs` | Passed: one fixed viewport loaded 35 actual OSM tiles, with valid origin referrers, directional overlays and no runtime errors. No automated pan/zoom against the public tile service. |
| `git diff --check` | Passed. |
| `python -m ttcmap.cli refresh` using the above environment | Published the real complete five-line dataset. |
| `python -m ttcmap.cli serve --port 8000` using the above environment | Successful startup, real GTFS/NTAS integration verified. |

There is no frontend build, type-checker, package-manager build script, or JS
linter configured in this vanilla-JavaScript project. No such checks are claimed.

The browser connector was unavailable. Optional Playwright was downloaded into
the gitignored `data/ui-validation/` directory and used with installed Chrome;
no runtime or root package dependency was added. Reproduce with
`npm.cmd install --prefix data/ui-validation --cache data/ui-validation/npm-cache --no-audit --no-fund --package-lock=false playwright`,
then `node tests/web/browser-smoke.mjs`. The runner accepts `PLAYWRIGHT_MODULE`,
`CHROME_PATH` and `TTCMAP_URL` environment overrides.

## Route coverage

Loaded every static frontend document and public alias individually:

- `/` and `/index.html`.
- `/search`, `/search/`, `/search/index.html` (the slashless URL redirects).
- `/map` and `/map/` (existing redirects to `/`).
- `/?line=1`, `/?line=2`, `/?line=4`, `/?line=5`, `/?line=6`.
- All five lines with a valid `&station=<id>` selection using actual topology.
- `/search/?line=1`, `2`, `4`, `5`, `6`, including real timetable submissions.

`/docs`, `/redoc`, and `/openapi.json` are framework API documentation, not
redesigned rider-facing frontend routes. No new server-side route was added.

## API integration and actual data

At the final run, the real API returned 109 stations with a mixed source:
NTAS on Lines 1/2/4, schedules on Lines 5/6 (`realtime_not_enabled`). All five
real timetable queries returned HTTP 200 and rendered schedule cards. Counts
and train positions naturally change over time; the report captures the sample.

The first startup had no published database or verified offline cache, and its
unavailable UI was tested without mocks. Enabling network access for the existing
refresh/server commands resolved that local setup limitation. No transit API changes,
credentials, fabricated observations, or alternate transit feeds were used. The
refinement adjusts only CSP/referrer security headers to permit the map provider.

Verified browser requests were exclusively:
`/api/v1/map-config`, `/api/v1/map-state`,
`/api/v1/departures`, and `/api/v1/health`. No nonexistent endpoint was called.
The final run recorded zero unhandled runtime errors, unexpected console errors,
or transport failures. Intentionally injected HTTP 404/503 cases were expected.

## Interaction and failure coverage

- Overview cards, in-place route selection, route fit/dimming, directional station
  order, station selection, transfer navigation and browser back navigation.
- Station/line search, Enter selection, empty results, keyboard focus, and the
  search-to-map transition.
- Zoom in/out, fit, keyboard pan, geographic/schematic toggle, panel collapse.
- About, service diagnostics and settings dialogs; Escape/close; label visibility,
  scheduled-marker filter and light appearance.
- Current-time control, line selection, scheduled results and raw record expansion.
- Browser-only fixtures exercise departure 404/empty/503/missing optional fields,
  state empty/missing optional fields, state outage clearing train markers,
  missing coordinates falling back to the schematic, and tile failures leaving
  the accurate-coordinate transit overlay available.
- 1440×900 desktop, 768×1024 tablet, 390×844 mobile and 320×640 narrow mobile:
  horizontal overflow checks, direct navigation, scrollable panels and screenshots.
  Route details and timetable views remain accessible through the panel scroll area.

The fixture records are explicitly test-only and do not ship in the application.
They use committed topology/layout for visual tests, with synthetic train/departure
observations only inside request interception in `tests/web/browser-smoke.mjs`.

## Evidence and remaining limits

Ignored local evidence in `data/ui-validation/`:

- `report.json`: final routes, endpoint allowlist, real data summary and error counts.
- `real-street-map.png`: real OSM background and actual API-backed transit overlay.
- `basemap-live-report.json`: live tile checks and referrer verification.
- `lod-report.json` and `lod-fixture-{fit,wide,detail}-{width}.png`: zoom and label
  regression evidence. These intentionally use test-only tile images, not geography.
- `real-backend-desktop.png`: actual transit API interface; the automated route
  regression runner now intercepts background tiles to avoid public-service scanning.
- `real-unavailable-desktop.png`: initial genuine backend-unavailable state.
- `fixture-overview-desktop.png`, `fixture-route-desktop.png`, and
  `fixture-overview-{320,390,768,1440}.png`: explicitly fixture-backed visual tests.

No external dependency was still blocking validation at completion. The street
basemap is now connected; OSM tile availability remains best-effort. The design's
missing backend capabilities remain: exact track geometry/GPS, live platform
arrival boards, operational alerts, address/journey planning and longer departure
horizons. Location centering and account/contact flows are not implemented.
See [UI_API_AUDIT.md](UI_API_AUDIT.md) for the exact supported/partial/unsupported
mapping and intentionally unused endpoints.

The September 12 backend run initially encountered an existing Windows
subprocess-lock cleanup timeout, followed by permissions on a sandbox-owned temp
directory. Rerunning with a new isolated temp directory outside the sandbox passed
all 106 tests: `python -m pytest -p no:cacheprovider --basetemp=data/ui-validation/pytest-refinement-run`.
No backend test was weakened or skipped. Ruff passed after the security test
formatting fix. The existing Starlette/httpx deprecation warning remains.
