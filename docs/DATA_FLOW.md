# How rail data reaches the displays

The application supports Lines 1, 2, 4, 5 Eglinton and 6 Finch West. All five
have scheduled positions. NTAS is enabled for 1/2/4 by default. Line 5 can be
enabled after coverage validation; Line 6 is scheduled only.

```text
Toronto merged GTFS ZIP                 TTC NTAS platform countdowns
         |                                         |
verified cache + isolated extraction    bounded, fair per-line polling
         |                                         |
validate schedules, calendars,          immutable per-line observations
station identities and layout           with dataset generation + time
         |                                         |
SQLite transaction publishes            reject failed, stale or
schedule + active_dataset               mismatched-generation observations
         |                                         |
         +-------------- map state ----------------+
                         |
             one selected source per line
                         |
                web map + LED bitmask
```

A refresh imports only the five public rail line numbers. Lines 5 and 6 use
GTFS route type 0; ordinary streetcars also use type 0 and are excluded. Public
line numbers and stable station IDs are independent of TTC's feed-specific IDs.
The reviewed crosswalk is `shared/stations.json`.

The published SQLite dataset contains stop times, base service calendars,
date-specific exceptions, topology and both layouts. All change in one commit.
Each map computation reads them in one transaction, so a concurrent refresh
cannot combine yesterday's topology with today's schedule. The generation hash
covers schedule/calendar content, topology, layouts and importer inputs.

The schedule source applies Toronto service dates, calendar validity and holiday
exceptions. It includes the previous service day's departures above 24:00.
Positions are departure-to-departure estimates, including dwell in the segment
span; the simulator uses local civil-clock seconds, including on DST dates.

NTAS predictions are arrival countdowns, not GPS locations or durable vehicle
identities. Polling has a shared concurrency limit and a 25-second HTTP deadline.
Completed lines remain usable when another line times out. HTTP success alone is
not sufficient: payload association and coverage are checked per direction.
A failed line loses live positions immediately; observations expire after 90
seconds. The arrival cutoff expands to cover the published segment durations.

Automatic mode chooses exactly one source for each line. `lineSources` explains
the choice and `source` is `ntas`, `schedule`, or `mixed`. A deliberately scheduled
line is not an outage. Empty predictions during scheduled operating service cause
labelled estimates, not a claim that service is actually running or suspended.
If a required schedule is unavailable, the endpoint returns 503 instead of an
apparently successful partial map.

The browser loads `/api/v1/map-config` for matching topology/layout/generation,
and reloads it when map-state generation changes. It serializes polling and
clears train markers on failed updates. The existing LED bit layout is unchanged;
new-line trains can light existing interchange LEDs, but new physical stations
need a verified board mapping. See [FIRMWARE_API.md](FIRMWARE_API.md).
