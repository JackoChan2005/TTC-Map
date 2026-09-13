# Lines 5 and 6

All five rail lines share the GTFS import, station registry, published dataset
and map-state pipeline. Public line numbers differ from feed route IDs.
Lines 5/6 have route type 0; ordinary streetcars are excluded by public identity.

Line 5 uses schedules by default. Before adding it to `NTAS_ENABLED_LINES`,
record bounded feed checks across both directions, terminals and several operating
periods. Verify payload association, changing predictions, empty queues, coverage
and cycle duration. Stop on rate limiting. A populated response alone does not
establish live provenance or reliable coverage.

The configured Line 5 gate is 90% valid platforms per direction within the poll
deadline. General live use remains unverified. Keep schedules if the gate is not
met. Line 6 is schedule-only; no live adapter is claimed.

Tests cover station identities, short turns, atomic publication, calendars,
source isolation and generation matching. See [ARCHITECTURE.md](ARCHITECTURE.md)
and [UI_API_AUDIT.md](UI_API_AUDIT.md) for current behavior.

The rev-a board retains eight mapped LEDs. New lines can activate existing
interchange LEDs; additional stations require verified wiring and a board map.
