"""Failure isolation at the real HTTP poll/deadline boundary."""

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from ttcmap.map import recorder
from ttcmap.map.sources import ntas
from ttcmap.map.sources.ntas import LinePoll


@pytest.fixture(autouse=True)
def reset():
    recorder.set_snapshot(None)
    yield
    recorder.set_snapshot(None)


def mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        ntas.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )


async def test_one_line_hanging_preserves_other_completed_lines(rail_feed, monkeypatch):
    network = rail_feed.prepare()[1]["network"]
    monkeypatch.setattr(rail_feed.settings, "ntas_enabled_lines", {"1", "2", "4", "5"})
    monkeypatch.setattr(rail_feed.settings, "ntas_poll_timeout_s", 0.1)
    requested = []

    async def handler(request):
        pid = request.url.path.rsplit("/", 1)[-1]
        requested.append(pid)
        platform = network["platforms"][pid]
        line = platform["line"].removeprefix("line-")
        if line == "5":
            await asyncio.sleep(60)
        return httpx.Response(
            200,
            json=[
                {
                    "line": line,
                    "direction": str(platform["direction"]),
                    "stopCode": pid,
                    "nextTrains": "1, 7",
                }
            ],
        )

    mock_client(monkeypatch, handler)
    results = await asyncio.wait_for(ntas.poll_lines(network, "g", 8), 2)
    assert all(results[line].status == "ok" for line in ("line-1", "line-2", "line-4"))
    assert results["line-5"].status == "error"
    assert not any("p-6-" in pid for pid in requested)
    assert all(results[line].positions for line in ("line-1", "line-2", "line-4"))


async def test_direction_coverage_does_not_hide_invalid_other_direction(rail_feed, monkeypatch):
    network = rail_feed.prepare()[1]["network"]
    monkeypatch.setattr(rail_feed.settings, "ntas_enabled_lines", {"1"})

    async def handler(request):
        pid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200, json=[{"line": "1", "direction": "0", "stopCode": pid, "nextTrains": "1"}]
        )

    mock_client(monkeypatch, handler)
    result = (await ntas.poll_lines(network, "g", 8))["line-1"]
    assert result.valid == (3, 0)
    assert result.status == "error"
    assert not result.positions


async def test_recorder_drops_failed_lines_and_old_generation_floors(monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(recorder, "_poll_context", lambda: ({}, "new", {}))

    async def poll(*_):
        return {
            "line-1": LinePoll("line-1", "new", now, status="ok", reason=None),
            "line-5": LinePoll("line-5", "new", now),
        }

    monkeypatch.setattr(recorder, "poll_lines", poll)
    result = await recorder.poll_once()
    assert result.status == "partial"
    assert result.lines["line-1"].status == "ok"
    assert result.lines["line-5"].positions == ()


async def test_context_failure_immediately_replaces_snapshot(monkeypatch):
    def fail():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(recorder, "_poll_context", fail)
    result = await recorder.poll_once()
    assert result.status == "error" and not result.lines
