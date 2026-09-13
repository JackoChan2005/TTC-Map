"""Ported from node-api/test/torontoTime.test.js."""

from datetime import UTC, datetime

from ttcmap.map.toronto_time import get_service_windows, get_toronto_parts


def test_daytime_instant_maps_to_toronto_clock_seconds_and_weekday():
    # 2026-06-10T15:00:00Z is 11:00:00 EDT on a Wednesday
    parts = get_toronto_parts(datetime(2026, 6, 10, 15, 0, tzinfo=UTC))
    assert parts.day == "wednesday"
    assert parts.sec == 11 * 3600


def test_service_windows_include_the_previous_day_shifted_by_24h():
    # 2026-06-11T05:30:00Z is 01:30:00 EDT Thursday — GTFS encodes late-night
    # service as 25:30:00 on Wednesday
    windows = get_service_windows(datetime(2026, 6, 11, 5, 30, tzinfo=UTC))
    assert (windows[0].day, windows[0].sec) == ("thursday", 5400)
    assert (windows[1].day, windows[1].sec) == ("wednesday", 5400 + 86400)


def test_winter_instant_uses_standard_time_offset():
    # 2026-01-14T15:00:00Z is 10:00:00 EST on a Wednesday — catches a hardcoded
    # UTC offset that summer-only tests would miss
    parts = get_toronto_parts(datetime(2026, 1, 14, 15, 0, tzinfo=UTC))
    assert parts.day == "wednesday"
    assert parts.sec == 10 * 3600
