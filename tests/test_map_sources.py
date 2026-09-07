from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ttcmap.db import DatasetUnavailable
from ttcmap.map import _compute, get_map_state, recorder
from ttcmap.map.recorder import Snapshot
from ttcmap.map.sources.ntas import LinePoll
from ttcmap.map.state import TrainPosition
from ttcmap.routes.map import router

NOW = datetime(2026, 9, 7, 16, 1, tzinfo=UTC)


def seed_live(artifact, lines=("1", "2", "4")):
    polls = {}
    for line in lines:
        key = "line-" + line
        p = TrainPosition(
            line=key, direction=0, from_station=f"s-{line}-a", to_station=f"s-{line}-b", eta_s=60
        )
        polls[key] = LinePoll(
            key,
            artifact["generation"],
            NOW,
            (p,),
            (3, 3),
            (3, 3),
            prediction_count=1,
            status="ok",
            reason=None,
        )
    recorder.set_snapshot(Snapshot(NOW, polls))
    return polls


def test_mixed_auto_has_one_source_per_line_and_planned_schedule_is_not_fallback(rail_feed):
    artifact = rail_feed.publish()
    seed_live(artifact)
    state = _compute(NOW, "auto")
    assert state.source == "mixed" and not state.fallback
    assert state.lineSources["line-5"]["source"] == "schedule"
    assert state.lineSources["line-6"]["source"] == "schedule"
    assert len([p for p in state.trains if p["line"] == "line-1"]) == 1
    assert len([p for p in state.trains if p["line"] == "line-6"]) == 2
    assert state.generation == artifact["generation"]


def test_failed_line5_falls_back_without_hiding_healthy_old_lines(rail_feed, monkeypatch):
    artifact = rail_feed.publish()
    monkeypatch.setattr(rail_feed.settings, "ntas_enabled_lines", {"1", "2", "4", "5"})
    seed_live(artifact)
    state = _compute(NOW, "auto")
    assert state.source == "mixed" and state.fallback
    assert state.lineSources["line-1"]["source"] == "ntas"
    assert state.lineSources["line-5"]["source"] == "schedule"


def test_strict_ntas_reuses_snapshot_and_reports_excluded_lines(rail_feed):
    artifact = rail_feed.publish()
    seed_live(artifact)
    state = _compute(NOW, "ntas")
    assert state.source == "ntas" and not state.fallback
    assert state.lineSources["line-6"]["source"] is None
    assert {p["line"] for p in state.trains} == {"line-1", "line-2", "line-4"}


def test_no_predictions_and_generation_mismatch_use_schedule(rail_feed):
    artifact = rail_feed.publish()
    polls = seed_live(artifact)
    polls["line-1"] = replace(polls["line-1"], positions=(), prediction_count=0)
    polls["line-2"] = replace(polls["line-2"], generation="old")
    recorder.set_snapshot(Snapshot(NOW, polls))
    state = _compute(NOW, "auto")
    assert state.lineSources["line-1"]["reason"] == "insufficient_predictions"
    assert state.lineSources["line-2"]["source"] == "schedule"
    assert state.lineSources["line-4"]["source"] == "ntas"


def test_predictions_beyond_display_cutoff_do_not_mark_line_unhealthy(rail_feed):
    artifact = rail_feed.publish()
    polls = seed_live(artifact)
    polls["line-1"] = replace(polls["line-1"], positions=(), prediction_count=3)
    recorder.set_snapshot(Snapshot(NOW, polls))
    assert _compute(NOW, "auto").lineSources["line-1"]["source"] == "ntas"


def test_strict_ntas_missing_snapshot_or_empty_enabled_set_is_unavailable(rail_feed, monkeypatch):
    rail_feed.publish()
    with pytest.raises(DatasetUnavailable):
        _compute(NOW, "ntas")
    monkeypatch.setattr(rail_feed.settings, "ntas_enabled_lines", set())
    with pytest.raises(DatasetUnavailable, match="no_realtime_lines"):
        _compute(NOW, "ntas")


async def test_explicit_at_is_scheduled_and_rejects_forced_live(rail_feed):
    seed_live(rail_feed.publish())
    state = await get_map_state(now=NOW)
    assert state.source == "schedule" and not state.fallback
    with pytest.raises(ValueError, match="explicit at"):
        await get_map_state(now=NOW, source="ntas")


def test_map_config_and_state_share_generation_and_expired_fallback_is_503(rail_feed):
    artifact = rail_feed.publish()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    config = client.get("/map-config").json()
    state = client.get("/map-state", params={"at": NOW.isoformat()}).json()
    assert config["generation"] == state["generation"] == artifact["generation"]
    assert len(config["network"]["lines"]) == 5
    response = client.get("/map-state", params={"at": "2027-01-02T12:00:00-05:00"})
    assert response.status_code == 503


def test_snapshot_and_train_positions_are_immutable(rail_feed):
    from dataclasses import FrozenInstanceError

    seed_live(rail_feed.publish())
    snapshot = recorder.get_snapshot()
    with pytest.raises(TypeError):
        snapshot.lines["line-1"] = None
    with pytest.raises(FrozenInstanceError):
        snapshot.lines["line-1"].positions[0].eta_s = 999


@pytest.mark.parametrize("mode", ["auto", "schedule", "ntas"])
def test_health_sources_match_configured_mode(rail_feed, monkeypatch, mode):
    from ttcmap.routes import gtfs

    class Clock:
        @staticmethod
        def now(tz):
            return NOW

    seed_live(rail_feed.publish())
    monkeypatch.setattr(gtfs, "datetime", Clock)
    monkeypatch.setattr(rail_feed.settings, "map_source", mode)
    actual = gtfs.health()["realtime"]["lines"]
    expected = _compute(NOW, mode).lineSources
    assert {key: value["source"] for key, value in actual.items()} == {
        key: value["source"] for key, value in expected.items()
    }
