@echo off
REM TTC-Map - start the server (Windows). Double-click or run start.bat
REM Keep the virtual environment outside the repository. OneDrive can turn
REM files under .venv into read-only reparse points that uv cannot update.
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo Error: uv is not installed or is not available on PATH.
    echo Install it from https://docs.astral.sh/uv/ and try again.
    pause
    exit /b 1
)

if not defined LOCALAPPDATA (
    echo Error: LOCALAPPDATA is not defined.
    pause
    exit /b 1
)

set "UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\TTC-Map\venv"
uv sync --link-mode copy
if errorlevel 1 (
    echo Error: dependency setup failed.
    pause
    exit /b 1
)

uv run --no-sync ttcmap serve
set "TTCMAP_EXIT=%ERRORLEVEL%"
pause
exit /b %TTCMAP_EXIT%
