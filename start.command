#!/bin/bash
# TTC-Map — start the server (macOS/Linux). Double-click in Finder or run ./start.command
# uv creates the virtualenv and installs dependencies on first run, so there is
# no separate setup step. Press Ctrl+C to stop.
cd "$(dirname "$0")"
exec uv run ttcmap serve
