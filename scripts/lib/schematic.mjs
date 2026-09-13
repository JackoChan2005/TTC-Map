// Pure octolinear layout generator: places stations on a unit grid where
// every edge points in one of 8 compass directions. Interchanges anchor
// later lines to positions fixed by earlier ones.

export const DIRECTIONS = [
  [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]
];

// nearest of the 8 compass directions for a screen-space delta (y grows down)
export const quantizeDirection = (dx, dy) => {
  const angle = Math.atan2(dy, dx);
  const index = ((Math.round(angle / (Math.PI / 4)) % 8) + 8) % 8;
  return DIRECTIONS[index];
};

const key = (x, y) => `${x},${y}`;

// walks a line's station list from an anchored index, stepping one grid cell
// per edge in the quantized geographic direction; occupied cells push the
// step outward so stations never collide
const walk = (stations, startIndex, step, geo, positions, occupied) => {
  for (let i = startIndex + step; i >= 0 && i < stations.length; i += step) {
    const current = stations[i];
    const previous = stations[i - step];
    if (positions[current] || !positions[previous]) {
      continue;
    }

    const gCur = geo[current];
    const gPrev = geo[previous];
    if (!gCur || !gPrev) {
      continue;
    }

    const [ux, uy] = quantizeDirection(gCur.x - gPrev.x, gCur.y - gPrev.y);
    let [x, y] = positions[previous];
    do {
      x += ux;
      y += uy;
    } while (occupied.has(key(x, y)));

    positions[current] = [x, y];
    occupied.add(key(x, y));
  }
};

export const buildSchematicPositions = (network, geoLayout) => {
  const geo = geoLayout.stations;
  const positions = {};
  const occupied = new Set();

  for (const line of network.lines) {
    const stations = line.stations;
    let anchors = stations
      .map((s, i) => (positions[s] ? i : -1))
      .filter((i) => i >= 0);

    if (anchors.length === 0) {
      positions[stations[0]] = [0, 0];
      occupied.add(key(0, 0));
      anchors = [0];
    }

    walk(stations, anchors[0], -1, geo, positions, occupied);
    for (const anchor of anchors) {
      walk(stations, anchor, +1, geo, positions, occupied);
    }
  }

  return positions;
};

export const fitToCanvas = (positions, { width = 1000, margin = 40 } = {}) => {
  const xs = Object.values(positions).map(([x]) => x);
  const ys = Object.values(positions).map(([, y]) => y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const spanX = Math.max(Math.max(...xs) - minX, 1);
  const spanY = Math.max(Math.max(...ys) - minY, 1);

  const cell = (width - 2 * margin) / spanX;
  const height = Math.round(spanY * cell + 2 * margin);

  const stations = {};
  for (const [id, [x, y]] of Object.entries(positions)) {
    stations[id] = {
      x: Math.round((x - minX) * cell + margin),
      y: Math.round((y - minY) * cell + margin)
    };
  }

  return { name: 'schematic', width, height, stations };
};

export const buildSchematicLayout = (network, geoLayout, options) =>
  fitToCanvas(buildSchematicPositions(network, geoLayout), options);
