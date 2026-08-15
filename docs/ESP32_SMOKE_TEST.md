# ESP32 smoke test

1. Copy `TTC/include/secrets.h.example` to `TTC/include/secrets.h` and set the
   Wi-Fi profiles plus the laptop's LAN URL. The local file is ignored by Git.
2. Start the Node server on the laptop (`PORT=3000 npm start` from `node-api`).
   The server must be reachable from the ESP32; do not use `localhost`.
3. Check the binary contract from another device on the same network:

   ```text
   GET /api/v1/led-state.bin?map=rev-a
   ```

   It returns packed bytes with `ETag`, `X-Led-Count`, `X-Generated-At`, and
   `X-Source` headers. Repeating the request with `If-None-Match` should return
   `304` when the frame is unchanged.
4. Flash the `TTC` PlatformIO target and open the monitor at 115200 baud. The
   expected sequence is Wi-Fi association, an `RX frame` line, decoded LED
   indices, a 74HC595 latch line, then periodic `HTTP 304` lines.

Never commit `TTC/include/secrets.h`; it contains local credentials and the
LAN address.
