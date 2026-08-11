"""The recorder's failure handling.

Covers the two rules the LED board depends on: a failed poll must record an
`error` snapshot (so serving falls back rather than showing stale positions),
and a hanging feed must not block the recorder past one cycle.
"""

import asyncio

import pytest

from ttcmap.config import get_settings
from ttcmap.map import recorder


@pytest.fixture(autouse=True)
def clear_snapshot():
    recorder.set_snapshot(None)
    yield
    recorder.set_snapshot(None)


async def test_successful_poll_records_an_ok_snapshot(monkeypatch):
    async def fake_positions():
        return ["a", "b"]

    monkeypatch.setattr(recorder.ntas, "get_train_positions", fake_positions)

    snapshot = await recorder.poll_once()
    assert snapshot.status == "ok"
    assert snapshot.positions == ["a", "b"]
    assert recorder.get_snapshot() is snapshot


async def test_failed_poll_records_an_error_snapshot(monkeypatch):
    async def boom():
        raise RuntimeError("NTAS unavailable: only 0/148 platforms responded")

    monkeypatch.setattr(recorder.ntas, "get_train_positions", boom)

    snapshot = await recorder.poll_once()
    assert snapshot.status == "error"
    assert snapshot.positions == []


async def test_hanging_feed_is_abandoned_at_the_poll_deadline(monkeypatch):
    """Without the deadline this would block for
    (platforms / concurrency) x request-timeout — far past the poll interval."""

    async def hang():
        await asyncio.sleep(60)

    monkeypatch.setattr(recorder.ntas, "get_train_positions", hang)
    monkeypatch.setattr(get_settings(), "ntas_poll_timeout_s", 0.05)

    snapshot = await asyncio.wait_for(recorder.poll_once(), timeout=5)
    assert snapshot.status == "error"
    assert snapshot.positions == []
