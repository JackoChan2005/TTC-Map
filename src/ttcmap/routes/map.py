"""Map configuration, state and LED endpoints."""

from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from ttcmap.db import read_dataset
from ttcmap.map import SOURCES, get_map_state
from ttcmap.map.topology import load_layout, load_topology
from ttcmap.renderers.led import etag_for, load_led_map, render_led_state

router = APIRouter()


def _parse_at(at: str | None) -> datetime | None:
    if not at:
        return None
    try:
        return datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(400, 'Query parameter "at" must be a valid date/time') from error


def _validate_source(source: str | None) -> str | None:
    if source and source != "auto" and source not in SOURCES:
        raise HTTPException(400, f'Unknown source "{source}". Use auto, schedule or ntas.')
    return source


@router.get("/map-config")
def get_map_config() -> dict:
    try:
        with read_dataset() as dataset:
            return {
                "generation": dataset.generation,
                "network": dataset.network,
                "layout": dataset.payload["layouts"]["schematic"],
            }
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/network")
def get_network() -> dict:
    try:
        return load_topology()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(503, str(error)) from error


@router.get("/layout/{name}")
def get_layout(name: str) -> dict:
    try:
        layout = load_layout(name)
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if layout is None:
        raise HTTPException(404, f'Layout "{name}" not found')
    return layout


async def _state_or_503(source: str | None, at: str | None = None):
    """Return 503 when the requested source or its fallback is unavailable."""
    try:
        return await get_map_state(now=_parse_at(at), source=_validate_source(source))
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(503, f"Source unavailable: {error}") from error


@router.get("/map-state")
async def get_map_state_route(source: str | None = None, at: str | None = None) -> dict:
    state = await _state_or_503(source, at)
    return state.as_dict()


async def _render(map_name: str, source: str | None) -> tuple[dict, dict]:
    try:
        led_map = load_led_map(map_name)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if led_map is None:
        raise HTTPException(404, f'LED map "{map_name}" not found')

    state = await _state_or_503(source)
    return led_map, render_led_state(state, led_map)


@router.get("/led-state")
async def get_led_state(map: str = Query("rev-a"), source: str | None = None) -> dict:
    _, rendered = await _render(map, source)
    return {k: v for k, v in rendered.items() if not k.startswith("_")}


@router.get("/led-state.bin")
async def get_led_state_bin(
    request: Request, map: str = Query("rev-a"), source: str | None = None
) -> Response:
    """Raw packed bitmask — no JSON parser needed on the ESP32.

    Exactly ceil(ledCount / 8) bytes, LSB-first within each byte. Send the ETag
    back as If-None-Match to get a 304 and skip unchanged frames.
    """
    led_map, rendered = await _render(map, source)
    packed: bytes = rendered["_packed"]
    etag = etag_for(packed, led_map["name"])

    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "X-Generated-At": rendered["generatedAt"],
        "X-Source": rendered["source"],
        "X-Led-Count": str(rendered["ledCount"]),
    }

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return Response(content=packed, media_type="application/octet-stream", headers=headers)
