from datetime import UTC, datetime

from ttcmap.map.toronto_time import get_service_windows, get_toronto_parts


def test_daytime_instant_maps_to_toronto_clock_seconds_and_weekday():
    parts = get_toronto_parts(datetime(2026, 6, 10, 15, 0, tzinfo=UTC))
    assert parts.day == "wednesday"
    assert parts.sec == 11 * 3600


def test_service_windows_include_the_previous_day_shifted_by_24h():
    # 01:30 Thursday also belongs to Wednesday service as 25:30.
    windows = get_service_windows(datetime(2026, 6, 11, 5, 30, tzinfo=UTC))
    assert (windows[0].day, windows[0].sec) == ("thursday", 5400)
    assert (windows[1].day, windows[1].sec) == ("wednesday", 5400 + 86400)


def test_winter_instant_uses_standard_time_offset():
    # Winter time catches fixed UTC offsets that summer tests miss.
    parts = get_toronto_parts(datetime(2026, 1, 14, 15, 0, tzinfo=UTC))
    assert parts.day == "wednesday"
    assert parts.sec == 10 * 3600
