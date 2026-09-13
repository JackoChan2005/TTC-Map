// Validate transit API responses.

const FALLBACK_COLOR = '#1f2937';
const COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

const asString = (value) => (typeof value === 'string' ? value : '');

const asColor = (value) => (COLOR_PATTERN.test(asString(value)) ? value : FALLBACK_COLOR);

const asFiniteNumber = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

export const validateNetwork = (raw) => {
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.lines) || !raw.stations || typeof raw.stations !== 'object') {
    throw new Error('Invalid network payload');
  }

  const stations = {};
  for (const [id, station] of Object.entries(raw.stations)) {
    if (!station || typeof station !== 'object') {
      continue;
    }
    stations[id] = {
      name: asString(station.name) || 'Unknown',
      lat: typeof station.lat === 'number' && Number.isFinite(station.lat) && Math.abs(station.lat) <= 85.05112878 ? station.lat : null,
      lon: typeof station.lon === 'number' && Number.isFinite(station.lon) && Math.abs(station.lon) <= 180 ? station.lon : null,
      interchange: station.interchange === true,
      lines: Array.isArray(station.lines) ? station.lines.map(asString) : []
    };
  }

  const lines = raw.lines
    .filter((line) => line && typeof line === 'object' && Array.isArray(line.stations))
    .map((line) => ({
      id: asString(line.id),
      number: asString(line.number) || asString(line.id).replace('line-', ''),
      routeId: asString(line.routeId),
      textColor: asColor(line.textColor),
      name: asString(line.name) || 'Line',
      color: asColor(line.color),
      stations: line.stations.map(asString).filter((s) => stations[s])
    }));

  return { lines, stations, platforms: raw.platforms || {} };
};

export const validateLayout = (raw) => {
  if (!raw || typeof raw !== 'object' || !raw.stations || typeof raw.stations !== 'object') {
    throw new Error('Invalid layout payload');
  }

  const stations = {};
  for (const [id, point] of Object.entries(raw.stations)) {
    if (!point || typeof point !== 'object') {
      continue;
    }
    stations[id] = { x: asFiniteNumber(point.x), y: asFiniteNumber(point.y) };
  }

  return {
    width: Math.max(asFiniteNumber(raw.width, 1000), 1),
    height: Math.max(asFiniteNumber(raw.height, 600), 1),
    stations
  };
};

export const validateMapState = (raw) => {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Invalid map state payload');
  }

  const trains = (Array.isArray(raw.trains) ? raw.trains : [])
    .filter((train) => train && typeof train === 'object')
    .map((train) => ({
      line: asString(train.line),
      direction: train.direction === 0 || train.direction === 1 ? train.direction : null,
      at: train.at === null || train.at === undefined ? null : asString(train.at),
      between: Array.isArray(train.between) && train.between.length === 2
        ? [asString(train.between[0]), asString(train.between[1])]
        : null,
      progress: Math.min(Math.max(asFiniteNumber(train.progress), 0), 1),
      stationName: asString(train.stationName)
    }))
    .filter((train) => train.at !== null || train.between !== null);

  return {
    generatedAt: asString(raw.generatedAt),
    source: ['ntas', 'mixed'].includes(raw.source) ? raw.source : 'schedule',
    generation: asString(raw.generation),
    lineSources: Object.fromEntries(Object.entries(raw.lineSources || {}).filter(
      ([key, value]) => /^line-[12456]$/.test(key) && value && typeof value === 'object'
    ).map(([key, value]) => [key, {
      source: ['ntas', 'schedule'].includes(value.source) ? value.source : null,
      reason: asString(value.reason)
    }])),
    fallback: raw.fallback === true,
    trains
  };
};
