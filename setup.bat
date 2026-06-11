@echo off
setlocal
REM ============================================
REM  TTC-Map - One-click setup (Windows)
REM  Installs Python + Node deps, configures
REM  env.config, and runs the first data sync.
REM ============================================
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup\Setup.ps1"
if errorlevel 1 (
    echo.
    echo Setup failed. See errors above.
    pause
    exit /b 1
)

echo.
echo Running first data sync...
echo (downloads the ~66 MB TTC GTFS feed and builds the database - takes a few minutes)
cd /d "%~dp0node-api"
call npm.cmd run sync
if errorlevel 1 (
    echo.
    echo Sync failed. Check PYTHON_BIN in node-api\env.config.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete! Run start.bat to launch.
echo ============================================
pause
