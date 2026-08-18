# How the data flows (plain-language guide)

This project shows where Toronto's subway trains are right now on both a web
map and an ESP32-driven LED board. This page explains where the data comes
from, how it moves through the system, and what happens when realtime data is
unavailable.

## The two kinds of information

Think of a train station: there is a printed **timetable** on the wall and a
live **departures board** overhead.

1. **Schedule data.** The City of Toronto publishes the TTC's full subway
   schedule as open data. It changes only every few weeks.
2. **Realtime data.** The TTC's next-train service reports how many minutes
   remain until trains reach each platform. The app polls it every 30 seconds
   and converts those countdowns into positions between stations.

## The journey of the data

```text
 City of Toronto open data          TTC next-train service
       (schedule)                       (realtime)
           |                                 |
           v                                 v
 GTFS refresh stores data in       recorder keeps one fresh
 data/ttc.db and rebuilds the      snapshot in memory
 shared network topology
           |                                 |
           +----------------+----------------+
                            v
               the Python map engine picks:
          fresh realtime when it is available,
             otherwise a schedule simulation
                            |
                            v
                    one MapState frame
                            |
                 +----------+----------+
                 v                     v
          web map in a browser   packed LED bitmask
                                      |
                                      v
                              ESP32 and 74HC595s
```

Everything runs in one Python service started with `uv run ttcmap serve`.
The web map and the firmware consume different representations of the same
MapState, so they cannot disagree about where a train is.

## The rules the system follows

**Only rebuild the timetable when it changes.** Every six hours the service
checks the city's feed metadata. It downloads and rebuilds `data/ttc.db` only
when the published feed has changed. The rebuild uses staging tables and a
transaction, so requests keep reading the previous complete schedule until
the replacement is ready.

**Never serve stale realtime positions.** Each successful 30-second poll
replaces the in-memory snapshot. If a poll fails or the snapshot becomes more
than 90 seconds old, the map engine immediately switches to the schedule
simulation and labels the response as a fallback. Live positions return after
the next healthy poll.

**Keep display details outside the map engine.** The web renderer uses a
layout file, while the LED renderer uses `hardware/led-maps/<revision>.json` to
turn occupied stations into packed bits. Adding a board revision changes the
mapping file rather than the train-position logic.

## How the LED board receives a frame

The ESP32 requests `/api/v1/led-state.bin?map=rev-a`. A successful response is
a compact bitmask: one bit per physical LED. The response also includes an
`ETag`; the firmware sends it with the next request so an unchanged frame can
return `304 Not Modified` without shifting the same data again.

If the laptop becomes unreachable, the firmware holds the last valid frame
for a configured grace period and then blanks the outputs so an old display
is not mistaken for current train data. See `docs/FIRMWARE_API.md` for the wire
contract and `docs/ESP32_SMOKE_TEST.md` for setup steps.
