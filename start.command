#!/bin/bash
# Start the server. Press Ctrl+C to stop.
set -e
cd "$(dirname "$0")"

# Finder-launched terminals may not include uv's default install directory.
if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 1
    fi
fi

uv sync --locked
if [ "$#" -eq 0 ]; then
    set -- serve
fi
exec uv run --no-sync ttcmap "$@"
