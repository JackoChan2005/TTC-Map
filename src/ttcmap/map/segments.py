"""How long a train takes to travel each segment, measured from the GTFS feed.

NTAS answers "next train in N minutes", which is a countdown to a *destination*,
not a position. Converting one into the other needs the segment's traversal
time: a train 3 minutes from B is halfway along A->B if that run takes 6
minutes, and has not left A yet if it takes 2.

Times are the median over every scheduled trip rather than the mean, because a
handful of rows carry absurd spans (a trip straddling the service-day rollover,
or a short-turn reusing a stop pair) and one of those drags a mean badly.

Departure-to-departure, matching how sources/schedule.py measures progress, so
both sources place a train the same way. That folds the dwell at the far end
into the span; it is a few seconds against a two-minute run.
"""

import logging
from functools import lru_cache

from ttcmap.db import query
from ttcmap.map.topology import load_topology

log = logging.getLogger(__name__)

# Spans outside this range are not real runs — they are service-day rollovers,
# short-turns or data errors. Excluded before the median is taken.
MIN_SPAN_S = 20
MAX_SPAN_S = 900

# Used when a segment has no scheduled trips at all, which happens for pairs
# that only exist in the realtime feed (diversions, non-revenue moves).
DEFAULT_SPAN_S = 120.0

_SQL = """
    SELECT
        a.stop_id AS fromStop,
        b.stop_id AS toStop,
        b.departing_time_sec - a.departing_time_sec AS span,
        COUNT(*) AS n
    FROM SUBWAY_STOP_TIMES a
    JOIN SUBWAY_STOP_TIMES b
      ON b.trip_id = a.trip_id
     AND b.stop_sequence = a.stop_sequence + 1
    WHERE b.departing_time_sec - a.departing_time_sec BETWEEN ? AND ?
    GROUP BY fromStop, toStop, span
"""


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


@lru_cache(maxsize=1)
def segment_spans() -> dict[tuple[str, str], float]:
    """(from_station, to_station) -> median seconds. Direction is implied by order."""
    topology = load_topology()
    platforms = topology["platforms"]

    histograms: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for row in query(_SQL, (MIN_SPAN_S, MAX_SPAN_S)):
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
    return spans


def clear_cache() -> None:
    """Called after a GTFS refresh, alongside topology.clear_cache()."""
    segment_spans.cache_clear()


def span_for(from_station: str, to_station: str | None) -> float:
    if to_station is None:
        return DEFAULT_SPAN_S
    try:
        spans = segment_spans()
    except Exception:  # no database yet — the map still has to render
        log.warning("Segment spans unavailable; falling back to %.0fs", DEFAULT_SPAN_S)
        return DEFAULT_SPAN_S
    return spans.get((from_station, to_station), DEFAULT_SPAN_S)
