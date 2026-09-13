# ESP32 smoke test

1. Copy `firmware/include/secrets.h.example` to `firmware/include/secrets.h` and set the
   Wi-Fi profiles plus the laptop's LAN URL. The local file is ignored by Git.
2. From the repository root, start the API on the laptop with
   `uv run ttcmap serve --host 0.0.0.0`. Port `8000` is the default. The server
   must be reachable from the ESP32; do not put `localhost` in `TTC_FRAME_URL`.
3. Check the binary contract from another device on the same network:

   ```text
   GET /api/v1/led-state.bin?map=rev-a
   ```

   It returns packed bytes with `ETag`, `X-Led-Count`, `X-Generated-At`, and
   `X-Source` headers. Repeating the request with `If-None-Match` should return
   `304` when the frame is unchanged.
4. Build with `pio run --project-dir firmware`, then flash the `firmware`
   PlatformIO project and open the monitor at 115200 baud. The
   expected sequence is Wi-Fi association, an `RX frame` line, decoded LED
   indices, a 74HC595 latch line, then periodic `HTTP 304` lines.

Never commit `firmware/include/secrets.h`; it contains local credentials and the
LAN address.

The project uses a 2 MB flash layout to match the checked-in SDK configuration;
this does not measure the chip's physical capacity. Keep that setting aligned when
regenerating sdkconfig. The current rev-a consumer drives eight LEDs through two
four-bit register groups. Compilation verifies neither wiring nor Wi-Fi operation.

On Windows, PlatformIO may be installed by its editor extension without being on
PATH. Its usual command is `%USERPROFILE%\.platformio\penv\Scripts\platformio.exe`;
use the PlatformIO terminal if it is installed elsewhere.
