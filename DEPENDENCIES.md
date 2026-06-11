# Dependencies & Setup (fresh machine)

Everything needed to run the TTC-Map data pipeline and API server.

> **Shortcut:** `setup.bat` (Windows) or `./setup.command` (macOS) in the repo root
> automates sections 2–4 and runs the first sync. Then `start.bat` / `./start.command`
> launches the server and opens the browser. The sections below describe what those
> scripts do, for manual setup or troubleshooting.

## 1. System requirements

| Tool | Version | Notes |
|------|---------|-------|
| Git | any recent | to clone the repo |
| Node.js + npm | Node 18+ (tested on v20.7.0 / npm 10) | runs the API server |
| Python | 3.12 (tested on 3.12.5) | builds the GTFS database |
| Internet access | — | downloads ~66 MB GTFS feed from Toronto Open Data each sync |
| Disk space | ~500 MB free | extracted GTFS files are large (stop_times.txt alone is ~280 MB) |

On macOS, `sqlite3` (the npm package) ships prebuilt binaries; if the prebuild fails you also need Xcode Command Line Tools (`xcode-select --install`). On Windows, use `npm.cmd` instead of `npm` if PowerShell blocks scripts.

## 2. Python dependencies (repo root `requirements.txt`)

| Package | Version |
|---------|---------|
| fastapi | 0.129.0 |
| pandas | 3.0.0 |
| Requests | 2.32.5 |
| SQLAlchemy | 2.0.46 |

Install into a virtual environment:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Node dependencies (`node-api/package.json`)

| Package | Version | Purpose |
|---------|---------|---------|
| express | ^4.18.2 | HTTP server |
| sqlite3 | ^5.1.6 | reads/writes the shared SQLite DB (native module) |
| dotenv | ^16.0.3 | loads `env.config` |
| nodemon | ^2.0.20 | dev only — auto-restart |

Install:

```bash
cd node-api
npm install
```

## 4. Configuration (`env.config` + `.env.local`)

Config is split across two files in `node-api/`:

| File | Tracked? | Purpose |
|------|----------|---------|
| `env.config` | yes | shared defaults — works as committed |
| `.env.local` | no (gitignored) | machine-specific overrides — any variable set here wins |

The Node server spawns the Python GTFS loader during sync, so `PYTHON_BIN`
must point at an interpreter that has the requirements installed.
**The setup scripts (`setup.bat` / `setup.command` / `Setup/Setup.ps1` / `Setup/Setup.sh`)
write this to `.env.local` automatically.** For a manual setup with a venv, create
`node-api/.env.local` containing:

```
PYTHON_BIN=/absolute/path/to/TTC-Map/venv/bin/python   # Windows: ...\venv\Scripts\python.exe
```

The committed defaults (`DATABASE_PATH`, `PYTHON_SYNC_*`) need no changes.

## 5. Run it

Easiest: `start.bat` (Windows) or `./start.command` (macOS) from the repo root —
starts the server and opens the browser automatically. Manually:

```bash
cd node-api
npm run sync    # one-off: download GTFS + build DB (takes a few minutes)
npm start       # starts server on http://localhost:3000 (also syncs on startup)
```

A successful sync reports ~120k records. Data lands in `API/db/SubwaySystem.db`
(`API/data/` and `API/db/` are created automatically).

## 6. Optional — hardware/firmware development only

| Tool | Used for |
|------|----------|
| PlatformIO (with ESP-IDF, target `esp32doit-devkit-v1`) | `TTC/` ESP32 firmware |
| KiCad 7+ | `Hardware/` PCB design files |
