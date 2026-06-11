# The beginning of the TTC display
PCB to display the TTC subway routes and realtime positions

Full dependency list: see [DEPENDENCIES.md](DEPENDENCIES.md)

## Setup

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

## Quick Setup (recommended)

Run the automated setup script from the repo root — it creates the Python venv, installs all Python and Node dependencies, and regenerates `requirements.txt` from source:

**Windows (PowerShell / CMD)**
```powershell
python setup.py
```

**macOS / Linux / Git Bash**
```bash
bash Setup/Setup.sh
```

Once the script finishes, skip to [Configure env.config and run](#configure-envconfigconfiguring-envconfig-and-running).

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
python -m venv venv
venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```
4. Install Python dependencies:
```bash
pip install -r requirements.txt
```
5. Install Node dependencies:
```bash
cd node-api
npm install
```
6. **Point the server at your venv's Python.** The Node server runs the
Python GTFS loader during every sync, so in `node-api/env.config` set
`PYTHON_BIN` to your venv's interpreter:
```
# macOS/Linux
PYTHON_BIN=/absolute/path/to/TTC-Map/venv/bin/python
# Windows
PYTHON_BIN=C:\path\to\TTC-Map\venv\Scripts\python.exe
```
If you skip this, `python` may resolve to a system install (e.g. Anaconda)
that doesn't have the required packages, and the sync will fail.

7. Run the first sync (downloads the ~66 MB TTC GTFS feed and builds the
database — takes a few minutes, a successful run reports ~120k records):
```bash
npm run sync
```
8. Start the server and open http://localhost:3000:
```bash
npm start
```

See [instructions.txt](instructions.txt) for API endpoints and troubleshooting.

## Alternative: run the Python FastAPI directly

1. Move to src:
```bash
cd ./API/src/
```
2. Run update_db.py:
```bash
python ./update_db.py
```
3. To view the api run:
```bash
fastapi dev ./main.py
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
Verify that `PYTHON_BIN` in `node-api/env.config` points to the venv interpreter, not a system Python.

**`sqlite3` build fails on macOS**  
Install Xcode Command Line Tools:
```bash
xcode-select --install
```

See [instructions.txt](instructions.txt) for additional API details and troubleshooting.
