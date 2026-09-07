"""Toronto service-day helpers.

Ported from node-api/src/map/torontoTime.js. This logic previously existed three
times (also in API/src/main.py and node-api/src/routes.js, each subtly
different); this is now the only copy.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")

WEEKDAY_COLUMNS = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)


@dataclass(frozen=True)
class ServiceWindow:
    day: str
    sec: int
    date: str = ""


def get_toronto_parts(moment: datetime) -> ServiceWindow:
    """Weekday name and seconds-since-midnight in Toronto local time."""
    local = moment.astimezone(TORONTO_TZ)
    return ServiceWindow(
        date=local.strftime("%Y%m%d"),
        day=local.strftime("%A").lower(),
        sec=local.hour * 3600 + local.minute * 60 + local.second,
    )


def get_service_windows(moment: datetime) -> list[ServiceWindow]:
    """The windows a query must check to catch late-night service.

    GTFS encodes after-midnight trips as >24:00:00 on the *previous* service
    day, so 01:30 Thursday is also 25:30 Wednesday. Both are returned.
    """
    today = get_toronto_parts(moment)
    yesterday = moment.astimezone(TORONTO_TZ).date() - timedelta(days=1)
    return [
        today,
        ServiceWindow(
            day=yesterday.strftime("%A").lower(),
            date=yesterday.strftime("%Y%m%d"),
            sec=today.sec + 86400,
        ),
    ]
