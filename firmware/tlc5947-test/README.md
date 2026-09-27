# TLC5947 test PCB acceptance test

Standalone Arduino/PlatformIO firmware using [Adafruit TLC5947](https://github.com/adafruit/Adafruit_TLC5947).
It exercises the 24-LED test PCB without Wi-Fi or API setup.

## Wiring

From `hardware/test_pcb/production/netlist.ipc` and the ESP32 schematic symbol:

| TLC5947 signal | ESP32 GPIO | ESP32 U2 pad |
| --- | --- | --- |
| SIN | 23 | 30 |
| SCLK | 18 | 24 |
| XLAT | 16 | 21 |
| BLANK | 17 | 22 |

OUT0..OUT23 correspond to D1..D24. BLANK is active high. The test blanks
outputs while writing each complete frame. Brightness starts at 256/4095.

## Run

From the repository root with PlatformIO installed:

```powershell
pio run -d firmware/tlc5947-test
pio run -d firmware/tlc5947-test -t upload
pio device monitor -b 115200 --echo
```

If multiple serial devices are connected, specify `--upload-port COMx` on
upload and `--port COMx` on the monitor. Upload replaces the ESP32's running
firmware. Open the monitor, send `t` followed by Enter, and watch the PCB.
The suite takes about 51 seconds; serial commands are processed after it finishes.

## Expected observations

1. All LEDs off for two seconds.
2. D1 through D24 light individually for one second each. Exactly one LED
   lights, with the previous LED turning off at every step.
3. Each fixture below holds for 2.5 seconds. Only the listed LEDs should light.

| Frame bytes (hex) | Expected LEDs | Purpose |
| --- | --- | --- |
| `800100` | D8, D9 | Cross first byte boundary |
| `008001` | D16, D17 | Cross second byte boundary |
| `010080` | D1, D24 | First and last channels |
| `090000` | D1, D4 | Two simulated trains |
| `120000` | D2, D5 | Both trains advance; D1/D4 clear |
| `100000` | D5 | First train leaves |
| `555555` | Odd-numbered LEDs | Alternating channels |
| `aaaaaa` | Even-numbered LEDs | Complement; old channels clear |
| `ffffff` | All 24 | Simultaneous outputs |
| `000000` | None | All trains leave |

Pass only if every observed pattern matches, with no extra, missing, or
lingering LEDs. Record failures by frame and physical LED designator.
The completion message means frames were sent, not that the hardware passed:
the board provides no optical feedback to this firmware.

## Hold a frame for inspection

Send six hex digits followed by Enter, e.g. `090000` lights D1 and D4 until
another command. Send `x` to clear or `t` to repeat the suite. Invalid input
leaves the current frame unchanged. Hex is three bytes in wire order, with
LED index i in bit i%8 of byte i/8, matching the existing binary API contract.

These are synthetic positions: test slot 0 maps to OUT0/D1, slot 1 to OUT1/D2,
and so on. This verifies output order and moving occupancy patterns. It does
not verify TTC feed accuracy or real station assignments. Before live use,
create a verified 24-channel station map for the production firmware in
`firmware/`, which drives the same pins. For a 24-channel API map, its six-digit
`bits` value can be pasted into this monitor to compare the physical display.
