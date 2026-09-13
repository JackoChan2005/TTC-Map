# Validation

Latest cleanup validation: September 13, 2026, Windows, Python 3.13.15 and Node 22.
See [SETUP.md](SETUP.md) for reproducible setup and [ASSETS.md](ASSETS.md) for
the remaining ownership decisions.

## Automated checks

| Check | Result |
|---|---|
| `uv sync --locked --link-mode copy` in a fresh environment | Passed; editable project built from the lockfile |
| `python -m pytest -p no:cacheprovider --basetemp=data/review/pytest-readiness-20260913` | 108 passed without warnings |
| `python -m ruff check src tests` | Passed |
| `node --test tests/web/*.test.mjs` | 41 passed; six obsolete renderer tests were removed |
| `node tests/web/browser-smoke.mjs` | Passed on the updated app and fresh source clone |
| `node tests/web/map-lod-smoke.mjs` | Passed transfer labels, collisions, zoom detail, marker bounds and tile failure |
| `node tests/web/docs-smoke.mjs` | Passed local assets, all reference URLs, GET execution, mobile and schema failure states |
| PlatformIO build with example configuration | Passed; 896,661 bytes flash and 34,528 bytes RAM |

Python checks used a separate environment under
`%LOCALAPPDATA%/TTC-Map/readiness-venv`. Browser checks used locked Playwright
1.63.0 and installed Chrome through `CHROME_PATH`, with `TTCMAP_URL` set to the
test server. See SETUP for the default Chromium installation. Pan and zoom tests
intercept tiles; no repeated real-tile scan was performed.

## Clean-clone launch

The uncommitted working source was copied into an isolated snapshot repository,
committed there only, and cloned with `git clone --no-local` into an ignored
validation directory. This tests the changed source, not the previous remote
branch. No original Git metadata, local captures, private assets, environment,
cache or database was copied. The temporary commit did not change this branch.

The final clean-clone rehearsal used `start.bat serve --host 127.0.0.1 --port
8010` and a new environment at
`%LOCALAPPDATA%/TTC-Map/boot-verification-20260913-2`. It used the installed uv
executable and package cache; this was not a new operating-system installation.
The first startup feed request failed transiently while City metadata remained
reachable. The server stayed available with degraded health. The documented
`start.bat refresh` retry then published 109 stations and valid schedules for all
five lines without restarting the server. No transit fixture populated the
application data. The server health became `ok`; its process-local `lastRefresh`
field retained the earlier startup error even though the published dataset and
per-line health fields reflected the successful external refresh.

The clean-clone Python run initially encountered a pre-existing Windows ACL error
under `%TEMP%\pytest-of-zhouj`. Pointing `TEMP` and `TMP` at the checkout's ignored
`data/test-temp` directory produced the recorded 108-pass result. SETUP documents
that workaround.

With feed origins deliberately pointed to a refusing local port, the prepared
dataset still returned HTTP 200 with scheduled positions. An empty data directory
returned degraded health and map-state 503. These checks simulate external-service
failure; they do not claim the machine was physically disconnected. The API
reference rendered while all external browser requests were blocked.

## Browser coverage

Directly loaded `/`, `/index.html`, `/search`, `/search/`, `/search/index.html`,
`/map`, `/map/`, and route/station selections for Lines 1/2/4/5/6. Real timetable
queries for all five lines returned 200. The local API reference rendered at
`/docs`, `/redoc`, `/api/` and `/api/index.html`; `/openapi.json` remains available.

Checked navigation and back, line/station search, direction selection, scheduled
countdowns, dialogs, settings, zoom, fit, geographic/schematic mode and panel
controls. Tested 1440×900, 768×1024, 390×844 and 320×640. Browser fixtures cover
empty data, missing fields/coordinates, departure 404/503, state failure clearing
markers and tile outages. All eight interchange labels remain at wide zoom. No
unexpected console, runtime or network errors occurred in successful runs.

The final browser run used the clean-clone server and current City data. It
reported 109 stations, 119 positions at capture time, live NTAS observations for
Lines 1/2/4, scheduled estimates for Lines 5/6, and successful departure queries
for all five lines. A visible browser check confirmed the geographic basemap,
coloured routes, directional train markers, departure results and both API
reference URLs. Browser warning/error logs were empty.

The rider UI calls `/api/v1/map-config`, `/api/v1/map-state`,
`/api/v1/departures` and `/api/v1/health`. The reference can issue existing GET
endpoints. Tests confirm the removed HTTP refresh route is absent from OpenAPI and
rejects POST.

## Scope

The September 12 map integration check loaded 35 real OSM tiles in one fixed
viewport with attribution and referrers. The README screenshot comes from that
session; current counts naturally differ. It is not a data fixture.

There is no JavaScript build, type checker or linter configured. A standalone
wheel is unsupported because repository resources are required. Linux, macOS,
physical GPIO and Wi-Fi connection behavior were not tested.

The successful firmware build initially reported a 4 MB PlatformIO board default
against the checked-in 2 MB SDK layout. `board_upload.flash_size = 2MB` now aligns
that metadata. PlatformIO's builder source confirms this setting controls the
comparison. A repeat build after the one-line correction could not acquire the
user-level PlatformIO lock from the sandbox; the full compile immediately before
the correction passed. Re-run the documented build outside the sandbox before
flashing hardware.
