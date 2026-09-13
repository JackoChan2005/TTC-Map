@echo off
REM TTC-Map - start the server (Windows). Double-click or run start.bat
REM uv creates the virtualenv and installs dependencies on first run, so there
REM is no separate setup step. Press Ctrl+C to stop.
cd /d "%~dp0"
uv run ttcmap serve
pause
