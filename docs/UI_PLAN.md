# Frontend design plan — minimalist transit map UI

## Goals

Replace the geographic web map with a Mini-Metro-inspired, minimalist main
page. We recreate the *style* (octolinear schematic lines, geometric station
markers, capsule trains, warm flat background) with original assets — no game
artwork is copied.

## Information architecture

| Route | Page | Content |
|---|---|---|
| `/` | Main page | Banner (top 1/6 of viewport) + schematic live map (bottom 5/6) |
| `/search/` | TTC Live Search | Existing departure search (moved from `/`) |
| `/map/` | redirect → `/` | Compatibility with old links |

Banner: project title left, **TTC LIVE SEARCH** button top-right → `/search/`.

## Visual language

- Octolinear geometry: every edge is horizontal, vertical, or 45°; non-grid
  edges are drawn as one diagonal + one straight segment with rounded joins.
- Stations: white fill, dark stroke — **circle** = regular, **square** =
  interchange, **triangle** = terminal.
- Trains: rounded capsules in the line colour, rotated to the segment they
  ride; positions come from the existing `/api/v1/map-state` contract.
- Palette: warm cream background, official TTC line colours, one dark ink.

## Module structure (high cohesion, low coupling)

```
shared/layouts/schematic.json        generated octolinear layout (data)
node-api/scripts/
  lib/schematic.mjs                  pure layout generator (testable)
  build-schematic.mjs                CLI wrapper
node-api/public/
  js/                                ES modules, no DOM (unit-testable in Node)
    geometry.js                      octolinear paths, length, point-at-t
    mapModel.js                      network+layout+state -> view models,
                                     API response validation/sanitization
    format.js                        display formatting
  render/svgMap.js                   DOM-only SVG layer (thin)
  main.js                            page glue: fetch -> validate -> render
  css/site.css                       banner + map page styles
  search/                            moved search page (own html + app.js)
node-api/src/securityHeaders.js      CSP & friends, single concern
```

Coupling points are data contracts only: `network.json`, `layouts/*.json`,
`MapState`. The renderer never reaches into the engine; the engine never knows
a renderer exists. A new visual design = a new layout file; a new city = a new
network.json; nothing else changes.

## Security

Feeds (GTFS, NTAS) and API responses are **untrusted input** — the same
posture as prompt injection in LLM systems: data must never become code or
markup.

- All dynamic text rendered via `textContent`/SVG attributes — never
  `innerHTML` with data.
- `mapModel.validate*` sanitizes API responses: type-checks every field,
  coerces/clamps numbers, drops malformed entries before they reach the DOM.
- Content-Security-Policy (`default-src 'self'`, fonts pinned, `object-src
  'none'`, `frame-ancestors 'self'`), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: SAMEORIGIN`.
- No inline `<style>`/`style=` attributes or inline scripts on new pages, so
  CSP needs no `unsafe-inline`.
- Server-side: parameterized SQL (existing), allow-listed layout/LED-map
  names, validated query params (existing).

## Testing strategy

Pure modules are imported directly by `node --test` (no browser needed):

- `geometry`: straight/diagonal/elbow path shapes, path length,
  point-along-path interpolation + angles, clamping.
- `mapModel`: line path building, station kinds (terminal/interchange/regular
  precedence), train placement (at-station and between), validation rejecting
  malformed/hostile API payloads.
- `schematic` generator: bearing quantization, unit steps, anchor
  preservation, collision avoidance.
- `securityHeaders`: every header asserted on a stub response.

DOM glue (`render/`, `main.js`) stays thin enough that logic bugs land in the
tested modules.

## Scalability

- Layouts, LED maps, and cities are data files; adding one touches no code.
- The schematic generator is deterministic — regenerating after a GTFS update
  is one npm script.
- View models are plain serializable objects: a future canvas/WebGL renderer
  or animation layer consumes the same shapes.
