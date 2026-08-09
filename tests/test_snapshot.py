"""Ported from node-api/test/snapshotSource.test.js.

The JS version also asserted that an unparseable polled_at is rejected; here
polled_at is a datetime, so that case cannot occur and has no test.
"""

from datetime import UTC, datetime, timedelta

from ttcmap.map.recorder import Snapshot
from ttcmap.map.sources.snapshot import snapshot_is_usable

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
MAX_AGE_S = 90.0


def snapshot_at(seconds_ago: float, status: str = "ok") -> Snapshot:
    return Snapshot(polled_at=NOW - timedelta(seconds=seconds_ago), status=status, positions=[])


def test_fresh_ok_snapshot_is_usable():
    assert snapshot_is_usable(snapshot_at(30), NOW, MAX_AGE_S) is True


def test_snapshot_at_exactly_max_age_is_still_usable():
    assert snapshot_is_usable(snapshot_at(90), NOW, MAX_AGE_S) is True


def test_stale_snapshot_is_rejected_even_when_status_is_ok():
    assert snapshot_is_usable(snapshot_at(91), NOW, MAX_AGE_S) is False


def test_error_snapshot_is_rejected_immediately_regardless_of_age():
    assert snapshot_is_usable(snapshot_at(1, status="error"), NOW, MAX_AGE_S) is False


def test_missing_snapshot_is_rejected():
    assert snapshot_is_usable(None, NOW, MAX_AGE_S) is False
