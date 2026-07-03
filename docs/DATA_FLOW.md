# How the data flows (plain-language guide)

This project shows where Toronto's subway trains are right now — on a web map,
and eventually on a physical board with LED lights. This page explains where
the data comes from, how it moves through the system, and why it's built this
way. No programming knowledge needed.

## The two kinds of information

Think of a train station: there's a printed **timetable** on the wall, and a
live **departures board** overhead.

1. **The timetable (schedule data).** The City of Toronto publishes the TTC's
   full subway schedule as open data. It changes only every few weeks.
2. **The departures board (live data).** The TTC's "next train" service tells
   us, for every platform, how many minutes until the next trains arrive. We
   ask it every 30 seconds and use the answers to work out where trains are.

## The journey of the data

```
 City of Toronto open data          TTC "next train" service
   (the timetable)                    (the live departures)
        │                                   │
        ▼                                   ▼
 Python downloads and             Node asks every 30 seconds
 organizes it into a              and saves ONE fresh snapshot
 schedule database                into a realtime database
        │                                   │
        └───────────────┬───────────────────┘
                        ▼
              the map engine picks:
        live snapshot if it's fresh,
        otherwise the schedule as a stand-in
                        ▼
        ┌───────────────┴───────────────┐
        ▼                               ▼
   web map in your browser        LED board (in progress)
```

## The rules the system follows

**Only re-download the timetable when it actually changes.** Every few hours
we ask the city "has the schedule been updated?" — a tiny question. Only if
the answer is yes do we download the whole thing again. (It used to
re-download everything every minute, which was wasteful.)

**Keep exactly one live snapshot, never a stale one.** Each 30-second check
replaces the previous snapshot completely. If a check fails — the TTC service
is down, the internet hiccups — the snapshot is marked bad **immediately**,
and the map switches to showing scheduled positions instead (labelled as a
simulation, so you're never misled into thinking it's live). The moment a
check succeeds again, live positions return.

## Why two separate databases?

Each half of the system owns its own filing cabinet:

- **`API/db/SubwaySystem.db`** — the timetable. Only the Python downloader
  writes to it; everything else just reads.
- **`node-api/data/realtime.db`** — the live snapshot and housekeeping notes.
  Only the Node server writes to it.

With one writer per file, the two halves can never trip over each other —
the map keeps working even while a schedule update is being written. It also
makes problems easy to trace: if schedule data looks wrong, look at the
Python side; if live data looks wrong, look at the Node side.

## Why "fall back" instead of failing?

The schedule is a good guess at where trains *should* be, even when we can't
see where they *actually* are. Showing a clearly-labelled simulation beats
showing an empty map — and the switch happens automatically, in both
directions, with no one needing to restart anything.
