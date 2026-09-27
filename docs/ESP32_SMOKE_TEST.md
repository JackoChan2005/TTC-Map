# ESP32 smoke test

To check the 24-channel TLC5947 test PCB without Wi-Fi or the server, use the
separate [TLC5947 acceptance test](../firmware/tlc5947-test/README.md).
The steps below run the production firmware, which drives the same TLC5947.

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
   `304` when the frame is unchanged. `?map=` must name a file in
   `hardware/led-maps/`. This branch has none yet (`rev-a` was removed with the
   74HC595 board), so the server returns `404` until a 24-channel map is added.
4. Flash the `firmware` PlatformIO project and open the monitor at 115200 baud. The
   expected sequence is the self-test (all 24 LEDs lit for one second), Wi-Fi
   association, an `RX frame` line, decoded LED indices, a `TLC5947 latch
   complete` line, then periodic `HTTP 304` lines.

Never commit `firmware/include/secrets.h`; it contains local credentials and the
LAN address.
