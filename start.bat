@echo off
setlocal
REM ============================================
REM  TTC-Map - Start server (Windows)
REM  Starts the Node server and opens the
REM  frontend in your browser when it's ready.
REM  Press Ctrl+C to stop.
REM ============================================
cd /d "%~dp0node-api"

set PORT=3000
for /f "tokens=2 delims==" %%a in ('findstr /b "PORT=" env.config') do set PORT=%%a

echo Starting TTC-Map server on http://localhost:%PORT% ...
echo (the browser opens automatically once the server is ready -
echo  the first start syncs data and can take a few minutes)

REM Background watcher: opens the browser once the port accepts connections.
start "" /b powershell -NoProfile -Command ^
  "$ok = $false; for ($i = 0; $i -lt 1800 -and -not $ok; $i++) { Start-Sleep -Milliseconds 500; try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('localhost', %PORT%); $ok = $c.Connected; $c.Close() } catch {} }; if ($ok) { Start-Process 'http://localhost:%PORT%' }"

call npm.cmd start
