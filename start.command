#!/bin/bash
# ============================================
#  TTC-Map - Start server (macOS)
#  Starts the Node server and opens the
#  frontend in your browser when it's ready.
#  Double-click in Finder or run: ./start.command
#  Press Ctrl+C to stop.
# ============================================
cd "$(dirname "$0")/node-api"

PORT=$(grep -E '^PORT=' env.config | head -1 | cut -d= -f2)
if [ -f .env.local ]; then
  LOCAL_PORT=$(grep -E '^PORT=' .env.local | head -1 | cut -d= -f2)
  [ -n "$LOCAL_PORT" ] && PORT=$LOCAL_PORT
fi
PORT=${PORT:-3000}

echo "Starting TTC-Map server on http://localhost:$PORT ..."
echo "(the browser opens automatically once the server is ready —"
echo " the first start syncs data and can take a few minutes)"

# Background watcher: opens the browser once the port accepts connections.
(
  for _ in $(seq 1 1800); do
    if nc -z localhost "$PORT" 2>/dev/null; then
      open "http://localhost:$PORT"
      exit 0
    fi
    sleep 0.5
  done
) &
WATCHER_PID=$!
trap 'kill $WATCHER_PID 2>/dev/null' EXIT

npm start
