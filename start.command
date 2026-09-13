#!/bin/bash
# Start the server. Press Ctrl+C to stop.
cd "$(dirname "$0")"
exec uv run ttcmap serve
