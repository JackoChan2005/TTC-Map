# The beginning of the TTC display
PCB to display the TTC subway routes and realtime positions

Full dependency list: see [DEPENDENCIES.md](DEPENDENCIES.md)

## Setup

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
```
3. Activate the virtual environment:
- On Windows:
```bash
venv\Scripts\activate
```
- On macOS/Linux:
```bash
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
