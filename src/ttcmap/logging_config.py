"""Logging setup shared by the server and the CLI."""

import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=FORMAT)
    # the NTAS recorder issues 148 requests every 30s; at INFO httpx logs a line
    # for each and buries everything else
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
