"""Logging setup shared by the server and the CLI."""

import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=FORMAT)
    # Suppress per-platform HTTP logs so recorder diagnostics remain readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
