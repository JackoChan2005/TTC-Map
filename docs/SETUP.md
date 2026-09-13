# Setup and demo rehearsal

Run from a repository checkout. Web pages, station inputs and board maps live
outside the Python package; installing a wheel alone is not supported.

## Windows

Install uv and reopen the terminal so it is on PATH. The repository selects
Python 3.13; uv installs it if necessary. Initial setup needs internet access.

```powershell
.\start.bat
```

This runs `uv sync --locked --link-mode copy` and starts the CLI using
`%LOCALAPPDATA%\TTC-Map\venv`. The environment is outside the checkout because
OneDrive can lock/reparse files in `.venv`. The launcher does not alter that old
folder. It also respects an explicit `UV_PROJECT_ENVIRONMENT` override.

Equivalent manual setup:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\TTC-Map\venv"
uv sync --locked --link-mode copy
uv run --no-sync ttcmap serve
```

Use `start.bat serve --port 8001` for another port or `start.bat refresh` for a
feed check. `TTCMAP_NO_PAUSE=1` disables the closing prompt in scripted runs.
Do not run two checkouts against the same editable environment: assign a distinct
`UV_PROJECT_ENVIRONMENT` to each. Keep that variable set for subsequent uv test
and CLI commands. In VS Code, select the corresponding `Scripts/python.exe`.

The app defaults to loopback port 8000 and one worker. For ESP32 access on a
trusted LAN, use `serve --host 0.0.0.0` and the laptop's LAN address in the local
firmware configuration. Refresh is CLI-only; there is no HTTP write route.

The database and feed archive default to ignored `data/`. To place them outside
OneDrive too, set both `DATA_DIR` and `DB_PATH` in `.env` to a local directory and
database path before the first refresh. Never share an active SQLite database
across computers through cloud synchronization.

If the first City feed request fails, the server stays up with degraded health.
Run `start.bat refresh` when connectivity returns, then reload the site. A
successful refresh is published atomically and does not require a server restart.

## macOS / Linux

```sh
uv sync --locked
uv run --no-sync ttcmap serve
```

The default LED directory uses the tracked lowercase `hardware/led-maps` path.
The current validation was performed on Windows; this path fix is not a claim
of an executed Linux or macOS test.

## Offline rehearsal

1. While online, run `uv run --no-sync ttcmap refresh` and check
   `/api/v1/health`: the published schedule must be ready for the presentation date.
2. Stop the server. Set `MAP_SOURCE=schedule` in `.env` or the shell, then restart.
   Markers should be outlined and labelled scheduled. This uses real published
   schedules, not a synthetic feed.
3. Disconnect external access and reload `/`, `/search/`, `/docs` and `/redoc`.
   Use the schematic if street tiles are unavailable. The API reference needs
   no external JavaScript or CSS. Try a scheduled departure search.
4. Restore automatic mode for a live demonstration. Lines 5/6 remain scheduled
   by default. Never describe schedule fallback as proof of operational service.

A compatible existing publication survives a metadata outage. An offline importer
upgrade can use the checksum-verified ZIP recorded in the dataset. Neither path
makes expired calendars valid. With no usable publication or cache, transit APIs
return unavailable states; a fresh offline clone is intentionally not populated.
For a backup of a running database use SQLite's backup API, not a raw WAL file copy.

## Tests

After the platform setup above, from the repository root:

```sh
uv run --no-sync pytest
uv run --no-sync ruff check src tests
node --test tests/web/*.test.mjs
git diff --check
```

Node is optional for service startup. Browser tests require the separately pinned
Playwright package. Install it from its own directory:

```sh
cd tests/web
npm ci
npx playwright install chromium
cd ../..
node tests/web/browser-smoke.mjs
node tests/web/map-lod-smoke.mjs
node tests/web/docs-smoke.mjs
```

On PowerShell use `npm.cmd` and `npx.cmd` if script execution policy blocks their
PowerShell wrappers. Set `TTCMAP_URL` for another server port. `CHROME_PATH` can
point to an already-installed compatible Chrome instead of downloading Chromium;
there is no machine-specific executable default. `PLAYWRIGHT_MODULE` is an optional
absolute module override for existing tool installations.

The runners resolve fixtures from the repository root and write ignored results
under `data/ui-validation`. Pan/zoom tests intercept tile images. The separate
`basemap-live.mjs` is a manual, fixed-viewport integration check; do not use public
OSM tiles for repeated automated pan/zoom scans. Transit fixtures are explicitly
test-only and never become application fallback data.

Python TestClient's `httpx2` dependency is locked in the development group to avoid
the deprecated HTTPX compatibility path. Runtime feed requests continue using HTTPX.
There is no JS build/type-check/lint command configured.

If pytest reports `Access is denied` for `%TEMP%\pytest-of-<user>` on Windows,
point `TEMP` and `TMP` at an ignored writable directory for that terminal:

```powershell
New-Item -ItemType Directory -Force data\test-temp | Out-Null
$env:TEMP = "$PWD\data\test-temp"
$env:TMP = $env:TEMP
uv run --no-sync pytest
```

## Hardware and sharing

Follow [ESP32_SMOKE_TEST.md](ESP32_SMOKE_TEST.md) for firmware. A successful compile
does not verify GPIO wiring or a physical display. Optional CAD libraries are
described in [ASSETS.md](ASSETS.md).

Share a reviewed checkout or archive of the intended commit, excluding `.git`,
local captures, `data/`, `.env`, secrets headers and build directories. An archive
of an old commit still contains its old files. Asset removals in this revision do
not erase them from prior history. Resolve the remaining ownership/history questions
in [ASSETS.md](ASSETS.md) before publishing the repository itself.
