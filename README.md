# TTC Map

TTC rail state for Lines 1, 2, 4, 5 Eglinton and 6 Finch West, served to two displays: a web map and an ESP32-driven
LED board on a custom PCB.

```
Toronto Open Data (GTFS)  ─┐
                           ├─► ttcmap API ─┬─► web frontend (SVG map + route search)
TTC NTAS (realtime)       ─┘               └─► ESP32 / LED board (packed bitmask)
```

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.12+.
Nothing else — no separate setup step, no virtualenv to activate.

```bash
uv run ttcmap serve
```

Or double-click `start.command` (macOS/Linux) / `start.bat` (Windows). The Windows
launcher keeps its virtual environment in `%LOCALAPPDATA%\TTC-Map\venv` so that
OneDrive cannot make installed packages read-only.

Then open <http://localhost:8000> for the map and <http://localhost:8000/docs> for the
interactive API reference.

The first run downloads the ~84 MB GTFS feed and builds the database, which takes a few
minutes. The server answers requests while that happens; the map falls back to whatever data
it has. Later runs check whether the feed changed and start in seconds when it has not.

## Commands

| Command | What it does |
|---|---|
| `uv run ttcmap serve` | Run the API and web frontend |
| `uv run ttcmap refresh` | Check the GTFS feed, rebuild if it changed (`--force` to rebuild anyway) |
| `uv run ttcmap build-network` | Regenerate shared exports from the verified cache (`--data-dir` for an explicit extract) |
| `uv run pytest` | Run the test suite |
| `uv run ruff check src tests` | Lint |
| `node --test tests/web/*.test.mjs` | Run frontend tests (optional Node.js) |
| `node scripts/build-schematic.mjs` | Regenerate the schematic layout (optional Node.js) |

## API

All endpoints are under `/api/v1`. Full schemas at `/docs`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Service, GTFS and realtime status |
| GET | `/api/v1/map-config` | Matching topology, schematic layout and generation |
| GET | `/api/v1/network` | Canonical topology — lines, stations, platforms |
| GET | `/api/v1/layout/{name}` | Station x/y for a visual design (`schematic`, `geographic`) |
| GET | `/api/v1/map-state` | Train positions. `?source=auto\|schedule\|ntas`, `?at=<ISO8601>` |
| GET | `/api/v1/led-state` | LED frame as JSON. `?map=rev-a` |
| GET | `/api/v1/led-state.bin` | LED frame as a raw bitmask — see [docs/FIRMWARE_API.md](docs/FIRMWARE_API.md) |
| GET | `/api/v1/departures` | Next departures. `?route=1&at=<ISO8601>` |
| GET | `/api/v1/gtfs/status` | Feed version and last refresh result |
| POST | `/api/v1/gtfs/refresh` | Trigger a check. `?force=true` to rebuild regardless |

`map-state` selects data per line: NTAS for healthy enabled lines and labelled
scheduled estimates for the others. Lines 1/2/4 use NTAS by default. Line 5 is
opt-in after coverage validation; Line 6 is schedule-only. Mixed responses carry
`source: "mixed"` and `lineSources`; a configured live line falling back sets
`fallback: true`. Failed/stale observations are never retained as live positions.
`source=ntas` reuses fresh recorder snapshots, excludes disabled lines and returns
503 when an enabled line is unavailable. An explicit `at` uses schedules;
combining it with `source=ntas` is invalid.

The browser uses `/api/v1/map-config` to load a matching network, layout and
generation. Schedules, date exceptions and runtime topology publish in one SQLite
transaction. If an old installation has not completed its first upgraded build,
data endpoints return 503 until publication succeeds. See
[upgrade and rollback instructions](docs/ARCHITECTURE.md#refresh-and-upgrade-operations).

## Layout

| Path | Contents |
|---|---|
| `src/ttcmap/` | The API — GTFS pipeline, map state engine, sources, renderers, routes |
| `web/` | Static frontend (schematic SVG map + route search) |
| `scripts/` | Dependency-free schematic layout generator |
| `firmware/` | ESP32 firmware (PlatformIO, ESP-IDF, `esp32doit-devkit-v1`) |
| `Hardware/` | KiCad project and `led-maps/` board revisions |
| `shared/` | Station registry and generated network/layout exports |
| `tests/` | pytest suite |
| `data/` | Gitignored: GTFS extract and `ttc.db` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together and
[docs/FIRMWARE_API.md](docs/FIRMWARE_API.md) for the ESP32 contract.

## Configuration

Everything has a working default; the app runs with no config at all. To override, copy
`.env.example` to `.env` and uncomment what you need. The full list of settings is
`src/ttcmap/config.py`.

## Troubleshooting

**Port already in use** — `uv run ttcmap serve --port 8001`, or set `PORT` in `.env`.

**`Topology not found` / `503` from `/api/v1/network`** — the first GTFS refresh has not
finished. Check progress in the server log, or run `uv run ttcmap refresh` directly.

**Map shows "schedule simulation (realtime unavailable)"** — TTC's NTAS feed is unreachable or
returned too few platforms. This is expected behaviour, not a failure; the map keeps working
from the schedule. `/api/v1/health` shows the last poll result.

**Rebuild seems stuck** — the pandas merge over `stop_times.txt` (~280 MB extracted) takes
several minutes. It runs off the event loop, so the API stays responsive.
