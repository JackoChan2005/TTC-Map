import { octolinearPoints, pointAlongPath } from './geometry.js';

export const BASE_ZOOM = 12;
export const WORLD_SIZE = 256 * 2 ** BASE_ZOOM;

export function project(lat, lon) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 85.05112878 || Math.abs(lon) > 180) return null;
  const sin = Math.sin(lat * Math.PI / 180);
  return { x: (lon + 180) / 360 * WORLD_SIZE,
    y: (.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * WORLD_SIZE };
}

export function geographicLayout(network) {
  const entries = Object.entries(network.stations).map(([id, station]) => [id, project(station.lat, station.lon)]);
  if (!entries.length || entries.some(([, point]) => !point)) return null;
  const xs = entries.map(([, p]) => p.x), ys = entries.map(([, p]) => p.y);
  const originX = Math.min(...xs) - 80, originY = Math.min(...ys) - 80;
  return { width: Math.max(...xs) - originX + 80, height: Math.max(...ys) - originY + 80, originX, originY,
    stations: Object.fromEntries(entries.map(([id, p]) => [id, { x: p.x - originX, y: p.y - originY }])) };
}

export const zoomLevel = unit => BASE_ZOOM - Math.log2(unit);
export function detailLevel(zoom) {
  return zoom < 10.8 ? 'wide' : zoom < 12 ? 'network' : zoom < 13.2 ? 'local' : 'detail';
}

// Direction 0 follows canonical line.stations; direction 1 reverses it.
// At a terminal, use the incoming tangent, never invent a reversal/departure.
export function trainGeometry(train, network, layout, geographic) {
  const line = network.lines.find(line => line.id === train.line);
  if (!line) return null;
  const point = id => layout.stations[id];
  const segment = (a, b) => geographic ? [a, b] : octolinearPoints(a, b);
  const known = train.direction === 0 || train.direction === 1;
  let p, angle = null;
  if (train.at) {
    if (!line.stations.includes(train.at)) return null;
    p = point(train.at);
    const order = train.direction === 1 ? [...line.stations].reverse() : line.stations;
    const index = order.indexOf(train.at);
    if (known && p && index >= 0) {
      const next = point(order[index + 1]), previous = point(order[index - 1]);
      if (next) angle = pointAlongPath(segment(p, next), 0).angle;
      else if (previous) angle = pointAlongPath(segment(previous, p), 1).angle;
    }
  } else if (train.between) {
    const [from, to] = train.between;
    const a = point(from), b = point(to);
    if (!a || !b || !line.stations.includes(from) || !line.stations.includes(to)) return null;
    p = pointAlongPath(segment(a, b), train.progress);
    // The backend serializes between=[from,to] in travel order. Only show an
    // arrow when the explicit direction agrees, otherwise show a neutral dot.
    const forward = line.stations.indexOf(to) > line.stations.indexOf(from);
    if (known && forward === (train.direction === 0)) angle = p.angle;
  }
  if (!p) return null;
  const terminal = known ? network.stations[train.direction === 0 ? line.stations.at(-1) : line.stations[0]]?.name : null;
  return { ...p, angle, line, terminal };
}

export function visibleTiles(layout, box, unit) {
  const z = Math.max(0, Math.min(19, Math.round(zoomLevel(unit))));
  const tileSize = 256 * 2 ** (BASE_ZOOM - z), count = 2 ** z;
  const minX = Math.max(0, Math.floor((layout.originX + box.x) / tileSize));
  const maxX = Math.min(count - 1, Math.floor((layout.originX + box.x + box.w) / tileSize));
  const minY = Math.max(0, Math.floor((layout.originY + box.y) / tileSize));
  const maxY = Math.min(count - 1, Math.floor((layout.originY + box.y + box.h) / tileSize));
  const tiles = [];
  for (let x = minX; x <= maxX; x++) for (let y = minY; y <= maxY; y++) {
    tiles.push({ key: `${z}/${x}/${y}`, x: x * tileSize - layout.originX, y: y * tileSize - layout.originY, size: tileSize });
  }
  return tiles;
}

const overlaps = (a, b) => a.x < b.x + b.w + 4 && a.x + a.w + 4 > b.x && a.y < b.y + b.h + 3 && a.y + a.h + 3 > b.y;

// Reserve interchange labels first. Nearby crowded labels get leader lines;
// never discard a transfer label to make room for an ordinary station.
export function placeLabels(items, bounds) {
  const placed = [];
  const inside = b => b.x >= bounds.x && b.y >= bounds.y && b.x + b.w <= bounds.x + bounds.w && b.y + b.h <= bounds.y + bounds.h;
  for (const item of [...items].sort((a, b) => Number(b.interchange) - Number(a.interchange) || b.priority - a.priority)) {
    const w = Math.min(item.width, bounds.w), h = 15;
    const candidates = [];
    for (const dy of [-7, -24, 12, -41, 29]) {
      candidates.push({ x: item.x + 10, y: item.y + dy, w, h }, { x: item.x - w - 10, y: item.y + dy, w, h });
    }
    if (item.interchange) {
      const grid = [];
      for (let y = bounds.y; y + h <= bounds.y + bounds.h; y += 19) {
        for (let x = bounds.x; x + w <= bounds.x + bounds.w; x += 10) grid.push({ x, y, w, h });
      }
      grid.sort((a, b) => Math.hypot(a.x + w / 2 - item.x, a.y - item.y) - Math.hypot(b.x + w / 2 - item.x, b.y - item.y));
      candidates.push(...grid);
    }
    const position = candidates.find(candidate => inside(candidate) && !placed.some(other => overlaps(candidate, other)));
    if (position) placed.push({ ...item, ...position, stationX: item.x, stationY: item.y });
  }
  return placed;
}
