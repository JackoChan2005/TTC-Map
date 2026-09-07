"""Compose one source per line using a consistent published dataset."""

import asyncio
from datetime import UTC, datetime

from ttcmap.config import get_settings
from ttcmap.db import DatasetUnavailable, read_dataset
from ttcmap.map import interpolate, recorder
from ttcmap.map.segments import segment_spans
from ttcmap.map.sources.snapshot import snapshot_is_usable
from ttcmap.map.state import MapState, compute_map_state

SOURCES = ("schedule", "ntas")


def _compute(now: datetime, mode: str) -> MapState:
    from ttcmap.map.sources import schedule

    settings = get_settings()
    snapshot = recorder.get_snapshot()
    with read_dataset() as dataset:
        selected, positions, scheduled = {}, [], set()
        spans = segment_spans(dataset)
        if mode == "ntas" and not settings.ntas_enabled_lines:
            raise DatasetUnavailable("no_realtime_lines_configured")
        for line in dataset.network["lines"]:
            key = line["id"]
            enabled = key.removeprefix("line-") in settings.ntas_enabled_lines
            live = snapshot.lines.get(key) if snapshot else None
            reason = None
            usable = snapshot_is_usable(live, now, generation=dataset.generation)
            if mode != "schedule" and enabled and usable and live.prediction_count == 0:
                if key in schedule.operating_lines(dataset, now, {key}):
                    usable, reason = False, "insufficient_predictions"
            if mode == "ntas" and not enabled:
                selected[key] = {"source": None, "reason": "realtime_not_enabled"}
                continue
            if mode != "schedule" and enabled and usable:
                positions.extend(
                    interpolate.advance(
                        list(live.positions), (now - live.polled_at).total_seconds(), spans
                    )
                )
                selected[key] = {"source": "ntas", "reason": None}
            else:
                reason = reason or (live.reason if live and live.reason else "snapshot_unavailable")
                if mode == "ntas":
                    raise DatasetUnavailable(f"{key}: {reason}")
                scheduled.add(key)
                selected[key] = {
                    "source": "schedule",
                    "reason": reason
                    if enabled and mode == "auto"
                    else "forced_schedule"
                    if mode == "schedule"
                    else "realtime_not_enabled",
                }
        if scheduled:
            positions.extend(schedule.get_train_positions(now, dataset=dataset, lines=scheduled))
        sources = {s["source"] for s in selected.values() if s["source"]}
        state = compute_map_state(
            dataset.network,
            positions,
            source=next(iter(sources)) if len(sources) == 1 else "mixed",
            generated_at=now.isoformat(),
        )
        state.lineSources = selected
        state.generation = dataset.generation
        state.fallback = mode == "auto" and any(
            key.removeprefix("line-") in settings.ntas_enabled_lines for key in scheduled
        )
        return state


async def get_map_state(now: datetime | None = None, source: str | None = None) -> MapState:
    mode = source or get_settings().map_source
    if mode not in ("auto", *SOURCES):
        raise ValueError(f"Unknown map source: {mode}")
    if now is not None:
        if mode == "ntas":
            raise ValueError("An explicit at time requires scheduled computation")
        if now.tzinfo is None:
            from ttcmap.map.toronto_time import TORONTO_TZ

            now = now.replace(tzinfo=TORONTO_TZ)
        mode = "schedule"
    return await asyncio.to_thread(_compute, now or datetime.now(UTC), mode)
