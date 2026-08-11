"""The FastAPI application.

One service replaces the Express server plus the separate FastAPI app. On
startup it checks the GTFS feed (rebuilding only when it changed) and starts the
NTAS recorder, both as background tasks so the server answers requests
immediately — including during the several-minute first-run rebuild.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ttcmap.config import get_settings
from ttcmap.db import init_schema
from ttcmap.gtfs.refresh import refresh, refresh_loop
from ttcmap.logging_config import configure as configure_logging
from ttcmap.map import recorder, topology
from ttcmap.routes import departures, gtfs
from ttcmap.routes import map as map_routes
from ttcmap.security import security_headers

log = logging.getLogger(__name__)


async def _startup_gtfs_check() -> None:
    result = await refresh()
    log.info("GTFS check: %s", result.message)
    if result.updated:
        topology.clear_cache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_schema()

    tasks = [
        asyncio.create_task(_startup_gtfs_check()),
        asyncio.create_task(refresh_loop()),
        asyncio.create_task(recorder.poll_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TTC Map API",
        version="1.0.0",
        summary="Realtime TTC subway state for the web map and the ESP32 LED board",
        lifespan=lifespan,
    )
    app.middleware("http")(security_headers)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        # the Express API answered errors as {message}, and the frontend reads
        # that key; keep the shape rather than churn the client
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> RedirectResponse:
        # browsers request /favicon.ico for any page that declares no icon --
        # /docs, or an API URL opened in a tab. Point them at the real one so
        # the log is not full of 404s.
        return RedirectResponse("/favicon.svg")

    @app.get("/map", include_in_schema=False)
    @app.get("/map/", include_in_schema=False)
    async def legacy_map() -> RedirectResponse:
        """Keep old map bookmarks working after the schematic map moved to `/`."""
        return RedirectResponse("/")

    app.include_router(gtfs.router, prefix="/api/v1", tags=["gtfs"])
    app.include_router(map_routes.router, prefix="/api/v1", tags=["map"])
    app.include_router(departures.router, prefix="/api/v1", tags=["departures"])

    # mounted last so /api/v1 and /docs win
    if settings.web_path.exists():
        app.mount("/", StaticFiles(directory=settings.web_path, html=True), name="web")

    return app


app = create_app()
