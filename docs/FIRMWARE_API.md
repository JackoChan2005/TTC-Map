# Firmware API

The contract between the ESP32 and the server. Designed so the firmware needs no JSON parser
and a fixed-size buffer.

## The endpoint

```
GET /api/v1/led-state.bin?map=rev-a
```

| | |
|---|---|
| Response | `200 application/octet-stream`, exactly `ceil(ledCount / 8)` bytes |
| `ETag` | Content hash of the frame. Send back as `If-None-Match` to get `304` |
| `X-Led-Count` | Number of LEDs the board revision declares |
| `X-Generated-At` | ISO 8601 timestamp of the frame |
| `X-Source` | `ntas` (realtime) or `schedule` (simulation) |

`?map=` selects a board revision; it must match `^[a-z][a-z0-9-]*$` and name a file in
`hardware/led-maps/`. Unknown names return `404`. `rev-a` is the default.

`?source=schedule` forces the schedule simulation — useful for bench testing when you want
deterministic, always-populated output regardless of whether NTAS is up.

## Bit layout

LED index `i` lives in **byte `i / 8`, bit `i % 8`** — LSB first within each byte.

For `rev-a` (8 LEDs, one byte), with D1 and D4 lit:

```
on          = [0, 3]
byte 0      = 0b00001001 = 0x09
             │      │└──── bit 0 → LED 0 (D1, Finch)
             │      └───── bit 3 → LED 3 (D4, St George)
             └── bit 7 → LED 7 (D8, Don Mills)
```

Reading it back out:

```c
bool led_is_on(const uint8_t *frame, int index) {
    return (frame[index / 8] >> (index % 8)) & 1;
}
```

Note this is one bit per LED, LSB-first, while the TLC5947 takes 12 grayscale bits per
channel, OUT23 first and MSB first. Walk the indices with `led_is_on()` and build the
grayscale data yourself — do not pass the buffer straight through.

## Suggested poll loop

1. `GET /api/v1/led-state.bin?map=rev-a` with `If-None-Match: <last etag>`.
2. `304` → nothing changed, keep the current display and skip the shift-out.
3. `200` → store the new `ETag`, shift the frame out to the TLC5947 and pulse XLAT.
4. Sleep ~5s. The server refreshes realtime data every 30s, so polling faster than that only
   costs power; slower than ~30s and the board visibly lags the trains.

## Failure behaviour

| Condition | What the server does | What the firmware should do |
|---|---|---|
| NTAS feed down | Serves the schedule simulation, `X-Source: schedule` | Nothing — the frame is still valid |
| GTFS not yet built | `503` with a JSON `{message}` body | Retry with backoff; the first build takes minutes |
| Unknown `?map=` | `404` | Fix the board revision name; do not retry |
| Server unreachable | — | Hold the last frame, retry with backoff. Consider blanking after a few minutes so a frozen display is not mistaken for live data |

## Adding a board revision

Add `hardware/led-maps/<rev>.json`. No server code changes.

```json
{
  "name": "rev-b",
  "description": "Second PCB revision",
  "ledCount": 16,
  "leds": [
    { "index": 0, "designator": "D1", "station": "99992", "stationName": "Finch" }
  ]
}
```

`station` must be a station id from `shared/network.json` — `tests/test_led.py` asserts every
LED maps to a real station, so a typo fails the test suite rather than silently never lighting
up. `GET /api/v1/network` lists the ids alongside their names.
