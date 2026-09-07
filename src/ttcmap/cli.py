"""Command line entry point: `uv run ttcmap <command>`."""

import argparse
import asyncio
import sys

from ttcmap.config import get_settings
from ttcmap.logging_config import configure as configure_logging


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "ttcmap.app:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
    )
    return 0


def _refresh(args: argparse.Namespace) -> int:
    from ttcmap.db import init_schema
    from ttcmap.gtfs.refresh import refresh

    init_schema()
    result = asyncio.run(refresh(force=args.force))
    print(f"{result.status}: {result.message}")
    return 0 if result.status != "error" else 1


def _build_network(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ttcmap.gtfs.ckan import feed_input
    from ttcmap.gtfs.network import write_network
    from ttcmap.gtfs.refresh import active_metadata
    from ttcmap.gtfs.refresh_lock import refresh_lock

    with refresh_lock():
        if args.data_dir:
            write_network(Path(args.data_dir))
        else:
            active, _, _ = active_metadata()
            with feed_input(None, active.get("feedCache")) as (directory, _):
                write_network(directory)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    parser = argparse.ArgumentParser(prog="ttcmap", description="TTC Map API")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API and web frontend")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    serve.set_defaults(func=_serve)

    refresh = sub.add_parser("refresh", help="check the GTFS feed and rebuild if it changed")
    refresh.add_argument("--force", action="store_true", help="rebuild even if unchanged")
    refresh.set_defaults(func=_refresh)

    build = sub.add_parser(
        "build-network", help="regenerate shared/network.json from the extracted feed"
    )
    build.add_argument(
        "--data-dir", help="explicit extracted GTFS directory; defaults to verified cache"
    )
    build.set_defaults(func=_build_network)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
