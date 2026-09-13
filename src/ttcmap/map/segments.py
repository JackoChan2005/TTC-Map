"""Median scheduled travel times for each directed station pair.

Use departure-to-departure spans, as the schedule source does. Filter outliers
before taking the median; spans include station dwell time.
"""

import logging

from ttcmap.db import Dataset, read_dataset

log = logging.getLogger(__name__)

# Exclude implausible travel times before taking the median.
MIN_SPAN_S = 20
MAX_SPAN_S = 900

# Estimate travel time when no scheduled span is available.
DEFAULT_SPAN_S = 120.0

_SQL = """
    SELECT stop_id AS fromStop, next_stop_id AS toStop,
           next_departing_time_sec - departing_time_sec AS span, COUNT(*) AS n
    FROM SUBWAY_STOP_TIMES
    WHERE next_departing_time_sec - departing_time_sec BETWEEN ? AND ?
    GROUP BY fromStop, toStop, span
"""
_cache: dict[str, dict] = {}


def _weighted_median(histogram: list[tuple[int, int]]) -> float:
    """Median of a span->count histogram, without expanding it row by row."""
    ordered = sorted(histogram)
    total = sum(count for _, count in ordered)
    seen = 0
    for span, count in ordered:
        seen += count
        if seen * 2 >= total:
            return float(span)
    return float(ordered[-1][0])


def segment_spans(dataset: Dataset | None = None) -> dict[tuple[str, str], float]:
    """(from_station, to_station) -> median seconds. Direction is implied by order."""
    if dataset is None:
        with read_dataset() as current:
            return segment_spans(current)
    if dataset.generation in _cache:
        return _cache[dataset.generation]
    platforms = dataset.network["platforms"]

    histograms: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for row in dataset.conn.execute(_SQL, (MIN_SPAN_S, MAX_SPAN_S)):
        origin = platforms.get(str(row["fromStop"]))
        destination = platforms.get(str(row["toStop"]))
        if not origin or not destination:
            continue
        pair = (origin["station"], destination["station"])
        if pair[0] == pair[1]:
            continue
        histograms.setdefault(pair, []).append((row["span"], row["n"]))

    spans = {pair: _weighted_median(hist) for pair, hist in histograms.items()}
    log.info("Measured %d segment traversal times from the schedule", len(spans))
    if len(_cache) >= 2:
        _cache.clear()
    _cache[dataset.generation] = spans
    return spans


def clear_cache() -> None:
    _cache.clear()


def span_for(from_station: str, to_station: str | None) -> float:
    if to_station is None:
        return DEFAULT_SPAN_S
    try:
        spans = segment_spans()
    except Exception:  # no database yet — the map still has to render
        log.warning("Segment spans unavailable; falling back to %.0fs", DEFAULT_SPAN_S)
        return DEFAULT_SPAN_S
    return spans.get((from_station, to_station), DEFAULT_SPAN_S)
