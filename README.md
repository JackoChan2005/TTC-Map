# The beginning of the TTC display
PCB to display the TTC subway routes and realtime positions
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
4. Install dependencies:
```bash
pip install -r requirements.txt
```
5. Move to src:
```bash
cd .\API\src\
```
6. Run update_db.py:
```bash
python .\update_db.py
```
7. To view the api run
```bash
Fastapi dev .\main.py
```
