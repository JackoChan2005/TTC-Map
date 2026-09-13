@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
    echo Install uv: https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)
if not defined UV_PROJECT_ENVIRONMENT (
    if not defined LOCALAPPDATA exit /b 1
    REM Keep Python dependencies outside OneDrive.
    set "UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\TTC-Map\venv"
)
uv sync --locked --link-mode copy
if errorlevel 1 exit /b 1
if "%~1"=="" (
    uv run --no-sync ttcmap serve
) else (
    uv run --no-sync ttcmap %*
)
set "TTCMAP_EXIT=%ERRORLEVEL%"
if not defined TTCMAP_NO_PAUSE pause
exit /b %TTCMAP_EXIT%
