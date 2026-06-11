# TTC Map Display

A PCB display showing TTC subway routes and real-time train positions.

Full dependency list: [DEPENDENCIES.md](DEPENDENCIES.md)

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js + npm | 18+ (tested on v20.7.0 / npm 10) |
| Git | any recent |

---

## Quick Start (recommended)

Two scripts in the repo root do everything. **Setup** (one-time) creates the Python venv, installs all Python and Node dependencies, writes `PYTHON_BIN` to a gitignored `node-api/.env.local` so the server uses the venv automatically, and runs the first data sync. **Start** launches the server and opens [http://localhost:3000](http://localhost:3000) in your browser as soon as it's ready.

**Windows** — double-click the file, or run from a terminal in the repo root:
```bat
setup.bat
start.bat
```

**macOS** — double-click in Finder, or run from a terminal in the repo root:
```bash
./setup.command
./start.command
```

Press `Ctrl+C` in the terminal window to stop the server.

> **VS Code tip:** open the `TTC-Map` folder directly (not a parent folder). The editor then auto-detects the `.venv` created by setup and selects it as the Python interpreter.

> Prefer the underlying scripts? `python Setup.py` runs the platform-appropriate setup (without the data sync), and `bash Setup/Setup.sh` / `Setup\Setup.ps1` can be run directly.

---

## Manual Setup

**1. Clone the repository**
```bash
git clone https://github.com/JackoChan2005/TTC-Map.git
cd TTC-Map
```

**2. Create a Python virtual environment**

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**4. Install Node dependencies**
```bash
cd node-api
npm install
```

> **Windows PowerShell note:** if npm scripts are blocked, use `npm.cmd` in place of `npm` throughout.

---

## Configuration and running

The committed `node-api/env.config` holds shared defaults. Machine-specific values go in `node-api/.env.local` (gitignored) — anything set there overrides `env.config`, so you never need to edit the tracked file.

**5. Point `PYTHON_BIN` at your venv**

Create `node-api/.env.local` containing one line (the setup scripts do this for you):

```
# macOS / Linux
PYTHON_BIN=/absolute/path/to/TTC-Map/.venv/bin/python

# Windows
PYTHON_BIN=C:\path\to\TTC-Map\.venv\Scripts\python.exe
```

> The Node server spawns this interpreter on every sync to load the GTFS feed.
> If left as the default `python` from `env.config`, it may resolve to a system
> install (e.g. Anaconda) that lacks the required packages, and the sync will fail.

**6. Run the first sync** (from the `node-api/` directory)

Downloads the ~66 MB TTC GTFS feed and builds the SQLite database. Takes a few minutes; a successful run reports ~120 k records.

```bash
npm run sync
```

Windows PowerShell:
```powershell
npm.cmd run sync
```

**7. Start the server** (from the `node-api/` directory)

```bash
npm start
```

Windows PowerShell:
```powershell
npm.cmd start
```

**8. Open the frontend:** [http://localhost:3000](http://localhost:3000)

---

## Alternative: Python FastAPI only

To run just the FastAPI data pipeline without the Node server:

**1. Activate the virtual environment**

Windows:
```powershell
.venv\Scripts\Activate.ps1
```
macOS / Linux:
```bash
source .venv/bin/activate
```

**2. Build the database**
```bash
cd API/src
python update_db.py
```

**3. Start the API**
```bash
fastapi dev main.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/sync/run` | Trigger a manual sync |
| GET | `/api/sync/status` | Latest sync run status |
| GET | `/api/records?limit=100` | List synced records |
| GET | `/api/records/:sourceKey` | Get record by source key |
| GET | `/api/route-search?route=1` | Search by route number |
| GET | `/api/route-search?route=1&at=<ISO8601>` | Search by route at a specific time (`at` defaults to now) |

---

## Troubleshooting

**PowerShell blocks npm scripts**  
Use `npm.cmd` instead of `npm`.

**Port already in use (EADDRINUSE)**  
```powershell
$env:PORT='3001'; npm.cmd start
```

**Sync fails with import errors / missing packages**  
Verify that `PYTHON_BIN` in `node-api/.env.local` points to the venv interpreter, not a system Python. Re-running the setup script fixes this.

**Port change**  
Add `PORT=3001` (or any port) to `node-api/.env.local` — both the server and the start scripts pick it up.

**`sqlite3` build fails on macOS**  
Install Xcode Command Line Tools:
```bash
xcode-select --install
```

See [instructions.txt](instructions.txt) for additional API details and troubleshooting.
